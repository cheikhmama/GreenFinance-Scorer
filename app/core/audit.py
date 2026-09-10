"""Écriture du journal d'audit (app/core/models.py::JournalAudit).

Même convention que app/core/notifications.py::notifier — petit utilitaire partagé plutôt que
dupliqué dans chaque module qui déclenche une entrée d'audit.
"""

import uuid

from sqlmodel import Session

from app.core.models import JournalAudit


def auditer(
    session: Session,
    acteur_id: uuid.UUID | None,
    action: str,
    type_ressource: str,
    id_ressource: uuid.UUID | None,
    resultat: str,
    ancienne_valeur: str | None = None,
    nouvelle_valeur: str | None = None,
    correlation_id: str | None = None,
) -> JournalAudit:
    """Construit et ajoute une JournalAudit à la session — ne commit jamais : l'appelant
    contrôle la limite de la transaction (même convention que notifier).

    ancienne_valeur/nouvelle_valeur : jamais un mot de passe, un jeton, un contenu de document
    ou une donnée personnelle au-delà de ce qui est déjà public dans l'API — seulement des
    champs non sensibles (ex. un rôle, un statut actif/inactif)."""
    entree = JournalAudit(
        acteur_id=acteur_id,
        action=action,
        type_ressource=type_ressource,
        id_ressource=id_ressource,
        resultat=resultat,
        ancienne_valeur=ancienne_valeur,
        nouvelle_valeur=nouvelle_valeur,
        correlation_id=correlation_id,
    )
    session.add(entree)
    return entree
