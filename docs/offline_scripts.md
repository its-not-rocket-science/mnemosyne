# Offline Scripts Reference — Mnemosyne

Scripts in `scripts/` run outside the web server. They populate lexicons,
build morphological indices, seed curated data, and maintain i18n. None touch
the request/response path.

---

## Prerequisites

```bash
poetry install
```

Set `DATABASE_URL` for any script that writes to the database
(`harvest_language_data.py`, `cleanup_orphaned_corpus.py`).

Run all scripts from the **project root**:

```bash
python -m scripts.<name> [args]      # preferred (module form, resolves imports)
python scripts/<name>.py [args]      # also works
```

---

## Script inventory

### `ingest_kaikki.py` — Kaikki/Wiktionary lexicon ingestion

Builds `{la,grc}_lemmas.json` and `{la,grc}_inflections.json` from
`kaikki.org` JSONL dumps.

**Input files** (must be present before running):

```
data/lang_capture/raw/kaikki_la.jsonl.gz
data/lang_capture/raw/kaikki_grc.jsonl.gz
```

**Output files:**

```
data/lexicons/la_lemmas.json
data/lexicons/la_inflections.json
data/lexicons/grc_lemmas.json
data/lexicons/grc_inflections.json
```

**Usage:**

```bash
python -m scripts.ingest_kaikki --lang la      # Latin only
python -m scripts.ingest_kaikki --lang grc     # Koine Greek only
python -m scripts.ingest_kaikki --lang all     # both (default)
```

**Notes:**

- Downloads are not included in the repository. Obtain dumps from
  `https://kaikki.org/dictionary/` (CC BY-SA 4.0; same licence as Wiktionary).
- Filters to content-word POS only (`verb`, `noun`, `adj`, `adv`, …); skips
  form-of entries using head-template name heuristics and gloss patterns.
- Normalises forms via `backend.core.classical_normalize` (strips diacritics,
  lowercases) so lookup keys are accent-free.

---

### `ingest_classical_morph.py` — Latin/Greek morphological annotation

Parses Universal Dependencies CoNLL-U treebanks and MorphGNT into
per-form feature indices used by the Latin and Koine Greek plugins.

**Input files** (must be present before running):

```
data/lang_capture/raw/la_ittb-ud-dev.conllu      # Latin ITTB (CC BY-NC-SA 3.0)
data/lang_capture/raw/grc_proiel-ud-dev.conllu   # Greek PROIEL (CC BY-NC-SA)
data/lang_capture/raw/morphgnt_sblgnt.txt        # MorphGNT (CC BY-SA 3.0, non-commercial)
```

**Output files:**

```
data/lexicons/la_morph.json    (~3 400 entries)
data/lexicons/grc_morph.json   (~27 000 entries)
```

**Usage:**

```bash
python -m scripts.ingest_classical_morph --lang la
python -m scripts.ingest_classical_morph --lang grc
python -m scripts.ingest_classical_morph --lang all
```

**Output schema (per entry):**

```json
{
  "version": "1",
  "language": "la",
  "source": ["la_ittb-ud-dev.conllu"],
  "entries": {
    "amorem": {
      "lemma": "amor",
      "pos": "noun",
      "case": "accusative",
      "number": "singular",
      "gender": "masculine"
    }
  }
}
```

**Notes:**

- After running, restart (or reimport) the Latin/Greek plugins — they load
  the index once at import time.
- Morph features flow into `lesson_data` on `CandidateObject` and raise
  confidence from 0.70 (dict-only) to 0.80 (dict + morph).
- All three source files are licensed for non-commercial use only; do not
  redistribute the output files under a more permissive licence.

---

### `harvest_language_data.py` — CEFR vocabulary and grammar harvesting

Seeds the database with frequency-ranked vocabulary (CEFR A1–C2) and
curated grammar rules for each supported language.

**Sources:**

- `FrequencyWords` (hermitdave/FrequencyWords on GitHub; CC BY-SA 3.0) —
  OpenSubtitles-derived frequency lists; CEFR band assigned by frequency rank.
- JLPT word lists (Japanese, N5–N1 → A1–C1).
- HSK word lists (Mandarin, HSK 1–6 → A1–C2).
- Wiktionary API for definitions (rate-limited; skippable).

**Requires:**

```bash
pip install httpx asyncpg "sqlalchemy[asyncio]" tqdm
DATABASE_URL=postgresql+asyncpg://...
```

**Usage:**

```bash
python scripts/harvest_language_data.py
python scripts/harvest_language_data.py --languages es fr de
python scripts/harvest_language_data.py --levels A1 A2 B1
python scripts/harvest_language_data.py --skip-vocab         # grammar only
python scripts/harvest_language_data.py --skip-grammar       # vocabulary only
python scripts/harvest_language_data.py --skip-definitions   # no Wiktionary calls
python scripts/harvest_language_data.py --dry-run            # no DB writes
```

---

### `gen_etymology.py` — Insert etymology entries into source

Reads JSON spec files at `scripts/data/etymology_{lang}.json` and patches
them into `_CURATED` in `backend/dictionary/etymology.py`.

**Spec schema:**

```json
{
  "language": "it",
  "lemma": "crescendo",
  "origin_summary": "From Latin crescere (to grow)...",
  "roots": ["Latin crescere (to grow)"],
  "cognates": ["English 'increase' (same root)"],
  "semantic_shift": "'growing' → musical term for gradually increasing volume"
}
```

**Usage:**

```bash
python scripts/gen_etymology.py --lang it
python scripts/gen_etymology.py --lang es fr --dry-run
python scripts/gen_etymology.py --validate-only
```

**Notes:**

- Idempotent: existing `(language, lemma)` pairs are skipped.
- Verifies the patched module imports cleanly before writing.
- `cognates` and `semantic_shift` are optional; all other fields are required.

---

### `gen_verbal_government.py` — Insert verbal government entries into source

Reads JSON spec files at `scripts/data/{lang}_verbal_government.json` and
patches them into `_VERBAL_GOV` in `backend/nuance/{lang}.py`.

**Spec schema:**

```json
{
  "lemma": "желать",
  "case": "genitive",
  "example": "«желать» governs the genitive: желать успеха (to wish success)"
}
```

**Usage:**

```bash
python scripts/gen_verbal_government.py --lang ru
python scripts/gen_verbal_government.py --dry-run
python scripts/gen_verbal_government.py --validate-only
```

**Notes:**

- Idempotent: lemmas already present in the target dict are skipped.
- Add a new language by adding an entry to `LANG_CONFIG` at the top of the
  script and creating the corresponding `{lang}_verbal_government.json` spec.

---

### `gen_phrase_families.py` — Insert phrase family entries into source

Reads JSON spec files at `scripts/data/phrase_families_{lang}.json` and
patches them into `_FAMILY_CATALOG` in `backend/dictionary/phrase_families.py`.

**Spec schema:**

```json
{
  "id": "es_ir_al_grano",
  "canonical": "ir al grano",
  "meaning": "Get to the point.",
  "register": "neutral",
  "origin": "Optional origin note.",
  "why_it_matters": "Optional learner note.",
  "variants": [
    {"surface": "ir al grano", "type": "exact"},
    {"surface": "yendo al grano", "type": "inflectional_variant", "note": "Gerund form."}
  ],
  "confusables": []
}
```

**Usage:**

```bash
python scripts/gen_phrase_families.py --lang es
python scripts/gen_phrase_families.py --dry-run
python scripts/gen_phrase_families.py --validate-only
```

**Notes:**

- Checks for duplicate IDs and normalised-surface collisions across the entire
  catalog (existing + new entries) before writing.
- Every family must have exactly one `"type": "exact"` variant.

---

### `audit_nuance_coverage.py` — Nuance coverage CI gate

Reports which language plugins have declared `nuance_capabilities` and
which are missing them. Exits 1 if any supported language lacks the block.

**Usage:**

```bash
PYTHONPATH=. python scripts/audit_nuance_coverage.py
PYTHONPATH=. python scripts/audit_nuance_coverage.py --no-color
```

**Output columns:** language | idioms | phrase families | etymology |
grammar nuance | literary/cultural | tests

Intended as a CI step so new language plugins cannot be merged without
declaring nuance capability coverage.

---

### `cleanup_orphaned_corpus.py` — Remove stale corpus rows

Deletes `SourceDocumentRow` entries whose `source_url` no longer appears in
`corpora/manifest.yaml`. Dry-run by default.

**Usage:**

```bash
poetry run python scripts/cleanup_orphaned_corpus.py            # dry run
poetry run python scripts/cleanup_orphaned_corpus.py --execute  # actually delete
```

**Notes:**

- Safe to re-run; no-ops if no orphans remain.
- Cascades to `SourceChunkRow` and `SourceProgressionRow` via FK constraints.
- Requires `DATABASE_URL`.

---

### `fill_i18n.py` — One-off i18n key backfill

Inserts missing i18n keys into `frontend/js/i18n.js`. This is a maintenance
script; run it after adding new UI strings that span many language sections.

**Usage:**

```bash
python scripts/fill_i18n.py
```

Modifies `frontend/js/i18n.js` in-place. Review the diff before committing.

---

### `add_fl_keys.py` — Add field-label (`fl_*`) i18n keys

Adds the 10 `fl_*` field-label keys (fl_surface_form, fl_aspect, fl_voice,
fl_construction, fl_verb_class, fl_romanized, fl_form, fl_translation,
fl_gloss, fl_note) to all 11 UI language sections in `frontend/js/i18n.js`.

**Usage:**

```bash
python scripts/add_fl_keys.py
```

Already applied as of 2026-05-27. Safe to re-run (inserting after the
`fl_separable_verb` anchor is idempotent if keys already present).

---

## Typical new-language setup sequence

When adding a new language plugin, run scripts in this order:

```bash
# 1. Harvest vocabulary (if language in FrequencyWords/JLPT/HSK)
python scripts/harvest_language_data.py --languages <code> --skip-grammar

# 2. Build lexicon from Kaikki (for classical languages only)
python -m scripts.ingest_kaikki --lang <code>

# 3. Build morphological index (for la/grc only)
python -m scripts.ingest_classical_morph --lang <code>

# 4. Add etymology entries (if curated data available)
python scripts/gen_etymology.py --lang <code>

# 5. Add phrase families
python scripts/gen_phrase_families.py --lang <code>

# 6. Add verbal government (for case-governed languages)
python scripts/gen_verbal_government.py --lang <code>

# 7. Verify nuance coverage passes
PYTHONPATH=. python scripts/audit_nuance_coverage.py
```

---

## Data file layout

```
data/
  lang_capture/raw/          Raw corpus dumps and treebanks (git-ignored)
    kaikki_la.jsonl.gz       Kaikki/Wiktionary Latin dump
    kaikki_grc.jsonl.gz      Kaikki/Wiktionary Greek dump
    la_ittb-ud-dev.conllu    Latin UD treebank (ITTB dev)
    grc_proiel-ud-dev.conllu Greek UD treebank (PROIEL dev)
    morphgnt_sblgnt.txt      MorphGNT annotated Greek NT

  lexicons/                  Generated lexicon JSON (committed for la/grc)
    la_lemmas.json
    la_inflections.json
    la_morph.json
    grc_lemmas.json
    grc_inflections.json
    grc_morph.json

scripts/data/               Curated source spec files
  etymology_{lang}.json
  phrase_families_{lang}.json
  {lang}_verbal_government.json
```
