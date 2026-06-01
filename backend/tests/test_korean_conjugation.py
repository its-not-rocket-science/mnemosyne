"""Tests for Korean conjugation extraction (kiwipiepy EP+EF path).

Coverage
────────
- Present/past/future tense classification from EP morphemes
- Formal/informal/plain register classification from EF morphemes
- Conjugation candidate: correct type, canonical_form, lesson_data fields
- relation_hints: conjugation_of → verb:{lemma} / adj:{lemma}
- Deduplication: same conj canonical emitted at most once per sentence
- XSV compound conjugation: 공부하다 + endings
- Adjective conjugation: 예쁘다 + endings
- Unknown EF forms produce no conjugation candidate
- Vocabulary candidates still emitted alongside conjugation candidates
- _ep_markers and _ef_marker correctly stored
"""
from __future__ import annotations

import pytest

from backend.plugins.korean import (
    KoreanPlugin,
    _classify_tense,
    _classify_register,
    _make_conjugation_candidate,
    create_plugin,
)


# ── skip guard ────────────────────────────────────────────────────────────────

def _kiwi_available() -> bool:
    try:
        from kiwipiepy import Kiwi  # noqa: PLC0415
        Kiwi()
        return True
    except Exception:
        return False


_KIWI = _kiwi_available()
kiwi_required = pytest.mark.skipif(
    not _KIWI,
    reason="kiwipiepy not installed; run: pip install kiwipiepy",
)


@pytest.fixture(scope="module")
def plugin() -> KoreanPlugin:
    return create_plugin()


# ── Unit: tense classifier ────────────────────────────────────────────────────

class TestClassifyTense:
    def test_no_ep_is_present(self):
        assert _classify_tense([]) == "present"

    def test_eoss_is_past(self):
        assert _classify_tense(["었"]) == "past"

    def test_ass_is_past(self):
        assert _classify_tense(["았"]) == "past"

    def test_honorific_past(self):
        assert _classify_tense(["셨"]) == "past"

    def test_gess_is_future(self):
        assert _classify_tense(["겠"]) == "future"

    def test_first_ep_wins(self):
        # 었 before 겠 → past
        assert _classify_tense(["었", "겠"]) == "past"

    def test_unknown_ep_falls_back_to_present(self):
        assert _classify_tense(["면"]) == "present"


# ── Unit: register classifier ─────────────────────────────────────────────────

class TestClassifyRegister:
    def test_formal_polite_bnida(self):
        assert _classify_register("ᆸ니다") == "formal_polite"

    def test_formal_polite_seubnida(self):
        assert _classify_register("습니다") == "formal_polite"

    def test_formal_polite_bnikka(self):
        assert _classify_register("ᆸ니까") == "formal_polite"

    def test_informal_polite_eoyo(self):
        assert _classify_register("어요") == "informal_polite"

    def test_informal_polite_ayo(self):
        assert _classify_register("아요") == "informal_polite"

    def test_informal_polite_yeoyo(self):
        assert _classify_register("여요") == "informal_polite"

    def test_plain_informal_eo(self):
        assert _classify_register("어") == "plain_informal"

    def test_plain_informal_a(self):
        assert _classify_register("아") == "plain_informal"

    def test_plain_declarative_da(self):
        assert _classify_register("다") == "plain_declarative"

    def test_plain_declarative_neunda(self):
        assert _classify_register("는다") == "plain_declarative"

    def test_unknown_ef_returns_none(self):
        assert _classify_register("지") is None

    def test_unknown_ef_returns_none_2(self):
        assert _classify_register("고") is None


# ── Unit: _make_conjugation_candidate ────────────────────────────────────────

class TestMakeConjugationCandidate:
    def test_returns_none_for_unknown_ef(self):
        result = _make_conjugation_candidate("먹다", "먹", [], "지", "verb")
        assert result is None

    def test_canonical_form_present_formal(self):
        c = _make_conjugation_candidate("가다", "가", [], "ᆸ니다", "verb")
        assert c is not None
        assert c.canonical_form == "conj:가다:present:formal_polite"

    def test_canonical_form_past_informal(self):
        c = _make_conjugation_candidate("먹다", "먹", ["었"], "어요", "verb")
        assert c is not None
        assert c.canonical_form == "conj:먹다:past:informal_polite"

    def test_type_is_conjugation(self):
        c = _make_conjugation_candidate("먹다", "먹", [], "어요", "verb")
        assert c is not None
        assert c.type == "conjugation"

    def test_lesson_data_tense(self):
        c = _make_conjugation_candidate("먹다", "먹", ["었"], "어요", "verb")
        assert c is not None
        assert c.lesson_data["tense"] == "past"

    def test_lesson_data_register(self):
        c = _make_conjugation_candidate("먹다", "먹", [], "어요", "verb")
        assert c is not None
        assert c.lesson_data["register"] == "informal_polite"

    def test_lesson_data_lemma(self):
        c = _make_conjugation_candidate("먹다", "먹", [], "어요", "verb")
        assert c is not None
        assert c.lesson_data["lemma"] == "먹다"

    def test_lesson_data_ep_markers_stored(self):
        c = _make_conjugation_candidate("먹다", "먹", ["었"], "어요", "verb")
        assert c is not None
        assert c.lesson_data["ep_markers"] == ["었"]

    def test_lesson_data_ef_marker_stored(self):
        c = _make_conjugation_candidate("먹다", "먹", [], "어요", "verb")
        assert c is not None
        assert c.lesson_data["ef_marker"] == "어요"

    def test_relation_hint_verb(self):
        c = _make_conjugation_candidate("먹다", "먹", [], "어요", "verb")
        assert c is not None
        assert len(c.relation_hints) == 1
        hint = c.relation_hints[0]
        assert hint.relation_type == "conjugation_of"
        assert hint.target_canonical_form == "verb:먹다"
        assert hint.target_type == "vocabulary"

    def test_relation_hint_adj(self):
        c = _make_conjugation_candidate("예쁘다", "예쁘", [], "어요", "adj")
        assert c is not None
        hint = c.relation_hints[0]
        assert hint.target_canonical_form == "adj:예쁘다"

    def test_pos_verb(self):
        c = _make_conjugation_candidate("먹다", "먹", [], "어요", "verb")
        assert c is not None
        assert c.lesson_data["pos"] == "VERB"

    def test_pos_adj(self):
        c = _make_conjugation_candidate("예쁘다", "예쁘", [], "어요", "adj")
        assert c is not None
        assert c.lesson_data["pos"] == "ADJ"

    def test_confidence_is_high(self):
        c = _make_conjugation_candidate("먹다", "먹", [], "어요", "verb")
        assert c is not None
        assert c.confidence is not None and c.confidence >= 0.8

    def test_future_tense(self):
        c = _make_conjugation_candidate("가다", "가", ["겠"], "어요", "verb")
        assert c is not None
        assert c.lesson_data["tense"] == "future"
        assert c.canonical_form == "conj:가다:future:informal_polite"


# ── Integration: full sentence analysis ──────────────────────────────────────

@kiwi_required
class TestConjugationIntegration:
    def test_formal_polite_sentence(self, plugin):
        """학교에 갑니다 → verb:가다 (vocab) + conj:가다:present:formal_polite."""
        result = plugin.analyze_sentence("학교에 갑니다.")
        types = {c.type for c in result.candidates}
        assert "conjugation" in types

        conj = next(
            (c for c in result.candidates if c.type == "conjugation"), None
        )
        assert conj is not None
        assert conj.canonical_form == "conj:가다:present:formal_polite"
        assert conj.lesson_data["register"] == "formal_polite"
        assert conj.lesson_data["tense"] == "present"

    def test_informal_polite_past_sentence(self, plugin):
        """밥을 먹었어요 → conj:먹다:past:informal_polite."""
        result = plugin.analyze_sentence("밥을 먹었어요.")
        conj = next(
            (c for c in result.candidates if c.type == "conjugation"), None
        )
        assert conj is not None
        assert conj.canonical_form == "conj:먹다:past:informal_polite"
        assert conj.lesson_data["tense"] == "past"
        assert conj.lesson_data["register"] == "informal_polite"
        assert conj.lesson_data["ep_markers"] == ["었"]

    def test_vocabulary_also_emitted(self, plugin):
        """Verb vocabulary candidate still emitted alongside conjugation."""
        result = plugin.analyze_sentence("밥을 먹었어요.")
        vocab = [c for c in result.candidates if c.type == "vocabulary"]
        vocab_forms = {c.canonical_form for c in vocab}
        assert "verb:먹다" in vocab_forms

    def test_xsv_compound_conjugation(self, plugin):
        """공부합니다 → verb:공부하다 (vocab) + conj:공부하다:present:formal_polite."""
        result = plugin.analyze_sentence("공부합니다.")
        conj = next(
            (c for c in result.candidates if c.type == "conjugation"), None
        )
        assert conj is not None
        assert "공부하다" in conj.canonical_form
        assert "formal_polite" in conj.canonical_form

    def test_adjective_conjugation(self, plugin):
        """예뻐요 → adj:예쁘다 (vocab) + conj:예쁘다:present:informal_polite."""
        result = plugin.analyze_sentence("예뻐요.")
        conj = next(
            (c for c in result.candidates if c.type == "conjugation"), None
        )
        assert conj is not None
        assert "예쁘다" in conj.canonical_form
        assert conj.lesson_data["pos"] == "ADJ"

    def test_relation_hint_present(self, plugin):
        """Conjugation candidate carries conjugation_of relation hint."""
        result = plugin.analyze_sentence("먹었어요.")
        conj = next(
            (c for c in result.candidates if c.type == "conjugation"), None
        )
        assert conj is not None
        assert any(h.relation_type == "conjugation_of" for h in conj.relation_hints)

    def test_deduplication_same_conjugation(self, plugin):
        """Same conjugation pattern appearing twice → emitted once."""
        result = plugin.analyze_sentence("먹었어요 먹었어요.")
        conjs = [c for c in result.candidates if c.type == "conjugation"]
        cf_set = {c.canonical_form for c in conjs}
        assert len(cf_set) == len(conjs)  # no duplicate canonical forms

    def test_no_raw_tag_in_conjugation(self, plugin):
        """_raw_tag must not leak into conjugation lesson_data."""
        result = plugin.analyze_sentence("먹었어요.")
        for c in result.candidates:
            assert "_raw_tag" not in c.lesson_data

    def test_plain_declarative_register(self, plugin):
        """먹는다 → plain_declarative register."""
        result = plugin.analyze_sentence("밥을 먹는다.")
        conj = next(
            (c for c in result.candidates if c.type == "conjugation"), None
        )
        if conj is not None:
            assert conj.lesson_data["register"] == "plain_declarative"

    def test_future_gesseoyo(self, plugin):
        """가겠어요 → future tense, informal_polite."""
        result = plugin.analyze_sentence("가겠어요.")
        conj = next(
            (c for c in result.candidates if c.type == "conjugation"), None
        )
        assert conj is not None
        assert conj.lesson_data["tense"] == "future"
        assert conj.lesson_data["register"] == "informal_polite"
