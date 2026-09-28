"""Gestion des rattachements Institution<->Chercheur (invitations) — Étape 17.

Sert aussi de brique de sélection parmi les acteurs existants (même principe que
app/admin/utilisateurs.py) : une Institution invite toujours un compte CHERCHEUR déjà enregistré
et actif, jamais une identité saisie librement.
"""

import uuid

from sqlmodel import Session, col, select

from app.auth.models import ChercheurInstitution, Utilisateur
from app.core.database import utcnow
from app.core.enums import Role, StatutRattachement
from app.core.exceptions import ValidationError
from app.core.notifications import notifier


def lister_chercheurs_disponibles(session: Session, institution_id: uuid.UUID) -> list[Utilisateur]:
    """Comptes CHERCHEUR actifs jamais encore invités par cette institution — un rattachement
    REFUSE se réinvite via inviter_chercheur (qui remet le même enregistrement à EN_ATTENTE),
    pas via cette liste."""
    deja_rattaches = select(ChercheurInstitution.chercheur_id).where(
        ChercheurInstitution.institution_id == institution_id
    )
    return list(
        session.exec(
            select(Utilisateur).where(
                col(Utilisateur.role) == Role.CHERCHEUR,
                col(Utilisateur.actif).is_(True),
                col(Utilisateur.id).not_in(deja_rattaches),
            )
        ).all()
    )


def _notifier_invitation(session: Session, institution_id: uuid.UUID, chercheur_id: uuid.UUID) -> None:
    institution = session.get(Utilisateur, institution_id)
    if institution is not None:
        notifier(
            session,
            chercheur_id,
            "RATTACHEMENT_INVITATION",
            f"{institution.nom or institution.email} vous invite à rejoindre ses projets.",
        )


def inviter_chercheur(
    session: Session,
    institution_id: uuid.UUID,
    chercheur_id: uuid.UUID,
    conditions_collaboration: str | None = None,
) -> ChercheurInstitution:
    chercheur = session.get(Utilisateur, chercheur_id)
    if chercheur is None or chercheur.role != Role.CHERCHEUR or not chercheur.actif:
        raise ValidationError("Chercheur invalide.", code="chercheur_invalide")

    existant = session.exec(
        select(ChercheurInstitution).where(
            ChercheurInstitution.institution_id == institution_id,
            ChercheurInstitution.chercheur_id == chercheur_id,
        )
    ).first()
    if existant is not None:
        if existant.statut != StatutRattachement.REFUSE:
            raise ValidationError(
                "Ce chercheur est déjà invité ou rattaché.", code="rattachement_existant"
            )
        # Réinvitation après un refus : même ligne, jamais un doublon (voir uq_chercheur_institution).
        existant.statut = StatutRattachement.EN_ATTENTE
        existant.date_invitation = utcnow()
        existant.date_reponse = None
        existant.conditions_collaboration = conditions_collaboration
        session.add(existant)
        _notifier_invitation(session, institution_id, chercheur_id)
        session.commit()
        session.refresh(existant)
        return existant

    rattachement = ChercheurInstitution(
        institution_id=institution_id,
        chercheur_id=chercheur_id,
        conditions_collaboration=conditions_collaboration,
    )
    session.add(rattachement)
    _notifier_invitation(session, institution_id, chercheur_id)
    session.commit()
    session.refresh(rattachement)
    return rattachement


def lister_mes_chercheurs(
    session: Session, institution_id: uuid.UUID, *, statut: StatutRattachement | None = None
) -> list[ChercheurInstitution]:
    filtres = [col(ChercheurInstitution.institution_id) == institution_id]
    if statut is not None:
        filtres.append(col(ChercheurInstitution.statut) == statut)
    return list(session.exec(select(ChercheurInstitution).where(*filtres)).all())
