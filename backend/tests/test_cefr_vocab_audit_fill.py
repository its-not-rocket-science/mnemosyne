"""Audit coverage for Finnish/Turkish/Hindi CEFR vocabulary fills."""
from __future__ import annotations

from scripts.audit_cefr_vocab import DEFAULT_LANGUAGES, audit_languages


def test_fi_tr_hi_cefr_vocab_audit_passes():
    results, failures = audit_languages(DEFAULT_LANGUAGES)
    assert not failures
    assert {(result.language, result.level) for result in results} == {
        (lang, level)
        for lang in DEFAULT_LANGUAGES
        for level in ("A1", "A2", "B1", "B2", "C1", "C2")
    }


def test_fi_tr_hi_upper_level_confidence_chain():
    from unittest.mock import MagicMock

    from backend.plugins.cefr_vocab import B2, C1, C2
    from backend.plugins.finnish import FinnishPlugin
    from backend.plugins.hindi import _hi_cefr_confidence
    from backend.plugins.turkish import _tr_cefr_confidence

    fi_plugin = FinnishPlugin()
    fi_tok = MagicMock()
    fi_tok.pos_ = "NOUN"
    fi_tok.is_oov = True

    expectations = ((B2, 0.84, "B2"), (C1, 0.82, "C1"), (C2, 0.80, "C2"))
    for table, confidence, cefr_level in expectations:
        fi_conf, fi_note = fi_plugin._vocab_confidence(fi_tok, next(iter(table["fi"])))
        assert fi_conf == confidence
        assert fi_note is None

        tr_conf, tr_cefr = _tr_cefr_confidence(next(iter(table["tr"])))
        assert tr_conf == confidence
        assert tr_cefr == cefr_level

        hi_conf, hi_cefr = _hi_cefr_confidence(next(iter(table["hi"])), 0.50)
        assert hi_conf == confidence
        assert hi_cefr == cefr_level
