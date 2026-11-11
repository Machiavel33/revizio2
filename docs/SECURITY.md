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

---

## 6. Recommandations futures (hors périmètre actuel)

1. **Rate-limit distribué** : remplacer le store in-memory par Redis (multi-instance).
2. **2FA admin** : TOTP pour les comptes administrateurs.
3. **CSP stricte** côté web (actuellement permissive pour les fonts Google).
4. **Rotation des clés BYOK** : endpoint de re-chiffrement.
5. **Audit log immuable** : journalisation append-only des actions admin.
6. **Migration react-router 7.x** lors d'un refactor de routing.
7. **SBOM** : génération (CycloneDX) pour la chaîne d'approvisionnement.
8. **Tests de charge** : valider les limites de rate-limit et d'upload sous charge réelle.

---

## 7. Conclusion

Le projet est **consolidé et durci**. Les vulnérabilités critiques et hautes sont éliminées.
Les 2 vulnérabilités modérées restantes sont soit dev-only (esbuild/vite transitive), soit
non exploitables dans le contexte applicatif (react-router). Le scan de sécurité automatisé
passe au vert et est intégré à la CI.
