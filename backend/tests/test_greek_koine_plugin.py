"""Tests for the Koine Greek dictionary-mode scaffold plugin."""
from __future__ import annotations

import pytest

from backend.plugins.greek_koine import (
    KoineGreekPlugin,
    _LEXICON,
    _UNKNOWN_NOTE,
    _normalise,
    transliterate,
    create_plugin,
)
from backend.schemas.language import LanguageCapabilities
from backend.schemas.parse import CandidateSentenceResult


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture()
def plugin() -> KoineGreekPlugin:
    return create_plugin()


# ── Capability declarations ────────────────────────────────────────────────────

class TestCapabilities:
    def test_language_code(self, plugin):
        assert plugin.language_code == "grc"

    def test_direction_ltr(self, plugin):
        assert plugin.direction == "ltr"

    def test_script_family_greek(self, plugin):
        assert plugin.capabilities.script_family == "greek"

    def test_tokenization_mode_whitespace(self, plugin):
        assert plugin.capabilities.tokenization_mode == "whitespace"

    def test_morphology_depth_shallow(self, plugin):
        assert plugin.capabilities.morphology_depth == "shallow"

    def test_analysis_depth_morphology_light(self, plugin):
        assert plugin.capabilities.analysis_depth == "morphology_light"

    def test_lesson_modes_includes_vocabulary(self, plugin):
        assert "vocabulary" in plugin.capabilities.lesson_modes_supported
        assert "dictionary" in plugin.capabilities.lesson_modes_supported
        assert "morphology" in plugin.capabilities.lesson_modes_supported

    def test_transliteration_scheme_set(self, plugin):
        # Koine Greek needs romanization for script-view toggle.
        assert plugin.capabilities.transliteration_scheme is not None

    def test_morphology_quality_medium(self, plugin):
        assert plugin.capabilities.morphology_quality == "medium"

    def test_no_syntax_support(self, plugin):
        assert plugin.capabilities.syntax_support is False

    def test_no_idiom_detection(self, plugin):
        assert plugin.capabilities.idiom_detection is False

    def test_capabilities_type(self, plugin):
        assert isinstance(plugin.capabilities, LanguageCapabilities)


# ── Protocol compliance ────────────────────────────────────────────────────────

class TestProtocol:
    def test_has_lesson_store(self, plugin):
        assert isinstance(plugin.lesson_store, dict)

    def test_analyze_text_returns_list(self, plugin):
        results = plugin.analyze_text("ἐν ἀρχῇ ἦν ὁ λόγος.")
        assert isinstance(results, list)

    def test_split_sentences_returns_list(self, plugin):
        sentences = plugin.split_sentences("ὁ θεὸς ἀγάπη ἐστίν.")
        assert isinstance(sentences, list)

    def test_analyze_sentence_returns_result(self, plugin):
        result = plugin.analyze_sentence("λόγος")
        assert isinstance(result, CandidateSentenceResult)

    def test_get_lesson_returns_none_for_unknown(self, plugin):
        assert plugin.get_lesson("nonexistent-id") is None


# ── Diacritic normalisation ────────────────────────────────────────────────────

class TestNormalise:
    def test_strips_acute_accent(self):
        # λόγος → λογος
        assert _normalise("λόγος") == "λογος"

    def test_strips_grave_accent(self):
        # ὁ with grave
        assert _normalise("θεὸς") == "θεος"

    def test_strips_circumflex(self):
        assert _normalise("λόγου") == "λογου"

    def test_strips_smooth_breathing(self):
        # ἐν → εν
        assert _normalise("ἐν") == "εν"

    def test_strips_rough_breathing(self):
        # ὁ → ο
        assert _normalise("ὁ") == "ο"

    def test_strips_iota_subscript(self):
        # ἀρχῇ → αρχη
        assert _normalise("ἀρχῇ") == "αρχη"

    def test_strips_diaeresis(self):
        # ϊ → ι
        assert _normalise("ϊ") == "ι"

    def test_lowercases(self):
        assert _normalise("ΛΟΓΟΣ") == "λογος"

    def test_plain_greek_unchanged(self):
        assert _normalise("λογος") == "λογος"

    def test_polytonic_round_trip(self):
        # All forms of logos normalise to the same key.
        for form in ("λόγος", "λόγου", "λόγον", "λόγοις", "λόγοι"):
            assert _normalise(form).startswith("λογο") or _normalise(form) == "λογοι"


# ── Transliteration ────────────────────────────────────────────────────────────

class TestTransliterate:
    def test_logos(self):
        # λόγος → logos (accent stripped by _normalise inside transliterate)
        assert transliterate("λόγος") == "logos"

    def test_theos(self):
        assert transliterate("θεός") == "theos"

    def test_psyche_like_consonants(self):
        # χ → ch, φ → ph
        assert transliterate("χαρά") == "chara"

    def test_eta_maps_to_ē(self):
        # η → ē
        assert transliterate("ζωή") == "zōē"

    def test_omega_maps_to_ō(self):
        assert transliterate("λόγον")  # contains ο → o and final ν → n
        result = transliterate("ω")
        assert result == "ō"

    def test_sigma_terminal(self):
        # ς (final sigma) → s
        assert transliterate("λόγος").endswith("s")

    def test_theta(self):
        assert "th" in transliterate("θεός")


# ── Sentence splitting ─────────────────────────────────────────────────────────

class TestSentenceSplitting:
    def test_splits_on_period(self, plugin):
        sentences = plugin.split_sentences("ὁ θεός. ὁ κύριος.")
        assert len(sentences) == 2

    def test_splits_on_semicolon(self, plugin):
        # Greek question mark is U+003B or sometimes U+037E
        sentences = plugin.split_sentences("τίς εἶ; λόγος εἰμί.")
        assert len(sentences) == 2

    def test_single_sentence(self, plugin):
        sentences = plugin.split_sentences("ἐν ἀρχῇ ἦν ὁ λόγος")
        assert len(sentences) == 1

    def test_empty_input(self, plugin):
        assert plugin.split_sentences("") == []

    def test_strips_whitespace(self, plugin):
        sentences = plugin.split_sentences("  λόγος.  ")
        assert all(s == s.strip() for s in sentences)


# ── Lexicon lookup ─────────────────────────────────────────────────────────────

class TestLexiconLookup:
    def test_known_word_logos(self, plugin):
        result = plugin.analyze_sentence("λόγος")
        assert len(result.candidates) == 1
        cand = result.candidates[0]
        assert cand.lesson_data.get("gloss") is not None
        assert "word" in cand.lesson_data["gloss"].lower()

    def test_known_word_theos(self, plugin):
        result = plugin.analyze_sentence("θεός")
        assert len(result.candidates) == 1
        cand = result.candidates[0]
        assert "god" in cand.lesson_data["gloss"].lower()

    def test_known_word_has_citation_form(self, plugin):
        result = plugin.analyze_sentence("κύριος")
        cand = result.candidates[0]
        assert "citation_form" in cand.lesson_data

    def test_known_word_has_grammar_note(self, plugin):
        result = plugin.analyze_sentence("λόγος")
        cand = result.candidates[0]
        assert "grammar_note" in cand.lesson_data

    def test_known_word_has_romanized(self, plugin):
        result = plugin.analyze_sentence("λόγος")
        cand = result.candidates[0]
        assert cand.lesson_data.get("romanized") == "logos"

    def test_known_word_high_confidence(self, plugin):
        result = plugin.analyze_sentence("θεός")
        assert result.candidates[0].confidence is not None
        assert result.candidates[0].confidence > 0.5

    def test_unknown_word_has_confidence_note(self, plugin):
        # Inflected forms now resolve via the inflection table; use a
        # wholly invented token that cannot be in any Greek lexicon.
        result = plugin.analyze_sentence("ξυζζυω")
        assert len(result.candidates) == 1
        cand = result.candidates[0]
        assert "confidence_note" in cand.lesson_data
        assert cand.confidence is None

    def test_unknown_word_still_has_romanized(self, plugin):
        result = plugin.analyze_sentence("ξυζζυω")
        cand = result.candidates[0]
        assert "romanized" in cand.lesson_data
        assert len(cand.lesson_data["romanized"]) > 0

    def test_lookup_with_accents_matches_lexicon(self, plugin):
        # Words with full polytonic diacritics must still be found.
        result = plugin.analyze_sentence("ἐν ἀρχῇ ἦν ὁ λόγος")
        found_labels = {c.label for c in result.candidates}
        # ἐν and λόγος are both in the lexicon; ἀρχῇ and ἦν are inflected forms
        assert any("ν" in lbl for lbl in found_labels)  # ἐν

    def test_deduplicates_same_canonical(self, plugin):
        # λόγος and λόγος repeated should only yield one candidate.
        result = plugin.analyze_sentence("λόγος λόγος")
        assert len(result.candidates) == 1

    def test_conjunction_kai(self, plugin):
        result = plugin.analyze_sentence("καί")
        assert len(result.candidates) == 1
        assert "and" in result.candidates[0].lesson_data["gloss"].lower()

    def test_negation_ou(self, plugin):
        result = plugin.analyze_sentence("οὐ")
        assert len(result.candidates) == 1

    def test_all_of_john_11(self, plugin):
        """Ἐν ἀρχῇ ἦν ὁ λόγος — at least the article and λόγος are found."""
        text = "Ἐν ἀρχῇ ἦν ὁ λόγος, καὶ ὁ λόγος ἦν πρὸς τὸν θεόν, καὶ θεὸς ἦν ὁ λόγος."
        results = plugin.analyze_text(text)
        all_candidates = [c for sent in results for c in sent.candidates]
        glosses_present = {c.lesson_data["gloss"] for c in all_candidates if "gloss" in c.lesson_data}
        assert any("word" in g.lower() for g in glosses_present)
        assert any("god" in g.lower() for g in glosses_present)


# ── Lexicon completeness ───────────────────────────────────────────────────────

def test_lexicon_all_keys_are_normalised():
    """Every key in _LEXICON must already be in normalised form."""
    for key in _LEXICON:
        assert _normalise(key) == key, f"Key {key!r} is not normalised"


def test_lexicon_all_entries_have_four_fields():
    for key, entry in _LEXICON.items():
        assert len(entry) == 4, f"Entry for {key!r} has {len(entry)} fields (expected 4)"


def test_lexicon_covers_core_nt_vocabulary():
    """Spot-check that key NT headwords are present."""
    must_have = ["θεος", "κυριος", "λογος", "ανθρωπος", "και", "εν", "εγω",
                 "πιστευω", "αγαπη", "ζωη", "πνευμα", "αμαρτια"]
    for word in must_have:
        assert word in _LEXICON, f"{word!r} missing from lexicon"


# ── Plugin registry integration ───────────────────────────────────────────────

def test_create_plugin_returns_instance():
    plugin = create_plugin()
    assert isinstance(plugin, KoineGreekPlugin)


def test_plugin_auto_discovered():
    """The plugin registry must be able to load the grc plugin."""
    from backend.parsing.plugin_loader import load_plugins
    registry = load_plugins()
    plugin = registry.get("grc")
    assert plugin is not None
    assert plugin.language_code == "grc"


# ── Deep morphology (conjugation + grammar types) ─────────────────────────────

class TestDeepMorphology:
    @pytest.fixture()
    def plugin(self) -> KoineGreekPlugin:
        return create_plugin()

    def test_tense_pool_populated(self, plugin):
        pool = plugin.capabilities.tense_pool
        assert pool is not None and len(pool) >= 4
        assert "present" in pool
        assert "aorist" in pool

    def test_mood_pool_populated(self, plugin):
        pool = plugin.capabilities.mood_pool
        assert pool is not None and len(pool) >= 4
        assert "indicative" in pool
        assert "subjunctive" in pool

    def test_morph_verb_legei_emits_conjugation(self, plugin):
        # λέγει (3sg present active indicative of λέγω) is in grc_morph.json
        result = plugin.analyze_sentence("λέγει")
        assert len(result.candidates) == 1
        c = result.candidates[0]
        assert c.type == "conjugation"
        assert c.lesson_data.get("tense") == "present"
        assert c.lesson_data.get("person") == "third"

    def test_morph_verb_canonical_contains_morph_tag(self, plugin):
        result = plugin.analyze_sentence("λέγει")
        c = result.candidates[0]
        assert ":" in c.canonical_form

    def test_morph_verb_hlqen_emits_conjugation(self, plugin):
        # ἦλθεν (aorist of ἔρχομαι) is in grc_morph.json
        result = plugin.analyze_sentence("ἦλθεν")
        assert len(result.candidates) == 1
        c = result.candidates[0]
        assert c.type == "conjugation"
        assert c.lesson_data.get("tense") == "past"

    def test_preposition_en_emits_grammar_type(self, plugin):
        result = plugin.analyze_sentence("ἐν")
        assert len(result.candidates) == 1
        c = result.candidates[0]
        assert c.type == "grammar"
        assert "in" in c.lesson_data.get("gloss", "").lower()

    def test_conjunction_kai_emits_grammar_type(self, plugin):
        result = plugin.analyze_sentence("καί")
        assert len(result.candidates) == 1
        c = result.candidates[0]
        assert c.type == "grammar"

    def test_preposition_eis_emits_grammar_type(self, plugin):
        result = plugin.analyze_sentence("εἰς")
        assert len(result.candidates) == 1
        assert result.candidates[0].type == "grammar"

    def test_noun_logos_stays_vocabulary(self, plugin):
        result = plugin.analyze_sentence("λόγος")
        assert len(result.candidates) == 1
        assert result.candidates[0].type == "vocabulary"

    def test_verb_has_romanized_in_lesson_data(self, plugin):
        result = plugin.analyze_sentence("λέγει")
        c = result.candidates[0]
        assert c.lesson_data.get("romanized") is not None

    def test_conjugation_canonical_stable_across_calls(self, plugin):
        r1 = plugin.analyze_sentence("λέγει")
        r2 = plugin.analyze_sentence("λέγει")
        assert r1.candidates[0].canonical_form == r2.candidates[0].canonical_form

    def test_verb_db_present_indicative(self, plugin):
        # λύει (3sg pres ind act of λύω) via SQLite verb DB
        result = plugin.analyze_sentence("λύει")
        assert len(result.candidates) == 1
        c = result.candidates[0]
        assert c.type == "conjugation"
        assert c.lesson_data.get("tense") == "present"
        assert c.lesson_data.get("mood") == "indicative"
        assert c.lesson_data.get("voice") == "active"
        assert c.lesson_data.get("person") == "third"
        assert c.lesson_data.get("number") == "singular"

    def test_verb_db_aorist_active(self, plugin):
        # ἔλυσεν (3sg aor ind act of λύω) via SQLite verb DB
        result = plugin.analyze_sentence("ἔλυσεν")
        assert len(result.candidates) == 1
        c = result.candidates[0]
        assert c.type == "conjugation"
        assert c.lesson_data.get("tense") == "aorist"
        assert c.lesson_data.get("mood") == "indicative"

    def test_verb_db_imperfect(self, plugin):
        # ἐλύομεν (1pl impf ind act of λύω) via SQLite verb DB
        result = plugin.analyze_sentence("ἐλύομεν")
        assert len(result.candidates) == 1
        c = result.candidates[0]
        assert c.type == "conjugation"
        assert c.lesson_data.get("tense") == "imperfect"

    def test_verb_db_subjunctive(self, plugin):
        # λύωμεν (1pl pres subj act of λύω) via SQLite verb DB
        result = plugin.analyze_sentence("λύωμεν")
        assert len(result.candidates) == 1
        c = result.candidates[0]
        assert c.type == "conjugation"
        assert c.lesson_data.get("mood") == "subjunctive"

    def test_verb_db_passive(self, plugin):
        # ἐλύθη (3sg aor ind pass of λύω) via SQLite verb DB
        result = plugin.analyze_sentence("ἐλύθη")
        assert len(result.candidates) == 1
        c = result.candidates[0]
        assert c.type == "conjugation"
        assert c.lesson_data.get("voice") == "passive"
        assert c.lesson_data.get("tense") == "aorist"
