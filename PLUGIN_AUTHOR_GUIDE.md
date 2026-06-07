# Plugin Author Guide

A reference for building a new Mnemosyne language plugin.  Read this
alongside `backend/plugins/spanish.py`, which is the reference implementation
for a full-parse living-language plugin.

---

## Overview

A language plugin is a Python class that:

1. Declares its capabilities via a `LanguageCapabilities` instance.
2. Implements `analyze_text(text)` → `list[CandidateSentenceResult]`.
3. Optionally implements `split_sentences(text)` → `list[str]` and
   `analyze_sentence(sentence)` → `CandidateSentenceResult`.
4. Maintains a `lesson_store` dict so the lesson route can retrieve objects by
   UUID after a parse.

The plugin does **not** build lessons itself — that is the job of
`backend/lesson/generators.py`.  The plugin's only job is to fill
`lesson_data` with the keys that each builder expects.

---

## Capability Metadata

Declare capabilities accurately — the frontend and lesson route use them to
adapt the UI and select the right lesson template.

```python
from backend.schemas.language import LanguageCapabilities

capabilities = LanguageCapabilities(
    code="xx",
    display_name="My Language",
    direction="ltr",          # or "rtl" / "ttb"
    script_family="latin",    # latin | arabic | hebrew | devanagari | cjk | other
    tokenization_mode="whitespace",  # whitespace | character | segmented
    morphology_depth="none",  # none | pos_only | rich
    lesson_modes_supported=["vocabulary"],

    # ── v2 fields (all optional but recommended) ──────────────────────────
    analysis_depth="stub",          # stub | partial | full
    segmentation_quality="none",    # none | low | medium | high
    tokenization_quality="medium",
    morphology_quality="none",
    syntax_support=False,
    idiom_detection=False,
    tts_lang_tag="xx",              # BCP-47 tag for TTS — may differ from code
    transliteration_scheme=None,    # e.g. "hepburn_romaji" | "pinyin" | None
)
```

### Choosing `lesson_modes_supported`

| What your plugin can do             | Include these modes       |
|-------------------------------------|---------------------------|
| Surface form only (no NLP)          | `["dictionary"]`          |
| POS tagging, no morphology          | `["vocabulary"]`          |
| Full morphology + paradigms         | `["morphology", "vocabulary"]` |

The lesson route selects the first supported mode unless the client overrides.
The `morphology` builder dispatches by object type; `vocabulary` always uses
the vocabulary builder; `dictionary` is the minimal word + gloss template.

### `analysis_depth` — internal vs user-facing labels

`analysis_depth` is a **machine-readable ID** used internally and in the API.
It is **not** shown directly to learners. The mapping to user-facing display
text is in `backend/schemas/language.py`:

```python
ANALYSIS_DEPTH_USER_LABELS = {
    "full":              "Detailed grammar analysis",
    "morphology_light":  "Basic grammar hints",
    "dictionary":        "Vocabulary lookup",
    "segmentation_only": "Text segmentation only",
}
```

`LanguageCapabilities` exposes `analysis_depth_label` as a computed field —
use that in any UI or API response that surfaces language quality to learners.
Frontend localisation of these labels is in `CAPABILITY_LABELS_I18N` in
`frontend/js/i18n.js`.

**Do not invent new `analysis_depth` values.** If your plugin falls between
"full" and "morphology_light", use `morphology_light` and add a
`confidence_note` in `lesson_data` explaining the actual coverage.

### `transliteration_scheme`

Set this to a non-`None` string when the plugin emits romanized forms
alongside native-script text (e.g. `"pinyin"`, `"hepburn_romaji"`,
`"iso_233"`).  The frontend uses this flag to show the script-view toggle
(Script / Romanized / Both) in the results toolbar and in lesson modals.

### `tts_lang_tag`

Use the most specific BCP-47 tag the TTS engine accepts.  For example:
`"zh-TW"` instead of `"zh"`, `"pt-BR"` instead of `"pt"`.  Falls back to
the plugin's `code` when absent.

---


## Practice-generation hooks

Plugins can optionally expose `practice_hooks()` to customize lesson practice generation.
The hook bundle supports:
- term normalization
- acceptable answer variants
- cloze generation
- distractor generation
- grammar-pattern detection
- feedback text tuning

If omitted, the lesson engine uses safe default hooks so unsupported languages still get
basic comprehension and retrieval activities.


## Data-driven cultural catalogue

Do not hard-code literary references, cultural references, proverb traditions,
or classical/scriptural allusions inside plugin files. Maintain those entries in
`data/cultural_references_seed.yaml`, then generate runtime catalogues with:

```bash
python scripts/build_cultural_catalog.py --check
python scripts/build_cultural_catalog.py --report
python scripts/build_cultural_catalog.py --write
pytest backend/tests -k "cultural or literary or proverb or allusion"
```

Runtime detection loads committed
`backend/nuance/data/cultural_references/<lang>.json` lazily and emits
`type="nuance"` candidates with `reference_type`, `canonical_reference`, source
metadata, explanation, surface form, learner level, register, and confidence
notes where needed. The detector is global enrichment applied by
`backend/lesson_extraction/engine.py` after plugin/extractor enrichment; it is
not a per-language `NuanceExtractor`. Plugins should only declare the capability
level (`partial` for the starter catalogue languages); they should not duplicate
catalogue rows.

The catalogue is curated exact/near-exact string matching only. It does not use
LLMs, embeddings, external APIs, or runtime network calls, and its coverage is
partial rather than comprehensive cultural interpretation.

The seed supports production entries and draft imported rows. Missing
`review_status` is treated as `reviewed` for backwards compatibility. Explicit
statuses are `draft`, `reviewed`, `needs_native_review`, and `rejected`. Default
generation emits only missing-status/`reviewed` rows; `--include-drafts` also
emits `draft` and `needs_native_review` rows for local review builds.
`rejected` rows are never emitted, even with `--include-drafts`, so known-bad
imports cannot become runtime annotations accidentally. Generated JSON preserves
public provenance fields (`source_location`, `source_url`, `source_license`,
`source_dataset`) and omits internal review-only fields, including
`review_status`; production runtime files should not be generated with
`--include-drafts`. Confirm source licensing before adding imported rows, and
include `source_license` whenever `source_url` is present.


Cultural source import rows may also carry human-authored `short_explanation` text
and optional localisation keys. Cultural catalogue localisation keys use the
canonical `mnemosyne.en.*` namespace:

- `mnemosyne.en.explanation.<source_dataset>.<entry_slug>`
- `mnemosyne.en.work.<source_work_slug>`
- `mnemosyne.en.author.<source_author_slug>`

The older `cultural.*` key family is deprecated and should not be used for new
entries. The importer generates canonical keys when fields are missing, preserves
explicit canonical keys, and warns while migrating old explicit keys when the
mapping is unambiguous. `--l10n-out` adds missing English fallback resource
strings, removes deprecated `cultural.*` resource keys, and does not overwrite
conflicting existing canonical values. Generated runtime JSON preserves these
keys and emits them in `lesson_data` alongside fallback strings. Keep fallback
strings because missing translations must never break parsing or lesson
rendering, do not use machine translation for these resources, and treat source
attribution as review metadata rather than proof of origin. See `data/README.md`
for the full CSV header and command examples.

---

## Object Types

Each `CandidateObject` has a `type` field.  The built-in lesson builders
handle these types:

| Type              | Builder             | When to emit                                 |
|-------------------|---------------------|----------------------------------------------|
| `vocabulary`      | `_build_vocabulary` | Open-class content words (NOUN, ADJ, ADV, non-finite VERB) |
| `conjugation`     | `_build_conjugation`| Finite VERB / AUX with morphological features |
| `agreement`       | `_build_agreement`  | DET+NOUN or ADJ+NOUN morphological agreement pairs |
| `idiom`           | `_build_idiom`      | Fixed-form multi-word expressions            |
| `grammar`         | `_build_grammar`    | Periphrastic / structural patterns           |
| `nuance`          | `_build_nuance`     | Aspect, mood, or verb-type observations      |
| `script`          | `_build_script`     | Individual characters / signs (CJK, Arabic…) |
| `transliteration` | `_build_transliteration` | Native ↔ romanized form pairs          |
| `case_agreement`  | `_build_case_agreement` | DET/ADJ+NOUN with case+gender+number (German etc.) |

Unknown types fall through to `_build_generic`, which renders every
`lesson_data` key as a plain field.  Prefer registering a dedicated builder
for your type in `generators.py` rather than relying on the fallback.

---

## `lesson_data` Key Reference

### vocabulary

```python
{
    "lemma":           str,           # required — base/dictionary form
    "pos":             str,           # required — UD POS tag (NOUN, VERB, ADJ…)
    "gender":          str | None,    # for NOUN: "Masc" | "Fem"
    "number":          str | None,    # for NOUN: "Sing" | "Plur"
    "verb_form":       str | None,    # for non-finite VERB: "Inf" | "Ger" | "Part"
    "confidence_note": str | None,    # human-readable penalty rationale
}
```

### conjugation

```python
{
    "lemma":          str,    # required — infinitive
    "surface":        str,    # required — inflected form as it appears in the text
    "tense":          str,    # "present" | "preterite" | "imperfect" | "future" | …
    "mood":           str,    # "indicative" | "subjunctive" | "imperative" | "unknown"
    "person":         str,    # "1" | "2" | "3" | "unknown"
    "number":         str,    # "Sing" | "Plur" | "unknown"
    "morph_complete": bool,   # True when tense+mood+person are all resolved
    "construction":   str,    # "standalone" | "progressive" | "perfect" | …
    "is_reflexive":   bool,
    "paradigm_class": str,    # "-ar" | "-er" | "-ir" | "irregular"
    "is_irregular":   bool,
    "confidence_note": str | None,
}
```

`paradigm_class` and `is_irregular` enable conjugation-table drills in
future lesson generators.  Emit them whenever you know the infinitive.

### agreement

```python
{
    "modifier":       str,   # surface form of the modifier (DET or ADJ)
    "modifier_pos":   str,   # UD POS tag of the modifier
    "noun":           str,   # surface form of the head noun
    "gender":         str,   # gender of the noun ("Masc" | "Fem")
    "number":         str,   # number of the noun ("Sing" | "Plur")
    "gender_match":   bool | None,  # None = feature not available on one token
    "number_match":   bool | None,
    "confidence_note": str | None,
}
```

**Never emit an agreement object with a confirmed mismatch** (`False`).
Confirmed mismatches indicate a model parse error; they confuse learners and
should be silently dropped.

### idiom

```python
{
    "phrase":   str,   # canonical fixed-form phrase (lowercased)
    "meaning":  str,   # English gloss
    "register": str,   # "neutral" | "formal" | "informal"
}
```

Only include fixed-form (non-conjugable) expressions in your idiom table.
Verb idioms whose form depends on subject or tense require lemma-based
matching and are significantly harder to implement correctly.

### grammar

```python
{
    "pattern_id":   str,  # stable snake_case identifier, e.g. "ser_copula"
    "pattern":      str,  # human-readable label, e.g. "ser + [adjective / noun]"
    "usage":        str,  # when and why this construction is used
    "contrast":     str,  # how it differs from a related construction
    "verb_lemma":   str,  # triggering verb lemma
    "surface_verb": str,  # surface form found in the text
}
```

Emit grammar objects **derived from conjugation results**, not from a second
pass over raw tokens.  One object per `pattern_id` per sentence.

### nuance

```python
{
    "nuance_type":    str,         # "imperfect_aspect" | "subjunctive_mood" | …
    "lemma":          str,         # the verb this nuance was derived from
    "surface":        str,         # surface form found in the text
    "note":           str,         # human-readable explanation
    "contrast_tense": str | None,  # for aspect nuances (e.g. "preterite")
}
```

Emit nuance objects derived from conjugation results.  One object per
`(nuance_type, lemma)` pair per sentence.

### case_agreement

```python
{
    "modifier":       str,   # surface form of the modifier (DET or ADJ)
    "modifier_pos":   str,   # UD POS tag of the modifier
    "noun":           str,   # surface form of the head noun
    # case — use display name, not raw spaCy tag:
    "case":           str,   # "nominative" | "accusative" | "dative" | "genitive"
                             # | "instrumental" | "locative" | "unknown"
    "gender":         str,   # "Masc" | "Fem" | "Neut" | "unknown"
    "number":         str,   # "Sing" | "Plur" | "unknown"
    "case_match":     bool | None,
    "gender_match":   bool | None,
    "number_match":   bool | None,
    "confidence_note": str,  # always present (describes what was confirmed)
}
```

Use `case_agreement` instead of `agreement` for languages with morphological
case (German, Latin, Russian, etc.) so the lesson builder can present all
three agreement dimensions.  The canonical form scheme is:

```
case_agreement:{case_lower}:{modifier_lemma}_{noun_lemma}
```

e.g. `"case_agreement:nom:der_Mann"` (German), `"case_agreement:ins:новый_друг"` (Russian).

Russian adds two cases beyond the German/Latin four: **Instrumental** and
**Locative**.  German uses DET+NOUN and ADJ+NOUN pairs; Russian omits DET
(no articles) and uses only ADJ+NOUN pairs.

### script

```python
{
    "character":    str,          # the character or sign
    "readings":     list[str],    # pronunciations (e.g. on'yomi + kun'yomi)
    "meaning":      str | None,   # English gloss
    "stroke_count": int | None,
    "notes":        str | None,
}
```

### transliteration

```python
{
    "native_form": str,         # original-script form
    "romanized":   str,         # romanized / phonetic form
    "scheme":      str,         # e.g. "hepburn_romaji", "pinyin"
    "meaning":     str | None,  # optional English gloss
}
```

---

## Canonical Form Schemes

The canonical form is the **stable string** used to derive the UUID for a
learning object.  The same canonical form always produces the same UUID.
Objects that carry the same meaning across different sentences must share a
canonical form so the spaced-repetition scheduler can aggregate reviews.

| Type              | Canonical form scheme                              | Example                             |
|-------------------|----------------------------------------------------|-------------------------------------|
| `vocabulary`      | lemma string                                       | `"casa"`                            |
| `conjugation`     | `lemma:tense:mood:person:number`                   | `"hablar:present:indicative:1:Sing"`|
| `agreement`       | `pos:modifier_lemma_noun_lemma`                    | `"det:el_casa"`                     |
| `idiom`           | phrase string (lowercased)                         | `"sin embargo"`                     |
| `grammar`         | `"grammar:{pattern_id}"`                           | `"grammar:ser_copula"`              |
| `nuance`          | `"nuance:{nuance_type}:{verb_lemma}"`              | `"nuance:imperfect_aspect:vivir"`   |
| `script`          | character string                                   | `"水"`                              |
| `transliteration` | `"{native_form}:{scheme}"`                         | `"水:pinyin"`                       |

Design your canonical form so that two objects that teach the **same thing**
get the same UUID, and two objects that teach **different things** get
different UUIDs.  Avoid embedding surface forms that vary across sentences.

---

## Confidence Scores

Scores are heuristic proxies for how much the plugin trusts its output.
They are displayed in the UI and used to calibrate initial SRS intervals.

Suggested ranges from the Spanish reference implementation:

| Situation                                     | Score |
|-----------------------------------------------|-------|
| Direct table match (idioms)                   | 0.90  |
| High-confidence morphological analysis        | 0.80–0.85 |
| Reliable dep-parse observation (reflexives)   | 0.82  |
| Aspect / tense-based nuance                   | 0.78  |
| Ambiguous surface form (e.g. subj/ind overlap)| 0.72  |
| Proper noun (limited generalisability)        | 0.60  |
| Out-of-vocabulary word                        | 0.50  |

Always include a `confidence_note` in `lesson_data` when the score is below
the nominal maximum for that type, so learners understand the caveat.

---

## Relation Hints

A `RelationHint` records a directed relationship between two learning objects.
The parse route resolves both ends to UUIDs and records them in the relations
table.  Hints for objects not present in the same parse are silently skipped.

```python
from backend.schemas.parse import RelationHint

# conjugation → vocabulary
RelationHint(
    relation_type="conjugation_of",
    target_canonical_form=lemma,   # vocabulary object's canonical_form
    target_type="vocabulary",
)

# agreement → noun
RelationHint(
    relation_type="agreement_of",
    target_canonical_form=noun_lemma,
    target_type="vocabulary",
)

# grammar → conjugation
RelationHint(
    relation_type="instance_of",
    target_canonical_form=conj.canonical_form,
    target_type="conjugation",
)

# nuance → conjugation
RelationHint(
    relation_type="nuance_of",
    target_canonical_form=conj.canonical_form,
    target_type="conjugation",
)
```

---

## Graceful Omission

**Better to omit than to hallucinate.**  If you cannot reliably determine a
feature, leave its `lesson_data` key absent or set to `"unknown"`.  The
lesson builders degrade gracefully for absent keys.

Rules of thumb:

- Do not invent tense/mood/person from context — if the model's morphology
  feature is absent, emit `"unknown"`.
- Do not infer gender from definiteness heuristics — only emit gender when
  the morphological feature is present.
- Do not match verb idioms by surface form unless all variants are
  exhaustively listed — partial matches produce false positives.
- Drop agreement pairs with a confirmed mismatch rather than emitting them
  as errors.

---

## Deduplication Pattern

Use shared `seen_*` sets to prevent the same lemma or canonical form from
appearing twice in one sentence result.

```python
seen_vocab: set[str] = set()
seen_conj:  set[str] = set()

# Conjugation runs first and pre-populates seen_vocab with verb lemmas.
conj_candidates = self._extract_conjugations(tokens, seen_conj, seen_vocab)
candidates.extend(conj_candidates)

# Vocabulary skips any lemma already in seen_vocab.
candidates.extend(self._extract_vocabulary(tokens, seen_vocab))
```

Grammar and nuance objects should use their own `seen_grammar` / `seen_nuance`
sets keyed by `canonical_form` (not lemma) so that one pattern per type is
emitted per sentence.

---

## Testing Patterns

Write tests for:

1. **Required `lesson_data` keys present** — one test per object type.
2. **Confidence in valid range** — `0 < confidence <= 1.0`.
3. **Canonical form stability** — same input → same canonical form, same UUID.
4. **No duplicate canonical forms** in one sentence result.
5. **Deduplication** — finite verbs not in vocabulary; lemmas not appearing twice.
6. **Graceful absence** — punctuation-only input returns empty candidates.
7. **Known-item extraction** — e.g. `"sin embargo"` is detected as an idiom.
8. **Known-item exclusion** — e.g. present indicative has no imperfect nuance.

Scope the spaCy model load to `module` so it runs once per test session:

```python
@pytest.fixture(scope="module")
def plugin():
    from backend.plugins.my_language import MyLanguagePlugin
    return MyLanguagePlugin()
```

Gate the whole test module on model availability:

```python
pytestmark = pytest.mark.skipif(
    not _model_available(),
    reason="NLP model not installed",
)
```

---

## Language Support Levels

### Spanish (`es`) — Reference Implementation

`backend/plugins/spanish.py` is the reference for a full-parse plugin:

- `analysis_depth="full"`, `morphology_depth="rich"`
- Vocabulary, conjugation, agreement, idiom, grammar, nuance objects
- Paradigm class (-ar/-er/-ir/irregular), irregular verb detection
- `fr_core_news_sm` — 12 MB model

### French (`fr`) — Full-Parse Plugin (Grammar/Idiom Deferred)

`backend/plugins/french.py` provides:

- `analysis_depth="full"`, `morphology_depth="rich"`
- Vocabulary, conjugation, agreement objects
- Paradigm class (-er/-ir/-re/irregular), irregular verb detection
- Reflexive detection via `Reflex=Yes` morph (more portable than surface lists)
- Grammar patterns and idiom detection are **not yet implemented** (future)
- `fr_core_news_sm` — 16 MB model

**Known limitation**: `fr_core_news_sm` sometimes mis-tags finite verbs as
ADJ/NOUN after noun subjects.  These are silently under-extracted.

**Architecture findings** this plugin surfaced:
1. `generators._TENSE_OPTIONS` includes "preterite" (Spanish-specific)
2. `paradigm_class` encoding is language-dependent (-ar/-er/-ir vs -er/-ir/-re)
3. Reflexive detection via surface forms is less portable than using `Reflex=Yes`

### English (`en`) — Minimal Stub

`backend/plugins/english.py` — regex tokenisation, no NLP:

- `analysis_depth="dictionary"`, `lesson_modes_supported=["vocabulary"]`
- Whitespace-split tokens, no POS or morphology

### German (`de`) — Full-Parse Plugin (Grammar/Idiom Deferred)

`backend/plugins/german.py` provides:

- `analysis_depth="full"`, `morphology_depth="rich"`
- Vocabulary (with capitalised NOUN lemmas per German orthographic convention),
  conjugation, `case_agreement` objects
- Separable verb detection via `dep=svp`; full lemma reconstructed as
  `{particle}{bare_lemma}` (e.g. `an` + `rufen` → `anrufen`)
- Paradigm class (weak/strong/modal), irregular/strong verb detection
- Reflexive detection via `Reflex=Yes` morph feature
- Grammar patterns and idiom detection **not yet implemented** (future)
- `de_core_news_sm` — ~43 MB model

**Known limitation**: `is_oov` is always `True` for `de_core_news_sm` — not
used for confidence.  Confidence is based on count of resolved features.

**Architecture findings** this plugin surfaced:
1. `agreement` type is insufficient for case-marking languages; the new
   `case_agreement` type (with `_build_case_agreement` in `generators.py`)
   carries case as a first-class dimension alongside gender and number.
2. German noun lemmas preserve capitalisation — use `tok.lemma_` as-is, not
   `.lower()`, so canonical forms match German dictionary headwords.
3. Separable verb lemma reconstruction (`{particle}{bare_lemma}`) is a
   Germanic-language pattern that Dutch/Swedish/Norwegian plugins will reuse.
4. Feature-count confidence is more portable than `is_oov`-based heuristics.

### Russian (`ru`) — Full-Parse Plugin (Grammar/Idiom Deferred)

`backend/plugins/russian.py` provides:

- `analysis_depth="full"`, `morphology_depth="rich"`, `script_family="cyrillic"`
- Vocabulary (lowercase Cyrillic lemmas from pymorphy3), conjugation, `case_agreement`
- **Aspect** (imperfective/perfective) on every conjugation object — critical for Russian learners
- **Past tense uses Gender** (Masc/Fem/Neut), not Person — Russian past verbs agree with the
  subject's gender.  The `person_or_gender` key encodes a person digit for present/future and a
  gender word for past.
- **Six cases** in `case_agreement`: Nom, Gen, Dat, Acc, **Ins, Loc** (two beyond German)
- No DET in case agreement (Russian has no articles — only ADJ+NOUN pairs)
- `ru_core_news_sm` + pymorphy3

**Canonical form scheme for Russian conjugation** (6 axes):
```
{lemma}:{tense}:{aspect}:{mood}:{person_or_gender}:{number}
```

**Architecture findings** this plugin surfaced:
1. Aspect is a first-class morphological axis in Russian — encode it in the canonical form
   so imperfective and perfective of the same verb get different UUIDs.
2. Past tense agreement targets gender, not person — `person_or_gender` must vary by tense.
3. Lowercase lemma convention (pymorphy3) differs from German (capitalised nouns).
4. Six-case system extends the `_CASE_DISPLAY` map; display names are full English words
   (`"instrumental"`, `"locative"`) stored in `lesson_data["case"]`.

### Japanese (`ja`) — Morphology-Light Vocabulary Plugin

`backend/plugins/japanese.py` provides:

- `analysis_depth="morphology_light"`, `morphology_depth="shallow"`, `script_family="cjk"`
- `tokenization_mode="segmented"` — SudachiPy word-boundary segmentation, not whitespace
- `transliteration_scheme="hiragana"` — readings stored as hiragana in `lesson_data["reading"]`
- Vocabulary only (NOUN, PROPN, ADJ, ADV, VERB content words)
- Particles (ADP), auxiliaries (AUX), and all function words filtered out
- Readings from `tok.morph.get("Reading")` converted from katakana to hiragana via
  `_kata_to_hira(text)`: subtract `0x60` from chars in `U+30A1–U+30F6`
- `ja_core_news_sm` + SudachiPy (`sudachidict-core`)

**Architecture findings** this plugin surfaced:
1. CJK tokenisation requires `tokenization_mode="segmented"` — whitespace splitting produces
   one token per entire sentence for Japanese/Chinese.
2. Readings are in katakana from SudachiPy; a simple subtraction converts them to hiragana
   without an extra dependency.
3. Japanese verbal morphology is carried by the auxiliary chain (ます, た, ない…), not by the
   main verb stem — extracting conjugation objects for the full chain is deferred.
4. `transliteration_scheme` triggers the script-view toggle (Script / Romanized / Both) in
   the frontend; set it to `"hiragana"` not `"romaji"` to signal the scheme used.

### Agglutinative Languages (Finnish, Turkish, Hungarian, …)

Agglutinative languages attach 10+ productive morphological suffixes to a single
stem.  Turkish can express in one word what takes an English sentence.  These
rules prevent ID space explosions and keep canonical forms stable across parses.

#### Core rules

1. **Encode only axes your plugin extracts reliably.**  Do not emit axes you
   cannot determine.  A 4-axis canonical form is better than a 10-axis form
   where 6 axes are guessed.  A wrong canonical form is worse than a missing one
   because it creates a permanent ID collision.

2. **Fix the axis order per language before the first parse.**  The order must be
   stable across all parses; changing it after rows exist invalidates all stored
   IDs.  Declare the order in a module-level docstring and in the plugin's
   `CANONICAL_FORM_AXES` constant.

3. **Use lowercase English labels** for axis values (`nominative` not `NOM`,
   `singular` not `SG`).

4. **Vocabulary canonical form** — the citation form (lemma as it appears in a
   standard printed dictionary).  For Finnish: nominative singular.  For
   Turkish: bare verbal stem (infinitive minus the `-mek`/`-mak` suffix — just
   the stem, e.g. `git` not `gitmek`).

#### Turkish conjugation canonical form

Turkish verbs encode: tense, aspect, mood, person, number, voice (active,
passive, causative, reflexive).  Suggested axis order:

```
{lemma}:{tense}:{aspect}:{mood}:{person}:{number}:{voice}
```

Omit trailing axes when unknown.  Only encode what your plugin verifies.

| Axis | Example values |
|---|---|
| tense | `present`, `aorist`, `past`, `future`, `conditional` |
| aspect | `progressive`, `habitual`, `perfective` |
| mood | `indicative`, `optative`, `necessitative`, `imperative` |
| person | `1`, `2`, `3` |
| number | `singular`, `plural` |
| voice | `active`, `passive`, `causative`, `reflexive` (omit when active) |

Example: `git:past:perfective:indicative:1:singular` (I went).

Turkish has a vowel harmony rule — the same morpheme has different surface forms
depending on the stem vowels (`-dım`/`-dim`/`-dum`/`-düm` for past 1sg).
The canonical form uses the abstract tense label, not the surface suffix.

#### Finnish nominal canonical form

Finnish nominals (nouns, adjectives, pronouns) have 15 cases × 2 numbers = 30
inflected forms per word.  Encode:

```
{lemma}:{case}:{number}
```

Full case inventory (lowercase English names):

```
nominative  genitive    accusative  partitive
inessive    elative     illative
adessive    ablative    allative
essive      translative
instructive abessive    comitative
```

Example: `talo:inessive:singular` ("talossa" — in the house).

Finnish verbs add: tense, mood, person, number, infinitive type.  Suggested
conjugation form:

```
{lemma}:{tense}:{mood}:{person}:{number}
```

| Axis | Example values |
|---|---|
| tense | `present`, `past`, `perfect`, `pluperfect` |
| mood | `indicative`, `conditional`, `imperative`, `potential` |
| person | `1`, `2`, `3`, `passive` |
| number | `singular`, `plural` |

Example: `talo:inessive:singular` for a nominal; `puhua:present:indicative:1:singular` for a verb.

#### Compatibility with the lesson builder

The `_build_conjugation` and `_build_agreement` builders in `generators.py`
expect English-label values for tense, mood, person, and number.  The Finnish
and Turkish values above use the same label convention.  Set
`LanguageCapabilities.tense_pool` and `mood_pool` to the tense/mood labels your
plugin emits so MC drills only offer language-appropriate wrong answers.

#### Architecture guidance

- Do not extract suffixes as separate learnable objects.  The boundary between
  stem and suffix is meaningful to linguists but not to language learners; teach
  inflected forms as wholes.
- Use `lesson_data["morphology_note"]` for a free-text explanation of the
  grammatical structure (e.g. `"2nd person plural past passive"`).
- For languages with 15+ cases, the `_build_case_agreement` lesson builder is
  insufficiently parameterised — it knows only 4 cases.  You will need to extend
  `_CASE_DISPLAY` in `generators.py` and add case labels to `_CASE_OPTIONS` when
  implementing a Finnish or Turkish plugin.

---

## Minimal Stub Plugin

If full NLP is not yet available for your language, start with a stub that
returns vocabulary objects with `pos="WORD"` and no morphology.  Set
`lesson_modes_supported=["dictionary"]` and `morphology_depth="none"`.

The English plugin (`backend/plugins/english.py`) is the reference for
this pattern.  It demonstrates:

- `analysis_depth="dictionary"` capability
- `lesson_modes_supported=["vocabulary"]`
- No conjugation, agreement, idiom, grammar, or nuance objects
- All words tokenised by whitespace split and emitted as `vocabulary`

Once a real NLP model is available, upgrade the capabilities and add
extraction methods incrementally — each new method is independently testable.

**Migration checklist when upgrading a stub to a real plugin:**

1. Change `morphology_depth` to match the model's actual capability.
2. Update `analysis_depth` to `"full"` or `"morphology_light"`.
3. Add `lesson_modes_supported=["morphology", "vocabulary"]`.
4. Update `test_plugin.py` and `test_language_capabilities.py` stub-specific
   assertions to reflect the new capabilities.
5. Create a dedicated `test_{lang}_spacy.py` test file with a skip guard.

---

### Classical / Dead Languages (Latin, Koine Greek) — Offline Morph-Index Pattern

`backend/plugins/latin.py` and `backend/plugins/greek_koine.py` demonstrate the pattern
for dead languages where no live NLP model exists but offline treebank annotations are
available.

**Key design decisions:**

- `lesson_modes_supported=["morphology", "vocabulary", "dictionary"]` — all three modes
  enabled because the plugin emits `conjugation`, `grammar`, and `vocabulary` objects.
- `morphology_quality="low"` (Latin, ~3 400 forms from UD ITTB dev split) or `"medium"`
  (Koine Greek, ~27 000 forms from UD PROIEL + full MorphGNT New Testament).
- `grammar_nuance="none"` — grammar detection is binary (is it a preposition / conjunction
  / particle?) rather than context-sensitive nuance analysis.

**Lookup order per token:**

```
curated dict  →  Kaikki/Wiktionary lemma  →  Kaikki inflection table  →  morph index  →  suffix rules (Latin only)  →  unknown
```

**Conjugation type rules:**

Emit `type="conjugation"` **only when tense and mood are both known** (contract C9).
Sources for tense/mood, in priority order:
1. Morph index hit (`la_morph.json` / `grc_morph.json`) — confidence 0.80.
2. Latin suffix rules (imperfect: `-abat`/`-ebat`…; future: `-abit`/`-ebit`…;
   infinitive: `-are`/`-ere`/`-ire`) — confidence 0.55.
3. No tense/mood source → emit `type="vocabulary"` instead (honest degradation).

**Grammar type rules:**

Emit `type="grammar"` for curated entries whose `pos` is in
`frozenset({"prep", "conj", "particle", "det"})`.

**Canonical form for morph-indexed conjugations:**

```
{surface_key}:{field1}={val1}:{field2}={val2}:...
```

Fields sorted alphabetically; only fields present in the morph entry are included.

Example: `amabat:aspect=imperfective:mood=indicative:number=singular:person=third:tense=imperfect`

**Diacritic normalisation:**

Both plugins strip all diacritics (accents, breathings, iota subscript, diaeresis)
and lowercase before lookup.  Normalised keys are used for all dict and morph index
lookups.  The `romanized` field in `lesson_data` is computed from the normalised form
via the plugin's transliteration function.

**Offline data pipeline:**

Re-build morph indices with `scripts/ingest_classical_morph.py` after obtaining larger
treebank splits (the current indices use dev splits only; full treebanks give ~5× more
Latin coverage and ~3× more Greek coverage).  Lexicon JSON files committed at
`data/lexicons/{la,grc}_{lemmas,inflections,morph}.json`.

---

### Suffix-Rule Morphology-Light Plugins (Hindi, Turkish, Finnish)

`backend/plugins/hindi.py`, `backend/plugins/turkish.py`, and
`backend/plugins/finnish.py` demonstrate the suffix-rule pattern for languages
where a spaCy model is not available or not yet integrated.

**Key design decisions:**

- `analysis_depth="morphology_light"`, `morphology_depth="shallow"`,
  `morphology_quality="low"` — honest about partial coverage.
- `lesson_modes_supported=["morphology", "vocabulary"]` — conjugation and
  case/nominal objects emitted from suffix rules.
- `grammar_nuance="none"` — no context-sensitive grammar analysis.

**Hindi (`hi`) specifics:**
- Devanagari word regex for tokenisation (not whitespace — script has no spaces between words in some contexts).
- IAST romanisation via a Unicode codepoint mapping.
- Verb suffix rules: aspect (`raha/rahi/rahe` → progressive), perfective (`a/i/e` endings), future (`ga/gi/ge`).
- Noun/postposition tagging: `_POSTPOSITIONS` table for bigram postpositions (`के लिए`, `की ओर`, etc.).
- `tts_lang_tag="hi-IN"`, `transliteration_scheme="iast"`.

**Turkish (`tr`) specifics:**
- Whitespace tokenisation; vowel-harmony-aware suffix matching.
- Nominal: `-lar`/`-ler` plural; `-da`/`-de`/`-ta`/`-te` locative; `-dan`/`-den`/`-tan`/`-ten` ablative; `-a`/`-e` dative; `-ı`/`-i`/`-u`/`-ü` accusative.
- Verbal: `-yor` present progressive; `-di`/`-dı`/`-du`/`-dü`/`-ti`/`-tı`/`-tu`/`-tü` definite past; `-ecek`/`-acak` future; `-meli`/`-malı` necessitative.
- Short suffixes (`-ı`, `-a`, `-da`) deliberately excluded to limit false positives.
- `transliteration_scheme="latin"`.

**Finnish (`fi`) specifics:**
- 15-case suffix table (inessive through comitative); plural detection (`-t` nominative plural).
- Vowel harmony variants for each case.
- Conjugation: present (`-n`/`-t`/`-mme`/`-tte`/`-vat`/`-vät`), past (`-i-` stem + person suffixes), conditional (`-isi-`), imperative (`-kaa`/`-kää`).
- `transliteration_scheme="latin"`.

**Testing pattern (no model required):**

All three plugins use word injection directly into `analyze_sentence()` — no spaCy
model load needed.  Tests live in `test_hindi_turkish_finnish_plugins.py` and follow
the same `module`-scoped fixture pattern as spaCy tests, but with no skip guard since
the plugins have no external dependency.
