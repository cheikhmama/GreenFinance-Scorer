"""Contrôles KYC (app/admin/kyc.py, tâche 5.3) : client GLEIF, comparaison des noms et du domaine."""

import uuid

import httpx
import pytest

import app.core.registre_modeles  # noqa: F401  -- enregistre tous les modèles (relations de Company)
from app.admin import kyc
from app.company.models import Company
from app.core.enums import KycCheckResult

FICHE = {
    "lei": "5493001KJTIIGC8Y1R12",
    "entity": {
        "legalName": {"name": "Minière du Nord S.A.", "language": "fr"},
        "otherNames": [{"name": "MDN Mining", "language": "en", "type": "TRADING_OR_OPERATING_NAME"}],
        "status": "ACTIVE",
    },
    "registration": {"status": "ISSUED"},
}


def _gleif_repond(monkeypatch, reponse: httpx.Response | Exception) -> list[str]:
    appels: list[str] = []

    def _get(url, **_kwargs):
        appels.append(url)
        if isinstance(reponse, Exception):
            raise reponse
        return reponse

    monkeypatch.setattr(kyc.httpx, "get", _get)
    return appels


def test_client_gleif_lit_les_attributs_de_la_fiche(monkeypatch) -> None:
    appels = _gleif_repond(monkeypatch, httpx.Response(200, json={"data": {"attributes": FICHE}}))

    assert kyc.recuperer_fiche_gleif("5493001KJTIIGC8Y1R12") == FICHE
    assert appels == ["https://api.gleif.org/api/v1/lei-records/5493001KJTIIGC8Y1R12"]


def test_lei_inconnu_de_la_gleif(monkeypatch) -> None:
    _gleif_repond(monkeypatch, httpx.Response(404, text="<html>Not Found</html>"))

    assert kyc.recuperer_fiche_gleif("5493001KJTIIGC8Y1R12") is None


@pytest.mark.parametrize(
    "reponse",
    [
        httpx.ConnectTimeout("délai"),
        httpx.ConnectError("réseau"),
        httpx.Response(503, text="maintenance"),
        httpx.Response(200, text="pas du json"),
        httpx.Response(200, json={"data": None}),
    ],
    ids=["delai", "reseau", "503", "pas-json", "sans-attributs"],
)
def test_gleif_inexploitable_devient_indisponible(monkeypatch, reponse) -> None:
    _gleif_repond(monkeypatch, reponse)

    with pytest.raises(kyc.GleifIndisponible):
        kyc.recuperer_fiche_gleif("5493001KJTIIGC8Y1R12")


@pytest.mark.parametrize(
    ("declare", "gleif"),
    [
        ("Minière du Nord", "MINIERE DU NORD S.A."),
        ("Atlas Industries SARL", "Atlas Industries"),
        ("Société  Générale", "societe generale"),
    ],
)
def test_noms_equivalents(declare, gleif) -> None:
    assert kyc.normaliser_nom(declare) == kyc.normaliser_nom(gleif)


def _entreprise(**champs) -> Company:
    return Company(**{"id": uuid.uuid4(), "name": "Minière du Nord", "sector": "Mines", "country": "MR", **champs})


def test_controles_gleif_reussis_par_nom_legal_ou_autre_nom(monkeypatch) -> None:
    monkeypatch.setattr(kyc, "recuperer_fiche_gleif", lambda _lei: FICHE)

    legal = kyc._controles_gleif(_entreprise(lei="5493001KJTIIGC8Y1R12"))
    commercial = kyc._controles_gleif(_entreprise(lei="5493001KJTIIGC8Y1R12", name="MDN Mining"))

    assert [c.result for c in legal] == [KycCheckResult.PASSED, KycCheckResult.PASSED]
    assert commercial[1].result == KycCheckResult.PASSED
    assert "autre nom" in commercial[1].detail


def test_enregistrement_echu_et_nom_different(monkeypatch) -> None:
    echu = {**FICHE, "registration": {"status": "LAPSED"}}
    monkeypatch.setattr(kyc, "recuperer_fiche_gleif", lambda _lei: echu)

    enregistrement, nom = kyc._controles_gleif(
        _entreprise(lei="5493001KJTIIGC8Y1R12", name="Autre Société")
    )

    assert enregistrement.result == KycCheckResult.FAILED
    assert "LAPSED" in enregistrement.detail
    assert nom.result == KycCheckResult.FAILED
    assert "Minière du Nord S.A." in nom.detail


def test_sans_lei_ou_gleif_injoignable(monkeypatch) -> None:
    sans_lei = kyc._controles_gleif(_entreprise())

    def _injoignable(_lei):
        raise kyc.GleifIndisponible

    monkeypatch.setattr(kyc, "recuperer_fiche_gleif", _injoignable)
    injoignable = kyc._controles_gleif(_entreprise(lei="5493001KJTIIGC8Y1R12"))

    assert {c.result for c in sans_lei} == {KycCheckResult.NOT_APPLICABLE}
    assert {c.result for c in injoignable} == {KycCheckResult.NOT_VERIFIABLE}


@pytest.mark.parametrize(
    ("site", "email", "attendu"),
    [
        ("https://www.miniere.mr", "contact@miniere.mr", KycCheckResult.PASSED),
        ("https://miniere.mr/fr", "rse@groupe.miniere.mr", KycCheckResult.PASSED),
        ("https://miniere.mr", "contact@autre.mr", KycCheckResult.FAILED),
        ("https://miniere.mr", "patron@gmail.com", KycCheckResult.FAILED),
        (None, "contact@miniere.mr", KycCheckResult.NOT_APPLICABLE),
    ],
    ids=["meme-domaine", "sous-domaine", "autre-domaine", "grand-public", "sans-site"],
)
def test_domaine_du_contact(site, email, attendu) -> None:
    assert kyc._controle_domaine(_entreprise(website=site), email).result == attendu
