"""Russian nuance extractor — motion verbs, verbal government, etymology, phrase families."""
from __future__ import annotations

from typing import Any

from backend.schemas.parse import CandidateObject, RelationHint

# Paired motion verbs: (unidirectional, multidirectional)
_MOTION_PAIRS: list[tuple[str, str]] = [
    ("идти",   "ходить"),
    ("ехать",  "ездить"),
    ("лететь", "летать"),
    ("плыть",  "плавать"),
    ("нести",  "носить"),
    ("вести",  "водить"),
    ("везти",  "возить"),
    ("бежать", "бегать"),
]

_MOTION_UNI: dict[str, str] = {
    u: f"unidirectional: movement in one direction at a specific moment"
    for u, _ in _MOTION_PAIRS
}
_MOTION_MULTI: dict[str, str] = {
    m: f"multidirectional: habitual, repeated, or back-and-forth movement"
    for _, m in _MOTION_PAIRS
}

_PAIR_MAP: dict[str, str] = {}
for _u, _m in _MOTION_PAIRS:
    _PAIR_MAP[_u] = _m
    _PAIR_MAP[_m] = _u

# Common verbs with non-obvious case government
_VERBAL_GOV: dict[str, tuple[str, str]] = {
    "ждать":          ("genitive",       "«ждать» governs the genitive: ждать автобуса"),
    "бояться":        ("genitive",       "«бояться» governs the genitive: бояться темноты"),
    "слушаться":      ("genitive",       "«слушаться» (obey) governs the genitive"),
    "помогать":       ("dative",         "«помогать» governs the dative: помогать другу"),
    "учить":          ("accusative",     "«учить» (teach/learn) governs the accusative"),
    "интересоваться": ("instrumental",   "«интересоваться» governs the instrumental"),
    "заниматься":     ("instrumental",   "«заниматься» governs the instrumental"),
    "пользоваться":   ("instrumental",   "«пользоваться» governs the instrumental"),
    "гордиться":      ("instrumental",   "«гордиться» governs the instrumental"),
    "руководить":     ("instrumental",   "«руководить» governs the instrumental"),
    "хотеть":         ("accusative/genitive",
                       "«хотеть» takes accusative (concrete) or genitive (abstract/partial)"),
}


def _lemma(c: CandidateObject) -> str:
    return c.lesson_data.get("lemma", c.canonical_form)


class RussianNuanceExtractor:
    language = "ru"

    def extract_nuance(
        self,
        sentence: str,
        tokens: list[Any],
        candidates: list[CandidateObject],
        language: str,
    ) -> list[CandidateObject]:
        out: list[CandidateObject] = []
        seen: set[str] = set()
        out.extend(self._motion_verbs(candidates, seen))
        out.extend(self._verbal_government(candidates, seen))
        out.extend(self._etymology(candidates, seen))
        out.extend(self._phrase_families(tokens))
        return out

    def _motion_verbs(
        self, candidates: list[CandidateObject], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for c in candidates:
            if c.type not in ("vocabulary", "conjugation"):
                continue
            lemma = _lemma(c)
            if lemma in _MOTION_UNI:
                direction = "unidirectional"
                desc = _MOTION_UNI[lemma]
            elif lemma in _MOTION_MULTI:
                direction = "multidirectional"
                desc = _MOTION_MULTI[lemma]
            else:
                continue
            cf = f"nuance:ru:motion_verb:{lemma}"
            if cf in seen:
                continue
            seen.add(cf)
            partner = _PAIR_MAP.get(lemma)
            hints = [RelationHint(
                relation_type="nuance_of",
                target_canonical_form=lemma,
                target_type="vocabulary",
            )]
            if partner:
                hints.append(RelationHint(
                    relation_type="motion_pair",
                    target_canonical_form=partner,
                    target_type="vocabulary",
                ))
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=c.surface_form,
                type="nuance",
                label=c.label,
                lesson_data={
                    "nuance_type": "motion_verb",
                    "explanation": (
                        f"«{lemma}» is a {direction} motion verb: {desc}. "
                        "Russian pairs motion verbs by directionality: unidirectional verbs "
                        "describe a single trip at a given moment; multidirectional verbs "
                        "describe habitual, repeated, or back-and-forth movement."
                        + (f" Its pair is «{partner}»." if partner else "")
                    ),
                    "register": "neutral",
                    "learner_level": "B1",
                    "source": "heuristic",
                    "lemma": lemma,
                    "direction_type": direction,
                    "partner_lemma": partner,
                },
                confidence=0.85,
                relation_hints=hints,
            ))
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
            cf = f"nuance:ru:verbal_government:{lemma}"
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
                        "Russian verbs govern a specific case for their direct/indirect objects — "
                        "this is an inherent property of the verb, not predictable from context. "
                        f"Required case: {required_case}."
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
        def _text(tok: Any) -> str:
            return tok.text if hasattr(tok, "text") else str(tok)
        return match_phrase_families([_text(t) for t in tokens], self.language)
