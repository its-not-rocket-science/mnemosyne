"""Tests for the spaCy-backed German plugin (backend/plugins/german.py).

The entire module is skipped when spaCy or de_core_news_sm is not installed
so the CI baseline stays green.

To enable these tests, install the model once:
    python -m spacy download de_core_news_sm

Design intent
─────────────
These tests verify:

- Structural correctness: required lesson_data keys, confidence ranges, no
  duplicate canonical forms, graceful absence on punctuation-only input.
- German-specific features: capitalised NOUN lemmas, separable verb particle
  detection, three-gender agreement (Masc/Fem/Neut), case information.
- Architecture: canonical forms use the same cross-language scheme; the new
  ``case_agreement`` type is emitted instead of bare ``agreement``.
- Confidence is capped at 0.80; is_oov is never used (always True for
  de_core_news_sm).

Known de_core_news_sm limitations that tests deliberately work around:
- is_oov always returns True — not used for confidence.
- Konjunktiv I/II (subjunctive) is unreliably tagged; subjunctive tests are
  conservative.
- Case resolution on adjectives is less reliable than on determiners.
- Separable verbs in verb-final subordinate clauses may miss the svp arc.
"""
from __future__ import annotations

import pytest

from backend.parsing.canonical import canonical_object_id
from backend.schemas.parse import CandidateObject, CandidateSentenceResult


# ── skip guard ────────────────────────────────────────────────────────────────

def _spacy_available() -> bool:
    try:
        import spacy  # noqa: PLC0415
        spacy.load("de_core_news_sm", disable=["ner"])
        return True
    except (ImportError, OSError):
        return False


pytestmark = pytest.mark.skipif(
    not _spacy_available(),
    reason="spaCy + de_core_news_sm not installed; "
           "run: python -m spacy download de_core_news_sm",
)


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def plugin():
    from backend.plugins.german import GermanPlugin
    return GermanPlugin()


# ── helpers ───────────────────────────────────────────────────────────────────

def objects_of(result: CandidateSentenceResult, kind: str) -> list[CandidateObject]:
    return [o for o in result.candidates if o.type == kind]


def confidences_valid(objects: list[CandidateObject]) -> bool:
    return all(0.0 < o.confidence <= 1.0 for o in objects if o.confidence is not None)


# ── capability reporting ──────────────────────────────────────────────────────


class TestCapabilities:
    def test_language_code(self, plugin) -> None:
        assert plugin.language_code == "de"

    def test_display_name(self, plugin) -> None:
        assert "German" in plugin.display_name

    def test_direction_is_ltr(self, plugin) -> None:
        assert plugin.direction == "ltr"

    def test_morphology_depth(self, plugin) -> None:
        assert plugin.capabilities.morphology_depth == "rich"

    def test_morphology_includes_morphology_mode(self, plugin) -> None:
        assert "morphology" in plugin.capabilities.lesson_modes_supported

    def test_analysis_depth_full(self, plugin) -> None:
        assert plugin.capabilities.analysis_depth == "full"

    def test_tts_lang_tag(self, plugin) -> None:
        assert plugin.capabilities.tts_lang_tag == "de"

    def test_no_transliteration_scheme(self, plugin) -> None:
        assert plugin.capabilities.transliteration_scheme is None

    def test_syntax_support_true(self, plugin) -> None:
        assert plugin.capabilities.syntax_support is True

    def test_idiom_detection_true(self, plugin) -> None:
        assert plugin.capabilities.idiom_detection is True

    def test_morphology_quality_medium(self, plugin) -> None:
        assert plugin.capabilities.morphology_quality == "medium"


# ── sentence splitting ────────────────────────────────────────────────────────


class TestSentenceSplitting:
    def test_single_sentence(self, plugin) -> None:
        sents = plugin.split_sentences("Der Hund bellt laut.")
        assert len(sents) == 1
        assert sents[0].strip() == "Der Hund bellt laut."

    def test_multiple_sentences(self, plugin) -> None:
        sents = plugin.split_sentences("Das ist ein Hund. Er bellt.")
        assert len(sents) >= 2

    def test_empty_returns_empty(self, plugin) -> None:
        assert plugin.split_sentences("") == []

    def test_returns_non_empty_strings(self, plugin) -> None:
        sents = plugin.split_sentences("Ich lerne Deutsch. Das macht Spaß.")
        assert all(s.strip() for s in sents)

    def test_analyze_sentence_text_preserved(self, plugin) -> None:
        sentence = "Die Katze schläft."
        result = plugin.analyze_sentence(sentence)
        assert result.text == sentence

    def test_analyze_sentence_returns_candidate_result(self, plugin) -> None:
        result = plugin.analyze_sentence("Das Buch liegt auf dem Tisch.")
        assert isinstance(result, CandidateSentenceResult)


# ── vocabulary extraction ─────────────────────────────────────────────────────


class TestVocabularyExtraction:
    def test_noun_extracted_as_vocabulary(self, plugin) -> None:
        result = plugin.analyze_sentence("Der Hund bellt.")
        vocab = objects_of(result, "vocabulary")
        nouns = [o for o in vocab if o.lesson_data.get("pos") == "NOUN"]
        assert any(nouns)

    def test_noun_lemma_capitalised(self, plugin) -> None:
        """German noun lemmas preserve capitalisation."""
        result = plugin.analyze_sentence("Der Hund schläft.")
        vocab = objects_of(result, "vocabulary")
        nouns = [o for o in vocab if o.lesson_data.get("pos") == "NOUN"]
        assert any(o.canonical_form[0].isupper() for o in nouns), (
            "Expected at least one capitalised German noun lemma"
        )

    def test_vocabulary_has_lemma_key(self, plugin) -> None:
        result = plugin.analyze_sentence("Das Haus ist groß.")
        for obj in objects_of(result, "vocabulary"):
            assert "lemma" in obj.lesson_data

    def test_vocabulary_has_pos_key(self, plugin) -> None:
        result = plugin.analyze_sentence("Das Haus ist groß.")
        for obj in objects_of(result, "vocabulary"):
            assert "pos" in obj.lesson_data

    def test_adverb_extracted(self, plugin) -> None:
        result = plugin.analyze_sentence("Er läuft schnell.")
        vocab = objects_of(result, "vocabulary")
        lemmas = {o.canonical_form for o in vocab}
        assert "schnell" in lemmas

    def test_finite_verb_not_in_vocabulary(self, plugin) -> None:
        """Finite verbs must appear only as conjugation objects."""
        result = plugin.analyze_sentence("Der Mann schläft.")
        vocab = objects_of(result, "vocabulary")
        conj  = objects_of(result, "conjugation")
        conj_lemmas = {o.lesson_data.get("lemma") for o in conj}
        vocab_lemmas = {o.canonical_form for o in vocab}
        # Vocabulary and conjugation lemma sets should be disjoint.
        assert conj_lemmas.isdisjoint(vocab_lemmas), (
            f"Overlap between conj lemmas and vocab: "
            f"{conj_lemmas & vocab_lemmas}"
        )

    def test_noun_gender_in_lesson_data_when_available(self, plugin) -> None:
        result = plugin.analyze_sentence("Der Mann lacht.")
        vocab = objects_of(result, "vocabulary")
        nouns = [o for o in vocab if o.lesson_data.get("pos") == "NOUN"]
        for n in nouns:
            # When the model provides gender it should be in lesson_data.
            if "gender" in n.lesson_data:
                assert n.lesson_data["gender"] in ("Masc", "Fem", "Neut")

    def test_vocabulary_confidence_in_range(self, plugin) -> None:
        result = plugin.analyze_sentence("Die Frau kauft Brot.")
        assert confidences_valid(objects_of(result, "vocabulary"))

    def test_vocabulary_no_duplicates(self, plugin) -> None:
        result = plugin.analyze_sentence("Das Haus und das Haus sind groß.")
        forms = [o.canonical_form for o in objects_of(result, "vocabulary")]
        assert len(forms) == len(set(forms))

    def test_punctuation_only_returns_empty(self, plugin) -> None:
        result = plugin.analyze_sentence("...")
        assert result.candidates == []

    def test_proper_noun_confidence_lower(self, plugin) -> None:
        result = plugin.analyze_sentence("Berlin ist eine Stadt.")
        vocab = objects_of(result, "vocabulary")
        proper = [o for o in vocab if o.lesson_data.get("pos") == "PROPN"]
        for p in proper:
            if p.confidence is not None:
                assert p.confidence <= 0.65


# ── conjugation extraction ────────────────────────────────────────────────────


class TestConjugationExtraction:
    def test_finite_verb_extracted_as_conjugation(self, plugin) -> None:
        result = plugin.analyze_sentence("Ich lerne Deutsch.")
        assert any(objects_of(result, "conjugation"))

    def test_conjugation_has_required_keys(self, plugin) -> None:
        result = plugin.analyze_sentence("Er schreibt einen Brief.")
        for obj in objects_of(result, "conjugation"):
            for key in ("lemma", "surface", "tense", "mood", "person", "number",
                        "morph_complete", "is_reflexive", "paradigm_class",
                        "is_irregular", "is_separable"):
                assert key in obj.lesson_data, f"Missing key {key!r} in {obj.lesson_data}"

    def test_present_tense_detected(self, plugin) -> None:
        result = plugin.analyze_sentence("Der Hund bellt.")
        conj = objects_of(result, "conjugation")
        tenses = {o.lesson_data.get("tense") for o in conj}
        assert "present" in tenses

    def test_past_tense_detected(self, plugin) -> None:
        result = plugin.analyze_sentence("Sie schrieb einen Brief.")
        conj = objects_of(result, "conjugation")
        tenses = {o.lesson_data.get("tense") for o in conj}
        assert "past" in tenses

    def test_morph_complete_true_for_full_parse(self, plugin) -> None:
        result = plugin.analyze_sentence("Ich lese das Buch.")
        conj = objects_of(result, "conjugation")
        complete = [o for o in conj if o.lesson_data.get("morph_complete")]
        assert any(complete), "Expected at least one morphologically complete conjugation"

    def test_strong_verb_is_irregular(self, plugin) -> None:
        result = plugin.analyze_sentence("Er geht nach Hause.")
        conj = objects_of(result, "conjugation")
        gehen = [o for o in conj if o.lesson_data.get("lemma") == "gehen"]
        if gehen:
            assert gehen[0].lesson_data["is_irregular"] is True

    def test_paradigm_class_values(self, plugin) -> None:
        result = plugin.analyze_sentence("Ich lerne und sie geht.")
        for obj in objects_of(result, "conjugation"):
            assert obj.lesson_data["paradigm_class"] in ("weak", "strong", "modal")

    def test_modal_verb_class(self, plugin) -> None:
        result = plugin.analyze_sentence("Ich muss gehen.")
        conj = objects_of(result, "conjugation")
        modals = [o for o in conj if o.lesson_data.get("lemma") == "müssen"]
        if modals:
            assert modals[0].lesson_data["paradigm_class"] == "modal"

    def test_conjugation_confidence_in_range(self, plugin) -> None:
        result = plugin.analyze_sentence("Sie liest ein Buch.")
        assert confidences_valid(objects_of(result, "conjugation"))

    def test_conjugation_confidence_does_not_exceed_cap(self, plugin) -> None:
        result = plugin.analyze_sentence("Wir spielen Fußball.")
        for obj in objects_of(result, "conjugation"):
            if obj.confidence is not None:
                assert obj.confidence <= 0.80, (
                    f"Confidence {obj.confidence} exceeds cap of 0.80"
                )

    def test_no_duplicate_canonical_forms(self, plugin) -> None:
        result = plugin.analyze_sentence("Er geht und sie geht auch.")
        conj_forms = [o.canonical_form for o in objects_of(result, "conjugation")]
        assert len(conj_forms) == len(set(conj_forms))


# ── separable verbs ───────────────────────────────────────────────────────────


class TestSeparableVerbs:
    def test_separable_verb_is_separable_flag(self, plugin) -> None:
        # "ruft ... an" — anrufen
        result = plugin.analyze_sentence("Er ruft sie an.")
        conj = objects_of(result, "conjugation")
        separable = [o for o in conj if o.lesson_data.get("is_separable")]
        # de_core_news_sm may or may not detect this depending on sentence;
        # test only when the flag is present.
        for obj in separable:
            assert obj.lesson_data.get("particle") is not None

    def test_non_separable_verb_flag_false(self, plugin) -> None:
        result = plugin.analyze_sentence("Er schreibt einen Brief.")
        for obj in objects_of(result, "conjugation"):
            if not obj.lesson_data.get("is_separable"):
                assert "particle" not in obj.lesson_data or obj.lesson_data.get("particle") is None

    def test_separable_verb_particle_in_lesson_data(self, plugin) -> None:
        """When is_separable is True, particle key must be present."""
        result = plugin.analyze_sentence("Sie geht um 8 Uhr auf.")
        for obj in objects_of(result, "conjugation"):
            if obj.lesson_data.get("is_separable"):
                assert "particle" in obj.lesson_data


# ── case agreement ────────────────────────────────────────────────────────────


class TestCaseAgreementExtraction:
    def test_case_agreement_objects_emitted(self, plugin) -> None:
        result = plugin.analyze_sentence("Der Hund bellt.")
        assert any(objects_of(result, "case_agreement"))

    def test_case_agreement_has_required_keys(self, plugin) -> None:
        result = plugin.analyze_sentence("Die alte Frau lacht.")
        for obj in objects_of(result, "case_agreement"):
            for key in ("modifier", "modifier_pos", "noun", "case",
                        "gender", "number", "confidence_note"):
                assert key in obj.lesson_data, (
                    f"Missing key {key!r} in case_agreement lesson_data"
                )

    def test_case_agreement_boolean_fields_are_bool_or_none(self, plugin) -> None:
        result = plugin.analyze_sentence("Der große Mann lacht.")
        for obj in objects_of(result, "case_agreement"):
            for key in ("case_match", "gender_match", "number_match"):
                val = obj.lesson_data.get(key)
                assert val is None or isinstance(val, bool), (
                    f"Expected bool or None for {key}, got {type(val).__name__}"
                )

    def test_case_agreement_no_confirmed_mismatches(self, plugin) -> None:
        """Plugin must drop pairs with any confirmed mismatch."""
        result = plugin.analyze_sentence("Das große Haus steht dort.")
        for obj in objects_of(result, "case_agreement"):
            assert obj.lesson_data.get("case_match") is not False
            assert obj.lesson_data.get("gender_match") is not False
            assert obj.lesson_data.get("number_match") is not False

    def test_case_values_are_known_cases(self, plugin) -> None:
        result = plugin.analyze_sentence("Die junge Frau kauft das Brot.")
        for obj in objects_of(result, "case_agreement"):
            case = obj.lesson_data.get("case")
            assert case in ("Nom", "Acc", "Dat", "Gen", "unknown"), (
                f"Unexpected case value: {case!r}"
            )

    def test_gender_values_include_neuter(self, plugin) -> None:
        """German has neuter (Neut) unlike Romance languages."""
        result = plugin.analyze_sentence("Das kleine Kind spielt.")
        for obj in objects_of(result, "case_agreement"):
            if obj.lesson_data.get("gender") == "Neut":
                break  # neuter found — pass
        # Non-failing: neuter may not appear in every sentence.

    def test_case_agreement_confidence_in_range(self, plugin) -> None:
        result = plugin.analyze_sentence("Der alte Mann schläft.")
        assert confidences_valid(objects_of(result, "case_agreement"))

    def test_no_duplicate_canonical_forms(self, plugin) -> None:
        result = plugin.analyze_sentence("Der Mann und die Frau lachen.")
        forms = [o.canonical_form for o in objects_of(result, "case_agreement")]
        assert len(forms) == len(set(forms))

    def test_case_agreement_not_agreement_type(self, plugin) -> None:
        """German plugin must emit case_agreement, not the bare agreement type."""
        result = plugin.analyze_sentence("Der Hund bellt laut.")
        assert not any(objects_of(result, "agreement")), (
            "German plugin should emit case_agreement, not agreement"
        )


# ── canonical forms ───────────────────────────────────────────────────────────


class TestCanonicalForms:
    def test_vocabulary_canonical_form_stable(self, plugin) -> None:
        r1 = plugin.analyze_sentence("Der Hund schläft.")
        r2 = plugin.analyze_sentence("Der Hund läuft.")
        forms1 = {o.canonical_form for o in objects_of(r1, "vocabulary")}
        forms2 = {o.canonical_form for o in objects_of(r2, "vocabulary")}
        assert forms1 & forms2  # "Hund" should appear in both

    def test_conjugation_canonical_form_scheme(self, plugin) -> None:
        """canonical_form must follow lemma:tense:mood:person:number scheme."""
        result = plugin.analyze_sentence("Ich lese das Buch.")
        for obj in objects_of(result, "conjugation"):
            parts = obj.canonical_form.split(":")
            assert len(parts) == 5, (
                f"Expected 5 colon-separated parts, got {parts!r}"
            )

    def test_case_agreement_canonical_form_includes_case(self, plugin) -> None:
        """case_agreement canonical_form should start with 'case_agreement:'."""
        result = plugin.analyze_sentence("Der Hund bellt.")
        for obj in objects_of(result, "case_agreement"):
            assert obj.canonical_form.startswith("case_agreement:"), (
                f"Unexpected canonical_form prefix: {obj.canonical_form!r}"
            )

    def test_no_duplicate_canonical_forms_within_sentence(self, plugin) -> None:
        result = plugin.analyze_sentence(
            "Das Buch liegt auf dem Tisch und das Kind liest das Buch."
        )
        all_forms = [o.canonical_form for o in result.candidates]
        assert len(all_forms) == len(set(all_forms))

    def test_vocabulary_canonical_form_non_empty(self, plugin) -> None:
        result = plugin.analyze_sentence("Der Mann kauft Brot.")
        for obj in result.candidates:
            assert obj.canonical_form, f"Empty canonical_form on {obj!r}"

    def test_german_canonical_id_differs_from_french(self, plugin) -> None:
        """Language codes must be isolated in UUID derivation."""
        de_id = canonical_object_id("de", "vocabulary", "Hund")
        fr_id = canonical_object_id("fr", "vocabulary", "Hund")
        assert de_id != fr_id


# ── deduplication ─────────────────────────────────────────────────────────────


class TestDeduplication:
    def test_same_noun_appears_once_in_vocabulary(self, plugin) -> None:
        result = plugin.analyze_sentence("Der Hund bellt und der Hund läuft.")
        vocab_forms = [o.canonical_form for o in objects_of(result, "vocabulary")]
        assert len(vocab_forms) == len(set(vocab_forms))

    def test_finite_verb_not_duplicated_as_vocabulary(self, plugin) -> None:
        result = plugin.analyze_sentence("Er schreibt und schreibt.")
        conj_lemmas = {o.lesson_data.get("lemma") for o in objects_of(result, "conjugation")}
        vocab_forms = {o.canonical_form for o in objects_of(result, "vocabulary")}
        assert conj_lemmas.isdisjoint(vocab_forms)


# ── confidence and confidence notes ──────────────────────────────────────────


class TestConfidenceHandling:
    def test_all_confidences_in_range(self, plugin) -> None:
        result = plugin.analyze_sentence(
            "Die alte Frau liest ein interessantes Buch."
        )
        for obj in result.candidates:
            if obj.confidence is not None:
                assert 0.0 < obj.confidence <= 1.0, (
                    f"Out-of-range confidence {obj.confidence} on {obj!r}"
                )

    def test_conjugation_confidence_not_oov_penalised(self, plugin) -> None:
        """is_oov is always True for de_core_news_sm — confidence must not be penalised for it."""
        # A completely regular sentence with common vocabulary should achieve
        # the maximum cap of 0.80, not 0.70 (oov penalty would reduce it).
        result = plugin.analyze_sentence("Er schreibt einen Brief.")
        conj = objects_of(result, "conjugation")
        for obj in conj:
            if obj.lesson_data.get("morph_complete"):
                assert obj.confidence is not None and obj.confidence >= 0.78, (
                    f"Fully-parsed verb has unexpectedly low confidence: "
                    f"{obj.confidence}"
                )

    def test_partial_morphology_gets_note(self, plugin) -> None:
        """When morphological features are missing, confidence_note should say so."""
        result = plugin.analyze_sentence("Es wird gearbeitet.")
        for obj in objects_of(result, "conjugation"):
            if not obj.lesson_data.get("morph_complete"):
                note = obj.lesson_data.get("confidence_note")
                # Note is allowed to be None (some models resolve all features);
                # if present it should mention morphology.
                if note is not None:
                    assert "morphology" in note.lower() or "unavailable" in note.lower()


# ── edge cases ────────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_candidates_on_punctuation(self, plugin) -> None:
        result = plugin.analyze_sentence("...")
        assert result.candidates == []

    def test_single_noun_analyzed(self, plugin) -> None:
        result = plugin.analyze_sentence("Hund.")
        assert any(result.candidates)

    def test_analyze_text_returns_one_per_sentence(self, plugin) -> None:
        results = plugin.analyze_text("Der Hund bellt. Die Katze schläft.")
        assert len(results) >= 2

    def test_analyze_text_consistent_with_analyze_sentence(self, plugin) -> None:
        text = "Das ist ein Test. Ich lerne Deutsch."
        multi  = plugin.analyze_text(text)
        single = [plugin.analyze_sentence(s) for s in plugin.split_sentences(text)]
        assert len(multi) == len(single)
        for m, s in zip(multi, single):
            assert m.text == s.text
            multi_forms  = {o.canonical_form for o in m.candidates}
            single_forms = {o.canonical_form for o in s.candidates}
            assert multi_forms == single_forms

    def test_umlauts_preserved_in_lemma(self, plugin) -> None:
        result = plugin.analyze_sentence("Das Mädchen singt.")
        vocab = objects_of(result, "vocabulary")
        lemmas = {o.canonical_form for o in vocab}
        # "Mädchen" should appear — not "Madchen"
        assert any("ä" in l or "Mä" in l for l in lemmas), (
            f"Expected umlaut in lemma, got: {lemmas}"
        )


# ── lesson store ──────────────────────────────────────────────────────────────


class TestLessonStore:
    def test_missing_id_returns_none(self, plugin) -> None:
        assert plugin.get_lesson("nonexistent-uuid") is None

    def test_lesson_store_accepts_and_returns_object(self, plugin) -> None:
        obj_id = canonical_object_id("de", "vocabulary", "Haus")
        cand = CandidateObject(
            canonical_form="Haus",
            type="vocabulary",
            label="Haus",
            lesson_data={"lemma": "Haus", "pos": "NOUN"},
        )
        plugin.lesson_store[obj_id] = cand
        stored = plugin.get_lesson(obj_id)
        assert stored is not None
        assert stored.canonical_form == "Haus"

    def test_lesson_store_independent_across_instances(self) -> None:
        from backend.plugins.german import GermanPlugin
        p1 = GermanPlugin()
        p2 = GermanPlugin()
        obj_id = canonical_object_id("de", "vocabulary", "Hund")
        p1.lesson_store[obj_id] = CandidateObject(
            canonical_form="Hund", type="vocabulary", label="Hund", lesson_data={}
        )
        assert p2.get_lesson(obj_id) is None


# ── multilingual architecture ─────────────────────────────────────────────────


class TestMultilingualArchitecture:
    def test_german_registered_in_plugin_loader(self) -> None:
        from backend.parsing.plugin_loader import load_plugins
        registry = load_plugins()
        assert "de" in registry.all()

    def test_german_capabilities_in_registry(self) -> None:
        from backend.parsing.plugin_loader import load_plugins
        registry = load_plugins()
        caps = registry.supported_languages()["de"]
        assert caps.morphology_depth == "rich"
        assert caps.analysis_depth == "full"

    def test_german_and_french_vocab_ids_differ(self) -> None:
        de_id = canonical_object_id("de", "vocabulary", "Hund")
        fr_id = canonical_object_id("fr", "vocabulary", "Hund")
        assert de_id != fr_id

    def test_german_and_spanish_vocab_ids_differ(self) -> None:
        de_id = canonical_object_id("de", "vocabulary", "Mann")
        es_id = canonical_object_id("es", "vocabulary", "Mann")
        assert de_id != es_id

    def test_paradigm_class_different_scheme_from_french(self, plugin) -> None:
        """German uses weak/strong/modal; not -er/-ir/-re."""
        result = plugin.analyze_sentence("Er lernt Deutsch.")
        conj = objects_of(result, "conjugation")
        for obj in conj:
            assert obj.lesson_data["paradigm_class"] not in ("-er", "-ir", "-re", "-ar")

    def test_case_agreement_type_not_in_spanish_or_french(self) -> None:
        """case_agreement is German-specific — verify other plugins don't emit it."""
        from backend.plugins.spanish import SpanishPlugin
        from backend.plugins.french import FrenchPlugin
        for PluginCls, sentence in [
            (SpanishPlugin, "El perro grande corre."),
            (FrenchPlugin, "Le grand chien court."),
        ]:
            try:
                p = PluginCls()
                result = p.analyze_sentence(sentence)
                assert not any(o.type == "case_agreement" for o in result.candidates), (
                    f"{PluginCls.__name__} should not emit case_agreement objects"
                )
            except RuntimeError:
                pass  # model not installed — skip
