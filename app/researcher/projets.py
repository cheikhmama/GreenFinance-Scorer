"""Consultation des projets affectés au Chercheur (Étape 17) — lecture seule, jamais de création
(le Chercheur ne crée jamais de projet, voir app/institution/models.py::Projet)."""

import uuid

from sqlmodel import Session, col, select

from app.institution.models import AffectationProjet, Projet


def lister_mes_projets(session: Session, chercheur_id: uuid.UUID) -> list[Projet]:
    projet_ids = select(AffectationProjet.projet_id).where(
        AffectationProjet.chercheur_id == chercheur_id
    )
    return list(session.exec(select(Projet).where(col(Projet.id).in_(projet_ids))).all())
