# Contributing to Mnemosyne

## Prerequisites

| Tool | Version |
|---|---|
| Python | 3.12+ |
| Poetry | 1.8+ |
| Docker + Compose v2 | any recent |
| spaCy model (Spanish) | `es_core_news_sm` |

---

## Setup

### Local (no Docker)

```bash
poetry install
python -m spacy download es_core_news_sm
cp .env.example .env
```

Edit `.env` to point `DATABASE_URL` and `REDIS_URL` at locally running services, then:

```bash
make dev                      # uvicorn --reload on :8000
python -m http.server 8080 -d frontend
```

### Docker

```bash
cp .env.example .env
make build && make up
make ready                    # should print {"status": "ready", ...}
```

Backend code is bind-mounted (`./backend → /app/backend`), so uvicorn hot-reloads on every save. Frontend is also mounted but served statically — refresh the browser to pick up changes.

---

## Testing

```bash
make test
# or: pytest backend/tests -q
```

**No external services required.** The test suite is split into two layers:

| File | What it tests | DB / Redis |
|---|---|---|
| `test_api.py` | Route shape, status codes, error paths | none (DB calls non-fatal) |
| `test_persistence.py` | DB writes and reads end-to-end | in-memory SQLite via `aiosqlite` |
| `test_fsrs.py` | FSRS scheduler pure functions | none |
| `test_plugin.py` | Plugin registry and loader | none |
| `test_spanish_spacy.py` | Spanish NLP extraction | requires `es_core_news_sm` |

Run only the fast tests (no spaCy model required):

```bash
pytest backend/tests -q --ignore=backend/tests/test_spanish_spacy.py
```

---

## Lint and type checking

```bash
make lint
# runs: ruff check backend && mypy backend --ignore-missing-imports
```

`ruff` is configured in `pyproject.toml` (line-length 100, target py312). All backend files should pass without warnings. `mypy` is not set to strict; new code should not add `# type: ignore` without a comment explaining why.

---

## Coding standards

- **`from __future__ import annotations`** at the top of every backend module.
- **Pydantic v2** for all data contracts crossing module boundaries. No raw dicts as function signatures.
- **Async SQLAlchemy 2.0** for all DB access. No `Session.execute` — use `AsyncSession`.
- **Fault-tolerant I/O.** All DB and Redis calls in routes are wrapped in `try/except` with a `logger.warning`. The app must degrade gracefully, not crash.
- **No global mutable state** outside of the lazy-initialised singletons (`_redis_client`, `PluginRegistry`).
- **Object ID stability.** A given lemma/form must always produce the same ID across server restarts. Use `{language}:{type}:{lemma}` (e.g. `es:vocab:hola`).
- **Conservative extractions.** Omit rather than guess. A missing learnable object is better than a wrong one.

---

## Adding a language plugin

A plugin is a single Python module in `backend/plugins/` that exports a `create_plugin()` factory. The loader discovers it automatically — no registration step needed.

### 1. Create the module

```python
# backend/plugins/french.py
from __future__ import annotations

from backend.parsing.plugin_interface import Token
from backend.schemas.parse import LearnableObject, SentenceResult


class FrenchPlugin:
    language_code = "fr"          # must match the BCP-47 tag used in /parse requests
    display_name  = "French"
    direction     = "ltr"

    def __init__(self) -> None:
        # In-session cache for get_lesson() fallback (populated during analyze_sentence).
        self._lesson_store: dict[str, LearnableObject] = {}

    def split_sentences(self, text: str) -> list[str]:
        # Return a list of sentence strings in document order.
        ...

    def analyze_sentence(self, sentence: str) -> SentenceResult:
        # Parse one sentence; return all learnable objects found in it.
        objects: list[LearnableObject] = []
        # ... extract, build LearnableObject(s), store in self._lesson_store ...
        return SentenceResult(text=sentence, learnable_objects=objects)

    def get_lesson(self, object_id: str) -> LearnableObject | None:
        # Called by GET /lesson when the DB row is absent (e.g. first request
        # in a new server session after a DB wipe).
        return self._lesson_store.get(object_id)


def create_plugin() -> FrenchPlugin:
    return FrenchPlugin()
```

### 2. Construct `LearnableObject` correctly

```python
LearnableObject(
    id       = "fr:vocab:maison",         # {lang}:{type}:{lemma} — must be stable
    type     = "vocabulary",              # one of the LearnableType literals
    label    = "maison",                  # surface form shown in the UI
    lesson_data = {                       # arbitrary key-value pairs; rendered
        "lemma":    "maison",             # as a bullet list in the lesson modal
        "gender":   "feminine",
        "pos":      "noun",
    },
    confidence = 0.80,                    # 0–1 heuristic; None if not computed
)
```

`type` must be one of: `vocabulary`, `conjugation`, `agreement`, `idiom`, `grammar`, `nuance`.

### 3. ID rules

- Format: `{language_code}:{type}:{canonical_form}` — all lowercase, no spaces.
- Must be **deterministic**: re-parsing the same text must produce the same IDs.
- Lemmas with spaces (enclitic fusion artifacts) should be silently dropped — IDs with spaces break URL routing.

### 4. Confidence guidelines

| Score | Meaning |
|---|---|
| 0.90+ | High confidence — morphology complete, unambiguous |
| 0.70–0.89 | Normal — minor uncertainty (OOV word, incomplete morphology) |
| 0.50–0.69 | Low — heuristic inference, parse may be wrong |
| below 0.50 | Consider omitting entirely |

There is no calibration infrastructure yet; these are communicative heuristics, not probabilities.

### 5. Lazy model loading

Load heavy NLP models lazily using `@cached_property` or equivalent, not at import time. The loader runs `create_plugin()` eagerly at startup; a model failure during import would prevent the whole server from starting.

```python
from functools import cached_property

class FrenchPlugin:
    @cached_property
    def _nlp(self):
        import spacy
        return spacy.load("fr_core_news_sm")
```

### 6. Tests

Add `backend/tests/test_french.py`. At minimum:

- Sentences split correctly (count, text).
- Known words appear in `learnable_objects` with the right type and ID.
- The `get_lesson()` fallback returns the stored object after `analyze_sentence`.
- Sentences with no extractable content return an empty list, not an error.

Use `pytest` with sync calls — plugins are synchronous. No fixtures needed for basic extraction tests.

---

## Frontend

The frontend is vanilla JS with no build step. Edit files in `frontend/` and refresh the browser.

- `frontend/js/main.js` — application logic, fetch calls, DOM rendering
- `frontend/components/` — Web Components (`mnemosyne-pill`, `mnemosyne-modal`)
- `frontend/css/` — global tokens and component styles (no framework)

Keep changes consistent with the accessibility constraints in [ARCHITECTURE.md](ARCHITECTURE.md): solid focus rings, `aria-live` live regions, `inert` for modal backgrounds, minimum 44 px touch targets.
