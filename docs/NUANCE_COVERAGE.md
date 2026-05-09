# Nuance Coverage Reference

Coverage status for all 13 supported languages across every `NuanceCapabilities`
dimension.  Run `scripts/audit_nuance_coverage.py` to regenerate the summary
table from live plugin declarations.

---

## Coverage levels

| Level | Meaning |
|-------|---------|
| `none` | Not implemented; no signal produced |
| `stub` | Heuristic or partial-signal; fires but may over- or under-detect |
| `partial` | Curated rules cover the most common cases; known gaps remain |
| `strong` | High recall; edge cases documented |
| `gold` | Near-exhaustive; machine-verified against a held-out corpus |

---

## Coverage table

| Language | Idioms | Phrase families | Etymology | Grammar nuance | Formality/register | Pronunciation TTS | Transliteration | Literary/cultural | Tests |
|----------|--------|-----------------|-----------|----------------|--------------------|-------------------|-----------------|-------------------|-------|
| en (English) | stub | stub | none | none | none | partial | none | none | 8 |
| es (Spanish) | partial | **partial** | **partial** | partial | stub | partial | none | none | **26** |
| fr (French) | partial | stub | none | partial | stub | partial | none | none | 9 |
| de (German) | partial | **partial** | **partial** | partial | stub | partial | none | none | **24** |
| it (Italian) | partial | stub | none | partial | stub | partial | none | none | 8 |
| pt (Portuguese) | partial | stub | none | partial | stub | partial | none | none | 8 |
| ru (Russian) | partial | stub | none | partial | stub | partial | none | none | 8 |
| ar (Arabic) | none | none | none | none | none | stub | none | none | 6 |
| he (Hebrew) | none | none | none | none | none | stub | none | none | 6 |
| zh (Chinese) | none | none | none | none | none | partial | partial | none | 8 |
| ja (Japanese) | none | none | none | stub | none | partial | stub | none | 7 |
| la (Latin) | none | none | none | none | none | stub | none | none | 7 |
| grc (Koine Greek) | none | none | none | none | none | stub | partial | none | 7 |

> "Literary/cultural" collapses `literary_references`, `cultural_references`,
> `proverb_tradition`, and `classical_or_scriptural_allusion` — all are `none`
> for every language currently.

---

## Coverage by layer

### Plugin layer (analyze\_sentence)

The plugin's `analyze_sentence` call returns candidates directly from curated
catalogs and morphological analysis.  It does not call the nuance extractor.

| Language | Idiom catalog | Grammar rules | Register |
|----------|--------------|---------------|---------|
| es | ~35 fixed expressions | ser/estar copula, subjunctive trigger, diminutive suffix | tú/usted |
| fr | ~35 fixed expressions | être copula, subjunctive trigger | tu/vous |
| de | ~35 fixed expressions | separable-verb prefix, two-way prepositions | Sie/du |
| it | ~30 fixed expressions | essere copula, subjunctive trigger, conditional mood | Lei/tu |
| pt | ~30 fixed expressions | ser/estar copula, subjunctive trigger, conditional mood | você/tu |
| ru | ~35 fixed expressions | imperfective/perfective aspect, verbal government | formal/informal verb forms |
| en | heuristic blend-detection | — | — |
| ar | — | — | — |
| he | — | — | — |
| zh | — | — | — |
| ja | — | basic verb-form via morphology\_light | — |
| la | — | — | — |
| grc | — | — | — |

### Extractor layer (NuanceExtractor.extract\_nuance)

The extractor runs after the plugin and receives the plugin's candidates,
the tokenized sentence, and the language tag.  It adds `type="nuance"`
candidates independently.  No extractor is registered for `en`, `it`, or `pt`.

| Language | Extractor detects |
|----------|------------------|
| es | ser/estar distinction · por/para contrast · subjunctive mood triggers · diminutive suffixes (-ito/-ita) · **etymology (16 lemmas)** · **phrase families (15 families)** |
| fr | tu/vous register · *ne* explétif · subjunctive mood · liaison triggers |
| de | modal particles (doch, mal, ja, eigentlich, wohl, …) · separable-verb prefixes · Wechselpräpositionen · **etymology (20 lemmas)** · **phrase families (15 families)** |
| ru | motion-verb direction (идти vs ходить) · verbal government (любить + acc, etc.) |
| zh | aspect particles (了 le · 过 guò · 着 zhe) · measure words (量词) · chengyu (4-char idioms) |
| ja | keigo types (sonkeigo · kenjogo · teineigo) · case particles (は · が · を · に · で · から · まで …) · yojijukugo (4-char set phrases) |
| ar | definite article ال · negation markers (لا · لم · لن · ما · ليس) · root-pattern annotation (when candidate carries root metadata) |
| he | definite prefix ה- · waw conjunction ו- · binyan annotation (when candidate carries binyan metadata) · biblical register (cantillation marks) |
| la | discourse particles (autem · igitur · ergo · tamen · enim · sed · nam · …) · enclitic -que · classical register (macrons in sentence) |
| grc | discourse particles (δέ · γάρ · οὖν · μέν · ἀλλά · …) · οὐ/μή negation distinction · definite article forms |

---

## Rule-based vs curated vs model-derived

| Method | Languages | What it covers |
|--------|-----------|---------------|
| **Curated catalog** | es fr de it pt ru | Fixed-expression idiom tables hand-checked against native-speaker corpora |
| **Rule-based regex/token-match** | all with extractor | Discourse particles, particles, aspect markers, affixes, enclitics — deterministic |
| **Dependency-parse heuristic** | es fr de it pt ru ja | Copula/aspect detection using spaCy dep labels; correctness depends on model quality |
| **Dictionary lookup** | ar he la grc | Vocabulary candidates from embedded lexicon; no morphological inference |
| **Model-derived** | — | *None currently.* No learned classifiers in production. |

All nuance signals are hand-authored or rule-derived.  There are no ML
classifiers or embedding-based detectors in the current codebase.

---

## Known limitations

### Universal
- No etymology data beyond Spanish and German: all other plugins declare `etymology="none"`.
- No literary/cultural references: `literary_references`, `cultural_references`,
  `proverb_tradition`, and `classical_or_scriptural_allusion` are all `none`.
- Phrase families `stub` for French, Italian, Portuguese, Russian; `partial` for Spanish and German only.

### English
- `EnglishStubPlugin` is a scaffold.  Idiom detection is heuristic and fires
  on blend families only.  No grammar nuance or register detection.

### Spanish
- ser/estar detection relies on spaCy dep parse; low-confidence when parse
  is ambiguous (nominal predicates, weather constructions).
- por/para contrast fires on surface token only; indirect-object ambiguity
  not resolved.

### French
- *Ne* explétif fires only in subordinate clauses with trigger verbs (craindre,
  éviter, etc.); free-standing *ne* in informal omission not distinguished.
- Liaison detection is positional (trigger word + vowel-initial next word);
  does not account for *h* aspiré.

### German
- Two-way prepositions detected by surface token; accusative vs dative
  distinction requires dep-parse case label which `de_core_news_sm` under-tags.
- Modal particle confidence is low (0.65) because particles are
  context-dependent; the same word carries different pragmatic force in
  different positions.

### Russian
- Motion-verb extractor requires plugin vocabulary candidates to already
  contain the lemma; pipeline must be `"both"`, not `"extractor"` alone.
- Imperfective/perfective detection covers only the plugin's heuristic rules
  for past-tense verb forms; present and future aspect pairs not covered.
- Verbal government table has ~10 high-frequency verbs; full valency coverage
  would require a lexical database.

### Arabic
- Dictionary-mode plugin; no morphological analysis.  Root-pattern nuance only
  fires when a candidate already carries `root` metadata (rare).
- Definite article detection is regex on ال prefix; does not handle
  elision with sun letters.

### Hebrew
- Dictionary-mode plugin; no morphological analysis.  Binyan nuance fires only
  when a candidate carries `binyan` metadata.
- Inseparable preposition prefixes (ב-, ל-, כ-, מ-, ש-) are stripped for
  dictionary lookup but the stripping is not exposed as a nuance signal.

### Chinese
- chengyu detection requires jieba segmentation; character-level tokenization
  misses 4-char units that jieba would keep together.
- Measure-word detection requires character-level tokenization; jieba may merge
  numeral + classifier into one token.
- No tonal information in lesson data; pinyin readings rely on pypinyin which
  may mis-tone polyphonic characters.

### Japanese
- yojijukugo detection fails when spaCy splits the 4-char compound into
  sub-morpheme tokens (observed for most common yojijukugo in ja_core_news_sm).
- keigo detection via spaCy lemmas is limited to the ~15 honoric/humble lemma
  table and the polite ます/ません endings.
- No pitch-accent information.

### Latin
- 90-entry embedded lexicon covers common prose vocabulary only; inflected
  forms not in the lexicon receive only a `confidence_note`.
- Macron normalization strips length distinctions that differentiate words
  (e.g., malum "apple" vs mālum "evil").

### Koine Greek
- 100-entry lexicon biased toward New Testament vocabulary.
- Diacritic normalization (NFD + strip combining) means canonical forms lose
  accent information needed to distinguish oxytone/barytone pairs.
- Modern Greek TTS (el) used as a proxy; pronunciation differs from
  Erasmian or reconstructed Koine.

---

## Examples per language

### English — idiom blend (heuristic)
```
Input:  "The startup is a fintech-SaaS-AI mashup."
Signal: blend_family · confidence 0.62
```

### Spanish — ser/estar distinction
```
Input:  "Ella es profesora y está muy cansada."
Signal: nuance · ser_copula (permanent role) · estar_predicate (transient state)
```

### Spanish — phrase family (exact match)
```
Input:  "No quiero meter la pata otra vez."
Signal: phrase_family · es_meter_la_pata · 'meter la pata' · confidence 0.95
        lesson_data: meaning='To make a blunder', register='informal', variants=[…]
```

### Spanish — phrase family (inflectional variant)
```
Input:  "No vale la pena discutir esto ahora."
Signal: phrase_family · es_valer_la_pena · 'vale la pena' · confidence 0.85
        matched_variant='vale la pena' · match_type='inflectional_variant'
```

### Spanish — etymology
```
Input:  "Mi amigo vive en Madrid."
Signal: nuance · etymology · nuance:es:etymology:amigo · confidence 0.85
        explanation='From Latin amicus … amare "to love"'
        etymology.cognates=['French ami', 'Italian amico', 'English amicable']
```

### French — register (tu/vous)
```
Input:  "Tu veux venir avec nous ce soir ?"
Signal: nuance · tu_vous_informal · confidence 0.90
```

### German — modal particle
```
Input:  "Das ist doch klar."
Signal: nuance · modal_particle · doch · "speaker assumes shared knowledge" · confidence 0.65
```

### German — phrase family (exact match)
```
Input:  "Das wäre wie Eulen nach Athen tragen."
Signal: phrase_family · de_eulen_nach_athen · 'Eulen nach Athen tragen' · confidence 0.95
        meaning='To carry coals to Newcastle' · origin='Aristophanes, Birds (414 BCE)'
```

### German — etymology
```
Input:  "Das Wort Schadenfreude ist weltweit bekannt."
Signal: nuance · etymology · nuance:de:etymology:schadenfreude · confidence 0.85
        explanation='Compound of Schaden "harm" + Freude "joy" … borrowed into English'
        etymology.roots=['Old High German scado (harm)', 'Old High German frewida (joy)']
```

### Italian — subjunctive mood
```
Input:  "Voglio che lui venga alla riunione."
Signal: nuance · subjunctive_mood · venire · confidence 0.70
```

### Portuguese — ser/estar + subjunctive
```
Input:  "Ela é professora e está muito cansada hoje."
Signal: grammar · ser_copula · pattern "permanent identity vs transient state"

Input:  "Quero que ele venha à reunião amanhã."
Signal: nuance · subjunctive_mood · vir · confidence 0.70
```

### Russian — motion-verb directionality
```
Input:  "Он идёт в библиотеку прямо сейчас."
Signal: nuance · motion_verb · идти · direction_type=unidirectional · confidence 0.85

Input:  "Она ходит в библиотеку каждую субботу."
Signal: nuance · motion_verb · ходить · direction_type=multidirectional · confidence 0.85
```

### Arabic — definite article
```
Input:  "الكتاب على الطاولة."
Signal: nuance · definite_article · الكتاب · confidence 0.90
```

### Hebrew — waw conjunction
```
Input:  "הלך וישב בגן."
Signal: nuance · waw_conjunction · וישב · confidence 0.80
```

### Chinese — aspect particle
```
Input:  "我吃了早饭就去学校了。"
Signal: nuance · aspect_le · 了 · "completion / change of state" · confidence 0.85

Input:  "他到过很多国家。"
Signal: nuance · aspect_guo · 过 · "experiential — happened at least once in life" · confidence 0.85
```

### Japanese — keigo teineigo
```
Input:  "猫は毎日魚を食べます。"
Signal: nuance · keigo · teineigo · ます · "polite present/future" · confidence 0.80
```

### Latin — discourse particle
```
Input:  "Caesar autem in Gallia erat."
Signal: nuance · discourse_particle · autem · "adversative/continuative, always postpositive" · confidence 0.85
```

### Koine Greek — negation distinction
```
Input:  "οὐκ οἶδα τί λέγεις."
Signal: nuance · negation_ou · οὐκ · "negates indicative; factual denial" · confidence 0.85

Input:  "μὴ ποιεῖ τοῦτο ἔτι."
Signal: nuance · negation_me · μή · "negates non-indicative moods; prohibition/wish" · confidence 0.85
```

---

## Test coverage summary

Gold-test fixtures live in `backend/tests/fixtures/nuance_gold/`.
Each fixture covers:

| Category | What is tested |
|----------|---------------|
| Idiom | Canonical form present, confidence ≥ 0.85, lesson\_data keys phrase/meaning/register |
| Grammar nuance | Candidate type, nuance\_type string, confidence threshold |
| Register/formality | Nuance type present for formal/informal sentences; absent in neutral sentences |
| Etymology vocab | Vocabulary candidate present, canonical form substring match, no raw UUIDs |
| False positive | Named nuance types absent from plain control sentences |
| Capability | `plugin.capabilities.nuance_capabilities.<dim>` in declared allowed set |

Total: **~202 parametrized test cases** across 13 languages (as of 2026-05-09).

| Language | Cases | Capability assertions |
|----------|-------|-----------------------|
| en | 8 | 3 |
| es | 26 | 5 |
| fr | 9 | 3 |
| de | 24 | 5 |
| it | 8 | 3 |
| pt | 8 | 3 |
| ru | 8 | 3 |
| ar | 6 | 2 |
| he | 6 | 2 |
| zh | 8 | 2 |
| ja | 7 | 3 |
| la | 7 | 2 |
| grc | 7 | 2 |

---

## Next catalog targets

Priority order based on pedagogical impact vs implementation cost:

1. **it / pt nuance extractors** — Italian and Portuguese have full spaCy
   pipelines but no registered extractor.  Minimum viable: ser/estar (pt),
   essere copula (it), subjunctive triggers (both), register (Lei/você).
   Etymology and phrase-family infrastructure already exists; just needs
   curated data and a registered extractor class.

2. **Etymology store expansion** — Spanish and German have ~16 and ~20 entries
   respectively.  Expanding to 100 high-frequency lemmas per language (with
   cross-language cognate chains) would bring both to `strong`.
   French, Italian, Portuguese, and Russian have zero entries; a 20-lemma
   starter per language would bring each to `stub`.

3. **Phrase family catalog expansion** — Spanish and German now have 15 families
   each (`partial`).  Expanding to 50+ would approach `strong`.
   French, Italian, Portuguese, and Russian declare `stub`; a 15-family
   starter each would upgrade all four to `partial`.

4. **ar / he morphological upgrade** — replace dictionary-mode plugins with
   Stanza or Camel-Tools (Arabic) and YAP/HebSpacy (Hebrew).  Unlocks
   grammar\_nuance, formality\_register, and root/binyan signals.

5. **ja yojijukugo** — extractor detects them but spaCy splits all common
   4-char compounds.  Workaround: pre-scan sentence for dictionary matches
   before passing to spaCy, or use `custom_tokenizer` to protect compounds.

6. **ru verbal government** — current table has ~10 verbs.  Expanding to
   100+ high-frequency verbs would meaningfully improve grammar\_nuance
   quality; partner with a Russian valency lexicon (RuVallex).

7. **proverb\_tradition** — no language has this.  A curated 20-proverb
   starter for each language is achievable without tooling changes.

8. **classical\_or\_scriptural\_allusion for la / grc** — both plugins are
   scaffold-only but the extractor infrastructure exists.  A 50-phrase NT
   Greek / Ciceronian Latin allusion table would bring grc to `partial`
   and la to `stub`.
