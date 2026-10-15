"""Conversion Docling RÉELLE (modèles, OCR ONNX) — tests lents, exclus par défaut :

    uv run pytest -m slow
"""

from pathlib import Path

import pymupdf
import pytest
from docling_core.types.doc.document import DoclingDocument

from app.ingestion.docling_pipeline import convertir_rapport

pytestmark = pytest.mark.slow

ATLAS = Path(__file__).resolve().parents[2] / "data_test" / "reference_e2e" / "atlas_industries" / "rapport.pdf"


def _textes(documents) -> str:
    return " ".join(t.text for d in documents for t in d.texts)


def test_rapport_numerique_converti_par_lots_sans_ocr(tmp_path: Path) -> None:
    documents: list[DoclingDocument] = []

    rapport = convertir_rapport(
        ATLAS, tmp_path, taille=3, pages_max=600, threads=2, indexer=documents.append
    )

    assert (rapport.pages_total, rapport.pages_ocr) == (6, 0)
    assert [d.num_pages() for d in documents] == [3, 3]
    assert "Atlas Industries" in _textes(documents)
    assert rapport.document_de_la_page(5).num_pages() == 3  # lot 4-6 rechargé depuis son JSON


def test_page_scannee_lue_par_l_ocr_onnx(tmp_path: Path) -> None:
    source = pymupdf.open()
    source.new_page().insert_text((72, 120), "Scope 1 emissions : 48 210 tCO2e", fontsize=20)
    scan = pymupdf.open()
    scan.new_page().insert_image(scan[0].rect, pixmap=source[0].get_pixmap(dpi=200))
    pdf = tmp_path / "scan.pdf"
    scan.save(pdf)
    documents: list[DoclingDocument] = []

    rapport = convertir_rapport(pdf, tmp_path / "json", taille=20, pages_max=600, threads=2, indexer=documents.append)

    assert rapport.pages_ocr == 1
    assert "48" in _textes(documents) and "Scope" in _textes(documents)
