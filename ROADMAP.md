# Mnemosyne Roadmap

## Phase 0 — Working MVP
- [x] FastAPI app scaffold
- [x] No-framework accessible frontend
- [x] Spanish plugin with vocabulary, conjugation, and agreement extraction
- [x] Lesson modal with focus trap, keyboard navigation, and aria-live feedback
- [x] TTS via Web Speech API
- [x] Review submission endpoint
- [x] FSRS-5 spaced-repetition scheduler (pure Python)
- [x] PostgreSQL persistence: `ParsedText`, `Sentence`, `LearnableObject`, `ReviewState`
- [x] Database-backed `/lesson` lookup (DB-first, plugin fallback)
- [x] `/review` loads and persists FSRS state from DB
- [x] Redis-backed parse cache (fault-tolerant — degrades gracefully)
- [x] Persistence integration tests (in-memory SQLite, no external services)

## Phase 1 — Accuracy and durability
- [ ] Alembic migrations (replace `create_all` with `alembic upgrade head`)
- [ ] User accounts and per-user review state
- [ ] Structured logging and metrics
- [ ] Background processing for large texts
- [ ] Stable lesson IDs across plugin versions
- [ ] Real dictionary and translation integration

## Phase 2 — More languages
- [ ] French plugin
- [ ] German plugin
- [ ] Optional deeper spaCy morphology (medium/large models)
- [ ] RTL-aware Arabic/Hebrew frontend pass

## Phase 3 — Mobile and offline
- [ ] PWA support
- [ ] Service Worker
- [ ] IndexedDB lesson cache
- [ ] Offline reviews with sync-on-reconnect

## Quality targets
- [ ] < 2s parse time for 500 words on MVP languages
- [ ] WCAG 2.1 AA audit
- [ ] Keyboard-only complete lesson flow
- [ ] 90 % test coverage on scheduler and persistence paths
