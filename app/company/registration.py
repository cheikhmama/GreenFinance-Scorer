"""Inscription publique d'une entreprise (tâches 1.3 et 5.2, décision D5 : validation par
l'Administrateur).

Une demande crée, dans une seule transaction :
- l'entreprise, en PENDING_ONBOARDING — invisible des autres rôles, sans dépôt de rapport possible —
  avec sa lettre de mandat (PDF, obligatoire) ;
- son compte titulaire (ENTERPRISE), SANS mot de passe et sans lien d'activation : le lien n'est
  envoyé qu'à la validation par l'Administrateur, si bien que personne ne peut se connecter à une
  entreprise non validée ;
- un jeton de suivi : seule son empreinte est stockée, le jeton part dans l'accusé de réception et
  ouvre la page de suivi publique (statut, demande d'informations, motif de refus) ;
- une notification à chaque Administrateur actif, et une entrée du journal d'audit.

Réponse uniforme (202) dès que le formulaire est bien formé, que la demande aboutisse ou non :
comme pour « mot de passe oublié », un e-mail, un ISIN ou un LEI déjà connus ne doivent jamais se
lire dans la réponse HTTP (ce serait révéler quels comptes et quelles entreprises existent, y
compris celles encore en attente). Le demandeur est informé par e-mail, après la réponse — c'est
aussi pourquoi le jeton de suivi n'est jamais renvoyé dans la réponse.

Une demande refusée est conservée (REJECTED, motif). Une nouvelle demande portant les mêmes
identifiants (e-mail, ISIN, LEI) rouvre cette même demande plutôt que d'en créer une seconde —
sauf si l'un d'eux appartient à autre chose qu'elle, auquel cas elle n'aboutit pas.

Protections contre l'abus : limite par adresse IP (même règle que le formulaire de contact —
l'IP vient du serveur ASGI, jamais d'un en-tête lu directement) et champ piège `company_fax`.
Aucun CAPTCHA : il supposerait un service tiers, à décider avant la mise en production.
"""

import hashlib
import secrets
import uuid

import redis
import structlog
from fastapi import BackgroundTasks
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, and_, col, or_, select

from app.auth.models import User
from app.company.models import Company
from app.company.schemas import CompanyRegistrationRequest, RegistrationStatusView
from app.company.upload_validation import TAILLE_MAX_MANDAT_OCTETS, valider_pdf
from app.company.verification_email import emettre_code, envoyer_code, verifier_code
from app.core.audit import auditer
from app.core.config import get_settings
from app.core.database import utcnow
from app.core.email import (
    EmailDeliveryError,
    ensure_email_configured,
    envoyer_email_differe,
)
from app.core.enums import RegistrationStatus, Role
from app.core.exceptions import (
    NotFoundError,
    ServiceUnavailableError,
    TooManyRequestsError,
    ValidationError,
)
from app.core.notifications import notifier
from app.core.redis import get_redis_client, incrementer_fenetre
from app.core.storage import save_bytes

logger = structlog.get_logger(__name__)

MAX_DEMANDES_PAR_IP = 3
FENETRE_SECONDES = 60 * 60
# Demande qui attend une décision de l'Administrateur.
STATUTS_EN_EXAMEN = (RegistrationStatus.PENDING_ONBOARDING, RegistrationStatus.INFO_REQUESTED)
# Demandes qu'une nouvelle inscription avec les mêmes identifiants reprend : refusée, ou jamais
# confirmée par son code (tâche 5.11).
STATUTS_REOUVRABLES = (RegistrationStatus.REJECTED, RegistrationStatus.EMAIL_VERIFICATION_PENDING)


def _limiter_par_ip(adresse_ip: str, prefixe: str = "company_registrations") -> None:
    cle = f"{prefixe}:{hashlib.sha256(adresse_ip.encode()).hexdigest()}"
    try:
        demandes = incrementer_fenetre(get_redis_client(), cle, FENETRE_SECONDES)
    except redis.RedisError as exc:
        logger.error("company_registration_rate_limit_unavailable", error_type=type(exc).__name__)
        raise ServiceUnavailableError(
            "Le service d'inscription est temporairement indisponible. Réessayez plus tard."
        ) from exc
    if demandes > MAX_DEMANDES_PAR_IP:
        raise TooManyRequestsError("Trop de demandes d'inscription. Réessayez dans une heure.")


def _verifier_envoi_possible() -> None:
    try:
        ensure_email_configured()
    except EmailDeliveryError as exc:
        raise ServiceUnavailableError(
            "Le service d'inscription est temporairement indisponible. Réessayez plus tard."
        ) from exc


def _empreinte(jeton: str) -> str:
    return hashlib.sha256(jeton.encode()).hexdigest()


def nouveau_jeton_de_suivi(entreprise: Company) -> str:
    """Remplace le jeton de suivi de l'entreprise (l'ancien cesse de fonctionner) et renvoie le
    nouveau, en clair, à n'envoyer que par e-mail. Ne commite pas."""
    jeton = secrets.token_urlsafe(32)
    entreprise.status_token_hash = _empreinte(jeton)
    return jeton


def lien_de_suivi(jeton: str) -> str:
    base_url = get_settings().frontend_base_url.rstrip("/")
    return f"{base_url}/inscription-entreprise/suivi?token={jeton}"


def _envoyer(destinataire: str, sujet: str, corps: str, evenement: str) -> None:
    try:
        envoyer_email_differe(recipient=destinataire, subject=sujet, body=corps)
    except EmailDeliveryError as exc:
        # Jamais l'adresse ni le contenu dans les logs.
        logger.error(evenement, error_type=type(exc.__cause__ or exc).__name__)


def _accuse_de_reception(email: str, nom_entreprise: str, jeton: str) -> None:
    _envoyer(
        email,
        "Demande d'inscription reçue — GreenFinance-Scorer",
        (
            f"Nous avons bien reçu la demande d'inscription de {nom_entreprise}.\n\n"
            "Un administrateur va l'examiner. Vous recevrez un lien pour créer votre mot de passe "
            "dès que votre entreprise aura été validée.\n\n"
            "Suivez votre demande, et répondez à une éventuelle demande d'informations, ici :\n"
            f"{lien_de_suivi(jeton)}\n\n"
            "Ce lien est personnel : ne le partagez pas.\n"
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


class _Conflit:
    """Un identifiant de la demande appartient à autre chose qu'une demande refusée."""


_CONFLIT = _Conflit()


def _demande_existante(
    session: Session, demande: CompanyRegistrationRequest
) -> Company | _Conflit | None:
    """None : rien de connu, nouvelle demande. Une Company REJECTED : la demande à rouvrir.
    _CONFLIT : un identifiant est déjà pris ailleurs (compte d'un autre rôle, autre entreprise,
    demande en cours ou entreprise validée)."""
    entreprises: dict[uuid.UUID, Company] = {}
    utilisateur = session.exec(select(User).where(col(User.email) == demande.contact_email)).first()
    if utilisateur is not None:
        possedee = session.exec(
            select(Company).where(col(Company.owner_user_id) == utilisateur.id)
        ).first()
        if possedee is None:
            return _CONFLIT
        entreprises[possedee.id] = possedee
    identifiants = [
        condition
        for condition in (
            col(Company.isin) == demande.isin if demande.isin else None,
            col(Company.lei) == demande.lei if demande.lei else None,
            # Identifiant fiscal (tâche 5.10) : unique dans son pays.
            and_(col(Company.country) == demande.country, col(Company.tax_id) == demande.tax_id),
        )
        if condition is not None
    ]
    if identifiants:
        for entreprise in session.exec(select(Company).where(or_(*identifiants))).all():
            entreprises[entreprise.id] = entreprise
    if not entreprises:
        return None
    if len(entreprises) == 1:
        (entreprise,) = entreprises.values()
        if entreprise.status in STATUTS_REOUVRABLES:
            return entreprise
    return _CONFLIT


def _enregistrer_mandat(entreprise_id: uuid.UUID, contenu: bytes) -> str:
    # Nom entièrement déterminé par le serveur, comme pour les rapports.
    chemin = f"mandats/{entreprise_id}/{uuid.uuid4()}.pdf"
    try:
        save_bytes(chemin, contenu)
    except OSError as exc:
        raise ValidationError(
            "Le fichier n'a pas pu être enregistré. Réessayez.", code="stockage_echoue"
        ) from exc
    return chemin


def _notifier_admins(session: Session, type_notification: str, message: str, entreprise: Company) -> None:
    admins = session.exec(
        select(User).where(col(User.role) == Role.ADMIN, col(User.active).is_(True))
    ).all()
    for admin in admins:
        notifier(session, admin.id, type_notification, message, id_ressource=entreprise.id)


def _titulaire_de_la_demande_rouverte(
    session: Session, entreprise: Company, demande: CompanyRegistrationRequest
) -> User:
    """Titulaire d'une demande refusée : jamais activé (pas de mot de passe), il reprend l'adresse
    et le nom de la nouvelle demande. Recréé s'il n'existe plus."""
    titulaire = session.get(User, entreprise.owner_user_id) if entreprise.owner_user_id else None
    if titulaire is None:
        titulaire = User(email=demande.contact_email, role=Role.ENTERPRISE, password_hash=None)
        session.add(titulaire)
        session.flush()
        entreprise.owner_user_id = titulaire.id
    titulaire.email = demande.contact_email
    titulaire.name = demande.contact_name
    titulaire.active = True
    session.add(titulaire)
    return titulaire


def enregistrer_demande(
    session: Session,
    demande: CompanyRegistrationRequest,
    lettre_de_mandat: bytes,
    adresse_ip: str | None,
    background_tasks: BackgroundTasks,
) -> None:
    if demande.company_fax:
        # Champ piège rempli : réponse identique, rien d'enregistré, rien d'envoyé.
        logger.warning("company_registration_honeypot")
        return

    _limiter_par_ip(adresse_ip or "inconnue")
    _verifier_envoi_possible()
    # Le fichier se valide avant toute recherche : son refus ne dit rien de ce qui existe.
    valider_pdf(lettre_de_mandat, taille_max=TAILLE_MAX_MANDAT_OCTETS)

    existante = _demande_existante(session, demande)
    if isinstance(existante, _Conflit):
        background_tasks.add_task(_demande_non_aboutie, demande.contact_email)
        return

    if existante is None:
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
            owner_user_id=titulaire.id,
        )
        action = "company_registered"
    else:
        entreprise = existante
        _titulaire_de_la_demande_rouverte(session, entreprise, demande)
        entreprise.rejection_reason = None
        entreprise.rejected_at = None
        entreprise.info_request_message = None
        entreprise.info_requested_at = None
        entreprise.info_response_message = None
        action = "registration_resubmitted"

    entreprise.name = demande.company_name
    entreprise.sector = demande.sector
    entreprise.country = demande.country
    entreprise.isin = demande.isin
    entreprise.lei = demande.lei
    entreprise.website = demande.website
    entreprise.tax_id = demande.tax_id
    entreprise.tax_id_type = demande.tax_id_type
    # En attente de la confirmation de l'adresse (tâche 5.11) : la demande n'est transmise — jeton
    # de suivi, Administrateurs prévenus — qu'une fois le code saisi (confirmer_adresse).
    entreprise.status = RegistrationStatus.EMAIL_VERIFICATION_PENDING
    entreprise.email_verified_at = None
    entreprise.status_token_hash = None
    entreprise.registered_at = utcnow()
    session.add(entreprise)
    session.flush()
    code = emettre_code(entreprise)
    entreprise.mandate_letter_path = _enregistrer_mandat(entreprise.id, lettre_de_mandat)
    entreprise.mandate_letter_uploaded_at = utcnow()
    session.add(entreprise)

    auditer(session, None, action, "Company", entreprise.id, "success")

    try:
        session.commit()
    except IntegrityError:
        # Course : une autre demande a pris le même e-mail / ISIN / LEI entre la vérification et
        # le commit — même issue qu'un doublon détecté plus haut, jamais une 500.
        session.rollback()
        background_tasks.add_task(_demande_non_aboutie, demande.contact_email)
        return

    logger.info("company_registration_received", company_id=str(entreprise.id), action=action)
    background_tasks.add_task(envoyer_code, demande.contact_email, demande.company_name, code)


def confirmer_adresse(
    session: Session,
    email: str,
    code: str,
    adresse_ip: str | None,
    background_tasks: BackgroundTasks,
) -> None:
    """Code juste : la demande passe à PENDING_ONBOARDING et part chez l'Administrateur — jeton
    de suivi, accusé de réception avec le lien de suivi, notification (tâche 5.11)."""
    entreprise = verifier_code(session, email, code, adresse_ip)
    entreprise.status = RegistrationStatus.PENDING_ONBOARDING
    jeton = nouveau_jeton_de_suivi(entreprise)
    session.add(entreprise)
    auditer(session, None, "registration_email_verified", "Company", entreprise.id, "success")
    _notifier_admins(
        session,
        "ENTREPRISE_INSCRITE",
        f"{entreprise.name} demande à rejoindre la plateforme : inscription à valider.",
        entreprise,
    )
    session.commit()
    logger.info("company_registration_email_verified", company_id=str(entreprise.id))
    background_tasks.add_task(_accuse_de_reception, email, entreprise.name, jeton)


def _entreprise_du_jeton(session: Session, jeton: str, *, verrouiller: bool = False) -> Company:
    requete = select(Company).where(col(Company.status_token_hash) == _empreinte(jeton))
    if verrouiller:
        requete = requete.with_for_update()
    entreprise = session.exec(requete).first()
    if entreprise is None:
        # Jeton inconnu ou remplacé par un plus récent : même réponse.
        raise NotFoundError("Lien de suivi invalide ou expiré.", code="suivi_introuvable")
    return entreprise


def _vue(entreprise: Company) -> RegistrationStatusView:
    return RegistrationStatusView(
        company_name=entreprise.name,
        status=entreprise.status,
        registered_at=entreprise.registered_at,
        info_request_message=entreprise.info_request_message,
        info_requested_at=entreprise.info_requested_at,
        rejection_reason=entreprise.rejection_reason,
        rejected_at=entreprise.rejected_at,
        can_respond=entreprise.status == RegistrationStatus.INFO_REQUESTED,
    )


def consulter_suivi(session: Session, jeton: str) -> RegistrationStatusView:
    return _vue(_entreprise_du_jeton(session, jeton))


def repondre_demande_infos(
    session: Session,
    jeton: str,
    lettre_de_mandat: bytes,
    message: str | None,
    adresse_ip: str | None,
) -> RegistrationStatusView:
    """Réponse du demandeur à une demande d'informations : nouvelle lettre de mandat (et un
    message facultatif), la demande repasse en examen. Ligne verrouillée : deux envois simultanés
    ne repassent la demande en examen qu'une fois."""
    _limiter_par_ip(adresse_ip or "inconnue", prefixe="company_registration_replies")
    entreprise = _entreprise_du_jeton(session, jeton, verrouiller=True)
    if entreprise.status != RegistrationStatus.INFO_REQUESTED:
        raise ValidationError(
            "Aucune information n'est demandée pour cette inscription.", code="transition_invalide"
        )
    valider_pdf(lettre_de_mandat, taille_max=TAILLE_MAX_MANDAT_OCTETS)
    entreprise.mandate_letter_path = _enregistrer_mandat(entreprise.id, lettre_de_mandat)
    entreprise.mandate_letter_uploaded_at = utcnow()
    entreprise.info_response_message = message
    entreprise.status = RegistrationStatus.PENDING_ONBOARDING
    session.add(entreprise)
    auditer(session, None, "registration_info_provided", "Company", entreprise.id, "success")
    _notifier_admins(
        session,
        "ENTREPRISE_INFOS_COMPLETEES",
        f"{entreprise.name} a répondu à la demande d'informations : inscription à réexaminer.",
        entreprise,
    )
    session.commit()
    session.refresh(entreprise)
    logger.info("company_registration_info_provided", company_id=str(entreprise.id))
    return _vue(entreprise)
