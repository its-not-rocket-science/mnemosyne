"""Latin nuance extractor — discourse particles, enclitic -que, classical register."""
from __future__ import annotations

from typing import Any

from backend.schemas.parse import CandidateObject, RelationHint

_DISCOURSE_PARTICLES: dict[str, str] = {
    "autem":   "adversative/continuative — 'however', 'but', 'on the other hand' (postpositive)",
    "enim":    "explanatory — 'for', 'indeed', 'you see' (postpositive; explains what precedes)",
    "igitur":  "inferential — 'therefore', 'consequently', 'so then'",
    "ergo":    "inferential — 'therefore', 'then', 'consequently'",
    "itaque":  "inferential — 'and so', 'accordingly', 'therefore'",
    "sed":     "adversative — 'but', 'however', 'yet'",
    "nam":     "causal — 'for', 'for indeed' (introduces an explanation; typically clause-initial)",
    "dum":     "temporal/conditional — 'while', 'as long as', 'until', 'provided that'",
    "tamen":   "concessive — 'nevertheless', 'yet', 'still', 'however'",
    "quidem":  "restrictive/emphatic — 'indeed', 'at least', 'to be sure' (postpositive)",
    "vero":    "emphatic/adversative — 'indeed', 'truly', 'but in fact' (postpositive)",
    "nisi":    "conditional/exceptive — 'unless', 'if not', 'except'",
    "vel":     "disjunctive — 'or' (free choice); intensifying: 'even', 'or rather'",
    "aut":     "disjunctive — 'or' (exclusive); 'either…or' in aut…aut constructions",
    "sic":     "demonstrative adverb — 'thus', 'in this way', 'so'",
    "ita":     "demonstrative adverb — 'so', 'thus', 'in this way' (often correlative with ut)",
    "nunc":    "temporal — 'now', 'at this time'",
    "iam":     "temporal — 'already', 'now', 'soon', 'by now'",
    "etiam":   "additive — 'also', 'even', 'yet', 'still'",
    "quoque":  "additive — 'also', 'too', 'likewise' (postpositive)",
    "neque":   "negative conjunction — 'and not', 'nor'",
    "nec":     "negative conjunction — 'and not', 'nor' (shortened form of neque)",
    "at":      "strong adversative — 'but', 'yet', 'but at least' (introduces counterargument)",
    "atque":   "additive — 'and', 'and also', 'and even' (stronger than et)",
    "ac":      "additive — 'and', 'and also' (shortened form of atque, used before consonants)",
    "et":      "additive — 'and'; also intensive: 'even', 'and in fact'",
    "ut":      "subordinating — purpose ('so that'), comparison ('as'), temporal ('when')",
    "cum":     "temporal/causal/concessive — 'when', 'since', 'although'",
    "si":      "conditional — 'if'",
}

_MACRON_CHARS = frozenset("āēīōūĀĒĪŌŪ")


def _text(tok: Any) -> str:
    return tok.text if hasattr(tok, "text") else str(tok)


class LatinNuanceExtractor:
    language = "la"

    def extract_nuance(
        self,
        sentence: str,
        tokens: list[Any],
        candidates: list[CandidateObject],
        language: str,
    ) -> list[CandidateObject]:
        out: list[CandidateObject] = []
        seen: set[str] = set()
        out.extend(self._discourse_particles(tokens, seen))
        out.extend(self._enclitic_que(tokens, seen))
        out.extend(self._classical_register(sentence, seen))
        return out

    def _discourse_particles(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for tok in tokens:
            low = _text(tok).lower().rstrip(".,;:!?")
            if low not in _DISCOURSE_PARTICLES:
                continue
            cf = f"nuance:la:discourse_particle:{low}"
            if cf in seen:
                continue
            seen.add(cf)
            meaning = _DISCOURSE_PARTICLES[low]
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=_text(tok),
                type="nuance",
                label=_text(tok),
                lesson_data={
                    "nuance_type": "discourse_particle",
                    "explanation": (
                        f"«{low}»: {meaning}. "
                        "Latin discourse particles and conjunctions structure argument and "
                        "narrative logic. Postpositive particles (autem, enim, quidem, vero, "
                        "quoque) cannot stand first in their clause — an important reading signal."
                    ),
                    "register": "neutral",
                    "learner_level": "B1",
                    "source": "heuristic",
                    "particle": low,
                },
                confidence=0.85,
            ))
        return out

    def _enclitic_que(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for tok in tokens:
            raw = _text(tok)
            low = raw.lower().rstrip(".,;:!?")
            if not low.endswith("que") or len(low) <= 3:
                continue
            host = low[:-3]
            if not host:
                continue
            cf = f"nuance:la:enclitic_que:{low}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=raw,
                type="nuance",
                label=raw,
                lesson_data={
                    "nuance_type": "enclitic_que",
                    "explanation": (
                        f"«-que» enclitic on «{host}»: this suffix meaning 'and' attaches "
                        "to the second of two closely connected elements. "
                        "«Senatus Populusque Romanus» (SPQR) = 'the Senate and People of Rome'. "
                        "-que is more formal than et and implies close logical or semantic connection."
                    ),
                    "register": "formal",
                    "learner_level": "A2",
                    "source": "heuristic",
                    "host_word": host,
                },
                confidence=0.80,
            ))
        return out

    def _classical_register(
        self, sentence: str, seen: set[str]
    ) -> list[CandidateObject]:
        if not any(ch in _MACRON_CHARS for ch in sentence):
            return []
        cf = "nuance:la:classical_register"
        if cf in seen:
            return []
        seen.add(cf)
        return [CandidateObject(
            canonical_form=cf,
            surface_form="",
            type="nuance",
            label="macron notation",
            lesson_data={
                "nuance_type": "classical_register",
                "explanation": (
                    "This text uses macrons (ā, ē, ī, ō, ū) to mark long vowels, "
                    "a feature of Classical Latin pedagogical and critical editions. "
                    "Vowel quantity was phonemically contrastive in Classical Latin: "
                    "mālum (apple) vs. malum (evil). "
                    "Medieval and Church Latin texts typically omit macrons."
                ),
                "register": "classical",
                "learner_level": "B1",
                "source": "heuristic",
            },
            confidence=0.90,
        )]
