"""Extraction d'un PDF hors base de données, jusqu'au JSON aligné sur les référentiels publics.

Point d'entrée de l'outil MCP extract_esg_report (app/mcp/serveur.py) : même pipeline que le worker
(extractor.analyser_document — conversion par lots, recherche sémantique, LLM, pages déduites),
sans rapport en base, sans preuve générée, sans notification.
"""

import hashlib
import tempfile
import uuid
from pathlib import Path

# Toutes les tables déclarées : couvertures() instancie MetricCoverage, dont les relations doivent
# se résoudre sans que l'API (app.main) ait été importée — cas du processus MCP.
from app.core import registre_modeles  # noqa: F401
from app.ingestion import extractor
from app.ingestion.memoire import pic_memoire_mo
from app.ingestion.sortie import (
    DocumentSortie,
    ExecutionSortie,
    RapportExtraitJSON,
    construire_sortie,
)

DOSSIER_TRAVAIL = Path(tempfile.gettempdir()) / "greenfinance-extraction"


def _empreinte(chemin: Path) -> str:
    sha = hashlib.sha256()
    with chemin.open("rb") as fichier:
        for bloc in iter(lambda: fichier.read(1 << 20), b""):
            sha.update(bloc)
    return sha.hexdigest()


def extraire_document(
    chemin_pdf: Path,
    *,
    nom_entreprise: str | None,
    annee: int | None,
    dossier_travail: Path = DOSSIER_TRAVAIL,
) -> RapportExtraitJSON:
    """Les lots Docling sont rangés par empreinte du PDF : une extraction interrompue, ou relancée
    sur le même fichier, reprend les lots déjà convertis au lieu de tout reconvertir."""
    empreinte = _empreinte(chemin_pdf)
    nom = nom_entreprise or chemin_pdf.stem
    identifiant = uuid.uuid4()  # journalisation uniquement : aucun rapport en base
    analyse = extractor.analyser_document(
        chemin_pdf, dossier_travail / empreinte, nom_entreprise=nom, rapport_id=identifiant
    )
    return construire_sortie(
        analyse.extraction,
        annee=annee,
        document=DocumentSortie(
            nom=chemin_pdf.name, pages=analyse.conversion.pages_total, sha256=empreinte
        ),
        execution=ExecutionSortie(
            modele=analyse.modele,
            prompt_version=extractor.PROMPT_VERSION,
            docling_version=extractor.version_docling(),
            pages_ocr=analyse.conversion.pages_ocr,
            duree_conversion_s=analyse.conversion.elapsed_s,
            duree_llm_s=analyse.duree_llm_s,
            pic_memoire_mo=pic_memoire_mo(),
        ),
        statuts={c.metric_code: c.status for c in extractor.couvertures(analyse, identifiant)},
    )
