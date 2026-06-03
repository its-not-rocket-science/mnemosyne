"""Tests for CEFR B1 vocabulary tables and plugin wiring.

Checks:
  1. B1 dict has all 10 expected languages
  2. B1 sets are non-empty (min threshold per language)
  3. No item appears in A1 or A2 for the same language
  4. B1 words get cefr_level="B1" in lesson_data (plugin-level)
  5. B1 words get confidence=0.86 from _vocab_confidence where applicable
"""
from __future__ import annotations

import pytest

from backend.plugins.cefr_vocab import A1, A2, B1

_EXPECTED_LANGS = {"es", "fr", "de", "it", "pt", "ru", "ja", "zh", "ar", "he", "fi", "tr", "hi"}
_MIN_B1_SIZE = 200


class TestB1Tables:
    def test_all_expected_languages_present(self):
        assert set(B1.keys()) >= _EXPECTED_LANGS

    def test_minimum_size_per_language(self):
        for lang in _EXPECTED_LANGS:
            assert len(B1[lang]) >= _MIN_B1_SIZE, (
                f"{lang} B1 table too small: {len(B1[lang])} < {_MIN_B1_SIZE}"
            )

    def test_no_overlap_with_a1(self):
        for lang in _EXPECTED_LANGS:
            overlap = A1.get(lang, frozenset()) & B1.get(lang, frozenset())
            assert not overlap, (
                f"{lang}: {len(overlap)} items appear in both A1 and B1: "
                f"{sorted(overlap)[:5]}..."
            )

    def test_no_overlap_with_a2(self):
        for lang in _EXPECTED_LANGS:
            overlap = A2.get(lang, frozenset()) & B1.get(lang, frozenset())
            assert not overlap, (
                f"{lang}: {len(overlap)} items appear in both A2 and B1: "
                f"{sorted(overlap)[:5]}..."
            )

    def test_b1_entries_are_strings(self):
        for lang in _EXPECTED_LANGS:
            for item in B1[lang]:
                assert isinstance(item, str) and item, (
                    f"{lang}: non-string or empty entry in B1: {item!r}"
                )


class TestSpanishPluginB1:
    def test_b1_word_confidence(self):
        from unittest.mock import MagicMock
        from backend.plugins.spanish import SpanishPlugin
        plugin = SpanishPlugin()
        from backend.plugins.cefr_vocab import B1 as _B1
        b1_word = next(iter(_B1["es"]))
        tok = MagicMock()
        tok.pos_ = "NOUN"
        tok.is_oov = True
        conf, note = plugin._vocab_confidence(tok, b1_word)
        assert conf == 0.86
        assert note is None


class TestFrenchPluginB1:
    def test_b1_word_confidence(self):
        from unittest.mock import MagicMock
        from backend.plugins.french import FrenchPlugin
        plugin = FrenchPlugin()
        from backend.plugins.cefr_vocab import B1 as _B1
        b1_word = next(iter(_B1["fr"]))
        tok = MagicMock()
        tok.pos_ = "NOUN"
        tok.is_oov = True
        conf, note = plugin._vocab_confidence(tok, b1_word)
        assert conf == 0.86


class TestItalianPluginB1:
    def test_b1_word_confidence(self):
        from unittest.mock import MagicMock
        from backend.plugins.italian import ItalianPlugin
        plugin = ItalianPlugin()
        from backend.plugins.cefr_vocab import B1 as _B1
        b1_word = next(iter(_B1["it"]))
        tok = MagicMock()
        tok.pos_ = "NOUN"
        tok.is_oov = True
        conf, note = plugin._vocab_confidence(tok, b1_word)
        assert conf == 0.86


class TestPortuguesePluginB1:
    def test_b1_word_confidence(self):
        from unittest.mock import MagicMock
        from backend.plugins.portuguese import PortuguesePlugin
        plugin = PortuguesePlugin()
        from backend.plugins.cefr_vocab import B1 as _B1
        b1_word = next(iter(_B1["pt"]))
        tok = MagicMock()
        tok.pos_ = "NOUN"
        tok.is_oov = True
        conf, note = plugin._vocab_confidence(tok, b1_word)
        assert conf == 0.86


class TestJapanesePluginB1:
    def test_b1_word_confidence(self):
        from unittest.mock import MagicMock
        from backend.plugins.japanese import JapanesePlugin
        plugin = JapanesePlugin()
        from backend.plugins.cefr_vocab import B1 as _B1
        b1_word = next(iter(_B1["ja"]))
        tok = MagicMock()
        tok.pos_ = "NOUN"
        tok.lemma_ = b1_word
        conf = plugin._vocab_confidence(tok, reading="dummy")
        assert conf == 0.86


class TestFinnishPluginB1:
    def test_b1_word_confidence(self):
        from unittest.mock import MagicMock
        from backend.plugins.finnish import FinnishPlugin
        plugin = FinnishPlugin()
        from backend.plugins.cefr_vocab import B1 as _B1
        b1_word = next(iter(_B1["fi"]))
        tok = MagicMock()
        tok.pos_ = "NOUN"
        tok.is_oov = True
        conf, note = plugin._vocab_confidence(tok, b1_word)
        assert conf == 0.86
        assert note is None


class TestTurkishPluginB1:
    def test_b1_word_confidence(self):
        from backend.plugins.turkish import _tr_cefr_confidence
        from backend.plugins.cefr_vocab import B1 as _B1
        b1_word = next(iter(_B1["tr"]))
        conf, cefr = _tr_cefr_confidence(b1_word)
        assert conf == 0.86
        assert cefr == "B1"


class TestHindiPluginB1:
    def test_b1_word_confidence(self):
        from backend.plugins.hindi import _hi_cefr_confidence
        from backend.plugins.cefr_vocab import B1 as _B1
        b1_word = next(iter(_B1["hi"]))
        conf, cefr = _hi_cefr_confidence(b1_word, 0.80)
        assert conf == 0.86
        assert cefr == "B1"
