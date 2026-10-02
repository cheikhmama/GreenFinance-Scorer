import pytest

from app.core.config import Settings

_CHAMPS_REQUIS_VALIDES = {
    "secret_key": "un-vrai-secret-genere-aleatoirement-32-octets",
    "mfa_issuer_name": "GreenFinance-Scorer",
    "gemini_api_key": "un-vrai-jeton-gemini",
    "storage_backend": "local",
    "storage_path": "./storage",
    "default_scoring_config": "config/weights/default.yaml",
    "emission_factors_path": "config/carbon/emission_factors.yaml",
    "database_url": "postgresql+psycopg://greenfinance:un-vrai-mdp@db:5432/greenfinance",
    # Explicite : le .env local du développeur peut viser Mailpit (`plain`, tâche 5.11), interdit
    # en production — ces tests ne doivent pas en dépendre.
    "smtp_security": "starttls",
}


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


def test_production_rejects_a_placeholder_secret_key() -> None:
    champs = {**_CHAMPS_REQUIS_VALIDES, "environment": "production"}
    champs["secret_key"] = "changeme-dev-secret-key-at-least-32-bytes-long"

    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(**champs)  # type: ignore[arg-type]  # dict[str,str] vs BaseSettings' propres kwargs (_cli_*, _secrets_dir...)


def test_production_rejects_a_placeholder_database_url() -> None:
    champs = {**_CHAMPS_REQUIS_VALIDES, "environment": "production"}
    champs["database_url"] = "postgresql+psycopg://greenfinance:changeme@db:5432/greenfinance"

    with pytest.raises(ValueError, match="DATABASE_URL"):
        Settings(**champs)  # type: ignore[arg-type]  # dict[str,str] vs BaseSettings' propres kwargs (_cli_*, _secrets_dir...)


def test_production_rejects_a_placeholder_gemini_api_key() -> None:
    champs = {**_CHAMPS_REQUIS_VALIDES, "environment": "production"}
    champs["gemini_api_key"] = "gemini-api-key-example-replace-me"

    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        Settings(**champs)  # type: ignore[arg-type]  # dict[str,str] vs BaseSettings' propres kwargs (_cli_*, _secrets_dir...)


def test_production_accepts_real_looking_values() -> None:
    champs = {**_CHAMPS_REQUIS_VALIDES, "environment": "production"}

    Settings(**champs)  # type: ignore[arg-type]  # ne lève pas


def test_development_tolerates_placeholder_values() -> None:
    champs = {**_CHAMPS_REQUIS_VALIDES, "environment": "development"}
    champs["secret_key"] = "changeme-dev-secret-key-at-least-32-bytes-long"

    Settings(**champs)  # type: ignore[arg-type]  # ne lève pas — le garde ne s'applique qu'en production


def test_production_rejects_unencrypted_smtp() -> None:
    champs = {**_CHAMPS_REQUIS_VALIDES, "environment": "production", "smtp_security": "plain"}
    with pytest.raises(ValueError, match="SMTP_SECURITY=plain"):
        Settings(**champs)  # type: ignore[arg-type]  # dict[str,str] vs BaseSettings' propres kwargs (_cli_*, _secrets_dir...)


@pytest.mark.parametrize(
    ("field", "value"),
    [("smtp_port", 0), ("smtp_port", 65536), ("smtp_timeout_seconds", 0), ("smtp_timeout_seconds", 61)],
)
def test_smtp_connection_settings_are_bounded(field, value) -> None:
    champs = {**_CHAMPS_REQUIS_VALIDES, "environment": "development", field: value}
    with pytest.raises(ValueError):
        Settings(**champs)  # type: ignore[arg-type]  # dict[str,str] vs BaseSettings' propres kwargs (_cli_*, _secrets_dir...)
