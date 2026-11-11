# Revizio — Déploiement

## Prérequis

- Docker + Docker Compose v2
- (dev) Node 20, pnpm 9, Python 3.12, Rust 1.77+

## Déploiement complet (Docker)

```bash
cd infra
cp .env.example .env
# Éditer .env : SECRET_KEY et BYOK_ENCRYPTION_KEY OBLIGATOIRES
#   openssl rand -hex 32        -> SECRET_KEY
#   openssl rand -base64 32     -> BYOK_ENCRYPTION_KEY
docker compose up -d --build
```

Services exposés :
- **Web** : http://localhost:8080
- **API** : http://localhost:8000 (docs désactivées en prod)
- **MinIO console** : http://localhost:9001

La migration Alembic est appliquée automatiquement au démarrage de l'API.

### Créer un compte admin

Par défaut, tous les comptes sont `student`. Pour promouvoir un admin :

```bash
docker compose exec postgres psql -U revizio -d revizio \
  -c "UPDATE users SET role='admin' WHERE email='vous@exemple.fr';"
```

## Développement local

```bash
make install        # deps JS + Python
make infra-up       # postgres/redis/minio
make api            # API en reload (terminal 1)
make worker         # Celery (terminal 2)
make web            # front web (terminal 3)
make desktop        # app desktop Tauri (terminal 4)
```

## Build desktop multi-OS

```bash
cd apps/desktop
pnpm tauri build
```

Produit les installeurs dans `src-tauri/target/release/bundle/` :
- Linux : `.deb`, `.AppImage`
- macOS : `.dmg`, `.app`
- Windows : `.msi`, `.exe`

La CI (`.github/workflows/ci.yml`) construit et vérifie les 3 OS.

## Sécurité en production

- `SECRET_KEY` et `BYOK_ENCRYPTION_KEY` **doivent** être des valeurs fortes
  (l'API refuse de démarrer sinon).
- Docs OpenAPI désactivées (`APP_ENV=production`).
- Rate-limiting actif (120 req/min API, 20 req/min auth).
- Headers de sécurité (nosniff, DENY frame, referrer-policy).
- Clés BYOK chiffrées AES-256-GCM au repos.
- Utilisateur non-root dans les conteneurs.

## Variables d'environnement clés

| Variable | Rôle |
|---|---|
| `SECRET_KEY` | Signature JWT (obligatoire, forte) |
| `BYOK_ENCRYPTION_KEY` | Chiffrement des clés API (base64 32 octets) |
| `DATABASE_URL` | Connexion PostgreSQL (asyncpg) |
| `CELERY_BROKER_URL` | Broker Redis Celery |
| `S3_ENDPOINT_URL` | Endpoint MinIO/S3 |
| `CORS_ORIGINS` | Origines autorisées (URL du front) |
