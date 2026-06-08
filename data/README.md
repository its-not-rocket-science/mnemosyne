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

## Source CSV explanations and localisation keys

Source import files under `data/cultural_sources/` may be CSV, JSONL, or NDJSON.
CSV files should use this Windows/PowerShell-friendly header:

```csv
language,surface_pattern,surface_patterns,variants,canonical_reference,reference_type,source_work,source_author,source_location,source_quote,source_note,short_explanation,explanation_key,source_work_key,source_author_key,learner_level,register,confidence,source_url,source_license,rights_basis,source_dataset,notes
```


Source provenance and rights fields should be split cleanly:

- `source_location`: precise location in the source work, such as chapter, act,
  scene, verse, or section. Keep this to locator text only.
- `source_quote`: a short supporting quote or source phrase when useful for
  review. Keep it brief; long quotations should not be imported.
- `source_note`: contextual provenance note that is not itself a location, such
  as review caveats, wording context, or why a work is associated with the row.
- `source_license`: licence or licence-requirement status. Common values include
  `public_domain`, `not_required`, `CC0`, `CC-BY-4.0`, and
  `copyright_or_rights_review_needed`.
- `rights_basis`: rights rationale or assessment, especially when a licence is
  not required. Current structured values include
  `common_usage_short_expression`, `public_domain_source`, and
  `quotation_under_review`.

Examples:

```yaml
source_location: Act II Scene 2
source_quote: That which we call a rose by any other name would smell as sweet.
source_license: public_domain
rights_basis: public_domain_source

source_work: Nineteen Eighty-Four
source_author: George Orwell
source_location: Part 1, Chapter 1
source_license: not_required
rights_basis: common_usage_short_expression
notes: >
  Short common-use term or phrase only, not extended source text.
```

`short_explanation` is optional in source rows. When it is present, the importer
copies it into the draft YAML. When it is missing or blank, the importer keeps the
review placeholder `TODO: add explanation` so reviewers can identify rows that
still need human-authored explanation text before promotion.

`explanation_key`, `source_work_key`, and `source_author_key` are optional. Cultural catalogue localisation keys use the canonical `mnemosyne.en.*` namespace. The `en` segment names the English fallback localisation resource, not necessarily the source-row language. If a row omits keys, the importer generates deterministic suggested keys from stable row fields where possible:

- `mnemosyne.en.explanation.<source_dataset>.<entry_slug>`
- `mnemosyne.en.work.<source_work_slug>`
- `mnemosyne.en.author.<source_author_slug>`

For example, an English Shakespeare phrase row can generate
`mnemosyne.en.explanation.en_shakespeare_phrases.break_the_ice`,
`mnemosyne.en.work.the_taming_of_the_shrew`, and
`mnemosyne.en.author.william_shakespeare`. Explicit `mnemosyne.en.*` keys are preserved. Older `cultural.explanation.*`, `cultural.source_work.*`, and `cultural.source_author.*` keys are deprecated; the importer warns and migrates them to the canonical key when the row contains enough source data to do so, and it rejects ambiguous old keys instead of generating new `cultural.*` keys. Blank source-work and source-author values do not produce keys.

To create or update an English cultural localisation resource while importing,
pass `--l10n-out` explicitly:

```bash
python scripts/import_cultural_sources.py \
  --source data/cultural_sources/en_shakespeare_phrases.csv \
  --out data/cultural_drafts/en_shakespeare.generated.yaml \
  --l10n-out backend/lesson/l10n/cultural_references/en.json
```

PowerShell path separators are also supported:

```powershell
python scripts/import_cultural_sources.py `
  --source data\cultural_sources\en_shakespeare_phrases.csv `
  --out data\cultural_drafts\en_shakespeare.generated.yaml `
  --l10n-out backend\lesson\l10n\cultural_references\en.json
```

The localisation resource is a sorted UTF-8 JSON object. The importer adds
missing canonical mappings for non-placeholder explanation text, source work
titles, and source author names, and removes deprecated `cultural.*` resource
keys from the file it updates. Existing canonical values are preserved. If an
imported row proposes a different value for an existing key, the importer prints
a warning showing both values and does not overwrite silently. It only writes the
file you point it at; it does not create other locales and does not perform
machine translation or interpretation.

Generated runtime JSON preserves localisation keys, and the detector exposes
those keys in `lesson_data` alongside fallback strings (`explanation`,
`source_work`, and `source_author`). Keep fallback strings in reviewed catalogue
entries: missing translations must never break parsing or lesson generation.
Source attribution should remain cautious; imported source metadata is for review
and traceability, not proof that a phrase originated with the named work or
author.


## Reviewing generated cultural drafts

Generated draft files can be reviewed interactively before promotion:

```bash
python scripts/review_cultural_draft.py \
  --draft data/cultural_drafts/en_literary_idioms_normalised_v3.generated.yaml \
  --reviewed-by paul
```

The tool writes a reviewed copy with `_reviewed` in the filename. For inputs
ending in `.generated.yaml`, the deterministic output convention is to insert
`_reviewed` before the final `.yaml` suffix, for example
`en_literary_idioms_normalised_v3.generated_reviewed.yaml`. It prompts for
missing `source_location`, unresolved rights-review flags, blank source URLs for
public-domain rows, and generic placeholder explanations. It does not promote
entries into the production seed.

Validation commands:

```bash
python scripts/review_cultural_draft.py \
  --draft data/cultural_drafts/en_literary_idioms_normalised_v3.generated.yaml \
  --reviewed-by paul \
  --dry-run

pytest backend/tests/test_review_cultural_draft.py
python scripts/build_cultural_catalog.py --check
pytest backend/tests -k "cultural or literary or proverb or allusion or l10n"
```

## Promoting draft cultural entries

Use `scripts/promote_cultural_drafts.py` to promote only reviewed, allowlisted
draft rows into `data/cultural_references_seed.yaml`. The allowlist is a UTF-8
text file with one `canonical_reference` per line; blank lines and lines starting
with `#` are ignored. The script refuses unsafe rows by default, including
rejected drafts, rights-review licences, placeholder explanations, missing
`source_location`, low-confidence rows, duplicate ids, duplicate
`language`/`canonical_reference` pairs, and duplicate surface-pattern collisions.
It does not generate runtime JSON; run the catalogue builder separately after
promotion.

Example dry run:

```bash
python scripts/promote_cultural_drafts.py \
  --draft data/cultural_drafts/en_literary_idioms_normalised_v3.generated.yaml \
  --seed data/cultural_references_seed.yaml \
  --allowlist data/cultural_drafts/promote_en_literary_idioms_batch_001.txt \
  --reviewed-by paul \
  --reviewed-at 2026-06-07 \
  --dry-run
```

Remove `--dry-run` after reviewing the proposed YAML block and summary.

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
- `source_quote`
- `source_note`
- `source_url`
- `source_license`
- `rights_basis`
- `source_dataset`

Licensing caution: only import or emit rows from sources that Mnemosyne is allowed
to redistribute or reference. The builder warns when `source_url` is present
without `source_license`; treat that warning as a prompt to confirm licensing
before promoting the row. Use `source_license: not_required` plus
`rights_basis: common_usage_short_expression` for short common-use expressions
where no licence is required; keep `copyright_or_rights_review_needed` as a hard
review blocker. The builder also warns when an explicitly
`review_status: reviewed` row lacks `reviewed_by` or `reviewed_at`, but this does
not fail legacy starter entries that rely on the missing-status compatibility
default.
