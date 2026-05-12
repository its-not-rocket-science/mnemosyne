"""Tests for the English plugin (EnglishPlugin).

Covers:
- LanguagePlugin protocol conformance
- Sentence splitting
- Vocabulary extraction: deduplication, case handling, lesson_data shape
- Phrase-family integration: idioms detected, phrase tokens not re-tagged as vocab
- lesson_store isolation
- analyze_text multi-sentence dispatch
"""
from __future__ import annotations

import pytest

from backend.parsing.canonical import canonical_object_id
from backend.plugins.english import EnglishPlugin
from backend.schemas.language import LanguageCapabilities
from backend.schemas.parse import CandidateObject, CandidateSentenceResult


# ── Protocol conformance ──────────────────────────────────────────────────────


class TestEnglishStubProtocol:
    def setup_method(self) -> None:
        self.plugin = EnglishPlugin()

    def test_language_code_is_en(self) -> None:
        assert self.plugin.language_code == "en"

    def test_direction_ltr(self) -> None:
        assert self.plugin.direction == "ltr"

    def test_capabilities_is_language_capabilities(self) -> None:
        assert isinstance(self.plugin.capabilities, LanguageCapabilities)

    def test_capabilities_code_matches_language_code(self) -> None:
        assert self.plugin.capabilities.code == self.plugin.language_code

    def test_capabilities_direction_matches_direction(self) -> None:
        assert self.plugin.capabilities.direction == self.plugin.direction

    def test_split_sentences_returns_list(self) -> None:
        result = self.plugin.split_sentences("Hello. World.")
        assert isinstance(result, list)
        assert all(isinstance(s, str) for s in result)

    def test_analyze_sentence_returns_candidate_result(self) -> None:
        result = self.plugin.analyze_sentence("The quick brown fox.")
        assert isinstance(result, CandidateSentenceResult)
        assert result.text == "The quick brown fox."
        assert isinstance(result.candidates, list)

    def test_get_lesson_returns_none_without_parse_route(self) -> None:
        result = self.plugin.analyze_sentence("The sun shines.")
        for obj in result.candidates:
            obj_id = canonical_object_id("en", obj.type, obj.canonical_form)
            assert self.plugin.get_lesson(obj_id) is None


# ── Sentence splitting ────────────────────────────────────────────────────────


class TestEnglishStubSentenceSplitting:
    def setup_method(self) -> None:
        self.plugin = EnglishPlugin()

    def test_single_sentence_returns_one_item(self) -> None:
        assert len(self.plugin.split_sentences("The cat sat.")) == 1

    def test_two_sentences_returns_two_items(self) -> None:
        result = self.plugin.split_sentences("The cat sat. The dog ran.")
        assert len(result) == 2

    def test_question_mark_splits(self) -> None:
        result = self.plugin.split_sentences("Is it gold? Not always.")
        assert len(result) == 2

    def test_exclamation_splits(self) -> None:
        result = self.plugin.split_sentences("Stop! Go.")
        assert len(result) == 2

    def test_empty_string_returns_empty_list(self) -> None:
        assert self.plugin.split_sentences("") == []

    def test_sentences_are_stripped(self) -> None:
        result = self.plugin.split_sentences("  Hello.  World.  ")
        for s in result:
            assert s == s.strip()


# ── Vocabulary extraction ─────────────────────────────────────────────────────


class TestEnglishStubVocabulary:
    def setup_method(self) -> None:
        self.plugin = EnglishPlugin()

    def _vocab(self, sentence: str) -> list[CandidateObject]:
        result = self.plugin.analyze_sentence(sentence)
        return [c for c in result.candidates if c.type == "vocabulary"]

    def test_extracts_vocabulary(self) -> None:
        assert len(self._vocab("The sun shines.")) >= 1

    def test_lemma_is_lowercase(self) -> None:
        for obj in self._vocab("The Bright Sun Shines."):
            assert obj.canonical_form == obj.canonical_form.lower()

    def test_surface_form_preserves_original_case(self) -> None:
        objs = self._vocab("The Bright Sun.")
        surfaces = {o.surface_form for o in objs}
        # At least one capitalised surface should survive
        assert any(s and s[0].isupper() for s in surfaces)

    def test_no_duplicate_canonical_forms(self) -> None:
        objs = self._vocab("The cat and the dog and the bird.")
        canonical = [o.canonical_form for o in objs]
        assert len(canonical) == len(set(canonical))

    def test_repeated_word_yields_one_candidate(self) -> None:
        objs = self._vocab("Gold gold gold.")
        assert len([o for o in objs if o.canonical_form == "gold"]) == 1

    def test_lesson_data_has_lemma_key(self) -> None:
        for obj in self._vocab("The river flows."):
            assert "lemma" in obj.lesson_data

    def test_lesson_data_lemma_matches_canonical_form(self) -> None:
        for obj in self._vocab("The river flows."):
            assert obj.lesson_data["lemma"] == obj.canonical_form

    def test_confidence_is_none(self) -> None:
        for obj in self._vocab("Simple sentence here."):
            assert obj.confidence is None

    def test_type_is_vocabulary(self) -> None:
        for obj in self._vocab("One two three."):
            assert obj.type == "vocabulary"


# ── Phrase-family integration ─────────────────────────────────────────────────


class TestEnglishStubPhrases:
    def setup_method(self) -> None:
        self.plugin = EnglishPlugin()

    def _candidates(self, sentence: str) -> list[CandidateObject]:
        return self.plugin.analyze_sentence(sentence).candidates

    def _by_type(self, sentence: str, typ: str) -> list[CandidateObject]:
        return [c for c in self._candidates(sentence) if c.type == typ]

    def test_phrase_family_detected(self) -> None:
        candidates = self._candidates("All that glitters is not gold.")
        phrase_objs = [c for c in candidates if c.type == "phrase_family"]
        assert len(phrase_objs) == 1

    def test_phrase_family_type_correct(self) -> None:
        candidates = self._candidates("She hit the nail on the head.")
        phrase_objs = [c for c in candidates if c.type == "phrase_family"]
        assert len(phrase_objs) == 1
        assert phrase_objs[0].lesson_data["family_id"] == "hit_the_nail_on_the_head"

    def test_phrase_tokens_not_double_tagged_as_vocab(self) -> None:
        # "glitters", "gold", etc. are part of the phrase; they must not also
        # appear as standalone vocabulary candidates.
        candidates = self._candidates("All that glitters is not gold.")
        phrase_objs = [c for c in candidates if c.type == "phrase_family"]
        vocab_objs  = [c for c in candidates if c.type == "vocabulary"]
        assert len(phrase_objs) == 1
        phrase_surface = phrase_objs[0].surface_form or ""
        phrase_words   = {w.lower() for w in phrase_surface.split()}
        vocab_lemmas   = {o.canonical_form for o in vocab_objs}
        # No vocabulary candidate should have a lemma that's a core phrase word
        # (the stub skips matched phrase words from the vocabulary pass).
        overlap = phrase_words & vocab_lemmas
        assert not overlap, f"Phrase words leaked into vocabulary: {overlap}"

    def test_no_phrase_match_for_unrelated_sentence(self) -> None:
        candidates = self._candidates("The weather is nice today.")
        phrase_objs = [c for c in candidates if c.type == "phrase_family"]
        assert phrase_objs == []

    def test_analyze_text_dispatches_to_each_sentence(self) -> None:
        results = self.plugin.analyze_text("The sun shines. The moon glows.")
        assert len(results) == 2
        assert all(isinstance(r, CandidateSentenceResult) for r in results)

    def test_analyze_text_preserves_sentence_text(self) -> None:
        results = self.plugin.analyze_text("Hello world. Goodbye now.")
        texts = [r.text for r in results]
        assert "Hello world." in texts
        assert "Goodbye now." in texts


# ── lesson_store isolation ────────────────────────────────────────────────────


class TestEnglishStubLessonStore:
    def setup_method(self) -> None:
        self.plugin = EnglishPlugin()

    def test_missing_id_returns_none(self) -> None:
        assert self.plugin.get_lesson("nonexistent-uuid") is None

    def test_lesson_store_accepts_and_returns_candidate_object(self) -> None:
        obj_id = canonical_object_id("en", "vocabulary", "gold")
        cand = CandidateObject(
            canonical_form="gold",
            type="vocabulary",
            label="gold",
            lesson_data={"lemma": "gold"},
        )
        self.plugin.lesson_store[obj_id] = cand
        stored = self.plugin.get_lesson(obj_id)
        assert stored is not None
        assert stored.canonical_form == "gold"

    def test_lesson_store_independent_across_instances(self) -> None:
        plugin2 = EnglishPlugin()
        obj_id = canonical_object_id("en", "vocabulary", "silver")
        self.plugin.lesson_store[obj_id] = CandidateObject(
            canonical_form="silver", type="vocabulary", label="silver",
            lesson_data={},
        )
        assert plugin2.get_lesson(obj_id) is None
