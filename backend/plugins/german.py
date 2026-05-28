"""German language plugin — spaCy ``de_core_news_sm``.

Registers as ``language_code = "de"``.

Read this alongside ``PLUGIN_AUTHOR_GUIDE.md`` and the Spanish and French
reference implementations when building or extending this plugin.

─────────────────────────────────────────────────────────────────────────────
WHAT THIS PLUGIN EXTRACTS
─────────────────────────────────────────────────────────────────────────────

**Vocabulary** — open-class content words (NOUN, ADJ, ADV, non-finite
VERB/AUX).  Finite verbs are excluded here; they appear as conjugation
objects.

  NOUN lemmas preserve German capitalisation (e.g. "Haus", "Mann") because
  that is how German dictionaries list headwords.

  lesson_data keys: lemma, pos, gender*, number*, case*, degree*,
                    verb_form*, confidence_note*
  (* = only when available)

**Conjugation** — finite VERB and AUX tokens (VerbForm=Fin), annotated with:
  • morphological features: tense, mood, person, number
  • is_reflexive: True when a child PRON carries Reflex=Yes
  • morph_complete: True when tense + mood + person are all resolved
  • paradigm_class: weak / strong / modal
  • is_irregular: True for known strong/irregular verb lemmas
  • is_separable: True when a ``dep=svp`` particle child is detected
  • particle: the surface form of the separable prefix (when is_separable)

  Separable verbs: spaCy's de_core_news_sm gives the bare-stem lemma for the
  host verb (e.g. ``fangen`` for ``anfangen``).  When a ``svp`` particle is
  found, the canonical_form is reconstructed as ``{particle}{lemma}``
  (e.g. ``anfangen``), matching the expected dictionary form.

  lesson_data keys: lemma, surface, tense, mood, person, number,
                    morph_complete, is_reflexive, paradigm_class, is_irregular,
                    is_separable, particle*, verb_class*, confidence_note*

**Case agreement** (type = ``case_agreement``) — DET+NOUN and ADJ+NOUN
clusters where case, gender, and number are all resolvable.  Emitted only
when case is available on both modifier and noun (or can be inferred from
the noun's morph features).

  German introduces a third gender (neuter) and case (Nom/Acc/Dat/Gen)
  not present in Romance-language agreement objects.  A new object type
  ``case_agreement`` is used so the lesson builder can present all three
  agreement dimensions without overloading the existing ``agreement`` type.

  Confirmed mismatches (False) are silently dropped.

  lesson_data keys: modifier, modifier_pos, noun, case, gender, number,
                    case_match, gender_match, number_match, confidence_note

─────────────────────────────────────────────────────────────────────────────
NOT YET IMPLEMENTED (future iterations)
─────────────────────────────────────────────────────────────────────────────

Grammar patterns (modal + infinitive, werden + infinitive future, sein/haben
+ past participle perfect, Konjunktiv II) are deferred.

Idiom detection is deferred pending curation of a German-specific idiom table.

─────────────────────────────────────────────────────────────────────────────
KNOWN MODEL LIMITATIONS (de_core_news_sm)
─────────────────────────────────────────────────────────────────────────────

- ``tok.is_oov`` is **always True** for de_core_news_sm — it is not a useful
  confidence signal and is intentionally excluded from this plugin's
  confidence heuristics.
- Separable verb particle detection is limited to the current sentence.
  Verb-final word order in subordinate clauses or long-distance particle
  separation may cause the svp arc to be missed; the bare lemma is then
  emitted instead of the full lemma.
- The small model underperforms on morphologically ambiguous forms (e.g.
  nominative/accusative neuter, genitive/dative feminine).
- Participle forms (past participle of strong verbs) may be assigned
  incorrect lemmas by the model.
- ``de_core_news_sm`` does not assign ``Mood=Sub`` reliably; Konjunktiv I/II
  are largely undetected.

─────────────────────────────────────────────────────────────────────────────
MULTILINGUAL ARCHITECTURE FINDINGS
─────────────────────────────────────────────────────────────────────────────

This plugin surfaces several places where the core was implicitly
Romance-language-specific:

1. ``agreement`` type is insufficient for German: German agreement requires
   case (Nom/Acc/Dat/Gen) in addition to gender and number.  A new
   ``case_agreement`` type with a dedicated ``_build_case_agreement`` builder
   (in ``lesson/generators.py``) was introduced to carry all three dimensions.

2. Noun canonicalisation: German nouns are capitalised in the lemma (spaCy
   preserves German orthographic convention).  The canonical form for German
   vocabulary uses the capitalised lemma so that "Haus" and "haus" are not
   treated as the same word by the SRS scheduler.

3. Separable verb lemma reconstruction: spaCy de_core_news_sm returns the
   bare stem as the lemma for separable verbs (e.g. ``fangen`` for ``fängt
   an``).  The plugin reconstructs the full lemma by prepending the svp
   particle.  This pattern may recur for other Germanic languages (Dutch,
   Swedish, Norwegian).

4. Morphological confidence without is_oov: de_core_news_sm always sets
   is_oov=True.  A purely feature-count-based confidence heuristic is used
   instead, which is more portable across models than vocabulary-coverage
   signals.
"""
from __future__ import annotations

import logging
from functools import cached_property
from typing import Any

from backend.plugins.cefr_vocab import A1 as _CEFR_A1, A2 as _CEFR_A2, B1 as _CEFR_B1
from backend.core.vocab_index import get_cefr_level as _get_cefr_level
from backend.schemas.language import LanguageCapabilities, NuanceCapabilities
from backend.schemas.parse import (
    CandidateObject,
    CandidateSentenceResult,
    RelationHint,
)

logger = logging.getLogger(__name__)

_A1 = _CEFR_A1.get("de", frozenset())
_A2 = _CEFR_A2.get("de", frozenset())
_B1 = _CEFR_B1.get("de", frozenset())

# ── POS filter ────────────────────────────────────────────────────────────────

_SKIP_POS = frozenset({
    "DET", "ADP", "CCONJ", "SCONJ", "CONJ", "PUNCT", "SPACE",
    "X", "SYM", "NUM", "PRON", "INTJ", "PART",
})

# VerbForm values that classify a VERB/AUX token as non-finite.
_NON_FINITE_FORMS = frozenset({"Inf", "Part", "Ger"})

# ── Display maps ──────────────────────────────────────────────────────────────

_TENSE_DISPLAY: dict[str, str] = {
    "Pres": "present",
    "Past": "past",    # Präteritum (simple past)
}

_MOOD_DISPLAY: dict[str, str] = {
    "Ind": "indicative",
    "Sub": "subjunctive",
    "Imp": "imperative",
}

# ── Verb classification ───────────────────────────────────────────────────────

_MODAL_VERBS: frozenset[str] = frozenset({
    "müssen", "können", "dürfen", "sollen", "wollen", "mögen", "möchten",
    "lassen",
})

# Common strong (ablaut) verbs whose stems change in the past tense.
_STRONG_VERBS: frozenset[str] = frozenset({
    "sein", "haben", "werden", "gehen", "stehen", "kommen", "nehmen",
    "geben", "sehen", "fahren", "laufen", "lesen", "schreiben", "sprechen",
    "treffen", "finden", "rufen", "fallen", "halten", "lassen", "schlafen",
    "wissen", "bringen", "denken", "heißen", "bleiben", "tragen", "schlagen",
    "ziehen", "fliegen", "steigen", "bieten", "bitten", "liegen", "sitzen",
    "trinken", "fangen", "helfen", "sterben", "werfen", "verlieren",
    "anfangen", "aufstehen", "ausgehen", "einschlafen", "vorstellen",
    "anrufen", "einladen", "aufnehmen", "mitsprechen",
})


# ── Idiom table ───────────────────────────────────────────────────────────────
# Fixed-form (non-conjugable) multi-word expressions.
# Tuples: (lowercased_word_sequence, english_meaning, register)
# Sorted longest-first so longer matches are consumed before their substrings.

_IDIOM_TABLE: tuple[tuple[tuple[str, ...], str, str], ...] = (
    # ── 4-word phrases ────────────────────────────────────────────────────────
    (("so", "schnell", "wie", "möglich"),  "as quickly as possible",     "neutral"),
    (("auf", "der", "einen", "seite"),     "on the one hand",            "neutral"),
    # ── 3-word phrases ────────────────────────────────────────────────────────
    (("auf", "jeden", "fall"),             "in any case / definitely",   "neutral"),
    (("auf", "keinen", "fall"),            "under no circumstances",     "neutral"),
    (("in", "der", "tat"),                 "in fact / indeed",           "formal"),
    (("im", "großen", "ganzen"),           "on the whole / by and large","neutral"),
    (("unter", "anderem"),                 "among other things",         "neutral"),
    (("zum", "beispiel"),                  "for example",                "neutral"),
    (("im", "gegenteil"),                  "on the contrary",            "neutral"),
    (("auf", "einmal"),                    "all at once / suddenly",     "neutral"),
    (("im", "allgemeinen"),                "in general",                 "neutral"),
    (("in", "der", "regel"),               "as a rule / generally",      "neutral"),
    (("ab", "und", "zu"),                  "from time to time",          "neutral"),
    (("hin", "und", "wieder"),             "now and then",               "neutral"),
    # ── 2-word phrases ────────────────────────────────────────────────────────
    (("auf", "deutsch"),                   "in German",                  "neutral"),
    (("auf", "englisch"),                  "in English",                 "neutral"),
    (("zum", "glück"),                     "fortunately / luckily",      "neutral"),
    (("zum", "schluss"),                   "finally / in conclusion",    "neutral"),
    (("zum", "beispiel"),                  "for example",                "neutral"),
    (("im", "moment"),                     "at the moment",              "neutral"),
    (("im", "gegensatz"),                  "in contrast (to)",           "neutral"),
    (("auf", "wiedersehen"),               "goodbye (formal)",           "formal"),
    (("tschüss",),                         "bye (informal)",             "informal"),
    (("natürlich",),                       "of course / naturally",      "neutral"),
    (("übrigens",),                        "by the way",                 "neutral"),
    (("trotzdem",),                        "nevertheless / still",       "neutral"),
    (("außerdem",),                        "besides / moreover",         "neutral"),
    (("deswegen",),                        "because of that / therefore","neutral"),
    (("deshalb",),                         "therefore / that's why",     "neutral"),
    (("allerdings",),                      "however / admittedly",       "neutral"),
    (("nämlich",),                         "namely / you see",           "neutral"),
)


# ── Plugin ────────────────────────────────────────────────────────────────────

class GermanPlugin:
    language_code = "de"
    display_name  = "German"
    direction     = "ltr"
    capabilities  = LanguageCapabilities(
        code="de",
        display_name="German",
        direction="ltr",
        script_family="latin",
        tokenization_mode="whitespace",
        morphology_depth="rich",
        lesson_modes_supported=["morphology", "vocabulary"],
        # v2 fields
        analysis_depth="full",
        segmentation_quality="medium",
        tokenization_quality="high",
        morphology_quality="medium",   # small model; case inference is imperfect
        syntax_support=True,
        idiom_detection=True,    # curated fixed-expression table (~35 entries)
        tts_lang_tag="de",
        transliteration_scheme=None,
        # German: only present/past (Präteritum) in simple tenses; perfect and
        # pluperfect are compound.  "preterite" and "conditional" are not
        # German terms — exclude them from wrong-answer options.
        tense_pool=["present", "past", "perfect", "pluperfect", "future"],
        mood_pool=["indicative", "subjunctive", "imperative"],
        nuance_capabilities=NuanceCapabilities(
            idioms="partial",            # curated ~35-entry fixed-expression table
            phrase_families="partial",   # 10 families with variants and pedagogical notes
            literary_references="none",
            cultural_references="none",
            etymology="strong",          # 100-entry curated catalog; core vocabulary + loanwords covered
            formality_register="stub",   # formal/informal verb forms detectable
            grammar_nuance="partial",    # case detection via dep-parse + drilling
            pronunciation_tts="partial", # browser TTS reliable for de
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
            return spacy.load("de_core_news_sm", disable=["ner"])
        except ImportError as exc:
            raise RuntimeError(
                "spaCy is not installed.  Run: pip install spacy"
            ) from exc
        except OSError as exc:
            raise RuntimeError(
                "spaCy model 'de_core_news_sm' not found. "
                "Run: python -m spacy download de_core_news_sm"
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
        candidates.extend(self._extract_case_agreements(tokens))
        candidates.extend(self._extract_idioms(tokens))

        return CandidateSentenceResult(text=sentence, candidates=candidates)

    def get_lesson(self, object_id: str) -> CandidateObject | None:
        return self.lesson_store.get(object_id)

    # ------------------------------------------------------------------
    # Idioms
    # ------------------------------------------------------------------

    def _extract_idioms(self, tokens: list[Any]) -> list[CandidateObject]:
        """Detect invariant multi-word expressions by surface-form token matching.

        Scans the lowercased token sequence for entries in ``_IDIOM_TABLE``.
        Sorted longest-first (by table order); once a span is consumed by a
        longer match, shorter overlapping phrases are not re-matched.
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

            # German nouns keep capitalisation in the lemma; other POS lowercased.
            lemma = tok.lemma_ if tok.pos_ == "NOUN" else tok.lemma_.lower()

            # Skip very short lemmas and artefacts.
            if len(lemma) < 2 or lemma in seen:
                continue
            seen.add(lemma)

            data: dict[str, Any] = {"lemma": lemma, "pos": tok.pos_}
            cefr = _get_cefr_level("de", lemma) or ("A1" if lemma in _A1 else "A2" if lemma in _A2 else "B1" if lemma in _B1 else None)
            if cefr:
                data["cefr_level"] = cefr

            if tok.pos_ == "NOUN":
                if noun_gender := _morph_first(tok, "Gender"):
                    data["gender"] = noun_gender
                if noun_number := _morph_first(tok, "Number"):
                    data["number"] = noun_number
                if noun_case := _morph_first(tok, "Case"):
                    data["case"] = noun_case

            if tok.pos_ == "ADJ":
                if degree := _morph_first(tok, "Degree"):
                    data["degree"] = degree

            if tok.pos_ in {"VERB", "AUX"} and verb_form:
                data["verb_form"] = verb_form

            confidence = self._vocab_confidence(tok)
            candidates.append(CandidateObject(
                canonical_form=lemma,
                surface_form=tok.text,
                type="vocabulary",
                label=tok.text,
                lesson_data=data,
                confidence=confidence,
            ))
        return candidates

    def _vocab_confidence(self, tok: Any) -> float:
        # is_oov is always True for de_core_news_sm — not a useful signal.
        if tok.pos_ == "PROPN":
            return 0.60
        return 0.80

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

            # Reconstruct full lemma for separable verbs.
            particle    = _find_separable_particle(tok, tokens)
            is_separable = particle is not None
            bare_lemma  = tok.lemma_.lower()
            lemma       = f"{particle}{bare_lemma}" if is_separable else bare_lemma

            if len(lemma) < 2:
                continue

            feats         = self._verb_morph(tok)
            canonical_form = _conj_canonical_form(lemma, feats)
            if canonical_form in seen_conj:
                continue
            seen_conj.add(canonical_form)
            seen_vocab.add(lemma)

            is_reflexive = _has_reflexive_clitic(tok, tokens)
            confidence   = self._conj_confidence(feats)
            conf_note    = _conj_confidence_note(feats)

            paradigm = _paradigm_class(lemma)
            lesson: dict[str, Any] = {
                "lemma":          lemma,
                "surface":        tok.text,
                "tense":          feats["tense"],
                "mood":           feats["mood"],
                "person":         feats["person"],
                "number":         feats["number"],
                "morph_complete": _conj_is_complete(feats),
                "is_reflexive":   is_reflexive,
                "paradigm_class": paradigm,
                "is_irregular":   lemma in _STRONG_VERBS or paradigm == "modal",
                "is_separable":   is_separable,
                "verb_class":     paradigm,
            }
            if is_separable and particle:
                lesson["particle"] = particle
            if conf_note:
                lesson["confidence_note"] = conf_note

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

        return {
            "tense":  _TENSE_DISPLAY.get(tense_raw or "", tense_raw or "unknown"),
            "mood":   _MOOD_DISPLAY.get(mood_raw or "", mood_raw or "unknown"),
            "person": person or "unknown",
            "number": number or "unknown",
        }

    def _conj_confidence(self, feats: dict[str, str]) -> float:
        # Cannot use is_oov (always True for de_core_news_sm).
        # Use count of resolved morphological features instead.
        known = sum(
            1 for k in ("tense", "mood", "person")
            if feats.get(k) not in (None, "unknown")
        )
        return round(min(0.50 + known * 0.10, 0.80), 2)

    # ------------------------------------------------------------------
    # Case agreement
    # ------------------------------------------------------------------

    def _extract_case_agreements(self, tokens: list[Any]) -> list[CandidateObject]:
        """Find DET+NOUN and ADJ+NOUN agreement clusters with case info.

        Emits ``case_agreement`` objects when:
        - case can be read from the noun or inferred from a DET/ADJ child, AND
        - at least one of gender/number is confirmed from the modifier AND
        - there is no confirmed mismatch on any feature.

        German-specific notes:
        - The model provides Case on DET tokens reliably, less so on ADJ.
        - Neuter nouns in nominative and accusative are often identical;
          the model may not distinguish them (case_match may be None).
        - Proper nouns are excluded from agreement analysis.
        """
        candidates: list[CandidateObject] = []
        seen_pairs: set[tuple[str, str, str]] = set()

        nouns = [t for t in tokens if t.pos_ == "NOUN"]
        for noun in nouns:
            noun_case   = _morph_first(noun, "Case")
            noun_gender = _morph_first(noun, "Gender")
            noun_number = _morph_first(noun, "Number")

            for mod in _find_modifiers(noun, tokens):
                mod_case   = _morph_first(mod, "Case")
                mod_gender = _morph_first(mod, "Gender")
                mod_number = _morph_first(mod, "Number")

                # Case on the modifier is the primary source; fall back to noun.
                resolved_case = mod_case or noun_case

                case_match = (
                    mod_case == noun_case
                    if mod_case and noun_case else None
                )
                gender_match = (
                    mod_gender == noun_gender
                    if mod_gender and noun_gender else None
                )
                number_match = (
                    mod_number == noun_number
                    if mod_number and noun_number else None
                )

                # Drop confirmed mismatches (model parse error).
                if case_match is False or gender_match is False or number_match is False:
                    continue

                # Require at least one positive match or a resolved case.
                if (
                    gender_match is None
                    and number_match is None
                    and case_match is None
                    and not resolved_case
                ):
                    continue

                # German nouns keep capitalisation in the lemma.
                noun_lemma = noun.lemma_
                mod_lemma  = mod.lemma_.lower()

                pair_key = (mod.pos_, mod_lemma, noun_lemma)
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                label = (
                    f"{mod.text} {noun.text}"
                    if mod.i < noun.i
                    else f"{noun.text} {mod.text}"
                )
                canonical_form = (
                    f"case_agreement:{(resolved_case or 'unk').lower()}"
                    f":{mod_lemma}_{noun_lemma}"
                )

                confidence = _case_agreement_confidence(
                    case_match, gender_match, number_match
                )
                conf_note  = _case_agreement_confidence_note(
                    case_match, gender_match, number_match
                )

                candidates.append(CandidateObject(
                    canonical_form=canonical_form,
                    surface_form=label,
                    type="case_agreement",
                    label=label,
                    lesson_data={
                        "modifier":        mod.text,
                        "modifier_pos":    mod.pos_,
                        "noun":            noun.text,
                        "case":            resolved_case or "unknown",
                        "gender":          noun_gender or "unknown",
                        "number":          noun_number or "unknown",
                        "case_match":      case_match,
                        "gender_match":    gender_match,
                        "number_match":    number_match,
                        "confidence_note": conf_note,
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


# ── Module-level helpers (stateless) ─────────────────────────────────────────

def _morph_first(tok: Any, feature: str) -> str | None:
    """Return the first value for a morph feature, or None if absent."""
    values = tok.morph.get(feature)
    return values[0] if values else None


def _paradigm_class(lemma: str) -> str:
    """Return the verb class for a German lemma: weak / strong / modal."""
    if lemma in _MODAL_VERBS:
        return "modal"
    if lemma in _STRONG_VERBS:
        return "strong"
    return "weak"


def _find_separable_particle(tok: Any, tokens: list[Any]) -> str | None:
    """Return the separable particle if *tok* has a ``dep=svp`` child.

    de_core_news_sm assigns ``dep="svp"`` to the prefix in a separable verb
    construction (e.g. ``an`` in ``Er ruft an``).  Returns the lower-cased
    text of the particle, or None.
    """
    for child in tok.children:
        if child.dep_ == "svp":
            return child.text.lower()
    return None


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


def _conj_confidence_note(feats: dict[str, str]) -> str | None:
    unknown = [
        k for k in ("tense", "mood", "person")
        if feats.get(k) in (None, "unknown")
    ]
    if unknown:
        return f"morphology unavailable for: {', '.join(unknown)}"
    return None


def _has_reflexive_clitic(tok: Any, tokens: list[Any]) -> bool:
    """True when *tok* has a reflexive pronoun as a syntactic child.

    Uses the model-agnostic ``Reflex=Yes`` morphological feature.
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
    """Return DET and ADJ tokens that directly modify *noun*.

    Primary: spaCy dependency arcs.  Fallback: immediate adjacency.
    Coordinated modifiers (dep_=conj or flat) are excluded.
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


def _case_agreement_confidence(
    case_match: bool | None,
    gender_match: bool | None,
    number_match: bool | None,
) -> float:
    confirmed = sum(
        1 for m in (case_match, gender_match, number_match) if m is True
    )
    if confirmed == 3:
        return 0.82
    if confirmed == 2:
        return 0.72
    if confirmed == 1:
        return 0.62
    return 0.52


def _case_agreement_confidence_note(
    case_match: bool | None,
    gender_match: bool | None,
    number_match: bool | None,
) -> str:
    labels = {True: "confirmed", None: "unavailable"}
    parts = [
        f"case: {labels.get(case_match, 'unknown')}",
        f"gender: {labels.get(gender_match, 'unknown')}",
        f"number: {labels.get(number_match, 'unknown')}",
    ]
    return "; ".join(parts)


def create_plugin() -> GermanPlugin:
    return GermanPlugin()
