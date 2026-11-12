"""Service de présence live (sessions actives) via Redis.

Chaque requête authentifiée met à jour un heartbeat (clé Redis avec TTL).
Les utilisateurs "en ligne" = ceux dont le heartbeat est encore valide.
"""

import time
import uuid

import redis.asyncio as aioredis

from app.core.config import settings

PRESENCE_PREFIX = "presence:user:"
PRESENCE_TTL = 120  # secondes : un user est "en ligne" s'il a une activité < 2 min


def _client() -> aioredis.Redis:
    return aioredis.from_url(settings.redis_url, decode_responses=True)


async def heartbeat(user_id: uuid.UUID, email: str, display_name: str) -> None:
    """Enregistre/rafraîchit la présence d'un utilisateur."""
    try:
        r = _client()
        key = f"{PRESENCE_PREFIX}{user_id}"
        now = int(time.time())
        await r.hset(key, mapping={"email": email, "name": display_name, "last_seen": now})
        await r.expire(key, PRESENCE_TTL)
        await r.aclose()
    except Exception:  # noqa: BLE001
        # La présence est best-effort : ne jamais bloquer une requête
        pass


async def online_users() -> list[dict]:
    """Retourne la liste des utilisateurs actuellement en ligne."""
    try:
        r = _client()
        keys = [k async for k in r.scan_iter(match=f"{PRESENCE_PREFIX}*")]
        result = []
        now = int(time.time())
        for k in keys:
            data = await r.hgetall(k)
            if not data:
                continue
            last_seen = int(data.get("last_seen", 0))
            if now - last_seen > PRESENCE_TTL:
                continue
            result.append(
                {
                    "user_id": k.split(":")[-1],
                    "email": data.get("email", ""),
                    "display_name": data.get("name", ""),
                    "last_seen": last_seen,
                    "idle_seconds": now - last_seen,
                }
            )
        await r.aclose()
        result.sort(key=lambda x: x["last_seen"], reverse=True)
        return result
    except Exception:  # noqa: BLE001
        return []


async def online_count() -> int:
    return len(await online_users())
