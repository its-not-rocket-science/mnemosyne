from __future__ import annotations

import re

from backend.schemas.parse import CandidateObject
from .base import LessonExtractionAdapter
from ..types import PedagogyTag, with_pedagogy

_PARTICLES: dict[str, tuple[str, str, int]] = {
    "は": ("topic_particle_wa", "marks the topic — what the sentence is about", 1),
    "が": ("subject_particle_ga", "marks the grammatical subject or new information", 1),
    "を": ("object_particle_o", "marks the direct object", 1),
    "に": ("target_time_location_particle_ni", "marks target, time, location, or indirect object", 2),
    "で": ("means_location_particle_de", "marks location of action or means/instrument", 2),
    "へ": ("direction_particle_e", "marks direction toward", 2),
    "と": ("quotation_and_with_particle_to", "marks quotation, pairing, or accompaniment", 2),
    "も": ("also_particle_mo", "means also/even", 1),
    "の": ("possessive_nominal_particle_no", "links nouns or nominalizes", 1),
    "から": ("source_particle_kara", "marks from/source or because", 2),
    "まで": ("limit_particle_made", "marks until/up to", 2),
}

_KANA_RE = re.compile(r"[\u3040-\u30ff]")
_KANJI_RE = re.compile(r"[\u4e00-\u9fff]")


class JapaneseAdapter(LessonExtractionAdapter):
    language = "ja"

    def enrich_existing(self, candidates: list[CandidateObject], sentence_text: str) -> list[CandidateObject]:
        enriched: list[CandidateObject] = []

        for cand in candidates:
            data = dict(cand.lesson_data or {})
            if cand.type in {"vocabulary", "conjugation"}:
                skill = "lemma"
                level = self._level_from_candidate(cand)
                if verb_class := data.get("verb_class") or data.get("conjugation_class"):
                    skill = f"verb_class:{verb_class}"
                    level = max(level, 2)
                elif data.get("pos") in {"VERB", "AUX"}:
                    skill = "verb_morphology"
                    level = max(level, 2)

                tag = PedagogyTag(
                    family="morphology" if cand.type == "conjugation" else "vocabulary",
                    skill=skill,
                    level=level,
                    why_it_matters="Japanese meaning depends heavily on particles, verb endings, and reading choices.",
                    prompt_hint="Compare the written form, reading, and base form.",
                    source="lesson_extraction",
                )
                enriched.append(cand.model_copy(update={"lesson_data": with_pedagogy(data, tag)}))
            else:
                enriched.append(super()._default_enrich(cand))

        return enriched

    def derive_additional(self, candidates: list[CandidateObject], sentence_text: str) -> list[CandidateObject]:
        extra: list[CandidateObject] = []
        seen: set[str] = set()

        for particle, (skill, note, level) in sorted(_PARTICLES.items(), key=lambda kv: len(kv[0]), reverse=True):
            if particle not in sentence_text:
                continue
            key = f"grammar:ja:{skill}:{particle}"
            if key in seen:
                continue
            seen.add(key)
            tag = PedagogyTag(
                family="semantic_pattern",
                skill=skill,
                level=level,
                why_it_matters=f"“{particle}” is a core Japanese particle: it {note}.",
                prompt_hint=f"Find what phrase “{particle}” attaches to.",
                source="lesson_extraction",
            )
            extra.append(CandidateObject(
                canonical_form=key,
                surface_form=particle,
                type="grammar",
                label=particle,
                lesson_data=with_pedagogy({
                    "grammar_type": skill,
                    "particle": particle,
                    "note": note,
                }, tag),
                confidence=0.72,
            ))

        for cand in candidates:
            surface = cand.surface_form or cand.label
            reading = (
                (cand.lesson_data or {}).get("reading")
                or (cand.lesson_data or {}).get("kana")
                or (cand.lesson_data or {}).get("romaji")
                or (cand.lesson_data or {}).get("romanized")
            )
            if reading:
                key = f"translit:ja:{surface}:{reading}"
                if key not in seen:
                    seen.add(key)
                    tag = PedagogyTag(
                        family="transliteration",
                        skill="reading",
                        level=1,
                        why_it_matters="Japanese often separates written form from reading; learning both improves recall.",
                        prompt_hint="Read the native form aloud, then check the romanized or kana reading.",
                        source="lesson_extraction",
                    )
                    extra.append(CandidateObject(
                        canonical_form=key,
                        surface_form=surface,
                        type="transliteration",
                        label=surface,
                        lesson_data=with_pedagogy({
                            "native_form": surface,
                            "romanized": reading,
                            "scheme": "japanese_reading",
                        }, tag),
                        confidence=0.78,
                    ))

            # Script items: one object per kanji in short words.
            kanji = _KANJI_RE.findall(surface)
            if 0 < len(kanji) <= 4:
                for ch in kanji:
                    key = f"script:ja:{ch}"
                    if key in seen:
                        continue
                    seen.add(key)
                    tag = PedagogyTag(
                        family="script",
                        skill="kanji",
                        level=2,
                        why_it_matters="Kanji recur across word families; recognizing them makes vocabulary less arbitrary.",
                        prompt_hint="Look for this kanji in related words.",
                        source="lesson_extraction",
                    )
                    extra.append(CandidateObject(
                        canonical_form=key,
                        surface_form=ch,
                        type="script",
                        label=ch,
                        lesson_data=with_pedagogy({
                            "character": ch,
                            "notes": "Kanji extracted from a parsed word.",
                        }, tag),
                        confidence=0.65,
                    ))

        return extra
