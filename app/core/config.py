from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Valeurs par défaut raisonnables pour le développement local.
    database_url: str = "postgresql+psycopg://greenfinance:changeme@localhost:5432/greenfinance"
    redis_url: str = "redis://localhost:6379/0"
    app_name: str = "GreenFinance-Scorer"
    app_version: str = "0.1.0"
    # Origines autorisées à appeler l'API en cross-origin (frontend Vite en dev,
    # domaine réel en production) — liste séparée par des virgules, jamais "*"
    # car les routes auth posent un cookie (allow_credentials nécessite une
    # liste explicite, voir app/api/router.py).
    cors_allowed_origins: str = "http://localhost:5173"

    @property
    def cors_allowed_origins_list(self) -> list[str]:
        origins = [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]
        if "*" in origins:
            # Starlette ne refuse pas "*" combiné à allow_credentials=True — il
            # reflète l'origine de la requête telle quelle (vérifié empiriquement),
            # ce qui autoriserait n'importe quel site à appeler l'API avec le
            # cookie de session. Refus explicite à la lecture plutôt qu'un trou
            # de sécurité silencieux.
            raise ValueError(
                "CORS_ALLOWED_ORIGINS ne doit jamais contenir '*' : combiné aux "
                "cookies de session (allow_credentials=True), Starlette reflète "
                "n'importe quelle origine au lieu de la refuser."
            )
        return origins

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
