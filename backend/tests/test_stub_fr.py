"""Tests for the French stub plugin (backend/tests/plugins/stub_fr.py).

These tests verify that the stub satisfies the LanguagePlugin protocol and
produces structurally valid output.  They do not test linguistic correctness —
the stub uses regex heuristics, not a real NLP model.

Note: the stub is not registered by the plugin loader (no create_plugin()).
The real French plugin is in backend/plugins/french.py.
These tests are kept to verify that the stub class itself remains valid as
a minimal reference for the LanguagePlugin protocol.
"""
from __future__ import annotations

import pytest

from backend.tests.plugins.stub_fr import FrenchStubPlugin
from backend.schemas.parse import CandidateObject, CandidateSentenceResult


@pytest.fixture(scope="module")
def plugin() -> FrenchStubPlugin:
    return FrenchStubPlugin()


# ── Protocol attributes ───────────────────────────────────────────────────────


def test_language_code(plugin: FrenchStubPlugin) -> None:
    assert plugin.language_code == "fr"


def test_display_name(plugin: FrenchStubPlugin) -> None:
    assert "French" in plugin.display_name


def test_direction(plugin: FrenchStubPlugin) -> None:
    assert plugin.direction == "ltr"


# ── Sentence splitting ────────────────────────────────────────────────────────


def test_split_single_sentence(plugin: FrenchStubPlugin) -> None:
    sents = plugin.split_sentences("Bonjour le monde.")
    assert len(sents) == 1
    assert sents[0].strip() == "Bonjour le monde."


def test_split_multiple_sentences(plugin: FrenchStubPlugin) -> None:
    sents = plugin.split_sentences("Bonjour. Comment allez-vous?")
    assert len(sents) >= 2


def test_split_empty_string(plugin: FrenchStubPlugin) -> None:
    assert plugin.split_sentences("") == []


def test_split_returns_non_empty_strings(plugin: FrenchStubPlugin) -> None:
    sents = plugin.split_sentences("Je parle français. Tu parles anglais.")
    assert all(s.strip() for s in sents)


# ── analyze_sentence ──────────────────────────────────────────────────────────


def test_analyze_sentence_returns_candidate_result(plugin: FrenchStubPlugin) -> None:
    result = plugin.analyze_sentence("Le chat dort.")
    assert isinstance(result, CandidateSentenceResult)
    assert result.text == "Le chat dort."


def test_analyze_sentence_candidates_are_candidate_objects(plugin: FrenchStubPlugin) -> None:
    result = plugin.analyze_sentence("La maison est grande.")
    for obj in result.candidates:
        assert isinstance(obj, CandidateObject)


def test_analyze_sentence_text_preserved(plugin: FrenchStubPlugin) -> None:
    sentence = "Où est la bibliothèque?"
    result = plugin.analyze_sentence(sentence)
    assert result.text == sentence


def test_analyze_sentence_stop_words_excluded(plugin: FrenchStubPlugin) -> None:
    result = plugin.analyze_sentence("Le chat et la souris.")
    lemmas = {o.canonical_form for o in result.candidates}
    assert "le" not in lemmas
    assert "et" not in lemmas
    assert "la" not in lemmas


def test_analyze_sentence_content_words_included(plugin: FrenchStubPlugin) -> None:
    result = plugin.analyze_sentence("Le professeur parle français.")
    lemmas = {o.canonical_form for o in result.candidates}
    assert "professeur" in lemmas
    assert "parle" in lemmas or "français" in lemmas


def test_analyze_sentence_no_duplicate_lemmas(plugin: FrenchStubPlugin) -> None:
    result = plugin.analyze_sentence("Le chat mange le poisson.")
    lemmas = [o.canonical_form for o in result.candidates]
    assert len(lemmas) == len(set(lemmas))


def test_analyze_sentence_candidates_have_vocabulary_type(plugin: FrenchStubPlugin) -> None:
    result = plugin.analyze_sentence("La maison est grande.")
    for obj in result.candidates:
        assert obj.type == "vocabulary"


def test_analyze_sentence_lesson_data_has_lemma(plugin: FrenchStubPlugin) -> None:
    result = plugin.analyze_sentence("La maison est grande.")
    for obj in result.candidates:
        assert "lemma" in obj.lesson_data


def test_analyze_sentence_empty_returns_empty_candidates(plugin: FrenchStubPlugin) -> None:
    result = plugin.analyze_sentence("...")
    assert result.candidates == []


# ── analyze_text ──────────────────────────────────────────────────────────────


def test_analyze_text_returns_list(plugin: FrenchStubPlugin) -> None:
    results = plugin.analyze_text("Bonjour. Au revoir.")
    assert isinstance(results, list)
    assert len(results) >= 1


def test_analyze_text_consistent_with_analyze_sentence(plugin: FrenchStubPlugin) -> None:
    text = "Le chat dort. La souris mange."
    multi = plugin.analyze_text(text)
    single = [plugin.analyze_sentence(s) for s in plugin.split_sentences(text)]
    assert len(multi) == len(single)
    for m, s in zip(multi, single):
        assert m.text == s.text
        assert {o.canonical_form for o in m.candidates} == {o.canonical_form for o in s.candidates}


# ── Lesson store ──────────────────────────────────────────────────────────────


def test_get_lesson_missing_returns_none(plugin: FrenchStubPlugin) -> None:
    assert plugin.get_lesson("nonexistent-uuid") is None


def test_lesson_store_accepts_candidate_object(plugin: FrenchStubPlugin) -> None:
    from backend.parsing.canonical import canonical_object_id
    obj_id = canonical_object_id("fr", "vocabulary", "maison")
    cand = CandidateObject(
        canonical_form="maison",
        type="vocabulary",
        label="maison",
        lesson_data={"lemma": "maison"},
    )
    plugin.lesson_store[obj_id] = cand
    stored = plugin.get_lesson(obj_id)
    assert stored is not None
    assert stored.canonical_form == "maison"


# ── Registry integration ──────────────────────────────────────────────────────


def test_real_plugin_factory() -> None:
    # The real French plugin (french.py) exposes create_plugin(); the stub does not.
    from backend.plugins.french import create_plugin
    p = create_plugin()
    assert p.language_code == "fr"
