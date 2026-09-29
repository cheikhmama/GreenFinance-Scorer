"""Stockage des fichiers déposés par les entreprises (rapports PDF) et des artefacts générés par le
pipeline d'extraction (JSON Docling, extraits de preuve) — voir app/ingestion/extractor.py et
proof_generator.py.

Seul le backend "local" (STORAGE_PATH sur le disque du processus) est implémenté aujourd'hui, seule
valeur que STORAGE_BACKEND ait jamais prise — un backend non reconnu échoue explicitement plutôt que
d'écrire silencieusement au mauvais endroit.
"""

from pathlib import Path

from app.core.config import get_settings


def save_bytes(relative_path: str, content: bytes) -> str:
    """Écrit `content` sous STORAGE_PATH/relative_path (crée les dossiers parents si besoin) et
    renvoie relative_path tel quel — la valeur à stocker dans ESGReport.source_file ou
    PreuveDocumentaire.pdf_extrait_genere, jamais un chemin absolu (portable entre environnements)."""
    path = resolve_path(relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return relative_path


def resolve_path(stored_path: str) -> Path:
    """Reconvertit une valeur déjà stockée (ex. ESGReport.source_file) en chemin filesystem
    réel, symétrique de save_bytes. Refuse explicitement un chemin qui s'échapperait de
    STORAGE_PATH (ex. stored_path contenant "..") plutôt que d'écrire/lire hors du dossier prévu."""
    settings = get_settings()
    if settings.storage_backend != "local":
        raise NotImplementedError(
            f"Backend de stockage {settings.storage_backend!r} non implémenté — seul 'local' l'est."
        )

    base = Path(settings.storage_path).resolve()
    target = (base / stored_path).resolve()
    if target != base and base not in target.parents:
        raise ValueError(f"Chemin de stockage hors de STORAGE_PATH : {stored_path!r}")
    return target
