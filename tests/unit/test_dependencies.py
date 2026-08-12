import pytest

from app.core.dependencies import get_current_user, get_session


def test_get_current_user_raises_not_implemented_with_explicit_message() -> None:
    with pytest.raises(NotImplementedError, match=r"^Authentification implémentée à l'Étape 9$"):
        get_current_user()


def test_get_session_is_reexported_from_database_module() -> None:
    from app.core.database import get_session as original_get_session

    assert get_session is original_get_session
