from decimal import Decimal
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.core.enums import DevisePosition
from app.core.exceptions import ValidationError
from app.investor.fx import convertir

_CHEMIN_TAUX = get_settings().fx_rates_path


def test_convertir_sans_changement_de_devise_ne_convertit_pas() -> None:
    montant, taux = convertir(Decimal("1000.00"), DevisePosition.EUR, DevisePosition.EUR, _CHEMIN_TAUX)

    assert montant == Decimal("1000.00")
    assert taux is None


def test_convertir_entre_deux_devises_retourne_un_taux_exact() -> None:
    montant, taux = convertir(Decimal("100.00"), DevisePosition.EUR, DevisePosition.USD, _CHEMIN_TAUX)

    # Decimal de bout en bout : 1.08 lu dans le YAML reste 1.08, pas 1.0800000000000000710…
    assert taux == Decimal("1.08")
    assert montant == Decimal("108.00")


def test_convertir_arrondit_au_centime_et_le_taux_fige_retrouve_le_montant() -> None:
    montant, taux = convertir(Decimal("1234.57"), DevisePosition.MRU, DevisePosition.EUR, _CHEMIN_TAUX)

    assert taux is not None
    assert montant == montant.quantize(Decimal("0.01"))
    assert montant == (Decimal("1234.57") * taux).quantize(Decimal("0.01"))


def test_convertir_est_reversible_aller_retour() -> None:
    montant_usd, _ = convertir(Decimal("100.00"), DevisePosition.EUR, DevisePosition.USD, _CHEMIN_TAUX)
    montant_retour, _ = convertir(montant_usd, DevisePosition.USD, DevisePosition.EUR, _CHEMIN_TAUX)

    assert montant_retour == Decimal("100.00")


def test_devise_absente_du_fichier_de_taux_donne_une_422(tmp_path: Path) -> None:
    """Une devise de l'énumération sans taux ne doit jamais remonter en KeyError (500)."""
    chemin = tmp_path / "rates.yaml"
    chemin.write_text("version: 1\ntaux_vers_usd:\n  USD: 1.0\n  EUR: 1.08\n", encoding="utf-8")

    with pytest.raises(ValidationError) as erreur:
        convertir(Decimal("10.00"), DevisePosition.MRU, DevisePosition.USD, str(chemin))

    assert erreur.value.code == "devise_non_prise_en_charge"
