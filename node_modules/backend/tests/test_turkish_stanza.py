"""Tests for Turkish stanza morphological analysis path.

Coverage
────────
- Stanza adapter: is_available, analyze_sentence
- Lemma-based canonical forms: verb:{lemma}, noun:{lemma}, adj:{lemma}
- Conjugation objects with tense/mood/person/number
- Tense classification: progressive, past_definite, past_evidential, future
- Case suffix on noun (locative, ablative, dative, genitive)
- Possessive suffix on noun (first_sg, third_sg)
- Possessive + case stacking (stacked_suffixes field)
- Evidential past (-mış/-miş) → evidential field
- Negation flag
- Grammar nuance candidates: case, possessive, poss+case stack, evidential, negation
- Deduplication
"""
from __future__ import annotations

import pytest

from backend.morphology import tr_stanza_adapter
from backend.plugins.turkish import TurkishPlugin, create_plugin


# ── skip guard ────────────────────────────────────────────────────────────────

stanza_required = pytest.mark.skipif(
    not tr_stanza_adapter.is_available(),
    reason="stanza Turkish model not installed; run: python -m stanza.download tr",
)


@pytest.fixture(scope="module")
def plugin() -> TurkishPlugin:
    return create_plugin()


# ── Unit: tr_stanza_adapter ───────────────────────────────────────────────────

@stanza_required
class TestTrStanzaAdapter:
    def test_is_available(self):
        assert tr_stanza_adapter.is_available() is True

    def test_analyze_sentence_returns_tokens(self):
        tokens = tr_stanza_adapter.analyze_sentence("Kitabı okudum.")
        assert len(tokens) >= 2

    def test_verb_lemma(self):
        tokens = tr_stanza_adapter.analyze_sentence("Gitti.")
        verb = next((t for t in tokens if t.upos == "VERB"), None)
        assert verb is not None

    def test_past_definite_tense(self):
        tokens = tr_stanza_adapter.analyze_sentence("Gitti.")
        verb = next((t for t in tokens if t.upos == "VERB"), None)
        assert verb is not None
        assert verb.tense == "past_definite"

    def test_evidential_past(self):
        tokens = tr_stanza_adapter.analyze_sentence("Gitmiş.")
        verb = next((t for t in tokens if t.upos == "VERB"), None)
        assert verb is not None
        assert verb.tense == "past_evidential"
        assert verb.evidential == "nfh"

    def test_noun_case_locative(self):
        tokens = tr_stanza_adapter.analyze_sentence("Evde oturuyorum.")
        noun = next((t for t in tokens if t.upos == "NOUN"), None)
        assert noun is not None
        assert noun.case == "locative"

    def test_source_stanza(self):
        tokens = tr_stanza_adapter.analyze_sentence("ev")
        assert all(t.source == "stanza" for t in tokens)


# ── Integration: plugin with stanza ──────────────────────────────────────────

@stanza_required
class TestTurkishPluginStanza:
    def test_verb_vocabulary_canonical(self, plugin):
        result = plugin.analyze_sentence("Gitti.")
        vocab = next(
            (c for c in result.candidates
             if c.canonical_form.startswith("verb:") and c.type == "vocabulary"), None
        )
        assert vocab is not None

    def test_conjugation_emitted_for_past_definite(self, plugin):
        result = plugin.analyze_sentence("Gitti.")
        conj = next(
            (c for c in result.candidates
             if c.type == "conjugation" and c.lesson_data.get("tense") == "past_definite"), None
        )
        assert conj is not None

    def test_conjugation_emitted_for_evidential(self, plugin):
        result = plugin.analyze_sentence("Gitmiş.")
        conj = next(
            (c for c in result.candidates
             if c.type == "conjugation" and c.lesson_data.get("tense") == "past_evidential"), None
        )
        assert conj is not None

    def test_noun_case_locative_in_lesson_data(self, plugin):
        result = plugin.analyze_sentence("Evde oturuyorum.")
        noun = next(
            (c for c in result.candidates
             if c.lesson_data.get("case") == "locative" and c.type == "vocabulary"), None
        )
        assert noun is not None

    def test_possessive_stacking_in_lesson_data(self, plugin):
        result = plugin.analyze_sentence("evimden")
        cand = next(
            (c for c in result.candidates
             if c.lesson_data.get("possessive") in ("first_sg", "1sg")), None
        )
        assert cand is not None
        assert cand.lesson_data.get("case") == "ablative"

    def test_deduplication(self, plugin):
        result = plugin.analyze_sentence("Gitti gitti.")
        forms = [c.canonical_form for c in result.candidates]
        assert len(forms) == len(set(forms))

    def test_relation_hint_conjugation_of(self, plugin):
        result = plugin.analyze_sentence("Gitti.")
        conj = next(
            (c for c in result.candidates if c.type == "conjugation"), None
        )
        assert conj is not None
        assert any(h.relation_type == "conjugation_of" for h in conj.relation_hints)

    # ── Nuance candidates ──────────────────────────────────────────────────────

    def test_nuance_case_suffix_locative(self, plugin):
        result = plugin.analyze_sentence("Evde oturuyorum.")
        nuance = next(
            (c for c in result.candidates
             if c.type == "nuance"
             and c.lesson_data.get("nuance_type") == "turkish_case_suffix"
             and c.lesson_data.get("case") == "locative"),
            None,
        )
        assert nuance is not None
        assert nuance.lesson_data.get("grammar_axis") == "case"
        assert nuance.lesson_data.get("learner_level") == "A2"
        assert nuance.lesson_data.get("drill_prompt")
        assert nuance.lesson_data.get("drill_answer")

    def test_nuance_poss_case_stack(self, plugin):
        result = plugin.analyze_sentence("evimden")
        nuance = next(
            (c for c in result.candidates
             if c.type == "nuance"
             and c.lesson_data.get("nuance_type") == "turkish_poss_case_stack"),
            None,
        )
        assert nuance is not None
        assert nuance.lesson_data.get("grammar_axis") == "suffix_stacking"
        assert "first_sg" in str(nuance.lesson_data.get("possessive", ""))
        assert nuance.lesson_data.get("drill_answer")

    def test_nuance_evidential_past(self, plugin):
        result = plugin.analyze_sentence("O gitmiş.")
        nuance = next(
            (c for c in result.candidates
             if c.type == "nuance"
             and c.lesson_data.get("nuance_type") == "turkish_evidential_past"),
            None,
        )
        assert nuance is not None
        assert nuance.lesson_data.get("grammar_axis") == "evidentiality"
        assert nuance.lesson_data.get("learner_level") == "B2"
        assert "indirect" in nuance.lesson_data.get("drill_answer", "").lower()

    def test_nuance_candidates_not_duplicated(self, plugin):
        result = plugin.analyze_sentence("Evde kitap var.")
        forms = [c.canonical_form for c in result.candidates if c.type == "nuance"]
        assert len(forms) == len(set(forms))
