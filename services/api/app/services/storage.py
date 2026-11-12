"""Service de stockage audio.

Deux backends :
- S3/MinIO si `S3_ENDPOINT_URL` est configuré (production cloud).
- Filesystem local sinon (déploiement mono-serveur sans S3).

Le backend est choisi automatiquement via `settings.storage_backend`.
"""

import uuid
from functools import lru_cache
from pathlib import Path

from app.core.config import settings


@lru_cache
def get_s3_client():
    import boto3
    from botocore.client import Config

    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4"),
    )


def _local_root() -> Path:
    root = Path(settings.local_storage_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def build_audio_key(user_id: uuid.UUID, course_id: uuid.UUID, filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "webm"
    return f"audio/{user_id}/{course_id}.{ext}"


def upload_audio(key: str, data: bytes, content_type: str = "audio/webm") -> str:
    """Stocke un blob audio et retourne une URL de référence."""
    if settings.storage_backend == "s3":
        client = get_s3_client()
        client.put_object(
            Bucket=settings.minio_bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return f"{settings.s3_endpoint_url}/{settings.minio_bucket}/{key}"

    # Backend filesystem local
    dest = _local_root() / key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    # URL interne servie par l'API (/api/files/<key>)
    return f"local://{key}"


def read_audio(key: str) -> bytes:
    """Lit un blob audio (utilisé par le worker pour la transcription)."""
    if settings.storage_backend == "s3":
        client = get_s3_client()
        obj = client.get_object(Bucket=settings.minio_bucket, Key=key)
        return obj["Body"].read()
    return (_local_root() / key).read_bytes()


def delete_audio(key: str) -> None:
    if settings.storage_backend == "s3":
        client = get_s3_client()
        client.delete_object(Bucket=settings.minio_bucket, Key=key)
        return
    path = _local_root() / key
    if path.exists():
        path.unlink()


def local_path(key: str) -> Path | None:
    """Retourne le chemin local d'un blob (backend filesystem uniquement)."""
    if settings.storage_backend != "s3":
        return _local_root() / key
    return None


def key_from_url(url: str) -> str:
    """Extrait la clé de stockage depuis une URL de référence."""
    if url.startswith("local://"):
        return url[len("local://") :]
    # URL S3 : .../<bucket>/<key>
    marker = f"/{settings.minio_bucket}/"
    if marker in url:
        return url.split(marker, 1)[1]
    return url


__all__ = [
    "build_audio_key",
    "upload_audio",
    "read_audio",
    "delete_audio",
    "local_path",
    "key_from_url",
]
