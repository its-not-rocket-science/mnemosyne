"""Spanish language plugin — spaCy ``es_core_news_sm``.

Registers as ``language_code = "es"``.

This module is the **reference implementation** for full-parse living-language
plugins.  Read it alongside ``PLUGIN_AUTHOR_GUIDE.md`` when building a plugin
for a new language.  The sections below document every design decision that is
not immediately obvious from the code.

─────────────────────────────────────────────────────────────────────────────
WHAT THE PLUGIN EXTRACTS
─────────────────────────────────────────────────────────────────────────────

**Vocabulary** — open-class content words (NOUN, ADJ, ADV, non-finite
VERB/AUX).  Finite verbs are *excluded* here; they are already represented
as conjugation objects.  Cross-tracking (``seen_vocab``) prevents the same
lemma from appearing twice in the same sentence.

  lesson_data keys: lemma, pos, gender*, number*, verb_form*, confidence_note*
  (* = only when available)

**Conjugation** — finite VERB and AUX tokens, annotated with:
  • morphological features: tense, mood, person, number
  • construction: standalone / progressive / perfect / passive /
                  near_future / modal / copula
  • is_reflexive: True when a reflexive clitic is a dependent of this verb
  • morph_complete: True when tense + mood + person are all resolved
  • paradigm_class: -ar / -er / -ir / irregular
  • is_irregular: True for known irregular verb stems
  • confidence_note: human-readable rationale for any score penalty

**Agreement** — DET+NOUN and ADJ+NOUN pairs with at least one positively
confirmed morphological match (gender or number).  Confirmed mismatches are
silently dropped (they indicate model errors).

  lesson_data keys: modifier, modifier_pos, noun, gender, number,
                    gender_match, number_match, confidence_note

**Idiom** — invariant multi-word expressions detected by token-sequence
surface matching against a curated table of ~35 common Spanish idioms.
Only fixed-form expressions (no conjugable verb) are in the table; this
prevents false positives caused by morphological variation.

  lesson_data keys: phrase, meaning, register

**Grammar** — periphrastic construction objects derived from conjugation
results.  One object per distinct construction type per sentence.  Covers:
  ser_copula, estar_copula, estar_progressive, ir_near_future,
  haber_perfect, ser_passive.

  lesson_data keys: pattern_id, pattern, usage, contrast, verb_lemma,
                    surface_verb

**Nuance** — aspect and mood observations derived from conjugation results.
Emitted when morphology is reliably resolved.  Covers:
  imperfect_aspect (one per imperfect verb lemma, per sentence),
  subjunctive_mood (one per subjunctive verb lemma, per sentence),
  reflexive_verb   (one per reflexive lemma, per sentence).

  lesson_data keys: nuance_type, lemma, surface, note, contrast_tense*

─────────────────────────────────────────────────────────────────────────────
CONFIDENCE SCORES
─────────────────────────────────────────────────────────────────────────────

Scores are heuristic proxies, not calibrated probabilities.  They reflect
how much the plugin trusts its own output for this specific object.

  0.90  idiom — direct string match against curated table
  0.85  vocabulary (in-vocabulary word), full-match agreement, grammar
  0.82  reflexive nuance — dep parse required but reliable
  0.80  conjugation with complete morphology, in-vocabulary word
  0.78  imperfect nuance — tense detection is reliable for regular forms
  0.72  agreement with one confirmed feature; subjunctive nuance
  0.60  PROPN vocabulary — may not generalise
  0.50  OOV vocabulary — surface form may be incorrect

A ``confidence_note`` key in ``lesson_data`` provides a human-readable
rationale whenever the score is below the nominal maximum for that type.

─────────────────────────────────────────────────────────────────────────────
RELATION HINTS
─────────────────────────────────────────────────────────────────────────────

Each conjugation carries a ``conjugation_of`` hint pointing to its
vocabulary lemma.  Each agreement object carries an ``agreement_of`` hint
pointing to the head noun.  Grammar and nuance objects carry ``instance_of``
and ``nuance_of`` hints pointing back to the triggering conjugation.  The
parse route resolves both ends to UUIDs and records them in the relation
table; hints for objects not present in the same parse are silently skipped.

─────────────────────────────────────────────────────────────────────────────
CANONICAL FORMS (deterministic ID scheme)
─────────────────────────────────────────────────────────────────────────────

  vocabulary:   lemma string           e.g. "casa"
  conjugation:  lemma:tense:mood:person:number
                                       e.g. "hablar:present:indicative:1:Sing"
  agreement:    pos:modifier_lemma_noun_lemma
                                       e.g. "det:el_casa"
  idiom:        phrase string          e.g. "sin embargo"
  grammar:      "grammar:{pattern_id}" e.g. "grammar:ser_copula"
  nuance:       "nuance:{type}:{lemma}" e.g. "nuance:imperfect_aspect:hablar"

─────────────────────────────────────────────────────────────────────────────
KNOWN LIMITATIONS
─────────────────────────────────────────────────────────────────────────────

- ``es_core_news_sm`` is a small model (~12 MB).  Morphology is often
  incomplete for irregular verbs, clitic clusters, and archaic forms.
  Nearly every surface token is marked OOV by this model.
- Verb-initial sentences are sometimes mis-tagged as PROPN; silently
  under-extracted rather than re-tagged.
- Present-subjunctive forms homographic with indicative (e.g. "hable")
  receive reduced confidence (0.72) to reflect this ambiguity.
- Reflexive detection relies on the dependency parse; parse errors produce
  missed or spurious results.
- Idiom detection is surface-form only; inflected verb idioms like
  "tener en cuenta" are not matched.  See _IDIOM_TABLE for the curated list.
"""
from __future__ import annotations

import logging
from functools import cached_property
from typing import Any

from backend.plugins.cefr_vocab import A1 as _CEFR_A1
from backend.core.vocab_index import get_cefr_level as _get_cefr_level
from backend.schemas.language import LanguageCapabilities, NuanceCapabilities
from backend.schemas.parse import (
    CandidateObject,
    CandidateSentenceResult,
    RelationHint,
)

_A1 = _CEFR_A1.get("es", frozenset())

logger = logging.getLogger(__name__)

# ── POS filter ────────────────────────────────────────────────────────────────

# Universal-Dependencies POS tags excluded from vocabulary extraction.
# PRON is excluded: reflexive/clitic pronouns ("me", "se") lemmatise to
# misleading forms and represent a closed class better taught through the
# verb construction they modify.
_SKIP_POS = frozenset(
    {"DET", "ADP", "CCONJ", "SCONJ", "CONJ", "PUNCT", "SPACE",
     "X", "SYM", "NUM", "PRON"}
)

# VerbForm values that classify a VERB/AUX token as non-finite.
_NON_FINITE_FORMS = frozenset({"Inf", "Part", "Ger"})

# Spanish reflexive/clitic pronoun surface forms.
_REFLEXIVE_CLITICS = frozenset({"me", "te", "se", "nos", "os"})

# ── Display maps ──────────────────────────────────────────────────────────────

_TENSE_DISPLAY: dict[str, str] = {
    "Pres": "present",
    "Past": "preterite",
    "Imp":  "imperfect",
    "Fut":  "future",
    "Cnd":  "conditional",
}

_MOOD_DISPLAY: dict[str, str] = {
    "Ind": "indicative",
    "Sub": "subjunctive",
    "Imp": "imperative",
}

# ── Irregular verbs ───────────────────────────────────────────────────────────
# Common verbs whose paradigm cannot be predicted from the infinitive ending
# alone.  Used by _paradigm_class() to label conjugations "irregular".

_IRREGULAR_VERBS: frozenset[str] = frozenset({
    "ser", "estar", "ir", "haber", "tener", "hacer", "poder", "querer",
    "saber", "venir", "decir", "ver", "dar", "poner", "traer", "caer",
    "oir", "oír", "salir", "valer", "caber", "andar", "conducir", "reír",
})

# ── Idiom table ───────────────────────────────────────────────────────────────
# Invariant multi-word expressions — no conjugable verb in the phrase.
# Format: (word_tuple, english_meaning, register)
# Sorted longest-first so longer matches take priority over sub-phrases.
# Register: "neutral" | "formal" | "informal"

_IDIOM_TABLE: tuple[tuple[tuple[str, ...], str, str], ...] = (
    # ── 4-word phrases ────────────────────────────────────────────────────────
    (("de", "vez", "en", "cuando"),   "from time to time",          "neutral"),
    (("al", "mismo", "tiempo"),       "at the same time",           "neutral"),
    (("cada", "vez", "más"),          "more and more",              "neutral"),
    # ── 3-word phrases ────────────────────────────────────────────────────────
    (("a", "pesar", "de"),            "in spite of",                "neutral"),
    (("en", "vez", "de"),             "instead of",                 "neutral"),
    (("a", "partir", "de"),           "starting from / from",       "neutral"),
    (("a", "causa", "de"),            "because of",                 "neutral"),
    (("en", "cuanto", "a"),           "as for / regarding",         "formal"),
    (("por", "lo", "tanto"),          "therefore",                  "formal"),
    (("por", "lo", "menos"),          "at least",                   "neutral"),
    (("en", "todo", "caso"),          "in any case",                "neutral"),
    (("a", "lo", "mejor"),            "maybe / perhaps",            "neutral"),
    (("más", "o", "menos"),           "more or less",               "neutral"),
    # ── 2-word phrases ────────────────────────────────────────────────────────
    (("sin", "embargo"),              "however",                    "neutral"),
    (("no", "obstante"),              "nevertheless",               "formal"),
    (("en", "cambio"),                "on the other hand",          "neutral"),
    (("así", "que"),                  "so / and so",                "neutral"),
    (("de", "hecho"),                 "in fact",                    "neutral"),
    (("en", "realidad"),              "in fact / actually",         "neutral"),
    (("en", "efecto"),                "indeed / in effect",         "formal"),
    (("por", "supuesto"),             "of course",                  "neutral"),
    (("desde", "luego"),              "of course / certainly",      "neutral"),
    (("por", "cierto"),               "by the way",                 "neutral"),
    (("de", "acuerdo"),               "agreed / OK",                "informal"),
    (("sin", "duda"),                 "without doubt",              "neutral"),
    (("por", "ejemplo"),              "for example",                "neutral"),
    (("a", "veces"),                  "sometimes",                  "neutral"),
    (("a", "menudo"),                 "often",                      "neutral"),
    (("de", "repente"),               "suddenly",                   "neutral"),
    (("por", "fin"),                  "finally",                    "neutral"),
    (("al", "final"),                 "in the end",                 "neutral"),
    (("en", "seguida"),               "right away / immediately",   "neutral"),
    (("al", "menos"),                 "at least",                   "neutral"),
    (("en", "absoluto"),              "not at all / absolutely not","neutral"),
    (("o", "sea"),                    "that is / I mean",           "informal"),
    (("de", "nuevo"),                 "again / anew",               "neutral"),
    (("a", "tiempo"),                 "on time",                    "neutral"),
)

# ── Grammar patterns ──────────────────────────────────────────────────────────
# Each entry: (construction, required_lemma_or_None, pattern_id,
#              pattern_label, usage_text, contrast_text)
# Derived from conjugation construction + lemma fields.

_GRAMMAR_PATTERNS: tuple[
    tuple[str, str | None, str, str, str, str], ...
] = (
    (
        "copula", "ser",
        "ser_copula",
        "ser + [adjective / noun]",
        "Expresses permanent or defining characteristics: identity, "
        "origin, occupation, nationality, or material.",
        "Use estar for temporary states, conditions, emotions, or location.",
    ),
    (
        "copula", "estar",
        "estar_copula",
        "estar + [adjective]",
        "Expresses temporary states, conditions, emotions, or location.",
        "Use ser for permanent or defining characteristics.",
    ),
    (
        "progressive", None,
        "estar_progressive",
        "estar + [gerund]",
        "Expresses an action in progress at the moment of speaking "
        "(e.g. estoy comiendo — I am eating).",
        "The simple present can also express ongoing actions without "
        "emphasising the immediacy.",
    ),
    (
        "near_future", "ir",
        "ir_near_future",
        "ir a + [infinitive]",
        "Expresses a planned or near-future action "
        "(e.g. voy a estudiar — I am going to study).",
        "The future tense (estudiaré) is more formal and less immediate.",
    ),
    (
        "perfect", "haber",
        "haber_perfect",
        "haber + [past participle]",
        "Expresses a past action with relevance to the present "
        "(e.g. he comido — I have eaten).",
        "The preterite (comí) marks a completed event with no implied "
        "present relevance.",
    ),
    (
        "passive", None,
        "ser_passive",
        "ser + [past participle] (passive voice)",
        "Expresses a passive action where the subject receives the action "
        "(e.g. fue escrito — it was written).",
        "Spanish often prefers the se-passive (se vendió el libro) over "
        "ser-passive in everyday speech.",
    ),
)


# ── Plugin ────────────────────────────────────────────────────────────────────

class SpanishPlugin:
    language_code = "es"
    display_name  = "Spanish"
    direction     = "ltr"
    capabilities  = LanguageCapabilities(
        code="es",
        display_name="Spanish",
        direction="ltr",
        script_family="latin",
        tokenization_mode="whitespace",
        morphology_depth="rich",
        lesson_modes_supported=["morphology", "vocabulary"],
        # v2 fields
        analysis_depth="full",
        segmentation_quality="medium",   # es_core_news_sm sentence splits are decent
        tokenization_quality="high",     # word tokenisation is reliable for Spanish
        morphology_quality="medium",     # small model; many OOV tokens
        syntax_support=True,             # dep parse used for reflexive / modifier detection
        idiom_detection=True,            # invariant fixed-expression table
        tts_lang_tag="es",
        transliteration_scheme=None,
        tense_pool=["present", "preterite", "imperfect", "future", "conditional"],
        mood_pool=["indicative", "subjunctive", "imperative"],
        nuance_capabilities=NuanceCapabilities(
            idioms="partial",            # curated ~35-entry fixed-expression table
            phrase_families="partial",   # 10 families with variants and pedagogical notes
            literary_references="none",
            cultural_references="none",
            etymology="partial",         # 10 curated entries covering high-frequency learner vocabulary
            formality_register="stub",   # tú/usted distinction detectable
            grammar_nuance="partial",    # tense/mood/person/number drilling
            pronunciation_tts="partial", # browser TTS reliable for es
            transliteration="none",
            proverb_tradition="none",
            classical_or_scriptural_allusion="none",
        ),
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
            return spacy.load("es_core_news_sm", disable=["ner"])
        except ImportError as exc:
            raise RuntimeError(
                "spaCy is not installed.  Run: pip install spacy"
            ) from exc
        except OSError as exc:
            raise RuntimeError(
                "spaCy model 'es_core_news_sm' not found. "
                "Run: python -m spacy download es_core_news_sm"
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
        # seen_vocab is shared: conjugation pre-populates it with verb lemmas so
        # the same lemma is not also emitted as a vocabulary item.
        seen_vocab: set[str] = set()
        seen_conj:  set[str] = set()

        candidates: list[CandidateObject] = []

        # Conjugation runs first to populate seen_vocab before vocabulary
        # extraction consults it.
        conj_candidates = self._extract_conjugations(tokens, seen_conj, seen_vocab)
        candidates.extend(conj_candidates)
        candidates.extend(self._extract_vocabulary(tokens, seen_vocab))
        candidates.extend(self._extract_agreements(tokens))
        candidates.extend(self._extract_idioms(tokens))

        # Grammar and nuance objects are derived from the already-extracted
        # conjugation results — no second pass over raw tokens required.
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
            # their host verb, yielding multi-word lemmas like "hacer él".
            if " " in lemma:
                continue

            if len(lemma) < 2 or lemma in seen:
                continue
            seen.add(lemma)

            confidence, confidence_note = self._vocab_confidence(tok, lemma)
            data: dict[str, Any] = {"lemma": lemma, "pos": tok.pos_}
            cefr = _get_cefr_level("es", lemma) or ("A1" if lemma in _A1 else None)
            if cefr:
                data["cefr_level"] = cefr

            # Gender and number for noun entries help lesson generators frame
            # "el/la" article drills and agree-pattern explanations.
            if tok.pos_ == "NOUN":
                if noun_gender := _morph_first(tok, "Gender"):
                    data["gender"] = noun_gender
                if noun_number := _morph_first(tok, "Number"):
                    data["number"] = noun_number

            # Verb form type for non-finite verb vocabulary entries.
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
        if lemma in _A1:
            return 0.90, None  # known A1 word — suppress is_oov false-positive
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
                continue  # infinitives, participles, gerunds → vocabulary

            lemma = tok.lemma_.lower()
            if " " in lemma:
                continue  # enclitic fusion artefact

            feats = self._verb_morph(tok)
            canonical_form = _conj_canonical_form(lemma, feats)
            if canonical_form in seen_conj:
                continue
            seen_conj.add(canonical_form)
            seen_vocab.add(lemma)  # prevent the lemma from appearing in vocabulary

            construction    = _detect_construction(tok)
            is_reflexive    = _has_reflexive_clitic(tok, tokens)
            # Suppress OOV signal for known A1 lemmas — sm model has no vectors
            _oov            = tok.is_oov and lemma not in _A1
            confidence      = self._conj_confidence(tok, feats, _oov)
            confidence_note = _conj_confidence_note(feats, _oov)

            lesson: dict[str, Any] = {
                "lemma":          lemma,
                "surface":        tok.text,
                "tense":          feats["tense"],
                "mood":           feats["mood"],
                "person":         feats["person"],
                "number":         feats["number"],
                "morph_complete": _conj_is_complete(feats),
                "construction":   construction,
                "is_reflexive":   is_reflexive,
                # Conjugation-class and irregularity metadata for lesson
                # generators.  "-ar"/"-er"/"-ir" enables paradigm-table drills;
                # is_irregular signals that surface forms cannot be predicted
                # by rule from the infinitive alone.
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
            "tense":  (
                _TENSE_DISPLAY.get(tense_raw or "", "")
                or _fallback_tense(tok)
                or "unknown"
            ),
            "mood":   _MOOD_DISPLAY.get(mood_raw or "", mood_raw or "unknown"),
            "person": person or "unknown",
            "number": number or "unknown",
        }
        if verb_form:
            feats["verb_form"] = verb_form
        return feats

    def _conj_confidence(self, tok: Any, feats: dict[str, str], is_oov: bool | None = None) -> float:
        known = sum(
            1 for k in ("tense", "mood", "person")
            if feats.get(k) not in (None, "unknown")
        )
        base = 0.55 + known * 0.10
        if (tok.is_oov if is_oov is None else is_oov):
            base -= 0.10
        return round(min(base, 0.85), 2)

    # ------------------------------------------------------------------
    # Agreement
    # ------------------------------------------------------------------

    def _extract_agreements(self, tokens: list[Any]) -> list[CandidateObject]:
        """Find DET+NOUN and ADJ+NOUN gender/number agreement pairs.

        Emission rules:
        - At least one morphological feature (gender or number) must be
          *positively confirmed* to match (value is True, not None).
        - A pair with a *confirmed mismatch* on any available feature is
          silently dropped; it indicates a model parse error rather than a
          valid grammatical pattern worth teaching.
        - Primary signal: spaCy dependency arcs (dep_ in {det, amod}).
        - Fallback: single-position adjacency, skipping pairs separated by a
          CCONJ (coordination) to avoid spurious pairs like "inglés y español".
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
        The table is sorted longest-first; once a span is claimed by a longer
        match, shorter overlapping phrases are skipped.

        Confidence is 0.90 for all idiom matches because the evidence is
        direct string equality on a curated fixed-form list — no morphological
        analysis is required, so the OOV penalty does not apply.

        Only fixed-form (non-conjugable) expressions are in the table.  Verb
        idioms like "tener en cuenta" require lemma-based matching and are not
        yet supported.
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
                # Skip spans claimed by a prior (longer) match.
                if any(start + k in used_positions for k in range(wlen)):
                    continue
                if lower_texts[start : start + wlen] == list(words):
                    phrase = " ".join(words)
                    if phrase in seen_idioms:
                        continue
                    seen_idioms.add(phrase)
                    used_positions.update(range(start, start + wlen))

                    # Preserve original casing from the text for the surface form.
                    surface = " ".join(t.text for t in tokens[start : start + wlen])

                    candidates.append(CandidateObject(
                        canonical_form=phrase,
                        surface_form=surface,
                        type="idiom",
                        label=surface,
                        lesson_data={
                            "phrase":    phrase,
                            "meaning":   meaning,
                            "register":  register,
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

        Each construction type (ser_copula, estar_progressive, etc.) is emitted
        at most once per sentence regardless of how many conjugated verbs
        exhibit that construction.

        Grammar objects complement conjugation objects: the conjugation tells
        the learner *which* form was used; the grammar object explains *why*
        the construction exists and what the contrast is.

        Confidence is 0.85 for all grammar objects: construction detection is
        based on spaCy dependency arcs and is reliable for common sentences,
        but parse errors may produce spurious or missed objects.
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
                        "pattern_id":  pattern_id,
                        "pattern":     pattern,
                        "usage":       usage,
                        "contrast":    contrast,
                        "verb_lemma":  lemma,
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

        Three nuance types are currently supported:

          imperfect_aspect  — tense == "imperfect"
            Signals the ongoing/habitual vs. preterite/completed distinction.
            Confidence 0.78: suffix heuristics are reliable for -aba/-ía
            endings; irregular imperfects may be mis-classified as "unknown".

          subjunctive_mood  — mood == "subjunctive"
            Confidence 0.72: present-subjunctive forms that are homographic
            with indicative (e.g. "hable") may be mis-classified.

          reflexive_verb    — is_reflexive == True
            Confidence 0.82: dep-parse based; reliable for common sentences.

        One nuance object is emitted per (nuance_type, verb_lemma) pair per
        sentence.  The canonical_form encodes both so the UUID is stable.
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
                                "The imperfect tense describes an ongoing, habitual, "
                                "or background action in the past. Contrast with the "
                                "preterite, which marks a single completed event."
                            ),
                            "contrast_tense": "preterite",
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
                                "The subjunctive mood expresses doubt, desire, "
                                "emotion, or hypothetical situations. It typically "
                                "appears after verbs of wanting or fearing, or after "
                                "subordinating conjunctions such as 'para que', "
                                "'aunque', and 'cuando' (future reference)."
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
                                "(me / te / se / nos / os). The pronoun signals "
                                "that the action affects the subject (true reflexive) "
                                "or is intrinsic to the meaning of this verb form "
                                "(pronominal verb, e.g. llamarse, levantarse)."
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

def _morph_first(tok: Any, feature: str) -> str | None:
    """Return the first value for a morph feature, or None if absent."""
    values = tok.morph.get(feature)
    return values[0] if values else None


def _paradigm_class(lemma: str) -> str:
    """Return the conjugation class of a Spanish verb lemma.

    Returns "-ar", "-er", "-ir", or "irregular".  Known irregular verbs
    (see ``_IRREGULAR_VERBS``) always return "irregular" regardless of their
    infinitive ending.  Unknown forms that do not end in a regular infinitive
    suffix also return "irregular" as a conservative fallback.
    """
    if lemma in _IRREGULAR_VERBS:
        return "irregular"
    if lemma.endswith("ar"):
        return "-ar"
    if lemma.endswith("er"):
        return "-er"
    if lemma.endswith("ir"):
        return "-ir"
    return "irregular"


def _conj_canonical_form(lemma: str, feats: dict[str, str]) -> str:
    """Stable conjugation canonical_form: lemma + the four morphological axes."""
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
    """Human-readable rationale for conjugation confidence.  None when nominal."""
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


def _detect_construction(tok: Any) -> str:
    """Annotate the periphrastic construction for a conjugated verb token.

    Returns one of:
        "standalone"   — simple finite verb, not part of a periphrasis
        "progressive"  — estar + gerund  (estoy comiendo)
        "perfect"      — haber + participle  (he comido)
        "passive"      — ser/estar + participle  (fue escrito)
        "near_future"  — ir a + infinitive  (voy a estudiar)
        "modal"        — modal AUX + infinitive  (debo estudiar)
        "copula"       — ser/estar as copula  (soy médico)
    """
    if tok.pos_ != "AUX":
        return "standalone"
    if tok.dep_ == "cop":
        return "copula"
    if tok.dep_ == "ROOT":
        return "standalone"
    if tok.dep_ == "aux":
        head_vf = _morph_first(tok.head, "VerbForm")
        if head_vf == "Ger":
            return "progressive"
        if head_vf == "Part":
            return "perfect" if tok.lemma_.lower() == "haber" else "passive"
        if head_vf == "Inf":
            return "near_future" if tok.lemma_.lower() == "ir" else "modal"
    return "standalone"


def _has_reflexive_clitic(tok: Any, tokens: list[Any]) -> bool:
    """True when *tok* has a reflexive or pronominal clitic as a dependent.

    Covers proclitic pronouns ("me levanto", "se llama") via dependency
    arcs where the PRON's head is the verb.  Subject pronouns (nsubj) are
    excluded because "yo" is not a clitic.
    """
    return any(
        t.pos_ == "PRON"
        and t.head.i == tok.i
        and t.text.lower() in _REFLEXIVE_CLITICS
        and t.dep_ not in {"nsubj", "nsubj:pass"}
        for t in tokens
    )


def _fallback_tense(tok: Any) -> str | None:
    """Heuristic tense from suffix when the model's morphology is empty."""
    w = tok.text.lower()
    if w.endswith(("aba", "abas", "\u00e1bamos", "aban")):
        return "imperfect"
    if w.endswith(("\u00eda", "\u00edas", "\u00edamos", "\u00edan")):
        return "imperfect"
    if w.endswith(("r\u00e9", "r\u00e1s", "r\u00e1", "remos", "r\u00e9is", "r\u00e1n")):
        return "future"
    if w.endswith(("r\u00eda", "r\u00edas", "r\u00edamos", "r\u00edan")):
        return "conditional"
    return None


def _find_modifiers(noun: Any, tokens: list[Any]) -> list[Any]:
    """Return DET and ADJ tokens that modify *noun*.

    Primary: spaCy dependency arcs.  Fallback: immediate adjacency, skipping
    CCONJ-separated pairs.  Coordinated modifiers (dep_=conj or flat) are
    excluded to prevent spurious agreement pairs like "inglés y español".
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


def create_plugin() -> SpanishPlugin:
    return SpanishPlugin()
