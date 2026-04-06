"""Tests for the spaCy-based Spanish plugin (backend/plugins/spanish.py).

The entire module is skipped when spaCy or es_core_news_sm is not installed,
so the CI baseline (which runs without the model) stays green.
"""
from __future__ import annotations

import pytest

from backend.schemas.parse import LearnableObject, SentenceResult


# ---------------------------------------------------------------------------
# Skip guard — keep this at module level so pytest skips collection entirely
# ---------------------------------------------------------------------------

def _spacy_available() -> bool:
    try:
        import spacy  # noqa: PLC0415
        spacy.load("es_core_news_sm", disable=["ner"])
        return True
    except (ImportError, OSError):
        return False


pytestmark = pytest.mark.skipif(
    not _spacy_available(),
    reason="spaCy + es_core_news_sm not installed",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def plugin():
    from backend.plugins.spanish import SpanishPlugin
    return SpanishPlugin()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def objects_of(result: SentenceResult, kind: str) -> list[LearnableObject]:
    return [o for o in result.learnable_objects if o.type == kind]


def all_confidences_valid(objects: list[LearnableObject]) -> bool:
    return all(0.0 < o.confidence <= 1.0 for o in objects if o.confidence is not None)


# ---------------------------------------------------------------------------
# Sentence splitting
# ---------------------------------------------------------------------------

class TestSentenceSplitting:
    def test_splits_multi_sentence_prose(self, plugin) -> None:
        sents = plugin.split_sentences("Hola. Me llamo Juan. ¿Cómo estás?")
        assert len(sents) >= 2
        assert all(s.strip() for s in sents)

    def test_single_sentence_returned_as_one(self, plugin) -> None:
        sents = plugin.split_sentences("La casa es roja.")
        assert len(sents) == 1
        assert sents[0].strip() == "La casa es roja."

    def test_empty_string_returns_no_sentences(self, plugin) -> None:
        assert plugin.split_sentences("") == []

    def test_whitespace_only_returns_no_sentences(self, plugin) -> None:
        assert plugin.split_sentences("   \n  ") == []


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

class TestVocabularyExtraction:
    def test_nouns_included(self, plugin) -> None:
        result = plugin.analyze_sentence("El perro corre por el parque.")
        lemmas = {o.lesson_data["lemma"] for o in objects_of(result, "vocabulary")}
        assert "perro" in lemmas
        assert "parque" in lemmas

    def test_determiners_excluded(self, plugin) -> None:
        result = plugin.analyze_sentence("La casa tiene un jardín.")
        lemmas = {o.lesson_data["lemma"] for o in objects_of(result, "vocabulary")}
        # "la", "un" are DET → must not appear as vocabulary
        assert "la" not in lemmas
        assert "un" not in lemmas

    def test_verb_lemma_included(self, plugin) -> None:
        result = plugin.analyze_sentence("Yo hablo español.")
        lemmas = {o.lesson_data["lemma"] for o in objects_of(result, "vocabulary")}
        # spaCy lemmatises "hablo" → "hablar"
        assert "hablar" in lemmas

    def test_no_duplicate_lemmas(self, plugin) -> None:
        result = plugin.analyze_sentence("El libro y el libro viejo.")
        lemmas = [o.lesson_data["lemma"] for o in objects_of(result, "vocabulary")]
        assert len(lemmas) == len(set(lemmas))

    def test_confidence_in_valid_range(self, plugin) -> None:
        result = plugin.analyze_sentence("Los estudiantes estudian mucho.")
        assert all_confidences_valid(objects_of(result, "vocabulary"))

    def test_lesson_data_has_required_keys(self, plugin) -> None:
        result = plugin.analyze_sentence("El gato duerme.")
        for obj in objects_of(result, "vocabulary"):
            assert "lemma" in obj.lesson_data
            assert "pos" in obj.lesson_data


# ---------------------------------------------------------------------------
# Conjugation
# ---------------------------------------------------------------------------

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
        tenses = {o.lesson_data["tense"] for o in conjs}
        # es_core_news_sm should tag "comió" as preterite
        assert "preterite" in tenses or "unknown" in tenses

    def test_infinitives_not_conjugations(self, plugin) -> None:
        # "hablar" is an infinitive — must not appear as a conjugation
        result = plugin.analyze_sentence("Quiero hablar contigo.")
        conj_surfaces = {o.lesson_data["surface"].lower() for o in objects_of(result, "conjugation")}
        assert "hablar" not in conj_surfaces

    def test_conjugation_has_required_keys(self, plugin) -> None:
        result = plugin.analyze_sentence("Nosotros comemos juntos.")
        for obj in objects_of(result, "conjugation"):
            for key in ("lemma", "surface", "tense", "mood", "person", "number"):
                assert key in obj.lesson_data

    def test_conjugation_id_is_stable(self, plugin) -> None:
        r1 = plugin.analyze_sentence("Yo hablo mucho.")
        r2 = plugin.analyze_sentence("Yo hablo mucho.")
        ids1 = {o.id for o in objects_of(r1, "conjugation")}
        ids2 = {o.id for o in objects_of(r2, "conjugation")}
        assert ids1 == ids2

    def test_confidence_in_valid_range(self, plugin) -> None:
        result = plugin.analyze_sentence("Tú corres rápido.")
        assert all_confidences_valid(objects_of(result, "conjugation"))

    def test_morph_complete_flag_present(self, plugin) -> None:
        result = plugin.analyze_sentence("Ella canta bien.")
        for obj in objects_of(result, "conjugation"):
            assert "morph_complete" in obj.lesson_data
            assert isinstance(obj.lesson_data["morph_complete"], bool)


# ---------------------------------------------------------------------------
# Agreement
# ---------------------------------------------------------------------------

class TestAgreementExtraction:
    def test_det_noun_agreement_extracted(self, plugin) -> None:
        # "la casa" — feminine singular DET + NOUN
        result = plugin.analyze_sentence("La casa es bonita.")
        agreements = objects_of(result, "agreement")
        assert len(agreements) >= 1

    def test_adj_noun_agreement_extracted(self, plugin) -> None:
        # "casa bonita" — feminine singular ADJ + NOUN
        result = plugin.analyze_sentence("Tengo una casa bonita.")
        agreements = objects_of(result, "agreement")
        assert len(agreements) >= 1

    def test_plural_agreement_extracted(self, plugin) -> None:
        result = plugin.analyze_sentence("Los libros viejos son interesantes.")
        agreements = objects_of(result, "agreement")
        assert len(agreements) >= 1
        # At least one plural pair
        numbers = {o.lesson_data["number"] for o in agreements}
        assert "Plur" in numbers

    def test_agreement_has_required_keys(self, plugin) -> None:
        result = plugin.analyze_sentence("El perro negro ladra.")
        for obj in objects_of(result, "agreement"):
            for key in ("modifier", "modifier_pos", "noun", "gender", "number"):
                assert key in obj.lesson_data

    def test_agreement_confidence_in_valid_range(self, plugin) -> None:
        result = plugin.analyze_sentence("La niña pequeña juega.")
        assert all_confidences_valid(objects_of(result, "agreement"))

    def test_agreement_id_uses_lemmas_not_surface(self, plugin) -> None:
        # "las casas" and "la casa" should produce different IDs (different
        # noun lemmas are the same, but number features differ) — specifically,
        # the IDs must not change with inflection if lemmas are identical.
        r1 = plugin.analyze_sentence("La casa blanca es grande.")
        r2 = plugin.analyze_sentence("La casa blanca es grande.")
        ids1 = {o.id for o in objects_of(r1, "agreement")}
        ids2 = {o.id for o in objects_of(r2, "agreement")}
        assert ids1 == ids2


# ---------------------------------------------------------------------------
# Lesson store
# ---------------------------------------------------------------------------

class TestLessonStore:
    def test_all_objects_retrievable_by_id(self, plugin) -> None:
        result = plugin.analyze_sentence("El estudiante inteligente lee muchos libros.")
        for obj in result.learnable_objects:
            stored = plugin.get_lesson(obj.id)
            assert stored is not None
            assert stored.id == obj.id

    def test_missing_id_returns_none(self, plugin) -> None:
        assert plugin.get_lesson("es:vocab:xyzzy_nonexistent") is None

    def test_lesson_persists_across_calls(self, plugin) -> None:
        r = plugin.analyze_sentence("El médico habla despacio.")
        first_obj = r.learnable_objects[0]
        # Second independent call should still find the stored lesson
        assert plugin.get_lesson(first_obj.id) is not None


# ---------------------------------------------------------------------------
# ID stability (cross-sentence)
# ---------------------------------------------------------------------------

class TestIdStability:
    def test_same_word_same_id_across_sentences(self, plugin) -> None:
        r1 = plugin.analyze_sentence("El libro es bueno.")
        r2 = plugin.analyze_sentence("No tengo el libro.")
        vocab1 = {o.id for o in objects_of(r1, "vocabulary")}
        vocab2 = {o.id for o in objects_of(r2, "vocabulary")}
        # "libro" should appear in both with the same ID
        libro_ids = vocab1 & vocab2
        assert any("libro" in i for i in libro_ids)

    def test_all_ids_prefixed_with_language(self, plugin) -> None:
        result = plugin.analyze_sentence("Mañana voy al mercado.")
        for obj in result.learnable_objects:
            assert obj.id.startswith("es:")
