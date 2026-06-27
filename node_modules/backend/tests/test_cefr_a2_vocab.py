"""Tests for CEFR A2 vocabulary tables and plugin wiring.

Checks:
  1. A2 dict has all 10 expected languages
  2. A2 sets are non-empty (min threshold per language)
  3. No item appears in both A1 and A2 for the same language
  4. Plugin-level: A2 words get cefr_level="A2" in lesson_data
  5. A2 words get confidence=0.88 from _vocab_confidence where applicable
"""
from __future__ import annotations

import pytest

from backend.plugins.cefr_vocab import A1, A2

_EXPECTED_LANGS = {"es", "fr", "de", "it", "pt", "ru", "ja", "zh", "ar", "he", "fi", "tr", "hi"}
_MIN_A2_SIZE = 200


class TestA2Tables:
    def test_all_expected_languages_present(self):
        assert set(A2.keys()) >= _EXPECTED_LANGS

    def test_minimum_size_per_language(self):
        for lang in _EXPECTED_LANGS:
            assert len(A2[lang]) >= _MIN_A2_SIZE, (
                f"{lang} A2 table too small: {len(A2[lang])} < {_MIN_A2_SIZE}"
            )

    def test_no_overlap_with_a1(self):
        for lang in _EXPECTED_LANGS:
            overlap = A1.get(lang, frozenset()) & A2.get(lang, frozenset())
            assert not overlap, (
                f"{lang}: {len(overlap)} items appear in both A1 and A2: "
                f"{sorted(overlap)[:5]}..."
            )

    def test_a2_entries_are_strings(self):
        for lang in _EXPECTED_LANGS:
            for item in A2[lang]:
                assert isinstance(item, str) and item, (
                    f"{lang}: non-string or empty entry in A2: {item!r}"
                )


class TestSpanishPluginA2:
    def test_a2_word_confidence(self):
        from unittest.mock import MagicMock
        from backend.plugins.spanish import SpanishPlugin
        plugin = SpanishPlugin()
        from backend.plugins.cefr_vocab import A2 as _A2
        # pick any word from es A2 set and verify confidence
        a2_word = next(iter(_A2["es"]))
        tok = MagicMock()
        tok.pos_ = "NOUN"
        tok.is_oov = True  # would normally get 0.50 — A2 should override to 0.88
        conf, note = plugin._vocab_confidence(tok, a2_word)
        assert conf == 0.88
        assert note is None


class TestFrenchPluginA2:
    def test_a2_word_confidence(self):
        from unittest.mock import MagicMock
        from backend.plugins.french import FrenchPlugin
        plugin = FrenchPlugin()
        from backend.plugins.cefr_vocab import A2 as _A2
        a2_word = next(iter(_A2["fr"]))
        tok = MagicMock()
        tok.pos_ = "NOUN"
        tok.is_oov = True
        conf, note = plugin._vocab_confidence(tok, a2_word)
        assert conf == 0.88


class TestItalianPluginA2:
    def test_a2_word_confidence(self):
        from unittest.mock import MagicMock
        from backend.plugins.italian import ItalianPlugin
        plugin = ItalianPlugin()
        from backend.plugins.cefr_vocab import A2 as _A2
        a2_word = next(iter(_A2["it"]))
        tok = MagicMock()
        tok.pos_ = "NOUN"
        tok.is_oov = True
        conf, note = plugin._vocab_confidence(tok, a2_word)
        assert conf == 0.88


class TestPortuguesePluginA2:
    def test_a2_word_confidence(self):
        from unittest.mock import MagicMock
        from backend.plugins.portuguese import PortuguesePlugin
        plugin = PortuguesePlugin()
        from backend.plugins.cefr_vocab import A2 as _A2
        a2_word = next(iter(_A2["pt"]))
        tok = MagicMock()
        tok.pos_ = "NOUN"
        tok.is_oov = True
        conf, note = plugin._vocab_confidence(tok, a2_word)
        assert conf == 0.88


class TestJapanesePluginA2:
    def test_a2_word_confidence(self):
        from unittest.mock import MagicMock
        from backend.plugins.japanese import JapanesePlugin
        plugin = JapanesePlugin()
        from backend.plugins.cefr_vocab import A2 as _A2
        a2_word = next(iter(_A2["ja"]))
        tok = MagicMock()
        tok.pos_ = "NOUN"
        tok.lemma_ = a2_word
        conf = plugin._vocab_confidence(tok, reading="dummy")
        assert conf == 0.88


class TestFinnishPluginA2:
    def test_a2_word_confidence(self):
        from unittest.mock import MagicMock
        from backend.plugins.finnish import FinnishPlugin
        plugin = FinnishPlugin()
        from backend.plugins.cefr_vocab import A2 as _A2
        a2_word = next(iter(_A2["fi"]))
        tok = MagicMock()
        tok.pos_ = "NOUN"
        tok.is_oov = True
        conf, note = plugin._vocab_confidence(tok, a2_word)
        assert conf == 0.88
        assert note is None


class TestTurkishPluginA2:
    def test_a2_word_in_cefr_table(self):
        from backend.plugins.cefr_vocab import A2 as _A2
        from backend.plugins.turkish import _TR_A2
        assert _TR_A2 is _A2["tr"]
        assert len(_TR_A2) >= 200

    def test_a2_word_confidence(self):
        from backend.plugins.turkish import _tr_cefr_confidence
        from backend.plugins.cefr_vocab import A2 as _A2
        a2_word = next(iter(_A2["tr"]))
        conf, cefr = _tr_cefr_confidence(a2_word)
        assert conf == 0.88
        assert cefr == "A2"


class TestHindiPluginA2:
    def test_a2_word_in_cefr_table(self):
        from backend.plugins.cefr_vocab import A2 as _A2
        from backend.plugins.hindi import _HI_A2
        assert _HI_A2 is _A2["hi"]
        assert len(_HI_A2) >= 200

    def test_a2_word_confidence(self):
        from backend.plugins.hindi import _hi_cefr_confidence
        from backend.plugins.cefr_vocab import A2 as _A2
        a2_word = next(iter(_A2["hi"]))
        conf, cefr = _hi_cefr_confidence(a2_word, 0.80)
        assert conf == 0.88
        assert cefr == "A2"
