"""Génération des preuves de traçabilité de l'extraction documentaire.

Produit, pour une page physique donnée d'un rapport, un mini-PDF extrait (la preuve documentaire
visible par un Auditeur ou un Investisseur) et l'entité PreuveDocumentaire correspondante.

Fonction pure : ne touche pas la session DB — l'appelant (app/ingestion/extractor.py) décide de
l'ajout/flush, et est responsable de dédupliquer les appels par page (PreuveDocumentaire est
many-to-one avec IndicateurESG/DonneeCarbone : plusieurs indicateurs trouvés sur la même page
partagent une seule preuve, pas une par indicateur).
"""

import uuid
from pathlib import Path

import pymupdf

from app.core import storage
from app.ingestion.models import PreuveDocumentaire


def generate_page_proof(
    *,
    source_pdf_path: Path,
    nom_document: str,
    annee: int,
    nombre_pages_total: int,
    page: int,
    rapport_id: uuid.UUID,
) -> PreuveDocumentaire:
    """Découpe la page physique `page` du PDF source (1-indexée, cohérente avec la provenance
    Docling) en un mini-PDF autonome, le persiste via app.core.storage, et renvoie une
    PreuveDocumentaire non ajoutée à la session. page_debut == page_fin == page pour ce MVP : chaque
    IndicateurExtrait.page_source désigne toujours une page unique, jamais une plage."""
    with pymupdf.open(source_pdf_path) as source:
        extrait = pymupdf.open()
        extrait.insert_pdf(source, from_page=page - 1, to_page=page - 1)
        contenu = extrait.tobytes()
        extrait.close()

    chemin_relatif = f"preuves/{rapport_id}/page_{page}.pdf"
    storage.save_bytes(chemin_relatif, contenu)

    return PreuveDocumentaire(
        nom_document=nom_document,
        annee=annee,
        nombre_pages_total=nombre_pages_total,
        page_debut=page,
        page_fin=page,
        pdf_extrait_genere=chemin_relatif,
    )
