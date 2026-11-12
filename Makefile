# Revizio — commandes de développement et déploiement
.PHONY: help install infra-up infra-down api worker web desktop test lint build docker-up docker-down security sbom load verify-image

help:
	@echo "Revizio — cibles disponibles:"
	@echo "  make install     Installe les dépendances (JS + Python)"
	@echo "  make infra-up    Démarre postgres/redis/minio (dev)"
	@echo "  make infra-down  Arrête l'infra"
	@echo "  make api         Lance l'API en dev (reload)"
	@echo "  make worker      Lance le worker Celery"
	@echo "  make web         Lance le front web en dev"
	@echo "  make desktop     Lance l'app desktop (Tauri dev)"
	@echo "  make test        Lance les tests backend"
	@echo "  make lint        Lint backend + typecheck front"
	@echo "  make build       Build web + desktop"
	@echo "  make docker-up   Démarre la stack complète (docker compose)"
	@echo "  make docker-down Arrête la stack complète"

install:
	pnpm install
	cd services/api && python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"

infra-up:
	cd infra && docker compose up -d postgres redis minio minio-init

infra-down:
	cd infra && docker compose down

api:
	cd services/api && . .venv/bin/activate && uvicorn app.main:app --reload

worker:
	cd services/api && . .venv/bin/activate && celery -A app.workers.celery_app.celery_app worker --loglevel=info

web:
	pnpm --filter web dev

desktop:
	pnpm --filter desktop tauri dev

test:
	cd services/api && . .venv/bin/activate && pytest -q

lint:
	cd services/api && . .venv/bin/activate && ruff check app tests && ruff format --check app tests
	pnpm --filter web lint
	pnpm --filter desktop lint

build:
	pnpm --filter web build
	pnpm --filter desktop build

docker-up:
	cd infra && docker compose up -d --build

docker-down:
	cd infra && docker compose down

security:
	./scripts/security-scan.sh

sbom:
	./scripts/generate-sbom.sh

load:
	k6 run load/load-test.js

verify-image:
	./scripts/verify-image.sh $(IMAGE)
