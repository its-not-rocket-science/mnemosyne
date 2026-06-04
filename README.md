# Mnemosyne

Paste any text, parse it into sentences, open per-word micro-lessons, and rate your recall. FSRS schedules the next review.

**Current state:** multi-user system with seventeen language plugins. Full morphological analysis for Spanish, French, German, Russian, Japanese, Portuguese, and Italian; full grammar and nuance analysis for English (phrasal verbs, tense constructions, register markers via spaCy; shallow tense morphology — present and past only); morphology-light for Latin, Koine Greek, Korean, Hindi, and Turkish; Stanza-primary rich morphology plus grammar-nuance drills for Finnish; vocabulary/dictionary mode for Arabic, Hebrew, and Mandarin Chinese. RTL layout (Arabic, Hebrew) and CJK segmentation (Chinese, Japanese) are supported. User authentication is implemented (JWT); see [ROADMAP.md](ROADMAP.md).

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


### Windows note

Use Docker Desktop and PowerShell:

```powershell
Copy-Item .env.example .env
docker compose build
docker compose up -d
Invoke-WebRequest http://localhost:8000/ready | Select-Object -Expand Content
```

### Local (no Docker)

Requires PostgreSQL and Redis already running.

```bash
poetry install
# Minimum — Spanish only:
python -m spacy download es_core_news_sm
# Optional — install additional language models as needed:
# python -m spacy download fr_core_news_sm de_core_news_sm
# python -m spacy download ru_core_news_sm ja_core_news_sm
# python -m spacy download pt_core_news_sm it_core_news_sm
cp .env.example .env     # set DATABASE_URL and REDIS_URL
psql -h localhost -U postgres -l
make dev                 # uvicorn --reload on :8000
python -m http.server 8080 -d frontend
```

Tables are managed by Alembic. On first startup the application runs `alembic upgrade head` automatically. No manual migration step is needed for fresh or existing databases.


Windows PowerShell:

```powershell
poetry install
python -m spacy download es_core_news_sm
Copy-Item .env.example .env
psql -h localhost -U postgres -l
```

Example .env for Windows:

```env
DATABASE_URL=postgresql+asyncpg://postgres:changeme@postgres:5432/mnemosyne
REDIS_URL=redis://localhost:6379/0
```

Run:

```powershell
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

or as a background process:
Start-Process python -WorkingDirectory "working directory path" `
  -ArgumentList "-m","uvicorn","backend.main:app","--reload","--host","0.0.0.0","--port","8000"

python -m http.server 8080 -d frontend
```

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
          "id": "a7f3c2d1-e4b5-5678-90ab-cdef12345678",
          "language": "es",
          "type": "vocabulary",
          "label": "hola",
          "lesson_data": { "lemma": "hola", "pos": "INTJ" },
          "confidence": 0.85
        }
      ]
    }
  ]
}
```

`id` is a deterministic UUID-v5 derived from `(language, type, canonical_form)`. The same word in any text always produces the same UUID.

`type` is one of: `vocabulary` `conjugation` `agreement` `idiom` `grammar` `nuance`.

---

### `POST /ingest`

Preferred ingest endpoint. Accepts text plus attribution metadata, runs the same parse pipeline as `/parse`, and additionally persists a `SourceDocument` + `SourceChunk` row for reading-progression tracking.

**Request**
```json
{
  "text": "Hola. Yo hablo español.",
  "language": "es",
  "content_type": "article",
  "title": "Mi primer artículo",
  "source_url": "https://example.com",
  "author": null,
  "filename": null
}
```

`content_type`: one of `article`, `book`, `lyrics`, `legal`, `conversation`, `other`.

**Response** — same `sentences` array as `/parse`, plus:
```json
{
  "sentences": [...],
  "source_document_id": "a1b2c3d4-...",
  "warnings": []
}
```

`source_document_id` is the stable reference for repeated-exposure tracking and reading-progression queries (`GET /reading/{id}`).

`POST /parse` is retained for backward compatibility. New clients should use `/ingest`.

---

### `GET /lesson/{object_id}?language=es`

Returns lesson content for one learnable object. Checks the database first; falls back to the plugin's in-session store.

---

### `POST /review`

Submits a recall rating and returns the next scheduled interval.

**Request**
```json
{
  "object_id": "a7f3c2d1-e4b5-5678-90ab-cdef12345678",
  "quality": 3,
  "review_state": null
}
```

`quality`: 1 = Again, 2 = Hard, 3 = Good, 4 = Easy.

`review_state`: send `null` on the first review. On subsequent reviews within the same browser session pass back the `review_state` from the previous response so the server can use it as a fallback if the database is unavailable.

**Response**
```json
{
  "object_id": "a7f3c2d1-e4b5-5678-90ab-cdef12345678",
  "next_interval_days": 3,
  "review_state": { "stability": 2.4, "difficulty": 5.31, "reviews": 1, "...": "..." }
}
```

---

### `GET /dashboard`

Returns a knowledge-state summary for the default user.

Optional query parameter: `?language=es` — scopes results to one language.

```json
{
  "known": [...],
  "weak": [...],
  "new": [...],
  "due_for_review": [...],
  "total_objects": 42
}
```

Each item carries `object_id`, `language`, `status` (`new` / `learning` / `mastered` / `forgotten`), `mastery_score`, `total_reviews`, `last_seen`, and `due_at`.

---

### `GET /metrics`

Returns quantitative learning-effectiveness figures.

Optional query parameter: `?language=es`.

```json
{
  "total_seen": 84,
  "total_reviewed": 31,
  "total_mastered": 7,
  "overall_retention": 0.74,
  "success_rate": 0.82,
  "avg_stability_days": 4.3,
  "overdue_count": 3,
  "by_language": [{ "language": "es", "seen": 80, "mastered": 7, "retention": 0.74 }],
  "by_type": [{ "type": "vocabulary", "seen": 60, "reviewed": 22, "mastered": 5, "retention": 0.78 }],
  "weakest": [{ "object_id": "...", "type": "conjugation", "mastery_score": 0.12, "lapse_rate": 0.5 }]
}
```

---

### `GET /recommend` or `GET /recommend-text`

Returns sentences from the user's parse history at the difficulty appropriate for their current knowledge state, following the i+1 comprehensible-input principle.

Required query parameter: `?language=es`  
Optional: `&limit=10` (1–50)

```json
{
  "sentences": [
    {
      "sentence_id": "...",
      "text": "El gato duerme.",
      "difficulty": 0.38,
      "difficulty_label": "ideal",
      "unknown_ratio": 0.25,
      "grammar_score": 0.14,
      "length_score": 0.12,
      "known_count": 3,
      "unknown_count": 1,
      "total_objects": 4
    }
  ],
  "user_level": "elementary",
  "target_difficulty_min": 0.15,
  "target_difficulty_max": 0.39,
  "total_mastered": 12,
  "total_seen": 47
}
```

`difficulty_label` is `easy` (< 15% unknown), `ideal` (15–40% unknown), or `hard` (> 40% unknown).

---

### `GET /languages`

Returns the list of active language plugins.

```json
[
  { "code": "es", "display_name": "Spanish",        "direction": "ltr" },
  { "code": "fr", "display_name": "French",         "direction": "ltr" },
  { "code": "ar", "display_name": "Arabic",         "direction": "rtl" },
  { "code": "en", "display_name": "English (stub)", "direction": "ltr" }
]
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

No external services needed for most tests. See [CONTRIBUTING.md](CONTRIBUTING.md) for the full breakdown.

---

## Configuration

| Variable | Default |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5432/mnemosyne` |
| `REDIS_URL` | `redis://localhost:6379/0` |
| `DEBUG` | `true` |
| `CORS_ORIGINS` | `["*"]` |
| `PLUGIN_PACKAGE` | `backend.plugins` |
| `ENABLED_LANGUAGES` | *(empty — all plugins loaded)* |

`ENABLED_LANGUAGES` is a comma-separated list (e.g. `es,fr`) that restricts which plugins are registered. Unset means load all discovered plugins.

See `.env.example` for the full list including the `POSTGRES_*` variables used by Docker Compose.

---

## Known limitations

- **Lesson prose is English-only.** `build_lesson()` always produces English explanations ("The word X is a noun"). There is no `l1_language` parameter yet; learners whose native language is not English see English metalanguage regardless of the target language.
- **Background parse is in-process.** `POST /parse/jobs` runs NLP in a thread-pool executor inside the same uvicorn process. Multi-worker deployments (`--workers N > 1`) require sticky sessions (e.g. Nginx `ip_hash`, Traefik sticky cookie) scoped to the job ID so that SSE/polling requests reach the same worker that created the job. Single-worker deployments (`--workers 1`, the default) are unaffected.
- **Classical morphology is shallow.** Latin and Koine Greek use offline treebank annotations (Universal Dependencies ITTB/PROIEL + MorphGNT) for morphological features. Coverage is limited to attested forms in those corpora (~3 400 Latin, ~27 000 Greek forms). Unattested forms fall back to the curated dictionary with lower confidence. Run `python -m scripts.ingest_classical_morph --lang all` to rebuild the indices from updated corpora.
- **WCAG 2.1 AA — static audit passes; manual AT test pending.** Static checks run via `pytest backend/tests/test_accessibility_static.py`. A human keyboard-only walkthrough and NVDA/VoiceOver smoke test have not been run; see `MANUAL_ACCESSIBILITY_TEST.md` and `WCAG_AUDIT.md` for the checklist and full audit.

---

## Docs

- [ARCHITECTURE.md](ARCHITECTURE.md) — request flows, plugin system, FSRS scheduler, persistence, difficulty scoring
- [CONTRIBUTING.md](CONTRIBUTING.md) — setup, coding standards, how to write a language plugin
- [ROADMAP.md](ROADMAP.md) — what is done and what is next
- [VISION_ALIGNMENT.md](VISION_ALIGNMENT.md) — vision, current state, gaps, and design principles
- [WCAG_AUDIT.md](WCAG_AUDIT.md) — WCAG 2.1 AA static audit findings and manual test instructions
- [MANUAL_ACCESSIBILITY_TEST.md](MANUAL_ACCESSIBILITY_TEST.md) — step-by-step keyboard/AT manual test script
- [docs/offline_scripts.md](docs/offline_scripts.md) — offline data pipeline scripts reference
- [docs/corpus_pipeline.md](docs/corpus_pipeline.md) — offline corpus ingestion pipeline
