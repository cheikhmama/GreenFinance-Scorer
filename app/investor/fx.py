"""Conversion de devises pour les positions de portefeuille (Étape 15/16).

Taux statiques (config/fx/rates.yaml, chemin dans Settings.fx_rates_path) — pas d'API de change
en temps réel, décision prise pour garder la conversion déterministe et sans dépendance externe
tant qu'un vrai besoin de taux en temps réel n'est pas exprimé. Un montant converti n'est jamais
recalculé après coup (voir app/investor/models.py::PositionPortefeuille) : convertir() n'est
appelé qu'à la création d'une position, jamais en lecture.
"""

from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from pathlib import Path

import yaml

from app.core.enums import Currency
from app.core.exceptions import ValidationError

CENTIME = Decimal("0.01")
# Précision du taux figé sur la position (portfolio_positions.fx_rate_used, numeric(20,10)).
PRECISION_TAUX = Decimal("1e-10")


@lru_cache
def _charger_taux(chemin: str) -> dict[str, Decimal]:
    contenu = yaml.safe_load(Path(chemin).read_text(encoding="utf-8"))
    # str() d'abord : Decimal(1.08) garderait l'erreur binaire du float lu par YAML.
    return {devise: Decimal(str(taux)) for devise, taux in contenu["taux_vers_usd"].items()}


def _taux_vers_usd(devise: Currency, chemin_taux: str) -> Decimal:
    """Une devise de l'énumération absente du fichier de taux est une erreur de saisie à signaler
    (422), jamais une KeyError qui remonterait en 500."""
    taux = _charger_taux(chemin_taux).get(devise.value)
    if taux is None or taux <= 0:
        raise ValidationError(
            f"Aucun taux de change n'est disponible pour la devise {devise.value}.",
            code="devise_non_prise_en_charge",
        )
    return taux


def convertir(
    montant: Decimal, depuis: Currency, vers: Currency, chemin_taux: str
) -> tuple[Decimal, Decimal | None]:
    """Retourne (montant_converti, taux_change_utilise), en Decimal, le montant arrondi au centime.

    taux_change_utilise est None quand depuis == vers (aucune conversion nécessaire — voir
    PortfolioPosition.fx_rate_used/converted_amount, nuls dans ce cas précis). Sinon le montant
    converti vaut exactement montant × taux arrondi : le taux figé sur la position suffit à
    retrouver le montant converti."""
    if depuis == vers:
        return montant, None
    taux_direct = (_taux_vers_usd(depuis, chemin_taux) / _taux_vers_usd(vers, chemin_taux)).quantize(
        PRECISION_TAUX
    )
    return (montant * taux_direct).quantize(CENTIME, rounding=ROUND_HALF_UP), taux_direct
