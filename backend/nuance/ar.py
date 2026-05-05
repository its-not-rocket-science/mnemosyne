"""Arabic nuance extractor — definite article, negation markers, root-pattern note."""
from __future__ import annotations

import re
from typing import Any

from backend.schemas.parse import CandidateObject, RelationHint

# Strip tashkeel (Arabic short-vowel diacriticals) for surface matching
_TASHKEEL_RE = re.compile(
    r"[ً-ٟؐ-ؚۖ-ۜ۟-۪ۤۧۨ-ۭ]"
)


def _strip(s: str) -> str:
    return _TASHKEEL_RE.sub("", s)


_NEGATION: dict[str, tuple[str, str]] = {
    "لا": (
        "negation_la",
        "«لا» negates present/future verbs and makes categorical negations: "
        "لا أعرف (I don't know). Also used for nominal negation: لا إله إلا الله.",
    ),
    "لم": (
        "negation_lam",
        "«لم» negates past actions and requires the jussive (مجزوم) verb form: "
        "لم يذهب (he didn't go). It shifts present-tense morphology to past meaning.",
    ),
    "لن": (
        "negation_lan",
        "«لن» negates future actions using the subjunctive (منصوب) mood: "
        "لن يذهب (he will not go). It is the emphatic future negation particle.",
    ),
    "ما": (
        "negation_ma",
        "«ما» negates past verbs (Classical/literary) or nominal predicates. "
        "In MSA it also functions as 'whatever/that which' (relative pronoun).",
    ),
    "ليس": (
        "negation_laysa",
        "«ليس» is a defective verb meaning 'to not be'. It negates nominal sentences "
        "in the present tense and governs accusative on its predicate: "
        "ليسَ هذا صحيحًا (This is not correct).",
    ),
}

_DEF_ARTICLE_RE = re.compile(r"^ال")


def _tok_text(tok: Any) -> str:
    return tok.text if hasattr(tok, "text") else str(tok)


class ArabicNuanceExtractor:
    language = "ar"

    def extract_nuance(
        self,
        sentence: str,
        tokens: list[Any],
        candidates: list[CandidateObject],
        language: str,
    ) -> list[CandidateObject]:
        out: list[CandidateObject] = []
        seen: set[str] = set()
        out.extend(self._definite_article(tokens, seen))
        out.extend(self._negation_markers(tokens, seen))
        out.extend(self._root_pattern(candidates, seen))
        return out

    def _definite_article(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        cf = "nuance:ar:definite_article"
        for tok in tokens:
            surface = _tok_text(tok)
            if not _DEF_ARTICLE_RE.match(_strip(surface)):
                continue
            if cf in seen:
                break
            seen.add(cf)
            return [CandidateObject(
                canonical_form=cf,
                surface_form=surface,
                type="nuance",
                label=surface,
                lesson_data={
                    "nuance_type": "definite_article",
                    "explanation": (
                        "«ال» (al-) is the Arabic definite article, a prefix clitic. "
                        "It assimilates to following sun letters (حروف شمسية): "
                        "الشمس → ash-shams (not *al-shams). "
                        "Moon letters (حروف قمرية) do not trigger assimilation: "
                        "القمر → al-qamar. The article is invariable for gender and case."
                    ),
                    "register": "neutral",
                    "learner_level": "A1",
                    "source": "heuristic",
                },
                confidence=0.90,
            )]
        return []

    def _negation_markers(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for tok in tokens:
            surface = _tok_text(tok)
            stripped = _strip(surface)
            if stripped not in _NEGATION:
                continue
            nuance_type, explanation = _NEGATION[stripped]
            cf = f"nuance:ar:{nuance_type}"
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
                    "particle": stripped,
                },
                confidence=0.85,
            ))
        return out

    def _root_pattern(
        self, candidates: list[CandidateObject], seen: set[str]
    ) -> list[CandidateObject]:
        """Fire when a candidate already carries root metadata (e.g. from ArabicAdapter)."""
        out = []
        for c in candidates:
            root = c.lesson_data.get("root")
            if not root:
                continue
            form = c.lesson_data.get("form") or c.lesson_data.get("pattern")
            cf = f"nuance:ar:root_pattern:{root}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=c.surface_form,
                type="nuance",
                label=c.label,
                lesson_data={
                    "nuance_type": "root_pattern",
                    "explanation": (
                        f"Arabic root «{root}» participates in the consonantal root-and-pattern "
                        "system. Words are built by inserting a root (usually 3 consonants) into "
                        "a pattern (وزن wazn): فعل (verb), فاعل (agent), مفعول (object/result). "
                        + (f"This word follows pattern «{form}»." if form else "")
                    ),
                    "register": "neutral",
                    "learner_level": "B2",
                    "source": "plugin",
                    "root": root,
                    "form": form,
                },
                confidence=0.80,
                relation_hints=[RelationHint(
                    relation_type="nuance_of",
                    target_canonical_form=c.canonical_form,
                    target_type=c.type,
                )],
            ))
        return out
