"""Gestion des rattachements Institution<->Chercheur (invitations) — Étape 17.

Sert aussi de brique de sélection parmi les acteurs existants (même principe que
app/admin/utilisateurs.py) : une Institution invite toujours un compte CHERCHEUR déjà enregistré
et actif, jamais une identité saisie librement.
"""

import uuid

from sqlmodel import Session, col, select

from app.auth.models import ResearcherAffiliation, User
from app.core.database import utcnow
from app.core.enums import AffiliationStatus, Role
from app.core.exceptions import ValidationError
from app.core.notifications import notifier


def lister_chercheurs_disponibles(session: Session, institution_id: uuid.UUID) -> list[User]:
    """Comptes CHERCHEUR actifs jamais encore invités par cette institution — un rattachement
    REFUSE se réinvite via inviter_chercheur (qui remet le même enregistrement à EN_ATTENTE),
    pas via cette liste."""
    deja_rattaches = select(ResearcherAffiliation.researcher_id).where(
        ResearcherAffiliation.institution_id == institution_id
    )
    return list(
        session.exec(
            select(User).where(
                col(User.role) == Role.RESEARCHER,
                col(User.active).is_(True),
                col(User.id).not_in(deja_rattaches),
            )
        ).all()
    )


def _notifier_invitation(session: Session, institution_id: uuid.UUID, chercheur_id: uuid.UUID) -> None:
    institution = session.get(User, institution_id)
    if institution is not None:
        notifier(
            session,
            chercheur_id,
            "RATTACHEMENT_INVITATION",
            f"{institution.name or institution.email} vous invite à rejoindre ses projets.",
        )


def inviter_chercheur(
    session: Session,
    institution_id: uuid.UUID,
    chercheur_id: uuid.UUID,
    conditions_collaboration: str | None = None,
) -> ResearcherAffiliation:
    chercheur = session.get(User, chercheur_id)
    if chercheur is None or chercheur.role != Role.RESEARCHER or not chercheur.active:
        raise ValidationError("Chercheur invalide.", code="chercheur_invalide")

    existant = session.exec(
        select(ResearcherAffiliation).where(
            ResearcherAffiliation.institution_id == institution_id,
            ResearcherAffiliation.researcher_id == chercheur_id,
        )
    ).first()
    if existant is not None:
        if existant.status != AffiliationStatus.REFUSE:
            raise ValidationError(
                "Ce chercheur est déjà invité ou rattaché.", code="rattachement_existant"
            )
        # Réinvitation après un refus : même ligne, jamais un doublon (voir uq_chercheur_institution).
        existant.status = AffiliationStatus.EN_ATTENTE
        existant.invited_at = utcnow()
        existant.responded_at = None
        existant.collaboration_terms = conditions_collaboration
        session.add(existant)
        _notifier_invitation(session, institution_id, chercheur_id)
        session.commit()
        session.refresh(existant)
        return existant

    rattachement = ResearcherAffiliation(
        institution_id=institution_id,
        researcher_id=chercheur_id,
        collaboration_terms=conditions_collaboration,
    )
    session.add(rattachement)
    _notifier_invitation(session, institution_id, chercheur_id)
    session.commit()
    session.refresh(rattachement)
    return rattachement


def lister_mes_chercheurs(
    session: Session, institution_id: uuid.UUID, *, statut: AffiliationStatus | None = None
) -> list[ResearcherAffiliation]:
    filtres = [col(ResearcherAffiliation.institution_id) == institution_id]
    if statut is not None:
        filtres.append(col(ResearcherAffiliation.status) == statut)
    return list(session.exec(select(ResearcherAffiliation).where(*filtres)).all())
