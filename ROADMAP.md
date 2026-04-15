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
| Multi-user architecture | implemented | `X-User-Id` header; `get_current_user` dependency; per-user isolation across all routes; `UserLanguagePreferenceRow` table; `/users/me/*` preference CRUD |
| User authentication | partial | Header-based identity complete; JWT auth not yet implemented — header is not cryptographically verified |

---

## Category 1 — Release hardening

These are blockers or near-blockers before the system is safe to run against real data.
See `BETA_GAP_REPORT.md` for the detailed blocker breakdown by alpha / beta / vision tier.

- **Replace `create_all` with `alembic upgrade head`** on fresh startup. `create_all` silently diverges from migration history. (*partial → implemented*) — **Private alpha blocker A1**
- **`max_chars` guard on `/parse` and `/ingest`** — long texts block the event loop. Configurable, default 10 000 characters. Return 413 above the limit. — **Private alpha blocker A2**
- **Data export endpoint** — `GET /users/me/export` returns all knowledge state as JSON. — **Private alpha blocker A4**
- **JWT authentication** — `POST /auth/register` + `POST /auth/login`; replace header-only identity in `get_current_user`. — **Public beta blocker B1**
- **Login/register UI** — frontend login panel, JWT in `sessionStorage`, logout. — **Public beta blocker B2**
- **WCAG 2.1 AA audit** — keyboard-only run through the full parse → lesson → review flow; screen-reader smoke test with NVDA and VoiceOver. — **Public beta blocker B3**
- **CORS lockdown** — warn-on-`*` is already in `main.py`; wire it to a deployment checklist. — **Public beta blocker B5**
- **Rate limiting** — per-IP and per-user rate limiting on the parse endpoint at minimum. — **Public beta blocker B6**
- **Privacy policy + data deletion** — `DELETE /users/me` removes all user data; visible privacy policy page. — **Public beta blocker B7**
- **Error monitoring** — Sentry SDK or equivalent before public traffic. — **Public beta blocker B8**
- **Structured request logging** — add `request_id` to each request's log lines for trace correlation.
- **Background DB persist** — currently `_persist_parse` runs in the request path after the response is built. Move to a true background task so the client is not held waiting on DB I/O.
- **< 2 s parse time for 500 words** — profile `es_core_news_sm` on the target hardware; document the result.

---

## Category 2 — Multilingual foundations

These unlock meaningful expansion beyond Spanish.

- **Full French plugin** — replace the regex stub with `fr_core_news_md`; extract conjugation, agreement, and elision contractions. — **Private alpha blocker A3, Public beta blocker B9**
- **Full German plugin** — `de_core_news_sm`, vocabulary + conjugation; document canonical_form conventions for German compound nouns and case-marked articles.
- **Modal RTL fix** — apply `dir`/`lang` to example text and drill prompts in `mnemosyne-modal.js`. RTL integration test with Arabic fixture. — **Public beta blocker B4**
- **RTL CSS audit** — complete `[dir="rtl"]` layout pass: modal margins, button ordering, focus ring visibility. Must not break LTR.
- **Non-Latin script round-trip tests** — push `(ar, vocabulary, كتاب)`, `(he, vocabulary, ספר)`, `(zh, vocabulary, 书)` through `canonical_object_id`, DB insert, retrieve, and assert lossless. Zero such tests exist today.
- **`canonical_form` conventions for non-Latin morphology** — extend `CONTRIBUTING.md` to cover Arabic root+pattern forms, CJK lexeme conventions, and agglutinative language axes before adding any plugin for those scripts.
- **Lesson generator pluggable templates** — `build_lesson()` produces English prose regardless of target language. Needs a per-language template layer so lesson text can be composed from structured data.
- **`ENABLED_LANGUAGES` documentation** — explain how to run a single-language deployment and how to add a new language to an existing database without affecting other users' data.
- **Plugin loading resilience** — a plugin that raises during `create_plugin()` is already skipped with a `WARNING`. Add a `GET /ready` signal that reports degraded-plugin status so operators can see partial failures.

---

## Category 3 — Vision-complete / long-horizon work

These follow from the starting vision but require category 1 and 2 to be solid first.

- **User accounts** — multi-user data isolation is complete (all routes scoped to `current_user`; `UserLanguagePreferenceRow` implemented). Remaining work: JWT auth middleware, login/register API routes, login UI. See category 1.
- **Review event log** — a `review_events` table (one row per review: user_id, object_id, quality, mastery_score_before/after, reviewed_at) unlocks retention curves, exact time-to-mastery, per-session analytics, and FSRS parameter fitting. The current `user_knowledge` table stores only the current FSRS state. This is pure DB + route work; the scheduler does not change.
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
