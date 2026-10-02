"""Routes des demandes d'accès (tâche 5.10) : dépôt public, examen par l'Administrateur."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from sqlmodel import Session

from app.access_requests import service
from app.access_requests.schemas import (
    AccessDecisionRequest,
    AccessRequestCreate,
    AccessRequestView,
)
from app.auth.models import User
from app.auth.permissions import require_role
from app.core.dependencies import get_session
from app.core.enums import AccessRequestStatus, Role

router = APIRouter(tags=["access-requests"])


@router.post(
    "/access-requests",
    status_code=202,
    operation_id="requestAccess",
    summary="Demander un accès Investisseur ou Chercheur (validation par l'Administrateur)",
    responses={
        202: {"description": "Demande reçue. Réponse identique que la demande aboutisse ou non."},
        429: {"description": "Limite de demandes par adresse IP atteinte."},
        503: {"description": "Envoi d'e-mails indisponible."},
    },
)
def request_access(
    payload: AccessRequestCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> None:
    service.demander_acces(
        session, payload, request.client.host if request.client else None, background_tasks
    )


@router.get(
    "/admin/access-requests",
    response_model=list[AccessRequestView],
    operation_id="listAccessRequests",
    summary="Lister les demandes d'accès Investisseur / Chercheur",
)
def list_access_requests(
    status: AccessRequestStatus | None = None,
    _admin: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> list[AccessRequestView]:
    return service.lister_demandes(session, status)


@router.patch(
    "/admin/access-requests/{request_id}",
    response_model=AccessRequestView,
    operation_id="decideAccessRequest",
    summary="Approuver (lien d'activation) ou refuser (motif) une demande d'accès",
)
def decide_access_request(
    request_id: uuid.UUID,
    payload: AccessDecisionRequest,
    background_tasks: BackgroundTasks,
    admin: User = Depends(require_role(Role.ADMIN)),
    session: Session = Depends(get_session),
) -> AccessRequestView:
    return service.decider_demande(
        session, admin.id, request_id, payload.decision, payload.reason, background_tasks
    )
