from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Marqueurs des valeurs d'exemple de .env.example — jamais acceptables une fois
# ENVIRONMENT=production (voir Settings._rejeter_placeholders_en_production).
_MARQUEURS_PLACEHOLDER = ("changeme", "gemini-api-key-example-replace-me")


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
    # Origine servant à construire le lien de réinitialisation de mot de passe
    # (app/auth/password_reset.py) — le frontend Vite en dev, le domaine réel en production.
    frontend_base_url: str = "http://localhost:5173"
    # Le serveur peut démarrer sans SMTP ; les formulaires publics signalent alors
    # l'indisponibilité de l'envoi, sans exposer les comptes ni les jetons.
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_security: Literal["starttls", "ssl", "plain"] = "starttls"
    smtp_timeout_seconds: float = Field(default=10, gt=0, le=60)
    mail_from: str = ""
    contact_to_email: str = ""
    # Délai au-delà duquel un rapport affecté sans avis rendu (ESGReport.assigned_at) compte
    # comme "en retard" au dashboard Administrateur — configurable par déploiement (SLA_AUDIT_JOURS
    # dans .env), pas via un écran admin (aucun n'existe pour cette pondération, cohérent avec
    # app/scoring/config_schema.py, pas plus exposé).
    sla_audit_jours: int = 10
    # Délai au-delà duquel un rapport dont l'extraction reste RUNNING
    # compte comme "bloqué" (traitement probablement interrompu) plutôt que "encore en cours" —
    # même principe de configuration que sla_audit_jours. Docling seul a pris ~9 min sur un rapport
    # de 25 pages (mesuré Phase 5) ; généreux pour éviter un faux positif sur un long rapport.
    extraction_timeout_minutes: int = 60
    # Contrôle KYC d'une inscription (tâche 5.3) : fiche LEI publique de la GLEIF. Délai court —
    # l'Administrateur attend la réponse ; GLEIF indisponible donne « non vérifiable », jamais une
    # erreur ni un blocage de la décision.
    gleif_api_url: str = "https://api.gleif.org/api/v1"
    gleif_timeout_seconds: float = Field(default=5, gt=0, le=30)

    @property
    def gemini_api_key_is_placeholder(self) -> bool:
        """Utilisé par app/ingestion/extractor.py pour basculer sur une extraction synthétique
        de démonstration plutôt que d'échouer à chaque dépôt tant qu'aucune vraie clé n'est
        configurée — jamais vrai en production (_rejeter_placeholders_en_production ci-dessous
        bloque le démarrage dans ce cas)."""
        return "gemini-api-key-example-replace-me" in self.gemini_api_key

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
    gemini_api_key: str
    storage_backend: str
    storage_path: str
    default_scoring_config: str
    fx_rates_path: str
    emission_factors_path: str
    environment: str

    @model_validator(mode="after")
    def _rejeter_placeholders_en_production(self) -> "Settings":
        """Un déploiement production avec une valeur encore recopiée de
        .env.example (ex. SECRET_KEY=changeme-...) n'est pas une erreur de
        config à découvrir en incident — elle doit bloquer le démarrage."""
        if self.environment != "production":
            return self

        if self.smtp_security == "plain":
            raise ValueError("SMTP_SECURITY=plain est interdit quand ENVIRONMENT=production.")

        valeurs_sensibles = {
            "SECRET_KEY": self.secret_key,
            "DATABASE_URL": self.database_url,
            "GEMINI_API_KEY": self.gemini_api_key,
        }
        for nom, valeur in valeurs_sensibles.items():
            if any(marqueur in valeur for marqueur in _MARQUEURS_PLACEHOLDER):
                raise ValueError(
                    f"{nom} contient encore une valeur d'exemple de .env.example — "
                    "interdit quand ENVIRONMENT=production."
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
