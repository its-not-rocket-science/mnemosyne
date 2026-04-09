# Architecture

Mnemosyne is a FastAPI backend + static frontend. There is no build step on the frontend. The backend is a single Python process; all heavy work happens synchronously inside the language plugins.

---

## Components

```
Browser
  └── frontend/          Vanilla JS, Web Components, no framework
        ├── main.js      Fetch calls, DOM rendering, status live regions
        ├── mnemosyne-pill.js    Shadow-DOM button; dispatches lesson-open
        └── mnemosyne-modal.js  Dialog with focus trap, inert background

FastAPI app (uvicorn)
  ├── POST /parse        Parse text → sentences + learnable objects
  ├── GET  /lesson/:id   Fetch lesson content for one learnable object
  ├── POST /review       Submit a recall rating; persist FSRS state
  ├── GET  /health       Liveness probe (process only)
  └── GET  /ready        Readiness probe (DB + Redis)

PostgreSQL             Persistence (SQLAlchemy 2.0 async, asyncpg)
Redis                  Parse result cache (fault-tolerant, 1 h TTL)
```

---

## Request flows

### POST /parse

```
1.  Compute SHA-256 cache key over (language + text).
2.  GET cache key from Redis.
        HIT  → return cached ParseResponse immediately.
        MISS or Redis down → continue.
3.  registry.get(language) → LanguagePlugin instance.
        Unknown language → 404.
4.  plugin.split_sentences(text) → list[str].
5.  plugin.analyze_sentence(s) for each sentence → SentenceResult.
        Extracts vocabulary, conjugation, agreement, etc.
        Stores each LearnableObject in the plugin's _lesson_store.
6.  Persist to DB (fault-tolerant — failure is logged, not raised):
        INSERT parsed_texts
        INSERT sentences (one per sentence, ordered by position)
        UPSERT learnable_objects (refresh lesson_data on re-parse)
7.  SET Redis cache (1 h TTL, fault-tolerant).
8.  Return ParseResponse.
```

### GET /lesson/{object_id}

```
1.  SELECT learnable_objects WHERE id = object_id.
        Found → build LessonResponse from DB row.
        DB down or row absent → continue.
2.  registry.get(language) → LanguagePlugin.
3.  plugin.get_lesson(object_id) → LearnableObject | None.
        None → 404.
4.  Build and return LessonResponse.
```

The DB is authoritative when the row exists. The plugin fallback handles the case where the app has restarted and the DB was not available during the originating parse.

### POST /review

```
1.  Load prior FSRS state from DB (ReviewStateRow WHERE object_id = ?).
        DB down or first review for this object → use payload.review_state (may be None).
2.  fsrs.review(quality, state) → (next_interval_days, updated_state).
3.  UPSERT ReviewStateRow with updated_state.
4.  Return ReviewResponse { object_id, next_interval_days, review_state }.
```

The frontend keeps the last `review_state` in memory per session (`reviewStateByObject` Map) and sends it in the request body. The server ignores it if a DB row is present, uses it as a fallback if not. This means reviews work even if the DB was unavailable during the originating parse.

---

## Plugin system

### Discovery

At startup, `load_plugins()` scans every module in `PLUGIN_PACKAGE` (`backend.plugins` by default). For each module that exports a `create_plugin()` function, it calls the factory and registers the returned object in a `PluginRegistry` keyed by `plugin.language_code`.

A plugin that fails to load (e.g. missing spaCy model) is skipped with a warning — it does not prevent the server from starting.

### Interface

```python
class LanguagePlugin(Protocol):
    language_code: str      # BCP-47 tag: "es", "fr", "de", …
    display_name: str
    direction: str          # "ltr" or "rtl"

    def split_sentences(self, text: str) -> list[str]: ...
    def analyze_sentence(self, sentence: str) -> SentenceResult: ...
    def get_lesson(self, object_id: str) -> LearnableObject | None: ...
```

This is a structural (`Protocol`) interface — no base class to inherit. Any object with the right attributes and methods satisfies it.

### Object IDs

IDs are deterministic strings constructed by the plugin: `{language_code}:{type}:{canonical_form}`, e.g. `es:vocab:hola`, `es:conj:hablar`. The same text must always produce the same IDs across server restarts so that stored `ReviewStateRow` records remain valid.

### Spanish plugin (`backend/plugins/spanish.py`)

Uses `spacy.load("es_core_news_sm")` with NER disabled. The model is loaded lazily via `cached_property` — the first call to `analyze_sentence` triggers it.

Three extraction passes per sentence (in this order to enable cross-deduplication):

1. **Conjugations** — finite VERB and AUX tokens. Each entry records tense, mood, person, number, construction type (`standalone`, `progressive`, `perfect`, `passive`, `near_future`, `modal`, `copula`), and whether a reflexive clitic is present. The lemma is added to a `seen_vocab` set.
2. **Vocabulary** — open-class tokens (NOUN, ADJ, ADV, non-finite VERB/AUX). Tokens whose lemma is in `seen_vocab` are skipped (avoids duplicating a verb as both conjugation and vocabulary). Lemmas containing spaces are silently dropped (enclitic fusion artifacts).
3. **Agreement** — DET+NOUN and ADJ+NOUN pairs with at least one confirmed morphological match (gender or number). Pairs with a confirmed mismatch are dropped (they indicate a parse error, not a valid teaching object).

---

## FSRS scheduler (`backend/srs/fsrs.py`)

All scheduling is pure Python, no I/O, no global state. The public API is a single function:

```python
def review(
    quality: int,              # 1 (Again) | 2 (Hard) | 3 (Good) | 4 (Easy)
    state: dict | None,        # prior CardState.to_dict(), or None for new cards
    now: datetime | None,      # defaults to utcnow(); pass explicit value in tests
) -> tuple[int, dict]:         # (next_interval_days, updated_state_dict)
```

### Memory model

Two scalar parameters describe each card:

- **S (Stability)** — days until recall probability decays to the target (90 %). By definition, R(S, S) = 0.9.
- **D (Difficulty)** — intrinsic item hardness ∈ [1, 10]. Higher D → slower stability growth.

Forgetting curve (FSRS-5 power law):

```
R(t, S) = (1 + FACTOR × t / S) ^ DECAY
FACTOR = 19/81 ≈ 0.235,  DECAY = −0.5
Verify: R(S, S) = (1 + 19/81) ^ (−0.5) = (100/81)^(−0.5) = 9/10 = 0.9 ✓
```

### Update logic

```
review(quality, state, now)
  │
  ├─ Deserialize state → CardState (or default_state() for new cards)
  ├─ R = retrievability(card, now)        # current recall probability
  ├─ D' = _next_difficulty(D, quality)    # drift toward neutral (5.0)
  ├─ S' = _next_stability(S, D', R, quality)
  │     ├─ first review  → INITIAL_STABILITY[quality]
  │     ├─ quality ≥ 2   → stability_after_recall(S, D', R, quality)
  │     └─ quality == 1  → stability_after_lapse(S, D', R)
  └─ interval = next_interval(S')         # ≈ S' days, always ≥ 1
```

`CardState` is a frozen dataclass. Every review returns a new object; nothing is mutated in place.

### Parameters

All coefficients are named constants with docstrings rather than an opaque weight vector. The implementation closely follows FSRS-5 defaults but is not an exact reproduction; per-user parameter fitting is not yet implemented.

---

## Persistence

### Tables

```
parsed_texts
  id, language, source_text, source_url, created_at

  sentences (FK → parsed_texts)
    id, parsed_text_id, position, text

learnable_objects
  id (plugin-generated, e.g. "es:vocab:hola")
  language, type, label, lesson_data (JSON), confidence, created_at
  — upserted on every /parse; lesson_data stays current with the plugin

review_states
  object_id (no FK — reviews survive object re-creation)
  state (JSON CardState), updated_at
```

`review_states.object_id` intentionally has no foreign key to `learnable_objects`. This means a review can be submitted for an object that was parsed in a previous deployment of the plugin, even if the object row was deleted or never existed in the current DB.

### Migrations

Tables are created at startup with `Base.metadata.create_all`. This is fine for development and for fresh deployments. For a production deploy with existing data, replace the `create_all` call with `alembic upgrade head` (Alembic setup is planned for Phase 1).

### Fault tolerance

Every DB and Redis call in the route handlers is wrapped in `try/except`. Failures are logged at `WARNING` level and the request continues with degraded behaviour:

| Failure | Behaviour |
|---|---|
| Redis unavailable on read | Parse proceeds without cache |
| Redis unavailable on write | Result returned uncached |
| DB unavailable on parse | Objects not persisted; result still returned |
| DB unavailable on lesson | Falls back to plugin in-session store |
| DB unavailable on review | FSRS runs; result returned but state not saved |

---

## Frontend

Three layers, no build step:

- **`global.css`** — design tokens (`--accent`, `--muted`, etc.), base typography, layout utilities
- **`components.css`** — card and result styles that live in the light DOM
- **`mnemosyne-pill`** (shadow DOM) — per-word button. Emits `lesson-open` (bubbles, `composed: true`) which crosses the shadow boundary and reaches the light-DOM delegate in `main.js`.
- **`mnemosyne-modal`** (shadow DOM) — lesson dialog. On open: inerts all sibling body elements (background inaccessible to AT), focuses the `[role="dialog"]` container, installs keyboard trap. On close: restores inert, returns focus to the originating pill.

### Accessibility constraints

- Focus rings are solid (not semi-transparent) — `color-mix(..., transparent)` fails WCAG 2.4.11 3:1 non-text contrast.
- Status messages use the clear-then-set pattern (`textContent = ''` then `queueMicrotask(() => { ... })`) to force re-announcement even when the text is unchanged.
- Rating errors go to a `role="alert"` region (assertive); progress and success go to `role="status"` (polite).
- Pills use `delegatesFocus: true` so that returning focus to the host element delegates into the shadow button.
- All interactive elements meet the 44 px / 2.75 rem WCAG 2.5.8 touch target minimum.
