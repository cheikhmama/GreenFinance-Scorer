"""Avatar de profil : validation et stockage en fichier (tâche 4.3).

Même principe frontière que app/company/upload_validation.py : le Content-Type déclaré par le
client est falsifiable, seule la signature binaire réelle du fichier fait foi.

Stockage : un fichier sous STORAGE_PATH/avatars/{user_id}/ (nom aléatoire), le chemin relatif sur
User.avatar_path — plus un data URI base64 dans la ligne utilisateur, relue à CHAQUE requête
authentifiée (get_current_user) : jusqu'à ~2,7 Mo par requête pour rien. Servi par
GET /auth/avatars/{user_id}/{fichier} ; le nom de fichier change à chaque envoi, l'URL peut donc
être mise en cache sans fin.

construire_avatar_data_uri reste pour le logo des entreprises (Company.logo), pas encore migré.
"""

import base64
import uuid
from pathlib import Path

import structlog
from sqlmodel import Session

from app.auth.models import User
from app.auth.tokens import API_V1_PREFIX
from app.core import storage
from app.core.exceptions import NotFoundError, ValidationError

logger = structlog.get_logger(__name__)

TAILLE_MAX_OCTETS = 2 * 1024 * 1024

_SIGNATURES_PNG_JPEG: dict[bytes, str] = {
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"\xff\xd8\xff": "image/jpeg",
}
EXTENSIONS: dict[str, str] = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}
TYPES_PAR_EXTENSION: dict[str, str] = {ext: type_mime for type_mime, ext in EXTENSIONS.items()}


def _type_mime_reel(contenu: bytes) -> str:
    for signature, type_mime in _SIGNATURES_PNG_JPEG.items():
        if contenu.startswith(signature):
            return type_mime
    if len(contenu) >= 12 and contenu[0:4] == b"RIFF" and contenu[8:12] == b"WEBP":
        return "image/webp"
    raise ValidationError(
        "Le fichier doit être une image PNG, JPEG ou WEBP.", code="signature_invalide"
    )


def _valider(contenu: bytes) -> str:
    if len(contenu) == 0:
        raise ValidationError("Le fichier est vide.", code="fichier_vide")
    if len(contenu) > TAILLE_MAX_OCTETS:
        raise ValidationError(
            f"L'image dépasse la taille maximale autorisée "
            f"({TAILLE_MAX_OCTETS // (1024 * 1024)} Mo).",
            code="fichier_trop_volumineux",
        )
    return _type_mime_reel(contenu)


def construire_avatar_data_uri(contenu: bytes) -> str:
    type_mime = _valider(contenu)
    encode = base64.b64encode(contenu).decode("ascii")
    return f"data:{type_mime};base64,{encode}"


def url_avatar(user: User) -> str | None:
    if user.avatar_path is None:
        return None
    return f"{API_V1_PREFIX}/auth/avatars/{user.id}/{Path(user.avatar_path).name}"


def _supprimer_fichier(chemin: str | None) -> None:
    """Best-effort, après le commit : un fichier orphelin ne casse rien, une ligne pointant vers
    un fichier absent, si."""
    if chemin is None:
        return
    try:
        storage.resolve_path(chemin).unlink(missing_ok=True)
    except OSError:
        logger.warning("avatar_ancien_fichier_non_supprime", user_id=chemin.split("/")[1])


def remplacer_avatar(session: Session, user: User, contenu: bytes) -> User:
    type_mime = _valider(contenu)
    ancien = user.avatar_path
    user.avatar_path = storage.save_bytes(
        f"avatars/{user.id}/{uuid.uuid4().hex}.{EXTENSIONS[type_mime]}", contenu
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    _supprimer_fichier(ancien)
    return user


def retirer_avatar(session: Session, user: User) -> User:
    ancien = user.avatar_path
    user.avatar_path = None
    session.add(user)
    session.commit()
    session.refresh(user)
    _supprimer_fichier(ancien)
    return user


def fichier_avatar(session: Session, user_id: uuid.UUID, nom_fichier: str) -> tuple[Path, str]:
    """Seulement l'avatar COURANT de cet utilisateur (jamais un ancien fichier, jamais un chemin
    construit depuis la requête) : le nom demandé doit être celui enregistré sur sa ligne."""
    user = session.get(User, user_id)
    if user is None or user.avatar_path is None or Path(user.avatar_path).name != nom_fichier:
        raise NotFoundError("Avatar introuvable.", code="avatar_introuvable")
    chemin = storage.resolve_path(user.avatar_path)
    if not chemin.is_file():
        raise NotFoundError("Avatar introuvable.", code="avatar_introuvable")
    return chemin, TYPES_PAR_EXTENSION.get(chemin.suffix.lstrip("."), "application/octet-stream")
