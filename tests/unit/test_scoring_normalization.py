import pytest

from app.scoring.normalization import normaliser


def test_plus_haut_est_meilleur_valeur_mediane() -> None:
    assert normaliser(25.0, borne_min=0, borne_max=50, plus_haut_est_meilleur=True) == 50.0


def test_plus_bas_est_meilleur_valeur_mediane() -> None:
    assert normaliser(25.0, borne_min=0, borne_max=50, plus_haut_est_meilleur=False) == 50.0


def test_plus_haut_est_meilleur_borne_min() -> None:
    assert normaliser(0.0, borne_min=0, borne_max=50, plus_haut_est_meilleur=True) == 0.0


def test_plus_haut_est_meilleur_borne_max() -> None:
    assert normaliser(50.0, borne_min=0, borne_max=50, plus_haut_est_meilleur=True) == 100.0


def test_plus_bas_est_meilleur_borne_min_donne_100() -> None:
    assert normaliser(0.0, borne_min=0, borne_max=5, plus_haut_est_meilleur=False) == 100.0


def test_plus_bas_est_meilleur_borne_max_donne_0() -> None:
    assert normaliser(5.0, borne_min=0, borne_max=5, plus_haut_est_meilleur=False) == 0.0


@pytest.mark.parametrize("valeur", [-10.0, 60.0])
def test_valeur_hors_bornes_est_plafonnee(valeur: float) -> None:
    resultat = normaliser(valeur, borne_min=0, borne_max=50, plus_haut_est_meilleur=True)
    assert 0.0 <= resultat <= 100.0
