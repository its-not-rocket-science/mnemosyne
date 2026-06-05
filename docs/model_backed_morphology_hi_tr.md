# Model-backed morphology prototype: Hindi and Turkish

## Sources checked

- Stanza has downloadable UD-backed models for both Hindi (`hi`, HDTB) and Turkish (`tr`, several treebanks). Its public performance table reports Hindi HDTB at very strong end-to-end scores, including 97.95 UPOS, 94.41 UFeats, and 96.88 lemma; Turkish is more variable by treebank, ranging from high-domain sets such as Tourism/ATIS to lower BOUN/IMST parsing and morphology scores.
- UDPipe 2 also publishes UD 2.15 models for Hindi and Turkish. Hindi HDTB is strong (raw-text 97.59 UPOS, 94.21 UFeats, 98.92 lemma), while Turkish quality is treebank-dependent: ATIS/Tourism/FrameNet are strong but BOUN/IMST/Kenet show lower raw-text UFeats/LAS, so UDPipe is viable but not obviously better than Stanza for this prototype.
- Universal Dependencies has a single Hindi HDTB-backed path through Stanza/UDPipe and several Turkish treebanks. That means Hindi is a simpler upgrade target; Turkish needs more care around treebank/domain choice and agglutinative ambiguity.

## Prototype decision

- **Hindi:** use Stanza as the optional model-backed adapter. `backend/morphology/hi_adapter.py` maps UD `lemma`, `upos`, `Case`, `Number`, `Person`, `Tense`, `Mood`, `Aspect`, `Voice`, and `VerbForm` into Mnemosyne lesson fields. If Stanza or its model is unavailable, the plugin keeps using the existing Devanagari suffix-rule path.
- **Turkish:** keep the current layered prototype: Stanza UD first (`backend/morphology/tr_stanza_adapter.py`), zeyrek FST second (`backend/morphology/tr_adapter.py`), and suffix rules last. `tr_adapter.py` already existed as the zeyrek adapter, so the Stanza prototype lives in `tr_stanza_adapter.py` rather than replacing that module. The Stanza adapter maps `lemma`, `upos`, case, number, person, tense/aspect/evidential, mood, polarity, verb form, and possessive (`Person[psor]`/`Number[psor]`) into existing Mnemosyne fields.

## Fixture comparison summary

- Existing rule fixtures still pass by construction when model availability is monkeypatched off: Hindi future/habitual forms and Turkish future/locative forms continue to emit conjugation or vocabulary candidates from suffix rules.
- Model-backed paths are richer where available: Hindi gains lemma-backed verb/noun/adjective canonical forms and UD feature-backed aspect/tense/gender/case; Turkish gains UD lemma/upostag features and possessive-case stacking from `Person[psor]` and `Number[psor]`.
- Confidence is intentionally conservative. Heuristic candidates keep low confidence and a `confidence_note`; opaque unknown rule output remains `None`; Turkish Stanza tokens with no UD feature string no longer receive high confidence merely because the tokenizer/POS tagger emitted a token.
- Candidate canonical forms are de-duplicated in all model and fallback paths tested.

## Recommendation

**C. Upgrade both, with different confidence levels.**

- Upgrade **Hindi now** as Stanza-backed morphology. Hindi has a clear Stanza model, a single strong UD treebank path, and materially better learner output than suffix-only rules.
- Upgrade **Turkish now as a layered optional path**, not as a Stanza-only replacement. Stanza adds UD features and possessive-case stacking, but Turkish model quality varies by treebank/domain; zeyrek remains useful as a rule-based agglutinative backup, and suffix rules must stay as the final no-dependency fallback.

No public APIs or canonical UUID namespace behavior were changed.
