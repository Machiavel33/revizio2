"""Agrégation des routes API."""

from fastapi import APIRouter

from app.api.routes import (
    admin,
    api_keys,
    auth,
    courses,
    downloads,
    revision,
    stripe_webhook,
    totp,
    ws_transcribe,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(totp.router)
api_router.include_router(api_keys.router)
api_router.include_router(courses.router)
api_router.include_router(revision.router)
api_router.include_router(admin.router)
api_router.include_router(downloads.router)
api_router.include_router(stripe_webhook.router)
api_router.include_router(ws_transcribe.router)
