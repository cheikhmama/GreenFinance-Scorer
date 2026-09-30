"""Réponse du Chercheur aux invitations reçues (Étape 17)."""

import uuid

from sqlmodel import Session, col, select

from app.auth.models import ResearcherAffiliation, User
from app.core.database import utcnow
from app.core.enums import AffiliationStatus
from app.core.exceptions import NotFoundError, ValidationError
from app.core.notifications import notifier


def lister_mes_rattachements(session: Session, chercheur_id: uuid.UUID) -> list[ResearcherAffiliation]:
    return list(
        session.exec(
            select(ResearcherAffiliation).where(col(ResearcherAffiliation.researcher_id) == chercheur_id)
        ).all()
    )


def _rattachement_du_chercheur(
    session: Session, chercheur_id: uuid.UUID, rattachement_id: uuid.UUID
) -> ResearcherAffiliation:
    rattachement = session.get(ResearcherAffiliation, rattachement_id)
    if rattachement is None or rattachement.researcher_id != chercheur_id:
        raise NotFoundError("Rattachement introuvable.", code="rattachement_introuvable")
    return rattachement


def _repondre(
    session: Session,
    chercheur_id: uuid.UUID,
    rattachement_id: uuid.UUID,
    statut: AffiliationStatus,
) -> ResearcherAffiliation:
    rattachement = _rattachement_du_chercheur(session, chercheur_id, rattachement_id)
    if rattachement.status != AffiliationStatus.EN_ATTENTE:
        raise ValidationError(
            "Cette invitation a déjà reçu une réponse.", code="invitation_deja_traitee"
        )
    rattachement.status = statut
    rattachement.responded_at = utcnow()
    session.add(rattachement)

    chercheur = session.get(User, chercheur_id)
    if chercheur is not None:
        type_notification = (
            "RATTACHEMENT_ACCEPTE" if statut == AffiliationStatus.ACCEPTE else "RATTACHEMENT_REFUSE"
        )
        libelle = "accepté" if statut == AffiliationStatus.ACCEPTE else "refusé"
        notifier(
            session,
            rattachement.institution_id,
            type_notification,
            f"{chercheur.name or chercheur.email} a {libelle} votre invitation.",
        )

    session.commit()
    session.refresh(rattachement)
    return rattachement


def accepter_invitation(
    session: Session, chercheur_id: uuid.UUID, rattachement_id: uuid.UUID
) -> ResearcherAffiliation:
    return _repondre(session, chercheur_id, rattachement_id, AffiliationStatus.ACCEPTE)


def refuser_invitation(
    session: Session, chercheur_id: uuid.UUID, rattachement_id: uuid.UUID
) -> ResearcherAffiliation:
    return _repondre(session, chercheur_id, rattachement_id, AffiliationStatus.REFUSE)
