"""Générateur du rapport synthétique long (banc mémoire, test de fumée Docling réel)."""

import importlib.util
import json
from pathlib import Path

import pymupdf

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "generate_large_esg_pdf.py"


def _module():
    spec = importlib.util.spec_from_file_location("generate_large_esg_pdf", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_rapport_long_conforme_a_son_scenario(tmp_path: Path) -> None:
    _module().generer(tmp_path, pages=40, pages_scannees=4)

    scenario = json.loads((tmp_path / "scenario.json").read_text(encoding="utf-8"))
    with pymupdf.open(tmp_path / "rapport.pdf") as doc:
        assert doc.page_count == 40
        textes = {i + 1: page.get_text("text") for i, page in enumerate(doc)}

    scannees = scenario["pages_scannees"]
    assert len(scannees) == 4
    assert all(len(textes[p].strip()) == 0 for p in scannees)  # aucune couche texte : OCR requis
    indicateurs = scenario["extraction_attendue"]["indicateurs"]
    assert {i["code"] for i in indicateurs} >= {"scope_1", "scope_3", "femmes_conseil_pourcentage"}
    for indicateur in indicateurs:
        page = indicateur["page_attendue"]
        if page in scannees:
            continue  # valeur lisible seulement après OCR
        assert indicateur["valeur_affichee"] in textes[page], indicateur["code"]
    # Au moins une valeur ne se lit que sur une page scannée : le chemin OCR est exercé.
    assert any(i["page_attendue"] in scannees for i in indicateurs)
