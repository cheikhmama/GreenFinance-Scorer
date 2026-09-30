"""GET /reports/{id}/score-explanation (tâche 3.2) — cascade SHAP exacte contre les pairs."""

import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.company.models import Company
from app.core.config import get_settings
from app.core.database import utcnow
from app.core.enums import (
    CanalDepot,
    CompanyStatus,
    MethodeDonnee,
    Pillar,
    ReportStatus,
    Role,
    TypeRapport,
)
from app.ingestion.models import ESGMetric, ESGReport, Evidence
from app.scoring.config_schema import charger_configuration_depuis_fichier
from app.scoring.engine import calculer_score
from tests.integration.test_investor_router import _create_utilisateur, _login

CODE = "femmes_conseil_pourcentage"


def _valeur_normalisee_a(part: float) -> float:
    """Valeur brute qui se normalise à part × 100 sous la référence (bornes lues, pas recopiées)."""
    config = charger_configuration_depuis_fichier(
        Path(get_settings().default_scoring_config)
    ).piliers[Pillar.GOUVERNANCE].indicateurs[CODE]
    assert config.plus_haut_est_meilleur
    return config.borne_min + part * (config.borne_max - config.borne_min)


def _entreprise_scoree(
    session, secteur: str, part: float, *, publiee: bool = True, proprietaire=None
) -> tuple[Company, ESGReport]:
    entreprise = Company(
        name=f"Pair {uuid.uuid4()}",
        sector=secteur,
        country="MR",
        status=CompanyStatus.ACTIVE,
        published_at=utcnow() if publiee else None,
        owner_user_id=proprietaire,
    )
    session.add(entreprise)
    session.flush()
    rapport = _rapport_valide(session, entreprise, part)
    return entreprise, rapport


def _rapport_valide(session, entreprise: Company, part: float) -> ESGReport:
    rapport = ESGReport(
        company_id=entreprise.id,
        type=TypeRapport.RAPPORT_ESG,
        channel=CanalDepot.ENTREPRISE,
        status=ReportStatus.VALIDATED,
        source_file="rapports/test/dummy.pdf",
        submitted_at=utcnow(),
    )
    preuve = Evidence(
        document_name="r.pdf", year=2025, total_pages=1, page_start=1, page_end=1,
        excerpt_pdf_path="preuves/test/p.pdf",
    )
    session.add_all([rapport, preuve])
    session.flush()
    session.add(
        ESGMetric(
            report_id=rapport.id, pillar=Pillar.GOUVERNANCE, metric_code=CODE,
            value=_valeur_normalisee_a(part), unit="%", method=MethodeDonnee.RAPPORTEE,
            proof_id=preuve.id,
        )
    )
    session.flush()
    calculer_score(session, rapport.id)
    session.commit()
    return rapport


@pytest.fixture()
def investisseur(session) -> TestClient:
    return _login(_create_utilisateur(session, Role.INVESTOR).email)


def _url(rapport_id, **params) -> str:
    requete = "&".join(f"{cle}={valeur}" for cle, valeur in params.items())
    return f"/api/v1/reports/{rapport_id}/score-explanation" + (f"?{requete}" if requete else "")


def test_cascade_contre_les_pairs_du_secteur(session, investisseur) -> None:
    secteur = f"Secteur {uuid.uuid4()}"
    _entreprise, rapport = _entreprise_scoree(session, secteur, 0.8)
    for part in (0.2, 0.4, 0.6):
        _entreprise_scoree(session, secteur, part)
    _entreprise_scoree(session, secteur, 0.0, publiee=False)  # jamais un pair : non publiée

    reponse = investisseur.get(_url(rapport.id))

    assert reponse.status_code == 200, reponse.text
    corps = reponse.json()
    assert corps["baseline"] == {
        "requested": "SECTOR", "used": "SECTOR", "sector": secteur, "peer_count": 3,
    }
    assert corps["score"] == pytest.approx(80)
    assert corps["baseline_score"] == pytest.approx(40)
    [contribution] = corps["contributions"]
    assert contribution["metric_code"] == CODE
    assert contribution["baseline_value"] == pytest.approx(40)
    assert contribution["effective_weight"] == pytest.approx(1)
    assert contribution["contribution"] == pytest.approx(40)
    assert corps["pillars"] == [{"pillar": "GOUVERNANCE", "contribution": pytest.approx(40)}]
    assert corps["config_hash"] is not None and corps["coverage_rate"] is not None


def test_secteur_trop_petit_repli_sur_toutes_les_entreprises(session, investisseur) -> None:
    secteur = f"Secteur {uuid.uuid4()}"
    _entreprise, rapport = _entreprise_scoree(session, secteur, 0.5)
    _entreprise_scoree(session, secteur, 0.1)

    corps = investisseur.get(_url(rapport.id)).json()
    universel = investisseur.get(_url(rapport.id, baseline="UNIVERSE")).json()

    assert corps["baseline"]["requested"] == "SECTOR"
    assert corps["baseline"]["used"] == "UNIVERSE"
    assert corps["baseline"]["sector"] is None
    assert corps["baseline"]["peer_count"] >= 1
    assert universel["baseline"]["requested"] == "UNIVERSE"
    # Invariant SHAP, quel que soit l'ensemble de référence.
    for explication in (corps, universel):
        total = sum(c["contribution"] for c in explication["contributions"])
        assert total == pytest.approx(explication["score"] - explication["baseline_score"])


def test_acces_limite_a_ce_que_chaque_role_voit_deja(session, investisseur) -> None:
    secteur = f"Secteur {uuid.uuid4()}"
    proprietaire = _create_utilisateur(session, Role.ENTERPRISE)
    entreprise, ancien = _entreprise_scoree(session, secteur, 0.3, proprietaire=proprietaire.id)
    recent = _rapport_valide(session, entreprise, 0.6)
    _cache, non_publie = _entreprise_scoree(session, secteur, 0.5, publiee=False)
    autre_proprietaire = _create_utilisateur(session, Role.ENTERPRISE)
    _entreprise_scoree(session, secteur, 0.4, proprietaire=autre_proprietaire.id)
    autre_entreprise = _login(autre_proprietaire.email)
    admin = _login(_create_utilisateur(session, Role.ADMIN).email)

    assert investisseur.get(_url(recent.id)).status_code == 200
    # Investisseur : seulement le dernier rapport validé d'une entreprise publiée.
    assert investisseur.get(_url(ancien.id)).status_code == 404
    assert investisseur.get(_url(non_publie.id)).status_code == 404
    # Chercheur : seulement les entreprises de son périmètre de projets (ici aucun).
    chercheur = _login(_create_utilisateur(session, Role.RESEARCHER).email)
    assert chercheur.get(_url(recent.id)).status_code == 404
    # Entreprise : ses propres rapports (périmètre /reports), jamais ceux d'une autre.
    assert _login(proprietaire.email).get(_url(ancien.id)).status_code == 200
    assert autre_entreprise.get(_url(recent.id)).status_code == 404
    assert admin.get(_url(non_publie.id)).status_code == 200


def test_rapport_sans_score_officiel(session) -> None:
    entreprise = Company(name=f"Sans score {uuid.uuid4()}", sector="X", country="MR")
    session.add(entreprise)
    session.flush()
    rapport = ESGReport(
        company_id=entreprise.id, type=TypeRapport.RAPPORT_ESG, channel=CanalDepot.ENTREPRISE,
        status=ReportStatus.SUBMITTED, source_file="rapports/x.pdf", submitted_at=utcnow(),
    )
    session.add(rapport)
    session.commit()
    admin = _login(_create_utilisateur(session, Role.ADMIN).email)

    reponse = admin.get(_url(rapport.id))

    assert reponse.status_code == 422
    assert reponse.json()["error"]["code"] == "score_absent"
