import pytest

from app.core.config import get_settings
from app.core.enums import DevisePosition
from app.investor.fx import convertir

_CHEMIN_TAUX = get_settings().fx_rates_path


def test_convertir_sans_changement_de_devise_ne_convertit_pas() -> None:
    montant, taux = convertir(1000.0, DevisePosition.EUR, DevisePosition.EUR, _CHEMIN_TAUX)

    assert montant == 1000.0
    assert taux is None


def test_convertir_entre_deux_devises_retourne_un_taux() -> None:
    montant, taux = convertir(100.0, DevisePosition.EUR, DevisePosition.USD, _CHEMIN_TAUX)

    assert taux is not None
    assert montant == 100.0 * taux


def test_convertir_est_reversible_aller_retour() -> None:
    montant_usd, _ = convertir(100.0, DevisePosition.EUR, DevisePosition.USD, _CHEMIN_TAUX)
    montant_retour, _ = convertir(montant_usd, DevisePosition.USD, DevisePosition.EUR, _CHEMIN_TAUX)

    assert montant_retour == pytest.approx(100.0)
