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
# Optional local inspection only: include draft and needs-native-review rows.
python scripts/build_cultural_catalog.py --write --include-drafts --out-dir /tmp/cultural-catalog-drafts
pytest backend/tests -k "cultural or literary or proverb or allusion"
```

## YAML parser fallback

`build_cultural_catalog.py` prefers PyYAML when available. If PyYAML is not
installed, it uses a deliberately small fallback parser that supports only the
subset used by this seed file:

- a top-level list of mappings;
- scalar string/number/bool/null values;
- nested lists of scalar strings, such as `surface_patterns`, `variants`, and
  `avoid_if`;
- folded block scalars using `>` for prose fields.

The fallback parser does not support YAML anchors, aliases, inline maps, nested
objects, complex quoting rules, or arbitrary YAML tags. Keep the seed file simple
and run:

```bash
python scripts/build_cultural_catalog.py --check
```

after editing.

## Adding entries

Each item should include `language`, `surface_patterns`, `canonical_reference`,
`reference_type`, `short_explanation`, `learner_level`, and `confidence`. Use
`variants` for alternate spellings or inflected forms that should match the same
canonical reference; the builder merges them into generated `surface_patterns`
and deduplicates the result deterministically. Use `allow_short_pattern: true`
only for reviewed short forms that are meaningful in context despite ambiguity.


## Review status and provenance

The committed seed can hold both production-ready starter entries and larger
import batches that still need curation. Imported rows, such as phrase-list rows,
should start as draft data and must not automatically become trusted production
annotations.

Optional review fields:

- `review_status`: one of `draft`, `reviewed`, `rejected`, or
  `needs_native_review`. Missing `review_status` is treated as `reviewed` for
  backwards compatibility with the existing starter catalogue.
- `review_notes`: internal curation notes.
- `reviewed_by`: reviewer identifier for explicitly reviewed rows.
- `reviewed_at`: review date or timestamp for explicitly reviewed rows.

Emission policy:

- Default `--check`, `--report`, and `--write` output includes entries whose
  `review_status` is missing and entries marked `reviewed`.
- Default output excludes `draft`, `needs_native_review`, and `rejected` rows.
- `--include-drafts` includes `draft` and `needs_native_review` rows so reviewers
  can inspect candidate runtime JSON locally.
- `rejected` rows are never emitted, even with `--include-drafts`, so known-bad
  entries can remain in the seed for audit/history without becoming runtime
  annotations.

The generated runtime JSON intentionally omits review-only fields, including
`review_status`, `review_notes`, `reviewed_by`, and `reviewed_at`. Runtime files
therefore represent the set selected at build time; do not generate production
artifacts with `--include-drafts`.

Optional public provenance fields are preserved in generated JSON for explanation
and debugging:

- `source_location`
- `source_url`
- `source_license`
- `source_dataset`

Licensing caution: only import or emit rows from sources that Mnemosyne is allowed
to redistribute or reference. The builder warns when `source_url` is present
without `source_license`; treat that warning as a prompt to confirm licensing
before promoting the row. The builder also warns when an explicitly
`review_status: reviewed` row lacks `reviewed_by` or `reviewed_at`, but this does
not fail legacy starter entries that rely on the missing-status compatibility
default.
