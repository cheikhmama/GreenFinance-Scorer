"""Extrait de preuve (tâche 4.5) : une page exacte d'un vrai PDF, rien d'autre."""

import uuid

import pymupdf

from app.core import storage
from app.ingestion.proof_generator import generate_page_proof


def test_extrait_une_seule_page_la_bonne(tmp_path) -> None:
    source = tmp_path / "rapport.pdf"
    with pymupdf.open() as document:
        for numero in (1, 2, 3):
            page = document.new_page()
            page.insert_text((72, 72), f"Contenu de la page {numero}")
        document.save(source)
    rapport_id = uuid.uuid4()

    preuve = generate_page_proof(
        source_pdf_path=source,
        nom_document="rapport.pdf",
        annee=2025,
        nombre_pages_total=3,
        page=2,
        rapport_id=rapport_id,
    )

    assert preuve.excerpt_pdf_path == f"preuves/{rapport_id}/page_2.pdf"
    assert (preuve.page_start, preuve.page_end, preuve.total_pages) == (2, 2, 3)
    with pymupdf.open(storage.resolve_path(preuve.excerpt_pdf_path)) as extrait:
        assert extrait.page_count == 1
        assert "Contenu de la page 2" in extrait[0].get_text()
