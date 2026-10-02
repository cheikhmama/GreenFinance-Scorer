"""Validation des inscriptions d'entreprises par l'Administrateur (tâche 1.4, décision D5).

Une inscription publique (app/company/registration.py) attend en PENDING_ONBOARDING (ou
INFO_REQUESTED). Trois décisions (tâche 5.3 : la fenêtre KYC les présente avec les contrôles
d'app/admin/kyc.py),
chacune dans une seule transaction, l'entreprise verrouillée (SELECT ... FOR UPDATE) pour que deux
Administrateurs ne décident jamais deux fois :

- VALIDER : l'entreprise passe ACTIVE (onboarded_at / onboarded_by_id renseignés) et le lien
  d'activation part vers le titulaire — c'est seulement maintenant qu'il peut créer son mot de
  passe (app/auth/activation.py). Jeton et changement de statut commitent ensemble.
- DEMANDER DES INFORMATIONS : la demande passe INFO_REQUESTED avec le message de l'Administrateur ;
  un nouveau lien de suivi (l'ancien jeton n'est connu que par son empreinte) part avec le message,
  et le demandeur répond depuis sa page de suivi (nouvelle lettre de mandat, message).
- REFUSER : l'inscription passe REJECTED avec son motif (tâche 5.2 : plus supprimée), le compte
  titulaire — qui n'a jamais eu de mot de passe — est désactivé, le motif est envoyé au demandeur
  et reste lisible sur sa page de suivi. Une nouvelle demande aux mêmes identifiants rouvre cette
  même inscription (app/company/registration.py).

Aucune donnée financière n'est exigée pour valider (ISIN/LEI, chiffre d'affaires, EVIC) : beaucoup
d'entreprises non cotées n'en ont pas. L'Administrateur peut compléter le profil avant de valider
(PATCH /admin/entreprises/{id}) ; le module carbone (tâche 2.3) signalera les données manquantes
quand il en aura besoin.
"""

import uuid

import structlog
from fastapi import BackgroundTasks
from sqlmodel import Session, col, select

from app.admin.schemas import (
    CompanyOnboardingResult,
    OnboardingDecision,
    PendingRegistration,
)
from app.auth.activation import envoyer_lien_activation
from app.auth.models import User
from app.company.models import Company
from app.company.registration import (
    STATUTS_EN_EXAMEN,
    lien_de_suivi,
    nouveau_jeton_de_suivi,
)
from app.core.audit import auditer
from app.core.database import utcnow
from app.core.email import (
    EmailDeliveryError,
    ensure_email_configured,
    envoyer_email_differe,
)
from app.core.enums import RegistrationStatus
from app.core.exceptions import NotFoundError, ServiceUnavailableError, ValidationError

logger = structlog.get_logger(__name__)


def _prevenir_refus(email: str, nom_entreprise: str, motif: str) -> None:
    try:
        envoyer_email_differe(
            recipient=email,
            subject="Votre demande d'inscription — GreenFinance-Scorer",
            body=(
                f"Nous ne pouvons pas donner suite à la demande d'inscription de {nom_entreprise}."
                f"\n\nMotif : {motif}\n\nVous pouvez déposer une nouvelle demande avec les "
                "mêmes identifiants, ou nous écrire via le formulaire de contact.\n"
            ),
        )
    except EmailDeliveryError as exc:
        logger.error("onboarding_rejection_notice_failed", error_type=type(exc.__cause__ or exc).__name__)


def _demander_informations(email: str, nom_entreprise: str, message: str, jeton: str) -> None:
    try:
        envoyer_email_differe(
            recipient=email,
            subject="Votre demande d'inscription — informations demandées",
            body=(
                f"Pour poursuivre l'examen de la demande d'inscription de {nom_entreprise}, nous "
                f"avons besoin d'informations complémentaires :\n\n{message}\n\n"
                "Répondez depuis votre page de suivi (nouvelle lettre de mandat, message) :\n"
                f"{lien_de_suivi(jeton)}\n\n"
                "Ce lien remplace celui reçu précédemment.\n"
            ),
        )
    except EmailDeliveryError as exc:
        logger.error("onboarding_info_request_notice_failed", error_type=type(exc.__cause__ or exc).__name__)


def lister_inscriptions_a_examiner(session: Session) -> list[PendingRegistration]:
    """Inscriptions confirmées qui attendent une décision (PENDING_ONBOARDING, INFO_REQUESTED), la
    plus ancienne d'abord (tâche 5.11). Une demande dont l'adresse n'est pas encore confirmée
    n'y figure pas : elle n'a pas encore été transmise."""
    lignes = session.exec(
        select(Company, User)
        .join(User, col(User.id) == col(Company.owner_user_id), isouter=True)
        .where(col(Company.status).in_(STATUTS_EN_EXAMEN))
        .order_by(col(Company.registered_at).asc().nulls_last(), col(Company.name))
    ).all()
    return [
        PendingRegistration(
            company_id=entreprise.id,
            company_name=entreprise.name,
            sector=entreprise.sector,
            country=entreprise.country,
            status=entreprise.status,
            registered_at=entreprise.registered_at,
            contact_name=titulaire.name if titulaire else None,
            contact_email=titulaire.email if titulaire else None,
            tax_id=entreprise.tax_id,
            tax_id_type=entreprise.tax_id_type,
        )
        for entreprise, titulaire in lignes
    ]


def decider_inscription(
    session: Session,
    acteur_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    decision: OnboardingDecision,
    motif: str | None,
    background_tasks: BackgroundTasks,
    message: str | None = None,
) -> CompanyOnboardingResult:
    entreprise = session.get(Company, entreprise_id, with_for_update=True)
    if entreprise is None:
        raise NotFoundError("Entreprise introuvable.", code="entreprise_introuvable")
    if entreprise.status not in STATUTS_EN_EXAMEN:
        raise ValidationError(
            "Cette entreprise n'a pas d'inscription en attente.", code="transition_invalide"
        )
    titulaire = session.get(User, entreprise.owner_user_id) if entreprise.owner_user_id else None
    if titulaire is None:
        # Une inscription publique crée toujours son titulaire : état incohérent, jamais une
        # validation « à l'aveugle » dont personne ne recevrait le lien.
        raise ValidationError(
            "Cette inscription n'a pas de compte titulaire.", code="titulaire_manquant"
        )
    try:
        ensure_email_configured()
    except EmailDeliveryError as exc:
        raise ServiceUnavailableError(
            "L'envoi d'e-mails est indisponible : réessayez plus tard."
        ) from exc

    if decision == OnboardingDecision.APPROVE:
        entreprise.status = RegistrationStatus.ACTIVE
        entreprise.onboarded_at = utcnow()
        entreprise.onboarded_by_id = acteur_id
        session.add(entreprise)
        envoyer_lien_activation(session, titulaire, background_tasks)
        auditer(session, acteur_id, "registration_approved", "Company", entreprise.id, "success")
        session.commit()
        logger.info("company_onboarded", company_id=str(entreprise.id))
        return CompanyOnboardingResult(
            company_id=entreprise.id,
            decision=decision,
            status=entreprise.status,
            onboarded_at=entreprise.onboarded_at,
        )

    if decision == OnboardingDecision.REQUEST_INFO:
        assert message is not None  # garanti par CompanyOnboardingRequest
        entreprise.status = RegistrationStatus.INFO_REQUESTED
        entreprise.info_request_message = message
        entreprise.info_requested_at = utcnow()
        entreprise.info_response_message = None
        jeton = nouveau_jeton_de_suivi(entreprise)
        session.add(entreprise)
        auditer(
            session,
            acteur_id,
            "registration_info_requested",
            "Company",
            entreprise.id,
            "success",
            new_value=message,
        )
        session.commit()
        background_tasks.add_task(
            _demander_informations, titulaire.email, entreprise.name, message, jeton
        )
        logger.info("company_registration_info_requested", company_id=str(entreprise_id))
        return CompanyOnboardingResult(
            company_id=entreprise_id,
            decision=decision,
            status=RegistrationStatus.INFO_REQUESTED,
            onboarded_at=None,
        )

    assert motif is not None  # garanti par CompanyOnboardingRequest
    entreprise.status = RegistrationStatus.REJECTED
    entreprise.rejection_reason = motif
    entreprise.rejected_at = utcnow()
    session.add(entreprise)
    titulaire.active = False
    session.add(titulaire)
    auditer(
        session,
        acteur_id,
        "registration_rejected",
        "Company",
        entreprise.id,
        "success",
        new_value=motif,
    )
    session.commit()
    background_tasks.add_task(_prevenir_refus, titulaire.email, entreprise.name, motif)
    logger.info("company_registration_rejected", company_id=str(entreprise_id))
    return CompanyOnboardingResult(
        company_id=entreprise_id,
        decision=decision,
        status=RegistrationStatus.REJECTED,
        onboarded_at=None,
    )
