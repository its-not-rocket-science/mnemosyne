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
| `test_api.py` | Route shapes, status codes, error paths | none |
| `test_persistence.py` | DB reads and writes end-to-end | in-memory SQLite |
| `test_knowledge.py` | UserKnowledge, dashboard, review state | in-memory SQLite |
| `test_metrics.py` | GET /metrics endpoint | in-memory SQLite |
| `test_recommend.py` | GET /recommend endpoint | in-memory SQLite |
| `test_difficulty.py` | Difficulty scorer — pure functions | none |
| `test_fsrs.py` | FSRS scheduler — pure functions | none |
| `test_plugin.py` | Plugin registry and loader | none |
| `test_stub_fr.py` | French stub plugin | none |
| `test_spanish_spacy.py` | Spanish NLP extraction | **requires `es_core_news_sm`** |

Skip the spaCy-dependent test when the model is not installed:

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

**`from __future__ import annotations`** on every backend module.

**Pydantic v2** for all inter-module data contracts. No raw `dict` in function signatures where a schema exists.

**Async SQLAlchemy 2.0** everywhere. Use `AsyncSession`; never import the synchronous `Session`.

**Fault-tolerant I/O.** Every DB and Redis call in a route handler is wrapped in `try/except` with `logger.warning`. The server must degrade gracefully, never crash on a backing-service failure.

**No mutable module-level state** except the lazy singletons (`_redis_client`, `PluginRegistry`).

**Deterministic object IDs.** Canonical IDs are UUID-v5 derived from `(language, type, canonical_form)` via `canonical_object_id()` in `backend/parsing/canonical.py`. Never construct IDs directly in a plugin or test. The namespace UUID in that module is fixed; changing it invalidates all stored data.

**Conservative extractions.** Omit rather than guess. A missing learnable object is better than a wrong one.

---

## Adding a language plugin

A plugin is a single Python module in `backend/plugins/` that exports a `create_plugin()` factory. The loader scans the package at startup and registers every module that has this function — no manual registration step needed.

### Module skeleton

```python
# backend/plugins/german.py
from __future__ import annotations

from backend.schemas.parse import CandidateObject, CandidateSentenceResult, RelationHint


class GermanPlugin:
    language_code = "de"       # BCP-47 tag used in /parse requests
    display_name  = "German"
    direction     = "ltr"      # "rtl" for Arabic, Hebrew, etc.

    def __init__(self) -> None:
        # Populated by the parse route after UUID resolution.
        # Used by get_lesson() as a DB-unavailable fallback.
        self.lesson_store: dict[str, CandidateObject] = {}

    def analyze_text(self, text: str) -> list[CandidateSentenceResult]:
        """Parse the full input in one NLP call; return one result per sentence.

        This is the preferred entry point.  The parse route calls this method
        to avoid N+1 NLP invocations.  Implement analyze_sentence as a thin
        wrapper or for test use.
        """
        return [self.analyze_sentence(s) for s in self.split_sentences(text)]

    def split_sentences(self, text: str) -> list[str]:
        """Return sentence strings in document order."""
        ...

    def analyze_sentence(self, sentence: str) -> CandidateSentenceResult:
        """Parse one sentence; return candidate objects with canonical forms."""
        candidates: list[CandidateObject] = []
        # ... build CandidateObject instances and append to candidates ...
        return CandidateSentenceResult(text=sentence, candidates=candidates)

    def get_lesson(self, object_id: str) -> CandidateObject | None:
        """Return the stored candidate object, or None if unknown.

        Called by GET /lesson when the DB row is absent — e.g. on the first
        request after a restart if the DB was unavailable during /parse.
        """
        return self.lesson_store.get(object_id)


def create_plugin() -> GermanPlugin:
    return GermanPlugin()
```

### Building a `CandidateObject`

```python
CandidateObject(
    canonical_form = "Haus",          # stable key within (language, type)
    surface_form   = "Häuser",        # the specific inflected form seen in this text
    type           = "vocabulary",    # see LearnableType in schemas/parse.py
    label          = "Häuser",        # surface form shown in the UI pill
    lesson_data    = {
        "lemma":   "Haus",
        "gender":  "neuter",
        "pos":     "NOUN",
    },
    confidence     = 0.85,            # 0–1 heuristic; None if not computed
    relation_hints = [],              # list[RelationHint] — leave empty for vocabulary
)
```

For a conjugation with a relation to its lemma:

```python
CandidateObject(
    canonical_form = "spielen:present:indicative:1:singular",
    surface_form   = "spiele",
    type           = "conjugation",
    label          = "spiele",
    lesson_data    = { "lemma": "spielen", "tense": "present", ... },
    confidence     = 0.80,
    relation_hints = [
        RelationHint(
            relation_type        = "conjugation_of",
            target_canonical_form = "spielen",
            target_type          = "vocabulary",
        )
    ],
)
```

The parse route derives stable UUIDs via `canonical_object_id(language, type, canonical_form)`. You never construct UUIDs in the plugin. `surface_form` is accumulated into `canonical_objects.surface_forms[]` across parses.

`type` must be one of: `vocabulary`, `conjugation`, `agreement`, `idiom`, `grammar`, `nuance`.

### canonical_form rules

- **Stable**: re-parsing the same text must produce the same `canonical_form`.
- Lowercase, no leading/trailing whitespace.
- Drop any form that contains a space (NLP enclitic-fusion artifact).
- For conjugations, encode the morphological axes: `{lemma}:{tense}:{mood}:{person}:{number}`.
- For agreements, encode the pair: `{modifier_pos_lower}:{modifier_lemma}_{noun_lemma}`.

### surface_form rules

- The specific inflected form seen in this text (e.g. `"gatos"` for canonical `"gato"`).
- Preserve original casing from the source text.
- Set to `None` only when there is genuinely no single surface form (e.g. a multiword expression where the label already encodes the surface).

### Confidence guidelines

These are communicative heuristics; there is no calibration infrastructure yet.

| Range | Meaning |
|---|---|
| 0.90+ | Morphology complete, unambiguous |
| 0.70–0.89 | Minor uncertainty — OOV token, incomplete morphology |
| 0.50–0.69 | Heuristic inference; parse may be wrong |
| < 0.50 | Omit the object entirely |

### Lazy model loading

Load heavy NLP models with `@cached_property`, not at import time. `create_plugin()` is called eagerly at startup; a model crash at import time prevents the whole server from starting.

```python
from functools import cached_property

class GermanPlugin:
    @cached_property
    def _nlp(self):
        try:
            import spacy
            return spacy.load("de_core_news_sm", disable=["ner"])
        except OSError as exc:
            raise RuntimeError(
                "spaCy model 'de_core_news_sm' not found. "
                "Run: python -m spacy download de_core_news_sm"
            ) from exc
```

See `SpanishPlugin._nlp` in `backend/plugins/spanish.py` for the exact pattern.

### Tests

Add `backend/tests/test_german.py`. Minimum coverage:

- Sentence splitting returns the right count and texts.
- Known lemmas appear in `candidates` with the correct `type` and `canonical_form`.
- `get_lesson()` returns `None` for an unknown object_id and the stored object after manual insertion.
- A sentence with nothing extractable returns an empty candidates list, not an exception.
- `canonical_form` contains no spaces.
- `surface_form` is set and non-empty for extracted objects.

Plugin extraction methods are synchronous; no async fixtures needed for unit tests. Integration tests that call `/parse` with the plugin require the `async_client` fixture from `test_persistence.py`.

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
- The modal background is made inert on open, restored on close.
- All interactive elements must meet the 44 px / 2.75 rem WCAG 2.5.8 touch target.
- Errors go to `role="alert"` (assertive); progress/success to `role="status"` (polite).
- Do not use `dir`, `font-family`, or layout assumptions that presuppose Latin script or LTR flow. The `direction` attribute must be applied dynamically from the plugin metadata when rendering text.
