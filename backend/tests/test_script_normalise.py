"""Tests for backend.nuance.script_normalise — language-aware script
normalisation for cultural-catalogue surface pattern matching."""
from __future__ import annotations

from backend.nuance.script_normalise import normalise_for_matching


def test_arabic_tashkeel_removed():
    assert normalise_for_matching("كَتَبَ", "ar") == normalise_for_matching("كتب", "ar")


def test_arabic_alef_variants_unified():
    forms = ["أ", "إ", "آ", "ا"]
    normalised = {normalise_for_matching(f, "ar") for f in forms}
    assert len(normalised) == 1


def test_arabic_kashida_removed():
    assert normalise_for_matching("بـاب", "ar") == normalise_for_matching("باب", "ar")


def test_arabic_ta_marbuta_normalised_to_ha():
    assert normalise_for_matching("مدرسة", "ar") == normalise_for_matching("مدرسه", "ar")


def test_persian_ye_variants_unified():
    assert normalise_for_matching("ي", "fa") == normalise_for_matching("ی", "fa")


def test_persian_alef_maqsura_unified_with_farsi_ye():
    assert normalise_for_matching("ى", "fa") == normalise_for_matching("ی", "fa")


def test_persian_zwnj_removed():
    assert normalise_for_matching("می‌روم", "fa") == normalise_for_matching("میروم", "fa")


def test_persian_reuses_arabic_tashkeel_removal():
    assert normalise_for_matching("کَتَبَ", "fa") == normalise_for_matching("کتب", "fa")


def test_hindi_chandrabindu_equals_anusvara():
    assert normalise_for_matching("ँ", "hi") == normalise_for_matching("ं", "hi")


def test_hindi_zwj_removed():
    assert normalise_for_matching("क्‍ष", "hi") == normalise_for_matching("क्ष", "hi")


def test_english_casefold_only_no_change():
    assert normalise_for_matching("Hello", "en") == "hello"


def test_english_unaffected_by_script_normalisation_rules():
    # Sanity check: plain ASCII text must round-trip through the "all other
    # languages" branch (NFC + casefold) without any Arabic/Persian/Hindi
    # substitution rules being applied.
    assert normalise_for_matching("The Writing on the Wall", "en") == "the writing on the wall"


def test_exception_safety_unknown_language_returns_casefolded_text():
    assert normalise_for_matching("", "unknown_lang") == ""
    assert normalise_for_matching("Test", "unknown_lang") == "test"


def test_never_raises_on_odd_input():
    # None is not a valid `text` per the type hint, but the function must
    # never raise (per its own docstring) — confirm it degrades to *some*
    # string rather than raising, regardless of language.
    result = normalise_for_matching(None, "ar")  # type: ignore[arg-type]
    assert isinstance(result, str)


def test_urdu_uses_persian_normalisation():
    # "ur" shares Persian's script-normalisation rules per normalise_for_matching.
    assert normalise_for_matching("ي", "ur") == normalise_for_matching("ی", "ur")
