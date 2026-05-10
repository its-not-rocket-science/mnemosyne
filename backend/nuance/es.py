"""Spanish nuance extractor — ser/estar, por/para, subjunctive, diminutives, etymology, phrase families."""
from __future__ import annotations

from typing import Any

from backend.schemas.parse import CandidateObject, RelationHint

_DIMINUTIVE_SUFFIXES = (
    "ito", "ita", "itos", "itas",
    "illo", "illa", "illos", "illas",
    "cito", "cita", "citos", "citas",
    "ecito", "ecita",
)

# Verbal government — populate via gen_verbal_government.py.
# Keys: verb lemma (or "verb + preposition" for prepositional verbs).
_VERBAL_GOV: dict[str, tuple[str, str]] = {}


def _text(tok: Any) -> str:
    return tok.text if hasattr(tok, "text") else str(tok)


def _lemma(c: CandidateObject) -> str:
    return c.lesson_data.get("lemma", c.canonical_form)


class SpanishNuanceExtractor:
    language = "es"

    def extract_nuance(
        self,
        sentence: str,
        tokens: list[Any],
        candidates: list[CandidateObject],
        language: str,
    ) -> list[CandidateObject]:
        out: list[CandidateObject] = []
        seen: set[str] = set()
        out.extend(self._ser_estar(candidates, seen))
        out.extend(self._por_para(tokens, seen))
        out.extend(self._subjunctive(candidates, seen))
        out.extend(self._diminutive(tokens, seen))
        out.extend(self._verbal_government(candidates, seen))
        out.extend(self._etymology(candidates, seen))
        out.extend(self._phrase_families(tokens))
        return out

    def _verbal_government(
        self, candidates: list[CandidateObject], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for c in candidates:
            if c.type not in ("vocabulary", "conjugation"):
                continue
            lemma = _lemma(c)
            if lemma not in _VERBAL_GOV:
                continue
            required_case, example = _VERBAL_GOV[lemma]
            cf = f"nuance:es:verbal_government:{lemma}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=c.surface_form,
                type="nuance",
                label=c.label,
                lesson_data={
                    "nuance_type": "verbal_government",
                    "explanation": (
                        f"{example}. "
                        "Spanish prepositional verbs select a fixed preposition that often "
                        "shifts the verb's meaning — quedar (to remain) vs. quedar en (to agree to). "
                        f"Required structure: {required_case}."
                    ),
                    "register": "neutral",
                    "learner_level": "B1",
                    "source": "heuristic",
                    "lemma": lemma,
                    "required_case": required_case,
                },
                confidence=0.85,
                relation_hints=[RelationHint(
                    relation_type="nuance_of",
                    target_canonical_form=lemma,
                    target_type="vocabulary",
                )],
            ))
        return out

    def _ser_estar(
        self, candidates: list[CandidateObject], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for c in candidates:
            if c.type != "conjugation":
                continue
            lemma = c.lesson_data.get("lemma", "")
            if lemma not in ("ser", "estar"):
                continue
            cf = f"nuance:es:ser_estar:{lemma}"
            if cf in seen:
                continue
            seen.add(cf)
            if lemma == "ser":
                explanation = (
                    "«ser» marks stable, defining qualities: identity, origin, occupation, "
                    "nationality, material. It answers what something fundamentally *is*."
                )
            else:
                explanation = (
                    "«estar» marks transient states, conditions, locations, and results of "
                    "change. It describes how something currently *is*, not what it inherently is."
                )
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=c.surface_form,
                type="nuance",
                label=c.label,
                lesson_data={
                    "nuance_type": "ser_estar",
                    "explanation": explanation,
                    "register": "neutral",
                    "learner_level": "A2",
                    "source": "heuristic",
                    "lemma": lemma,
                },
                confidence=0.85,
                relation_hints=[RelationHint(
                    relation_type="nuance_of",
                    target_canonical_form=lemma,
                    target_type="vocabulary",
                )],
            ))
        return out

    def _por_para(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for tok in tokens:
            surface = _text(tok)
            low = surface.lower()
            if low not in ("por", "para"):
                continue
            cf = f"nuance:es:por_para:{low}"
            if cf in seen:
                continue
            seen.add(cf)
            if low == "por":
                explanation = (
                    "«por» marks cause/reason, means/instrument, exchange, "
                    "duration, agent in passives, and movement through a space."
                )
            else:
                explanation = (
                    "«para» marks purpose/goal, recipient, destination, deadline, "
                    "and standards or comparisons."
                )
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=surface,
                type="nuance",
                label=surface,
                lesson_data={
                    "nuance_type": "por_para",
                    "explanation": explanation,
                    "register": "neutral",
                    "learner_level": "B1",
                    "source": "heuristic",
                    "preposition": low,
                },
                confidence=0.80,
            ))
        return out

    def _subjunctive(
        self, candidates: list[CandidateObject], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for c in candidates:
            if c.type != "conjugation":
                continue
            mood = str(c.lesson_data.get("mood", "")).lower()
            mood_raw = str(c.lesson_data.get("mood_raw", ""))
            if "sub" not in mood and "Sub" not in mood_raw:
                continue
            lemma = c.lesson_data.get("lemma", c.canonical_form)
            cf = f"nuance:es:subjunctive:{lemma}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=c.surface_form,
                type="nuance",
                label=c.label,
                lesson_data={
                    "nuance_type": "subjunctive_trigger",
                    "explanation": (
                        "The subjunctive expresses doubt, desire, emotion, or hypothetical "
                        "situations. It appears in subordinate clauses after triggers like "
                        "«querer que», «es posible que», «aunque» (hypothetical), "
                        "«antes de que», «para que»."
                    ),
                    "register": "neutral",
                    "learner_level": "B2",
                    "source": "heuristic",
                    "lemma": lemma,
                },
                confidence=0.75,
                relation_hints=[RelationHint(
                    relation_type="nuance_of",
                    target_canonical_form=lemma,
                    target_type="vocabulary",
                )],
            ))
        return out

    def _diminutive(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for tok in tokens:
            surface = _text(tok)
            low = surface.lower()
            if len(low) < 6:
                continue
            if not any(low.endswith(suf) for suf in _DIMINUTIVE_SUFFIXES):
                continue
            cf = f"nuance:es:diminutive:{low}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=surface,
                type="nuance",
                label=surface,
                lesson_data={
                    "nuance_type": "diminutive",
                    "explanation": (
                        "Spanish diminutive suffixes (-ito/-ita, -illo/-illa) express smallness, "
                        "affection, or informality, and soften requests in casual speech. "
                        "They are extremely frequent in conversational Spanish."
                    ),
                    "register": "informal",
                    "learner_level": "B1",
                    "source": "heuristic",
                    "surface": surface,
                },
                confidence=0.70,
            ))
        return out

    def _etymology(
        self, candidates: list[CandidateObject], seen: set[str]
    ) -> list[CandidateObject]:
        from backend.dictionary.etymology import DEFAULT_STORE
        out = []
        for c in candidates:
            if c.type != "vocabulary":
                continue
            lemma = c.lesson_data.get("lemma") or c.canonical_form
            entry = DEFAULT_STORE.get(self.language, lemma)
            if not entry:
                continue
            cf = f"nuance:{self.language}:etymology:{lemma.lower()}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=c.surface_form,
                type="nuance",
                label=c.label,
                lesson_data={
                    "nuance_type": "etymology",
                    "explanation": entry.origin_summary,
                    "register": "neutral",
                    "learner_level": "B1",
                    "source": entry.source_type,
                    "etymology": entry.to_lesson_data(),
                },
                confidence=0.85,
                relation_hints=[RelationHint(
                    relation_type="nuance_of",
                    target_canonical_form=lemma,
                    target_type="vocabulary",
                )],
            ))
        return out

    def _phrase_families(self, tokens: list[Any]) -> list[CandidateObject]:
        from backend.dictionary.phrase_families import match_phrase_families
        return match_phrase_families([_text(t) for t in tokens], self.language)
