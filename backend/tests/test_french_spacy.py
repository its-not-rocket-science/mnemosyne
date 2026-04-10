"""Tests for the spaCy-backed French plugin (backend/plugins/french.py).

The entire module is skipped when spaCy or fr_core_news_sm is not installed
so the CI baseline stays green.

To enable these tests, install the model once:
    python -m spacy download fr_core_news_sm

Design intent
─────────────
Beyond verifying basic extraction, these tests document the *known limits* of
fr_core_news_sm and validate that the multilingual architecture generalises
beyond Spanish:

- Canonical forms use the same scheme as Spanish (lemma, lemma:t:m:p:n, …).
- lesson_data keys are the same cross-language fields.
- Confidence is capped lower (0.80) to reflect the model's higher error rate.
- Elision and contraction tokens are handled transparently.
- Reflexive detection uses Reflex=Yes morph rather than a hardcoded surface list.

Known fr_core_news_sm bugs that tests deliberately work around:
- Finite verbs after noun subjects are sometimes mis-tagged as ADJ/NOUN.
  Tests that would fail due to this are marked with a comment.
- Future simple (parlerai) may be tagged as Tense=Pres.
"""
from __future__ import annotations

import pytest

from backend.parsing.canonical import canonical_object_id
from backend.schemas.parse import CandidateObject, CandidateSentenceResult


# ── skip guard ────────────────────────────────────────────────────────────────

def _spacy_available() -> bool:
    try:
        import spacy  # noqa: PLC0415
        spacy.load("fr_core_news_sm", disable=["ner"])
        return True
    except (ImportError, OSError):
        return False


pytestmark = pytest.mark.skipif(
    not _spacy_available(),
    reason="spaCy + fr_core_news_sm not installed; "
           "run: python -m spacy download fr_core_news_sm",
)


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def plugin():
    from backend.plugins.french import FrenchPlugin
    return FrenchPlugin()


# ── helpers ───────────────────────────────────────────────────────────────────

def objects_of(result: CandidateSentenceResult, kind: str) -> list[CandidateObject]:
    return [o for o in result.candidates if o.type == kind]


def confidences_valid(objects: list[CandidateObject]) -> bool:
    return all(0.0 < o.confidence <= 1.0 for o in objects if o.confidence is not None)


# ── capability reporting ──────────────────────────────────────────────────────


class TestCapabilities:
    def test_language_code(self, plugin) -> None:
        assert plugin.language_code == "fr"

    def test_display_name_is_french(self, plugin) -> None:
        assert "French" in plugin.display_name

    def test_direction_is_ltr(self, plugin) -> None:
        assert plugin.direction == "ltr"

    def test_capabilities_code_matches(self, plugin) -> None:
        assert plugin.capabilities.code == "fr"

    def test_capabilities_morphology_depth_is_rich(self, plugin) -> None:
        assert plugin.capabilities.morphology_depth == "rich"

    def test_capabilities_analysis_depth_is_full(self, plugin) -> None:
        assert plugin.capabilities.analysis_depth == "full"

    def test_capabilities_morphology_supports_morphology_mode(self, plugin) -> None:
        assert "morphology" in plugin.capabilities.lesson_modes_supported

    def test_capabilities_syntax_support_is_true(self, plugin) -> None:
        assert plugin.capabilities.syntax_support is True

    def test_capabilities_idiom_detection_is_false(self, plugin) -> None:
        # Not yet implemented — must be declared honestly.
        assert plugin.capabilities.idiom_detection is False

    def test_capabilities_no_transliteration(self, plugin) -> None:
        assert plugin.capabilities.transliteration_scheme is None

    def test_capabilities_tts_lang_tag(self, plugin) -> None:
        assert plugin.capabilities.tts_lang_tag == "fr"


# ── sentence splitting ────────────────────────────────────────────────────────


class TestSentenceSplitting:
    def test_splits_multi_sentence_prose(self, plugin) -> None:
        sents = plugin.split_sentences("Bonjour. Comment allez-vous? Je vais bien.")
        assert len(sents) >= 2
        assert all(s.strip() for s in sents)

    def test_single_sentence_returned_as_one(self, plugin) -> None:
        sents = plugin.split_sentences("Le chat dort sur le canapé.")
        assert len(sents) == 1

    def test_empty_string_returns_empty_list(self, plugin) -> None:
        assert plugin.split_sentences("") == []

    def test_whitespace_only_returns_empty_list(self, plugin) -> None:
        assert plugin.split_sentences("   \n  ") == []

    def test_sentences_are_non_empty_strings(self, plugin) -> None:
        sents = plugin.split_sentences("Je parle. Tu écoutes.")
        assert all(isinstance(s, str) and s.strip() for s in sents)

    def test_sentence_text_preserved_verbatim(self, plugin) -> None:
        sentence = "Où est la bibliothèque?"
        result = plugin.analyze_sentence(sentence)
        assert result.text == sentence


# ── vocabulary extraction ─────────────────────────────────────────────────────


class TestVocabularyExtraction:
    def test_nouns_extracted(self, plugin) -> None:
        # Use a sentence where the model reliably tags the verb as VERB
        result = plugin.analyze_sentence("Nous mangeons du pain.")
        lemmas = {o.lesson_data["lemma"] for o in objects_of(result, "vocabulary")}
        assert "pain" in lemmas

    def test_determiners_excluded(self, plugin) -> None:
        result = plugin.analyze_sentence("La maison est grande.")
        lemmas = {o.lesson_data["lemma"] for o in objects_of(result, "vocabulary")}
        assert "le" not in lemmas
        assert "la" not in lemmas

    def test_prepositions_excluded(self, plugin) -> None:
        result = plugin.analyze_sentence("Nous vivons dans la ville.")
        lemmas = {o.lesson_data["lemma"] for o in objects_of(result, "vocabulary")}
        assert "dans" not in lemmas
        assert "de" not in lemmas

    def test_pronouns_excluded(self, plugin) -> None:
        result = plugin.analyze_sentence("Elle parle avec lui.")
        lemmas = {o.lesson_data["lemma"] for o in objects_of(result, "vocabulary")}
        assert "lui" not in lemmas
        # Subject pronoun lemmas should not appear
        pron_forms = {"il", "elle", "nous", "vous", "ils", "elles", "je", "tu"}
        assert not (lemmas & pron_forms)

    def test_no_duplicate_lemmas(self, plugin) -> None:
        result = plugin.analyze_sentence("Le chat et le chat noir.")
        lemmas = [o.lesson_data["lemma"] for o in objects_of(result, "vocabulary")]
        assert len(lemmas) == len(set(lemmas))

    def test_lesson_data_has_required_keys(self, plugin) -> None:
        result = plugin.analyze_sentence("Le chien court vite.")
        for obj in objects_of(result, "vocabulary"):
            assert "lemma" in obj.lesson_data
            assert "pos" in obj.lesson_data

    def test_noun_has_gender_when_available(self, plugin) -> None:
        result = plugin.analyze_sentence("La maison est grande.")
        vocab = objects_of(result, "vocabulary")
        maison = next(
            (o for o in vocab if o.lesson_data.get("lemma") == "maison"), None
        )
        assert maison is not None, "Expected 'maison' in vocabulary"
        # fr_core_news_sm provides Gender for 'maison'
        assert "gender" in maison.lesson_data

    def test_noun_has_number_when_available(self, plugin) -> None:
        result = plugin.analyze_sentence("Les enfants jouent.")
        vocab = objects_of(result, "vocabulary")
        enfant = next(
            (o for o in vocab if o.lesson_data.get("lemma") == "enfant"), None
        )
        assert enfant is not None, "Expected 'enfant' in vocabulary"
        assert "number" in enfant.lesson_data

    def test_confidence_in_valid_range(self, plugin) -> None:
        result = plugin.analyze_sentence("Les étudiants lisent des livres.")
        assert confidences_valid(objects_of(result, "vocabulary"))

    def test_elided_determiner_not_in_vocabulary(self, plugin) -> None:
        # "L'" is the elided form of "le" — must not appear in vocabulary.
        result = plugin.analyze_sentence("L'eau est froide.")
        lemmas = {o.lesson_data["lemma"] for o in objects_of(result, "vocabulary")}
        assert "le" not in lemmas
        assert "l" not in lemmas

    def test_contraction_au_not_in_vocabulary(self, plugin) -> None:
        # "au" = à + le; spaCy tags it as ADP → skipped.
        result = plugin.analyze_sentence("Je vais au marché.")
        lemmas = {o.lesson_data["lemma"] for o in objects_of(result, "vocabulary")}
        assert "au" not in lemmas

    def test_contraction_du_not_in_vocabulary(self, plugin) -> None:
        # "du" = de + le; spaCy tags it as ADP → skipped.
        result = plugin.analyze_sentence("Il revient du travail.")
        lemmas = {o.lesson_data["lemma"] for o in objects_of(result, "vocabulary")}
        assert "du" not in lemmas

    def test_infinitive_in_vocabulary(self, plugin) -> None:
        result = plugin.analyze_sentence("Je veux manger maintenant.")
        vocab_lemmas = {o.lesson_data["lemma"] for o in objects_of(result, "vocabulary")}
        assert "manger" in vocab_lemmas

    def test_multi_word_lemmas_excluded(self, plugin) -> None:
        # Enclitic-fusion artefacts produce multi-word lemmas — must be dropped.
        result = plugin.analyze_sentence("Il veut le faire.")
        lemmas = {o.lesson_data["lemma"] for o in objects_of(result, "vocabulary")}
        assert all(" " not in l for l in lemmas)


# ── conjugation extraction ────────────────────────────────────────────────────


class TestConjugationExtraction:
    def test_present_tense_detected(self, plugin) -> None:
        # Use explicit personal pronoun to help the model tag correctly.
        result = plugin.analyze_sentence("Nous mangeons ensemble.")
        conjs = objects_of(result, "conjugation")
        assert len(conjs) >= 1
        tenses = {o.lesson_data["tense"] for o in conjs}
        assert "present" in tenses

    def test_imperfect_tense_detected(self, plugin) -> None:
        result = plugin.analyze_sentence("Elle était fatiguée hier.")
        conjs = objects_of(result, "conjugation")
        tenses = {o.lesson_data["tense"] for o in conjs}
        assert "imperfect" in tenses

    def test_infinitive_not_in_conjugation(self, plugin) -> None:
        result = plugin.analyze_sentence("Je veux manger maintenant.")
        conj_surfaces = {o.lesson_data["surface"].lower() for o in objects_of(result, "conjugation")}
        assert "manger" not in conj_surfaces

    def test_conjugation_has_required_keys(self, plugin) -> None:
        result = plugin.analyze_sentence("Nous finissons le travail.")
        for obj in objects_of(result, "conjugation"):
            for key in ("lemma", "surface", "tense", "mood", "person", "number"):
                assert key in obj.lesson_data, f"Missing key {key!r} in {obj.lesson_data}"

    def test_morph_complete_flag_present(self, plugin) -> None:
        result = plugin.analyze_sentence("Vous vendez des légumes.")
        for obj in objects_of(result, "conjugation"):
            assert "morph_complete" in obj.lesson_data
            assert isinstance(obj.lesson_data["morph_complete"], bool)

    def test_paradigm_class_present(self, plugin) -> None:
        result = plugin.analyze_sentence("Nous finissons le travail.")
        for obj in objects_of(result, "conjugation"):
            assert "paradigm_class" in obj.lesson_data

    def test_is_irregular_bool_present(self, plugin) -> None:
        result = plugin.analyze_sentence("Nous finissons le travail.")
        for obj in objects_of(result, "conjugation"):
            assert "is_irregular" in obj.lesson_data
            assert isinstance(obj.lesson_data["is_irregular"], bool)

    def test_etre_is_irregular(self, plugin) -> None:
        result = plugin.analyze_sentence("La maison est grande.")
        conjs = objects_of(result, "conjugation")
        etre_conj = next(
            (o for o in conjs if o.lesson_data.get("lemma") == "être"), None
        )
        assert etre_conj is not None, "Expected être conjugation"
        assert etre_conj.lesson_data["is_irregular"] is True

    def test_avoir_is_irregular(self, plugin) -> None:
        result = plugin.analyze_sentence("Nous avons mangé.")
        conjs = objects_of(result, "conjugation")
        avoir_conj = next(
            (o for o in conjs if o.lesson_data.get("lemma") == "avoir"), None
        )
        assert avoir_conj is not None, "Expected avoir conjugation"
        assert avoir_conj.lesson_data["is_irregular"] is True

    def test_parler_paradigm_class_is_er(self, plugin) -> None:
        result = plugin.analyze_sentence("Nous parlons français.")
        conjs = objects_of(result, "conjugation")
        parler_conj = next(
            (o for o in conjs if o.lesson_data.get("lemma") == "parler"), None
        )
        assert parler_conj is not None, "Expected parler conjugation"
        assert parler_conj.lesson_data["paradigm_class"] == "-er"

    def test_finir_paradigm_class_is_ir(self, plugin) -> None:
        result = plugin.analyze_sentence("Nous finissons le travail.")
        conjs = objects_of(result, "conjugation")
        finir_conj = next(
            (o for o in conjs if o.lesson_data.get("lemma") == "finir"), None
        )
        assert finir_conj is not None, "Expected finir conjugation"
        assert finir_conj.lesson_data["paradigm_class"] == "-ir"

    def test_confidence_in_valid_range(self, plugin) -> None:
        result = plugin.analyze_sentence("Vous vendez des légumes.")
        assert confidences_valid(objects_of(result, "conjugation"))

    def test_confidence_capped_at_0_80(self, plugin) -> None:
        # French plugin caps at 0.80, not 0.85, due to higher model error rate.
        result = plugin.analyze_sentence("Elle finit le travail.")
        for obj in objects_of(result, "conjugation"):
            assert obj.confidence is not None
            assert obj.confidence <= 0.80

    def test_conjugation_id_is_stable(self, plugin) -> None:
        r1 = plugin.analyze_sentence("Nous parlons français.")
        r2 = plugin.analyze_sentence("Nous parlons français.")
        ids1 = {canonical_object_id("fr", o.type, o.canonical_form) for o in objects_of(r1, "conjugation")}
        ids2 = {canonical_object_id("fr", o.type, o.canonical_form) for o in objects_of(r2, "conjugation")}
        assert ids1 == ids2

    def test_canonical_form_has_five_parts(self, plugin) -> None:
        result = plugin.analyze_sentence("Vous vendez des légumes.")
        for obj in objects_of(result, "conjugation"):
            parts = obj.canonical_form.split(":")
            assert len(parts) == 5, f"Unexpected canonical_form: {obj.canonical_form!r}"

    def test_conjugation_has_relation_hint(self, plugin) -> None:
        result = plugin.analyze_sentence("Elle finit le travail.")
        for obj in objects_of(result, "conjugation"):
            assert obj.relation_hints, f"No relation_hints on {obj.canonical_form}"
            relations = {h.relation_type for h in obj.relation_hints}
            assert "conjugation_of" in relations

    def test_reflexive_detected(self, plugin) -> None:
        # "se lève" — the reflexive pronoun "se" has Reflex=Yes.
        result = plugin.analyze_sentence("Elle se lève tôt.")
        conjs = objects_of(result, "conjugation")
        lever_conj = next(
            (o for o in conjs if o.lesson_data.get("lemma") == "lever"), None
        )
        assert lever_conj is not None, "Expected lever conjugation"
        assert lever_conj.lesson_data["is_reflexive"] is True

    def test_non_reflexive_verb_not_flagged(self, plugin) -> None:
        result = plugin.analyze_sentence("Elle finit le travail.")
        for obj in objects_of(result, "conjugation"):
            assert obj.lesson_data["is_reflexive"] is False

    def test_conditional_mood_detected(self, plugin) -> None:
        # "auraient" has Mood=Cnd
        result = plugin.analyze_sentence("Ils auraient pu venir.")
        conjs = objects_of(result, "conjugation")
        moods = {o.lesson_data["mood"] for o in conjs}
        assert "conditional" in moods


# ── deduplication ─────────────────────────────────────────────────────────────


class TestDeduplication:
    def test_finite_verb_not_in_vocabulary(self, plugin) -> None:
        result = plugin.analyze_sentence("Nous mangeons ensemble.")
        vocab_lemmas = {o.lesson_data["lemma"] for o in objects_of(result, "vocabulary")}
        assert "manger" not in vocab_lemmas

    def test_no_canonical_form_appears_twice(self, plugin) -> None:
        result = plugin.analyze_sentence(
            "Nous mangeons du pain avec des étudiants."
        )
        forms = [o.canonical_form for o in result.candidates]
        assert len(forms) == len(set(forms))

    def test_infinitive_in_vocabulary_when_no_finite_form(self, plugin) -> None:
        result = plugin.analyze_sentence("Je veux manger maintenant.")
        vocab_lemmas = {o.lesson_data["lemma"] for o in objects_of(result, "vocabulary")}
        assert "manger" in vocab_lemmas

    def test_finite_aux_not_in_vocabulary(self, plugin) -> None:
        result = plugin.analyze_sentence("Nous avons mangé.")
        vocab_lemmas = {o.lesson_data["lemma"] for o in objects_of(result, "vocabulary")}
        assert "avoir" not in vocab_lemmas


# ── agreement extraction ──────────────────────────────────────────────────────


class TestAgreementExtraction:
    def test_det_noun_agreement_extracted(self, plugin) -> None:
        result = plugin.analyze_sentence("La maison est grande.")
        assert len(objects_of(result, "agreement")) >= 1

    def test_adj_noun_agreement_extracted(self, plugin) -> None:
        result = plugin.analyze_sentence("Une petite maison verte.")
        assert len(objects_of(result, "agreement")) >= 1

    def test_plural_agreement_detected(self, plugin) -> None:
        result = plugin.analyze_sentence("Les petits chiens noirs courent.")
        agreements = objects_of(result, "agreement")
        assert len(agreements) >= 1
        numbers = {o.lesson_data["number"] for o in agreements}
        assert "Plur" in numbers

    def test_agreement_has_required_keys(self, plugin) -> None:
        result = plugin.analyze_sentence("La grande maison.")
        for obj in objects_of(result, "agreement"):
            for key in ("modifier", "modifier_pos", "noun", "gender", "number"):
                assert key in obj.lesson_data, f"Missing key {key!r}"

    def test_agreement_confidence_in_valid_range(self, plugin) -> None:
        result = plugin.analyze_sentence("La belle maison blanche.")
        assert confidences_valid(objects_of(result, "agreement"))

    def test_agreement_id_stable_across_identical_sentences(self, plugin) -> None:
        r1 = plugin.analyze_sentence("La maison blanche est grande.")
        r2 = plugin.analyze_sentence("La maison blanche est grande.")
        ids1 = {canonical_object_id("fr", o.type, o.canonical_form) for o in objects_of(r1, "agreement")}
        ids2 = {canonical_object_id("fr", o.type, o.canonical_form) for o in objects_of(r2, "agreement")}
        assert ids1 == ids2

    def test_no_confirmed_mismatch_emitted(self, plugin) -> None:
        result = plugin.analyze_sentence("Les grandes maisons bleues sont belles.")
        for obj in objects_of(result, "agreement"):
            assert obj.lesson_data.get("gender_match") is not False
            assert obj.lesson_data.get("number_match") is not False

    def test_agreement_canonical_form_uses_lemmas(self, plugin) -> None:
        result = plugin.analyze_sentence("Les grandes maisons.")
        for obj in objects_of(result, "agreement"):
            # Surface form "les" lemmatises to "le"; must not appear verbatim.
            assert "les" not in obj.canonical_form, (
                f"Surface 'les' found in canonical_form: {obj.canonical_form!r}"
            )

    def test_agreement_has_relation_hint(self, plugin) -> None:
        result = plugin.analyze_sentence("La belle maison.")
        for obj in objects_of(result, "agreement"):
            assert obj.relation_hints
            relations = {h.relation_type for h in obj.relation_hints}
            assert "agreement_of" in relations

    def test_post_nominal_adj_agreement_extracted(self, plugin) -> None:
        # French ADJ often follows the noun: "maison blanche".
        result = plugin.analyze_sentence("Une maison blanche.")
        agreements = objects_of(result, "agreement")
        assert len(agreements) >= 1

    def test_pre_nominal_adj_agreement_extracted(self, plugin) -> None:
        # French ADJ can precede the noun: "belle maison".
        result = plugin.analyze_sentence("Une belle maison.")
        agreements = objects_of(result, "agreement")
        assert len(agreements) >= 1


# ── canonical forms ───────────────────────────────────────────────────────────


class TestCanonicalForms:
    def test_vocabulary_canonical_form_is_lemma(self, plugin) -> None:
        result = plugin.analyze_sentence("Les enfants jouent dans le jardin.")
        for obj in objects_of(result, "vocabulary"):
            assert obj.canonical_form == obj.lesson_data["lemma"]

    def test_conjugation_canonical_form_format(self, plugin) -> None:
        result = plugin.analyze_sentence("Vous vendez des légumes.")
        for obj in objects_of(result, "conjugation"):
            parts = obj.canonical_form.split(":")
            assert len(parts) == 5

    def test_same_word_same_canonical_form_across_sentences(self, plugin) -> None:
        r1 = plugin.analyze_sentence("Les enfants jouent.")
        r2 = plugin.analyze_sentence("Beaucoup d'enfants arrivent.")
        cf1 = {o.canonical_form for o in objects_of(r1, "vocabulary")}
        cf2 = {o.canonical_form for o in objects_of(r2, "vocabulary")}
        assert "enfant" in cf1 & cf2

    def test_canonical_object_id_is_deterministic(self, plugin) -> None:
        result = plugin.analyze_sentence("Nous finissons le travail.")
        for obj in result.candidates:
            id1 = canonical_object_id("fr", obj.type, obj.canonical_form)
            id2 = canonical_object_id("fr", obj.type, obj.canonical_form)
            assert id1 == id2

    def test_canonical_object_id_is_uuid(self, plugin) -> None:
        result = plugin.analyze_sentence("Elle finit le travail.")
        for obj in result.candidates:
            obj_id = canonical_object_id("fr", obj.type, obj.canonical_form)
            assert len(obj_id) == 36
            assert obj_id.count("-") == 4

    def test_french_and_spanish_ids_differ(self, plugin) -> None:
        # "maison" and Spanish "casa" share nothing; French "chat" and
        # Spanish "gato" differ.  More importantly, even if a word were
        # spelled the same in both languages, its UUID must differ because
        # the language code is part of the key.
        fr_id = canonical_object_id("fr", "vocabulary", "chat")
        es_id = canonical_object_id("es", "vocabulary", "chat")
        assert fr_id != es_id, (
            "Same canonical_form in two languages must produce different UUIDs"
        )


# ── confidence handling ───────────────────────────────────────────────────────


class TestConfidenceHandling:
    def test_propn_has_reduced_confidence(self, plugin) -> None:
        result = plugin.analyze_sentence("Elle parle avec Marie.")
        vocab = objects_of(result, "vocabulary")
        propn_confs = [o.confidence for o in vocab if o.lesson_data.get("pos") == "PROPN"]
        assert propn_confs, "Expected at least one PROPN"
        assert all(c == 0.60 for c in propn_confs)

    def test_conjugation_max_confidence_is_0_80(self, plugin) -> None:
        # French plugin caps at 0.80, not 0.85 (higher model error rate).
        result = plugin.analyze_sentence("Elle finit le travail.")
        for obj in objects_of(result, "conjugation"):
            assert obj.confidence is not None
            assert obj.confidence <= 0.80

    def test_complete_morph_gives_higher_conjugation_confidence(self, plugin) -> None:
        result = plugin.analyze_sentence("Vous vendez des légumes.")
        for obj in objects_of(result, "conjugation"):
            if obj.lesson_data["morph_complete"]:
                assert obj.confidence >= 0.60

    def test_full_agreement_match_confidence(self, plugin) -> None:
        result = plugin.analyze_sentence("La grande maison.")
        full_match = [
            o for o in objects_of(result, "agreement")
            if o.lesson_data.get("gender_match") is True
            and o.lesson_data.get("number_match") is True
        ]
        for obj in full_match:
            assert obj.confidence == 0.85

    def test_all_confidences_in_valid_range(self, plugin) -> None:
        result = plugin.analyze_sentence(
            "Les grandes maisons blanches sont belles."
        )
        for obj in result.candidates:
            if obj.confidence is not None:
                assert 0.0 < obj.confidence <= 1.0


# ── edge cases ────────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_punctuation_only_returns_no_objects(self, plugin) -> None:
        result = plugin.analyze_sentence("...")
        assert result.candidates == []

    def test_single_word_does_not_crash(self, plugin) -> None:
        result = plugin.analyze_sentence("Bonjour.")
        assert isinstance(result.candidates, list)

    def test_repeated_analysis_is_idempotent(self, plugin) -> None:
        sentence = "Le chat noir dort."
        r1 = plugin.analyze_sentence(sentence)
        r2 = plugin.analyze_sentence(sentence)
        assert {o.canonical_form for o in r1.candidates} == {o.canonical_form for o in r2.candidates}

    def test_all_returned_types_are_known(self, plugin) -> None:
        known_types = {"vocabulary", "conjugation", "agreement"}
        result = plugin.analyze_sentence(
            "Les grandes maisons blanches sont belles."
        )
        for obj in result.candidates:
            assert obj.type in known_types, f"Unknown type: {obj.type!r}"

    def test_canonical_forms_are_non_empty_strings(self, plugin) -> None:
        result = plugin.analyze_sentence("Nous finissons ensemble.")
        for obj in result.candidates:
            assert isinstance(obj.canonical_form, str) and obj.canonical_form


# ── lesson store ──────────────────────────────────────────────────────────────


class TestLessonStore:
    def test_missing_id_returns_none(self, plugin) -> None:
        assert plugin.get_lesson("nonexistent-uuid-0000") is None

    def test_stored_object_is_retrievable(self, plugin) -> None:
        fake_id = canonical_object_id("fr", "vocabulary", "_test_fr_")
        cand = CandidateObject(
            canonical_form="_test_fr_",
            type="vocabulary",
            label="test",
            lesson_data={"lemma": "_test_fr_"},
        )
        plugin.lesson_store[fake_id] = cand
        stored = plugin.get_lesson(fake_id)
        assert stored is not None
        assert stored.canonical_form == "_test_fr_"


# ── multilingual architecture validation ─────────────────────────────────────


class TestMultilingualArchitecture:
    """Validate that the multilingual plugin architecture generalises beyond Spanish.

    These tests are intentionally cross-cutting — they check that the French
    plugin produces structurally identical output to the Spanish plugin so the
    lesson generator and route layer can treat them uniformly.
    """

    def test_vocabulary_lesson_data_has_same_keys_as_spanish(self, plugin) -> None:
        result = plugin.analyze_sentence("Les étudiants lisent des livres.")
        for obj in objects_of(result, "vocabulary"):
            assert "lemma" in obj.lesson_data
            assert "pos" in obj.lesson_data
            # No extra required keys — additional keys (gender, number, verb_form)
            # are optional and match what the Spanish plugin also emits.

    def test_conjugation_lesson_data_has_same_required_keys_as_spanish(self, plugin) -> None:
        result = plugin.analyze_sentence("Vous vendez des légumes.")
        for obj in objects_of(result, "conjugation"):
            required = {
                "lemma", "surface", "tense", "mood", "person", "number",
                "morph_complete", "is_reflexive", "paradigm_class", "is_irregular",
            }
            missing = required - obj.lesson_data.keys()
            assert not missing, f"Missing keys: {missing}"

    def test_agreement_lesson_data_has_same_keys_as_spanish(self, plugin) -> None:
        result = plugin.analyze_sentence("La belle maison.")
        for obj in objects_of(result, "agreement"):
            required = {"modifier", "modifier_pos", "noun", "gender", "number"}
            missing = required - obj.lesson_data.keys()
            assert not missing, f"Missing keys: {missing}"

    def test_paradigm_class_is_different_scheme_from_spanish(self, plugin) -> None:
        # French uses -er/-ir/-re/irregular; Spanish uses -ar/-er/-ir/irregular.
        # This test documents the difference so future paradigm-table builders
        # know to check the language code before interpreting the value.
        result = plugin.analyze_sentence("Nous finissons le travail.")
        conjs = objects_of(result, "conjugation")
        finir_conj = next(
            (o for o in conjs if o.lesson_data.get("lemma") == "finir"), None
        )
        if finir_conj:
            # French "-ir" is a valid paradigm_class; Spanish "-er" would be wrong here.
            assert finir_conj.lesson_data["paradigm_class"] == "-ir"
            # Not "-ar" which would indicate a Spanish assumption bleed-through.
            assert finir_conj.lesson_data["paradigm_class"] != "-ar"
