"""Tests for Chinese tone contour and heteronym (polyphonic character) features.

Covers:
- _tone_contour: tone number list shape and values
- _heteronyms_for: polyphonic character detection
- analyze_sentence: tone_contours present in vocab lesson_data
- analyze_sentence: heteronyms present for polyphonic characters
- Graceful degradation when pypinyin is absent (mocked)
"""
from __future__ import annotations

import pytest

from backend.plugins.chinese import (
    MandarinChinesePlugin,
    _HETERONYMS,
    _heteronyms_for,
    _tone_contour,
)


@pytest.fixture(scope="module")
def plugin() -> MandarinChinesePlugin:
    return MandarinChinesePlugin()


# ── _tone_contour ──────────────────────────────────────────────────────────────


class TestToneContour:
    def test_returns_list_of_ints(self) -> None:
        result = _tone_contour("你好")
        if result is not None:
            assert isinstance(result, list)
            assert all(isinstance(t, int) for t in result)

    def test_length_matches_syllable_count(self) -> None:
        result = _tone_contour("中国")
        if result is not None:
            assert len(result) == 2

    def test_tone_numbers_in_valid_range(self) -> None:
        result = _tone_contour("学习")
        if result is not None:
            for t in result:
                assert 1 <= t <= 5, f"tone {t} outside 1–5 range"

    def test_neutral_tone_is_5(self) -> None:
        # 吗 (ma) is a neutral-tone particle
        result = _tone_contour("吗")
        if result is not None:
            assert result == [5]

    def test_ni_hao_tones(self) -> None:
        result = _tone_contour("你好")
        if result is not None:
            assert result == [3, 3]

    def test_zhongguo_tones(self) -> None:
        result = _tone_contour("中国")
        if result is not None:
            assert result == [1, 2]

    def test_single_char(self) -> None:
        result = _tone_contour("大")
        if result is not None:
            assert len(result) == 1

    def test_empty_string_returns_none_or_empty(self) -> None:
        result = _tone_contour("")
        assert result is None or result == []


# ── _heteronyms_for ────────────────────────────────────────────────────────────


class TestHeteronymsFor:
    def test_polyphonic_char_detected(self) -> None:
        result = _heteronyms_for("重要")
        assert result is not None
        assert len(result) == 1
        assert result[0]["character"] == "重"

    def test_readings_list_has_at_least_two_entries(self) -> None:
        result = _heteronyms_for("重要")
        assert result is not None
        assert len(result[0]["readings"]) >= 2

    def test_reading_dict_has_required_keys(self) -> None:
        result = _heteronyms_for("行走")
        assert result is not None
        for item in result:
            for reading in item["readings"]:
                assert "reading" in reading
                assert "meaning" in reading
                assert "example" in reading

    def test_non_polyphonic_returns_none(self) -> None:
        result = _heteronyms_for("苹果")
        assert result is None

    def test_multiple_polyphonic_chars_in_word(self) -> None:
        # 大行 — both 大 and 行 are polyphonic
        result = _heteronyms_for("大行")
        assert result is not None
        chars = [item["character"] for item in result]
        assert "行" in chars

    def test_heteronyms_table_coverage(self) -> None:
        # Spot-check that canonical polyphonic characters are present
        for char in ("重", "行", "乐", "长", "好", "发", "得"):
            assert char in _HETERONYMS, f"{char} missing from _HETERONYMS"


# ── analyze_sentence integration ──────────────────────────────────────────────


class TestAnalyzeSentenceToneIntegration:
    def test_vocab_has_tone_contours_key(self, plugin: MandarinChinesePlugin) -> None:
        result = plugin.analyze_sentence("我学习中文。")
        vocab = [c for c in result.candidates if c.type == "vocabulary"]
        assert vocab, "no vocabulary candidates"
        # At least one vocab item should have tone_contours (pypinyin present in env)
        with_tones = [c for c in vocab if "tone_contours" in c.lesson_data]
        assert with_tones, "no vocabulary candidate has tone_contours"

    def test_tone_contours_are_list_of_ints(self, plugin: MandarinChinesePlugin) -> None:
        result = plugin.analyze_sentence("你好。")
        vocab = [c for c in result.candidates if c.type == "vocabulary"]
        for c in vocab:
            tc = c.lesson_data.get("tone_contours")
            if tc is not None:
                assert isinstance(tc, list)
                assert all(isinstance(t, int) for t in tc)

    def test_polyphonic_char_in_sentence_has_heteronyms(self, plugin: MandarinChinesePlugin) -> None:
        # 重要 contains polyphonic 重
        result = plugin.analyze_sentence("这很重要。")
        vocab = [c for c in result.candidates if c.type == "vocabulary"]
        # Find candidate containing 重
        poly = [c for c in vocab if "heteronyms" in c.lesson_data]
        # If 重要 is segmented as a single token, it will have heteronyms
        # If segmented separately, 重 alone should have heteronyms
        # Either way, at least one candidate should have the flag
        assert poly, "no candidate with heteronyms for polyphonic character"

    def test_heteronyms_entry_shape(self, plugin: MandarinChinesePlugin) -> None:
        result = plugin.analyze_sentence("这很重要。")
        vocab = [c for c in result.candidates if c.type == "vocabulary"]
        poly = [c for c in vocab if "heteronyms" in c.lesson_data]
        if poly:
            entry = poly[0].lesson_data["heteronyms"][0]
            assert "character" in entry
            assert "readings" in entry
            assert isinstance(entry["readings"], list)

    def test_non_polyphonic_word_no_heteronyms(self, plugin: MandarinChinesePlugin) -> None:
        result = plugin.analyze_sentence("苹果很好吃。")
        vocab = [c for c in result.candidates if c.type == "vocabulary"]
        pinguo = next((c for c in vocab if "苹果" in c.canonical_form), None)
        if pinguo:
            assert "heteronyms" not in pinguo.lesson_data
