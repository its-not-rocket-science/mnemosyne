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

import logging
import types

import pytest

from backend.parsing.canonical import canonical_object_id
from backend.parsing.plugin_loader import PluginRegistry, load_plugins
from backend.tests.plugins.spanish_stub import SpanishStubPlugin
from backend.schemas.language import LanguageCapabilities
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

    def test_en_plugin_is_real_non_stub_plugin(self) -> None:
        registry = load_plugins()
        plugin = registry.get("en")
        assert plugin.__class__.__module__ == "backend.plugins.english"
        assert plugin.__class__.__name__ == "EnglishPlugin"

    def test_en_plugin_not_routed_through_stub_module(self) -> None:
        registry = load_plugins()
        plugin = registry.get("en")
        module_name = plugin.__class__.__module__.lower()
        assert "stub" not in module_name
        assert "stub_en" not in module_name

    def test_fr_plugin_registered(self) -> None:
        registry = load_plugins()
        assert "fr" in registry.all()

    def test_de_plugin_registered(self) -> None:
        registry = load_plugins()
        assert "de" in registry.all()

    def test_supported_languages_includes_all_active(self) -> None:
        registry = load_plugins()
        langs = registry.supported_languages()
        assert "es" in langs
        assert "en" in langs
        assert "fr" in langs
        assert "de" in langs

    def test_english_available_where_spanish_and_french_are_available(self) -> None:
        registry = load_plugins()
        langs = registry.supported_languages()
        if "es" in langs and "fr" in langs:
            assert "en" in langs

    def test_supported_languages_returns_capabilities_objects(self) -> None:
        registry = load_plugins()
        for code, caps in registry.supported_languages().items():
            assert isinstance(caps, LanguageCapabilities)
            assert caps.code == code

    def test_supported_languages_direction_valid(self) -> None:
        registry = load_plugins()
        for caps in registry.supported_languages().values():
            assert caps.direction in ("ltr", "rtl")

    def test_supported_languages_tokenization_mode_valid(self) -> None:
        registry = load_plugins()
        valid = {"whitespace", "segmented", "character"}
        for caps in registry.supported_languages().values():
            assert caps.tokenization_mode in valid

    def test_supported_languages_morphology_depth_valid(self) -> None:
        registry = load_plugins()
        valid = {"none", "shallow", "rich"}
        for caps in registry.supported_languages().values():
            assert caps.morphology_depth in valid

    def test_supported_languages_lesson_modes_non_empty(self) -> None:
        registry = load_plugins()
        valid = {"morphology", "vocabulary", "dictionary"}
        for caps in registry.supported_languages().values():
            assert len(caps.lesson_modes_supported) >= 1
            assert all(m in valid for m in caps.lesson_modes_supported)

    def test_supported_languages_analysis_depth_valid(self) -> None:
        registry = load_plugins()
        valid = {"full", "morphology_light", "dictionary", "segmentation_only"}
        for caps in registry.supported_languages().values():
            assert caps.analysis_depth in valid

    def test_supported_languages_quality_levels_valid(self) -> None:
        registry = load_plugins()
        valid = {"high", "medium", "low", "none"}
        for caps in registry.supported_languages().values():
            assert caps.segmentation_quality in valid
            assert caps.tokenization_quality in valid
            assert caps.morphology_quality in valid

    def test_supported_languages_feature_flags_are_bool(self) -> None:
        registry = load_plugins()
        for caps in registry.supported_languages().values():
            assert isinstance(caps.syntax_support, bool)
            assert isinstance(caps.idiom_detection, bool)

    def test_spanish_capabilities_rich_morphology(self) -> None:
        registry = load_plugins()
        caps = registry.supported_languages()["es"]
        assert caps.morphology_depth == "rich"
        assert "morphology" in caps.lesson_modes_supported

    def test_spanish_capabilities_v2_fields(self) -> None:
        registry = load_plugins()
        caps = registry.supported_languages()["es"]
        assert caps.analysis_depth == "full"
        assert caps.morphology_quality in ("medium", "high")
        assert caps.syntax_support is True
        assert caps.tts_lang_tag == "es"
        assert caps.transliteration_scheme is None

    def test_english_capabilities_no_morphology(self) -> None:
        registry = load_plugins()
        caps = registry.supported_languages()["en"]
        assert caps.morphology_depth == "rich"
        assert "morphology" in caps.lesson_modes_supported

    def test_english_capabilities_v2_fields(self) -> None:
        registry = load_plugins()
        caps = registry.supported_languages()["en"]
        assert caps.analysis_depth == "full"
        assert caps.morphology_quality == "medium"
        assert caps.syntax_support is True
        assert caps.tts_lang_tag == "en"

    def test_english_display_name_is_english_not_stub(self) -> None:
        registry = load_plugins()
        caps = registry.supported_languages()["en"]
        assert caps.display_name == "English"
        assert "stub" not in caps.display_name.lower()
        assert "fake" not in caps.display_name.lower()
        assert "incomplete" not in caps.display_name.lower()

    def test_french_capabilities_morphology(self) -> None:
        # French now uses the real spaCy plugin (fr_core_news_sm), not the stub.
        registry = load_plugins()
        caps = registry.supported_languages()["fr"]
        assert caps.morphology_depth == "rich"
        assert "morphology" in caps.lesson_modes_supported

    def test_french_capabilities_v2_fields(self) -> None:
        registry = load_plugins()
        caps = registry.supported_languages()["fr"]
        assert caps.analysis_depth == "full"
        assert caps.morphology_quality == "medium"
        assert caps.tts_lang_tag == "fr"


    def test_english_nuance_capabilities_match_spanish_and_french(self) -> None:
        registry = load_plugins()
        en = registry.supported_languages()["en"].nuance_capabilities
        es = registry.supported_languages()["es"].nuance_capabilities
        fr = registry.supported_languages()["fr"].nuance_capabilities
        assert en is not None and es is not None and fr is not None

        assert en.idioms in {"strong", "gold"}
        assert en.phrase_families in {"strong", "gold"}
        assert en.etymology in {"strong", "gold"}

        rank = {"none": 0, "stub": 1, "partial": 2, "strong": 3, "gold": 4}
        assert rank[en.grammar_nuance] >= rank[es.grammar_nuance]
        assert rank[en.grammar_nuance] >= rank[fr.grammar_nuance]

    def test_english_nuance_module_populated(self) -> None:
        sentence = "Could you please make a decision?"
        result = load_plugins().get("en").analyze_sentence(sentence)
        nuance = [c for c in result.candidates if c.type == "nuance"]
        assert nuance, "Expected non-empty nuance output from English plugin"
        assert any(c.lesson_data.get("nuance_type") == "politeness" for c in nuance)

    def test_german_capabilities_morphology(self) -> None:
        registry = load_plugins()
        caps = registry.supported_languages()["de"]
        assert caps.morphology_depth == "rich"
        assert "morphology" in caps.lesson_modes_supported

    def test_german_capabilities_v2_fields(self) -> None:
        registry = load_plugins()
        caps = registry.supported_languages()["de"]
        assert caps.analysis_depth == "full"
        assert caps.morphology_quality == "medium"
        assert caps.tts_lang_tag == "de"
        assert caps.syntax_support is True

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
        with pytest.raises(KeyError, match="xx-unknown"):
            registry.get("xx-unknown")

    def test_all_returns_copy(self) -> None:
        registry = load_plugins()
        copy = registry.all()
        copy["zz"] = None  # type: ignore[assignment]  # intentional None to verify the copy is independent of the registry
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

    def test_capabilities_is_language_capabilities(self) -> None:
        assert isinstance(self.plugin.capabilities, LanguageCapabilities)

    def test_capabilities_code_matches_language_code(self) -> None:
        assert self.plugin.capabilities.code == self.plugin.language_code

    def test_capabilities_direction_matches_direction(self) -> None:
        assert self.plugin.capabilities.direction == self.plugin.direction

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


# ── PluginRegistry edge cases ─────────────────────────────────────────────────


class TestPluginRegistryEdgeCases:
    """Cover the three remaining plugin_loader.py branches."""

    def test_register_duplicate_logs_warning(self, caplog) -> None:
        """Registering two plugins with the same language code logs a warning
        and the newer registration wins."""
        registry = PluginRegistry()
        p1 = SpanishStubPlugin()
        p2 = SpanishStubPlugin()
        registry.register(p1)
        with caplog.at_level(logging.WARNING, logger="backend.parsing.plugin_loader"):
            registry.register(p2)
        assert any("already registered" in r.message for r in caplog.records)
        assert registry.get("es") is p2

    def test_load_plugins_enabled_languages_filter(self, monkeypatch) -> None:
        """When ENABLED_LANGUAGES restricts to a single code, only that plugin
        is registered and the rest are silently skipped."""
        import backend.parsing.plugin_loader as _loader

        class _FakeSettings:
            debug             = True   # suppress production gate
            enabled_languages = ["es"]
            plugin_package    = "backend.plugins"

        monkeypatch.setattr(_loader, "get_settings", lambda: _FakeSettings())
        registry = _loader.load_plugins()
        registered = set(registry.all().keys())
        assert "es" in registered
        assert "en" not in registered
        assert "fr" not in registered

    def test_load_plugins_records_failed_plugin(self, monkeypatch) -> None:
        """A plugin whose create_plugin() raises is recorded in failed_plugins()
        and does not prevent other plugins from loading."""
        import backend.parsing.plugin_loader as _loader

        def _bad_create():
            raise RuntimeError("missing model")

        broken_mod = types.SimpleNamespace(
            __name__="backend.plugins.fake_broken",
            create_plugin=_bad_create,
        )

        class _FakeSettings:
            debug             = True   # suppress production gate
            enabled_languages = None
            plugin_package    = "backend.plugins"

        monkeypatch.setattr(_loader, "_iter_plugin_modules", lambda _: [broken_mod])
        monkeypatch.setattr(_loader, "get_settings", lambda: _FakeSettings())
        registry = _loader.load_plugins()
        failed = registry.failed_plugins()
        assert "backend.plugins.fake_broken" in failed
        assert "RuntimeError" in failed["backend.plugins.fake_broken"]
