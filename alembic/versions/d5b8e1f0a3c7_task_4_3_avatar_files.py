"""task 4.3: user avatars stored as files instead of base64 in the users row

users.avatar (data URI complet, relu à chaque requête authentifiée) -> users.avatar_path (chemin
relatif sous STORAGE_PATH, fichier avatars/{user_id}/{hex}.{ext}). Les avatars existants sont
écrits sur disque puis la colonne est supprimée. Un data URI illisible ou qui n'est pas une image
PNG/JPEG/WEBP est abandonné (signalé par la migration), jamais une ligne pointant vers un fichier
inexistant ni un contenu arbitraire écrit sur disque.

Écrit sous le STORAGE_PATH de l'environnement qui exécute la migration : le même volume que
l'API (service `migrate`, docker-compose.yml).

Revision ID: d5b8e1f0a3c7
Revises: a7e3b9c2d410
Create Date: 2026-10-05 09:00:00.000000

"""
import base64
import binascii
import uuid
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa

from alembic import op
from app.core.config import get_settings

# revision identifiers, used by Alembic.
revision: str = 'd5b8e1f0a3c7'
down_revision: str | Sequence[str] | None = 'a7e3b9c2d410'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_EXTENSIONS = {'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp'}
_TYPES = {ext: type_mime for type_mime, ext in _EXTENSIONS.items()}


def _racine() -> Path:
    return Path(get_settings().storage_path).resolve()


def _decoder(data_uri: str) -> tuple[str, bytes] | None:
    entete, _, charge = data_uri.partition(',')
    type_mime = entete.removeprefix('data:').removesuffix(';base64')
    if type_mime not in _EXTENSIONS or not entete.endswith(';base64'):
        return None
    try:
        return type_mime, base64.b64decode(charge, validate=True)
    except (binascii.Error, ValueError):
        return None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('avatar_path', sa.String(length=255), nullable=True))
    connexion = op.get_bind()
    racine = _racine()
    for user_id, data_uri in connexion.execute(
        sa.text('SELECT id, avatar FROM users WHERE avatar IS NOT NULL')
    ).all():
        decode = _decoder(data_uri)
        if decode is None:
            print(f'avatar illisible abandonné pour {user_id}')
            continue
        type_mime, contenu = decode
        relatif = f'avatars/{user_id}/{uuid.uuid4().hex}.{_EXTENSIONS[type_mime]}'
        cible = racine / relatif
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(contenu)
        connexion.execute(
            sa.text('UPDATE users SET avatar_path = :chemin WHERE id = :id'),
            {'chemin': relatif, 'id': user_id},
        )
    op.drop_column('users', 'avatar')


def downgrade() -> None:
    """Downgrade schema — les fichiers sont relus dans la colonne puis laissés sur disque."""
    op.add_column('users', sa.Column('avatar', sa.String(), nullable=True))
    connexion = op.get_bind()
    racine = _racine()
    for user_id, relatif in connexion.execute(
        sa.text('SELECT id, avatar_path FROM users WHERE avatar_path IS NOT NULL')
    ).all():
        fichier = racine / relatif
        type_mime = _TYPES.get(fichier.suffix.lstrip('.'))
        if type_mime is None or not fichier.is_file():
            continue
        encode = base64.b64encode(fichier.read_bytes()).decode('ascii')
        connexion.execute(
            sa.text('UPDATE users SET avatar = :avatar WHERE id = :id'),
            {'avatar': f'data:{type_mime};base64,{encode}', 'id': user_id},
        )
    op.drop_column('users', 'avatar_path')
