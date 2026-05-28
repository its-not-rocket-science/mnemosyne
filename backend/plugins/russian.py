"""Russian language plugin — spaCy ``ru_core_news_sm`` + pymorphy3.

Registers as ``language_code = "ru"``.

─────────────────────────────────────────────────────────────────────────────
WHAT THIS PLUGIN EXTRACTS
─────────────────────────────────────────────────────────────────────────────

**Vocabulary** — open-class content words (NOUN, ADJ, ADV, non-finite
VERB/AUX).  Finite verbs are excluded here; they appear as conjugation
objects.

  Russian nouns are stored with lowercase lemmas (pymorphy3 convention).

  lesson_data keys: lemma, pos, gender*, number*, case*, animacy*,
                    degree*, verb_form*, confidence_note*
  (* = only when available)

**Conjugation** — finite VERB and AUX tokens (VerbForm=Fin), annotated with:
  • morphological features: tense, aspect, mood, person_or_gender, number
  • morph_complete: True when tense + mood + aspect are all resolved
  • Russian past tense uses Gender (Masc/Fem/Neut) rather than Person because
    past-tense agreement is with the subject's gender, not person.  Present /
    future / imperative use Person as normal.

  lesson_data keys: lemma, surface, tense, aspect, mood, person_or_gender,
                    number, morph_complete, confidence_note*

**Case agreement** (type = ``case_agreement``) — ADJ+NOUN clusters where
case, gender, and number are resolvable.  Russian has six cases:
  Nom, Gen, Dat, Acc, Ins, Loc.

  Russian has no articles so DET is not part of case agreement.
  Confirmed mismatches are silently dropped.

  lesson_data keys: modifier, modifier_pos, noun, case, gender, number,
                    case_match, gender_match, number_match, confidence_note

─────────────────────────────────────────────────────────────────────────────
NOT YET IMPLEMENTED (future iterations)
─────────────────────────────────────────────────────────────────────────────

Aspect pairs (imperfective ↔ perfective partner lookup) are deferred.
Verbal government (verb + required case) is deferred.
Short-form adjectives and comparative forms are deferred.
Idiom detection is deferred.

─────────────────────────────────────────────────────────────────────────────
KNOWN MODEL LIMITATIONS (ru_core_news_sm)
─────────────────────────────────────────────────────────────────────────────

- The small model underperforms on ambiguous prepositional phrases where the
  same form can be instrumental or nominative (e.g. neuter short adjectives).
- Long-distance agreement across clauses may not be detected.
- Verbal aspect is generally reliable but may be wrong for prefixed verbs.
- The model does not distinguish animate/inanimate accusative reliably for
  all noun classes.
"""
from __future__ import annotations

import logging
from functools import cached_property
from typing import Any

from backend.plugins.cefr_vocab import A1 as _CEFR_A1, A2 as _CEFR_A2
from backend.core.vocab_index import get_cefr_level as _get_cefr_level
from backend.schemas.language import LanguageCapabilities, NuanceCapabilities
from backend.schemas.parse import (
    CandidateObject,
    CandidateSentenceResult,
    RelationHint,
)

logger = logging.getLogger(__name__)

_A1 = _CEFR_A1.get("ru", frozenset())
_A2 = _CEFR_A2.get("ru", frozenset())

# ── POS filter ────────────────────────────────────────────────────────────────

# Russian has no articles (DET is rare / proper-noun demonstratives).
# PRON covers pronouns (я, ты, он…); skip them as vocabulary.
_SKIP_POS = frozenset({
    "DET", "ADP", "CCONJ", "SCONJ", "CONJ", "PUNCT", "SPACE",
    "X", "SYM", "NUM", "PRON", "INTJ", "PART",
})

_NON_FINITE_FORMS = frozenset({"Inf", "Part", "Conv"})   # Conv = converb/gerund

# ── Display maps ──────────────────────────────────────────────────────────────

_TENSE_DISPLAY: dict[str, str] = {
    "Pres": "present",
    "Past": "past",
    "Fut":  "future",
}

_MOOD_DISPLAY: dict[str, str] = {
    "Ind": "indicative",
    "Imp": "imperative",
    "Cnd": "conditional",
}

_ASPECT_DISPLAY: dict[str, str] = {
    "Imp":  "imperfective",
    "Perf": "perfective",
}

_CASE_DISPLAY: dict[str, str] = {
    "Nom": "nominative",
    "Gen": "genitive",
    "Dat": "dative",
    "Acc": "accusative",
    "Ins": "instrumental",
    "Loc": "locative",
}

_GENDER_DISPLAY: dict[str, str] = {
    "Masc": "masculine",
    "Fem":  "feminine",
    "Neut": "neuter",
}

# Tenses in which the model reports Gender on the verb (not Person).
_PAST_TENSES = frozenset({"Past"})


# ── Idiom table ───────────────────────────────────────────────────────────────
# Fixed-form (non-conjugable) multi-word expressions.
# Tuples: (lowercased_word_sequence, english_meaning, register)
# Sorted longest-first so longer matches are consumed before their substrings.

_IDIOM_TABLE: tuple[tuple[tuple[str, ...], str, str], ...] = (
    # ── 4-word phrases ────────────────────────────────────────────────────────
    (("в", "то", "же", "время"),          "at the same time",           "neutral"),
    (("с", "одной", "стороны",),          "on the one hand",            "neutral"),
    # ── 3-word phrases ────────────────────────────────────────────────────────
    (("в", "самом", "деле"),              "really / in fact",           "neutral"),
    (("на", "самом", "деле"),             "in fact / actually",         "neutral"),
    (("в", "конце", "концов"),            "in the end / after all",     "neutral"),
    (("по", "крайней", "мере"),           "at least",                   "neutral"),
    (("прежде", "всего"),                 "first of all / above all",   "neutral"),
    (("в", "общем",),                     "in general / on the whole",  "neutral"),
    (("в", "частности",),                 "in particular",              "formal"),
    (("тем", "не", "менее"),              "nevertheless",               "formal"),
    (("иными", "словами",),               "in other words",             "neutral"),
    (("другими", "словами",),             "in other words",             "neutral"),
    (("то", "есть"),                      "that is / i.e.",             "neutral"),
    # ── 2-word phrases ────────────────────────────────────────────────────────
    (("конечно",),                        "of course / certainly",      "neutral"),
    (("наверное",),                       "probably / perhaps",         "neutral"),
    (("наверняка",),                      "for sure / certainly",       "neutral"),
    (("вообще-то",),                      "actually / generally speaking","neutral"),
    (("честно", "говоря"),                "honestly speaking",          "neutral"),
    (("кстати",),                         "by the way",                 "neutral"),
    (("вдруг",),                          "suddenly / what if",         "neutral"),
    (("пожалуй",),                        "perhaps / I'd say",          "neutral"),
    (("например",),                       "for example",                "neutral"),
    (("поэтому",),                        "therefore / that's why",     "neutral"),
    (("однако",),                         "however / but",              "neutral"),
    (("зато",),                           "but on the other hand",      "neutral"),
    (("всё-таки",),                       "all the same / still",       "neutral"),
    (("всё", "равно"),                    "all the same / anyway",      "neutral"),
    (("до", "свидания"),                  "goodbye (formal)",           "formal"),
    (("спокойной", "ночи"),               "good night",                 "neutral"),
)


# ── Plugin ────────────────────────────────────────────────────────────────────

class RussianPlugin:
    language_code = "ru"
    display_name  = "Russian"
    direction     = "ltr"
    capabilities  = LanguageCapabilities(
        code="ru",
        display_name="Russian",
        direction="ltr",
        script_family="cyrillic",
        tokenization_mode="whitespace",
        morphology_depth="rich",
        lesson_modes_supported=["morphology", "vocabulary"],
        # v2 fields
        analysis_depth="full",
        segmentation_quality="medium",
        tokenization_quality="high",
        morphology_quality="medium",   # small model; ambiguous forms may err
        syntax_support=True,
        idiom_detection=True,    # curated fixed-expression table (~35 entries)
        tts_lang_tag="ru",
        transliteration_scheme=None,   # no romanisation in this iteration
        nuance_capabilities=NuanceCapabilities(
            idioms="partial",            # curated ~35-entry fixed-expression table
            phrase_families="partial",   # 14-family curated catalog; extractor wired
            literary_references="none",
            cultural_references="none",
            etymology="partial",         # 50-entry curated catalog; Proto-Slavic/PIE chains covered
            formality_register="stub",   # formal/informal verb forms detectable
            grammar_nuance="partial",    # aspect/tense/case drilling
            pronunciation_tts="partial", # browser TTS reliable for ru
            transliteration="none",      # no romanisation scheme active
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
            return spacy.load("ru_core_news_sm", disable=["ner"])
        except ImportError as exc:
            raise RuntimeError(
                "spaCy is not installed.  Run: pip install spacy"
            ) from exc
        except OSError as exc:
            raise RuntimeError(
                "spaCy model 'ru_core_news_sm' not found. "
                "Run: python -m spacy download ru_core_news_sm"
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

        seen_nuance: set[str] = set()
        candidates.extend(self._extract_nuance(conj_candidates, seen_nuance))

        return CandidateSentenceResult(text=sentence, candidates=candidates)

    def get_lesson(self, object_id: str) -> CandidateObject | None:
        return self.lesson_store.get(object_id)

    # ------------------------------------------------------------------
    # Idioms
    # ------------------------------------------------------------------

    def _extract_idioms(self, tokens: list[Any]) -> list[CandidateObject]:
        """Detect invariant multi-word expressions by surface-form token matching."""
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
    # Nuance
    # ------------------------------------------------------------------

    def _extract_nuance(
        self,
        conj_candidates: list[CandidateObject],
        seen_nuance: set[str],
    ) -> list[CandidateObject]:
        """Emit aspect nuance observations derived from conjugation results.

        Russian verbal aspect is one of the most important grammatical concepts
        for learners.  A nuance object is emitted once per (aspect, lemma) pair:

        - ``perfective_aspect`` — the action is presented as completed or
          resulting in a state change.
        - ``imperfective_aspect`` — the action is ongoing, habitual, or viewed
          as a process without reference to completion.
        """
        candidates: list[CandidateObject] = []

        for cand in conj_candidates:
            lemma  = cand.lesson_data.get("lemma", "")
            aspect = cand.lesson_data.get("aspect", "")
            surface = cand.lesson_data.get("surface", cand.surface_form or "")

            if aspect == "perfective":
                cf = f"nuance:perfective_aspect:{lemma}"
                if cf in seen_nuance:
                    continue
                seen_nuance.add(cf)
                candidates.append(CandidateObject(
                    canonical_form=cf,
                    surface_form=surface,
                    type="nuance",
                    label=surface,
                    lesson_data={
                        "nuance_type": "perfective_aspect",
                        "lemma":       lemma,
                        "surface":     surface,
                        "note": (
                            f"«{surface}» is perfective: the action is viewed as "
                            "completed or resulting in a definite outcome. "
                            "Perfective verbs typically cannot form an imperfective present."
                        ),
                    },
                    confidence=0.80,
                    relation_hints=[RelationHint(
                        relation_type="nuance_of",
                        target_canonical_form=lemma,
                        target_type="vocabulary",
                    )],
                ))

            elif aspect == "imperfective":
                cf = f"nuance:imperfective_aspect:{lemma}"
                if cf in seen_nuance:
                    continue
                seen_nuance.add(cf)
                candidates.append(CandidateObject(
                    canonical_form=cf,
                    surface_form=surface,
                    type="nuance",
                    label=surface,
                    lesson_data={
                        "nuance_type": "imperfective_aspect",
                        "lemma":       lemma,
                        "surface":     surface,
                        "note": (
                            f"«{surface}» is imperfective: the action is viewed as "
                            "ongoing, repeated, or habitual — not necessarily completed. "
                            "Imperfective verbs form a full present-tense paradigm."
                        ),
                    },
                    confidence=0.80,
                    relation_hints=[RelationHint(
                        relation_type="nuance_of",
                        target_canonical_form=lemma,
                        target_type="vocabulary",
                    )],
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

            # Russian lemmas are lowercase from pymorphy3.
            lemma = tok.lemma_.lower()

            if len(lemma) < 2 or lemma in seen:
                continue
            seen.add(lemma)

            data: dict[str, Any] = {"lemma": lemma, "pos": tok.pos_}
            cefr = _get_cefr_level("ru", lemma) or ("A1" if lemma in _A1 else "A2" if lemma in _A2 else None)
            if cefr:
                data["cefr_level"] = cefr

            if tok.pos_ == "NOUN":
                if gender := _morph_first(tok, "Gender"):
                    data["gender"] = gender
                if number := _morph_first(tok, "Number"):
                    data["number"] = number
                if case := _morph_first(tok, "Case"):
                    data["case"] = case
                if animacy := _morph_first(tok, "Animacy"):
                    data["animacy"] = animacy

            if tok.pos_ == "ADJ":
                if degree := _morph_first(tok, "Degree"):
                    data["degree"] = degree

            if tok.pos_ in {"VERB", "AUX"} and verb_form:
                data["verb_form"] = verb_form
                if aspect := _morph_first(tok, "Aspect"):
                    data["aspect"] = _ASPECT_DISPLAY.get(aspect, aspect)

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

            lemma = tok.lemma_.lower()
            if len(lemma) < 2:
                continue

            feats          = self._verb_morph(tok)
            canonical_form = _conj_canonical_form(lemma, feats)
            if canonical_form in seen_conj:
                continue
            seen_conj.add(canonical_form)
            seen_vocab.add(lemma)

            confidence = self._conj_confidence(feats)
            conf_note  = _conj_confidence_note(feats)

            lesson: dict[str, Any] = {
                "lemma":            lemma,
                "surface":          tok.text,
                "tense":            feats["tense"],
                "aspect":           feats["aspect"],
                "mood":             feats["mood"],
                "person_or_gender": feats["person_or_gender"],
                "number":           feats["number"],
                "morph_complete":   _conj_is_complete(feats),
            }
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
        tense_raw  = _morph_first(tok, "Tense")
        mood_raw   = _morph_first(tok, "Mood")
        aspect_raw = _morph_first(tok, "Aspect")
        number     = _morph_first(tok, "Number")

        # Russian past tense expresses Gender (agreement with subject), not Person.
        if tense_raw in _PAST_TENSES:
            gender_raw        = _morph_first(tok, "Gender")
            person_or_gender  = _GENDER_DISPLAY.get(gender_raw or "", gender_raw or "unknown")
        else:
            person = _morph_first(tok, "Person")
            person_or_gender  = person or "unknown"

        return {
            "tense":            _TENSE_DISPLAY.get(tense_raw or "", tense_raw or "unknown"),
            "aspect":           _ASPECT_DISPLAY.get(aspect_raw or "", aspect_raw or "unknown"),
            "mood":             _MOOD_DISPLAY.get(mood_raw or "", mood_raw or "unknown"),
            "person_or_gender": person_or_gender,
            "number":           number or "unknown",
        }

    def _conj_confidence(self, feats: dict[str, str]) -> float:
        known = sum(
            1 for k in ("tense", "mood", "aspect")
            if feats.get(k) not in (None, "unknown")
        )
        return round(min(0.50 + known * 0.10, 0.82), 2)

    # ------------------------------------------------------------------
    # Case agreement
    # ------------------------------------------------------------------

    def _extract_case_agreements(self, tokens: list[Any]) -> list[CandidateObject]:
        """Find ADJ+NOUN agreement clusters with case info.

        Russian has no articles, so only ADJ modifiers are considered.
        Emits ``case_agreement`` objects for all six Russian cases.
        """
        candidates: list[CandidateObject] = []
        seen_pairs: set[tuple[str, str, str]] = set()

        nouns = [t for t in tokens if t.pos_ == "NOUN"]
        for noun in nouns:
            noun_case   = _morph_first(noun, "Case")
            noun_gender = _morph_first(noun, "Gender")
            noun_number = _morph_first(noun, "Number")

            for mod in _find_adj_modifiers(noun, tokens):
                mod_case   = _morph_first(mod, "Case")
                mod_gender = _morph_first(mod, "Gender")
                mod_number = _morph_first(mod, "Number")

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

                if (
                    gender_match is None
                    and number_match is None
                    and case_match is None
                    and not resolved_case
                ):
                    continue

                noun_lemma = noun.lemma_.lower()
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
                        "case":            _CASE_DISPLAY.get(resolved_case or "", resolved_case or "unknown"),
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


def _conj_canonical_form(lemma: str, feats: dict[str, str]) -> str:
    """Stable conjugation canonical_form: lemma + five morphological axes."""
    return (
        f"{lemma}"
        f":{feats.get('tense', 'unk')}"
        f":{feats.get('aspect', 'unk')}"
        f":{feats.get('mood', 'unk')}"
        f":{feats.get('person_or_gender', 'unk')}"
        f":{feats.get('number', 'unk')}"
    )


def _conj_is_complete(feats: dict[str, str]) -> bool:
    """morph_complete when tense, mood, and aspect are all resolved."""
    return all(
        feats.get(k) not in (None, "unknown")
        for k in ("tense", "mood", "aspect")
    )


def _conj_confidence_note(feats: dict[str, str]) -> str | None:
    unknown = [
        k for k in ("tense", "mood", "aspect")
        if feats.get(k) in (None, "unknown")
    ]
    if unknown:
        return f"morphology unavailable for: {', '.join(unknown)}"
    return None


def _find_adj_modifiers(noun: Any, tokens: list[Any]) -> list[Any]:
    """Return ADJ tokens that directly modify *noun*.

    Russian has no articles, so only ADJ modifiers are considered for
    case agreement (unlike German which also includes DET).
    """
    dep_based: list[Any] = [
        t for t in tokens
        if t.pos_ == "ADJ"
        and t.head.i == noun.i
        and t.i != noun.i
        and t.dep_ not in {"conj", "flat"}
    ]
    if dep_based:
        return dep_based

    adjacent: list[Any] = []
    for t in tokens:
        if t.pos_ != "ADJ" or t.i == noun.i:
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


def create_plugin() -> RussianPlugin:
    return RussianPlugin()
