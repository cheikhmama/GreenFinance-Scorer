"""Validation et encodage de l'avatar de profil (image envoyée par l'utilisateur).

Même principe frontière que app/company/upload_validation.py : le Content-Type déclaré par le
client est falsifiable, seule la signature binaire réelle du fichier fait foi. Stocké comme data
URI complet directement sur Utilisateur.avatar (même convention que Company.logo) — une image
d'avatar reste petite, pas besoin d'un fichier séparé sur disque ni d'une route de téléchargement
dédiée.
"""

import base64

from app.core.exceptions import ValidationError

TAILLE_MAX_OCTETS = 2 * 1024 * 1024

_SIGNATURES_PNG_JPEG: dict[bytes, str] = {
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
}


def _type_mime_reel(contenu: bytes) -> str:
    for signature, type_mime in _SIGNATURES_PNG_JPEG.items():
        if contenu.startswith(signature):
            return type_mime
    if len(contenu) >= 12 and contenu[0:4] == b"RIFF" and contenu[8:12] == b"WEBP":
        return "image/webp"
    raise ValidationError(
        "Le fichier doit être une image PNG, JPEG ou WEBP.", code="signature_invalide"
    )


def construire_avatar_data_uri(contenu: bytes) -> str:
    if len(contenu) == 0:
        raise ValidationError("Le fichier est vide.", code="fichier_vide")
    if len(contenu) > TAILLE_MAX_OCTETS:
        raise ValidationError(
            f"L'image dépasse la taille maximale autorisée "
            f"({TAILLE_MAX_OCTETS // (1024 * 1024)} Mo).",
            code="fichier_trop_volumineux",
        )
    type_mime = _type_mime_reel(contenu)
    encode = base64.b64encode(contenu).decode("ascii")
    return f"data:{type_mime};base64,{encode}"
