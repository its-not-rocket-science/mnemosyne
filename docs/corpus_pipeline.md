# Corpus Pipeline

The offline corpus pipeline populates Mnemosyne with legally usable literature
for all implemented language plugins.  It operates entirely outside the HTTP
layer, reading from a source manifest and writing to the same database that the
web backend uses.

---

## Prerequisites

1. PostgreSQL running and `DATABASE_URL` set (or `.env` present).
2. At least one spaCy language model downloaded for the target language.
   ```bash
   python -m spacy download es_core_news_sm   # example for Spanish
   ```
3. Dependencies installed:
   ```bash
   poetry install
   ```
4. Alembic migrations applied:
   ```bash
   alembic upgrade head
   ```

Redis is **not** required for corpus builds.  The pipeline calls
`run_pipeline()` directly; if Redis is unavailable the cache step is skipped
silently and build continues.

---

## Quick start

```bash
# Verify the manifest is structurally valid
poetry run mnemosyne-corpus validate

# Download and cache one language (no DB writes)
poetry run mnemosyne-corpus acquire --language es

# Dry-run: show what would be ingested without touching the DB
poetry run mnemosyne-corpus build --language es --dry-run

# Full build for one language
poetry run mnemosyne-corpus build --language es

# Full build for all languages in the manifest
poetry run mnemosyne-corpus build --all

# Coverage report from the DB
poetry run mnemosyne-corpus report
```

---

## CLI reference

All commands accept `--manifest <path>` (default: `corpora/manifest.yaml`).

### `list-languages`

```
mnemosyne-corpus list-languages [--manifest PATH]
```

Prints a table of every language code in the manifest and how many source
entries it has.

### `list-sources`

```
mnemosyne-corpus list-sources [--manifest PATH] [--language LANG]
```

Prints a table of every source entry, sorted by language then difficulty.
Filter with `--language` to see one language only.

### `validate`

```
mnemosyne-corpus validate [--manifest PATH] [--check-plugins]
```

Loads and structurally validates the manifest (Pydantic).  Reports:

- Duplicate `source_url` values (error)
- Invalid or unknown license strings (error)
- Invalid level values for the declared framework (error)
- Missing author (warning)
- Language code not found in the loaded plugin registry (warning, requires
  `--check-plugins`)

Exits with code 1 if any errors are found.

### `acquire`

```
mnemosyne-corpus acquire (--language LANG | --all) [--force] [--cache-dir DIR]
```

Downloads source texts and writes them to the local file cache.  Does **not**
parse or write to the database.

- Cached files live at `data/corpus_cache/{language}/{slug}.txt`.
- Skips downloads for entries already cached (unless `--force`).
- Handles Project Gutenberg plain text (strips PG header/footer),
  Aozora Bunko HTML (strips ruby furigana), MediaWiki raw wikitext
  (strips templates, links, headings), and generic HTML automatically.
- Reports each 404 or network error without aborting the rest of the run.

### `ingest`

```
mnemosyne-corpus ingest (--language LANG | --all)
  [--dry-run] [--force] [--cache-dir DIR] [--max-chunk-chars N]
```

Parses cached texts through the NLP pipeline and persists to the database.
Assumes files are already cached; run `acquire` first if they are not.

- Skips any document whose `source_document_id` is already in the DB
  (unless `--force`).
- `--dry-run` shows what would be processed without any DB writes.

### `build`

```
mnemosyne-corpus build (--language LANG | --all)
  [--dry-run] [--force] [--cache-dir DIR] [--max-chunk-chars N]
```

`acquire` + `ingest` in a single command.  This is the typical entry point for
a fresh setup.

### `report`

```
mnemosyne-corpus report [--manifest PATH]
```

Queries the database and prints a per-language table of:
- Number of source documents with `content_type = corpus`
- Number of parsed sentences
- Number of canonical objects

Also reports languages present in the manifest but not yet in the database.

---

## Manifest format

The manifest is a YAML file at `corpora/manifest.yaml`.  Each entry describes
one source text.

```yaml
entries:
  - language: ja           # BCP-47 code matching the plugin (e.g. "ja", "grc")
    framework: JLPT        # CEFR | JLPT | HSK | TOPIK | custom
    level: N3              # Framework-specific level string
    cefr_equivalent: B1    # Normalised CEFR level (required when framework != CEFR)
    title: "注文の多い料理店"
    author: "宮沢賢治"
    year: 1924             # Publication year; null if unknown
    source_url: "https://www.aozora.gr.jp/cards/000081/files/456_15050.html"
    source_name: "Aozora Bunko"
    license: public_domain  # See allowed values below
    genre: short_story      # Free text; informational only
    dialect: ja-JP          # BCP-47 dialect tag; informational only
    script: cjk             # Dominant script; informational only
    notes:
      - "Verify file ID before bulk ingest"
```

### Allowed `license` values

| Value | Meaning |
|-------|---------|
| `public_domain` | Work is in the public domain in its country of origin and the US |
| `cc0` | Creative Commons Zero (explicit waiver) |
| `cc_by` | Creative Commons Attribution |
| `cc_by_sa` | Creative Commons Attribution-ShareAlike |
| `cc_by_nc` | Creative Commons Attribution-NonCommercial |
| `cc_by_nc_sa` | Creative Commons Attribution-NonCommercial-ShareAlike |

Any other value is rejected at manifest load time.

### Level values by framework

| Framework | Valid levels |
|-----------|-------------|
| CEFR | A1, A2, B1, B2, C1, C2 |
| JLPT | N5, N4, N3, N2, N1 |
| HSK | HSK1, HSK2, HSK3, HSK4, HSK5, HSK6 |
| TOPIK | TOPIK-I, TOPIK-II |
| custom | Any string |

`cefr_equivalent` must be one of A1–C2 when set.  It is used by the CLI sort
order (`list-sources`, `build --all`) to process easier texts first.

### Adding a new entry

1. Find a text that is genuinely public domain in both its country of origin
   **and** the United States (life+70 in most jurisdictions; pre-1928 for US
   publication).
2. Confirm the direct download URL returns plain text or HTML you can verify
   locally with `curl`.
3. Add the entry to `corpora/manifest.yaml`.
4. Run `mnemosyne-corpus validate` to catch structural errors early.
5. Run `mnemosyne-corpus acquire --language LANG` to download and cache.
6. Inspect `data/corpus_cache/{lang}/{slug}.txt` to confirm the extracted text
   is clean (no boilerplate, no wikitext markup left).
7. Run `mnemosyne-corpus build --language LANG --dry-run` to see chunk count.
8. Run `mnemosyne-corpus build --language LANG` for the actual ingest.

---

## Source type detection

The acquisition module auto-detects source format and strips boilerplate:

| Source | Detection | Extraction |
|--------|-----------|------------|
| Project Gutenberg | `*** START OF THE PROJECT GUTENBERG EBOOK` marker | Strips header and footer boilerplate; returns body text only |
| Aozora Bunko | `aozora.gr.jp` in URL + HTML | Strips `<rt>` / `<rp>` (furigana); extracts `.main_text` div |
| Wikisource | `wikisource.org` in URL + HTML | Extracts `#mw-content-text .mw-parser-output`; removes edit links, ref sections, category chrome |
| MediaWiki `?action=raw` | `{{` or `[[` near start of file | Strips templates, links, headings, bold/italic markup |
| Generic HTML | `<html` near start | BeautifulSoup `get_text()`; drops script/style/nav |
| Plain text | Everything else | Used as-is after encoding normalisation |

Encoding: tries the `Content-Type` charset first, then UTF-8, then latin-1.

---

## Chunking

Long documents are split into chunks before NLP processing.

- Default chunk size: **2,000 characters** (`--max-chunk-chars`).
- Split strategy: paragraph boundaries (`\n\n+`) first; sentences within
  over-large paragraphs second; hard character split as last resort.
- CJK texts (zh, ja, ko) split sentences on `。！？` rather than `. `.
- Each chunk records `char_start` and `char_end` as offsets into the original
  full document text, stored in `SourceChunkRow`.
- Multiple `SourceChunkRow` rows per `SourceDocumentRow`; all chunks share the
  same `source_document_id`.

---

## Resumability and idempotency

Each manifest entry maps to a **deterministic** `source_document_id`:

```
UUID-v5(CORPUS_NS, language + "\x00" + title + "\x00" + author + "\x00" + source_url)
```

Before processing, `build_entry` checks whether a `SourceDocumentRow` with
that ID already exists.  If it does, the entry is skipped.

- Re-running `build` after a partial failure will skip completed documents and
  resume from the first missing one.
- Use `--force` to re-ingest a document that is already in the database (e.g.
  after updating the plugin or manifest text).
- The `CORPUS_NS` constant in `backend/corpus/build.py` must **never** change
  after initial deployment.  Changing it invalidates all stored corpus IDs and
  breaks the resumability check.

---

## Database interaction

The corpus pipeline writes through the same persistence layer as `POST /ingest`:

```
backend/services/parse_persistence.py
  create_source_document_row   ← one call per document
  persist_chunk                ← one call per chunk
  create_source_progression_row← one call per document after all chunks
```

All writes for one document are committed atomically.  If the commit fails the
document is marked `failed` and the pipeline moves to the next entry.

The pipeline seeds `UserKnowledgeRow` rows with `mastery_score=0.0` and
`total_reviews=0` for every new canonical object it encounters, exactly as the
`/ingest` route does.  This means newly ingested corpus content appears
immediately in the `GET /recommend` endpoint.

---

## Known limitations

### URL verification

Several entries in `corpora/manifest.yaml` include a `"verify URL"` note.
These URLs follow the correct format for their source (Project Gutenberg ID,
Aozora Bunko card number) but have not been independently confirmed to resolve
to the expected text.  Run `mnemosyne-corpus acquire --all` to surface 404s
before a bulk ingest.

### Wikitext stripping is shallow

The MediaWiki stripper handles the most common markup patterns (templates,
links, headings, bold/italic) for any `action=raw` URL you add manually.  The
manifest's Wikisource entries use regular HTML URLs, which go through the
dedicated Wikisource extractor (`#mw-content-text .mw-parser-output`) instead
of the wikitext stripper, so markup leakage is not a concern for those entries.

### Classical vs. modern language mismatch

Several entries (Analects of Confucius, Biblical Hebrew, Medieval Arabic,
Caesar, Koine Greek) are in classical registers that differ significantly from
the language models the plugins use.  The NLP pipeline will still run, but OOV
(out-of-vocabulary) rates will be high and extracted objects may not be useful
for modern-language learners.  This is noted in the manifest; no warning is
suppressed.

### Don Quijote / large documents

Don Quijote Part I is approximately 2 MB and produces ~1,200 chunks.  A full
ingest will take 10–20 minutes depending on hardware.  spaCy model warm-up
happens once per `build` run, not per chunk.

### No idiom mining

Idiom and collocation extraction depends on the individual language plugins.
The corpus pipeline does not implement any extra idiom logic.  Plugins that do
not implement `idiom_detection` will not produce idiom objects from corpus
text.

### CJK Aozora Bunko file IDs

The two Aozora Bunko entries use file IDs derived from the Aozora card pages.
These IDs are stable but should be verified at
`https://www.aozora.gr.jp/cards/{AUTHOR_ID}/` before a production ingest.

### No EPUB or subtitle support

`ContentType.EBOOK` and `ContentType.SUBTITLE` are defined in the schema but
not wired to the corpus pipeline.  Only web-downloadable plain text and HTML
are supported.

### Windows console encoding

The CLI uses Rich for output.  On older Windows consoles (ConHost) stdout is
reconfigured to UTF-8 at startup.  If you see `UnicodeEncodeError` output,
run the CLI in Windows Terminal or PowerShell 7+ which default to UTF-8.

---

## File layout

```
corpora/
  manifest.yaml              Source manifest (edit this to add texts)

backend/corpus/
  __init__.py
  manifest.py                CorpusEntry and CorpusManifest Pydantic models
  levels.py                  JLPT/HSK/TOPIK → CEFR mappings and sort keys
  cache.py                   Local file cache (read/write/exists)
  acquisition.py             HTTP download + format-aware text extraction
  normalize.py               Thin wrapper over ingestion validator
  chunking.py                Paragraph-aware chunking with char offsets
  build.py                   Full pipeline orchestration
  reports.py                 DB aggregation for the report command
  quality.py                 Manifest quality checks
  cli.py                     Typer CLI entry point

backend/services/
  parse_persistence.py       Shared DB persistence (used by /ingest and corpus)

data/corpus_cache/           Local text cache (git-ignored)
  {language}/
    {title_slug}.txt
```

---

## Integration with the web backend

Corpus-ingested content is indistinguishable from user-ingested content at
query time.  The only difference is `source_documents.content_type = 'corpus'`
and the deterministic `id`.

- `GET /sources` returns corpus documents alongside user documents.
- `GET /recommend` considers corpus sentences when selecting i+1 candidates.
- `GET /reading/{id}` and `PATCH /reading/{id}` work normally for corpus
  source documents.
- `GET /lesson/{object_id}` works for any object mined from corpus text.
- `POST /review` updates FSRS state for corpus-derived objects exactly as for
  user-ingested objects.
