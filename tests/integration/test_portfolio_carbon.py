"""Empreinte carbone PCAF d'un portefeuille et données financières Admin (tâches 2.3 et 5.4 :
chiffre d'affaires et EVIC portés par le rapport de l'exercice)."""

import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.database import utcnow
from app.core.enums import ReportStatus, ReportType, Role, SubmissionChannel
from app.ingestion.models import ESGReport
from app.investor.entreprises import dernier_rapport_valide
from tests.integration.test_company_registration import _isin_aleatoire
from tests.integration.test_investor_router import (
    _create_utilisateur,
    _creer_portefeuille,
    _entreprise_publiee,
    _login,
)
from tests.integration.test_portfolio_import import _avec_identifiants, _importer


@pytest.fixture()
def admin(session) -> TestClient:
    return _login(_create_utilisateur(session, Role.ADMIN).email)


@pytest.fixture()
def investisseur(session) -> TestClient:
    return _login(_create_utilisateur(session, Role.INVESTOR).email)


def _url_financieres(rapport_id) -> str:
    return f"/api/v1/admin/reports/{rapport_id}/financials"


def _rapport_valide(session, entreprise) -> ESGReport:
    rapport = dernier_rapport_valide(session, entreprise.id)
    assert rapport is not None
    return rapport


def test_admin_renseigne_les_donnees_financieres(session, admin) -> None:
    entreprise = _entreprise_publiee(session)
    rapport = _rapport_valide(session, entreprise)
    corps = {
        "revenue": 20_000_000.5,
        "revenue_currency": "USD",
        "enterprise_value": "10000000",
        "enterprise_value_currency": "EUR",
        "evic_date": "2025-12-31",
    }

    reponse = admin.put(_url_financieres(rapport.id), json=corps)
    lue = admin.get(_url_financieres(rapport.id))
    effacee = admin.put(_url_financieres(rapport.id), json={})

    assert reponse.status_code == 200, reponse.text
    assert lue.json() == {
        "report_id": str(rapport.id),
        "company_id": str(entreprise.id),
        "fiscal_year": rapport.fiscal_year,
        "status": "VALIDATED",
        "revenue": 20_000_000.5,
        "revenue_currency": "USD",
        "enterprise_value": 10_000_000,
        "enterprise_value_currency": "EUR",
        "evic_date": "2025-12-31",
    }
    # Remplacement complet : un corps vide efface tout.
    assert effacee.json()["revenue"] is None and effacee.json()["enterprise_value"] is None


@pytest.mark.parametrize(
    "corps",
    [
        {"revenue": 1000},  # montant sans devise
        {"enterprise_value_currency": "USD"},  # devise sans montant
        {"evic_date": "2025-12-31"},  # date sans EVIC
        {"revenue": 10.005, "revenue_currency": "USD"},  # plus de deux décimales
        {"revenue": -5, "revenue_currency": "USD"},
        {"revenue": 10, "revenue_currency": "JPY"},
        {"ebitda": 10},  # champ inconnu
    ],
)
def test_donnees_financieres_invalides_refusees(session, admin, corps) -> None:
    rapport = _rapport_valide(session, _entreprise_publiee(session))

    reponse = admin.put(_url_financieres(rapport.id), json=corps)

    assert reponse.status_code == 422


def test_donnees_financieres_d_un_rapport_inconnu(session, admin) -> None:
    reponse = admin.get(_url_financieres(uuid.uuid4()))

    assert reponse.status_code == 404
    assert reponse.json()["error"]["code"] == "rapport_introuvable"


def test_donnees_financieres_reservees_a_l_admin(session, investisseur) -> None:
    rapport = _rapport_valide(session, _entreprise_publiee(session))

    assert investisseur.get(_url_financieres(rapport.id)).status_code == 403


def test_empreinte_carbone_du_portefeuille(session, admin, investisseur) -> None:
    # A : émissions (helper : Scope 1 = 100, Scope 2 market 50 / location 60, Scope 3 = 1 000,
    # qualité 3) + EVIC en EUR + chiffre d'affaires. B : émissions mais aucune donnée financière.
    a = _avec_identifiants(session, _entreprise_publiee(session), isin=_isin_aleatoire())
    b = _avec_identifiants(session, _entreprise_publiee(session), isin=_isin_aleatoire())
    admin.put(
        _url_financieres(_rapport_valide(session, a).id),
        json={
            "revenue": 20_000_000,
            "revenue_currency": "USD",
            "enterprise_value": 10_000_000,
            "enterprise_value_currency": "EUR",
            "evic_date": "2025-12-31",
        },
    ).raise_for_status()
    # Rapport plus récent de B encore en audit : ses données financières ne comptent pas — PCAF
    # ne lit que le dernier rapport validé, celui dont viennent les émissions.
    en_audit = ESGReport(
        company_id=b.id,
        type=ReportType.RAPPORT_ESG,
        channel=SubmissionChannel.ENTREPRISE,
        status=ReportStatus.IN_AUDIT,
        source_file="rapports/x.pdf",
        submitted_at=utcnow() + timedelta(minutes=1),
        fiscal_year=2026,
        revenue=1,
        revenue_currency="USD",
        enterprise_value=1,
        enterprise_value_currency="USD",
    )
    session.add(en_audit)
    session.commit()
    inconnu = _isin_aleatoire()
    portefeuille_id = _creer_portefeuille(investisseur)
    _importer(
        investisseur,
        portefeuille_id,
        "identifier,outstanding_amount,currency\n"
        f"{a.isin},1000000,USD\n{b.isin},1000000,USD\n{inconnu},1000000,USD\n",
    ).raise_for_status()
    # Position planifiée (démarre demain) : pas encore détenue, absente du calcul PCAF.
    investisseur.post(
        f"/api/v1/investor/portefeuilles/{portefeuille_id}/positions",
        json={
            "company_id": str(a.id),
            "amount": 5000,
            "currency": "USD",
            "duration_type": "OUVERTE",
            "start_date": (utcnow() + timedelta(days=1)).isoformat(),
        },
    ).raise_for_status()

    reponse = investisseur.get(f"/api/v1/portfolios/{portefeuille_id}/carbon")

    assert reponse.status_code == 200, reponse.text
    corps = reponse.json()
    evic_usd = 10_000_000 * 1.08
    facteur = 1_000_000 / evic_usd
    assert corps["currency"] == "USD"
    assert corps["total_value"] == 3_000_000
    # Scope 2 market-based retenu (50), jamais location-based (60) quand les deux existent.
    assert corps["financed_emissions_scope_1_2"] == pytest.approx(facteur * 150)
    assert corps["financed_emissions_scope_3"] == pytest.approx(facteur * 1000)
    assert corps["carbon_footprint_scope_1_2"] == pytest.approx(facteur * 150)
    assert corps["waci_scope_1_2"] == pytest.approx(150 / 20)
    assert corps["data_quality_scope_1_2"] == pytest.approx(3)
    assert corps["coverage_scope_1_2"] == pytest.approx(1 / 3)
    assert corps["coverage_waci"] == pytest.approx(1 / 3)

    positions = {p["company_id"]: p for p in corps["positions"]}
    assert len(corps["positions"]) == 3  # la position planifiée n'y figure pas
    assert positions[str(a.id)]["excluded_reason"] is None
    assert positions[str(a.id)]["scope_2_basis"] == "market_based"
    assert positions[str(a.id)]["evic_date"] == "2025-12-31"
    assert positions[str(b.id)]["excluded_reason"] == "MISSING_EVIC"
    assert positions[None]["excluded_reason"] == "UNMATCHED"
    assert positions[None]["identifier"] == inconnu


def test_empreinte_carbone_d_un_portefeuille_d_autrui_introuvable(session, investisseur) -> None:
    portefeuille_id = _creer_portefeuille(investisseur)
    autre = _login(_create_utilisateur(session, Role.INVESTOR).email)

    assert autre.get(f"/api/v1/portfolios/{portefeuille_id}/carbon").status_code == 404
