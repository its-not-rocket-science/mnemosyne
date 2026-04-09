# Mnemosyne

Turn any text into a spaced-repetition lesson.

Paste a passage, parse it into sentences, open per-word micro-lessons, and rate your recall. FSRS schedules the next review. No accounts, no tracking, no ads.

**Current state:** working single-user MVP — Spanish (`es_core_news_sm`) and an English stub. User accounts, Alembic migrations, and additional language plugins are planned; see [ROADMAP.md](ROADMAP.md).

---

## Quick start

### Docker (recommended)

```bash
cp .env.example .env          # review and adjust if needed
make build                    # builds image; generates poetry.lock if absent
make up                       # starts app + postgres + redis
make ready                    # prints connectivity report
```

Serve the frontend separately:

```bash
python -m http.server 8080 -d frontend
# → http://localhost:8080
```

### Local (no Docker)

```bash
poetry install
python -m spacy download es_core_news_sm

cp .env.example .env          # point DATABASE_URL and REDIS_URL at local services
make dev                      # uvicorn with hot-reload on :8000
python -m http.server 8080 -d frontend
```

Tables are created automatically on first startup via `create_all`. Replace with `alembic upgrade head` before any production deploy.

---

## API

### `POST /parse`

Splits text into sentences, extracts learnable objects, persists the result, and caches it in Redis (1 h TTL).

```json
{
  "text": "Hola. Yo hablo español.",
  "language": "es",
  "source_url": "https://example.com/article"
}
```

Response:

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
          "confidence": 0.85
        }
      ]
    }
  ]
}
```

`learnable_objects[].type` is one of: `vocabulary`, `conjugation`, `agreement`, `idiom`, `grammar`, `nuance`.

### `GET /lesson/{object_id}?language=es`

Returns lesson content. Checks the database first; falls back to the plugin's in-session store.

### `POST /review`

Submits a recall rating (1 = Again, 2 = Hard, 3 = Good, 4 = Easy) and returns the next scheduled interval. `review_state` can be omitted — the server loads it from the database.

```json
{ "object_id": "es:vocab:hola", "quality": 3 }
```

### `GET /health`

Liveness probe. Returns `{"status": "ok"}` when the process is alive.

### `GET /ready`

Readiness probe. Checks PostgreSQL and Redis. Returns `{"status": "ready", "db": "ok", "redis": "ok"}` on success, `503` with per-service error detail on failure.

---

## Tests

```bash
make test
# or: pytest backend/tests -q
```

No external services needed. Route tests use a sync `TestClient`; persistence tests use in-memory SQLite via `aiosqlite`. The Spanish NLP tests (`test_spanish_spacy.py`) require `es_core_news_sm`.

---

## Configuration

All settings come from environment variables or `.env`:

| Variable | Default |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/mnemosyne` |
| `REDIS_URL` | `redis://localhost:6379/0` |
| `DEBUG` | `true` |
| `CORS_ORIGINS` | `["*"]` |
| `PLUGIN_PACKAGE` | `backend.plugins` |

See `.env.example` for the full list including Docker Compose's `POSTGRES_*` variables.

---

## Further reading

- [ARCHITECTURE.md](ARCHITECTURE.md) — request flow, plugin system, FSRS scheduler, persistence model
- [CONTRIBUTING.md](CONTRIBUTING.md) — setup, coding standards, how to add a language plugin
- [ROADMAP.md](ROADMAP.md) — what's done and what's next
