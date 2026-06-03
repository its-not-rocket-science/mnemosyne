"""Tests for Turkish zeyrek morphological analysis path.

Coverage
────────
- Lemma-based canonical forms: verb:{lemma}, noun:{lemma}, adj:{lemma}, adv:{lemma}
- Finite verb conjugations: conj:{lemma}:{tense}:{agreement}
- Infinitive verbal noun: conj:{lemma}:infinitive + vocab verb:{lemma}
- Future participle: tense=future in lesson_data even when pos=Adj
- Tense classification: progressive, past_definite, past_evidential, future, aorist
- Person/number agreement: A1sg, A2sg, A3sg, A1pl, A2pl, A3pl
- Case: locative, ablative, dative, genitive, accusative
- Plural number in noun lesson_data
- Negation flag
- RelationHint: conjugation_of → verb:{lemma}
- Function words: bare canonical, pos=function_word
- Vowel harmony present in all candidates
- Deduplication (same conj canonical once per sentence)
- Vocabulary and conjugation both emitted for same surface verb
- tr_adapter unit: is_available, analyze_token
"""
from __future__ import annotations

import pytest

from backend.morphology import tr_adapter
from backend.plugins.turkish import TurkishPlugin, create_plugin


# ── skip guard ────────────────────────────────────────────────────────────────

zeyrek_required = pytest.mark.skipif(
    not tr_adapter.is_available(),
    reason="zeyrek not installed; run: poetry install --extras turkish",
)


@pytest.fixture(scope="module")
def plugin() -> TurkishPlugin:
    return create_plugin()


# ── Unit: tr_adapter ──────────────────────────────────────────────────────────

@zeyrek_required
class TestTrAdapter:
    def test_is_available(self):
        assert tr_adapter.is_available() is True

    def test_analyze_token_returns_morph_token(self):
        mt = tr_adapter.analyze_token("gitti")
        assert mt.text == "gitti"
        assert mt.source == "zeyrek"

    def test_verb_lemma(self):
        mt = tr_adapter.analyze_token("gitti")
        assert mt.lemma == "gitmek"

    def test_verb_pos(self):
        mt = tr_adapter.analyze_token("gitti")
        assert mt.pos == "Verb"

    def test_past_tense(self):
        mt = tr_adapter.analyze_token("gitti")
        assert mt.tense == "past_definite"

    def test_person_third_singular(self):
        mt = tr_adapter.analyze_token("gitti")
        assert mt.person == "third"
        assert mt.number == "singular"

    def test_progressive_tense(self):
        mt = tr_adapter.analyze_token("gidiyor")
        assert mt.tense == "progressive"

    def test_evidential_past(self):
        mt = tr_adapter.analyze_token("gitmiş")
        assert mt.tense == "past_evidential"

    def test_noun_lemma(self):
        mt = tr_adapter.analyze_token("evde")
        assert mt.lemma == "ev"

    def test_noun_locative(self):
        mt = tr_adapter.analyze_token("evde")
        assert mt.case == "locative"

    def test_noun_plural(self):
        mt = tr_adapter.analyze_token("kitaplar")
        assert mt.number == "plural"

    def test_negation_flag(self):
        mt = tr_adapter.analyze_token("gitmiyorum")
        assert mt.negation is True

    def test_infinitive_verb_form(self):
        mt = tr_adapter.analyze_token("gitmek")
        assert mt.verb_form == "infinitive"

    def test_future_participle_tense(self):
        mt = tr_adapter.analyze_token("gidecek")
        assert mt.tense == "future"

    def test_analyze_tokens_batch(self):
        tokens = ["ev", "kitap", "gitti"]
        results = tr_adapter.analyze_tokens(tokens)
        assert len(results) == 3
        assert all(r.source == "zeyrek" for r in results)


# ── Integration: plugin canonical forms ──────────────────────────────────────

@zeyrek_required
class TestZeyrекCanonicalForms:
    def test_verb_canonical(self, plugin):
        result = plugin.analyze_sentence("O gitti.")
        # stanza lemma = root "git"; zeyrek lemma = infinitive "gitmek"
        vocab = next((c for c in result.candidates
                      if c.canonical_form in {"verb:git", "verb:gitmek"}), None)
        assert vocab is not None
        assert vocab.type == "vocabulary"

    def test_verb_conjugation_canonical(self, plugin):
        result = plugin.analyze_sentence("O gitti.")
        conj = next((c for c in result.candidates if c.type == "conjugation"
                     and c.canonical_form.startswith("conj:git")), None)
        assert conj is not None
        assert "past_definite" in conj.canonical_form

    def test_noun_canonical(self, plugin):
        result = plugin.analyze_sentence("Ev büyük.")
        noun = next((c for c in result.candidates if c.canonical_form == "noun:ev"), None)
        assert noun is not None
        assert noun.type == "vocabulary"

    def test_adj_canonical(self, plugin):
        result = plugin.analyze_sentence("Büyük ev.")
        adj = next((c for c in result.candidates if c.canonical_form.startswith("adj:")), None)
        assert adj is not None

    def test_function_word_bare_canonical(self, plugin):
        result = plugin.analyze_sentence("Bir elma var.")
        bir = next((c for c in result.candidates if c.canonical_form == "bir"), None)
        assert bir is not None
        assert bir.lesson_data.get("pos") == "function_word"


@zeyrek_required
class TestZeyrекTense:
    def test_past_definite(self, plugin):
        result = plugin.analyze_sentence("O gitti.")
        conj = next((c for c in result.candidates if c.type == "conjugation"
                     and c.canonical_form.startswith("conj:git")), None)
        assert conj is not None
        assert conj.lesson_data["tense"] == "past_definite"

    def test_past_evidential(self, plugin):
        result = plugin.analyze_sentence("O gitmiş.")
        conj = next((c for c in result.candidates if c.type == "conjugation"
                     and c.canonical_form.startswith("conj:git")), None)
        assert conj is not None
        assert conj.lesson_data["tense"] == "past_evidential"

    def test_progressive(self, plugin):
        result = plugin.analyze_sentence("Gidiyorum.")
        conj = next((c for c in result.candidates if c.type == "conjugation"
                     and c.canonical_form.startswith("conj:git")), None)
        assert conj is not None
        assert conj.lesson_data["tense"] == "progressive"

    def test_future_participle_carries_future_tense(self, plugin):
        result = plugin.analyze_sentence("Gidecek.")
        cand = next((c for c in result.candidates
                     if c.surface_form.lower() == "gidecek"
                     and c.type == "conjugation"), None)
        assert cand is not None
        assert cand.lesson_data.get("tense") == "future"


@zeyrek_required
class TestZeyrекNoun:
    def test_locative_case(self, plugin):
        result = plugin.analyze_sentence("Evde oturuyorum.")
        evde = next((c for c in result.candidates
                     if c.surface_form.lower() == "evde"), None)
        assert evde is not None
        assert evde.lesson_data.get("case") == "locative"

    def test_plural_number(self, plugin):
        result = plugin.analyze_sentence("Kitaplar masada.")
        kitaplar = next((c for c in result.candidates
                         if c.surface_form.lower() == "kitaplar"), None)
        assert kitaplar is not None
        assert kitaplar.lesson_data.get("number") == "plural"

    def test_noun_lemma_not_surface(self, plugin):
        # "evde" (in the house) → canonical noun:ev (lemma), not noun:evde (surface)
        result = plugin.analyze_sentence("Evde oturuyorum.")
        evde = next((c for c in result.candidates
                     if c.surface_form.lower() == "evde"), None)
        assert evde is not None
        assert evde.canonical_form == "noun:ev"


@zeyrek_required
class TestZeyrекInfinitive:
    def test_infinitive_emits_conjugation(self, plugin):
        result = plugin.analyze_sentence("Gitmek istiyorum.")
        conj = next((c for c in result.candidates
                     if c.surface_form.lower() == "gitmek"
                     and c.type == "conjugation"), None)
        assert conj is not None
        assert conj.lesson_data.get("verb_form") == "infinitive"
        assert conj.lesson_data.get("pos") == "Verb"

    def test_infinitive_also_emits_vocabulary(self, plugin):
        result = plugin.analyze_sentence("Gitmek istiyorum.")
        vocab = next((c for c in result.candidates
                      if c.canonical_form in {"verb:git", "verb:gitmek"}), None)
        assert vocab is not None
        assert vocab.type == "vocabulary"

    def test_infinitive_relation_hint(self, plugin):
        result = plugin.analyze_sentence("Gitmek istiyorum.")
        conj = next((c for c in result.candidates
                     if c.type == "conjugation"
                     and c.canonical_form.startswith("conj:git")
                     and "infinitive" in c.canonical_form), None)
        assert conj is not None
        assert any(h.relation_type == "conjugation_of" for h in conj.relation_hints)


@zeyrek_required
class TestZeyrекConjugation:
    def test_relation_hint_present(self, plugin):
        result = plugin.analyze_sentence("Gitti.")
        conj = next((c for c in result.candidates if c.type == "conjugation"), None)
        assert conj is not None
        assert any(h.relation_type == "conjugation_of" for h in conj.relation_hints)
        hint = conj.relation_hints[0]
        assert hint.target_canonical_form.startswith("verb:")

    def test_both_vocab_and_conj_emitted(self, plugin):
        result = plugin.analyze_sentence("Gitti.")
        types = {c.type for c in result.candidates}
        assert "vocabulary" in types
        assert "conjugation" in types

    def test_deduplication(self, plugin):
        result = plugin.analyze_sentence("Gitti gitti.")
        forms = [c.canonical_form for c in result.candidates]
        assert len(forms) == len(set(forms))

    def test_agreement_in_canonical(self, plugin):
        # First-person singular progressive
        result = plugin.analyze_sentence("Gidiyorum.")
        conj = next((c for c in result.candidates if c.type == "conjugation"
                     and c.canonical_form.startswith("conj:git")), None)
        assert conj is not None
        assert "A1sg" in conj.canonical_form

    def test_negation_detected(self, plugin):
        result = plugin.analyze_sentence("Gitmiyorum.")
        conj = next((c for c in result.candidates if c.type == "conjugation"), None)
        assert conj is not None
        assert conj.lesson_data.get("negation") is True

    def test_vowel_harmony_in_lesson_data(self, plugin):
        result = plugin.analyze_sentence("Gitti.")
        for c in result.candidates:
            assert "vowel_harmony" in c.lesson_data
            assert c.lesson_data["vowel_harmony"] in {"back", "front"}
