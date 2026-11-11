"""Tests du rate-limiter distribué (Redis via fakeredis) + fallback mémoire."""

import pytest

from app.core.middleware import RateLimitMiddleware, _InMemoryStore


class _FakeApp:
    """App ASGI minimale pour instancier le middleware."""

    async def __call__(self, scope, receive, send):  # pragma: no cover
        pass


@pytest.mark.asyncio
async def test_redis_sliding_window_allows_then_blocks():
    import fakeredis.aioredis

    server = fakeredis.FakeServer()
    fake = fakeredis.aioredis.FakeRedis(server=server, decode_responses=True)

    mw = RateLimitMiddleware(_FakeApp(), limit=3, window=60, auth_limit=3)
    # Injecte le client fakeredis + script
    mw._redis = fake
    mw._redis_script = fake.register_script(
        __import__("app.core.middleware", fromlist=["_SLIDING_WINDOW_LUA"])._SLIDING_WINDOW_LUA
    )

    key = "rl:1.2.3.4:api"
    assert await mw._allow(key, 3) is True
    assert await mw._allow(key, 3) is True
    assert await mw._allow(key, 3) is True
    # 4e requête : bloquée
    assert await mw._allow(key, 3) is False


@pytest.mark.asyncio
async def test_redis_failure_falls_back_to_memory():
    mw = RateLimitMiddleware(_FakeApp(), limit=2, window=60, auth_limit=2)

    class _BrokenRedis:
        async def __call__(self, *a, **k):
            raise ConnectionError("redis down")

    mw._redis = object()
    mw._redis_script = _BrokenRedis()

    key = "rl:5.6.7.8:api"
    assert await mw._allow(key, 2) is True
    assert await mw._allow(key, 2) is True
    # 3e : bloquée par le fallback mémoire
    assert await mw._allow(key, 2) is False


def test_in_memory_store_window():
    store = _InMemoryStore()
    assert store.allow("k", 2, 60) is True
    assert store.allow("k", 2, 60) is True
    assert store.allow("k", 2, 60) is False
    store.reset()
    assert store.allow("k", 2, 60) is True
