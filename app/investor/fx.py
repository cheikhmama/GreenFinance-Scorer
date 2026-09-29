"""Conversion de devises pour les positions de portefeuille (Étape 15/16).

Taux statiques (config/fx/rates.yaml, chemin dans Settings.fx_rates_path) — pas d'API de change
en temps réel, décision prise pour garder la conversion déterministe et sans dépendance externe
tant qu'un vrai besoin de taux en temps réel n'est pas exprimé. Un montant converti n'est jamais
recalculé après coup (voir app/investor/models.py::PositionPortefeuille) : convertir() n'est
appelé qu'à la création d'une position, jamais en lecture.
"""

from functools import lru_cache
from pathlib import Path

import yaml

from app.core.enums import DevisePosition


@lru_cache
def _charger_taux(chemin: str) -> dict[str, float]:
    contenu = yaml.safe_load(Path(chemin).read_text(encoding="utf-8"))
    return contenu["taux_vers_usd"]


def convertir(
    montant: float, depuis: DevisePosition, vers: DevisePosition, chemin_taux: str
) -> tuple[float, float | None]:
    """Retourne (montant_converti, taux_change_utilise).

    taux_change_utilise est None quand depuis == vers (aucune conversion nécessaire — voir
    PortfolioPosition.fx_rate_used/converted_amount, nuls dans ce cas précis)."""
    if depuis == vers:
        return montant, None

    taux_vers_usd = _charger_taux(chemin_taux)
    montant_usd = montant * taux_vers_usd[depuis.value]
    taux_direct = taux_vers_usd[depuis.value] / taux_vers_usd[vers.value]
    montant_cible = montant_usd / taux_vers_usd[vers.value]
    return montant_cible, taux_direct
