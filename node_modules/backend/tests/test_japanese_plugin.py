"""Tests for the spaCy-backed Japanese plugin (backend/plugins/japanese.py).

The entire module is skipped when spaCy or ja_core_news_sm is not installed
so the CI baseline stays green.

To enable these tests, install the model once:
    python -m spacy download ja_core_news_sm

Design intent
─────────────
These tests verify:

- Structural correctness: required lesson_data keys, confidence ranges, no
  duplicate canonical forms, graceful absence on punctuation-only input.
- Japanese-specific features: katakana→hiragana reading conversion, particle
  (ADP) tokens excluded from vocabulary, CJK lemmas preserved, segmented
  tokenization mode, hiragana transliteration_scheme.
- Architecture: canonical forms use the same cross-language UUID scheme.
- Vocabulary-only output (no conjugation or case_agreement types).

Known ja_core_news_sm limitations that tests deliberately work around:
- Reading is absent for some rare vocabulary and all-kana words.
- な-adjectives may be tagged NOUN; tests accept both ADJ and NOUN for
  な-adjective forms.
- Particle は is both a topic marker and the copula; reliably tagged ADP.
"""
from __future__ import annotations

import pytest

from backend.parsing.canonical import canonical_object_id
from backend.schemas.parse import CandidateObject, CandidateSentenceResult


# ── skip guard ────────────────────────────────────────────────────────────────

def _spacy_available() -> bool:
    try:
        import spacy  # noqa: PLC0415
        spacy.load("ja_core_news_sm")
        return True
    except (ImportError, OSError):
        return False


pytestmark = pytest.mark.skipif(
    not _spacy_available(),
    reason="spaCy + ja_core_news_sm not installed; "
           "run: python -m spacy download ja_core_news_sm",
)


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def plugin():
    from backend.plugins.japanese import JapanesePlugin
    return JapanesePlugin()


# ── helpers ───────────────────────────────────────────────────────────────────

def objects_of(result: CandidateSentenceResult, kind: str) -> list[CandidateObject]:
    return [o for o in result.candidates if o.type == kind]


def confidences_valid(objects: list[CandidateObject]) -> bool:
    return all(0.0 < o.confidence <= 1.0 for o in objects if o.confidence is not None)


def is_hiragana(text: str) -> bool:
    """True when all characters in text are hiragana or are safe non-letter chars."""
    return all("\u3041" <= c <= "\u3096" or c in " ー" for c in text)


# ── capabilities ──────────────────────────────────────────────────────────────


class TestCapabilities:
    def test_language_code(self, plugin) -> None:
        assert plugin.language_code == "ja"

    def test_display_name(self, plugin) -> None:
        assert "Japanese" in plugin.display_name

    def test_direction_is_ltr(self, plugin) -> None:
        assert plugin.direction == "ltr"

    def test_script_family_cjk(self, plugin) -> None:
        assert plugin.capabilities.script_family == "cjk"

    def test_tokenization_mode_segmented(self, plugin) -> None:
        assert plugin.capabilities.tokenization_mode == "segmented"

    def test_morphology_depth_shallow(self, plugin) -> None:
        assert plugin.capabilities.morphology_depth == "shallow"

    def test_lesson_modes_includes_vocabulary(self, plugin) -> None:
        assert "vocabulary" in plugin.capabilities.lesson_modes_supported

    def test_analysis_depth_full(self, plugin) -> None:
        assert plugin.capabilities.analysis_depth == "full"

    def test_tts_lang_tag(self, plugin) -> None:
        assert plugin.capabilities.tts_lang_tag == "ja"

    def test_transliteration_scheme_hiragana(self, plugin) -> None:
        assert plugin.capabilities.transliteration_scheme == "hiragana"

    def test_syntax_support_false(self, plugin) -> None:
        assert plugin.capabilities.syntax_support is False

    def test_idiom_detection_false(self, plugin) -> None:
        assert plugin.capabilities.idiom_detection is False

    def test_morphology_quality_low(self, plugin) -> None:
        assert plugin.capabilities.morphology_quality == "low"

    def test_segmentation_quality_high(self, plugin) -> None:
        assert plugin.capabilities.segmentation_quality == "high"


# ── sentence splitting ────────────────────────────────────────────────────────


class TestSentenceSplitting:
    def test_single_sentence_japanese(self, plugin) -> None:
        sents = plugin.split_sentences("私は本を読みます。")
        assert len(sents) >= 1

    def test_empty_returns_empty(self, plugin) -> None:
        assert plugin.split_sentences("") == []

    def test_returns_non_empty_strings(self, plugin) -> None:
        sents = plugin.split_sentences("東京は大きい都市です。私は学生です。")
        assert all(s.strip() for s in sents)

    def test_analyze_sentence_text_preserved(self, plugin) -> None:
        sentence = "猫が寝ています。"
        result = plugin.analyze_sentence(sentence)
        assert result.text == sentence

    def test_analyze_sentence_returns_result_type(self, plugin) -> None:
        result = plugin.analyze_sentence("犬が走る。")
        assert isinstance(result, CandidateSentenceResult)


# ── vocabulary extraction ─────────────────────────────────────────────────────


class TestVocabularyExtraction:
    def test_noun_extracted(self, plugin) -> None:
        result = plugin.analyze_sentence("東京は日本の首都です。")
        vocab = objects_of(result, "vocabulary")
        nouns = [o for o in vocab if o.lesson_data.get("pos") in ("NOUN", "PROPN")]
        assert any(nouns), "Expected at least one NOUN or PROPN"

    def test_vocabulary_has_lemma_key(self, plugin) -> None:
        result = plugin.analyze_sentence("犬が走る。")
        for obj in objects_of(result, "vocabulary"):
            assert "lemma" in obj.lesson_data

    def test_vocabulary_has_pos_key(self, plugin) -> None:
        result = plugin.analyze_sentence("大きな犬が走る。")
        for obj in objects_of(result, "vocabulary"):
            assert "pos" in obj.lesson_data

    def test_cjk_lemmas_preserved(self, plugin) -> None:
        """CJK characters must not be stripped or transliterated in lemma."""
        result = plugin.analyze_sentence("本を読む。")
        vocab = objects_of(result, "vocabulary")
        for obj in vocab:
            assert any("\u3000" <= c or c >= "\u4E00" for c in obj.canonical_form
                       if c > "\u00FF"), "Expected CJK in at least one canonical form"

    def test_vocabulary_confidence_in_range(self, plugin) -> None:
        result = plugin.analyze_sentence("赤い車が速く走る。")
        assert confidences_valid(objects_of(result, "vocabulary"))

    def test_vocabulary_no_duplicates(self, plugin) -> None:
        result = plugin.analyze_sentence("犬と犬が走る。")
        forms = [o.canonical_form for o in objects_of(result, "vocabulary")]
        assert len(forms) == len(set(forms))

    def test_punctuation_only_returns_empty(self, plugin) -> None:
        result = plugin.analyze_sentence("。")
        assert result.candidates == []

    def test_proper_noun_confidence_lower(self, plugin) -> None:
        result = plugin.analyze_sentence("東京は首都です。")
        vocab = objects_of(result, "vocabulary")
        proper = [o for o in vocab if o.lesson_data.get("pos") == "PROPN"]
        for p in proper:
            if p.confidence is not None:
                assert p.confidence <= 0.65


# ── particle filtering ────────────────────────────────────────────────────────


class TestParticleFiltering:
    def test_adp_particles_not_in_vocabulary(self, plugin) -> None:
        """Particles (ADP) like は、が、を must be excluded from vocabulary."""
        result = plugin.analyze_sentence("私は本を読みます。")
        vocab = objects_of(result, "vocabulary")
        pos_tags = {o.lesson_data.get("pos") for o in vocab}
        assert "ADP" not in pos_tags, (
            f"ADP particles should not appear in vocabulary; pos_tags={pos_tags}"
        )

    def test_no_conjugation_type_emitted(self, plugin) -> None:
        """Japanese plugin is vocabulary-only; no conjugation objects."""
        result = plugin.analyze_sentence("私は走る。")
        assert not any(objects_of(result, "conjugation")), (
            "Japanese plugin should not emit conjugation objects"
        )

    def test_no_case_agreement_type_emitted(self, plugin) -> None:
        """Japanese plugin is vocabulary-only; no case_agreement objects."""
        result = plugin.analyze_sentence("大きい犬が走る。")
        assert not any(objects_of(result, "case_agreement")), (
            "Japanese plugin should not emit case_agreement objects"
        )

    def test_aux_particles_not_in_vocabulary(self, plugin) -> None:
        """AUX tokens (ます, た, ない…) must not appear in vocabulary."""
        result = plugin.analyze_sentence("彼は走ります。")
        vocab = objects_of(result, "vocabulary")
        pos_tags = {o.lesson_data.get("pos") for o in vocab}
        assert "AUX" not in pos_tags, (
            f"AUX should not appear in vocabulary; pos_tags={pos_tags}"
        )


# ── reading (hiragana) ────────────────────────────────────────────────────────


class TestHiraganaReading:
    def test_reading_is_hiragana_not_katakana(self, plugin) -> None:
        """Stored readings must be hiragana, not katakana."""
        result = plugin.analyze_sentence("東京に行く。")
        vocab = objects_of(result, "vocabulary")
        for obj in vocab:
            reading = obj.lesson_data.get("reading")
            if reading:
                # Must not contain katakana (U+30A1–U+30F6)
                katakana_chars = [c for c in reading if "\u30A1" <= c <= "\u30F6"]
                assert not katakana_chars, (
                    f"Reading {reading!r} contains katakana; expected hiragana"
                )

    def test_reading_contains_hiragana(self, plugin) -> None:
        """Readings for kanji words should contain hiragana characters."""
        result = plugin.analyze_sentence("東京は首都です。")
        vocab = objects_of(result, "vocabulary")
        has_reading = [o for o in vocab if "reading" in o.lesson_data]
        if has_reading:
            for obj in has_reading:
                reading = obj.lesson_data["reading"]
                assert any("\u3041" <= c <= "\u3096" for c in reading), (
                    f"Expected hiragana in reading, got: {reading!r}"
                )

    def test_reading_is_string(self, plugin) -> None:
        result = plugin.analyze_sentence("本を読む。")
        vocab = objects_of(result, "vocabulary")
        for obj in vocab:
            if "reading" in obj.lesson_data:
                assert isinstance(obj.lesson_data["reading"], str)

    def test_missing_reading_has_confidence_note(self, plugin) -> None:
        """When reading is absent, confidence_note should explain it."""
        result = plugin.analyze_sentence("本を読む。")
        vocab = objects_of(result, "vocabulary")
        for obj in vocab:
            if "reading" not in obj.lesson_data:
                assert "confidence_note" in obj.lesson_data, (
                    f"Expected confidence_note when reading absent for {obj.canonical_form!r}"
                )


# ── kata_to_hira helper ───────────────────────────────────────────────────────


class TestKataToHiraHelper:
    def test_katakana_converted_to_hiragana(self) -> None:
        from backend.plugins.japanese import _kata_to_hira
        assert _kata_to_hira("トウキョウ") == "とうきょう"

    def test_non_katakana_unchanged(self) -> None:
        from backend.plugins.japanese import _kata_to_hira
        assert _kata_to_hira("hello") == "hello"

    def test_mixed_input(self) -> None:
        from backend.plugins.japanese import _kata_to_hira
        result = _kata_to_hira("シュト")
        assert result == "しゅと"

    def test_hiragana_passthrough(self) -> None:
        from backend.plugins.japanese import _kata_to_hira
        # Hiragana is below the katakana range — should pass through unchanged.
        assert _kata_to_hira("あいう") == "あいう"

    def test_boundary_katakana_a(self) -> None:
        """U+30A1 (ァ small a) is the first katakana in the range."""
        from backend.plugins.japanese import _kata_to_hira
        result = _kata_to_hira("\u30A1")
        assert result == "\u3041"

    def test_boundary_katakana_n(self) -> None:
        """U+30F6 (ヶ) is the last katakana in the conversion range."""
        from backend.plugins.japanese import _kata_to_hira
        result = _kata_to_hira("\u30F6")
        assert result == "\u3096"


# ── edge cases ────────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_single_word_analyzed(self, plugin) -> None:
        result = plugin.analyze_sentence("猫")
        assert any(result.candidates)

    def test_analyze_text_multi_sentence(self, plugin) -> None:
        results = plugin.analyze_text("犬が走る。猫が寝る。")
        assert len(results) >= 2

    def test_analyze_text_consistent_with_analyze_sentence(self, plugin) -> None:
        text = "本を読む。犬が走る。"
        multi  = plugin.analyze_text(text)
        single = [plugin.analyze_sentence(s) for s in plugin.split_sentences(text)]
        assert len(multi) == len(single)
        for m, s in zip(multi, single):
            assert m.text == s.text
            assert {o.canonical_form for o in m.candidates} == {o.canonical_form for o in s.candidates}

    def test_only_vocabulary_and_nuance_types_emitted(self, plugin) -> None:
        result = plugin.analyze_sentence("東京は大きな都市です。")
        allowed = {"vocabulary", "nuance"}
        for obj in result.candidates:
            assert obj.type in allowed, (
                f"Unexpected type {obj.type!r} for {obj.canonical_form!r}"
            )


# ── lesson store ──────────────────────────────────────────────────────────────


class TestLessonStore:
    def test_missing_id_returns_none(self, plugin) -> None:
        assert plugin.get_lesson("nonexistent-uuid") is None

    def test_lesson_store_accepts_and_returns_object(self, plugin) -> None:
        obj_id = canonical_object_id("ja", "vocabulary", "猫")
        cand = CandidateObject(
            canonical_form="猫",
            type="vocabulary",
            label="猫",
            lesson_data={"lemma": "猫", "pos": "NOUN", "reading": "ねこ"},
        )
        plugin.lesson_store[obj_id] = cand
        stored = plugin.get_lesson(obj_id)
        assert stored is not None
        assert stored.canonical_form == "猫"

    def test_lesson_store_independent_across_instances(self) -> None:
        from backend.plugins.japanese import JapanesePlugin
        p1 = JapanesePlugin()
        p2 = JapanesePlugin()
        obj_id = canonical_object_id("ja", "vocabulary", "犬")
        p1.lesson_store[obj_id] = CandidateObject(
            canonical_form="犬", type="vocabulary", label="犬", lesson_data={}
        )
        assert p2.get_lesson(obj_id) is None


# ── multilingual architecture ─────────────────────────────────────────────────


class TestMultilingualArchitecture:
    def test_japanese_registered_in_plugin_loader(self) -> None:
        from backend.parsing.plugin_loader import load_plugins
        registry = load_plugins()
        assert "ja" in registry.all()

    def test_japanese_capabilities_in_registry(self) -> None:
        from backend.parsing.plugin_loader import load_plugins
        registry = load_plugins()
        caps = registry.supported_languages()["ja"]
        assert caps.script_family == "cjk"
        assert caps.transliteration_scheme == "hiragana"

    def test_japanese_and_chinese_vocab_ids_differ(self) -> None:
        ja_id = canonical_object_id("ja", "vocabulary", "犬")
        zh_id = canonical_object_id("zh", "vocabulary", "犬")
        assert ja_id != zh_id

    def test_japanese_and_korean_vocab_ids_differ(self) -> None:
        ja_id = canonical_object_id("ja", "vocabulary", "猫")
        ko_id = canonical_object_id("ko", "vocabulary", "猫")
        assert ja_id != ko_id

    def test_japanese_has_hiragana_scheme_arabic_has_none(self) -> None:
        from backend.plugins.arabic import ArabicPlugin
        ar = ArabicPlugin()
        assert ar.capabilities.transliteration_scheme is None
        # Japanese plugin has hiragana
        from backend.plugins.japanese import JapanesePlugin
        ja = JapanesePlugin()
        assert ja.capabilities.transliteration_scheme == "hiragana"

    def test_japanese_vocabulary_only_no_morphology_mode(self, plugin) -> None:
        """Japanese plugin does not claim morphology lesson mode."""
        assert "morphology" not in plugin.capabilities.lesson_modes_supported


# ── Nuance extraction ─────────────────────────────────────────────────────────

class TestNuanceExtraction:
    def test_particle_wa_emitted(self, plugin) -> None:
        result = plugin.analyze_sentence("猫は魚を食べる。")
        nuance = [c for c in result.candidates if c.type == "nuance"]
        particles = [c for c in nuance if c.lesson_data.get("nuance_type") == "particle"]
        assert any(c.canonical_form == "nuance:ja:particle:は" for c in particles), (
            "topic particle は should be extracted"
        )

    def test_particle_wo_emitted(self, plugin) -> None:
        result = plugin.analyze_sentence("猫は魚を食べる。")
        nuance = [c for c in result.candidates if c.type == "nuance"]
        assert any(c.canonical_form == "nuance:ja:particle:を" for c in nuance)

    def test_keigo_teineigo_detected(self, plugin) -> None:
        result = plugin.analyze_sentence("東京は大きな都市です。")
        nuance = [c for c in result.candidates if c.type == "nuance"]
        keigo = [c for c in nuance if c.lesson_data.get("nuance_type") == "keigo"]
        assert any(c.lesson_data.get("keigo_type") == "teineigo" for c in keigo), (
            "です ending should trigger teineigo keigo nuance"
        )

    def test_yojijukugo_detected(self, plugin) -> None:
        result = plugin.analyze_sentence("一石二鳥だ。")
        nuance = [c for c in result.candidates if c.type == "nuance"]
        yoji = [c for c in nuance if c.lesson_data.get("nuance_type") == "yojijukugo"]
        assert any(c.canonical_form == "nuance:ja:yojijukugo:一石二鳥" for c in yoji)

    def test_nuance_candidates_not_duplicated(self, plugin) -> None:
        result = plugin.analyze_sentence("先生が学校に来ました。")
        cfs = [c.canonical_form for c in result.candidates]
        assert len(cfs) == len(set(cfs)), "duplicate canonical forms found"

    def test_nuance_type_field_present(self, plugin) -> None:
        result = plugin.analyze_sentence("猫は魚を食べる。")
        for cand in result.candidates:
            if cand.type == "nuance":
                assert "nuance_type" in cand.lesson_data
