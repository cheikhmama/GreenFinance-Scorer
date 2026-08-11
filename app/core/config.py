from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Valeurs par défaut raisonnables pour le développement local.
    database_url: str = "postgresql+psycopg://greenfinance:changeme@localhost:5432/greenfinance"
    redis_url: str = "redis://localhost:6379/0"
    app_name: str = "GreenFinance-Scorer"
    app_version: str = "0.1.0"

    # Pas de valeur par défaut : une variable manquante doit lever une erreur explicite.
    secret_key: str
    mfa_issuer_name: str
    anthropic_api_key: str
    storage_backend: str
    storage_path: str
    default_scoring_config: str
    emission_factors_path: str
    environment: str


@lru_cache
def get_settings() -> Settings:
    return Settings()
