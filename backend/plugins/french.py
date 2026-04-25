"""French language plugin — spaCy ``fr_core_news_sm``.

Registers as ``language_code = "fr"``.

Read this alongside ``PLUGIN_AUTHOR_GUIDE.md`` and the Spanish reference
implementation (``spanish.py``) when building or extending this plugin.

─────────────────────────────────────────────────────────────────────────────
WHAT THIS PLUGIN EXTRACTS
─────────────────────────────────────────────────────────────────────────────

**Vocabulary** — open-class content words (NOUN, ADJ, ADV, non-finite
VERB/AUX).  Finite verbs are *excluded* here; they appear as conjugation
objects.  Gender and number are included for NOUN entries when the model
provides them.

  lesson_data keys: lemma, pos, gender*, number*, verb_form*, confidence_note*
  (* = only when available)

**Conjugation** — finite VERB and AUX tokens (VerbForm=Fin), annotated with:
  • morphological features: tense, mood, person, number
  • is_reflexive: True when a child PRON carries Reflex=Yes
  • morph_complete: True when tense + mood + person are all resolved
  • paradigm_class: -er / -ir / -re / irregular
  • is_irregular: True for known irregular verb stems

  lesson_data keys: lemma, surface, tense, mood, person, number,
                    morph_complete, is_reflexive, paradigm_class, is_irregular,
                    confidence_note*

**Agreement** — DET+NOUN and ADJ+NOUN pairs with at least one positively
confirmed morphological match (gender or number).  Confirmed mismatches are
silently dropped.

  lesson_data keys: modifier, modifier_pos, noun, gender, number,
                    gender_match, number_match, confidence_note

─────────────────────────────────────────────────────────────────────────────
GRAMMAR PATTERNS
─────────────────────────────────────────────────────────────────────────────

**Grammar** — periphrastic construction objects derived from conjugation
results.  One object per distinct construction type per sentence.  Covers:
  être_copula, avoir_perfect, être_perfect, aller_near_future.

  lesson_data keys: pattern_id, pattern, usage, contrast, verb_lemma,
                    surface_verb

**Idiom** — ~35 common fixed French expressions detected by surface-form
token matching against a curated table.

  lesson_data keys: phrase, meaning, register

**Nuance** — aspectual and modal observations derived from conjugation
results.  Covers: imperfect_aspect, subjunctive_mood, conditional_mood,
reflexive_verb.

  lesson_data keys: nuance_type, lemma, surface, note, contrast_tense*

─────────────────────────────────────────────────────────────────────────────
KNOWN MODEL LIMITATIONS (fr_core_news_sm)
─────────────────────────────────────────────────────────────────────────────

- ``fr_core_news_sm`` (~16 MB) is a small model.  It has a confirmed bug where
  finite verbs following noun subjects are sometimes mis-tagged as ADJ or NOUN
  (e.g. "Le professeur parle." → ``parle`` tagged as ADJ, not VERB).  These
  are silently under-extracted — the plugin never re-tags tokens.
- French future simple ("je parlerai") is sometimes tagged as ``Tense=Pres``
  rather than ``Tense=Fut`` by this model.  The emitted tense label reflects
  what the model provides, not what is linguistically correct.
- Elided pronouns ("l'", "j'", "n'", "s'") are correctly split by spaCy into
  separate tokens before analysis reaches this plugin.  No extra handling is
  needed; the elided DET/PRON tokens are skipped by ``_SKIP_POS``.
- Contractions "au" (= à + le) and "du" (= de + le) are tagged as ADP with
  embedded determiner morphology.  The plugin skips them correctly (ADP is in
  ``_SKIP_POS``).  Learners are not shown these as agreement examples.
- The model occasionally misassigns gender on nouns — ``pomme`` (feminine) may
  receive ``Gender=Masc``.  Confidence is accordingly modest.

─────────────────────────────────────────────────────────────────────────────
MULTILINGUAL ARCHITECTURE FINDINGS
─────────────────────────────────────────────────────────────────────────────

This plugin reveals the following places where the core was implicitly
Spanish-specific:

1. ``generators._TENSE_OPTIONS`` includes "preterite", a term specific to
   Spanish pedagogy.  French has no preterite; its simple past (passé simple)
   is literary and the pedagogically relevant past forms are imparfait and
   passé composé (a compound tense, not a single conjugation token).
   "preterite" therefore appears as a wrong option in tense MC drills for
   French, which is misleading.
   Tracked: see the ``# ARCH:`` comment in ``lesson/generators.py`` near
   ``_TENSE_OPTIONS``.

2. ``paradigm_class`` is language-specific: Spanish uses ``-ar``/``-er``/``-ir``;
   French uses ``-er``/``-ir``/``-re``/``irregular``.  The lesson generator
   treats this field as an opaque string so no core change is needed today,
   but future paradigm-table drills will need per-language awareness.

3. Reflexive detection: Spanish uses a hardcoded frozenset of surface forms
   (``me``, ``te``, ``se``, ``nos``, ``os``).  French uses the same pronoun
   surfaces in different grammatical contexts (``me``, ``te``, ``se``,
   ``nous``, ``vous``).  This plugin uses the model-agnostic ``Reflex=Yes``
   morph feature, which is more portable.  The Spanish plugin should be
   updated to also accept ``Reflex=Yes`` as an alternative signal.
"""
from __future__ import annotations

import logging
from functools import cached_property
from typing import Any

from backend.plugins.cefr_vocab import A1 as _CEFR_A1
from backend.core.vocab_index import get_cefr_level as _get_cefr_level
from backend.schemas.language import LanguageCapabilities
from backend.schemas.parse import (
    CandidateObject,
    CandidateSentenceResult,
    RelationHint,
)

logger = logging.getLogger(__name__)

_A1 = _CEFR_A1.get("fr", frozenset())

# ── POS filter ────────────────────────────────────────────────────────────────

_SKIP_POS = frozenset({
    "DET", "ADP", "CCONJ", "SCONJ", "CONJ", "PUNCT", "SPACE",
    "X", "SYM", "NUM", "PRON", "INTJ",
})

# VerbForm values that classify a VERB/AUX token as non-finite.
_NON_FINITE_FORMS = frozenset({"Inf", "Part", "Ger"})

# ── Display maps ──────────────────────────────────────────────────────────────
#
# French tense values differ from Spanish:
#   - "Past" appears only on past participles (VerbForm=Part).  On a finite
#     verb it would indicate literary passé simple, rarely emitted by
#     fr_core_news_sm.
#   - Conditional is encoded as Mood=Cnd (not a Tense value).  Tense=Cnd is
#     listed defensively in case the model ever uses it.

_TENSE_DISPLAY: dict[str, str] = {
    "Pres": "present",
    "Imp":  "imperfect",
    "Fut":  "future",
    "Past": "past",        # passé simple (literary); also on past participles
    "Cnd":  "conditional", # defensive — French conditional normally via Mood=Cnd
}

_MOOD_DISPLAY: dict[str, str] = {
    "Ind": "indicative",
    "Sub": "subjunctive",
    "Cnd": "conditional",  # conditionnel présent (Mood=Cnd, Tense=Pres)
    "Imp": "imperative",
}

# ── Irregular verbs ───────────────────────────────────────────────────────────
# Common French verbs whose paradigm cannot be predicted from the infinitive
# ending alone.

_IRREGULAR_VERBS: frozenset[str] = frozenset({
    "être", "avoir", "aller", "faire", "pouvoir", "vouloir", "savoir",
    "venir", "voir", "prendre", "mettre", "partir", "sortir", "tenir",
    "croire", "boire", "recevoir", "devoir", "valoir", "falloir",
    "naître", "connaître", "paraître", "rire", "suivre", "vivre",
    "dire", "lire", "écrire", "courir", "mourir", "ouvrir", "offrir",
})


# ── Idiom table ───────────────────────────────────────────────────────────────
# Each entry: (token_tuple_lowercase, english_meaning, register)
# Sorted longest-first so a longer match claims positions before shorter ones.
# Only invariant fixed-form expressions are listed.  Verb-headed idioms
# (e.g. "casser les pieds") require lemma matching and are not yet supported.

_IDIOM_TABLE: tuple[tuple[tuple[str, ...], str, str], ...] = (
    # ── 4-word ────────────────────────────────────────────────────────────────
    (("de", "temps", "en", "temps"),    "from time to time",               "neutral"),
    (("de", "toute", "façon"),           "anyway / in any case",            "neutral"),
    (("tout", "au", "plus"),             "at most",                         "neutral"),
    # ── 3-word ────────────────────────────────────────────────────────────────
    (("tout", "à", "fait"),              "absolutely / quite right",        "neutral"),
    (("tout", "de", "même"),             "all the same / even so",          "neutral"),
    (("tout", "à", "coup"),              "suddenly",                        "neutral"),
    (("tout", "de", "suite"),            "immediately / right away",        "neutral"),
    (("à", "peu", "près"),               "approximately / more or less",    "neutral"),
    (("à", "vrai", "dire"),              "to tell the truth",               "formal"),
    (("à", "la", "fois"),               "at the same time / both",          "neutral"),
    (("en", "même", "temps"),           "at the same time",                 "neutral"),
    (("en", "tout", "cas"),             "in any case / at any rate",        "neutral"),
    (("à", "ce", "propos"),             "on that subject / in that regard", "formal"),
    (("bien", "au", "contraire"),       "quite the contrary",               "neutral"),
    # ── 2-word ────────────────────────────────────────────────────────────────
    (("bien", "sûr"),                   "of course",                        "neutral"),
    (("bien", "entendu"),               "of course / naturally",            "formal"),
    (("en", "effet"),                   "indeed / in fact",                 "formal"),
    (("par", "exemple"),                "for example",                      "neutral"),
    (("en", "fait"),                    "in fact / actually",               "neutral"),
    (("de", "plus"),                    "furthermore / moreover",           "neutral"),
    (("en", "général"),                 "in general / generally",           "neutral"),
    (("après", "tout"),                 "after all",                        "neutral"),
    (("sans", "doute"),                 "no doubt / probably",              "neutral"),
    (("en", "revanche"),                "on the other hand / in return",    "formal"),
    (("au", "contraire"),               "on the contrary",                  "neutral"),
    (("au", "moins"),                   "at least",                         "neutral"),
    (("à", "nouveau"),                  "again / anew",                     "neutral"),
    (("quand", "même"),                 "all the same / nevertheless",      "neutral"),
    (("par", "contre"),                 "on the other hand",                "neutral"),
    (("en", "principe"),                "in principle / as a rule",         "neutral"),
    (("en", "pratique"),                "in practice",                      "neutral"),
    (("à", "part"),                     "apart from / except for",          "neutral"),
    (("en", "dehors"),                  "outside / apart from",             "neutral"),
    (("tôt", "ou"),                     "sooner or later",                  "neutral"),
)

# ── Grammar patterns ──────────────────────────────────────────────────────────
# Each entry: (construction, required_lemma_or_None, pattern_id,
#              pattern_label, usage_text, contrast_text)
# Matched against the ``construction`` and ``lemma`` fields of conjugation
# candidates produced by ``_extract_conjugations``.

_GRAMMAR_PATTERNS: tuple[
    tuple[str, str | None, str, str, str, str], ...
] = (
    (
        "copula", "être",
        "être_copula",
        "être + [noun / adjective]",
        "Expresses identity, profession, nationality, and descriptive states: "
        "'Je suis médecin', 'Elle est intelligente'. "
        "Unlike Spanish, French uses a single copula for both permanent and "
        "temporary states.",
        "English learners should resist translating 'be' as 'avoir'; "
        "'avoir' is used for age and physical sensations "
        "('j'ai faim', 'j'ai vingt ans').",
    ),
    (
        "perfect", "avoir",
        "avoir_perfect",
        "avoir + [past participle]",
        "Forms the passé composé for most verbs: 'j'ai mangé' (I ate / I have eaten). "
        "The past participle agrees in gender and number with a preceding direct object.",
        "Verbs of movement and reflexive verbs use être, not avoir, to form the passé composé.",
    ),
    (
        "perfect", "être",
        "être_perfect",
        "être + [past participle]",
        "Forms the passé composé for verbs of movement and state change "
        "(aller, venir, partir, arriver, naître, mourir, etc.) and all reflexive verbs: "
        "'il est parti', 'elle s'est levée'. "
        "The past participle agrees with the subject in gender and number.",
        "Most other verbs use avoir to form the passé composé.",
    ),
    (
        "near_future", "aller",
        "aller_near_future",
        "aller + [infinitive]",
        "Expresses a planned or near-future action: "
        "'je vais étudier' (I am going to study). "
        "More common than the simple future in everyday speech.",
        "The simple future (j'étudierai) is more formal and used for "
        "more distant or uncertain events.",
    ),
)


# ── Plugin ────────────────────────────────────────────────────────────────────

class FrenchPlugin:
    language_code = "fr"
    display_name  = "French"
    direction     = "ltr"
    capabilities  = LanguageCapabilities(
        code="fr",
        display_name="French",
        direction="ltr",
        script_family="latin",
        tokenization_mode="whitespace",
        morphology_depth="rich",
        lesson_modes_supported=["morphology", "vocabulary"],
        # v2 fields
        analysis_depth="full",
        segmentation_quality="medium",    # fr_core_news_sm sentence splits are decent
        tokenization_quality="high",      # French word tokenisation + elision handling is reliable
        morphology_quality="medium",      # small model; verb POS-tagging errors in some contexts
        syntax_support=True,              # dep parse used for modifier / reflexive detection
        idiom_detection=True,             # curated fixed-expression table (~35 entries)
        tts_lang_tag="fr",
        transliteration_scheme=None,
        # French: conditional is a mood (Mood=Cnd), not a tense — "preterite"
        # does not exist in modern French; passé simple is literary only.
        tense_pool=["present", "imperfect", "future", "past", "past perfect"],
        mood_pool=["indicative", "subjunctive", "conditional", "imperative"],
    )

    def __init__(self) -> None:
        self.lesson_store: dict[str, CandidateObject] = {}

    # ------------------------------------------------------------------
    # Model — lazy, loaded at most once per process via cached_property
    # ------------------------------------------------------------------

    @cached_property
    def _nlp(self) -> Any:
        try:
            import spacy  # noqa: PLC0415
            return spacy.load("fr_core_news_sm", disable=["ner"])
        except ImportError as exc:
            raise RuntimeError(
                "spaCy is not installed.  Run: pip install spacy"
            ) from exc
        except OSError as exc:
            raise RuntimeError(
                "spaCy model 'fr_core_news_sm' not found. "
                "Run: python -m spacy download fr_core_news_sm"
            ) from exc

    # ------------------------------------------------------------------
    # LanguagePlugin protocol
    # ------------------------------------------------------------------

    def analyze_text(self, text: str) -> list[CandidateSentenceResult]:
        """Parse full text in a single spaCy call; return one result per sentence."""
        doc = self._nlp(text.strip())
        results = []
        for sent in doc.sents:
            sent_text = sent.text.strip()
            if not sent_text:
                continue
            results.append(self._analyze_tokens(sent_text, list(sent)))
        return results

    def split_sentences(self, text: str) -> list[str]:
        doc = self._nlp(text.strip())
        return [s.text.strip() for s in doc.sents if s.text.strip()]

    def analyze_sentence(self, sentence: str) -> CandidateSentenceResult:
        doc = self._nlp(sentence)
        return self._analyze_tokens(sentence, list(doc))

    def _analyze_tokens(
        self, sentence: str, tokens: list[Any]
    ) -> CandidateSentenceResult:
        seen_vocab: set[str] = set()
        seen_conj:  set[str] = set()

        candidates: list[CandidateObject] = []

        conj_candidates = self._extract_conjugations(tokens, seen_conj, seen_vocab)
        candidates.extend(conj_candidates)
        candidates.extend(self._extract_vocabulary(tokens, seen_vocab))
        candidates.extend(self._extract_agreements(tokens))
        candidates.extend(self._extract_idioms(tokens))

        seen_grammar: set[str] = set()
        seen_nuance:  set[str] = set()
        candidates.extend(self._extract_grammar(conj_candidates, seen_grammar))
        candidates.extend(self._extract_nuance(conj_candidates, seen_nuance))

        return CandidateSentenceResult(text=sentence, candidates=candidates)

    def get_lesson(self, object_id: str) -> CandidateObject | None:
        return self.lesson_store.get(object_id)

    # ------------------------------------------------------------------
    # Vocabulary
    # ------------------------------------------------------------------

    def _extract_vocabulary(
        self,
        tokens: list[Any],
        seen: set[str],
    ) -> list[CandidateObject]:
        candidates: list[CandidateObject] = []
        for tok in tokens:
            if tok.pos_ in _SKIP_POS or tok.is_punct or tok.is_space:
                continue

            verb_form = _morph_first(tok, "VerbForm")

            # Finite VERB/AUX → conjugation only; non-finite → vocabulary.
            if tok.pos_ in {"VERB", "AUX"} and verb_form not in _NON_FINITE_FORMS:
                continue

            lemma = tok.lemma_.lower()

            # Enclitic-fusion artefact: the model cannot split clitics from
            # their host verb, yielding multi-word lemmas (e.g. "s' appeler").
            if " " in lemma:
                continue

            if len(lemma) < 2 or lemma in seen:
                continue
            seen.add(lemma)

            confidence, confidence_note = self._vocab_confidence(tok, lemma)
            data: dict[str, Any] = {"lemma": lemma, "pos": tok.pos_}
            cefr = _get_cefr_level("fr", lemma) or ("A1" if lemma in _A1 else None)
            if cefr:
                data["cefr_level"] = cefr

            if tok.pos_ == "NOUN":
                if noun_gender := _morph_first(tok, "Gender"):
                    data["gender"] = noun_gender
                if noun_number := _morph_first(tok, "Number"):
                    data["number"] = noun_number

            if tok.pos_ in {"VERB", "AUX"} and verb_form:
                data["verb_form"] = verb_form

            if confidence_note is not None:
                data["confidence_note"] = confidence_note

            candidates.append(CandidateObject(
                canonical_form=lemma,
                surface_form=tok.text,
                type="vocabulary",
                label=tok.text,
                lesson_data=data,
                confidence=confidence,
            ))
        return candidates

    def _vocab_confidence(self, tok: Any, lemma: str) -> tuple[float, str | None]:
        if tok.pos_ == "PROPN":
            return 0.60, "proper noun — may not represent general vocabulary"
        if lemma in _A1 or _get_cefr_level("fr", lemma):
            return 0.90, None  # known word — suppress is_oov false-positive
        if tok.is_oov:
            return 0.50, "word not found in model vocabulary — form may be incorrect"
        return 0.85, None

    # ------------------------------------------------------------------
    # Conjugation
    # ------------------------------------------------------------------

    def _extract_conjugations(
        self,
        tokens: list[Any],
        seen_conj: set[str],
        seen_vocab: set[str],
    ) -> list[CandidateObject]:
        candidates: list[CandidateObject] = []
        for tok in tokens:
            if tok.pos_ not in {"VERB", "AUX"}:
                continue
            verb_form = _morph_first(tok, "VerbForm")
            if verb_form in _NON_FINITE_FORMS:
                continue

            lemma = tok.lemma_.lower()
            if " " in lemma:
                continue

            feats = self._verb_morph(tok)
            canonical_form = _conj_canonical_form(lemma, feats)
            if canonical_form in seen_conj:
                continue
            seen_conj.add(canonical_form)
            seen_vocab.add(lemma)

            is_reflexive    = _has_reflexive_clitic(tok, tokens)
            construction    = _detect_construction(tok)
            confidence      = self._conj_confidence(tok, feats)
            confidence_note = _conj_confidence_note(feats, tok.is_oov)

            lesson: dict[str, Any] = {
                "lemma":          lemma,
                "surface":        tok.text,
                "tense":          feats["tense"],
                "mood":           feats["mood"],
                "person":         feats["person"],
                "number":         feats["number"],
                "morph_complete": _conj_is_complete(feats),
                "is_reflexive":   is_reflexive,
                "construction":   construction,
                "paradigm_class": _paradigm_class(lemma),
                "is_irregular":   lemma in _IRREGULAR_VERBS,
            }
            if "verb_form" in feats:
                lesson["verb_form"] = feats["verb_form"]
            if confidence_note is not None:
                lesson["confidence_note"] = confidence_note

            candidates.append(CandidateObject(
                canonical_form=canonical_form,
                surface_form=tok.text,
                type="conjugation",
                label=tok.text,
                lesson_data=lesson,
                confidence=confidence,
                relation_hints=[
                    RelationHint(
                        relation_type="conjugation_of",
                        target_canonical_form=lemma,
                        target_type="vocabulary",
                    )
                ],
            ))
        return candidates

    def _verb_morph(self, tok: Any) -> dict[str, str]:
        tense_raw = _morph_first(tok, "Tense")
        mood_raw  = _morph_first(tok, "Mood")
        person    = _morph_first(tok, "Person")
        number    = _morph_first(tok, "Number")
        verb_form = _morph_first(tok, "VerbForm")

        feats: dict[str, str] = {
            "tense":  _TENSE_DISPLAY.get(tense_raw or "", tense_raw or "unknown"),
            "mood":   _MOOD_DISPLAY.get(mood_raw or "", mood_raw or "unknown"),
            "person": person or "unknown",
            "number": number or "unknown",
        }
        if verb_form:
            feats["verb_form"] = verb_form
        return feats

    def _conj_confidence(self, tok: Any, feats: dict[str, str]) -> float:
        known = sum(
            1 for k in ("tense", "mood", "person")
            if feats.get(k) not in (None, "unknown")
        )
        # Cap at 0.80 (vs 0.85 for Spanish) — fr_core_news_sm has higher verb
        # mis-tagging rate in some sentence structures.
        base = 0.50 + known * 0.10
        if tok.is_oov:
            base -= 0.10
        return round(min(base, 0.80), 2)

    # ------------------------------------------------------------------
    # Agreement
    # ------------------------------------------------------------------

    def _extract_agreements(self, tokens: list[Any]) -> list[CandidateObject]:
        """Find DET+NOUN and ADJ+NOUN agreement pairs.

        French-specific notes:
        - Adjectives may precede or follow the noun (belle maison, maison
          blanche).  The dep-arc approach handles both positions.
        - Elided determiners ("l'", "d'") are already split by spaCy into
          separate tokens with correct dep=det arcs.
        - "au" and "du" (contracted prepositions) are tagged ADP, not DET,
          so they are naturally excluded.
        """
        candidates: list[CandidateObject] = []
        seen_pairs: set[tuple[str, str, str]] = set()

        nouns = [t for t in tokens if t.pos_ == "NOUN"]
        for noun in nouns:
            noun_gender = _morph_first(noun, "Gender")
            noun_number = _morph_first(noun, "Number")
            if not noun_gender and not noun_number:
                continue

            for cand in _find_modifiers(noun, tokens):
                cand_gender = _morph_first(cand, "Gender")
                cand_number = _morph_first(cand, "Number")

                gender_match = (
                    cand_gender == noun_gender
                    if cand_gender and noun_gender else None
                )
                number_match = (
                    cand_number == noun_number
                    if cand_number and noun_number else None
                )

                if gender_match is None and number_match is None:
                    continue
                if gender_match is False or number_match is False:
                    continue

                pair_key = (cand.pos_, cand.lemma_.lower(), noun.lemma_.lower())
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                noun_lemma = noun.lemma_.lower()
                cand_lemma = cand.lemma_.lower()
                label = (
                    f"{cand.text} {noun.text}"
                    if cand.i < noun.i
                    else f"{noun.text} {cand.text}"
                )
                canonical_form = f"{cand.pos_.lower()}:{cand_lemma}_{noun_lemma}"
                confidence      = _agreement_confidence(gender_match, number_match)
                confidence_note = _agreement_confidence_note(gender_match, number_match)

                candidates.append(CandidateObject(
                    canonical_form=canonical_form,
                    surface_form=label,
                    type="agreement",
                    label=label,
                    lesson_data={
                        "modifier":        cand.text,
                        "modifier_pos":    cand.pos_,
                        "noun":            noun.text,
                        "gender":          noun_gender or "unknown",
                        "number":          noun_number or "unknown",
                        "gender_match":    gender_match,
                        "number_match":    number_match,
                        "confidence_note": confidence_note,
                    },
                    confidence=confidence,
                    relation_hints=[
                        RelationHint(
                            relation_type="agreement_of",
                            target_canonical_form=noun_lemma,
                            target_type="vocabulary",
                        )
                    ],
                ))
        return candidates


    # ------------------------------------------------------------------
    # Idioms
    # ------------------------------------------------------------------

    def _extract_idioms(self, tokens: list[Any]) -> list[CandidateObject]:
        """Detect invariant multi-word expressions by surface-form token matching.

        Scans the lowercased token sequence for entries in ``_IDIOM_TABLE``.
        The table is sorted longest-first so a longer match claims positions
        before shorter overlapping phrases are considered.

        Confidence is 0.90: direct string equality on a curated fixed-form
        list requires no morphological analysis.
        """
        if not tokens:
            return []

        lower_texts = [t.text.lower() for t in tokens]
        n = len(lower_texts)
        seen_idioms: set[str] = set()
        used_positions: set[int] = set()
        candidates: list[CandidateObject] = []

        for words, meaning, register in _IDIOM_TABLE:
            wlen = len(words)
            for start in range(n - wlen + 1):
                if any(start + k in used_positions for k in range(wlen)):
                    continue
                if lower_texts[start : start + wlen] == list(words):
                    phrase = " ".join(words)
                    if phrase in seen_idioms:
                        continue
                    seen_idioms.add(phrase)
                    used_positions.update(range(start, start + wlen))
                    surface = " ".join(t.text for t in tokens[start : start + wlen])
                    candidates.append(CandidateObject(
                        canonical_form=phrase,
                        surface_form=surface,
                        type="idiom",
                        label=surface,
                        lesson_data={
                            "phrase":   phrase,
                            "meaning":  meaning,
                            "register": register,
                        },
                        confidence=0.90,
                    ))

        return candidates

    # ------------------------------------------------------------------
    # Grammar patterns
    # ------------------------------------------------------------------

    def _extract_grammar(
        self,
        conj_candidates: list[CandidateObject],
        seen_grammar: set[str],
    ) -> list[CandidateObject]:
        """Emit grammar-pattern objects derived from conjugation results.

        Each construction type is emitted at most once per sentence.  Grammar
        objects complement conjugation objects: the conjugation tells the
        learner *which* form was used; the grammar object explains *why* the
        construction exists and what the contrast is.

        Confidence is 0.85: construction detection is based on spaCy dependency
        arcs and is reliable for common sentences.
        """
        candidates: list[CandidateObject] = []

        for conj in conj_candidates:
            construction = conj.lesson_data.get("construction", "standalone")
            lemma        = conj.lesson_data.get("lemma", "")
            surface_verb = conj.lesson_data.get("surface", conj.label)

            for (
                expected_construction,
                expected_lemma,
                pattern_id,
                pattern,
                usage,
                contrast,
            ) in _GRAMMAR_PATTERNS:
                if construction != expected_construction:
                    continue
                if expected_lemma is not None and lemma != expected_lemma:
                    continue

                canonical_form = f"grammar:{pattern_id}"
                if canonical_form in seen_grammar:
                    continue
                seen_grammar.add(canonical_form)

                candidates.append(CandidateObject(
                    canonical_form=canonical_form,
                    surface_form=surface_verb,
                    type="grammar",
                    label=surface_verb,
                    lesson_data={
                        "pattern_id":   pattern_id,
                        "pattern":      pattern,
                        "usage":        usage,
                        "contrast":     contrast,
                        "verb_lemma":   lemma,
                        "surface_verb": surface_verb,
                    },
                    confidence=0.85,
                    relation_hints=[
                        RelationHint(
                            relation_type="instance_of",
                            target_canonical_form=conj.canonical_form,
                            target_type="conjugation",
                        )
                    ],
                ))

        return candidates

    # ------------------------------------------------------------------
    # Nuance
    # ------------------------------------------------------------------

    def _extract_nuance(
        self,
        conj_candidates: list[CandidateObject],
        seen_nuance: set[str],
    ) -> list[CandidateObject]:
        """Emit nuance observations derived from conjugation results.

        Four nuance types:

          imperfect_aspect  — tense == "imperfect"
            The imparfait signals ongoing, habitual, or background past action.
            Confidence 0.78.

          subjunctive_mood  — mood == "subjunctive"
            The subjonctif signals doubt, desire, emotion, or subordinate
            hypotheticals.  Confidence 0.72.

          conditional_mood  — mood == "conditional"
            The conditionnel signals hypothesis, polite requests, or reported
            speech.  Confidence 0.78.

          reflexive_verb    — is_reflexive == True
            Verbes pronominaux use a reflexive pronoun that changes the meaning
            or signals reciprocal action.  Confidence 0.82.
        """
        candidates: list[CandidateObject] = []

        for conj in conj_candidates:
            tense        = conj.lesson_data.get("tense")
            mood         = conj.lesson_data.get("mood")
            is_reflexive = conj.lesson_data.get("is_reflexive", False)
            lemma        = conj.lesson_data.get("lemma", "")
            surface      = conj.lesson_data.get("surface", conj.label)

            # ── Imperfect aspect ──────────────────────────────────────────────
            if tense == "imperfect":
                cf = f"nuance:imperfect_aspect:{lemma}"
                if cf not in seen_nuance:
                    seen_nuance.add(cf)
                    candidates.append(CandidateObject(
                        canonical_form=cf,
                        surface_form=surface,
                        type="nuance",
                        label=surface,
                        lesson_data={
                            "nuance_type":    "imperfect_aspect",
                            "lemma":          lemma,
                            "surface":        surface,
                            "note": (
                                "The imparfait describes an ongoing, habitual, or "
                                "background action in the past. Contrast with the "
                                "passé composé, which marks a completed event."
                            ),
                            "contrast_tense": "passé composé",
                        },
                        confidence=0.78,
                        relation_hints=[
                            RelationHint(
                                relation_type="nuance_of",
                                target_canonical_form=conj.canonical_form,
                                target_type="conjugation",
                            )
                        ],
                    ))

            # ── Subjunctive mood ──────────────────────────────────────────────
            if mood == "subjunctive":
                cf = f"nuance:subjunctive_mood:{lemma}"
                if cf not in seen_nuance:
                    seen_nuance.add(cf)
                    candidates.append(CandidateObject(
                        canonical_form=cf,
                        surface_form=surface,
                        type="nuance",
                        label=surface,
                        lesson_data={
                            "nuance_type": "subjunctive_mood",
                            "lemma":       lemma,
                            "surface":     surface,
                            "note": (
                                "The subjonctif expresses doubt, desire, emotion, "
                                "or hypothetical situations. It typically appears after "
                                "verbs of wanting, fearing, or doubting, and after "
                                "subordinating conjunctions such as 'pour que', "
                                "'bien que', and 'avant que'."
                            ),
                        },
                        confidence=0.72,
                        relation_hints=[
                            RelationHint(
                                relation_type="nuance_of",
                                target_canonical_form=conj.canonical_form,
                                target_type="conjugation",
                            )
                        ],
                    ))

            # ── Conditional mood ──────────────────────────────────────────────
            if mood == "conditional":
                cf = f"nuance:conditional_mood:{lemma}"
                if cf not in seen_nuance:
                    seen_nuance.add(cf)
                    candidates.append(CandidateObject(
                        canonical_form=cf,
                        surface_form=surface,
                        type="nuance",
                        label=surface,
                        lesson_data={
                            "nuance_type": "conditional_mood",
                            "lemma":       lemma,
                            "surface":     surface,
                            "note": (
                                "The conditionnel is used for hypothetical situations "
                                "('si j'avais le temps, je lirais'), polite requests "
                                "('je voudrais un café'), and reported speech "
                                "('il a dit qu'il viendrait')."
                            ),
                        },
                        confidence=0.78,
                        relation_hints=[
                            RelationHint(
                                relation_type="nuance_of",
                                target_canonical_form=conj.canonical_form,
                                target_type="conjugation",
                            )
                        ],
                    ))

            # ── Reflexive / pronominal verb ───────────────────────────────────
            if is_reflexive:
                cf = f"nuance:reflexive_verb:{lemma}"
                if cf not in seen_nuance:
                    seen_nuance.add(cf)
                    candidates.append(CandidateObject(
                        canonical_form=cf,
                        surface_form=surface,
                        type="nuance",
                        label=surface,
                        lesson_data={
                            "nuance_type": "reflexive_verb",
                            "lemma":       lemma,
                            "surface":     surface,
                            "note": (
                                "This verb uses a reflexive pronoun "
                                "(me / te / se / nous / vous). The pronoun signals "
                                "a reflexive action (the subject acts on itself), "
                                "a reciprocal action (two subjects act on each other), "
                                "or is intrinsic to the meaning of the verb "
                                "(verbe essentiellement pronominal, e.g. se souvenir)."
                            ),
                        },
                        confidence=0.82,
                        relation_hints=[
                            RelationHint(
                                relation_type="nuance_of",
                                target_canonical_form=conj.canonical_form,
                                target_type="conjugation",
                            )
                        ],
                    ))

        return candidates


# ── Module-level helpers (stateless) ─────────────────────────────────────────

def _detect_construction(tok: Any) -> str:
    """Annotate the periphrastic construction for a conjugated verb token.

    Returns one of:
        "standalone"   — simple finite verb, not part of a known periphrasis
        "copula"       — être as a copula  (je suis médecin)
        "perfect"      — avoir/être + past participle  (j'ai mangé / il est parti)
        "near_future"  — aller + infinitive  (je vais étudier)
        "progressive"  — être en train de + infinitive  (rare with this model)
        "modal"        — modal AUX + infinitive  (je dois partir)

    Handles both the canonical AUX case and a fr_core_news_sm quirk where
    "aller" in the near-future construction is tagged as VERB ROOT (not AUX)
    with the dependent infinitive attached via dep_=xcomp.
    """
    if tok.pos_ == "AUX":
        if tok.dep_ == "cop":
            return "copula"
        if tok.dep_ in {"aux", "aux:pass"}:
            head_vf = _morph_first(tok.head, "VerbForm")
            if head_vf == "Part":
                return "perfect"
            if head_vf == "Inf":
                lemma = tok.lemma_.lower()
                return "near_future" if lemma == "aller" else "modal"
            if head_vf == "Ger":
                return "progressive"
    elif tok.pos_ == "VERB" and tok.lemma_.lower() == "aller":
        # fr_core_news_sm tags "aller" as VERB ROOT in "je vais + infinitive".
        # Detect near_future by looking for an xcomp infinitive child.
        for child in tok.children:
            if (
                child.pos_ in {"VERB", "AUX"}
                and child.dep_ == "xcomp"
                and _morph_first(child, "VerbForm") == "Inf"
            ):
                return "near_future"
    return "standalone"


def _morph_first(tok: Any, feature: str) -> str | None:
    """Return the first value for a morph feature, or None if absent."""
    values = tok.morph.get(feature)
    return values[0] if values else None


def _paradigm_class(lemma: str) -> str:
    """Return the conjugation group of a French verb lemma.

    French has three conjugation groups:
      -er   (1st group — most regular, largest class)
      -ir   (2nd group when present participle ends in -issant, e.g. finir;
             and 3rd-group -ir verbs — e.g. partir, venir)
      -re   (3rd group, e.g. prendre, vendre)
      irregular

    Since distinguishing 2nd-group from 3rd-group -ir verbs requires a
    paradigm lookup, this function uses the simpler three-way split:
    -er / -ir / -re / irregular.  Known irregular verbs always return
    "irregular" regardless of their infinitive ending.
    """
    if lemma in _IRREGULAR_VERBS:
        return "irregular"
    if lemma.endswith("er"):
        return "-er"
    if lemma.endswith("ir"):
        return "-ir"
    if lemma.endswith("re"):
        return "-re"
    return "irregular"


def _conj_canonical_form(lemma: str, feats: dict[str, str]) -> str:
    """Stable conjugation canonical_form: lemma + four morphological axes."""
    return (
        f"{lemma}"
        f":{feats.get('tense', 'unk')}"
        f":{feats.get('mood', 'unk')}"
        f":{feats.get('person', 'unk')}"
        f":{feats.get('number', 'unk')}"
    )


def _conj_is_complete(feats: dict[str, str]) -> bool:
    return all(
        feats.get(k) not in (None, "unknown")
        for k in ("tense", "mood", "person")
    )


def _conj_confidence_note(feats: dict[str, str], is_oov: bool) -> str | None:
    unknown = [
        k for k in ("tense", "mood", "person")
        if feats.get(k) in (None, "unknown")
    ]
    parts: list[str] = []
    if unknown:
        parts.append(f"morphology unavailable for: {', '.join(unknown)}")
    if is_oov:
        parts.append("word not found in model vocabulary")
    return "; ".join(parts) if parts else None


def _has_reflexive_clitic(tok: Any, tokens: list[Any]) -> bool:
    """True when *tok* has a reflexive pronoun as a syntactic child.

    Uses the model-agnostic ``Reflex=Yes`` morphological feature rather than
    a hardcoded surface-form list (cf. Spanish plugin which uses a frozenset
    of clitic surfaces).  This is more portable but depends on the model
    correctly assigning the Reflex feature.

    Subject pronouns (dep nsubj/nsubj:pass) are excluded.
    """
    return any(
        t.pos_ == "PRON"
        and t.head.i == tok.i
        and _morph_first(t, "Reflex") == "Yes"
        and t.dep_ not in {"nsubj", "nsubj:pass"}
        for t in tokens
    )


def _find_modifiers(noun: Any, tokens: list[Any]) -> list[Any]:
    """Return DET and ADJ tokens that modify *noun*.

    Primary: spaCy dependency arcs.  Fallback: immediate adjacency, skipping
    CCONJ-separated pairs.  Coordinated modifiers (dep_=conj or flat) are
    excluded.

    French-specific: ADJ may appear before or after the noun.  The dep-arc
    approach handles both positions correctly.  The adjacency fallback also
    handles both (abs(t.i - noun.i) == 1 catches pre- and post-nominal ADJ).
    """
    dep_based: list[Any] = [
        t for t in tokens
        if t.pos_ in {"DET", "ADJ"}
        and t.head.i == noun.i
        and t.i != noun.i
        and t.dep_ not in {"conj", "flat"}
    ]
    if dep_based:
        return dep_based

    adjacent: list[Any] = []
    for t in tokens:
        if t.pos_ not in {"DET", "ADJ"} or t.i == noun.i:
            continue
        if abs(t.i - noun.i) != 1:
            continue
        lo, hi = min(t.i, noun.i), max(t.i, noun.i)
        if any(
            tokens[k].is_sent_start or tokens[k].pos_ == "CCONJ"
            for k in range(lo + 1, hi)
        ):
            continue
        adjacent.append(t)
    return adjacent


def _agreement_confidence(
    gender_match: bool | None,
    number_match: bool | None,
) -> float:
    if gender_match is True and number_match is True:
        return 0.85
    if gender_match is True or number_match is True:
        return 0.72
    return 0.55


def _agreement_confidence_note(
    gender_match: bool | None,
    number_match: bool | None,
) -> str:
    if gender_match is True and number_match is True:
        return "gender and number both confirmed"
    if gender_match is True:
        return "gender confirmed; number unavailable"
    if number_match is True:
        return "number confirmed; gender unavailable"
    return "agreement inferred from adjacency — morphology incomplete"


def create_plugin() -> FrenchPlugin:
    return FrenchPlugin()
