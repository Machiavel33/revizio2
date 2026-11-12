#!/bin/sh
# Entrypoint : garantit que les volumes montés sont accessibles par l'utilisateur
# revizio (les volumes Docker nommés sont créés root par défaut).
set -e

for d in /data/audio /data/whisper /data/downloads; do
    if [ -d "$d" ]; then
        chown -R revizio:revizio "$d" 2>/dev/null || true
    fi
done

# Exécute la commande en tant que revizio
exec gosu revizio "$@"
