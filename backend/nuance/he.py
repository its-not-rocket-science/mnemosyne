"""Hebrew nuance extractor — definite prefix, waw conjunction, binyan, Biblical register."""
from __future__ import annotations

import re
from typing import Any

from backend.schemas.parse import CandidateObject, RelationHint

# Strip nikud (Hebrew vowel points) and cantillation marks
_NIKUD_RE = re.compile(
    r"[֑-ְ֯-ׇֽֿׁׂׅׄ]"
)

_HEBREW_CONSONANTS = frozenset("אבגדהוזחטיכלמנסעפצקרשת")


def _strip(s: str) -> str:
    return _NIKUD_RE.sub("", s)


def _tok_text(tok: Any) -> str:
    return tok.text if hasattr(tok, "text") else str(tok)


class HebrewNuanceExtractor:
    language = "he"

    def extract_nuance(
        self,
        sentence: str,
        tokens: list[Any],
        candidates: list[CandidateObject],
        language: str,
    ) -> list[CandidateObject]:
        out: list[CandidateObject] = []
        seen: set[str] = set()
        out.extend(self._definite_prefix(tokens, seen))
        out.extend(self._waw_conjunction(tokens, seen))
        out.extend(self._binyan_note(candidates, seen))
        out.extend(self._biblical_register(sentence, seen))
        return out

    def _definite_prefix(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        cf = "nuance:he:definite_prefix"
        for tok in tokens:
            surface = _tok_text(tok)
            stripped = _strip(surface)
            if len(stripped) < 2:
                continue
            if stripped[0] != "ה" or stripped[1] not in _HEBREW_CONSONANTS:
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
                    "nuance_type": "definite_prefix",
                    "explanation": (
                        "«ה-» (he) is the Hebrew definite article, a prefix that attaches "
                        "directly to nouns and adjectives: ספר → הספר (the book). "
                        "Adjectives modifying a definite noun must also carry ה-. "
                        "The article triggers vowel changes (dagesh or patah) in the following letter."
                    ),
                    "register": "neutral",
                    "learner_level": "A1",
                    "source": "heuristic",
                },
                confidence=0.75,
            )]
        return []

    def _waw_conjunction(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        cf = "nuance:he:waw_conjunction"
        for tok in tokens:
            surface = _tok_text(tok)
            stripped = _strip(surface)
            if not stripped.startswith("ו") or len(stripped) < 2:
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
                    "nuance_type": "waw_conjunction",
                    "explanation": (
                        "«ו-» (vav/waw) prefixed to a word is the coordinating conjunction 'and'. "
                        "In Biblical Hebrew the waw-consecutive (וַיִּ / וְ) is a distinctive "
                        "narrative device that sequences verb-clauses. "
                        "In Modern Hebrew it is a simple coordinating conjunction."
                    ),
                    "register": "neutral",
                    "learner_level": "A1",
                    "source": "heuristic",
                },
                confidence=0.80,
            )]
        return []

    def _binyan_note(
        self, candidates: list[CandidateObject], seen: set[str]
    ) -> list[CandidateObject]:
        """Fire when a candidate carries binyan metadata (requires morphological plugin)."""
        out = []
        for c in candidates:
            binyan = c.lesson_data.get("binyan")
            if not binyan:
                continue
            cf = f"nuance:he:binyan:{binyan}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=c.surface_form,
                type="nuance",
                label=c.label,
                lesson_data={
                    "nuance_type": "binyan",
                    "explanation": (
                        f"«{binyan}» is one of the seven Hebrew verb patterns (בניינים binyanim). "
                        "Each binyan encodes voice and valency: "
                        "Pa'al (simple active), Nif'al (passive/reflexive), "
                        "Pi'el (intensive active), Pu'al (intensive passive), "
                        "Hitpa'el (reflexive/reciprocal), Hif'il (causative active), "
                        "Huf'al (causative passive). "
                        "Knowing the binyan is essential for reading Hebrew verbs correctly."
                    ),
                    "register": "neutral",
                    "learner_level": "B1",
                    "source": "plugin",
                    "binyan": binyan,
                },
                confidence=0.85,
                relation_hints=[RelationHint(
                    relation_type="nuance_of",
                    target_canonical_form=c.canonical_form,
                    target_type=c.type,
                )],
            ))
        return out

    def _biblical_register(
        self, sentence: str, seen: set[str]
    ) -> list[CandidateObject]:
        """Detect cantillation marks → Biblical Hebrew register note."""
        has_cantillation = any("֑" <= ch <= "֯" for ch in sentence)
        if not has_cantillation:
            return []
        cf = "nuance:he:biblical_register"
        if cf in seen:
            return []
        seen.add(cf)
        return [CandidateObject(
            canonical_form=cf,
            surface_form="",
            type="nuance",
            label="biblical register",
            lesson_data={
                "nuance_type": "biblical_register",
                "explanation": (
                    "Cantillation marks (טַעֲמֵי הַמִּקְרָא te'amei hamikra) indicate "
                    "Biblical Hebrew text. Biblical Hebrew differs from Modern Hebrew "
                    "in its verbal system (waw-consecutive), vocabulary, and syntax. "
                    "Cantillation marks serve both as musical notation and syntactic "
                    "punctuation in the Masoretic text."
                ),
                "register": "liturgical",
                "learner_level": "C2",
                "source": "heuristic",
            },
            confidence=0.95,
        )]
