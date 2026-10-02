"""En-têtes de sécurité posés sur toutes les réponses de l'API.

Middleware ASGI pur (pas BaseHTTPMiddleware) : il ne réécrit que les en-têtes du message
`http.response.start`, sans mettre en mémoire le corps des réponses en flux (FileResponse).

- `X-Content-Type-Options: nosniff` : le navigateur respecte le Content-Type déclaré ;
- `X-Frame-Options: DENY` : aucune réponse affichable dans un cadre (clickjacking) ;
- `Referrer-Policy: no-referrer` : les liens à jeton (suivi d'inscription, activation) ne fuient
  jamais dans l'en-tête Referer — même règle que frontend/index.html ;
- `Cache-Control: no-store` sur /api/v1 quand la route n'en pose pas : statut d'une demande,
  profil, PDF déposés ne restent dans aucun cache partagé ;
- `Strict-Transport-Security` en production seulement (les cookies __Host- exigent déjà HTTPS).
"""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.auth.tokens import API_V1_PREFIX

_HSTS = (b"strict-transport-security", b"max-age=31536000; includeSubDomains")


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, *, hsts: bool = False) -> None:
        self.app = app
        self.hsts = hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        api = str(scope.get("path", "")).startswith(API_V1_PREFIX)

        async def envoyer(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                presents = {nom.lower() for nom, _ in headers}
                ajouts = [
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"no-referrer"),
                ]
                if api:
                    ajouts.append((b"cache-control", b"no-store"))
                if self.hsts:
                    ajouts.append(_HSTS)
                headers.extend((nom, valeur) for nom, valeur in ajouts if nom not in presents)
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, envoyer)
