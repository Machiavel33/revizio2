"""Schémas Pydantic — BYOK (clés API utilisateur)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Provider = Literal["openai", "anthropic", "deepgram"]


class ApiKeyCreate(BaseModel):
    provider: Provider
    api_key: str = Field(min_length=8, max_length=512)
    is_default: bool = False


class ApiKeyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    provider: str
    key_hint: str
    is_default: bool
    created_at: datetime
