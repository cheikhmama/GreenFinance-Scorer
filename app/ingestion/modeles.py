"""Préchargement des modèles du pipeline d'extraction, à la construction de l'image worker.

`python -m app.ingestion.modeles /opt/modeles` — l'image démarre ensuite hors ligne
(HF_HUB_OFFLINE=1) : aucun téléchargement au premier rapport, aucun dossier de modèles à écrire
par l'utilisateur sans privilèges, et une image reproductible. Docling lit ses modèles via
DOCLING_ARTIFACTS_PATH (= <dossier>/docling), bge-m3 via le cache Hugging Face (HF_HOME).
"""

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

MODELE_EMBEDDING = "BAAI/bge-m3"


def _telecharger_docling(**options: Any) -> None:
    from docling.utils.model_downloader import download_models

    download_models(**options)


def _telecharger_hf(depot: str) -> None:
    from huggingface_hub import snapshot_download

    # Le dépôt bge-m3 publie aussi une copie ONNX (~2 Go) et des images de documentation que
    # FlagEmbedding ne charge jamais (il lit pytorch_model.bin, colbert/sparse_linear.pt, tokenizer).
    snapshot_download(depot, ignore_patterns=["onnx/*", "imgs/*", "*.onnx", "*.jpg"])


def precharger(
    dossier: Path,
    *,
    telecharger_docling: Callable[..., None] = _telecharger_docling,
    telecharger_hf: Callable[[str], None] = _telecharger_hf,
) -> None:
    """Seuls les modèles du pipeline (voir docling_pipeline.options_pipeline) : mise en page,
    structure des tableaux, OCR RapidOCR sur ONNX Runtime — pas de formules, ni de classification
    d'images, ni la variante torch de l'OCR, qui alourdiraient l'image sans servir."""
    from docling.models.stages.ocr.rapid_ocr_model import _RAPIDOCR_DEFAULT_LANGUAGE

    telecharger_docling(
        output_dir=dossier / "docling",
        with_layout=True,
        with_tableformer=True,
        with_code_formula=False,
        with_picture_classifier=False,
        with_rapidocr=True,
        rapidocr_models=[f"onnxruntime:{_RAPIDOCR_DEFAULT_LANGUAGE}"],
    )
    telecharger_hf(MODELE_EMBEDDING)


if __name__ == "__main__":
    precharger(Path(sys.argv[1]))
