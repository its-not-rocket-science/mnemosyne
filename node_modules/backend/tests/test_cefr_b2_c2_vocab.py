"""Tests for CEFR B2/C1/C2 vocabulary tables and plugin wiring.

Checks:
  1. Each dict has all 10 expected languages
  2. Sets are non-empty (min threshold per language)
  3. No item appears in A1/A2/B1 for the same language
  4. No overlap between B2, C1, and C2 within a language
  5. Confidence checks for spaCy plugins (OOV path)
"""
from __future__ import annotations

import pytest

from backend.plugins.cefr_vocab import A1, A2, B1, B2, C1, C2

_EXPECTED_LANGS = {"es", "fr", "de", "it", "pt", "ru", "ja", "zh", "ar", "he", "fi", "tr", "hi"}
_MIN_SIZE = 55


class TestB2Tables:
    def test_all_languages_present(self):
        assert set(B2.keys()) >= _EXPECTED_LANGS

    def test_minimum_size(self):
        for lang in _EXPECTED_LANGS:
            assert len(B2[lang]) >= _MIN_SIZE, f"{lang} B2 too small: {len(B2[lang])}"

    def test_no_overlap_with_a1(self):
        for lang in _EXPECTED_LANGS:
            overlap = A1.get(lang, frozenset()) & B2.get(lang, frozenset())
            assert not overlap, f"{lang}: {len(overlap)} items in both A1 and B2: {sorted(overlap)[:5]}"

    def test_no_overlap_with_a2(self):
        for lang in _EXPECTED_LANGS:
            overlap = A2.get(lang, frozenset()) & B2.get(lang, frozenset())
            assert not overlap, f"{lang}: {len(overlap)} items in both A2 and B2: {sorted(overlap)[:5]}"

    def test_no_overlap_with_b1(self):
        for lang in _EXPECTED_LANGS:
            overlap = B1.get(lang, frozenset()) & B2.get(lang, frozenset())
            assert not overlap, f"{lang}: {len(overlap)} items in both B1 and B2: {sorted(overlap)[:5]}"

    def test_entries_are_strings(self):
        for lang in _EXPECTED_LANGS:
            for item in B2[lang]:
                assert isinstance(item, str) and item, f"{lang}: bad B2 entry: {item!r}"


class TestC1Tables:
    def test_all_languages_present(self):
        assert set(C1.keys()) >= _EXPECTED_LANGS

    def test_minimum_size(self):
        for lang in _EXPECTED_LANGS:
            assert len(C1[lang]) >= _MIN_SIZE, f"{lang} C1 too small: {len(C1[lang])}"

    def test_no_overlap_with_a1(self):
        for lang in _EXPECTED_LANGS:
            overlap = A1.get(lang, frozenset()) & C1.get(lang, frozenset())
            assert not overlap, f"{lang}: {len(overlap)} items in both A1 and C1: {sorted(overlap)[:5]}"

    def test_no_overlap_with_a2(self):
        for lang in _EXPECTED_LANGS:
            overlap = A2.get(lang, frozenset()) & C1.get(lang, frozenset())
            assert not overlap, f"{lang}: {len(overlap)} items in both A2 and C1: {sorted(overlap)[:5]}"

    def test_no_overlap_with_b1(self):
        for lang in _EXPECTED_LANGS:
            overlap = B1.get(lang, frozenset()) & C1.get(lang, frozenset())
            assert not overlap, f"{lang}: {len(overlap)} items in both B1 and C1: {sorted(overlap)[:5]}"

    def test_no_overlap_with_b2(self):
        for lang in _EXPECTED_LANGS:
            overlap = B2.get(lang, frozenset()) & C1.get(lang, frozenset())
            assert not overlap, f"{lang}: {len(overlap)} items in both B2 and C1: {sorted(overlap)[:5]}"

    def test_entries_are_strings(self):
        for lang in _EXPECTED_LANGS:
            for item in C1[lang]:
                assert isinstance(item, str) and item, f"{lang}: bad C1 entry: {item!r}"


class TestC2Tables:
    def test_all_languages_present(self):
        assert set(C2.keys()) >= _EXPECTED_LANGS

    def test_minimum_size(self):
        for lang in _EXPECTED_LANGS:
            assert len(C2[lang]) >= _MIN_SIZE, f"{lang} C2 too small: {len(C2[lang])}"

    def test_no_overlap_with_a1(self):
        for lang in _EXPECTED_LANGS:
            overlap = A1.get(lang, frozenset()) & C2.get(lang, frozenset())
            assert not overlap, f"{lang}: {len(overlap)} items in both A1 and C2: {sorted(overlap)[:5]}"

    def test_no_overlap_with_a2(self):
        for lang in _EXPECTED_LANGS:
            overlap = A2.get(lang, frozenset()) & C2.get(lang, frozenset())
            assert not overlap, f"{lang}: {len(overlap)} items in both A2 and C2: {sorted(overlap)[:5]}"

    def test_no_overlap_with_b1(self):
        for lang in _EXPECTED_LANGS:
            overlap = B1.get(lang, frozenset()) & C2.get(lang, frozenset())
            assert not overlap, f"{lang}: {len(overlap)} items in both B1 and C2: {sorted(overlap)[:5]}"

    def test_no_overlap_with_b2(self):
        for lang in _EXPECTED_LANGS:
            overlap = B2.get(lang, frozenset()) & C2.get(lang, frozenset())
            assert not overlap, f"{lang}: {len(overlap)} items in both B2 and C2: {sorted(overlap)[:5]}"

    def test_no_overlap_with_c1(self):
        for lang in _EXPECTED_LANGS:
            overlap = C1.get(lang, frozenset()) & C2.get(lang, frozenset())
            assert not overlap, f"{lang}: {len(overlap)} items in both C1 and C2: {sorted(overlap)[:5]}"

    def test_entries_are_strings(self):
        for lang in _EXPECTED_LANGS:
            for item in C2[lang]:
                assert isinstance(item, str) and item, f"{lang}: bad C2 entry: {item!r}"


class TestSpanishPluginB2:
    def test_b2_oov_confidence(self):
        from unittest.mock import MagicMock
        from backend.plugins.spanish import SpanishPlugin
        plugin = SpanishPlugin()
        b2_word = next(iter(B2["es"]))
        tok = MagicMock()
        tok.pos_ = "NOUN"
        tok.is_oov = True
        conf, note = plugin._vocab_confidence(tok, b2_word)
        assert conf == 0.84
        assert note is None

    def test_b2_in_vocab_not_overridden(self):
        from unittest.mock import MagicMock
        from backend.plugins.spanish import SpanishPlugin
        plugin = SpanishPlugin()
        b2_word = next(iter(B2["es"]))
        tok = MagicMock()
        tok.pos_ = "NOUN"
        tok.is_oov = False
        conf, note = plugin._vocab_confidence(tok, b2_word)
        assert conf == 0.85  # in-vocab wins over B2

    def test_c1_oov_confidence(self):
        from unittest.mock import MagicMock
        from backend.plugins.spanish import SpanishPlugin
        plugin = SpanishPlugin()
        c1_word = next(iter(C1["es"]))
        tok = MagicMock()
        tok.pos_ = "NOUN"
        tok.is_oov = True
        conf, note = plugin._vocab_confidence(tok, c1_word)
        assert conf == 0.82

    def test_c2_oov_confidence(self):
        from unittest.mock import MagicMock
        from backend.plugins.spanish import SpanishPlugin
        plugin = SpanishPlugin()
        c2_word = next(iter(C2["es"]))
        tok = MagicMock()
        tok.pos_ = "NOUN"
        tok.is_oov = True
        conf, note = plugin._vocab_confidence(tok, c2_word)
        assert conf == 0.80


class TestFrenchPluginB2:
    def test_b2_oov_confidence(self):
        from unittest.mock import MagicMock
        from backend.plugins.french import FrenchPlugin
        plugin = FrenchPlugin()
        b2_word = next(iter(B2["fr"]))
        tok = MagicMock()
        tok.pos_ = "NOUN"
        tok.is_oov = True
        conf, note = plugin._vocab_confidence(tok, b2_word)
        assert conf == 0.84


class TestItalianPluginB2:
    def test_b2_oov_confidence(self):
        from unittest.mock import MagicMock
        from backend.plugins.italian import ItalianPlugin
        plugin = ItalianPlugin()
        b2_word = next(iter(B2["it"]))
        tok = MagicMock()
        tok.pos_ = "NOUN"
        tok.is_oov = True
        conf, note = plugin._vocab_confidence(tok, b2_word)
        assert conf == 0.84


class TestPortuguesePluginB2:
    def test_b2_oov_confidence(self):
        from unittest.mock import MagicMock
        from backend.plugins.portuguese import PortuguesePlugin
        plugin = PortuguesePlugin()
        b2_word = next(iter(B2["pt"]))
        tok = MagicMock()
        tok.pos_ = "NOUN"
        tok.is_oov = True
        conf, note = plugin._vocab_confidence(tok, b2_word)
        assert conf == 0.84
