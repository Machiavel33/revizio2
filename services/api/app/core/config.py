"""Configuration applicative (Pydantic Settings)."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "Revizio"
    app_env: str = "development"
    debug: bool = True
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    backend_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:5173,http://localhost:1420"

    # Security / JWT
    secret_key: str = "change_me_dev_only"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30
    byok_encryption_key: str = "change_me_dev_only_base64_32"

    # Database
    database_url: str = "postgresql+asyncpg://revizio:revizio_dev@localhost:5432/revizio"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    # Rate-limit distribué via Redis (fallback in-memory si indisponible)
    rate_limit_use_redis: bool = True
    # Désactivation totale du rate-limit (tests de charge uniquement)
    rate_limit_enabled: bool = True

    # S3 / MinIO
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key: str = "revizio"
    s3_secret_key: str = "revizio_dev_secret"
    s3_region: str = "us-east-1"
    minio_bucket: str = "revizio-audio"
    # Backend de stockage : "s3" (MinIO/cloud) ou "local" (filesystem mono-serveur)
    storage_backend: str = "s3"
    local_storage_dir: str = "/data/audio"
    # Répertoire des binaires de l'app desktop (installeurs)
    downloads_dir: str = "/data/downloads"

    # --- SMTP (emails transactionnels) ---
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_from: str = "Revizio <no-reply@revizio.darkops.fr>"
    frontend_url: str = "https://revizio.darkops.fr"

    # --- Quotas (par utilisateur, mensuel) ---
    quota_audio_minutes: int = 600
    quota_sheet_count: int = 100
    quota_alert_threshold: float = 0.8

    # --- Détection d'abus ---
    abuse_max_courses_per_hour: int = 20
    abuse_max_distinct_ips: int = 3

    # IA defaults
    default_transcribe_provider: str = "openai"
    default_sheet_provider: str = "anthropic"

    # --- Transcription locale (faster-whisper, open source) ---
    # Moteur : "auto" (local si dispo, sinon cloud), "local", "cloud"
    transcribe_engine: str = "auto"
    whisper_model: str = "small"  # tiny|base|small|medium|large-v3
    whisper_device: str = "cpu"  # cpu|cuda
    whisper_compute_type: str = "int8"  # int8|float16|float32

    # Upload limits (sécurité : prévention DoS mémoire)
    max_upload_bytes: int = 200 * 1024 * 1024  # 200 Mo
    allowed_audio_types: str = (
        "audio/webm,audio/wav,audio/x-wav,audio/mpeg,audio/ogg,audio/mp4,audio/flac"
    )

    @property
    def allowed_audio_type_list(self) -> list[str]:
        return [t.strip().lower() for t in self.allowed_audio_types.split(",") if t.strip()]

    @field_validator("cors_origins")
    @classmethod
    def _strip_origins(cls, v: str) -> str:
        return v.strip()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    def validate_production(self) -> None:
        """Refuse de démarrer en prod avec des secrets par défaut."""
        if not self.is_production:
            return
        problems = []
        if self.secret_key.startswith("change_me") or len(self.secret_key) < 32:
            problems.append("SECRET_KEY doit être une valeur forte (openssl rand -hex 32)")
        if self.byok_encryption_key.startswith("change_me"):
            problems.append("BYOK_ENCRYPTION_KEY doit être configurée (openssl rand -base64 32)")
        if problems:
            raise RuntimeError("Configuration de production invalide:\n- " + "\n- ".join(problems))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
settings.validate_production()
