"""Verify that RECOMMEND_UI_I18N in frontend/js/i18n.js:

- Contains translations for all 11 UI languages.
- Provides all required recommendation UI keys.
- Does not expose internal reason codes as display values.
"""
from __future__ import annotations

import pathlib
import re

import pytest

# RECOMMEND_UI_I18N lives in js/i18n/library.js since Session 5 of the
# frontend refactor split the former monolithic js/i18n.js (now a thin
# re-export shim) into js/i18n/{core,annotations,lesson,library,review}.js.
_I18N_PATH = pathlib.Path(__file__).parents[2] / "frontend" / "js" / "i18n" / "library.js"

_REQUIRED_LANGS = {"en", "es", "fr", "de", "it", "pt", "ru", "ja", "zh", "ar", "he"}

_REQUIRED_KEYS = {
    "reason_level_match",
    "reason_continuing",
    "reason_closest_match",
    "cefr_label",
    "provenance_label",
    "filter_continuation",
    "filter_cefr",
    "filter_max_words",
}

# Internal reason codes that must NOT leak into display values
_BANNED_VALUES = {"level_match", "continuing", "closest_match"}


@pytest.fixture(scope="module")
def i18n_src() -> str:
    return _I18N_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def recommend_block(i18n_src: str) -> str:
    match = re.search(
        r"export const RECOMMEND_UI_I18N\s*=\s*\{(.*?)\n\}",
        i18n_src,
        re.DOTALL,
    )
    assert match, "RECOMMEND_UI_I18N not found in frontend/js/i18n.js"
    return match.group(1)


class TestRecommendUIPresence:
    def test_block_exported(self, i18n_src):
        assert "export const RECOMMEND_UI_I18N" in i18n_src

    @pytest.mark.parametrize("lang", sorted(_REQUIRED_LANGS))
    def test_language_present(self, lang, recommend_block):
        assert f"{lang}:" in recommend_block, (
            f"Language '{lang}' missing from RECOMMEND_UI_I18N"
        )

    @pytest.mark.parametrize("key", sorted(_REQUIRED_KEYS))
    def test_key_present_in_english(self, key, recommend_block):
        en_match = re.search(r"en:\s*\{([^}]+)\}", recommend_block)
        assert en_match, "English block not found in RECOMMEND_UI_I18N"
        assert key in en_match.group(1), (
            f"Key '{key}' missing from English RECOMMEND_UI_I18N block"
        )


class TestRecommendUIContent:
    def test_english_level_match_label(self, recommend_block):
        assert "Matched your level" in recommend_block

    def test_english_continuing_label(self, recommend_block):
        assert "Continuing this text" in recommend_block

    def test_english_closest_match_label(self, recommend_block):
        assert "Closest to your level" in recommend_block

    @pytest.mark.parametrize("banned", sorted(_BANNED_VALUES))
    def test_no_internal_reason_code_in_values(self, banned, recommend_block):
        value_lines = [
            line for line in recommend_block.splitlines()
            if ":" in line and "reason_" in line
        ]
        for line in value_lines:
            value_part = line.split(":", 1)[-1] if ":" in line else ""
            assert banned not in value_part, (
                f"Internal reason code '{banned}' found in display value: {line.strip()!r}"
            )
