# Architecture

Mnemosyne is a FastAPI backend and a static frontend with no build step. The backend is a single Python process; all NLP work happens synchronously inside the language plugins.

---

## System overview

```
Browser
  └── frontend/
        ├── index.html
        ├── js/main.js               fetch, DOM, live regions
        ├── components/
        │     ├── mnemosyne-pill      shadow-DOM pill button
        │     └── mnemosyne-modal     shadow-DOM lesson dialog
        └── css/

FastAPI (uvicorn)
  ├── POST /parse
  ├── GET  /lesson/{id}
  ├── POST /review
  ├── GET  /health        liveness (process only)
  └── GET  /ready         readiness (DB + Redis)

PostgreSQL   ←  SQLAlchemy 2.0 async + asyncpg
Redis        ←  parse-result cache (fault-tolerant, 1 h TTL)
```

---

## Request flows

### POST /parse

```
1.  SHA-256 cache key ← hash(language + text)
2.  Redis GET cache key
      HIT  → return cached ParseResponse
      MISS or Redis down → continue
3.  registry.get(language) → LanguagePlugin      [404 if unknown]
4.  plugin.split_sentences(text) → list[str]
5.  plugin.analyze_sentence(s) for each sentence → SentenceResult
      plugin stores each LearnableObject in self._lesson_store
6.  Persist to DB (non-fatal — logged, not raised)
      INSERT  parsed_texts
      INSERT  sentences           (one row per sentence, ordered by position)
      UPSERT  learnable_objects   (refresh lesson_data on re-parse)
7.  Redis SET result (1 h TTL, non-fatal)
8.  Return ParseResponse
```

### GET /lesson/{object_id}

```
1.  DB SELECT learnable_objects WHERE id = object_id
      found  → build and return LessonResponse
      not found or DB down → continue
2.  registry.get(language) → LanguagePlugin      [404 if unknown]
3.  plugin.get_lesson(object_id)
      None → 404
4.  Build and return LessonResponse
```

The database row is authoritative when present. The in-session plugin store is the fallback for requests that arrive before the DB has the row (e.g. immediately after a cold-start with a slow first `/parse`).

### POST /review

```
1.  DB GET ReviewStateRow WHERE object_id = ?
      found  → use DB state    (ignores payload.review_state)
      not found or DB down → use payload.review_state (may be None → new card)
2.  fsrs.review(quality, state, now) → (next_interval_days, updated_state)
3.  DB UPSERT ReviewStateRow ← updated_state    (non-fatal)
4.  Return ReviewResponse { object_id, next_interval_days, review_state }
```

The frontend carries the last `review_state` dict in a `Map` keyed by `objectId` and sends it with every review request. The server uses it only when the DB is unreachable, so reviews remain accurate even through a transient DB outage.

---

## Plugin system

### Discovery

At startup `load_plugins()` iterates every module in `PLUGIN_PACKAGE` (`backend.plugins` by default). Any module that exports `create_plugin()` is called; the returned object is registered in a `PluginRegistry` keyed by `plugin.language_code`. A plugin that raises during loading (e.g. missing spaCy model) is skipped with a `WARNING`; the rest of the server starts normally.

### Interface

```python
class LanguagePlugin(Protocol):
    language_code: str      # BCP-47, e.g. "es"
    display_name:  str
    direction:     str      # "ltr" | "rtl"

    def split_sentences(self, text: str) -> list[str]: ...
    def analyze_sentence(self, sentence: str) -> SentenceResult: ...
    def get_lesson(self, object_id: str) -> LearnableObject | None: ...
```

`Protocol` is structural — plugins do not inherit anything. Any class with the right attributes and methods satisfies it.

### Object IDs

Plugins return `CandidateObject` values with a `canonical_form` field (the stable key within a `(language, type)` space — e.g. the lemma for vocabulary, or `{lemma}:{tense}:{mood}:{person}:{number}` for conjugations). The parse route derives a deterministic UUID-v5 from `(language, type, canonical_form)` via `canonical_object_id()` in `backend/parsing/canonical.py`. The same word in any text always maps to the same UUID without a database round-trip.

### Spanish plugin

`backend/plugins/spanish.py` uses `spacy.load("es_core_news_sm", disable=["ner"])` loaded lazily via `@cached_property`.

Each sentence goes through three ordered passes so that conjugation extraction can populate a `seen_vocab` set before vocabulary extraction runs, preventing the same lemma from appearing in both categories:

| Pass | What is extracted | Notes |
|---|---|---|
| **Conjugations** | Finite VERB and AUX tokens | Records tense, mood, person, number, construction (`standalone`, `progressive`, `perfect`, `passive`, `near_future`, `modal`, `copula`), and `is_reflexive`. Adds each lemma to `seen_vocab`. |
| **Vocabulary** | NOUN, ADJ, ADV, non-finite VERB/AUX | Skips lemmas in `seen_vocab`. Silently drops lemmas containing a space (enclitic fusion artifacts from `es_core_news_sm`). |
| **Agreement** | DET+NOUN and ADJ+NOUN pairs | Requires at least one confirmed morphological match (gender or number). Drops pairs with a confirmed mismatch (parse error, not a teaching object). |

---

## FSRS scheduler

`backend/srs/fsrs.py` — pure Python, no I/O, no global state. All functions are deterministic given the same inputs; pass an explicit `now` in tests.

### Public API

```python
def review(
    quality: int,           # 1 Again | 2 Hard | 3 Good | 4 Easy
    state:   dict | None,   # prior CardState.to_dict(), or None for a new card
    now:     datetime | None = None,
) -> tuple[int, dict]:      # (next_interval_days, updated_state_dict)
```

### Memory model

Each card is described by two scalars:

**S (Stability)** — days until recall probability decays to the target (90 %). By construction, R(S, S) = 0.9.

**D (Difficulty)** — intrinsic item hardness ∈ [1, 10]. Higher D → slower stability growth per review.

Forgetting curve (FSRS-5 power law):

```
R(t, S) = (1 + FACTOR × t / S) ^ DECAY
FACTOR = 19/81 ≈ 0.235,  DECAY = −0.5

Verify: R(S, S) = (1 + 19/81)^(−0.5) = (100/81)^(−0.5) = 9/10 ✓
```

### Update logic

```
review(quality, state, now)
  │
  ├─ CardState.from_dict(state)   or   default_state(now)   for new cards
  ├─ R  ←  retrievability(card, now)       # P(recall) right now
  ├─ D' ←  _next_difficulty(D, quality, reviews)
  │          first review → INITIAL_DIFFICULTY[quality]
  │          later        → drift by DIFFICULTY_DELTA × (3 − quality),
  │                         then 10 % mean-reversion toward 5.0
  ├─ S' ←  _next_stability(S, D', R, quality, reviews)
  │          reviews == 0 → INITIAL_STABILITY[quality]
  │          quality >= 2 → stability_after_recall(S, D', R, quality)
  │          quality == 1 → stability_after_lapse(S, D', R)
  └─ interval ← next_interval(S')    # ≈ S' days, always ≥ 1
```

`CardState` is a `frozen=True` dataclass. Every `review()` call returns a **new** object; nothing is mutated.

The implementation follows FSRS-5 defaults closely but is not an exact reproduction. Per-user or per-deck parameter fitting is not implemented.

---

## Persistence

### Schema

```
parsed_texts
  id (uuid), language, source_text, source_url, created_at

  sentences  (FK → parsed_texts, cascade delete)
    id, parsed_text_id, position, text

canonical_objects                             PRIMARY KEY: deterministic UUID-v5
  id           uuid string   canonical_object_id(language, type, canonical_form)
  language, type, canonical_form             UNIQUE together
  display_label, lesson_data JSON, confidence float | null
  created_at, updated_at

object_relations
  source_id FK → canonical_objects
  target_id FK → canonical_objects
  relation_type   e.g. "conjugation_of", "agreement_of"
  UNIQUE (source_id, target_id, relation_type)

sentence_objects   (join table)
  sentence_id FK → sentences   PRIMARY KEY (composite)
  object_id   FK → canonical_objects
  position    int

review_states
  object_id   string   PRIMARY KEY   — intentionally no FK to canonical_objects
  state       JSON     CardState serialised via to_dict()
  updated_at
```

`review_states.object_id` has no foreign key constraint. This lets a review be submitted for an object that pre-dates the current server session, without cascading failure.

### Migrations

`Base.metadata.create_all` runs at startup for fresh deployments. For existing databases run `alembic upgrade head`. Migration `0001_canonical_object_graph` creates the new tables and data-migrates the old `learnable_objects` rows (string PKs) to `canonical_objects` (UUID PKs) by recomputing IDs with `canonical_object_id()`.

### Fault tolerance

Every DB and Redis operation in the route handlers is wrapped in `try/except`. Failures are logged at `WARNING` and the request continues:

| Failure point | Degraded behaviour |
|---|---|
| Redis read (parse) | Proceeds without cache |
| Redis write (parse) | Result returned, not cached |
| DB write (parse) | Objects not persisted; result still returned |
| DB read (lesson) | Falls back to plugin in-session store |
| DB read/write (review) | FSRS runs stateless; interval returned, state not saved |

---

## Frontend

Three CSS layers and two Web Components; no build step, no framework.

**`global.css`** — design tokens (`--accent`, `--muted`, `--error-color`, etc.), typography, `.sr-only`, `.skip-link`.

**`components.css`** — sentence cards, pill list, empty-state styles, markdown content.

**`mnemosyne-pill`** (shadow DOM, `delegatesFocus: true`) — button per learnable object. Emits `lesson-open` as a composed, bubbling `CustomEvent` so it crosses the shadow boundary and reaches the delegated listener in `main.js`.

**`mnemosyne-modal`** (shadow DOM) — lesson dialog. On `open()`: renders content, inerts all sibling `<body>` children so background content is unreachable to AT and keyboard, then focuses `[role="dialog"]` so the screen reader announces "dialog, *title*". On `close()`: removes `inert`, renders the empty-state template, returns focus to `previouslyFocused`.

### Live-region strategy

| Scenario | Region | ARIA role |
|---|---|---|
| Parse progress, sentence count, lesson title | `#status` in `main.js` | `role="status"` (polite) |
| Review save progress and success | `.status` in modal shadow | `role="status"` (polite) |
| Review save error | `.status-error` in modal shadow | `role="alert"` (assertive) |

All live regions use the **clear-then-set** pattern (`textContent = ''` then `queueMicrotask(...)`) to guarantee re-announcement even when the new message text is identical to the old one.

### Accessibility invariants

- Focus rings are solid, not semi-transparent — `color-mix(..., transparent)` fails the WCAG 2.4.11 3:1 non-text contrast requirement against adjacent colours.
- All interactive elements have `min-block-size: 2.75rem` (≈ 44 CSS px) per WCAG 2.5.8.
- Error colour tokens (`--error-color`) have separate light-mode and dark-mode values set in a `@media (prefers-color-scheme: dark)` block to maintain contrast in both schemes.
- `prefers-reduced-motion` suppresses the `.status` colour transition.
