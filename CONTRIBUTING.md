# Contributing to Mnemosyne

## Prerequisites

| Tool | Minimum version |
|---|---|
| Python | 3.12 |
| Poetry | 2.x |
| Docker + Compose v2 | any recent |
| spaCy models | See below — only models for languages you want to test |

**spaCy model download commands:**

```bash
# Full morphological plugins (each model ~12–50 MB):
python -m spacy download es_core_news_sm   # Spanish
python -m spacy download fr_core_news_sm   # French
python -m spacy download de_core_news_sm   # German
python -m spacy download ru_core_news_sm   # Russian
python -m spacy download ja_core_news_sm   # Japanese  (also: pip install sudachipy sudachidict-small)
python -m spacy download pt_core_news_sm   # Portuguese
python -m spacy download it_core_news_sm   # Italian
python -m spacy download fi_core_news_sm   # Finnish

# Dictionary-mode plugins — no spaCy model needed:
# Arabic, Hebrew, Chinese (jieba), Latin, Koine Greek
# Morphology-light (suffix rules, no model needed): Hindi, Turkish, Korean
```

Tests that require a model are auto-skipped when the model is not installed.

---

## Setup

### Local

```bash
poetry install
python -m spacy download es_core_news_sm
cp .env.example .env
# Edit .env — minimum changes for local dev:
#   DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/mnemosyne
#   REDIS_URL=redis://localhost:6379/0
#   JWT_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")
make dev                       # uvicorn --reload on :8000
python -m http.server 8080 -d frontend
```

### Docker

```bash
cp .env.example .env
# Set a strong JWT_SECRET before starting:
#   Linux/macOS: sed -i "s/CHANGE_ME_IN_PRODUCTION/$(python -c "import secrets; print(secrets.token_hex(32))")/" .env
#   PowerShell:  (see below)
make build && make up
make ready                     # should print {"status": "ready", ...}
```

`./backend` and `./frontend` are bind-mounted into the container. Uvicorn reloads on backend saves; refresh the browser for frontend changes.

PowerShell:

```powershell
Copy-Item .env.example .env
# Generate a strong JWT secret and write it to .env:
$secret = -join ((65..90)+(97..122)+(48..57) | Get-Random -Count 32 | ForEach-Object {[char]$_})
(Get-Content .env) -replace 'CHANGE_ME_IN_PRODUCTION', $secret | Set-Content .env
docker compose build
docker compose up -d
# Verify the stack is ready:
Invoke-RestMethod http://localhost:8000/ready | ConvertTo-Json
```

### Local Windows

```powershell
poetry install
python -m spacy download es_core_news_sm
Copy-Item .env.example .env
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Windows-specific notes:
- Use [Memurai](https://www.memurai.com/) for a native Redis or start Redis via `docker compose up redis -d`.
- The `DATABASE_URL` must use `localhost`, not the Compose service name `postgres`, when running the app outside Docker.
- The `alembic upgrade head` startup migration runs in a subprocess; `alembic` must be on `PATH` (installed by `poetry install`).

---

## Required environment variables

Copy `.env.example` to `.env` and set at minimum:

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | yes | `postgresql+asyncpg://user:pass@host:5432/db` |
| `REDIS_URL` | yes | `redis://host:6379/0` |
| `JWT_SECRET` | **yes in prod** | Long random hex string — see setup above |
| `CORS_ORIGINS` | **yes in prod** | JSON array, e.g. `["https://yourapp.example.com"]` — wildcards rejected when `DEBUG=false` |
| `DEBUG` | no | Default `true`; set `false` in any deployed environment |
| `MAX_PARSE_CHARS` | no | Default `10000` |
| `RATE_LIMIT_PARSE` | no | Default `20/minute` |
| `SENTRY_DSN` | no | Leave empty to disable error monitoring |
| `ENABLED_LANGUAGES` | no | Comma-separated BCP-47 codes, e.g. `es,fr` — see below |

Postgres-specific (consumed by the `postgres` container in Compose):

| Variable | Default |
|---|---|
| `POSTGRES_DB` | `mnemosyne` |
| `POSTGRES_USER` | `mnemosyne` |
| `POSTGRES_PASSWORD` | `changeme` — **change before deploying** |

---

## Single-language deployments

`ENABLED_LANGUAGES` restricts which plugins are loaded at startup.  Set it to a
comma-separated list of BCP-47 codes when you only need a subset of the
bundled languages:

```bash
# .env — Spanish and French only
ENABLED_LANGUAGES=es,fr
```

Behaviour:

- Plugins not in the list are skipped silently — no `WARNING` is emitted.
- The database is **not modified** — existing rows for excluded languages are
  preserved and will reappear if the language is re-enabled later.
- `GET /languages` returns only the loaded plugins, so the frontend never shows
  languages that are unavailable on this instance.
- `GET /ready` still reports `"plugins": "ok"` when every *requested* plugin
  loaded successfully.  Set `ENABLED_LANGUAGES` to the set of languages you care
  about to suppress warnings about plugins that are intentionally absent.

Unset `ENABLED_LANGUAGES` (or leave it empty) to load every plugin in
`PLUGIN_PACKAGE`.

---

## Adding a language to an existing deployment

Mnemosyne's schema is language-agnostic.  Every learnable object is stored as a
row in `canonical_objects` and keyed by `(language, type, canonical_form)`.
Adding a new language to a running instance requires no database migration:

1. **Create the plugin** — drop a new `.py` file into `backend/plugins/` (or
   your custom `PLUGIN_PACKAGE`).  See the *Adding a language plugin* section
   below for the full interface.
2. **Download the model** — follow the plugin's model-download instructions,
   typically `python -m spacy download xx_core_news_sm`.
3. **Update `ENABLED_LANGUAGES`** — if this variable is set, add the new
   language code to the comma-separated list.  If it is not set, nothing to do.
4. **Restart the server** — plugins are loaded once at startup via
   `lru_cache`; a running server will not pick up a new file.
5. **Verify** — `GET /languages` should include the new language code.  `GET /ready`
   should report `"plugins": "ok"`.

No `alembic` migration is needed.  Existing data for other languages is
untouched.

---

## Notes

- Use Memurai or Redis via Docker
- Use localhost in .env when running outside Docker

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
| `test_non_latin_roundtrip.py` | Non-Latin DB round-trip + RTL API pipeline | in-memory SQLite |
| `test_arabic_plugin.py` | Arabic plugin (dictionary mode) | none |
| `test_hebrew_plugin.py` | Hebrew plugin (dictionary mode) | none |
| `test_latin_plugin.py` | Latin plugin (morphology-light mode) | none |
| `test_chinese_plugin.py` | Chinese plugin (jieba segmentation) | none |
| `test_spanish_spacy.py` | Spanish NLP extraction | **requires `es_core_news_sm`** |
| `test_french_spacy.py` | French NLP extraction | **requires `fr_core_news_sm`** |
| `test_german_spacy.py` | German NLP extraction | **requires `de_core_news_sm`** |
| `test_russian_spacy.py` | Russian NLP extraction | **requires `ru_core_news_sm`** |
| `test_japanese_plugin.py` | Japanese plugin (SudachiPy) | **requires `ja_core_news_sm`** |
| `test_portuguese_spacy.py` | Portuguese NLP extraction | **requires `pt_core_news_sm`** |
| `test_italian_spacy.py` | Italian NLP extraction | **requires `it_core_news_sm`** |
| `test_greek_koine_plugin.py` | Koine Greek plugin (morphology-light mode) | none |
| `test_hindi_turkish_finnish_plugins.py` | Hindi, Turkish, Finnish suffix-rule plugins | none |
| `test_classical_morph.py` | Latin/Greek morphological index structure + plugin integration | none |

Tests that require spaCy models are auto-skipped when the model is not installed (each file has a `pytestmark = pytest.mark.skipif(not _model_available(), ...)` guard). Run the full suite without any model installed:

```bash
pytest backend/tests -q
```

To run only the model-free tests:

```bash
pytest backend/tests -q -k "not (spacy or spanish or french or german or russian or japanese)"
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

from backend.schemas.language import LanguageCapabilities
from backend.schemas.parse import CandidateObject, CandidateSentenceResult, RelationHint


class GermanPlugin:
    language_code = "de"       # BCP-47 tag used in /parse requests
    display_name  = "German"
    direction     = "ltr"      # "rtl" for Arabic, Hebrew, etc.
    capabilities  = LanguageCapabilities(
        code="de",
        display_name="German",
        direction="ltr",
        script_family="latin",          # "arabic" | "hebrew" | "cjk" | "devanagari" | …
        tokenization_mode="whitespace", # "segmented" for CJK/Thai; "character" for annotation mode
        morphology_depth="rich",        # "none" | "shallow" | "rich"
        lesson_modes_supported=["morphology", "vocabulary"],  # richest first
    )

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
- Lowercase, no leading/trailing whitespace (exception: German noun lemmas keep their initial capital — see below).
- Drop any form that contains a space (NLP enclitic-fusion artifact).
- For conjugations, encode the morphological axes: `{lemma}:{tense}:{mood}:{person}:{number}`.
- For agreements, encode the pair: `{modifier_pos_lower}:{modifier_lemma}_{noun_lemma}`.

**Script-family conventions:**

| Script family | Lemma case | Notes |
|---|---|---|
| Latin (es, fr, la) | lowercase | Standard; matches dictionary headword convention |
| Latin-German (de) | preserve capital on NOUN | German dictionaries capitalise nouns; `"Haus"` not `"haus"` |
| Cyrillic (ru) | lowercase | pymorphy3 returns lowercase lemmas |
| Arabic (ar) | undiacritised (tashkeel stripped) | `كتب` not `كَتَبَ`; strip combining marks U+064B–U+0670 before storing |
| Hebrew (he) | unpointed (nikud stripped) | `ספר` not `סֵפֶר`; strip combining marks U+05B0–U+05C7 before storing |
| CJK (zh, ja) | surface form as-is | No case; no diacritic stripping; store the segmented word token directly |
| Hiragana/katakana (ja) | surface form as-is | Do not convert katakana to hiragana in the canonical form; readings go in `lesson_data["reading"]`, not in the canonical form |

**Russian conjugation canonical form** (6 axes, not 5):

```
{lemma}:{tense}:{aspect}:{mood}:{person_or_gender}:{number}
```

`person_or_gender` is a person digit (`1`, `2`, `3`) for present/future tense, and a gender word (`masculine`, `feminine`, `neuter`) for past tense, because Russian past-tense verbs agree with the subject's gender, not person.

**`case_agreement` canonical form** (German, Russian, Latin):

```
case_agreement:{case_lower}:{modifier_lemma}_{noun_lemma}
```

e.g. `"case_agreement:nom:der_mann"` (German), `"case_agreement:ins:новый_друг"` (Russian).

**Arabic conjugation canonical form** (5 axes):

```
{undiacritised_lemma}:{tense}:{person}:{gender}:{number}
```

Arabic verbs agree with person, gender, and number — not mood as the primary axis. Use lowercase English labels:

| Axis | Values |
|---|---|
| tense | `past` \| `present` \| `future` \| `imperative` |
| person | `1` \| `2` \| `3` |
| gender | `masculine` \| `feminine` |
| number | `singular` \| `dual` \| `plural` |

Example: `كتب:past:3:masculine:singular`

**Arabic trilateral roots** do NOT go in `canonical_form`. If your plugin identifies a root (e.g. `ك-ت-ب`), store it in `lesson_data["root"]` using the bare consonant sequence without diacritics (`ktb` in romanisation, or the Unicode consonants `كتب`). Root objects, if taught separately, use the type `"script"` with `canonical_form = "root:{consonants}"` — e.g. `"root:كتب"`. This keeps vocabulary and root objects in separate ID spaces so they can be related via `RelationHint` without colliding.

**Languages where the lemma is a derived form** (Hebrew binyanim, Classical Arabic masdar, etc.): use the dictionary citation form — the form that appears as the headword in a standard printed dictionary for that language. Do not attempt to decompose it to a root. Roots go in `lesson_data["root"]`; the canonical form stays as the citation form. For Hebrew verbs, the citation form is the Pa'al (or binyan-specific) 3rd person masculine singular past: e.g. `כתב` not `כ-ת-ב`.

**Chinese polysemy disambiguation**: when a segmented token has multiple readings that differ in meaning (e.g. `长 cháng` = "long" vs `长 zhǎng` = "to grow"), the canonical form uses the bare character sequence when the plugin cannot resolve the reading, and appends the pinyin reading (tones as digits) when it can:

```
{characters}:{pinyin_tones_no_spaces}
```

Example: `长:zhang3` (to grow) vs `长:chang2` (long). Append pinyin **only when you can determine the reading from context**. When ambiguous, use the bare form `长` — a wrong disambiguation is worse than no disambiguation. Pinyin tones use the digit convention (1–4, 5 for neutral tone).

**Agglutinative languages** (Finnish, Turkish, Hungarian, and similar): these languages have 10+ productive morphological axes. Rules:

1. **Encode only axes your plugin extracts reliably.** Do not emit axes you cannot determine. A 4-axis canonical form is better than a 10-axis form where 6 axes are guessed.
2. **Fix the axis order per language and document it in the plugin file.** The order must be stable across all parses; if it changes, all stored IDs become invalid. Use a module-level docstring or comment that states the axis order explicitly.
3. **Use lowercase English labels** for axis values (e.g. `nominative` not `NOM`, `singular` not `SG`).
4. Suggested axis order for Turkish conjugations: `{lemma}:{tense}:{aspect}:{mood}:{person}:{number}:{voice}` — omit trailing axes when unknown.
5. Suggested axis order for Finnish nominals: `{lemma}:{case}:{number}` (14 cases; use full lowercase English names: `nominative`, `genitive`, `accusative`, `partitive`, `inessive`, `elative`, `illative`, `adessive`, `ablative`, `allative`, `essive`, `translative`, `instructive`, `abessive`, `comitative`).

Until a plugin for an agglutinative language is implemented, no canonical forms are stored. Define the axis order in the plugin before the first parse — you cannot change it after rows exist.

### surface_form rules

- The specific inflected form seen in this text (e.g. `"gatos"` for canonical `"gato"`).
- Preserve original casing from the source text.
- Set to `None` only when there is genuinely no single surface form (e.g. a multiword expression where the label already encodes the surface).

### Capability metadata

Every plugin must declare a `capabilities` class attribute of type `LanguageCapabilities` (from `backend.schemas.language`). The registry reads it to populate `GET /languages`; the lesson route reads it to choose the right lesson template.

| Field | Values | Notes |
|---|---|---|
| `direction` | `"ltr"` \| `"rtl"` | Applied as `dir=` attribute on sentence text in the frontend |
| `script_family` | `"latin"` \| `"arabic"` \| `"hebrew"` \| `"cjk"` \| `"devanagari"` \| `"cyrillic"` \| `"other"` | Frontend uses this to select a font stack |
| `tokenization_mode` | `"whitespace"` \| `"segmented"` \| `"character"` | Pass `word_count_hint` to `score_sentence` for `"segmented"` languages |
| `morphology_depth` | `"none"` \| `"shallow"` \| `"rich"` | Informs how much morphological analysis the plugin provides |
| `lesson_modes_supported` | `["morphology", "vocabulary", "dictionary"]` | Richest mode first; lesson route picks first available |

**Lesson mode selection:** the lesson route calls `best_lesson_mode(capabilities.lesson_modes_supported)` and passes it to `build_lesson()`. Match your mode to your actual extraction depth:

- `"dictionary"` — only a gloss or translation is available; no POS, no inflection.
- `"vocabulary"` — lemma + POS available; no conjugation paradigms.
- `"morphology"` — full tense/mood/person/number analysis available.

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
