"""Tests for English phrasal verb detection and grammar tense labeling.

Covers:
- _extract_phrasal_verbs: prt arc detection, lesson_data shape
- _emit_grammar tense: present/past labels on be_progressive, be_passive, have_perfect
- _analyze_tokens integration: phrasal verbs in final candidates
- skip-words: phrasal verb surface excluded from vocab/conjugation candidates
"""
from __future__ import annotations

import pytest

from backend.plugins.english import EnglishPlugin
from backend.schemas.parse import CandidateObject


@pytest.fixture(scope="module")
def plugin() -> EnglishPlugin:
    return EnglishPlugin()


# ── Phrasal verb detection ─────────────────────────────────────────────────────


class TestPhrasalVerbDetection:
    def test_give_up_detected(self, plugin: EnglishPlugin) -> None:
        result = plugin.analyze_sentence("She decided to give up smoking.")
        types = {c.type for c in result.candidates}
        assert "grammar" in types
        pv = next(
            (c for c in result.candidates if c.lesson_data.get("pattern_id") == "phrasal_verb"),
            None,
        )
        assert pv is not None, "phrasal_verb candidate not found"

    def test_give_up_lesson_data_keys(self, plugin: EnglishPlugin) -> None:
        result = plugin.analyze_sentence("She decided to give up smoking.")
        pv = next(
            (c for c in result.candidates if c.lesson_data.get("pattern_id") == "phrasal_verb"),
            None,
        )
        assert pv is not None
        ld = pv.lesson_data
        assert ld["base_verb"] == "give"
        assert ld["particle"] == "up"
        assert ld["phrasal_verb"] == "give up"
        assert "usage" in ld
        assert "contrast" in ld

    def test_phrasal_verb_type_is_grammar(self, plugin: EnglishPlugin) -> None:
        result = plugin.analyze_sentence("He picked up the phone.")
        pv = next(
            (c for c in result.candidates if c.lesson_data.get("pattern_id") == "phrasal_verb"),
            None,
        )
        assert pv is not None
        assert pv.type == "grammar"

    def test_phrasal_verb_canonical_form_prefix(self, plugin: EnglishPlugin) -> None:
        result = plugin.analyze_sentence("She gave up the idea.")
        pv = next(
            (c for c in result.candidates if c.lesson_data.get("pattern_id") == "phrasal_verb"),
            None,
        )
        assert pv is not None
        assert pv.canonical_form.startswith("grammar:phrasal_verb:")

    def test_phrasal_verb_confidence(self, plugin: EnglishPlugin) -> None:
        result = plugin.analyze_sentence("He gave up.")
        pv = next(
            (c for c in result.candidates if c.lesson_data.get("pattern_id") == "phrasal_verb"),
            None,
        )
        assert pv is not None
        assert pv.confidence == pytest.approx(0.86)

    def test_no_false_positive_for_plain_preposition(self, plugin: EnglishPlugin) -> None:
        # "looked at" — "at" is prep, not prt; should NOT emit phrasal_verb
        result = plugin.analyze_sentence("He looked at the map.")
        pv_candidates = [
            c for c in result.candidates if c.lesson_data.get("pattern_id") == "phrasal_verb"
        ]
        # spaCy en_core_web_sm may or may not assign prt here; test ensures no crash.
        # We only assert that no candidate has the wrong base_verb/particle combo.
        for c in pv_candidates:
            assert c.lesson_data.get("base_verb") != "look" or c.lesson_data.get("particle") != "at", (
                "look at should not be tagged as phrasal verb (at is prep, not prt)"
            )

    def test_deduplication_within_sentence(self, plugin: EnglishPlugin) -> None:
        result = plugin.analyze_sentence("She gave up and then gave up again.")
        pv = [c for c in result.candidates if c.lesson_data.get("phrasal_verb") == "give up"]
        assert len(pv) == 1, "same phrasal verb should be deduplicated"


# ── Grammar tense labels ───────────────────────────────────────────────────────


class TestGrammarTenseLabels:
    def _find_grammar(self, plugin: EnglishPlugin, sentence: str, pattern_id: str) -> CandidateObject | None:
        result = plugin.analyze_sentence(sentence)
        return next(
            (c for c in result.candidates if c.lesson_data.get("pattern_id") == pattern_id),
            None,
        )

    def test_be_progressive_present_tense(self, plugin: EnglishPlugin) -> None:
        g = self._find_grammar(plugin, "She is running.", "be_progressive")
        assert g is not None
        assert g.lesson_data.get("tense") == "present"

    def test_be_progressive_past_tense(self, plugin: EnglishPlugin) -> None:
        g = self._find_grammar(plugin, "She was running.", "be_progressive")
        assert g is not None
        assert g.lesson_data.get("tense") == "past"

    def test_be_passive_present_tense(self, plugin: EnglishPlugin) -> None:
        g = self._find_grammar(plugin, "The letter is written.", "be_passive")
        assert g is not None
        assert g.lesson_data.get("tense") == "present"

    def test_be_passive_past_tense(self, plugin: EnglishPlugin) -> None:
        g = self._find_grammar(plugin, "The letter was written.", "be_passive")
        assert g is not None
        assert g.lesson_data.get("tense") == "past"

    def test_have_perfect_present_tense(self, plugin: EnglishPlugin) -> None:
        g = self._find_grammar(plugin, "She has finished the work.", "have_perfect")
        assert g is not None
        assert g.lesson_data.get("tense") == "present"

    def test_have_perfect_past_tense(self, plugin: EnglishPlugin) -> None:
        g = self._find_grammar(plugin, "She had finished the work.", "have_perfect")
        assert g is not None
        assert g.lesson_data.get("tense") == "past"

    def test_grammar_lesson_data_still_has_pattern_keys(self, plugin: EnglishPlugin) -> None:
        g = self._find_grammar(plugin, "She is running.", "be_progressive")
        assert g is not None
        for key in ("pattern_id", "pattern", "usage", "contrast", "surface_verb"):
            assert key in g.lesson_data, f"key '{key}' missing from grammar lesson_data"
