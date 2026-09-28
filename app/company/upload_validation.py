"""Validation d'un fichier PDF déposé par une Entreprise (Phase 4 §4.2).

Frontière délibérée : le contenu vient d'un client non fiable — nom de fichier et Content-Type
sont tous deux fournis par lui, donc falsifiables (voir app/company/router.py). Seule la
signature binaire réelle du fichier fait foi ici, jamais ces deux en-têtes.
"""

import hashlib

import pymupdf

from app.core.exceptions import ValidationError

# Le plus gros rapport du pilote documentaire (Schneider Electric, 290 pages) pèse une fraction
# de cette limite — large marge sans autoriser un dépôt disproportionné.
TAILLE_MAX_OCTETS = 50 * 1024 * 1024


def valider_pdf(contenu: bytes) -> None:
    if len(contenu) == 0:
        raise ValidationError("Le fichier est vide.", code="fichier_vide")
    if len(contenu) > TAILLE_MAX_OCTETS:
        raise ValidationError(
            f"Le fichier dépasse la taille maximale autorisée "
            f"({TAILLE_MAX_OCTETS // (1024 * 1024)} Mo).",
            code="fichier_trop_volumineux",
        )
    if not contenu.startswith(b"%PDF-"):
        raise ValidationError("Le fichier n'est pas un PDF valide.", code="signature_invalide")

    try:
        with pymupdf.open(stream=contenu, filetype="pdf") as document:
            if document.is_encrypted:
                raise ValidationError(
                    "Les fichiers PDF protégés par mot de passe ne sont pas acceptés.",
                    code="pdf_chiffre",
                )
    except ValidationError:
        raise
    except Exception as exc:
        # invalide doit être rejeté explicitement, jamais propager une exception bibliothèque brute.
        raise ValidationError(
            "Le fichier PDF est corrompu ou illisible.", code="pdf_illisible"
        ) from exc


def calculer_checksum(contenu: bytes) -> str:
    return hashlib.sha256(contenu).hexdigest()


# Longueur de colonne DB pour nom_fichier_origine (app/ingestion/models.py) — un nom de fichier
# client n'a aucune limite fiable, cette valeur ne sert qu'à l'affichage donc une troncature
# silencieuse est sans conséquence fonctionnelle.
LONGUEUR_MAX_NOM_FICHIER = 255


def nettoyer_nom_fichier(nom: str | None) -> str:
    """Nom de fichier original (client, falsifiable — voir docstring du module) retenu uniquement
    pour l'affichage, jamais comme chemin de stockage (app/company/rapports.py::_enregistrer_fichier)."""
    nom = (nom or "").strip()
    if not nom:
        return "rapport.pdf"
    return nom[:LONGUEUR_MAX_NOM_FICHIER]
