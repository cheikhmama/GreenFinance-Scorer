"""Décision de l'Institution sur une analyse soumise, et export (Étape 17).

Un seul acteur décide (l'Institution) — pas d'entité "avis" séparée comme AvisAudit, statut +
commentaire_institution sur Analyse suffisent (voir app/researcher/models.py).
"""

import csv
import io
import uuid

from sqlmodel import Session, select

from app.auth.models import InstitutionProfil, Utilisateur
from app.company.models import Entreprise
from app.core.database import utcnow
from app.core.enums import StatutAnalyse
from app.core.exceptions import NotFoundError, ValidationError
from app.institution.models import Projet
from app.researcher.models import Analyse, AnalyseEntreprise


def analyse_de_institution(
    session: Session, institution_id: uuid.UUID, analyse_id: uuid.UUID
) -> Analyse:
    analyse = session.get(Analyse, analyse_id)
    if analyse is None:
        raise NotFoundError("Analyse introuvable.", code="analyse_introuvable")
    projet = session.get(Projet, analyse.projet_id)
    if projet is None or projet.institution_id != institution_id:
        # Même code que l'analyse soit inconnue ou d'un autre projet — jamais de 403 qui
        # confirmerait l'existence de l'analyse à une institution qui n'y a pas droit.
        raise NotFoundError("Analyse introuvable.", code="analyse_introuvable")
    return analyse


def valider_analyse(
    session: Session, institution_id: uuid.UUID, analyse_id: uuid.UUID, commentaire: str | None
) -> Analyse:
    analyse = analyse_de_institution(session, institution_id, analyse_id)
    if analyse.statut != StatutAnalyse.SOUMISE:
        raise ValidationError("Cette analyse n'est pas en attente de décision.", code="decision_impossible")
    analyse.statut = StatutAnalyse.VALIDEE
    analyse.commentaire_institution = commentaire
    analyse.date_decision = utcnow()
    session.add(analyse)
    session.commit()
    session.refresh(analyse)
    return analyse


def demander_correction(
    session: Session, institution_id: uuid.UUID, analyse_id: uuid.UUID, commentaire: str | None
) -> Analyse:
    analyse = analyse_de_institution(session, institution_id, analyse_id)
    if analyse.statut != StatutAnalyse.SOUMISE:
        raise ValidationError("Cette analyse n'est pas en attente de décision.", code="decision_impossible")
    if not commentaire:
        raise ValidationError(
            "Un commentaire est requis pour demander une correction.", code="commentaire_requis"
        )
    analyse.statut = StatutAnalyse.CORRECTION_DEMANDEE
    analyse.commentaire_institution = commentaire
    analyse.date_decision = utcnow()
    session.add(analyse)
    session.commit()
    session.refresh(analyse)
    return analyse


def _consommer_quota_export(session: Session, institution_id: uuid.UUID) -> None:
    profil = session.exec(
        select(InstitutionProfil).where(InstitutionProfil.utilisateur_id == institution_id)
    ).first()
    if profil is None:
        raise ValidationError("Profil institution introuvable.", code="profil_institution_introuvable")
    if profil.quota_export <= 0:
        raise ValidationError("Quota d'export épuisé.", code="quota_export_epuise")
    profil.quota_export -= 1
    session.add(profil)


def exporter_analyse_csv(session: Session, institution_id: uuid.UUID, analyse_id: uuid.UUID) -> str:
    analyse = analyse_de_institution(session, institution_id, analyse_id)
    _consommer_quota_export(session, institution_id)

    chercheur = session.get(Utilisateur, analyse.chercheur_id)
    entreprise_ids = [
        lien.entreprise_id
        for lien in session.exec(
            select(AnalyseEntreprise).where(AnalyseEntreprise.analyse_id == analyse.id)
        ).all()
    ]
    noms_entreprises = [
        entreprise.nom
        for eid in entreprise_ids
        if (entreprise := session.get(Entreprise, eid)) is not None
    ]

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["titre", "statut", "version", "chercheur", "entreprises_comparees", "contenu"])
    writer.writerow(
        [
            analyse.titre,
            analyse.statut.value,
            analyse.version,
            chercheur.email if chercheur else "",
            "; ".join(noms_entreprises),
            analyse.contenu,
        ]
    )
    session.commit()
    return buffer.getvalue()
