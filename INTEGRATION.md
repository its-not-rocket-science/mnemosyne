# Lesson extraction integration

Copy `lesson_extraction/` to:

```text
backend/lesson_extraction/
```

Then wire it into both parsing entry points.

## `backend/api/routes/parse.py`

Add:

```python
from backend.lesson_extraction import enrich as enrich_lessons
```

After:

```python
candidate_results = await asyncio.to_thread(
    plugin.analyze_text, payload.text
)
```

insert:

```python
candidate_results = enrich_lessons(
    payload.language,
    candidate_results,
    plugin.capabilities,
)
```

## `backend/api/routes/ingest.py`

Add:

```python
from backend.lesson_extraction import enrich as enrich_lessons
```

After:

```python
candidate_results = plugin.analyze_text(normalized_text)
```

insert:

```python
candidate_results = enrich_lessons(
    payload.language,
    candidate_results,
    plugin.capabilities,
)
```

## Test target

The first smoke test should assert that enrichment never removes existing
objects and that every enriched object still validates as a `CandidateObject`.
