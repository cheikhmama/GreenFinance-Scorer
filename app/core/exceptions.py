"""Hiérarchie d'exceptions métier et gestionnaires d'erreurs globaux.

Impose un format de réponse d'erreur unique à toute la plateforme :
{"error": {"code", "message", "correlation_id"}}. Aucune trace technique
Python n'est jamais exposée dans une réponse HTTP — uniquement dans les
logs serveur (voir app/core/logging.py, Étape 2.4, pour la propagation du
correlation_id dans les logs).
"""

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = structlog.get_logger(__name__)


class GreenFinanceError(Exception):
    """Exception métier de base. Toute erreur applicative en hérite."""

    status_code: int = 500

    def __init__(self, code: str, message: str, fields: dict[str, str] | None = None) -> None:
        self.code = code
        self.message = message
        # Non nul uniquement pour une erreur de validation de formulaire — associe un message à
        # chaque champ concerné (ex. {"annee_reporting": "L'année est invalide."}).
        self.fields = fields
        super().__init__(message)


class NotFoundError(GreenFinanceError):
    status_code = 404

    def __init__(self, message: str, code: str = "not_found") -> None:
        super().__init__(code=code, message=message)


class ValidationError(GreenFinanceError):
    status_code = 422

    def __init__(
        self,
        message: str,
        code: str = "validation_error",
        fields: dict[str, str] | None = None,
    ) -> None:
        super().__init__(code=code, message=message, fields=fields)


class PermissionDeniedError(GreenFinanceError):
    status_code = 403

    def __init__(self, message: str, code: str = "permission_denied") -> None:
        super().__init__(code=code, message=message)


class ConflictError(GreenFinanceError):
    """La requête est valide mais l'état courant de la ressource ne la permet pas encore."""

    status_code = 409

    def __init__(self, message: str, code: str = "conflict") -> None:
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


def _error_body(
    request: Request,
    code: str,
    message: str,
    fields: dict[str, str] | None = None,
) -> dict[str, dict[str, object]]:
    error: dict[str, object] = {
        "code": code,
        "message": message,
        "correlation_id": _correlation_id(request),
    }
    if fields:
        error["fields"] = fields
    return {"error": error}


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
            content=_error_body(request, exc.code, exc.message, exc.fields),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Validation Pydantic native de FastAPI (corps/paramètres mal formés), levée avant
        # d'atteindre la route — sans ce gestionnaire, sa réponse ({"detail": [...]}) rompt le
        # contrat {"error": {...}} appliqué partout ailleurs (voir tests/unit/test_error_handlers.py).
        fields: dict[str, str] = {}
        for error in exc.errors():
            # error["loc"] est un tuple type ("body", "annee_reporting") pour un champ précis.
            # Un corps structurellement invalide (JSON illisible) donne juste ("body",) ou
            # ("body", 1) — pas de vrai nom de champ à isoler, jamais ajouté à fields.
            loc = error["loc"]
            if len(loc) > 1 and isinstance(loc[-1], str):
                fields[loc[-1]] = error["msg"]
        return JSONResponse(
            status_code=422,
            content=_error_body(request, "validation_error", "Données invalides.", fields),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_exception", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content=_error_body(request, "internal_error", "Une erreur interne est survenue."),
        )
