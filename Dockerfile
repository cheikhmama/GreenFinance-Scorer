# syntax=docker/dockerfile:1
#
# Images de production (tâche 4.2) — une seule recette, deux cibles :
#
#   docker build --target api    -t greenfinance-api .     # API, worker par défaut, migrations
#   docker build --target worker -t greenfinance-worker .  # worker d'extraction (Docling, torch)
#
# Étapes de construction séparées des images finales : uv, le cache de téléchargement et les
# outils de compilation ne sont jamais dans une image livrée. Aucune dépendance de développement
# (pytest, mypy, ruff) ni tests/ dans les images : `uv sync --no-default-groups`, et seuls app/,
# alembic/ et config/ sont copiés. Les deux images tournent sous un utilisateur sans privilèges.

ARG PYTHON_VERSION=3.11

# --- construction : environnement virtuel de l'API ---------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS construction-api

COPY --from=ghcr.io/astral-sh/uv:0.11.15 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /code
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-default-groups --no-install-project

# --- construction : + pile d'extraction ---------------------------------------------------------
FROM construction-api AS construction-worker
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-default-groups --group extraction --no-install-project

# --- base d'exécution commune --------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim AS execution

RUN groupadd --system --gid 10001 greenfinance \
    && useradd --system --uid 10001 --gid greenfinance --create-home greenfinance
WORKDIR /code
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# --- image API (et worker par défaut, et migrations) ---------------------------------------------
FROM execution AS api

COPY --from=construction-api /opt/venv /opt/venv
COPY --chown=greenfinance:greenfinance app ./app
COPY --chown=greenfinance:greenfinance alembic ./alembic
COPY --chown=greenfinance:greenfinance alembic.ini ./
COPY --chown=greenfinance:greenfinance config ./config
RUN install -d -o greenfinance -g greenfinance /code/storage

USER greenfinance
EXPOSE 8000
# Derrière un reverse proxy : FORWARDED_ALLOW_IPS doit désigner ce proxy (limites de débit par IP,
# docs/ARCHITECTURE.md §4) — uvicorn le lit dans l'environnement.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]

# --- image worker d'extraction --------------------------------------------------------------------
FROM execution AS worker

# Bibliothèques système requises par Docling / PaddleOCR (rendu, OCR), absentes de l'image API.
RUN apt-get update -qq \
    && apt-get install -y -qq --no-install-recommends \
        libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 libgomp1 libxcb1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=construction-worker /opt/venv /opt/venv
COPY --chown=greenfinance:greenfinance app ./app
COPY --chown=greenfinance:greenfinance config ./config
RUN install -d -o greenfinance -g greenfinance /code/storage

# Pas de compilateur C++ dans cette image slim : torch.compile (modèles de structuration Docling)
# échouerait et retenterait en boucle — l'exécution eager suffit sur CPU.
ENV TORCHDYNAMO_DISABLE=1 \
    TORCH_COMPILE_DISABLE=1 \
    HF_HOME=/home/greenfinance/.cache/huggingface

USER greenfinance
CMD ["arq", "app.worker.settings.ExtractionWorkerSettings"]
