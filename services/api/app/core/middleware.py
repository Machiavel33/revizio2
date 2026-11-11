"""Middleware de sécurité : headers HTTP + rate-limiting simple (in-memory).

Le rate-limit est volontairement simple (fenêtre glissante par IP) et suffisant
pour un déploiement mono-instance. En multi-instance, remplacer par un backend
Redis (slowapi + storage Redis).
"""

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-XSS-Protection": "1; mode=block",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        for key, value in SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fenêtre glissante par IP : max `limit` requêtes par `window` secondes.

    Les routes d'authentification ont une limite plus stricte.
    """

    # Store partagé au niveau classe (permet un reset propre en tests)
    _hits: dict[str, deque[float]] = defaultdict(deque)

    def __init__(self, app, limit: int = 120, window: int = 60, auth_limit: int = 20):
        super().__init__(app)
        self.limit = limit
        self.window = window
        self.auth_limit = auth_limit

    @classmethod
    def reset(cls) -> None:
        """Vide les compteurs (utile pour l'isolation des tests)."""
        cls._hits.clear()

    def _client_key(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _is_limited(self, key: str, limit: int) -> bool:
        now = time.monotonic()
        bucket = self._hits[key]
        while bucket and now - bucket[0] > self.window:
            bucket.popleft()
        if len(bucket) >= limit:
            return True
        bucket.append(now)
        return False

    async def dispatch(self, request: Request, call_next) -> Response:
        # Ne pas limiter le health check
        if request.url.path == "/health":
            return await call_next(request)

        key = self._client_key(request)
        is_auth = request.url.path.startswith("/api/auth/")
        limit = self.auth_limit if is_auth else self.limit
        bucket_key = f"{key}:{'auth' if is_auth else 'api'}"

        if self._is_limited(bucket_key, limit):
            return JSONResponse(
                status_code=429,
                content={"detail": "Trop de requêtes. Réessayez dans un instant."},
                headers={"Retry-After": str(self.window)},
            )
        return await call_next(request)
