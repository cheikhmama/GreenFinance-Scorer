"""Préchargement des modèles dans l'image worker (exécuté à la construction, jamais à l'exécution)."""

from pathlib import Path
from typing import Any

from app.ingestion.modeles import precharger


def test_precharge_seulement_les_modeles_du_pipeline(tmp_path: Path) -> None:
    """Mise en page, TableFormer et OCR ONNX pour Docling, bge-m3 pour l'indexation — rien d'autre :
    chaque modèle en trop alourdit l'image de plusieurs centaines de Mo."""
    appels_docling: list[dict[str, Any]] = []
    depots_hf: list[str] = []

    precharger(
        tmp_path,
        telecharger_docling=lambda **kw: appels_docling.append(kw),
        telecharger_hf=depots_hf.append,
    )

    assert len(appels_docling) == 1
    options = appels_docling[0]
    assert options["output_dir"] == tmp_path / "docling"
    assert options["with_layout"] and options["with_tableformer"] and options["with_rapidocr"]
    assert not options["with_code_formula"] and not options["with_picture_classifier"]
    assert [m.split(":")[0] for m in options["rapidocr_models"]] == ["onnxruntime"]
    assert depots_hf == ["BAAI/bge-m3"]
