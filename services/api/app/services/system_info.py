"""Service d'information système : versions, santé des services, uptime."""

import platform
import time

import redis.asyncio as aioredis
from sqlalchemy import text

from app.core.config import settings
from app.core.database import AsyncSessionLocal

# Uptime de l'API (process)
_START_TIME = time.time()

APP_VERSION = "0.1.0"


def uptime_seconds() -> int:
    return int(time.time() - _START_TIME)


async def check_database() -> dict:
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        return {"name": "PostgreSQL", "status": "up"}
    except Exception as exc:  # noqa: BLE001
        return {"name": "PostgreSQL", "status": "down", "error": str(exc)[:120]}


async def check_redis() -> dict:
    try:
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        pong = await r.ping()
        await r.aclose()
        return {"name": "Redis", "status": "up" if pong else "down"}
    except Exception as exc:  # noqa: BLE001
        return {"name": "Redis", "status": "down", "error": str(exc)[:120]}


async def check_celery() -> dict:
    """Vérifie qu'au moins un worker Celery répond (via inspect ping)."""
    try:
        from app.workers.celery_app import celery_app

        replies = celery_app.control.inspect(timeout=1.0).ping()
        workers = list(replies.keys()) if replies else []
        return {
            "name": "Celery worker",
            "status": "up" if workers else "down",
            "workers": workers,
        }
    except Exception as exc:  # noqa: BLE001
        return {"name": "Celery worker", "status": "down", "error": str(exc)[:120]}


async def system_info() -> dict:
    db, redis, celery = await check_database(), await check_redis(), await check_celery()
    return {
        "app": {
            "name": settings.app_name,
            "version": APP_VERSION,
            "environment": settings.app_env,
            "python": platform.python_version(),
            "platform": platform.platform(),
            "uptime_seconds": uptime_seconds(),
        },
        "services": [db, redis, celery],
        "storage_backend": settings.storage_backend,
        "rate_limit": {
            "enabled": settings.rate_limit_enabled,
            "backend": "redis" if settings.rate_limit_use_redis else "memory",
        },
    }
