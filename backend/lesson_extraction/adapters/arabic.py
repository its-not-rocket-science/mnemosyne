from __future__ import annotations

import re

from backend.schemas.parse import CandidateObject
from .base import LessonExtractionAdapter
from ..types import PedagogyTag, with_pedagogy

_FORM_MEANINGS = {
    "form-i": ("Form I", "base verbal meaning", 1),
    "form_1": ("Form I", "base verbal meaning", 1),
    "i": ("Form I", "base verbal meaning", 1),
    "form-ii": ("Form II", "intensive or causative meaning", 2),
    "form_2": ("Form II", "intensive or causative meaning", 2),
    "ii": ("Form II", "intensive or causative meaning", 2),
    "form-iii": ("Form III", "associative or reciprocal meaning", 3),
    "form_3": ("Form III", "associative or reciprocal meaning", 3),
    "iii": ("Form III", "associative or reciprocal meaning", 3),
    "form-iv": ("Form IV", "causative meaning", 3),
    "form_4": ("Form IV", "causative meaning", 3),
    "iv": ("Form IV", "causative meaning", 3),
    "form-v": ("Form V", "reflexive counterpart of Form II", 4),
    "form_5": ("Form V", "reflexive counterpart of Form II", 4),
    "v": ("Form V", "reflexive counterpart of Form II", 4),
    "form-vi": ("Form VI", "reflexive or reciprocal counterpart of Form III", 4),
    "form_6": ("Form VI", "reflexive or reciprocal counterpart of Form III", 4),
    "vi": ("Form VI", "reflexive or reciprocal counterpart of Form III", 4),
    "form-vii": ("Form VII", "passive or reflexive meaning", 4),
    "form_7": ("Form VII", "passive or reflexive meaning", 4),
    "vii": ("Form VII", "passive or reflexive meaning", 4),
    "form-viii": ("Form VIII", "reflexive or reciprocal meaning", 4),
    "form_8": ("Form VIII", "reflexive or reciprocal meaning", 4),
    "viii": ("Form VIII", "reflexive or reciprocal meaning", 4),
    "form-x": ("Form X", "seeking, considering, or requesting meaning", 5),
    "form_10": ("Form X", "seeking, considering, or requesting meaning", 5),
    "x": ("Form X", "seeking, considering, or requesting meaning", 5),
}

_PREFIXES = {
    "و": ("wa_prefix", "and / linking prefix", 1),
    "ف": ("fa_prefix", "so / then prefix", 2),
    "ب": ("bi_prefix", "with/by/in prefix", 2),
    "ك": ("ka_prefix", "like/as prefix", 2),
    "ل": ("li_prefix", "to/for prefix", 2),
    "ال": ("definite_article", "definite article “the”", 1),
}

_ARABIC_RE = re.compile(r"[\u0600-\u06ff]")


class ArabicAdapter(LessonExtractionAdapter):
    language = "ar"

    def enrich_existing(self, candidates: list[CandidateObject], sentence_text: str) -> list[CandidateObject]:
        enriched: list[CandidateObject] = []

        for cand in candidates:
            data = dict(cand.lesson_data or {})
            form_key = self._extract_form_key(data)
            if form_key:
                form_label, meaning, level = _FORM_MEANINGS[form_key]
                tag = PedagogyTag(
                    family="morphology",
                    skill=f"arabic_{form_label.lower().replace(' ', '_')}",
                    level=level,
                    why_it_matters=f"{form_label} often signals {meaning}; this lets learners infer meaning from structure.",
                    prompt_hint="Compare the root meaning with the derived form meaning.",
                    source="lesson_extraction",
                )
                enriched.append(cand.model_copy(update={"lesson_data": with_pedagogy(
                    data,
                    tag,
                    extra={"verb_form": form_label, "form_meaning": meaning},
                )}))
            elif cand.type == "vocabulary":
                tag = PedagogyTag(
                    family="vocabulary",
                    skill="root_or_lemma",
                    level=self._level_from_candidate(cand),
                    why_it_matters="Arabic vocabulary is often organized around roots and derived patterns.",
                    prompt_hint="Look for shared consonants across related words.",
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
            data = cand.lesson_data or {}
            root = data.get("root") or data.get("lemma")
            form_key = self._extract_form_key(data)
            surface = cand.surface_form or cand.label

            if root and form_key:
                form_label, meaning, level = _FORM_MEANINGS[form_key]
                key = f"grammar:ar:root_form:{root}:{form_label}"
                if key not in seen:
                    seen.add(key)
                    tag = PedagogyTag(
                        family="morphology",
                        skill="root_pattern",
                        level=level,
                        why_it_matters="Arabic roots combine with patterns to create predictable families of meaning.",
                        prompt_hint="Identify the root consonants, then identify the form.",
                        source="lesson_extraction",
                    )
                    extra.append(CandidateObject(
                        canonical_form=key,
                        surface_form=surface,
                        type="grammar",
                        label=surface,
                        lesson_data=with_pedagogy({
                            "grammar_type": "root_pattern",
                            "root": root,
                            "verb_form": form_label,
                            "form_meaning": meaning,
                            "note": f"{form_label}: {meaning}.",
                        }, tag),
                        confidence=0.76,
                    ))

            # Prefix/clitic lessons from surface form.
            for pref, (skill, note, level) in sorted(_PREFIXES.items(), key=lambda kv: len(kv[0]), reverse=True):
                if surface.startswith(pref) and len(surface) > len(pref) + 1 and _ARABIC_RE.search(surface):
                    key = f"grammar:ar:prefix:{pref}:{skill}"
                    if key in seen:
                        continue
                    seen.add(key)
                    tag = PedagogyTag(
                        family="semantic_pattern",
                        skill=skill,
                        level=level,
                        why_it_matters=f"Arabic frequently attaches small function words directly to words; “{pref}ـ” marks {note}.",
                        prompt_hint="Separate the prefix from the base word.",
                        source="heuristic",
                    )
                    extra.append(CandidateObject(
                        canonical_form=key,
                        surface_form=pref,
                        type="grammar",
                        label=pref,
                        lesson_data=with_pedagogy({
                            "grammar_type": "prefix_particle",
                            "prefix": pref,
                            "note": note,
                            "example_surface": surface,
                        }, tag),
                        confidence=0.58,
                    ))
                    break

            romanized = data.get("romanized") or data.get("transliteration")
            if romanized:
                key = f"translit:ar:{surface}:{romanized}"
                if key not in seen:
                    seen.add(key)
                    tag = PedagogyTag(
                        family="transliteration",
                        skill="arabic_romanization",
                        level=1,
                        why_it_matters="Romanization helps connect Arabic script to pronunciation while learners build script fluency.",
                        prompt_hint="Read the Arabic form, then compare with the romanization.",
                        source="lesson_extraction",
                    )
                    extra.append(CandidateObject(
                        canonical_form=key,
                        surface_form=surface,
                        type="transliteration",
                        label=surface,
                        lesson_data=with_pedagogy({
                            "native_form": surface,
                            "romanized": romanized,
                            "scheme": "arabic_romanization",
                        }, tag),
                        confidence=0.75,
                    ))

        return extra

    def _extract_form_key(self, data: dict) -> str | None:
        candidates = [
            data.get("verb_form"),
            data.get("form"),
            data.get("arabic_form"),
            data.get("pattern"),
        ]
        tags = data.get("tags")
        if isinstance(tags, list):
            candidates.extend(tags)

        for value in candidates:
            if not value:
                continue
            key = str(value).strip().lower().replace(" ", "-")
            key = key.replace("form_", "form-")
            if key in _FORM_MEANINGS:
                return key
            if key.startswith("form-") and key in _FORM_MEANINGS:
                return key
        return None
