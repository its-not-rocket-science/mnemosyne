"""German nuance extractor — modal particles, separable verbs, Wechselpräpositionen, etymology, phrase families."""
from __future__ import annotations

from typing import Any

from backend.schemas.parse import CandidateObject, RelationHint

_MODAL_PARTICLES: dict[str, str] = {
    "ja":         "marks shared assumption or mild surprise; 'you know', 'obviously'",
    "doch":       "contradicts an assumption, adds insistence, or softens a command",
    "mal":        "softens requests or commands; purely conversational, no literal meaning",
    "halt":       "marks resignation or self-evidence (Southern German register); ≈ 'just'",
    "eben":       "marks inevitability or self-evidence; often interchangeable with halt",
    "wohl":       "expresses probability or polite uncertainty; 'probably', 'I suppose'",
    "denn":       "softens questions, expresses curiosity or mild impatience",
    "schon":      "offers reassurance; 'it'll be fine', 'that should count', 'already'",
    "eigentlich": "marks a polite reality-check; 'actually', 'in principle'",
    "bloß":       "adds urgency or warning; 'just', 'don't you dare'",
    "etwa":       "in questions: 'by any chance?', 'surely not?'",
    "ruhig":      "gives permission or encouragement; 'go ahead and', 'feel free to'",
    "nur":        "restricts scope or adds pressure; 'only'; in questions: 'why on earth'",
}

_WECHSEL_PREPS = frozenset({
    "in", "an", "auf", "über", "unter", "vor", "hinter", "neben", "zwischen",
})


def _text(tok: Any) -> str:
    return tok.text if hasattr(tok, "text") else str(tok)


def _dep(tok: Any) -> str:
    return getattr(tok, "dep_", "")


class GermanNuanceExtractor:
    language = "de"

    def extract_nuance(
        self,
        sentence: str,
        tokens: list[Any],
        candidates: list[CandidateObject],
        language: str,
    ) -> list[CandidateObject]:
        out: list[CandidateObject] = []
        seen: set[str] = set()
        out.extend(self._modal_particles(tokens, seen))
        out.extend(self._separable_verb(tokens, seen))
        out.extend(self._wechsel_preps(tokens, seen))
        out.extend(self._etymology(candidates, seen))
        out.extend(self._phrase_families(tokens))
        return out

    def _modal_particles(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for tok in tokens:
            low = _text(tok).lower()
            if low not in _MODAL_PARTICLES:
                continue
            cf = f"nuance:de:modal_particle:{low}"
            if cf in seen:
                continue
            seen.add(cf)
            meaning = _MODAL_PARTICLES[low]
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=_text(tok),
                type="nuance",
                label=_text(tok),
                lesson_data={
                    "nuance_type": "modal_particle",
                    "explanation": (
                        f"«{low}» as a Modalpartikel (modal/flavoring particle): {meaning}. "
                        "Modal particles are unstressed and resist literal translation — they "
                        "encode the speaker's attitude toward the utterance. Mastering them "
                        "is central to sounding natural in German conversation."
                    ),
                    "register": "neutral",
                    "learner_level": "B2",
                    "source": "heuristic",
                    "particle": low,
                },
                confidence=0.65,
            ))
        return out

    def _separable_verb(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        """Detect detached verb prefixes via spaCy dep=svp label."""
        out = []
        for tok in tokens:
            if _dep(tok) != "svp":
                continue
            surface = _text(tok)
            low = surface.lower()
            cf = f"nuance:de:separable_verb:{low}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=surface,
                type="nuance",
                label=surface,
                lesson_data={
                    "nuance_type": "separable_verb",
                    "explanation": (
                        f"«{surface}» is a separable verb prefix (trennbares Präfix). "
                        "In main clauses the prefix detaches from the verb stem and moves "
                        "to clause-final position: «anrufen» → «Ich rufe dich an». "
                        "The prefix often changes the base verb's meaning fundamentally."
                    ),
                    "register": "neutral",
                    "learner_level": "A2",
                    "source": "plugin",
                    "prefix": low,
                },
                confidence=0.90,
            ))
        return out

    def _wechsel_preps(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for tok in tokens:
            low = _text(tok).lower()
            if low not in _WECHSEL_PREPS:
                continue
            cf = f"nuance:de:wechselpraep:{low}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=_text(tok),
                type="nuance",
                label=_text(tok),
                lesson_data={
                    "nuance_type": "two_way_preposition",
                    "explanation": (
                        f"«{low}» is a Wechselpräposition (two-way preposition). "
                        "It governs the accusative for directed movement (Wohin? — where to?): "
                        "«Ich lege das Buch in die Tasche». "
                        "It governs the dative for static location (Wo? — where?): "
                        "«Das Buch liegt in der Tasche»."
                    ),
                    "register": "neutral",
                    "learner_level": "A2",
                    "source": "heuristic",
                    "preposition": low,
                },
                confidence=0.80,
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
