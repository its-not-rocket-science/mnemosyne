"""Tests for the plugin loader and SpanishStubPlugin.

These tests never touch spaCy and always run.  They cover:
  - the PluginRegistry loads available plugins
  - the LanguagePlugin protocol contract via the stub implementation
  - SpanishStubPlugin extraction behaviour

To run all tests including the spaCy-backed Spanish plugin, see
test_spanish_spacy.py and ensure es_core_news_sm is installed:
    python -m spacy download es_core_news_sm
"""
from __future__ import annotations

import pytest

from backend.parsing.canonical import canonical_object_id
from backend.parsing.plugin_loader import PluginRegistry, load_plugins
from backend.plugins.spanish_stub import SpanishStubPlugin
from backend.schemas.parse import CandidateObject, CandidateSentenceResult


# ── helpers ───────────────────────────────────────────────────────────────────


def objects_of(result: CandidateSentenceResult, kind: str) -> list[CandidateObject]:
    return [o for o in result.candidates if o.type == kind]


# ── plugin registry ───────────────────────────────────────────────────────────


class TestPluginRegistry:
    def test_load_plugins_returns_registry(self) -> None:
        registry = load_plugins()
        assert isinstance(registry, PluginRegistry)

    def test_es_plugin_registered(self) -> None:
        registry = load_plugins()
        assert "es" in registry.all()

    def test_en_plugin_registered(self) -> None:
        registry = load_plugins()
        assert "en" in registry.all()

    def test_fr_plugin_registered(self) -> None:
        registry = load_plugins()
        assert "fr" in registry.all()

    def test_supported_languages_includes_all_active(self) -> None:
        registry = load_plugins()
        langs = registry.supported_languages()
        assert "es" in langs
        assert "en" in langs
        assert "fr" in langs

    def test_supported_languages_has_expected_fields(self) -> None:
        registry = load_plugins()
        for code, meta in registry.supported_languages().items():
            assert meta["code"] == code
            assert "display_name" in meta
            assert meta["direction"] in ("ltr", "rtl")

    def test_get_returns_correct_plugin(self) -> None:
        registry = load_plugins()
        plugin = registry.get("es")
        assert plugin.language_code == "es"

    def test_get_normalises_case(self) -> None:
        registry = load_plugins()
        # "ES" and "es" should resolve to the same plugin
        assert registry.get("ES").language_code == "es"

    def test_get_unknown_language_raises_key_error(self) -> None:
        registry = load_plugins()
        with pytest.raises(KeyError, match="zh"):
            registry.get("zh")

    def test_all_returns_copy(self) -> None:
        registry = load_plugins()
        copy = registry.all()
        copy["zz"] = None  # type: ignore[assignment]
        assert "zz" not in registry.all()

    def test_spanish_stub_not_in_registry(self) -> None:
        # spanish_stub.py has no create_plugin() — the "es" slot belongs to
        # spanish.py.  If spanish.py fails to load (no model), the slot may be
        # absent; either way the stub must never shadow the real plugin.
        registry = load_plugins()
        plugin = registry.get("es")
        assert type(plugin).__name__ != "SpanishStubPlugin"


# ── SpanishStubPlugin — protocol conformance ─────────────────────────────────


class TestStubProtocol:
    """The stub must satisfy the LanguagePlugin protocol."""

    def setup_method(self) -> None:
        self.plugin = SpanishStubPlugin()

    def test_language_code(self) -> None:
        assert self.plugin.language_code == "es"

    def test_direction_ltr(self) -> None:
        assert self.plugin.direction == "ltr"

    def test_split_sentences_returns_list(self) -> None:
        result = self.plugin.split_sentences("Hola. Yo hablo.")
        assert isinstance(result, list)
        assert all(isinstance(s, str) for s in result)

    def test_analyze_sentence_returns_candidate_result(self) -> None:
        result = self.plugin.analyze_sentence("La casa roja habla.")
        assert isinstance(result, CandidateSentenceResult)
        assert result.text == "La casa roja habla."
        assert isinstance(result.candidates, list)

    def test_get_lesson_returns_none_without_parse_route(self) -> None:
        # lesson_store is only populated by the parse route; direct analyze_sentence
        # calls do not populate it.
        result = self.plugin.analyze_sentence("Hola.")
        for obj in result.candidates:
            obj_id = canonical_object_id("es", obj.type, obj.canonical_form)
            assert self.plugin.get_lesson(obj_id) is None

    def test_canonical_forms_are_non_empty(self) -> None:
        result = self.plugin.analyze_sentence("El gato duerme bien.")
        for obj in result.candidates:
            assert obj.canonical_form, f"Empty canonical_form on {obj!r}"

    def test_confidence_none_or_float_in_range(self) -> None:
        result = self.plugin.analyze_sentence("Los niños juegan mucho.")
        for obj in result.candidates:
            if obj.confidence is not None:
                assert 0.0 < obj.confidence <= 1.0, (
                    f"Confidence out of range: {obj.confidence}"
                )


# ── SpanishStubPlugin — extraction behaviour ─────────────────────────────────


class TestStubVocabulary:
    def setup_method(self) -> None:
        self.plugin = SpanishStubPlugin()

    def test_extracts_vocabulary(self) -> None:
        # "sol" and "pan" end in consonants → NOUN → vocabulary.
        # Words ending in "a"/"o"/"e" are tagged as VERB by the stub heuristic.
        result = self.plugin.analyze_sentence("El sol brilla hoy.")
        assert any(o.type == "vocabulary" for o in result.candidates)

    def test_vocabulary_has_lemma(self) -> None:
        result = self.plugin.analyze_sentence("El libro.")
        for obj in objects_of(result, "vocabulary"):
            assert "lemma" in obj.lesson_data

    def test_no_duplicate_canonical_forms(self) -> None:
        result = self.plugin.analyze_sentence("El libro y el libro viejo.")
        forms = [o.canonical_form for o in result.candidates]
        assert len(forms) == len(set(forms))

    def test_same_word_same_canonical_form_across_sentences(self) -> None:
        # "pan" ends in a consonant → NOUN → vocabulary in both sentences.
        r1 = self.plugin.analyze_sentence("El pan es fresco.")
        r2 = self.plugin.analyze_sentence("No hay pan hoy.")
        forms1 = {o.canonical_form for o in objects_of(r1, "vocabulary")}
        forms2 = {o.canonical_form for o in objects_of(r2, "vocabulary")}
        assert "pan" in forms1 & forms2


class TestStubConjugation:
    def setup_method(self) -> None:
        self.plugin = SpanishStubPlugin()

    def test_finite_verb_tagged_as_conjugation(self) -> None:
        # "hablo" ends in "-o" (first person singular present)
        result = self.plugin.analyze_sentence("Yo hablo español.")
        assert any(o.type == "conjugation" for o in result.candidates)

    def test_conjugation_has_stem_and_form(self) -> None:
        result = self.plugin.analyze_sentence("Ella habla mucho.")
        for obj in objects_of(result, "conjugation"):
            assert "stem" in obj.lesson_data
            assert "form" in obj.lesson_data

    def test_conjugation_canonical_form_stable_across_calls(self) -> None:
        r1 = self.plugin.analyze_sentence("Yo como pizza.")
        r2 = self.plugin.analyze_sentence("Yo como pizza.")
        forms1 = {o.canonical_form for o in objects_of(r1, "conjugation")}
        forms2 = {o.canonical_form for o in objects_of(r2, "conjugation")}
        assert forms1 == forms2


class TestStubAgreement:
    def setup_method(self) -> None:
        self.plugin = SpanishStubPlugin()

    def test_noun_adj_pair_tagged_as_agreement(self) -> None:
        # The stub only produces ADJ for words ending in "os" (stem >= 3).
        # "Los" → NOUN (stem too short), "libros" → ADJ, so libros follows a NOUN.
        result = self.plugin.analyze_sentence("Los libros rojos.")
        assert any(o.type == "agreement" for o in result.candidates)

    def test_agreement_has_noun_and_adjective(self) -> None:
        result = self.plugin.analyze_sentence("El perro negro ladra.")
        for obj in objects_of(result, "agreement"):
            assert "noun" in obj.lesson_data
            assert "adjective" in obj.lesson_data


class TestStubLessonStore:
    def setup_method(self) -> None:
        self.plugin = SpanishStubPlugin()

    def test_missing_id_returns_none(self) -> None:
        assert self.plugin.get_lesson("nonexistent-uuid") is None

    def test_lesson_store_accepts_and_returns_candidate_object(self) -> None:
        obj_id = canonical_object_id("es", "vocabulary", "médico")
        cand = CandidateObject(
            canonical_form="médico",
            type="vocabulary",
            label="médico",
            lesson_data={"lemma": "médico"},
        )
        self.plugin.lesson_store[obj_id] = cand
        stored = self.plugin.get_lesson(obj_id)
        assert stored is not None
        assert stored.canonical_form == "médico"

    def test_lesson_store_independent_across_instances(self) -> None:
        plugin2 = SpanishStubPlugin()
        obj_id = canonical_object_id("es", "vocabulary", "sol")
        self.plugin.lesson_store[obj_id] = CandidateObject(
            canonical_form="sol", type="vocabulary", label="sol", lesson_data={}
        )
        assert plugin2.get_lesson(obj_id) is None
