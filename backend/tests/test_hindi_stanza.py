"""Tests for Hindi stanza morphological analysis path.

Coverage
────────
- Lemma-based canonical forms: verb:{lemma}, noun:{lemma}, adj:{lemma}
- Conjugation objects: conj:{lemma}:{aspect}:{gender}:{number}
- Habitual aspect (Aspect=Imp → habitual)
- Perfective aspect (Aspect=Perf)
- Future tense (Tense=Fut)
- Present finite (Tense=Pres + VerbForm=Fin on AUX)
- Infinitive verbal noun (noun ending -ना → conj:{lemma}:infinitive)
- Gender and number from stanza features
- Postposition tagged as grammar (ADP → grammar/postposition)
- Function word AUX → vocabulary/function_word
- Latin loanword → surface-based canonical (no prefix)
- RelationHint: conjugation_of → verb:{lemma}
- Deduplication
- Vocabulary + conjugation both emitted for same verb surface
- C9 contract: tense + mood keys always present in conjugation lesson_data
- hi_adapter unit: is_available, analyze_sentence
"""
from __future__ import annotations

import pytest

from backend.morphology import hi_adapter
from backend.plugins.hindi import HindiPlugin, create_plugin


# ── skip guard ────────────────────────────────────────────────────────────────

stanza_required = pytest.mark.skipif(
    not hi_adapter.is_available(),
    reason="stanza not installed; run: poetry install --extras hindi",
)


@pytest.fixture(scope="module")
def plugin() -> HindiPlugin:
    return create_plugin()


# ── Unit: hi_adapter ──────────────────────────────────────────────────────────

@stanza_required
class TestHiAdapter:
    def test_is_available(self):
        assert hi_adapter.is_available() is True

    def test_analyze_sentence_returns_tokens(self):
        tokens = hi_adapter.analyze_sentence("वह जाता है।")
        assert len(tokens) >= 2

    def test_verb_lemma(self):
        tokens = hi_adapter.analyze_sentence("वह जाता है।")
        verb = next((t for t in tokens if t.upos == "VERB"), None)
        assert verb is not None
        assert verb.lemma == "जाना"

    def test_verb_aspect_habitual(self):
        tokens = hi_adapter.analyze_sentence("वह जाता है।")
        verb = next((t for t in tokens if t.upos == "VERB"), None)
        assert verb is not None
        assert verb.aspect == "habitual"

    def test_verb_gender_masculine(self):
        tokens = hi_adapter.analyze_sentence("वह जाता है।")
        verb = next((t for t in tokens if t.upos == "VERB"), None)
        assert verb is not None
        assert verb.gender == "masculine"

    def test_future_tense(self):
        tokens = hi_adapter.analyze_sentence("वह जाएगा।")
        verb = next((t for t in tokens if t.upos == "VERB"), None)
        assert verb is not None
        assert verb.tense == "future"

    def test_perfective_aspect(self):
        tokens = hi_adapter.analyze_sentence("राम ने खाया।")
        verb = next((t for t in tokens if t.upos == "VERB"), None)
        assert verb is not None
        assert verb.aspect == "perfective"

    def test_noun_lemma(self):
        tokens = hi_adapter.analyze_sentence("घर बड़ा है।")
        noun = next((t for t in tokens if t.upos == "NOUN" and t.text == "घर"), None)
        assert noun is not None
        assert noun.lemma == "घर"

    def test_adp_postposition(self):
        tokens = hi_adapter.analyze_sentence("राम ने सेब खाया।")
        adp = next((t for t in tokens if t.upos == "ADP"), None)
        assert adp is not None

    def test_aux_lemma(self):
        tokens = hi_adapter.analyze_sentence("वह जाता है।")
        aux = next((t for t in tokens if t.upos == "AUX"), None)
        assert aux is not None
        assert aux.lemma == "है"

    def test_source_stanza(self):
        tokens = hi_adapter.analyze_sentence("किताब")
        assert all(t.source == "stanza" for t in tokens)


# ── Integration: plugin with stanza ──────────────────────────────────────────

@stanza_required
class TestHindiPluginStanza:
    def test_verb_vocabulary_canonical(self, plugin):
        result = plugin.analyze_sentence("वह जाता है।")
        vocab = next(
            (c for c in result.candidates if c.canonical_form == "verb:जाना"), None
        )
        assert vocab is not None
        assert vocab.type == "vocabulary"

    def test_verb_conjugation_emitted(self, plugin):
        result = plugin.analyze_sentence("वह जाता है।")
        conj = next(
            (c for c in result.candidates
             if c.type == "conjugation" and "जाना" in c.canonical_form), None
        )
        assert conj is not None

    def test_habitual_aspect_in_lesson_data(self, plugin):
        result = plugin.analyze_sentence("वह जाता है।")
        conj = next(
            (c for c in result.candidates
             if c.type == "conjugation" and "जाना" in c.canonical_form), None
        )
        assert conj is not None
        assert conj.lesson_data.get("aspect") == "habitual"

    def test_gender_in_lesson_data(self, plugin):
        result = plugin.analyze_sentence("वह जाता है।")
        conj = next(
            (c for c in result.candidates
             if c.type == "conjugation" and "जाना" in c.canonical_form), None
        )
        assert conj is not None
        assert conj.lesson_data.get("gender") == "masculine"

    def test_future_tense_canonical(self, plugin):
        result = plugin.analyze_sentence("वह जाएगा।")
        conj = next(
            (c for c in result.candidates
             if c.type == "conjugation" and "future" in c.canonical_form), None
        )
        assert conj is not None
        assert conj.lesson_data.get("tense") == "future"

    def test_perfective_aspect_canonical(self, plugin):
        result = plugin.analyze_sentence("राम ने सेब खाया।")
        conj = next(
            (c for c in result.candidates
             if c.type == "conjugation" and "perfective" in c.canonical_form), None
        )
        assert conj is not None
        assert conj.lesson_data.get("aspect") == "perfective"

    def test_noun_canonical(self, plugin):
        result = plugin.analyze_sentence("घर बड़ा है।")
        noun = next(
            (c for c in result.candidates if c.canonical_form == "noun:घर"), None
        )
        assert noun is not None
        assert noun.type == "vocabulary"

    def test_adj_canonical(self, plugin):
        result = plugin.analyze_sentence("घर बड़ा है।")
        adj = next(
            (c for c in result.candidates if c.canonical_form.startswith("adj:")), None
        )
        assert adj is not None

    def test_postposition_tagged_grammar(self, plugin):
        result = plugin.analyze_sentence("राम ने सेब खाया।")
        ne = next(
            (c for c in result.candidates
             if c.surface_form == "ने" and c.type == "grammar"), None
        )
        assert ne is not None
        assert ne.lesson_data.get("pos") == "postposition"

    def test_aux_tagged_function_word(self, plugin):
        result = plugin.analyze_sentence("वह जाता है।")
        hai = next(
            (c for c in result.candidates
             if c.surface_form == "है" and c.lesson_data.get("pos") == "function_word"), None
        )
        assert hai is not None

    def test_infinitive_conjugation(self, plugin):
        result = plugin.analyze_sentence("खाना अच्छा है।")
        conj = next(
            (c for c in result.candidates
             if c.surface_form == "खाना" and c.type == "conjugation"), None
        )
        assert conj is not None
        assert conj.lesson_data.get("verb_form") == "infinitive"

    def test_relation_hint_present(self, plugin):
        result = plugin.analyze_sentence("वह जाता है।")
        conj = next(
            (c for c in result.candidates if c.type == "conjugation"), None
        )
        assert conj is not None
        assert any(h.relation_type == "conjugation_of" for h in conj.relation_hints)
        hint = conj.relation_hints[0]
        assert hint.target_canonical_form.startswith("verb:")

    def test_deduplication(self, plugin):
        result = plugin.analyze_sentence("जाता जाता।")
        forms = [c.canonical_form for c in result.candidates]
        assert len(forms) == len(set(forms))

    def test_both_vocab_and_conj_emitted(self, plugin):
        result = plugin.analyze_sentence("वह जाता है।")
        types = {c.type for c in result.candidates}
        assert "vocabulary" in types
        assert "conjugation" in types

    def test_latin_loanword_canonical(self, plugin):
        result = plugin.analyze_sentence("मुझे computer चाहिए।")
        computer = next(
            (c for c in result.candidates if c.canonical_form == "computer"), None
        )
        assert computer is not None

    def test_romanized_present_in_lesson_data(self, plugin):
        result = plugin.analyze_sentence("किताब")
        assert result.candidates
        for c in result.candidates:
            assert "romanized" in c.lesson_data

    def test_c9_tense_and_mood_keys_in_conjugation(self, plugin):
        # C9 contract: both tense and mood keys must be present (may be None)
        result = plugin.analyze_sentence("वह जाता है।")
        for c in result.candidates:
            if c.type == "conjugation":
                assert "tense" in c.lesson_data, f"tense missing in {c.canonical_form}"
                assert "mood" in c.lesson_data,  f"mood missing in {c.canonical_form}"
