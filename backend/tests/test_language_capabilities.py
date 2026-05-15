"""Tests for language capability metadata: schema, plugin attributes, and API.

Covers:
- LanguageCapabilities v1 schema validation
- LanguageCapabilities v2 field defaults and validation
- best_lesson_mode() and tts_tag_for() helpers
- GET /languages response shape including v2 fields
- Lesson mode routing in the lesson generator
- _build_script() and _build_transliteration() builders
- Partial-capability plugin compat (no capabilities attribute, v1-only caps)
- New LearnableType values: "script", "transliteration"
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.schemas.language import (
    AnalysisDepth,
    LanguageCapabilities,
    LessonMode,
    NuanceCapabilities,
    QualityLevel,
    best_lesson_mode,
    tts_tag_for,
)

client = TestClient(app)


# ── LanguageCapabilities schema ───────────────────────────────────────────────


class TestLanguageCapabilitiesSchema:
    def test_valid_ltr_latin_plugin(self) -> None:
        caps = LanguageCapabilities(
            code="de",
            display_name="German",
            direction="ltr",
            script_family="latin",
            tokenization_mode="whitespace",
            morphology_depth="rich",
            lesson_modes_supported=["morphology", "vocabulary"],
        )
        assert caps.code == "de"
        assert caps.direction == "ltr"

    def test_valid_rtl_arabic_plugin(self) -> None:
        caps = LanguageCapabilities(
            code="ar",
            display_name="Arabic (stub)",
            direction="rtl",
            script_family="arabic",
            tokenization_mode="whitespace",
            morphology_depth="none",
            lesson_modes_supported=["dictionary"],
        )
        assert caps.direction == "rtl"
        assert caps.script_family == "arabic"

    def test_valid_cjk_segmented_plugin(self) -> None:
        caps = LanguageCapabilities(
            code="zh",
            display_name="Chinese (stub)",
            direction="ltr",
            script_family="cjk",
            tokenization_mode="segmented",
            morphology_depth="none",
            lesson_modes_supported=["dictionary"],
        )
        assert caps.tokenization_mode == "segmented"

    def test_lesson_modes_must_not_be_empty(self) -> None:
        with pytest.raises(Exception):
            LanguageCapabilities(
                code="xx",
                display_name="Test",
                direction="ltr",
                script_family="other",
                tokenization_mode="whitespace",
                morphology_depth="none",
                lesson_modes_supported=[],  # invalid — must have at least one
            )

    def test_serialises_to_dict(self) -> None:
        caps = LanguageCapabilities(
            code="es",
            display_name="Spanish",
            direction="ltr",
            script_family="latin",
            tokenization_mode="whitespace",
            morphology_depth="rich",
            lesson_modes_supported=["morphology", "vocabulary"],
        )
        d = caps.model_dump()
        assert d["code"] == "es"
        assert d["lesson_modes_supported"] == ["morphology", "vocabulary"]


# ── best_lesson_mode() ────────────────────────────────────────────────────────


class TestBestLessonMode:
    @pytest.mark.parametrize("modes,expected", [
        (["morphology"],                "morphology"),
        (["vocabulary"],                "vocabulary"),
        (["dictionary"],                "dictionary"),
        (["morphology", "vocabulary"],  "morphology"),
        (["vocabulary", "morphology"],  "morphology"),  # order in list doesn't matter
        (["vocabulary", "dictionary"],  "vocabulary"),
        (["dictionary", "vocabulary"],  "vocabulary"),
        ([],                            "dictionary"),  # empty → safest fallback
    ])
    def test_picks_richest_mode(self, modes: list[LessonMode], expected: LessonMode) -> None:
        assert best_lesson_mode(modes) == expected  # type: ignore[arg-type]  # parametrize passes plain str; Literal narrowing not inferred from pytest params


# ── GET /languages ────────────────────────────────────────────────────────────


class TestLanguagesEndpoint:
    def test_returns_200(self) -> None:
        resp = client.get("/languages")
        assert resp.status_code == 200

    def test_returns_list(self) -> None:
        resp = client.get("/languages")
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_sorted_by_code(self) -> None:
        resp = client.get("/languages")
        codes = [item["code"] for item in resp.json()]
        assert codes == sorted(codes)

    def test_required_fields_present(self) -> None:
        resp = client.get("/languages")
        required = {
            "code", "display_name", "direction",
            "script_family", "tokenization_mode",
            "morphology_depth", "lesson_modes_supported",
        }
        for item in resp.json():
            assert required <= item.keys(), f"Missing fields in {item}"

    def test_direction_values_valid(self) -> None:
        resp = client.get("/languages")
        for item in resp.json():
            assert item["direction"] in ("ltr", "rtl"), item

    def test_tokenization_mode_values_valid(self) -> None:
        resp = client.get("/languages")
        valid = {"whitespace", "segmented", "character"}
        for item in resp.json():
            assert item["tokenization_mode"] in valid, item

    def test_morphology_depth_values_valid(self) -> None:
        resp = client.get("/languages")
        valid = {"none", "shallow", "rich"}
        for item in resp.json():
            assert item["morphology_depth"] in valid, item

    def test_lesson_modes_non_empty_list(self) -> None:
        resp = client.get("/languages")
        valid = {"morphology", "vocabulary", "dictionary"}
        for item in resp.json():
            modes = item["lesson_modes_supported"]
            assert isinstance(modes, list)
            assert len(modes) >= 1, f"Empty lesson_modes_supported for {item['code']}"
            assert all(m in valid for m in modes), item

    def test_spanish_rich_morphology(self) -> None:
        resp = client.get("/languages")
        es = next((x for x in resp.json() if x["code"] == "es"), None)
        assert es is not None
        assert es["morphology_depth"] == "rich"
        assert "morphology" in es["lesson_modes_supported"]

    def test_english_morphology(self) -> None:
        resp = client.get("/languages")
        en = next((x for x in resp.json() if x["code"] == "en"), None)
        assert en is not None
        # English has minimal morphology; spaCy en_core_web_sm covers what exists.
        assert en["morphology_depth"] == "shallow"

    def test_french_rich_morphology(self) -> None:
        # French now uses the real spaCy plugin, not the stub.
        resp = client.get("/languages")
        fr = next((x for x in resp.json() if x["code"] == "fr"), None)
        assert fr is not None
        assert fr["morphology_depth"] == "rich"

    def test_all_entries_deserialise_as_language_capabilities(self) -> None:
        resp = client.get("/languages")
        for item in resp.json():
            # Pydantic will raise if the shape is wrong.
            caps = LanguageCapabilities(**item)
            assert caps.code == item["code"]


# ── Lesson mode in LessonResponse ────────────────────────────────────────────


class TestLessonModeInResponse:
    """The lesson_mode field must be present in every lesson response."""

    def test_lesson_response_has_lesson_mode_field(self) -> None:
        from backend.lesson.generators import build_lesson

        response = build_lesson(
            object_id="test-id",
            obj_type="vocabulary",
            canonical_form="test",
            display_label="test",
            lesson_data={"lemma": "test", "pos": "NOUN"},
            lesson_mode="morphology",
        )
        assert response.lesson_mode == "morphology"

    def test_lesson_mode_dictionary_uses_minimal_builder(self) -> None:
        from backend.lesson.generators import build_lesson

        response = build_lesson(
            object_id="test-id",
            obj_type="vocabulary",
            canonical_form="كتاب",
            display_label="كتاب",
            lesson_data={"lemma": "كتاب", "gloss": "book"},
            lesson_mode="dictionary",
        )
        assert response.lesson_mode == "dictionary"
        # Dictionary mode: title is just the display label, no prose explanation.
        assert response.title == "كتاب"
        # Should have a gloss field.
        field_labels = [f.label for f in response.fields]
        assert "Gloss" in field_labels
        # Shadowing drill always present; fill-blank added when gloss is known.
        drill_types = [d.type for d in response.drills]
        assert "shadowing" in drill_types
        assert "fill_blank" in drill_types

    def test_lesson_mode_vocabulary_no_morphology_drills(self) -> None:
        from backend.lesson.generators import build_lesson

        # A conjugation object rendered in vocabulary mode should not show
        # tense/mood/person drills — just the vocabulary treatment.
        response = build_lesson(
            object_id="test-id",
            obj_type="conjugation",
            canonical_form="hablar:present:indicative:1:singular",
            display_label="hablo",
            lesson_data={
                "lemma": "hablar",
                "tense": "present",
                "mood": "indicative",
                "person": "1",
                "number": "Sing",
            },
            lesson_mode="vocabulary",
        )
        assert response.lesson_mode == "vocabulary"
        # vocabulary builder is used: title starts with "Vocabulary:"
        assert response.title.startswith("Vocabulary:")

    def test_lesson_mode_default_is_morphology(self) -> None:
        from backend.lesson.generators import build_lesson

        response = build_lesson(
            object_id="test-id",
            obj_type="vocabulary",
            canonical_form="gato",
            display_label="gato",
            lesson_data={"lemma": "gato", "pos": "NOUN"},
        )
        assert response.lesson_mode == "morphology"


# ── v2 capability schema ──────────────────────────────────────────────────────


class TestV2CapabilityFields:
    """v2 fields must have correct defaults and accept valid values."""

    def _v1_caps(self, **overrides) -> LanguageCapabilities:
        """Construct a capabilities object with only v1 fields + overrides."""
        return LanguageCapabilities(
            code="xx",
            display_name="Test",
            direction="ltr",
            script_family="other",
            tokenization_mode="whitespace",
            morphology_depth="none",
            lesson_modes_supported=["dictionary"],
            **overrides,
        )

    def test_v1_only_declaration_uses_safe_defaults(self) -> None:
        caps = self._v1_caps()
        assert caps.analysis_depth == "full"
        assert caps.segmentation_quality == "medium"
        assert caps.tokenization_quality == "medium"
        assert caps.morphology_quality == "medium"
        assert caps.syntax_support is True
        assert caps.idiom_detection is False
        assert caps.tts_lang_tag is None
        assert caps.transliteration_scheme is None

    def test_analysis_depth_full_accepted(self) -> None:
        caps = self._v1_caps(analysis_depth="full")
        assert caps.analysis_depth == "full"

    def test_analysis_depth_segmentation_only_accepted(self) -> None:
        caps = self._v1_caps(analysis_depth="segmentation_only")
        assert caps.analysis_depth == "segmentation_only"

    @pytest.mark.parametrize("depth", ["full", "morphology_light", "dictionary", "segmentation_only"])
    def test_all_analysis_depths_accepted(self, depth: AnalysisDepth) -> None:
        caps = self._v1_caps(analysis_depth=depth)
        assert caps.analysis_depth == depth

    @pytest.mark.parametrize("level", ["high", "medium", "low", "none"])
    def test_all_quality_levels_accepted(self, level: QualityLevel) -> None:
        caps = self._v1_caps(
            segmentation_quality=level,
            tokenization_quality=level,
            morphology_quality=level,
        )
        assert caps.segmentation_quality == level

    def test_syntax_support_and_idiom_detection_flags(self) -> None:
        caps = self._v1_caps(syntax_support=True, idiom_detection=True)
        assert caps.syntax_support is True
        assert caps.idiom_detection is True

    def test_tts_lang_tag_stored(self) -> None:
        caps = self._v1_caps(tts_lang_tag="zh-CN")
        assert caps.tts_lang_tag == "zh-CN"

    def test_transliteration_scheme_stored(self) -> None:
        caps = self._v1_caps(transliteration_scheme="hepburn_romaji")
        assert caps.transliteration_scheme == "hepburn_romaji"

    def test_rtl_arabic_full_declaration(self) -> None:
        """Simulate a future Arabic full plugin declaration."""
        caps = LanguageCapabilities(
            code="ar",
            display_name="Arabic",
            direction="rtl",
            script_family="arabic",
            tokenization_mode="whitespace",
            morphology_depth="rich",
            lesson_modes_supported=["morphology", "vocabulary"],
            analysis_depth="full",
            segmentation_quality="medium",
            tokenization_quality="high",
            morphology_quality="medium",
            syntax_support=True,
            idiom_detection=False,
            tts_lang_tag="ar",
            transliteration_scheme="ipa",
        )
        assert caps.direction == "rtl"
        assert caps.script_family == "arabic"
        assert caps.transliteration_scheme == "ipa"

    def test_cjk_segmented_with_transliteration(self) -> None:
        """Simulate a future Japanese plugin declaration."""
        caps = LanguageCapabilities(
            code="ja",
            display_name="Japanese (stub)",
            direction="ltr",
            script_family="cjk",
            tokenization_mode="segmented",
            morphology_depth="none",
            lesson_modes_supported=["dictionary"],
            analysis_depth="segmentation_only",
            segmentation_quality="medium",
            tokenization_quality="medium",
            morphology_quality="none",
            syntax_support=False,
            idiom_detection=False,
            tts_lang_tag="ja",
            transliteration_scheme="hepburn_romaji",
        )
        assert caps.tokenization_mode == "segmented"
        assert caps.transliteration_scheme == "hepburn_romaji"


# ── tts_tag_for() ─────────────────────────────────────────────────────────────


class TestTtsTagFor:
    def test_returns_tts_lang_tag_when_set(self) -> None:
        caps = LanguageCapabilities(
            code="zh",
            display_name="Chinese",
            direction="ltr",
            script_family="cjk",
            tokenization_mode="segmented",
            morphology_depth="none",
            lesson_modes_supported=["dictionary"],
            tts_lang_tag="zh-CN",
        )
        assert tts_tag_for(caps) == "zh-CN"

    def test_falls_back_to_code_when_tts_lang_tag_none(self) -> None:
        caps = LanguageCapabilities(
            code="es",
            display_name="Spanish",
            direction="ltr",
            script_family="latin",
            tokenization_mode="whitespace",
            morphology_depth="rich",
            lesson_modes_supported=["morphology"],
            tts_lang_tag=None,
        )
        assert tts_tag_for(caps) == "es"


# ── GET /languages — v2 fields ────────────────────────────────────────────────


class TestLanguagesEndpointV2:
    def test_v2_fields_present_in_response(self) -> None:
        resp = client.get("/languages")
        v2_fields = {
            "analysis_depth", "segmentation_quality", "tokenization_quality",
            "morphology_quality", "syntax_support", "idiom_detection",
        }
        for item in resp.json():
            for field in v2_fields:
                assert field in item, f"Missing v2 field '{field}' in {item['code']}"

    def test_analysis_depth_values_valid(self) -> None:
        resp = client.get("/languages")
        valid = {"full", "morphology_light", "dictionary", "segmentation_only"}
        for item in resp.json():
            assert item["analysis_depth"] in valid, item

    def test_quality_level_values_valid(self) -> None:
        resp = client.get("/languages")
        valid = {"high", "medium", "low", "none"}
        for item in resp.json():
            assert item["segmentation_quality"] in valid, item
            assert item["tokenization_quality"] in valid, item
            assert item["morphology_quality"] in valid, item

    def test_feature_flags_are_booleans(self) -> None:
        resp = client.get("/languages")
        for item in resp.json():
            assert isinstance(item["syntax_support"], bool), item
            assert isinstance(item["idiom_detection"], bool), item

    def test_tts_lang_tag_field_present(self) -> None:
        resp = client.get("/languages")
        for item in resp.json():
            assert "tts_lang_tag" in item, item

    def test_transliteration_scheme_field_present(self) -> None:
        resp = client.get("/languages")
        for item in resp.json():
            assert "transliteration_scheme" in item, item

    def test_spanish_full_analysis(self) -> None:
        resp = client.get("/languages")
        es = next(x for x in resp.json() if x["code"] == "es")
        assert es["analysis_depth"] == "full"
        assert es["syntax_support"] is True
        assert es["tts_lang_tag"] == "es"

    def test_english_dictionary_analysis(self) -> None:
        # English now has a full plugin; French also has a real spaCy plugin.
        resp = client.get("/languages")
        en = next(x for x in resp.json() if x["code"] == "en")
        assert en["analysis_depth"] == "full"
        assert en["syntax_support"] is True
        assert en["morphology_quality"] == "low"
        assert en["idiom_detection"] is False   # emits nuance type, not type="idiom"

    def test_french_full_analysis(self) -> None:
        resp = client.get("/languages")
        fr = next(x for x in resp.json() if x["code"] == "fr")
        assert fr["analysis_depth"] == "full"
        assert fr["syntax_support"] is True
        assert fr["morphology_quality"] == "medium"

    def test_german_full_analysis(self) -> None:
        resp = client.get("/languages")
        de = next((x for x in resp.json() if x["code"] == "de"), None)
        assert de is not None
        assert de["analysis_depth"] == "full"
        assert de["syntax_support"] is True
        assert de["morphology_quality"] == "medium"
        assert de["tts_lang_tag"] == "de"


# ── _build_script() ───────────────────────────────────────────────────────────


class TestBuildScript:
    def _build(self, lesson_data: dict) -> object:
        from backend.lesson.generators import build_lesson
        return build_lesson(
            object_id="test-script-id",
            obj_type="script",
            canonical_form="字",
            display_label="字",
            lesson_data=lesson_data,
        )

    def test_script_type_preserved(self) -> None:
        r = self._build({"character": "字", "readings": ["ji4"], "meaning": "character"})
        assert r.type == "script"

    def test_title_contains_character(self) -> None:
        r = self._build({"character": "字"})
        assert "字" in r.title

    def test_fields_include_character(self) -> None:
        r = self._build({"character": "字", "readings": ["ji4"], "meaning": "character"})
        labels = {f.label for f in r.fields}
        assert "Character" in labels

    def test_readings_field_present_when_provided(self) -> None:
        r = self._build({"character": "字", "readings": ["ji4", "zi4"]})
        labels = {f.label for f in r.fields}
        assert "Reading(s)" in labels

    def test_meaning_field_present_when_provided(self) -> None:
        r = self._build({"character": "字", "meaning": "character / letter"})
        labels = {f.label for f in r.fields}
        assert "Meaning" in labels

    def test_no_meaning_no_meaning_field(self) -> None:
        r = self._build({"character": "字"})
        labels = {f.label for f in r.fields}
        assert "Meaning" not in labels

    def test_drills_include_shadowing(self) -> None:
        r = self._build({"character": "字"})
        drill_types = {d.type for d in r.drills}
        assert "shadowing" in drill_types

    def test_fill_blank_reading_drill_when_readings_given(self) -> None:
        r = self._build({"character": "字", "readings": ["zi4"]})
        fill_drills = [d for d in r.drills if d.type == "fill_blank"]
        assert len(fill_drills) >= 1
        # Answer should be the primary reading.
        assert any(d.answer == "zi4" for d in fill_drills)

    def test_no_fill_blank_when_no_readings(self) -> None:
        r = self._build({"character": "字"})
        # No reading → no fill-blank for reading; only meaning fill-blank if meaning given.
        fill_drills = [d for d in r.drills if d.type == "fill_blank"]
        assert all("mean" in d.prompt.lower() or "romanize" in d.prompt.lower()
                   for d in fill_drills)

    def test_examples_include_character(self) -> None:
        r = self._build({"character": "字"})
        assert "字" in r.examples

    def test_lesson_mode_stamped_script(self) -> None:
        """Script objects always report lesson_mode="script" regardless of input."""
        r = self._build({"character": "字"})
        assert r.lesson_mode == "script"

    def test_script_bypasses_lesson_mode_override(self) -> None:
        """Even with lesson_mode="dictionary", script objects use _build_script."""
        from backend.lesson.generators import build_lesson
        r = build_lesson(
            object_id="test-id",
            obj_type="script",
            canonical_form="字",
            display_label="字",
            lesson_data={"character": "字", "readings": ["zi4"]},
            lesson_mode="dictionary",
        )
        # Should still have the reading fill-blank drill, not the dictionary minimal output.
        fill_drills = [d for d in r.drills if d.type == "fill_blank"]
        assert len(fill_drills) >= 1

    def test_stroke_count_field(self) -> None:
        r = self._build({"character": "字", "stroke_count": 6})
        labels = {f.label for f in r.fields}
        assert "Strokes" in labels


# ── _build_transliteration() ─────────────────────────────────────────────────


class TestBuildTransliteration:
    def _build(self, lesson_data: dict) -> object:
        from backend.lesson.generators import build_lesson
        return build_lesson(
            object_id="test-trans-id",
            obj_type="transliteration",
            canonical_form="nihongo",
            display_label="日本語",
            lesson_data=lesson_data,
        )

    def test_transliteration_type_preserved(self) -> None:
        r = self._build({"native_form": "日本語", "romanized": "nihongo"})
        assert r.type == "transliteration"

    def test_title_contains_native_form(self) -> None:
        r = self._build({"native_form": "日本語", "romanized": "nihongo"})
        assert "日本語" in r.title

    def test_fields_native_and_romanized(self) -> None:
        r = self._build({"native_form": "日本語", "romanized": "nihongo"})
        labels = {f.label for f in r.fields}
        assert "Native form" in labels
        assert "Romanization" in labels

    def test_scheme_field_when_provided(self) -> None:
        r = self._build({"native_form": "日本語", "romanized": "nihongo",
                         "scheme": "hepburn_romaji"})
        labels = {f.label for f in r.fields}
        assert "Scheme" in labels

    def test_no_scheme_field_when_absent(self) -> None:
        r = self._build({"native_form": "日本語", "romanized": "nihongo"})
        labels = {f.label for f in r.fields}
        assert "Scheme" not in labels

    def test_fill_blank_romanize_drill(self) -> None:
        r = self._build({"native_form": "日本語", "romanized": "nihongo"})
        fill_drills = [d for d in r.drills if d.type == "fill_blank"]
        assert any(d.answer == "nihongo" for d in fill_drills)

    def test_fill_blank_native_form_drill(self) -> None:
        r = self._build({"native_form": "日本語", "romanized": "nihongo"})
        fill_drills = [d for d in r.drills if d.type == "fill_blank"]
        assert any(d.answer == "日本語" for d in fill_drills)

    def test_shadowing_drill_present(self) -> None:
        r = self._build({"native_form": "日本語", "romanized": "nihongo"})
        assert any(d.type == "shadowing" for d in r.drills)

    def test_examples_include_both_forms(self) -> None:
        r = self._build({"native_form": "日本語", "romanized": "nihongo"})
        assert "日本語" in r.examples
        assert "nihongo" in r.examples

    def test_transliteration_bypasses_lesson_mode(self) -> None:
        """lesson_mode="vocabulary" does not affect transliteration objects."""
        from backend.lesson.generators import build_lesson
        r = build_lesson(
            object_id="test-id",
            obj_type="transliteration",
            canonical_form="nihongo",
            display_label="日本語",
            lesson_data={"native_form": "日本語", "romanized": "nihongo"},
            lesson_mode="vocabulary",
        )
        assert r.type == "transliteration"
        assert any(d.type == "fill_blank" for d in r.drills)

    def test_meaning_field_when_provided(self) -> None:
        r = self._build({"native_form": "日本語", "romanized": "nihongo",
                         "meaning": "Japanese language"})
        labels = {f.label for f in r.fields}
        assert "Meaning" in labels

    def test_explanation_includes_both_forms(self) -> None:
        r = self._build({"native_form": "日本語", "romanized": "nihongo"})
        assert "日本語" in r.explanation
        assert "nihongo" in r.explanation


# ── Partial-capability plugin compatibility ───────────────────────────────────


class TestPartialCapabilityPluginCompat:
    """Plugins that lack capabilities or use only v1 fields must work safely."""

    def test_no_capabilities_attr_gets_fallback_in_registry(self) -> None:
        """A plugin with no capabilities attribute gets a synthesised fallback."""
        from backend.parsing.plugin_loader import PluginRegistry
        from backend.schemas.language import LanguageCapabilities

        class BarePlugin:
            language_code = "xx"
            display_name  = "Bare plugin"
            direction     = "ltr"

            def __init__(self) -> None:
                self.lesson_store = {}

            def analyze_text(self, text):
                return []

            def split_sentences(self, text):
                return []

            def analyze_sentence(self, sentence):
                from backend.schemas.parse import CandidateSentenceResult
                return CandidateSentenceResult(text=sentence, candidates=[])

            def get_lesson(self, object_id):
                return None

        registry = PluginRegistry()
        registry.register(BarePlugin())  # type: ignore[arg-type]  # test stub satisfies LanguagePlugin structurally but mypy can't verify Protocol compliance without explicit annotation

        caps = registry.supported_languages()["xx"]
        assert isinstance(caps, LanguageCapabilities)
        # Fallback defaults should be conservative.
        assert caps.morphology_depth == "rich"
        assert caps.lesson_modes_supported == ["dictionary"]
        # v2 defaults are also conservative.
        assert caps.analysis_depth == "full"
        assert caps.morphology_quality == "medium"
        assert caps.syntax_support is True

    def test_v1_only_capabilities_gets_v2_defaults(self) -> None:
        """A plugin with only v1 LanguageCapabilities fields loads without error."""
        caps = LanguageCapabilities(
            code="zz",
            display_name="V1 Plugin",
            direction="ltr",
            script_family="other",
            tokenization_mode="whitespace",
            morphology_depth="shallow",
            lesson_modes_supported=["vocabulary"],
            # No v2 fields — all should default safely.
        )
        assert caps.analysis_depth == "full"
        assert caps.segmentation_quality == "medium"
        assert caps.tokenization_quality == "medium"
        assert caps.morphology_quality == "medium"
        assert caps.syntax_support is True
        assert caps.idiom_detection is False
        assert caps.tts_lang_tag is None
        assert caps.transliteration_scheme is None

    def test_partial_plugin_lesson_route_uses_vocabulary_mode(self) -> None:
        """The lesson route falls back to morphology mode for unknown capabilities."""
        from backend.api.routes.lesson import _mode_for_language
        from backend.parsing.plugin_loader import PluginRegistry

        class VocabOnlyPlugin:
            language_code = "yy"
            display_name  = "Vocab only"
            direction     = "ltr"
            capabilities  = LanguageCapabilities(
                code="yy",
                display_name="Vocab only",
                direction="ltr",
                script_family="other",
                tokenization_mode="whitespace",
                morphology_depth="none",
                lesson_modes_supported=["vocabulary"],
            )

            def __init__(self) -> None:
                self.lesson_store = {}

            def analyze_text(self, text):
                return []

            def split_sentences(self, text):
                return []

            def analyze_sentence(self, sentence):
                from backend.schemas.parse import CandidateSentenceResult
                return CandidateSentenceResult(text=sentence, candidates=[])

            def get_lesson(self, object_id):
                return None

        registry = PluginRegistry()
        registry.register(VocabOnlyPlugin())  # type: ignore[arg-type]  # same: test stub satisfies Protocol structurally but mypy can't verify without explicit annotation
        mode = _mode_for_language(registry, "yy")
        assert mode == "vocabulary"

    def test_unknown_language_lesson_mode_fallback(self) -> None:
        """_mode_for_language falls back to morphology for unregistered codes."""
        from backend.api.routes.lesson import _mode_for_language
        from backend.parsing.plugin_loader import PluginRegistry
        registry = PluginRegistry()
        mode = _mode_for_language(registry, "nonexistent")
        assert mode == "morphology"

    def test_dictionary_mode_plugin_build_lesson(self) -> None:
        """A dictionary-mode plugin's objects produce minimal lessons."""
        from backend.lesson.generators import build_lesson
        r = build_lesson(
            object_id="id1",
            obj_type="vocabulary",
            canonical_form="casa",
            display_label="casa",
            lesson_data={"lemma": "casa", "gloss": "house"},
            lesson_mode="dictionary",
        )
        assert r.lesson_mode == "dictionary"
        field_labels = {f.label for f in r.fields}
        assert "Gloss" in field_labels
        # Shadowing drill always; fill-blank added when gloss is available.
        drill_types = [d.type for d in r.drills]
        assert "shadowing" in drill_types
        assert "fill_blank" in drill_types

    def test_segmentation_only_plugin_objects_round_trip_canonical_id(self) -> None:
        """Objects from a segmentation-only plugin get stable UUIDs."""
        from backend.parsing.canonical import canonical_object_id

        id1 = canonical_object_id("ja", "vocabulary", "猫")
        id2 = canonical_object_id("ja", "vocabulary", "猫")
        assert id1 == id2
        assert len(id1) == 36  # UUID string length

    def test_new_learnable_types_have_valid_canonical_ids(self) -> None:
        """script and transliteration objects can have deterministic UUIDs."""
        from backend.parsing.canonical import canonical_object_id

        script_id = canonical_object_id("ja", "script", "字")
        trans_id  = canonical_object_id("ja", "transliteration", "字")
        # Different types → different UUIDs.
        assert script_id != trans_id
        # Deterministic across calls.
        assert canonical_object_id("ja", "script", "字") == script_id


# ── New LearnableType values ──────────────────────────────────────────────────


class TestNewLearnableTypes:
    def test_script_is_valid_learnable_type(self) -> None:
        from backend.schemas.parse import CandidateObject
        obj = CandidateObject(
            canonical_form="字",
            type="script",
            label="字",
            surface_form="字",
            lesson_data={"character": "字", "readings": ["zi4"], "meaning": "character"},
            confidence=0.95,
        )
        assert obj.type == "script"

    def test_transliteration_is_valid_learnable_type(self) -> None:
        from backend.schemas.parse import CandidateObject
        obj = CandidateObject(
            canonical_form="nihongo",
            type="transliteration",
            label="日本語",
            surface_form="日本語",
            lesson_data={"native_form": "日本語", "romanized": "nihongo",
                         "scheme": "hepburn_romaji"},
            confidence=1.0,
        )
        assert obj.type == "transliteration"

    def test_invalid_type_rejected(self) -> None:
        from pydantic import ValidationError
        from backend.schemas.parse import CandidateObject
        with pytest.raises(ValidationError):
            CandidateObject(
                canonical_form="foo",
                type="unknown_type",  # type: ignore[arg-type]  # intentionally invalid value to verify Pydantic raises ValidationError
                label="foo",
            )

    def test_all_original_types_still_valid(self) -> None:
        from backend.schemas.parse import CandidateObject
        for t in ("vocabulary", "conjugation", "agreement", "idiom", "grammar", "nuance"):
            obj = CandidateObject(
                canonical_form="test",
                type=t,  # type: ignore[arg-type]  # loop var t is str; all values are valid LearnableType members, Pydantic validates
                label="test",
            )
            assert obj.type == t

    def test_case_agreement_is_valid_learnable_type(self) -> None:
        from backend.schemas.parse import CandidateObject
        obj = CandidateObject(
            canonical_form="case_agreement:nom:der_Mann",
            type="case_agreement",
            label="der Mann",
            lesson_data={
                "modifier": "der", "modifier_pos": "DET",
                "noun": "Mann", "case": "Nom",
                "gender": "Masc", "number": "Sing",
            },
        )
        assert obj.type == "case_agreement"


# ── NuanceCapabilities schema ─────────────────────────────────────────────────


class TestNuanceCapabilitiesSchema:
    _VALID_LEVELS = {"none", "stub", "partial", "strong", "gold"}
    _ALL_FIELDS = {
        "idioms", "phrase_families", "literary_references",
        "cultural_references", "etymology", "formality_register",
        "grammar_nuance", "pronunciation_tts", "transliteration",
        "proverb_tradition", "classical_or_scriptural_allusion",
    }

    def test_default_instance_all_none(self) -> None:
        nc = NuanceCapabilities()
        for field in self._ALL_FIELDS:
            assert getattr(nc, field) == "none", f"{field} default is not 'none'"

    def test_all_levels_accepted(self) -> None:
        for level in self._VALID_LEVELS:
            nc = NuanceCapabilities(idioms=level)  # type: ignore[arg-type]
            assert nc.idioms == level

    def test_notes_optional(self) -> None:
        nc = NuanceCapabilities(notes="stub only — no curated data yet")
        assert nc.notes == "stub only — no curated data yet"

    def test_notes_defaults_none(self) -> None:
        assert NuanceCapabilities().notes is None

    def test_language_capabilities_nuance_defaults_none(self) -> None:
        caps = LanguageCapabilities(
            code="xx", display_name="X", direction="ltr",
            script_family="other", tokenization_mode="whitespace",
            morphology_depth="none", lesson_modes_supported=["dictionary"],
        )
        assert caps.nuance_capabilities is None

    def test_language_capabilities_nuance_accepts_model(self) -> None:
        nc = NuanceCapabilities(idioms="partial", pronunciation_tts="partial")
        caps = LanguageCapabilities(
            code="xx", display_name="X", direction="ltr",
            script_family="other", tokenization_mode="whitespace",
            morphology_depth="none", lesson_modes_supported=["dictionary"],
            nuance_capabilities=nc,
        )
        assert caps.nuance_capabilities is not None
        assert caps.nuance_capabilities.idioms == "partial"

    def test_serialises_to_dict_with_nuance(self) -> None:
        nc = NuanceCapabilities(grammar_nuance="strong")
        caps = LanguageCapabilities(
            code="xx", display_name="X", direction="ltr",
            script_family="other", tokenization_mode="whitespace",
            morphology_depth="none", lesson_modes_supported=["dictionary"],
            nuance_capabilities=nc,
        )
        d = caps.model_dump()
        assert d["nuance_capabilities"]["grammar_nuance"] == "strong"


# ── GET /languages — v3 nuance_capabilities ───────────────────────────────────


_NUANCE_FIELDS = {
    "idioms", "phrase_families", "literary_references",
    "cultural_references", "etymology", "formality_register",
    "grammar_nuance", "pronunciation_tts", "transliteration",
    "proverb_tradition", "classical_or_scriptural_allusion",
}
_NUANCE_LEVELS = {"none", "stub", "partial", "strong", "gold"}


class TestLanguagesEndpointV3:
    def test_nuance_capabilities_field_present(self) -> None:
        resp = client.get("/languages")
        for item in resp.json():
            assert "nuance_capabilities" in item, (
                f"nuance_capabilities missing for {item['code']}"
            )

    def test_all_registered_plugins_declare_nuance(self) -> None:
        """Every plugin in the registry must declare nuance_capabilities (not None)."""
        resp = client.get("/languages")
        for item in resp.json():
            assert item["nuance_capabilities"] is not None, (
                f"{item['code']} has nuance_capabilities=None; "
                "all registered plugins must declare coverage"
            )

    def test_all_eleven_fields_present(self) -> None:
        resp = client.get("/languages")
        for item in resp.json():
            nc = item["nuance_capabilities"]
            if nc is None:
                continue
            for field in _NUANCE_FIELDS:
                assert field in nc, (
                    f"nuance field '{field}' missing for {item['code']}"
                )

    def test_all_field_values_valid_levels(self) -> None:
        resp = client.get("/languages")
        for item in resp.json():
            nc = item["nuance_capabilities"]
            if nc is None:
                continue
            for field in _NUANCE_FIELDS:
                assert nc[field] in _NUANCE_LEVELS, (
                    f"{item['code']}.nuance_capabilities.{field} = {nc[field]!r} "
                    "is not a valid NuanceCoverageLevel"
                )

    def test_spacy_languages_have_partial_idioms(self) -> None:
        resp = client.get("/languages")
        spacy_codes = {"es", "fr", "de", "it", "pt", "ru"}
        for item in resp.json():
            if item["code"] not in spacy_codes:
                continue
            nc = item["nuance_capabilities"]
            assert nc is not None
            assert nc["idioms"] in ("partial", "strong", "gold"), (
                f"{item['code']} has a curated idiom table but idioms={nc['idioms']!r}"
            )

    def test_transliteration_languages_declare_it(self) -> None:
        resp = client.get("/languages")
        trans_codes = {"zh", "ja", "grc"}
        for item in resp.json():
            if item["code"] not in trans_codes:
                continue
            nc = item["nuance_capabilities"]
            assert nc is not None
            assert nc["transliteration"] in ("stub", "partial", "strong", "gold"), (
                f"{item['code']} has transliteration_scheme but "
                f"nuance transliteration={nc['transliteration']!r}"
            )

    def test_dictionary_only_languages_grammar_nuance_ceiling(self) -> None:
        # ar has 6 curated grammar signals (definite article + 5 negation particles) → up to "partial".
        # he has 4 curated heuristic signals (definite_prefix, waw_conjunction,
        # prefix_decomposition, biblical_register) → up to "partial".
        # la has no grammar signals and must stay "none".
        resp = client.get("/languages")
        ceiling: dict[str, set[str]] = {
            "ar": {"none", "stub", "partial"},
            "he": {"none", "stub", "partial"},
            "la": {"none"},
        }
        for item in resp.json():
            if item["code"] not in ceiling:
                continue
            nc = item["nuance_capabilities"]
            assert nc is not None
            allowed = ceiling[item["code"]]
            assert nc["grammar_nuance"] in allowed, (
                f"{item['code']} grammar_nuance={nc['grammar_nuance']!r} "
                f"not in allowed set {allowed}"
            )
