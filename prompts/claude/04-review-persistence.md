# Claude Prompt 4 — Review Persistence

Persist review state in PostgreSQL.

Tasks:
- create review models
- store object_id, user_id placeholder, state JSON, due_at, last_reviewed_at
- update /review to read and write persistent state
- keep FSRS pure functions isolated from database code

Return full files.
