"""Tests for Hindi, Turkish, and Finnish morphology-light plugins.

Covers:
1. Plugin registration and capabilities (honest declarations).
2. Sentence splitting.
3. Tokenisation.
4. Vocabulary extraction (non-empty candidates).
5. Morphological feature hints for known-suffix words.
6. Conjugation type emitted for detected verb forms.
7. Function word and postposition detection.
8. Multi-word postposition detection (Hindi bigram/trigram scan).
9. Confidence degradation (None for unknown words, float for recognised).
10. Script/direction metadata.
11. tense_pool / mood_pool populated in capabilities.
12. Turkish evidential past (-mış/-miş).
13. Turkish I/İ normalisation.
14. Finnish 15-case detection.
15. Finnish passive voice.
16. No duplicate canonical forms per sentence.
17. Lesson retrieval via get_lesson.
18. Round-trip: analyze → stored canonical forms are unique.
"""
from __future__ import annotations

import pytest

from backend.plugins.hindi   import HindiPlugin,   create_plugin as create_hindi
from backend.plugins.turkish import TurkishPlugin,  create_plugin as create_turkish
from backend.plugins.finnish import FinnishPlugin,  create_plugin as create_finnish


# ─────────────────────────────────────────────────────────────────────────────
# Hindi
# ─────────────────────────────────────────────────────────────────────────────

class TestHindiPlugin:

    def setup_method(self):
        self.plugin = create_hindi()

    def test_create_plugin_returns_hindi_plugin(self):
        assert isinstance(self.plugin, HindiPlugin)

    def test_language_code(self):
        assert self.plugin.language_code == "hi"

    def test_direction_ltr(self):
        assert self.plugin.direction == "ltr"

    def test_capabilities_honest(self):
        caps = self.plugin.capabilities
        assert caps.script_family == "devanagari"
        assert caps.analysis_depth == "morphology_light"
        assert caps.morphology_depth == "shallow"
        assert caps.morphology_quality == "low"
        assert caps.syntax_support is False

    def test_tense_pool_populated(self):
        caps = self.plugin.capabilities
        assert caps.tense_pool is not None
        assert len(caps.tense_pool) >= 2

    def test_mood_pool_populated(self):
        caps = self.plugin.capabilities
        assert caps.mood_pool is not None
        assert len(caps.mood_pool) >= 1

    def test_sentence_splitting_danda(self):
        text = "यह किताब है। वह बहुत अच्छा है।"
        sentences = self.plugin.split_sentences(text)
        assert len(sentences) >= 2

    def test_sentence_splitting_newline(self):
        text = "पहला वाक्य\nदूसरा वाक्य"
        sentences = self.plugin.split_sentences(text)
        assert len(sentences) >= 2

    def test_tokenisation_produces_candidates(self):
        result = self.plugin.analyze_sentence("मैं घर जाता हूँ।")
        assert len(result.candidates) > 0

    def test_candidates_have_romanized(self):
        result = self.plugin.analyze_sentence("किताब")
        cand = result.candidates[0]
        assert "romanized" in cand.lesson_data
        assert isinstance(cand.lesson_data["romanized"], str)
        assert len(cand.lesson_data["romanized"]) > 0

    def test_postposition_tagged(self):
        result = self.plugin.analyze_sentence("राम ने सेब खाया।")
        # "ने" is a postposition (ergative case marker)
        ne = next(
            (c for c in result.candidates if c.canonical_form == "ने"), None
        )
        assert ne is not None
        assert ne.lesson_data.get("pos") == "postposition"
        assert ne.type == "grammar"

    def test_function_word_tagged(self):
        result = self.plugin.analyze_sentence("यह किताब है।")
        hai = next(
            (c for c in result.candidates if c.canonical_form == "है"), None
        )
        assert hai is not None
        assert hai.lesson_data.get("pos") == "function_word"

    def test_habitual_verb_emits_conjugation_type(self):
        # "जाता" = go (habitual masculine) — should emit conjugation, not vocabulary
        result = self.plugin.analyze_sentence("वह रोज़ जाता है।")
        jaata = next(
            (c for c in result.candidates if c.surface_form == "जाता"), None
        )
        assert jaata is not None
        assert jaata.type == "conjugation", f"Expected conjugation, got {jaata.type}"
        assert jaata.lesson_data.get("aspect") == "habitual"
        assert jaata.lesson_data.get("gender") == "masculine"

    def test_future_verb_emits_conjugation_type(self):
        # "जाएगा" = will go (masc sg)
        result = self.plugin.analyze_sentence("वह कल जाएगा।")
        jaayega = next(
            (c for c in result.candidates if c.surface_form == "जाएगा"), None
        )
        assert jaayega is not None
        assert jaayega.type == "conjugation"
        assert jaayega.lesson_data.get("tense") == "future"
        assert jaayega.lesson_data.get("gender") == "masculine"

    def test_infinitive_emits_conjugation_type(self):
        result = self.plugin.analyze_sentence("खाना अच्छा है।")
        khaana = next(
            (c for c in result.candidates if c.surface_form == "खाना"), None
        )
        assert khaana is not None
        assert khaana.type == "conjugation"
        assert khaana.lesson_data.get("verb_form") == "infinitive"

    def test_multi_word_postposition_ke_liye(self):
        # "के लिए" = for (purpose)
        result = self.plugin.analyze_sentence("यह राम के लिए है।")
        grammar_items = [c for c in result.candidates if c.type == "grammar"]
        assert len(grammar_items) >= 1

    def test_multi_word_postposition_ke_baad(self):
        # "के बाद" = after; tests bigram postposition detection
        result = self.plugin.analyze_sentence("खाने के बाद वह सोया।")
        # At minimum, "के" should be tagged as postposition or a grammar MWP candidate emitted
        postpositions = [
            c for c in result.candidates
            if c.type == "grammar" or c.lesson_data.get("pos") == "postposition"
        ]
        assert len(postpositions) >= 1

    def test_confidence_none_for_unknown_words(self):
        result = self.plugin.analyze_sentence("अज्ञात")
        assert result.candidates[0].confidence is None

    def test_confidence_float_for_postposition(self):
        result = self.plugin.analyze_sentence("को")
        ko = result.candidates[0]
        assert ko.confidence is not None
        assert 0.0 < ko.confidence <= 1.0

    def test_analyze_text_returns_per_sentence(self):
        results = self.plugin.analyze_text("पहला। दूसरा।")
        assert len(results) >= 2
        for r in results:
            assert r.text
            assert isinstance(r.candidates, list)

    def test_get_lesson_returns_none_for_unknown(self):
        assert self.plugin.get_lesson("nonexistent") is None

    def test_latin_loanword_captured(self):
        result = self.plugin.analyze_sentence("मुझे computer चाहिए।")
        computer = next(
            (c for c in result.candidates if c.canonical_form == "computer"), None
        )
        assert computer is not None

    def test_no_duplicate_candidates(self):
        result = self.plugin.analyze_sentence("किताब किताब किताब।")
        forms = [c.canonical_form for c in result.candidates]
        assert len(forms) == len(set(forms))

    def test_conjugation_canonical_form_is_stable(self):
        # The same surface form should yield the same canonical form deterministically
        r1 = self.plugin.analyze_sentence("वह जाता है।")
        r2 = self.plugin.analyze_sentence("वह जाता है।")
        forms1 = {c.canonical_form for c in r1.candidates}
        forms2 = {c.canonical_form for c in r2.candidates}
        assert forms1 == forms2


# ─────────────────────────────────────────────────────────────────────────────
# Turkish
# ─────────────────────────────────────────────────────────────────────────────

class TestTurkishPlugin:

    def setup_method(self):
        self.plugin = create_turkish()

    def test_create_plugin_returns_turkish_plugin(self):
        assert isinstance(self.plugin, TurkishPlugin)

    def test_language_code(self):
        assert self.plugin.language_code == "tr"

    def test_direction_ltr(self):
        assert self.plugin.direction == "ltr"

    def test_capabilities_honest(self):
        caps = self.plugin.capabilities
        assert caps.script_family == "latin"
        assert caps.analysis_depth == "morphology_light"
        assert caps.morphology_depth == "shallow"
        assert caps.morphology_quality == "low"
        assert caps.syntax_support is False

    def test_tense_pool_populated(self):
        caps = self.plugin.capabilities
        assert caps.tense_pool is not None
        assert "progressive" in caps.tense_pool
        assert "past_definite" in caps.tense_pool
        assert "past_evidential" in caps.tense_pool

    def test_mood_pool_populated(self):
        caps = self.plugin.capabilities
        assert caps.mood_pool is not None
        assert "conditional" in caps.mood_pool

    def test_sentence_splitting(self):
        text = "Merhaba dünya. Nasılsın?"
        sentences = self.plugin.split_sentences(text)
        assert len(sentences) >= 2

    def test_tokenisation_produces_candidates(self):
        result = self.plugin.analyze_sentence("Kitabı okudum.")
        assert len(result.candidates) > 0

    def test_vowel_harmony_back(self):
        result = self.plugin.analyze_sentence("adam")
        cand = result.candidates[0]
        assert cand.lesson_data.get("vowel_harmony") == "back"

    def test_vowel_harmony_front(self):
        result = self.plugin.analyze_sentence("ev")
        cand = result.candidates[0]
        assert cand.lesson_data.get("vowel_harmony") == "front"

    def test_infinitive_suffix_emits_conjugation(self):
        # "gitmek" = to go — verb infinitive → conjugation type
        result = self.plugin.analyze_sentence("Gitmek istiyorum.")
        gitmek = next(
            (c for c in result.candidates if c.surface_form.lower() == "gitmek"), None
        )
        assert gitmek is not None
        assert gitmek.type == "conjugation"
        assert gitmek.lesson_data.get("verb_form") == "infinitive"
        assert gitmek.lesson_data.get("pos") == "verb"

    def test_past_definite_tense_emits_conjugation(self):
        # "gitti" = (he/she) went → conjugation type
        result = self.plugin.analyze_sentence("O gitti.")
        gitti = next(
            (c for c in result.candidates if c.surface_form.lower() == "gitti"), None
        )
        assert gitti is not None
        assert gitti.type == "conjugation"
        assert gitti.lesson_data.get("tense") == "past_definite"
        assert gitti.lesson_data.get("pos") == "verb"

    def test_evidential_past_emits_conjugation(self):
        # "gitmiş" = apparently (he/she) went (reported/hearsay)
        result = self.plugin.analyze_sentence("O gitmiş.")
        gitmiş = next(
            (c for c in result.candidates if "gitmiş" in c.surface_form.lower()), None
        )
        assert gitmiş is not None
        assert gitmiş.type == "conjugation"
        assert gitmiş.lesson_data.get("tense") == "past_evidential"

    def test_progressive_tense_emits_conjugation(self):
        result = self.plugin.analyze_sentence("Gidiyor.")
        gidiyor = next(
            (c for c in result.candidates if c.surface_form.lower() == "gidiyor"), None
        )
        assert gidiyor is not None
        assert gidiyor.type == "conjugation"
        assert gidiyor.lesson_data.get("tense") == "progressive"

    def test_future_tense_emits_conjugation(self):
        result = self.plugin.analyze_sentence("Gidecek.")
        gidecek = next(
            (c for c in result.candidates if c.surface_form.lower() == "gidecek"), None
        )
        assert gidecek is not None
        assert gidecek.type == "conjugation"
        assert gidecek.lesson_data.get("tense") == "future"

    def test_plural_suffix_vocabulary(self):
        # "kitaplar" = books (plural noun → vocabulary with number=plural)
        result = self.plugin.analyze_sentence("Kitaplar masada.")
        kitaplar = next(
            (c for c in result.candidates if c.canonical_form == "kitaplar"), None
        )
        assert kitaplar is not None
        assert kitaplar.lesson_data.get("number") == "plural"

    def test_locative_case_vocabulary(self):
        result = self.plugin.analyze_sentence("Evde oturuyorum.")
        evde = next(
            (c for c in result.candidates if c.canonical_form == "evde"), None
        )
        assert evde is not None
        assert evde.lesson_data.get("case") == "locative"

    def test_function_word_bir(self):
        result = self.plugin.analyze_sentence("Bir elma var.")
        bir = next(
            (c for c in result.candidates if c.canonical_form == "bir"), None
        )
        assert bir is not None
        assert bir.lesson_data.get("pos") == "function_word"
        assert bir.confidence == 0.80

    def test_confidence_float_for_verb_suffix(self):
        result = self.plugin.analyze_sentence("Gitmek.")
        gitmek = result.candidates[0]
        assert gitmek.confidence is not None
        assert gitmek.confidence == pytest.approx(0.45)

    def test_confidence_none_for_bare_stem(self):
        result = self.plugin.analyze_sentence("masa")
        masa = result.candidates[0]
        assert masa.confidence is None

    def test_turkish_dotted_i_normalisation(self):
        # Turkish İ (dotted capital I) should normalise to 'i', not 'ı'
        result = self.plugin.analyze_sentence("İstanbul güzel.")
        istanbul = next(
            (c for c in result.candidates if "stanbul" in c.canonical_form), None
        )
        assert istanbul is not None
        # canonical starts with lowercase 'i' (not 'ı')
        assert istanbul.canonical_form.startswith("i")

    def test_no_duplicate_candidates(self):
        result = self.plugin.analyze_sentence("ev ev ev")
        forms = [c.canonical_form for c in result.candidates]
        assert len(forms) == len(set(forms))

    def test_analyze_text_returns_per_sentence(self):
        results = self.plugin.analyze_text("Merhaba. Nasılsın?")
        assert len(results) >= 2

    def test_get_lesson_returns_none_for_unknown(self):
        assert self.plugin.get_lesson("xyz") is None

    def test_conjugation_canonical_form_is_stable(self):
        r1 = self.plugin.analyze_sentence("Gitti.")
        r2 = self.plugin.analyze_sentence("Gitti.")
        forms1 = {c.canonical_form for c in r1.candidates}
        forms2 = {c.canonical_form for c in r2.candidates}
        assert forms1 == forms2


# ─────────────────────────────────────────────────────────────────────────────
# Finnish
# ─────────────────────────────────────────────────────────────────────────────

class TestFinnishPlugin:

    def setup_method(self):
        self.plugin = create_finnish()

    def test_create_plugin_returns_finnish_plugin(self):
        assert isinstance(self.plugin, FinnishPlugin)

    def test_language_code(self):
        assert self.plugin.language_code == "fi"

    def test_direction_ltr(self):
        assert self.plugin.direction == "ltr"

    def test_capabilities_honest(self):
        caps = self.plugin.capabilities
        assert caps.script_family == "latin"
        assert caps.analysis_depth == "full"
        assert caps.morphology_depth == "rich"
        assert caps.morphology_quality == "medium"
        assert caps.syntax_support is True

    def test_tense_pool_populated(self):
        caps = self.plugin.capabilities
        assert caps.tense_pool is not None
        assert "present" in caps.tense_pool
        assert "past" in caps.tense_pool

    def test_mood_pool_populated(self):
        caps = self.plugin.capabilities
        assert caps.mood_pool is not None
        assert "conditional" in caps.mood_pool
        assert "imperative" in caps.mood_pool

    def test_sentence_splitting(self):
        text = "Hei maailma. Kuinka voit?"
        sentences = self.plugin.split_sentences(text)
        assert len(sentences) >= 2

    def test_tokenisation_produces_candidates(self):
        result = self.plugin.analyze_sentence("Minä asun kaupungissa.")
        assert len(result.candidates) > 0

    def test_vowel_harmony_back(self):
        result = self.plugin.analyze_sentence("talo")
        cand = result.candidates[0]
        assert cand.lesson_data.get("vowel_harmony") == "back"

    def test_vowel_harmony_front(self):
        result = self.plugin.analyze_sentence("tyttö")
        cand = result.candidates[0]
        assert cand.lesson_data.get("vowel_harmony") == "front"

    def test_inessive_case(self):
        result = self.plugin.analyze_sentence("Kaupungissa on paljon ihmisiä.")
        kaupungissa = next(
            (c for c in result.candidates if c.canonical_form == "kaupungissa"), None
        )
        assert kaupungissa is not None
        assert kaupungissa.lesson_data.get("case") == "inessive"

    def test_elative_case(self):
        # spaCy lemmatizes "kaupungista" → "kaupunki"; canonical_form = lemma
        result = self.plugin.analyze_sentence("Tulen kaupungista.")
        kaupungista = next(
            (c for c in result.candidates if c.lesson_data.get("case") == "elative"), None
        )
        assert kaupungista is not None
        assert kaupungista.type == "vocabulary"

    def test_allative_case(self):
        # spaCy lemmatizes "koululle" → "koulu"; canonical_form = "koulu"
        result = self.plugin.analyze_sentence("Menen koululle.")
        koululle = next(
            (c for c in result.candidates if c.lesson_data.get("case") == "allative"), None
        )
        assert koululle is not None
        assert koululle.type == "vocabulary"

    def test_plural_nominative(self):
        result = self.plugin.analyze_sentence("Koirat juoksevat.")
        koirat = next(
            (c for c in result.candidates if c.canonical_form == "koirat"), None
        )
        assert koirat is not None
        assert koirat.lesson_data.get("number") == "plural"
        assert koirat.lesson_data.get("case") == "nominative"

    def test_third_plural_verb_emits_conjugation(self):
        # "juoksevat" = they run (-vat 3pl present) → conjugation type
        result = self.plugin.analyze_sentence("Koirat juoksevat.")
        juoksevat = next(
            (c for c in result.candidates if c.canonical_form.startswith("juoksevat")), None
        )
        assert juoksevat is not None
        assert juoksevat.type == "conjugation"
        assert juoksevat.lesson_data.get("number") == "plural"
        assert juoksevat.lesson_data.get("person") == "third"

    def test_passive_voice_emits_conjugation(self):
        # "luetaan" = is read (passive present); spaCy lemma="lukea"
        result = self.plugin.analyze_sentence("Kirja luetaan.")
        luetaan = next(
            (c for c in result.candidates if c.surface_form == "luetaan"), None
        )
        assert luetaan is not None
        assert luetaan.type == "conjugation"
        assert luetaan.lesson_data.get("voice") == "passive"

    def test_conditional_emits_conjugation(self):
        # "menisi" = would go (conditional); spaCy lemma="mennä"
        result = self.plugin.analyze_sentence("Hän menisi kotiin.")
        menisi = next(
            (c for c in result.candidates if c.surface_form == "menisi"), None
        )
        assert menisi is not None
        assert menisi.type == "conjugation"
        assert menisi.lesson_data.get("mood") == "conditional"

    def test_first_plural_present_emits_conjugation(self):
        # "menemme" = we go (-mme 1pl present)
        result = self.plugin.analyze_sentence("Menemme kotiin.")
        menemme = next(
            (c for c in result.candidates if c.canonical_form.startswith("menemme")), None
        )
        assert menemme is not None
        assert menemme.type == "conjugation"
        assert menemme.lesson_data.get("person") == "first"
        assert menemme.lesson_data.get("number") == "plural"

    def test_negation_aux_ei_emits_conjugation(self):
        # "ei" = negation AUX, conjugated (finite). spaCy: AUX, VerbForm=Fin, Polarity=Neg
        result = self.plugin.analyze_sentence("Minä ei tule.")
        ei = next(
            (c for c in result.candidates if c.surface_form == "ei"), None
        )
        assert ei is not None
        assert ei.type == "conjugation"
        assert ei.lesson_data.get("polarity") == "neg"
        assert ei.confidence == 0.80

    def test_confidence_float_for_noun_with_case(self):
        # "kaupungissa" = inessive NOUN; spaCy gives Case=Ine → confidence 0.80
        result = self.plugin.analyze_sentence("kaupungissa")
        cand = result.candidates[0]
        assert cand.confidence == pytest.approx(0.80)

    def test_confidence_for_bare_nominative(self):
        # spaCy assigns Case=Nom|Number=Sing for "auto" → confidence 0.80
        result = self.plugin.analyze_sentence("auto")
        auto = next(
            (c for c in result.candidates if c.canonical_form == "auto"), None
        )
        assert auto is not None
        assert auto.confidence == pytest.approx(0.80)

    def test_no_duplicate_candidates(self):
        result = self.plugin.analyze_sentence("talo talo talo")
        forms = [c.canonical_form for c in result.candidates]
        assert len(forms) == len(set(forms))

    def test_analyze_text_returns_per_sentence(self):
        results = self.plugin.analyze_text("Hei. Voitko auttaa?")
        assert len(results) >= 2

    def test_get_lesson_returns_none_for_unknown(self):
        assert self.plugin.get_lesson("xyz") is None

    def test_umlaut_characters_in_token(self):
        result = self.plugin.analyze_sentence("tyttö laulaa kauniisti.")
        tytto = next(
            (c for c in result.candidates if c.canonical_form == "tyttö"), None
        )
        assert tytto is not None

    def test_conjugation_canonical_form_is_stable(self):
        r1 = self.plugin.analyze_sentence("Koirat juoksevat.")
        r2 = self.plugin.analyze_sentence("Koirat juoksevat.")
        forms1 = {c.canonical_form for c in r1.candidates}
        forms2 = {c.canonical_form for c in r2.candidates}
        assert forms1 == forms2

    def test_past_passive_emits_conjugation(self):
        # "luettiin" = was read (passive past); spaCy lemma="lukea"
        result = self.plugin.analyze_sentence("Kirja luettiin.")
        luettiin = next(
            (c for c in result.candidates if c.surface_form == "luettiin"), None
        )
        assert luettiin is not None
        assert luettiin.type == "conjugation"
        assert luettiin.lesson_data.get("voice") == "passive"
        assert luettiin.lesson_data.get("tense") == "past"
