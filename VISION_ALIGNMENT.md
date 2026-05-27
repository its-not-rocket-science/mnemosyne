# Vision Alignment

This document maps Mnemosyne's founding vision against the current implementation. It is intended to be read before making architectural decisions, especially decisions that touch language support, accessibility, or the learning model.

---

## The starting vision

> Turn any text into a living lesson. Build from authentic texts, not canned exercises. Support many languages and scripts, including RTL and eventually historic and dead languages. Use memory science and spaced repetition. Remain minimalist, accessible, and extensible.

The five pillars are:

1. **Authentic text first** — the learner supplies the text; the system reveals what is learnable in it.
2. **Broad language support** — every design decision should be language-agnostic; any language-specific logic belongs in a plugin.
3. **Memory science** — FSRS governs scheduling; difficulty scoring follows the i+1 principle.
4. **Minimalism** — no framework, no bloat, no speculative abstraction.
5. **Accessibility** — usable without mouse, without colour, without motion, and in any script.

---

## Current implementation state

### Core loop

| Capability | Status | Notes |
|-----------|--------|-------|
| Parse authentic text into learnable objects | implemented | `/parse` with Redis cache, PostgreSQL persistence |
| Open a micro-lesson on any extracted object | implemented | `/lesson/{id}` DB-first, plugin fallback |
| Rate recall; schedule next review via FSRS | implemented | `/review` with FSRS-5 scheduler |
| Adaptive sentence recommendations (i+1) | implemented | `/recommend`; difficulty window shifts with mastery |
| Knowledge dashboard | implemented | `/dashboard` with language filter |
| Learning metrics | implemented | `/metrics`; retention, success_rate, weakest-10 |

### Language support

| Language | Code | Plugin type | Extracts | spaCy model |
|----------|------|-------------|----------|-------------|
| Spanish | `es` | Full morphological | vocabulary, conjugation, agreement, idiom, grammar, nuance | `es_core_news_sm` |
| French | `fr` | Full morphological | vocabulary, conjugation, agreement | `fr_core_news_sm` |
| German | `de` | Full morphological | vocabulary, conjugation, case_agreement, separable verbs | `de_core_news_sm` |
| Russian | `ru` | Full morphological | vocabulary, conjugation (aspect+gender), case_agreement, idiom, nuance | `ru_core_news_sm` |
| Japanese | `ja` | Full morphological | vocabulary (+ hiragana readings), particles filtered | `ja_core_news_sm` + SudachiPy |
| Portuguese | `pt` | Full morphological | vocabulary, conjugation, agreement, grammar patterns, idiom, nuance | `pt_core_news_sm` |
| Italian | `it` | Full morphological | vocabulary, conjugation, agreement, grammar patterns, idiom, nuance | `it_core_news_sm` |
| Arabic | `ar` | Dictionary mode | vocabulary (tashkeel-normalised), RTL | none |
| Hebrew | `he` | Dictionary mode | vocabulary (nikud-normalised), RTL | none |
| Mandarin Chinese | `zh` | Dictionary mode | vocabulary (jieba segmentation + pinyin) | jieba + pypinyin |
| Latin | `la` | Dictionary mode | vocabulary (regex tokenisation), dead-language scaffold | none |
| Koine Greek | `grc` | Dictionary mode | vocabulary (polytonic normalisation + SBL transliteration) | none |
| English | `en` | Stub | vocabulary (regex only) | none |

**Production-quality** means full morphological extraction with relation hints. Seven languages qualify: Spanish, French, German, Russian, Japanese, Portuguese, and Italian.

### Infrastructure

| Capability | Status | Notes |
|-----------|--------|-------|
| Canonical knowledge layer (UUID-v5 PKs, surface_forms, object_relations) | implemented | |
| Plugin registry with multi-language support | implemented | `ENABLED_LANGUAGES` filter; degraded-plugin reporting in `/ready` |
| Alembic migrations | implemented | 9 revision files (0000–0008); startup runs `alembic upgrade head`; `create_all` removed |
| RTL layout support | implemented | `dir`/`lang` applied throughout modal, sentence cards, drill prompts; logical CSS properties; `<bdi>` isolation; 43 non-Latin round-trip tests |
| Multi-user data isolation | implemented | JWT auth; per-user isolation across all routes; `UserLanguagePreferenceRow` table; `/users/me/*` preference CRUD |
| User authentication (JWT) | implemented | `/auth/register` + `/auth/login`; HS256 JWT; login/logout UI |
| Review event log | implemented | `review_events` append-only table (migration 0006); drives metrics and FSRS calibration |
| Offline / PWA | implemented | Service worker (cache-first app shell); IndexedDB review queue; drain-on-reconnect |
| Background processing | implemented | `POST /parse/jobs` + SSE progress stream; all texts route through the job API |
| FSRS per-user calibration | implemented | `UserFsrsParamsRow`; `POST /users/me/calibrate` bias-correction over `ReviewEventRow` |
| Source progression tracking | implemented | `SourceDocumentRow`; `GET/PATCH /reading/{id}`; `POST /ingest` creates progression row |

---

## Resolved gaps (historical record)

These were the major open issues when this document was first written. All are resolved.

**Gap 1 — One real language** → Seven languages now have production-quality full-morphological plugins (es, fr, de, ru, ja, pt, it). Five more are in dictionary mode (ar, he, zh, la, grc).

**Gap 2 — RTL and non-Latin scripts** → `dir`/`lang` applied throughout modal, sentence cards, and drill prompts. Logical CSS properties throughout. `<bdi>` isolation in drill feedback. 43 non-Latin DB round-trip tests. `canonical_form` conventions documented for Arabic, Hebrew, CJK, Cyrillic, and agglutinative languages in `PLUGIN_AUTHOR_GUIDE.md`. Difficulty scorer accepts `word_count_hint` for CJK.

**Gap 3 — No review event history** → `review_events` append-only table (migration 0006) records every review with quality, mastery_score_before/after, and timestamp. `/metrics` exposes `reviews_today`, `streak_days`, `daily_activity`. FSRS calibration uses this history.

**Gap 4 — Authentication** → JWT authentication implemented. `/auth/register` + `/auth/login`; HS256; `get_current_user` verifies Bearer token; login/logout UI.

**Gap 5 — NLP in the request path** → All parses route through the async job API (`POST /parse/jobs` + `GET /parse/jobs/{id}/events`). NLP runs in a thread-pool executor. SSE progress stream. `max_chars` guard (413 above limit).

**Gap 6 — Dead and historic languages** → Latin (`la`) and Koine Greek (`grc`) implemented in dictionary mode with honest capability declarations (no morphology claimed). ~100–200 curated lexicon entries each.

**Gap 7 — Lesson text localisation** → `backend/lesson/l10n.py` renders `build_lesson()` explanations in the learner's native language for all 12 UI locales. Static templates; zero-latency; deterministic. 326 tests in `test_l10n.py`. Untranslated L1 codes fall back to English.

**Gap 8 — Frontend UI string localisation** → all hardcoded English strings in frontend components replaced with `t()`/`ti()` calls in `frontend/js/i18n.js`. Covers `mnemosyne-modal`, `mnemosyne-pill`, `mnemosyne-text-panel`, `mnemosyne-top-nav`, and `main.js`. The grammatical terminal label values from `generators.py` (e.g. `"third"`, `"singular"`, `"present"`) remain untranslated.

---

## What remains genuinely open

- **Manual keyboard + screen-reader test.** Static audit done (11 issues found and fixed, incl. concept dialog ARIA); NVDA/VoiceOver smoke test not yet run; see `MANUAL_ACCESSIBILITY_TEST.md`.
- **Shallow morphological plugins for Hindi, Turkish, Finnish — done.** Suffix-rule `morphology_light` plugins added (2026-05-27). Full spaCy-model morphology for Korean and deeper per-language coverage remains planned.
- **Classical lexicon depth — partially done.** Latin (~3 400 forms) and Koine Greek (~27 000 forms) now have offline treebank morphological annotations. Perseus/Logeion integration would cover unattested forms.
- **Grammatical label localisation.** `build_lesson()` prose is now in the learner's language, but the terminal label values (`"third"`, `"singular"`, `"present"`, `"indicative"`) produced by `backend/lesson/generators.py` remain English strings. A second lookup table in `l10n.py` is needed to translate these.

---

## Architectural decisions that help the vision

### UUID-v5 canonical IDs

Every learnable object has a deterministic UUID derived from `(language, type, canonical_form)`. This means:
- The same word in different texts always maps to the same ID.
- Review history survives re-parses, plugin upgrades, and server restarts.
- No database round-trip is needed to assign IDs during a parse.

This is a strong foundation for the "living lesson" model. Any text the user pastes that contains a word they have seen before immediately shows their existing mastery state.

### Plugin protocol (structural typing)

Plugins satisfy an interface without inheriting from anything. Adding a language is a single file plus tests — no changes to core. The `ENABLED_LANGUAGES` config key means a deployment can be locked to one language without any code changes.

### FSRS stability scalar

FSRS stability (S) is stored per-object in `user_knowledge.fsrs_state`. The scheduler is pure Python with no I/O. This makes the scheduling loop testable, portable, and independent of any particular review UI — which matters for a system that wants to work across many language types and review modalities.

### surface_forms accumulation

Every parse of a canonical object records the specific inflected form seen in that text. Over time, `canonical_objects.surface_forms` accumulates all the forms the user has encountered. This is the start of a data structure that can power recognition-mode drills, cloze exercises, and frequency analysis without additional NLP work.

### Fault-tolerant degradation

Every database and Redis operation in the route handlers is wrapped in `try/except`. The system returns correct results even when backing services are down; it just loses persistence. This is essential for a single-user tool that people run on laptops and personal servers.

---

## Architectural decisions that currently limit multilingual expansion

### RTL and non-Latin scripts — implemented

The frontend applies `dir` and `lang` attributes dynamically from plugin capabilities. Logical CSS properties (`inline-size`, `margin-inline-start`, etc.) are used throughout. Non-Latin font stacks are declared in `global.css`. The modal applies RTL to example text, drill prompts, and fill-blank inputs. `<bdi>` elements isolate bidirectional strings in feedback. 43 non-Latin DB round-trip tests cover Arabic, Hebrew, Chinese, Russian, and Japanese canonical forms.

**Remaining limitation:** `build_lesson()` prose is now in the learner's language via `backend/lesson/l10n.py`, but the terminal grammatical label values (`"third"`, `"singular"`, `"present"`, `"indicative"`) produced by `generators.py` remain English strings. For most learners the mixed output is adequate; full label translation requires a second lookup table in `l10n.py`.

### Lesson generator — prose localised; grammatical labels remain English

`backend/lesson/generators.py` produces grammatical category labels as bare English strings (`"third"`, `"singular"`, `"present"`, `"indicative"`). The surrounding prose is now localised via `l10n.py`, but these terminal values are not yet run through a translation table. For languages with significantly different grammatical concepts (verb classes, classifier systems, tone) the label framing may also need adaptation.

### `canonical_form` string format is Latin-script-centric in practice

The format rules (`lowercase`, `{lemma}:{tense}:{mood}:{person}:{number}`) are documented for Latin-script morphological categories. There is no guidance for tonal languages, agglutinative languages with many more morphological axes, or languages where the lemma is itself a derived form. The UUID derivation will work for any Unicode string, but the form-construction conventions need to be extended.

### Non-Latin test coverage — implemented

43 tests in `test_non_latin_roundtrip.py` push Arabic, Hebrew, Chinese, Russian, and Japanese canonical forms through `canonical_object_id()`, SQLite insert, retrieve, and lossless round-trip assertion. API-level RTL pipeline tests are included.

### Single-pass NLP is spaCy-centric

The `analyze_text()` method was optimised for spaCy's `doc.sents` iterator. Plugins for languages without a good spaCy model (e.g. Classical Arabic, Latin) would need a different architecture — possibly a sentence-splitting + dictionary-lookup pipeline — but the protocol only exposes `list[CandidateSentenceResult]` as output. This is fine; the point is that the optimisation was made with spaCy in mind, and a non-spaCy plugin author needs to know they can ignore the single-pass idiom.

---

## Design principles

These are non-negotiable. Any feature that violates one of them should be redesigned, not shipped.

### 1. Every feature works from authentic text first

Mnemosyne has no built-in vocabulary lists, no canned exercises, and no curated syllabuses. The user supplies text — a news article, a song lyric, a legal clause — and the system reveals what is learnable in it. Features that require pre-structured content (e.g. "lesson packs") are out of scope unless they are layered on top of the authentic-text core, not in place of it.

### 2. Language support is plugin-first

All language-specific logic lives inside a plugin module. The core — the parse route, the scheduler, the canonical ID system, the dashboard, the recommendation engine — must work without knowing anything about Spanish morphology or French elision. If a core module contains a language-specific string (other than a test fixture) that is a bug.

### 3. The frontend must not assume Latin script or LTR

Every layout primitive — text alignment, flex direction, scroll direction, line breaking, font stack — must be either direction-agnostic or switchable. The `direction` field on the plugin metadata exists for this reason. Before shipping RTL support, a full layout audit with an Arabic or Hebrew fixture is required. "Works for now" is not acceptable for a system that names multilingual support as a core goal.

### 4. Accessibility must survive multilingual expansion

Adding a new language must not regress keyboard navigation, screen-reader announcements, or contrast ratios. Newly added text must carry correct `lang` attributes. RTL layout changes must not break focus-ring visibility or touch-target sizes. Treat each new language as a new accessibility test surface, not just a new data source.

### 5. Narrow and correct beats broad and unreliable

A Spanish plugin that correctly identifies 70% of interesting morphological features is more valuable than one that attempts 100% and silently misclassifies 30%. When a plugin cannot reliably extract a category (e.g. subjunctive vs. indicative in homographic forms), it should omit the object or mark it with a low confidence score — not return a confident wrong answer. The learner's mental model is harmed by incorrect analysis more than by silence.

This principle extends to new languages: a stub plugin that extracts vocabulary by lemma lookup is preferable to a full plugin that extracts conjugations inaccurately. Ship the stub; improve incrementally; never over-claim.
