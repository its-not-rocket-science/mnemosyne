# Beta Gap Report — Mnemosyne

*Date: 2026-04-15. Written against the current `main` branch.*

This report answers two questions separately:

1. **What is required to ship a credible private alpha / public beta?**
2. **What is required to keep moving toward the original vision of a fully multilingual, authentic-text language learning platform?**

They are not the same question. Some beta blockers are irrelevant to the vision. Some vision items would be premature to pursue before beta. The report names both without conflating them.

---

## Current strengths

These are genuinely solid and should not be second-guessed.

- **Core loop works.** Parse → lesson → review → recommend is complete, tested, and persistent. 920 tests collected.
- **FSRS-5 is correct.** Pure Python, deterministic, no external dependencies. Survives restart, DB outage, and re-parse. Review state is authoritative in the DB; payload fallback on outage.
- **Canonical knowledge layer is robust.** UUID-v5 PKs mean the same word in two different texts always maps to the same DB row. Surface forms accumulate across parses. Object relations are stored. This is the right foundation for cross-text reinforcement and it will not need to be redesigned.
- **Plugin architecture is clean.** Structural typing, no ABC, no registration step — drop a file in `backend/plugins/` and the server picks it up. Plugins are isolated; a crash in one does not affect others.
- **Accessibility baseline is real.** Skip link, focus trap, ARIA live regions, reduced motion, 44 px touch targets. Not complete (WCAG AA not audited end-to-end) but deliberately built.
- **Multi-user architecture is complete.** `X-User-Id` header, `"default"` fallback, per-user isolation across all routes, `UserLanguagePreferenceRow` table, preference CRUD at `/users/me/*`. The schema was right all along; the routes are now wired correctly.
- **RTL plugin metadata is real.** `direction`, `script_family`, `tokenization_mode`, `morphology_depth` on every plugin. Frontend reads these at load and applies `dir`/`lang` to sentence text. Non-Latin font stacks in `global.css`.
- **i+1 recommendation engine works.** Difficulty window shifts with mastery. Per-language calibration profiles. Passage context for ingested documents. Deduplication of identical sentence texts.
- **Operational baseline is sound.** Health + readiness probes. CORS wildcard warning. Credential hygiene warning. Redis graceful degradation. Per-route timing logs.

---

## Current reality

These are true today. Name them plainly.

- **Five production-quality languages.** Spanish, French, German, Russian, and Japanese have full spaCy-backed morphological pipelines. Arabic, Hebrew, Chinese, and Latin are in dictionary/vocabulary mode. The multi-language promise is architecturally solid and partially delivered.
- **No authentication beyond a header.** `X-User-Id` is trivially spoofable. Anyone who knows the API can read or overwrite another user's knowledge state. This is acceptable for local single-user use; it is not acceptable for a hosted service with multiple users who do not trust each other.
- **No login UI.** There is no frontend for user registration, login, or session management. The multi-user backend is complete; the frontend has no way to surface it.
- **NLP blocks the event loop.** `plugin.analyze_text()` runs synchronously in the FastAPI handler. For a 500-word Spanish text this is < 1 s and acceptable. For a 5 000-word paste it will block other requests. There is no `max_chars` guard.
- **`create_all` still runs on startup.** Alembic migrations exist (0001–0004) but `Base.metadata.create_all` is still the startup path. On a fresh database this works; on an existing database that has been migrated, it is silently inconsistent.
- **RTL layout is complete.** `dir`/`lang` are applied to all text elements in the modal (title, example text, drill text/prompt/input) via `#applyTargetLang`. `<bdi>` isolation is used in fill-blank and multiple-choice feedback so RTL answer strings do not scramble surrounding LTR punctuation. CSS uses logical properties throughout. 43 non-Latin round-trip tests (M4) cover Arabic, Hebrew, Chinese, Russian, Japanese through the DB and API pipeline.
- **No review event history.** `user_knowledge` stores only the current FSRS state. There is no record of when individual reviews happened, what quality rating was given, or what the mastery score was at each point. Retention curves, exact time-to-mastery, and per-session analytics are unavailable.
- **No data export.** A user has no way to get their knowledge state or review history out of the system.
- **Lesson generator is English-prose-centric.** `build_lesson()` produces sentences like "The word *X* is a noun" in English regardless of the target language. For a Spanish learner reading Spanish text this is acceptable. For a learner whose native language is not English, or for languages with grammatical concepts that do not map to English prose ("aspect", "classifier", "tone class"), it is a friction point.

---

## Private alpha blockers

*Definition: a small number of trusted testers (3–10) who accept rough edges and will give structured feedback.*

These are blockers because they either cause data loss, prevent setup, or make the system embarrassing to hand to a real person.

### A1. `alembic upgrade head` on fresh startup

**Why it blocks:** `create_all` diverges silently from migration history. Alpha testers who set up from scratch via Docker Compose will end up with a schema that does not match what `alembic upgrade head` would produce. When the migration is fixed later, their database will be broken. Fix this before the first external tester ever runs the app.

**What to do:** In `main.py` lifespan, replace `conn.run_sync(Base.metadata.create_all)` with `conn.run_sync(lambda c: alembic.command.upgrade(alembic_cfg, "head"))` or an equivalent async-safe migration run.

### A2. `max_chars` guard on `/parse` and `/ingest`

**Why it blocks:** An enthusiastic tester who pastes a chapter will block the server for all other users. 10 000 characters is a reasonable default. Return 413 with a clear error message above the limit.

**What to do:** Add `max_chars: int = settings.max_parse_chars` to `ParseRequest`; validate in the route before calling the plugin. Document the setting in `.env.example`.

### A3. At least one working second language

**Why it blocks:** Spanish-only is a credibility problem even for a trusted internal alpha. The system claims to be multilingual. A French plugin backed by `fr_core_news_md` (or a German plugin backed by `de_core_news_sm`) demonstrates that the architecture works for more than one language. The scaffolds already exist; this is NLP work, not architecture work.

**What to do:** Implement the French plugin using `fr_core_news_md`. Extract vocabulary and conjugation. Tests already exist in `test_french_spacy.py` — make them pass.

### A4. Data export endpoint

**Why it blocks:** Alpha testers should be able to get their data out. This is a trust and dignity requirement, not a feature. A `GET /users/me/export` that returns all `UserKnowledgeRow` entries as JSON is sufficient.

### A5. Docker Compose works end-to-end

**Why it blocks:** Setup friction kills alpha testers before they start. Verify that `docker compose up` (PowerShell path documented in `CONTRIBUTING.md`) produces a running, testable instance. Document any Windows-specific gotchas.

---

## Public beta blockers

*Definition: an open or semi-open deployment accessible to strangers via the internet.*

Everything in private alpha plus the following.

### B1. Real authentication

**Why it blocks:** `X-User-Id` is not authentication. Any request with `X-User-Id: alice` is treated as Alice regardless of who sent it. On a hosted service this means any user can read or overwrite any other user's knowledge state. This is a hard blocker for any multi-user deployment.

**What to do:** JWT-based authentication via a `POST /auth/register` + `POST /auth/login` flow. The `get_current_user` dependency already exists and is the single injection point — replacing its implementation does not touch any route logic. No OAuth required for beta; a simple email + bcrypt-hashed password is sufficient.

### B2. Login and registration UI

**Why it blocks:** The backend auth is wired; the frontend has no login flow. Users who cannot log in cannot use the service.

**What to do:** A login/register panel in `index.html`. After login, store the JWT in `sessionStorage` (not `localStorage` — reduce XSS exposure) and include it in every API request as `Authorization: Bearer <token>`. Logout clears the token and returns to the login panel.

### B3. WCAG 2.1 AA audit on the core flow

**Why it blocks:** The accessibility baseline was built deliberately, but has not been audited end-to-end. Shipping a public beta without a keyboard-only run-through of parse → lesson → review exposes real users to barriers. Screen-reader smoke test with NVDA and VoiceOver at minimum.

**What to do:** Run the full flow keyboard-only. Fix any focus management gaps. Run `axe` or `Lighthouse` accessibility audit on the rendered page. Document the result.

### B4. RTL layout complete ✓ DONE

**Why it blocked:** The modal did not apply `dir` or `lang` to example text or drill prompts.

**What was done:**
1. `mnemosyne-modal.js` — `#applyTargetLang` applies `dir` and `lang` to: title, example text, all drill text/prompt elements, and fill-blank input. CSS uses logical properties throughout.
2. `<bdi>` elements wrap embedded target-language answers in fill-blank and multiple-choice feedback, preventing Unicode bidi algorithm from mis-ordering typographic quotes around RTL text.
3. `test_non_latin_roundtrip.py` — API-level RTL pipeline tests assert `direction="rtl"` on Arabic and Hebrew plugins via `GET /languages`, and verify Arabic/Hebrew parse requests return valid UUID object IDs.

### B5. CORS lockdown

**Why it blocks:** Wildcard CORS on a public endpoint is an XSS amplifier. The warning is logged; the fix is one config change. Document the required environment variable and add it to the deployment checklist.

### B6. Rate limiting

**Why it blocks:** No protection against a user who submits 1 000 parse requests in a minute, either accidentally or maliciously. The NLP endpoint is expensive. Add per-IP and per-user rate limiting at the FastAPI middleware layer or via a reverse proxy.

### B7. Privacy policy and data deletion

**Why it blocks:** Legally required in GDPR jurisdictions (and most others) for any service that stores personal data. A `DELETE /users/me` endpoint that removes all user knowledge state is the minimum implementation. A visible privacy policy page is the minimum disclosure.

### B8. Error monitoring

**Why it blocks:** Before accepting public traffic, you need to know when things break. Structured logging exists; centralised error capture (Sentry or equivalent) does not. Without it, a bug that affects 10% of requests is invisible until a user complains.

### B9. At least three production-quality language plugins

**Why it blocks:** Beta implies a real multilingual value proposition. Spanish + stubs does not demonstrate it. Spanish + French + German (or Spanish + French + Arabic, if RTL is prioritised) is a credible minimum.

---

## Multilingual blockers

*These are required to deliver on the multilingual promise, regardless of beta timeline.*

### M1. Full French plugin ✓ DONE

`backend/plugins/french.py` — `fr_core_news_sm`, vocabulary + conjugation + agreement.
Paradigm class (-er/-ir/-re/irregular), reflexive detection via `Reflex=Yes`.

### M2. Full German plugin ✓ DONE

`backend/plugins/german.py` — `de_core_news_sm`, vocabulary + conjugation + `case_agreement`.
Separable verb detection, 3-gender/4-case agreement, capitalised noun lemmas.
Canonical form conventions for German documented in `PLUGIN_AUTHOR_GUIDE.md` and `CONTRIBUTING.md`.

### M3. Modal RTL fix ✓ DONE

See B4 above.

### M4. Integration tests for non-Latin scripts ✓ DONE

`backend/tests/test_non_latin_roundtrip.py` — 43 tests covering:
- `canonical_object_id()` UUID stability for Arabic, Hebrew, Chinese, Russian, Japanese
- `CanonicalObjectRow` insert + retrieve via in-memory SQLite — lossless for all five scripts
- `surface_forms` JSON array round-trip with diacritically-marked Arabic
- `lesson_data` JSON round-trip with Hebrew
- Unique constraint enforcement for Arabic
- API-level: `GET /languages` returns `direction="rtl"` for Arabic and Hebrew
- API-level: `POST /parse` with Arabic/Hebrew/Chinese text returns stable UUID v5 object IDs

### M5. Lesson generator pluggable templates

`build_lesson()` generates English prose. For a multilingual platform, the lesson template layer needs to be pluggable — either by language code (so a French plugin can return French-language lesson text) or by template variable (so the UI can compose lesson text from structured data without prose from the server). The current implementation is a medium-term blocker to supporting learners whose native language is not English.

### M6. `canonical_form` conventions for non-Latin morphology ✓ DONE

`CONTRIBUTING.md` now documents:
- **Arabic conjugation** — 5-axis form `{lemma}:{tense}:{person}:{gender}:{number}`; trilateral roots go in `lesson_data["root"]`, not in `canonical_form`; root objects use `"root:{consonants}"` as canonical form with type `"script"`
- **Derived lemmas** (Hebrew binyanim, Arabic masdar) — use the dictionary citation form; decompose to root only in `lesson_data`
- **Chinese polysemy** — bare character sequence when reading is ambiguous; `{chars}:{pinyin_tones}` (digit notation) only when the plugin can determine the reading from context
- **Agglutinative languages** (Finnish, Turkish, Hungarian) — encode only reliably-extracted axes; fix axis order per-language in the plugin file before the first row is stored; suggested axis orders for Turkish conjugations and Finnish nominals are specified

---

## Vision blockers

*These are required for the full vision: a platform that turns any authentic text in any language into a spaced-repetition curriculum.*

### V1. Review event log

A `review_events` table (one row per review: `user_id`, `object_id`, `quality`, `mastery_score_before`, `mastery_score_after`, `reviewed_at`) is the foundation for:
- Retention curves
- Exact time-to-mastery
- Per-session statistics (reviews per day, study streaks)
- FSRS parameter fitting (without this, FSRS uses global defaults, not personal parameters)

This is pure DB work. It does not require changes to the FSRS scheduler. The review route already has all the data needed to write it.

### V2. Background processing for large texts

A user who pastes a novel chapter should not wait 30 seconds for a response, and should not block other users while waiting. This requires:
- Async job queue (Redis Streams is sufficient; Celery is acceptable but heavier)
- `POST /ingest` returns a job ID immediately
- `GET /ingest/{job_id}/status` polls job completion
- Frontend polls and displays progress

The current synchronous path is fine for short texts (< 2 000 characters). The guard from A2 (`max_chars`) buys time but is not a substitute.

### V3. Real dictionary integration

The `lesson_data` JSON field accepts any keys. The lesson generator produces lessons from what the plugin provides. For languages without a good spaCy model, the honest approach is a dictionary lookup mode that provides a gloss, a frequency rank, and example sentences — without pretending to offer morphological analysis.

The architecture supports this (the `"dictionary"` lesson mode already exists in `LanguageCapabilities`). What is missing is a data source: Wiktionary API, CEDICT for Chinese, Buckwalter for Arabic. The choice of data source determines licensing constraints. This needs a decision, not just an implementation.

### V4. FSRS parameter fitting

FSRS-5 ships with global default parameters derived from population-level review data. Per-user parameter optimisation (fitting on the user's own review history) improves retention predictions by approximately 5 percentage points. This requires the review event log (V1) and a fitting algorithm. Deferred until V1 is in place.

### V5. PWA and offline mode

Service worker, IndexedDB lesson cache, offline review submission with sync on reconnect. This is a significant frontend effort and requires the auth story to be settled first (offline tokens, token refresh). Not a beta requirement.

### V6. 10+ production-quality language plugins

The authentic-text vision requires breadth. Spanish + French + German + Arabic + Mandarin + Japanese + Russian + Portuguese + Italian + Latin is a reasonable 10-language target. Each language requires NLP research, plugin implementation, tests, and a native-speaker review of the lesson output. This is years of work, not weeks.

### V7. Dead and historic language annotation mode

Latin, Classical Greek, and Classical Arabic do not have spaCy models of sufficient quality for morphological analysis at production confidence. The honest path is an annotation mode: dictionary lookup, part-of-speech tagging from a curated lexicon, and explicit `confidence = None` on everything. The Latin and Arabic scaffolds already exist; they need a data source (Perseus for Latin/Greek, Lane's Lexicon or Buckwalter for Classical Arabic) and a policy decision on what "production quality" means for a dead language.

---

## 6-week execution plan

These are concrete, achievable tasks. No heroics required.

| Week | Work | Outcome |
|------|------|---------|
| 1 | Replace `create_all` with `alembic upgrade head`. Add `max_chars` guard to `/parse` and `/ingest`. | Alpha A1, A2 complete |
| 2 | Full French plugin: `fr_core_news_md`, vocabulary + conjugation, passing `test_french_spacy.py`. | Alpha A3 complete |
| 2 | `GET /users/me/export` endpoint. | Alpha A4 complete |
| 3 | JWT auth: `POST /auth/register`, `POST /auth/login`, JWT middleware, `get_current_user` updated. | Beta B1 unblocked |
| 4 | Login/register UI in `index.html`. Token storage in `sessionStorage`. Logout. | Beta B2 complete |
| 5 | Modal RTL fix: apply `dir`/`lang` to example text and drill prompts. RTL integration test with Arabic fixture. | Beta B4, M3, M4 complete |
| 6 | WCAG 2.1 AA audit. Fix focus management gaps. CORS lockdown. Rate limiting middleware. | Beta B3, B5, B6 complete |

After week 6: **private alpha is ready.** The system is safe to hand to trusted testers.

---

## 12-week execution plan

Weeks 1–6 as above, then:

| Week | Work | Outcome |
|------|------|---------|
| 7 | `review_events` table + migration. Write to it from the review route. Basic event-count queries in `/metrics`. | V1 started |
| 7 | Full German plugin: `de_core_news_sm`, vocabulary + conjugation. | M2 complete |
| 8 | Lesson generator pluggable templates. English template as default; per-plugin override optional. | M5 complete |
| 8 | `canonical_form` conventions documented for Arabic and CJK in `CONTRIBUTING.md`. | M6 complete |
| 9 | Privacy policy page. `DELETE /users/me` endpoint. Data deletion from all tables. | Beta B7 complete |
| 9 | Error monitoring (Sentry SDK). Structured request IDs across log lines. | Beta B8 complete |
| 10 | Arabic plugin: regex vocabulary + dictionary mode. RTL end-to-end test through full pipeline. | B9 started, M4 extended |
| 11 | Non-Latin script round-trip tests: Arabic, Hebrew, Chinese canonical forms through DB and back. | M4 complete |
| 12 | Retention curve metrics from `review_events`. Deploy beta to staging. WCAG re-audit. | V1 functional, beta candidate |

After week 12: **public beta is ready** assuming error monitoring is live and the audit passes.

---

## Explicit "not now" list

These are good ideas. Do not start them before the 12-week plan is complete.

- **PWA and offline mode.** Blocked on auth story (offline tokens, sync). Not a beta requirement.
- **FSRS parameter fitting.** Blocked on review event log having enough data. Needs 30+ reviews per user to be meaningful.
- **Background job queue for large texts.** The `max_chars` guard buys sufficient time for beta. Implement after beta, when real usage patterns are known.
- **Real dictionary integration.** Requires a licensing decision and a data pipeline. Not a beta requirement.
- **10+ language plugins.** Three production-quality languages is a credible beta. More is better but not required to ship.
- **Dead language annotation mode.** The scaffolds are there. This is a research and data-source problem, not an architecture problem. Post-beta.
- **FSRS optimisation (parameter fitting, deck separation, interleaving).** Post-beta, post event log.
- **Idiom and multiword-expression detection.** The schema supports it (`idiom` type). No plugin extracts idioms yet. Post-beta.
- **Mobile-specific UI.** Touch targets are already WCAG-compliant. A dedicated mobile layout is a post-beta quality-of-life improvement.
- **`source_progression` reading continuity engine.** The model and schema exist. The recommendation engine does not yet prefer continuing an in-progress document. This is a curriculum quality improvement, not a beta blocker.

---

## Architectural principles not to violate under schedule pressure

These are the invariants. If a shortcut violates one of these, it is the wrong shortcut.

### 1. The UUID-v5 namespace is frozen

`backend/parsing/canonical.py` contains a namespace UUID. Every canonical object ID ever stored in any database is derived from it. Changing it invalidates all stored review history. Do not change it. Do not generate IDs by any other method.

### 2. No language-specific logic in core

If a route handler, the scheduler, the canonical ID module, or the recommendation engine contains a language code string (other than in a test fixture), that is a bug. All language-specific behaviour belongs in a plugin. This constraint is what makes the plugin architecture real rather than nominal.

### 3. Fault-tolerant I/O is not optional

Every DB and Redis call in a route handler must be wrapped in `try/except` with a `logger.warning`. The system must return a useful result even when backing services are down. Removing this for performance or code brevity is the wrong trade.

### 4. The canonical form convention for a language is fixed once the first row is stored

Once a canonical form like `"spielen:present:indicative:1:singular"` is in the database, it cannot be changed without a migration that updates every affected row, every `UserKnowledgeRow`, and every `SentenceObjectRow`. Design the convention correctly before shipping a plugin, not after. The CONTRIBUTING.md conventions must be extended to cover non-Latin morphological axes before any new script family is added.

### 5. Authentication is a dependency injection swap, not a rewrite

The `get_current_user` dependency is the single injection point for user identity. JWT, OAuth, API keys — all are implementable by changing this one function and adding middleware. Do not bake user identity logic into individual route handlers.

### 6. Authentic text first — no canned content

Mnemosyne has no vocabulary lists, no built-in lessons, and no curated syllabuses. The user supplies the text. Features that require pre-structured content are out of scope unless they are layered on top of the authentic-text core. Do not introduce vocabulary-list endpoints or predefined exercises as a beta shortcut. The whole product value is that it works on *any* text the user brings.

### 7. Narrow and correct beats broad and unreliable

A plugin that extracts 70% of interesting forms correctly is better than one that attempts 100% and silently mislabels 30%. When in doubt, omit the object or set a low confidence score. The learner's mental model is harmed by wrong analysis more than by silence. This applies to lesson templates, difficulty scores, and FSRS predictions as well as NLP extraction.
