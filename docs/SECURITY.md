# Revizio — Rapport de sécurité

> Audit de consolidation et durcissement. Date : 2026-11-11.
> Périmètre : code backend (FastAPI), fronts (React), dépendances, configuration, conteneurs.
> Méthodologie : revue de code sécurisée, SCA (pip-audit / pnpm audit), SAST léger, revue de config.

---

## 1. Résumé exécutif

L'audit a identifié **5 catégories de faiblesses**, dont une vulnérabilité **critique** (jspdf LFI)
et deux **hautes** (python-jose forge HS256, upload DoS). Toutes ont été corrigées.

| Sévérité | Avant | Après |
|---|---|---|
| Critique | 2 (jspdf LFI, jspdf ReDoS) | **0** |
| Haute | 10 (jspdf, dompurify, vite, python-jose) | **0** |
| Moyenne | 24 | 2 (react-router, non exploitable ici) |
| Basse | 6 | 0 |

**Dépendances Python** : 3 CVE → **0** (migration python-jose → PyJWT).
**Dépendances JS** : 42 vulns → **2 moderate** (dev-only / non exploitables).

---

## 2. Périmètre et exclusions

**Testé :**
- `services/api/app/**` (auth, courses, BYOK, admin, WS, workers, crypto, middleware)
- `apps/web/src/**`, `apps/desktop/src/**` (client API, navigation, PDF)
- `services/api/pyproject.toml`, `apps/*/package.json` (dépendances)
- `infra/docker-compose.yml`, `services/api/Dockerfile`, `apps/web/Dockerfile`, `nginx.conf`
- Configuration (CORS, headers, secrets, rate-limit)

**Exclusions :**
- Tests d'intrusion réseau actifs (hors périmètre, pas de cible déployée)
- Audit du binaire Tauri compilé (code Rust revu statiquement)
- Fournisseurs IA externes (OpenAI/Anthropic/Deepgram — hors périmètre)

---

## 3. Observations et corrections

### 3.1 [CRITIQUE] jspdf — Local File Inclusion / Path Traversal
- **Constat** : `jspdf@2.5.2` vulnérable (CVE LFI + ReDoS), utilisé pour l'export PDF.
- **Impact** : inclusion de fichiers locaux / DoS via regex.
- **Correction** : upgrade `jspdf@4.2.1` (web + desktop). Vérifié : builds OK.
- **Statut** : ✅ Corrigé.

### 3.2 [HAUTE] python-jose — forge de tokens HS256
- **Constat** : `python-jose@3.5.0` (PYSEC-2026-4298) accepte des clés publiques DER
  pour forger des tokens HS256. Dépend aussi de `ecdsa` (Minerva timing attack).
- **Impact** : contournement d'authentification si l'algorithme n'est pas restreint.
- **Correction** : migration vers **PyJWT 2.15.1**, algorithme fixé à HS256 au décodage,
  `options={"require": ["exp","sub"]}`. `ecdsa` supprimé.
- **Statut** : ✅ Corrigé. pip-audit : 0 vulnérabilité.

### 3.3 [HAUTE] Upload audio sans limite — DoS mémoire
- **Constat** : `await file.read()` chargeait tout le fichier en mémoire, sans limite de taille
  ni validation de type MIME.
- **Impact** : un fichier de plusieurs Go provoque un OOM / crash serveur.
- **Correction** :
  - Lecture bornée `file.read(max_bytes + 1)` + rejet 413 si dépassement.
  - Whitelist MIME (`audio/webm`, `audio/wav`, `audio/mpeg`, `audio/ogg`, `audio/mp4`, `audio/flac`).
  - Limite configurable `MAX_UPLOAD_BYTES` (défaut 200 Mo).
- **Statut** : ✅ Corrigé. 3 tests de sécurité ajoutés (415, 400, 413).

### 3.4 [MOYENNE] CORS trop permissif
- **Constat** : `allow_methods=["*"]`, `allow_headers=["*"]`.
- **Correction** : méthodes explicites (`GET, POST, PATCH, DELETE, OPTIONS`),
  headers explicites (`Authorization, Content-Type`).
- **Statut** : ✅ Corrigé.

### 3.5 [MOYENNE] react-router — open redirect (accepté)
- **Constat** : `react-router@6.x` (CVE open redirect via backslash dans `<Link>`).
- **Analyse d'exploitabilité** : les seules navigations dynamiques sont des items de nav
  statiques (`to={to}`) et `navigate(\`/courses/${course.id}\`)` où `course.id` est un UUID
  serveur. **Aucune cible de navigation contrôlée par l'utilisateur** → non exploitable.
- **Décision** : risque accepté. Le correctif exige react-router 7.x (breaking change majeur)
  pour un risque nul dans ce contexte. À réévaluer lors d'une migration de routing.
- **Statut** : ⚠️ Accepté (documenté).

---

## 4. Contrôles déjà en place (vérifiés)

| Contrôle | Statut |
|---|---|
| Secrets non commités (.env ignoré, .env.example placeholders) | ✅ |
| Garde-fou secrets de production (`validate_production`) | ✅ |
| Headers de sécurité (nosniff, DENY frame, referrer-policy, permissions-policy) | ✅ |
| Rate-limiting (120/min API, 20/min auth) | ✅ |
| Clés BYOK chiffrées AES-256-GCM au repos | ✅ |
| JWT algorithme restreint (HS256) + exp/sub requis | ✅ |
| Isolation des ressources par `user_id` (pas d'IDOR) | ✅ |
| RBAC admin (403 si non-admin) | ✅ |
| Conteneurs non-root | ✅ |
| Docs OpenAPI désactivées en production | ✅ |
| Validation MIME + taille upload | ✅ (nouveau) |

---

## 5. Automatisation

- **`scripts/security-scan.sh`** : scan local (secrets, pip-audit, pnpm audit, SAST léger,
  vérification config prod). Code de sortie non-nul si échec.
- **CI** : job `security` exécute le script à chaque push/PR.
- **`make security`** : raccourci local.
- **`scripts/generate-sbom.sh`** : génère les SBOM CycloneDX (Python + JS) dans `sbom/`.
- **CI** : job `sbom` génère et publie les SBOM en artefacts à chaque push/PR.
- **`make sbom`** : raccourci local.

### Rate-limit distribué (Redis)

Le rate-limit utilise une **fenêtre glissante atomique** implémentée en Lua côté Redis
(`ZREMRANGEBYSCORE` + `ZCARD` + `ZADD`), compatible multi-instance. Si Redis est
indisponible, le middleware bascule automatiquement sur un store in-memory (mono-instance)
pour ne jamais bloquer le service. Activation via `RATE_LIMIT_USE_REDIS` (défaut `true`).

### SBOM (Software Bill of Materials)

Deux SBOM CycloneDX sont générés :
- `sbom/revizio-api.cdx.json` — dépendances Python (cyclonedx-py, ~114 composants)
- `sbom/revizio-web.cdx.json` — dépendances JS (cdxgen pnpm, ~289 composants)

Ils servent à la traçabilité de la chaîne d'approvisionnement et à l'analyse de vulnérabilités
en aval (ex. Dependency-Track, Grype).

### CSP stricte

- **Fonts self-hostées** via `@fontsource` (Inter, Space Grotesk, JetBrains Mono) — plus aucune
  dépendance à Google Fonts. 35 fichiers woff2 bundlés localement.
- **CSP stricte** (nginx + Tauri) : `default-src 'self'`, `script-src 'self'`,
  `object-src 'none'`, `frame-ancestors 'none'`, `base-uri 'self'`, `form-action 'self'`.
  Seul `style-src` autorise `'unsafe-inline'` (styles inline React/Tailwind).

### Journal d'audit immuable

- Table `audit_logs` **append-only** avec **chaîne de hachage** SHA-256 :
  `entry_hash = SHA256(prev_hash || seq || actor || action || target || metadata || ts)`.
- Toute altération/suppression d'une entrée casse la chaîne, détectable via
  `GET /api/admin/audit/verify` (retourne `ok` + `broken_at_seq`).
- Événements journalisés : `user.register`, `user.login`, `byok.create`, `byok.rotate`,
  `byok.delete`, `admin.user.update`.
- Consultation admin : `GET /api/admin/audit`.

### Rotation des clés BYOK

- **Rotation côté utilisateur** : `POST /api/api-keys/{id}/rotate` remplace la valeur d'une
  clé existante (re-chiffrement AES-256-GCM), avec vérification du provider.
- **Rotation de la clé maître** : `scripts/rekey_byok.py` re-chiffre toutes les clés stockées
  d'une ancienne clé maître vers une nouvelle (transaction unique, `--dry-run` disponible).
- UI : bouton de rotation par clé dans les réglages.

### Migration react-router 7.x

- Passage de react-router-dom 6.x → 7.18.5 (corrige la CVE open redirect).
- API déclarative inchangée (BrowserRouter/Routes/Route/Link/NavLink/useNavigate/useParams).
- **pnpm audit : 0 vulnérabilité** (toutes sévérités).

### 2FA admin TOTP (facultatif, opt-in)

- Enrôlement : `POST /api/2fa/setup` (secret + URI otpauth), `POST /api/2fa/enable` (confirme
  avec un code, retourne 8 backup codes à usage unique).
- Login : si 2FA activée, `/api/auth/login` renvoie un `mfa_token` court (5 min) au lieu des
  tokens ; `POST /api/2fa/verify` (code TOTP ou backup code) émet les tokens finaux.
- Secret TOTP chiffré AES-256-GCM au repos ; backup codes hachés bcrypt.
- Désactivation : `POST /api/2fa/disable` (code TOTP ou backup code requis).
- UI : section dédiée dans les réglages (secret, activation, backup codes, désactivation).

### Tests de charge (k6)

- `load/load-test.js` : scénarios health, auth (register+login), courses (CRUD), rate-limit.
- Thresholds : p95 < 2s (réaliste car bcrypt CPU-bound), taux d'erreur < 5%.
- **A révélé et fait corriger une race condition** sur `audit_logs.seq` (max()+1 concurrent →
  séquence PostgreSQL atomique `nextval` + `SELECT ... FOR UPDATE`).
- Résultat mesuré : 100% checks, 0% erreurs, p95 ≈ 1.5s (bcrypt-bound).
- `make load` / `k6 run load/load-test.js`.

### Signature d'artefacts (cosign keyless)

- CI : build des images Docker, push vers GHCR (sur `main`), signature **keyless** via OIDC
  GitHub Actions (`cosign sign --yes`). Aucune clé privée à gérer.
- Vérification : `scripts/verify-image.sh <image>` (contrôle identité OIDC + issuer).
- `make verify-image IMAGE=...`.
- Traçabilité supply-chain de bout en bout (SBOM + signature).

---

## 6. Recommandations futures

**Livrées :**
1. ✅ Rate-limit distribué Redis (fenêtre glissante atomique Lua).
2. ✅ CSP stricte (fonts self-hostées, headers nginx + Tauri).
3. ✅ Rotation des clés BYOK (endpoint + re-keying master key).
4. ✅ Audit log immuable (chaîne de hachage SHA-256).
5. ✅ Migration react-router 7.x (0 vulnérabilité JS).
6. ✅ SBOM CycloneDX (Python + JS).

7. ✅ 2FA TOTP (facultatif, opt-in).
8. ✅ Tests de charge k6 (a révélé + corrigé une race condition audit).
9. ✅ Signature d'artefacts cosign keyless (CI + vérification).

**Restantes (nice-to-have) :**
10. **Signature des binaires Tauri** (au-delà des images Docker).
11. **Tests de charge prolongés** (soak test 1h+) et tuning pool DB.
12. **WAF / protection DDoS** en amont (Cloudflare, etc.).

---

## 7. Conclusion

Le projet est **consolidé et durci**. Les vulnérabilités critiques et hautes sont éliminées.
Les 2 vulnérabilités modérées restantes sont soit dev-only (esbuild/vite transitive), soit
non exploitables dans le contexte applicatif (react-router). Le scan de sécurité automatisé
passe au vert et est intégré à la CI.
