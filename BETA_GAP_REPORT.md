# Beta Gap Report — Mnemosyne

*Originally written 2026-04-15. Updated 2026-04-18 to reflect current `main` branch state.*

All private alpha and public beta blockers are resolved. All vision items V1–V5 are
implemented. The system is at or beyond the original 12-week plan. This document is
retained as a record of what was built and what remains genuinely open at the vision
tier.

---

## What is solid (do not second-guess)

- **Core loop.** Parse → lesson → review → recommend is complete, tested, and persistent.
  1 555 tests collected and passing.
- **FSRS-5.** Pure Python, deterministic, no external dependencies. Per-user calibration
  via `POST /users/me/calibrate` (bias-correction over `ReviewEventRow` history).
  `UserFsrsParamsRow` table; `GET/PATCH /users/me/fsrs-params`.
- **Canonical knowledge layer.** UUID-v5 PKs; the same word in any text always maps to
  the same DB row. Surface forms accumulate. Object relations stored.
- **Plugin architecture.** Structural typing, no registration step. 10 full plugins + 1
  stub (English). Drop a file in `backend/plugins/` and the server picks it up.
- **Accessibility baseline.** Skip link, focus trap, ARIA live regions, reduced motion,
  44 px targets, roving tabindex, `role="list"` on pill lists. Static WCAG 2.1 AA code
  audit complete — 8 issues found and fixed. See `WCAG_AUDIT.md`.
- **Multi-user with real auth.** JWT (`/auth/register` + `/auth/login`), login/register
  UI, `sessionStorage` token, per-user isolation across all routes.
- **Review event log.** `review_events` append-only table (migration 0006). Written by
  every review. Drives `reviews_today`, `streak_days`, `daily_activity` in `/metrics`
  and FSRS calibration.
- **Full multilingual stack.** Spanish, French, German, Russian, Japanese: full spaCy
  morphological pipelines. Arabic, Hebrew, Chinese (jieba + pypinyin), Latin, Koine
  Greek: dictionary/vocabulary mode with honest capability declarations. 11 registered
  language codes.
- **RTL support.** `dir`/`lang` applied throughout modal and sentence cards; logical CSS
  properties; `<bdi>` isolation in drill feedback; 43 non-Latin DB round-trip tests.
- **Operational baseline.** Health + readiness probes (degraded-plugin reporting).
  CORS lockdown (hard-fails startup on wildcard in production). Rate limiting (slowapi,
  JWT > X-User-Id > IP). Sentry SDK. Structured `request_id` logging.
- **Offline + PWA.** Service worker (cache-first app shell), IndexedDB review queue,
  drain-on-reconnect, offline badge. `frontend/manifest.json` enables install.
- **Background large-text processing.** `POST /parse/jobs` + SSE progress stream.
  Frontend routes texts > 10 k chars through the job API with a live progress bar.
- **Dictionary + translation enrichment.** Wiktionary gloss enrichment
  (`ENABLE_DICTIONARY_LOOKUP`). LibreTranslate + MyMemory translation
  (`ENABLE_TRANSLATION_ENRICHMENT`). Both run as background tasks post-parse.

---

## Private alpha blockers — all resolved

| Blocker | Status |
|---------|--------|
| A1. `alembic upgrade head` on fresh startup | ✓ done |
| A2. `max_chars` guard on `/parse` and `/ingest` (413) | ✓ done |
| A3. At least one working second language | ✓ done — 10 language plugins |
| A4. `GET /users/me/export` data export endpoint | ✓ done |
| A5. Docker Compose works end-to-end | ✓ `docker-compose.yml` present; `make up` starts postgres + redis + app |

---

## Public beta blockers — all resolved

| Blocker | Status |
|---------|--------|
| B1. JWT authentication (`/auth/register`, `/auth/login`) | ✓ done |
| B2. Login/register UI; JWT in `sessionStorage`; logout | ✓ done |
| B3. WCAG 2.1 AA audit on parse → lesson → review | ✓ done (code-level; manual AT run recommended) |
| B4. RTL layout complete (modal `dir`/`lang`, `<bdi>`) | ✓ done |
| B5. CORS lockdown | ✓ done |
| B6. Rate limiting | ✓ done |
| B7. Privacy policy + `DELETE /users/me` | ✓ done |
| B8. Error monitoring (Sentry SDK) | ✓ done |
| B9. Three+ production-quality language plugins | ✓ done — 5 full morphological + 5 dictionary-mode |

---

## Vision blockers — status

| Item | Status |
|------|--------|
| V1. Review event log | ✓ done |
| V2. Background processing for large texts | ✓ done |
| V3. Real dictionary integration | ✓ done (Wiktionary) |
| V4. FSRS parameter fitting | ✓ done (per-user calibration via `ReviewEventRow`) |
| V5. PWA and offline mode | ✓ done |
| V6. 10+ production-quality language plugins | ~ partial — 5 full morphological (es/fr/de/ru/ja), 5 dictionary-mode (ar/he/zh/la/grc), 1 stub (en). Full morphological coverage for Portuguese, Italian, Korean, Hindi etc. remains open. |
| V7. Dead and historic language annotation mode | ~ partial — Latin, Arabic, Koine Greek implemented in dictionary mode with honest capability declarations. Classical Arabic lexicon and Perseus-backed Latin morphology remain open. |

---

## What is genuinely open

These are the only items without a completed implementation:

**Manual keyboard + screen-reader test** — The WCAG 2.1 AA code audit is done and 8
issues were fixed. A human keyboard-only walkthrough and NVDA/VoiceOver smoke test
have not been run. See `WCAG_AUDIT.md` for the testing checklist.

**Full morphological plugins for additional languages** — Korean, Hindi,
Turkish, Finnish are natural next targets given available spaCy models. Each
requires NLP research, canonical-form convention decisions (per `PLUGIN_AUTHOR_GUIDE.md`),
plugin implementation, and tests. This is the main remaining work toward the V6 target.

**Portuguese (`pt`) — done**: `pt_core_news_sm`; vocabulary, conjugation, agreement,
grammar patterns (ser/estar copula, ter_perfect, ir_near_future, estar_progressive),
idioms (~30 entries), nuance (imperfect, subjunctive, conditional, reflexive,
personal infinitive). 62 tests in `test_portuguese_spacy.py`.
Install: `python -m spacy download pt_core_news_sm`.

**Italian (`it`) — done**: `it_core_news_sm`; vocabulary, conjugation, agreement,
grammar patterns (essere_copula, avere_perfect, essere_perfect, stare_progressive,
andare_near_future), idioms (~30 entries), nuance (imperfect, subjunctive,
conditional, reflexive). avere/essere auxiliary distinction documented.
60 tests in `test_italian_spacy.py`.
Install: `python -m spacy download it_core_news_sm`.

**Classical-text lexicon depth** — Latin and Koine Greek are in dictionary mode with
small curated lexicons (~100–200 entries). Perseus Digital Library integration or a
comparable classical lexicon would substantially improve coverage. Policy decision on
what "production quality" means for a dead language is still needed.

**`source_progression` reading continuity** — **done**: `GET /reading/{id}` and
`PATCH /reading/{id}` expose the per-(user, document) reading position.
`POST /ingest` now creates a `SourceProgressionRow` at ingestion time with
`sentences_total` set from the parsed sentence count. `GET /recommend` loads
in-progress documents and sorts continuation sentences (at or after
`next_position`) first within the difficulty window, with an `is_continuation`
flag in each response item. 14 new tests in `test_source_progression.py`.

**Lesson text localisation** — `build_lesson()` produces English prose regardless of
target language. The template layer is pluggable (`tense_pool`/`mood_pool` on
`LanguageCapabilities`) but lesson explanations ("The word X is a noun") are always
English. For learners whose native language is not English this is a friction point.

---

## Architectural invariants

These must not be violated under schedule pressure.

1. **UUID-v5 namespace is frozen.** Every canonical object ID ever stored is derived
   from it. Do not change it.
2. **No language-specific logic in core.** If a route handler or the scheduler contains
   a language code string (other than in a test fixture), that is a bug.
3. **Fault-tolerant I/O is not optional.** Every DB and Redis call in a route handler
   must be wrapped in `try/except` with `logger.warning`.
4. **Canonical form convention is fixed once the first row is stored.** Design it
   correctly before shipping a plugin.
5. **Authentication is a dependency injection swap.** `get_current_user` is the single
   injection point. Do not bake identity logic into route handlers.
6. **Authentic text first.** No vocabulary lists, no built-in lessons, no curated
   syllabuses. The user supplies the text.
7. **Narrow and correct beats broad and unreliable.** Omit or penalise-confidence rather
   than silently mislabel.
