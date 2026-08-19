import pytest

from app.core.config import Settings


def test_cors_allowed_origins_list_splits_on_comma_and_trims_whitespace() -> None:
    settings = Settings.model_construct(cors_allowed_origins=" http://localhost:5173 , http://localhost:4173 ")

    assert settings.cors_allowed_origins_list == [
        "http://localhost:5173",
        "http://localhost:4173",
    ]


def test_cors_allowed_origins_list_ignores_empty_entries() -> None:
    settings = Settings.model_construct(cors_allowed_origins="http://localhost:5173,,")

    assert settings.cors_allowed_origins_list == ["http://localhost:5173"]


def test_cors_allowed_origins_list_rejects_a_bare_wildcard() -> None:
    settings = Settings.model_construct(cors_allowed_origins="*")

    with pytest.raises(ValueError, match="ne doit jamais contenir"):
        _ = settings.cors_allowed_origins_list


def test_cors_allowed_origins_list_rejects_a_wildcard_mixed_with_real_origins() -> None:
    settings = Settings.model_construct(cors_allowed_origins="http://localhost:5173,*")

    with pytest.raises(ValueError, match="ne doit jamais contenir"):
        _ = settings.cors_allowed_origins_list
