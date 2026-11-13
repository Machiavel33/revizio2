"""Configuration du service STT (Pydantic Settings)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Revizio STT"
    app_env: str = "development"
    debug: bool = False
    api_host: str = "0.0.0.0"
    api_port: int = 8100

    # --- faster-whisper (batch) ---
    whisper_model: str = "small"  # tiny|base|small|medium|large-v3
    whisper_device: str = "cpu"  # cpu|cuda
    whisper_compute_type: str = "int8"  # int8|float16|float32
    whisper_cpu_threads: int = 4
    # Nombre max de transcriptions simultanées (sémaphore).
    whisper_max_concurrency: int = 2
    # Nombre d'instances de modèle (pool). 1 = un modèle partagé borné par sémaphore.
    whisper_pool_size: int = 1

    # --- sherpa-onnx streaming (live) ---
    # Dossier du modèle zipformer FR (téléchargé/vérifié hors ligne).
    sherpa_model_dir: str = "/data/models/sherpa-onnx-streaming-zipformer-fr-2023-04-14"
    sherpa_num_threads: int = 1
    sherpa_int8: bool = True
    # Active le moteur streaming (sinon /stream renvoie 503).
    sherpa_enabled: bool = True

    # --- Sécurité ---
    # Secret partagé avec l'API (X-STT-Token / ?token=). Vide = pas d'auth (dev).
    stt_shared_secret: str = ""

    # --- Limites ---
    max_upload_bytes: int = 200 * 1024 * 1024  # 200 Mo

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
