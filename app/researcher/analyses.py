"""Cycle de vie d'une analyse Chercheur (Étape 17).

Une correction demandée par l'Institution ne réécrit jamais l'analyse existante — corriger_analyse
crée une nouvelle ligne (version+1, analyse_precedente_id), même principe que
app/company/rapports.py::creer_correction sur RapportESG.
"""

import uuid

from sqlmodel import Session, col, select

from app.company.models import Entreprise
from app.core.database import utcnow
from app.core.enums import StatutAnalyse, StatutProjet
from app.core.exceptions import NotFoundError, ValidationError
from app.institution.models import AffectationProjet, Projet
from app.researcher.models import Analyse, AnalyseEntreprise


def _projet_affecte(session: Session, chercheur_id: uuid.UUID, projet_id: uuid.UUID) -> Projet:
    projet = session.get(Projet, projet_id)
    affectation = session.exec(
        select(AffectationProjet).where(
            AffectationProjet.projet_id == projet_id,
            AffectationProjet.chercheur_id == chercheur_id,
        )
    ).first()
    if projet is None or affectation is None:
        # Même code que le projet soit inconnu ou non affecté à ce chercheur — jamais de 403 qui
        # confirmerait l'existence d'un projet auquel il n'a pas accès.
        raise NotFoundError("Projet introuvable.", code="projet_introuvable")
    return projet


def _verifier_entreprises_publiees(session: Session, entreprise_ids: list[uuid.UUID]) -> None:
    if not entreprise_ids:
        raise ValidationError(
            "Une analyse doit comparer au moins une entreprise.", code="entreprises_requises"
        )
    for entreprise_id in entreprise_ids:
        entreprise = session.get(Entreprise, entreprise_id)
        if entreprise is None or entreprise.date_publication is None:
            raise NotFoundError("Entreprise introuvable.", code="entreprise_introuvable")


def _remplacer_entreprises(
    session: Session, analyse_id: uuid.UUID, entreprise_ids: list[uuid.UUID]
) -> None:
    existantes = session.exec(
        select(AnalyseEntreprise).where(AnalyseEntreprise.analyse_id == analyse_id)
    ).all()
    for lien in existantes:
        session.delete(lien)
    session.flush()
    for entreprise_id in entreprise_ids:
        session.add(AnalyseEntreprise(analyse_id=analyse_id, entreprise_id=entreprise_id))


def lister_entreprise_ids(session: Session, analyse_id: uuid.UUID) -> list[uuid.UUID]:
    return [
        lien.entreprise_id
        for lien in session.exec(
            select(AnalyseEntreprise).where(AnalyseEntreprise.analyse_id == analyse_id)
        ).all()
    ]


def creer_analyse(
    session: Session,
    chercheur_id: uuid.UUID,
    projet_id: uuid.UUID,
    titre: str,
    contenu: str,
    entreprise_ids: list[uuid.UUID],
) -> Analyse:
    projet = _projet_affecte(session, chercheur_id, projet_id)
    if projet.statut != StatutProjet.OUVERT:
        raise ValidationError("Ce projet est clôturé.", code="projet_cloture")
    _verifier_entreprises_publiees(session, entreprise_ids)

    analyse = Analyse(projet_id=projet_id, chercheur_id=chercheur_id, titre=titre, contenu=contenu)
    session.add(analyse)
    session.flush()
    _remplacer_entreprises(session, analyse.id, entreprise_ids)
    session.commit()
    session.refresh(analyse)
    return analyse


def _analyse_du_chercheur(session: Session, chercheur_id: uuid.UUID, analyse_id: uuid.UUID) -> Analyse:
    analyse = session.get(Analyse, analyse_id)
    if analyse is None or analyse.chercheur_id != chercheur_id:
        raise NotFoundError("Analyse introuvable.", code="analyse_introuvable")
    return analyse


def modifier_analyse(
    session: Session,
    chercheur_id: uuid.UUID,
    analyse_id: uuid.UUID,
    titre: str,
    contenu: str,
    entreprise_ids: list[uuid.UUID],
) -> Analyse:
    analyse = _analyse_du_chercheur(session, chercheur_id, analyse_id)
    if analyse.statut != StatutAnalyse.BROUILLON:
        raise ValidationError(
            "Seule une analyse en brouillon peut être modifiée.", code="analyse_non_modifiable"
        )
    _verifier_entreprises_publiees(session, entreprise_ids)

    analyse.titre = titre
    analyse.contenu = contenu
    session.add(analyse)
    _remplacer_entreprises(session, analyse.id, entreprise_ids)
    session.commit()
    session.refresh(analyse)
    return analyse


def soumettre_analyse(session: Session, chercheur_id: uuid.UUID, analyse_id: uuid.UUID) -> Analyse:
    analyse = _analyse_du_chercheur(session, chercheur_id, analyse_id)
    if analyse.statut != StatutAnalyse.BROUILLON:
        raise ValidationError(
            "Seule une analyse en brouillon peut être soumise.", code="soumission_impossible"
        )
    a_des_entreprises = session.exec(
        select(AnalyseEntreprise.id).where(col(AnalyseEntreprise.analyse_id) == analyse.id)
    ).first()
    if a_des_entreprises is None:
        raise ValidationError(
            "Une analyse doit comparer au moins une entreprise avant d'être soumise.",
            code="entreprises_requises",
        )
    analyse.statut = StatutAnalyse.SOUMISE
    analyse.date_soumission = utcnow()
    session.add(analyse)
    session.commit()
    session.refresh(analyse)
    return analyse


def corriger_analyse(
    session: Session,
    chercheur_id: uuid.UUID,
    analyse_id: uuid.UUID,
    titre: str,
    contenu: str,
    entreprise_ids: list[uuid.UUID],
) -> Analyse:
    precedente = _analyse_du_chercheur(session, chercheur_id, analyse_id)
    if precedente.statut != StatutAnalyse.CORRECTION_DEMANDEE:
        raise ValidationError(
            "Cette analyse n'est pas en attente de correction.", code="correction_non_attendue"
        )
    _verifier_entreprises_publiees(session, entreprise_ids)

    nouvelle = Analyse(
        projet_id=precedente.projet_id,
        chercheur_id=chercheur_id,
        titre=titre,
        contenu=contenu,
        version=precedente.version + 1,
        analyse_precedente_id=precedente.id,
    )
    session.add(nouvelle)
    session.flush()
    _remplacer_entreprises(session, nouvelle.id, entreprise_ids)
    session.commit()
    session.refresh(nouvelle)
    return nouvelle
