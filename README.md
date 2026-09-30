# GreenFinance-Scorer

[![CI](https://github.com/cheikhmama/GreenFinance-Scorer/actions/workflows/ci.yml/badge.svg)](https://github.com/cheikhmama/GreenFinance-Scorer/actions/workflows/ci.yml)

Plateforme de scoring ESG et carbone pour entreprises, à partir de documents financiers et extra-financiers.

## Démarrage local

```bash
cp .env.example .env               # une seule fois
./scripts/dev-up.sh                # PostgreSQL + Redis + migrations
uv run uvicorn app.main:app --reload --port 8000   # terminal 1
cd frontend && npm install && npm run dev           # terminal 2
uv run arq app.worker.settings.WorkerSettings              # terminal 3 : e-mails, PDF, tâche planifiée
uv run arq app.worker.settings.ExtractionWorkerSettings    # terminal 4 : extraction des rapports
```

Les e-mails et l'extraction des rapports sont traités par les workers ARQ (Redis) : sans eux,
les jobs attendent dans Redis et sont traités au démarrage d'un worker. En Docker :
`docker compose up api worker worker-extraction` (développement : ports et identifiants de
`docker-compose.override.yml`).

## Production (Docker)

```bash
POSTGRES_PASSWORD=… REDIS_PASSWORD=… \
  docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Deux images depuis le même `Dockerfile` : `api` (API, worker par défaut, migrations — sans la
pile d'extraction) et `worker` (extraction Docling/torch). Utilisateur non privilégié, ni tests
ni outils de développement. Le service `migrate` applique `alembic upgrade head` avant tout le
reste ; seul le port de l'API est publié, Postgres et Redis restent sur le réseau Docker, Redis
exige un mot de passe.

Frontend sur `http://localhost:5173`, API sur `http://localhost:8000` (même port que
`docker compose up api`, voir `docker-compose.yml` — un seul port à retenir quel que soit
le mode de lancement de l'API). Le proxy Vite fait apparaître `/api/v1` comme same-origin
depuis le frontend, voir `frontend/vite.config.ts`.
