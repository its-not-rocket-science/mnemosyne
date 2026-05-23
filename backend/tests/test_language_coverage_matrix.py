"""Validates the machine-readable language coverage matrix.

The matrix is generated from the nuance inventory in dimensions.py via
backend.nuance.coverage.build_matrix().  These tests assert structural
correctness so any inventory regression is caught early.
"""
from __future__ import annotations

import pytest

from backend.nuance.coverage import build_matrix
from backend.nuance.dimensions import all_languages

_MATRIX = build_matrix()
_LANGS = _MATRIX["languages"]

_CEFR_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]


class TestMatrixStructure:
    def test_top_level_key(self):
        assert "languages" in _MATRIX

    def test_all_languages_present(self):
        matrix_langs = set(_LANGS.keys())
        inventory_langs = set(all_languages())
        assert matrix_langs == inventory_langs

    @pytest.mark.parametrize("lang", sorted(all_languages()))
    def test_required_fields(self, lang):
        entry = _LANGS[lang]
        for field in ("system_count", "dimensions", "cefr_min", "cefr_max", "systems"):
            assert field in entry, f"{lang}: missing field {field!r}"

    @pytest.mark.parametrize("lang", sorted(all_languages()))
    def test_system_count_matches_systems_list(self, lang):
        entry = _LANGS[lang]
        assert entry["system_count"] == len(entry["systems"])

    @pytest.mark.parametrize("lang", sorted(all_languages()))
    def test_dimensions_nonempty(self, lang):
        assert len(_LANGS[lang]["dimensions"]) >= 1

    @pytest.mark.parametrize("lang", sorted(all_languages()))
    def test_cefr_values_valid(self, lang):
        entry = _LANGS[lang]
        valid = set(_CEFR_ORDER)
        assert entry["cefr_min"] in valid
        assert entry["cefr_max"] in valid

    @pytest.mark.parametrize("lang", sorted(all_languages()))
    def test_cefr_min_le_max(self, lang):
        entry = _LANGS[lang]
        assert _CEFR_ORDER.index(entry["cefr_min"]) <= _CEFR_ORDER.index(entry["cefr_max"])

    @pytest.mark.parametrize("lang", sorted(all_languages()))
    def test_systems_have_required_keys(self, lang):
        for s in _LANGS[lang]["systems"]:
            for key in ("name", "dimension", "cefr_range"):
                assert key in s, f"{lang}: system missing {key!r}"
            assert len(s["cefr_range"]) == 2


class TestMatrixContent:
    def test_total_language_count(self):
        assert len(_LANGS) >= 14

    def test_aspect_dimension_widespread(self):
        langs_with_aspect = [
            lang for lang, entry in _LANGS.items()
            if "aspect" in entry["dimensions"]
        ]
        assert len(langs_with_aspect) >= 8, (
            f"only {len(langs_with_aspect)} languages cover aspect"
        )

    def test_politeness_covered(self):
        langs_with_politeness = [
            lang for lang, entry in _LANGS.items()
            if "politeness" in entry["dimensions"]
        ]
        assert len(langs_with_politeness) >= 3

    def test_all_languages_reach_b_level(self):
        """Every language should be relevant at least through B1."""
        for lang, entry in _LANGS.items():
            reached = _CEFR_ORDER.index(entry["cefr_max"]) >= _CEFR_ORDER.index("B1")
            assert reached, f"{lang}: cefr_max {entry['cefr_max']} never reaches B1"

    def test_has_discourse_effects_flag(self):
        langs_with_effects = [
            lang for lang, entry in _LANGS.items()
            if entry["has_discourse_effects"]
        ]
        assert len(langs_with_effects) >= 5
