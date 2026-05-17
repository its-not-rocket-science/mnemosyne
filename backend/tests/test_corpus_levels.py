"""Tests for corpus level normalization."""
from __future__ import annotations

import pytest

from backend.corpus.levels import (
    CEFR_ORDER,
    HSK_TO_CEFR,
    JLPT_TO_CEFR,
    TOPIK_TO_CEFR,
    difficulty_rank,
    to_cefr,
)


def test_cefr_to_cefr():
    assert to_cefr("CEFR", "B1") == "B1"
    assert to_cefr("CEFR", "A1") == "A1"
    assert to_cefr("CEFR", "C2") == "C2"


def test_cefr_unknown_level():
    assert to_cefr("CEFR", "X9") is None


def test_jlpt_all_levels():
    for jlpt, cefr in JLPT_TO_CEFR.items():
        assert to_cefr("JLPT", jlpt) == cefr


def test_jlpt_n5_is_a1():
    assert to_cefr("JLPT", "N5") == "A1"


def test_jlpt_n1_is_c1():
    assert to_cefr("JLPT", "N1") == "C1"


def test_hsk_all_levels():
    for hsk, cefr in HSK_TO_CEFR.items():
        assert to_cefr("HSK", hsk) == cefr


def test_hsk_progression():
    cefr_ranks = [CEFR_ORDER[to_cefr("HSK", f"HSK{i}")] for i in range(1, 7)]
    assert cefr_ranks == sorted(cefr_ranks), "HSK levels must map to non-decreasing CEFR order"


def test_topik_all_levels():
    for topik, cefr in TOPIK_TO_CEFR.items():
        assert to_cefr("TOPIK", topik) == cefr


def test_custom_framework():
    # Custom framework returns None (no mapping).
    assert to_cefr("custom", "intermediate") is None


def test_unknown_framework():
    assert to_cefr("UNKNOWN", "B1") is None


def test_difficulty_rank_cefr_order():
    ranks = [difficulty_rank("CEFR", lvl) for lvl in ["A1", "A2", "B1", "B2", "C1", "C2"]]
    assert ranks == sorted(ranks)


def test_difficulty_rank_jlpt_order():
    # N5 (easiest) < N4 < N3 < N2 < N1 (hardest)
    ranks = [difficulty_rank("JLPT", f"N{i}") for i in [5, 4, 3, 2, 1]]
    assert ranks == sorted(ranks)


def test_difficulty_rank_unknown_sorts_last():
    assert difficulty_rank("custom", "unknown") == 99
    assert difficulty_rank("CEFR", "Z9") == 99
