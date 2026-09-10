"""Cycle de vie des projets Institution (Étape 17).

Un projet ne peut affecter qu'un Chercheur déjà ACCEPTE (voir app/auth/models.py::ChercheurInstitution)
— l'invitation et l'affectation restent deux gestes distincts, jamais fusionnés.
"""

import uuid

from sqlmodel import Session, col, select

from app.auth.models import ChercheurInstitution
from app.core.database import utcnow
from app.core.enums import StatutProjet, StatutRattachement
from app.core.exceptions import NotFoundError, ValidationError
from app.institution.models import AffectationProjet, Projet


def creer_projet(
    session: Session, institution_id: uuid.UUID, nom: str, description: str | None
) -> Projet:
    projet = Projet(institution_id=institution_id, nom=nom, description=description)
    session.add(projet)
    session.commit()
    session.refresh(projet)
    return projet


def lister_mes_projets(session: Session, institution_id: uuid.UUID) -> list[Projet]:
    return list(
        session.exec(select(Projet).where(col(Projet.institution_id) == institution_id)).all()
    )


def _projet_de_institution(
    session: Session, institution_id: uuid.UUID, projet_id: uuid.UUID
) -> Projet:
    projet = session.get(Projet, projet_id)
    if projet is None or projet.institution_id != institution_id:
        raise NotFoundError("Projet introuvable.", code="projet_introuvable")
    return projet


def consulter_projet(session: Session, institution_id: uuid.UUID, projet_id: uuid.UUID) -> Projet:
    return _projet_de_institution(session, institution_id, projet_id)


def affecter_chercheur(
    session: Session, institution_id: uuid.UUID, projet_id: uuid.UUID, chercheur_id: uuid.UUID
) -> AffectationProjet:
    projet = _projet_de_institution(session, institution_id, projet_id)
    if projet.statut != StatutProjet.OUVERT:
        raise ValidationError("Ce projet est clôturé.", code="projet_cloture")

    rattachement = session.exec(
        select(ChercheurInstitution).where(
            ChercheurInstitution.institution_id == institution_id,
            ChercheurInstitution.chercheur_id == chercheur_id,
        )
    ).first()
    if rattachement is None or rattachement.statut != StatutRattachement.ACCEPTE:
        raise ValidationError(
            "Ce chercheur n'a pas accepté de rattachement avec votre institution.",
            code="rattachement_requis",
        )

    deja_affecte = session.exec(
        select(AffectationProjet).where(
            AffectationProjet.projet_id == projet_id,
            AffectationProjet.chercheur_id == chercheur_id,
        )
    ).first()
    if deja_affecte is not None:
        raise ValidationError("Ce chercheur est déjà affecté à ce projet.", code="deja_affecte")

    affectation = AffectationProjet(projet_id=projet_id, chercheur_id=chercheur_id)
    session.add(affectation)
    session.commit()
    session.refresh(affectation)
    return affectation


def cloturer_projet(session: Session, institution_id: uuid.UUID, projet_id: uuid.UUID) -> Projet:
    projet = _projet_de_institution(session, institution_id, projet_id)
    if projet.statut == StatutProjet.CLOTURE:
        raise ValidationError("Ce projet est déjà clôturé.", code="projet_deja_cloture")
    projet.statut = StatutProjet.CLOTURE
    projet.date_cloture = utcnow()
    session.add(projet)
    session.commit()
    session.refresh(projet)
    return projet
