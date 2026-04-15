# Segmentation Languages in Mnemosyne

This document explains how Mnemosyne handles languages that do not use
whitespace to delimit words — primarily Chinese, Japanese, and Thai — and how
this differs from the assumptions baked into the Indo-European plugin model.

---

## The Core Difference

In Spanish, German, or French, the input text itself tells you where words
begin and end: spaces separate tokens.  `"gatos bonitos"` is unambiguously
two words.

In Mandarin Chinese or Japanese, word boundaries do not appear in the text.
`"你好世界"` is four characters but exactly two words (`你好` "hello" and
`世界` "world").  Without an NLP segmenter, the text is opaque.

This has downstream consequences for every layer of the stack.

---

## Architecture Impact

### 1. `tokenization_mode = "segmented"`

Plugins for these languages declare `tokenization_mode = "segmented"` in their
`LanguageCapabilities`.  This single field drives several behaviours:

| Layer | Whitespace mode | Segmented mode |
|-------|-----------------|----------------|
| **Difficulty scorer** | `len(text.split())` for word count | uses `word_count_hint = len(objects)` |
| **Frontend pill list** | 0.5 rem gap between pills | 0.2 rem gap (packed, no implied space) |
| **Sentence card text** | normal overflow-wrap | `overflow-wrap: break-word` (already default) |

The `word_count_hint` mechanism exists in `difficulty/scorer.py` specifically so
segmented-language plugins can pass a meaningful token count without the scorer
having to know about segmentation.

### 2. Canonical Forms

For inflected Indo-European languages, the canonical form is the lemma — the
base/dictionary form of a word (`"gato"` for `"gatos"`).  For Chinese, a word
is its own canonical form because Chinese vocabulary does not inflect:

```
es → canonical_form = "gato"  (lemma, not surface "gatos")
zh → canonical_form = "学习"   (word = lemma = surface — all the same)
```

This means Chinese vocabulary objects have `surface_form == canonical_form`.
The lesson engine's vocabulary builder is already robust to this case.

### 3. Transliteration

CJK plugins should declare `transliteration_scheme` when they provide
romanization.  The Chinese plugin uses `"pinyin_tone_marks"`.  This enables:

- The script-view toggle in the results panel (native / romanized / both).
- The script-view toggle inside the lesson modal.
- The `"Romanized"` lesson field tagged with `data-layer="romanized"`.

For a plugin with no romanization support, leave `transliteration_scheme=None`
(the default).

### 4. No Morphology

The vocabulary/conjugation/agreement/case_agreement lesson types all assume
morphological inflection.  Chinese has none in the Latin sense.

Chinese plugins should:
- Set `morphology_depth = "none"`
- Set `lesson_modes_supported = ["vocabulary", "dictionary"]`
- Emit only `"vocabulary"` (or `"dictionary"`) type candidates
- Never emit `"conjugation"`, `"agreement"`, or `"case_agreement"` candidates

The lesson engine degrades cleanly — it will produce vocabulary-mode lessons
with whatever `lesson_data` fields the plugin supplies.

### 5. POS Tags

The Chinese plugin sets `lesson_data["pos"] = "WORD"` as a conservative
default.  The vocabulary builder maps `"WORD"` to the display string `"word"`,
which is correct for a word the learner is encountering.

A future plugin with jieba's POS tagger could supply more specific POS values
(noun, verb, etc.) once the accuracy tradeoffs are evaluated.

---

## The Chinese Plugin (`backend/plugins/chinese.py`)

The Mandarin Chinese (Simplified) plugin is the reference implementation for
this pattern.  It uses:

- **jieba** for word segmentation (optional; falls back to character-level)
- **pypinyin** for tone-marked pinyin romanization (optional; omits the
  "Romanized" lesson field when absent)

Install the CJK extras to enable full functionality:

```bash
poetry install --extras cjk
```

### What it produces

For the sentence `"我喜欢学习中文。"`, the plugin segments it (with jieba) into
something like `["我", "喜欢", "学习", "中文"]` and emits one vocabulary
candidate per unique token:

```python
CandidateObject(
    canonical_form = "学习",
    surface_form   = "学习",
    type           = "vocabulary",
    label          = "学习",
    lesson_data    = {
        "word":   "学习",
        "pos":    "WORD",
        "pinyin": "xué xí",   # omitted when pypinyin absent
    },
    confidence = 0.70,
)
```

### What it does NOT produce (honest claims)

| Feature | Why absent | Upgrade path |
|---------|------------|--------------|
| POS tagging | jieba accuracy varies; not validated | Add jieba POS + confidence threshold |
| Measure words / classifiers | Requires lexicon; not in scope | Dedicated `"measure_word"` plugin or lesson type |
| Idiom detection | Requires fixed-phrase dictionary | `idiom_detection=True` + chengyu list |
| Individual character (hanzi) lessons | Adds complexity; prioritise word-level first | Emit `"script"` type objects per character |
| Traditional Chinese | Separate character set | Add `zh-Hant` plugin or variant flag |

---

## How Segmented-Language Assumptions Differ from Indo-European

| Assumption | Indo-European (ES/DE/FR) | Segmented (ZH/JA) |
|-----------|--------------------------|-------------------|
| Word boundaries visible in text | Yes — spaces | No — segmenter required |
| Lemmatisation needed | Yes — `gatos → gato` | No — form IS lemma |
| Morphological categories | Gender, case, tense, mood | None (or different system) |
| Whitespace word count meaningful | Yes | No — use `word_count_hint` |
| Romanization / transliteration | Usually not needed | Often essential for learners |
| Script-view toggle | Hidden | Shown when scheme declared |

---

## Adding a New Segmentation-Language Plugin

1. Pick a segmentation library (jieba for Chinese, MeCab/fugashi for Japanese,
   pythainlp for Thai, etc.).
2. Declare `tokenization_mode = "segmented"` and the appropriate
   `transliteration_scheme`.
3. Return `"vocabulary"` type candidates from `analyze_sentence()`.
4. Put romanization under `lesson_data["pinyin"]` / `lesson_data["romaji"]` /
   etc. — and use `label = "Romanized"` for the lesson field so the modal's
   `ROMANIZED_LABELS` set picks it up automatically.
5. Do not claim morphological capabilities (`morphology_depth = "none"`,
   `morphology_quality = "none"`) unless the language genuinely has inflection
   your plugin analyses.
6. Pass `word_count_hint = len(candidates)` when calling the difficulty scorer
   (the parse route does this automatically when `tokenization_mode` is not
   `"whitespace"`).

---

## Japanese (Planned)

Japanese is similar to Chinese in tokenization needs but adds:

- **Mixed scripts** — hiragana, katakana, kanji, and romaji coexist in one
  sentence.  The canonical form should use the dictionary form (kanji or
  hiragana as appropriate).
- **Furigana** — ruby-text pronunciation guides.  The lesson field label
  `"Reading(s)"` is already in `ROMANIZED_LABELS` in the modal.
- **Hepburn romanization** — declare `transliteration_scheme = "hepburn_romaji"`.
- **Particles** — は, が, を, etc. are learnable grammatical objects unlike
  anything in the current `LearnableType` set.  A `"particle"` type could be
  added in a future v4 schema revision.

The segmentation infrastructure is identical to Chinese; only the library
(MeCab / fugashi) and romanization scheme differ.
