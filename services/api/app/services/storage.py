"""Service de stockage S3/MinIO (audio)."""

import uuid
from functools import lru_cache

import boto3
from botocore.client import Config

from app.core.config import settings


@lru_cache
def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4"),
    )


def build_audio_key(user_id: uuid.UUID, course_id: uuid.UUID, filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "webm"
    return f"audio/{user_id}/{course_id}.{ext}"


def upload_audio(key: str, data: bytes, content_type: str = "audio/webm") -> str:
    """Upload un blob audio et retourne l'URL S3 (endpoint + bucket + key)."""
    client = get_s3_client()
    client.put_object(
        Bucket=settings.minio_bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    return f"{settings.s3_endpoint_url}/{settings.minio_bucket}/{key}"


def delete_audio(key: str) -> None:
    client = get_s3_client()
    client.delete_object(Bucket=settings.minio_bucket, Key=key)
