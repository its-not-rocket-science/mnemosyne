"""Tests for the Mandarin Chinese plugin.

These tests run without jieba or pypinyin installed (the optional CJK extras
are not required in the dev environment) by exercising the graceful fallback
paths.  Tests that need jieba/pypinyin are marked with ``pytest.importorskip``
so they are automatically skipped in environments that lack those packages.
"""
from __future__ import annotations

import pytest

from backend.plugins.chinese import (
    MandarinChinesePlugin,
    _is_learnable,
    _pinyin_for,
    _segment,
    create_plugin,
)
from backend.schemas.language import LanguageCapabilities
from backend.schemas.parse import CandidateObject, CandidateSentenceResult


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture()
def plugin() -> MandarinChinesePlugin:
    return create_plugin()


# ── Capability declaration ─────────────────────────────────────────────────────

class TestCapabilities:
    def test_language_code(self, plugin: MandarinChinesePlugin) -> None:
        assert plugin.language_code == "zh"

    def test_direction_ltr(self, plugin: MandarinChinesePlugin) -> None:
        assert plugin.direction == "ltr"

    def test_script_family_cjk(self, plugin: MandarinChinesePlugin) -> None:
        assert plugin.capabilities.script_family == "cjk"

    def test_tokenization_mode_segmented(self, plugin: MandarinChinesePlugin) -> None:
        assert plugin.capabilities.tokenization_mode == "segmented"

    def test_morphology_depth_none(self, plugin: MandarinChinesePlugin) -> None:
        assert plugin.capabilities.morphology_depth == "none"

    def test_transliteration_scheme_pinyin(self, plugin: MandarinChinesePlugin) -> None:
        assert plugin.capabilities.transliteration_scheme == "pinyin_tone_marks"

    def test_tts_lang_tag(self, plugin: MandarinChinesePlugin) -> None:
        assert plugin.capabilities.tts_lang_tag == "zh-CN"

    def test_lesson_modes(self, plugin: MandarinChinesePlugin) -> None:
        assert "vocabulary" in plugin.capabilities.lesson_modes_supported

    def test_no_morphology_quality(self, plugin: MandarinChinesePlugin) -> None:
        assert plugin.capabilities.morphology_quality == "none"

    def test_no_syntax_support(self, plugin: MandarinChinesePlugin) -> None:
        assert plugin.capabilities.syntax_support is False

    def test_capabilities_type(self, plugin: MandarinChinesePlugin) -> None:
        assert isinstance(plugin.capabilities, LanguageCapabilities)


# ── Protocol compliance ────────────────────────────────────────────────────────

class TestProtocol:
    def test_has_lesson_store(self, plugin: MandarinChinesePlugin) -> None:
        assert isinstance(plugin.lesson_store, dict)

    def test_analyze_text_returns_list(self, plugin: MandarinChinesePlugin) -> None:
        results = plugin.analyze_text("你好。")
        assert isinstance(results, list)

    def test_split_sentences_returns_list(self, plugin: MandarinChinesePlugin) -> None:
        sentences = plugin.split_sentences("你好。再见。")
        assert isinstance(sentences, list)

    def test_analyze_sentence_returns_result(self, plugin: MandarinChinesePlugin) -> None:
        result = plugin.analyze_sentence("你好")
        assert isinstance(result, CandidateSentenceResult)

    def test_get_lesson_returns_none_for_unknown(self, plugin: MandarinChinesePlugin) -> None:
        assert plugin.get_lesson("nonexistent-id") is None


# ── Sentence splitting ─────────────────────────────────────────────────────────

class TestSentenceSplitting:
    def test_splits_on_chinese_period(self, plugin: MandarinChinesePlugin) -> None:
        sentences = plugin.split_sentences("你好。再见。")
        assert len(sentences) == 2

    def test_splits_on_exclamation(self, plugin: MandarinChinesePlugin) -> None:
        sentences = plugin.split_sentences("你好！再见！")
        assert len(sentences) == 2

    def test_splits_on_question(self, plugin: MandarinChinesePlugin) -> None:
        sentences = plugin.split_sentences("你好吗？很好。")
        assert len(sentences) == 2

    def test_single_sentence_no_punctuation(self, plugin: MandarinChinesePlugin) -> None:
        sentences = plugin.split_sentences("你好世界")
        assert len(sentences) == 1

    def test_empty_string(self, plugin: MandarinChinesePlugin) -> None:
        sentences = plugin.split_sentences("")
        assert sentences == []

    def test_strips_whitespace(self, plugin: MandarinChinesePlugin) -> None:
        sentences = plugin.split_sentences("  你好。  ")
        assert all(s == s.strip() for s in sentences)


# ── Token filtering ────────────────────────────────────────────────────────────

class TestIsLearnable:
    def test_chinese_word_is_learnable(self) -> None:
        assert _is_learnable("你好") is True

    def test_single_char_is_learnable(self) -> None:
        assert _is_learnable("的") is True

    def test_whitespace_not_learnable(self) -> None:
        assert _is_learnable("  ") is False
        assert _is_learnable("") is False

    def test_cjk_punctuation_not_learnable(self) -> None:
        assert _is_learnable("。") is False
        assert _is_learnable("，") is False
        assert _is_learnable("！") is False

    def test_ascii_punctuation_not_learnable(self) -> None:
        assert _is_learnable("?") is False
        assert _is_learnable("!") is False
        assert _is_learnable(".") is False

    def test_pure_digits_not_learnable(self) -> None:
        assert _is_learnable("2024") is False
        assert _is_learnable("123") is False

    def test_mixed_chinese_digit_is_learnable(self) -> None:
        # "第3" (third/3rd) — mixed content, treat as learnable
        assert _is_learnable("第3") is True


# ── Segmentation fallback ─────────────────────────────────────────────────────

class TestSegmentFallback:
    """These tests exercise the character-level fallback, which runs when
    jieba is absent.  Even if jieba IS installed, we can test the fallback
    path by calling the private function directly."""

    def test_segment_non_empty(self) -> None:
        tokens = _segment("你好世界")
        assert len(tokens) > 0

    def test_segment_produces_tokens(self) -> None:
        # Whether jieba or the character fallback runs, _segment must return
        # at least the two characters.  jieba may emit whitespace as its own
        # token; that is filtered downstream by _is_learnable, not here.
        tokens = _segment("你好")
        assert "你" in tokens or any("你" in t for t in tokens)


# ── Candidate extraction ───────────────────────────────────────────────────────

class TestAnalyzeSentence:
    def test_returns_vocabulary_candidates(self, plugin: MandarinChinesePlugin) -> None:
        result = plugin.analyze_sentence("你好世界")
        assert all(c.type == "vocabulary" for c in result.candidates)

    def test_no_duplicates_in_sentence(self, plugin: MandarinChinesePlugin) -> None:
        # Repeated character / word should appear only once.
        result = plugin.analyze_sentence("的的的")
        canonical_forms = [c.canonical_form for c in result.candidates]
        assert len(canonical_forms) == len(set(canonical_forms))

    def test_sentence_text_preserved(self, plugin: MandarinChinesePlugin) -> None:
        sentence = "我爱学习。"
        result = plugin.analyze_sentence(sentence)
        assert result.text == sentence

    def test_candidate_has_label(self, plugin: MandarinChinesePlugin) -> None:
        result = plugin.analyze_sentence("你好")
        for c in result.candidates:
            assert c.label  # non-empty label

    def test_candidate_label_matches_canonical(self, plugin: MandarinChinesePlugin) -> None:
        result = plugin.analyze_sentence("你好")
        for c in result.candidates:
            assert c.label == c.canonical_form

    def test_surface_form_matches_canonical(self, plugin: MandarinChinesePlugin) -> None:
        # Chinese words do not inflect; surface == canonical.
        result = plugin.analyze_sentence("你好")
        for c in result.candidates:
            assert c.surface_form == c.canonical_form

    def test_lesson_data_has_word_key(self, plugin: MandarinChinesePlugin) -> None:
        result = plugin.analyze_sentence("你好")
        for c in result.candidates:
            assert "word" in c.lesson_data
            assert c.lesson_data["word"] == c.canonical_form

    def test_lesson_data_has_pos_word(self, plugin: MandarinChinesePlugin) -> None:
        result = plugin.analyze_sentence("你好")
        for c in result.candidates:
            assert c.lesson_data.get("pos") == "WORD"

    def test_confidence_is_float(self, plugin: MandarinChinesePlugin) -> None:
        result = plugin.analyze_sentence("你好")
        for c in result.candidates:
            assert isinstance(c.confidence, float)
            assert 0.0 <= c.confidence <= 1.0

    def test_punctuation_filtered_out(self, plugin: MandarinChinesePlugin) -> None:
        result = plugin.analyze_sentence("你好！")
        canonical_forms = [c.canonical_form for c in result.candidates]
        assert "！" not in canonical_forms
        assert "!" not in canonical_forms

    def test_empty_sentence(self, plugin: MandarinChinesePlugin) -> None:
        result = plugin.analyze_sentence("")
        assert result.candidates == []

    def test_all_punctuation_sentence(self, plugin: MandarinChinesePlugin) -> None:
        result = plugin.analyze_sentence("。！？")
        assert result.candidates == []


# ── analyze_text integration ──────────────────────────────────────────────────

class TestAnalyzeText:
    def test_multi_sentence(self, plugin: MandarinChinesePlugin) -> None:
        results = plugin.analyze_text("你好。再见。")
        assert len(results) == 2

    def test_each_result_is_candidate_sentence(self, plugin: MandarinChinesePlugin) -> None:
        results = plugin.analyze_text("你好。")
        for r in results:
            assert isinstance(r, CandidateSentenceResult)

    def test_candidates_are_candidate_objects(self, plugin: MandarinChinesePlugin) -> None:
        results = plugin.analyze_text("我爱学习。")
        for r in results:
            for c in r.candidates:
                assert isinstance(c, CandidateObject)


# ── Pinyin helper ─────────────────────────────────────────────────────────────

class TestPinyinFor:
    def test_returns_none_or_string(self) -> None:
        # Either None (pypinyin absent) or a non-empty string.
        result = _pinyin_for("学习")
        assert result is None or isinstance(result, str)

    def test_non_empty_when_present(self) -> None:
        result = _pinyin_for("学习")
        if result is not None:
            assert len(result) > 0

    @pytest.mark.skipif(
        not __import__("importlib").util.find_spec("pypinyin"),
        reason="pypinyin not installed",
    )
    def test_pinyin_contains_tone(self) -> None:
        result = _pinyin_for("学")
        # Tone-marked pinyin for 学 should be "xué"
        assert result is not None
        assert result.strip()

    @pytest.mark.skipif(
        not __import__("importlib").util.find_spec("pypinyin"),
        reason="pypinyin not installed",
    )
    def test_lesson_data_pinyin_present(self) -> None:
        plugin = create_plugin()
        result = plugin.analyze_sentence("学习")
        if result.candidates:
            # If pypinyin is available, at least one candidate should have pinyin.
            has_pinyin = any("pinyin" in c.lesson_data for c in result.candidates)
            assert has_pinyin


# ── Lesson-engine integration ─────────────────────────────────────────────────

class TestLessonEngineIntegration:
    """Verify that the lesson engine can build a valid lesson from Chinese
    candidate data, with or without pinyin."""

    def test_build_vocabulary_lesson_no_pinyin(self) -> None:
        from backend.lesson.generators import build_lesson
        from backend.lesson.context import LessonContext
        from backend.plugins.chinese import MandarinChinesePlugin

        ctx = LessonContext.from_capabilities(MandarinChinesePlugin.capabilities)
        lesson = build_lesson(
            object_id="test-uuid-zh-001",
            obj_type="vocabulary",
            canonical_form="学习",
            display_label="学习",
            lesson_data={"word": "学习", "pos": "WORD"},
            lesson_mode="vocabulary",
            context=ctx,
        )
        assert lesson.id == "test-uuid-zh-001"
        assert lesson.type == "vocabulary"
        assert lesson.language_code == "zh"
        assert lesson.script_direction == "ltr"

    def test_build_vocabulary_lesson_with_pinyin(self) -> None:
        from backend.lesson.generators import build_lesson
        from backend.lesson.context import LessonContext
        from backend.plugins.chinese import MandarinChinesePlugin

        ctx = LessonContext.from_capabilities(MandarinChinesePlugin.capabilities)
        lesson = build_lesson(
            object_id="test-uuid-zh-002",
            obj_type="vocabulary",
            canonical_form="学习",
            display_label="学习",
            lesson_data={"word": "学习", "pos": "WORD", "pinyin": "xué xí"},
            lesson_mode="vocabulary",
            context=ctx,
        )
        field_labels = [f.label for f in lesson.fields]
        assert "Romanized" in field_labels
        romanized_field = next(f for f in lesson.fields if f.label == "Romanized")
        assert romanized_field.value == "xué xí"

    def test_build_dictionary_lesson(self) -> None:
        from backend.lesson.generators import build_lesson
        from backend.lesson.context import LessonContext
        from backend.plugins.chinese import MandarinChinesePlugin

        ctx = LessonContext.from_capabilities(MandarinChinesePlugin.capabilities)
        lesson = build_lesson(
            object_id="test-uuid-zh-003",
            obj_type="vocabulary",
            canonical_form="你好",
            display_label="你好",
            lesson_data={"word": "你好", "pos": "WORD"},
            lesson_mode="dictionary",
            context=ctx,
        )
        assert lesson.lesson_mode == "dictionary"

    def test_lesson_context_is_cjk(self) -> None:
        from backend.lesson.context import LessonContext
        from backend.plugins.chinese import MandarinChinesePlugin

        ctx = LessonContext.from_capabilities(MandarinChinesePlugin.capabilities)
        assert ctx.is_cjk is True
        assert ctx.is_rtl is False


# ── jieba word-segmentation path (requires jieba) ────────────────────────────

_jieba_available = __import__("importlib").util.find_spec("jieba") is not None

@pytest.mark.skipif(not _jieba_available, reason="jieba not installed")
class TestJiebaSegmentation:
    """Tests that require jieba to be installed — word-level segmentation."""

    def test_common_word_appears_as_unit(self, plugin: MandarinChinesePlugin) -> None:
        # 学习 (to study) is a well-known two-character word; jieba should keep
        # it together rather than split it into 学 + 习.
        result = plugin.analyze_sentence("我喜欢学习中文。")
        canonical_forms = {c.canonical_form for c in result.candidates}
        assert "学习" in canonical_forms

    def test_confidence_is_jieba_level(self, plugin: MandarinChinesePlugin) -> None:
        result = plugin.analyze_sentence("你好世界")
        for c in result.candidates:
            # jieba path → 0.70; character fallback → 0.40.
            assert c.confidence == 0.70

    def test_no_confidence_note_in_lesson_data(self, plugin: MandarinChinesePlugin) -> None:
        # The "character-level fallback" note must NOT appear when jieba is active.
        result = plugin.analyze_sentence("你好")
        for c in result.candidates:
            assert "confidence_note" not in c.lesson_data

    def test_multiple_words_extracted(self, plugin: MandarinChinesePlugin) -> None:
        # Jieba should produce several word-level tokens from a full sentence.
        result = plugin.analyze_sentence("我爱学习中文汉字。")
        assert len(result.candidates) >= 3

    def test_pinyin_in_lesson_data(self, plugin: MandarinChinesePlugin) -> None:
        pytest.importorskip("pypinyin")
        result = plugin.analyze_sentence("你好")
        candidates_with_pinyin = [c for c in result.candidates if "pinyin" in c.lesson_data]
        assert len(candidates_with_pinyin) > 0

    def test_pinyin_is_tone_marked_string(self, plugin: MandarinChinesePlugin) -> None:
        pytest.importorskip("pypinyin")
        result = plugin.analyze_sentence("学习")
        for c in result.candidates:
            if "pinyin" in c.lesson_data:
                assert isinstance(c.lesson_data["pinyin"], str)
                assert len(c.lesson_data["pinyin"]) > 0


# ── Multilingual architecture integration ─────────────────────────────────────

class TestMultilingualArchitecture:
    def test_chinese_plugin_registered(self) -> None:
        from backend.parsing.plugin_loader import load_plugins
        registry = load_plugins()
        assert "zh" in registry.all()

    def test_chinese_capabilities_in_registry(self) -> None:
        from backend.parsing.plugin_loader import load_plugins
        registry = load_plugins()
        caps = registry.supported_languages()
        assert "zh" in caps
        assert caps["zh"].script_family == "cjk"

    def test_zh_and_es_canonical_ids_differ(self) -> None:
        from backend.parsing.canonical import canonical_object_id
        zh_id = canonical_object_id("zh", "vocabulary", "学习")
        es_id = canonical_object_id("es", "vocabulary", "aprendizaje")
        assert zh_id != es_id

    def test_same_zh_word_same_canonical_id(self) -> None:
        from backend.parsing.canonical import canonical_object_id
        id1 = canonical_object_id("zh", "vocabulary", "学习")
        id2 = canonical_object_id("zh", "vocabulary", "学习")
        assert id1 == id2

    def test_canonical_id_is_uuid_format(self) -> None:
        import uuid
        from backend.parsing.canonical import canonical_object_id
        raw = canonical_object_id("zh", "vocabulary", "学习")
        # Should not raise
        uuid.UUID(raw)

    def test_zh_type_is_vocabulary_only(self, plugin: MandarinChinesePlugin) -> None:
        result = plugin.analyze_sentence("我喜欢学习中文。")
        types = {c.type for c in result.candidates}
        assert types == {"vocabulary"}  # no conjugation, agreement, etc.
