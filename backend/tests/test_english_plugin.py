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


class TestEnglishPluginProtocol:
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


class TestEnglishPluginSentenceSplitting:
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


class TestEnglishPluginVocabulary:
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

    def test_confidence_is_scored(self) -> None:
        for obj in self._vocab("Simple sentence here."):
            assert obj.confidence is not None

    def test_type_is_vocabulary(self) -> None:
        for obj in self._vocab("One two three."):
            assert obj.type == "vocabulary"


# ── Phrase-family integration ─────────────────────────────────────────────────


class TestEnglishPluginPhrases:
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


class TestEnglishPluginLessonStore:
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


class TestEnglishPluginNuanceIntegration:
    def setup_method(self) -> None:
        self.plugin = EnglishPlugin()

    def _nuance_types(self, sentence: str) -> set[str]:
        result = self.plugin.analyze_sentence(sentence)
        return {c.lesson_data.get("nuance_type") for c in result.candidates if c.type == "nuance"}

    def test_includes_nuance_from_backend_nuance_en(self) -> None:
        types = self._nuance_types("Could you help, please?")
        assert "politeness" in types

    def test_phrase_family_from_nuance_removes_phrase_tokens_from_vocab(self) -> None:
        result = self.plugin.analyze_sentence("All that glitters is not gold.")
        phrase_words = {
            w.lower()
            for c in result.candidates
            if c.type in {"phrase_family", "idiom"} and c.surface_form
            for w in c.surface_form.split()
        }
        vocab_lemmas = {c.canonical_form for c in result.candidates if c.type == "vocabulary"}
        assert phrase_words.isdisjoint(vocab_lemmas)


# ── Grammar construction detection ───────────────────────────────────────────


class TestEnglishPluginGrammar:
    def setup_method(self) -> None:
        self.plugin = EnglishPlugin()

    def _grammar(self, sentence: str) -> list[CandidateObject]:
        return [c for c in self.plugin.analyze_sentence(sentence).candidates if c.type == "grammar"]

    def _pattern_ids(self, sentence: str) -> set[str]:
        return {c.lesson_data["pattern_id"] for c in self._grammar(sentence)}

    def test_be_progressive_detected(self) -> None:
        assert "be_progressive" in self._pattern_ids("The dog is running in the park.")

    def test_be_passive_detected(self) -> None:
        assert "be_passive" in self._pattern_ids("The letter was written by her.")

    def test_have_perfect_detected(self) -> None:
        assert "have_perfect" in self._pattern_ids("She has finished the work.")

    def test_modal_verb_detected(self) -> None:
        assert "modal_verb" in self._pattern_ids("You should leave now.")

    def test_modal_with_negation_detected(self) -> None:
        assert "modal_verb" in self._pattern_ids("You should not leave now.")

    def test_going_to_future_detected(self) -> None:
        assert "going_to_future" in self._pattern_ids("She is going to leave early.")

    def test_going_to_does_not_emit_be_progressive(self) -> None:
        ids = self._pattern_ids("She is going to leave early.")
        assert "be_progressive" not in ids

    def test_at_most_one_object_per_pattern_type(self) -> None:
        objs = self._grammar("He is running and she is walking.")
        prog_count = sum(1 for o in objs if o.lesson_data["pattern_id"] == "be_progressive")
        assert prog_count <= 1

    def test_multiple_construction_types_in_one_sentence(self) -> None:
        ids = self._pattern_ids("You should leave because she has finished.")
        assert "modal_verb" in ids
        assert "have_perfect" in ids

    def test_grammar_canonical_form_prefix(self) -> None:
        for obj in self._grammar("You should leave now."):
            assert obj.canonical_form.startswith("grammar:")

    def test_grammar_lesson_data_keys_present(self) -> None:
        required = {"pattern_id", "pattern", "usage", "contrast", "surface_verb"}
        for obj in self._grammar("She has finished the work."):
            assert required.issubset(obj.lesson_data.keys())

    def test_progressive_surface_verb_contains_participle(self) -> None:
        objs = self._grammar("The dog is running in the park.")
        prog = next(o for o in objs if o.lesson_data["pattern_id"] == "be_progressive")
        assert "running" in prog.lesson_data["surface_verb"]

    def test_passive_surface_verb_contains_participle(self) -> None:
        objs = self._grammar("The letter was written by her.")
        passive = next(o for o in objs if o.lesson_data["pattern_id"] == "be_passive")
        assert "written" in passive.lesson_data["surface_verb"]

    def test_perfect_surface_verb_contains_participle(self) -> None:
        objs = self._grammar("She has finished the work.")
        perfect = next(o for o in objs if o.lesson_data["pattern_id"] == "have_perfect")
        assert "finished" in perfect.lesson_data["surface_verb"]


# ── Irregular conjugation extraction ─────────────────────────────────────────


class TestEnglishPluginConjugation:
    def setup_method(self) -> None:
        self.plugin = EnglishPlugin()

    def _conj(self, sentence: str) -> list[CandidateObject]:
        return [c for c in self.plugin.analyze_sentence(sentence).candidates if c.type == "conjugation"]

    def _by_lemma(self, sentence: str, lemma: str) -> CandidateObject | None:
        return next(
            (c for c in self._conj(sentence) if c.lesson_data.get("lemma") == lemma),
            None,
        )

    def test_irregular_past_ran(self) -> None:
        obj = self._by_lemma("She ran away.", "run")
        assert obj is not None
        assert obj.lesson_data["tense"] == "past"

    def test_irregular_past_went(self) -> None:
        obj = self._by_lemma("He went home yesterday.", "go")
        assert obj is not None
        assert obj.lesson_data["tense"] == "past"

    def test_copula_was_past(self) -> None:
        obj = self._by_lemma("She was very happy.", "be")
        assert obj is not None
        assert obj.lesson_data["tense"] == "past"

    def test_copula_is_present(self) -> None:
        obj = self._by_lemma("She is very happy.", "be")
        assert obj is not None
        assert obj.lesson_data["tense"] == "present"

    def test_third_sg_present_walks(self) -> None:
        obj = self._by_lemma("She walks to school.", "walk")
        assert obj is not None
        assert obj.lesson_data["tense"] == "present"

    def test_have_auxiliary_has(self) -> None:
        obj = self._by_lemma("She has a book.", "have")
        assert obj is not None

    def test_surface_form_preserved_in_lesson_data(self) -> None:
        obj = self._by_lemma("She ran home.", "run")
        assert obj is not None
        assert obj.lesson_data["surface"].lower() == "ran"

    def test_surface_form_attribute_set(self) -> None:
        obj = self._by_lemma("She ran home.", "run")
        assert obj is not None
        assert obj.surface_form is not None
        assert obj.surface_form.lower() == "ran"

    def test_no_duplicate_lemma_within_sentence(self) -> None:
        objs = self._conj("She ran and ran again.")
        lemmas = [o.lesson_data["lemma"] for o in objs]
        assert len(lemmas) == len(set(lemmas))

    def test_required_lesson_data_keys_present(self) -> None:
        for obj in self._conj("She ran away."):
            assert "lemma" in obj.lesson_data
            assert "surface" in obj.lesson_data
            assert "tense" in obj.lesson_data

    def test_grammar_claimed_surface_not_in_conjugation(self) -> None:
        # "was" claimed by be_passive grammar; conjugation for "be" should be absent
        objs = self._conj("The letter was written by her.")
        be_conj = [o for o in objs if o.lesson_data.get("lemma") == "be"]
        assert be_conj == []

    def test_type_is_conjugation(self) -> None:
        for obj in self._conj("She ran away."):
            assert obj.type == "conjugation"


# ── No duplicate vocabulary overlap ──────────────────────────────────────────


class TestEnglishPluginNoOverlap:
    def setup_method(self) -> None:
        self.plugin = EnglishPlugin()

    def _candidates(self, sentence: str) -> list[CandidateObject]:
        return self.plugin.analyze_sentence(sentence).candidates

    def _by_type(self, candidates: list[CandidateObject], typ: str) -> list[CandidateObject]:
        return [c for c in candidates if c.type == typ]

    def _grammar_surface_words(self, candidates: list[CandidateObject]) -> set[str]:
        return {
            w.lower()
            for c in self._by_type(candidates, "grammar") if c.surface_form
            for w in c.surface_form.split()
        }

    def test_progressive_surface_words_not_in_vocabulary(self) -> None:
        cands = self._candidates("The dog is running in the park.")
        grammar_words = self._grammar_surface_words(cands)
        vocab_lemmas = {c.canonical_form for c in self._by_type(cands, "vocabulary")}
        assert grammar_words.isdisjoint(vocab_lemmas), (
            f"Grammar words leaked into vocabulary: {grammar_words & vocab_lemmas}"
        )

    def test_passive_surface_words_not_in_vocabulary(self) -> None:
        cands = self._candidates("The letter was written by her.")
        grammar_words = self._grammar_surface_words(cands)
        vocab_lemmas = {c.canonical_form for c in self._by_type(cands, "vocabulary")}
        assert grammar_words.isdisjoint(vocab_lemmas), (
            f"Grammar words leaked into vocabulary: {grammar_words & vocab_lemmas}"
        )

    def test_perfect_surface_words_not_in_vocabulary(self) -> None:
        cands = self._candidates("She has finished the work.")
        grammar_words = self._grammar_surface_words(cands)
        vocab_lemmas = {c.canonical_form for c in self._by_type(cands, "vocabulary")}
        assert grammar_words.isdisjoint(vocab_lemmas), (
            f"Grammar words leaked into vocabulary: {grammar_words & vocab_lemmas}"
        )

    def test_conjugation_lemma_not_in_vocabulary(self) -> None:
        # "ran" → conjugation for "run"; "run" should not also appear as vocabulary
        cands = self._candidates("She ran away quickly.")
        conj_lemmas = {c.lesson_data["lemma"] for c in self._by_type(cands, "conjugation")}
        vocab_canonicals = {c.canonical_form for c in self._by_type(cands, "vocabulary")}
        assert conj_lemmas.isdisjoint(vocab_canonicals), (
            f"Conjugation lemmas double-listed as vocabulary: {conj_lemmas & vocab_canonicals}"
        )

    def test_no_canonical_form_appears_in_two_types(self) -> None:
        # Same canonical form must not appear in both vocabulary and conjugation
        cands = self._candidates("She ran away and felt the cold wind.")
        vocab_cf = {c.canonical_form for c in self._by_type(cands, "vocabulary")}
        conj_cf  = {c.canonical_form for c in self._by_type(cands, "conjugation")}
        overlap = vocab_cf & conj_cf
        assert not overlap, f"Canonical forms in both vocab and conjugation: {overlap}"

    def test_grammar_surface_words_not_in_vocabulary_modal(self) -> None:
        cands = self._candidates("You should leave now.")
        grammar_words = self._grammar_surface_words(cands)
        vocab_lemmas = {c.canonical_form for c in self._by_type(cands, "vocabulary")}
        assert grammar_words.isdisjoint(vocab_lemmas), (
            f"Grammar words leaked into vocabulary: {grammar_words & vocab_lemmas}"
        )

    def test_going_to_surface_words_not_in_vocabulary(self) -> None:
        cands = self._candidates("She is going to leave early.")
        grammar_words = self._grammar_surface_words(cands)
        vocab_lemmas = {c.canonical_form for c in self._by_type(cands, "vocabulary")}
        assert grammar_words.isdisjoint(vocab_lemmas), (
            f"Grammar words leaked into vocabulary: {grammar_words & vocab_lemmas}"
        )

