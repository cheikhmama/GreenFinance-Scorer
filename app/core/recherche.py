"""Recherche textuelle « contient » (tâche 4.3).

`%` et `_` sont des jokers de LIKE/ILIKE : sans échappement, une recherche « % » renvoie tout et
« _ » n'importe quel caractère — et une saisie contrôlée par l'utilisateur ne doit jamais
devenir une partie du motif. `contient` échappe la saisie et déclare le caractère
d'échappement, pour chaque colonne cherchée.
"""

from typing import Any

from sqlalchemy import ColumnElement, or_
from sqlmodel import col

_ECHAPPEMENT = "\\"


def motif_contient(recherche: str) -> str:
    echappee = (
        recherche.replace(_ECHAPPEMENT, _ECHAPPEMENT * 2)
        .replace("%", f"{_ECHAPPEMENT}%")
        .replace("_", f"{_ECHAPPEMENT}_")
    )
    return f"%{echappee}%"


def contient(recherche: str, *colonnes: Any) -> ColumnElement[bool]:
    """Vrai si l'une des colonnes contient littéralement `recherche` (casse ignorée)."""
    motif = motif_contient(recherche)
    conditions = [col(colonne).ilike(motif, escape=_ECHAPPEMENT) for colonne in colonnes]
    return conditions[0] if len(conditions) == 1 else or_(*conditions)
