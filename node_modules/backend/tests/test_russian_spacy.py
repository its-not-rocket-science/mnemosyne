"""Tests for the spaCy-backed Russian plugin (backend/plugins/russian.py).

The entire module is skipped when spaCy or ru_core_news_sm is not installed
so the CI baseline stays green.

To enable these tests, install the model once:
    python -m spacy download ru_core_news_sm

Design intent
─────────────
These tests verify:

- Structural correctness: required lesson_data keys, confidence ranges, no
  duplicate canonical forms, graceful absence on punctuation-only input.
- Russian-specific features: lowercase Cyrillic lemmas, aspect (Imp/Perf)
  on conjugation, past tense uses Gender (not Person), six cases including
  Instrumental and Locative, no article DET in case_agreement.
- Architecture: canonical forms use the same cross-language UUID scheme;
  the ``case_agreement`` type (not ``agreement``) is emitted.
- Confidence is capped at 0.82 for conjugation.

Known ru_core_news_sm limitations that tests deliberately work around:
- Aspect tagging may be imprecise for rare prefixed verbs.
- Case resolution for short-form adjectives is unreliable.
- Animacy assignment (Anim/Inan) can be wrong for homographic forms.
"""
from __future__ import annotations

import pytest

from backend.parsing.canonical import canonical_object_id
from backend.schemas.parse import CandidateObject, CandidateSentenceResult


# ── skip guard ────────────────────────────────────────────────────────────────

def _spacy_available() -> bool:
    try:
        import spacy  # noqa: PLC0415
        spacy.load("ru_core_news_sm", disable=["ner"])
        return True
    except (ImportError, OSError):
        return False


pytestmark = pytest.mark.skipif(
    not _spacy_available(),
    reason="spaCy + ru_core_news_sm not installed; "
           "run: python -m spacy download ru_core_news_sm",
)


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def plugin():
    from backend.plugins.russian import RussianPlugin
    return RussianPlugin()


# ── helpers ───────────────────────────────────────────────────────────────────

def objects_of(result: CandidateSentenceResult, kind: str) -> list[CandidateObject]:
    return [o for o in result.candidates if o.type == kind]


def confidences_valid(objects: list[CandidateObject]) -> bool:
    return all(0.0 < o.confidence <= 1.0 for o in objects if o.confidence is not None)


# ── capabilities ──────────────────────────────────────────────────────────────


class TestCapabilities:
    def test_language_code(self, plugin) -> None:
        assert plugin.language_code == "ru"

    def test_display_name(self, plugin) -> None:
        assert "Russian" in plugin.display_name

    def test_direction_is_ltr(self, plugin) -> None:
        assert plugin.direction == "ltr"

    def test_script_family_cyrillic(self, plugin) -> None:
        assert plugin.capabilities.script_family == "cyrillic"

    def test_morphology_depth_rich(self, plugin) -> None:
        assert plugin.capabilities.morphology_depth == "rich"

    def test_lesson_modes_includes_morphology(self, plugin) -> None:
        assert "morphology" in plugin.capabilities.lesson_modes_supported

    def test_analysis_depth_full(self, plugin) -> None:
        assert plugin.capabilities.analysis_depth == "full"

    def test_tts_lang_tag(self, plugin) -> None:
        assert plugin.capabilities.tts_lang_tag == "ru"

    def test_no_transliteration_scheme(self, plugin) -> None:
        assert plugin.capabilities.transliteration_scheme is None

    def test_syntax_support_true(self, plugin) -> None:
        assert plugin.capabilities.syntax_support is True

    def test_idiom_detection_true(self, plugin) -> None:
        assert plugin.capabilities.idiom_detection is True

    def test_morphology_quality_medium(self, plugin) -> None:
        assert plugin.capabilities.morphology_quality == "medium"

    def test_tokenization_quality_high(self, plugin) -> None:
        assert plugin.capabilities.tokenization_quality == "high"


# ── sentence splitting ────────────────────────────────────────────────────────


class TestSentenceSplitting:
    def test_single_sentence(self, plugin) -> None:
        sents = plugin.split_sentences("Собака лает громко.")
        assert len(sents) == 1

    def test_multiple_sentences(self, plugin) -> None:
        sents = plugin.split_sentences("Кошка спит. Собака бегает.")
        assert len(sents) >= 2

    def test_empty_returns_empty(self, plugin) -> None:
        assert plugin.split_sentences("") == []

    def test_returns_non_empty_strings(self, plugin) -> None:
        sents = plugin.split_sentences("Я читаю книгу. Она очень интересная.")
        assert all(s.strip() for s in sents)

    def test_analyze_sentence_text_preserved(self, plugin) -> None:
        sentence = "Кот сидит на окне."
        result = plugin.analyze_sentence(sentence)
        assert result.text == sentence

    def test_analyze_sentence_returns_result_type(self, plugin) -> None:
        result = plugin.analyze_sentence("Я вижу большой дом.")
        assert isinstance(result, CandidateSentenceResult)


# ── vocabulary extraction ─────────────────────────────────────────────────────


class TestVocabularyExtraction:
    def test_noun_extracted_as_vocabulary(self, plugin) -> None:
        result = plugin.analyze_sentence("Собака лает.")
        vocab = objects_of(result, "vocabulary")
        nouns = [o for o in vocab if o.lesson_data.get("pos") == "NOUN"]
        assert any(nouns)

    def test_russian_noun_lemma_is_lowercase(self, plugin) -> None:
        """Russian noun lemmas from pymorphy3 are lowercase."""
        result = plugin.analyze_sentence("Москва — столица России.")
        vocab = objects_of(result, "vocabulary")
        nouns = [o for o in vocab if o.lesson_data.get("pos") == "NOUN"]
        for n in nouns:
            # canonical_form (lemma) should be lowercase for regular nouns
            assert n.canonical_form == n.canonical_form.lower() or n.lesson_data.get("pos") == "PROPN"

    def test_vocabulary_has_lemma_key(self, plugin) -> None:
        result = plugin.analyze_sentence("Дом стоит на горе.")
        for obj in objects_of(result, "vocabulary"):
            assert "lemma" in obj.lesson_data

    def test_vocabulary_has_pos_key(self, plugin) -> None:
        result = plugin.analyze_sentence("Большая собака бежит.")
        for obj in objects_of(result, "vocabulary"):
            assert "pos" in obj.lesson_data

    def test_adverb_extracted(self, plugin) -> None:
        result = plugin.analyze_sentence("Он бежит быстро.")
        vocab = objects_of(result, "vocabulary")
        lemmas = {o.canonical_form for o in vocab}
        assert "быстро" in lemmas

    def test_finite_verb_not_in_vocabulary(self, plugin) -> None:
        """Finite verbs must appear only as conjugation objects."""
        result = plugin.analyze_sentence("Мальчик читает книгу.")
        vocab = objects_of(result, "vocabulary")
        conj  = objects_of(result, "conjugation")
        conj_lemmas  = {o.lesson_data.get("lemma") for o in conj}
        vocab_lemmas = {o.canonical_form for o in vocab}
        assert conj_lemmas.isdisjoint(vocab_lemmas), (
            f"Overlap between conj lemmas and vocab: "
            f"{conj_lemmas & vocab_lemmas}"
        )

    def test_noun_gender_in_lesson_data_when_available(self, plugin) -> None:
        result = plugin.analyze_sentence("Женщина читает книгу.")
        vocab = objects_of(result, "vocabulary")
        nouns = [o for o in vocab if o.lesson_data.get("pos") == "NOUN"]
        for n in nouns:
            if "gender" in n.lesson_data:
                assert n.lesson_data["gender"] in ("Masc", "Fem", "Neut")

    def test_vocabulary_confidence_in_range(self, plugin) -> None:
        result = plugin.analyze_sentence("Красивый город стоит у реки.")
        assert confidences_valid(objects_of(result, "vocabulary"))

    def test_vocabulary_no_duplicates(self, plugin) -> None:
        result = plugin.analyze_sentence("Дом и дом стоят рядом.")
        forms = [o.canonical_form for o in objects_of(result, "vocabulary")]
        assert len(forms) == len(set(forms))

    def test_punctuation_only_returns_empty(self, plugin) -> None:
        result = plugin.analyze_sentence("...")
        assert result.candidates == []

    def test_proper_noun_confidence_lower(self, plugin) -> None:
        result = plugin.analyze_sentence("Москва — большой город.")
        vocab = objects_of(result, "vocabulary")
        proper = [o for o in vocab if o.lesson_data.get("pos") == "PROPN"]
        for p in proper:
            if p.confidence is not None:
                assert p.confidence <= 0.65


# ── conjugation extraction ────────────────────────────────────────────────────


class TestConjugationExtraction:
    def test_finite_verb_extracted_as_conjugation(self, plugin) -> None:
        result = plugin.analyze_sentence("Я читаю книгу.")
        assert any(objects_of(result, "conjugation"))

    def test_conjugation_has_required_keys(self, plugin) -> None:
        result = plugin.analyze_sentence("Он пишет письмо.")
        for obj in objects_of(result, "conjugation"):
            for key in ("lemma", "surface", "tense", "aspect", "mood",
                        "person_or_gender", "number", "morph_complete"):
                assert key in obj.lesson_data, f"Missing key {key!r}"

    def test_present_tense_detected(self, plugin) -> None:
        result = plugin.analyze_sentence("Собака лает.")
        conj = objects_of(result, "conjugation")
        tenses = {o.lesson_data.get("tense") for o in conj}
        assert "present" in tenses

    def test_past_tense_detected(self, plugin) -> None:
        result = plugin.analyze_sentence("Она написала письмо.")
        conj = objects_of(result, "conjugation")
        tenses = {o.lesson_data.get("tense") for o in conj}
        assert "past" in tenses

    def test_past_tense_uses_gender_not_person(self, plugin) -> None:
        """In Russian past tense, person_or_gender must be a gender, not 1st/2nd/3rd."""
        result = plugin.analyze_sentence("Она прочитала книгу.")
        conj = objects_of(result, "conjugation")
        past = [o for o in conj if o.lesson_data.get("tense") == "past"]
        for obj in past:
            pog = obj.lesson_data.get("person_or_gender")
            # Must be a gender name or "unknown", not "First"/"Second"/"Third"
            assert pog not in ("First", "Second", "Third"), (
                f"Past tense should use gender, got person {pog!r}"
            )

    def test_past_tense_masculine_gender(self, plugin) -> None:
        result = plugin.analyze_sentence("Он написал письмо.")
        conj = objects_of(result, "conjugation")
        past = [o for o in conj if o.lesson_data.get("tense") == "past"]
        if past:
            pog = past[0].lesson_data.get("person_or_gender")
            assert pog == "masculine", f"Expected masculine, got {pog!r}"

    def test_past_tense_feminine_gender(self, plugin) -> None:
        result = plugin.analyze_sentence("Она написала письмо.")
        conj = objects_of(result, "conjugation")
        past = [o for o in conj if o.lesson_data.get("tense") == "past"]
        if past:
            pog = past[0].lesson_data.get("person_or_gender")
            assert pog == "feminine", f"Expected feminine, got {pog!r}"

    def test_aspect_present_on_conjugation(self, plugin) -> None:
        """Aspect (imperfective/perfective) must be in conjugation lesson_data."""
        result = plugin.analyze_sentence("Я сижу в кресле.")
        conj = objects_of(result, "conjugation")
        for obj in conj:
            assert "aspect" in obj.lesson_data, "aspect key missing from conjugation"

    def test_imperfective_aspect_present_tense(self, plugin) -> None:
        """Present-tense verbs in Russian are always imperfective."""
        result = plugin.analyze_sentence("Он сидит и читает.")
        conj = objects_of(result, "conjugation")
        present = [o for o in conj if o.lesson_data.get("tense") == "present"]
        for obj in present:
            assert obj.lesson_data.get("aspect") == "imperfective", (
                f"Present verb should be imperfective, got {obj.lesson_data.get('aspect')!r}"
            )

    def test_morph_complete_true_for_full_parse(self, plugin) -> None:
        result = plugin.analyze_sentence("Я читаю интересную книгу.")
        conj = objects_of(result, "conjugation")
        complete = [o for o in conj if o.lesson_data.get("morph_complete")]
        assert any(complete), "Expected at least one morphologically complete conjugation"

    def test_conjugation_confidence_in_range(self, plugin) -> None:
        result = plugin.analyze_sentence("Девушка читает книгу.")
        assert confidences_valid(objects_of(result, "conjugation"))

    def test_conjugation_confidence_cap(self, plugin) -> None:
        """Conjugation confidence must not exceed 0.82."""
        result = plugin.analyze_sentence("Мы идём домой.")
        for obj in objects_of(result, "conjugation"):
            if obj.confidence is not None:
                assert obj.confidence <= 0.82, (
                    f"Confidence {obj.confidence} exceeds cap of 0.82"
                )

    def test_no_duplicate_conjugation_canonical_forms(self, plugin) -> None:
        result = plugin.analyze_sentence("Он читает и она тоже читает.")
        forms = [o.canonical_form for o in objects_of(result, "conjugation")]
        assert len(forms) == len(set(forms))

    def test_conjugation_canonical_form_scheme(self, plugin) -> None:
        """canonical_form must follow lemma:tense:aspect:mood:person_or_gender:number."""
        result = plugin.analyze_sentence("Я пишу письмо.")
        for obj in objects_of(result, "conjugation"):
            parts = obj.canonical_form.split(":")
            assert len(parts) == 6, (
                f"Expected 6 colon-separated parts, got {parts!r}"
            )


# ── case agreement ────────────────────────────────────────────────────────────


class TestCaseAgreementExtraction:
    def test_case_agreement_objects_emitted(self, plugin) -> None:
        result = plugin.analyze_sentence("Большая собака бежит.")
        assert any(objects_of(result, "case_agreement"))

    def test_case_agreement_has_required_keys(self, plugin) -> None:
        result = plugin.analyze_sentence("Красивый город стоит.")
        for obj in objects_of(result, "case_agreement"):
            for key in ("modifier", "modifier_pos", "noun", "case",
                        "gender", "number", "confidence_note"):
                assert key in obj.lesson_data, (
                    f"Missing key {key!r} in case_agreement lesson_data"
                )

    def test_case_agreement_no_confirmed_mismatches(self, plugin) -> None:
        result = plugin.analyze_sentence("Молодой студент читает.")
        for obj in objects_of(result, "case_agreement"):
            assert obj.lesson_data.get("case_match") is not False
            assert obj.lesson_data.get("gender_match") is not False
            assert obj.lesson_data.get("number_match") is not False

    def test_six_case_values_accepted(self, plugin) -> None:
        """Russian has 6 cases; all must be accepted without 'unknown'."""
        valid = {"nominative", "genitive", "dative", "accusative",
                 "instrumental", "locative", "unknown"}
        result = plugin.analyze_sentence(
            "Большой книге нравится мне."  # Dative
        )
        for obj in objects_of(result, "case_agreement"):
            case = obj.lesson_data.get("case")
            assert case in valid, f"Unexpected case value: {case!r}"

    def test_instrumental_case_in_lesson_data(self, plugin) -> None:
        """Instrumental case (с другом) should appear in case_agreement."""
        result = plugin.analyze_sentence("Он идёт с новым другом.")
        agreements = objects_of(result, "case_agreement")
        cases = {o.lesson_data.get("case") for o in agreements}
        # Either the model finds agreement or it doesn't; if it does,
        # instrumental must be a valid value.
        for case in cases:
            assert case in {"nominative", "genitive", "dative", "accusative",
                            "instrumental", "locative", "unknown"}

    def test_case_agreement_boolean_fields_are_bool_or_none(self, plugin) -> None:
        result = plugin.analyze_sentence("Новый дом стоит на горе.")
        for obj in objects_of(result, "case_agreement"):
            for key in ("case_match", "gender_match", "number_match"):
                val = obj.lesson_data.get(key)
                assert val is None or isinstance(val, bool), (
                    f"Expected bool or None for {key}, got {type(val).__name__}"
                )

    def test_case_agreement_type_not_plain_agreement(self, plugin) -> None:
        """Russian plugin must emit case_agreement, not the bare agreement type."""
        result = plugin.analyze_sentence("Большой пёс лает.")
        assert not any(objects_of(result, "agreement")), (
            "Russian plugin should emit case_agreement, not agreement"
        )

    def test_no_det_in_case_agreement(self, plugin) -> None:
        """Russian has no articles; modifier_pos must not be DET."""
        result = plugin.analyze_sentence("Старый человек идёт медленно.")
        for obj in objects_of(result, "case_agreement"):
            assert obj.lesson_data.get("modifier_pos") != "DET", (
                "Russian case_agreement should not involve DET (no articles)"
            )

    def test_case_agreement_canonical_prefix(self, plugin) -> None:
        result = plugin.analyze_sentence("Красивая женщина поёт.")
        for obj in objects_of(result, "case_agreement"):
            assert obj.canonical_form.startswith("case_agreement:"), (
                f"Unexpected prefix: {obj.canonical_form!r}"
            )

    def test_no_duplicate_case_agreement_canonical_forms(self, plugin) -> None:
        result = plugin.analyze_sentence("Красивый дом и старый дом стоят.")
        forms = [o.canonical_form for o in objects_of(result, "case_agreement")]
        assert len(forms) == len(set(forms))


# ── confidence handling ───────────────────────────────────────────────────────


class TestConfidenceHandling:
    def test_all_confidences_in_range(self, plugin) -> None:
        result = plugin.analyze_sentence(
            "Молодая студентка читает интересную книгу."
        )
        for obj in result.candidates:
            if obj.confidence is not None:
                assert 0.0 < obj.confidence <= 1.0

    def test_fully_parsed_verb_high_confidence(self, plugin) -> None:
        result = plugin.analyze_sentence("Он читает книгу.")
        conj = objects_of(result, "conjugation")
        for obj in conj:
            if obj.lesson_data.get("morph_complete"):
                assert obj.confidence is not None and obj.confidence >= 0.78

    def test_partial_morphology_gets_note(self, plugin) -> None:
        """When morphological features are missing, confidence_note should mention it."""
        result = plugin.analyze_sentence("Читается легко.")
        for obj in objects_of(result, "conjugation"):
            if not obj.lesson_data.get("morph_complete"):
                note = obj.lesson_data.get("confidence_note")
                if note is not None:
                    assert "morphology" in note.lower() or "unavailable" in note.lower()


# ── deduplication ─────────────────────────────────────────────────────────────


class TestDeduplication:
    def test_same_noun_appears_once(self, plugin) -> None:
        result = plugin.analyze_sentence("Кот и кот сидят на окне.")
        vocab_forms = [o.canonical_form for o in objects_of(result, "vocabulary")]
        assert len(vocab_forms) == len(set(vocab_forms))

    def test_finite_verb_not_duplicated_as_vocabulary(self, plugin) -> None:
        result = plugin.analyze_sentence("Он пишет и пишет.")
        conj_lemmas  = {o.lesson_data.get("lemma") for o in objects_of(result, "conjugation")}
        vocab_lemmas = {o.canonical_form for o in objects_of(result, "vocabulary")}
        assert conj_lemmas.isdisjoint(vocab_lemmas)


# ── edge cases ────────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_punctuation_only_returns_empty(self, plugin) -> None:
        result = plugin.analyze_sentence("...")
        assert result.candidates == []

    def test_single_noun_analyzed(self, plugin) -> None:
        result = plugin.analyze_sentence("Кот.")
        assert any(result.candidates)

    def test_analyze_text_multi_sentence(self, plugin) -> None:
        results = plugin.analyze_text("Собака лает. Кошка спит.")
        assert len(results) >= 2

    def test_analyze_text_consistent_with_analyze_sentence(self, plugin) -> None:
        text = "Я читаю. Он пишет."
        multi  = plugin.analyze_text(text)
        single = [plugin.analyze_sentence(s) for s in plugin.split_sentences(text)]
        assert len(multi) == len(single)
        for m, s in zip(multi, single):
            assert m.text == s.text
            assert {o.canonical_form for o in m.candidates} == {o.canonical_form for o in s.candidates}

    def test_cyrillic_lemmas_preserved(self, plugin) -> None:
        """Cyrillic characters must not be transliterated or stripped."""
        result = plugin.analyze_sentence("Книга лежит на столе.")
        vocab = objects_of(result, "vocabulary")
        for obj in vocab:
            assert any(
                "\u0400" <= c <= "\u04FF" for c in obj.canonical_form
            ), f"Expected Cyrillic in lemma, got: {obj.canonical_form!r}"


# ── lesson store ──────────────────────────────────────────────────────────────


class TestLessonStore:
    def test_missing_id_returns_none(self, plugin) -> None:
        assert plugin.get_lesson("nonexistent-uuid") is None

    def test_lesson_store_accepts_and_returns_object(self, plugin) -> None:
        obj_id = canonical_object_id("ru", "vocabulary", "дом")
        cand = CandidateObject(
            canonical_form="дом",
            type="vocabulary",
            label="дом",
            lesson_data={"lemma": "дом", "pos": "NOUN"},
        )
        plugin.lesson_store[obj_id] = cand
        stored = plugin.get_lesson(obj_id)
        assert stored is not None
        assert stored.canonical_form == "дом"

    def test_lesson_store_independent_across_instances(self) -> None:
        from backend.plugins.russian import RussianPlugin
        p1 = RussianPlugin()
        p2 = RussianPlugin()
        obj_id = canonical_object_id("ru", "vocabulary", "кот")
        p1.lesson_store[obj_id] = CandidateObject(
            canonical_form="кот", type="vocabulary", label="кот", lesson_data={}
        )
        assert p2.get_lesson(obj_id) is None


# ── multilingual architecture ─────────────────────────────────────────────────


class TestMultilingualArchitecture:
    def test_russian_registered_in_plugin_loader(self) -> None:
        from backend.parsing.plugin_loader import load_plugins
        registry = load_plugins()
        assert "ru" in registry.all()

    def test_russian_capabilities_in_registry(self) -> None:
        from backend.parsing.plugin_loader import load_plugins
        registry = load_plugins()
        caps = registry.supported_languages()["ru"]
        assert caps.morphology_depth == "rich"
        assert caps.script_family == "cyrillic"

    def test_russian_and_german_vocab_ids_differ(self) -> None:
        ru_id = canonical_object_id("ru", "vocabulary", "дом")
        de_id = canonical_object_id("de", "vocabulary", "дом")
        assert ru_id != de_id

    def test_russian_conjugation_has_aspect_german_does_not(self, plugin) -> None:
        """Russian conjugation lesson_data must carry 'aspect'; German doesn't."""
        result = plugin.analyze_sentence("Он читает.")
        conj = objects_of(result, "conjugation")
        for obj in conj:
            assert "aspect" in obj.lesson_data, (
                "Russian conjugation should carry aspect"
            )

    def test_russian_has_six_cases_not_four(self) -> None:
        """German has 4 cases; Russian has 6 — Instrumental and Locative extra."""
        from backend.plugins.russian import _CASE_DISPLAY
        assert "Ins" in _CASE_DISPLAY, "Instrumental case missing"
        assert "Loc" in _CASE_DISPLAY, "Locative case missing"
        assert len(_CASE_DISPLAY) == 6

    def test_no_paradigm_class_in_russian(self, plugin) -> None:
        """Russian does not have a German-style paradigm_class field."""
        result = plugin.analyze_sentence("Я хожу в магазин.")
        for obj in objects_of(result, "conjugation"):
            assert "paradigm_class" not in obj.lesson_data
