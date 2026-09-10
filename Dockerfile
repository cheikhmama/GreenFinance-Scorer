FROM python:3.11-slim

# Requis par Docling/PaddleOCR (dépendances de app/ingestion/ depuis l'Étape 5) — mêmes paquets que
# Dockerfile.notebook, l'API en a désormais besoin elle aussi.
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 libgomp1 libxcb1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
COPY app ./app
COPY tests ./tests
RUN uv sync --frozen

ENV PATH="/code/.venv/bin:$PATH"
# Pas de compilateur C++ dans cette image slim : torch.compile (utilisé par les modèles de
# structuration Docling) échouerait et retenterait en boucle sans ça — voir
# app/ingestion/docling_pipeline.py pour le garde-fou équivalent en code.
ENV TORCHDYNAMO_DISABLE=1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
