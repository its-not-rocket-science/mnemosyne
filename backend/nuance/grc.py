"""Koine/Classical Greek nuance extractor — discourse particles, negation, definite article."""
from __future__ import annotations

import unicodedata
from typing import Any

from backend.schemas.parse import CandidateObject, RelationHint


def _normalize(s: str) -> str:
    """Strip polytonic diacriticals and return lowercase for matching."""
    nfd = unicodedata.normalize("NFD", s)
    return "".join(
        ch for ch in nfd
        if unicodedata.category(ch) not in ("Mn", "Lm")
    ).lower()


_DISCOURSE_PARTICLES: dict[str, str] = {
    "μεν":    "affirmative/anticipatory — introduces a clause to be contrasted by δέ",
    "δε":     "mild adversative/continuative — 'but', 'and', 'then' (postpositive)",
    "γαρ":    "causal/explanatory — 'for', 'because', 'indeed' (postpositive)",
    "ουν":    "inferential — 'therefore', 'then', 'accordingly' (postpositive)",
    "αλλα":   "strong adversative — 'but', 'rather', 'on the contrary'",
    "και":    "additive — 'and', 'also', 'even', 'indeed'",
    "τε":     "additive/connective — 'and'; paired as τε…καί ('both…and')",
    "η":      "disjunctive — 'or'; in comparisons: 'than'",
    "οτι":    "declarative/causal — 'that' (indirect statement); 'because'",
    "ει":     "conditional — 'if'; introduces indirect question",
    "αρα":    "inferential — 'then', 'therefore', 'so' (draws a conclusion)",
    "γε":     "intensive/limitative — 'at least', 'indeed', 'even' (emphatic focus)",
    "δη":     "temporal/emphatic — 'indeed', 'now', 'clearly' (adds narrative vividness)",
    "που":    "modal — 'presumably', 'I suppose', 'somewhere' (approximative hedging)",
    "μεντοι": "adversative — 'however', 'and yet' (stronger than μέν alone)",
    "ωστε":   "consecutive/result — 'so that', 'with the result that', 'therefore'",
    "ινα":    "purpose — 'so that', 'in order that' (governs subjunctive/optative)",
}

_NEGATION: dict[str, tuple[str, str]] = {
    "ου": (
        "negation_ou",
        "«οὐ» (οὐκ before smooth vowels, οὐχ before rough breathing) negates indicative "
        "statements of fact. It is the standard negation for assertions. "
        "Example: οὐκ οἶδα (I do not know).",
    ),
    "μη": (
        "negation_me",
        "«μή» negates non-indicative moods (subjunctive, optative, imperative, infinitive, "
        "participle) and introduces negated purpose clauses. "
        "Example: μὴ ποιεῖ τοῦτο (do not do this). "
        "The οὐ/μή distinction is the most systematic feature of Greek negation.",
    ),
}

# Normalized forms of the Greek definite article (all cases/numbers/genders)
_ARTICLE_FORMS = frozenset({
    "ο", "η", "το",           # Nom sg M/F/N
    "τον", "την", "το",       # Acc sg M/F/N
    "του", "της", "του",      # Gen sg M/F/N
    "τω",                     # Dat sg M/N (contracted)
    "τη",                     # Dat sg F
    "οι", "αι", "τα",         # Nom pl M/F/N
    "τους", "τας", "τα",      # Acc pl M/F/N
    "των",                    # Gen pl all genders
    "τοις", "ταις", "τοις",   # Dat pl M/N, F
})


def _text(tok: Any) -> str:
    return tok.text if hasattr(tok, "text") else str(tok)


class AncientGreekNuanceExtractor:
    language = "grc"

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
        out.extend(self._negation(tokens, seen))
        out.extend(self._article_note(tokens, seen))
        return out

    def _discourse_particles(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for tok in tokens:
            surface = _text(tok)
            norm = _normalize(surface)
            if norm not in _DISCOURSE_PARTICLES:
                continue
            cf = f"nuance:grc:particle:{norm}"
            if cf in seen:
                continue
            seen.add(cf)
            meaning = _DISCOURSE_PARTICLES[norm]
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=surface,
                type="nuance",
                label=surface,
                lesson_data={
                    "nuance_type": "discourse_particle",
                    "explanation": (
                        f"«{surface}» (norm: {norm}): {meaning}. "
                        "Greek discourse particles encode the speaker's logical stance and "
                        "pragmatic intent. Postpositive particles (δέ, γάρ, οὖν, τε) "
                        "cannot stand first in their clause — a critical reading skill."
                    ),
                    "register": "neutral",
                    "learner_level": "B1",
                    "source": "heuristic",
                    "particle": norm,
                },
                confidence=0.85,
            ))
        return out

    def _negation(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for tok in tokens:
            surface = _text(tok)
            norm = _normalize(surface)
            # ουκ / ουχ variants: strip trailing κ/χ
            base = norm
            if norm.startswith("ου") and norm not in _NEGATION:
                base = "ου"
            if base not in _NEGATION:
                continue
            nuance_type, explanation = _NEGATION[base]
            cf = f"nuance:grc:{nuance_type}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=surface,
                type="nuance",
                label=surface,
                lesson_data={
                    "nuance_type": nuance_type,
                    "explanation": explanation,
                    "register": "neutral",
                    "learner_level": "A2",
                    "source": "heuristic",
                    "particle": surface,
                },
                confidence=0.85,
            ))
        return out

    def _article_note(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        cf = "nuance:grc:definite_article"
        if cf in seen:
            return []
        for tok in tokens:
            norm = _normalize(_text(tok))
            if norm not in _ARTICLE_FORMS:
                continue
            seen.add(cf)
            return [CandidateObject(
                canonical_form=cf,
                surface_form=_text(tok),
                type="nuance",
                label=_text(tok),
                lesson_data={
                    "nuance_type": "definite_article",
                    "explanation": (
                        "The Greek definite article (ὁ/ἡ/τό) declines for case, number, "
                        "and gender — 24 forms in classical Greek. Unlike English 'the', "
                        "Greek uses the article with abstract nouns, proper names, "
                        "and to substantivize adjectives: ὁ ἀγαθός = 'the good man'. "
                        "Its absence is as meaningful as its presence."
                    ),
                    "register": "neutral",
                    "learner_level": "A2",
                    "source": "heuristic",
                },
                confidence=0.85,
            )]
        return []
