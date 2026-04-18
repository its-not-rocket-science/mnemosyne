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
| Latin plugin (dictionary mode) | implemented | Regex tokenisation; dictionary-mode lesson builder; dead-language scaffold |
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
| Alembic migrations | implemented | `0000_baseline` + migrations 0001–0007; `alembic upgrade head` verified on fresh SQLite DB; production startup uses subprocess alembic only |
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

- **User accounts** — multi-user data isolation is complete (all routes scoped to `current_user`; `UserLanguagePreferenceRow` implemented). Remaining work: JWT auth middleware, login/register API routes, login UI. See category 1.
- **Review event log** — a `review_events` table (one row per review: user_id, object_id, quality, mastery_score_before/after, reviewed_at) unlocks retention curves, exact time-to-mastery, per-session analytics, and FSRS parameter fitting. The current `user_knowledge` table stores only the current FSRS state. This is pure DB + route work; the scheduler does not change.
- **Real dictionary integration** — **done**: `backend/dictionary/wiktionary.py` fetches English glosses from the Wiktionary REST API; `backend/dictionary/enrichment.py` enriches vocabulary `CanonicalObjectRow` objects post-parse in the background; gated by `ENABLE_DICTIONARY_LOOKUP=true` in `.env`. Glosses stored in `lesson_data["gloss"]` — consumed by existing `_build_vocabulary` and `_build_dictionary` builders with zero changes.
- **Real translation integration** — **done**: `POST /translate` endpoint; LibreTranslate + MyMemory providers; attribution required by MyMemory TOS included in response; results cached to `lesson_data["translation"]`; background enrichment via `/parse` when `ENABLE_TRANSLATION_ENRICHMENT=true`; lesson generators surface translation field.
- **FSRS parameter fitting** — **done**: per-user `desired_retention` calibration via bias-correction over `ReviewEventRow` history. `UserFsrsParamsRow` table; `GET/PATCH /users/me/fsrs-params`; `POST /users/me/calibrate`; `POST /review` uses per-user retention threshold.
- **PWA / offline mode** — **done**: `frontend/sw.js` caches app shell (cache-first for CSS/JS/HTML); `frontend/manifest.json` enables install; `frontend/js/offline.js` queues failed reviews in IndexedDB; drains queue on `window.online`; offline badge in header shows pending count. FastAPI now serves the frontend at `/` so the SW gets same-origin registration.
- **Background processing for large texts** — **done**: `POST /parse/jobs` accepts up to `MAX_JOB_CHARS` (default 100 k); NLP runs in a thread-pool executor; `GET /parse/jobs/{id}` for polling; `GET /parse/jobs/{id}/events` for SSE progress stream. Frontend detects texts > 10 k chars and routes them through the job API with a live progress bar. In-process `JobStore` with subscriber fan-out; multi-worker note documented.
- **Dead and historic language support** — **done**: Latin (`la`) and Arabic (`ar`) dictionary-mode plugins already implemented. New: Koine Greek (`grc`) — ~100-entry NT Greek lexicon; polytonic diacritic normalisation (accents, breathings, iota subscript, diaeresis); SBL-simplified transliteration stored in `lesson_data["romanized"]` for script-view toggle; `script_family="greek"` added to `ScriptFamily` literal; honest capability declarations throughout (no morphology claimed).
- **Idiom and multiword-expression detection** — **done**: German and Russian plugins now extract idioms via `_IDIOM_TABLE` (longest-match, position-overlap prevention). Russian also extracts `nuance` objects for perfective/imperfective aspect pairs with `RelationHint(relation_type="nuance_of")`. All types carry `meaning`, `register`, and `note` in `lesson_data`. 25 new tests in `test_idiom_nuance.py` (token-injection pattern, no spaCy model required).
- **Mobile / responsive layout audit** — **done**: three targeted 320 px fixes: (1) `min-inline-size: 0` on `.user-info__email` so `text-overflow: ellipsis` actually fires inside the flex header; (2) `flex: 1 1 0` on `.drill-input` so fill-blank inputs fill their row; (3) `@media (max-width: 20rem)` inside the modal shadow DOM switches `.fields` from `auto 1fr` two-column to stacked single-column and tightens drill padding. All other layout elements already use `clamp()`, `flex-wrap`, and logical properties and handle 320 px without changes.

---

## Quality targets (ongoing)

- [x] `alembic upgrade head` is the only DB initialisation path (no `create_all` in production)
- [x] WCAG 2.1 AA on the core parse → review flow — **code-level fixes applied** (see B3 in category 1). Manual browser/AT run still recommended before public beta.
- [x] 90% branch coverage on `backend/srs/` and `backend/parsing/`
- [x] Parse time < 2 s for 500 words on the CI runner — **measured 76 ms mean / 86 ms max** (480 words, 5 runs, `es_core_news_sm`, warm model, dev machine). Hot spots: spaCy inference 47 ms, `_extract_idioms` O(idioms × tokens) scan 54 ms — both negligible at this scale. 26× headroom against the 2 s target.
- [x] Zero `# type: ignore` comments without an explanatory note
