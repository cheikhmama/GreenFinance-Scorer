"""Import des positions d'un portefeuille (tâche 2.2) et identifiants d'entreprise côté Admin."""

import json
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import col, select

from app.company.models import Company
from app.core.enums import MatchStatus, Role
from app.investor.models import PortfolioPosition
from tests.integration.test_company_registration import _isin_aleatoire, _lei_aleatoire
from tests.integration.test_investor_router import (
    _create_utilisateur,
    _creer_portefeuille,
    _entreprise_non_publiee,
    _entreprise_publiee,
    _login,
)


def _url(portefeuille_id: str) -> str:
    return f"/api/v1/portfolios/{portefeuille_id}/positions/import"


def _avec_identifiants(session, entreprise: Company, **identifiants) -> Company:
    for champ, valeur in identifiants.items():
        setattr(entreprise, champ, valeur)
    session.add(entreprise)
    session.commit()
    return entreprise


@pytest.fixture()
def investisseur(session) -> TestClient:
    return _login(_create_utilisateur(session, Role.INVESTOR).email)


def _importer(client: TestClient, portefeuille_id: str, contenu: str, nom: str = "positions.csv", **form):
    return client.post(
        _url(portefeuille_id),
        files={"file": (nom, contenu.encode("utf-8"), "text/csv")},
        data={cle: str(valeur) for cle, valeur in form.items()},
    )


def _positions(session, portefeuille_id: str) -> list[PortfolioPosition]:
    session.expire_all()
    return list(
        session.exec(
            select(PortfolioPosition).where(
                col(PortfolioPosition.portfolio_id) == uuid.UUID(portefeuille_id)
            )
        ).all()
    )


def test_import_csv_rapproche_et_conserve_les_lignes_inconnues(session, investisseur) -> None:
    isin_connu = _isin_aleatoire()
    connue = _avec_identifiants(session, _entreprise_publiee(session), isin=isin_connu)
    ticker = f"T{uuid.uuid4().hex[:6].upper()}"
    _avec_identifiants(session, _entreprise_publiee(session), ticker=ticker)
    _avec_identifiants(session, _entreprise_publiee(session), ticker=ticker)
    isin_non_publie = _isin_aleatoire()
    _avec_identifiants(session, _entreprise_non_publiee(session), isin=isin_non_publie)
    portefeuille_id = _creer_portefeuille(investisseur)
    # Séparateur « ; » et virgule décimale : export Excel français.
    contenu = (
        "identifier;identifier_type;outstanding_amount;currency\n"
        f"{isin_connu.lower()};ISIN;1 000,50;USD\n"
        f"{ticker};TICKER;500;EUR\n"
        f"{_isin_aleatoire()};;250;USD\n"
        f"{isin_non_publie};ISIN;100;USD\n"
    )

    reponse = _importer(investisseur, portefeuille_id, contenu)

    assert reponse.status_code == 201, reponse.text
    assert reponse.json() == {
        "portfolio_id": portefeuille_id,
        "imported": 4,
        "matched": 1,
        "unmatched": 2,  # l'entreprise non publiée n'est jamais révélée
        "ambiguous": 1,
    }
    positions = {p.identifier_raw: p for p in _positions(session, portefeuille_id)}
    assert positions[isin_connu].company_id == connue.id
    assert positions[isin_connu].outstanding_amount == pytest.approx(1000.50)
    assert positions[ticker].match_status == MatchStatus.AMBIGUOUS
    assert positions[ticker].converted_amount == pytest.approx(500 * 1.08)  # EUR -> USD
    assert sum(p.weight or 0 for p in positions.values()) == pytest.approx(1)

    detail = investisseur.get(f"/api/v1/investor/portefeuilles/{portefeuille_id}").json()
    non_rapprochees = [p for p in detail["positions"] if p["entreprise"] is None]
    assert {p["statut_rapprochement"] for p in non_rapprochees} == {"UNMATCHED", "AMBIGUOUS"}
    assert all(p["identifiant"] for p in non_rapprochees)
    export = investisseur.get(f"/api/v1/investor/portefeuilles/{portefeuille_id}/export")
    assert export.status_code == 200
    assert f"[{ticker}]" in export.text


def test_import_json_par_poids_derive_les_montants(session, investisseur) -> None:
    isin = _isin_aleatoire()
    _avec_identifiants(session, _entreprise_publiee(session), isin=isin)
    portefeuille_id = _creer_portefeuille(investisseur)
    lignes = json.dumps({"lines": [{"identifier": isin, "weight": 0.6}, {"identifier": _isin_aleatoire(), "weight": 0.4}]})

    sans_total = _importer(investisseur, portefeuille_id, lignes, "positions.json")
    avec_total = _importer(investisseur, portefeuille_id, lignes, "positions.json", total_value=10000)

    assert sans_total.status_code == 422
    assert "total_value" in sans_total.json()["error"]["fields"]["file"]
    assert avec_total.status_code == 201
    montants = sorted(p.outstanding_amount for p in _positions(session, portefeuille_id))
    assert montants == [pytest.approx(4000), pytest.approx(6000)]


def test_import_tout_ou_rien_avec_rapport_par_ligne(session, investisseur) -> None:
    portefeuille_id = _creer_portefeuille(investisseur)
    isin = _isin_aleatoire()
    contenu = (
        "identifier,outstanding_amount,currency\n"
        f"{isin},100,USD\n"
        "US0378331004,100,USD\n"  # chiffre de contrôle faux
        f"{isin},50,USD\n"  # doublon
        f"{_isin_aleatoire()},-5,USD\n"
        f"{_isin_aleatoire()},10,JPY\n"
    )

    reponse = _importer(investisseur, portefeuille_id, contenu)

    assert reponse.status_code == 422
    erreurs = reponse.json()["error"]["fields"]
    assert set(erreurs) == {"line_3", "line_4", "line_5", "line_6"}
    assert "ISIN invalide" in erreurs["line_3"]
    assert "ligne 2" in erreurs["line_4"]
    assert _positions(session, portefeuille_id) == []  # rien n'est enregistré


@pytest.mark.parametrize(
    ("contenu", "attendu"),
    [
        ("identifier,outstanding_amount,currency,weight\nA,,,0.5\nB,10,USD,\n", "même mode"),
        ("identifier,weight\n{i1},0.5\n{i2},0.4\n", "somme des poids"),
    ],
)
def test_import_erreurs_de_fichier(session, investisseur, contenu, attendu) -> None:
    portefeuille_id = _creer_portefeuille(investisseur)
    contenu = contenu.format(i1=_isin_aleatoire(), i2=_isin_aleatoire()).replace(
        "\nA,", f"\n{_isin_aleatoire()},"
    ).replace("\nB,", f"\n{_isin_aleatoire()},")

    reponse = _importer(investisseur, portefeuille_id, contenu, total_value=1000)

    assert reponse.status_code == 422
    assert attendu in reponse.json()["error"]["fields"]["file"]


def test_regles_de_saisie_appliquees_aux_lignes_rapprochees(session, investisseur) -> None:
    suspendue = _avec_identifiants(session, _entreprise_publiee(session, actif=False), isin=_isin_aleatoire())
    exigeante = _avec_identifiants(
        session, _entreprise_publiee(session, montant_minimum=5000), isin=_isin_aleatoire()
    )
    portefeuille_id = _creer_portefeuille(investisseur)
    contenu = (
        "identifier,outstanding_amount,currency\n"
        f"{suspendue.isin},100,USD\n"
        f"{exigeante.isin},100,USD\n"
    )

    reponse = _importer(investisseur, portefeuille_id, contenu)

    assert reponse.status_code == 422
    erreurs = reponse.json()["error"]["fields"]
    assert "suspendue" in erreurs["line_2"]
    assert "minimum" in erreurs["line_3"]


def test_import_seulement_dans_un_portefeuille_vide_et_le_sien(session, investisseur) -> None:
    portefeuille_id = _creer_portefeuille(investisseur)
    contenu = f"identifier,outstanding_amount,currency\n{_isin_aleatoire()},100,USD\n"
    assert _importer(investisseur, portefeuille_id, contenu).status_code == 201

    second = _importer(investisseur, portefeuille_id, contenu)
    autre = _login(_create_utilisateur(session, Role.INVESTOR).email)
    dautrui = _importer(autre, portefeuille_id, contenu)

    assert second.status_code == 422
    assert second.json()["error"]["code"] == "portefeuille_non_vide"
    assert dautrui.status_code == 404


def test_admin_renseigne_les_identifiants_sans_effacer_les_autres(session) -> None:
    entreprise = _entreprise_publiee(session)
    autre = _avec_identifiants(session, _entreprise_publiee(session), isin=_isin_aleatoire())
    admin = _login(_create_utilisateur(session, Role.ADMIN).email)
    url = f"/api/v1/admin/companies/{entreprise.id}/identifiers"
    isin = _isin_aleatoire()
    # Aléatoire : la base de test persiste entre les exécutions et le LEI est unique.
    lei = _lei_aleatoire()

    premier = admin.patch(url, json={"isin": isin.lower(), "ticker": "gfs.pa"})
    partiel = admin.patch(url, json={"lei": lei})
    conflit = admin.patch(url, json={"isin": autre.isin})
    invalide = admin.patch(url, json={"isin": "US0378331004"})
    effacement = admin.patch(url, json={"ticker": None})

    assert premier.status_code == 200
    assert premier.json()["isin"] == isin and premier.json()["ticker"] == "GFS.PA"
    assert partiel.json() == {
        "company_id": str(entreprise.id),
        "isin": isin,
        "lei": lei,
        "ticker": "GFS.PA",
    }
    assert conflit.status_code == 422
    assert conflit.json()["error"]["code"] == "identifiant_deja_utilise"
    assert invalide.status_code == 422
    assert effacement.json()["ticker"] is None and effacement.json()["isin"] == isin
    detail = admin.get(f"/api/v1/admin/entreprises/{entreprise.id}").json()
    assert detail["isin"] == isin
