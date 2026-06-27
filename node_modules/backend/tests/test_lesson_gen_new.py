"""New test classes for the multilingual lesson engine.

These tests cover the three new modules (context, providers, formatters) and
the new behaviour introduced in generators.py:
  - LessonContext construction and property helpers
  - LessonProviders protocol and null implementations
  - Language-aware explanation text (formatters module)
  - Context threading through build_lesson
  - Effective LessonTemplate stamping on LessonResponse
  - Provider-supplied gloss field in vocabulary / dictionary lessons
"""
from __future__ import annotations

import pytest

from backend.lesson.context import LessonContext
from backend.lesson.generators import build_lesson
from backend.lesson.providers import LessonProviders, NullGlossProvider

# ── Shared contexts ───────────────────────────────────────────────────────────

_ES_CTX = LessonContext(
    language_code="es",
    language_name="Spanish",
    script_family="latin",
    direction="ltr",
)

_AR_CTX = LessonContext(
    language_code="ar",
    language_name="Arabic",
    script_family="arabic",
    direction="rtl",
)

_JA_CTX = LessonContext(
    language_code="ja",
    language_name="Japanese",
    script_family="cjk",
    direction="ltr",
)


# ── TestLessonContext ─────────────────────────────────────────────────────────


class TestLessonContext:
    def test_unknown_has_none_language_fields(self) -> None:
        ctx = LessonContext.unknown()
        assert ctx.language_code is None
        assert ctx.language_name is None

    def test_unknown_direction_default_ltr(self) -> None:
        ctx = LessonContext.unknown()
        assert ctx.direction == "ltr"
        assert not ctx.is_rtl

    def test_from_capabilities_maps_fields(self) -> None:
        from backend.schemas.language import LanguageCapabilities
        caps = LanguageCapabilities(
            code="fr",
            display_name="French",
            direction="ltr",
            script_family="latin",
            tokenization_mode="whitespace",
            morphology_depth="rich",
            lesson_modes_supported=["morphology", "vocabulary"],
        )
        ctx = LessonContext.from_capabilities(caps)
        assert ctx.language_code == "fr"
        assert ctx.language_name == "French"
        assert ctx.script_family == "latin"
        assert ctx.direction == "ltr"

    def test_from_capabilities_rtl(self) -> None:
        from backend.schemas.language import LanguageCapabilities
        caps = LanguageCapabilities(
            code="ar",
            display_name="Arabic",
            direction="rtl",
            script_family="arabic",
            tokenization_mode="whitespace",
            morphology_depth="none",
            lesson_modes_supported=["dictionary"],
        )
        ctx = LessonContext.from_capabilities(caps)
        assert ctx.is_rtl
        assert not ctx.is_cjk

    def test_is_cjk_flag(self) -> None:
        assert _JA_CTX.is_cjk
        assert not _ES_CTX.is_cjk

    def test_is_rtl_flag(self) -> None:
        assert _AR_CTX.is_rtl
        assert not _ES_CTX.is_rtl

    def test_context_is_hashable_and_frozen(self) -> None:
        ctx = LessonContext(language_code="de", language_name="German")
        s = {ctx}
        assert len(s) == 1

    def test_equality(self) -> None:
        a = LessonContext(language_code="es", language_name="Spanish")
        b = LessonContext(language_code="es", language_name="Spanish")
        assert a == b

    def test_inequality_on_code(self) -> None:
        a = LessonContext(language_code="es")
        b = LessonContext(language_code="fr")
        assert a != b


# ── TestLessonProviders ───────────────────────────────────────────────────────


class TestLessonProviders:
    def test_null_returns_empty_providers(self) -> None:
        prov = LessonProviders.null()
        assert isinstance(prov.gloss, NullGlossProvider)

    def test_null_gloss_returns_none_for_known(self) -> None:
        prov = LessonProviders.null()
        assert prov.gloss.lookup("casa", "es") is None

    def test_null_gloss_returns_none_for_unknown_language(self) -> None:
        prov = LessonProviders.null()
        assert prov.gloss.lookup("casa", None) is None

    def test_null_gloss_returns_none_with_pos(self) -> None:
        prov = LessonProviders.null()
        assert prov.gloss.lookup("casa", "es", "NOUN") is None

    def test_null_pronunciation_returns_none(self) -> None:
        prov = LessonProviders.null()
        assert prov.pronunciation.pronunciation("casa", "es") is None
        assert prov.pronunciation.pronunciation("casa", None) is None

    def test_custom_gloss_provider_satisfies_protocol(self) -> None:
        class DictGlossProvider:
            _glosses = {"casa": "house", "gato": "cat"}

            def lookup(self, lemma, language_code, pos=None):
                return self._glosses.get(lemma)

        prov = LessonProviders(gloss=DictGlossProvider())
        assert prov.gloss.lookup("casa", "es") == "house"
        assert prov.gloss.lookup("unknown", "es") is None

    def test_providers_frozen(self) -> None:
        prov = LessonProviders.null()
        with pytest.raises((AttributeError, TypeError)):
            prov.gloss = NullGlossProvider()  # type: ignore[misc]  # assignment to frozen dataclass field; we're testing it raises at runtime


# ── TestLessonFormatters ──────────────────────────────────────────────────────


class TestLessonFormatters:
    def test_idiom_with_language_name(self) -> None:
        from backend.lesson import formatters as fmt
        result = fmt.idiom_explanation("sin embargo", "nevertheless", _ES_CTX)
        assert "Spanish" in result
        assert "nevertheless" in result

    def test_idiom_without_language_name_grammatically_correct(self) -> None:
        from backend.lesson import formatters as fmt
        ctx = LessonContext.unknown()
        result = fmt.idiom_explanation("sin embargo", "nevertheless", ctx)
        assert "this language" not in result
        assert "nevertheless" in result
        # Must not start with "a " before "idiom" (would be "a idiom")
        assert "a idiom" not in result

    def test_idiom_no_meaning_with_language(self) -> None:
        from backend.lesson import formatters as fmt
        result = fmt.idiom_explanation("echar de menos", "", _ES_CTX)
        assert "Spanish" in result
        assert "idiomatic expression" in result

    def test_idiom_no_meaning_no_language(self) -> None:
        from backend.lesson import formatters as fmt
        result = fmt.idiom_explanation("echar de menos", "", LessonContext.unknown())
        assert "an idiomatic expression" in result

    def test_vocabulary_surface_equals_lemma(self) -> None:
        from backend.lesson import formatters as fmt
        result = fmt.vocabulary_explanation("casa", "noun", "casa", _ES_CTX)
        assert "lemma" not in result.lower()

    def test_vocabulary_surface_differs_from_lemma(self) -> None:
        from backend.lesson import formatters as fmt
        result = fmt.vocabulary_explanation("libros", "noun", "libro", _ES_CTX)
        assert "libro" in result
        assert "lemma" in result.lower()

    def test_conjugation_with_full_morphology(self) -> None:
        from backend.lesson import formatters as fmt
        result = fmt.conjugation_explanation(
            "hablo", "first", "singular", "present", "indicative", "hablar", _ES_CTX
        )
        assert "hablo" in result
        assert "hablar" in result
        assert "present" in result
        assert "indicative" in result

    def test_conjugation_unknown_morphology_no_unknown_text(self) -> None:
        from backend.lesson import formatters as fmt
        result = fmt.conjugation_explanation(
            "parle", "unknown", "unknown", "unknown", "unknown", "parler",
            LessonContext.unknown()
        )
        assert "parle" in result
        assert "parler" in result
        assert "unknown" not in result

    def test_grammar_with_usage(self) -> None:
        from backend.lesson import formatters as fmt
        result = fmt.grammar_explanation("ser + adj", "used for permanent qualities", _ES_CTX)
        assert "permanent" in result

    def test_grammar_without_usage(self) -> None:
        from backend.lesson import formatters as fmt
        result = fmt.grammar_explanation("ser + adj", "", _ES_CTX)
        assert "grammatical pattern" in result.lower()

    def test_script_with_meaning(self) -> None:
        from backend.lesson import formatters as fmt
        result = fmt.script_explanation("water", "water", _JA_CTX)
        assert "water" in result

    def test_transliteration_with_scheme(self) -> None:
        from backend.lesson import formatters as fmt
        result = fmt.transliteration_explanation("mizu", "mizu", "hepburn_romaji", None, _JA_CTX)
        assert "mizu" in result
        assert "hepburn_romaji" in result

    def test_nuance_with_note(self) -> None:
        from backend.lesson import formatters as fmt
        note = "describes an ongoing past state"
        result = fmt.nuance_explanation("vivía", "Imperfect aspect", note, _ES_CTX)
        assert result == note

    def test_nuance_without_note(self) -> None:
        from backend.lesson import formatters as fmt
        result = fmt.nuance_explanation("vivía", "Imperfect aspect", "", _ES_CTX)
        assert "vivía" in result
        assert "imperfect aspect" in result


# ── TestLanguageAwareness ─────────────────────────────────────────────────────


class TestLanguageAwareness:
    def test_language_code_stamped_on_response(self) -> None:
        lesson = build_lesson(
            object_id="x", obj_type="vocabulary",
            canonical_form="casa", display_label="casa",
            lesson_data={"lemma": "casa", "pos": "NOUN"},
            context=_ES_CTX,
        )
        assert lesson.language_code == "es"

    def test_script_direction_ltr(self) -> None:
        lesson = build_lesson(
            object_id="x", obj_type="vocabulary",
            canonical_form="maison", display_label="maison",
            lesson_data={"lemma": "maison", "pos": "NOUN"},
            context=LessonContext(language_code="fr", language_name="French"),
        )
        assert lesson.script_direction == "ltr"

    def test_script_direction_rtl(self) -> None:
        lesson = build_lesson(
            object_id="x", obj_type="vocabulary",
            canonical_form="bayt", display_label="bayt",
            lesson_data={"lemma": "bayt", "pos": "NOUN"},
            context=_AR_CTX,
        )
        assert lesson.script_direction == "rtl"

    def test_no_language_code_when_no_context(self) -> None:
        lesson = build_lesson(
            object_id="x", obj_type="vocabulary",
            canonical_form="casa", display_label="casa",
            lesson_data={"lemma": "casa", "pos": "NOUN"},
        )
        assert lesson.language_code is None
        assert lesson.script_direction is None

    def test_idiom_explanation_uses_language_name(self) -> None:
        lesson = build_lesson(
            object_id="x", obj_type="idiom",
            canonical_form="sin embargo", display_label="sin embargo",
            lesson_data={"phrase": "sin embargo", "meaning": "nevertheless",
                         "register": "neutral"},
            context=_ES_CTX,
        )
        assert "Spanish" in lesson.explanation

    def test_idiom_without_context_no_hardcoded_language(self) -> None:
        lesson = build_lesson(
            object_id="x", obj_type="idiom",
            canonical_form="sin embargo", display_label="sin embargo",
            lesson_data={"phrase": "sin embargo", "meaning": "nevertheless"},
        )
        assert "Spanish" not in lesson.explanation
        assert "this language" not in lesson.explanation
        assert "nevertheless" in lesson.explanation

    def test_context_does_not_change_drill_count(self) -> None:
        kwargs = dict(
            object_id="x", obj_type="vocabulary",
            canonical_form="casa", display_label="casa",
            lesson_data={"lemma": "casa", "pos": "NOUN"},
        )
        no_ctx   = build_lesson(**kwargs)
        with_ctx = build_lesson(**kwargs, context=_ES_CTX)
        assert len(no_ctx.drills) == len(with_ctx.drills)

    def test_determinism_with_context(self) -> None:
        kwargs = dict(
            object_id="x", obj_type="vocabulary",
            canonical_form="gato", display_label="gato",
            lesson_data={"lemma": "gato", "pos": "NOUN"},
            context=_ES_CTX,
        )
        assert build_lesson(**kwargs) == build_lesson(**kwargs)


# ── TestLessonModeStamping ────────────────────────────────────────────────────


class TestLessonModeStamping:
    def test_vocabulary_morphology_mode_stamps_morphology(self) -> None:
        r = build_lesson(
            object_id="x", obj_type="vocabulary",
            canonical_form="casa", display_label="casa",
            lesson_data={"lemma": "casa", "pos": "NOUN"},
            lesson_mode="morphology",
        )
        assert r.lesson_mode == "morphology"

    def test_vocabulary_vocabulary_mode_stamps_vocabulary(self) -> None:
        r = build_lesson(
            object_id="x", obj_type="vocabulary",
            canonical_form="casa", display_label="casa",
            lesson_data={"lemma": "casa", "pos": "NOUN"},
            lesson_mode="vocabulary",
        )
        assert r.lesson_mode == "vocabulary"

    def test_vocabulary_dictionary_mode_stamps_dictionary(self) -> None:
        r = build_lesson(
            object_id="x", obj_type="vocabulary",
            canonical_form="casa", display_label="casa",
            lesson_data={"lemma": "casa", "pos": "NOUN"},
            lesson_mode="dictionary",
        )
        assert r.lesson_mode == "dictionary"

    def test_script_stamps_script_regardless_of_lesson_mode(self) -> None:
        for mode in ("morphology", "vocabulary", "dictionary"):
            r = build_lesson(
                object_id="x", obj_type="script",
                canonical_form="字", display_label="字",
                lesson_data={"character": "字", "readings": ["zi4"]},
                lesson_mode=mode,  # type: ignore[arg-type]  # mode is str from loop; all values are valid LessonMode members, Pydantic validates
            )
            assert r.lesson_mode == "script", (
                f"Expected 'script', got {r.lesson_mode!r} for lesson_mode={mode!r}"
            )

    def test_transliteration_stamps_transliteration(self) -> None:
        r = build_lesson(
            object_id="x", obj_type="transliteration",
            canonical_form="mizu:hepburn_romaji",
            display_label="mizu",
            lesson_data={"native_form": "mizu", "romanized": "mizu"},
            lesson_mode="vocabulary",  # type: ignore[arg-type]  # "vocabulary" ∈ LessonMode; mypy can't narrow str literals to a Literal type alias
        )
        assert r.lesson_mode == "transliteration"

    def test_idiom_stamps_idiom(self) -> None:
        r = build_lesson(
            object_id="x", obj_type="idiom",
            canonical_form="sin embargo", display_label="sin embargo",
            lesson_data={"phrase": "sin embargo", "meaning": "nevertheless"},
            lesson_mode="vocabulary",  # type: ignore[arg-type]  # "vocabulary" ∈ LessonMode; mypy can't narrow str literals to a Literal type alias
        )
        assert r.lesson_mode == "idiom"

    def test_grammar_stamps_morphology(self) -> None:
        r = build_lesson(
            object_id="x", obj_type="grammar",
            canonical_form="grammar:ser_copula", display_label="ser",
            lesson_data={"pattern": "ser + adj", "usage": "permanent qualities"},
        )
        assert r.lesson_mode == "morphology"

    def test_nuance_stamps_morphology(self) -> None:
        r = build_lesson(
            object_id="x", obj_type="nuance",
            canonical_form="nuance:imperfect_aspect:vivir", display_label="vivía",
            lesson_data={
                "nuance_type": "imperfect_aspect",
                "lemma": "vivir",
                "surface": "vivía",
                "note": "describes an ongoing past state",
            },
        )
        assert r.lesson_mode == "morphology"

    def test_idiom_bypasses_vocabulary_lesson_mode(self) -> None:
        r = build_lesson(
            object_id="x", obj_type="idiom",
            canonical_form="por favor", display_label="por favor",
            lesson_data={"phrase": "por favor", "meaning": "please"},
            lesson_mode="vocabulary",  # type: ignore[arg-type]  # "vocabulary" ∈ LessonMode; mypy can't narrow str literals to a Literal type alias
        )
        # _build_idiom ran, not _build_vocabulary
        assert r.title.startswith("Idiom:")
        assert r.lesson_mode == "idiom"

    def test_case_agreement_stamps_morphology(self) -> None:
        r = build_lesson(
            object_id="x", obj_type="case_agreement",
            canonical_form="case_agreement:nom:der_Mann",
            display_label="der Mann",
            lesson_data={
                "modifier": "der", "modifier_pos": "DET",
                "noun": "Mann", "case": "Nom",
                "gender": "Masc", "number": "Sing",
                "confidence_note": "case: confirmed; gender: confirmed; number: confirmed",
            },
        )
        assert r.lesson_mode == "morphology"


# ── TestProviderIntegration ───────────────────────────────────────────────────


class TestProviderIntegration:
    def _dict_providers(self, glosses: dict[str, str]) -> LessonProviders:
        class DictGloss:
            def lookup(self, lemma, language_code, pos=None):
                return glosses.get(lemma)
        return LessonProviders(gloss=DictGloss())

    def test_gloss_provider_adds_field_to_vocabulary(self) -> None:
        prov = self._dict_providers({"casa": "house"})
        lesson = build_lesson(
            object_id="x", obj_type="vocabulary",
            canonical_form="casa", display_label="casa",
            lesson_data={"lemma": "casa", "pos": "NOUN"},
            providers=prov,
            context=_ES_CTX,
        )
        field_labels = {f.label for f in lesson.fields}
        assert "Gloss" in field_labels
        gloss_val = next(f.value for f in lesson.fields if f.label == "Gloss")
        assert gloss_val == "house"

    def test_null_provider_adds_no_gloss_field(self) -> None:
        lesson = build_lesson(
            object_id="x", obj_type="vocabulary",
            canonical_form="gato", display_label="gato",
            lesson_data={"lemma": "gato", "pos": "NOUN"},
            providers=LessonProviders.null(),
        )
        field_labels = {f.label for f in lesson.fields}
        assert "Gloss" not in field_labels

    def test_gloss_provider_dictionary_mode(self) -> None:
        prov = self._dict_providers({"libro": "book"})
        lesson = build_lesson(
            object_id="x", obj_type="vocabulary",
            canonical_form="libro", display_label="libro",
            lesson_data={"lemma": "libro"},
            lesson_mode="dictionary",
            providers=prov,
            context=_ES_CTX,
        )
        field_labels = {f.label for f in lesson.fields}
        assert "Gloss" in field_labels
        assert next(f.value for f in lesson.fields if f.label == "Gloss") == "book"

    def test_plugin_gloss_in_lesson_data_not_overwritten(self) -> None:
        # lesson_data already has gloss → provider is NOT called
        prov = self._dict_providers({"casa": "house (from provider)"})
        lesson = build_lesson(
            object_id="x", obj_type="vocabulary",
            canonical_form="casa", display_label="casa",
            lesson_data={"lemma": "casa", "pos": "NOUN", "gloss": "dwelling (from plugin)"},
            providers=prov,
        )
        # Provider should not have added a second Gloss field
        gloss_fields = [f for f in lesson.fields if f.label == "Gloss"]
        assert len(gloss_fields) <= 1
        # If a Gloss field is present it should NOT contain the provider value
        # (because vocabulary builder only calls provider when lesson_data has no gloss)
        if gloss_fields:
            assert "from provider" not in gloss_fields[0].value

    def test_missing_lemma_in_provider_no_gloss_field(self) -> None:
        prov = self._dict_providers({"casa": "house"})  # no "libro"
        lesson = build_lesson(
            object_id="x", obj_type="vocabulary",
            canonical_form="libro", display_label="libro",
            lesson_data={"lemma": "libro", "pos": "NOUN"},
            providers=prov,
        )
        assert "Gloss" not in {f.label for f in lesson.fields}

    def test_determinism_preserved_with_providers(self) -> None:
        prov = self._dict_providers({"sol": "sun"})
        kwargs = dict(
            object_id="x", obj_type="vocabulary",
            canonical_form="sol", display_label="sol",
            lesson_data={"lemma": "sol", "pos": "NOUN"},
            providers=prov,
            context=_ES_CTX,
        )
        assert build_lesson(**kwargs) == build_lesson(**kwargs)
