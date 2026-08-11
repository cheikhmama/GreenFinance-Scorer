import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response

from app.core.config import get_settings
from app.core.database import DatabaseConnectionError, check_database_connection

logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        check_database_connection()
    except DatabaseConnectionError as exc:
        logger.error("Database check failed at startup: %s", exc)
    yield


app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)


@app.get("/health")
def health(response: Response) -> dict[str, str]:
    try:
        check_database_connection()
    except DatabaseConnectionError as exc:
        response.status_code = 503
        return {"status": "error", "database": "unreachable", "detail": str(exc)}
    return {"status": "ok", "database": "connected"}
