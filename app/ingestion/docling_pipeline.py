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
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import structlog
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    RapidOcrOptions,
    TableFormerMode,
    TableStructureOptions,
)
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc.base import ImageRefMode
from docling_core.types.doc.document import DoclingDocument

from app.ingestion.lots import Lot

logger = structlog.get_logger(__name__)


def options_pipeline(*, ocr: bool = True, threads: int = 4) -> PdfPipelineOptions:
    """OCR RapidOCR sur le moteur ONNX Runtime (mêmes modèles PP-OCR qu'avec Paddle) :
    paddlepaddle n'a pas de roue Linux aarch64, ce qui empêchait de construire l'image worker sur
    l'hôte ARM visé (Oracle Always Free), alors qu'onnxruntime en a une. CPU explicite et threads
    bornés (limite cpus du conteneur) ; structure des tableaux en mode précis — les indicateurs ESG
    vivent surtout dans des tableaux imbriqués ; pas d'images de pages conservées."""
    return PdfPipelineOptions(
        do_ocr=ocr,
        ocr_options=RapidOcrOptions(backend="onnxruntime"),
        do_table_structure=True,
        accelerator_options=AcceleratorOptions(device=AcceleratorDevice.CPU, num_threads=threads),
        table_structure_options=TableStructureOptions(mode=TableFormerMode.ACCURATE),
        generate_page_images=False,
    )


@lru_cache
def _get_converter(ocr: bool = True, threads: int = 4) -> DocumentConverter:
    """Un convertisseur par réglage (avec/sans OCR), construit une seule fois par processus
    (chargement de modèles coûteux) ; lazy (pas au niveau module) pour ne pas alourdir le
    démarrage de l'API pour les requêtes qui ne touchent jamais l'ingestion."""
    options = options_pipeline(ocr=ocr, threads=threads)
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
    )


def persist_docling_json(document: DoclingDocument, out_path: Path) -> None:
    """Sauvegarde le DoclingDocument structuré en JSON. PLACEHOLDER (pas EMBEDDED, le défaut) : seuls
    le texte et les tableaux servent à la recherche sémantique et à l'extraction, jamais les images —
    les embarquer en base64 gonflerait le JSON pour rien (verbatim Prompt 4.2)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    document.save_as_json(out_path, image_mode=ImageRefMode.PLACEHOLDER)


# --- conversion par lots (rapports longs, mémoire bornée) -----------------------------------------


@dataclass(frozen=True)
class LotConverti:
    lot: Lot
    document: DoclingDocument
    repris: bool  # chargé depuis le JSON d'une exécution précédente, sans reconversion
    elapsed_s: float


def chemin_lot(dossier: Path, lot: Lot) -> Path:
    return dossier / f"p{lot.debut:04d}-{lot.fin:04d}.json"


def _convertir_lot(chemin_pdf: Path, lot: Lot, threads: int) -> DoclingDocument:
    resultat = _get_converter(lot.ocr, threads).convert(
        str(chemin_pdf), page_range=(lot.debut, lot.fin)
    )
    if resultat.errors:
        logger.warning(
            "docling_lot_erreurs", debut=lot.debut, fin=lot.fin, erreurs=[str(e) for e in resultat.errors]
        )
    return resultat.document


def convertir_par_lots(
    chemin_pdf: Path,
    dossier: Path,
    lots: list[Lot],
    *,
    threads: int,
    convertir: Callable[[Path, Lot], DoclingDocument] | None = None,
) -> Iterator[LotConverti]:
    """Un lot à la fois, chacun sauvegardé en JSON avant d'être rendu : l'appelant le traite puis
    le relâche, si bien qu'un seul lot vit en mémoire. Un lot dont le JSON existe déjà (exécution
    interrompue : délai, mémoire, redémarrage) est rechargé au lieu d'être reconverti — une reprise
    repart du dernier lot, pas du début du rapport."""
    for lot in lots:
        chemin = chemin_lot(dossier, lot)
        t0 = time.time()
        if chemin.exists():
            document, repris = DoclingDocument.load_from_json(chemin), True
        else:
            document = (convertir or (lambda p, lt: _convertir_lot(p, lt, threads)))(chemin_pdf, lot)
            persist_docling_json(document, chemin)
            repris = False
        yield LotConverti(lot, document, repris, round(time.time() - t0, 1))


class DocumentParLots:
    """Accès à la page d'un rapport converti par lots : seul le lot qui la contient est chargé
    (localisation des valeurs, déduction des pages manquantes), le dernier lu restant en cache."""

    def __init__(self, dossier: Path, lots: list[Lot]) -> None:
        self._dossier = dossier
        self._lots = lots
        self._courant: tuple[Lot, DoclingDocument] | None = None

    def document_de_la_page(self, page: int) -> DoclingDocument:
        lot = next((lt for lt in self._lots if lt.debut <= page <= lt.fin), None)
        if lot is None:
            raise KeyError(page)
        if self._courant is None or self._courant[0] != lot:
            self._courant = (lot, DoclingDocument.load_from_json(chemin_lot(self._dossier, lot)))
        return self._courant[1]


@dataclass(frozen=True)
class RapportConverti:
    pages_total: int
    pages_ocr: int  # pages des lots convertis avec OCR (lots contenant une page scannée)
    elapsed_s: float
    document_de_la_page: Callable[[int], DoclingDocument]


def convertir_rapport(
    chemin_pdf: Path,
    dossier: Path,
    *,
    taille: int,
    pages_max: int,
    threads: int,
    indexer: Callable[[DoclingDocument], object],
    convertir: Callable[[Path, Lot], DoclingDocument] | None = None,
) -> RapportConverti:
    """Conversion complète d'un rapport, lot par lot : chaque lot est indexé dès qu'il est converti
    puis relâché (voir convertir_par_lots). Lève lots.DocumentTropLong avant toute conversion
    au-delà de `pages_max`."""
    from app.ingestion.lots import planifier_lots

    t0 = time.time()
    lots = planifier_lots(chemin_pdf, taille=taille, pages_max=pages_max)
    for lot_converti in convertir_par_lots(chemin_pdf, dossier, lots, threads=threads, convertir=convertir):
        logger.info(
            "docling_lot_converti",
            debut=lot_converti.lot.debut,
            fin=lot_converti.lot.fin,
            ocr=lot_converti.lot.ocr,
            repris=lot_converti.repris,
            elapsed_s=lot_converti.elapsed_s,
        )
        indexer(lot_converti.document)
    return RapportConverti(
        pages_total=lots[-1].fin if lots else 0,
        pages_ocr=sum(lot.fin - lot.debut + 1 for lot in lots if lot.ocr),
        elapsed_s=round(time.time() - t0, 1),
        document_de_la_page=DocumentParLots(dossier, lots).document_de_la_page,
    )
