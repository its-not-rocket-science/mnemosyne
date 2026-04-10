"""Tests for language capability metadata: schema, plugin attributes, and API.

Covers:
- LanguageCapabilities schema validation
- best_lesson_mode() helper
- GET /languages response shape and field values
- Lesson mode routing in the lesson generator
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.schemas.language import (
    LanguageCapabilities,
    LessonMode,
    best_lesson_mode,
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
        assert best_lesson_mode(modes) == expected  # type: ignore[arg-type]


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

    def test_english_stub_no_morphology(self) -> None:
        resp = client.get("/languages")
        en = next((x for x in resp.json() if x["code"] == "en"), None)
        assert en is not None
        assert en["morphology_depth"] == "none"

    def test_french_stub_no_morphology(self) -> None:
        resp = client.get("/languages")
        fr = next((x for x in resp.json() if x["code"] == "fr"), None)
        assert fr is not None
        assert fr["morphology_depth"] == "none"

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
        # Only a shadowing drill — no multiple-choice or fill-blank.
        assert len(response.drills) == 1
        assert response.drills[0].type == "shadowing"

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
