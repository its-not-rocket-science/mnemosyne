# Architecture

Mnemosyne is a FastAPI backend and a static frontend with no build step. The backend is a single Python process; all NLP work happens synchronously inside the language plugins, loaded once per process.

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
  ├── POST /ingest                     rich ingest with source-document tracking (preferred)
  ├── POST /parse                      legacy ingest (backward compat)
  ├── POST /parse/jobs                 async job submission (all text sizes)
  ├── GET  /parse/jobs/{id}            job status polling
  ├── GET  /parse/jobs/{id}/events     SSE progress stream
  ├── GET  /lesson/{id}
  ├── POST /review
  ├── GET  /dashboard
  ├── GET  /metrics
  ├── GET  /recommend                  (alias: /recommend-text)
  ├── GET  /reading/{id}               source progression state
  ├── PATCH /reading/{id}              advance reading position
  ├── GET  /languages
  ├── POST /translate
  ├── POST /auth/register
  ├── POST /auth/login
  ├── GET  /users/me
  ├── DELETE /users/me
  ├── GET  /users/me/export
  ├── GET/PATCH /users/me/fsrs-params
  ├── POST /users/me/calibrate
  ├── GET/PATCH /users/me/language-preferences
  ├── GET  /health             liveness (process only)
  └── GET  /ready              readiness (DB + Redis + plugins)

PostgreSQL   ←  SQLAlchemy 2.0 async + asyncpg
Redis        ←  parse-result cache (fault-tolerant, 1 h TTL)
```

---

## Request flows

### POST /parse

```
1.  SHA-256 cache key ← hash(language + text)
2.  Redis GET cache key
      HIT  → return cached ParseResponse (NLP skipped entirely)
      MISS or Redis down → continue
3.  registry.get(language) → LanguagePlugin      [404 if unknown]
4.  plugin.analyze_text(text) → list[CandidateSentenceResult]
      Single spaCy call; iterates doc.sents internally.
      Each CandidateSentenceResult carries a list of CandidateObjects.
5.  For each CandidateObject:
        canonical_object_id(language, type, canonical_form) → UUID-v5
        Build LearnableObject for response
        Store CandidateObject in plugin.lesson_store[uuid] (DB fallback)
6.  Persist to DB (non-fatal — logged at WARNING, not raised)
        INSERT  parsed_texts
        INSERT  sentences               (one row per sentence, ordered by position)
        UPSERT  canonical_objects       (update display_label, lesson_data, confidence,
                                         accumulate surface_forms on re-parse)
        UPSERT  user_knowledge          (seed total_reviews=0 for new objects;
                                         update last_seen for existing)
        INSERT  sentence_objects        (join table)
        UPSERT  object_relations        (batched: one IN query per parse)
7.  Build ParseResponse; fire Redis SET as background task (asyncio.ensure_future)
8.  Return ParseResponse
```

### GET /lesson/{object_id}

```
1.  DB SELECT canonical_objects WHERE id = object_id
      found  → build and return LessonResponse
      not found or DB down → continue
2.  registry.get(language) → LanguagePlugin      [404 if unknown]
3.  plugin.get_lesson(object_id) → CandidateObject | None
      None → 404
4.  Build and return LessonResponse
```

The database row is authoritative when present. The in-session plugin store is the fallback for requests that arrive before the DB has written the row (e.g. the first request after a cold start with a slow `/parse`).

### POST /review

```
1.  DB SELECT user_knowledge WHERE user_id = 'default' AND object_id = ?
      found  → use DB fsrs_state as prior  (ignores payload.review_state)
      not found or DB down → use payload.review_state (may be None → new card)
2.  fsrs.review(quality, state, now) → (next_interval_days, updated_state)
3.  mastery_score ← retrievability(card, now)
4.  DB UPSERT user_knowledge ← updated_state, mastery_score, due_at  (non-fatal)
5.  Return ReviewResponse { object_id, next_interval_days, review_state }
```

### GET /dashboard

Loads all `user_knowledge` rows for the default user (optionally filtered by `?language=`), classifies each with `classify(total_reviews, fsrs_state, now)`, and buckets into `known` / `weak` / `new` / `due_for_review`.

### GET /metrics

Queries `user_knowledge` LEFT JOIN `canonical_objects` for type information, and `review_events` for historical figures. Computes in Python:
- overall retention, success rate, average FSRS stability
- per-language and per-type breakdowns
- weakest-10 reviewed objects (lowest `mastery_score`)
- `reviews_today`, `streak_days`, `daily_activity` from `review_events`

### GET /recommend (and /recommend-text)

```
1.  Load all user_knowledge for default user → mastery dict
2.  total_mastered → target_difficulty_window(total_mastered)
3.  4-way join: Sentence → ParsedText → SentenceObjectRow → CanonicalObjectRow
    filtered by language
4.  Group objects by sentence in Python; score each sentence
5.  Deduplicate identical sentence texts (re-parses create multiple DB rows)
6.  Filter to target window; fall back to closest-to-centre if window is empty
7.  Sort by closeness to window centre; return up to limit results
```

---

## Plugin system

### Discovery

At startup `load_plugins()` iterates every module in `PLUGIN_PACKAGE` (`backend.plugins` by default). Any module that exports `create_plugin()` is called; the returned object is registered in a `PluginRegistry` keyed by `plugin.language_code`. If `ENABLED_LANGUAGES` is set, only matching codes are registered. A plugin that raises during loading is skipped with a `WARNING`; the rest of the server starts normally.

### Interface

```python
class LanguagePlugin(Protocol):
    language_code: str               # BCP-47, e.g. "es"
    display_name:  str
    direction:     str               # "ltr" | "rtl" (kept for compat; mirrors capabilities)
    capabilities:  LanguageCapabilities   # full capability metadata — see below
    lesson_store:  dict[str, CandidateObject]

    def analyze_text(self, text: str) -> list[CandidateSentenceResult]:
        """Parse the full input in one NLP call; return one result per sentence.
        Preferred entry point — avoids N+1 NLP invocations."""
        ...

    def split_sentences(self, text: str) -> list[str]: ...

    def analyze_sentence(self, sentence: str) -> CandidateSentenceResult:
        """Single-sentence fallback; used in tests and tooling."""
        ...

    def get_lesson(self, object_id: str) -> CandidateObject | None: ...
```

`Protocol` is structural — plugins do not inherit anything. `analyze_text` is the required hot path; `analyze_sentence` is kept for tests and direct tooling use.

### Language capabilities

Every plugin declares a `capabilities: LanguageCapabilities` class attribute (from `backend/schemas/language.py`). The registry exposes it through `supported_languages()` and `GET /languages` returns the full object. The lesson route uses `best_lesson_mode(capabilities.lesson_modes_supported)` to select the appropriate lesson template.

```python
LanguageCapabilities(
    code="es",
    display_name="Spanish",
    direction="ltr",                         # "ltr" | "rtl"
    script_family="latin",                   # latin | arabic | hebrew | cjk | devanagari | cyrillic | other
    tokenization_mode="whitespace",          # whitespace | segmented | character
    morphology_depth="rich",                 # none | shallow | rich
    lesson_modes_supported=["morphology", "vocabulary"],  # richest first
)
```

The lesson builder dispatches based on the richest supported mode:
- `"morphology"` — full conjugation/agreement/tense drills (Spanish, French, German, Russian, Japanese, Portuguese, Italian)
- `"vocabulary"` — lemma + POS only; no morphological drills (English stub)
- `"dictionary"` — word + gloss only (Arabic, Hebrew, Chinese, Latin, Koine Greek)

The difficulty scorer's `score_sentence()` accepts an optional `word_count_hint: int` for languages where `text.split()` is meaningless (CJK, Thai). Pass this from plugin-derived token counts when available.

### Object IDs

Plugins return `CandidateObject` with a `canonical_form` field (the stable key within a `(language, type)` space — the lemma for vocabulary, or `{lemma}:{tense}:{mood}:{person}:{number}` for conjugations). The parse route derives a deterministic UUID-v5 via:

```python
# backend/parsing/canonical.py
_NAMESPACE = uuid.UUID("12e3d947-f3c4-4e2b-a9a1-0d3c2e1f5b7a")

def canonical_object_id(language, type_, canonical_form) -> str:
    key = f"{language}\x00{type_}\x00{canonical_form}"
    return str(uuid.uuid5(_NAMESPACE, key))
```

Null-byte separators prevent collisions between keys like `("es", "voc", "ab:cd")` and `("es", "vocab", "cd")`. The namespace UUID is fixed and must never change — altering it invalidates all stored UUIDs.

### Spanish plugin

`backend/plugins/spanish.py` uses `spacy.load("es_core_news_sm", disable=["ner"])` loaded lazily via `@cached_property` — one load per process, never reloaded.

`analyze_text` calls `self._nlp(text)` once. The returned `doc` is segmented by spaCy's sentencizer; each `sent` is passed to `_analyze_tokens` which runs three ordered passes:

| Pass | What is extracted | Notes |
|------|-------------------|-------|
| **Conjugations** | Finite VERB and AUX tokens | Tense, mood, person, number, construction type, `is_reflexive`. Adds each lemma to `seen_vocab`. |
| **Vocabulary** | NOUN, ADJ, ADV, non-finite VERB/AUX | Skips lemmas in `seen_vocab`. Drops multi-word lemmas (spaCy enclitic fusion artifacts). |
| **Agreement** | DET+NOUN and ADJ+NOUN pairs | Requires at least one confirmed morphological match. Drops confirmed mismatches. |

Conjugation runs first so verb lemmas are excluded from vocabulary — preventing duplicates when a conjugated form and its infinitive both appear.

---

## Difficulty scoring

`backend/difficulty/scorer.py` — pure Python, no I/O.

### Sentence score

```
difficulty = 0.55 × unknown_ratio
           + 0.25 × grammar_score
           + 0.20 × length_score

unknown_ratio  fraction of objects with mastery_score < 0.30
grammar_score  (conjugation_count/total)×0.70 + (agreement_count/total)×0.30
length_score   min(word_count / 25, 1.0)
```

### Difficulty labels

| Label | Condition |
|-------|-----------|
| `easy` | unknown_ratio < 0.15 (> 85% known) |
| `ideal` | 0.15 ≤ unknown_ratio ≤ 0.40 (60–85% known) — the i+1 zone |
| `hard` | unknown_ratio > 0.40 (< 60% known) |

### Progression window

The target difficulty window adapts to the user's mastery count:

- **Bootstrap** (< 5 mastered): `[0.50, 0.75]` — all objects are unknown, so only grammar and length vary; selects short, simple sentences.
- **Active** (5–100 mastered): window centre shifts from 0.15 to 0.40 as mastery grows, following the i+1 principle.
- **Saturated** (> 100 mastered): window stops moving at `[0.28, 0.52]`.

---

## FSRS scheduler

`backend/srs/fsrs.py` — pure Python, no I/O, no global state.

### Public API

```python
def review(
    quality: int,           # 1 Again | 2 Hard | 3 Good | 4 Easy
    state:   dict | None,   # prior CardState.to_dict(), or None for a new card
    now:     datetime | None = None,
) -> tuple[int, dict]:      # (next_interval_days, updated_state_dict)
```

### Memory model

**S (Stability)** — days until recall probability decays to 90%. R(S, S) = 0.9 by construction.

**D (Difficulty)** — intrinsic item hardness ∈ [1, 10]. Higher D → slower stability growth.

Forgetting curve (FSRS-5 power law):
```
R(t, S) = (1 + FACTOR × t / S) ^ DECAY
FACTOR = 19/81 ≈ 0.235,  DECAY = −0.5
```

`CardState` is `frozen=True`. Every `review()` call returns a **new** object; nothing is mutated. Pass an explicit `now` in tests for deterministic results.

This implementation follows FSRS-5 defaults but is not an exact reproduction. Per-user parameter fitting is implemented via `POST /users/me/calibrate`: bias-correction over `ReviewEventRow` history updates `UserFsrsParamsRow`; subsequent reviews use the calibrated `desired_retention`.

---

## Knowledge classification

`backend/srs/knowledge.py` — pure Python, no I/O.

| Status | Condition |
|--------|-----------|
| `new` | `total_reviews == 0` |
| `learning` | reviewed; mastery_score ≥ 0.30 but below mastery threshold |
| `forgotten` | reviewed; mastery_score < 0.30 (was known, now decayed) |
| `mastered` | mastery_score ≥ 0.80 AND total_reviews ≥ 3 |

`mastery_score` is the FSRS retrievability R(t, S) evaluated at the current time — the probability the learner can recall the item right now.

---

## Persistence

### Schema

```
parsed_texts
  id (uuid), language, source_text, source_url, created_at

  sentences  (FK → parsed_texts, cascade delete)
    id, parsed_text_id, position, text

canonical_objects                             PRIMARY KEY: deterministic UUID-v5
  id           deterministic UUID-v5 from (language, type, canonical_form)
  language, type, canonical_form             UNIQUE together
  display_label, surface_forms JSON []
  lesson_data JSON {}, confidence float | null
  created_at, updated_at

object_relations
  source_id FK → canonical_objects
  target_id FK → canonical_objects
  relation_type   "conjugation_of" | "agreement_of" | "related_to"
  UNIQUE (source_id, target_id, relation_type)

sentence_objects   (join table)
  sentence_id FK → sentences   PRIMARY KEY (composite)
  object_id   FK → canonical_objects
  position    int

user_knowledge                     PRIMARY KEY: (user_id, object_id)
  user_id     string
  object_id   string              — intentionally no FK to canonical_objects
  language    string | null
  fsrs_state  JSON | null         CardState serialised via to_dict()
  mastery_score float             current FSRS retrievability
  first_seen  datetime | null     set on first INSERT, never updated
  last_seen   datetime            updated on every /parse encounter
  total_reviews int
  due_at      datetime            mirrors fsrs_state["due_at"] for indexed queries

review_events                      append-only; never updated
  id (uuid), user_id, object_id, language
  quality int, mastery_score_before float, mastery_score_after float
  reviewed_at datetime

users
  id (uuid), email, hashed_password, created_at

user_language_preferences
  user_id, language                PRIMARY KEY (composite)
  created_at

user_fsrs_params
  user_id                          PRIMARY KEY
  desired_retention float, params JSON
  updated_at

source_documents
  id (uuid), language, content_type, title, author, source_url, filename
  char_count int, script_hint str | null, created_at

  source_chunks  (FK → source_documents)
    id (uuid), source_document_id, parsed_text_id
    chunk_index int, char_start int, char_end int

source_progression               PRIMARY KEY: (user_id, source_document_id)
  user_id, source_document_id
  next_position int, sentences_total int
  avg_comprehension float, completion_fraction float
  updated_at
```

`user_knowledge.object_id` has no FK constraint intentionally — reviews can be submitted for objects absent from `canonical_objects` during a DB outage.

### Migrations

Nine Alembic revision files (all in `alembic/versions/`):

| Revision | Content |
|----------|---------|
| `0000_baseline` | Initial `parsed_texts`, `sentences`, `user_knowledge` tables |
| `0001_canonical_object_graph` | `canonical_objects`, `object_relations`, `sentence_objects`; UUID-v5 PK migration |
| `0002_surface_forms` | Adds `surface_forms JSON []` to `canonical_objects` |
| `0003_first_seen` | Adds `first_seen datetime` to `user_knowledge` |
| `0004_users_auth` | `users` table; JWT auth support |
| `0005_user_language_prefs` | `user_language_preferences`, `user_fsrs_params` |
| `0006_review_events` | `review_events` append-only table |
| `0007_source_documents` | `source_documents`, `source_chunks`, `source_progression` |
| `0008_jsonb_key_removal` | Casts `lesson_data`/`fsrs_state` from JSON → jsonb for key-removal operators |

Startup runs `alembic upgrade head` in a subprocess. `Base.metadata.create_all` is not called in production.

### Fault tolerance

| Failure point | Degraded behaviour |
|---|---|
| Redis read (parse) | Proceeds without cache |
| Redis write (parse) | Result returned, not cached |
| DB write (parse) | Objects not persisted; result still returned |
| DB read (lesson) | Falls back to plugin in-session store |
| DB read/write (review) | FSRS runs stateless; interval returned, state not saved |
| DB read (dashboard / metrics) | Returns HTTP 503 with error detail |

---

## Frontend

Three CSS layers and two Web Components; no build step, no framework.

**`global.css`** — design tokens (`--accent`, `--muted`, `--error-color`, etc.), typography, `.sr-only`, `.skip-link`.

**`components.css`** — sentence cards, pill list, empty-state styles, markdown content.

**`mnemosyne-pill`** (shadow DOM, `delegatesFocus: true`) — button per learnable object. Emits `lesson-open` as a composed, bubbling `CustomEvent` so it crosses the shadow boundary.

**`mnemosyne-modal`** (shadow DOM) — lesson dialog. On `open()`: renders content, sets `inert` on all sibling `<body>` children, focuses `[role="dialog"]`. On `close()`: removes `inert`, restores focus.

### Live-region strategy

| Scenario | Region | ARIA role |
|---|---|---|
| Parse progress, sentence count | `#status` in `main.js` | `role="status"` (polite) |
| Review save progress / success | `.status` in modal shadow | `role="status"` (polite) |
| Review save error | `.status-error` in modal shadow | `role="alert"` (assertive) |

All live regions use the **clear-then-set** pattern (`textContent = ''` then `queueMicrotask(...)`) to guarantee re-announcement even when the new text is identical.

### Accessibility invariants

- Focus rings are solid — `color-mix(..., transparent)` fails WCAG 2.4.11 non-text contrast.
- All interactive elements: `min-block-size: 2.75rem` (≈ 44 CSS px) per WCAG 2.5.8.
- `--error-color` has separate light-mode and dark-mode values for contrast in both schemes.
- `prefers-reduced-motion` suppresses the `.status` colour transition.

### Multilingual frontend status

`dir` and `lang` attributes are applied dynamically from plugin capabilities to sentence cards, pill lists, modal title, example text, drill prompts, and fill-blank inputs. `<bdi>` elements isolate bidirectional strings in feedback. Logical CSS properties are used throughout. Non-Latin font stacks declared in `global.css`. RTL tested with Arabic and Hebrew fixtures; 43 non-Latin DB round-trip tests pass.

**Remaining limitation:** lesson explanations (`build_lesson()` output) are always English prose regardless of target language.
