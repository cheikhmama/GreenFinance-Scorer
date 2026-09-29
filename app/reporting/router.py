"""Routes /reports (tâche 1.5). Le contrôle d'accès fin (périmètre par rôle) vit dans
app/reporting/sessions.py ; ce router n'exige qu'une session authentifiée."""

import math
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Query, UploadFile
from sqlmodel import Session

from app.auth.models import User
from app.company.upload_validation import TAILLE_MAX_OCTETS
from app.core.dependencies import get_current_user, get_session
from app.core.enums import ReportStatus, TypeRapport
from app.core.schemas import Page
from app.reporting import sessions
from app.reporting.schemas import ReportCreateRequest, ReportResponse

router = APIRouter(tags=["reports"])


@router.post(
    "/reports",
    response_model=ReportResponse,
    status_code=201,
    operation_id="openReport",
    summary="Ouvrir une déclaration (brouillon) pour un exercice",
)
def open_report(
    payload: ReportCreateRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ReportResponse:
    return ReportResponse.depuis(sessions.ouvrir(session, current_user, payload))


@router.get(
    "/reports",
    response_model=Page[ReportResponse],
    operation_id="listReports",
    summary="Lister les rapports visibles pour mon rôle",
)
def list_reports(
    fiscal_year: int | None = None,
    status: ReportStatus | None = None,
    report_type: TypeRapport | None = None,
    company_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Page[ReportResponse]:
    rapports, total = sessions.lister(
        session,
        current_user,
        fiscal_year=fiscal_year,
        status=status,
        report_type=report_type,
        company_id=company_id,
        page=page,
        page_size=page_size,
    )
    return Page[ReportResponse](
        items=[ReportResponse.depuis(rapport) for rapport in rapports],
        page=page,
        page_size=page_size,
        total=total,
        pages=math.ceil(total / page_size),
    )


@router.get(
    "/reports/{report_id}",
    response_model=ReportResponse,
    operation_id="getReport",
    summary="Consulter un rapport de mon périmètre",
)
def get_report(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ReportResponse:
    return ReportResponse.depuis(sessions.consulter(session, current_user, report_id))


@router.post(
    "/reports/{report_id}/submit",
    response_model=ReportResponse,
    operation_id="submitReport",
    summary="Déposer le PDF d'un brouillon et le soumettre à l'extraction",
)
def submit_report(
    report_id: uuid.UUID,
    file: UploadFile,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ReportResponse:
    # Lecture bornée : un octet de plus que la taille maximale suffit à la refuser, sans jamais
    # charger en mémoire un fichier arbitrairement gros.
    contenu = file.file.read(TAILLE_MAX_OCTETS + 1)
    rapport = sessions.soumettre(
        session, background_tasks, current_user, report_id, contenu, file.filename
    )
    return ReportResponse.depuis(rapport)


@router.delete(
    "/reports/{report_id}",
    status_code=204,
    operation_id="discardReport",
    summary="Abandonner un brouillon",
)
def discard_report(
    report_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> None:
    sessions.abandonner(session, current_user, report_id)
