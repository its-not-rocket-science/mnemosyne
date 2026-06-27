"""Tests for the Persian (Farsi) dictionary-mode plugin.

The Persian plugin provides:
  - Sentence splitting on standard and Arabic-block terminal punctuation
  - Whitespace tokenisation over the Perso-Arabic Unicode block
  - Tashkeel (harakat) stripping for canonical forms
  - RTL direction metadata and arabic script-family for frontend rendering
  - Grammar nuance detection: ra accusative, mi- / nami- aspect, negation,
    formality register (shoma/to), classical register markers

Tests verify the plugin contract and honest capability declarations
without asserting Persian linguistic correctness.
"""
from __future__ import annotations

import pytest

from backend.plugins.persian import (
    PersianPlugin,
    _strip_tashkeel,
    create_plugin,
)
from backend.schemas.language import LanguageCapabilities
from backend.schemas.parse import CandidateObject, CandidateSentenceResult


@pytest.fixture()
def plugin() -> PersianPlugin:
    return create_plugin()


# ── Capability declarations ────────────────────────────────────────────────────

class TestCapabilities:
    def test_language_code(self, plugin: PersianPlugin) -> None:
        assert plugin.language_code == "fa"

    def test_direction_rtl(self, plugin: PersianPlugin) -> None:
        assert plugin.direction == "rtl"

    def test_script_family_arabic(self, plugin: PersianPlugin) -> None:
        assert plugin.capabilities.script_family == "arabic"

    def test_tokenization_mode_whitespace(self, plugin: PersianPlugin) -> None:
        assert plugin.capabilities.tokenization_mode == "whitespace"

    def test_morphology_depth_none(self, plugin: PersianPlugin) -> None:
        assert plugin.capabilities.morphology_depth == "none"

    def test_analysis_depth_dictionary(self, plugin: PersianPlugin) -> None:
        assert plugin.capabilities.analysis_depth == "dictionary"

    def test_lesson_modes(self, plugin: PersianPlugin) -> None:
        assert "vocabulary" in plugin.capabilities.lesson_modes_supported
        assert "dictionary" in plugin.capabilities.lesson_modes_supported

    def test_no_syntax_support(self, plugin: PersianPlugin) -> None:
        assert plugin.capabilities.syntax_support is False

    def test_no_idiom_detection(self, plugin: PersianPlugin) -> None:
        assert plugin.capabilities.idiom_detection is False

    def test_tts_lang_tag(self, plugin: PersianPlugin) -> None:
        assert plugin.capabilities.tts_lang_tag == "fa"

    def test_no_transliteration_scheme(self, plugin: PersianPlugin) -> None:
        assert plugin.capabilities.transliteration_scheme is None

    def test_capabilities_type(self, plugin: PersianPlugin) -> None:
        assert isinstance(plugin.capabilities, LanguageCapabilities)

    def test_capabilities_code_matches_language_code(self, plugin: PersianPlugin) -> None:
        assert plugin.capabilities.code == plugin.language_code

    def test_grammar_nuance_partial(self, plugin: PersianPlugin) -> None:
        assert plugin.capabilities.nuance_capabilities.grammar_nuance == "partial"

    def test_formality_register_partial(self, plugin: PersianPlugin) -> None:
        assert plugin.capabilities.nuance_capabilities.formality_register == "partial"

    def test_cultural_references_partial(self, plugin: PersianPlugin) -> None:
        assert plugin.capabilities.nuance_capabilities.cultural_references == "partial"

    def test_phrase_families_partial(self, plugin: PersianPlugin) -> None:
        assert plugin.capabilities.nuance_capabilities.phrase_families == "partial"

    def test_proverb_tradition_partial(self, plugin: PersianPlugin) -> None:
        assert plugin.capabilities.nuance_capabilities.proverb_tradition == "partial"


# ── Protocol compliance ────────────────────────────────────────────────────────

class TestProtocol:
    def test_has_lesson_store(self, plugin: PersianPlugin) -> None:
        assert isinstance(plugin.lesson_store, dict)

    def test_analyze_text_returns_list(self, plugin: PersianPlugin) -> None:
        results = plugin.analyze_text("کتاب را خواندم.")
        assert isinstance(results, list)

    def test_split_sentences_returns_list(self, plugin: PersianPlugin) -> None:
        sentences = plugin.split_sentences("کجا رفتی؟ خانه بودم.")
        assert isinstance(sentences, list)

    def test_analyze_sentence_returns_result(self, plugin: PersianPlugin) -> None:
        result = plugin.analyze_sentence("کتاب")
        assert isinstance(result, CandidateSentenceResult)

    def test_get_lesson_returns_none_for_unknown(self, plugin: PersianPlugin) -> None:
        assert plugin.get_lesson("does-not-exist") is None


# ── Tashkeel stripping ────────────────────────────────────────────────────────

class TestTashkeelStripping:
    def test_strips_fatha(self) -> None:
        # kataba-style fatha mark removed
        assert _strip_tashkeel("كَتَبَ") == "كتب"

    def test_strips_kasra(self) -> None:
        assert _strip_tashkeel("كِتاب") == "كتاب"

    def test_strips_damma(self) -> None:
        # U+064F damma
        assert _strip_tashkeel("كُتُب") == "كتب"

    def test_plain_text_unchanged(self) -> None:
        assert _strip_tashkeel("کتاب") == "کتاب"

    def test_latin_text_unchanged(self) -> None:
        assert _strip_tashkeel("hello") == "hello"

    def test_empty_string_unchanged(self) -> None:
        assert _strip_tashkeel("") == ""


# ── Sentence splitting ─────────────────────────────────────────────────────────

class TestSentenceSplitting:
    def test_splits_on_full_stop(self, plugin: PersianPlugin) -> None:
        sentences = plugin.split_sentences("سلام. خداحافظ.")
        assert len(sentences) == 2

    def test_splits_on_arabic_question_mark(self, plugin: PersianPlugin) -> None:
        sentences = plugin.split_sentences("کجا رفتی؟ خانه بودم.")
        assert len(sentences) == 2

    def test_splits_on_latin_question_mark(self, plugin: PersianPlugin) -> None:
        sentences = plugin.split_sentences("حالت خوب است? بله.")
        assert len(sentences) == 2

    def test_splits_on_exclamation(self, plugin: PersianPlugin) -> None:
        sentences = plugin.split_sentences("سلام! خوش آمدید!")
        assert len(sentences) == 2

    def test_splits_on_newline(self, plugin: PersianPlugin) -> None:
        sentences = plugin.split_sentences("سلام\nخداحافظ")
        assert len(sentences) == 2

    def test_single_sentence_no_punctuation(self, plugin: PersianPlugin) -> None:
        sentences = plugin.split_sentences("کتاب روی میز است")
        assert len(sentences) == 1

    def test_empty_string_returns_empty(self, plugin: PersianPlugin) -> None:
        assert plugin.split_sentences("") == []

    def test_whitespace_only_returns_empty(self, plugin: PersianPlugin) -> None:
        assert plugin.split_sentences("   ") == []

    def test_sentences_are_stripped(self, plugin: PersianPlugin) -> None:
        sentences = plugin.split_sentences("  سلام.  ")
        assert all(s == s.strip() for s in sentences)

    def test_sentences_are_non_empty(self, plugin: PersianPlugin) -> None:
        sentences = plugin.split_sentences("سلام. خداحافظ.")
        assert all(len(s) > 0 for s in sentences)


# ── Word tokenisation and candidate extraction ────────────────────────────────

class TestCandidateExtraction:
    def test_persian_words_extracted(self, plugin: PersianPlugin) -> None:
        result = plugin.analyze_sentence("کتاب خوب")
        vocab = [c for c in result.candidates if c.type == "vocabulary"]
        assert len(vocab) == 2

    def test_ra_particle_extracted(self, plugin: PersianPlugin) -> None:
        result = plugin.analyze_sentence("کتاب را خواندم")
        canonical_forms = {c.canonical_form for c in result.candidates}
        # "را" surfaces as a vocabulary candidate (letter run)
        assert "را" in canonical_forms

    def test_each_candidate_is_vocabulary_or_nuance(self, plugin: PersianPlugin) -> None:
        result = plugin.analyze_sentence("من کتاب را خواندم.")
        allowed = {"vocabulary", "nuance"}
        for c in result.candidates:
            assert c.type in allowed

    def test_sentence_text_preserved(self, plugin: PersianPlugin) -> None:
        sentence = "کتاب روی میز است."
        result = plugin.analyze_sentence(sentence)
        assert result.text == sentence

    def test_candidate_has_non_empty_label(self, plugin: PersianPlugin) -> None:
        result = plugin.analyze_sentence("کتاب")
        for c in result.candidates:
            assert c.label and len(c.label) > 0

    def test_candidate_has_canonical_form(self, plugin: PersianPlugin) -> None:
        result = plugin.analyze_sentence("کتاب")
        for c in result.candidates:
            assert c.canonical_form

    def test_latin_text_produces_no_vocab_candidates(self, plugin: PersianPlugin) -> None:
        result = plugin.analyze_sentence("Hello world")
        vocab = [c for c in result.candidates if c.type == "vocabulary"]
        assert len(vocab) == 0

    def test_punctuation_only_produces_no_candidates(self, plugin: PersianPlugin) -> None:
        result = plugin.analyze_sentence(".,!?؟")
        assert result.candidates == []

    def test_empty_sentence_produces_no_candidates(self, plugin: PersianPlugin) -> None:
        result = plugin.analyze_sentence("")
        assert result.candidates == []

    def test_single_word_sentence(self, plugin: PersianPlugin) -> None:
        result = plugin.analyze_sentence("کتاب")
        vocab = [c for c in result.candidates if c.type == "vocabulary"]
        assert len(vocab) == 1

    def test_lesson_data_has_lemma(self, plugin: PersianPlugin) -> None:
        result = plugin.analyze_sentence("کتاب")
        for c in result.candidates:
            if c.type == "vocabulary":
                assert "lemma" in c.lesson_data

    def test_confidence_is_none_for_vocabulary(self, plugin: PersianPlugin) -> None:
        result = plugin.analyze_sentence("کتاب روی میز")
        for c in result.candidates:
            if c.type == "vocabulary":
                assert c.confidence is None


# ── ZWNJ compound forms ────────────────────────────────────────────────────────

class TestZWNJCompounds:
    def test_mi_konam_splits_at_zwnj(self, plugin: PersianPlugin) -> None:
        # mi-konam = mi + ZWNJ + konam; WORD_RE should split into two tokens
        result = plugin.analyze_sentence("می‌کنم")
        vocab_forms = {c.canonical_form for c in result.candidates if c.type == "vocabulary"}
        # The letter-run before ZWNJ is "می" and after is "کنم"
        assert "می" in vocab_forms or "کنم" in vocab_forms

    def test_mi_raftan_triggers_mi_nuance(self, plugin: PersianPlugin) -> None:
        # می‌رفتم = I was going; should fire mi_imperfective nuance
        result = plugin.analyze_sentence("دیروز می‌رفتم به بازار")
        nuance_types = {
            c.lesson_data.get("nuance_type")
            for c in result.candidates
            if c.type == "nuance"
        }
        assert "mi_imperfective" in nuance_types


# ── Nuance detection ──────────────────────────────────────────────────────────

class TestNuanceDetection:
    def test_ra_accusative_nuance(self, plugin: PersianPlugin) -> None:
        result = plugin.analyze_sentence("من کتاب را خواندم.")
        nuance = [c for c in result.candidates if c.type == "nuance" and c.lesson_data.get("nuance_type") == "ra_accusative"]
        assert len(nuance) == 1
        assert nuance[0].confidence >= 0.9

    def test_ra_nuance_has_required_lesson_keys(self, plugin: PersianPlugin) -> None:
        result = plugin.analyze_sentence("کتاب را دیدم.")
        nuance = [c for c in result.candidates if c.lesson_data.get("nuance_type") == "ra_accusative"]
        assert nuance
        for key in ("nuance_type", "explanation", "register", "learner_level", "source"):
            assert key in nuance[0].lesson_data

    def test_mi_imperfective_nuance(self, plugin: PersianPlugin) -> None:
        result = plugin.analyze_sentence("من می‌روم به خانه.")
        nuance_types = {c.lesson_data.get("nuance_type") for c in result.candidates if c.type == "nuance"}
        assert "mi_imperfective" in nuance_types

    def test_nami_negative_nuance(self, plugin: PersianPlugin) -> None:
        result = plugin.analyze_sentence("نمی‌دانم چرا.")
        nuance_types = {c.lesson_data.get("nuance_type") for c in result.candidates if c.type == "nuance"}
        assert "nami_negative" in nuance_types

    def test_nami_does_not_also_fire_mi(self, plugin: PersianPlugin) -> None:
        # A sentence with only nami- should not also produce mi_imperfective
        result = plugin.analyze_sentence("نمی‌دانم.")
        nuance_types = {c.lesson_data.get("nuance_type") for c in result.candidates if c.type == "nuance"}
        assert "nami_negative" in nuance_types
        assert "mi_imperfective" not in nuance_types

    def test_nist_negation_nuance(self, plugin: PersianPlugin) -> None:
        result = plugin.analyze_sentence("او اینجا نیست.")
        nuance_types = {c.lesson_data.get("nuance_type") for c in result.candidates if c.type == "nuance"}
        assert "negation_nist" in nuance_types

    def test_formality_shoma_nuance(self, plugin: PersianPlugin) -> None:
        result = plugin.analyze_sentence("شما کجا می‌روید؟")
        nuance_types = {c.lesson_data.get("nuance_type") for c in result.candidates if c.type == "nuance"}
        assert "formality_shoma" in nuance_types

    def test_formality_to_nuance(self, plugin: PersianPlugin) -> None:
        result = plugin.analyze_sentence("تو کتاب داری؟")
        nuance_types = {c.lesson_data.get("nuance_type") for c in result.candidates if c.type == "nuance"}
        assert "formality_to" in nuance_types

    def test_classical_register_hamana(self, plugin: PersianPlugin) -> None:
        result = plugin.analyze_sentence("همانا این حق است.")
        nuance_types = {c.lesson_data.get("nuance_type") for c in result.candidates if c.type == "nuance"}
        assert "classical_register" in nuance_types

    def test_no_nuance_on_plain_sentence(self, plugin: PersianPlugin) -> None:
        # Simple sentence with no nuance markers
        result = plugin.analyze_sentence("کتاب روی میز است.")
        nuance = [c for c in result.candidates if c.type == "nuance"]
        # نیست is not present, و/ای not present — no grammar nuance should fire
        nuance_types = {c.lesson_data.get("nuance_type") for c in nuance}
        assert "ra_accusative" not in nuance_types
        assert "mi_imperfective" not in nuance_types
        assert "nami_negative" not in nuance_types


# ── Deduplication ─────────────────────────────────────────────────────────────

class TestDeduplication:
    def test_repeated_word_appears_once(self, plugin: PersianPlugin) -> None:
        result = plugin.analyze_sentence("کتاب کتاب کتاب")
        canonical_forms = [c.canonical_form for c in result.candidates]
        assert len(canonical_forms) == len(set(canonical_forms))
        assert canonical_forms.count("کتاب") == 1

    def test_different_words_not_deduplicated(self, plugin: PersianPlugin) -> None:
        result = plugin.analyze_sentence("کتاب قلم")
        vocab = [c for c in result.candidates if c.type == "vocabulary"]
        assert len(vocab) == 2


# ── Edge cases ────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_analyze_text_one_result_per_sentence(self, plugin: PersianPlugin) -> None:
        results = plugin.analyze_text("سلام. حالت چطور است؟")
        sentences = plugin.split_sentences("سلام. حالت چطور است؟")
        assert len(results) == len(sentences)

    def test_idempotent_analysis(self, plugin: PersianPlugin) -> None:
        sentence = "من کتاب را خواندم."
        r1 = plugin.analyze_sentence(sentence)
        r2 = plugin.analyze_sentence(sentence)
        forms1 = [c.canonical_form for c in r1.candidates]
        forms2 = [c.canonical_form for c in r2.candidates]
        assert forms1 == forms2

    def test_multi_sentence_paragraph(self, plugin: PersianPlugin) -> None:
        text = "هوا خوب است. خورشید می‌تابد. پرنده‌ها آواز می‌خوانند."
        results = plugin.analyze_text(text)
        assert len(results) == 3
        assert all(isinstance(r, CandidateSentenceResult) for r in results)


# ── Lesson store ──────────────────────────────────────────────────────────────

class TestLessonStore:
    def test_missing_id_returns_none(self, plugin: PersianPlugin) -> None:
        assert plugin.get_lesson("no-such-id") is None

    def test_stored_object_is_retrievable(self, plugin: PersianPlugin) -> None:
        obj = CandidateObject(
            canonical_form="کتاب",
            surface_form="کتاب",
            type="vocabulary",
            label="کتاب",
            lesson_data={"lemma": "کتاب"},
        )
        plugin.lesson_store["test-fa-001"] = obj
        assert plugin.get_lesson("test-fa-001") is obj

    def test_lesson_stores_independent_across_instances(self) -> None:
        p1 = create_plugin()
        p2 = create_plugin()
        obj = CandidateObject(
            canonical_form="کتاب",
            surface_form="کتاب",
            type="vocabulary",
            label="کتاب",
            lesson_data={},
        )
        p1.lesson_store["x"] = obj
        assert p2.get_lesson("x") is None


# ── Lesson engine integration ─────────────────────────────────────────────────

class TestLessonEngineIntegration:
    def test_build_dictionary_lesson_rtl(self) -> None:
        from backend.lesson.generators import build_lesson
        from backend.lesson.context import LessonContext

        ctx = LessonContext.from_capabilities(PersianPlugin.capabilities)
        lesson = build_lesson(
            object_id="test-fa-001",
            obj_type="vocabulary",
            canonical_form="کتاب",
            display_label="کتاب",
            lesson_data={"lemma": "کتاب"},
            lesson_mode="dictionary",
            context=ctx,
        )
        assert lesson.language_code == "fa"
        assert lesson.script_direction == "rtl"
        assert lesson.lesson_mode == "dictionary"

    def test_lesson_context_is_rtl_not_cjk(self) -> None:
        from backend.lesson.context import LessonContext
        ctx = LessonContext.from_capabilities(PersianPlugin.capabilities)
        assert ctx.is_rtl is True
        assert ctx.is_cjk is False

    def test_analyze_sentence_roundtrip_to_lesson(self, plugin: PersianPlugin) -> None:
        from backend.lesson.generators import build_lesson
        from backend.lesson.context import LessonContext
        from backend.parsing.canonical import canonical_object_id

        result = plugin.analyze_sentence("کتاب")
        assert result.candidates

        c = next(c for c in result.candidates if c.type == "vocabulary")
        oid = canonical_object_id("fa", c.type, c.canonical_form)
        ctx = LessonContext.from_capabilities(PersianPlugin.capabilities)
        lesson = build_lesson(
            object_id=oid,
            obj_type=c.type,
            canonical_form=c.canonical_form,
            display_label=c.label,
            lesson_data=c.lesson_data,
            lesson_mode="dictionary",
            context=ctx,
        )
        assert lesson.language_code == "fa"
        assert lesson.script_direction == "rtl"


# ── Multilingual architecture integration ─────────────────────────────────────

class TestMultilingualArchitecture:
    def test_persian_registered_in_plugin_loader(self) -> None:
        from backend.parsing.plugin_loader import load_plugins
        registry = load_plugins()
        assert "fa" in registry.all()

    def test_persian_capabilities_in_registry(self) -> None:
        from backend.parsing.plugin_loader import load_plugins
        registry = load_plugins()
        caps = registry.supported_languages()
        assert "fa" in caps
        assert caps["fa"].direction == "rtl"
        assert caps["fa"].script_family == "arabic"

    def test_persian_rtl_different_from_latin_ltr(self) -> None:
        from backend.parsing.plugin_loader import load_plugins
        registry = load_plugins()
        caps = registry.supported_languages()
        assert caps["fa"].direction == "rtl"
        assert caps.get("de", caps.get("es")).direction == "ltr"

    def test_canonical_id_is_uuid_format(self) -> None:
        import uuid
        from backend.parsing.canonical import canonical_object_id
        raw = canonical_object_id("fa", "vocabulary", "کتاب")
        uuid.UUID(raw)

    def test_same_fa_word_same_canonical_id(self) -> None:
        from backend.parsing.canonical import canonical_object_id
        id1 = canonical_object_id("fa", "vocabulary", "کتاب")
        id2 = canonical_object_id("fa", "vocabulary", "کتاب")
        assert id1 == id2

    def test_persian_and_arabic_ids_differ(self) -> None:
        from backend.parsing.canonical import canonical_object_id
        fa_id = canonical_object_id("fa", "vocabulary", "کتاب")
        ar_id = canonical_object_id("ar", "vocabulary", "كتاب")
        assert fa_id != ar_id
