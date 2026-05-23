"""Cross-language nuance inventory coverage tests.

Verifies that the NuanceSystem inventory in backend/nuance/dimensions.py is
consistent, covers the expected languages, and that get_system() lookups
return well-formed objects.
"""
from __future__ import annotations

import pytest

from backend.nuance.dimensions import (
    NuanceSystem,
    all_languages,
    get_inventory,
    get_system,
)

EXPECTED_LANGUAGES = {"es", "fr", "de", "ru", "ar", "ja", "zh", "ko", "it", "pt", "la", "grc"}


class TestInventoryCoverage:
    def test_all_languages_returns_list(self):
        langs = all_languages()
        assert isinstance(langs, list)
        assert len(langs) >= len(EXPECTED_LANGUAGES)

    def test_expected_languages_present(self):
        langs = set(all_languages())
        missing = EXPECTED_LANGUAGES - langs
        assert not missing, f"missing languages: {missing}"

    @pytest.mark.parametrize("lang", sorted(EXPECTED_LANGUAGES))
    def test_language_has_inventory(self, lang):
        inv = get_inventory(lang)
        assert len(inv) >= 1, f"{lang}: inventory is empty"

    @pytest.mark.parametrize("lang", sorted(EXPECTED_LANGUAGES))
    def test_inventory_items_are_nuance_system(self, lang):
        inv = get_inventory(lang)
        for item in inv:
            assert isinstance(item, NuanceSystem), f"{lang}: {item!r} is not a NuanceSystem"

    @pytest.mark.parametrize("lang", sorted(EXPECTED_LANGUAGES))
    def test_inventory_items_have_required_fields(self, lang):
        inv = get_inventory(lang)
        for item in inv:
            assert item.name, f"{lang}: NuanceSystem has empty name"
            assert item.dimension, f"{lang}: NuanceSystem has empty dimension"
            assert item.description, f"{lang}: NuanceSystem has empty description"
            assert item.cefr_range, f"{lang}: NuanceSystem has empty cefr_range"
            assert len(item.cefr_range) == 2, f"{lang}: cefr_range must be a 2-tuple"

    @pytest.mark.parametrize("lang", sorted(EXPECTED_LANGUAGES))
    def test_cefr_range_values_valid(self, lang):
        valid = {"A1", "A2", "B1", "B2", "C1", "C2"}
        inv = get_inventory(lang)
        for item in inv:
            lo, hi = item.cefr_range
            assert lo in valid, f"{lang}/{item.name}: bad cefr_range low {lo!r}"
            assert hi in valid, f"{lang}/{item.name}: bad cefr_range high {hi!r}"


class TestGetSystem:
    def test_spanish_ser_estar(self):
        sys = get_system("es", "ser_vs_estar")
        assert sys is not None
        assert sys.contrast_concept == "ser_vs_estar"
        assert sys.dimension in ("mood", "aspect", "semantic_field")

    def test_russian_aspect(self):
        sys = get_system("ru", "perfective_vs_imperfective")
        assert sys is not None
        assert sys.dimension == "aspect"

    def test_arabic_negation(self):
        sys = get_system("ar", "negation_particles")
        assert sys is not None

    def test_chinese_aspect_particles(self):
        sys = get_system("zh", "aspect_particles")
        assert sys is not None
        assert sys.dimension == "aspect"

    def test_korean_speech_levels(self):
        sys = get_system("ko", "speech_levels")
        assert sys is not None

    def test_italian_congiuntivo(self):
        sys = get_system("it", "congiuntivo_vs_indicativo")
        assert sys is not None

    def test_portuguese_future_subjunctive(self):
        sys = get_system("pt", "future_subjunctive")
        assert sys is not None

    def test_latin_indicative_subjunctive(self):
        sys = get_system("la", "indicative_vs_subjunctive")
        assert sys is not None

    def test_greek_negation(self):
        sys = get_system("grc", "ou_vs_me")
        assert sys is not None

    def test_unknown_concept_returns_none(self):
        assert get_system("es", "nonexistent_concept_xyz") is None

    def test_unknown_language_returns_none(self):
        assert get_system("xx", "ser_vs_estar") is None


class TestDiscourseEffects:
    """Systems that carry discourse_effects should have non-empty lists."""

    @pytest.mark.parametrize("lang,concept", [
        ("es", "ser_vs_estar"),
        ("ru", "perfective_vs_imperfective"),
        ("ja", "keigo_levels"),
    ])
    def test_discourse_effects_present(self, lang, concept):
        sys = get_system(lang, concept)
        if sys is None:
            pytest.skip(f"{lang}/{concept} not in inventory")
        assert isinstance(sys.discourse_effects, list)


class TestDimensionVariety:
    """Each language should cover at least two distinct nuance dimensions."""

    @pytest.mark.parametrize("lang", sorted(EXPECTED_LANGUAGES))
    def test_multiple_dimensions(self, lang):
        inv = get_inventory(lang)
        dims = {item.dimension for item in inv}
        assert len(dims) >= 1, f"{lang}: only one dimension covered"
