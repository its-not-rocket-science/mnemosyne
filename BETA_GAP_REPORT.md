# Beta Gap Report — Mnemosyne

*Originally written 2026-04-15. Updated 2026-05-28 to reflect feature-maturity pass (Priority 1–8 complete).*

All private alpha and public beta blockers are resolved. All vision items V1–V5 are
implemented. The system is at or beyond the original 12-week plan. This document is
retained as a record of what was built and what remains genuinely open at the vision
tier.

---

## What is solid (do not second-guess)

- **Core loop.** Parse → lesson → review → recommend is complete, tested, and persistent.
  3 680+ passing tests (full suite as of 2026-05-28 feature-maturity pass).
- **Practice activities.** Detail pane exposes scored retell, typed drill, comprehension, and
  mini-quiz practice panels. Every practice check dispatches `pane-practice-check` → `submitReview(objectId, quality)` → FSRS `/review` endpoint, so practice directly updates spaced-repetition state. Session score and next-interval feedback shown inline.
- **FSRS-5.** Pure Python, deterministic, no external dependencies. Per-user calibration
  via `POST /users/me/calibrate` (bias-correction over `ReviewEventRow` history).
  `UserFsrsParamsRow` table; `GET/PATCH /users/me/fsrs-params`.
- **Canonical knowledge layer.** UUID-v5 PKs; the same word in any text always maps to
  the same DB row. Surface forms accumulate. Object relations stored.
- **Plugin architecture.** Structural typing, no registration step. 17 production plugins:
  8 full morphological (es/fr/de/ru/ja/pt/it/**en**) + 5 dictionary-mode
  (ar/he/zh/la/grc) + 4 morphology-light (ko/hi/tr/fi — suffix-rule, no model required).
  Drop a file in `backend/plugins/` and the server picks it up.
- **Accessibility baseline.** Skip link, focus trap, ARIA live regions, reduced motion,
  44 px targets, roving tabindex, `role="list"` on pill lists. Static WCAG 2.1 AA code
  audit complete — 8 issues found and fixed. See `WCAG_AUDIT.md`.
- **Multi-user with real auth.** JWT (`/auth/register` + `/auth/login`), login/register
  UI, `sessionStorage` token, per-user isolation across all routes.
- **Review event log.** `review_events` append-only table (migration 0006). Written by
  every review. Drives `reviews_today`, `streak_days`, `daily_activity` in `/metrics`
  and FSRS calibration.
- **Full multilingual stack.** Spanish, French, German, Russian, Japanese, Portuguese,
  Italian: full spaCy morphological pipelines. Arabic, Hebrew, Chinese (jieba + pypinyin),
  Latin, Koine Greek: dictionary/vocabulary mode with honest capability declarations.
  Hindi, Turkish, Finnish: suffix-rule morphology-light plugins (Devanagari/Latin/Latin
  script; IAST/Latin/Latin romanisation; no external model required). Korean: morphology-
  light via kiwipiepy. 17 registered language codes.
- **Language capability labels (user-facing).** `LanguageCapabilities` now carries a `analysis_depth_label` computed field mapping internal IDs (`morphology_light`, `dictionary`, `full`, `segmentation_only`) to English display strings ("Basic grammar hints", "Vocabulary lookup", etc.). `CAPABILITY_LABELS_I18N` in `i18n.js` localises these for all 11 UI languages. Internal IDs unchanged; user-facing labels are separate.
- **Gold linguistic tests.** Per-language gold fixtures cover hi/tr/fi with false-positive and confidence assertions. `pytest_terminal_summary` hook prints per-language pass/fail/skip table after every full run. New assertion types: `assert_min_vocabulary_count` and `assert_no_confidence_above`.
- **Morphology improvements.** Hindi: single-char matras require min token length 5 (prevents "अच्छा"/"लड़का" false-positive conjugation tags). Turkish: `_AORIST_BLOCKLIST` blocks ~30 common words from aorist 3sg suffix match. Finnish: possessive suffix detection after case suffix match; `_INESSIVE_GUARD` blocks known false-positive forms.
- **Latin noun suffix hints.** `_extract_latin_noun_suffix_hint` provides heuristic `case_hint`, `number_hint`, `gender_hint`, and optional `ambiguity_note` for tokens not in the morph index. Wired into both the inflection-resolved non-verb branch and the unknown-token fallback.
- **Greek article agreement.** `_ARTICLE_FORMS` dict covers all 17 standard Koine article forms. A pre-pass over each sentence detects article + following-token bigrams and annotates the following token with `article_agrees_with: {case, gender, number}` from the article.
- **Corpus product features.** `GET /recommend-text` now returns `cefr_level` (from `CorpusIngestionRow`), `provenance` (author · source_url), and `recommendation_reason` (level_match | continuing | closest_match) per sentence. New query params: `?continuation=true`, `?cefr=`, `?max_words=`. `RECOMMEND_UI_I18N` export in `i18n.js` localises these for all 11 UI languages.
- **Privacy-conscious analytics.** `LearningEventRow` table stores aggregate, non-identifiable session counts (no text, no canonical forms). `UserRow.analytics_opt_out` bool (migration 0016). `backend/services/analytics.py`: `record_event`, `maybe_record_event` (respects opt-out), `delete_user_events` (GDPR). `GET /metrics/learning-events` dev endpoint (DEBUG=true only) returns aggregate event counts grouped by (event_type, language).
- **Manual accessibility test additions.** MANUAL_ACCESSIBILITY_TEST.md extended with tests 13–17 (reduced motion, 200% zoom, 400% zoom/reflow, offline/error states, Practice tab full). Structured session results template added. Automated static tests added: `TestReducedMotionCSS`, `TestConceptDialogStructure`, `TestPracticeTabInputs`, `TestLiveRegionCompleteness` — 38 tests, all pass.
- **Classical morphology.** Latin and Koine Greek deepened beyond dictionary mode:
  ~3 400 Latin forms (UD ITTB) and ~27 000 Greek forms (UD PROIEL + MorphGNT) provide
  conjugation type + tense/mood/person in lesson_data. Suffix rules fill gaps for Latin
  imperfect/future/infinitive. `morphology_quality="low"` (Latin) / `"medium"` (Greek).
- **Offline data pipeline.** `scripts/harvest_language_data.py` covers all 17 languages:
  FrequencyWords (en/es/fr/de/it/pt/ru/ar/he/hi/tr/fi), JLPT (ja), HSK (zh), inline
  curated vocab A1–B1 (la/grc). Grammar rules A1–C2 for all 17 languages.
- **RTL support.** `dir`/`lang` applied throughout modal and sentence cards; logical CSS
  properties; `<bdi>` isolation in drill feedback; 43 non-Latin DB round-trip tests.
- **Operational baseline.** Health + readiness probes (degraded-plugin reporting).
  CORS lockdown (hard-fails startup on wildcard in production). Rate limiting (slowapi,
  JWT > X-User-Id > IP). Sentry SDK. Structured `request_id` logging.
- **Offline + PWA.** Service worker (cache-first app shell), IndexedDB review queue,
  drain-on-reconnect, offline badge. `frontend/manifest.json` enables install.
- **Background processing.** `POST /parse/jobs` + SSE progress stream. All parses
  route through the job API with a live progress bar, regardless of text size.
- **Auth rate limiting.** `/auth/register` and `/auth/login` rate-limited via `RATE_LIMIT_AUTH` (default `5/minute`); same slowapi limiter as parse endpoints.
- **Lesson prose localisation.** `build_lesson()` explanations rendered in learner's
  native language for all 12 UI locales (en/es/fr/de/ru/ja/pt/it/ar/he/zh/ko) via
  `backend/lesson/l10n.py`. Static templates, zero-latency, deterministic. Untranslated
  L1 codes fall back to English. 326 tests in `test_l10n.py`.
- **Frontend UI string localisation.** All hardcoded English strings in frontend
  components replaced with `t()`/`ti()` calls from `frontend/js/i18n.js`. Covers
  `mnemosyne-modal` (drill feedback, rating labels, aria-labels), `mnemosyne-pill`
  (type labels, aria-label), `mnemosyne-text-panel` (empty state, play-line aria),
  `mnemosyne-top-nav` (all aria-labels, mode indicator), and `main.js` (all
  aria-announces and dynamic labels). True/False drill comparison updated to use
  `data-bool-value` so it survives translation.
- **GDPR text deletion.** `DELETE /users/me` now cascades `parsed_texts` (source_text), `sentences`, `sentence_objects`, `source_documents`, and `source_chunks`. `parsed_texts.user_id` column added (migration 0009).
- **Offline queue 401 handling.** `drainReviewQueue` detects 401 (expired JWT), surfaces localised "Session expired" message in all 11 UI languages, and stops drain without discarding queued reviews.
- **JWT_SECRET hard-fail in production.** `DEBUG=false` + default `JWT_SECRET` now hard-fails startup (same pattern as CORS wildcard guard).
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
| B9. Three+ production-quality language plugins | ✓ done — 8 full morphological (es/fr/de/ru/ja/pt/it/en) + 5 dictionary-mode (ar/he/zh/la/grc) + 1 morphology-light (ko) |

---

## Vision blockers — status

| Item | Status |
|------|--------|
| V1. Review event log | ✓ done |
| V2. Background processing for large texts | ✓ done |
| V3. Real dictionary integration | ✓ done (Wiktionary) |
| V4. FSRS parameter fitting | ✓ done (per-user calibration via `ReviewEventRow`) |
| V5. PWA and offline mode | ✓ done |
| V6. 10+ production-quality language plugins | ✓ done — 8 full morphological (es/fr/de/ru/ja/pt/it/en) + 5 dictionary-mode (ar/he/zh/la/grc) + 4 morphology-light (ko/hi/tr/fi) = 17 total. |
| V7. Dead and historic language annotation mode | ~ partial — Latin and Koine Greek deepened to morphology-light with UD treebank annotations (ITTB, PROIEL + MorphGNT); conjugation type + tense/mood/person emitted. Perseus/Logeion API integration for full classical lexicon coverage remains open. |

---

## What is genuinely open

These are the only items without a completed implementation:

**Manual keyboard + screen-reader test** — The WCAG 2.1 AA code audit is done and 8
issues were fixed; automated static a11y tests cover 38 ARIA/CSS invariants; Tests 13–17
(zoom, reduced-motion, offline states, Practice tab) are documented in `MANUAL_ACCESSIBILITY_TEST.md`.
A human keyboard-only walkthrough and NVDA/VoiceOver smoke test have not been run.
See `MANUAL_ACCESSIBILITY_TEST.md` for the structured session results template.

**Full spaCy-model morphological plugins for additional languages** — Hindi,
Turkish, and Finnish now have suffix-rule morphology-light plugins (no model
required); full spaCy-model-backed versions with richer agreement/case analysis
remain open. Each would require installing a suitable model and expanding the
suffix logic into full morphological extraction.

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

**Classical-text lexicon depth** — Latin and Koine Greek now have ~3 400 and ~27 000
morphologically-annotated forms respectively (UD ITTB + PROIEL/MorphGNT), plus curated
A1–B1 vocabularies in the harvest pipeline. Perseus Digital Library / Logeion API
integration would further improve attested-form coverage and gloss quality for forms
outside these corpora. The offline script infrastructure (harvest_language_data.py) is
ready to ingest additional lexicon sources.

**`source_progression` reading continuity** — **done**: `GET /reading/{id}` and
`PATCH /reading/{id}` expose the per-(user, document) reading position.
`POST /ingest` now creates a `SourceProgressionRow` at ingestion time with
`sentences_total` set from the parsed sentence count. `GET /recommend` loads
in-progress documents and sorts continuation sentences (at or after
`next_position`) first within the difficulty window, with an `is_continuation`
flag in each response item. 14 new tests in `test_source_progression.py`.

**Grammatical label localisation** — Both lesson prose (`backend/lesson/l10n.py`) and
frontend UI strings (`frontend/js/i18n.js`) are now localised. The one remaining
English-only layer is the terminal grammatical label values (person `"third"`, number
`"singular"`, tense `"present"`, mood `"indicative"`) produced by `generators.py`.
For most learners the mixed output is adequate; full label localisation would require a
second lookup table in `l10n.py`.

---

## What remains before deployment or user testing

*These are not implemented in this pass and are NOT deployment/onboarding/user-testing tasks.
This section documents known limitations and future work.*

1. **Manual AT run** — Human keyboard-only + NVDA + VoiceOver session using `MANUAL_ACCESSIBILITY_TEST.md`. Must record results in `docs/accessibility_results/`. Not automated.
2. **Database migration on production** — `alembic upgrade head` must be run on the target PostgreSQL instance before `0016_analytics` tables and columns are live.
3. **Analytics opt-out UI** — `UserRow.analytics_opt_out` backend column and service exist. A frontend toggle (Settings or Privacy page) to expose opt-out has not been built.
4. **Analytics instrumentation call sites** — `backend/services/analytics.py` (`maybe_record_event`) is written and tested but not yet wired to any actual route (parse, review, recommend, etc.). Instrumentation calls must be added to route handlers when ready.
5. ~~**Greek article agreement display**~~ — **done** (2026-05-29): `article_agrees_with` rendered as "Article agrees: nominative · masculine · singular" field in vocabulary and conjugation lessons.
6. ~~**Latin noun suffix hints display**~~ — **done** (2026-05-29): `case_hint`, `number_hint`, `gender_hint`, `ambiguity_note` rendered as labelled fields ("Case (hint)", "Number (hint)", "Gender (hint)", "Ambiguity") in vocabulary lessons. 11 tests in `test_lesson_gen.py`.
7. **`RECOMMEND_UI_I18N` keys — frontend wiring** — Export added to `i18n.js`, tests pass. No frontend component consumes `provenance`, `cefr_level`, or `recommendation_reason` from the recommend response yet.
8. **CEFR A2–C2 vocabulary tables** — `cefr_vocab.py` only covers A1. CEFR filter in `/recommend-text?cefr=` will return empty results for most sentences until corpus pipeline produces more `cefr_equivalent`-tagged documents.
9. **Full spaCy morphology for hi/tr/fi** — Still morphology-light (suffix rules); improvements to false positives made but full model-backed morphology remains open.
10. **Perseus/Logeion API integration** — Latin/Greek lexicon depth limited to ~3 400 / ~27 000 attested forms. API integration would improve coverage of rare forms.
11. ~~**Grammatical label localisation**~~ — **done** (2026-05-29): "pos" category added to `_GRAM_LABELS` in `l10n.py` (bare POS labels for all 11 UI languages). `_build_vocabulary()` and `_build_inflection()` now call `gram_label("pos", ...)` for the "Part of speech" field and MC pool; gender/number fields in vocabulary also localised. Latin suffix hints (case_hint/number_hint/gender_hint) and Greek article_agrees_with values run through `gram_label()`. 16 new tests in `TestGrammaticalLabelLocalisation`.
12. **Docker Compose end-to-end smoke test in CI** — Not in automated CI; currently manual `make up` only.

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
