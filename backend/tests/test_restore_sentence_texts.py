"""Regression tests for _restore_sentence_texts.

Covers the exact Spanish sample bug where the NLP model over-split the passage
into single-token "sentences" and the reader rendered word-per-card gibberish
instead of the full source sentences.

All tests are pure unit tests — no FastAPI client, no DB, no spaCy required.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.parsing.pipeline import _restore_sentence_texts
from backend.schemas.parse import CandidateObject, CandidateSentenceResult

_SPANISH_SAMPLE = (
    "El sol brillaba sobre las montañas mientras los viajeros descansaban junto al río. "
    "El agua fría refrescaba sus pies cansados después de un largo día de camino."
)

_FULL_SENTENCES = [
    "El sol brillaba sobre las montañas mientras los viajeros descansaban junto al río.",
    "El agua fría refrescaba sus pies cansados después de un largo día de camino.",
]


def _plugin(split_return=None, raises=False):
    p = MagicMock()
    if raises:
        p.split_sentences.side_effect = RuntimeError("model unavailable")
    else:
        p.split_sentences.return_value = _FULL_SENTENCES if split_return is None else split_return
    return p


def _cr(text, *, candidates=None):
    return CandidateSentenceResult(text=text, candidates=candidates or [])


def _vocab(label):
    return CandidateObject(
        type="vocabulary",
        label=label,
        canonical_form=label.lower(),
        lesson_data={},
        confidence=0.85,
        surface_form=label,
    )


# ── Count-match path (original behaviour) ────────────────────────────────────

class TestCountMatchPath:
    def test_exact_spanish_sample_restored(self):
        corrupted = [
            _cr("sobre mientras ."),
            _cr("El de un de ."),
        ]
        result = _restore_sentence_texts(_SPANISH_SAMPLE, _plugin(), corrupted)
        assert [r.text for r in result] == _FULL_SENTENCES

    def test_candidates_preserved_on_restore(self):
        cands = [_vocab("montañas")]
        corrupted = [
            _cr("sobre mientras .", candidates=cands),
            _cr("El de un de ."),
        ]
        result = _restore_sentence_texts(_SPANISH_SAMPLE, _plugin(), corrupted)
        assert result[0].candidates == cands
        assert result[0].text == _FULL_SENTENCES[0]

    def test_already_correct_text_unchanged(self):
        good = [_cr(s) for s in _FULL_SENTENCES]
        result = _restore_sentence_texts(_SPANISH_SAMPLE, _plugin(), good)
        assert [r.text for r in result] == _FULL_SENTENCES


# ── split_sentences raises ────────────────────────────────────────────────────

class TestSplitSentencesRaises:
    def test_exception_returns_original_results(self):
        corrupted = [_cr("terms only"), _cr("more terms")]
        result = _restore_sentence_texts(_SPANISH_SAMPLE, _plugin(raises=True), corrupted)
        assert result == corrupted


# ── Empty-input edge cases ────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_candidate_results_returned_unchanged(self):
        result = _restore_sentence_texts(_SPANISH_SAMPLE, _plugin(), [])
        assert result == []

    def test_empty_source_sentences_returns_original(self):
        corrupted = [_cr("something")]
        result = _restore_sentence_texts(_SPANISH_SAMPLE, _plugin(split_return=[]), corrupted)
        assert result == corrupted

    def test_single_sentence_restored(self):
        text = "Una frase simple."
        plugin = _plugin(split_return=["Una frase simple."])
        corrupted = [_cr("frase simple .")]
        result = _restore_sentence_texts(text, plugin, corrupted)
        assert result[0].text == "Una frase simple."


# ── Count-mismatch: over-split (n_cand > n_src) ───────────────────────────────

class TestCountMismatchOverSplit:
    """This is the trust-breaker scenario: es_core_news_sm over-splits
    the passage into many single-token 'sentences'.  The reader must never
    show word-per-card gibberish."""

    def test_over_split_merges_into_source_sentences(self):
        # Model splits 2-sentence passage into 5 single-token results
        over_split = [
            _cr("El"),
            _cr("sol brillaba"),
            _cr("sobre las montañas"),
            _cr("El agua"),
            _cr("refrescaba sus pies"),
        ]
        result = _restore_sentence_texts(_SPANISH_SAMPLE, _plugin(), over_split)
        # After merging, we must have exactly 2 output sentences
        assert len(result) == 2
        # Each output sentence text must be the FULL source sentence
        assert result[0].text == _FULL_SENTENCES[0]
        assert result[1].text == _FULL_SENTENCES[1]

    def test_over_split_candidates_are_not_lost(self):
        cand1 = _vocab("sol")
        cand2 = _vocab("montañas")
        over_split = [
            _cr("El sol", candidates=[cand1]),
            _cr("sobre las montañas", candidates=[cand2]),
            _cr("mientras los viajeros"),
            _cr("El agua fría"),
            _cr("refrescaba sus pies"),
        ]
        result = _restore_sentence_texts(_SPANISH_SAMPLE, _plugin(), over_split)
        assert len(result) == 2
        # The vocabulary candidates must be present somewhere in the merged output
        all_cands = [c for r in result for c in r.candidates]
        labels = [c.label for c in all_cands]
        assert "sol" in labels
        assert "montañas" in labels

    def test_extreme_over_split_one_word_each(self):
        words = _FULL_SENTENCES[0].split()
        over_split = [_cr(w) for w in words] + [_cr(w) for w in _FULL_SENTENCES[1].split()]
        result = _restore_sentence_texts(_SPANISH_SAMPLE, _plugin(), over_split)
        assert len(result) == 2
        assert result[0].text == _FULL_SENTENCES[0]
        assert result[1].text == _FULL_SENTENCES[1]

    def test_no_source_sentences_lost_when_over_split(self):
        over_split = [_cr("word")] * 10
        result = _restore_sentence_texts(_SPANISH_SAMPLE, _plugin(), over_split)
        texts = [r.text for r in result]
        assert _FULL_SENTENCES[0] in texts
        assert _FULL_SENTENCES[1] in texts


# ── Count-mismatch: under-split (n_cand < n_src) ─────────────────────────────

class TestCountMismatchUnderSplit:
    def test_under_split_restores_matched_sentences(self):
        # Plugin returned only 1 result for a 2-sentence passage
        under_split = [_cr("combined text")]
        result = _restore_sentence_texts(_SPANISH_SAMPLE, _plugin(), under_split)
        # The one result gets the first source sentence
        assert result[0].text == _FULL_SENTENCES[0]


# ── Longer Spanish passage with vocabulary candidates ─────────────────────────

class TestSpanishSampleWithCandidates:
    """Reproduces the exact trust-breaker scenario end-to-end through
    _restore_sentence_texts — no full app startup needed."""

    def test_full_sample_with_vocab_candidates(self):
        sol = _vocab("sol")
        montañas = _vocab("montañas")
        viajeros = _vocab("viajeros")
        rio = _vocab("río")
        agua = _vocab("agua")
        pies = _vocab("pies")

        # Simulate the over-split output with vocabulary candidates attached
        over_split = [
            _cr("El sol brillaba", candidates=[sol]),
            _cr("sobre las montañas", candidates=[montañas]),
            _cr("mientras los viajeros", candidates=[viajeros]),
            _cr("descansaban junto al río", candidates=[rio]),
            _cr("El agua fría", candidates=[agua]),
            _cr("refrescaba sus pies cansados", candidates=[pies]),
        ]
        result = _restore_sentence_texts(_SPANISH_SAMPLE, _plugin(), over_split)

        assert len(result) == 2
        assert result[0].text == _FULL_SENTENCES[0]
        assert result[1].text == _FULL_SENTENCES[1]

        first_labels = [c.label for c in result[0].candidates]
        second_labels = [c.label for c in result[1].candidates]

        # Words from the first sentence → first bucket
        assert "sol" in first_labels
        assert "montañas" in first_labels
        assert "viajeros" in first_labels
        assert "río" in first_labels

        # Words from the second sentence → second bucket
        assert "agua" in second_labels
        assert "pies" in second_labels
