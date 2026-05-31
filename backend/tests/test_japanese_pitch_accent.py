"""Tests for Japanese pitch accent data and expanded yojijukugo catalog."""
import pytest
from backend.plugins.japanese import _PITCH_ACCENT, _pitch_accent_entry
from backend.nuance.ja import JapaneseNuanceExtractor, _YOJIJUKUGO


# ── Pitch accent table ────────────────────────────────────────────────────────

class TestPitchAccentTable:
    def test_all_entries_have_valid_drop_mora(self):
        for lemma, (drop_mora, pattern, _) in _PITCH_ACCENT.items():
            assert isinstance(drop_mora, int) and drop_mora >= 0, lemma

    def test_all_entries_have_valid_pattern(self):
        valid = {"heiban", "atamadaka", "nakadaka", "odaka"}
        for lemma, (_, pattern, _) in _PITCH_ACCENT.items():
            assert pattern in valid, f"{lemma}: unexpected pattern '{pattern}'"

    def test_heiban_always_drop_mora_zero(self):
        for lemma, (drop_mora, pattern, _) in _PITCH_ACCENT.items():
            if pattern == "heiban":
                assert drop_mora == 0, f"{lemma}: heiban must have drop_mora=0"

    def test_atamadaka_always_drop_mora_one(self):
        for lemma, (drop_mora, pattern, _) in _PITCH_ACCENT.items():
            if pattern == "atamadaka":
                assert drop_mora == 1, f"{lemma}: atamadaka must have drop_mora=1"

    def test_nakadaka_odaka_drop_mora_gt_one(self):
        for lemma, (drop_mora, pattern, _) in _PITCH_ACCENT.items():
            if pattern in ("nakadaka", "odaka"):
                assert drop_mora > 1, f"{lemma}: {pattern} must have drop_mora>1"

    def test_catalog_size(self):
        assert len(_PITCH_ACCENT) >= 50


# ── _pitch_accent_entry helper ───────────────────────────────────────────────

class TestPitchAccentEntry:
    def test_known_lemma_returns_dict(self):
        result = _pitch_accent_entry("猫")
        assert result is not None
        assert "drop_mora" in result
        assert "pattern" in result

    def test_unknown_lemma_returns_none(self):
        assert _pitch_accent_entry("XXXXXXX") is None

    def test_neko_atamadaka(self):
        result = _pitch_accent_entry("猫")
        assert result["drop_mora"] == 1
        assert result["pattern"] == "atamadaka"

    def test_inu_odaka(self):
        result = _pitch_accent_entry("犬")
        assert result["drop_mora"] == 2
        assert result["pattern"] == "odaka"

    def test_yama_heiban(self):
        result = _pitch_accent_entry("山")
        assert result["drop_mora"] == 0
        assert result["pattern"] == "heiban"


# ── Minimal-pair coverage ────────────────────────────────────────────────────

class TestMinimalPairs:
    @pytest.mark.parametrize("lemma_a,lemma_b", [
        ("橋", "箸"),     # bridge vs chopsticks
        ("雨", "飴"),     # rain vs candy
        ("花", "鼻"),     # flower vs nose
        ("神", "紙"),     # god vs paper
    ])
    def test_pair_members_differ_in_pattern(self, lemma_a, lemma_b):
        a = _pitch_accent_entry(lemma_a)
        b = _pitch_accent_entry(lemma_b)
        assert a is not None and b is not None
        assert a["pattern"] != b["pattern"] or a["drop_mora"] != b["drop_mora"], (
            f"{lemma_a} and {lemma_b} should differ in pitch"
        )

    def test_hashi_bridge_heiban(self):
        assert _pitch_accent_entry("橋")["pattern"] == "heiban"

    def test_hashi_chopsticks_atamadaka(self):
        assert _pitch_accent_entry("箸")["pattern"] == "atamadaka"

    def test_ame_rain_atamadaka(self):
        assert _pitch_accent_entry("雨")["pattern"] == "atamadaka"

    def test_ame_candy_heiban(self):
        assert _pitch_accent_entry("飴")["pattern"] == "heiban"

    def test_hana_flower_odaka(self):
        assert _pitch_accent_entry("花")["pattern"] == "odaka"

    def test_hana_nose_heiban(self):
        assert _pitch_accent_entry("鼻")["pattern"] == "heiban"

    def test_kami_god_atamadaka(self):
        assert _pitch_accent_entry("神")["pattern"] == "atamadaka"

    def test_kami_paper_odaka(self):
        assert _pitch_accent_entry("紙")["pattern"] == "odaka"

    def test_kami_hair_odaka(self):
        assert _pitch_accent_entry("髪")["pattern"] == "odaka"

    def test_minimal_pair_note_present(self):
        result = _pitch_accent_entry("橋")
        assert "note" in result
        assert "箸" in result["note"] or "chopsticks" in result["note"]


# ── Season accent patterns ───────────────────────────────────────────────────

class TestSeasonAccents:
    def test_haru_spring_heiban(self):
        assert _pitch_accent_entry("春")["pattern"] == "heiban"

    def test_natsu_summer_odaka(self):
        assert _pitch_accent_entry("夏")["pattern"] == "odaka"

    def test_aki_autumn_odaka(self):
        assert _pitch_accent_entry("秋")["pattern"] == "odaka"

    def test_fuyu_winter_heiban(self):
        assert _pitch_accent_entry("冬")["pattern"] == "heiban"


# ── Yojijukugo catalog ───────────────────────────────────────────────────────

class TestYojijukugoCatalog:
    def test_catalog_size_at_least_forty(self):
        assert len(_YOJIJUKUGO) >= 40

    def test_all_entries_are_four_chars(self):
        for yoji in _YOJIJUKUGO:
            assert len(yoji) == 4, f"«{yoji}» has {len(yoji)} chars, must be 4"

    def test_all_glosses_are_nonempty_strings(self):
        for yoji, gloss in _YOJIJUKUGO.items():
            assert isinstance(gloss, str) and gloss.strip(), f"«{yoji}» has empty gloss"

    @pytest.mark.parametrize("yoji", [
        "一石二鳥", "一期一会", "自業自得", "十人十色",
        "喜怒哀楽", "温故知新", "危機一髪", "単刀直入",
        "有言実行", "明鏡止水",
    ])
    def test_key_entries_present(self, yoji):
        assert yoji in _YOJIJUKUGO, f"«{yoji}» missing from catalog"


# ── Yojijukugo detection — split-token robustness ───────────────────────────

class _Tok:
    def __init__(self, text: str, lemma: str | None = None):
        self.text = text
        self.lemma_ = lemma or text


class TestYojijukugoDetection:
    @pytest.fixture()
    def ext(self):
        return JapaneseNuanceExtractor()

    def test_detects_when_token_intact(self, ext):
        tokens = [_Tok("一石二鳥")]
        results = ext.extract_nuance("一石二鳥", tokens, [], "ja")
        types = {c.lesson_data.get("nuance_type") for c in results}
        assert "yojijukugo" in types

    def test_detects_when_compound_split(self, ext):
        # SudachiPy splits 一石二鳥 → [一石][二鳥]; pre-scan catches it
        tokens = [_Tok("一石"), _Tok("二鳥")]
        results = ext.extract_nuance("一石二鳥", tokens, [], "ja")
        types = {c.lesson_data.get("nuance_type") for c in results}
        assert "yojijukugo" in types

    def test_no_duplicate_when_split_and_in_token(self, ext):
        # Both passes would match; dedup via seen set — must emit exactly one
        tokens = [_Tok("一石二鳥")]
        results = ext.extract_nuance("一石二鳥", tokens, [], "ja")
        yoji_hits = [c for c in results if c.lesson_data.get("nuance_type") == "yojijukugo"]
        assert len(yoji_hits) == 1

    def test_new_entry_detected(self, ext):
        tokens = [_Tok("喜怒哀楽")]
        results = ext.extract_nuance("喜怒哀楽とは人間の感情のことです。", tokens, [], "ja")
        types = {c.lesson_data.get("nuance_type") for c in results}
        assert "yojijukugo" in types

    def test_lesson_data_keys(self, ext):
        tokens = [_Tok("温故知新")]
        results = ext.extract_nuance("温故知新", tokens, [], "ja")
        yoji = next(c for c in results if c.lesson_data.get("nuance_type") == "yojijukugo")
        for key in ("nuance_type", "explanation", "register", "learner_level", "gloss", "yojijukugo"):
            assert key in yoji.lesson_data, f"missing key: {key}"

    def test_five_char_string_not_flagged(self, ext):
        tokens = [_Tok("あいうえお")]
        results = ext.extract_nuance("あいうえお", tokens, [], "ja")
        types = {c.lesson_data.get("nuance_type") for c in results}
        assert "yojijukugo" not in types

    def test_split_new_entry_detected(self, ext):
        # 危機一髪 split into [危機][一髪] — pre-scan should still detect
        tokens = [_Tok("危機"), _Tok("一髪")]
        results = ext.extract_nuance("危機一髪", tokens, [], "ja")
        types = {c.lesson_data.get("nuance_type") for c in results}
        assert "yojijukugo" in types
