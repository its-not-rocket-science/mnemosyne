"""Persian (Farsi) nuance extractor.

Detects core Persian grammar markers and register signals that are
high-value for learners and reliably identifiable from surface form:

  ra_accusative     -- the direct object / accusative particle
  mi_imperfective   -- mi- preverb marking present / habitual / past-progressive
  nami_negative     -- na-mi- negative imperfective preverb
  negation_*        -- nist, nabud, nashod, na standalone negation forms
  formality_shoma   -- shoma: formal/polite second-person address
  formality_to      -- to: informal second-person address
  classical_register -- classical/literary vocabulary or vocative ay
"""
from __future__ import annotations

import re
from typing import Any

from backend.schemas.parse import CandidateObject, RelationHint

# mi- imperfective preverb: U+0645 U+06CC U+200C (mi + ZWNJ).
# Negative: U+0646 U+0645 U+06CC U+200C (na + mi + ZWNJ).
_MI_RE   = re.compile(r"می‌", re.IGNORECASE)
_NAMI_RE = re.compile(r"نمی‌", re.IGNORECASE)

# Direct object marker and negation tokens (standalone words in prose):
_RA           = "را"                   # را  ra
_SHOMA        = "شما"             # شما  shoma (formal you)
_TO           = "تو"                   # تو  to (informal you)

# Negation: nah (no), nist (is not), nabud (was not), nashod (did not happen).
_NEGATION: dict[str, tuple[str, str]] = {
    "نه": (
        "negation_na",
        "'no / not' -- the basic Persian word for 'no' and a refusal marker. "
        "As a prefix it becomes na- before verbs in classical usage; in modern "
        "speech na- combines with the verb directly.",
    ),
    "نیست": (
        "negation_nist",
        "Negative present-tense copula: 'is not / are not'. "
        "Formed from na- + ast (is): khaneh anja nist (the house is not there). "
        "Contrast with hast (is, existential) -- both take the same na- negation.",
    ),
    "نبود": (
        "negation_nabud",
        "Negative past-tense copula: 'was not / were not'. "
        "Formed from na- + bud (was): u anja nabud (he was not there). "
        "The positive form bud is rarely used alone in modern Persian.",
    ),
    "نشد": (
        "negation_nashod",
        "Negates shodan (to become / to happen) in the simple past: "
        "'it did not happen / it did not work out'. "
        "nashod kar (the work did not get done) is a very common idiomatic use.",
    ),
}

# Classical / literary register markers:
_CLASSICAL: dict[str, str] = {
    "همانا": (
        "hamana (verily, truly) -- a classical Persian affirmative particle. "
        "Common in Qur'anic commentary, Rumi (Masnavi), and Sa'di (Gulistan/Bustan). "
        "Absent from modern conversational Persian."
    ),
    "بدان": (
        "bedan (know that...) -- classical imperative of danestan (to know). "
        "Introduces authoritative statements in classical prose and poetry. "
        "A marker of formal literary register."
    ),
    "هرگاه": (
        "hargah (whenever) -- classical temporal conjunction. "
        "More common in classical and formal Persian than the colloquial harvaght. "
        "Frequently found in Sa'di's prose and philosophical texts."
    ),
}

# Classical vocative particle ay (O!) -- standalone token before a noun/name.
_AY = "ای"  # ای


def _tok_text(tok: Any) -> str:
    return tok.text if hasattr(tok, "text") else str(tok)


_TRAILING_PUNCT_RE = re.compile(r"[.,!?؟۔:؛;\"'()]+$")


def _tok_surface(tok: Any) -> str:
    """Return token text with trailing punctuation stripped.

    Whitespace-split tokenisers (used in gold fixture tests) attach
    terminal punctuation to the final token of a sentence.  Stripping
    it normalises the surface for dictionary lookups.
    """
    return _TRAILING_PUNCT_RE.sub("", _tok_text(tok))


class FarsiNuanceExtractor:
    language = "fa"

    def extract_nuance(
        self,
        sentence: str,
        tokens: list[Any],
        candidates: list[CandidateObject],
        language: str,
    ) -> list[CandidateObject]:
        out: list[CandidateObject] = []
        seen: set[str] = set()
        out.extend(self._phrase_families(sentence))
        out.extend(self._ra_accusative(tokens, seen))
        out.extend(self._nami_negative(sentence, seen))
        out.extend(self._mi_imperfective(sentence, seen))
        out.extend(self._negation_markers(tokens, seen))
        out.extend(self._formality_register(tokens, seen))
        out.extend(self._classical_register(tokens, seen))
        return out

    # ------------------------------------------------------------------

    def _phrase_families(self, sentence: str) -> list[CandidateObject]:
        from backend.dictionary.phrase_families import match_phrase_families
        # Whitespace-split preserves ZWNJ compound verbs as single tokens;
        # the matcher's normaliser strips ZWNJ before comparison, so
        # "می‌شمارند" normalises to "میشمارند" and matches the stored surface.
        # Using WORD_RE-split tokens would break ZWNJ compounds into two parts.
        return match_phrase_families(sentence.split(), self.language)

    def _ra_accusative(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        cf = "nuance:fa:ra_accusative"
        for tok in tokens:
            if _tok_surface(tok) != _RA:
                continue
            if cf in seen:
                break
            seen.add(cf)
            return [CandidateObject(
                canonical_form=cf,
                surface_form=_RA,
                type="nuance",
                label=_RA,
                lesson_data={
                    "nuance_type": "ra_accusative",
                    "explanation": (
                        "ra is the Persian direct object marker (accusative particle). "
                        "It follows definite or specific direct objects: "
                        "ketab ra khandam (I read the book). "
                        "Ra is absent with indefinite objects: ketabi khandam (I read a book). "
                        "This definiteness-sensitive object marking distinguishes "
                        "Persian from Arabic, which marks case morphologically on the noun."
                    ),
                    "register": "neutral",
                    "learner_level": "A2",
                    "source": "heuristic",
                },
                confidence=0.95,
                relation_hints=[RelationHint(
                    relation_type="nuance_of",
                    target_canonical_form=_RA,
                    target_type="vocabulary",
                )],
            )]
        return []

    def _nami_negative(
        self, sentence: str, seen: set[str]
    ) -> list[CandidateObject]:
        cf = "nuance:fa:nami_negative"
        if cf in seen or not _NAMI_RE.search(sentence):
            return []
        seen.add(cf)
        return [CandidateObject(
            canonical_form=cf,
            surface_form="نمی‌",
            type="nuance",
            label="نمی‌",
            lesson_data={
                "nuance_type": "nami_negative",
                "explanation": (
                    "nami- is the negative imperfective preverb: "
                    "na- (not) + mi- (imperfective aspect marker). "
                    "nami-danam (I don't know), nami-raftam (I was not going). "
                    "nami- is the standard negation for all imperfective verb forms. "
                    "The ZWNJ (zero-width non-joiner) between nami and the stem is "
                    "required in correct Persian orthography."
                ),
                "register": "neutral",
                "learner_level": "A1",
                "source": "heuristic",
            },
            confidence=0.93,
        )]

    def _mi_imperfective(
        self, sentence: str, seen: set[str]
    ) -> list[CandidateObject]:
        # Check after nami- so the nami- candidate takes precedence.
        # Only fire mi- if there is a mi- that is NOT part of nami-.
        # Strategy: remove all nami- occurrences from the sentence and check remainder.
        cf = "nuance:fa:mi_imperfective"
        if cf in seen:
            return []
        remainder = _NAMI_RE.sub("", sentence)
        if not _MI_RE.search(remainder):
            return []
        seen.add(cf)
        return [CandidateObject(
            canonical_form=cf,
            surface_form="می‌",
            type="nuance",
            label="می‌",
            lesson_data={
                "nuance_type": "mi_imperfective",
                "explanation": (
                    "mi- is the Persian imperfective preverb, written before the "
                    "main verb with a ZWNJ: mi-konam (I do / am doing), "
                    "mi-raftam (I was going). "
                    "It marks present tense, present continuous, past continuous, "
                    "and habitual aspect. Without mi-, the verb is simple past or subjunctive. "
                    "Negative forms use na-mi- (nami-), not a separate word."
                ),
                "register": "neutral",
                "learner_level": "A1",
                "source": "heuristic",
            },
            confidence=0.92,
        )]

    def _negation_markers(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for tok in tokens:
            surface = _tok_surface(tok)
            if surface not in _NEGATION:
                continue
            nuance_key, explanation = _NEGATION[surface]
            cf = f"nuance:fa:negation:{nuance_key}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=surface,
                type="nuance",
                label=surface,
                lesson_data={
                    "nuance_type": nuance_key,
                    "explanation": explanation,
                    "register": "neutral",
                    "learner_level": "A2",
                    "source": "heuristic",
                },
                confidence=0.90,
                relation_hints=[RelationHint(
                    relation_type="nuance_of",
                    target_canonical_form=surface,
                    target_type="vocabulary",
                )],
            ))
        return out

    def _formality_register(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for tok in tokens:
            surface = _tok_surface(tok)
            if surface == _SHOMA:
                cf = "nuance:fa:formality_shoma"
                if cf not in seen:
                    seen.add(cf)
                    out.append(CandidateObject(
                        canonical_form=cf,
                        surface_form=surface,
                        type="nuance",
                        label=surface,
                        lesson_data={
                            "nuance_type": "formality_shoma",
                            "explanation": (
                                "shoma is the formal/polite second-person pronoun and also "
                                "the plural 'you'. Addressing a single person as shoma "
                                "marks respect or social distance; to is the intimate singular. "
                                "Unlike French tu/vous or German du/Sie, shoma does not "
                                "change verb inflection -- the verb takes the third-person "
                                "plural form regardless. Shoma is the safe default with "
                                "anyone unfamiliar in Iranian Persian."
                            ),
                            "register": "formal",
                            "learner_level": "A2",
                            "source": "heuristic",
                        },
                        confidence=0.88,
                    ))
            elif surface == _TO:
                cf = "nuance:fa:formality_to"
                if cf not in seen:
                    seen.add(cf)
                    out.append(CandidateObject(
                        canonical_form=cf,
                        surface_form=surface,
                        type="nuance",
                        label=surface,
                        lesson_data={
                            "nuance_type": "formality_to",
                            "explanation": (
                                "to is the informal singular second-person pronoun. "
                                "Use it with family, close friends, and children. "
                                "Using to with a social superior or stranger can be "
                                "perceived as disrespectful; shoma is the safe default "
                                "with anyone unfamiliar."
                            ),
                            "register": "informal",
                            "learner_level": "A2",
                            "source": "heuristic",
                        },
                        confidence=0.88,
                    ))
        return out

    def _classical_register(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        cf = "nuance:fa:classical_register"
        if cf in seen:
            return []

        token_set = {_tok_surface(t) for t in tokens}
        trigger_surface: str | None = None
        trigger_explanation: str | None = None

        for surface, explanation in _CLASSICAL.items():
            if surface in token_set:
                trigger_surface = surface
                trigger_explanation = explanation
                break

        if trigger_surface is None and _AY in token_set:
            trigger_surface = _AY
            trigger_explanation = (
                "ay (O!) is the classical Persian vocative particle, "
                "used before a name or noun to address someone directly: "
                "ay dust (O friend!), ay khoda (O God!). "
                "It is a hallmark of classical poetry (Rumi, Hafez, Sa'di) "
                "and formal religious registers. Colloquial Persian uses ey instead."
            )

        if trigger_surface is None:
            return []

        seen.add(cf)
        return [CandidateObject(
            canonical_form=cf,
            surface_form=trigger_surface,
            type="nuance",
            label=trigger_surface,
            lesson_data={
                "nuance_type": "classical_register",
                "explanation": trigger_explanation,
                "register": "literary",
                "learner_level": "C1",
                "source": "heuristic",
            },
            confidence=0.80,
        )]
