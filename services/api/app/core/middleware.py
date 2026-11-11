"""Middleware de sécurité : headers HTTP + rate-limiting distribué (Redis).

Le rate-limit utilise une fenêtre glissante atomique implémentée en Lua côté Redis
(compatible multi-instance). Si Redis est indisponible, on retombe sur un store
in-memory (mono-instance) pour ne jamais bloquer le service.
"""

import time
import uuid
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

# Fenêtre glissante atomique : ZREMRANGEBYSCORE (purge) + ZCARD (compte) + ZADD.
# Retourne 1 si la requête est autorisée, 0 si la limite est atteinte.
_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local member = ARGV[4]
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)
if count < limit then
  redis.call('ZADD', key, now, member)
  redis.call('PEXPIRE', key, window)
  return 1
end
return 0
"""


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        for key, value in SECURITY_HEADERS.items():
            response.headers.setdefault(key, value)
        return response


class _InMemoryStore:
    """Store de secours (mono-instance) : fenêtre glissante par clé."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, limit: int, window: float) -> bool:
        now = time.monotonic()
        bucket = self._hits[key]
        while bucket and now - bucket[0] > window:
            bucket.popleft()
        if len(bucket) >= limit:
            return False
        bucket.append(now)
        return True

    def reset(self) -> None:
        self._hits.clear()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fenêtre glissante par IP : max `limit` requêtes par `window` secondes.

    - Si `redis_url` est fourni et joignable : store Redis distribué (Lua atomique).
    - Sinon : store in-memory (mono-instance).
    Les routes d'authentification ont une limite plus stricte.
    """

    def __init__(
        self,
        app,
        limit: int = 120,
        window: int = 60,
        auth_limit: int = 20,
        redis_url: str | None = None,
    ):
        super().__init__(app)
        self.limit = limit
        self.window = window
        self.auth_limit = auth_limit
        self._memory = _InMemoryStore()
        self._redis = None
        self._redis_script = None
        if redis_url:
            try:
                import redis.asyncio as aioredis

                self._redis = aioredis.from_url(redis_url, decode_responses=True)
                self._redis_script = self._redis.register_script(_SLIDING_WINDOW_LUA)
            except Exception:  # noqa: BLE001
                self._redis = None

    @classmethod
    def reset(cls) -> None:
        """Compat tests : no-op au niveau classe (le store est par instance)."""

    def _client_key(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def _allow(self, bucket_key: str, limit: int) -> bool:
        if self._redis is not None and self._redis_script is not None:
            try:
                now_ms = int(time.time() * 1000)
                # Membre unique (timestamp + aléa) pour éviter les collisions ZADD
                member = f"{now_ms}-{uuid.uuid4().hex}"
                result = await self._redis_script(
                    keys=[bucket_key],
                    args=[now_ms, self.window * 1000, limit, member],
                )
                return bool(result)
            except Exception:  # noqa: BLE001
                # Redis indisponible : bascule sur le store mémoire
                pass
        return self._memory.allow(bucket_key, limit, self.window)

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path == "/health":
            return await call_next(request)

        key = self._client_key(request)
        is_auth = request.url.path.startswith("/api/auth/")
        limit = self.auth_limit if is_auth else self.limit
        bucket_key = f"rl:{key}:{'auth' if is_auth else 'api'}"

        if not await self._allow(bucket_key, limit):
            return JSONResponse(
                status_code=429,
                content={"detail": "Trop de requêtes. Réessayez dans un instant."},
                headers={"Retry-After": str(self.window)},
            )
        return await call_next(request)
