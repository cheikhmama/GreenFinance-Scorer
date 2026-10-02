"""Provenance d'une extraction (tâche 5.5) : une ExtractionRun par exécution du pipeline, son issue,
et, sur chaque valeur écrite, l'exécution d'origine et les boîtes de la valeur sur sa page."""

from datetime import timedelta
from pathlib import Path

from docling_core.types.doc import DoclingDocument
from sqlmodel import col, select

from app.core.config import get_settings
from app.core.database import utcnow
from app.core.enums import ExtractionRunStatus, ReportStatus, Role
from app.ingestion import extractor
from app.ingestion.models import CarbonEmission, ESGMetric, ExtractionRun
from app.ingestion.schemas import ExtractionEntreprise, IndicateurExtrait
from app.worker import jobs
from tests.integration.test_admin_router import (
    _create_entreprise_avec_utilisateur,
    _create_rapport,
    _create_utilisateur,
    _login,
)
from tests.integration.test_company_router import (
    _rapport_a_extraire,
    _simuler_pipeline_extraction,
)
from tests.integration.test_worker_jobs import (
    _executer,
    _pipeline_qui_echoue,
    _RedisEnregistreur,
)

ATLAS = Path("data_test/reference_e2e/atlas_industries")


def _executions(session, rapport_id) -> list[ExtractionRun]:
    session.expire_all()
    return list(
        session.exec(
            select(ExtractionRun)
            .where(col(ExtractionRun.report_id) == rapport_id)
            .order_by(col(ExtractionRun.started_at))
        ).all()
    )


def _extraction_atlas() -> ExtractionEntreprise:
    """Ce que le LLM renvoie sur le rapport Atlas : deux valeurs de la page 3."""
    return ExtractionEntreprise(
        entreprise="Atlas Industries",
        indicateurs=[
            IndicateurExtrait(
                code="scope_1", valeur=12500.0, unite="tCO2e", page_source=3, trouve=True,
                valeur_brute="12 500.0",
            ),
            IndicateurExtrait(
                code="intensite_scope_1_2_marketbased", valeur=22.0, unite="gCO2e/kWh",
                page_source=3, trouve=True,
            ),
        ],
    )


def test_execution_reussie_enregistree_et_valeurs_localisees(session, monkeypatch) -> None:
    document = DoclingDocument.load_from_json(ATLAS / "docling.json")
    _simuler_pipeline_extraction(monkeypatch, _extraction_atlas(), document=document)
    rapport = _rapport_a_extraire(session)

    extractor.run_extraction_pipeline(rapport.id, 2025)

    (execution,) = _executions(session, rapport.id)
    assert execution.status == ExtractionRunStatus.SUCCEEDED
    assert execution.finished_at is not None and execution.error is None
    assert execution.prompt_version == extractor.PROMPT_VERSION
    assert execution.docling_version == extractor.version_docling() != "absent"
    # Clé GEMINI_API_KEY factice en test : le mode démonstration est enregistré comme tel.
    attendu = extractor.MODELE_DEMO if get_settings().gemini_api_key_is_placeholder else extractor.EXTRACTION_MODEL
    assert execution.llm_model == attendu

    emission = session.exec(select(CarbonEmission).where(CarbonEmission.report_id == rapport.id)).one()
    indicateur = session.exec(select(ESGMetric).where(ESGMetric.report_id == rapport.id)).one()
    assert emission.extraction_run_id == indicateur.extraction_run_id == execution.id
    for ligne in (emission, indicateur):
        assert len(ligne.proof_boxes) == 1
        assert ligne.proof_boxes[0]["page"] == 3
        assert set(ligne.proof_boxes[0]) == {"page", "x0", "y0", "x1", "y1"}


def test_localisation_impossible_n_empeche_pas_l_extraction(session, monkeypatch) -> None:
    """Document factice (pas une vraie sortie Docling) : aucune boîte, extraction réussie."""
    _simuler_pipeline_extraction(monkeypatch, _extraction_atlas())
    rapport = _rapport_a_extraire(session)

    extractor.run_extraction_pipeline(rapport.id, 2025)

    assert _executions(session, rapport.id)[0].status == ExtractionRunStatus.SUCCEEDED
    emission = session.exec(select(CarbonEmission).where(CarbonEmission.report_id == rapport.id)).one()
    assert emission.proof_boxes == []


def test_echec_transitoire_puis_definitif_deux_executions(session, monkeypatch) -> None:
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    rapport = _create_rapport(session, entreprise.id, status=ReportStatus.EXTRACTING, fiscal_year=2024)
    _pipeline_qui_echoue(monkeypatch, ConnectionError("réseau"))

    try:
        extractor.run_extraction_pipeline(rapport.id, 2024, derniere_tentative=False)
    except extractor.ExtractionTransitoire:
        pass
    extractor.run_extraction_pipeline(rapport.id, 2024, derniere_tentative=True)

    premiere, seconde = _executions(session, rapport.id)
    assert (premiere.status, premiere.error) == (
        ExtractionRunStatus.RETRY_SCHEDULED,
        "chargement_modele_embedding_echoue",
    )
    assert (seconde.status, seconde.error) == (
        ExtractionRunStatus.FAILED,
        "chargement_modele_embedding_echoue",
    )
    assert premiere.finished_at is not None and seconde.finished_at is not None


def test_quota_journalier_epuise_echoue_aussitot_avec_sa_cause(session, monkeypatch) -> None:
    """Pas de reprise (elle ferait attendre une dizaine de minutes pour rien) et une cause qui dit
    ce qui se passe, au lieu de « réseau ou fournisseur indisponible »."""
    from google.genai import errors as genai_errors

    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    rapport = _create_rapport(session, entreprise.id, status=ReportStatus.EXTRACTING, fiscal_year=2024)
    quota = genai_errors.ClientError(
        429, {"error": {"code": 429, "details": [{"violations": [{"quotaId": "RequestsPerDay"}]}]}}
    )
    _pipeline_qui_echoue(monkeypatch, quota)

    extractor.run_extraction_pipeline(rapport.id, 2024, derniere_tentative=False)

    [execution] = _executions(session, rapport.id)
    assert (execution.status, execution.error) == (ExtractionRunStatus.FAILED, "quota_llm_epuise")
    session.refresh(rapport)
    assert rapport.extraction_error == "quota_llm_epuise"


def test_execution_interrompue_close_par_la_supervision(session) -> None:
    entreprise, _ = _create_entreprise_avec_utilisateur(session)
    debut = utcnow() - timedelta(minutes=get_settings().extraction_timeout_minutes + 1)
    rapport = _create_rapport(
        session, entreprise.id, status=ReportStatus.EXTRACTING, extraction_started_at=debut,
        fiscal_year=2024,
    )
    session.add(
        ExtractionRun(
            report_id=rapport.id, started_at=debut, docling_version="2.0", llm_model="m",
            prompt_version="v",
        )
    )
    session.commit()

    _executer(jobs.reprendre_extractions({"redis": _RedisEnregistreur()}))

    (execution,) = _executions(session, rapport.id)
    assert (execution.status, execution.error) == (ExtractionRunStatus.FAILED, "delai_depasse")


def test_executions_et_boites_visibles_de_l_administrateur(session, monkeypatch) -> None:
    document = DoclingDocument.load_from_json(ATLAS / "docling.json")
    _simuler_pipeline_extraction(monkeypatch, _extraction_atlas(), document=document)
    rapport = _rapport_a_extraire(session)
    extractor.run_extraction_pipeline(rapport.id, 2025)
    admin = _login(_create_utilisateur(session, Role.ADMIN).email, "s3cret-pass")

    executions = admin.get(f"/api/v1/admin/reports/{rapport.id}/extraction-runs")
    detail = admin.get(f"/api/v1/admin/rapports/{rapport.id}")

    assert executions.status_code == 200
    assert [e["status"] for e in executions.json()] == ["SUCCEEDED"]
    corps = detail.json()
    assert corps["carbon_data"][0]["extraction_run_id"] == executions.json()[0]["id"]
    assert corps["carbon_data"][0]["proof_boxes"][0]["page"] == 3
    assert corps["metrics"][0]["proof_boxes"][0]["page"] == 3


def _scope_1_sans_page(valeur: float, valeur_brute: str) -> ExtractionEntreprise:
    """Le LLM trouve la valeur mais omet sa page (constaté sur un Scope 2, tâche 5.11)."""
    return ExtractionEntreprise(
        entreprise="Atlas Industries",
        indicateurs=[
            IndicateurExtrait(
                code="scope_1", valeur=valeur, unite="tCO2e", page_source=None, trouve=True,
                valeur_brute=valeur_brute,
            ),
        ],
    )


def _couverture(session, rapport_id, code: str):
    from app.ingestion.models import MetricCoverage

    session.expire_all()
    return session.exec(
        select(MetricCoverage).where(
            col(MetricCoverage.report_id) == rapport_id, col(MetricCoverage.metric_code) == code
        )
    ).one()


def test_page_omise_par_le_llm_retrouvee_dans_les_pages_montrees(session, monkeypatch) -> None:
    from app.core.enums import MetricCoverageStatus
    from app.ingestion.models import Evidence

    document = DoclingDocument.load_from_json(ATLAS / "docling.json")
    _simuler_pipeline_extraction(
        monkeypatch, _scope_1_sans_page(12500.0, "12 500.0"), document=document
    )
    rapport = _rapport_a_extraire(session)

    extractor.run_extraction_pipeline(rapport.id, 2025)

    session.expire_all()
    (scope_1,) = session.exec(
        select(CarbonEmission).where(col(CarbonEmission.report_id) == rapport.id)
    ).all()
    assert scope_1.tonnes_co2e == 12500.0
    preuve = session.get(Evidence, scope_1.proof_id)
    assert preuve is not None and preuve.page_start == 3
    assert _couverture(session, rapport.id, "scope_1").status == MetricCoverageStatus.TROUVE


def test_valeur_sans_page_introuvable_ni_enregistree_ni_comptee(session, monkeypatch) -> None:
    from app.core.enums import MetricCoverageStatus

    document = DoclingDocument.load_from_json(ATLAS / "docling.json")
    _simuler_pipeline_extraction(
        monkeypatch, _scope_1_sans_page(98765.0, "98 765.0"), document=document
    )
    rapport = _rapport_a_extraire(session)

    extractor.run_extraction_pipeline(rapport.id, 2025)

    session.expire_all()
    assert session.exec(
        select(CarbonEmission).where(col(CarbonEmission.report_id) == rapport.id)
    ).all() == []
    # Plus d'écart entre la liste de complétude et ce qui est enregistré.
    assert _couverture(session, rapport.id, "scope_1").status != MetricCoverageStatus.TROUVE
