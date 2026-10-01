"""Vérification GLEIF du LEI pour l'en-tête de l'espace Entreprise (tâche 5.9)."""

import pytest

from app.admin import kyc
from tests.integration.test_company_kyc import _lei_aleatoire
from tests.integration.test_company_router import _create_entreprise_utilisateur, _login

URL = "/api/v1/company/lei-verification"


@pytest.fixture()
def entreprise(session):
    user = _create_entreprise_utilisateur(session, password="s3cret-pass")
    return user, _login(user.email, "s3cret-pass")


def _avec_lei(session, user, lei: str | None) -> None:
    user.company.lei = lei
    session.add(user.company)
    session.commit()


def test_sans_lei_rien_a_verifier(session, entreprise) -> None:
    user, client = entreprise
    _avec_lei(session, user, None)

    corps = client.get(URL).json()

    assert corps == {"lei": None, "result": "NOT_APPLICABLE", "detail": "Aucun LEI déclaré. Aucun LEI déclaré."}


def test_lei_enregistre_et_nom_identique_est_valide(session, entreprise, monkeypatch) -> None:
    user, client = entreprise
    lei = _lei_aleatoire()
    _avec_lei(session, user, lei)
    fiche = {
        "entity": {"legalName": {"name": user.company.name.upper()}, "status": "ACTIVE"},
        "registration": {"status": "ISSUED"},
    }
    monkeypatch.setattr(kyc, "recuperer_fiche_gleif", lambda v: fiche if v == lei else None)

    corps = client.get(URL).json()

    assert corps["lei"] == lei
    assert corps["result"] == "PASSED"


def test_nom_different_ou_lei_inconnu_nest_pas_valide(session, entreprise, monkeypatch) -> None:
    user, client = entreprise
    lei = _lei_aleatoire()
    _avec_lei(session, user, lei)
    fiche = {
        "entity": {"legalName": {"name": "Autre Société SA"}, "status": "ACTIVE"},
        "registration": {"status": "ISSUED"},
    }
    monkeypatch.setattr(kyc, "recuperer_fiche_gleif", lambda v: fiche)
    nom_different = client.get(URL).json()
    monkeypatch.setattr(kyc, "recuperer_fiche_gleif", lambda v: None)
    inconnu = client.get(URL).json()

    assert nom_different["result"] == "FAILED"
    assert "Autre Société SA" in nom_different["detail"]
    assert inconnu["result"] == "FAILED"
    assert "inconnu de la GLEIF" in inconnu["detail"]


def test_gleif_muette_reste_non_verifiable(session, entreprise) -> None:
    # Fixture autouse gleif_hors_ligne : le réseau est coupé.
    user, client = entreprise
    _avec_lei(session, user, _lei_aleatoire())

    assert client.get(URL).json()["result"] == "NOT_VERIFIABLE"
