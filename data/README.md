# Cultural references seed catalogue

`cultural_references_seed.yaml` is the curated, hand-editable source of truth
for Mnemosyne's literary, cultural, proverb, classical, and scriptural allusion
catalogue. Keep it as idiomatic YAML so future maintainers can add comments and
review entries without touching generated files. The runtime detector reads the
committed JSON generated under `backend/nuance/data/cultural_references/`
instead.

This catalogue is global lesson enrichment, not a per-language
`NuanceExtractor`. `backend/lesson_extraction/engine.py` applies it after
plugin/extractor enrichment. Matching is curated exact/near-exact string
matching only; it does not use LLMs, embeddings, external APIs, or runtime
network calls, and `partial` coverage means starter recognition data rather
than comprehensive cultural interpretation.

## Local workflow

```bash
python scripts/build_cultural_catalog.py --check
python scripts/build_cultural_catalog.py --report
python scripts/build_cultural_catalog.py --write
pytest backend/tests -k "cultural or literary or proverb or allusion"
```

## Adding entries

Each item should include `language`, `surface_patterns`, `canonical_reference`,
`reference_type`, `short_explanation`, `learner_level`, and `confidence`. Use
`variants` for alternate spellings or inflected forms that should match the same
canonical reference; the builder merges them into generated `surface_patterns`
and deduplicates the result deterministically. Use `allow_short_pattern: true`
only for reviewed short forms that are meaningful in context despite ambiguity.
