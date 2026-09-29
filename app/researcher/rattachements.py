"""Réponse du Chercheur aux invitations reçues (Étape 17)."""

import uuid

from sqlmodel import Session, col, select

from app.auth.models import ChercheurInstitution, User
from app.core.database import utcnow
from app.core.enums import StatutRattachement
from app.core.exceptions import NotFoundError, ValidationError
from app.core.notifications import notifier


def lister_mes_rattachements(session: Session, chercheur_id: uuid.UUID) -> list[ChercheurInstitution]:
    return list(
        session.exec(
            select(ChercheurInstitution).where(col(ChercheurInstitution.chercheur_id) == chercheur_id)
        ).all()
    )


def _rattachement_du_chercheur(
    session: Session, chercheur_id: uuid.UUID, rattachement_id: uuid.UUID
) -> ChercheurInstitution:
    rattachement = session.get(ChercheurInstitution, rattachement_id)
    if rattachement is None or rattachement.chercheur_id != chercheur_id:
        raise NotFoundError("Rattachement introuvable.", code="rattachement_introuvable")
    return rattachement


def _repondre(
    session: Session,
    chercheur_id: uuid.UUID,
    rattachement_id: uuid.UUID,
    statut: StatutRattachement,
) -> ChercheurInstitution:
    rattachement = _rattachement_du_chercheur(session, chercheur_id, rattachement_id)
    if rattachement.statut != StatutRattachement.EN_ATTENTE:
        raise ValidationError(
            "Cette invitation a déjà reçu une réponse.", code="invitation_deja_traitee"
        )
    rattachement.statut = statut
    rattachement.date_reponse = utcnow()
    session.add(rattachement)

    chercheur = session.get(User, chercheur_id)
    if chercheur is not None:
        type_notification = (
            "RATTACHEMENT_ACCEPTE" if statut == StatutRattachement.ACCEPTE else "RATTACHEMENT_REFUSE"
        )
        libelle = "accepté" if statut == StatutRattachement.ACCEPTE else "refusé"
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
) -> ChercheurInstitution:
    return _repondre(session, chercheur_id, rattachement_id, StatutRattachement.ACCEPTE)


def refuser_invitation(
    session: Session, chercheur_id: uuid.UUID, rattachement_id: uuid.UUID
) -> ChercheurInstitution:
    return _repondre(session, chercheur_id, rattachement_id, StatutRattachement.REFUSE)
