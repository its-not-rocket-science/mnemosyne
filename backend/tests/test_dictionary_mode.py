"""Tests for the enhanced dictionary-mode lesson builder.

Covers the new fields (grammar_note, citation_form, romanized) and the
fill-blank drill that was added to _build_dictionary.
"""
from __future__ import annotations

import pytest

from backend.lesson.context import LessonContext
from backend.lesson.generators import build_lesson
from backend.lesson.formatters import dictionary_explanation


# ── Helpers ────────────────────────────────────────────────────────────────────

def _dict_lesson(lesson_data: dict, display_label: str = "word") -> object:
    """Build a dictionary-mode lesson with minimal boilerplate."""
    return build_lesson(
        object_id="test-dict-id",
        obj_type="vocabulary",
        canonical_form=display_label,
        display_label=display_label,
        lesson_data=lesson_data,
        lesson_mode="dictionary",
    )


# ── dictionary_explanation formatter ─────────────────────────────────────────

class TestDictionaryExplanation:
    def test_with_gloss(self) -> None:
        ctx = LessonContext.unknown()
        result = dictionary_explanation("amor", "love, desire", ctx)
        assert "amor" in result
        assert "love" in result

    def test_with_language_name_no_gloss(self) -> None:
        from backend.schemas.language import LanguageCapabilities
        caps = LanguageCapabilities(
            code="la", display_name="Latin", direction="ltr",
            script_family="latin", tokenization_mode="whitespace",
            morphology_depth="none", lesson_modes_supported=["dictionary"],
        )
        ctx = LessonContext.from_capabilities(caps)
        result = dictionary_explanation("amor", None, ctx)
        assert "amor" in result
        assert "Latin" in result

    def test_fallback_no_gloss_no_language(self) -> None:
        ctx = LessonContext.unknown()
        result = dictionary_explanation("amor", None, ctx)
        assert "amor" in result

    def test_gloss_ends_with_period(self) -> None:
        ctx = LessonContext.unknown()
        result = dictionary_explanation("amor", "love", ctx)
        assert result.endswith(".")

    def test_no_gloss_language_name_ends_with_period(self) -> None:
        from backend.schemas.language import LanguageCapabilities
        caps = LanguageCapabilities(
            code="la", display_name="Latin", direction="ltr",
            script_family="latin", tokenization_mode="whitespace",
            morphology_depth="none", lesson_modes_supported=["dictionary"],
        )
        ctx = LessonContext.from_capabilities(caps)
        result = dictionary_explanation("amor", None, ctx)
        assert result.endswith(".")


# ── Fields ─────────────────────────────────────────────────────────────────────

class TestDictionaryFields:
    def test_gloss_field_present(self) -> None:
        lesson = _dict_lesson({"gloss": "love"})
        field_labels = [f.label for f in lesson.fields]
        assert "Gloss" in field_labels

    def test_gloss_field_value(self) -> None:
        lesson = _dict_lesson({"gloss": "love, desire"})
        gloss_field = next(f for f in lesson.fields if f.label == "Gloss")
        assert gloss_field.value == "love, desire"

    def test_citation_form_field_present(self) -> None:
        lesson = _dict_lesson({"citation_form": "amor, amōris m."})
        field_labels = [f.label for f in lesson.fields]
        assert "Citation form" in field_labels

    def test_citation_form_field_value(self) -> None:
        lesson = _dict_lesson({"citation_form": "amor, amōris m."})
        field = next(f for f in lesson.fields if f.label == "Citation form")
        assert field.value == "amor, amōris m."

    def test_grammar_note_field_present(self) -> None:
        lesson = _dict_lesson({"grammar_note": "3rd declension masculine noun"})
        field_labels = [f.label for f in lesson.fields]
        assert "Grammar" in field_labels

    def test_grammar_note_field_value(self) -> None:
        lesson = _dict_lesson({"grammar_note": "3rd declension masculine noun"})
        field = next(f for f in lesson.fields if f.label == "Grammar")
        assert field.value == "3rd declension masculine noun"

    def test_romanized_field_from_romanized_key(self) -> None:
        lesson = _dict_lesson({"romanized": "amōr"})
        field_labels = [f.label for f in lesson.fields]
        assert "Romanized" in field_labels

    def test_romanized_field_from_pinyin_key(self) -> None:
        """Mandarin-specific "pinyin" key falls through to Romanized field."""
        lesson = _dict_lesson({"pinyin": "ài"})
        field_labels = [f.label for f in lesson.fields]
        assert "Romanized" in field_labels

    def test_romanized_prefers_romanized_key_over_pinyin(self) -> None:
        lesson = _dict_lesson({"romanized": "ipa-form", "pinyin": "pinyin-form"})
        field = next(f for f in lesson.fields if f.label == "Romanized")
        assert field.value == "ipa-form"

    def test_base_form_shown_when_different(self) -> None:
        lesson = _dict_lesson({"lemma": "amare"}, display_label="amabant")
        field_labels = [f.label for f in lesson.fields]
        assert "Base form" in field_labels

    def test_base_form_hidden_when_same(self) -> None:
        lesson = _dict_lesson({"lemma": "amor"}, display_label="amor")
        field_labels = [f.label for f in lesson.fields]
        assert "Base form" not in field_labels

    def test_confidence_note_shown(self) -> None:
        lesson = _dict_lesson({"confidence_note": "scaffold plugin"})
        field_labels = [f.label for f in lesson.fields]
        assert "Note" in field_labels

    def test_all_fields_in_one_lesson(self) -> None:
        lesson = _dict_lesson({
            "gloss": "love",
            "citation_form": "amor, amōris m.",
            "grammar_note": "3rd declension",
            "romanized": "amor",
            "confidence_note": "scaffold",
        })
        field_labels = [f.label for f in lesson.fields]
        assert "Gloss" in field_labels
        assert "Citation form" in field_labels
        assert "Grammar" in field_labels
        assert "Romanized" in field_labels
        assert "Note" in field_labels

    def test_empty_lesson_data_no_fields(self) -> None:
        lesson = _dict_lesson({})
        # No fields when lesson_data is empty (and no provider gloss either).
        assert lesson.fields == []

    def test_field_order_gloss_first(self) -> None:
        lesson = _dict_lesson({
            "gloss": "love",
            "citation_form": "amor, amōris m.",
            "grammar_note": "3rd declension",
        })
        assert lesson.fields[0].label == "Gloss"


# ── Drills ─────────────────────────────────────────────────────────────────────

class TestDictionaryDrills:
    def test_shadowing_drill_always_present(self) -> None:
        lesson = _dict_lesson({})
        drill_types = [d.type for d in lesson.drills]
        assert "shadowing" in drill_types

    def test_fill_blank_present_when_gloss_available(self) -> None:
        lesson = _dict_lesson({"gloss": "love, desire"})
        drill_types = [d.type for d in lesson.drills]
        assert "fill_blank" in drill_types

    def test_fill_blank_absent_when_no_gloss(self) -> None:
        lesson = _dict_lesson({})
        drill_types = [d.type for d in lesson.drills]
        assert "fill_blank" not in drill_types

    def test_fill_blank_answer_is_gloss(self) -> None:
        lesson = _dict_lesson({"gloss": "love, desire"})
        fb = next(d for d in lesson.drills if d.type == "fill_blank")
        assert fb.answer == "love, desire"

    def test_fill_blank_prompt_contains_display_label(self) -> None:
        lesson = build_lesson(
            object_id="test-id",
            obj_type="vocabulary",
            canonical_form="amor",
            display_label="amor",
            lesson_data={"gloss": "love"},
            lesson_mode="dictionary",
        )
        fb = next(d for d in lesson.drills if d.type == "fill_blank")
        assert "amor" in fb.prompt

    def test_shadowing_text_is_display_label(self) -> None:
        lesson = build_lesson(
            object_id="test-id",
            obj_type="vocabulary",
            canonical_form="terra",
            display_label="terra",
            lesson_data={},
            lesson_mode="dictionary",
        )
        sh = next(d for d in lesson.drills if d.type == "shadowing")
        assert sh.text == "terra"

    def test_no_multiple_choice_drills(self) -> None:
        """Dictionary mode never emits MC drills — no reliable option pool."""
        lesson = _dict_lesson({"gloss": "love", "grammar_note": "noun"})
        drill_types = [d.type for d in lesson.drills]
        assert "multiple_choice" not in drill_types

    def test_no_recognition_drills(self) -> None:
        """Dictionary mode never emits recognition drills — confidence too low."""
        lesson = _dict_lesson({"gloss": "love", "grammar_note": "noun"})
        drill_types = [d.type for d in lesson.drills]
        assert "recognition" not in drill_types


# ── Metadata ───────────────────────────────────────────────────────────────────

class TestDictionaryMetadata:
    def test_lesson_mode_is_dictionary(self) -> None:
        lesson = _dict_lesson({})
        assert lesson.lesson_mode == "dictionary"

    def test_title_is_display_label(self) -> None:
        lesson = _dict_lesson({}, display_label="amor")
        assert lesson.title == "amor"

    def test_type_is_vocabulary(self) -> None:
        lesson = _dict_lesson({})
        assert lesson.type == "vocabulary"

    def test_examples_contain_display_label(self) -> None:
        lesson = _dict_lesson({}, display_label="amor")
        assert "amor" in lesson.examples

    def test_language_code_stamped_when_context_provided(self) -> None:
        from backend.schemas.language import LanguageCapabilities
        caps = LanguageCapabilities(
            code="la", display_name="Latin", direction="ltr",
            script_family="latin", tokenization_mode="whitespace",
            morphology_depth="none", lesson_modes_supported=["dictionary"],
        )
        ctx = LessonContext.from_capabilities(caps)
        lesson = build_lesson(
            object_id="test-id",
            obj_type="vocabulary",
            canonical_form="amor",
            display_label="amor",
            lesson_data={},
            lesson_mode="dictionary",
            context=ctx,
        )
        assert lesson.language_code == "la"

    def test_explanation_uses_gloss(self) -> None:
        lesson = _dict_lesson({"gloss": "love, desire"})
        assert "love" in lesson.explanation.lower()

    def test_explanation_without_gloss_is_nonempty(self) -> None:
        lesson = _dict_lesson({})
        assert lesson.explanation.strip()


# ── Interaction with context ───────────────────────────────────────────────────

class TestDictionaryWithContext:
    def test_rtl_direction_stamped(self) -> None:
        from backend.schemas.language import LanguageCapabilities
        caps = LanguageCapabilities(
            code="ar", display_name="Arabic", direction="rtl",
            script_family="arabic", tokenization_mode="whitespace",
            morphology_depth="none", lesson_modes_supported=["dictionary"],
        )
        ctx = LessonContext.from_capabilities(caps)
        lesson = build_lesson(
            object_id="test-id",
            obj_type="vocabulary",
            canonical_form="كتاب",
            display_label="كتاب",
            lesson_data={"gloss": "book"},
            lesson_mode="dictionary",
            context=ctx,
        )
        assert lesson.script_direction == "rtl"

    def test_cjk_context_with_pinyin(self) -> None:
        from backend.schemas.language import LanguageCapabilities
        caps = LanguageCapabilities(
            code="zh", display_name="Mandarin Chinese", direction="ltr",
            script_family="cjk", tokenization_mode="segmented",
            morphology_depth="none", lesson_modes_supported=["vocabulary", "dictionary"],
            transliteration_scheme="pinyin_tone_marks",
        )
        ctx = LessonContext.from_capabilities(caps)
        lesson = build_lesson(
            object_id="test-id",
            obj_type="vocabulary",
            canonical_form="爱",
            display_label="爱",
            lesson_data={"pinyin": "ài"},
            lesson_mode="dictionary",
            context=ctx,
        )
        field_labels = [f.label for f in lesson.fields]
        assert "Romanized" in field_labels
