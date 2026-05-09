"""Portuguese nuance extractor — você/tu register, ser/estar, subjunctive, diminutives, personal infinitive."""
from __future__ import annotations

from typing import Any

from backend.schemas.parse import CandidateObject, RelationHint

_DIMINUTIVE_SUFFIXES = (
    "inho", "inha", "inhos", "inhas",
    "zinho", "zinha", "zinhos", "zinhas",
    "ito", "ita", "itos", "itas",
)

_INFORMAL_PRONOUNS = frozenset({"tu", "te", "teu", "tua", "teus", "tuas"})
_FORMAL_PRONOUNS = frozenset({"você", "voce", "o senhor", "a senhora", "vossa"})

_PERSONAL_INF_SUFFIXES = ("ares", "ermos", "erdes", "erem", "irmos", "irdes", "irem", "armos", "ardes", "arem")


def _text(tok: Any) -> str:
    return tok.text if hasattr(tok, "text") else str(tok)


class PortugueseNuanceExtractor:
    language = "pt"

    def extract_nuance(
        self,
        sentence: str,
        tokens: list[Any],
        candidates: list[CandidateObject],
        language: str,
    ) -> list[CandidateObject]:
        out: list[CandidateObject] = []
        seen: set[str] = set()
        out.extend(self._register(tokens, seen))
        out.extend(self._ser_estar(candidates, seen))
        out.extend(self._subjunctive(candidates, seen))
        out.extend(self._diminutive(tokens, seen))
        out.extend(self._personal_infinitive(tokens, seen))
        out.extend(self._etymology(candidates, seen))
        out.extend(self._phrase_families(tokens))
        return out

    def _register(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for tok in tokens:
            low = _text(tok).lower()
            if low in _INFORMAL_PRONOUNS:
                register = "informal"
            elif low in _FORMAL_PRONOUNS:
                register = "formal"
            else:
                continue
            cf = f"nuance:pt:register:{register}"
            if cf in seen:
                continue
            seen.add(cf)
            if register == "informal":
                explanation = (
                    "«tu» is the informal second-person singular used with friends, "
                    "family, and peers, primarily in European Portuguese. In Brazilian "
                    "Portuguese, «você» is used even in informal contexts where European "
                    "Portuguese would use «tu»."
                )
            else:
                explanation = (
                    "«você» is the standard second-person form in Brazilian Portuguese, "
                    "functioning as both formal and informal 'you'. In European Portuguese "
                    "it retains a more formal or distancing register. «o senhor»/«a senhora» "
                    "are the most formal equivalents."
                )
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=_text(tok),
                type="nuance",
                label=_text(tok),
                lesson_data={
                    "nuance_type": "voce_tu_register",
                    "explanation": explanation,
                    "register": register,
                    "learner_level": "A2",
                    "source": "heuristic",
                    "pronoun": low,
                },
                confidence=0.85,
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
            cf = f"nuance:pt:ser_estar:{lemma}"
            if cf in seen:
                continue
            seen.add(cf)
            if lemma == "ser":
                explanation = (
                    "«ser» marks permanent or defining qualities: identity, nationality, "
                    "occupation, origin, material, and intrinsic characteristics. "
                    "It answers what something fundamentally is."
                )
            else:
                explanation = (
                    "«estar» marks transient states, moods, conditions, locations, and the "
                    "progressive aspect (estar + gerúndio / estar a + infinitivo in EP). "
                    "It describes how something currently is, not what it inherently is."
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
            cf = f"nuance:pt:subjunctive:{lemma}"
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
                        "The Portuguese subjunctive (conjuntivo/subjuntivo) is required "
                        "after verbs of wanting (querer que), emotion (ficar feliz que), "
                        "doubt (duvidar que), and conjunctions like «para que», «embora», "
                        "«antes que», «caso». Portuguese uses the subjunctive more "
                        "frequently than Spanish, including in temporal clauses with «quando» "
                        "for future events: «quando chegar» (when you arrive)."
                    ),
                    "register": "neutral",
                    "learner_level": "B2",
                    "source": "heuristic",
                    "lemma": lemma,
                },
                confidence=0.80,
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
            cf = f"nuance:pt:diminutive:{low}"
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
                        "Portuguese diminutive suffixes (-inho/-inha, -zinho/-zinha) express "
                        "smallness, affection, or soften requests. They are particularly "
                        "frequent in Brazilian Portuguese, where they extend beyond size to "
                        "politeness, endearment, and even irony."
                    ),
                    "register": "informal",
                    "learner_level": "B1",
                    "source": "heuristic",
                    "surface": surface,
                },
                confidence=0.70,
            ))
        return out

    def _personal_infinitive(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        """Flag inflected infinitives — a feature unique to Portuguese among Romance languages."""
        out = []
        for tok in tokens:
            surface = _text(tok)
            low = surface.lower()
            if len(low) < 5:
                continue
            if not any(low.endswith(suf) for suf in _PERSONAL_INF_SUFFIXES):
                continue
            cf = f"nuance:pt:personal_infinitive:{low}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=surface,
                type="nuance",
                label=surface,
                lesson_data={
                    "nuance_type": "personal_infinitive",
                    "explanation": (
                        "The inflected (personal) infinitive is unique to Portuguese among "
                        "Romance languages. It agrees with its own subject in person and number: "
                        "«para eles chegarem» (for them to arrive) vs «para eu chegar». "
                        "It is obligatory when the infinitive clause has a different subject "
                        "from the main clause, and optional when subjects are the same."
                    ),
                    "register": "neutral",
                    "learner_level": "B2",
                    "source": "heuristic",
                    "surface": surface,
                },
                confidence=0.65,
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
