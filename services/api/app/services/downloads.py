"""Service de distribution des binaires de l'app desktop.

Les installeurs sont déposés dans un répertoire (monté en volume) et servis
via l'API. Un fichier `manifest.json` décrit les versions disponibles.
"""

import json
from pathlib import Path

from app.core.config import settings


def _downloads_dir() -> Path:
    root = Path(settings.downloads_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def list_downloads() -> list[dict]:
    """Liste les binaires disponibles (scan du répertoire + manifest optionnel)."""
    root = _downloads_dir()
    manifest_path = root / "manifest.json"
    manifest: dict = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text())
        except Exception:  # noqa: BLE001
            manifest = {}

    items = []
    for f in sorted(root.iterdir()):
        if not f.is_file() or f.name == "manifest.json":
            continue
        meta = manifest.get(f.name, {})
        items.append(
            {
                "filename": f.name,
                "size": f.stat().st_size,
                "os": meta.get("os", _guess_os(f.name)),
                "arch": meta.get("arch", "x86_64"),
                "version": meta.get("version", "0.1.0"),
                "url": f"/api/downloads/{f.name}",
            }
        )
    return items


def _guess_os(filename: str) -> str:
    name = filename.lower()
    if name.endswith((".deb", ".appimage", ".rpm")):
        return "linux"
    if name.endswith((".msi", ".exe")):
        return "windows"
    if name.endswith((".dmg", ".app")):
        return "macos"
    return "unknown"


def download_path(filename: str) -> Path | None:
    """Retourne le chemin d'un binaire si valide (protection path traversal)."""
    root = _downloads_dir().resolve()
    target = (root / filename).resolve()
    # Empêche toute évasion hors du répertoire downloads
    if root not in target.parents and target != root:
        return None
    if not target.is_file():
        return None
    return target
