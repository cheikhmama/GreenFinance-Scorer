# GreenFinance-Scorer

[![CI](https://github.com/cheikhmama/GreenFinance-Scorer/actions/workflows/ci.yml/badge.svg)](https://github.com/cheikhmama/GreenFinance-Scorer/actions/workflows/ci.yml)

Plateforme de scoring ESG et carbone pour entreprises, à partir de documents financiers et extra-financiers.

## Démarrage local

```bash
cp .env.example .env               # une seule fois
./scripts/dev-up.sh                # PostgreSQL + Redis + migrations
uv run uvicorn app.main:app --reload --port 8000   # terminal 1
cd frontend && npm install && npm run dev           # terminal 2
```

Frontend sur `http://localhost:5173`, API sur `http://localhost:8000` (même port que
`docker compose up api`, voir `docker-compose.yml` — un seul port à retenir quel que soit
le mode de lancement de l'API). Le proxy Vite fait apparaître `/api/v1` comme same-origin
depuis le frontend, voir `frontend/vite.config.ts`.
