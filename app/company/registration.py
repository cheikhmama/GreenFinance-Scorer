"""Inscription publique d'une entreprise (tâche 1.3, décision D5 : validation par l'Administrateur).

Une demande crée, dans une seule transaction :
- l'entreprise, en PENDING_ONBOARDING — invisible des autres rôles, sans dépôt de rapport possible ;
- son compte titulaire (ENTERPRISE), SANS mot de passe et sans lien d'activation : le lien n'est
  envoyé qu'à la validation par l'Administrateur (tâche 1.4), si bien que personne ne peut se
  connecter à une entreprise non validée ;
- une notification à chaque Administrateur actif, et une entrée du journal d'audit.

Réponse uniforme (202) dès que le formulaire est bien formé, que la demande aboutisse ou non :
comme pour « mot de passe oublié », un e-mail, un ISIN ou un LEI déjà connus ne doivent jamais se
lire dans la réponse HTTP (ce serait révéler quels comptes et quelles entreprises existent, y
compris celles encore en attente). Le demandeur est informé par e-mail, après la réponse.

Protections contre l'abus : limite par adresse IP (même règle que le formulaire de contact —
l'IP vient du serveur ASGI, jamais d'un en-tête lu directement) et champ piège `company_fax`.
Aucun CAPTCHA : il supposerait un service tiers, à décider avant la mise en production.
"""

import hashlib

import redis
import structlog
from fastapi import BackgroundTasks
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, or_, select

from app.auth.models import User
from app.company.models import Company
from app.company.schemas import CompanyRegistrationRequest
from app.core.audit import auditer
from app.core.email import EmailDeliveryError, ensure_email_configured, send_email
from app.core.enums import CompanyStatus, Role
from app.core.exceptions import ServiceUnavailableError, TooManyRequestsError
from app.core.notifications import notifier
from app.core.redis import get_redis_client, incrementer_fenetre

logger = structlog.get_logger(__name__)

MAX_DEMANDES_PAR_IP = 3
FENETRE_SECONDES = 60 * 60


def _limiter_par_ip(adresse_ip: str) -> None:
    cle = f"company_registrations:{hashlib.sha256(adresse_ip.encode()).hexdigest()}"
    try:
        demandes = incrementer_fenetre(get_redis_client(), cle, FENETRE_SECONDES)
    except redis.RedisError as exc:
        logger.error("company_registration_rate_limit_unavailable", error_type=type(exc).__name__)
        raise ServiceUnavailableError(
            "Le service d'inscription est temporairement indisponible. Réessayez plus tard."
        ) from exc
    if demandes > MAX_DEMANDES_PAR_IP:
        raise TooManyRequestsError("Trop de demandes d'inscription. Réessayez dans une heure.")


def _envoyer(destinataire: str, sujet: str, corps: str, evenement: str) -> None:
    try:
        send_email(recipient=destinataire, subject=sujet, body=corps)
    except EmailDeliveryError as exc:
        # Jamais l'adresse ni le contenu dans les logs.
        logger.error(evenement, error_type=type(exc.__cause__ or exc).__name__)


def _accuse_de_reception(email: str, nom_entreprise: str) -> None:
    _envoyer(
        email,
        "Demande d'inscription reçue — GreenFinance-Scorer",
        (
            f"Nous avons bien reçu la demande d'inscription de {nom_entreprise}.\n\n"
            "Un administrateur va l'examiner. Vous recevrez un lien pour créer votre mot de passe "
            "dès que votre entreprise aura été validée.\n"
        ),
        "company_registration_ack_failed",
    )


def _demande_non_aboutie(email: str) -> None:
    _envoyer(
        email,
        "Demande d'inscription — GreenFinance-Scorer",
        (
            "Nous n'avons pas pu enregistrer votre demande d'inscription : cette adresse e-mail, "
            "cet ISIN ou ce LEI est déjà associé à la plateforme.\n\n"
            "Si vous avez déjà un compte, utilisez « Mot de passe oublié » sur la page de "
            "connexion. Sinon, contactez-nous via le formulaire de contact.\n"
        ),
        "company_registration_conflict_notice_failed",
    )


def _deja_connu(session: Session, demande: CompanyRegistrationRequest) -> bool:
    if session.exec(select(User.id).where(col(User.email) == demande.contact_email)).first():
        return True
    identifiants = [
        condition
        for condition in (
            col(Company.isin) == demande.isin if demande.isin else None,
            col(Company.lei) == demande.lei if demande.lei else None,
        )
        if condition is not None
    ]
    return bool(identifiants) and session.exec(
        select(Company.id).where(or_(*identifiants))
    ).first() is not None


def enregistrer_demande(
    session: Session,
    demande: CompanyRegistrationRequest,
    adresse_ip: str | None,
    background_tasks: BackgroundTasks,
) -> None:
    if demande.company_fax:
        # Champ piège rempli : réponse identique, rien d'enregistré, rien d'envoyé.
        logger.warning("company_registration_honeypot")
        return

    _limiter_par_ip(adresse_ip or "inconnue")
    try:
        ensure_email_configured()
    except EmailDeliveryError as exc:
        raise ServiceUnavailableError(
            "Le service d'inscription est temporairement indisponible. Réessayez plus tard."
        ) from exc

    if _deja_connu(session, demande):
        background_tasks.add_task(_demande_non_aboutie, demande.contact_email)
        return

    titulaire = User(
        email=demande.contact_email,
        name=demande.contact_name,
        role=Role.ENTERPRISE,
        active=True,
        password_hash=None,
    )
    session.add(titulaire)
    session.flush()
    entreprise = Company(
        name=demande.company_name,
        sector=demande.sector,
        country=demande.country,
        isin=demande.isin,
        lei=demande.lei,
        website=demande.website,
        status=CompanyStatus.PENDING_ONBOARDING,
        owner_user_id=titulaire.id,
    )
    session.add(entreprise)
    session.flush()

    auditer(session, None, "inscription_entreprise", "Entreprise", entreprise.id, "succes")
    admins = session.exec(
        select(User).where(col(User.role) == Role.ADMIN, col(User.active).is_(True))
    ).all()
    for admin in admins:
        notifier(
            session,
            admin.id,
            "ENTREPRISE_INSCRITE",
            f"{entreprise.name} demande à rejoindre la plateforme : inscription à valider.",
            id_ressource=entreprise.id,
        )

    try:
        session.commit()
    except IntegrityError:
        # Course : une autre demande a pris le même e-mail / ISIN / LEI entre la vérification et
        # le commit — même issue qu'un doublon détecté plus haut, jamais une 500.
        session.rollback()
        background_tasks.add_task(_demande_non_aboutie, demande.contact_email)
        return

    logger.info("company_registration_received", company_id=str(entreprise.id))
    background_tasks.add_task(_accuse_de_reception, demande.contact_email, demande.company_name)
