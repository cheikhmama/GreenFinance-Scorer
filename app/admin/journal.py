"""Consultation du journal d'audit par l'Administrateur (Phase 3 §3.5).

app/core/audit.py::auditer écrit chaque entrée ; ce module se limite à la lecture paginée et
filtrée — jamais d'écriture ici, la table reste immuable une fois construite ailleurs.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement
from sqlmodel import Session, col, func, or_, select

from app.core.models import AuditLogEntry


def lister_journal_audit(
    session: Session,
    *,
    acteur_id: UUID | None = None,
    action: str | None = None,
    type_ressource: str | None = None,
    id_ressource: UUID | None = None,
    concerne_id: UUID | None = None,
    depuis: datetime | None = None,
    jusqu_a: datetime | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[AuditLogEntry], int]:
    """Page d'entrées du journal d'audit, plus récentes d'abord, filtrée par tout sous-ensemble
    des critères fournis. `concerne_id` reconstruit l'historique d'activité d'un utilisateur
    précis, qu'il ait agi (acteur_id) ou subi l'action (id_ressource, ex. désactivé par un admin)
    — remplace acteur_id/id_ressource plutôt que de s'y combiner, les deux usages ne se recoupent
    pas (vue "un utilisateur précis" vs vue "filtrage libre" de la page journal générale)."""
    filtres: list[ColumnElement[bool]] = []
    if concerne_id is not None:
        filtres.append(
            or_(col(AuditLogEntry.actor_id) == concerne_id, col(AuditLogEntry.resource_id) == concerne_id)
        )
    elif acteur_id is not None:
        filtres.append(col(AuditLogEntry.actor_id) == acteur_id)
    if action is not None:
        filtres.append(col(AuditLogEntry.action) == action)
    if type_ressource is not None:
        filtres.append(col(AuditLogEntry.resource_type) == type_ressource)
    if concerne_id is None and id_ressource is not None:
        filtres.append(col(AuditLogEntry.resource_id) == id_ressource)
    if depuis is not None:
        filtres.append(col(AuditLogEntry.occurred_at) >= depuis)
    if jusqu_a is not None:
        filtres.append(col(AuditLogEntry.occurred_at) <= jusqu_a)

    total = session.exec(select(func.count()).select_from(AuditLogEntry).where(*filtres)).one()
    items = list(
        session.exec(
            select(AuditLogEntry)
            .where(*filtres)
            .order_by(col(AuditLogEntry.occurred_at).desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return items, total
