"""Tests for language-adjustable difficulty scoring.

Covers:
- LanguageScoringProfile defaults and field validation
- get_profile() registry lookup and fallback behaviour
- grammar_weight_scale effect on grammar contribution
- case_agree_weight recognition of case_agreement objects
- length_max_words / word_count_hint calibration for segmented scripts
- Multilingual fairness: morphologically rich language does not score
  systematically harder than an analytic language at the same comprehension
- All built-in language prefixes produce valid, in-range scores
"""
from __future__ import annotations

import pytest

from backend.difficulty.profiles import (
    LanguageScoringProfile,
    _PROFILES,
    get_profile,
)
from backend.difficulty.scorer import (
    KNOWN_THRESHOLD,
    ObjectMastery,
    score_sentence,
)


# ── helpers ───────────────────────────────────────────────────────────────────


def _obj(obj_id: str, obj_type: str, mastery: float = 0.0) -> ObjectMastery:
    return ObjectMastery(
        object_id=obj_id,
        obj_type=obj_type,
        mastery_score=mastery,
        total_reviews=max(1, int(mastery * 5)),
    )


def _known(obj_id: str, obj_type: str = "vocabulary") -> ObjectMastery:
    return _obj(obj_id, obj_type, mastery=0.9)


def _unknown(obj_id: str, obj_type: str = "vocabulary") -> ObjectMastery:
    return _obj(obj_id, obj_type, mastery=0.0)


# ── LanguageScoringProfile ────────────────────────────────────────────────────


class TestLanguageScoringProfile:
    def test_defaults_preserve_original_behaviour(self) -> None:
        """A default-constructed profile must reproduce the pre-profile scorer."""
        profile = LanguageScoringProfile()
        assert profile.length_max_words == 25
        assert profile.grammar_weight_scale == 1.0
        assert profile.conj_weight == 0.70
        assert profile.agree_weight == 0.30
        assert profile.case_agree_weight == 0.00

    def test_profile_is_frozen(self) -> None:
        """Profiles are immutable dataclasses."""
        profile = LanguageScoringProfile()
        with pytest.raises((AttributeError, TypeError)):
            profile.grammar_weight_scale = 0.5  # type: ignore[misc]

    def test_profile_fields_accessible(self) -> None:
        p = LanguageScoringProfile(
            length_max_words=12,
            grammar_weight_scale=0.65,
            conj_weight=0.40,
            agree_weight=0.10,
            case_agree_weight=0.50,
        )
        assert p.length_max_words == 12
        assert p.grammar_weight_scale == 0.65
        assert p.conj_weight == 0.40
        assert p.agree_weight == 0.10
        assert p.case_agree_weight == 0.50


# ── get_profile ───────────────────────────────────────────────────────────────


class TestGetProfile:
    def test_returns_default_for_unknown_language(self) -> None:
        p = get_profile("xx")  # no such language
        assert p == LanguageScoringProfile()

    def test_returns_default_for_empty_like_prefix(self) -> None:
        p = get_profile("zz-ZZ")
        assert p == LanguageScoringProfile()

    def test_spanish_gets_baseline_profile(self) -> None:
        p = get_profile("es")
        assert p.grammar_weight_scale == 1.0
        assert p.length_max_words == 25

    def test_german_profile_known(self) -> None:
        p = get_profile("de")
        assert p.grammar_weight_scale < 1.0
        assert p.case_agree_weight > 0.0

    def test_german_long_tag_resolves_correctly(self) -> None:
        assert get_profile("de-AT") == get_profile("de")
        assert get_profile("de-CH") == get_profile("de")

    def test_chinese_profile_has_reduced_length_max(self) -> None:
        p = get_profile("zh")
        assert p.length_max_words < 25

    def test_japanese_profile_has_reduced_length_max(self) -> None:
        p = get_profile("ja")
        assert p.length_max_words < 25

    def test_arabic_profile_has_reduced_grammar_scale(self) -> None:
        p = get_profile("ar")
        assert p.grammar_weight_scale < 1.0

    def test_russian_profile_has_reduced_grammar_scale(self) -> None:
        p = get_profile("ru")
        assert p.grammar_weight_scale < 1.0

    def test_all_built_in_profiles_have_sane_values(self) -> None:
        for code, p in _PROFILES.items():
            assert 0.0 < p.grammar_weight_scale <= 1.0, f"{code}: scale out of range"
            assert 1 <= p.length_max_words <= 50, f"{code}: length_max out of range"
            assert 0.0 <= p.conj_weight <= 1.0, f"{code}: conj_weight invalid"
            assert 0.0 <= p.agree_weight <= 1.0, f"{code}: agree_weight invalid"
            assert 0.0 <= p.case_agree_weight <= 1.0, f"{code}: case_agree_weight invalid"


# ── grammar_weight_scale ──────────────────────────────────────────────────────


class TestGrammarWeightScale:
    def test_scale_reduces_grammar_score(self) -> None:
        """A profile with scale < 1.0 must produce a lower grammar_score."""
        objects = [
            _unknown("c1", "conjugation"),
            _unknown("c2", "conjugation"),
            _unknown("v1", "vocabulary"),
        ]
        text = "El gato come."

        baseline = score_sentence(objects, text)
        scaled   = score_sentence(objects, text, profile=LanguageScoringProfile(grammar_weight_scale=0.5))

        assert scaled.grammar_score < baseline.grammar_score

    def test_scale_does_not_affect_unknown_ratio(self) -> None:
        """unknown_ratio must be identical regardless of profile grammar scale."""
        objects = [_unknown("c1", "conjugation"), _known("v1")]
        text = "Kommt gut."

        no_profile = score_sentence(objects, text)
        with_scale = score_sentence(objects, text, profile=LanguageScoringProfile(grammar_weight_scale=0.6))

        assert no_profile.unknown_ratio == with_scale.unknown_ratio

    def test_scale_zero_eliminates_grammar_contribution(self) -> None:
        """grammar_weight_scale=0.0 should zero out the grammar component."""
        objects = [_unknown("c1", "conjugation"), _unknown("c2", "conjugation")]
        profile = LanguageScoringProfile(grammar_weight_scale=0.0)
        ds = score_sentence(objects, "Test.", profile=profile)
        assert ds.grammar_score == 0.0

    def test_difficulty_decreases_with_lower_scale(self) -> None:
        """Higher morphological density with a lower scale → lower difficulty."""
        objects = [
            _unknown("c1", "conjugation"),
            _unknown("c2", "conjugation"),
            _unknown("v1", "vocabulary"),
        ]
        text = "Test sentence here."
        baseline = score_sentence(objects, text)
        reduced  = score_sentence(objects, text, profile=LanguageScoringProfile(grammar_weight_scale=0.5))
        assert reduced.difficulty <= baseline.difficulty


# ── case_agree_weight ─────────────────────────────────────────────────────────


class TestCaseAgreWeight:
    def test_case_agreement_ignored_by_default(self) -> None:
        """Without a profile, case_agreement objects contribute 0 grammar."""
        objects = [
            _unknown("ca1", "case_agreement"),
            _unknown("ca2", "case_agreement"),
            _unknown("v1",  "vocabulary"),
        ]
        ds = score_sentence(objects, "Der alte Mann.")
        # No profile → case_agree_weight=0 → grammar contribution from
        # case_agreement is zero.
        assert ds.grammar_score == 0.0

    def test_case_agreement_counted_with_german_profile(self) -> None:
        """German profile gives case_agreement a non-zero grammar weight."""
        de_profile = get_profile("de")
        objects = [
            _unknown("ca1", "case_agreement"),
            _unknown("ca2", "case_agreement"),
            _unknown("v1",  "vocabulary"),
        ]
        ds_de      = score_sentence(objects, "Der alte Mann.", profile=de_profile)
        ds_default = score_sentence(objects, "Der alte Mann.")
        assert ds_de.grammar_score > ds_default.grammar_score

    def test_case_agreement_weight_only_affects_grammar_not_unknown_ratio(self) -> None:
        objects = [_unknown("ca1", "case_agreement"), _known("v1")]
        de_profile = get_profile("de")
        ds = score_sentence(objects, "Test.", profile=de_profile)
        # unknown_ratio must still be 0.5 (one of two objects unknown)
        assert abs(ds.unknown_ratio - 0.5) < 1e-6

    def test_mixed_grammar_types_with_profile(self) -> None:
        """Conjugation + case_agreement should both contribute under German profile."""
        de_profile = get_profile("de")
        objects = [
            _unknown("c1",  "conjugation"),
            _unknown("ca1", "case_agreement"),
            _unknown("v1",  "vocabulary"),
        ]
        ds = score_sentence(objects, "Der Mann kommt.", profile=de_profile)
        assert ds.grammar_score > 0.0


# ── length calibration ────────────────────────────────────────────────────────


class TestLengthCalibration:
    def test_cjk_profile_uses_lower_length_max(self) -> None:
        """With zh profile, same object count yields a higher length_score."""
        objects = [_unknown(f"v{i}") for i in range(8)]
        text = "这是一个测试句子。"

        # 8 objects, default length_max=25 → 8/25 = 0.32
        default_ds = score_sentence(objects, text, word_count_hint=8)
        # 8 objects, zh length_max=10 → 8/10 = 0.80
        zh_ds = score_sentence(objects, text, word_count_hint=8, profile=get_profile("zh"))

        assert zh_ds.length_score > default_ds.length_score

    def test_profile_length_max_applied_correctly(self) -> None:
        profile = LanguageScoringProfile(length_max_words=10)
        objects = [_known("v1")]
        ds = score_sentence(objects, "Five words here total.", word_count_hint=5, profile=profile)
        # 5/10 = 0.5
        assert abs(ds.length_score - 0.5) < 1e-4

    def test_length_score_caps_at_one_with_profile(self) -> None:
        profile = LanguageScoringProfile(length_max_words=5)
        objects = [_known("v1")]
        ds = score_sentence(objects, "Many many many many many many words.", word_count_hint=30, profile=profile)
        assert ds.length_score == 1.0

    def test_word_count_hint_overrides_split_for_cjk(self) -> None:
        """For CJK text, text.split() returns 1; word_count_hint should override."""
        objects = [_unknown(f"v{i}") for i in range(10)]
        cjk_text = "日本語の文章はスペースがありません"  # no whitespace — split() returns 1

        default_ds = score_sentence(objects, cjk_text)
        hint_ds    = score_sentence(objects, cjk_text, word_count_hint=10)

        # Without hint: text.split() = 1 word → very short length_score
        # With hint: 10 units → higher length_score
        assert hint_ds.length_score > default_ds.length_score


# ── multilingual fairness ─────────────────────────────────────────────────────


class TestMultilingualFairness:
    """Key invariant: equal comprehension should yield comparable difficulty.

    A German learner who knows 80% of words in a morphologically dense
    sentence should not see it rated dramatically harder than a Spanish
    learner who knows 80% of words in an equivalent-complexity Spanish
    sentence.  The profile's grammar_weight_scale calibrates this.
    """

    def _spanish_simple(self, mastery_known: float = 0.9) -> tuple[list[ObjectMastery], str]:
        """Simple Spanish sentence: 1 conjugation, 3 vocabulary (80% known)."""
        return (
            [
                _obj("c1",  "conjugation", mastery=0.0),
                _obj("v1",  "vocabulary",  mastery=mastery_known),
                _obj("v2",  "vocabulary",  mastery=mastery_known),
                _obj("v3",  "vocabulary",  mastery=mastery_known),
            ],
            "El gato duerme bien.",
        )

    def _german_equivalent(self, mastery_known: float = 0.9) -> tuple[list[ObjectMastery], str]:
        """Equivalent German sentence: 1 conjugation, 1 case_agreement, 2 vocab (75% known).

        German naturally has more grammar objects, so 75% known is comparable
        to 80% in Spanish (since the extra case_agreement object is structural).
        """
        return (
            [
                _obj("c1",  "conjugation",   mastery=0.0),
                _obj("ca1", "case_agreement", mastery=0.0),
                _obj("v1",  "vocabulary",     mastery=mastery_known),
                _obj("v2",  "vocabulary",     mastery=mastery_known),
            ],
            "Die Katze schläft gut.",
        )

    def test_default_scorer_penalises_german_unfairly(self) -> None:
        """Without calibration, German grammar density inflates difficulty."""
        es_objs, es_text = self._spanish_simple()
        de_objs, de_text = self._german_equivalent()

        es_ds = score_sentence(es_objs, es_text)
        de_ds = score_sentence(de_objs, de_text)

        # Both have the same fraction of unknown objects (1/4 = 0.25 for es;
        # 2/4 = 0.50 for de when we count case_agreement as unknown too).
        # Without a profile, German scores harder — expected without calibration.
        # This test documents the known pre-profile behaviour.
        # (Not an assertion of desired behaviour — just a baseline record.)
        _ = (es_ds, de_ds)  # both computed; comparison is for documentation only

    def test_german_profile_narrows_gap_with_spanish(self) -> None:
        """German profile should reduce (but not erase) the difficulty gap."""
        es_objs, es_text = self._spanish_simple()
        de_objs, de_text = self._german_equivalent()

        es_profile = get_profile("es")
        de_profile = get_profile("de")

        es_ds_default = score_sentence(es_objs, es_text)
        de_ds_default = score_sentence(de_objs, de_text)
        de_ds_profile = score_sentence(de_objs, de_text, profile=de_profile)
        es_ds_profile = score_sentence(es_objs, es_text, profile=es_profile)

        gap_default  = de_ds_default.difficulty - es_ds_default.difficulty
        gap_profiled = de_ds_profile.difficulty - es_ds_profile.difficulty

        # The profile must reduce the gap, not widen it.
        assert gap_profiled < gap_default, (
            f"Profile did not narrow German-Spanish gap: "
            f"default={gap_default:.4f}, profiled={gap_profiled:.4f}"
        )

    def test_unknown_ratio_unchanged_by_profile(self) -> None:
        """Profile must never alter the unknown_ratio — only grammar and length."""
        de_objs, de_text = self._german_equivalent()
        ds_no_profile = score_sentence(de_objs, de_text)
        ds_profile    = score_sentence(de_objs, de_text, profile=get_profile("de"))
        assert ds_no_profile.unknown_ratio == ds_profile.unknown_ratio

    def test_all_profiles_produce_valid_score_range(self) -> None:
        """Every built-in profile must produce in-range scores for a sample sentence."""
        objects = [_unknown("c1", "conjugation"), _unknown("ca1", "case_agreement"),
                   _known("v1"), _known("v2")]
        text = "Sample sentence for testing."

        from backend.difficulty.profiles import _PROFILES
        for lang, p in _PROFILES.items():
            ds = score_sentence(objects, text, profile=p)
            assert 0.0 <= ds.difficulty <= 1.0, f"{lang}: difficulty={ds.difficulty}"
            assert 0.0 <= ds.grammar_score <= 1.0, f"{lang}: grammar={ds.grammar_score}"
            assert 0.0 <= ds.length_score <= 1.0, f"{lang}: length={ds.length_score}"
            assert 0.0 <= ds.unknown_ratio <= 1.0, f"{lang}: ratio={ds.unknown_ratio}"

    def test_cjk_sentences_not_penalised_by_naive_length(self) -> None:
        """CJK with object-count hint must not score near-zero length for 8 objects."""
        zh_profile = get_profile("zh")
        objects = [_unknown(f"v{i}") for i in range(8)]
        cjk_text = "这是测试句子，有八个词。"

        ds = score_sentence(objects, cjk_text, word_count_hint=8, profile=zh_profile)
        # 8 units / length_max_words(zh=10) = 0.80
        assert ds.length_score > 0.5, (
            f"CJK length_score unexpectedly low: {ds.length_score} "
            "(expected > 0.5 with 8-unit sentence and zh profile)"
        )

    def test_analytic_language_grammar_score_unaffected_by_vocab(self) -> None:
        """In an analytic language, pure vocabulary sentences score grammar=0."""
        objects = [_unknown(f"v{i}", "vocabulary") for i in range(5)]
        for lang in ("en", "zh", "ja"):
            profile = get_profile(lang)
            ds = score_sentence(objects, "Five vocab words sentence.", profile=profile)
            assert ds.grammar_score == 0.0, f"{lang}: expected grammar=0 for vocab-only"


# ── backward compatibility ────────────────────────────────────────────────────


class TestBackwardCompatibility:
    def test_no_profile_matches_original_formula(self) -> None:
        """score_sentence without a profile must reproduce the original result."""
        from backend.difficulty.scorer import _W_GRAMMAR, _W_LENGTH, _W_UNKNOWN

        objects = [_unknown("c1", "conjugation"), _known("v2", "vocabulary")]
        text = "Habla bien."

        ds = score_sentence(objects, text)
        # Recompute manually with original constants
        total  = 2
        unk    = 1
        conj   = 1
        words  = len(text.split())
        ur     = unk / total
        gs_raw = (conj / total) * 0.70
        ls     = min(words / 25, 1.0)
        expected = round(_W_UNKNOWN * ur + _W_GRAMMAR * gs_raw + _W_LENGTH * ls, 4)

        assert abs(ds.difficulty - expected) < 1e-4

    def test_default_profile_identical_to_no_profile(self) -> None:
        """An explicit default profile must produce the same result as no profile."""
        objects = [_unknown("c1", "conjugation"), _known("v2")]
        text = "Test."
        ds_none    = score_sentence(objects, text, profile=None)
        ds_default = score_sentence(objects, text, profile=LanguageScoringProfile())
        assert ds_none.difficulty == ds_default.difficulty
        assert ds_none.grammar_score == ds_default.grammar_score
        assert ds_none.length_score == ds_default.length_score
