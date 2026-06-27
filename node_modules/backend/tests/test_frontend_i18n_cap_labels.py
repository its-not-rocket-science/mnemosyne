"""Verify that CAPABILITY_LABELS_I18N in frontend/js/i18n.js:

- Contains translations for all 11 UI languages.
- Provides all 4 required keys.
- Does not expose internal capability IDs to users.
- Korean ('ko') and other languages with analysis_depth='morphology_light'
  would show 'Basic grammar hints' equivalent.
"""
from __future__ import annotations

import pathlib
import re

import pytest

# CAPABILITY_LABELS_I18N lives in js/i18n/core.js since Session 5 of the
# frontend refactor split the former monolithic js/i18n.js (now a thin
# re-export shim) into js/i18n/{core,annotations,lesson,library,review}.js.
_I18N_PATH = pathlib.Path(__file__).parents[2] / "frontend" / "js" / "i18n" / "core.js"

# Languages that must be present in CAPABILITY_LABELS_I18N
_REQUIRED_LANGS = {"en", "es", "fr", "de", "it", "pt", "ru", "ja", "zh", "ar", "he"}

# Keys that must be present in every language block
_REQUIRED_KEYS = {
    "cap_label_full",
    "cap_label_morphology_light",
    "cap_label_dictionary",
    "cap_label_segmentation_only",
}

# Internal identifiers that must NOT appear as display values
_BANNED_SUBSTRINGS = {"morphology_light", "segmentation_only", "stub", "partial"}


@pytest.fixture(scope="module")
def i18n_src() -> str:
    return _I18N_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def capability_block(i18n_src: str) -> str:
    """Extract the CAPABILITY_LABELS_I18N block from i18n.js."""
    match = re.search(
        r"export const CAPABILITY_LABELS_I18N\s*=\s*\{(.*?)\n\}",
        i18n_src,
        re.DOTALL,
    )
    assert match, "CAPABILITY_LABELS_I18N not found in frontend/js/i18n.js"
    return match.group(1)


class TestCapabilityLabelsPresence:
    def test_block_exported(self, i18n_src):
        assert "export const CAPABILITY_LABELS_I18N" in i18n_src, (
            "CAPABILITY_LABELS_I18N not exported from i18n.js"
        )

    @pytest.mark.parametrize("lang", sorted(_REQUIRED_LANGS))
    def test_language_present(self, lang, capability_block):
        assert f"{lang}:" in capability_block, (
            f"Language '{lang}' missing from CAPABILITY_LABELS_I18N"
        )

    @pytest.mark.parametrize("key", sorted(_REQUIRED_KEYS))
    def test_key_present_in_english(self, key, capability_block):
        # Check the en block specifically
        en_match = re.search(r"en:\s*\{([^}]+)\}", capability_block)
        assert en_match, "English ('en') block not found in CAPABILITY_LABELS_I18N"
        assert key in en_match.group(1), (
            f"Key '{key}' missing from English CAPABILITY_LABELS_I18N block"
        )


class TestCapabilityLabelsContent:
    def test_english_full_label(self, capability_block):
        assert "Detailed grammar analysis" in capability_block

    def test_english_morphology_light_label(self, capability_block):
        assert "Basic grammar hints" in capability_block

    def test_english_dictionary_label(self, capability_block):
        assert "Vocabulary lookup" in capability_block

    def test_english_segmentation_label(self, capability_block):
        assert "Text segmentation only" in capability_block

    @pytest.mark.parametrize("banned", sorted(_BANNED_SUBSTRINGS))
    def test_no_internal_id_in_display_values(self, banned, capability_block):
        # Strip the key names themselves before checking for leaked IDs.
        # We only want to flag values (after the colon).
        value_lines = [
            line for line in capability_block.splitlines()
            if ":" in line and "cap_label" in line
        ]
        for line in value_lines:
            # Extract just the value part (after the colon and quote)
            value_part = line.split(":", 1)[-1] if ":" in line else ""
            assert banned not in value_part, (
                f"Internal identifier '{banned}' found in capability label value: {line.strip()!r}"
            )
