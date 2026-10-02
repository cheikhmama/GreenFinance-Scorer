"""Consultation du journal d'audit par l'Administrateur (Phase 3 §3.5).

app/core/audit.py::auditer écrit chaque entrée ; ce module se limite à la lecture paginée et
filtrée — jamais d'écriture ici, la table reste immuable une fois construite ailleurs.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement
from sqlmodel import Session, col, func, or_, select

from app.admin.schemas import JournalAuditPublic
from app.auth.models import User
from app.core.models import AuditLogEntry


def avec_acteurs(session: Session, entrees: list[AuditLogEntry]) -> list[JournalAuditPublic]:
    """Joint le nom et l'e-mail de l'acteur à chaque entrée, en une seule requête par page."""
    ids = {e.actor_id for e in entrees if e.actor_id is not None}
    acteurs = (
        {u.id: u for u in session.exec(select(User).where(col(User.id).in_(ids))).all()}
        if ids
        else {}
    )
    lignes = []
    for entree in entrees:
        acteur = acteurs.get(entree.actor_id) if entree.actor_id is not None else None
        ligne = JournalAuditPublic.model_validate(entree)
        if acteur is not None:
            ligne.actor_name = acteur.name
            ligne.actor_email = acteur.email
        lignes.append(ligne)
    return lignes


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
