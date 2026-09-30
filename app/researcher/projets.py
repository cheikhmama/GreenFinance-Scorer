"""Consultation des projets affectés au Chercheur (Étape 17, étendu Étape 17bis) — lecture seule,
jamais de création (le Chercheur ne crée jamais de projet, voir app/institution/models.py::Projet).
"""

import uuid

from sqlmodel import Session, col, select

from app.core.exceptions import NotFoundError
from app.institution.models import (
    Project,
    ProjectAssignment,
    ProjectCompany,
    ProjectDocument,
)


def lister_mes_projets(session: Session, chercheur_id: uuid.UUID) -> list[Project]:
    projet_ids = select(ProjectAssignment.project_id).where(
        ProjectAssignment.researcher_id == chercheur_id
    )
    return list(session.exec(select(Project).where(col(Project.id).in_(projet_ids))).all())


def _verifier_affectation(session: Session, chercheur_id: uuid.UUID, projet_id: uuid.UUID) -> None:
    affectation = session.exec(
        select(ProjectAssignment).where(
            ProjectAssignment.project_id == projet_id,
            ProjectAssignment.researcher_id == chercheur_id,
        )
    ).first()
    if affectation is None:
        # Même code que le projet soit inconnu ou non affecté à ce chercheur — voir
        # app/researcher/analyses.py::_projet_affecte, même principe.
        raise NotFoundError("Projet introuvable.", code="projet_introuvable")


def lister_perimetre(
    session: Session, chercheur_id: uuid.UUID, projet_id: uuid.UUID
) -> list[ProjectCompany]:
    _verifier_affectation(session, chercheur_id, projet_id)
    return list(
        session.exec(select(ProjectCompany).where(ProjectCompany.project_id == projet_id)).all()
    )


def entreprises_perimetre_chercheur(session: Session, chercheur_id: uuid.UUID) -> set[uuid.UUID]:
    """Union des périmètres de TOUS les projets affectés à ce chercheur — la décision de
    gouvernance du 2026-09-02 interdit qu'un Chercheur consulte une entreprise nommée
    individuellement hors du périmètre que son Institution a explicitement construit pour lui
    (voir app/institution/projets.py::ajouter_entreprise_perimetre). Utilisé pour restreindre
    /researcher/entreprises(/{id}), /researcher/comparaison et le fichier de preuve associé
    (app/researcher/router.py) — jamais pour /researcher/projets/{id}/perimetre, qui reste
    volontairement scopé à un seul projet à la fois."""
    projet_ids = select(ProjectAssignment.project_id).where(
        ProjectAssignment.researcher_id == chercheur_id
    )
    return set(
        session.exec(
            select(ProjectCompany.company_id).where(col(ProjectCompany.project_id).in_(projet_ids))
        ).all()
    )


def lister_documents(
    session: Session, chercheur_id: uuid.UUID, projet_id: uuid.UUID
) -> list[ProjectDocument]:
    _verifier_affectation(session, chercheur_id, projet_id)
    return list(
        session.exec(select(ProjectDocument).where(ProjectDocument.project_id == projet_id)).all()
    )
