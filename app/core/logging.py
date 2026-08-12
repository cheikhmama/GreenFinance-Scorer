"""Logging structuré (structlog) et traçabilité par requête.

Configure structlog en JSON quand ENVIRONMENT=production, en format
lisible dans le terminal quand ENVIRONMENT=development. Le middleware
CorrelationIdMiddleware génère un identifiant de corrélation par requête,
propagé automatiquement (via les contextvars structlog) dans chaque log
émis pendant le traitement de cette requête, ainsi que dans
request.state pour que la réponse d'erreur (app.core.exceptions) puisse
le réutiliser.
"""

import logging
import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


def configure_logging(environment: str) -> None:
    is_production = environment == "production"

    shared_processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.format_exc_info,
    ]
    renderer: structlog.typing.Processor = (
        structlog.processors.JSONRenderer() if is_production else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.INFO if is_production else logging.DEBUG
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Génère un correlation_id par requête et le lie aux logs structlog
    émis pendant son traitement, ainsi qu'à request.state."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        correlation_id = str(uuid.uuid4())
        request.state.correlation_id = correlation_id

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()

        response.headers["X-Correlation-ID"] = correlation_id
        return response
