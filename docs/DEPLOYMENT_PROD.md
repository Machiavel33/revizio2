# Revizio — Déploiement production (revizio.darkops.fr)

> Déploiement réel sur serveur Debian 13, mono-serveur, stockage local.
> Domaine : **https://revizio.darkops.fr** — TLS Let's Encrypt.

---

## Architecture déployée

```
Internet ──443/80──> nginx (host) ──> 127.0.0.1:8080 (web SPA)
                                  └──> 127.0.0.1:8000 (API FastAPI)
                                          ├── postgres (127.0.0.1:5432)
                                          ├── redis    (127.0.0.1:6379)
                                          └── worker Celery
Stockage audio : volume Docker `revizio_audio_data` (filesystem local)
```

Tous les ports internes sont bindés sur `127.0.0.1` — **inaccessibles de l'extérieur**.
Seuls 80/443 sont publics (nginx).

## Emplacements

| Élément | Chemin |
|---|---|
| Projet | `/var/www/revizio` |
| Compose prod | `/var/www/revizio/infra/docker-compose.prod.yml` |
| Secrets | `/var/www/revizio/infra/.env` (chmod 600) |
| nginx vhost | `/etc/nginx/sites-available/revizio.darkops.fr` |
| Certificat | `/etc/letsencrypt/live/revizio.darkops.fr/` |
| Backups | `/var/backups/revizio/` |
| Logs backup | `/var/log/revizio-backup.log` |

## Commandes d'exploitation

```bash
cd /var/www/revizio/infra

# Démarrer / mettre à jour
docker compose -f docker-compose.prod.yml up -d --build

# État
docker compose -f docker-compose.prod.yml ps

# Logs
docker logs revizio-api -f
docker logs revizio-worker -f

# Redémarrer un service
docker compose -f docker-compose.prod.yml restart api

# Migrations manuelles
docker exec revizio-api alembic upgrade head

# Backup manuel
/var/www/revizio/scripts/backup.sh
```

## Créer un compte admin

```bash
# 1. Inscription via l'API
curl -X POST https://revizio.darkops.fr/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"vous@exemple.fr","password":"MotDePasseFort!","display_name":"Admin"}'

# 2. Promotion en admin
docker exec revizio-postgres psql -U revizio -d revizio \
  -c "UPDATE users SET role='admin' WHERE email='vous@exemple.fr';"
```

## Sécurité en place

- **TLS** : Let's Encrypt, renouvellement auto (certbot timer), TLS 1.2/1.3.
- **HSTS** : `max-age=63072000; includeSubDomains`.
- **Headers** : nosniff, DENY frame, referrer-policy (nginx + app).
- **Firewall (ufw)** : deny par défaut, SSH rate-limited, 80/443 ouverts.
- **fail2ban** : jail `sshd` + `revizio-auth` (brute-force login/register).
- **Ports internes** : bindés 127.0.0.1 uniquement.
- **Secrets** : générés aléatoirement, `.env` chmod 600, jamais commités.
- **Rate-limit** : Redis (120/min API, 20/min auth).
- **Backups** : quotidien 03:00 UTC (DB + audio), rétention 14j.
- **Conteneurs** : non-root, healthchecks.

## Stockage audio

Backend `local` (filesystem) par défaut en mono-serveur. Pour passer à S3/MinIO :
1. Décommenter le service `minio` dans un compose dédié.
2. Mettre `STORAGE_BACKEND=s3` + `S3_ENDPOINT_URL` dans l'environnement api/worker.

## Renouvellement TLS

Automatique via `certbot.timer`. Vérifier :
```bash
systemctl status certbot.timer
certbot renew --dry-run
```

## Restauration d'un backup

```bash
# DB
docker exec -i revizio-postgres pg_restore -U revizio -d revizio --clean \
  < /var/backups/revizio/db_YYYYMMDD_HHMMSS.dump

# Audio
docker run --rm -v revizio_audio_data:/data -v /var/backups/revizio:/backup alpine \
  tar xzf /backup/audio_YYYYMMDD_HHMMSS.tar.gz -C /data
```
