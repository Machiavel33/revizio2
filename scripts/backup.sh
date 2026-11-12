#!/usr/bin/env bash
# Revizio — sauvegarde production (PostgreSQL + audio).
# Usage: ./backup.sh [backup_dir]
# Cron recommandé: 0 3 * * * /var/www/revizio/scripts/backup.sh
set -euo pipefail

BACKUP_DIR="${1:-/var/backups/revizio}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
STAMP="$(date -u +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "[$(date -u +%FT%TZ)] Backup Revizio -> $BACKUP_DIR"

# 1. PostgreSQL (dump compressé)
docker exec revizio-postgres pg_dump -U revizio -d revizio --format=custom \
  > "$BACKUP_DIR/db_${STAMP}.dump"
echo "  DB: db_${STAMP}.dump ($(du -h "$BACKUP_DIR/db_${STAMP}.dump" | cut -f1))"

# 2. Audio (volume Docker)
docker run --rm -v revizio_audio_data:/data:ro -v "$BACKUP_DIR":/backup alpine \
  tar czf "/backup/audio_${STAMP}.tar.gz" -C /data . 2>/dev/null || true
echo "  Audio: audio_${STAMP}.tar.gz"

# 3. Rotation (supprime les backups > RETENTION_DAYS)
find "$BACKUP_DIR" -name 'db_*.dump' -mtime +"$RETENTION_DAYS" -delete
find "$BACKUP_DIR" -name 'audio_*.tar.gz' -mtime +"$RETENTION_DAYS" -delete

echo "[$(date -u +%FT%TZ)] Backup terminé (rétention ${RETENTION_DAYS}j)"
