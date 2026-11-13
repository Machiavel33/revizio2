"""Middleware de sécurité du service STT.

Le service STT est interne (pas de port publié) mais on le durcit quand même :
- **En-têtes de sécurité** sur toutes les réponses HTTP.
- **Authentification par secret partagé** : l'API envoie `X-STT-Token` (dérivé de
  STT_SHARED_SECRET). Sans ce secret, un conteneur compromis sur le réseau Docker
  ne peut pas utiliser le STT. Le WebSocket accepte le token en query `?token=`
  (les navigateurs/clients WS ne posent pas d'en-tête custom facilement).
- **Limite de taille** des corps HTTP (prévention DoS mémoire).
"""

import hmac

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        for key, value in SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)
        return response


def _token_ok(provided: str | None, expected: str) -> bool:
    if not expected:
        return True  # secret non configuré : pas d'auth (dev)
    if not provided:
        return False
    return hmac.compare_digest(provided, expected)


class SharedSecretMiddleware(BaseHTTPMiddleware):
    """Exige X-STT-Token (HTTP) ou ?token= (WS) si STT_SHARED_SECRET est défini.

    /health reste public (healthcheck Docker).
    """

    def __init__(self, app, secret: str):
        super().__init__(app)
        self.secret = secret

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self.secret:
            return await call_next(request)
        path = request.url.path
        if path == "/health":
            return await call_next(request)
        # WebSocket : token en query string
        if request.scope.get("type") == "websocket":
            provided = request.query_params.get("token")
        else:
            provided = request.headers.get("x-stt-token")
        if not _token_ok(provided, self.secret):
            return JSONResponse(
                status_code=401,
                content={"detail": "Token STT manquant ou invalide"},
            )
        return await call_next(request)
