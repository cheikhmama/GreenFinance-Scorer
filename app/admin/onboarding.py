"""Validation des inscriptions d'entreprises par l'Administrateur (tâche 1.4, décision D5).

Une inscription publique (app/company/registration.py) attend en PENDING_ONBOARDING. Deux issues,
chacune dans une seule transaction, l'entreprise verrouillée (SELECT ... FOR UPDATE) pour que deux
Administrateurs ne décident jamais deux fois :

- VALIDER : l'entreprise passe ACTIVE (onboarded_at / onboarded_by_id renseignés) et le lien
  d'activation part vers le titulaire — c'est seulement maintenant qu'il peut créer son mot de
  passe (app/auth/activation.py). Jeton et changement de statut commitent ensemble.
- REFUSER : l'inscription est supprimée (entreprise et compte titulaire, qui n'a jamais eu de mot de
  passe), le motif est envoyé au demandeur. Il peut en déposer une nouvelle ; la trace de la
  décision reste dans le journal d'audit.

Aucune donnée financière n'est exigée pour valider (ISIN/LEI, chiffre d'affaires, EVIC) : beaucoup
d'entreprises non cotées n'en ont pas. L'Administrateur peut compléter le profil avant de valider
(PATCH /admin/entreprises/{id}) ; le module carbone (tâche 2.3) signalera les données manquantes
quand il en aura besoin.
"""

import uuid

import structlog
from fastapi import BackgroundTasks
from sqlmodel import Session

from app.admin.schemas import CompanyOnboardingResult, OnboardingDecision
from app.auth.activation import envoyer_lien_activation
from app.auth.models import User
from app.company.models import Company
from app.core.audit import auditer
from app.core.database import utcnow
from app.core.email import EmailDeliveryError, ensure_email_configured, send_email
from app.core.enums import CompanyStatus
from app.core.exceptions import NotFoundError, ServiceUnavailableError, ValidationError

logger = structlog.get_logger(__name__)


def _prevenir_refus(email: str, nom_entreprise: str, motif: str) -> None:
    try:
        send_email(
            recipient=email,
            subject="Votre demande d'inscription — GreenFinance-Scorer",
            body=(
                f"Nous ne pouvons pas donner suite à la demande d'inscription de {nom_entreprise}."
                f"\n\nMotif : {motif}\n\nVous pouvez déposer une nouvelle demande, ou nous écrire "
                "via le formulaire de contact.\n"
            ),
        )
    except EmailDeliveryError as exc:
        logger.error("onboarding_rejection_notice_failed", error_type=type(exc.__cause__ or exc).__name__)


def decider_inscription(
    session: Session,
    acteur_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    decision: OnboardingDecision,
    motif: str | None,
    background_tasks: BackgroundTasks,
) -> CompanyOnboardingResult:
    entreprise = session.get(Company, entreprise_id, with_for_update=True)
    if entreprise is None:
        raise NotFoundError("Entreprise introuvable.", code="entreprise_introuvable")
    if entreprise.status != CompanyStatus.PENDING_ONBOARDING:
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
        entreprise.status = CompanyStatus.ACTIVE
        entreprise.onboarded_at = utcnow()
        entreprise.onboarded_by_id = acteur_id
        session.add(entreprise)
        envoyer_lien_activation(session, titulaire, background_tasks)
        auditer(session, acteur_id, "validation_inscription", "Entreprise", entreprise.id, "succes")
        session.commit()
        logger.info("company_onboarded", company_id=str(entreprise.id))
        return CompanyOnboardingResult(
            company_id=entreprise.id,
            decision=decision,
            status=entreprise.status,
            onboarded_at=entreprise.onboarded_at,
        )

    assert motif is not None  # garanti par CompanyOnboardingRequest
    email, nom = titulaire.email, entreprise.name
    auditer(
        session,
        acteur_id,
        "refus_inscription",
        "Entreprise",
        entreprise.id,
        "succes",
        nouvelle_valeur=motif,
    )
    session.delete(entreprise)
    session.flush()  # l'entreprise d'abord : elle référence son titulaire
    session.delete(titulaire)
    session.commit()
    background_tasks.add_task(_prevenir_refus, email, nom, motif)
    logger.info("company_registration_rejected", company_id=str(entreprise_id))
    return CompanyOnboardingResult(
        company_id=entreprise_id, decision=decision, status=None, onboarded_at=None
    )
