"""Cycle de vie des projets Institution (Étape 17).

Un projet ne peut affecter qu'un Chercheur déjà ACCEPTE (voir app/auth/models.py::ResearcherAffiliation)
— l'invitation et l'affectation restent deux gestes distincts, jamais fusionnés.
"""

import uuid
from datetime import datetime

from sqlalchemy import ColumnElement
from sqlmodel import Session, col, func, select

from app.auth.models import ResearcherAffiliation, User
from app.company.models import Company
from app.core.database import utcnow
from app.core.enums import AffiliationStatus, AnalysisStatus, ProjectStatus
from app.core.exceptions import NotFoundError, ValidationError
from app.core.notifications import notifier
from app.ingestion.models import ESGReport
from app.institution.models import (
    Project,
    ProjectAssignment,
    ProjectCompany,
    ProjectDocument,
)
from app.investor.entreprises import dernier_rapport_valide
from app.researcher.models import Analysis


def _verifier_coherence_dates(
    date_debut: datetime | None,
    date_fin_prevue: datetime | None,
    date_limite: datetime | None,
) -> None:
    if (
        date_debut is not None
        and date_fin_prevue is not None
        and date_debut > date_fin_prevue
    ):
        raise ValidationError(
            "La date de début doit précéder la date de fin prévue.",
            code="periode_incoherente",
        )
    if date_limite is not None and date_debut is not None and date_limite < date_debut:
        raise ValidationError(
            "La date limite ne peut pas précéder la date de début.",
            code="date_limite_incoherente",
        )


def creer_projet(
    session: Session,
    institution_id: uuid.UUID,
    nom: str,
    description: str | None,
    objectif: str | None = None,
    date_debut: datetime | None = None,
    date_fin_prevue: datetime | None = None,
    date_limite: datetime | None = None,
) -> Project:
    _verifier_coherence_dates(date_debut, date_fin_prevue, date_limite)
    projet = Project(
        institution_id=institution_id,
        name=nom,
        description=description,
        objective=objectif,
        start_date=date_debut,
        planned_end_date=date_fin_prevue,
        deadline=date_limite,
    )
    session.add(projet)
    session.commit()
    session.refresh(projet)
    return projet


def lister_mes_projets(session: Session, institution_id: uuid.UUID) -> list[Project]:
    return list(
        session.exec(
            select(Project).where(col(Project.institution_id) == institution_id)
        ).all()
    )


def _projet_de_institution(
    session: Session, institution_id: uuid.UUID, projet_id: uuid.UUID
) -> Project:
    projet = session.get(Project, projet_id)
    if projet is None or projet.institution_id != institution_id:
        raise NotFoundError("Projet introuvable.", code="projet_introuvable")
    return projet


def consulter_projet(
    session: Session, institution_id: uuid.UUID, projet_id: uuid.UUID
) -> Project:
    return _projet_de_institution(session, institution_id, projet_id)


def affecter_chercheur(
    session: Session,
    institution_id: uuid.UUID,
    projet_id: uuid.UUID,
    chercheur_id: uuid.UUID,
) -> ProjectAssignment:
    projet = _projet_de_institution(session, institution_id, projet_id)
    if projet.status != ProjectStatus.OUVERT:
        raise ValidationError("Ce projet est clôturé.", code="projet_cloture")

    rattachement = session.exec(
        select(ResearcherAffiliation).where(
            ResearcherAffiliation.institution_id == institution_id,
            ResearcherAffiliation.researcher_id == chercheur_id,
        )
    ).first()
    if rattachement is None or rattachement.status != AffiliationStatus.ACCEPTE:
        raise ValidationError(
            "Ce chercheur n'a pas accepté de rattachement avec votre institution.",
            code="rattachement_requis",
        )

    deja_affecte = session.exec(
        select(ProjectAssignment).where(
            ProjectAssignment.project_id == projet_id,
            ProjectAssignment.researcher_id == chercheur_id,
        )
    ).first()
    if deja_affecte is not None:
        raise ValidationError(
            "Ce chercheur est déjà affecté à ce projet.", code="deja_affecte"
        )

    affectation = ProjectAssignment(project_id=projet_id, researcher_id=chercheur_id)
    session.add(affectation)
    notifier(
        session,
        chercheur_id,
        "PROJET_AFFECTATION",
        f"Vous avez été affecté au projet « {projet.name} ».",
        id_ressource=projet.id,
    )
    session.commit()
    session.refresh(affectation)
    return affectation


def cloturer_projet(
    session: Session, institution_id: uuid.UUID, projet_id: uuid.UUID
) -> Project:
    projet = _projet_de_institution(session, institution_id, projet_id)
    if projet.status == ProjectStatus.CLOTURE:
        raise ValidationError("Ce projet est déjà clôturé.", code="projet_deja_cloture")
    projet.status = ProjectStatus.CLOTURE
    projet.closed_at = utcnow()
    session.add(projet)
    session.commit()
    session.refresh(projet)
    return projet


def lister_perimetre(
    session: Session, institution_id: uuid.UUID, projet_id: uuid.UUID
) -> list[ProjectCompany]:
    _projet_de_institution(session, institution_id, projet_id)
    return list(
        session.exec(
            select(ProjectCompany).where(ProjectCompany.project_id == projet_id)
        ).all()
    )


def entreprises_perimetre_institution(session: Session, institution_id: uuid.UUID) -> set[uuid.UUID]:
    """Union des périmètres de TOUS les projets de cette institution — restreint la fiche détail
    et le fichier de preuve d'une entreprise (app/institution/router.py) au même périmètre que
    celui qu'elle a elle-même construit pour ses projets (voir ajouter_entreprise_perimetre),
    conformément à la décision de gouvernance du 2026-09-02. Le catalogue de recherche
    (/institution/entreprises, liste) reste volontairement non filtré : l'Institution doit pouvoir
    parcourir les entreprises publiées pour choisir lesquelles ajouter à un périmètre."""
    projet_ids = select(Project.id).where(Project.institution_id == institution_id)
    return set(
        session.exec(
            select(ProjectCompany.company_id).where(col(ProjectCompany.project_id).in_(projet_ids))
        ).all()
    )


def ajouter_entreprise_perimetre(
    session: Session,
    institution_id: uuid.UUID,
    projet_id: uuid.UUID,
    entreprise_id: uuid.UUID,
) -> ProjectCompany:
    """N'autorise dans le périmètre qu'une entreprise déjà publiée (Étape 17bis) — jamais une
    entreprise non publiée, dont les données brutes ne doivent jamais atteindre un Chercheur."""
    projet = _projet_de_institution(session, institution_id, projet_id)
    if projet.status != ProjectStatus.OUVERT:
        raise ValidationError("Ce projet est clôturé.", code="projet_cloture")

    entreprise = session.get(Company, entreprise_id)
    if entreprise is None or entreprise.published_at is None:
        raise ValidationError(
            "Cette entreprise n'est pas publiée.", code="entreprise_non_publiee"
        )

    deja_present = session.exec(
        select(ProjectCompany).where(
            ProjectCompany.project_id == projet_id,
            ProjectCompany.company_id == entreprise_id,
        )
    ).first()
    if deja_present is not None:
        raise ValidationError(
            "Cette entreprise fait déjà partie du périmètre du projet.",
            code="deja_dans_perimetre",
        )

    lien = ProjectCompany(project_id=projet_id, company_id=entreprise_id)
    session.add(lien)
    session.commit()
    session.refresh(lien)
    return lien


def lister_documents(
    session: Session, institution_id: uuid.UUID, projet_id: uuid.UUID
) -> list[ProjectDocument]:
    _projet_de_institution(session, institution_id, projet_id)
    return list(
        session.exec(
            select(ProjectDocument).where(ProjectDocument.project_id == projet_id)
        ).all()
    )


def ajouter_document(
    session: Session,
    institution_id: uuid.UUID,
    projet_id: uuid.UUID,
    rapport_id: uuid.UUID,
) -> ProjectDocument:
    """N'accepte que le rapport actuellement publié de l'entreprise (Étape 17bis) — jamais
    seulement statut == VALIDATED : validation et publication restent deux gestes distincts (voir
    app/company/models.py::Company.published_at), et un ancien rapport VALIDATED remplacé
    depuis ne redevient jamais accessible ainsi. L'entreprise doit d'abord appartenir au périmètre
    du projet — mettre un document à disposition ne peut jamais élargir le périmètre en silence."""
    projet = _projet_de_institution(session, institution_id, projet_id)
    if projet.status != ProjectStatus.OUVERT:
        raise ValidationError("Ce projet est clôturé.", code="projet_cloture")

    rapport = session.get(ESGReport, rapport_id)
    if rapport is None:
        raise NotFoundError("Rapport introuvable.", code="rapport_introuvable")

    dans_perimetre = session.exec(
        select(ProjectCompany).where(
            ProjectCompany.project_id == projet_id,
            ProjectCompany.company_id == rapport.company_id,
        )
    ).first()
    if dans_perimetre is None:
        raise ValidationError(
            "Cette entreprise ne fait pas partie du périmètre du projet.",
            code="entreprise_hors_perimetre",
        )

    rapport_public = dernier_rapport_valide(session, rapport.company_id)
    if rapport_public is None or rapport_public.id != rapport.id:
        raise ValidationError(
            "Seul le rapport actuellement publié de l'entreprise peut être mis à disposition.",
            code="rapport_non_publie",
        )

    deja_present = session.exec(
        select(ProjectDocument).where(
            ProjectDocument.project_id == projet_id,
            ProjectDocument.report_id == rapport_id,
        )
    ).first()
    if deja_present is not None:
        raise ValidationError(
            "Ce document est déjà mis à disposition sur ce projet.", code="deja_ajoute"
        )

    document = ProjectDocument(project_id=projet_id, report_id=rapport_id)
    session.add(document)
    session.commit()
    session.refresh(document)
    return document


def statistiques_admin(session: Session) -> tuple[int, int, int, int]:
    """(projets ouverts, projets clôturés, invitations en attente, analyses soumises à examiner)
    toutes Institutions confondues — synthèse pour l'Aperçu Administrateur (app/admin/apercu.py).
    institutions_actives (comptes) est déjà calculé ailleurs (voir app/admin/dashboard.py)."""
    projets_ouverts = session.exec(
        select(func.count()).select_from(Project).where(col(Project.status) == ProjectStatus.OUVERT)
    ).one()
    projets_clotures = session.exec(
        select(func.count()).select_from(Project).where(col(Project.status) == ProjectStatus.CLOTURE)
    ).one()
    invitations_en_attente = session.exec(
        select(func.count())
        .select_from(ResearcherAffiliation)
        .where(col(ResearcherAffiliation.status) == AffiliationStatus.EN_ATTENTE)
    ).one()
    analyses_a_examiner = session.exec(
        select(func.count()).select_from(Analysis).where(col(Analysis.status) == AnalysisStatus.SOUMISE)
    ).one()
    return projets_ouverts, projets_clotures, invitations_en_attente, analyses_a_examiner


def lister_projets_admin(
    session: Session,
    *,
    statut: ProjectStatus | None = None,
    page: int = 1,
    page_size: int = 3,
) -> tuple[list[tuple[Project, str, int]], int]:
    """Vue de suivi Administrateur de tous les projets, avec filtre optionnel sur le statut — le
    détail derrière "Projets ouverts/clôturés" de l'Aperçu. Renvoie (Projet, e-mail de
    l'institution, nombre de chercheurs affectés) par ligne."""
    filtres: list[ColumnElement[bool]] = []
    if statut is not None:
        filtres.append(col(Project.status) == statut)

    total = session.exec(select(func.count()).select_from(Project).where(*filtres)).one()
    projets = list(
        session.exec(
            select(Project)
            .where(*filtres)
            .order_by(col(Project.created_at).desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )

    resultats: list[tuple[Project, str, int]] = []
    for projet in projets:
        institution = session.get(User, projet.institution_id)
        assert institution is not None  # FK NOT NULL, ne peut pas être absent
        nb_chercheurs = session.exec(
            select(func.count())
            .select_from(ProjectAssignment)
            .where(col(ProjectAssignment.project_id) == projet.id)
        ).one()
        resultats.append((projet, institution.email, nb_chercheurs))
    return resultats, total
