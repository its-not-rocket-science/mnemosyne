# syntax=docker/dockerfile:1
FROM python:3.12-slim

# asyncpg compiles a small C extension that needs gcc and libpq headers.
RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc libpq-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=2.1.0 \
    POETRY_VIRTUALENVS_CREATE=false

RUN pip install "poetry==$POETRY_VERSION"

# Copy dependency manifests first so this layer is only rebuilt when they change.
# poetry.lock must exist — run `poetry lock` (or `make lock`) before building.
COPY pyproject.toml poetry.lock ./
# --extras cjk installs jieba + pypinyin (Mandarin Chinese plugin).
# --extras korean installs kiwipiepy (Korean plugin).
# --extras arabic is intentionally OMITTED: camel-tools pulls in torch + transformers
# (~2 GB extra), inflating the image. To enable Arabic root/proclitic morphology,
# pass POETRY_INSTALL_EXTRAS="--extras cjk --extras korean --extras arabic"
# and add a camel_data install step. The Arabic plugin works in dictionary mode
# (tashkeel + nuance extractor) without it.
ARG POETRY_INSTALL_EXTRAS="--extras cjk --extras korean"
RUN poetry install --without dev ${POETRY_INSTALL_EXTRAS} --no-interaction --no-ansi

# Download spaCy models. CI can override SPACY_MODELS to install only the models
# exercised by the smoke test, avoiding unrelated network-heavy downloads.
ARG SPACY_MODELS="es_core_news_sm fr_core_news_sm de_core_news_sm it_core_news_sm pt_core_news_sm ru_core_news_sm ja_core_news_sm en_core_web_sm fi_core_news_sm"
RUN if [ -n "$SPACY_MODELS" ]; then \
      for model in $SPACY_MODELS; do \
        python -m spacy download "$model"; \
      done; \
    fi

# Application source is copied after deps to preserve layer caching on code changes.
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# Alembic migrations — must be present so the startup migration runner works.
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Run as a non-root user.
RUN useradd -m -u 1001 appuser && chown -R appuser /app
USER appuser

EXPOSE 8000

# Liveness check — confirms the process is alive and accepting HTTP.
# The /ready endpoint does the deeper DB + Redis check.
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c \
        "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
