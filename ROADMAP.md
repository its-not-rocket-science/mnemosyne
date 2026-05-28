# Mnemosyne Roadmap

Status markers: **implemented** · **partial** · **planned** · **deferred**

---

## What is built (current state)

| Feature | Status | Notes |
|---------|--------|-------|
| FastAPI scaffold + static frontend | implemented | No build step; vanilla JS + Web Components |
| Spanish NLP plugin (`es_core_news_sm`) | implemented | Vocabulary, conjugation, agreement, idiom, grammar, nuance; single-pass spaCy |
| French NLP plugin (`fr_core_news_sm`) | implemented | Vocabulary, conjugation, agreement; paradigm class; reflexive detection |
| German NLP plugin (`de_core_news_sm`) | implemented | Vocabulary, conjugation, `case_agreement`; separable verbs; 3-gender, 4-case |
| Russian NLP plugin (`ru_core_news_sm`) | implemented | Vocabulary, conjugation (aspect + past-tense gender), `case_agreement`; 6-case |
| Japanese plugin (`ja_core_news_sm`) | implemented | Vocabulary with hiragana readings; SudachiPy segmentation; particles filtered |
| Arabic plugin (dictionary mode) | implemented | Sentence splitting; whitespace tokenisation; tashkeel normalisation; RTL |
| Hebrew plugin (dictionary mode) | implemented | Sentence splitting; whitespace tokenisation; nikud normalisation; RTL |
| Mandarin Chinese plugin (jieba + pypinyin) | implemented | jieba segmentation; tone-marked pinyin; CJK script family |
| Portuguese NLP plugin (`pt_core_news_sm`) | implemented | Vocabulary, conjugation, agreement; ser/estar copula; ter_perfect; personal infinitive nuance |
| Italian NLP plugin (`it_core_news_sm`) | implemented | Vocabulary, conjugation, agreement; essere/avere auxiliary; stare_progressive; grammar + nuance |
| Latin plugin (morphology-light) | implemented | Regex tokenisation; ~3 400 UD ITTB morph-indexed forms; conjugation/grammar types; suffix rules for imperfect/future/infinitive; tense_pool + mood_pool declared |
| Koine Greek plugin (morphology-light) | implemented | Polytonic normalisation; ~27 000 MorphGNT+PROIEL morph-indexed forms; conjugation/grammar types; SBL transliteration; script_family="greek" |
| Korean plugin (morphology-light) | implemented | kiwipiepy segmentation; vocabulary only; script_family="hangul" |
| Hindi plugin (morphology-light) | implemented | Devanagari word regex; IAST romanisation; suffix rules for verb aspect/tense and noun case; postposition tagging |
| Turkish plugin (morphology-light) | implemented | Vowel-harmony-aware suffix rules; plural, case, tense, mood detection; morphology_quality="low" |
| Finnish plugin (morphology-light) | implemented | 15-case suffix detection; vowel harmony; conjugation tense/mood/person rules; morphology_quality="low" |
| English stub plugin | implemented | Regex vocab only; no morphology |
| Plugin registry with multi-language support | implemented | `ENABLED_LANGUAGES` filter; auto-discovery; collision warning on duplicates |
| Canonical knowledge layer | implemented | UUID-v5 PKs; `(language, type, canonical_form)` unique; `object_relations`; `surface_forms` accumulation |
| Non-Latin DB round-trip verified | implemented | Arabic, Hebrew, Chinese, Russian, Japanese canonical forms tested through SQLite |
| FSRS-5 spaced-repetition scheduler | implemented | Pure Python; all functions deterministic |
| `POST /parse` with Redis cache | implemented | SHA-256 key; 1 h TTL; graceful Redis-down degradation |
| `GET /lesson/{id}` | implemented | DB-first; plugin in-session fallback |
| `POST /review` | implemented | DB state authoritative; payload fallback on outage |
| `GET /dashboard` | implemented | `?language=` filter; known/weak/new/due_for_review |
| `GET /metrics` | implemented | Retention, success_rate, stability, weakest-10, by_language, by_type |
| `GET /recommend` + `/recommend-text` | implemented | i+1 window; difficulty_label (easy/ideal/hard); progression |
| `GET /languages` | implemented | Lists active plugins with direction metadata |
| `GET /health` + `GET /ready` | implemented | Liveness and readiness probes |
| Alembic migrations | implemented | `0000_baseline` + migrations 0001–0009; `alembic upgrade head` verified on fresh SQLite DB; production startup uses subprocess alembic only |
| Accessibility baseline | implemented | Skip link, focus trap (`inert` + Tab intercept), ARIA live regions, reduced-motion, 44 px touch targets, roving tabindex on auth tabs, `role="list"` on pill lists; static WCAG 2.1 AA code audit complete — 8 issues found and fixed (SC 1.4.11 border contrast, SC 2.5.3 label-in-name, SC 1.3.1 list role, plus 5 issues from prior audit); manual keyboard + screen-reader run recommended before public beta |
| RTL layout support | implemented | `dir`/`lang` applied to all text elements in modal; `<bdi>` isolation in drill feedback; CSS uses logical properties throughout |
| Multi-user architecture | implemented | `X-User-Id` header; `get_current_user` dependency; per-user isolation across all routes; `UserLanguagePreferenceRow` table; `/users/me/*` preference CRUD |
| User authentication | implemented | `/auth/register` + `/auth/login`; HS256 JWT; `get_current_user` verifies Bearer token or falls back to `X-User-Id`; login/logout UI |
| Rate limiting | implemented | `slowapi`; JWT > X-User-Id > IP key; configurable `RATE_LIMIT_PARSE`; per-user independent counters |
| Review event log | implemented | `ReviewEventRow` per review; `mastery_score_before/after`; `GET /metrics` exposes `reviews_today`, `streak_days`, `daily_activity` |
| Privacy policy + account deletion | implemented | `DELETE /users/me` cascades all rows; `frontend/privacy.html`; "Delete account" button with confirmation |
| Real dictionary integration | implemented | Wiktionary REST API; background enrichment of vocabulary gloss; `ENABLE_DICTIONARY_LOOKUP` flag; attempt-tracking prevents redundant fetches |
| FSRS per-user calibration | implemented | Bias-correction over `ReviewEventRow`; `UserFsrsParamsRow`; `GET/PATCH /users/me/fsrs-params`; `POST /users/me/calibrate`; `POST /review` uses per-user `desired_retention` |
| Sentry error monitoring | implemented | SDK init in `main.py` when `SENTRY_DSN` is set; environment tag auto-derived from `DEBUG` |
| Request-id structured logging | implemented | `RequestIdFilter` context-var; 8-char hex ID on every log line and `request.state.request_id` |
| Portuguese NLP plugin | implemented | `pt_core_news_sm`; vocabulary, conjugation, agreement, ser/estar copula, ter_perfect, personal infinitive; idioms; 62 tests |
| Italian NLP plugin | implemented | `it_core_news_sm`; vocabulary, conjugation, agreement, essere/avere auxiliary, stare_progressive; idioms; 60 tests |
| Source progression tracking | implemented | `SourceProgressionRow`; `GET/PATCH /reading/{id}`; `POST /ingest` creates row; `GET /recommend` surfaces `is_continuation` items first |
| Backend startup resilience | implemented | `app.state.startup_errors`; `X-Startup-Warning` response header; `/ready` startup field; frontend banner on degraded-startup detection |
| CEFR A1 vocabulary tables | implemented | `backend/plugins/cefr_vocab.py`; ~200–250 lemmas per language for es/fr/de/it/pt/ru/ja; suppresses `_sm` model OOV false-positives; adds `cefr_level: "A1"` to lesson_data; displayed in vocabulary lesson |
| Language capability user-facing labels | implemented | `ANALYSIS_DEPTH_USER_LABELS` dict + `@computed_field analysis_depth_label` in `LanguageCapabilities`; `CAPABILITY_LABELS_I18N` in `i18n.js` for 11 UI languages; internal IDs unchanged |
| Gold linguistic fixtures | implemented | Gold fixture files for all 17 languages; `assert_min_vocabulary_count` and `assert_no_confidence_above` assertions; `pytest_terminal_summary` per-language coverage report |
| Morphology false-positive fixes (hi/tr/fi) | implemented | Hindi single-char matra min-length guard; Turkish `_AORIST_BLOCKLIST` for common -ar/-er words; Finnish possessive suffix detection + `_INESSIVE_GUARD` |
| Latin noun suffix hints | implemented | `_LATIN_NOUN_SUFFIXES` table + `_extract_latin_noun_suffix_hint`; `case_hint`, `number_hint`, `gender_hint`, `ambiguity_note` in `lesson_data` for non-morph-indexed forms |
| Greek article agreement bigrams | implemented | `_ARTICLE_FORMS` for all 17 Koine article forms; pre-pass adds `article_agrees_with` to lesson_data of following tokens |
| Corpus product features | implemented | `/recommend-text` returns `cefr_level`, `provenance`, `recommendation_reason`; `?continuation=true`, `?cefr=`, `?max_words=` filters; `RECOMMEND_UI_I18N` in `i18n.js` |
| Privacy-conscious analytics | implemented | `LearningEventRow` table; `UserRow.analytics_opt_out`; `backend/services/analytics.py` with opt-out check and GDPR deletion; `GET /metrics/learning-events` dev endpoint (DEBUG only); migration 0016 |
| Manual accessibility test extensions | implemented | Tests 13–17 in `MANUAL_ACCESSIBILITY_TEST.md`; `TestReducedMotionCSS`, `TestConceptDialogStructure`, `TestPracticeTabInputs`, `TestLiveRegionCompleteness` (38 tests) |

---

## Category 1 — Release hardening

These are blockers or near-blockers before the system is safe to run against real data.
See `BETA_GAP_REPORT.md` for the detailed blocker breakdown by alpha / beta / vision tier.

- **Replace `create_all` with `alembic upgrade head`** on fresh startup. `create_all` silently diverges from migration history. (*partial → implemented*) — **Private alpha blocker A1**
- **`max_chars` guard on `/parse` and `/ingest`** — long texts block the event loop. Configurable, default 10 000 characters. Return 413 above the limit. — **Private alpha blocker A2**
- **Data export endpoint** — `GET /users/me/export` returns all knowledge state as JSON. — **Private alpha blocker A4**
- **JWT authentication** — `POST /auth/register` + `POST /auth/login`; replace header-only identity in `get_current_user`. — **Public beta blocker B1**
- **Login/register UI** — frontend login panel, JWT in `sessionStorage`, logout. — **Public beta blocker B2**
- **WCAG 2.1 AA audit** — ~~keyboard-only run through the full parse → lesson → review flow; screen-reader smoke test with NVDA and VoiceOver.~~ **Code-level audit done and three issues fixed**: (1) SC 1.4.11 Non-text Contrast — input/textarea/select/button borders raised from 20–25% to 45% CanvasText (≥ 3:1 against Canvas in light + dark); pill button borders raised from 35% to 60% (verify in browser per type-color); (2) SC 2.5.3 Label in Name — Speak button `aria-label` changed from "Listen to example" to "Speak example aloud" so visible label is contained in accessible name; (3) SC 1.3.1 — `role="list"` added to pill `<ul>` to restore list semantics removed by `list-style:none` in Safari VoiceOver. Manual keyboard + screen-reader smoke-test still recommended before public launch. — **Public beta blocker B3**
- **CORS lockdown** — ~~warn-on-`*` is already in `main.py`; wire it to a deployment checklist.~~ **done**: `Settings._reject_wildcard_cors_in_production` hard-fails startup when `DEBUG=false` + `CORS_ORIGINS=["*"]`; `DEPLOYMENT.md` pre-launch checklist covers CORS, JWT, DB credentials, HTTPS, Redis rate-limit storage, and smoke tests. — ~~**Public beta blocker B5**~~
- **Rate limiting** — ~~per-IP and per-user rate limiting on the parse endpoint at minimum.~~ **done**: `slowapi` limiter; JWT > X-User-Id > IP key function; configurable `RATE_LIMIT_PARSE`; tests in `test_rate_limit.py`. — ~~**Public beta blocker B6**~~
- **Privacy policy + data deletion** — ~~`DELETE /users/me` removes all user data; visible privacy policy page.~~ **done**: `DELETE /users/me` cascades all user rows; `frontend/privacy.html`; "Delete account" button in header with confirmation; privacy link in footer. — ~~**Public beta blocker B7**~~
- **Error monitoring** — ~~Sentry SDK or equivalent before public traffic.~~ **done**: `sentry_sdk` initialised in `main.py` when `SENTRY_DSN` env var is set; `sentry_environment` defaults to `development` / `production` from `DEBUG`. — ~~**Public beta blocker B8**~~
- **Structured request logging** — ~~add `request_id` to each request's log lines for trace correlation.~~ **done**: `RequestIdFilter` injects `request_id` (8-char hex UUID) into every log line via context var; middleware sets `request.state.request_id`. — ~~**done**~~
- **Background DB persist** — ~~currently `_persist_parse` runs in the request path after the response is built. Move to a true background task so the client is not held waiting on DB I/O.~~ **done**: `BackgroundTasks.add_task(_persist_parse_background, ...)` after response is built; factory injected so tests can override. — ~~**done**~~
- **< 2 s parse time for 500 words** — ~~profile `es_core_news_sm` on the target hardware; document the result.~~ **done**: 76 ms mean / 86 ms max for 480 words (5 runs, warm model). 26× headroom.

---

## Category 2 — Multilingual foundations

These unlock meaningful expansion beyond Spanish.

- **Full French plugin** — ~~replace the regex stub with `fr_core_news_md`~~ **done**: `fr_core_news_sm`, vocabulary + conjugation + agreement. — ~~**Private alpha blocker A3, Public beta blocker B9**~~
- **Full German plugin** — ~~`de_core_news_sm`~~ **done**: `de_core_news_sm`, vocabulary + conjugation + `case_agreement`; separable verbs; canonical_form conventions documented.
- **Full Russian plugin** — **done**: `ru_core_news_sm`, full morphology with aspect system, 6-case agreement, past-tense gender-based conjugation.
- **Full Japanese plugin** — **done**: `ja_core_news_sm` + SudachiPy, vocabulary with hiragana readings, katakana→hiragana conversion.
- **Modal RTL fix** — ~~apply `dir`/`lang` to example text and drill prompts~~ **done**: `#applyTargetLang` covers title, example text, drill prompts/text/input; `<bdi>` isolation in fill-blank and multiple-choice feedback. CSS uses logical properties throughout. — ~~**Public beta blocker B4**~~
- **RTL CSS audit** — **done**: `[dir="rtl"]` text-alignment; logical margin/padding/size properties throughout modal; close button stays at inline-end independent of content direction.
- **Non-Latin script round-trip tests** — **done**: 43 tests covering Arabic, Hebrew, Chinese, Russian, Japanese through `canonical_object_id`, SQLite insert, retrieve, and lossless assertion. API-level RTL pipeline tests included.
- **`canonical_form` conventions for non-Latin morphology** — **done**: `PLUGIN_AUTHOR_GUIDE.md` documents `case_agreement`, Russian/Japanese patterns, and a new "Agglutinative Languages" section covering Finnish (15-case nominal + conjugation) and Turkish (tense/aspect/mood/person/number/voice) canonical form schemes with axis-order rules and lesson-builder compatibility notes.
- **Lesson generator pluggable templates** — ~~`build_lesson()` produces English prose regardless of target language.~~ **done**: `LanguageCapabilities.tense_pool` / `mood_pool` let each plugin declare language-appropriate MC drill options; `LessonContext` carries them through to `_build_conjugation`; mood MC drill wired up (was defined but not emitted). Spanish/French/German pools set. — ~~**planned**~~
- **`ENABLED_LANGUAGES` documentation** — ~~explain how to run a single-language deployment and how to add a new language to an existing database without affecting other users' data.~~ **done**: `.env.example` documents the variable with inline notes; CONTRIBUTING.md has "Single-language deployments" and "Adding a language to an existing deployment" sections. — ~~**planned**~~
- **Plugin loading resilience** — ~~a plugin that raises during `create_plugin()` is already skipped with a `WARNING`. Add a `GET /ready` signal that reports degraded-plugin status so operators can see partial failures.~~ **done**: `PluginRegistry._failed` records failures; `GET /ready` includes a `plugins` field (`"ok"` or `{"degraded": [...]}`) and returns 503 when any plugin failed to load. — ~~**planned**~~

---

## Category 3 — Vision-complete / long-horizon work

These follow from the starting vision but require category 1 and 2 to be solid first.

- **User accounts** — **done**: JWT auth (`/auth/register` + `/auth/login`), login/register UI, JWT in `sessionStorage`, logout, per-user isolation across all routes, `UserLanguagePreferenceRow` preference CRUD. See B1/B2 in category 1.
- **Review event log** — **done**: `ReviewEventRow` append-only table (migration 0006); written by `POST /review` after every FSRS update; `mastery_score_before/after` stored; `GET /metrics` queries `review_events` for `reviews_today`, `streak_days`, `daily_activity`. FSRS calibration (`POST /users/me/calibrate`) uses `ReviewEventRow` history for per-user bias correction.
- **Real dictionary integration** — **done**: `backend/dictionary/wiktionary.py` fetches English glosses from the Wiktionary REST API; `backend/dictionary/enrichment.py` enriches vocabulary `CanonicalObjectRow` objects post-parse in the background; gated by `ENABLE_DICTIONARY_LOOKUP=true` in `.env`. Glosses stored in `lesson_data["gloss"]` — consumed by existing `_build_vocabulary` and `_build_dictionary` builders with zero changes.
- **Real translation integration** — **done**: `POST /translate` endpoint; LibreTranslate + MyMemory providers; attribution required by MyMemory TOS included in response; results cached to `lesson_data["translation"]`; background enrichment via `/parse` when `ENABLE_TRANSLATION_ENRICHMENT=true`; lesson generators surface translation field.
- **FSRS parameter fitting** — **done**: per-user `desired_retention` calibration via bias-correction over `ReviewEventRow` history. `UserFsrsParamsRow` table; `GET/PATCH /users/me/fsrs-params`; `POST /users/me/calibrate`; `POST /review` uses per-user retention threshold.
- **PWA / offline mode** — **done**: `frontend/sw.js` caches app shell (cache-first for CSS/JS/HTML); `frontend/manifest.json` enables install; `frontend/js/offline.js` queues failed reviews in IndexedDB; drains queue on `window.online`. FastAPI now serves the frontend at `/` so the SW gets same-origin registration. **Offline status indicator** (show queued-review count while offline) — **deferred**: badge UI removed for now; queue drain logic retained. Re-add as a toast or status-bar indicator once the layout is stable.
- **Background processing** — **done**: `POST /parse/jobs` accepts up to `MAX_JOB_CHARS` (default 100 k); NLP runs in a thread-pool executor; `GET /parse/jobs/{id}` for polling; `GET /parse/jobs/{id}/events` for SSE progress stream. All parses route through the job API with a live progress bar (no text-size threshold). In-process `JobStore` with subscriber fan-out; multi-worker note documented.
- **Dead and historic language support** — **done**: Latin (`la`) and Arabic (`ar`) dictionary-mode plugins already implemented. New: Koine Greek (`grc`) — ~100-entry NT Greek lexicon; polytonic diacritic normalisation (accents, breathings, iota subscript, diaeresis); SBL-simplified transliteration stored in `lesson_data["romanized"]` for script-view toggle; `script_family="greek"` added to `ScriptFamily` literal; honest capability declarations throughout. **Updated (2026-05-27):** Latin and Koine Greek deepened to `morphology_light` using offline UD treebank annotations (ITTB, PROIEL) and MorphGNT; morphological features overlaid in `lesson_data`; confidence scales 0.50–0.80 based on data availability; `scripts/ingest_classical_morph.py` for rebuilding the indices.
- **Idiom and multiword-expression detection** — **done**: German and Russian plugins now extract idioms via `_IDIOM_TABLE` (longest-match, position-overlap prevention). Russian also extracts `nuance` objects for perfective/imperfective aspect pairs with `RelationHint(relation_type="nuance_of")`. All types carry `meaning`, `register`, and `note` in `lesson_data`. 25 new tests in `test_idiom_nuance.py` (token-injection pattern, no spaCy model required).
- **Mobile / responsive layout audit** — **done**: three targeted 320 px fixes: (1) `min-inline-size: 0` on `.user-info__email` so `text-overflow: ellipsis` actually fires inside the flex header; (2) `flex: 1 1 0` on `.drill-input` so fill-blank inputs fill their row; (3) `@media (max-width: 20rem)` inside the modal shadow DOM switches `.fields` from `auto 1fr` two-column to stacked single-column and tightens drill padding. All other layout elements already use `clamp()`, `flex-wrap`, and logical properties and handle 320 px without changes.
- **Shallow morphological plugins for Hindi, Turkish, and Finnish** — **done** (2026-05-27): all three added as suffix-rule `morphology_light` plugins. Hindi: Devanagari word regex, IAST romanisation, verb aspect/tense and noun case suffix rules, postposition tagging. Turkish: vowel-harmony-aware suffix rules for plural, case, tense, and mood (false-positive-prone short suffixes removed; confirmed tests pass). Finnish: 15-case suffix detection (inessive through comitative), vowel harmony, 58 tests in `test_hindi_turkish_finnish_plugins.py`. All three declared with `morphology_quality="low"` and appropriate nuance_capabilities. All three covered by the harvest pipeline via FrequencyWords/OpenSubtitles. Full spaCy-model morphology for the deeper Indian/Turkic/Finnic coverage remains **planned**.
- **Latin and Koine Greek deepened to morphology-light** — **done** (2026-05-27/28): conjugation and grammar types emitted from morph indices; tense_pool/mood_pool declared; Greek morphology_quality raised to "medium" (27k forms vs Latin's 3.4k); suffix rules fill Latin imperfect/future/infinitive gaps. Curated A1–B1 inline vocabularies added to harvest pipeline (la/grc). Grammar rules A1–C2 for both languages added to harvest pipeline.
- **CEFR A2 vocabulary** — **done** (2026-05-28): `A2` tables added to `cefr_vocab.py` for all 10 languages (es/fr/de/it/pt/ru/ja/zh/ar/he); 245–268 lemmas per language covering extended family, workplace/school, travel, home, weather, health, shopping, food, entertainment, sport, communication/tech, nature, extended adjectives/verbs/adverbs. Plugin `_vocab_confidence` priority: A1 (0.90) → A2 (0.88) → in-vocab (0.85) → OOV (0.50). `cefr_level: "A2"` added to lesson_data. 9 tests in `test_cefr_a2_vocab.py`.
- **CEFR B1 vocabulary** — **done** (2026-05-28): `B1` tables added to `cefr_vocab.py` for all 10 languages (es/fr/de/it/pt/ru/ja/zh/ar/he); 241–308 lemmas per language covering abstract concepts, opinions/argumentation, news/current affairs, environment/sustainability, social issues, and extended cognitive/communicative vocabulary. Confidence 0.86. Priority: A1 (0.90) → A2 (0.88) → B1 (0.86) → in-vocab (0.85) → OOV (0.50). 10 tests in `test_cefr_b1_vocab.py`.
- **CEFR B2–C2 vocabulary** — **done** (2026-05-28): `B2`, `C1`, `C2` tables added to `cefr_vocab.py` for all 10 languages. B2 60–199 lemmas/lang (advanced academic/professional; confidence 0.84 OOV-only). C1 100–167 lemmas/lang (formal/literary/philosophical; confidence 0.82 OOV-only). C2 92–165 lemmas/lang (literary/archaic-formal; confidence 0.80 OOV-only). All levels disjoint from each other and from A1/A2/B1. 28 tests in `test_cefr_b2_c2_vocab.py`. Priority chain: A1 (0.90) → A2 (0.88) → B1 (0.86) → in-vocab (0.85) → B2/C1/C2 OOV-suppression → OOV (0.50).
- **CEFR-graded lesson ordering** — **planned**: once A1–B2 tables are populated, expose `cefr_level` in `GET /recommend` results so the frontend can offer a "start from A1" mode that surfaces simple vocabulary first before graduating the learner through authentic-text sentences. Pairs with `source_progression` continuity already implemented.
- **Lesson text localisation** — **implemented**: `build_lesson()` explanations rendered in the learner's native language via `backend/lesson/l10n.py` for all 12 UI locales (en/es/fr/de/ru/ja/pt/it/ar/he/zh/ko). Static templates; zero-latency; deterministic. Untranslated L1 codes fall back to English. 326 tests in `test_l10n.py`. ~~Add an optional `l1_language` parameter threaded through `LanguageCapabilities`.~~
- **Frontend UI string localisation** — **implemented**: all hardcoded English strings in frontend components replaced with `t()`/`ti()` calls sourced from `frontend/js/i18n.js`. Covers `mnemosyne-modal`, `mnemosyne-pill`, `mnemosyne-text-panel`, `mnemosyne-top-nav`, and `main.js` (aria-announces, drill feedback, rating labels). The only remaining English-only layer is the grammatical terminal labels (`"third"`, `"singular"`, `"present"`) produced by `backend/lesson/generators.py` — see BETA_GAP_REPORT.md.
- **Classical lexicon depth** — **done** (2026-05-29): Latin morphological coverage expanded from ~3 400 → ~257 000 forms by ingesting noun/adjective paradigm tables from kaikki.org Wiktionary dump (`scripts/ingest_kaikki_la_morph.py`). Greek unchanged at ~27 000 forms (PROIEL + MorphGNT already broad). Latin `morphology_quality` upgraded from `"low"` to `"medium"`. Common noun forms (rosam, rosae, verbi, domino …) now carry full case/number/gender annotations. la_morph.json: 23 MB, loaded via `lru_cache`. Perseus/Logeion API integration remains deferred.

---

## Quality targets (ongoing)

- [x] `alembic upgrade head` is the only DB initialisation path (no `create_all` in production)
- [x] WCAG 2.1 AA on the core parse → review flow — **code-level fixes applied** (see B3 in category 1). Manual browser/AT run still recommended before public beta.
- [x] 90% branch coverage on `backend/srs/` and `backend/parsing/`
- [x] Parse time < 2 s for 500 words on the CI runner — **measured 76 ms mean / 86 ms max** (480 words, 5 runs, `es_core_news_sm`, warm model, dev machine). Hot spots: spaCy inference 47 ms, `_extract_idioms` O(idioms × tokens) scan 54 ms — both negligible at this scale. 26× headroom against the 2 s target.
- [x] Zero `# type: ignore` comments without an explanatory note
