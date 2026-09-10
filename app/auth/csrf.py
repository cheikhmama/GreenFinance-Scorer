"""Protection CSRF (Phase 3 §3.2) — double soumission signée, sans stockage serveur.

Le jeton CSRF n'est pas un secret à conserver quelque part : c'est un HMAC(secret_key, user_id
+ génération de session) recalculable à partir du JWT déjà validé — cohérent avec le choix déjà
fait de sessions sans état (voir app/auth/tokens.py). Un site tiers peut faire suivre le cookie
de session par le navigateur (SameSite ne bloque pas toutes les navigations), mais ne peut
jamais lire sa valeur ni celle du cookie CSRF pour la rejouer dans l'en-tête X-CSRF-Token exigé
— la same-origin policy l'en empêche.
"""

import hashlib
import hmac
import uuid
from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.auth.tokens import (
    API_V1_PREFIX,
    COOKIE_NAME,
    CSRF_HEADER_NAME,
    InvalidTokenError,
    decode_access_token,
)
from app.core.config import get_settings

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# Aucune session à protéger avant la première connexion : la soumettre à la vérification CSRF
# romprait le tout premier appel possible. request.url.path conserve le préfixe de montage
# complet à l'intérieur d'api_app (voir API_V1_PREFIX, app/auth/tokens.py).
_EXEMPT_PATHS = {f"{API_V1_PREFIX}/auth/login"}


def generate_csrf_token(user_id: uuid.UUID, generation: int) -> str:
    settings = get_settings()
    message = f"{user_id}:{generation}".encode()
    return hmac.new(settings.secret_key.encode(), message, hashlib.sha256).hexdigest()


def _origin_allowed(origin: str) -> bool:
    parsed = urlsplit(origin)
    candidate = f"{parsed.scheme}://{parsed.netloc}"
    return candidate in get_settings().cors_allowed_origins_list


def _rejet(request: Request, message: str) -> JSONResponse:
    correlation_id = getattr(request.state, "correlation_id", None)
    return JSONResponse(
        status_code=403,
        content={
            "error": {"code": "csrf_failed", "message": message, "correlation_id": correlation_id}
        },
    )


class CSRFMiddleware(BaseHTTPMiddleware):
    """Vérifie l'origine et le jeton CSRF sur toute requête mutante déjà authentifiée.

    Une requête sans cookie de session (pas de connexion) ou avec un jeton invalide/expiré
    n'est pas concernée ici — get_current_user (app/core/dependencies.py) produira le 401
    approprié plus loin dans la chaîne ; ce middleware ne ferme que la porte CSRF, jamais
    l'authentification elle-même.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.method in _MUTATING_METHODS and request.url.path not in _EXEMPT_PATHS:
            token = request.cookies.get(COOKIE_NAME)
            if token is not None:
                echec = self._verifier(request, token)
                if echec is not None:
                    return echec
        return await call_next(request)

    @staticmethod
    def _verifier(request: Request, token: str) -> JSONResponse | None:
        try:
            payload = decode_access_token(token)
            user_id = uuid.UUID(payload["sub"])
            generation = int(payload["gen"])
        except (InvalidTokenError, KeyError, ValueError):
            return None

        origin = request.headers.get("origin") or request.headers.get("referer")
        if origin is not None and not _origin_allowed(origin):
            return _rejet(request, "Origine non autorisée.")

        expected = generate_csrf_token(user_id, generation)
        provided = request.headers.get(CSRF_HEADER_NAME)
        if provided is None or not hmac.compare_digest(provided, expected):
            return _rejet(request, "Jeton CSRF manquant ou invalide.")

        return None
