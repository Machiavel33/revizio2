"""Service d'audit immuable (chaîne de hachage append-only).

Chaque entrée est chaînée à la précédente via SHA-256 :
    entry_hash = SHA256(prev_hash || seq || actor_id || action || target || metadata || created_at)

Toute modification/suppression d'une entrée casse la chaîne, détectable par
`verify_chain()`. Le journal est append-only : on n'update/delete jamais.
"""

import hashlib
import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


def _normalize_ts(created_at: datetime) -> str:
    """Normalise le timestamp en UTC naïf (indépendant du backend DB).

    SQLite supprime la timezone au stockage ; on normalise donc toujours en
    UTC sans tzinfo pour que le hash soit stable entre écriture et vérification.
    """
    if created_at.tzinfo is not None:
        created_at = created_at.astimezone(UTC).replace(tzinfo=None)
    return created_at.isoformat()


def _compute_hash(
    prev_hash: str,
    seq: int,
    actor_id: str | None,
    action: str,
    target: str | None,
    metadata: dict,
    created_at: datetime,
) -> str:
    payload = json.dumps(
        {
            "prev": prev_hash,
            "seq": seq,
            "actor": actor_id,
            "action": action,
            "target": target,
            "metadata": metadata,
            "ts": _normalize_ts(created_at),
        },
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def record(
    db: AsyncSession,
    *,
    action: str,
    actor_id: uuid.UUID | None = None,
    target: str | None = None,
    metadata: dict | None = None,
) -> AuditLog:
    """Ajoute une entrée d'audit chaînée. À appeler dans la même transaction.

    Le `seq` est obtenu via une séquence PostgreSQL atomique (nextval) pour
    éviter les collisions sous concurrence. Le prev_hash est lu sous verrou
    (SELECT ... FOR UPDATE) pour garantir la cohérence de la chaîne.
    """
    metadata = metadata or {}

    # Verrouille la dernière entrée pour sérialiser l'append (évite la course).
    # with_for_update() est ignoré par SQLite (tests) mais actif sur PostgreSQL.
    last = await db.scalar(
        select(AuditLog).order_by(AuditLog.seq.desc()).limit(1).with_for_update()
    )
    prev_hash = last.entry_hash if last else ""

    # seq : séquence atomique PostgreSQL si disponible, sinon max()+1 (SQLite/tests)
    dialect = db.bind.dialect.name if db.bind is not None else ""
    if dialect == "postgresql":
        seq = int(await db.scalar(text("SELECT nextval('audit_logs_seq')")))
    else:
        seq = (last.seq + 1) if last else 1
    created_at = datetime.now(UTC)

    entry_hash = _compute_hash(
        prev_hash,
        seq,
        str(actor_id) if actor_id else None,
        action,
        target,
        metadata,
        created_at,
    )

    entry = AuditLog(
        seq=seq,
        actor_id=actor_id,
        action=action,
        target=target,
        metadata_=metadata,
        prev_hash=prev_hash,
        entry_hash=entry_hash,
        created_at=created_at,
    )
    db.add(entry)
    await db.flush()
    return entry


async def verify_chain(db: AsyncSession) -> tuple[bool, int | None]:
    """Vérifie l'intégrité de la chaîne. Retourne (ok, seq_de_la_première_entrée_cassée)."""
    rows = (await db.scalars(select(AuditLog).order_by(AuditLog.seq.asc()))).all()
    prev_hash = ""
    for entry in rows:
        expected = _compute_hash(
            prev_hash,
            entry.seq,
            str(entry.actor_id) if entry.actor_id else None,
            entry.action,
            entry.target,
            entry.metadata_,
            entry.created_at,
        )
        if entry.prev_hash != prev_hash or entry.entry_hash != expected:
            return False, entry.seq
        prev_hash = entry.entry_hash
    return True, None
