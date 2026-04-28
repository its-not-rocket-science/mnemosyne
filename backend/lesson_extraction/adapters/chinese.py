from __future__ import annotations

import re

from backend.schemas.parse import CandidateObject
from .base import LessonExtractionAdapter
from ..types import PedagogyTag, with_pedagogy

_HSK_RE = re.compile(r"HSK\s*([1-6])|HSK([1-6])", re.I)

_PARTICLES: dict[str, tuple[str, str, int]] = {
    "了": ("aspect_particle_le", "marks completed action or changed state", 2),
    "着": ("aspect_particle_zhe", "marks an ongoing state or manner", 3),
    "过": ("experiential_guo", "marks past experience", 3),
    "把": ("ba_construction", "foregrounds what happens to the object", 4),
    "被": ("bei_passive", "marks passive or affected perspective", 4),
    "吗": ("yes_no_question_particle", "turns a statement into a yes/no question", 1),
    "呢": ("topic_followup_particle", "asks about a known topic or continuation", 2),
    "的": ("de_modifier_particle", "links modifiers to nouns or forms nominal expressions", 1),
    "地": ("de_adverbial_particle", "links adverbial modifiers to verbs", 3),
    "得": ("de_complement_particle", "introduces degree or result complements", 3),
}


class ChineseAdapter(LessonExtractionAdapter):
    language = "zh"

    def enrich_existing(self, candidates: list[CandidateObject], sentence_text: str) -> list[CandidateObject]:
        enriched: list[CandidateObject] = []

        for cand in candidates:
            data = dict(cand.lesson_data or {})
            hsk_level = self._hsk_level(data)
            level = hsk_level or self._level_from_candidate(cand)

            if cand.type == "vocabulary":
                tag = PedagogyTag(
                    family="vocabulary",
                    skill="hsk_vocabulary" if hsk_level else "segmented_word",
                    level=level,
                    why_it_matters=(
                        f"This is an HSK {hsk_level} word, so it belongs in a standard Mandarin progression."
                        if hsk_level
                        else "Mandarin words are not separated by spaces, so recognizing this segment is essential."
                    ),
                    prompt_hint="Notice the word boundary, pronunciation, and meaning.",
                    source="lesson_extraction",
                )
                extra = {}
                if hsk_level:
                    extra["hsk_level"] = hsk_level
                    extra["level"] = level
                enriched.append(cand.model_copy(update={"lesson_data": with_pedagogy(data, tag, extra=extra)}))
            else:
                enriched.append(super()._default_enrich(cand))

        return enriched

    def derive_additional(self, candidates: list[CandidateObject], sentence_text: str) -> list[CandidateObject]:
        extra: list[CandidateObject] = []
        seen: set[str] = set()

        # Particle grammar objects from sentence surface.
        for char, (skill, note, level) in _PARTICLES.items():
            if char not in sentence_text or char in seen:
                continue
            seen.add(char)
            tag = PedagogyTag(
                family="semantic_pattern",
                skill=skill,
                level=level,
                why_it_matters=f"“{char}” is a high-value Mandarin grammar particle: it {note}.",
                prompt_hint=f"Look at what changes in the sentence when “{char}” appears.",
                source="lesson_extraction",
            )
            extra.append(CandidateObject(
                canonical_form=f"grammar:zh:{skill}:{char}",
                surface_form=char,
                type="grammar",
                label=char,
                lesson_data=with_pedagogy({
                    "grammar_type": skill,
                    "particle": char,
                    "note": note,
                }, tag),
                confidence=0.78,
            ))

        # Character-level script objects for short vocabulary items.
        for cand in candidates:
            if cand.type != "vocabulary":
                continue
            surface = cand.surface_form or cand.label
            chars = [ch for ch in surface if "\u4e00" <= ch <= "\u9fff"]
            if len(chars) == 0 or len(chars) > 4:
                continue
            for ch in chars:
                key = f"script:zh:{ch}"
                if key in seen:
                    continue
                seen.add(key)
                tag = PedagogyTag(
                    family="script",
                    skill="hanzi_character",
                    level=1,
                    why_it_matters="Recognizing recurring characters helps learners remember compounds and word families.",
                    prompt_hint="Look for this character inside other words.",
                    source="lesson_extraction",
                )
                extra.append(CandidateObject(
                    canonical_form=key,
                    surface_form=ch,
                    type="script",
                    label=ch,
                    lesson_data=with_pedagogy({
                        "character": ch,
                        "notes": "Character extracted from a parsed word.",
                    }, tag),
                    confidence=0.65,
                ))

            pinyin = (cand.lesson_data or {}).get("pinyin") or (cand.lesson_data or {}).get("romanized")
            if pinyin:
                key = f"translit:zh:{surface}:{pinyin}"
                if key not in seen:
                    seen.add(key)
                    tag = PedagogyTag(
                        family="transliteration",
                        skill="pinyin",
                        level=1,
                        why_it_matters="Pinyin connects characters to pronunciation and tone.",
                        prompt_hint="Say the pinyin, then match it back to the characters.",
                        source="lesson_extraction",
                    )
                    extra.append(CandidateObject(
                        canonical_form=key,
                        surface_form=surface,
                        type="transliteration",
                        label=surface,
                        lesson_data=with_pedagogy({
                            "native_form": surface,
                            "romanized": pinyin,
                            "scheme": "pinyin",
                        }, tag),
                        confidence=0.80,
                    ))

        return extra

    def _hsk_level(self, data: dict) -> int | None:
        raw = data.get("hsk_level") or data.get("hsk") or data.get("level")
        if raw is None:
            return None
        if isinstance(raw, int):
            return raw if 1 <= raw <= 6 else None
        match = _HSK_RE.search(str(raw))
        if match:
            return int(match.group(1) or match.group(2))
        try:
            value = int(str(raw))
            return value if 1 <= value <= 6 else None
        except Exception:
            return None
