# Coursify — Architecture & Plan de Développement

> Application d'enregistrement de cours, transcription live, et génération automatique de fiches de révision.
> Document d'architecture technique — V1 (MVP complet).

---

## 1. Vision produit

Un étudiant lance l'app desktop, appuie sur "Enregistrer", assiste à son cours. En temps réel :
- l'audio est capté via le micro du PC,
- le discours est transcrit (résistant au bruit de salle),
- à la fin, une **fiche de révision structurée** est générée automatiquement (résumé, notions clés, définitions, questions de révision).

Côté web : un **front étudiant** (consultation des cours, fiches, historique) et un **backend admin** (gestion utilisateurs, quotas, supervision, modération).

---

## 2. Décisions techniques (et le POURQUOI)

### 2.1 Stack desktop → **Tauri 2 + React + TypeScript**

| Critère | Electron | **Tauri 2** | Python/PyQt |
|---|---|---|---|
| Taille bundle | ~150 Mo | **~10 Mo** | ~80 Mo |
| Perf / RAM | lourd | **léger** | moyen |
| Accès micro natif | oui | **oui (plugin)** | oui |
| Packaging Win/Mac/Linux | oui | **oui (natif)** | fragile |
| Sécurité (sandbox) | faible | **forte** | faible |

**Choix : Tauri 2.** Le backend Rust gère la capture audio bas niveau (cpal), le buffering, l'encodage (opus), et l'envoi streaming. Le front React gère l'UI. On garde Electron en plan B si l'équipe n'est pas à l'aise avec Rust — mais Tauri est objectivement supérieur ici.

### 2.2 Capture & traitement audio → **Rust (cpal) + WebRTC APM**

Le problème n°1 que tu as identifié : **le bruit de salle**. On ne fait pas du `getUserMedia` naïf. Pipeline :

```
Micro → cpal (capture PCM) → WebRTC Audio Processing Module (APM)
        ├── Noise Suppression (RNNoise / WebRTC NS)
        ├── Acoustic Echo Cancellation (AEC)
        ├── Automatic Gain Control (AGC)
        └── Voice Activity Detection (VAD — Silero)
     → resampling 16 kHz mono → Opus encode → chunks 20-100ms
```

- **RNNoise** (ou WebRTC NS) : suppression de bruit de fond (chuchotements, clim, brouhaha diffus).
- **VAD Silero** : détecte les segments de parole → on n'envoie à l'IA que ce qui est parlé (économie + précision).
- **AGC** : normalise le volume (prof qui parle loin du micro).
- **AEC** : si le son sort des haut-parleurs (vidéo projetée), évite le feedback.

C'est **le** point différenciant. Un simple `MediaRecorder` ne suffira pas en amphi.

### 2.3 Transcription → **Hybride, BYOK (Bring Your Own Key)**

L'étudiant connecte **son** compte OpenAI / Anthropic / Deepgram. Pas de coût serveur pour toi, pas de clé partagée à gérer.

**Deux modes :**

1. **Streaming temps réel** (transcription live) :
   - OpenAI Realtime API (`gpt-4o-transcribe` / `whisper-1` streaming) — ou Deepgram Nova (meilleur rapport qualité/latence/prix pour le live).
   - Chunks audio → WebSocket → texte incrémental affiché.

2. **Batch post-cours** (transcription finale de qualité) :
   - Whisper large-v3 via API, ou faster-whisper **local** en option (offline, gratuit).
   - Meilleure précision que le live → sert de base à la fiche.

**Architecture BYOK sécurisée :**
- La clé API de l'étudiant est **chiffrée au repos** (AES-256-GCM, clé dérivée par utilisateur) côté backend.
- Les appels IA peuvent être **proxifiés par le backend** (la clé ne transite jamais en clair côté client après saisie) OU faits **en local depuis le desktop** (la clé reste sur la machine). → On choisit **proxy backend** pour permettre l'usage web + desktop avec la même clé, avec chiffrement fort.

### 2.4 Génération de fiche → **LLM structuré (JSON schema)**

À partir de la transcription finale :
- Prompt système spécialisé "prof agrégé qui fait des fiches de révision".
- Sortie **JSON structuré** (function calling / structured outputs) :
  ```json
  {
    "title": "...",
    "summary": "...",
    "key_concepts": [{"term": "...", "definition": "..."}],
    "sections": [{"heading": "...", "points": ["..."]}],
    "flashcards": [{"question": "...", "answer": "..."}],
    "review_questions": ["..."],
    "estimated_review_time_min": 15
  }
  ```
- Modèle : Claude (Sonnet) ou GPT-4o selon la clé de l'étudiant. Fallback configurable.

### 2.5 Backend → **Python FastAPI + PostgreSQL + Redis + Celery**

| Composant | Choix | Pourquoi |
|---|---|---|
| API | **FastAPI** | async, rapide, OpenAPI auto, écosystème IA Python |
| DB | **PostgreSQL 16** | relationnel solide, JSONB pour les fiches, pgvector pour recherche sémantique future |
| Cache/Queue | **Redis** | sessions, rate-limit, broker Celery |
| Jobs async | **Celery** | transcription batch, génération de fiche, envoi d'emails |
| Auth | **JWT + refresh** (ou OAuth Google/Apple) | standard, multi-plateforme |
| Stockage fichiers | **S3-compatible (MinIO en dev)** | audio brut, exports PDF |
| Chiffrement clés | **cryptography (AES-GCM)** | BYOK sécurisé |

### 2.6 Front web → **React + Vite + TypeScript + Tailwind + shadcn/ui**

- **Front étudiant** : dashboard cours, lecteur de fiche, flashcards, export PDF, historique, gestion clé API.
- **Backend admin** : gestion users, quotas, supervision jobs, logs, modération, stats.
- Même codebase, routes séparées (`/app` vs `/admin`), RBAC.

**Direction artistique : "DarkPunk Pro"** — sombre profond, accents néon maîtrisés (cyan/violet), typo géométrique (Space Grotesk / Inter / JetBrains Mono), glassmorphism discret, micro-animations. Le design system complet (palette, typo, composants, tokens Tailwind, animations, accessibilité) est défini dans `docs/DESIGN_SYSTEM.md`. Les tokens sont partagés desktop ↔ web via `packages/shared/design-tokens`.

### 2.7 Infra → **Docker Compose (dev) → Kubernetes-ready (prod)**

- `docker-compose.yml` : api, worker, postgres, redis, minio, front.
- CI/CD GitHub Actions : lint, tests, build, images Docker.

---

## 3. Architecture globale

```
┌─────────────────────────────────────────────────────────────────┐
│                        DESKTOP (Tauri 2)                          │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────────────┐    │
│  │ React UI     │◄─►│ Rust Core    │──►│ Audio Pipeline     │    │
│  │ (enregistr., │   │ (commands,   │   │ cpal→APM→VAD→Opus  │    │
│  │  live text)  │   │  state)      │   │                    │    │
│  └──────────────┘   └──────┬───────┘   └─────────┬──────────┘    │
└────────────────────────────┼─────────────────────┼───────────────┘
                             │ HTTPS/WSS            │ audio chunks
                             ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                     BACKEND (FastAPI)                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ Auth/JWT │  │ Courses  │  │ Transcr. │  │ Fiche Generator  │  │
│  │ + BYOK   │  │ API      │  │ Proxy WS │  │ (LLM structured) │  │
│  └──────────┘  └──────────┘  └────┬─────┘  └────────┬─────────┘  │
│                                    │                 │            │
│  ┌─────────────────────────────────▼─────────────────▼─────────┐ │
│  │              Celery Workers (batch jobs)                     │ │
│  └──────────────────────────────────────────────────────────────┘ │
└───────┬───────────────┬───────────────┬───────────────┬──────────┘
        ▼               ▼               ▼               ▼
   ┌─────────┐    ┌──────────┐    ┌─────────┐    ┌──────────┐
   │Postgres │    │  Redis   │    │  MinIO  │    │ LLM APIs │
   │+pgvector│    │cache/queue│   │  (S3)   │    │(BYOK)    │
   └─────────┘    └──────────┘    └─────────┘    └──────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    WEB (React SPA)                                │
│   /app  → Front étudiant      /admin → Backend admin             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Modèle de données (PostgreSQL)

```sql
-- Utilisateurs
users (
  id UUID PK,
  email CITEXT UNIQUE,
  password_hash TEXT,          -- null si OAuth
  display_name TEXT,
  role TEXT DEFAULT 'student', -- student | admin
  oauth_provider TEXT,         -- google | apple | null
  oauth_sub TEXT,
  created_at TIMESTAMPTZ,
  is_active BOOLEAN DEFAULT true
)

-- Clés API BYOK (chiffrées)
user_api_keys (
  id UUID PK,
  user_id UUID FK→users,
  provider TEXT,               -- openai | anthropic | deepgram
  encrypted_key BYTEA,         -- AES-256-GCM
  key_nonce BYTEA,
  key_tag BYTEA,
  is_default BOOLEAN,
  created_at TIMESTAMPTZ,
  UNIQUE(user_id, provider)
)

-- Cours (session d'enregistrement)
courses (
  id UUID PK,
  user_id UUID FK→users,
  title TEXT,
  subject TEXT,
  language TEXT DEFAULT 'fr',
  status TEXT,                 -- recording | transcribing | generating | ready | failed
  audio_url TEXT,              -- MinIO/S3
  duration_sec INT,
  created_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ
)

-- Transcription (segments horodatés)
transcripts (
  id UUID PK,
  course_id UUID FK→courses,
  full_text TEXT,
  segments JSONB,              -- [{start, end, text, speaker?}]
  provider TEXT,
  model TEXT,
  created_at TIMESTAMPTZ
)

-- Fiche de révision
study_sheets (
  id UUID PK,
  course_id UUID FK→courses,
  content JSONB,               -- structure JSON (summary, concepts, flashcards...)
  model TEXT,
  version INT DEFAULT 1,
  created_at TIMESTAMPTZ
)

-- Flashcards (extraction pour révision espacée future)
flashcards (
  id UUID PK,
  study_sheet_id UUID FK→study_sheets,
  question TEXT,
  answer TEXT,
  next_review_at TIMESTAMPTZ,
  ease_factor REAL DEFAULT 2.5,
  interval_days INT DEFAULT 0
)

-- Jobs (suivi async)
jobs (
  id UUID PK,
  course_id UUID FK→courses,
  type TEXT,                   -- transcribe | generate_sheet
  status TEXT,                 -- queued | running | done | failed
  error TEXT,
  created_at TIMESTAMPTZ,
  finished_at TIMESTAMPTZ
)

-- Quotas / usage
usage_logs (
  id UUID PK,
  user_id UUID FK→users,
  action TEXT,                 -- transcribe_min | sheet_gen
  amount NUMERIC,
  metadata JSONB,
  created_at TIMESTAMPTZ
)
```

---

## 5. Flux principal (happy path)

1. **Desktop** : étudiant clique "Enregistrer" → Rust démarre capture + APM + VAD.
2. Chunks audio (parole uniquement) → WebSocket vers backend `/ws/transcribe`.
3. Backend proxifie vers l'API de transcription (clé BYOK déchiffrée) → renvoie texte incrémental → affiché live dans le desktop.
4. Audio complet sauvegardé en local puis uploadé en S3 (MinIO) à la fin.
5. Fin d'enregistrement → création `course` + job `transcribe` (batch, qualité max) → job `generate_sheet`.
6. Celery worker : transcription finale → génération fiche JSON → stockage `study_sheets` + `flashcards`.
7. Desktop/web notifié (WebSocket ou polling) → fiche affichée, exportable PDF.
8. Front étudiant : consultation, révision flashcards, historique.

---

## 6. Sécurité & conformité

- **BYOK** : clés chiffrées AES-256-GCM, jamais loggées, jamais renvoyées en clair.
- **RGPD** : audio = donnée personnelle. Consentement explicite à l'enregistrement, suppression à la demande, rétention configurable (ex. audio supprimé après transcription, texte conservé).
- **Auth** : JWT court + refresh token httpOnly, rate-limiting, 2FA admin.
- **Isolation** : chaque requête scoping par `user_id` (pas d'IDOR).
- **Audit** : `usage_logs` + logs admin.

---

## 7. Roadmap de développement (phases)

### Phase 0 — Fondations (semaine 1)
- [ ] Monorepo (pnpm workspaces + Turborepo) : `apps/desktop`, `apps/web`, `services/api`, `packages/shared`.
- [ ] Docker Compose (postgres, redis, minio).
- [ ] CI GitHub Actions (lint, test, build).
- [ ] Schéma DB + migrations (Alembic).
- [ ] **Design tokens partagés** (`packages/shared/design-tokens`) : palette DarkPunk Pro, config Tailwind, variables CSS, fonts.

### Phase 1 — Backend core (semaines 2-3)
- [ ] Auth (register/login/JWT/refresh), RBAC.
- [ ] CRUD courses, upload audio S3.
- [ ] BYOK : endpoints clés API + chiffrement.
- [ ] WebSocket transcription proxy.
- [ ] Celery + jobs transcription batch & génération fiche.

### Phase 2 — Desktop capture (semaines 3-5)
- [ ] Tauri 2 scaffold + React UI.
- [ ] Pipeline audio Rust : cpal → APM (RNNoise/AEC/AGC) → VAD Silero → Opus.
- [ ] Calibration micro (niveau, sélection device, test bruit).
- [ ] Envoi streaming WS + affichage transcription live.
- [ ] Upload final + déclenchement jobs.

### Phase 3 — Génération de fiche (semaine 5-6)
- [ ] Prompt engineering + structured output JSON.
- [ ] Rendu fiche (React) : résumé, concepts, flashcards.
- [ ] Export PDF.

### Phase 4 — Front web étudiant (semaines 6-7)
- [ ] Dashboard, liste cours, lecteur fiche, flashcards.
- [ ] Gestion clé API, profil.

### Phase 5 — Backend admin (semaine 7-8)
- [ ] Gestion users, quotas, supervision jobs, logs, stats.

### Phase 6 — Packaging & polish (semaine 8-9)
- [ ] Build Tauri Win/Mac/Linux (signature, auto-update).
- [ ] Tests E2E, hardening, docs.

---

## 8. Risques & mitigations

| Risque | Impact | Mitigation |
|---|---|---|
| Qualité transcription en amphi bruyant | élevé | APM agressif + VAD + batch Whisper large-v3 en final |
| Coût API BYOK mal compris par étudiant | moyen | UI claire, estimation coût, mode local Whisper gratuit |
| Latence streaming | moyen | Deepgram Nova (faible latence) ou chunks optimisés |
| Packaging Tauri multi-OS | moyen | CI matrix build, tests sur VM |
| RGPD / consentement enregistrement | élevé | bannière consentement, suppression audio post-transcription |
| Dépendance clé étudiante (clé invalide/expirée) | moyen | validation à la saisie, fallback message clair |

---

## 9. Structure du monorepo

```
coursify/
├── apps/
│   ├── desktop/          # Tauri 2 + React
│   │   ├── src/          # React UI
│   │   └── src-tauri/    # Rust core (audio pipeline)
│   └── web/              # React SPA (étudiant + admin)
├── services/
│   └── api/              # FastAPI
│       ├── app/
│       │   ├── api/      # routes
│       │   ├── core/     # config, security, crypto
│       │   ├── models/   # SQLAlchemy
│       │   ├── schemas/  # Pydantic
│       │   ├── services/ # transcription, sheet gen, byok
│       │   └── workers/  # Celery tasks
│       └── alembic/
├── packages/
│   └── shared/           # types TS partagés, schémas JSON
├── infra/
│   ├── docker-compose.yml
│   └── k8s/              # (plus tard)
├── docs/
└── .github/workflows/
```

---

## 10. Prochaine étape

Valider cette architecture, puis attaquer **Phase 0** (scaffold monorepo + Docker + DB) et **Phase 1** (backend auth + courses + BYOK). Le desktop audio (Phase 2) est le morceau le plus technique — on le traite après avoir un backend solide sur lequel s'appuyer.
