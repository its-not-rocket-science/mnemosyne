# Semitic morphology spike: Arabic and Hebrew

This spike adds a **no-network, no-heavy-dependency fallback** for Arabic and Hebrew morphology while keeping the capability labels honest. It is intentionally small: the goal is to expose learner-useful root-pattern hints for common words and to exercise the lesson/nuance pipeline, not to claim full parsing accuracy.

## Scope

### Arabic

When CAMeL Tools is unavailable, `backend.morphology.ar_adapter` now provides:

- a tiny curated root/pattern lexicon for common ك.ت.ب and د.ر.س family forms;
- conservative proclitic hints for obvious `و-/ف-`, `ب-/ل-/ك-`, and `ال-` stacks;
- CAMeL-compatible fields (`root`, `pattern`, `prc0`, `prc1`, `prc2`, `aspect`, `voice`) where the heuristic recognizes a form;
- surface-token preservation: attached clitics remain part of the candidate's `canonical_form`.

Unrecognized forms remain vocabulary-only with a confidence note.

### Hebrew

When HebSpaCy is unavailable, `backend.morphology.he_adapter` now provides:

- the existing inseparable-prefix heuristic for `ב-`, `ו-`, `ה-`, `ל-`, `כ-`, `מ-`, `ש-`, and a few two-letter combinations;
- a false-positive blocklist for common complete words such as `שלום`;
- a tiny curated root/binyan/tense lexicon for common verbs such as `כתב`, `קרא`, and `הלך`;
- lesson-data fields (`root`, `binyan`, `tense`, `person`, `number`, `gender`, `verb_form`) when a curated entry matches.

Unrecognized forms remain vocabulary-only with a confidence note.

## Capability policy

Arabic and Hebrew now declare:

- `morphology_depth="shallow"`
- `analysis_depth="morphology_light"`
- `morphology_quality="low"`
- `lesson_modes_supported=["vocabulary", "dictionary"]`

This is deliberately below full morphology. The fallback is useful for basic grammar hints and nuance extraction, but it cannot disambiguate arbitrary unpointed Hebrew, Arabic clitic stacks, dialectal forms, or out-of-lexicon roots.

## Follow-up criteria before expanding

Expand the fallback only when a rule is both:

1. explainable in a learner-facing note, and
2. covered by positive and negative tests that demonstrate reduced false positives.

For production-grade Arabic, prefer CAMeL Tools with the morphology database installed. For production-grade Hebrew, revisit a maintained Hebrew NLP model that is compatible with the app's current spaCy version or another local/offline analyzer that exposes binyan reliably.
