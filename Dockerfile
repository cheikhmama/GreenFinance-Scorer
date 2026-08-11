FROM python:3.11-slim

WORKDIR /code

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
COPY app ./app
COPY tests ./tests
RUN uv sync --frozen

ENV PATH="/code/.venv/bin:$PATH"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
