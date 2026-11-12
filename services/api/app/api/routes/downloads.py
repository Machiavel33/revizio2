"""Routes de téléchargement de l'app desktop (publiques)."""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.services import downloads

router = APIRouter(prefix="/downloads", tags=["downloads"])


@router.get("")
async def list_downloads() -> list[dict]:
    """Liste les installeurs disponibles (public, pas d'auth requise)."""
    return downloads.list_downloads()


@router.get("/{filename}")
async def download_file(filename: str) -> FileResponse:
    path = downloads.download_path(filename)
    if path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fichier introuvable")
    return FileResponse(
        path,
        filename=filename,
        media_type="application/octet-stream",
    )
