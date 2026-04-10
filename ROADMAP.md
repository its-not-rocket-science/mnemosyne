# Mnemosyne Roadmap

Status markers: **implemented** · **partial** · **planned** · **deferred**

---

## What is built (current state)

| Feature | Status | Notes |
|---------|--------|-------|
| FastAPI scaffold + static frontend | implemented | No build step; vanilla JS + Web Components |
| Spanish NLP plugin (`es_core_news_sm`) | implemented | Vocabulary, conjugation, agreement; single-pass spaCy |
| English stub plugin | implemented | Regex vocab only; no morphology |
| French stub plugin | partial | Regex vocab + stop-word filter; no morphology, no conjugation |
| Plugin registry with multi-language support | implemented | `ENABLED_LANGUAGES` filter; collision warning on duplicates |
| Canonical knowledge layer | implemented | UUID-v5 PKs; `(language, type, canonical_form)` unique; `object_relations`; `surface_forms` accumulation |
| FSRS-5 spaced-repetition scheduler | implemented | Pure Python; all functions deterministic |
| `POST /parse` with Redis cache | implemented | SHA-256 key; 1 h TTL; graceful Redis-down degradation |
| `GET /lesson/{id}` | implemented | DB-first; plugin in-session fallback |
| `POST /review` | implemented | DB state authoritative; payload fallback on outage |
| `GET /dashboard` | implemented | `?language=` filter; known/weak/new/due_for_review |
| `GET /metrics` | implemented | Retention, success_rate, stability, weakest-10, by_language, by_type |
| `GET /recommend` + `/recommend-text` | implemented | i+1 window; difficulty_label (easy/ideal/hard); progression |
| `GET /languages` | implemented | Lists active plugins with direction metadata |
| `GET /health` + `GET /ready` | implemented | Liveness and readiness probes |
| Alembic migrations | partial | Three migration files exist; `create_all` still runs on fresh startup |
| Accessibility baseline | partial | Focus trap, ARIA live regions, reduced-motion, 44 px targets; WCAG AA not audited end-to-end |
| RTL layout support | partial | `direction` field on plugins; frontend CSS not yet RTL-aware |
| User authentication | deferred | All requests use `user_id = "default"` |

---

## Category 1 — Release hardening

These are blockers or near-blockers before the system is safe to run against real data.

- **Replace `create_all` with `alembic upgrade head`** on fresh startup. `create_all` silently diverges from migration history. (*partial → implemented*)
- **WCAG 2.1 AA audit** — keyboard-only run through the full parse → lesson → review flow; screen-reader smoke test with NVDA and VoiceOver.
- **CORS lockdown** — warn-on-`*` is already in `main.py`; wire it to a deployment checklist.
- **Secrets hygiene** — `DATABASE_URL` credential scrubbing already logs a warning; document the `.env` → secrets-manager migration path.
- **Structured request logging** — add `request_id` to each request's log lines for trace correlation. Currently timing is logged per route but with no correlation token.
- **Parse timeout** — long texts submitted to the spaCy plugin block the event loop. Add a `max_chars` guard (configurable, default 10 000) or offload to a thread pool.
- **Background DB persist** — currently `_persist_parse` runs in the request path after the response is built. Move to a true background task so the client is not held waiting on DB I/O.
- **< 2 s parse time for 500 words** — profile `es_core_news_sm` on the target hardware; document the result.

---

## Category 2 — Multilingual foundations

These unlock meaningful expansion beyond Spanish.

- **Full French plugin** — replace the regex stub with `fr_core_news_md`; extract conjugation, agreement, and elision contractions. Requires deciding on a morphology model and annotating tests.
- **RTL CSS pass** — add `[dir="rtl"]` layout variants: text alignment, pill flow direction, modal margins, scroll direction. Must not break LTR. Audit with a Hebrew or Arabic test fixture.
- **Arabic plugin stub** — even a regex vocab stub forces the RTL path to be tested with real data.
- **Script normalisation** — non-Latin canonical forms must survive the UUID-v5 key. Add a test that round-trips `(ar, vocabulary, كتاب)` through `canonical_object_id`.
- **Language-aware sentence splitting** — the current Spanish plugin delegates to spaCy's sentencizer, which is adequate. Stub plugins use a naive regex. A common `split_sentences` contract that plugins can override cleanly is needed before adding morphologically complex or script-variable languages.
- **`ENABLED_LANGUAGES` documentation** — explain how to run a single-language deployment and how to add a new language to an existing database without affecting other users' data.
- **Plugin loading resilience** — a plugin that raises during `create_plugin()` is already skipped with a `WARNING`. Add a `GET /ready` signal that reports degraded-plugin status so operators can see partial failures.

---

## Category 3 — Vision-complete / long-horizon work

These follow from the starting vision but require category 1 and 2 to be solid first.

- **User accounts and per-user review state** — multi-user requires authentication and a `user_id` propagated through every route. The schema already uses `user_id` with `"default"` as a placeholder.
- **Review event log** — a `review_events` table (one row per review) unlocks retention curves, exact time-to-mastery, and per-session analytics. The current `user_knowledge` table stores only the current FSRS state.
- **Real dictionary integration** — gloss data, example sentences, etymology. The `lesson_data` JSON field accepts any keys; the lesson generator needs a source to populate them.
- **Real translation integration** — one-tap translation of extracted objects. Requires a clear policy on attribution and API cost.
- **FSRS parameter fitting** — per-user or per-deck parameter optimisation improves retention predictions by ~5 pp. Requires the review event log.
- **PWA / offline mode** — service worker, IndexedDB lesson cache, offline reviews with sync-on-reconnect.
- **Background processing for large texts** — async job queue (e.g. Redis Streams or Celery) for corpora > 10 000 characters; progress SSE to the frontend.
- **Dead and historic language support** — annotation mode (dictionary lookup, no morphological parser) rather than pretending spaCy-style NLP is available. Latin, Classical Arabic, Koine Greek as first candidates.
- **Idiom and multiword-expression detection** — `idiom` and `nuance` types exist in the schema but no plugin extracts them yet.
- **Mobile / PWA** — responsive layout audit at 320 px; touch targets already meet WCAG 2.5.8.

---

## Quality targets (ongoing)

- [ ] `alembic upgrade head` is the only DB initialisation path (no `create_all` in production)
- [ ] WCAG 2.1 AA on the core parse → review flow
- [ ] 90% branch coverage on `backend/srs/` and `backend/parsing/`
- [ ] Parse time < 2 s for 500 words on the CI runner
- [ ] Zero `# type: ignore` comments without an explanatory note
