#!/usr/bin/env bash
# Revizio — téléchargement et vérification du modèle sherpa-onnx streaming FR.
#
# Télécharge le modèle zipformer français (Apache-2.0), vérifie son SHA-256
# (empreinte épinglée), et l'installe dans le volume stt_models.
# Idempotent : ne re-télécharge pas si déjà présent.
#
# Usage :
#   ./scripts/fetch-sherpa-model.sh [dest_dir]
#   (défaut dest_dir = /var/lib/docker/volumes/revizio_stt_models/_data)
#
# Ou via docker (recommandé, écrit dans le volume nommé) :
#   docker run --rm -v revizio_stt_models:/data/models alpine sh -c '...'
set -euo pipefail

DEST="${1:-/var/lib/docker/volumes/revizio_stt_models/_data}"
BASE="https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models"
FILE="sherpa-onnx-streaming-zipformer-fr-2023-04-14.tar.bz2"
SHA="77d4cbd61dcfa55fd2c14efc0ce5c6798be5931c05f35df5bab60c921950bb8c"
DIR="sherpa-onnx-streaming-zipformer-fr-2023-04-14"

mkdir -p "$DEST"
TARGET="$DEST/$DIR"

if [ -d "$TARGET" ] && [ -f "$TARGET/tokens.txt" ]; then
  echo "déjà présent : $TARGET"
  exit 0
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "Téléchargement de $FILE (~400 Mo)…"
curl -fsSL --retry 3 -o "$TMP/$FILE" "$BASE/$FILE"

echo "Vérification SHA-256…"
echo "$SHA  $TMP/$FILE" | sha256sum -c --quiet - || {
  echo "EMPREINTE INVALIDE pour $FILE : abandon" >&2
  exit 1
}

echo "Extraction vers $DEST…"
tar --no-same-owner -xjf "$TMP/$FILE" -C "$DEST"
chmod -R a+rX "$TARGET"
echo "installé : $TARGET"
