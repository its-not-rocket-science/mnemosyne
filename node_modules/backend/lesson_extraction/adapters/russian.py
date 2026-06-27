from __future__ import annotations

from backend.schemas.parse import CandidateObject
from .base import LessonExtractionAdapter
from ..types import PedagogyTag, with_pedagogy


class RussianAdapter(LessonExtractionAdapter):
    language = "ru"

    def enrich_existing(self, candidates: list[CandidateObject], sentence_text: str) -> list[CandidateObject]:
        enriched: list[CandidateObject] = []

        for cand in candidates:
            data = dict(cand.lesson_data or {})
            if cand.type == "conjugation" and data.get("aspect"):
                aspect = str(data["aspect"])
                tag = PedagogyTag(
                    family="morphology",
                    skill=f"russian_aspect:{aspect}",
                    level=3 if aspect in {"perfective", "imperfective"} else 2,
                    why_it_matters="Russian aspect changes whether an action is viewed as complete, ongoing, repeated, or result-focused.",
                    prompt_hint="Ask whether the verb presents the action as completed or ongoing.",
                    source="lesson_extraction",
                )
                enriched.append(cand.model_copy(update={"lesson_data": with_pedagogy(data, tag)}))
            elif cand.type == "case_agreement":
                case = data.get("case") or "case"
                tag = PedagogyTag(
                    family="morphology",
                    skill=f"russian_case_agreement:{case}",
                    level=2,
                    why_it_matters="Russian adjectives and nouns agree in case, gender, and number; this reveals sentence roles.",
                    prompt_hint="Compare the adjective ending with the noun ending.",
                    source="lesson_extraction",
                )
                enriched.append(cand.model_copy(update={"lesson_data": with_pedagogy(data, tag)}))
            else:
                enriched.append(super()._default_enrich(cand))

        return enriched

    def derive_additional(self, candidates: list[CandidateObject], sentence_text: str) -> list[CandidateObject]:
        extra: list[CandidateObject] = []
        seen: set[str] = set()

        for cand in candidates:
            if cand.type != "conjugation":
                continue

            lemma = (cand.lesson_data or {}).get("lemma")
            aspect = (cand.lesson_data or {}).get("aspect")
            surface = (cand.lesson_data or {}).get("surface") or cand.surface_form or cand.label
            if not lemma or not aspect:
                continue

            key = f"nuance:ru:aspect:{lemma}:{aspect}"
            if key in seen:
                continue
            seen.add(key)

            tag = PedagogyTag(
                family="semantic_pattern",
                skill="russian_aspect_nuance",
                level=3,
                why_it_matters="Aspect is one of the main ways Russian encodes viewpoint on events.",
                prompt_hint="Look for whether the sentence focuses on process, repetition, completion, or result.",
                source="lesson_extraction",
            )
            extra.append(CandidateObject(
                canonical_form=key,
                surface_form=surface,
                type="nuance",
                label=surface,
                lesson_data=with_pedagogy({
                    "nuance_type": "russian_aspect",
                    "lemma": lemma,
                    "surface": surface,
                    "aspect": aspect,
                    "note": f"“{surface}” is {aspect}; compare it with its opposite aspect partner where available.",
                }, tag),
                confidence=0.70,
            ))

        return extra
