"""Découpage d'un PDF en lots de pages pour la conversion Docling (mémoire bornée)."""

from pathlib import Path

import pymupdf
import pytest

from app.ingestion.lots import DocumentTropLong, Lot, planifier_lots


def _pdf(chemin: Path, pages: int, sans_texte: set[int]) -> Path:
    """Pages numérotées à partir de 1 ; une page « sans texte » ne porte qu'un dessin, comme une
    page scannée (aucune couche texte)."""
    doc = pymupdf.open()
    for numero in range(1, pages + 1):
        page = doc.new_page()
        if numero in sans_texte:
            page.draw_rect(pymupdf.Rect(50, 50, 300, 300), fill=(0.5, 0.5, 0.5))
        else:
            page.insert_text((72, 72), f"Page {numero} : emissions scope 1 et indicateurs sociaux. " * 3)
    doc.save(chemin)
    return chemin


def test_lots_consecutifs_et_ocr_seulement_ou_une_page_est_scannee(tmp_path: Path) -> None:
    pdf = _pdf(tmp_path / "r.pdf", 45, sans_texte={23})

    lots = planifier_lots(pdf, taille=20)

    assert lots == [Lot(1, 20, ocr=False), Lot(21, 40, ocr=True), Lot(41, 45, ocr=False)]


def test_un_seul_lot_pour_un_petit_document(tmp_path: Path) -> None:
    assert planifier_lots(_pdf(tmp_path / "r.pdf", 6, set()), taille=20) == [Lot(1, 6, ocr=False)]


def test_document_trop_long_refuse_avant_toute_conversion(tmp_path: Path) -> None:
    pdf = _pdf(tmp_path / "r.pdf", 12, set())

    with pytest.raises(DocumentTropLong):
        planifier_lots(pdf, taille=5, pages_max=10)
