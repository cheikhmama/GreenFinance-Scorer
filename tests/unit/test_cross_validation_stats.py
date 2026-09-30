"""Statistiques de la validation croisée (tâche 3.3) — implémentées sans dépendance."""

import warnings

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from app.researcher.cross_validation import rangs_moyens, spearman, sur_cent


def test_rangs_moyens_avec_ex_aequo() -> None:
    assert rangs_moyens([10, 30, 20, 30]) == [1, 3.5, 2, 3.5]


def test_spearman_cas_limites() -> None:
    assert spearman([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1)
    assert spearman([1, 2, 3, 4], [40, 30, 20, 10]) == pytest.approx(-1)
    # Monotone mais non linéaire : une corrélation de RANG reste parfaite.
    assert spearman([1, 2, 3, 4], [1, 8, 27, 1000]) == pytest.approx(1)
    assert spearman([1, 2], [1, 2]) is None  # trop peu de paires
    assert spearman([1, 2, 3], [5, 5, 5]) is None  # série constante : jamais un 0 trompeur


@settings(max_examples=200, deadline=None)
@given(paires=st.lists(st.tuples(st.integers(0, 5), st.integers(0, 5)), min_size=3, max_size=40))
def test_spearman_identique_a_scipy_ex_aequo_compris(paires) -> None:
    stats = pytest.importorskip("scipy.stats")
    x = [float(a) for a, _ in paires]
    y = [float(b) for _, b in paires]

    with warnings.catch_warnings():
        # Séries constantes tirées exprès : scipy prévient qu'il renvoie NaN, attendu ici.
        warnings.simplefilter("ignore")
        attendu = stats.spearmanr(x, y).statistic
    obtenu = spearman(x, y)

    if obtenu is None:
        assert len(set(x)) == 1 or len(set(y)) == 1
    else:
        assert obtenu == pytest.approx(attendu, abs=1e-9)


def test_echelle_ramenee_sur_cent_dans_les_deux_sens() -> None:
    assert sur_cent(750, 0, 1000, True) == pytest.approx(75)
    # Score de risque : 10 sur 50 (faible risque) vaut 80 sur l'échelle « plus haut = meilleur ».
    assert sur_cent(10, 0, 50, False) == pytest.approx(80)
