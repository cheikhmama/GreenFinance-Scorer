from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Response

from app.api.router import api_app

# Importés pour leur effet de bord : enregistrer chaque table dans le
# registre SQLAlchemy avant qu'une route ne déclenche la configuration des
# mappers — même besoin que alembic/env.py. Sans ça, une relationship() à
# référence différée (ex. Utilisateur.entreprise: Optional["Entreprise"])
# échoue au premier accès si son module n'a jamais été importé ailleurs.
from app.audit import models as _audit_models  # noqa: F401
from app.auth import models as _auth_models  # noqa: F401
from app.auth.tokens import API_V1_PREFIX
from app.company import models as _company_models  # noqa: F401
from app.core import models as _core_models  # noqa: F401
from app.core.config import get_settings
from app.core.database import DatabaseConnectionError, check_database_connection
from app.core.exceptions import register_exception_handlers
from app.core.logging import CorrelationIdMiddleware, configure_logging
from app.ingestion import models as _ingestion_models  # noqa: F401
from app.institution import models as _institution_models  # noqa: F401
from app.investor import models as _investor_models  # noqa: F401
from app.researcher import models as _researcher_models  # noqa: F401
from app.scoring import models as _scoring_models  # noqa: F401

settings = get_settings()
configure_logging(settings.environment)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        check_database_connection()
    except DatabaseConnectionError as exc:
        logger.error("database_check_failed_at_startup", error=str(exc))
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
register_exception_handlers(app)
app.add_middleware(CorrelationIdMiddleware)
app.mount(API_V1_PREFIX, api_app)


@app.get("/health")
def health(response: Response) -> dict[str, str]:
    try:
        check_database_connection()
    except DatabaseConnectionError as exc:
        # Route publique : jamais le message de l'exception (hôte, port, utilisateur de la base
        # peuvent y figurer) — seulement dans les journaux (tâche 4.3).
        logger.error("health_database_unreachable", error_type=type(exc.__cause__ or exc).__name__)
        response.status_code = 503
        return {"status": "error", "database": "unreachable"}
    return {"status": "ok", "database": "connected"}
