# Cultural references seed catalogue

`cultural_references_seed.yaml` is the curated source of truth for Mnemosyne's
literary, cultural, proverb, classical, and scriptural allusion catalogue. The
file is deliberately data-only; runtime code reads generated JSON under
`backend/nuance/data/cultural_references/` instead.

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
`allow_short_pattern: true` only for reviewed short forms that are meaningful in
context despite ambiguity.
