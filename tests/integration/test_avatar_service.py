"""Service d'avatar (tâche 4.5) : branches que le parcours HTTP ne traverse pas."""

import uuid

import pytest

from app.auth import avatar
from app.auth.models import User
from app.core import storage
from app.core.enums import Role
from app.core.exceptions import NotFoundError, ValidationError

WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 24


def _utilisateur(session) -> User:
    utilisateur = User(email=f"av-{uuid.uuid4()}@example.com", role=Role.INVESTOR)
    session.add(utilisateur)
    session.commit()
    return utilisateur


@pytest.mark.parametrize(
    ("contenu", "code"),
    [
        (b"", "fichier_vide"),
        (b"\x89PNG\r\n\x1a\n" + b"0" * avatar.TAILLE_MAX_OCTETS, "fichier_trop_volumineux"),
        (b"<svg onload=alert(1)>", "signature_invalide"),  # le type réel, jamais l'extension
    ],
    # Identifiants explicites : sans eux, pytest mettrait les 2 Mo du contenu dans l'identifiant.
    ids=["vide", "trop-volumineux", "pas-une-image"],
)
def test_contenus_refuses(session, contenu: bytes, code: str) -> None:
    utilisateur = _utilisateur(session)

    with pytest.raises(ValidationError) as refus:
        avatar.remplacer_avatar(session, utilisateur, contenu)

    assert refus.value.code == code
    session.refresh(utilisateur)
    assert utilisateur.avatar_path is None


def test_webp_accepte_et_servi_avec_son_type(session) -> None:
    utilisateur = avatar.remplacer_avatar(session, _utilisateur(session), WEBP)

    assert utilisateur.avatar_path is not None and utilisateur.avatar_path.endswith(".webp")
    nom = utilisateur.avatar_path.rsplit("/", 1)[1]
    chemin, type_mime = avatar.fichier_avatar(session, utilisateur.id, nom)
    assert type_mime == "image/webp"
    assert chemin.read_bytes() == WEBP


def test_fichier_disparu_du_stockage_devient_introuvable(session) -> None:
    utilisateur = avatar.remplacer_avatar(session, _utilisateur(session), WEBP)
    assert utilisateur.avatar_path is not None
    storage.resolve_path(utilisateur.avatar_path).unlink()

    with pytest.raises(NotFoundError):
        avatar.fichier_avatar(session, utilisateur.id, utilisateur.avatar_path.rsplit("/", 1)[1])
