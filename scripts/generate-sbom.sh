#!/usr/bin/env bash
# Revizio — génération des SBOM (CycloneDX) pour Python et JS.
# Usage: ./scripts/generate-sbom.sh
# Sortie: sbom/revizio-api.cdx.json, sbom/revizio-web.cdx.json
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
OUT="$ROOT/sbom"
mkdir -p "$OUT"

echo "=== SBOM Python (backend) ==="
if [ -x services/api/.venv/bin/cyclonedx-py ]; then
  (cd services/api && .venv/bin/cyclonedx-py environment --of JSON -o "$OUT/revizio-api.cdx.json")
  echo "  -> sbom/revizio-api.cdx.json"
else
  echo "  [SKIP] cyclonedx-py absent (pip install cyclonedx-bom dans services/api/.venv)"
fi

echo "=== SBOM JS (workspace pnpm) ==="
if command -v npx >/dev/null 2>&1; then
  npx --yes @cyclonedx/cdxgen -t pnpm -o "$OUT/revizio-web.cdx.json" . >/dev/null 2>&1
  echo "  -> sbom/revizio-web.cdx.json"
else
  echo "  [SKIP] npx absent"
fi

echo "=== Résumé ==="
for f in "$OUT"/*.cdx.json; do
  [ -f "$f" ] || continue
  python3 - "$f" <<'PY'
import json, sys
p = sys.argv[1]
d = json.load(open(p))
print(f"  {p.split('/')[-1]}: {len(d.get('components', []))} composants (CycloneDX {d.get('specVersion')})")
PY
done
