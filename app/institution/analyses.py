"""Décision de l'Institution sur une analyse soumise, et export (Étape 17).

Un seul acteur décide (l'Institution) — pas d'entité "avis" séparée comme AuditOpinion, statut +
commentaire_institution sur Analyse suffisent (voir app/researcher/models.py).
"""

import csv
import io
import uuid

from sqlmodel import Session, col, select

from app.auth.models import InstitutionProfile, User
from app.company.models import Company
from app.core.database import utcnow
from app.core.enums import AnalysisStatus
from app.core.exceptions import NotFoundError, ValidationError
from app.core.notifications import notifier
from app.institution.models import Project
from app.researcher.analyses import lister_versions
from app.researcher.models import Analysis, AnalysisCompany


def lister_mes_analyses(
    session: Session, institution_id: uuid.UUID, *, statut: AnalysisStatus | None = None
) -> list[Analysis]:
    """Toutes les analyses soumises sur les projets de l'institution, tous projets confondus —
    seule façon aujourd'hui de voir d'un coup d'œil ce qui reste à décider, sans ouvrir chaque
    projet un par un (voir ProjetDetail.analyses, limité à un seul projet à la fois). BROUILLON
    est toujours exclu, quel que soit le filtre demandé : un brouillon est l'espace de travail
    privé du chercheur tant qu'il n'a pas choisi de le soumettre (voir analyse_de_institution)."""
    filtres = [col(Project.institution_id) == institution_id, col(Analysis.status) != AnalysisStatus.BROUILLON]
    if statut is not None:
        filtres.append(col(Analysis.status) == statut)
    requete = (
        select(Analysis)
        .join(Project, col(Analysis.project_id) == col(Project.id))
        .where(*filtres)
    )
    return list(session.exec(requete).all())


def analyse_de_institution(
    session: Session, institution_id: uuid.UUID, analyse_id: uuid.UUID
) -> Analysis:
    """Chokepoint unique pour tout accès Institution à une analyse précise (lecture, décision,
    historique, export) — un BROUILLON jamais soumis par le Chercheur est traité comme inexistant
    pour l'Institution, jamais seulement filtré de la liste : sans cette vérification ici, un
    accès direct par id (consultation, export) contournerait lister_mes_analyses."""
    analyse = session.get(Analysis, analyse_id)
    if analyse is None:
        raise NotFoundError("Analyse introuvable.", code="analyse_introuvable")
    projet = session.get(Project, analyse.project_id)
    if (
        projet is None
        or projet.institution_id != institution_id
        or analyse.status == AnalysisStatus.BROUILLON
    ):
        # Même code dans les trois cas — jamais de 403 qui confirmerait l'existence de
        # l'analyse (ou son statut brouillon) à une institution qui n'y a pas droit.
        raise NotFoundError("Analyse introuvable.", code="analyse_introuvable")
    return analyse


def valider_analyse(
    session: Session,
    institution_id: uuid.UUID,
    analyse_id: uuid.UUID,
    commentaire: str | None,
) -> Analysis:
    analyse = analyse_de_institution(session, institution_id, analyse_id)
    if analyse.status != AnalysisStatus.SOUMISE:
        raise ValidationError(
            "Cette analyse n'est pas en attente de décision.",
            code="decision_impossible",
        )
    analyse.status = AnalysisStatus.VALIDEE
    analyse.institution_comment = commentaire
    analyse.decided_at = utcnow()
    session.add(analyse)
    notifier(
        session,
        analyse.researcher_id,
        "ANALYSE_VALIDEE",
        f"Votre analyse « {analyse.title} » a été validée.",
        id_ressource=analyse.id,
    )
    session.commit()
    session.refresh(analyse)
    return analyse


def demander_correction(
    session: Session,
    institution_id: uuid.UUID,
    analyse_id: uuid.UUID,
    commentaire: str | None,
) -> Analysis:
    analyse = analyse_de_institution(session, institution_id, analyse_id)
    if analyse.status != AnalysisStatus.SOUMISE:
        raise ValidationError(
            "Cette analyse n'est pas en attente de décision.",
            code="decision_impossible",
        )
    if not commentaire:
        raise ValidationError(
            "Un commentaire est requis pour demander une correction.",
            code="commentaire_requis",
        )
    analyse.status = AnalysisStatus.CORRECTION_DEMANDEE
    analyse.institution_comment = commentaire
    analyse.decided_at = utcnow()
    session.add(analyse)
    notifier(
        session,
        analyse.researcher_id,
        "ANALYSE_CORRECTION_DEMANDEE",
        f"Une correction est demandée sur votre analyse « {analyse.title} » : {commentaire}",
        id_ressource=analyse.id,
    )
    session.commit()
    session.refresh(analyse)
    return analyse


def historique_analyse(
    session: Session, institution_id: uuid.UUID, analyse_id: uuid.UUID
) -> list[Analysis]:
    analyse = analyse_de_institution(session, institution_id, analyse_id)
    return lister_versions(session, analyse)


def consulter_mon_profil(
    session: Session, institution_id: uuid.UUID
) -> InstitutionProfile:
    profil = session.exec(
        select(InstitutionProfile).where(
            InstitutionProfile.user_id == institution_id
        )
    ).first()
    if profil is None:
        raise NotFoundError(
            "Profil institution introuvable.", code="profil_institution_introuvable"
        )
    return profil


def _consommer_quota_export(session: Session, institution_id: uuid.UUID) -> None:
    profil = session.exec(
        select(InstitutionProfile).where(
            InstitutionProfile.user_id == institution_id
        )
    ).first()
    if profil is None:
        raise ValidationError(
            "Profil institution introuvable.", code="profil_institution_introuvable"
        )
    if profil.export_quota <= 0:
        raise ValidationError("Quota d'export épuisé.", code="quota_export_epuise")
    profil.export_quota -= 1
    session.add(profil)


def exporter_analyse_csv(
    session: Session, institution_id: uuid.UUID, analyse_id: uuid.UUID
) -> str:
    analyse = analyse_de_institution(session, institution_id, analyse_id)
    _consommer_quota_export(session, institution_id)

    chercheur = session.get(User, analyse.researcher_id)
    entreprise_ids = [
        lien.company_id
        for lien in session.exec(
            select(AnalysisCompany).where(AnalysisCompany.analysis_id == analyse.id)
        ).all()
    ]
    noms_entreprises = [
        entreprise.name
        for eid in entreprise_ids
        if (entreprise := session.get(Company, eid)) is not None
    ]

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["titre", "statut", "version", "chercheur", "entreprises_comparees", "contenu"]
    )
    writer.writerow(
        [
            analyse.title,
            analyse.status.value,
            analyse.version,
            chercheur.email if chercheur else "",
            "; ".join(noms_entreprises),
            analyse.content,
        ]
    )
    session.commit()
    return buffer.getvalue()
