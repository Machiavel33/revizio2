"""Stockage audio durable sur système de fichiers local (ADR-007, option MVP).

Écriture : fichier ``.part`` unique, ``fsync`` du fichier, ``os.replace`` atomique,
``fsync`` du répertoire. La clé contient le SHA-256 du contenu : deux écritures
concurrentes d'un même fragment avec des contenus différents ne s'écrasent jamais,
et la ligne SQL gagnante désigne sans ambiguïté le bon fichier. Les fichiers perdants
ou écrits avant un COMMIT avorté sont des orphelins : ``sessions.reconcile_session`` les
supprime sous le verrou SQL de la séance, le même que celui de l'insertion.

Les clés sont générées par le serveur ; aucun chemin fourni par le client n'est utilisé.
"""

from __future__ import annotations

import os
import re
import shutil
import uuid
from pathlib import Path

_KEY_RE = re.compile(r"^[0-9a-f-]{36}/\d{10}-[0-9a-f]{64}\.pcm$")


class StorageUnavailable(Exception):
    pass


class AudioStore:
    def __init__(self, root: Path, min_free_bytes: int = 0) -> None:
        self.root = root
        self.min_free_bytes = min_free_bytes
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    @staticmethod
    def key_for(session_id: uuid.UUID, chunk_seq: int, sha256: str) -> str:
        return f"{session_id}/{chunk_seq:010d}-{sha256}.pcm"

    def path_for(self, key: str) -> Path:
        if not _KEY_RE.match(key):
            raise ValueError(f"clé audio invalide : {key!r}")
        return self.root / key

    def free_bytes(self) -> int:
        return shutil.disk_usage(self.root).free

    def write_durable(self, key: str, data: bytes) -> None:
        """Bloquant : à appeler hors de la boucle asyncio."""
        if self.min_free_bytes and self.free_bytes() < self.min_free_bytes + len(data):
            raise StorageUnavailable("espace disque sous la réserve configurée")
        path = self.path_for(key)
        try:
            if self._already_durable(path, data):
                return
            new_dir = not path.parent.exists()
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if new_dir:
                _fsync_dir(self.root)
            tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.part")
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                view = memoryview(data)
                while view:
                    written = os.write(fd, view)
                    view = view[written:]
                os.fsync(fd)
            finally:
                os.close(fd)
            os.replace(tmp, path)
            _fsync_dir(path.parent)
        except OSError as exc:
            raise StorageUnavailable(f"écriture audio impossible : {exc.strerror}") from exc

    def read(self, key: str) -> bytes:
        return self.path_for(key).read_bytes()

    def delete(self, key: str) -> None:
        path = self.path_for(key)
        path.unlink(missing_ok=True)
        _fsync_dir(path.parent)

    def session_files(self, session_id: uuid.UUID) -> list[tuple[str, float]]:
        """Fichiers (``.pcm`` et ``.part``) d'une séance, avec leur date de modification."""
        directory = self.root / str(session_id)
        if not directory.is_dir():
            return []
        return sorted(
            (f"{session_id}/{p.name}", p.stat().st_mtime)
            for p in directory.iterdir()
            if p.is_file()
        )

    def is_intact(self, key: str, size: int) -> bool:
        path = self.path_for(key)
        return path.is_file() and path.stat().st_size == size

    def remove_file(self, rel: str) -> None:
        """Supprime un orphelin ou un ``.part`` ; ``rel`` provient de ``session_files``."""
        path = (self.root / rel).resolve()
        if path.parent.parent != self.root.resolve():
            raise ValueError(f"chemin hors du stockage : {rel!r}")
        path.unlink(missing_ok=True)

    @staticmethod
    def _already_durable(path: Path, data: bytes) -> bool:
        """Rejeu idempotent : même clé (donc même SHA) déjà écrite et intègre."""
        if not path.is_file() or path.stat().st_size != len(data):
            return False
        if path.read_bytes() != data:
            return False
        os.utime(path)  # rajeunit le fichier : le nettoyage ne le prendra pas pour un orphelin
        return True


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
