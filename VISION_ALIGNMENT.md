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

| Plugin | Status | Extracts |
|--------|--------|---------|
| Spanish (`es`) | implemented | vocabulary, conjugation (full morph), agreement (gender/number) |
| English (`en`) stub | partial | vocabulary only; regex-based; no morphology |
| French (`fr`) stub | partial | vocabulary only; regex-based; stop-word filter; no morphology |

All other languages: **not implemented**.

### Infrastructure

| Capability | Status | Notes |
|-----------|--------|-------|
| Canonical knowledge layer (UUID-v5 PKs, surface_forms, object_relations) | implemented | |
| Plugin registry with multi-language support | implemented | `ENABLED_LANGUAGES` filter |
| Alembic migrations | partial | 3 revision files exist; `create_all` still runs on fresh start |
| RTL layout support | partial | `direction` field on plugins; frontend CSS not yet RTL-aware |
| User authentication | deferred | All state belongs to `user_id = "default"` |
| Review event log | deferred | Only current FSRS state is stored; no per-review history |
| Offline / PWA | deferred | |
| Background processing for large texts | deferred | NLP blocks the request path |

---

## Major gaps

### Gap 1 — One real language

Only Spanish has a production-quality plugin. English and French stubs extract vocabulary by regex with no morphological understanding. A user learning either of those languages today would get a stripped-down experience.

**Impact:** The multi-language vision is architecturally ready but practically hollow. The infrastructure for a second real language (registry, canonical IDs, per-language dashboard filtering) is in place; the NLP work is not done.

### Gap 2 — RTL and non-Latin scripts

The `direction` field exists on every plugin and is returned by `GET /languages`. The frontend does not apply it. There are no layout rules for RTL text flow, no font considerations for Arabic, Hebrew, or CJK scripts, and no test fixture that exercises a non-Latin canonical form through the full pipeline.

**Impact:** The system cannot be used for Arabic, Hebrew, or Japanese today without visual breakage. Adding `[dir="rtl"]` CSS overrides is moderate work; the harder part is auditing every component for implicit LTR assumptions.

### Gap 3 — No review event history

`user_knowledge` stores only the current FSRS state. There is no table recording when each individual review happened, what the quality rating was, or what the mastery score was at that point. This means:

- Retention curves cannot be drawn.
- Exact time-to-mastery cannot be computed.
- Per-session statistics (reviews per day, best study time) are unavailable.

`/metrics` approximates these from the snapshot state (current `mastery_score`, `lapses`, `stability`), which is accurate for current-state reporting but useless for trend analysis.

### Gap 4 — Single user

Every piece of knowledge state is attached to `user_id = "default"`. The schema already uses a `user_id` primary key component and passes it through every query. Adding real users requires authentication middleware and a login flow, but the data model is not a blocker.

### Gap 5 — NLP in the request path

`plugin.analyze_text()` is called synchronously inside the FastAPI handler. For a 500-word text this is fast (< 1 s for Spanish on modern hardware), but for longer texts it blocks the event loop and risks timeout. There is a `max_chars` guard proposed in the roadmap but not yet implemented.

### Gap 6 — Dead and historic languages

There is no annotation mode. The system expects a plugin that can extract learnable objects with confidence scores. For Latin or Classical Greek, spaCy models exist but are lower quality than for modern languages. For truly under-resourced languages, the honest approach is a dictionary lookup mode that does not pretend to offer morphological analysis.

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

### Frontend assumes LTR Latin script

The frontend CSS uses no `[dir="rtl"]` overrides, no `writing-mode` properties, and no `font-family` abstractions that could accommodate Arabic or CJK glyphs. The pill buttons and modal are tested only with Spanish and English text. Adding Arabic or Hebrew requires a careful audit of every layout primitive.

### Lesson generator is language-agnostic but English-prose-centric

`backend/lesson/generators.py` produces lesson text with English phrasing like "The word *X* is a noun." For languages with significantly different grammatical concepts (verb classes, classifier systems, tone) this framing will not translate. The lesson generator needs a pluggable template layer.

### `canonical_form` string format is Latin-script-centric in practice

The format rules (`lowercase`, `{lemma}:{tense}:{mood}:{person}:{number}`) are documented for Latin-script morphological categories. There is no guidance for tonal languages, agglutinative languages with many more morphological axes, or languages where the lemma is itself a derived form. The UUID derivation will work for any Unicode string, but the form-construction conventions need to be extended.

### No test fixture for non-Latin scripts

There are no tests that push a non-ASCII, non-Latin canonical form through `canonical_object_id()`, store it in the database, and retrieve it. Adding such a fixture is cheap and would expose encoding or collation bugs early.

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
