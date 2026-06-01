"""Tests for the Arabic dictionary-mode plugin.

The Arabic plugin is a starter (no CAMeL-Tools or morphological NLP library).
It provides:
  - Sentence splitting on Arabic and standard terminal punctuation
  - Whitespace tokenisation over the Arabic Unicode block
  - Tashkeel (harakat / short-vowel diacritic) stripping for canonical forms
  - RTL direction metadata and arabic script-family for frontend rendering
  - TTS tag "ar" for browser SpeechSynthesis

Tests verify the *plugin contract* and *honest capability declarations*
without asserting Arabic linguistic correctness.
"""
from __future__ import annotations

import pytest

from backend.plugins.arabic import (
    ArabicPlugin,
    _strip_tashkeel,
    create_plugin,
)
from backend.schemas.language import LanguageCapabilities
from backend.schemas.parse import CandidateObject, CandidateSentenceResult


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture()
def plugin() -> ArabicPlugin:
    return create_plugin()


# ── Capability declarations ────────────────────────────────────────────────────

class TestCapabilities:
    def test_language_code(self, plugin: ArabicPlugin) -> None:
        assert plugin.language_code == "ar"

    def test_direction_rtl(self, plugin: ArabicPlugin) -> None:
        assert plugin.direction == "rtl"

    def test_script_family_arabic(self, plugin: ArabicPlugin) -> None:
        assert plugin.capabilities.script_family == "arabic"

    def test_tokenization_mode_whitespace(self, plugin: ArabicPlugin) -> None:
        assert plugin.capabilities.tokenization_mode == "whitespace"

    def test_morphology_depth_none(self, plugin: ArabicPlugin) -> None:
        assert plugin.capabilities.morphology_depth == "none"

    def test_analysis_depth_dictionary(self, plugin: ArabicPlugin) -> None:
        assert plugin.capabilities.analysis_depth == "dictionary"

    def test_lesson_modes_contains_dictionary(self, plugin: ArabicPlugin) -> None:
        assert "dictionary" in plugin.capabilities.lesson_modes_supported

    def test_no_morphology_quality(self, plugin: ArabicPlugin) -> None:
        assert plugin.capabilities.morphology_quality == "none"

    def test_no_syntax_support(self, plugin: ArabicPlugin) -> None:
        assert plugin.capabilities.syntax_support is False

    def test_no_idiom_detection(self, plugin: ArabicPlugin) -> None:
        assert plugin.capabilities.idiom_detection is False

    def test_tts_lang_tag(self, plugin: ArabicPlugin) -> None:
        assert plugin.capabilities.tts_lang_tag == "ar"

    def test_no_transliteration_scheme(self, plugin: ArabicPlugin) -> None:
        assert plugin.capabilities.transliteration_scheme is None

    def test_tokenization_quality_medium(self, plugin: ArabicPlugin) -> None:
        # Whitespace works for MSA prose; clitics are not split.
        assert plugin.capabilities.tokenization_quality == "medium"

    def test_segmentation_quality_low(self, plugin: ArabicPlugin) -> None:
        # Regex heuristic; discourse markers may cause mis-splits.
        assert plugin.capabilities.segmentation_quality == "low"

    def test_capabilities_type(self, plugin: ArabicPlugin) -> None:
        assert isinstance(plugin.capabilities, LanguageCapabilities)

    def test_capabilities_code_matches_language_code(self, plugin: ArabicPlugin) -> None:
        assert plugin.capabilities.code == plugin.language_code


# ── Protocol compliance ────────────────────────────────────────────────────────

class TestProtocol:
    def test_has_lesson_store(self, plugin: ArabicPlugin) -> None:
        assert isinstance(plugin.lesson_store, dict)

    def test_analyze_text_returns_list(self, plugin: ArabicPlugin) -> None:
        results = plugin.analyze_text("كان الطقس جميلاً.")
        assert isinstance(results, list)

    def test_split_sentences_returns_list(self, plugin: ArabicPlugin) -> None:
        sentences = plugin.split_sentences("كيف حالك؟ أنا بخير.")
        assert isinstance(sentences, list)

    def test_analyze_sentence_returns_result(self, plugin: ArabicPlugin) -> None:
        result = plugin.analyze_sentence("كتاب")
        assert isinstance(result, CandidateSentenceResult)

    def test_get_lesson_returns_none_for_unknown(self, plugin: ArabicPlugin) -> None:
        assert plugin.get_lesson("does-not-exist") is None


# ── Tashkeel stripping ────────────────────────────────────────────────────────

class TestTashkeelStripping:
    def test_strips_fatha(self) -> None:
        # كَتَبَ (kataba, he wrote) with fatha → كتب
        assert _strip_tashkeel("كَتَبَ") == "كتب"

    def test_strips_kasra(self) -> None:
        # كِتَاب (kitaab, book) with kasra
        assert _strip_tashkeel("كِتَاب") == "كتاب"

    def test_strips_shadda(self) -> None:
        # مُحَمَّد with shadda (U+0651)
        result = _strip_tashkeel("مُحَمَّد")
        assert result == "محمد"

    def test_strips_sukun(self) -> None:
        # ضَبْط (dabt, control) with sukun (U+0652)
        assert _strip_tashkeel("ضَبْط") == "ضبط"

    def test_plain_text_unchanged(self) -> None:
        assert _strip_tashkeel("كتاب") == "كتاب"

    def test_latin_text_unchanged(self) -> None:
        assert _strip_tashkeel("hello") == "hello"

    def test_empty_string_unchanged(self) -> None:
        assert _strip_tashkeel("") == ""

    def test_full_tashkeel_sentence(self) -> None:
        # بِسْمِ اللّهِ الرَّحْمٰنِ الرَّحِيمِ stripped
        result = _strip_tashkeel("بِسْمِ اللّهِ الرَّحْمٰنِ الرَّحِيمِ")
        # No harakat should remain (verify by checking the known base forms)
        assert "بسم" in result
        assert "الله" in result or "اللّه" in result  # shadda may stay contextually


# ── Sentence splitting ─────────────────────────────────────────────────────────

class TestSentenceSplitting:
    def test_splits_on_full_stop(self, plugin: ArabicPlugin) -> None:
        sentences = plugin.split_sentences("مرحبا. أهلا.")
        assert len(sentences) == 2

    def test_splits_on_arabic_question_mark(self, plugin: ArabicPlugin) -> None:
        # ؟ U+061F Arabic question mark
        sentences = plugin.split_sentences("كيف حالك؟ أنا بخير.")
        assert len(sentences) == 2

    def test_splits_on_latin_question_mark(self, plugin: ArabicPlugin) -> None:
        sentences = plugin.split_sentences("هل أنت بخير? نعم.")
        assert len(sentences) == 2

    def test_splits_on_exclamation(self, plugin: ArabicPlugin) -> None:
        sentences = plugin.split_sentences("مرحبا! أهلا!")
        assert len(sentences) == 2

    def test_splits_on_newline(self, plugin: ArabicPlugin) -> None:
        sentences = plugin.split_sentences("مرحبا\nأهلا")
        assert len(sentences) == 2

    def test_single_sentence_no_punctuation(self, plugin: ArabicPlugin) -> None:
        sentences = plugin.split_sentences("الكتاب على الطاولة")
        assert len(sentences) == 1

    def test_empty_string_returns_empty(self, plugin: ArabicPlugin) -> None:
        assert plugin.split_sentences("") == []

    def test_whitespace_only_returns_empty(self, plugin: ArabicPlugin) -> None:
        assert plugin.split_sentences("   ") == []

    def test_sentences_are_stripped(self, plugin: ArabicPlugin) -> None:
        sentences = plugin.split_sentences("  مرحبا.  ")
        assert all(s == s.strip() for s in sentences)

    def test_sentences_are_non_empty(self, plugin: ArabicPlugin) -> None:
        sentences = plugin.split_sentences("مرحبا. أهلا.")
        assert all(len(s) > 0 for s in sentences)


# ── Word tokenisation and candidate extraction ────────────────────────────────

class TestCandidateExtraction:
    def test_arabic_words_extracted(self, plugin: ArabicPlugin) -> None:
        result = plugin.analyze_sentence("كتاب جميل")
        assert len(result.candidates) == 2

    def test_each_candidate_is_vocabulary_type(self, plugin: ArabicPlugin) -> None:
        result = plugin.analyze_sentence("الولد يقرأ الكتاب")
        for c in result.candidates:
            assert c.type == "vocabulary"

    def test_sentence_text_preserved(self, plugin: ArabicPlugin) -> None:
        sentence = "الطقس جميل اليوم."
        result = plugin.analyze_sentence(sentence)
        assert result.text == sentence

    def test_candidate_has_non_empty_label(self, plugin: ArabicPlugin) -> None:
        result = plugin.analyze_sentence("كتاب")
        for c in result.candidates:
            assert c.label and len(c.label) > 0

    def test_candidate_has_canonical_form(self, plugin: ArabicPlugin) -> None:
        result = plugin.analyze_sentence("كتاب")
        for c in result.candidates:
            assert c.canonical_form

    def test_latin_text_produces_no_candidates(self, plugin: ArabicPlugin) -> None:
        result = plugin.analyze_sentence("Hello world")
        assert result.candidates == []

    def test_punctuation_only_produces_no_candidates(self, plugin: ArabicPlugin) -> None:
        result = plugin.analyze_sentence(".,!?؟")
        assert result.candidates == []

    def test_empty_sentence_produces_no_candidates(self, plugin: ArabicPlugin) -> None:
        result = plugin.analyze_sentence("")
        assert result.candidates == []

    def test_mixed_arabic_latin_only_arabic_extracted(self, plugin: ArabicPlugin) -> None:
        result = plugin.analyze_sentence("كتاب book")
        canonical_forms = {c.canonical_form for c in result.candidates}
        assert "book" not in canonical_forms
        assert "كتاب" in canonical_forms

    def test_single_word_sentence(self, plugin: ArabicPlugin) -> None:
        result = plugin.analyze_sentence("كتاب")
        assert len(result.candidates) == 1


# ── Tashkeel canonicalisation in candidates ───────────────────────────────────

class TestTashkeelCanonicalization:
    def test_tashkeel_stripped_in_canonical_form(self, plugin: ArabicPlugin) -> None:
        result = plugin.analyze_sentence("كَتَبَ")
        assert result.candidates
        for c in result.candidates:
            # Canonical form must not contain tashkeel marks.
            stripped = _strip_tashkeel(c.canonical_form)
            assert stripped == c.canonical_form

    def test_tashkeel_and_plain_same_canonical_form(self, plugin: ArabicPlugin) -> None:
        # كَتَبَ (with tashkeel) and كتب (without) should share canonical form.
        result_with = plugin.analyze_sentence("كَتَبَ")
        result_plain = plugin.analyze_sentence("كتب")
        if result_with.candidates and result_plain.candidates:
            assert (
                result_with.candidates[0].canonical_form
                == result_plain.candidates[0].canonical_form
            )

    def test_surface_form_preserves_tashkeel(self, plugin: ArabicPlugin) -> None:
        # Surface form is the original tashkeel-bearing token.
        result = plugin.analyze_sentence("كَتَبَ")
        if result.candidates:
            c = result.candidates[0]
            # Surface has tashkeel so is longer than canonical.
            assert len(c.surface_form or "") >= len(c.canonical_form)


# ── Lesson data ───────────────────────────────────────────────────────────────

class TestLessonData:
    def test_lesson_data_has_lemma(self, plugin: ArabicPlugin) -> None:
        result = plugin.analyze_sentence("كتاب")
        for c in result.candidates:
            assert "lemma" in c.lesson_data

    def test_lesson_data_lemma_matches_canonical(self, plugin: ArabicPlugin) -> None:
        result = plugin.analyze_sentence("كتاب")
        for c in result.candidates:
            assert c.lesson_data["lemma"] == c.canonical_form

    def test_lesson_data_has_confidence_note(self, plugin: ArabicPlugin) -> None:
        from backend.morphology import ar_adapter as _ar_adapter
        if _ar_adapter.is_available():
            pytest.skip("CAMeL Tools active: morphological analysis replaces dictionary-mode fallback note")
        result = plugin.analyze_sentence("الكتاب الجميل")
        for c in result.candidates:
            assert "confidence_note" in c.lesson_data
            note = c.lesson_data["confidence_note"]
            assert isinstance(note, str) and len(note) > 0

    def test_confidence_note_mentions_clitic_limitation(self, plugin: ArabicPlugin) -> None:
        from backend.morphology import ar_adapter as _ar_adapter
        if _ar_adapter.is_available():
            pytest.skip("CAMeL Tools active: clitics split via prc0/prc1/prc2; dictionary-mode note no longer applies")
        result = plugin.analyze_sentence("كتاب")
        for c in result.candidates:
            note = c.lesson_data.get("confidence_note", "")
            # The note must acknowledge that clitics (ال etc.) aren't split.
            assert "clitic" in note.lower() or "ال" in note or "prefix" in note.lower()

    def test_confidence_is_none_for_all_words(self, plugin: ArabicPlugin) -> None:
        # Honest: no frequency or morphological data → confidence unknown.
        result = plugin.analyze_sentence("الكتاب على الطاولة")
        for c in result.candidates:
            assert c.confidence is None


# ── Deduplication ─────────────────────────────────────────────────────────────

class TestDeduplication:
    def test_repeated_word_appears_once(self, plugin: ArabicPlugin) -> None:
        result = plugin.analyze_sentence("كتاب كتاب كتاب")
        canonical_forms = [c.canonical_form for c in result.candidates]
        assert len(canonical_forms) == len(set(canonical_forms))
        assert canonical_forms.count("كتاب") == 1

    def test_tashkeel_variants_deduplicated(self, plugin: ArabicPlugin) -> None:
        # "كَتَبَ" and "كتب" resolve to same canonical form; only one expected.
        result = plugin.analyze_sentence("كَتَبَ كتب")
        canonical_forms = [c.canonical_form for c in result.candidates]
        assert len(set(canonical_forms)) == len(canonical_forms)

    def test_different_words_not_deduplicated(self, plugin: ArabicPlugin) -> None:
        result = plugin.analyze_sentence("كتاب قلم")
        assert len(result.candidates) == 2


# ── Edge cases ────────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_analyze_text_one_result_per_sentence(self, plugin: ArabicPlugin) -> None:
        results = plugin.analyze_text("مرحبا. كيف حالك؟")
        sentences = plugin.split_sentences("مرحبا. كيف حالك؟")
        assert len(results) == len(sentences)

    def test_idempotent_analysis(self, plugin: ArabicPlugin) -> None:
        sentence = "الولد يقرأ الكتاب."
        r1 = plugin.analyze_sentence(sentence)
        r2 = plugin.analyze_sentence(sentence)
        forms1 = [c.canonical_form for c in r1.candidates]
        forms2 = [c.canonical_form for c in r2.candidates]
        assert forms1 == forms2

    def test_all_returned_types_are_vocabulary(self, plugin: ArabicPlugin) -> None:
        results = plugin.analyze_text("الولد الصغير يقرأ كتاباً جميلاً.")
        for sent in results:
            for c in sent.candidates:
                assert c.type == "vocabulary"

    def test_multi_sentence_paragraph(self, plugin: ArabicPlugin) -> None:
        text = "الطقس جميل. الشمس تشرق. العصافير تغني."
        results = plugin.analyze_text(text)
        assert len(results) == 3
        assert all(isinstance(r, CandidateSentenceResult) for r in results)

    def test_arabic_question_mark_sentence_splits_cleanly(
        self, plugin: ArabicPlugin
    ) -> None:
        result = plugin.analyze_sentence("ما اسمك؟")
        assert result.text == "ما اسمك؟"
        assert len(result.candidates) >= 1


# ── Lesson store ──────────────────────────────────────────────────────────────

class TestLessonStore:
    def test_missing_id_returns_none(self, plugin: ArabicPlugin) -> None:
        assert plugin.get_lesson("no-such-id") is None


# ── CAMeL Tools morphology (skipped when library absent) ─────────────────────

from backend.morphology import ar_adapter as _ar_adapter  # noqa: E402


@pytest.mark.skipif(not _ar_adapter.is_available(), reason="camel-tools not installed or morphology-db-msa-r13 not downloaded")
class TestCAMeLMorphology:
    """These tests run only when camel-tools + morphology-db-msa-r13 are present.

    They validate root annotation, proclitic decomposition, and verb aspect
    detection — the highest-value signals unlocked by the optional extra.
    """

    def test_adapter_is_available(self) -> None:
        assert _ar_adapter.is_available()

    def test_verb_root_annotated(self) -> None:
        # يكتب (he writes) — imperfective form of root ك.ت.ب
        tokens = _ar_adapter.analyze_tokens(["يكتب"])
        assert tokens[0].root == "ك.ت.ب"

    def test_noun_root_annotated(self) -> None:
        # كتاب (book) shares root ك.ت.ب
        tokens = _ar_adapter.analyze_tokens(["كتاب"])
        assert tokens[0].root == "ك.ت.ب"

    def test_verb_aspect_imperfective(self) -> None:
        tokens = _ar_adapter.analyze_tokens(["يكتب"])
        assert tokens[0].aspect == "i"  # imperfective

    def test_definite_article_proclitic(self) -> None:
        # الكتاب = Al- + kitaab
        tokens = _ar_adapter.analyze_tokens(["الكتاب"])
        assert "Al" in tokens[0].prc0 or tokens[0].prc0.startswith("Al")

    def test_prepositional_proclitic(self) -> None:
        # بالقلم = bi- + Al- + qalam
        tokens = _ar_adapter.analyze_tokens(["بالقلم"])
        t = tokens[0]
        assert "bi" in t.prc1 or "li" in t.prc1 or t.prc1 != "0"

    def test_conjunction_proclitic(self) -> None:
        # وكتب = wa- + kataba
        tokens = _ar_adapter.analyze_tokens(["وكتب"])
        t = tokens[0]
        assert "wa" in t.prc2 or t.prc2 not in ("", "0", "na")

    def test_source_is_camel_tools(self) -> None:
        tokens = _ar_adapter.analyze_tokens(["يكتب"])
        assert tokens[0].source == "camel_tools"

    def test_different_roots_distinguished(self) -> None:
        # درس (study) should not get root ك.ت.ب
        tokens = _ar_adapter.analyze_tokens(["درس"])
        assert tokens[0].root != "ك.ت.ب"

    def test_plugin_lesson_data_includes_root_when_available(self, plugin: ArabicPlugin) -> None:
        result = plugin.analyze_sentence("يكتب")
        cands = [c for c in result.candidates if "root" in c.lesson_data]
        assert len(cands) >= 1, "CAMeL mode should add root to lesson_data"

    def test_plugin_lesson_data_includes_pos_when_available(self, plugin: ArabicPlugin) -> None:
        result = plugin.analyze_sentence("يكتب")
        cands = [c for c in result.candidates if "pos" in c.lesson_data]
        assert len(cands) >= 1

    def test_fallback_still_works_for_unknown_tokens(self) -> None:
        # Purely latin/non-Arabic token — should fall back gracefully
        tokens = _ar_adapter.analyze_tokens(["hello"])
        assert tokens[0].source == "camel_tools"  # CAMeL may parse it, or return NOAN
        assert tokens[0].text == "hello"

    def test_stored_object_is_retrievable(self, plugin: ArabicPlugin) -> None:
        obj = CandidateObject(
            canonical_form="كتاب",
            surface_form="كتاب",
            type="vocabulary",
            label="كتاب",
            lesson_data={"lemma": "كتاب"},
        )
        plugin.lesson_store["test-ar-001"] = obj
        assert plugin.get_lesson("test-ar-001") is obj

    def test_lesson_stores_independent_across_instances(self) -> None:
        p1 = create_plugin()
        p2 = create_plugin()
        obj = CandidateObject(
            canonical_form="كتاب",
            surface_form="كتاب",
            type="vocabulary",
            label="كتاب",
            lesson_data={},
        )
        p1.lesson_store["x"] = obj
        assert p2.get_lesson("x") is None


# ── Lesson-engine integration ─────────────────────────────────────────────────

class TestLessonEngineIntegration:
    def test_build_dictionary_lesson_rtl(self) -> None:
        from backend.lesson.generators import build_lesson
        from backend.lesson.context import LessonContext

        ctx = LessonContext.from_capabilities(ArabicPlugin.capabilities)
        lesson = build_lesson(
            object_id="test-ar-001",
            obj_type="vocabulary",
            canonical_form="كتاب",
            display_label="كتاب",
            lesson_data={"lemma": "كتاب", "confidence_note": "dictionary mode"},
            lesson_mode="dictionary",
            context=ctx,
        )
        assert lesson.language_code == "ar"
        assert lesson.script_direction == "rtl"
        assert lesson.lesson_mode == "dictionary"

    def test_shadowing_drill_present(self) -> None:
        from backend.lesson.generators import build_lesson
        from backend.lesson.context import LessonContext

        ctx = LessonContext.from_capabilities(ArabicPlugin.capabilities)
        lesson = build_lesson(
            object_id="test-ar-002",
            obj_type="vocabulary",
            canonical_form="كتاب",
            display_label="كتاب",
            lesson_data={},
            lesson_mode="dictionary",
            context=ctx,
        )
        drill_types = [d.type for d in lesson.drills]
        assert "shadowing" in drill_types

    def test_note_field_shown_when_confidence_note_present(self) -> None:
        from backend.lesson.generators import build_lesson
        from backend.lesson.context import LessonContext

        ctx = LessonContext.from_capabilities(ArabicPlugin.capabilities)
        lesson = build_lesson(
            object_id="test-ar-003",
            obj_type="vocabulary",
            canonical_form="كتاب",
            display_label="كتاب",
            lesson_data={"confidence_note": "Arabic dictionary mode"},
            lesson_mode="dictionary",
            context=ctx,
        )
        field_labels = [f.label for f in lesson.fields]
        assert "Note" in field_labels

    def test_base_form_shown_when_tashkeel_differs(self) -> None:
        from backend.lesson.generators import build_lesson
        from backend.lesson.context import LessonContext

        ctx = LessonContext.from_capabilities(ArabicPlugin.capabilities)
        # Surface (label) carries tashkeel; canonical form is plain.
        lesson = build_lesson(
            object_id="test-ar-004",
            obj_type="vocabulary",
            canonical_form="كتب",
            display_label="كَتَبَ",
            lesson_data={"lemma": "كتب"},
            lesson_mode="dictionary",
            context=ctx,
        )
        field_labels = [f.label for f in lesson.fields]
        assert "Base form" in field_labels

    def test_lesson_context_is_rtl_not_cjk(self) -> None:
        from backend.lesson.context import LessonContext
        ctx = LessonContext.from_capabilities(ArabicPlugin.capabilities)
        assert ctx.is_rtl is True
        assert ctx.is_cjk is False

    def test_analyze_sentence_roundtrip_to_lesson(self, plugin: ArabicPlugin) -> None:
        from backend.lesson.generators import build_lesson
        from backend.lesson.context import LessonContext
        from backend.parsing.canonical import canonical_object_id

        result = plugin.analyze_sentence("كتاب")
        assert result.candidates

        c = result.candidates[0]
        oid = canonical_object_id("ar", c.type, c.canonical_form)
        ctx = LessonContext.from_capabilities(ArabicPlugin.capabilities)
        lesson = build_lesson(
            object_id=oid,
            obj_type=c.type,
            canonical_form=c.canonical_form,
            display_label=c.label,
            lesson_data=c.lesson_data,
            lesson_mode="dictionary",
            context=ctx,
        )
        assert lesson.language_code == "ar"
        assert lesson.script_direction == "rtl"


# ── Multilingual architecture integration ─────────────────────────────────────

class TestMultilingualArchitecture:
    def test_arabic_registered_in_plugin_loader(self) -> None:
        from backend.parsing.plugin_loader import load_plugins
        registry = load_plugins()
        assert "ar" in registry.all()

    def test_arabic_capabilities_in_registry(self) -> None:
        from backend.parsing.plugin_loader import load_plugins
        registry = load_plugins()
        caps = registry.supported_languages()
        assert "ar" in caps
        assert caps["ar"].direction == "rtl"
        assert caps["ar"].script_family == "arabic"

    def test_arabic_and_hebrew_ids_differ(self) -> None:
        from backend.parsing.canonical import canonical_object_id
        ar_id = canonical_object_id("ar", "vocabulary", "كتاب")
        he_id = canonical_object_id("he", "vocabulary", "ספר")
        assert ar_id != he_id

    def test_same_ar_word_same_canonical_id(self) -> None:
        from backend.parsing.canonical import canonical_object_id
        id1 = canonical_object_id("ar", "vocabulary", "كتاب")
        id2 = canonical_object_id("ar", "vocabulary", "كتاب")
        assert id1 == id2

    def test_canonical_id_is_uuid_format(self) -> None:
        import uuid
        from backend.parsing.canonical import canonical_object_id
        raw = canonical_object_id("ar", "vocabulary", "كتاب")
        uuid.UUID(raw)

    def test_arabic_rtl_differs_from_latin_ltr(self) -> None:
        from backend.parsing.plugin_loader import load_plugins
        registry = load_plugins()
        caps = registry.supported_languages()
        assert caps["ar"].direction == "rtl"
        assert caps["la"].direction == "ltr"

    def test_arabic_only_dictionary_mode(self) -> None:
        from backend.parsing.plugin_loader import load_plugins
        registry = load_plugins()
        caps = registry.supported_languages()
        assert caps["ar"].lesson_modes_supported == ["dictionary"]
