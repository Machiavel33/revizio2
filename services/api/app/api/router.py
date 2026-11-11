"""Agrégation des routes API."""

from fastapi import APIRouter

from app.api.routes import api_keys, auth, courses, ws_transcribe

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(api_keys.router)
api_router.include_router(courses.router)
api_router.include_router(ws_transcribe.router)
