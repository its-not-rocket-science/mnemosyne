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

EXPECTED_LANGUAGES = {"es", "fr", "de", "ru", "ar", "ja", "zh", "ko", "it", "pt", "la", "grc", "he", "en", "fi"}


class TestInventoryCoverage:
    def test_all_languages_returns_list(self):
        langs = all_languages()
        assert isinstance(langs, list)
        assert len(langs) >= len(EXPECTED_LANGUAGES)

    def test_expected_languages_present(self):
        langs = set(all_languages())
        missing = EXPECTED_LANGUAGES - langs
        assert not missing, f"missing languages: {missing}"

    def test_no_undeclared_languages(self):
        """Every language in the inventory must appear in EXPECTED_LANGUAGES."""
        langs = set(all_languages())
        undeclared = langs - EXPECTED_LANGUAGES
        assert not undeclared, f"inventory has undeclared languages: {undeclared}"

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
        ("de", "modal_particles"),
        ("fr", "tu_vs_vous"),
        ("ko", "speech_levels"),
        ("ar", "negation_particles"),
        ("zh", "aspect_particles"),
        ("it", "congiuntivo_vs_indicativo"),
    ])
    def test_discourse_effects_present(self, lang, concept):
        sys = get_system(lang, concept)
        if sys is None:
            pytest.skip(f"{lang}/{concept} not in inventory")
        assert isinstance(sys.discourse_effects, list)

    @pytest.mark.parametrize("lang,concept", [
        ("es", "ser_vs_estar"),
        ("ru", "perfective_vs_imperfective"),
        ("de", "modal_particles"),
        ("fr", "tu_vs_vous"),
        ("ja", "keigo_levels"),
        ("ko", "speech_levels"),
        ("ar", "negation_particles"),
        ("zh", "aspect_particles"),
    ])
    def test_discourse_effects_nonempty(self, lang, concept):
        sys = get_system(lang, concept)
        if sys is None:
            pytest.skip(f"{lang}/{concept} not in inventory")
        assert len(sys.discourse_effects) >= 1, (
            f"{lang}/{concept}: discourse_effects is empty"
        )


class TestDimensionVariety:
    """Each language should cover at least two distinct nuance dimensions."""

    @pytest.mark.parametrize("lang", sorted(EXPECTED_LANGUAGES))
    def test_multiple_dimensions(self, lang):
        inv = get_inventory(lang)
        dims = {item.dimension for item in inv}
        assert len(dims) >= 2, f"{lang}: fewer than two dimensions covered ({dims})"


class TestCrossLanguage:
    """Structural invariants that must hold across the full inventory."""

    def test_no_duplicate_contrast_concepts_within_language(self):
        for lang in all_languages():
            concepts = [
                s.contrast_concept
                for s in get_inventory(lang)
                if s.contrast_concept is not None
            ]
            seen: set[str] = set()
            dups = []
            for c in concepts:
                if c in seen:
                    dups.append(c)
                seen.add(c)
            assert not dups, f"{lang}: duplicate contrast_concept keys: {dups}"

    def test_cefr_range_lo_le_hi(self):
        order = ["A1", "A2", "B1", "B2", "C1", "C2"]
        for lang in all_languages():
            for s in get_inventory(lang):
                lo, hi = s.cefr_range
                assert order.index(lo) <= order.index(hi), (
                    f"{lang}/{s.name}: cefr_range lo={lo!r} > hi={hi!r}"
                )

    def test_aspect_dimension_covered_by_most_languages(self):
        """Aspect is grammatically relevant in all target languages — verify coverage."""
        langs_with_aspect = {
            lang
            for lang in all_languages()
            if any(s.dimension == "aspect" for s in get_inventory(lang))
        }
        assert len(langs_with_aspect) >= 8, (
            f"only {len(langs_with_aspect)} languages cover aspect: {langs_with_aspect}"
        )

    def test_all_languages_have_contrast_concept(self):
        """Every language must expose at least one contrast_concept (links to data files)."""
        for lang in all_languages():
            has_concept = any(
                s.contrast_concept is not None for s in get_inventory(lang)
            )
            assert has_concept, f"{lang}: no system has a contrast_concept"
