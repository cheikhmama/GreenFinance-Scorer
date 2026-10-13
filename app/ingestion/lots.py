"""Découpage d'un rapport en lots de pages consécutives, convertis un à un par Docling.

Un rapport de 200 à 600 pages converti d'un seul appel garde en mémoire tout le document Docling
et les images de pages en cours de traitement : c'est ce qui borne la mémoire du worker. Converti
par lots, le pic mémoire dépend de la taille d'un lot, plus de la longueur du rapport.

L'OCR n'est activé que pour les lots contenant au moins une page sans couche texte (page scannée) :
les rapports ESG sont presque toujours nativement numériques, et l'OCR est l'étape la plus coûteuse
de la conversion en temps comme en mémoire.
"""

from dataclasses import dataclass
from pathlib import Path

import pymupdf

# En dessous, une page est traitée comme scannée (texte natif absent ou résiduel : numéro de page).
SEUIL_CARACTERES_TEXTE = 50


class DocumentTropLong(ValueError):
    """Au-delà du plafond de pages configuré : refusé avant toute conversion."""


@dataclass(frozen=True)
class Lot:
    debut: int  # numéros de page à partir de 1, bornes incluses (convention page_range Docling)
    fin: int
    ocr: bool


def planifier_lots(
    chemin: Path,
    *,
    taille: int,
    pages_max: int | None = None,
    seuil_caracteres: int = SEUIL_CARACTERES_TEXTE,
) -> list[Lot]:
    with pymupdf.open(chemin) as document:
        nombre = document.page_count
        if pages_max is not None and nombre > pages_max:
            raise DocumentTropLong(f"{nombre} pages, plafond {pages_max}.")
        scannees = {
            index + 1
            for index, page in enumerate(document)
            if len(page.get_text("text").strip()) < seuil_caracteres
        }
    return [
        Lot(debut, fin, ocr=any(p in scannees for p in range(debut, fin + 1)))
        for debut in range(1, nombre + 1, taille)
        for fin in [min(debut + taille - 1, nombre)]
    ]
