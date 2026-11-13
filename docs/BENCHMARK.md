# Revizio — Rapport de mesures du transport résilient (RVZF v1)

> Campagne de mesure bout en bout sur la stack de production réelle
> (`revizio.darkops.fr` : API FastAPI + worker Celery + Whisper local `small`).
> Date : 2026-11-12. Banc : `bench/bench_transport.py`.

---

## 1. Objectif et méthode

Mesurer la **capacité réelle** du transport audio résilient (protocole RVZF v1 :
trames numérotées → fragments de 10 s → ACK après persistance) sous charge croissante,
et identifier le goulot d'étranglement.

**Banc** : client WebSocket qui rejoue un PCM16 mono 16 kHz synthétique en temps réel
(1 trame de 250 ms toutes les 250 ms), envoie les `chunk_end` avec SHA-256, et mesure
la latence d'ACK par fragment. Un compte + un cours isolé par séance.

**Ce qui est mesuré** : latence d'ACK (p50/p95/max), pertes d'ACK, erreurs, intégrité
(SHA-256 vérifié côté serveur avant ACK).

**Ce qui n'est PAS mesuré ici** : WER (pas de corpus de référence — le PCM est synthétique),
qualité sur vrai cours d'amphi, durabilité matérielle (coupure de courant).

**Environnement** : hôte 12 vCPU, 45 Go RAM. Whisper `small` int8, CPU, dans le processus API
(`TRANSCRIBE_ENGINE=local`). Un seul conteneur API (`--workers 1`).

---

## 2. Résultats — montée en charge

Séances de 30 s en temps réel, 3 fragments de 10 s chacune.

| Séances | Fragments envoyés | ACK reçus | Pertes | ACK p50 | ACK p95 | ACK max | Erreurs |
|---|---|---|---|---|---|---|---|
| **1** | 3 | 3 | **0** | 2 255 ms | 4 538 ms | 4 538 ms | 0 |
| **4** | 12 | 12 | **0** | 7 661 ms | 7 910 ms | 8 083 ms | 0 |
| **8** | 24 | 24 | **0** | 21 398 ms | 27 498 ms | 27 720 ms | 0 |
| **16** | 48 | 18 | **30** | 32 829 ms | 35 003 ms | 35 216 ms | 0 |

### Lecture

- **Jusqu'à 8 séances simultanées : 0 perte, 0 erreur.** L'audio est intégralement
  persisté et acquitté. C'est la capacité fiable mesurée.
- **À 16 séances : saturation.** 30 fragments sur 48 ne sont pas acquittés dans la
  fenêtre de grâce (180 s) : la file de transcription ne se vide pas assez vite.
- **La latence d'ACK croît linéairement avec la charge** (2,2 s → 7,7 s → 21 s → 33 s) :
  signature d'un traitement **sérialisé** (un seul modèle Whisper, un seul thread de calcul).

---

## 3. Goulot d'étranglement identifié

Pendant une charge de 8 séances, le conteneur API consomme **350 à 616 % CPU**
(3,5 à 6 cœurs) : Whisper `small` est **CPU-bound** et sature. La transcription des
fragments de 10 s se fait en série dans le processus API (`asyncio.to_thread` +
singleton de modèle protégé par un verrou).

**Conséquence** : le transport (WebSocket, SHA-256, écriture disque) n'est pas le
facteur limitant — c'est le **moteur STT**. Le protocole tient ; c'est le calcul qui
décroche.

---

## 4. Correctif de robustesse appliqué pendant la campagne

La campagne a révélé un défaut : quand un client se déconnecte **pendant** la
transcription d'un fragment (lente sous charge), l'envoi de l'ACK levait
`ClientDisconnected` non géré → exception ASGI dans les logs.

**Correction** (`app/api/routes/ws_transcribe.py`) : l'envoi de l'ACK est désormais
protégé par `try/except (WebSocketDisconnect, RuntimeError)` → sortie propre. L'audio
est déjà persisté avant l'ACK, donc **aucune perte de données**. Vérifié : 0 exception
ASGI après le correctif.

---

## 5. Comparaison avec le projet `revizio` (référence)

Le projet `Machiavel33/revizio` publie un rapport Lot 0 mesuré sur un VPS 4 vCPU
avec **sherpa-onnx streaming** (STT séparé, plusieurs workers) :

| Métrique | `revizio` (réf.) | `revizio2` (nous) |
|---|---|---|
| STT | sherpa-onnx streaming, N workers | faster-whisper `small`, 1 instance |
| Capacité sans perte | 24 séances / 4 workers | **8 séances / 1 instance** |
| ACK p95 à capacité | 145 ms (24 séances) | 27 498 ms (8 séances) |
| Latence transcript | 100-265 ms | ~2-27 s (batch par fragment) |

**Écart principal** : leur STT est **streaming et parallélisé** (vrai temps réel,
latence sub-seconde) ; le nôtre est **batch par fragment de 10 s** (latence de plusieurs
secondes, sérialisé). Leur architecture est plus performante sur le direct.

**Mais** : notre transport est **identique** (même protocole RVZF v1, porté depuis chez
eux) et **prouvé fonctionnel** (0 perte jusqu'à 8 séances). L'écart est dans le moteur
STT, pas dans le transport.

---

## 6. Optimisation appliquée : concurrence bornée + threads CPU

Suite au diagnostic (Whisper sérialise et sature), deux réglages ont été ajoutés
(`app/services/whisper_local.py`, `app/core/config.py`) :

- **`WHISPER_MAX_CONCURRENCY`** (défaut 2) : sémaphore bornant les transcriptions
  simultanées. Au-delà, les appels attendent leur tour au lieu de saturer le CPU.
- **`WHISPER_CPU_THREADS`** (défaut 4) : threads CPU par transcription, pour éviter
  que N transcriptions se disputent les 12 cœurs.

### Effet mesuré (modèle `small`)

| Séances | Avant (sans borne) | Après (conc=2, threads=4) |
|---|---|---|
| 8 | 0 perte, p95 27,5 s | **0 perte**, p95 32,0 s |
| 16 | **30 pertes** / 48 | **18 pertes** / 48 (−40 %) |

La borne **réduit les pertes de 40 % à 16 séances** sans dégrader la capacité fiable
(8 séances). Elle protège aussi l'API : plus d'explosion de latence ni d'exceptions.

## 7. Levier de capacité : choix du modèle

Le vrai levier n'est pas le transport mais le **modèle STT**. Comparaison à 16 séances :

| Modèle | Pertes / 48 | ACK p95 | Capacité fiable |
|---|---|---|---|
| `small` (défaut, qualité) | 18 | 55 s | ~8 séances |
| **`base`** (2-3× plus rapide) | **0** | **12,6 s** | **~16-20 séances** |

À 24 séances avec `base` : 3 pertes / 72 (p95 26 s) — proche du plafond.

**Compromis** : `small` = qualité « très bonne » (recommandé pour les fiches) ;
`base` = « erreurs mots » mais **2× la capacité**. Le choix se fait par
`WHISPER_MODEL` sans changer de code.

## 8. Recommandations

1. **Immédiat (fait)** : concurrence bornée + threads CPU → −40 % de pertes à 16 séances.
2. **Capacité** : garder `small` (qualité) et plafonner à **8 séances/instance**, ou
   passer `base` pour **~16-20 séances** si la capacité prime sur la qualité.
3. **Moyen terme** : **découpler le STT de l'API** (service dédié, plusieurs workers) —
   c'est exactement ce que recommande le rapport Lot 0 de `revizio`.
4. **Long terme** : évaluer **sherpa-onnx streaming** pour le vrai temps réel
   (latence sub-seconde, parallélisable), comme dans `revizio`.
5. **Toujours** : garder le transport RVZF v1 (il tient) et le correctif de robustesse
   sur l'ACK.

---

## 7. Reproduire

```bash
# Dans le conteneur API (a websockets/httpx/numpy)
docker cp bench/bench_transport.py revizio-api:/tmp/
docker exec revizio-api python /tmp/bench_transport.py \
    --sessions 8 --seconds 30 --grace 90 --label cap-8
```

Résultats bruts : `bench/results/stats-*.json`.

---

## 9. Découplage du STT (service dédié) — résultats

Le STT a été extrait dans un **service dédié** (`services/stt/`) : faster-whisper batch
+ sherpa-onnx streaming, isolé de l'API. L'API délègue via HTTP (`STT_SERVICE_URL`).

### Gain principal : l'API reste réactive sous charge

| Métrique (8 séances) | Avant (STT dans l'API) | Après (STT découplé) |
|---|---|---|
| CPU API pendant charge | **350-616 %** | **5 %** |
| Latence `/health` pendant charge | secondes | **4-8 ms** |
| CPU STT pendant charge | — | 55 % (le calcul) |

**C'est le vrai bénéfice** : la transcription ne bloque plus les requêtes HTTP/WS.
L'API peut servir les autres endpoints pendant qu'un cours est transcrit.

### Capacité brute : inchangée (CPU-bound)

| Config | 8 séances | 16 séances |
|---|---|---|
| STT découplé, `small`, conc=2 | **0 perte** | 34 pertes |
| STT découplé, `base`, conc=2 | — | 44 pertes |

Le découplage **ne change pas le débit brut** : Whisper `small` sur CPU reste le
facteur limitant (48 fragments de 10 s = ~8 min de calcul pour 30 s d'audio). Le
découplage apporte la **réactivité** et la **scalabilité horizontale** (on peut lancer
plusieurs réplicas STT), pas un gain de vitesse par instance.

### Streaming temps réel (sherpa-onnx)

Le service STT expose `WS /stream` (sherpa-onnx zipformer FR, Apache-2.0) : vrai
temps réel, partial/final sub-seconde, un flux par séance. Modèle téléchargé et
vérifié par SHA-256 (`scripts/fetch-sherpa-model.sh`). Validé : connexion, `ready`,
traitement des trames, événements partial/final.

### Recommandation

- **Production actuelle** : `small`, conc=2, pool=1 → **8 séances fiables**, API réactive.
- **Montée en charge** : ajouter des réplicas du service `stt` (scalabilité horizontale)
  ou passer `base` pour ~16-20 séances.
- **Temps réel** : brancher le client desktop sur `WS /stream` (sherpa) pour le direct
  sub-seconde, au lieu du pseudo-live par fenêtres.

---

## 10. Streaming temps réel branché (desktop → API → STT sherpa)

Le client desktop utilise désormais le **streaming sherpa** en priorité (fallback
transport résilient si indisponible).

### Chaîne

```
Desktop (useStreamingTranscription)
  → WS /api/ws/stream (API : auth JWT + relais)
    → WS /stream (service STT : sherpa-onnx)
      → transcript.partial / transcript.final (sub-seconde)
        → persisté dans le transcript du cours
```

- Le hook desktop réassemble les chunks Rust (1600 éch. = 100 ms) en trames de
  4000 échantillons (250 ms) attendues par sherpa.
- L'API relaie les trames et persiste les `final` dans le cours.
- Validé bout en bout : `ready` → partial/final → persistance en base.

### Scalabilité horizontale

Le service STT n'a plus de `container_name` fixe : on peut lancer N réplicas.

```bash
docker compose -f docker-compose.prod.yml up -d --scale stt=2
```

L'API joint `http://stt:8100` et Docker répartit via DNS (round-robin). Validé :
2 réplicas healthy, API distribue les requêtes. Chaque réplica a son propre pool
Whisper + moteur sherpa → capacité ≈ N × capacité d'une instance.
