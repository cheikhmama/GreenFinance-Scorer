import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import jwt
import pytest

from app.auth.tokens import ALGORITHM, create_access_token
from app.core.config import get_settings
from app.core.dependencies import get_current_user, get_session
from app.core.enums import Role
from app.core.exceptions import UnauthorizedError


class _FakeSession:
    """Double minimal — évite toute dépendance à une base réelle pour ces
    tests unitaires (voir ARCHITECTURE.md §7 : un test unitaire reste vert
    que la base de données soit démarrée ou non)."""

    def __init__(self, user: object | None) -> None:
        self._user = user

    def get(self, _model: type, _id: uuid.UUID) -> object | None:
        return self._user


class _FakeUtilisateur:
    def __init__(self, *, actif: bool = True) -> None:
        self.id = uuid.uuid4()
        self.active = actif


@pytest.fixture(autouse=True)
def _pas_de_session_revoquee():
    """Ces tests portent sur get_current_user lui-même, pas sur la révocation (voir
    test_revocation.py) — Redis n'a pas à être joignable pour qu'ils restent verts."""
    with patch("app.core.dependencies.is_session_revoked", return_value=False):
        yield


def test_get_current_user_raises_unauthorized_when_no_cookie_is_present() -> None:
    with pytest.raises(UnauthorizedError, match="Authentification requise"):
        get_current_user(session=_FakeSession(None), access_token=None)  # type: ignore[arg-type]


def test_get_current_user_raises_unauthorized_for_an_invalid_token() -> None:
    with pytest.raises(UnauthorizedError, match="Jeton invalide"):
        get_current_user(session=_FakeSession(None), access_token="pas-un-jwt")  # type: ignore[arg-type]


def test_get_current_user_raises_unauthorized_for_a_token_with_a_non_uuid_subject() -> None:
    """Un jeton valide (bien signé, non expiré) mais dont le claim "sub" n'est
    pas un UUID ne doit jamais faire fuir une ValueError brute (500) — voir la
    règle de app/core/exceptions.py : aucune trace technique dans une réponse
    HTTP."""
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {"sub": "pas-un-uuid", "role": Role.RESEARCHER.value, "iat": now, "exp": now + timedelta(hours=1)}
    token = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)

    with pytest.raises(UnauthorizedError, match="Jeton invalide"):
        get_current_user(session=_FakeSession(None), access_token=token)  # type: ignore[arg-type]


def test_get_current_user_raises_unauthorized_when_the_user_no_longer_exists() -> None:
    token = create_access_token(uuid.uuid4(), Role.INVESTOR)

    with pytest.raises(UnauthorizedError, match="Compte introuvable"):
        get_current_user(session=_FakeSession(None), access_token=token)  # type: ignore[arg-type]


def test_get_current_user_raises_unauthorized_for_a_deactivated_account() -> None:
    user = _FakeUtilisateur(actif=False)
    token = create_access_token(user.id, Role.AUDITOR)

    with pytest.raises(UnauthorizedError, match="Compte introuvable"):
        get_current_user(session=_FakeSession(user), access_token=token)  # type: ignore[arg-type]


def test_get_current_user_returns_the_matching_active_user() -> None:
    user = _FakeUtilisateur(actif=True)
    token = create_access_token(user.id, Role.ENTERPRISE)

    result = get_current_user(session=_FakeSession(user), access_token=token)  # type: ignore[arg-type]

    assert result is user


def test_get_current_user_raises_unauthorized_when_session_is_revoked() -> None:
    user = _FakeUtilisateur(actif=True)
    token = create_access_token(user.id, Role.ENTERPRISE)

    with (
        patch("app.core.dependencies.is_session_revoked", return_value=True),
        pytest.raises(UnauthorizedError, match="révoquée"),
    ):
        get_current_user(session=_FakeSession(user), access_token=token)  # type: ignore[arg-type]


def test_get_session_is_reexported_from_database_module() -> None:
    from app.core.database import get_session as original_get_session

    assert get_session is original_get_session
