# Mnemosyne

Paste any text, parse it into sentences, open per-word micro-lessons, and rate your recall. FSRS schedules the next review.

**Current state:** single-user MVP. Spanish (`es_core_news_sm`) and an English stub are the only active plugins. User accounts, Alembic migrations, and additional languages are Phase 1/2; see [ROADMAP.md](ROADMAP.md).

---

## Quick start

### Docker (recommended)

```bash
cp .env.example .env     # review defaults before starting
make build               # builds the image; generates poetry.lock if absent
make up                  # starts app + postgres + redis in the background
make ready               # prints { "status": "ready", "db": "ok", "redis": "ok" }
```

The API listens on `http://localhost:8000`. The frontend is static HTML/JS — serve it separately:

```bash
python -m http.server 8080 -d frontend
# open http://localhost:8080
```

Backend source is bind-mounted into the container, so uvicorn hot-reloads on save.

### Local (no Docker)

Requires PostgreSQL and Redis already running.

```bash
poetry install
python -m spacy download es_core_news_sm
cp .env.example .env     # set DATABASE_URL and REDIS_URL
make dev                 # uvicorn --reload on :8000
python -m http.server 8080 -d frontend
```

Tables are created automatically via `create_all` on first startup. Swap in `alembic upgrade head` before deploying over existing data.

---

## API

### `POST /parse`

Parses text into sentences and learnable objects. Caches the result in Redis (1 h TTL); persists to PostgreSQL.

**Request**
```json
{
  "text": "Hola. Yo hablo español.",
  "language": "es",
  "source_url": "https://example.com"
}
```
`source_url` is optional; stored for attribution, never fetched.

**Response**
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
          "lesson_data": { "lemma": "hola", "pos": "interjection" },
          "confidence": 0.85
        }
      ]
    }
  ]
}
```

`type` is one of: `vocabulary` `conjugation` `agreement` `idiom` `grammar` `nuance`.

---

### `GET /lesson/{object_id}?language=es`

Returns lesson content for one learnable object. Checks the database first; falls back to the plugin's in-session store.

---

### `POST /review`

Submits a recall rating and returns the next scheduled interval.

**Request**
```json
{
  "object_id": "es:vocab:hola",
  "quality": 3,
  "review_state": null
}
```

`quality`: 1 = Again, 2 = Hard, 3 = Good, 4 = Easy.

`review_state`: send `null` (or omit the field) on the first review — the server creates a fresh FSRS state. On subsequent reviews within the same browser session, pass back the `review_state` from the previous response so the server can use it as a fallback if the database is unavailable.

**Response**
```json
{
  "object_id": "es:vocab:hola",
  "next_interval_days": 3,
  "review_state": { "stability": 2.4, "difficulty": 5.31, "reviews": 1, "..." : "..." }
}
```

---

### `GET /health`

Liveness probe. Returns `{"status": "ok"}` when the process is alive. Does not check backing services.

### `GET /ready`

Readiness probe. Queries PostgreSQL and Redis. Returns `{"status": "ready", "db": "ok", "redis": "ok"}` (HTTP 200) or `{"status": "degraded", ...}` (HTTP 503) with per-service error detail.

---

## Tests

```bash
make test
# or: pytest backend/tests -q
```

No external services needed. See [CONTRIBUTING.md](CONTRIBUTING.md) for the full breakdown of which test files need the spaCy model.

---

## Configuration

| Variable | Default |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/mnemosyne` |
| `REDIS_URL` | `redis://localhost:6379/0` |
| `DEBUG` | `true` |
| `CORS_ORIGINS` | `["*"]` |
| `PLUGIN_PACKAGE` | `backend.plugins` |

See `.env.example` for the full list including the `POSTGRES_*` variables used by Docker Compose.

---

## Docs

- [ARCHITECTURE.md](ARCHITECTURE.md) — request flows, plugin system, FSRS scheduler, persistence
- [CONTRIBUTING.md](CONTRIBUTING.md) — setup, coding standards, how to write a language plugin
- [ROADMAP.md](ROADMAP.md) — what is done and what is next
