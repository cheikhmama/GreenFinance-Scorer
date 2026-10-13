"""Cœur de l'extraction sans base de données (partagé par le worker et l'outil MCP)."""

import uuid
from pathlib import Path

import pytest

from app.ingestion import extractor
from app.ingestion.docling_pipeline import RapportConverti
from app.ingestion.schemas import ExtractionEntreprise, IndicateurExtrait


class _Encodeur:
    def encode(self, *_a, **_k):
        return {"dense_vecs": []}


class _IndexVide:
    def __init__(self, *_a) -> None:
        pass

    def ajouter(self, *_a) -> int:
        return 0

    def en_dictionnaire(self) -> dict:
        return {}


@pytest.fixture
def doublures(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    appels: list[str] = []
    conversion = RapportConverti(
        pages_total=250, pages_ocr=20, elapsed_s=900.0, document_de_la_page=lambda _p: object()
    )
    monkeypatch.setattr(extractor, "_get_embed_model", lambda: _Encodeur())
    monkeypatch.setattr(extractor, "IndexIncremental", _IndexVide)
    monkeypatch.setattr(
        extractor.docling_pipeline, "convertir_rapport", lambda *_a, **_k: appels.append("conversion") or conversion
    )
    monkeypatch.setattr(
        extractor,
        "_build_context",
        lambda _i, _e, codes, _b, plafond_tokens=None: ("--- Page 88 ---\nx", [88], {c: [] for c in codes}),
    )

    def llm(**kw):
        appels.append("llm")
        return ExtractionEntreprise(
            entreprise=kw["nom_entreprise"],
            indicateurs=[
                IndicateurExtrait(code=c, valeur=1.0, unite="", page_source=88, trouve=True) for c in kw["codes"]
            ],
        )

    monkeypatch.setattr(extractor, "_call_llm_extraction", llm)

    class _Reglages:
        llm_demo = False
        llm_provider = "gemini"
        llm_context_tokens = extractor.CONTEXT_TOKEN_BUDGET
        extraction_pages_par_lot = 20
        extraction_pages_max = 600
        extraction_threads = 3

    monkeypatch.setattr(extractor, "get_settings", lambda: _Reglages())
    return appels


def test_analyse_complete_sans_base(doublures: list[str], tmp_path: Path) -> None:
    analyse = extractor.analyser_document(
        tmp_path / "r.pdf", tmp_path / "json", nom_entreprise="Helios", rapport_id=uuid.uuid4()
    )

    assert doublures == ["conversion", "llm"]
    assert analyse.conversion.pages_total == 250
    assert analyse.modele == extractor.EXTRACTION_MODEL and analyse.demo is False
    assert {i.code for i in analyse.extraction.indicateurs} == set(analyse.codes)
    assert analyse.pages_vues_par_code["scope_1"] == {88}
    assert analyse.duree_llm_s >= 0


def test_etape_d_echec_portee_par_l_exception(
    doublures: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def panne(*_a, **_k):
        raise RuntimeError("docling")

    monkeypatch.setattr(extractor.docling_pipeline, "convertir_rapport", panne)

    with pytest.raises(RuntimeError) as erreur:
        extractor.analyser_document(tmp_path / "r.pdf", tmp_path / "json", nom_entreprise="H", rapport_id=uuid.uuid4())
    assert erreur.value.etape_extraction == "docling_conversion_echouee"  # type: ignore[attr-defined]
