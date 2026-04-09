# Contributing to Mnemosyne

## Prerequisites

| Tool | Minimum version |
|---|---|
| Python | 3.12 |
| Poetry | 1.8 |
| Docker + Compose v2 | any recent |
| spaCy model | `es_core_news_sm` (Spanish tests only) |

---

## Setup

### Local

```bash
poetry install
python -m spacy download es_core_news_sm
cp .env.example .env
# Edit .env: set DATABASE_URL and REDIS_URL to local services.
make dev                       # uvicorn --reload on :8000
python -m http.server 8080 -d frontend
```

### Docker

```bash
cp .env.example .env
make build && make up
make ready                     # should print {"status": "ready", ...}
```

`./backend` and `./frontend` are bind-mounted into the container. Uvicorn reloads on backend saves; refresh the browser for frontend changes.

---

## Running tests

```bash
make test
# or: pytest backend/tests -q
```

The suite requires no running external services:

| File | Scope | External dependency |
|---|---|---|
| `test_api.py` | Route shapes, status codes, error paths | none — DB calls are non-fatal |
| `test_persistence.py` | DB reads and writes end-to-end | in-memory SQLite via `aiosqlite` |
| `test_fsrs.py` | FSRS pure functions | none |
| `test_plugin.py` | Plugin registry and loader | none |
| `test_spanish_spacy.py` | Spanish NLP extraction | **requires `es_core_news_sm`** |

Skip the spaCy-dependent tests when the model is not installed:

```bash
pytest backend/tests -q --ignore=backend/tests/test_spanish_spacy.py
```

---

## Lint and type checking

```bash
make lint
# expands to: ruff check backend && mypy backend --ignore-missing-imports
```

`ruff` is configured in `pyproject.toml` (line-length 100, target py312). `mypy` is not in strict mode; do not add `# type: ignore` without an explanatory comment.

---

## Coding standards

**`from __future__ import annotations`** on every backend module — keeps annotations as strings for forward-reference compatibility.

**Pydantic v2** for all inter-module data contracts. No raw `dict` in function signatures where a schema exists.

**Async SQLAlchemy 2.0** everywhere. Use `AsyncSession`; never import the synchronous `Session`.

**Fault-tolerant I/O.** Every DB and Redis call in a route handler is wrapped in `try/except` with `logger.warning`. The server must degrade gracefully — never crash on a backing-service failure.

**No mutable module-level state** except the lazy singletons (`_redis_client`, `PluginRegistry`), which are initialised at most once.

**Deterministic object IDs.** The same surface form must always produce the same ID across restarts: `{language}:{type}:{lemma}`, all lowercase, no spaces (e.g. `es:vocab:hola`). Stored `ReviewStateRow` records depend on ID stability.

**Conservative extractions.** Omit rather than guess. A missing learnable object is better than a wrong one.

---

## Adding a language plugin

A plugin is a single Python module in `backend/plugins/` that exports a `create_plugin()` factory function. The loader scans the package at startup and registers every module that has this function — no manual registration step needed.

### Module skeleton

```python
# backend/plugins/french.py
from __future__ import annotations

from backend.schemas.parse import LearnableObject, SentenceResult


class FrenchPlugin:
    language_code = "fr"       # must match the BCP-47 tag used in /parse requests
    display_name  = "French"
    direction     = "ltr"      # or "rtl" for Arabic, Hebrew, etc.

    def __init__(self) -> None:
        # Populated during analyze_sentence; used by get_lesson() as a fallback.
        self._lesson_store: dict[str, LearnableObject] = {}

    def split_sentences(self, text: str) -> list[str]:
        """Return sentence strings in document order."""
        ...

    def analyze_sentence(self, sentence: str) -> SentenceResult:
        """Parse one sentence; return all learnable objects found in it."""
        objects: list[LearnableObject] = []
        # ... build LearnableObject instances, append to objects,
        #     store each in self._lesson_store[obj.id] ...
        return SentenceResult(text=sentence, learnable_objects=objects)

    def get_lesson(self, object_id: str) -> LearnableObject | None:
        """Return the stored object, or None if unknown.

        Called by GET /lesson when the DB row is absent — e.g. on the first
        request after a restart if the DB was unavailable during /parse.
        """
        return self._lesson_store.get(object_id)


def create_plugin() -> FrenchPlugin:
    return FrenchPlugin()
```

### Building a `LearnableObject`

```python
LearnableObject(
    id          = "fr:vocab:maison",   # {lang}:{type}:{canonical_lemma}
    type        = "vocabulary",        # see LearnableType in schemas/parse.py
    label       = "maison",            # surface form shown in the UI pill
    lesson_data = {                    # rendered as a bullet list in the lesson modal;
        "lemma":  "maison",            # any key-value pairs are valid
        "gender": "feminine",
        "pos":    "noun",
    },
    confidence  = 0.80,                # 0–1 heuristic; None if not computed
)
```

`type` must be one of: `vocabulary`, `conjugation`, `agreement`, `idiom`, `grammar`, `nuance`.

### ID rules

- Format: `{language_code}:{type}:{canonical_form}` — lowercase, no spaces.
- Must be **stable**: re-parsing the same text must produce the same ID.
- Drop any lemma that contains a space (spaCy enclitic-fusion artifact); IDs with spaces break the `/lesson` URL route.

### Confidence guidelines

These are communicative heuristics; there is no calibration infrastructure yet.

| Range | Meaning |
|---|---|
| 0.90+ | Morphology complete, unambiguous |
| 0.70–0.89 | Minor uncertainty — OOV token, incomplete morphology |
| 0.50–0.69 | Heuristic inference; parse may be wrong |
| < 0.50 | Omit the object entirely |

### Lazy model loading

Load heavy NLP models with `@cached_property`, not at import time. `create_plugin()` is called eagerly at startup; a model crash at import prevents the whole server from starting.

```python
from functools import cached_property

class FrenchPlugin:
    @cached_property
    def _nlp(self):
        import spacy
        return spacy.load("fr_core_news_sm")
```

Wrap the `spacy.load` call in `try/except OSError` and raise a `RuntimeError` with a human-readable message pointing to the download command. See `SpanishPlugin._nlp` for the pattern.

### Tests

Add `backend/tests/test_french.py`. Minimum coverage:

- Sentence splitting returns the right count and texts.
- Known lemmas appear in `learnable_objects` with the correct type and ID.
- `get_lesson()` returns the stored object after `analyze_sentence` has run.
- A sentence with nothing extractable returns an empty list, not an exception.
- IDs contain no spaces.

Plugin methods are synchronous; no async fixtures are needed for extraction tests.

---

## Frontend

No build step. Edit files under `frontend/` and reload the browser.

| Path | Role |
|---|---|
| `frontend/js/main.js` | App logic, fetch calls, DOM rendering, live-region updates |
| `frontend/components/mnemosyne-pill.js` | Shadow-DOM pill button; dispatches `lesson-open` |
| `frontend/components/mnemosyne-modal.js` | Shadow-DOM lesson dialog with focus trap |
| `frontend/css/global.css` | Design tokens, typography, layout utilities |
| `frontend/css/components.css` | Card and result styles |

Key constraints (see [ARCHITECTURE.md](ARCHITECTURE.md) for rationale):

- Focus rings must be solid — `color-mix(..., transparent)` fails WCAG 2.4.11.
- Status messages use the clear-then-`queueMicrotask`-set pattern to force re-announcement.
- The modal background is made inert (`inert` attribute) on open, restored on close.
- All interactive elements must meet the 44 px / 2.75 rem WCAG 2.5.8 touch target.
- Errors in the review flow go to `role="alert"` (assertive); progress/success to `role="status"` (polite).
