#!/usr/bin/env bash
# Revizio — vérification de signature d'image (cosign keyless).
#
# Usage:
#   ./scripts/verify-image.sh ghcr.io/<owner>/<repo>-api:<tag>
#
# Vérifie la signature Sigstore keyless (OIDC GitHub Actions) de l'image.
# Prérequis: cosign installé (https://docs.sigstore.dev/cosign/installation/).
set -euo pipefail

IMAGE="${1:-}"
if [ -z "$IMAGE" ]; then
  echo "Usage: $0 <image-ref>"
  echo "Ex:    $0 ghcr.io/owner/revizio-api:abc123"
  exit 1
fi

if ! command -v cosign >/dev/null 2>&1; then
  echo "cosign non installé. Voir https://docs.sigstore.dev/cosign/installation/"
  exit 1
fi

# Identité attendue : le workflow GitHub Actions du repo
IDENTITY_REGEX="${COSIGN_IDENTITY_REGEX:-https://github.com/.+/.github/workflows/ci.yml@refs/heads/main}"
OIDC_ISSUER="${COSIGN_OIDC_ISSUER:-https://token.actions.githubusercontent.com}"

echo "=== Vérification de $IMAGE ==="
cosign verify "$IMAGE" \
  --certificate-identity-regexp "$IDENTITY_REGEX" \
  --certificate-oidc-issuer "$OIDC_ISSUER"

echo "✓ Signature valide"
