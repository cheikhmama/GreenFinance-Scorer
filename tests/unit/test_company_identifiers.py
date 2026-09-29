import pytest

from app.company.identifiers import isin_valide, lei_valide


@pytest.mark.parametrize(
    "isin",
    ["US0378331005", "FR0000131104", "DE000BAY0017"],  # Apple, BNP Paribas, Bayer
)
def test_isin_reels_valides(isin: str) -> None:
    assert isin_valide(isin)


@pytest.mark.parametrize(
    "isin",
    [
        "US0378331004",  # chiffre de contrôle faux
        "us0378331005",  # minuscules : la normalisation est faite en amont, jamais ici
        "US037833100",  # trop court
        "1S0378331005",  # pays non alphabétique
        "US03783310O5",  # lettre à la place du chiffre de contrôle
    ],
)
def test_isin_invalides(isin: str) -> None:
    assert not isin_valide(isin)


@pytest.mark.parametrize("lei", ["HWUPKR0MPOU8FGXBT394", "5493001KJTIIGC8Y1R12"])
def test_lei_reels_valides(lei: str) -> None:
    assert lei_valide(lei)


@pytest.mark.parametrize(
    "lei",
    [
        "HWUPKR0MPOU8FGXBT395",  # chiffres de contrôle faux
        "HWUPKR0MPOU8FGXBT39",  # trop court
        "HWUPKR0MPOU8FGXBT3A4",  # contrôle non numérique
        "hwupkr0mpou8fgxbt394",
    ],
)
def test_lei_invalides(lei: str) -> None:
    assert not lei_valide(lei)
