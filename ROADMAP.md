# Mnemosyne Roadmap

## Phase 0 — Working MVP
- [x] FastAPI app scaffold
- [x] No-framework frontend
- [x] Spanish starter plugin
- [x] Lesson modal flow
- [x] Review submission endpoint
- [x] FSRS-style scheduler
- [ ] PostgreSQL persistence
- [ ] Redis-backed parse cache
- [ ] Real lesson authoring system

## Phase 1 — Accuracy and durability
- [ ] SQLAlchemy models for users, texts, lessons, and review state
- [ ] Structured logging and metrics
- [ ] Background processing for large texts
- [ ] Stable lesson IDs across imports
- [ ] Real dictionary and translation integration

## Phase 2 — More languages
- [ ] French plugin
- [ ] German plugin
- [ ] Optional spaCy-backed morphology
- [ ] RTL-aware Arabic/Hebrew frontend pass

## Phase 3 — Mobile and offline
- [ ] PWA support
- [ ] Service Worker
- [ ] IndexedDB lesson cache
- [ ] Offline reviews

## Quality targets
- [ ] < 2s parse time for 500 words on MVP languages
- [ ] WCAG 2.1 AA review
- [ ] Keyboard-only complete lesson flow
