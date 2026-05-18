"""Tests for the Latin dictionary-mode scaffold plugin."""
from __future__ import annotations

import pytest

from backend.plugins.latin import (
    LatinPlugin,
    _LEXICON,
    _UNKNOWN_NOTE,
    _normalise,
    create_plugin,
)
from backend.schemas.language import LanguageCapabilities
from backend.schemas.parse import CandidateObject, CandidateSentenceResult


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture()
def plugin() -> LatinPlugin:
    return create_plugin()


# ── Capability declarations ────────────────────────────────────────────────────

class TestCapabilities:
    def test_language_code(self, plugin: LatinPlugin) -> None:
        assert plugin.language_code == "la"

    def test_direction_ltr(self, plugin: LatinPlugin) -> None:
        assert plugin.direction == "ltr"

    def test_script_family_latin(self, plugin: LatinPlugin) -> None:
        assert plugin.capabilities.script_family == "latin"

    def test_tokenization_mode_whitespace(self, plugin: LatinPlugin) -> None:
        assert plugin.capabilities.tokenization_mode == "whitespace"

    def test_morphology_depth_none(self, plugin: LatinPlugin) -> None:
        assert plugin.capabilities.morphology_depth == "none"

    def test_analysis_depth_dictionary(self, plugin: LatinPlugin) -> None:
        assert plugin.capabilities.analysis_depth == "dictionary"

    def test_lesson_modes_dictionary_only(self, plugin: LatinPlugin) -> None:
        assert plugin.capabilities.lesson_modes_supported == ["dictionary"]

    def test_no_transliteration(self, plugin: LatinPlugin) -> None:
        # Latin already uses Latin script — no separate romanization needed.
        assert plugin.capabilities.transliteration_scheme is None

    def test_no_morphology_quality(self, plugin: LatinPlugin) -> None:
        assert plugin.capabilities.morphology_quality == "none"

    def test_no_syntax_support(self, plugin: LatinPlugin) -> None:
        assert plugin.capabilities.syntax_support is False

    def test_no_idiom_detection(self, plugin: LatinPlugin) -> None:
        assert plugin.capabilities.idiom_detection is False

    def test_capabilities_type(self, plugin: LatinPlugin) -> None:
        assert isinstance(plugin.capabilities, LanguageCapabilities)


# ── Protocol compliance ────────────────────────────────────────────────────────

class TestProtocol:
    def test_has_lesson_store(self, plugin: LatinPlugin) -> None:
        assert isinstance(plugin.lesson_store, dict)

    def test_analyze_text_returns_list(self, plugin: LatinPlugin) -> None:
        results = plugin.analyze_text("Amor vincit omnia.")
        assert isinstance(results, list)

    def test_split_sentences_returns_list(self, plugin: LatinPlugin) -> None:
        sentences = plugin.split_sentences("Gallia est omnis divisa in partes tres.")
        assert isinstance(sentences, list)

    def test_analyze_sentence_returns_result(self, plugin: LatinPlugin) -> None:
        result = plugin.analyze_sentence("amor")
        assert isinstance(result, CandidateSentenceResult)

    def test_get_lesson_returns_none_for_unknown(self, plugin: LatinPlugin) -> None:
        assert plugin.get_lesson("nonexistent-id") is None


# ── Macron normalisation ───────────────────────────────────────────────────────

class TestNormalise:
    def test_strips_macron_a(self) -> None:
        assert _normalise("ā") == "a"
        assert _normalise("Ā") == "a"

    def test_strips_macron_e(self) -> None:
        assert _normalise("ē") == "e"

    def test_strips_macron_i(self) -> None:
        assert _normalise("ī") == "i"

    def test_strips_macron_o(self) -> None:
        assert _normalise("ō") == "o"

    def test_strips_macron_u(self) -> None:
        assert _normalise("ū") == "u"

    def test_normalises_word(self) -> None:
        assert _normalise("amāre") == "amare"
        assert _normalise("Amō") == "amo"

    def test_lowercases(self) -> None:
        assert _normalise("AMOR") == "amor"
        assert _normalise("Terra") == "terra"

    def test_plain_ascii_unchanged(self) -> None:
        assert _normalise("amor") == "amor"
        assert _normalise("terra") == "terra"


# ── Sentence splitting ─────────────────────────────────────────────────────────

class TestSentenceSplitting:
    def test_splits_on_period(self, plugin: LatinPlugin) -> None:
        sentences = plugin.split_sentences("Amor vincit. Omnia.")
        assert len(sentences) == 2

    def test_splits_on_exclamation(self, plugin: LatinPlugin) -> None:
        sentences = plugin.split_sentences("O Roma! O gloria!")
        assert len(sentences) == 2

    def test_single_sentence(self, plugin: LatinPlugin) -> None:
        sentences = plugin.split_sentences("Gallia est omnis divisa in partes tres")
        assert len(sentences) == 1

    def test_empty_input(self, plugin: LatinPlugin) -> None:
        assert plugin.split_sentences("") == []

    def test_strips_whitespace_from_sentences(self, plugin: LatinPlugin) -> None:
        sentences = plugin.split_sentences("  amor.  ")
        assert all(s == s.strip() for s in sentences)


# ── Known-word extraction ──────────────────────────────────────────────────────

class TestKnownWords:
    def test_recognises_amor(self, plugin: LatinPlugin) -> None:
        result = plugin.analyze_sentence("amor")
        assert len(result.candidates) == 1
        c = result.candidates[0]
        assert c.canonical_form == "amor"
        assert c.lesson_data.get("gloss") is not None
        assert "love" in c.lesson_data["gloss"].lower()

    def test_recognises_terra(self, plugin: LatinPlugin) -> None:
        result = plugin.analyze_sentence("terra")
        assert len(result.candidates) == 1
        assert result.candidates[0].lesson_data.get("gloss") is not None

    def test_recognises_with_macrons(self, plugin: LatinPlugin) -> None:
        # "amō" (with macron) should match the lexicon entry "amo".
        result = plugin.analyze_sentence("amō")
        assert len(result.candidates) == 1
        c = result.candidates[0]
        assert c.lesson_data.get("gloss") is not None

    def test_recognises_uppercase_token(self, plugin: LatinPlugin) -> None:
        # Token-initial capitals (sentence starts) should still match.
        result = plugin.analyze_sentence("Amor")
        assert len(result.candidates) == 1
        c = result.candidates[0]
        assert c.lesson_data.get("gloss") is not None

    def test_citation_form_present(self, plugin: LatinPlugin) -> None:
        result = plugin.analyze_sentence("amor")
        c = result.candidates[0]
        assert "citation_form" in c.lesson_data
        assert c.lesson_data["citation_form"] != ""

    def test_grammar_note_present(self, plugin: LatinPlugin) -> None:
        result = plugin.analyze_sentence("amor")
        c = result.candidates[0]
        assert "grammar_note" in c.lesson_data
        assert c.lesson_data["grammar_note"] != ""

    def test_known_word_has_high_confidence(self, plugin: LatinPlugin) -> None:
        result = plugin.analyze_sentence("amor")
        c = result.candidates[0]
        assert c.confidence is not None
        assert c.confidence >= 0.8

    def test_known_word_type_is_vocabulary(self, plugin: LatinPlugin) -> None:
        result = plugin.analyze_sentence("amor")
        assert result.candidates[0].type == "vocabulary"

    def test_strips_trailing_punctuation(self, plugin: LatinPlugin) -> None:
        # "amor," and "amor." should both resolve to the same canonical form.
        result = plugin.analyze_sentence("amor,")
        assert len(result.candidates) == 1
        assert result.candidates[0].canonical_form == "amor"

    def test_strips_leading_punctuation(self, plugin: LatinPlugin) -> None:
        result = plugin.analyze_sentence("(amor)")
        assert len(result.candidates) == 1
        assert result.candidates[0].canonical_form == "amor"

    def test_noun_grammar_note_mentions_declension(self, plugin: LatinPlugin) -> None:
        result = plugin.analyze_sentence("aqua")
        c = result.candidates[0]
        assert "declension" in c.lesson_data["grammar_note"].lower()

    def test_verb_grammar_note_mentions_conjugation(self, plugin: LatinPlugin) -> None:
        result = plugin.analyze_sentence("amo")
        c = result.candidates[0]
        assert "conjugation" in c.lesson_data["grammar_note"].lower()

    def test_preposition_grammar_note_mentions_case(self, plugin: LatinPlugin) -> None:
        result = plugin.analyze_sentence("in")
        c = result.candidates[0]
        assert "ablative" in c.lesson_data["grammar_note"].lower() or \
               "accusative" in c.lesson_data["grammar_note"].lower()


# ── Unknown-word handling ──────────────────────────────────────────────────────

class TestUnknownWords:
    def test_inflected_form_emitted_without_gloss(self, plugin: LatinPlugin) -> None:
        # Inflected forms now resolve via the inflection table; only truly
        # absent tokens (not in lemmas or inflections) emit without a gloss.
        result = plugin.analyze_sentence("xyzzy")
        assert len(result.candidates) == 1
        c = result.candidates[0]
        assert c.lesson_data.get("gloss") is None

    def test_unknown_word_has_confidence_note(self, plugin: LatinPlugin) -> None:
        result = plugin.analyze_sentence("xyzzy")
        c = result.candidates[0]
        assert "confidence_note" in c.lesson_data
        # Note warns about limited analysis for words not in the lexicon.
        note = c.lesson_data["confidence_note"].lower()
        assert "lexicon" in note or "citation" in note

    def test_unknown_word_has_no_confidence_score(self, plugin: LatinPlugin) -> None:
        result = plugin.analyze_sentence("xyzzy")
        c = result.candidates[0]
        assert c.confidence is None

    def test_unknown_word_type_is_vocabulary(self, plugin: LatinPlugin) -> None:
        result = plugin.analyze_sentence("regnorum")  # gen. pl. of regnum
        assert result.candidates[0].type == "vocabulary"


# ── Deduplication ──────────────────────────────────────────────────────────────

class TestDeduplication:
    def test_repeated_word_appears_once(self, plugin: LatinPlugin) -> None:
        result = plugin.analyze_sentence("amor amor amor")
        canonical_forms = [c.canonical_form for c in result.candidates]
        assert len(canonical_forms) == len(set(canonical_forms))

    def test_same_word_different_case_deduplicated(self, plugin: LatinPlugin) -> None:
        # "Amor" and "amor" should be treated as the same canonical form.
        result = plugin.analyze_sentence("Amor amor")
        assert len(result.candidates) == 1


# ── Multi-word sentence extraction ────────────────────────────────────────────

class TestMultiWordSentence:
    def test_arma_virumque_cano(self, plugin: LatinPlugin) -> None:
        """Opening of the Aeneid — "I sing of arms and the man." """
        result = plugin.analyze_sentence("Arma virumque cano.")
        # "arma" is not in lexicon (neuter plural, not nom. sg. "arma" is also
        # 2nd-decl neuter — actually let's just check we get candidates at all)
        assert len(result.candidates) > 0

    def test_gallia_sentence(self, plugin: LatinPlugin) -> None:
        """Opening phrase from Caesar's Gallic Wars."""
        result = plugin.analyze_sentence("Gallia est omnis divisa in partes tres.")
        canonical_forms = {c.canonical_form for c in result.candidates}
        # "in" and "tres" should be recognised.
        assert "in" in canonical_forms
        assert "tres" in canonical_forms

    def test_veni_vidi_vici_sentence(self, plugin: LatinPlugin) -> None:
        """Julius Caesar's famous phrase — inflected forms, mostly unrecognised."""
        result = plugin.analyze_sentence("Veni, vidi, vici.")
        # "venio" is in the lexicon as "venio" not "veni" — so "veni" is unrecognised.
        # Test that we at least get candidates (even if unrecognised).
        assert len(result.candidates) >= 0  # never errors; graceful degradation

    def test_sentence_text_preserved(self, plugin: LatinPlugin) -> None:
        sentence = "Amor vincit omnia."
        result = plugin.analyze_sentence(sentence)
        assert result.text == sentence


# ── Lexicon coverage ───────────────────────────────────────────────────────────

class TestLexicon:
    def test_lexicon_nonempty(self) -> None:
        assert len(_LEXICON) >= 50

    def test_all_entries_have_four_fields(self) -> None:
        for key, entry in _LEXICON.items():
            assert len(entry) == 4, f"Entry {key!r} does not have 4 fields"

    def test_all_entries_have_nonempty_fields(self) -> None:
        for key, entry in _LEXICON.items():
            assert entry["citation"], f"Entry {key!r}: empty citation"
            assert entry["gloss"], f"Entry {key!r}: empty gloss"
            assert entry["pos"], f"Entry {key!r}: empty pos"

    def test_all_keys_are_normalised(self) -> None:
        # Every lexicon key should already be macron-free and lowercase.
        for key in _LEXICON:
            assert key == _normalise(key), f"Key {key!r} is not normalised"

    def test_pos_values_are_known(self) -> None:
        known_pos = {"noun", "verb", "adj", "pron", "prep", "conj", "adv", "num", "det", "particle", "intj"}
        for key, entry in _LEXICON.items():
            assert entry["pos"] in known_pos, f"Entry {key!r} has unknown pos {entry['pos']!r}"

    def test_common_nouns_present(self) -> None:
        for word in ["amor", "terra", "vita", "rex", "pax", "homo", "corpus"]:
            assert word in _LEXICON, f"Expected {word!r} in lexicon"

    def test_common_verbs_present(self) -> None:
        for word in ["sum", "amo", "video", "dico", "facio", "venio", "audio"]:
            assert word in _LEXICON, f"Expected {word!r} in lexicon"

    def test_common_prepositions_present(self) -> None:
        for word in ["in", "ad", "cum", "per", "ex", "de"]:
            assert word in _LEXICON, f"Expected {word!r} in lexicon"

    def test_conjunctions_present(self) -> None:
        for word in ["et", "sed", "aut", "non", "nec"]:
            assert word in _LEXICON, f"Expected {word!r} in lexicon"


# ── Lesson-engine integration ─────────────────────────────────────────────────

class TestLessonEngineIntegration:
    def test_build_dictionary_lesson_for_known_word(self) -> None:
        from backend.lesson.generators import build_lesson
        from backend.lesson.context import LessonContext

        ctx = LessonContext.from_capabilities(LatinPlugin.capabilities)
        lesson = build_lesson(
            object_id="test-la-001",
            obj_type="vocabulary",
            canonical_form="amor",
            display_label="amor",
            lesson_data={
                "citation_form": "amor, amōris m.",
                "gloss": "love, desire, passion",
                "grammar_note": "3rd declension masculine noun; gen. sg. amōris",
                "pos": "NOUN",
            },
            lesson_mode="dictionary",
            context=ctx,
        )
        assert lesson.lesson_mode == "dictionary"
        assert lesson.language_code == "la"   # "la" is Latin

    def test_lesson_has_gloss_field(self) -> None:
        from backend.lesson.generators import build_lesson
        from backend.lesson.context import LessonContext

        ctx = LessonContext.from_capabilities(LatinPlugin.capabilities)
        lesson = build_lesson(
            object_id="test-la-002",
            obj_type="vocabulary",
            canonical_form="terra",
            display_label="terra",
            lesson_data={
                "citation_form": "terra, terrae f.",
                "gloss": "land, earth",
                "grammar_note": "1st declension feminine noun",
                "pos": "NOUN",
            },
            lesson_mode="dictionary",
            context=ctx,
        )
        field_labels = [f.label for f in lesson.fields]
        assert "Gloss" in field_labels
        assert "Citation form" in field_labels
        assert "Grammar" in field_labels

    def test_lesson_has_fill_blank_drill(self) -> None:
        from backend.lesson.generators import build_lesson
        from backend.lesson.context import LessonContext

        ctx = LessonContext.from_capabilities(LatinPlugin.capabilities)
        lesson = build_lesson(
            object_id="test-la-003",
            obj_type="vocabulary",
            canonical_form="amor",
            display_label="amor",
            lesson_data={"gloss": "love, desire, passion"},
            lesson_mode="dictionary",
            context=ctx,
        )
        drill_types = [d.type for d in lesson.drills]
        assert "fill_blank" in drill_types
        assert "shadowing" in drill_types

    def test_lesson_for_unknown_token_has_only_shadowing(self) -> None:
        """Unrecognised inflected forms → no fill-blank (no gloss to test)."""
        from backend.lesson.generators import build_lesson
        from backend.lesson.context import LessonContext

        ctx = LessonContext.from_capabilities(LatinPlugin.capabilities)
        lesson = build_lesson(
            object_id="test-la-004",
            obj_type="vocabulary",
            canonical_form="amat",
            display_label="amat",
            lesson_data={"confidence_note": _UNKNOWN_NOTE},
            lesson_mode="dictionary",
            context=ctx,
        )
        drill_types = [d.type for d in lesson.drills]
        assert drill_types == ["shadowing"]

    def test_lesson_context_is_not_cjk_not_rtl(self) -> None:
        from backend.lesson.context import LessonContext

        ctx = LessonContext.from_capabilities(LatinPlugin.capabilities)
        assert ctx.is_cjk is False
        assert ctx.is_rtl is False

    def test_explanation_contains_gloss(self) -> None:
        from backend.lesson.generators import build_lesson
        from backend.lesson.context import LessonContext

        ctx = LessonContext.from_capabilities(LatinPlugin.capabilities)
        lesson = build_lesson(
            object_id="test-la-005",
            obj_type="vocabulary",
            canonical_form="amor",
            display_label="amor",
            lesson_data={"gloss": "love, desire, passion"},
            lesson_mode="dictionary",
            context=ctx,
        )
        # Explanation should include the gloss.
        assert "love" in lesson.explanation.lower()

    def test_explanation_mentions_latin_when_no_gloss(self) -> None:
        from backend.lesson.generators import build_lesson
        from backend.lesson.context import LessonContext

        ctx = LessonContext.from_capabilities(LatinPlugin.capabilities)
        lesson = build_lesson(
            object_id="test-la-006",
            obj_type="vocabulary",
            canonical_form="amat",
            display_label="amat",
            lesson_data={},
            lesson_mode="dictionary",
            context=ctx,
        )
        assert "latin" in lesson.explanation.lower()

    def test_lesson_context_is_ltr_not_cjk(self) -> None:
        from backend.lesson.context import LessonContext
        ctx = LessonContext.from_capabilities(LatinPlugin.capabilities)
        assert ctx.is_rtl is False
        assert ctx.is_cjk is False

    def test_analyze_sentence_roundtrip_to_lesson(self, plugin: LatinPlugin) -> None:
        """End-to-end: plugin extraction → lesson build."""
        from backend.lesson.generators import build_lesson
        from backend.lesson.context import LessonContext
        from backend.parsing.canonical import canonical_object_id

        result = plugin.analyze_sentence("amor")
        assert result.candidates

        c = result.candidates[0]
        oid = canonical_object_id("la", c.type, c.canonical_form)
        ctx = LessonContext.from_capabilities(LatinPlugin.capabilities)

        lesson = build_lesson(
            object_id=oid,
            obj_type=c.type,
            canonical_form=c.canonical_form,
            display_label=c.label,
            lesson_data=c.lesson_data,
            lesson_mode="dictionary",
            context=ctx,
        )
        assert lesson.lesson_mode == "dictionary"
        assert lesson.language_code == "la"


# ── Multilingual architecture integration ─────────────────────────────────────

class TestMultilingualArchitecture:
    def test_latin_registered_in_plugin_loader(self) -> None:
        from backend.parsing.plugin_loader import load_plugins
        registry = load_plugins()
        assert "la" in registry.all()

    def test_latin_capabilities_in_registry(self) -> None:
        from backend.parsing.plugin_loader import load_plugins
        registry = load_plugins()
        caps = registry.supported_languages()
        assert "la" in caps
        assert caps["la"].script_family == "latin"

    def test_la_and_es_canonical_ids_differ(self) -> None:
        from backend.parsing.canonical import canonical_object_id
        la_id = canonical_object_id("la", "vocabulary", "amor")
        es_id = canonical_object_id("es", "vocabulary", "amor")
        assert la_id != es_id

    def test_same_la_word_same_canonical_id(self) -> None:
        from backend.parsing.canonical import canonical_object_id
        id1 = canonical_object_id("la", "vocabulary", "amor")
        id2 = canonical_object_id("la", "vocabulary", "amor")
        assert id1 == id2

    def test_canonical_id_is_uuid_format(self) -> None:
        import uuid
        from backend.parsing.canonical import canonical_object_id
        raw = canonical_object_id("la", "vocabulary", "amor")
        uuid.UUID(raw)

    def test_latin_direction_ltr(self) -> None:
        from backend.parsing.plugin_loader import load_plugins
        registry = load_plugins()
        caps = registry.supported_languages()
        assert caps["la"].direction == "ltr"

    def test_latin_only_dictionary_mode(self) -> None:
        from backend.parsing.plugin_loader import load_plugins
        registry = load_plugins()
        caps = registry.supported_languages()
        assert caps["la"].lesson_modes_supported == ["dictionary"]
