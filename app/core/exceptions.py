"""Hiérarchie d'exceptions métier et gestionnaires d'erreurs globaux.

Impose un format de réponse d'erreur unique à toute la plateforme :
{"error": {"code", "message", "correlation_id"}}. Aucune trace technique
Python n'est jamais exposée dans une réponse HTTP — uniquement dans les
logs serveur (voir app/core/logging.py, Étape 2.4, pour la propagation du
correlation_id dans les logs).
"""

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)


class GreenFinanceError(Exception):
    """Exception métier de base. Toute erreur applicative en hérite."""

    status_code: int = 500

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class NotFoundError(GreenFinanceError):
    status_code = 404

    def __init__(self, message: str, code: str = "not_found") -> None:
        super().__init__(code=code, message=message)


class ValidationError(GreenFinanceError):
    status_code = 422

    def __init__(self, message: str, code: str = "validation_error") -> None:
        super().__init__(code=code, message=message)


class PermissionDeniedError(GreenFinanceError):
    status_code = 403

    def __init__(self, message: str, code: str = "permission_denied") -> None:
        super().__init__(code=code, message=message)


class TooManyRequestsError(GreenFinanceError):
    status_code = 429

    def __init__(self, message: str, code: str = "too_many_requests") -> None:
        super().__init__(code=code, message=message)


class UnauthorizedError(GreenFinanceError):
    """Absence ou invalidité d'authentification — distinct de
    PermissionDeniedError, qui suppose un utilisateur déjà identifié mais
    dont le rôle n'autorise pas l'action."""

    status_code = 401

    def __init__(self, message: str, code: str = "unauthorized") -> None:
        super().__init__(code=code, message=message)


class ServiceUnavailableError(GreenFinanceError):
    """Dépendance d'infrastructure indisponible (ex. Redis pour la limitation
    de débit du login) — échec fermé explicite en 503, jamais un succès
    silencieux sans la protection attendue, ni une 500 générique qui
    masquerait la vraie cause."""

    status_code = 503

    def __init__(self, message: str, code: str = "service_unavailable") -> None:
        super().__init__(code=code, message=message)


def _correlation_id(request: Request) -> str | None:
    return getattr(request.state, "correlation_id", None)


def register_exception_handlers(app: FastAPI) -> None:
    """Enregistre les gestionnaires globaux sur une application FastAPI donnée.

    À appeler explicitement sur chaque application FastAPI indépendante de
    l'arborescence (l'app racine et la sous-application /api/v1 montée par
    app.mount ont chacune leur propre pile de gestionnaires d'exceptions).
    """

    @app.exception_handler(GreenFinanceError)
    async def handle_green_finance_error(
        request: Request, exc: GreenFinanceError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "correlation_id": _correlation_id(request),
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_exception", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "Une erreur interne est survenue.",
                    "correlation_id": _correlation_id(request),
                }
            },
        )
