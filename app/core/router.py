"""Routes HTTP des notifications (Phase 5 §10).

Notification (app/core/models.py) n'appartient à aucun espace acteur : tout utilisateur
authentifié, quel que soit son rôle, consulte et marque lues ses propres notifications — d'où
un router.py directement sous app/core/ plutôt que dupliqué dans admin/audit/company/investor/
researcher/institution. La logique vit dans app/core/notifications.py, ce router ne fait
qu'appliquer le contrôle d'accès et l'appeler (même convention que les autres modules).
"""

import math
import uuid

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.auth.models import Utilisateur
from app.core.dependencies import get_current_user, get_session
from app.core.models import Notification
from app.core.notifications import lister_mes_notifications, marquer_lue
from app.core.schemas import NotificationPublic, Page

router = APIRouter(tags=["notifications"])


@router.get(
    "/notifications",
    response_model=Page[NotificationPublic],
    operation_id="listMyNotifications",
    summary="Lister mes notifications, les plus récentes d'abord",
)
def lister_mes_notifications_route(
    non_lues_seulement: bool = Query(False, description="Ne renvoyer que les notifications non lues"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: Utilisateur = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Page[NotificationPublic]:
    items, total = lister_mes_notifications(
        session,
        current_user.id,
        non_lues_seulement=non_lues_seulement,
        page=page,
        page_size=page_size,
    )
    return Page[NotificationPublic](
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        pages=math.ceil(total / page_size) if page_size else 0,
    )


@router.post(
    "/notifications/{notification_id}/lu",
    response_model=NotificationPublic,
    operation_id="markNotificationRead",
    summary="Marquer une de mes notifications comme lue",
)
def marquer_notification_lue_route(
    notification_id: uuid.UUID,
    current_user: Utilisateur = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Notification:
    return marquer_lue(session, current_user.id, notification_id)
