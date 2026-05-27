"""Tests for Hindi, Turkish, and Finnish morphology-light plugins.

Covers:
1. Plugin registration and capabilities (honest declarations).
2. Sentence splitting.
3. Tokenisation.
4. Vocabulary extraction (non-empty candidates).
5. Morphological feature hints for known-suffix words.
6. Function word and closed-class detection.
7. Confidence degradation (None for unknown words, float for recognised).
8. Script/direction metadata.
9. Lesson retrieval via get_lesson.
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

    def test_habitual_verb_suffix_hint(self):
        # "जाता" = go (habitual masculine)
        result = self.plugin.analyze_sentence("वह रोज़ जाता है।")
        jaata = next(
            (c for c in result.candidates if c.canonical_form == "जाता"), None
        )
        assert jaata is not None
        assert jaata.lesson_data.get("aspect") == "habitual"
        assert jaata.lesson_data.get("gender") == "masculine"

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

    def test_infinitive_suffix(self):
        # "gitmek" = to go
        result = self.plugin.analyze_sentence("Gitmek istiyorum.")
        gitmek = next(
            (c for c in result.candidates if c.canonical_form == "gitmek"), None
        )
        assert gitmek is not None
        assert gitmek.lesson_data.get("verb_form") == "infinitive"
        assert gitmek.lesson_data.get("pos") == "verb"

    def test_past_definite_tense(self):
        # "gitti" = (he/she) went
        result = self.plugin.analyze_sentence("O gitti.")
        gitti = next(
            (c for c in result.candidates if c.canonical_form == "gitti"), None
        )
        assert gitti is not None
        assert gitti.lesson_data.get("tense") == "past_definite"
        assert gitti.lesson_data.get("pos") == "verb"

    def test_plural_suffix(self):
        # "kitaplar" = books
        result = self.plugin.analyze_sentence("Kitaplar masada.")
        kitaplar = next(
            (c for c in result.candidates if c.canonical_form == "kitaplar"), None
        )
        assert kitaplar is not None
        assert kitaplar.lesson_data.get("number") == "plural"

    def test_locative_case(self):
        # "evde" = at home
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

    def test_confidence_float_for_suffix_hit(self):
        result = self.plugin.analyze_sentence("Gitmek.")
        gitmek = result.candidates[0]
        assert gitmek.confidence is not None
        assert gitmek.confidence == pytest.approx(0.45)

    def test_confidence_none_for_bare_stem(self):
        # "masa" = table (bare nominative, no matching suffix)
        result = self.plugin.analyze_sentence("masa")
        masa = result.candidates[0]
        assert masa.confidence is None

    def test_no_duplicate_candidates(self):
        result = self.plugin.analyze_sentence("ev ev ev")
        forms = [c.canonical_form for c in result.candidates]
        assert len(forms) == len(set(forms))

    def test_analyze_text_returns_per_sentence(self):
        results = self.plugin.analyze_text("Merhaba. Nasılsın?")
        assert len(results) >= 2

    def test_get_lesson_returns_none_for_unknown(self):
        assert self.plugin.get_lesson("xyz") is None

    def test_future_tense(self):
        result = self.plugin.analyze_sentence("Gidecek.")
        gidecek = next(
            (c for c in result.candidates if c.canonical_form == "gidecek"), None
        )
        assert gidecek is not None
        assert gidecek.lesson_data.get("tense") == "future"

    def test_progressive_tense(self):
        result = self.plugin.analyze_sentence("Gidiyor.")
        gidiyor = next(
            (c for c in result.candidates if c.canonical_form == "gidiyor"), None
        )
        assert gidiyor is not None
        assert gidiyor.lesson_data.get("tense") == "progressive"


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
        assert caps.analysis_depth == "morphology_light"
        assert caps.morphology_depth == "shallow"
        assert caps.morphology_quality == "low"
        assert caps.syntax_support is False

    def test_sentence_splitting(self):
        text = "Hei maailma. Kuinka voit?"
        sentences = self.plugin.split_sentences(text)
        assert len(sentences) >= 2

    def test_tokenisation_produces_candidates(self):
        result = self.plugin.analyze_sentence("Minä asun kaupungissa.")
        assert len(result.candidates) > 0

    def test_vowel_harmony_back(self):
        # "talo" = house, back vowels a/o
        result = self.plugin.analyze_sentence("talo")
        cand = result.candidates[0]
        assert cand.lesson_data.get("vowel_harmony") == "back"

    def test_vowel_harmony_front(self):
        # "tyttö" = girl, front vowels ö
        result = self.plugin.analyze_sentence("tyttö")
        cand = result.candidates[0]
        assert cand.lesson_data.get("vowel_harmony") == "front"

    def test_inessive_case(self):
        # "kaupungissa" = in the city (-ssa inessive)
        result = self.plugin.analyze_sentence("Kaupungissa on paljon ihmisiä.")
        kaupungissa = next(
            (c for c in result.candidates if c.canonical_form == "kaupungissa"), None
        )
        assert kaupungissa is not None
        assert kaupungissa.lesson_data.get("case") == "inessive"

    def test_elative_case(self):
        # "kaupungista" = from the city (-sta elative)
        result = self.plugin.analyze_sentence("Tulen kaupungista.")
        kaupungista = next(
            (c for c in result.candidates if c.canonical_form == "kaupungista"), None
        )
        assert kaupungista is not None
        assert kaupungista.lesson_data.get("case") == "elative"

    def test_allative_case(self):
        # "kouluun" would be illative; "koululle" is allative (-lle)
        result = self.plugin.analyze_sentence("Menen koululle.")
        koululle = next(
            (c for c in result.candidates if c.canonical_form == "koululle"), None
        )
        assert koululle is not None
        assert koululle.lesson_data.get("case") == "allative"

    def test_plural_nominative(self):
        # "koirat" = dogs (-t plural nominative)
        result = self.plugin.analyze_sentence("Koirat juoksevat.")
        koirat = next(
            (c for c in result.candidates if c.canonical_form == "koirat"), None
        )
        assert koirat is not None
        assert koirat.lesson_data.get("number") == "plural"
        assert koirat.lesson_data.get("case") == "nominative"

    def test_third_plural_verb(self):
        # "juoksevat" = they run (-vat 3pl present)
        result = self.plugin.analyze_sentence("Koirat juoksevat.")
        juoksevat = next(
            (c for c in result.candidates if c.canonical_form == "juoksevat"), None
        )
        assert juoksevat is not None
        assert juoksevat.lesson_data.get("number") == "plural"
        assert juoksevat.lesson_data.get("person") == "third"

    def test_passive_voice(self):
        # "luetaan" = is read (passive present -taan)
        result = self.plugin.analyze_sentence("Kirja luetaan.")
        luetaan = next(
            (c for c in result.candidates if c.canonical_form == "luetaan"), None
        )
        assert luetaan is not None
        assert luetaan.lesson_data.get("voice") == "passive"

    def test_function_word_ei(self):
        result = self.plugin.analyze_sentence("Minä ei tule.")
        ei = next(
            (c for c in result.candidates if c.canonical_form == "ei"), None
        )
        assert ei is not None
        assert ei.lesson_data.get("pos") == "function_word"
        assert ei.confidence == 0.80

    def test_confidence_float_for_suffix_hit(self):
        result = self.plugin.analyze_sentence("kaupungissa")
        cand = result.candidates[0]
        assert cand.confidence == pytest.approx(0.45)

    def test_confidence_none_for_bare_stem(self):
        # "auto" = car, no matching suffix
        result = self.plugin.analyze_sentence("auto")
        auto = next(
            (c for c in result.candidates if c.canonical_form == "auto"), None
        )
        assert auto is not None
        assert auto.confidence is None

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
        # ä and ö must be included in token capture
        result = self.plugin.analyze_sentence("tyttö laulaa kauniisti.")
        tytto = next(
            (c for c in result.candidates if c.canonical_form == "tyttö"), None
        )
        assert tytto is not None
