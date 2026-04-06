# Claude Prompt 1 — Backend Scaffold

Using the existing Mnemosyne repo, improve the backend scaffold without changing the frontend contract.

Tasks:
- keep FastAPI and Pydantic v2
- preserve the plugin loader pattern
- add SQLAlchemy models for texts, lesson objects, and reviews
- replace in-memory lesson lookup with persistent storage
- keep typed schemas
- add a migration-ready metadata layout
- add structured error responses

Return full file diffs.
