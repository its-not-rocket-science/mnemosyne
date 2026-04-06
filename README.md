# Mnemosyne

**Turn any text into a living lesson.**

Mnemosyne is a minimalist, accessible language-learning web app that transforms text into sentence-level lessons. This starter pack includes a runnable FastAPI backend, a no-framework frontend, a plugin system, a Spanish MVP plugin, and a lightweight FSRS-style review scheduler.

## What is in this starter pack

- FastAPI backend
- Typed Pydantic v2 schemas
- Async SQLAlchemy setup
- Redis cache hook
- Language plugin interface + loader
- Spanish MVP plugin with conservative rule-based extraction
- FSRS-style scheduler implementation
- Accessible frontend with Web Components
- Lesson modal and review flow
- Basic tests

## Quick start

### 1. Install dependencies

```bash
poetry install
```

### 2. Run the backend

```bash
poetry run uvicorn backend.main:app --reload
```

### 3. Open the frontend

Serve the `frontend/` directory with any simple static server, for example:

```bash
python -m http.server 8080 -d frontend
```

Then open `http://localhost:8080`.

## API

### `POST /parse`

Request:

```json
{
  "text": "Hola. Yo hablo español.",
  "language": "es"
}
```

Response:

```json
{
  "sentences": [
    {
      "text": "Hola.",
      "learnable_objects": [
        {
          "id": "es:vocab:hola",
          "type": "vocabulary",
          "label": "hola",
          "lesson_data": {
            "kind": "vocabulary",
            "lemma": "hola",
            "gloss": "hello"
          },
          "confidence": 0.9
        }
      ]
    }
  ]
}
```

## Design notes

- The Spanish plugin is deliberately conservative.
- The scheduler is readable and testable rather than academically exact.
- The frontend uses semantic HTML, logical CSS properties, and keyboard-safe modal behavior.
- Dead-language support is intentionally deferred from the runnable codebase.

## Suggested next steps

1. Add persistent storage for lessons and reviews
2. Replace the in-memory lesson registry with database-backed objects
3. Add spaCy-backed plugins behind optional extras
4. Add authentication
5. Expand accessibility testing
