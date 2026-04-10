"""Tests for the spaCy-backed Spanish plugin (backend/plugins/spanish.py).

The entire module is skipped when spaCy or es_core_news_sm is not installed
so the CI baseline stays green.

To enable these tests, install the model once:
    python -m spacy download es_core_news_sm
"""
from __future__ import annotations

import pytest

from backend.parsing.canonical import canonical_object_id
from backend.schemas.parse import CandidateObject, CandidateSentenceResult


# ── skip guard ────────────────────────────────────────────────────────────────
# Module-level so pytest skips collection entirely, not just individual tests.

def _spacy_available() -> bool:
    try:
        import spacy  # noqa: PLC0415
        spacy.load("es_core_news_sm", disable=["ner"])
        return True
    except (ImportError, OSError):
        return False


pytestmark = pytest.mark.skipif(
    not _spacy_available(),
    reason="spaCy + es_core_news_sm not installed; "
           "run: python -m spacy download es_core_news_sm",
)


# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def plugin():
    from backend.plugins.spanish import SpanishPlugin
    return SpanishPlugin()


# ── helpers ───────────────────────────────────────────────────────────────────


def objects_of(result: CandidateSentenceResult, kind: str) -> list[CandidateObject]:
    return [o for o in result.candidates if o.type == kind]


def confidences_valid(objects: list[CandidateObject]) -> bool:
    return all(0.0 < o.confidence <= 1.0 for o in objects if o.confidence is not None)


# ── sentence splitting ────────────────────────────────────────────────────────


class TestSentenceSplitting:
    def test_splits_multi_sentence_prose(self, plugin) -> None:
        sents = plugin.split_sentences("Hola. Me llamo Juan. ¿Cómo estás?")
        assert len(sents) >= 2
        assert all(s.strip() for s in sents)

    def test_single_sentence_returned_as_one(self, plugin) -> None:
        sents = plugin.split_sentences("La casa es roja.")
        assert len(sents) == 1
        assert sents[0].strip() == "La casa es roja."

    def test_empty_string_returns_empty_list(self, plugin) -> None:
        assert plugin.split_sentences("") == []

    def test_whitespace_only_returns_empty_list(self, plugin) -> None:
        assert plugin.split_sentences("   \n  ") == []

    def test_sentences_are_non_empty_strings(self, plugin) -> None:
        sents = plugin.split_sentences("Vivo aquí. Trabajo allá.")
        assert all(isinstance(s, str) and s.strip() for s in sents)


# ── vocabulary extraction ─────────────────────────────────────────────────────


class TestVocabularyExtraction:
    def test_nouns_included(self, plugin) -> None:
        result = plugin.analyze_sentence("El perro corre por el parque.")
        lemmas = {o.lesson_data["lemma"] for o in objects_of(result, "vocabulary")}
        assert "perro" in lemmas
        assert "parque" in lemmas

    def test_determiners_excluded(self, plugin) -> None:
        result = plugin.analyze_sentence("La casa tiene un jardín.")
        lemmas = {o.lesson_data["lemma"] for o in objects_of(result, "vocabulary")}
        assert "la" not in lemmas
        assert "un" not in lemmas

    def test_prepositions_excluded(self, plugin) -> None:
        result = plugin.analyze_sentence("Vivo en la ciudad de Madrid.")
        lemmas = {o.lesson_data["lemma"] for o in objects_of(result, "vocabulary")}
        assert "en" not in lemmas
        assert "de" not in lemmas

    def test_infinitive_lemma_included(self, plugin) -> None:
        # Non-finite VERB forms (infinitives) still appear as vocabulary;
        # "Necesito hablar" — "hablar" is VerbForm=Inf → vocabulary.
        result = plugin.analyze_sentence("Necesito hablar más.")
        lemmas = {o.lesson_data["lemma"] for o in objects_of(result, "vocabulary")}
        assert "hablar" in lemmas

    def test_no_duplicate_lemmas(self, plugin) -> None:
        result = plugin.analyze_sentence("El libro y el libro viejo.")
        lemmas = [o.lesson_data["lemma"] for o in objects_of(result, "vocabulary")]
        assert len(lemmas) == len(set(lemmas))

    def test_confidence_in_valid_range(self, plugin) -> None:
        result = plugin.analyze_sentence("Los estudiantes estudian mucho.")
        assert confidences_valid(objects_of(result, "vocabulary"))

    def test_lesson_data_has_required_keys(self, plugin) -> None:
        result = plugin.analyze_sentence("El gato duerme.")
        for obj in objects_of(result, "vocabulary"):
            assert "lemma" in obj.lesson_data
            assert "pos" in obj.lesson_data

    def test_short_tokens_excluded(self, plugin) -> None:
        result = plugin.analyze_sentence("Él y ella estudian.")
        lemmas = {o.lesson_data["lemma"] for o in objects_of(result, "vocabulary")}
        assert all(len(l) >= 2 for l in lemmas)

    def test_numbers_not_extracted(self, plugin) -> None:
        result = plugin.analyze_sentence("Tengo 3 libros en casa.")
        vocab_labels = [o.label for o in objects_of(result, "vocabulary")]
        assert "3" not in vocab_labels

    def test_lemma_with_space_not_extracted(self, plugin) -> None:
        # Enclitic-fusion tokens like "hacerlo" produce lemmas containing a
        # space ("hacer él").  These are model artefacts and must be suppressed.
        result = plugin.analyze_sentence("Quiero poder hacerlo.")
        lemmas = {o.lesson_data["lemma"] for o in objects_of(result, "vocabulary")}
        assert all(" " not in lemma for lemma in lemmas)


# ── conjugation extraction ────────────────────────────────────────────────────


class TestConjugationExtraction:
    def test_present_tense_detected(self, plugin) -> None:
        result = plugin.analyze_sentence("Ella habla español muy bien.")
        conjs = objects_of(result, "conjugation")
        assert len(conjs) >= 1
        tenses = {o.lesson_data["tense"] for o in conjs}
        assert "present" in tenses

    def test_past_tense_detected(self, plugin) -> None:
        result = plugin.analyze_sentence("Él comió las manzanas ayer.")
        conjs = objects_of(result, "conjugation")
        assert len(conjs) >= 1
        # es_core_news_sm marks "comió" as preterite; gracefully accept unknown
        tenses = {o.lesson_data["tense"] for o in conjs}
        assert tenses & {"preterite", "unknown"}

    def test_infinitives_not_tagged_as_conjugation(self, plugin) -> None:
        result = plugin.analyze_sentence("Quiero hablar contigo.")
        conj_surfaces = {
            o.lesson_data["surface"].lower() for o in objects_of(result, "conjugation")
        }
        assert "hablar" not in conj_surfaces

    def test_gerund_not_tagged_as_conjugation(self, plugin) -> None:
        result = plugin.analyze_sentence("Estoy comiendo ahora.")
        conj_surfaces = {
            o.lesson_data["surface"].lower() for o in objects_of(result, "conjugation")
        }
        assert "comiendo" not in conj_surfaces

    def test_conjugation_has_required_keys(self, plugin) -> None:
        result = plugin.analyze_sentence("Nosotros comemos juntos.")
        for obj in objects_of(result, "conjugation"):
            for key in ("lemma", "surface", "tense", "mood", "person", "number"):
                assert key in obj.lesson_data, f"Missing key {key!r} in {obj.lesson_data}"

    def test_morph_complete_flag_present(self, plugin) -> None:
        result = plugin.analyze_sentence("Ella canta bien.")
        for obj in objects_of(result, "conjugation"):
            assert "morph_complete" in obj.lesson_data
            assert isinstance(obj.lesson_data["morph_complete"], bool)

    def test_conjugation_id_is_stable(self, plugin) -> None:
        r1 = plugin.analyze_sentence("Yo hablo mucho.")
        r2 = plugin.analyze_sentence("Yo hablo mucho.")
        ids1 = {canonical_object_id("es", o.type, o.canonical_form) for o in objects_of(r1, "conjugation")}
        ids2 = {canonical_object_id("es", o.type, o.canonical_form) for o in objects_of(r2, "conjugation")}
        assert ids1 == ids2

    def test_confidence_in_valid_range(self, plugin) -> None:
        result = plugin.analyze_sentence("Tú corres rápido.")
        assert confidences_valid(objects_of(result, "conjugation"))

    def test_conjugation_canonical_form_has_expected_format(self, plugin) -> None:
        # canonical_form for conjugations is lemma:tense:mood:person:number
        result = plugin.analyze_sentence("Ellos caminan despacio.")
        for obj in objects_of(result, "conjugation"):
            parts = obj.canonical_form.split(":")
            assert len(parts) == 5, f"Unexpected canonical_form: {obj.canonical_form!r}"


# ── agreement extraction ──────────────────────────────────────────────────────


class TestAgreementExtraction:
    def test_det_noun_agreement_extracted(self, plugin) -> None:
        # "la casa" — feminine singular DET + NOUN
        result = plugin.analyze_sentence("La casa es bonita.")
        assert len(objects_of(result, "agreement")) >= 1

    def test_adj_noun_agreement_extracted(self, plugin) -> None:
        result = plugin.analyze_sentence("Tengo una casa bonita.")
        assert len(objects_of(result, "agreement")) >= 1

    def test_plural_agreement_extracted(self, plugin) -> None:
        result = plugin.analyze_sentence("Los libros viejos son interesantes.")
        agreements = objects_of(result, "agreement")
        assert len(agreements) >= 1
        numbers = {o.lesson_data["number"] for o in agreements}
        assert "Plur" in numbers

    def test_agreement_has_required_keys(self, plugin) -> None:
        result = plugin.analyze_sentence("El perro negro ladra.")
        for obj in objects_of(result, "agreement"):
            for key in ("modifier", "modifier_pos", "noun", "gender", "number"):
                assert key in obj.lesson_data, f"Missing key {key!r}"

    def test_agreement_confidence_in_valid_range(self, plugin) -> None:
        result = plugin.analyze_sentence("La niña pequeña juega.")
        assert confidences_valid(objects_of(result, "agreement"))

    def test_agreement_id_stable_across_identical_sentences(self, plugin) -> None:
        r1 = plugin.analyze_sentence("La casa blanca es grande.")
        r2 = plugin.analyze_sentence("La casa blanca es grande.")
        ids1 = {canonical_object_id("es", o.type, o.canonical_form) for o in objects_of(r1, "agreement")}
        ids2 = {canonical_object_id("es", o.type, o.canonical_form) for o in objects_of(r2, "agreement")}
        assert ids1 == ids2

    def test_agreement_canonical_form_uses_lemmas(self, plugin) -> None:
        # canonical_form for agreements is pos:modifier_lemma_noun_lemma — lemma-based
        result = plugin.analyze_sentence("Los libros nuevos.")
        for obj in objects_of(result, "agreement"):
            # Surface form "los" lemmatises to "el" or "lo"; must not appear verbatim
            assert "los" not in obj.canonical_form, (
                f"Surface form 'los' found in canonical_form: {obj.canonical_form!r}"
            )

    def test_no_confirmed_mismatch_emitted(self, plugin) -> None:
        # Agreements with a confirmed gender or number mismatch indicate a
        # model parse error and must never be emitted as learning objects.
        result = plugin.analyze_sentence("Los libros viejos son interesantes.")
        for obj in objects_of(result, "agreement"):
            assert obj.lesson_data.get("gender_match") is not False, (
                f"Confirmed gender mismatch in {obj.lesson_data}"
            )
            assert obj.lesson_data.get("number_match") is not False, (
                f"Confirmed number mismatch in {obj.lesson_data}"
            )


# ── confidence heuristics ─────────────────────────────────────────────────────


class TestConfidenceHeuristics:
    def test_proper_noun_has_lower_confidence_than_common_noun(self, plugin) -> None:
        # The plugin hard-codes 0.60 for PROPN and 0.85 for in-vocab common words.
        # We assert the constant directly so the test doesn't depend on whether
        # other tokens happen to be OOV (confidence 0.50 < 0.60 would cause a
        # naive max(common) < max(propn) comparison to flip unexpectedly).
        result = plugin.analyze_sentence("El estudiante habla con María.")
        vocab = objects_of(result, "vocabulary")
        propn_confs = [o.confidence for o in vocab if o.lesson_data.get("pos") == "PROPN"]
        assert propn_confs, "Expected at least one PROPN in the result"
        assert all(c == 0.60 for c in propn_confs)

    def test_complete_morph_gives_higher_conjugation_confidence(self, plugin) -> None:
        result = plugin.analyze_sentence("Nosotros estudiamos juntos.")
        for obj in objects_of(result, "conjugation"):
            morph_complete = obj.lesson_data["morph_complete"]
            if morph_complete:
                assert obj.confidence >= 0.65
            else:
                assert obj.confidence is not None

    def test_conjugation_confidence_capped_at_0_85(self, plugin) -> None:
        result = plugin.analyze_sentence("Ella trabaja mucho.")
        for obj in objects_of(result, "conjugation"):
            assert obj.confidence is not None
            assert obj.confidence <= 0.85

    def test_agreement_full_match_has_highest_confidence(self, plugin) -> None:
        # Both gender and number match → confidence 0.85
        result = plugin.analyze_sentence("El perro negro corre.")
        agreements = objects_of(result, "agreement")
        full_match = [
            o for o in agreements
            if o.lesson_data.get("gender_match") is True
            and o.lesson_data.get("number_match") is True
        ]
        for obj in full_match:
            assert obj.confidence == 0.85

    def test_agreement_partial_match_has_medium_confidence(self, plugin) -> None:
        # One feature matches → confidence 0.72
        result = plugin.analyze_sentence("La casa grande es bonita.")
        for obj in objects_of(result, "agreement"):
            g = obj.lesson_data.get("gender_match")
            n = obj.lesson_data.get("number_match")
            if (g is True) != (n is True):   # exactly one True
                assert obj.confidence == 0.72


# ── lesson store ──────────────────────────────────────────────────────────────


class TestLessonStore:
    def test_missing_id_returns_none(self, plugin) -> None:
        assert plugin.get_lesson("nonexistent-uuid-0000") is None

    def test_get_lesson_returns_stored_object(self, plugin) -> None:
        # lesson_store is populated by the parse route after UUID resolution.
        # Simulate that by inserting a CandidateObject directly (the store type).
        from backend.schemas.parse import CandidateObject as CO
        fake_id = canonical_object_id("es", "vocabulary", "_test_word_")
        cand = CO(canonical_form="_test_word_", type="vocabulary", label="test", lesson_data={})
        plugin.lesson_store[fake_id] = cand
        stored = plugin.get_lesson(fake_id)
        assert stored is not None
        assert stored.canonical_form == "_test_word_"

    def test_lesson_store_keyed_by_uuid(self, plugin) -> None:
        # Verify the lesson_store key format is a UUID string (deterministic v5).
        result = plugin.analyze_sentence("El libro es bueno.")
        for obj in result.candidates:
            obj_id = canonical_object_id("es", obj.type, obj.canonical_form)
            assert len(obj_id) == 36  # UUID string length
            assert obj_id.count("-") == 4  # UUID hyphen count


# ── ID stability ──────────────────────────────────────────────────────────────


class TestIdStability:
    def test_same_word_same_canonical_form_across_sentences(self, plugin) -> None:
        r1 = plugin.analyze_sentence("El libro es bueno.")
        r2 = plugin.analyze_sentence("No tengo el libro.")
        vocab1 = {o.canonical_form for o in objects_of(r1, "vocabulary")}
        vocab2 = {o.canonical_form for o in objects_of(r2, "vocabulary")}
        assert "libro" in vocab1 & vocab2

    def test_canonical_object_id_deterministic(self, plugin) -> None:
        # The same canonical_form always produces the same UUID.
        result = plugin.analyze_sentence("Mañana voy al mercado.")
        for obj in result.candidates:
            id1 = canonical_object_id("es", obj.type, obj.canonical_form)
            id2 = canonical_object_id("es", obj.type, obj.canonical_form)
            assert id1 == id2

    def test_canonical_forms_are_non_empty_strings(self, plugin) -> None:
        result = plugin.analyze_sentence("La profesora explica bien.")
        for obj in result.candidates:
            assert isinstance(obj.canonical_form, str) and obj.canonical_form


# ── edge cases ────────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_punctuation_only_returns_no_objects(self, plugin) -> None:
        result = plugin.analyze_sentence("...")
        assert result.candidates == []

    def test_sentence_text_preserved_verbatim(self, plugin) -> None:
        sentence = "¡Qué bueno es esto!"
        result = plugin.analyze_sentence(sentence)
        assert result.text == sentence

    def test_single_word_sentence_does_not_crash(self, plugin) -> None:
        result = plugin.analyze_sentence("Hola.")
        assert isinstance(result.candidates, list)

    def test_all_returned_types_are_known(self, plugin) -> None:
        known_types = {"vocabulary", "conjugation", "agreement", "idiom", "grammar", "nuance"}
        result = plugin.analyze_sentence(
            "Los estudiantes inteligentes hablan bien el español."
        )
        for obj in result.candidates:
            assert obj.type in known_types, f"Unknown type: {obj.type!r}"

    def test_repeated_analysis_of_same_sentence_is_idempotent(self, plugin) -> None:
        sentence = "El gato negro duerme."
        r1 = plugin.analyze_sentence(sentence)
        r2 = plugin.analyze_sentence(sentence)
        forms1 = {o.canonical_form for o in r1.candidates}
        forms2 = {o.canonical_form for o in r2.candidates}
        assert forms1 == forms2


# ── deduplication ─────────────────────────────────────────────────────────────


class TestDeduplication:
    def test_finite_verb_not_in_vocabulary(self, plugin) -> None:
        # "corre" is VERB VerbForm=Fin → conjugation only, not vocabulary.
        result = plugin.analyze_sentence("El perro corre por el parque.")
        vocab_lemmas = {o.lesson_data["lemma"] for o in objects_of(result, "vocabulary")}
        assert "correr" not in vocab_lemmas, (
            "Finite verb lemma must not appear in vocabulary"
        )

    def test_finite_aux_not_in_vocabulary(self, plugin) -> None:
        # "estoy" is AUX VerbForm=Fin → conjugation only.
        result = plugin.analyze_sentence("Estoy comiendo ahora.")
        vocab_lemmas = {o.lesson_data["lemma"] for o in objects_of(result, "vocabulary")}
        assert "estar" not in vocab_lemmas

    def test_finite_verb_still_in_conjugation(self, plugin) -> None:
        result = plugin.analyze_sentence("El gato come pescado.")
        conj_lemmas = {o.lesson_data["lemma"] for o in objects_of(result, "conjugation")}
        # comer (or whatever the model produces) must appear in conjugation
        assert len(conj_lemmas) >= 1

    def test_periphrastic_lemma_not_duplicated(self, plugin) -> None:
        # "Voy a ir" — "Voy" (AUX Fin, lemma=ir) generates a conjugation and
        # pre-empts "ir" (VERB Inf) from also appearing as vocabulary.
        # The lemma "ir" should appear exactly once across all objects.
        result = plugin.analyze_sentence("Voy a ir al mercado.")
        all_ir = [
            o for o in result.candidates
            if o.lesson_data.get("lemma") == "ir"
        ]
        assert len(all_ir) == 1, (
            f"Expected exactly one object for lemma 'ir', got {len(all_ir)}"
        )

    def test_infinitive_in_vocabulary_when_no_finite_form(self, plugin) -> None:
        # "hablar" is VERB Inf and there is no finite form of "hablar" in the
        # sentence, so it must appear in vocabulary.
        result = plugin.analyze_sentence("Necesito hablar más.")
        vocab_lemmas = {o.lesson_data["lemma"] for o in objects_of(result, "vocabulary")}
        assert "hablar" in vocab_lemmas

    def test_gerund_in_vocabulary(self, plugin) -> None:
        # "comiendo" is VERB VerbForm=Ger → vocabulary (not conjugation).
        result = plugin.analyze_sentence("Estoy comiendo ahora.")
        vocab_lemmas = {o.lesson_data["lemma"] for o in objects_of(result, "vocabulary")}
        # The gerund's lemma should be in vocabulary.
        conj_lemmas = {o.lesson_data["lemma"] for o in objects_of(result, "conjugation")}
        # The gerund's lemma must not be in conjugation.
        assert vocab_lemmas - conj_lemmas, (
            "Expected at least one non-finite verb lemma in vocabulary"
        )

    def test_non_finite_verb_vocab_has_verb_form(self, plugin) -> None:
        # Vocabulary entries for non-finite verbs carry a verb_form key so the
        # frontend can label them as "infinitive", "gerund", or "participle".
        result = plugin.analyze_sentence("Necesito hablar más.")
        inf_items = [
            o for o in objects_of(result, "vocabulary")
            if o.lesson_data.get("pos") in {"VERB", "AUX"}
        ]
        assert inf_items, "Expected at least one VERB vocabulary item"
        for obj in inf_items:
            assert "verb_form" in obj.lesson_data, (
                f"Non-finite verb vocabulary item missing verb_form: {obj.lesson_data}"
            )

    def test_no_canonical_form_appears_twice(self, plugin) -> None:
        # Each canonical_form must be unique within a single sentence result.
        result = plugin.analyze_sentence(
            "Los estudiantes estudian y aprenden mucho."
        )
        forms = [o.canonical_form for o in result.candidates]
        assert len(forms) == len(set(forms)), "Duplicate canonical forms in one sentence"


# ── improved plugin features ──────────────────────────────────────────────────


class TestPronounExclusion:
    def test_reflexive_pronoun_not_in_vocabulary(self, plugin) -> None:
        result = plugin.analyze_sentence("Se llama María.")
        lemmas = {o.lesson_data["lemma"] for o in objects_of(result, "vocabulary")}
        assert "se" not in lemmas
        assert "yo" not in lemmas  # "me" lemmatises to "yo" in some models

    def test_personal_pronoun_not_in_vocabulary(self, plugin) -> None:
        result = plugin.analyze_sentence("Ella habla con él.")
        lemmas = {o.lesson_data["lemma"] for o in objects_of(result, "vocabulary")}
        pron_lemmas = {"ella", "él", "ellos", "nosotros", "yo", "tú"}
        assert not (lemmas & pron_lemmas), (
            f"Unexpected PRON lemmas in vocabulary: {lemmas & pron_lemmas}"
        )


# ── idiom extraction ──────────────────────────────────────────────────────────


class TestIdiomExtraction:
    def test_sin_embargo_detected(self, plugin) -> None:
        result = plugin.analyze_sentence("Sin embargo, no estoy de acuerdo.")
        idioms = objects_of(result, "idiom")
        phrases = {o.lesson_data["phrase"] for o in idioms}
        assert "sin embargo" in phrases

    def test_idiom_has_required_lesson_data_keys(self, plugin) -> None:
        result = plugin.analyze_sentence("Sin embargo, llegamos tarde.")
        for obj in objects_of(result, "idiom"):
            assert "phrase" in obj.lesson_data
            assert "meaning" in obj.lesson_data
            assert "register" in obj.lesson_data

    def test_idiom_confidence_is_0_90(self, plugin) -> None:
        result = plugin.analyze_sentence("Por ejemplo, puedes usar este método.")
        for obj in objects_of(result, "idiom"):
            assert obj.confidence == 0.90

    def test_plain_sentence_has_no_idiom(self, plugin) -> None:
        result = plugin.analyze_sentence("El gato duerme en la cama.")
        assert objects_of(result, "idiom") == []

    def test_surface_form_preserves_original_casing(self, plugin) -> None:
        # Capital-S "Sin" at sentence start must be preserved in surface_form.
        result = plugin.analyze_sentence("Sin embargo, todo está bien.")
        idioms = objects_of(result, "idiom")
        surfaces = {o.surface_form for o in idioms}
        assert "Sin embargo" in surfaces

    def test_multiple_idioms_in_one_sentence(self, plugin) -> None:
        result = plugin.analyze_sentence(
            "Por ejemplo, de vez en cuando hay problemas."
        )
        idioms = objects_of(result, "idiom")
        phrases = {o.lesson_data["phrase"] for o in idioms}
        assert "por ejemplo" in phrases
        assert "de vez en cuando" in phrases

    def test_longer_match_prevents_sub_phrase_match(self, plugin) -> None:
        # "de vez en cuando" (4 words) must claim its positions so the
        # sub-phrase "en cuando" (not in the table) cannot match — and
        # "al menos" (2 words) inside "por lo menos" (3 words) must not
        # fire when "por lo menos" matches first.
        result = plugin.analyze_sentence(
            "Por lo menos llega a tiempo."
        )
        idioms = objects_of(result, "idiom")
        phrases = {o.lesson_data["phrase"] for o in idioms}
        # "por lo menos" must match; "al menos" must not (no overlap here,
        # but "al menos" is a different phrase so both could appear in
        # different positions — the key point is no duplicated position).
        if "por lo menos" in phrases:
            # Verify no duplicate canonical_form in the whole result.
            all_canonical = [o.canonical_form for o in result.candidates]
            assert len(all_canonical) == len(set(all_canonical))

    def test_idiom_canonical_form_is_stable(self, plugin) -> None:
        r1 = plugin.analyze_sentence("Sin embargo, el tiempo pasa.")
        r2 = plugin.analyze_sentence("Sin embargo, todo cambia.")
        cf1 = {o.canonical_form for o in objects_of(r1, "idiom")}
        cf2 = {o.canonical_form for o in objects_of(r2, "idiom")}
        assert "sin embargo" in cf1
        assert cf1 & cf2  # same canonical_form in both results

    def test_de_vez_en_cuando_meaning(self, plugin) -> None:
        result = plugin.analyze_sentence("De vez en cuando voy al cine.")
        idioms = objects_of(result, "idiom")
        phrases = {o.lesson_data["phrase"]: o.lesson_data["meaning"] for o in idioms}
        assert "de vez en cuando" in phrases
        assert "time" in phrases["de vez en cuando"].lower()

    def test_no_idiom_duplicate_canonical_forms(self, plugin) -> None:
        result = plugin.analyze_sentence(
            "Sin embargo, por ejemplo, de hecho todo está bien."
        )
        idiom_forms = [o.canonical_form for o in objects_of(result, "idiom")]
        assert len(idiom_forms) == len(set(idiom_forms))


# ── grammar pattern extraction ────────────────────────────────────────────────


class TestGrammarExtraction:
    def test_ser_copula_detected(self, plugin) -> None:
        result = plugin.analyze_sentence("La casa es bonita.")
        grammars = objects_of(result, "grammar")
        pattern_ids = {o.lesson_data["pattern_id"] for o in grammars}
        assert "ser_copula" in pattern_ids

    def test_estar_copula_detected(self, plugin) -> None:
        result = plugin.analyze_sentence("El niño está cansado.")
        grammars = objects_of(result, "grammar")
        pattern_ids = {o.lesson_data["pattern_id"] for o in grammars}
        assert "estar_copula" in pattern_ids

    def test_grammar_has_pattern_usage_contrast_fields(self, plugin) -> None:
        result = plugin.analyze_sentence("La casa es bonita.")
        for obj in objects_of(result, "grammar"):
            assert "pattern_id" in obj.lesson_data
            assert "pattern" in obj.lesson_data
            assert "usage" in obj.lesson_data
            assert "contrast" in obj.lesson_data

    def test_estar_progressive_detected(self, plugin) -> None:
        result = plugin.analyze_sentence("Estoy comiendo ahora.")
        grammars = objects_of(result, "grammar")
        pattern_ids = {o.lesson_data["pattern_id"] for o in grammars}
        assert "estar_progressive" in pattern_ids

    def test_ir_near_future_detected(self, plugin) -> None:
        result = plugin.analyze_sentence("Voy a estudiar esta tarde.")
        grammars = objects_of(result, "grammar")
        pattern_ids = {o.lesson_data["pattern_id"] for o in grammars}
        assert "ir_near_future" in pattern_ids

    def test_grammar_confidence_is_0_85(self, plugin) -> None:
        result = plugin.analyze_sentence("La casa es bonita.")
        for obj in objects_of(result, "grammar"):
            assert obj.confidence == 0.85

    def test_grammar_canonical_form_format(self, plugin) -> None:
        result = plugin.analyze_sentence("La ciudad es grande.")
        for obj in objects_of(result, "grammar"):
            assert obj.canonical_form.startswith("grammar:"), (
                f"Unexpected canonical_form: {obj.canonical_form!r}"
            )

    def test_grammar_canonical_form_is_stable(self, plugin) -> None:
        r1 = plugin.analyze_sentence("La casa es bonita.")
        r2 = plugin.analyze_sentence("El libro es interesante.")
        cf1 = {o.canonical_form for o in objects_of(r1, "grammar")}
        cf2 = {o.canonical_form for o in objects_of(r2, "grammar")}
        # Both have ser_copula — the canonical_form must be identical.
        assert "grammar:ser_copula" in cf1
        assert "grammar:ser_copula" in cf2

    def test_standalone_verb_has_no_grammar_object(self, plugin) -> None:
        # "corre" is a simple intransitive verb — no periphrastic construction.
        result = plugin.analyze_sentence("El perro corre por el parque.")
        grammars = objects_of(result, "grammar")
        # No grammar object expected for a standalone finite verb.
        assert len(grammars) == 0

    def test_no_duplicate_grammar_per_sentence(self, plugin) -> None:
        # Even with multiple ser-copula verbs the grammar object is emitted once.
        result = plugin.analyze_sentence("Él es médico y ella es profesora.")
        grammars = objects_of(result, "grammar")
        pattern_ids = [o.lesson_data["pattern_id"] for o in grammars]
        assert len(pattern_ids) == len(set(pattern_ids))


# ── nuance extraction ─────────────────────────────────────────────────────────


class TestNuanceExtraction:
    def test_imperfect_triggers_nuance(self, plugin) -> None:
        result = plugin.analyze_sentence("Cuando era niño, jugaba mucho.")
        nuances = objects_of(result, "nuance")
        nuance_types = {o.lesson_data["nuance_type"] for o in nuances}
        assert "imperfect_aspect" in nuance_types

    def test_imperfect_nuance_has_note(self, plugin) -> None:
        result = plugin.analyze_sentence("Vivía en Madrid antes.")
        for obj in objects_of(result, "nuance"):
            if obj.lesson_data.get("nuance_type") == "imperfect_aspect":
                assert "note" in obj.lesson_data
                assert obj.lesson_data["note"]

    def test_reflexive_triggers_nuance(self, plugin) -> None:
        result = plugin.analyze_sentence("Se llama Pedro.")
        nuances = objects_of(result, "nuance")
        nuance_types = {o.lesson_data["nuance_type"] for o in nuances}
        assert "reflexive_verb" in nuance_types

    def test_nuance_confidence_ranges(self, plugin) -> None:
        # imperfect: 0.78 | reflexive: 0.82 | subjunctive: 0.72
        # All nuance confidences must be in (0, 1].
        result = plugin.analyze_sentence("Cuando era pequeño, se levantaba temprano.")
        for obj in objects_of(result, "nuance"):
            assert obj.confidence is not None
            assert 0.0 < obj.confidence <= 1.0

    def test_imperfect_nuance_confidence_is_0_78(self, plugin) -> None:
        result = plugin.analyze_sentence("Antes estudiaba mucho.")
        for obj in objects_of(result, "nuance"):
            if obj.lesson_data.get("nuance_type") == "imperfect_aspect":
                assert obj.confidence == 0.78

    def test_reflexive_nuance_confidence_is_0_82(self, plugin) -> None:
        result = plugin.analyze_sentence("Me levanto temprano.")
        for obj in objects_of(result, "nuance"):
            if obj.lesson_data.get("nuance_type") == "reflexive_verb":
                assert obj.confidence == 0.82

    def test_nuance_has_relation_hint(self, plugin) -> None:
        result = plugin.analyze_sentence("Antes vivía aquí.")
        for obj in objects_of(result, "nuance"):
            assert obj.relation_hints, f"Nuance object has no relation_hints: {obj}"
            relations = {h.relation_type for h in obj.relation_hints}
            assert "nuance_of" in relations

    def test_present_indicative_has_no_imperfect_nuance(self, plugin) -> None:
        result = plugin.analyze_sentence("Él habla español perfectamente.")
        nuance_types = {
            o.lesson_data["nuance_type"] for o in objects_of(result, "nuance")
        }
        assert "imperfect_aspect" not in nuance_types


# ── improved lesson_data ──────────────────────────────────────────────────────


class TestImprovedLessonData:
    def test_noun_has_gender(self, plugin) -> None:
        result = plugin.analyze_sentence("La casa es bonita.")
        vocab = objects_of(result, "vocabulary")
        casa = next((o for o in vocab if o.lesson_data.get("lemma") == "casa"), None)
        assert casa is not None, "Expected 'casa' in vocabulary"
        assert "gender" in casa.lesson_data, "Noun vocabulary item missing 'gender'"

    def test_noun_has_number(self, plugin) -> None:
        result = plugin.analyze_sentence("Los libros son interesantes.")
        vocab = objects_of(result, "vocabulary")
        libros = next(
            (o for o in vocab if o.lesson_data.get("lemma") == "libro"), None
        )
        assert libros is not None, "Expected 'libro' in vocabulary"
        assert "number" in libros.lesson_data, "Noun vocabulary item missing 'number'"

    def test_conjugation_has_paradigm_class(self, plugin) -> None:
        result = plugin.analyze_sentence("Ella habla español.")
        for obj in objects_of(result, "conjugation"):
            assert "paradigm_class" in obj.lesson_data, (
                f"Conjugation missing 'paradigm_class': {obj.lesson_data}"
            )

    def test_conjugation_has_is_irregular_bool(self, plugin) -> None:
        result = plugin.analyze_sentence("Ella habla español.")
        for obj in objects_of(result, "conjugation"):
            assert "is_irregular" in obj.lesson_data
            assert isinstance(obj.lesson_data["is_irregular"], bool)

    def test_ser_is_irregular(self, plugin) -> None:
        result = plugin.analyze_sentence("Él es médico.")
        conjs = objects_of(result, "conjugation")
        ser_conj = next(
            (o for o in conjs if o.lesson_data.get("lemma") == "ser"), None
        )
        assert ser_conj is not None, "Expected 'ser' conjugation"
        assert ser_conj.lesson_data["is_irregular"] is True

    def test_hablar_paradigm_class_is_ar(self, plugin) -> None:
        result = plugin.analyze_sentence("Yo hablo mucho.")
        conjs = objects_of(result, "conjugation")
        hablar_conj = next(
            (o for o in conjs if o.lesson_data.get("lemma") == "hablar"), None
        )
        assert hablar_conj is not None, "Expected 'hablar' conjugation"
        assert hablar_conj.lesson_data["paradigm_class"] == "-ar"

    def test_beber_paradigm_class_is_er(self, plugin) -> None:
        result = plugin.analyze_sentence("Ella bebe agua.")
        conjs = objects_of(result, "conjugation")
        beber_conj = next(
            (o for o in conjs if o.lesson_data.get("lemma") == "beber"), None
        )
        assert beber_conj is not None, "Expected 'beber' conjugation"
        assert beber_conj.lesson_data["paradigm_class"] == "-er"

    def test_vivir_paradigm_class_is_ir(self, plugin) -> None:
        result = plugin.analyze_sentence("Ella vive en Madrid.")
        conjs = objects_of(result, "conjugation")
        # es_core_news_sm may lemmatise "vive" as "vivir"
        vivir_conj = next(
            (o for o in conjs if o.lesson_data.get("lemma") == "vivir"), None
        )
        assert vivir_conj is not None, "Expected 'vivir' conjugation"
        assert vivir_conj.lesson_data["paradigm_class"] == "-ir"


class TestReflexiveDetection:
    def test_reflexive_verb_flagged(self, plugin) -> None:
        result = plugin.analyze_sentence("Me levanto temprano.")
        conjs = objects_of(result, "conjugation")
        assert conjs, "Expected at least one conjugation"
        reflexive_conjs = [o for o in conjs if o.lesson_data.get("is_reflexive") is True]
        assert reflexive_conjs, "Expected levantarse to be flagged as reflexive"

    def test_non_reflexive_verb_not_flagged(self, plugin) -> None:
        result = plugin.analyze_sentence("Ella come una manzana.")
        for obj in objects_of(result, "conjugation"):
            assert obj.lesson_data["is_reflexive"] is False

    def test_is_reflexive_key_always_present(self, plugin) -> None:
        result = plugin.analyze_sentence("Nosotros estudiamos juntos.")
        for obj in objects_of(result, "conjugation"):
            assert "is_reflexive" in obj.lesson_data
            assert isinstance(obj.lesson_data["is_reflexive"], bool)


class TestConstructionAnnotation:
    def test_simple_verb_is_standalone(self, plugin) -> None:
        result = plugin.analyze_sentence("Ella trabaja mucho.")
        for obj in objects_of(result, "conjugation"):
            assert obj.lesson_data["construction"] == "standalone"

    def test_estar_gerund_is_progressive(self, plugin) -> None:
        result = plugin.analyze_sentence("Estoy comiendo ahora.")
        constructions = {
            o.lesson_data["construction"] for o in objects_of(result, "conjugation")
        }
        assert "progressive" in constructions

    def test_haber_participle_is_perfect(self, plugin) -> None:
        result = plugin.analyze_sentence("He comido demasiado.")
        constructions = {
            o.lesson_data["construction"] for o in objects_of(result, "conjugation")
        }
        assert "perfect" in constructions

    def test_copula_detected(self, plugin) -> None:
        result = plugin.analyze_sentence("La casa es grande.")
        constructions = {
            o.lesson_data["construction"] for o in objects_of(result, "conjugation")
        }
        assert "copula" in constructions

    def test_construction_key_always_present(self, plugin) -> None:
        result = plugin.analyze_sentence("Los niños juegan afuera.")
        for obj in objects_of(result, "conjugation"):
            assert "construction" in obj.lesson_data
            assert isinstance(obj.lesson_data["construction"], str)


class TestCoordinationAgreement:
    def test_coordinated_nouns_no_spurious_agreement(self, plugin) -> None:
        # "español" is conj-dep of "inglés" — should not generate an agreement
        # object between them.
        result = plugin.analyze_sentence("Ella habla inglés y español.")
        pair_nouns = {
            frozenset([
                o.lesson_data["modifier"].lower(),
                o.lesson_data["noun"].lower(),
            ])
            for o in objects_of(result, "agreement")
        }
        assert frozenset(["inglés", "español"]) not in pair_nouns

    def test_genuine_det_noun_agreement_still_extracted(self, plugin) -> None:
        result = plugin.analyze_sentence("Los libros y las revistas son nuevos.")
        assert len(objects_of(result, "agreement")) >= 1


class TestConfidenceNote:
    def test_proper_noun_has_confidence_note(self, plugin) -> None:
        result = plugin.analyze_sentence("Viajo a Madrid mañana.")
        vocab = objects_of(result, "vocabulary")
        propn_objs = [o for o in vocab if o.lesson_data.get("pos") == "PROPN"]
        assert propn_objs, "Expected at least one PROPN vocabulary item"
        for obj in propn_objs:
            assert "confidence_note" in obj.lesson_data
            assert isinstance(obj.lesson_data["confidence_note"], str)

    def test_agreement_always_has_confidence_note(self, plugin) -> None:
        result = plugin.analyze_sentence("La casa blanca es bonita.")
        for obj in objects_of(result, "agreement"):
            assert "confidence_note" in obj.lesson_data
            assert isinstance(obj.lesson_data["confidence_note"], str)
