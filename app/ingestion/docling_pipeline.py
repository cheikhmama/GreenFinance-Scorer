"""Intégration de Docling pour la conversion des documents source.

Cœur porté depuis notebooks/_prompt_4_2_structuration.py (validé à l'Étape 4 sur le corpus pilote),
adapté pour être appelé depuis app/ingestion/extractor.py plutôt qu'exécuté comme script autonome.
"""

import os

# Docling utilise des modeles PyTorch (TableFormer, layout) qui tentent par defaut de se compiler
# via torch.compile (backend inductor). Ca necessite un compilateur C++ (cl.exe sous Windows) absent
# de cet environnement : sans le desactiver, chaque appel modele echoue et retente en boucle,
# jusqu'a saturer la memoire. Doit etre positionne AVANT tout import de torch/docling — ce module
# est le premier du graphe d'imports de l'app a importer ces bibliotheques (voir aussi le meme
# garde-fou en defense en profondeur dans le Dockerfile via ENV TORCHDYNAMO_DISABLE=1).
os.environ.setdefault("TORCHDYNAMO_DISABLE", "1")

import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pymupdf
import structlog
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, RapidOcrOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc.base import ImageRefMode
from docling_core.types.doc.document import DoclingDocument

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ConversionResult:
    document: DoclingDocument
    status: str
    errors: list[str]
    pages_docling: int
    pages_pymupdf: int
    pages_correspondent: bool
    elapsed_s: float


def options_pipeline() -> PdfPipelineOptions:
    """OCR RapidOCR sur le moteur ONNX Runtime (mêmes modèles PP-OCR qu'avec Paddle) :
    paddlepaddle n'a pas de roue Linux aarch64, ce qui empêchait de construire l'image worker sur
    l'hôte ARM visé (Oracle Always Free), alors qu'onnxruntime en a une."""
    return PdfPipelineOptions(do_ocr=True, ocr_options=RapidOcrOptions(backend="onnxruntime"))


@lru_cache
def _get_converter() -> DocumentConverter:
    """Construit une seule fois par processus (chargement de modèles coûteux) ; lazy (pas au niveau
    module) pour ne pas alourdir le démarrage de l'API pour les requêtes qui ne touchent jamais
    l'ingestion."""
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options_pipeline())}
    )


def convert_pdf(path: Path) -> ConversionResult:
    """Convertit un PDF en DoclingDocument structuré. Le nombre de pages est recompté
    indépendamment via pymupdf ; un désaccord est journalisé (jamais observé sur le corpus pilote
    validé) mais ne bloque pas la conversion — c'est un signal diagnostique, pas une erreur fatale."""
    t0 = time.time()
    conv = _get_converter().convert(str(path))
    elapsed = time.time() - t0
    doc = conv.document

    pages_docling = doc.num_pages()
    with pymupdf.open(path) as pm:
        pages_pymupdf = pm.page_count
    pages_correspondent = pages_docling == pages_pymupdf
    if not pages_correspondent:
        logger.warning(
            "docling_pages_desaccord",
            path=str(path),
            pages_docling=pages_docling,
            pages_pymupdf=pages_pymupdf,
        )

    return ConversionResult(
        document=doc,
        status=str(conv.status),
        errors=[str(e) for e in conv.errors],
        pages_docling=pages_docling,
        pages_pymupdf=pages_pymupdf,
        pages_correspondent=pages_correspondent,
        elapsed_s=round(elapsed, 1),
    )


def persist_docling_json(document: DoclingDocument, out_path: Path) -> None:
    """Sauvegarde le DoclingDocument structuré en JSON. PLACEHOLDER (pas EMBEDDED, le défaut) : seuls
    le texte et les tableaux servent à la recherche sémantique et à l'extraction, jamais les images —
    les embarquer en base64 gonflerait le JSON pour rien (verbatim Prompt 4.2)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    document.save_as_json(out_path, image_mode=ImageRefMode.PLACEHOLDER)
