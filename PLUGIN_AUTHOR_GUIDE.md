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

`backend/plugins/stub_en.py` — regex tokenisation, no NLP:

- `analysis_depth="dictionary"`, `lesson_modes_supported=["vocabulary"]`
- Whitespace-split tokens, no POS or morphology

## Minimal Stub Plugin

If full NLP is not yet available for your language, start with a stub that
returns vocabulary objects with `pos="WORD"` and no morphology.  Set
`lesson_modes_supported=["dictionary"]` and `morphology_depth="none"`.

The English stub (`backend/plugins/stub_en.py`) is the reference for
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
