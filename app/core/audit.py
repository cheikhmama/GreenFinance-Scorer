"""Écriture du journal d'audit (app/core/models.py::AuditLogEntry).

Même convention que app/core/notifications.py::notifier — petit utilitaire partagé plutôt que
dupliqué dans chaque module qui déclenche une entrée d'audit.
"""

import uuid

from sqlmodel import Session

from app.core.models import AuditLogEntry


def auditer(
    session: Session,
    actor_id: uuid.UUID | None,
    action: str,
    resource_type: str,
    resource_id: uuid.UUID | None,
    result: str,
    old_value: str | None = None,
    new_value: str | None = None,
    correlation_id: str | None = None,
) -> AuditLogEntry:
    """Construit et ajoute une AuditLogEntry à la session — ne commit jamais : l'appelant
    contrôle la limite de la transaction (même convention que notifier).

    old_value/new_value : jamais un mot de passe, un jeton, un contenu de document
    ou une donnée personnelle au-delà de ce qui est déjà public dans l'API — seulement des
    champs non sensibles (ex. un rôle, un statut actif/inactif)."""
    entree = AuditLogEntry(
        actor_id=actor_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        result=result,
        old_value=old_value,
        new_value=new_value,
        correlation_id=correlation_id,
    )
    session.add(entree)
    return entree
