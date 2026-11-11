# Revizio

> Enregistrement de cours, transcription live et génération automatique de fiches de révision.

Application desktop (Tauri 2) pour capturer et transcrire un cours en temps réel, backend FastAPI pour la génération de fiches via LLM (BYOK), et front web React (étudiant + admin).

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — architecture technique et roadmap
- [`docs/DESIGN_SYSTEM.md`](docs/DESIGN_SYSTEM.md) — design system "DarkPunk Pro"

## Structure

```
revizio/
├── apps/
│   ├── desktop/          # Tauri 2 + React (capture audio)
│   └── web/              # React SPA (étudiant + admin)
├── services/
│   └── api/              # FastAPI backend
├── packages/
│   └── shared/
│       └── design-tokens # Tokens partagés desktop ↔ web
├── infra/                # Docker Compose
└── docs/
```

## Démarrage rapide (dev)

```bash
# 1. Infra (postgres, redis, minio)
cd infra && docker compose up -d

# 2. Backend
cd services/api
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload

# 3. Front web
pnpm install
pnpm --filter web dev
```

## Stack

- **Desktop** : Tauri 2, React, Rust (pipeline audio cpal + APM + VAD)
- **Backend** : FastAPI, PostgreSQL, Redis, Celery
- **Front** : React, Vite, Tailwind, shadcn/ui
- **IA** : BYOK (OpenAI / Anthropic / Deepgram), transcription hybride, LLM structured output
