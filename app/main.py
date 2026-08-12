from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Response

from app.api.router import api_app
from app.core.config import get_settings
from app.core.database import DatabaseConnectionError, check_database_connection
from app.core.exceptions import register_exception_handlers
from app.core.logging import CorrelationIdMiddleware, configure_logging

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
app.mount("/api/v1", api_app)


@app.get("/health")
def health(response: Response) -> dict[str, str]:
    try:
        check_database_connection()
    except DatabaseConnectionError as exc:
        response.status_code = 503
        return {"status": "error", "database": "unreachable", "detail": str(exc)}
    return {"status": "ok", "database": "connected"}
