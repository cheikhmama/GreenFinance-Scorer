"""Demandes d'accès des Investisseurs et des Chercheurs (tâche 5.10).

Même hygiène que l'inscription d'une entreprise (app/company/registration.py) :
- réponse identique que la demande aboutisse ou non ; le demandeur l'apprend par e-mail ;
- limite par adresse IP, champ piège, envoi d'e-mails vérifié avant tout enregistrement ;
- le compte est créé sans mot de passe : aucune connexion possible avant l'approbation, qui
  envoie le lien d'activation (app/auth/activation.py) ;
- une demande refusée se rouvre en redemandant avec la même adresse ; toute autre adresse déjà
  connue de la plateforme n'aboutit pas.
"""

import uuid

import structlog
from fastapi import BackgroundTasks
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.access_requests.models import AccessRequest
from app.access_requests.schemas import (
    AccessDecision,
    AccessRequestCreate,
    AccessRequestView,
    RequestedRole,
)
from app.auth.activation import envoyer_lien_activation
from app.auth.models import User
from app.company.registration import _limiter_par_ip, _verifier_envoi_possible
from app.core.audit import auditer
from app.core.database import utcnow
from app.core.email import (
    EmailDeliveryError,
    ensure_email_configured,
    envoyer_email_differe,
)
from app.core.enums import AccessRequestStatus, Role
from app.core.exceptions import NotFoundError, ServiceUnavailableError, ValidationError
from app.core.notifications import notifier

logger = structlog.get_logger(__name__)

LIBELLES_ROLE = {Role.INVESTOR: "investisseur", Role.RESEARCHER: "chercheur"}


def _envoyer(destinataire: str, sujet: str, corps: str, evenement: str) -> None:
    try:
        envoyer_email_differe(recipient=destinataire, subject=sujet, body=corps)
    except EmailDeliveryError as exc:
        # Jamais l'adresse ni le contenu dans les journaux.
        logger.error(evenement, error_type=type(exc.__cause__ or exc).__name__)


def _accuse_de_reception(email: str, role: Role) -> None:
    _envoyer(
        email,
        "Demande d'accès reçue — GreenFinance-Scorer",
        (
            f"Nous avons bien reçu votre demande d'accès {LIBELLES_ROLE[role]}.\n\n"
            "Un administrateur va l'examiner. Vous recevrez un lien pour créer votre mot de passe "
            "dès que votre compte aura été activé.\n"
        ),
        "access_request_ack_failed",
    )


def _demande_non_aboutie(email: str) -> None:
    _envoyer(
        email,
        "Demande d'accès — GreenFinance-Scorer",
        (
            "Nous n'avons pas pu enregistrer votre demande d'accès : cette adresse e-mail est déjà "
            "associée à la plateforme.\n\n"
            "Si vous avez déjà un compte, utilisez « Mot de passe oublié » sur la page de "
            "connexion. Sinon, contactez-nous via le formulaire de contact.\n"
        ),
        "access_request_conflict_notice_failed",
    )


def _prevenir_refus(email: str, motif: str) -> None:
    _envoyer(
        email,
        "Demande d'accès — GreenFinance-Scorer",
        (
            "Votre demande d'accès n'a pas été retenue.\n\n"
            f"Motif : {motif}\n\n"
            "Vous pouvez présenter une nouvelle demande avec la même adresse e-mail.\n"
        ),
        "access_request_rejection_notice_failed",
    )


def _role(role: RequestedRole) -> Role:
    return Role.INVESTOR if role == RequestedRole.INVESTOR else Role.RESEARCHER


def demander_acces(
    session: Session,
    demande: AccessRequestCreate,
    adresse_ip: str | None,
    background_tasks: BackgroundTasks,
) -> None:
    if demande.website_fax:
        logger.warning("access_request_honeypot")
        return
    _limiter_par_ip(adresse_ip or "inconnue", prefixe="access_requests")
    _verifier_envoi_possible()

    role = _role(demande.role)
    utilisateur = session.exec(select(User).where(col(User.email) == demande.email)).first()
    if utilisateur is None:
        utilisateur = User(
            email=demande.email,
            name=demande.full_name,
            role=role,
            active=True,
            password_hash=None,
        )
        session.add(utilisateur)
        session.flush()
        acces = AccessRequest(user_id=utilisateur.id, role=role, organization=demande.organization)
        action = "access_requested"
    else:
        existante = session.exec(
            select(AccessRequest).where(col(AccessRequest.user_id) == utilisateur.id)
        ).first()
        if existante is None or existante.status != AccessRequestStatus.REJECTED:
            background_tasks.add_task(_demande_non_aboutie, demande.email)
            return
        # Demande refusée : rouverte, compte jamais activé repris (rôle compris).
        acces = existante
        utilisateur.name = demande.full_name
        utilisateur.role = role
        utilisateur.active = True
        session.add(utilisateur)
        acces.role = role
        acces.organization = demande.organization
        acces.rejection_reason = None
        acces.decided_at = None
        acces.decided_by_id = None
        action = "access_request_resubmitted"

    acces.investor_type = demande.investor_type
    acces.research_domain = demande.research_domain
    acces.status = AccessRequestStatus.PENDING_APPROVAL
    acces.requested_at = utcnow()
    session.add(acces)
    session.flush()

    auditer(session, None, action, "User", utilisateur.id, "success")
    for admin in session.exec(
        select(User).where(col(User.role) == Role.ADMIN, col(User.active).is_(True))
    ).all():
        notifier(
            session,
            admin.id,
            "DEMANDE_ACCES",
            f"{demande.full_name} ({demande.organization}) demande un accès "
            f"{LIBELLES_ROLE[role]} : à valider.",
            id_ressource=acces.id,
        )
    try:
        session.commit()
    except IntegrityError:
        # Course : la même adresse a été prise entre la vérification et le commit.
        session.rollback()
        background_tasks.add_task(_demande_non_aboutie, demande.email)
        return
    logger.info("access_request_received", access_request_id=str(acces.id), action=action)
    background_tasks.add_task(_accuse_de_reception, demande.email, role)


def _vue(acces: AccessRequest, utilisateur: User) -> AccessRequestView:
    return AccessRequestView(
        id=acces.id,
        user_id=utilisateur.id,
        role=acces.role,
        full_name=utilisateur.name,
        email=utilisateur.email,
        organization=acces.organization,
        investor_type=acces.investor_type,
        research_domain=acces.research_domain,
        status=acces.status,
        requested_at=acces.requested_at,
        decided_at=acces.decided_at,
        rejection_reason=acces.rejection_reason,
    )


def lister_demandes(
    session: Session, statut: AccessRequestStatus | None
) -> list[AccessRequestView]:
    requete = select(AccessRequest, User).where(col(AccessRequest.user_id) == col(User.id))
    if statut is not None:
        requete = requete.where(col(AccessRequest.status) == statut)
    lignes = session.exec(requete.order_by(col(AccessRequest.requested_at).desc())).all()
    return [_vue(acces, utilisateur) for acces, utilisateur in lignes]


def decider_demande(
    session: Session,
    acteur_id: uuid.UUID,
    demande_id: uuid.UUID,
    decision: AccessDecision,
    motif: str | None,
    background_tasks: BackgroundTasks,
) -> AccessRequestView:
    acces = session.get(AccessRequest, demande_id, with_for_update=True)
    if acces is None:
        raise NotFoundError("Demande introuvable.", code="demande_introuvable")
    if acces.status != AccessRequestStatus.PENDING_APPROVAL:
        raise ValidationError("Cette demande a déjà été traitée.", code="transition_invalide")
    utilisateur = session.get(User, acces.user_id)
    assert utilisateur is not None  # FK NOT NULL, CASCADE
    try:
        ensure_email_configured()
    except EmailDeliveryError as exc:
        raise ServiceUnavailableError(
            "L'envoi d'e-mails est indisponible : réessayez plus tard."
        ) from exc

    acces.decided_at = utcnow()
    acces.decided_by_id = acteur_id
    if decision == AccessDecision.APPROVE:
        acces.status = AccessRequestStatus.APPROVED
        session.add(acces)
        envoyer_lien_activation(session, utilisateur, background_tasks)
        auditer(session, acteur_id, "access_request_approved", "User", utilisateur.id, "success")
    else:
        assert motif is not None  # garanti par AccessDecisionRequest
        acces.status = AccessRequestStatus.REJECTED
        acces.rejection_reason = motif
        utilisateur.active = False
        session.add_all([acces, utilisateur])
        auditer(session, acteur_id, "access_request_rejected", "User", utilisateur.id, "success")
        background_tasks.add_task(_prevenir_refus, utilisateur.email, motif)
    session.commit()
    session.refresh(acces)
    logger.info("access_request_decided", access_request_id=str(acces.id), decision=decision.value)
    return _vue(acces, utilisateur)
