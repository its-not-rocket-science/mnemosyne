"""Hebrew nuance extractor — definite prefix, waw conjunction, prefix decomposition, binyan, verb template, Biblical register."""
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
        out.extend(self._prefix_decomposition(candidates, seen))
        out.extend(self._binyan_note(candidates, seen))
        out.extend(self._verb_template(candidates, seen))
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

    _PREFIX_MEANINGS: dict[str, str] = {
        "ב":  "«ב-» (be-) is the inseparable preposition 'in', 'at', 'with', or 'by'. "
              "It attaches directly to nouns without a space: ספר → בספר (in a book).",
        "ו":  "«ו-» (ve-/u-) is the coordinating conjunction 'and'. "
              "It attaches to the following word: ספר → וספר (and a book). "
              "In Biblical Hebrew the waw-consecutive (וַיִּ) sequences narrative verb-clauses.",
        "ה":  "«ה-» (ha-) is the definite article 'the'. "
              "It attaches directly to nouns and adjectives: ספר → הספר (the book). "
              "Adjectives in a definite noun phrase must also carry ה-.",
        "ל":  "«ל-» (le-) is the inseparable preposition 'to', 'for', or 'of'. "
              "It attaches directly to nouns: ספר → לספר (to a book; to read).",
        "כ":  "«כ-» (ke-/ki-) is the inseparable preposition 'like', 'as', or 'approximately'. "
              "It attaches directly: ספר → כספר (like a book).",
        "מ":  "«מ-» (me-/mi-) is the inseparable preposition 'from', 'than', or 'out of'. "
              "It attaches directly: ספר → מספר (from a book).",
        "ש":  "«ש-» (she-) is the relative pronoun / complementiser 'that', 'which', 'who'. "
              "It attaches to the following word: ידעתי שהספר (I knew that the book …).",
        "מה": "«מה-» combines מ- (from) and ה- (the): 'from the'. "
              "It appears before certain consonants: מהבית (from the house).",
        "שה": "«שה-» combines ש- (that/which) and ה- (the): 'that the'. "
              "It introduces relative clauses on definite nouns: שהספר (that the book …).",
        "וה": "«וה-» combines ו- (and) and ה- (the): 'and the'. "
              "Common in coordination: וְהַסֵּפֶר (and the book).",
        "בה": "«בה-» combines ב- (in) and ה- (the): 'in the'. "
              "It attaches before nouns: בהבית (in the house).",
        "כה": "«כה-» combines כ- (like) and ה- (the): 'like the'.",
        "לה": "«לה-» combines ל- (to/for) and ה- (the): 'to the'.",
    }

    def _prefix_decomposition(
        self, candidates: list[CandidateObject], seen: set[str]
    ) -> list[CandidateObject]:
        """Fire when a vocabulary candidate carries a non-empty `prefix` field.

        Works in heuristic fallback mode — HebSpaCy is NOT required.
        """
        out = []
        for c in candidates:
            if c.type != "vocabulary":
                continue
            prefix = c.lesson_data.get("prefix", "")
            if not prefix:
                continue
            cf = f"nuance:he:prefix_decomposition:{prefix}"
            if cf in seen:
                continue
            seen.add(cf)
            explanation = self._PREFIX_MEANINGS.get(
                prefix,
                f"«{prefix}-» is an inseparable Hebrew prefix that attaches "
                "directly to the following word without a space.",
            )
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=c.surface_form,
                type="nuance",
                label=c.label,
                lesson_data={
                    "nuance_type": "prefix_decomposition",
                    "explanation": explanation,
                    "register": "neutral",
                    "learner_level": "A2",
                    "source": "heuristic",
                    "prefix": prefix,
                    "stem": c.lesson_data.get("lemma", ""),
                },
                confidence=0.80,
            ))
        return out

    def _verb_template(
        self, candidates: list[CandidateObject], seen: set[str]
    ) -> list[CandidateObject]:
        """Fire when a vocabulary candidate carries both binyan AND tense (requires HebSpaCy)."""
        out = []
        for c in candidates:
            if c.type != "vocabulary":
                continue
            binyan = c.lesson_data.get("binyan", "")
            tense = c.lesson_data.get("tense", "")
            if not binyan or not tense:
                continue
            cf = f"nuance:he:verb_template:{binyan.lower()}:{tense.lower()}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=c.surface_form,
                type="nuance",
                label=c.label,
                lesson_data={
                    "nuance_type": "verb_template",
                    "explanation": (
                        f"«{c.surface_form}» is a {tense.lower()} verb in the "
                        f"{binyan} binyan. "
                        "Each binyan carries a consistent vowel pattern and semantic role: "
                        "Pa'al (simple active), Pi'el (intensive/denominative), "
                        "Hif'il (causative), Nif'al (passive/reflexive), "
                        "Hitpa'el (reflexive/reciprocal). "
                        "The binyan + tense combination determines the full inflectional paradigm."
                    ),
                    "register": "neutral",
                    "learner_level": "B1",
                    "source": "plugin",
                    "binyan": binyan,
                    "tense": tense,
                },
                confidence=0.85,
                relation_hints=[RelationHint(
                    relation_type="nuance_of",
                    target_canonical_form=c.canonical_form,
                    target_type=c.type,
                )],
            ))
        return out

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
