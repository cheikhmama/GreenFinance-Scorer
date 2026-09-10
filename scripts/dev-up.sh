#!/usr/bin/env bash
# Démarrage local minimal — Phase 1 (§1.5).
#
# Ne lance ni l'API ni le frontend : chacun veut son propre terminal en
# premier plan pour voir ses logs (uvicorn --reload, npm run dev). Ce script
# ne fait que le socle partagé par les deux : dépendances + migrations.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "==> Démarrage de PostgreSQL et Redis (attente des healthchecks)..."
docker compose up -d --wait db redis

echo "==> Application des migrations Alembic..."
uv run alembic upgrade head

cat <<'EOF'

Socle prêt. Dans deux terminaux séparés :

  Backend  : uv run uvicorn app.main:app --reload --port 8000
             (ou : docker compose up api)
  Frontend : cd frontend && npm run dev

EOF
