"""Routes HTTP de l'espace Entreprise.

Statut : Étape 5/10 + Phase 4 §4.1/§4.2. Dépôt, liste, détail, nouvelle version (correction) —
la logique vit dans app/company/rapports.py (et app/company/upload_validation.py pour la
validation du fichier), ce router ne fait qu'appliquer le contrôle d'accès par rôle et l'appeler.

app/ingestion/ n'expose pas de router.py (voir ARCHITECTURE.md §2 : ingestion n'est pas une
surface API directe) — la logique appelée ici invoque directement app.ingestion.extractor.
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Form, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session

from app.auth.models import Utilisateur
from app.auth.permissions import require_role
from app.company.import_rate_limit import enforce_url_import_rate_limit
from app.company.models import Company
from app.company.rapports import (
    creer_correction,
    deposer_rapport,
    importer_rapport_par_url,
    lister_mes_rapports,
    rapport_de_lentreprise,
)
from app.company.schemas import EntreprisePublic, ImporterRapportParURLRequest
from app.core import storage
from app.core.dependencies import get_session
from app.core.enums import Role, TypeRapport
from app.core.exceptions import NotFoundError, ValidationError
from app.ingestion.models import ESGReport
from app.ingestion.schemas import RapportESGDetail, RapportESGPublic
from app.scoring.engine import score_public

router = APIRouter(tags=["company"])


def _entreprise_id(current_user: Utilisateur) -> uuid.UUID:
    if current_user.entreprise is None:
        raise ValidationError(
            "Aucune entreprise n'est rattachée à ce compte.", code="entreprise_non_rattachee"
        )
    return current_user.entreprise.id


@router.get(
    "/company/profil",
    response_model=EntreprisePublic,
    operation_id="getMyCompanyProfile",
    summary="Consulter la fiche de mon entreprise, telle que vue par les investisseurs",
)
def consulter_mon_profil_route(
    current_user: Utilisateur = Depends(require_role(Role.ENTREPRISE)),
) -> Company:
    _entreprise_id(current_user)  # lève si aucune entreprise n'est rattachée
    assert current_user.entreprise is not None
    return current_user.entreprise


@router.get(
    "/company/rapports",
    response_model=list[RapportESGPublic],
    operation_id="listCompanyReports",
    summary="Lister les rapports déposés par l'entreprise",
)
def lister_rapports_route(
    current_user: Utilisateur = Depends(require_role(Role.ENTREPRISE)),
    session: Session = Depends(get_session),
) -> list[ESGReport]:
    return lister_mes_rapports(session, _entreprise_id(current_user))


@router.post(
    "/company/rapports",
    response_model=RapportESGPublic,
    status_code=201,
    operation_id="submitCompanyReport",
    summary="Déposer un rapport ESG/climat",
)
def deposer_rapport_route(
    background_tasks: BackgroundTasks,
    fichier: UploadFile,
    type: TypeRapport = Form(...),
    annee_reporting: int = Form(...),
    current_user: Utilisateur = Depends(require_role(Role.ENTREPRISE)),
    session: Session = Depends(get_session),
) -> ESGReport:
    contenu = fichier.file.read()
    return deposer_rapport(
        session,
        background_tasks,
        _entreprise_id(current_user),
        contenu,
        type,
        annee_reporting,
        fichier.filename,
    )


@router.post(
    "/company/rapports/import-url",
    response_model=RapportESGPublic,
    status_code=201,
    operation_id="importCompanyReportFromURL",
    summary="Importer un rapport ESG/climat depuis une URL (canal automatique)",
)
def importer_rapport_par_url_route(
    background_tasks: BackgroundTasks,
    payload: ImporterRapportParURLRequest,
    current_user: Utilisateur = Depends(require_role(Role.ENTREPRISE, Role.ADMINISTRATEUR)),
    session: Session = Depends(get_session),
) -> ESGReport:
    if current_user.role == Role.ENTREPRISE:
        # Un entreprise_id fourni par un appelant Entreprise est toujours ignoré -- jamais fait
        # confiance à un client pour désigner une entreprise autre que la sienne.
        entreprise_id = _entreprise_id(current_user)
    else:
        if payload.entreprise_id is None:
            raise ValidationError(
                "entreprise_id est requis pour un import déclenché par un administrateur.",
                code="entreprise_id_requis",
            )
        if session.get(Company, payload.entreprise_id) is None:
            raise NotFoundError("Entreprise introuvable.", code="entreprise_introuvable")
        entreprise_id = payload.entreprise_id

    enforce_url_import_rate_limit(entreprise_id)
    return importer_rapport_par_url(
        session,
        background_tasks,
        entreprise_id,
        payload.url,
        payload.type,
        payload.annee_reporting,
    )


@router.post(
    "/company/rapports/{rapport_id}/corrections",
    response_model=RapportESGPublic,
    status_code=201,
    operation_id="submitCompanyReportCorrection",
    summary="Déposer une nouvelle version d'un rapport en attente de correction",
)
def creer_correction_route(
    rapport_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    fichier: UploadFile,
    annee_reporting: int = Form(...),
    current_user: Utilisateur = Depends(require_role(Role.ENTREPRISE)),
    session: Session = Depends(get_session),
) -> ESGReport:
    contenu = fichier.file.read()
    return creer_correction(
        session,
        background_tasks,
        rapport_id,
        _entreprise_id(current_user),
        contenu,
        annee_reporting,
        fichier.filename,
    )


@router.get(
    "/company/rapports/{rapport_id}",
    response_model=RapportESGDetail,
    operation_id="getCompanyReport",
    summary="Consulter le détail d'un rapport déposé par l'entreprise",
)
def consulter_rapport(
    rapport_id: uuid.UUID,
    current_user: Utilisateur = Depends(require_role(Role.ENTREPRISE)),
    session: Session = Depends(get_session),
) -> RapportESGDetail:
    rapport = rapport_de_lentreprise(session, rapport_id, _entreprise_id(current_user))
    detail = RapportESGDetail.model_validate(rapport)
    return detail.model_copy(update={"score_officiel": score_public(session, rapport_id)})


@router.get(
    "/company/rapports/{rapport_id}/fichier",
    operation_id="getCompanyReportOriginalFile",
    summary="Télécharger le PDF original tel que déposé (non le rapport de synthèse)",
)
def telecharger_rapport_original_route(
    rapport_id: uuid.UUID,
    current_user: Utilisateur = Depends(require_role(Role.ENTREPRISE)),
    session: Session = Depends(get_session),
) -> FileResponse:
    rapport = rapport_de_lentreprise(session, rapport_id, _entreprise_id(current_user))
    return FileResponse(storage.resolve_path(rapport.source_file), media_type="application/pdf")


@router.get(
    "/company/rapports/{rapport_id}/synthese/fichier",
    operation_id="getCompanyReportSynthesisFile",
    summary="Télécharger le rapport de synthèse généré par la plateforme",
)
def telecharger_rapport_synthese_route(
    rapport_id: uuid.UUID,
    current_user: Utilisateur = Depends(require_role(Role.ENTREPRISE)),
    session: Session = Depends(get_session),
) -> FileResponse:
    rapport = rapport_de_lentreprise(session, rapport_id, _entreprise_id(current_user))
    if rapport.synthesis_report_path is None:
        # Code distinct de "rapport introuvable" -- sûr à distinguer ici, la propriété est déjà
        # établie par rapport_de_lentreprise ci-dessus, donc cela ne confirme rien à un tiers.
        raise NotFoundError(
            "Le rapport de synthèse n'a pas encore été généré pour ce rapport.",
            code="synthese_non_generee",
        )
    return FileResponse(
        storage.resolve_path(rapport.synthesis_report_path), media_type="application/pdf"
    )
