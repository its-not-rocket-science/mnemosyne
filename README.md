# Mnemosyne

**Turn any text into a living lesson.**

Mnemosyne is a minimalist, accessible language-learning web app that transforms text into sentence-level lessons with spaced-repetition review.

## What is in this repo

- FastAPI backend with PostgreSQL persistence and Redis parse cache
- SQLAlchemy 2.0 async ORM models (`ParsedText`, `Sentence`, `LearnableObject`, `ReviewState`)
- Typed Pydantic v2 schemas
- Language plugin interface and auto-loader
- spaCy-backed Spanish plugin (`es_core_news_sm`) with vocabulary, conjugation, and agreement extraction
- FSRS-5 spaced-repetition scheduler (pure Python, standard library only)
- Accessible frontend using semantic HTML and Web Components (no framework)
- Lesson modal with focus trap, keyboard navigation, and aria-live feedback
- TTS via Web Speech API

## Quick start

### 1. Install dependencies

```bash
poetry install
python -m spacy download es_core_news_sm
```

### 2. Start services

```bash
# PostgreSQL and Redis must be running.
# Default URLs: postgresql+asyncpg://postgres:postgres@localhost:5432/mnemosyne
#               redis://localhost:6379/0
# Override via .env or environment variables.
```

### 3. Run the backend

```bash
poetry run uvicorn backend.main:app --reload
```

Tables are created automatically on first startup.  Use Alembic for schema migrations in production.

### 4. Open the frontend

```bash
python -m http.server 8080 -d frontend
```

Then open `http://localhost:8080`.

## API

### `POST /parse`

Splits text into sentences, extracts learnable objects, and persists the result.

```json
{
  "text": "Hola. Yo hablo español.",
  "language": "es",
  "source_url": "https://example.com/article"
}
```

Response shape:

```json
{
  "sentences": [
    {
      "text": "Hola.",
      "learnable_objects": [
        {
          "id": "es:vocab:hola",
          "type": "vocabulary",
          "label": "hola",
          "lesson_data": { "lemma": "hola" },
          "confidence": 0.9
        }
      ]
    }
  ]
}
```

### `GET /lesson/{object_id}?language=es`

Returns lesson content for a learnable object.  Checks the database first; falls back to the plugin's in-memory store.

### `POST /review`

Submits a recall rating (1–4) and returns the next scheduled interval.  Loads prior FSRS state from the database; persists the updated state.

```json
{ "object_id": "es:vocab:hola", "quality": 3 }
```

### `GET /health`

Returns `{"status": "ok"}`.

## Running tests

```bash
poetry run pytest
```

Persistence tests use an in-memory SQLite database via `aiosqlite`; no running PostgreSQL or Redis is required.

## Configuration

All settings are read from environment variables or a `.env` file:

| Variable | Default |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/mnemosyne` |
| `REDIS_URL` | `redis://localhost:6379/0` |
| `DEBUG` | `true` |
| `CORS_ORIGINS` | `["*"]` |
| `PLUGIN_PACKAGE` | `backend.plugins` |

## Design notes

- The Spanish plugin is deliberately conservative; low-confidence extractions are omitted rather than guessed.
- The FSRS scheduler uses named, documented constants rather than an opaque optimised weight vector.
- The frontend uses logical CSS properties, `color-mix()` for adaptive theming, and shadow-DOM Web Components.
- DB and Redis failures are non-fatal: the API degrades gracefully to in-memory/stateless operation.
- `create_all` in the lifespan is suitable for development; replace with `alembic upgrade head` in production.
