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


def avec_acteurs(
    session: Session, entrees: list[AuditLogEntry]
) -> list[JournalAuditPublic]:
    """Joint à chaque entrée le nom/e-mail/rôle de l'acteur, et — quand la ressource visée est un
    compte (resource_type == "User", ex. une désactivation) — le rôle de ce compte, en une seule
    requête par page plutôt qu'un aller-retour par ligne."""
    ids_acteurs = {e.actor_id for e in entrees if e.actor_id is not None}
    ids_ressources_compte = {
        e.resource_id
        for e in entrees
        if e.resource_id is not None and e.resource_type == "User"
    }
    ids = ids_acteurs | ids_ressources_compte
    comptes = (
        {u.id: u for u in session.exec(select(User).where(col(User.id).in_(ids))).all()}
        if ids
        else {}
    )
    lignes = []
    for entree in entrees:
        acteur = comptes.get(entree.actor_id) if entree.actor_id is not None else None
        ligne = JournalAuditPublic.model_validate(entree)
        if acteur is not None:
            ligne.actor_name = acteur.name
            ligne.actor_email = acteur.email
            ligne.actor_role = acteur.role
        if entree.resource_type == "User" and entree.resource_id is not None:
            compte_vise = comptes.get(entree.resource_id)
            if compte_vise is not None:
                ligne.resource_user_role = compte_vise.role
        lignes.append(ligne)
    return lignes


def compter_actions(session: Session) -> list[tuple[str, int]]:
    """Nombre d'entrées par action, décroissant — sert à trier le filtre d'actions de la page
    Journal d'audit par pertinence réelle : une action jamais survenue passe en bas plutôt qu'en
    tête d'un ordre alphabétique qui ne dit rien de ce que la base contient vraiment."""
    return list(
        session.exec(
            select(AuditLogEntry.action, func.count())
            .group_by(col(AuditLogEntry.action))
            .order_by(func.count().desc())
        ).all()
    )


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
            or_(
                col(AuditLogEntry.actor_id) == concerne_id,
                col(AuditLogEntry.resource_id) == concerne_id,
            )
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

    total = session.exec(
        select(func.count()).select_from(AuditLogEntry).where(*filtres)
    ).one()
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
