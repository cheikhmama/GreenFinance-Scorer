"""Routes HTTP de l'espace Chercheur (Étape 17).

Consultation des entreprises publiées (réutilise app/investor/entreprises.py, interface déjà
publique — voir ARCHITECTURE.md §1), réponse aux invitations d'institution, et cycle de vie des
analyses sur les projets affectés. La logique vit dans app/researcher/{rattachements,projets,
analyses}.py — ce router ne fait qu'appliquer le contrôle d'accès par rôle et l'appeler.
"""

import uuid

import pydantic
from fastapi import APIRouter, Depends, Form, Query, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse
from sqlmodel import Session, col, select

from app.auth.models import User
from app.auth.permissions import require_role
from app.core import storage
from app.core.dependencies import get_session
from app.core.enums import Role
from app.core.exceptions import NotFoundError
from app.core.schemas import Page
from app.institution.router import entreprise_perimetre_public, rattachement_public
from app.institution.schemas import (
    DocumentProjetPublic,
    EntreprisePerimetrePublic,
    RattachementPublic,
)
from app.investor import entreprises
from app.investor.schemas import EntrepriseDetailInvestisseur, EntreprisePublieePublic
from app.researcher import analyses, cross_validation, projets, rattachements
from app.researcher.models import Analysis
from app.researcher.schemas import (
    AnalyseDetail,
    AnalysePublic,
    CreerAnalyseRequest,
    CrossValidationReport,
    ModifierAnalyseRequest,
    ProjetAffecte,
    ReferenceDatasetImportResult,
    ReferenceDatasetRequest,
    ReferenceDatasetSummary,
)

router = APIRouter(tags=["researcher"])


@router.get(
    "/researcher/entreprises",
    response_model=Page[EntreprisePublieePublic],
    operation_id="listPublishedCompaniesForResearcher",
    summary="Lister les entreprises publiées, avec leur score ESG et leurs émissions Scope 1/2/3",
)
def lister_entreprises_route(
    secteur: str | None = None,
    pays: str | None = None,
    recherche: str | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(require_role(Role.RESEARCHER)),
    session: Session = Depends(get_session),
) -> Page[EntreprisePublieePublic]:
    perimetre = projets.entreprises_perimetre_chercheur(session, current_user.id)
    items, total = entreprises.lister_entreprises_publiees(
        session,
        secteur=secteur,
        pays=pays,
        recherche=recherche,
        page=page,
        page_size=page_size,
        perimetre_autorise=perimetre,
    )
    return Page[EntreprisePublieePublic](
        items=items, page=page, page_size=page_size, total=total, pages=-(-total // page_size) or 1
    )


@router.get(
    "/researcher/entreprises/{entreprise_id}",
    response_model=EntrepriseDetailInvestisseur,
    operation_id="getPublishedCompanyDetailForResearcher",
    summary="Consulter le détail d'une entreprise publiée (indicateurs, carbone, preuves)",
)
def consulter_entreprise_route(
    entreprise_id: uuid.UUID,
    current_user: User = Depends(require_role(Role.RESEARCHER)),
    session: Session = Depends(get_session),
) -> EntrepriseDetailInvestisseur:
    perimetre = projets.entreprises_perimetre_chercheur(session, current_user.id)
    return entreprises.consulter_entreprise_publiee(
        session, entreprise_id, perimetre_autorise=perimetre
    )


@router.get(
    "/researcher/entreprises/{entreprise_id}/preuves/{preuve_id}/fichier",
    operation_id="getEvidenceFileForResearcher",
    summary="Consulter l'extrait PDF (une page) prouvant un indicateur ou une donnée carbone",
)
def consulter_preuve_route(
    entreprise_id: uuid.UUID,
    preuve_id: uuid.UUID,
    current_user: User = Depends(require_role(Role.RESEARCHER)),
    session: Session = Depends(get_session),
) -> FileResponse:
    perimetre = projets.entreprises_perimetre_chercheur(session, current_user.id)
    chemin = entreprises.fichier_preuve(
        session, entreprise_id, preuve_id, perimetre_autorise=perimetre
    )
    return FileResponse(storage.resolve_path(chemin), media_type="application/pdf")


@router.get(
    "/researcher/comparaison",
    response_model=list[EntrepriseDetailInvestisseur],
    operation_id="compareCompaniesForResearcher",
    summary="Comparer jusqu'à 4 entreprises publiées (score, indicateurs, carbone détaillés)",
)
def comparer_entreprises_route(
    entreprise_ids: list[uuid.UUID] = Query(...),
    current_user: User = Depends(require_role(Role.RESEARCHER)),
    session: Session = Depends(get_session),
) -> list[EntrepriseDetailInvestisseur]:
    perimetre = projets.entreprises_perimetre_chercheur(session, current_user.id)
    return entreprises.comparer_entreprises(session, entreprise_ids, perimetre_autorise=perimetre)


@router.get(
    "/researcher/rattachements",
    response_model=list[RattachementPublic],
    operation_id="listMyInstitutionInvitations",
    summary="Lister les invitations reçues d'institutions",
)
def lister_mes_rattachements_route(
    current_user: User = Depends(require_role(Role.RESEARCHER)),
    session: Session = Depends(get_session),
) -> list[RattachementPublic]:
    mes_rattachements = rattachements.lister_mes_rattachements(session, current_user.id)
    return [rattachement_public(session, r) for r in mes_rattachements]


@router.post(
    "/researcher/rattachements/{rattachement_id}/accepter",
    response_model=RattachementPublic,
    operation_id="acceptInstitutionInvitation",
    summary="Accepter une invitation d'institution",
)
def accepter_rattachement_route(
    rattachement_id: uuid.UUID,
    current_user: User = Depends(require_role(Role.RESEARCHER)),
    session: Session = Depends(get_session),
) -> RattachementPublic:
    rattachement = rattachements.accepter_invitation(session, current_user.id, rattachement_id)
    return rattachement_public(session, rattachement)


@router.post(
    "/researcher/rattachements/{rattachement_id}/refuser",
    response_model=RattachementPublic,
    operation_id="declineInstitutionInvitation",
    summary="Refuser une invitation d'institution",
)
def refuser_rattachement_route(
    rattachement_id: uuid.UUID,
    current_user: User = Depends(require_role(Role.RESEARCHER)),
    session: Session = Depends(get_session),
) -> RattachementPublic:
    rattachement = rattachements.refuser_invitation(session, current_user.id, rattachement_id)
    return rattachement_public(session, rattachement)


@router.get(
    "/researcher/projets",
    response_model=list[ProjetAffecte],
    operation_id="listMyAssignedProjects",
    summary="Lister les projets sur lesquels je suis affecté",
)
def lister_mes_projets_route(
    current_user: User = Depends(require_role(Role.RESEARCHER)),
    session: Session = Depends(get_session),
) -> list[ProjetAffecte]:
    mes_projets = projets.lister_mes_projets(session, current_user.id)
    resultat = []
    for projet in mes_projets:
        institution = session.get(User, projet.institution_id)
        resultat.append(
            ProjetAffecte(
                id=projet.id,
                name=projet.name,
                description=projet.description,
                objective=projet.objective,
                start_date=projet.start_date,
                planned_end_date=projet.planned_end_date,
                deadline=projet.deadline,
                status=projet.status,
                institution_email=institution.email if institution else "",
            )
        )
    return resultat


@router.get(
    "/researcher/projets/{projet_id}/perimetre",
    response_model=list[EntreprisePerimetrePublic],
    operation_id="listProjectScopeForResearcher",
    summary="Lister les entreprises autorisées dans le périmètre d'un projet affecté",
)
def lister_perimetre_route(
    projet_id: uuid.UUID,
    current_user: User = Depends(require_role(Role.RESEARCHER)),
    session: Session = Depends(get_session),
) -> list[EntreprisePerimetrePublic]:
    liens = projets.lister_perimetre(session, current_user.id, projet_id)
    return [entreprise_perimetre_public(session, lien) for lien in liens]


@router.get(
    "/researcher/projets/{projet_id}/documents",
    response_model=list[DocumentProjetPublic],
    operation_id="listProjectDocumentsForResearcher",
    summary="Lister les documents mis à disposition sur un projet affecté",
)
def lister_documents_route(
    projet_id: uuid.UUID,
    current_user: User = Depends(require_role(Role.RESEARCHER)),
    session: Session = Depends(get_session),
) -> list[DocumentProjetPublic]:
    documents = projets.lister_documents(session, current_user.id, projet_id)
    return [
        DocumentProjetPublic(
            id=document.id,
            report_id=document.report_id,
            company_id=document.report.company_id,
            company_name=document.report.company.name,
            fiscal_year=document.report.fiscal_year,
            added_at=document.added_at,
        )
        for document in documents
    ]


def _analyse_detail(session: Session, analyse: Analysis) -> AnalyseDetail:
    return AnalyseDetail(
        **AnalysePublic.model_validate(analyse).model_dump(),
        company_ids=analyses.lister_entreprise_ids(session, analyse.id),
    )


@router.post(
    "/researcher/projets/{projet_id}/analyses",
    response_model=AnalyseDetail,
    status_code=201,
    operation_id="createAnalysis",
    summary="Créer une analyse (brouillon) sur un projet affecté",
)
def creer_analyse_route(
    projet_id: uuid.UUID,
    payload: CreerAnalyseRequest,
    current_user: User = Depends(require_role(Role.RESEARCHER)),
    session: Session = Depends(get_session),
) -> AnalyseDetail:
    analyse = analyses.creer_analyse(
        session, current_user.id, projet_id, payload.title, payload.content, payload.company_ids
    )
    return _analyse_detail(session, analyse)


@router.get(
    "/researcher/analyses",
    response_model=list[AnalysePublic],
    operation_id="listMyAnalyses",
    summary="Lister mes analyses, tous projets confondus",
)
def lister_mes_analyses_route(
    current_user: User = Depends(require_role(Role.RESEARCHER)),
    session: Session = Depends(get_session),
) -> list[Analysis]:
    return list(
        session.exec(select(Analysis).where(col(Analysis.researcher_id) == current_user.id)).all()
    )


def _analyse_ou_404(session: Session, chercheur_id: uuid.UUID, analyse_id: uuid.UUID) -> Analysis:
    analyse = session.get(Analysis, analyse_id)
    if analyse is None or analyse.researcher_id != chercheur_id:
        raise NotFoundError("Analyse introuvable.", code="analyse_introuvable")
    return analyse


@router.get(
    "/researcher/analyses/{analyse_id}",
    response_model=AnalyseDetail,
    operation_id="getAnalysisDetail",
    summary="Consulter le détail d'une analyse (statut, décision de l'institution)",
)
def consulter_analyse_route(
    analyse_id: uuid.UUID,
    current_user: User = Depends(require_role(Role.RESEARCHER)),
    session: Session = Depends(get_session),
) -> AnalyseDetail:
    analyse = _analyse_ou_404(session, current_user.id, analyse_id)
    return _analyse_detail(session, analyse)


@router.patch(
    "/researcher/analyses/{analyse_id}",
    response_model=AnalyseDetail,
    operation_id="updateAnalysis",
    summary="Modifier une analyse encore en brouillon",
)
def modifier_analyse_route(
    analyse_id: uuid.UUID,
    payload: ModifierAnalyseRequest,
    current_user: User = Depends(require_role(Role.RESEARCHER)),
    session: Session = Depends(get_session),
) -> AnalyseDetail:
    analyse = analyses.modifier_analyse(
        session, current_user.id, analyse_id, payload.title, payload.content, payload.company_ids
    )
    return _analyse_detail(session, analyse)


@router.post(
    "/researcher/analyses/{analyse_id}/soumettre",
    response_model=AnalyseDetail,
    operation_id="submitAnalysis",
    summary="Soumettre une analyse à la décision de l'institution",
)
def soumettre_analyse_route(
    analyse_id: uuid.UUID,
    current_user: User = Depends(require_role(Role.RESEARCHER)),
    session: Session = Depends(get_session),
) -> AnalyseDetail:
    analyse = analyses.soumettre_analyse(session, current_user.id, analyse_id)
    return _analyse_detail(session, analyse)


@router.post(
    "/researcher/analyses/{analyse_id}/corriger",
    response_model=AnalyseDetail,
    status_code=201,
    operation_id="correctAnalysis",
    summary="Créer une nouvelle version d'une analyse suite à une correction demandée",
)
def corriger_analyse_route(
    analyse_id: uuid.UUID,
    payload: ModifierAnalyseRequest,
    current_user: User = Depends(require_role(Role.RESEARCHER)),
    session: Session = Depends(get_session),
) -> AnalyseDetail:
    nouvelle = analyses.corriger_analyse(
        session, current_user.id, analyse_id, payload.title, payload.content, payload.company_ids
    )
    return _analyse_detail(session, nouvelle)


@router.get(
    "/researcher/analyses/{analyse_id}/historique",
    response_model=list[AnalysePublic],
    operation_id="getAnalysisHistory",
    summary="Reconstruire la chaîne complète des versions d'une analyse (v1 -> correction -> v2 -> ...)",
)
def historique_analyse_route(
    analyse_id: uuid.UUID,
    current_user: User = Depends(require_role(Role.RESEARCHER)),
    session: Session = Depends(get_session),
) -> list[Analysis]:
    return analyses.historique_analyse(session, current_user.id, analyse_id)


# --- Validation croisée (tâche 3.3) ---------------------------------------------------------


def _metadonnees_dataset(
    name: str = Form(),
    source_url: str = Form(),
    licence: str = Form(),
    scale_min: float = Form(default=0),
    scale_max: float = Form(default=100),
    higher_is_better: bool = Form(default=True),
) -> ReferenceDatasetRequest:
    """Champs de formulaire à plat à côté du fichier (un modèle Form mêlé à un fichier serait
    imbriqué par FastAPI) ; les règles de ReferenceDatasetRequest restent la seule validation,
    et leurs erreurs une 422 par champ comme toute validation de requête."""
    try:
        return ReferenceDatasetRequest(
            name=name,
            source_url=source_url,
            licence=licence,
            scale_min=scale_min,
            scale_max=scale_max,
            higher_is_better=higher_is_better,
        )
    except pydantic.ValidationError as exc:
        raise RequestValidationError(exc.errors(include_url=False)) from exc


@router.post(
    "/researcher/reference-datasets",
    response_model=ReferenceDatasetImportResult,
    status_code=201,
    operation_id="importReferenceDataset",
    summary="Importer un jeu de données ESG public (CSV) pour une validation croisée",
)
def import_reference_dataset(
    file: UploadFile,
    metadata: ReferenceDatasetRequest = Depends(_metadonnees_dataset),
    current_user: User = Depends(require_role(Role.RESEARCHER)),
    session: Session = Depends(get_session),
) -> ReferenceDatasetImportResult:
    # Lecture bornée : un octet de plus que la limite suffit à refuser le fichier.
    contenu = file.file.read(cross_validation.TAILLE_MAX_OCTETS + 1)
    return cross_validation.importer(session, current_user, metadata, contenu)


@router.get(
    "/researcher/reference-datasets",
    response_model=list[ReferenceDatasetSummary],
    operation_id="listReferenceDatasets",
    summary="Lister mes jeux de données de référence",
)
def list_reference_datasets(
    current_user: User = Depends(require_role(Role.RESEARCHER)),
    session: Session = Depends(get_session),
) -> list[ReferenceDatasetSummary]:
    return cross_validation.lister(session, current_user)


@router.get(
    "/researcher/reference-datasets/{dataset_id}/cross-validation",
    response_model=CrossValidationReport,
    operation_id="getCrossValidationReport",
    summary="Comparer les scores de la plateforme à un jeu de données de référence",
)
def get_cross_validation_report(
    dataset_id: uuid.UUID,
    current_user: User = Depends(require_role(Role.RESEARCHER)),
    session: Session = Depends(get_session),
) -> CrossValidationReport:
    return cross_validation.rapport(session, current_user, dataset_id)


@router.delete(
    "/researcher/reference-datasets/{dataset_id}",
    status_code=204,
    operation_id="deleteReferenceDataset",
    summary="Supprimer un jeu de données de référence",
)
def delete_reference_dataset(
    dataset_id: uuid.UUID,
    current_user: User = Depends(require_role(Role.RESEARCHER)),
    session: Session = Depends(get_session),
) -> None:
    cross_validation.supprimer(session, current_user, dataset_id)

