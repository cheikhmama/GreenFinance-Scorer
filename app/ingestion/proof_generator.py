"""Génération des preuves de traçabilité de l'extraction documentaire.

Produit, pour une page physique donnée d'un rapport, un mini-PDF extrait (la preuve documentaire
visible par un Auditeur ou un Investisseur) et l'entité Evidence correspondante.

Fonction pure : ne touche pas la session DB — l'appelant (app/ingestion/extractor.py) décide de
l'ajout/flush, et est responsable de dédupliquer les appels par page (Evidence est
many-to-one avec ESGMetric/CarbonEmission : plusieurs indicateurs trouvés sur la même page
partagent une seule preuve, pas une par indicateur).
"""

import uuid
from pathlib import Path

import pymupdf

from app.core import storage
from app.ingestion.models import Evidence


def generate_page_proof(
    *,
    source_pdf_path: Path,
    nom_document: str,
    annee: int,
    nombre_pages_total: int,
    page: int,
    rapport_id: uuid.UUID,
) -> Evidence:
    """Découpe la page physique `page` du PDF source (1-indexée, cohérente avec la provenance
    Docling) en un mini-PDF autonome, le persiste via app.core.storage, et renvoie une
    Evidence non ajoutée à la session. page_debut == page_fin == page pour ce MVP : chaque
    IndicateurExtrait.page_source désigne toujours une page unique, jamais une plage."""
    with pymupdf.open(source_pdf_path) as source:
        extrait = pymupdf.open()
        extrait.insert_pdf(source, from_page=page - 1, to_page=page - 1)
        contenu = extrait.tobytes()
        extrait.close()

    chemin_relatif = f"preuves/{rapport_id}/page_{page}.pdf"
    storage.save_bytes(chemin_relatif, contenu)

    return Evidence(
        document_name=nom_document,
        year=annee,
        total_pages=nombre_pages_total,
        page_start=page,
        page_end=page,
        excerpt_pdf_path=chemin_relatif,
    )
