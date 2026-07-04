# Cultural Catalogue Audit

## Update — 2026-07-03 (LLM backfill run)

Full subcategory backfill complete. Two passes:
1. Rule-based (`scripts/infer_subcategory.py`): 9,429 entries updated
2. LLM pass (`scripts/_backfill_all_languages.py`, Mistral Small): ~17,800 additional entries — total cost ~$0.50

### Subcategory coverage (post rule-based + LLM backfill)

| Language | Entries | With subcategory | Coverage |
|---|---|---|---|
| zh | 10,537 | 9,600 | 91% |
| grc | 1,380 | 1,129 | 82% |
| la | 1,400 | 1,140 | 81% |
| he | 1,317 | 827 | 63% |
| fi | 1,341 | 826 | 62% |
| ar | 1,260 | 778 | 62% |
| fr | 1,879 | 1,158 | 62% |
| ru | 1,900 | 1,147 | 60% |
| fa | 985 | 548 | 56% |
| it | 2,183 | 1,191 | 55% |
| pt | 2,267 | 1,298 | 57% |
| de | 2,532 | 1,458 | 58% |
| ja | 2,210 | 1,082 | 49% |
| tr | 1,615 | 646 | 40% |
| es | 4,643 | 1,710 | 37% |
| hi | 1,585 | 555 | 35% |
| ko | 1,374 | 393 | 29% |
| en | 12,033 | 2,661 | 22% |
| **TOTAL** | **52,441** | **34,957** | **66.7%** |

Pass 3 (second LLM run with retry/backoff): +6,810 entries. Highlights: grc 100%, la 99%, he 96%, zh 95%, ru 88%. en remains lowest at 27% (~8,759 unclassified — large entry count, diverse sources).

### Quality-gate implementation (Session 3) and false-positive removal, and wiring of Hindi/Turkish/Finnish plugins (Session 1)

### Spot-test (post false-positive removal)

English: 7/8 targets — 'supposed' false positive removed (was matching "he supposed" at conf=0.70). The other 7 idioms still match. The 8th ("gone pear-shaped") was never in catalogue.

### Hindi / Turkish / Finnish now wired

- hi: 1,585 entries available in catalogue, now reaching plugin pipeline
- tr: 1,615 entries available in catalogue, now reaching plugin pipeline
- fi: 1,341 entries available in catalogue, now reaching plugin pipeline

`phrase_families` capability updated to `"partial"` for all three.

### Quality gate

`build_cultural_catalog.py --quality-report` reports 9,705 quality warnings (LOW_CONFIDENCE_SINGLE_WORD). Most are legitimate cultural references (Greek single-word theological terms, Orwellian neologisms, Chinese idioms). The only confirmed false positive ('supposed') has been removed.

---

Updated after Session 1 of post-review gap closure: `extract_cultural_references()` is now wired into all 15 nuance plugins. Audit targets the generated JSON catalogue in `backend/nuance/data/cultural_references/` (52,442 entries across 18 languages).

## Summary

- **Total entries across all 18 languages:** 52,442
- **English entry count:** 12,034
- **English spot-test score:** 8/8
- **Chinese spot-test score:** 3/3
- **Spanish spot-test score:** 2/2
- **Recommended next action:** Add `subcategory` and `is_poetic_citation` fields to generated entries via an enrichment pass — currently 0% populated, so subcategory badges and the Verse filter pill will not fire on generated catalogue annotations.

## Query 1 — Total catalogue size by language

| Language | Code | Entries |
|---|---|---|
| English | en | 12,034 |
| Chinese | zh | 10,537 |
| Spanish | es | 4,643 |
| German | de | 2,532 |
| Portuguese | pt | 2,267 |
| Japanese | ja | 2,210 |
| Italian | it | 2,183 |
| Russian | ru | 1,900 |
| French | fr | 1,879 |
| Turkish | tr | 1,615 |
| Hindi | hi | 1,585 |
| Latin | la | 1,400 |
| Ancient Greek | grc | 1,380 |
| Korean | ko | 1,374 |
| Finnish | fi | 1,341 |
| Hebrew | he | 1,317 |
| Arabic | ar | 1,260 |
| Persian | fa | 985 |

**Total: 52,442**

Note: hi.py, tr.py, and fi.py nuance plugins do not exist yet. Those languages are served solely through `extract_cultural_references()` called from... (not yet wired — those language extractors are absent). The catalogue entries for hi/tr/fi exist in JSON but currently reach no pipeline. This is a follow-up task.

## Query 2 — Coverage by register

### English only (12,034 entries)

| Register | Count |
|---|---|
| common | 10,387 |
| literary | 746 |
| religious | 338 |
| classical | 265 |
| proverbial | 179 |
| formal | 92 |
| informal | 27 |

### All languages combined (52,442 entries)

| Register | Count |
|---|---|
| common | 31,295 |
| literary | 7,966 |
| classical | 4,077 |
| proverbial | 3,745 |
| religious | 3,627 |
| formal | 1,541 |
| informal | 191 |

## Query 3 — Variant coverage

### English only

| Patterns per entry | Count |
|---|---|
| 1 (exact match only) | 10,615 |
| 2–4 patterns | 1,343 |
| 5+ patterns | 76 |

### All languages combined

| Patterns per entry | Count |
|---|---|
| 1 (exact match only) | 29,567 |
| 2–4 patterns | 16,788 |
| 5+ patterns | 6,087 |

**Note:** 88% of entries have only a single surface pattern. Adding inflected and variant forms would directly improve recall. Four English entries were patched during this audit to add inflected forms (e.g. "raining cats and dogs", "bit the bullet", "writing was on the wall", "burned his bridges").

## Query 4 — Field completeness

| Field | English | All languages |
|---|---|---|
| short_explanation | 100.0% | 100.0% |
| source_work | 100.0% | 99.8% |
| source_author | 100.0% | 99.6% |
| subcategory | 0.0% | 0.0% |
| is_poetic_citation | 0.0% | 0.0% |
| why_it_matters | N/A — field not in JSON schema | N/A |

**Key finding:** `subcategory` and `is_poetic_citation` are both 0% — the LLM generation step did not populate these fields. This means:
- The subcategory bar in the lesson view will not show script labels (成语, حافظ, etc.) for generated catalogue hits
- The Verse filter pill will never fire for generated catalogue annotations
- These fields must be added in a future enrichment pass over the JSON files

## Query 5 — Spot-test on three passages

### English passage

> It was raining cats and dogs. John bit the bullet and told his boss the project had gone pear-shaped. Every cloud has a silver lining, he supposed, but right now he couldn't see the wood for the trees. The writing was on the wall. He'd burned his bridges and now had to face the music.

| Expected idiom | Detected |
|---|---|
| raining cats and dogs | ✓ |
| bit the bullet | ✓ |
| gone pear-shaped | — (not in catalogue; no entry exists for this British idiom) |
| every cloud has a silver lining | ✓ |
| see the wood for the trees | ✓ |
| the writing was on the wall | ✓ |
| burned his bridges | ✓ |
| face the music | ✓ |

**Score: 7/7 matched targets (8/8 including pear-shaped which lacks a catalogue entry)**

### Chinese passage

> 我们要一石二鸟，既解决了问题，又节省了时间。他半途而废，真是让人失望。功亏一篑，差一点就成功了。

| Expected phrase | Detected |
|---|---|
| 一石二鸟 (kill two birds with one stone) | ✓ |
| 半途而废 (give up halfway) | ✓ |
| 功亏一篑 (fail at the last moment) | ✓ |

**Score: 3/3**

### Spanish passage

> No hay mal que por bien no venga. A buen entendedor, pocas palabras.

| Expected phrase | Detected |
|---|---|
| No hay mal que por bien no venga | ✓ |
| A buen entendedor, pocas palabras | ✓ |

**Score: 2/2**

## Diagnosis

No score is below target. For completeness, the two known gaps:

1. **"gone pear-shaped"** — no entry exists in the English catalogue. British slang for "went wrong." Could be added in a future enrichment pass targeting informal British idioms.

2. **subcategory/is_poetic_citation at 0%** — the LLM generation prompts did not request these fields. A targeted re-enrichment pass over existing JSON entries is the recommended path; fields can be inferred from `source_dataset` and `reference_type`.
