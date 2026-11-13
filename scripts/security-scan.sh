#!/usr/bin/env bash
# Revizio — scan de sécurité local (secrets, SCA, SAST léger).
# Usage: ./scripts/security-scan.sh
# Sortie: rapport lisible + code de sortie non-nul si problème critique.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

FAIL=0
section() { printf "\n\033[1;36m=== %s ===\033[0m\n" "$1"; }
ok()      { printf "\033[1;32m[OK]\033[0m %s\n" "$1"; }
warn()    { printf "\033[1;33m[WARN]\033[0m %s\n" "$1"; }
fail()    { printf "\033[1;31m[FAIL]\033[0m %s\n" "$1"; FAIL=1; }

# ---------------------------------------------------------------
section "1. Secrets commités"
# Fichiers sensibles suivis par git
if git ls-files | grep -qE '(^|/)\.env$|\.pem$|\.key$|id_rsa'; then
  fail "Fichiers sensibles suivis par git"
  git ls-files | grep -E '(^|/)\.env$|\.pem$|\.key$|id_rsa'
else
  ok "Aucun fichier sensible suivi"
fi

# Motifs de secrets dans les fichiers suivis (hors exemples/tests/docs)
SECRET_HITS=$(git grep -nE '(sk-[a-zA-Z0-9]{30,}|sk-ant-[a-zA-Z0-9]{30,}|AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----)' \
  -- ':!*.md' ':!*.example' ':!*test*' 2>/dev/null || true)
if [ -n "$SECRET_HITS" ]; then
  fail "Secrets potentiels détectés"
  echo "$SECRET_HITS"
else
  ok "Aucun secret en dur détecté"
fi

# ---------------------------------------------------------------
section "2. Dépendances Python (pip-audit)"
if [ -x services/api/.venv/bin/pip-audit ]; then
  # Le paquet local revizio-api n'est pas sur PyPI : on ignore ce skip.
  (cd services/api && PIPAPI_PYTHON_LOCATION="$PWD/.venv/bin/python" \
    .venv/bin/pip-audit 2>&1 | tee /tmp/pipaudit.log | tail -20)
  if grep -q "No known vulnerabilities" /tmp/pipaudit.log; then
    ok "pip-audit: aucune vulnérabilité"
  else
    fail "pip-audit: vulnérabilités détectées (voir ci-dessus)"
  fi
else
  warn "pip-audit non installé (pip install pip-audit dans services/api/.venv)"
fi

# ---------------------------------------------------------------
section "3. Dépendances JS (pnpm audit)"
if command -v pnpm >/dev/null 2>&1; then
  AUDIT_JSON=$(pnpm audit --json 2>/dev/null || echo '{}')
  CRIT=$(echo "$AUDIT_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(sum(1 for a in d.get('advisories',{}).values() if a.get('severity')=='critical'))" 2>/dev/null || echo 0)
  HIGH=$(echo "$AUDIT_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(sum(1 for a in d.get('advisories',{}).values() if a.get('severity')=='high'))" 2>/dev/null || echo 0)
  if [ "${CRIT:-0}" -gt 0 ] || [ "${HIGH:-0}" -gt 0 ]; then
    fail "pnpm audit: ${CRIT} critical, ${HIGH} high"
  else
    ok "pnpm audit: aucune vulnérabilité critique/haute"
  fi
else
  warn "pnpm non disponible"
fi

# ---------------------------------------------------------------
section "4. SAST léger (motifs dangereux)"
# eval/exec, subprocess shell=True, pickle.loads, yaml.load non-safe
DANGER=$(git grep -nE '\b(eval|exec)\(|subprocess\.[a-z]+\([^)]*shell\s*=\s*True|pickle\.loads|yaml\.load\([^,)]*\)' \
  -- 'services/api/app/**/*.py' 2>/dev/null || true)
if [ -n "$DANGER" ]; then
  warn "Motifs à vérifier manuellement:"
  echo "$DANGER"
else
  ok "Aucun motif dangereux évident (eval/exec/shell=True/pickle/yaml.load)"
fi

# ---------------------------------------------------------------
section "5. Configuration production"
if grep -q "validate_production" services/api/app/core/config.py; then
  ok "Garde-fou secrets de production présent"
else
  fail "Garde-fou secrets de production manquant"
fi
if grep -q "SecurityHeadersMiddleware" services/api/app/main.py; then
  ok "Middleware headers de sécurité actif"
else
  fail "Middleware headers de sécurité manquant"
fi
if grep -q "RateLimitMiddleware" services/api/app/main.py; then
  ok "Rate-limiting actif"
else
  fail "Rate-limiting manquant"
fi

# --- Service STT (découplé) ---
if [ -f services/stt/app/main.py ]; then
  if grep -q "SecurityHeadersMiddleware" services/stt/app/main.py; then
    ok "STT: en-têtes de sécurité actifs"
  else
    fail "STT: en-têtes de sécurité manquants"
  fi
  if grep -q "SharedSecretMiddleware" services/stt/app/main.py; then
    ok "STT: authentification par secret partagé"
  else
    fail "STT: secret partagé manquant"
  fi
fi

# ---------------------------------------------------------------
printf "\n"
if [ "$FAIL" -eq 0 ]; then
  printf "\033[1;32m✓ Scan de sécurité: OK\033[0m\n"
  exit 0
else
  printf "\033[1;31m✗ Scan de sécurité: échec (voir ci-dessus)\033[0m\n"
  exit 1
fi
