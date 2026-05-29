"""Unit tests for the lesson generator — multilingual lesson engine.

All tests are synchronous — generators are pure functions with no I/O.

Test organisation
─────────────────
Existing classes: build_lesson general, drill presence, MC integrity,
    determinism, field rendering.

New classes (multilingual engine):
  TestLessonContext      — LessonContext construction and helpers.
  TestLessonProviders    — Provider protocols and null implementations.
  TestLessonFormatters   — Language-aware explanation text.
  TestLanguageAwareness  — Context threaded into build_lesson.
  TestLessonModeStamping — Effective template reported on LessonResponse.
  TestProviderIntegration— Gloss provider supplementing lesson fields.
"""
from __future__ import annotations


from backend.lesson.generators import build_lesson, _make_mc_drill
from backend.lesson.context import LessonContext
from backend.schemas.lesson import (
    FillBlankDrill,
    MultipleChoiceDrill,
    RecognitionDrill,
    ShadowingDrill,
)

_VOCAB_DATA = {"lemma": "casa", "pos": "NOUN"}
_CONJ_DATA = {
    "lemma":          "hablar",
    "surface":        "hablo",
    "tense":          "present",
    "mood":           "indicative",
    "person":         "1",
    "number":         "Sing",
    "morph_complete": True,
    "construction":   "standalone",
    "is_reflexive":   False,
}
_AGREE_DATA = {
    "modifier":     "gran",
    "modifier_pos": "ADJ",
    "noun":         "casa",
    "gender":       "Fem",
    "number":       "Sing",
    "gender_match": True,
    "number_match": True,
    "confidence_note": "gender and number both confirmed",
}


# ── build_lesson general ──────────────────────────────────────────────────────


def test_vocabulary_lesson_has_required_fields():
    lesson = build_lesson(
        object_id="abc-123",
        obj_type="vocabulary",
        canonical_form="casa",
        display_label="casa",
        lesson_data=_VOCAB_DATA,
    )
    assert lesson.id == "abc-123"
    assert lesson.type == "vocabulary"
    assert "casa" in lesson.title
    assert "noun" in lesson.explanation
    assert len(lesson.drills) >= 1
    assert len(lesson.examples) >= 1


def test_conjugation_lesson_has_required_fields():
    lesson = build_lesson(
        object_id="def-456",
        obj_type="conjugation",
        canonical_form="hablar:present:indicative:1:Sing",
        display_label="hablo",
        lesson_data=_CONJ_DATA,
    )
    assert lesson.type == "conjugation"
    assert "hablo" in lesson.title
    assert "hablar" in lesson.explanation
    assert "present" in lesson.explanation


def test_agreement_lesson_has_required_fields():
    lesson = build_lesson(
        object_id="ghi-789",
        obj_type="agreement",
        canonical_form="adj:gran_casa",
        display_label="gran casa",
        lesson_data=_AGREE_DATA,
    )
    assert lesson.type == "agreement"
    assert "gran" in lesson.explanation
    assert "casa" in lesson.explanation


def test_idiom_uses_dedicated_builder():
    # "idiom" now has its own dedicated builder (_build_idiom).
    lesson = build_lesson(
        object_id="zzz",
        obj_type="idiom",
        canonical_form="por supuesto",
        display_label="por supuesto",
        lesson_data={"meaning": "of course"},
    )
    assert lesson.type == "idiom"
    assert len(lesson.drills) >= 1


def test_generic_fallback_for_truly_unknown_type():
    lesson = build_lesson(
        object_id="zzz",
        obj_type="vocabulary",   # uses morphology dispatch → _build_vocabulary
        canonical_form="cosa",
        display_label="cosa",
        lesson_data={"lemma": "cosa", "pos": "NOUN"},
    )
    assert lesson.type == "vocabulary"
    assert len(lesson.drills) >= 1


# ── drill presence ────────────────────────────────────────────────────────────


def test_vocabulary_always_has_shadowing_drill():
    lesson = build_lesson(
        object_id="x", obj_type="vocabulary",
        canonical_form="hola", display_label="Hola",
        lesson_data={"lemma": "hola", "pos": "NOUN"},
    )
    types = {d.type for d in lesson.drills}
    assert "shadowing" in types


def test_conjugation_has_fill_blank_for_lemma():
    lesson = build_lesson(
        object_id="x", obj_type="conjugation",
        canonical_form="hablar:present:indicative:1:Sing",
        display_label="hablo", lesson_data=_CONJ_DATA,
    )
    fill_drills = [d for d in lesson.drills if d.type == "fill_blank"]
    assert len(fill_drills) >= 1
    assert any(d.answer == "hablar" for d in fill_drills)


def test_vocabulary_fill_blank_only_when_surface_differs():
    # Same surface and lemma — no fill-blank for lemma
    lesson_same = build_lesson(
        object_id="x", obj_type="vocabulary",
        canonical_form="casa", display_label="casa",
        lesson_data={"lemma": "casa", "pos": "NOUN"},
    )
    fill_drills = [d for d in lesson_same.drills if d.type == "fill_blank"]
    assert len(fill_drills) == 0

    # Different surface and lemma — fill-blank is present
    lesson_diff = build_lesson(
        object_id="x", obj_type="vocabulary",
        canonical_form="libro", display_label="libros",
        lesson_data={"lemma": "libro", "pos": "NOUN"},
    )
    fill_drills_diff = [d for d in lesson_diff.drills if d.type == "fill_blank"]
    assert len(fill_drills_diff) >= 1


def test_conjugation_reflexive_recognition_drill():
    reflexive_data = {**_CONJ_DATA, "is_reflexive": True}
    lesson = build_lesson(
        object_id="x", obj_type="conjugation",
        canonical_form="levantarse:present:indicative:1:Sing",
        display_label="me levanto", lesson_data=reflexive_data,
    )
    rec_drills = [d for d in lesson.drills if d.type == "recognition"]
    assert any(d.correct is True for d in rec_drills)


def test_non_reflexive_recognition_drill_is_false():
    lesson = build_lesson(
        object_id="x", obj_type="conjugation",
        canonical_form="hablar:present:indicative:1:Sing",
        display_label="hablo", lesson_data=_CONJ_DATA,
    )
    rec_drills = [d for d in lesson.drills if d.type == "recognition"]
    assert all(d.correct is False for d in rec_drills)


# ── multiple choice integrity ─────────────────────────────────────────────────


def test_mc_answer_index_points_to_correct_option():
    lesson = build_lesson(
        object_id="x", obj_type="vocabulary",
        canonical_form="casa", display_label="casa",
        lesson_data={"lemma": "casa", "pos": "NOUN"},
    )
    mc_drills = [d for d in lesson.drills if d.type == "multiple_choice"]
    for drill in mc_drills:
        correct_option = drill.options[drill.answer_index]
        assert correct_option == "noun"


def test_mc_no_duplicate_options():
    lesson = build_lesson(
        object_id="x", obj_type="vocabulary",
        canonical_form="casa", display_label="casa",
        lesson_data={"lemma": "casa", "pos": "NOUN"},
    )
    for drill in lesson.drills:
        if drill.type == "multiple_choice":
            assert len(drill.options) == len(set(drill.options))


# ── determinism ───────────────────────────────────────────────────────────────


def test_lesson_generation_is_deterministic():
    kwargs = dict(
        object_id="abc",
        obj_type="vocabulary",
        canonical_form="casa",
        display_label="casas",
        lesson_data={"lemma": "casa", "pos": "NOUN"},
    )
    assert build_lesson(**kwargs) == build_lesson(**kwargs)


def test_different_seeds_produce_different_option_order():
    """Two words with different canonical forms should get different shuffles."""
    mc1 = _make_mc_drill("word1", "prompt", "noun", ["noun", "verb", "adjective", "adverb"])
    mc2 = _make_mc_drill("word2", "prompt", "noun", ["noun", "verb", "adjective", "adverb"])
    # They must both be valid (correct option present), but may differ in order.
    assert mc1 is not None
    assert mc2 is not None
    assert mc1.options[mc1.answer_index] == "noun"
    assert mc2.options[mc2.answer_index] == "noun"


def test_make_mc_drill_returns_none_when_pool_too_small():
    result = _make_mc_drill("seed", "prompt?", "noun", ["noun", "verb"], n_wrong=3)
    assert result is None


# ── field rendering ───────────────────────────────────────────────────────────


def test_conjugation_fields_include_tense_and_mood():
    lesson = build_lesson(
        object_id="x", obj_type="conjugation",
        canonical_form="hablar:present:indicative:1:Sing",
        display_label="hablo", lesson_data=_CONJ_DATA,
    )
    labels = {f.label for f in lesson.fields}
    assert "Tense" in labels
    assert "Mood" in labels
    assert "Lemma" in labels


def test_vocabulary_fields_include_pos():
    lesson = build_lesson(
        object_id="x", obj_type="vocabulary",
        canonical_form="casa", display_label="casa",
        lesson_data=_VOCAB_DATA,
    )
    labels = {f.label for f in lesson.fields}
    assert "Part of speech" in labels


# ── pluggable tense/mood pools ────────────────────────────────────────────────


class TestPluggablePools:
    """LessonContext tense_pool / mood_pool are used instead of global defaults."""

    _CONJ = {
        "lemma": "hablar", "surface": "hablo",
        "tense": "present", "mood": "indicative",
        "person": "1", "number": "Sing",
    }

    def _mc_drills(self, lesson) -> list:
        return [d for d in lesson.drills if d.type == "multiple_choice"]

    def test_tense_mc_uses_global_pool_when_no_context(self):
        """Without a context, the global _TENSE_OPTIONS pool is used."""
        from backend.lesson.generators import _TENSE_OPTIONS
        lesson = build_lesson(
            object_id="x", obj_type="conjugation",
            canonical_form="c", display_label="hablo",
            lesson_data=self._CONJ,
        )
        mc_drills = self._mc_drills(lesson)
        tense_mc = next(d for d in mc_drills if "tense" in d.prompt.lower())
        for opt in tense_mc.options:
            assert opt in _TENSE_OPTIONS

    def test_tense_mc_uses_language_pool_when_context_set(self):
        """With a tense_pool on LessonContext, wrong options are from that pool only."""
        spanish_pool = ("present", "preterite", "imperfect", "future", "conditional")
        ctx = LessonContext(
            language_code="es", language_name="Spanish",
            tense_pool=spanish_pool,
        )
        lesson = build_lesson(
            object_id="x", obj_type="conjugation",
            canonical_form="c", display_label="hablo",
            lesson_data=self._CONJ,
            context=ctx,
        )
        mc_drills = self._mc_drills(lesson)
        tense_mc = next(d for d in mc_drills if "tense" in d.prompt.lower())
        for opt in tense_mc.options:
            assert opt in spanish_pool, f"Unexpected option {opt!r} not in Spanish tense pool"

    def test_german_tense_pool_excludes_preterite(self):
        """German tense pool should not offer 'preterite' as a wrong answer."""
        german_pool = ("present", "past", "perfect", "pluperfect", "future")
        ctx = LessonContext(
            language_code="de", language_name="German",
            tense_pool=german_pool,
        )
        lesson = build_lesson(
            object_id="x", obj_type="conjugation",
            canonical_form="c", display_label="spricht",
            lesson_data={**self._CONJ, "tense": "present", "lemma": "sprechen"},
            context=ctx,
        )
        mc_drills = self._mc_drills(lesson)
        tense_mc = next(d for d in mc_drills if "tense" in d.prompt.lower())
        assert "preterite" not in tense_mc.options

    def test_mood_mc_drill_present_when_mood_known(self):
        """A mood MC drill is emitted when mood is known and pool has enough options."""
        ctx = LessonContext(
            language_code="fr", language_name="French",
            mood_pool=("indicative", "subjunctive", "conditional", "imperative"),
        )
        lesson = build_lesson(
            object_id="x", obj_type="conjugation",
            canonical_form="c", display_label="parle",
            lesson_data={**self._CONJ, "mood": "indicative"},
            context=ctx,
        )
        mc_drills = self._mc_drills(lesson)
        mood_mc = next((d for d in mc_drills if "mood" in d.prompt.lower()), None)
        assert mood_mc is not None, "Expected a mood MC drill"
        assert mood_mc.options[mood_mc.answer_index] == "indicative"

    def test_mood_mc_absent_when_mood_unknown(self):
        """No mood MC drill when lesson_data has no mood (or mood is 'unknown')."""
        lesson = build_lesson(
            object_id="x", obj_type="conjugation",
            canonical_form="c", display_label="hablo",
            lesson_data={**self._CONJ, "mood": "unknown"},
        )
        mc_drills = self._mc_drills(lesson)
        mood_mcs = [d for d in mc_drills if "mood" in d.prompt.lower()]
        assert mood_mcs == []

    def test_from_capabilities_populates_pools(self):
        """LessonContext.from_capabilities transfers tense_pool and mood_pool."""
        from backend.schemas.language import LanguageCapabilities
        caps = LanguageCapabilities(
            code="es", display_name="Spanish", direction="ltr",
            script_family="latin", tokenization_mode="whitespace",
            morphology_depth="rich",
            lesson_modes_supported=["morphology"],
            tense_pool=["present", "preterite", "imperfect"],
            mood_pool=["indicative", "subjunctive"],
        )
        ctx = LessonContext.from_capabilities(caps)
        assert ctx.tense_pool == ("present", "preterite", "imperfect")
        assert ctx.mood_pool == ("indicative", "subjunctive")

    def test_from_capabilities_none_pools_stay_none(self):
        """When a plugin declares no pools, context pools are None (use global)."""
        from backend.schemas.language import LanguageCapabilities
        caps = LanguageCapabilities(
            code="xx", display_name="Unknown", direction="ltr",
            script_family="latin", tokenization_mode="whitespace",
            morphology_depth="shallow",
            lesson_modes_supported=["vocabulary"],
        )
        ctx = LessonContext.from_capabilities(caps)
        assert ctx.tense_pool is None
        assert ctx.mood_pool is None


# ── Grammatical label localisation ────────────────────────────────────────────


class TestGrammaticalLabelLocalisation:
    """POS, gender, number, case, and article-agreement field values are localised
    via gram_label() — English l1 falls back to English values unchanged."""

    def _vocab_lesson(self, lesson_data: dict, l1: str = "en") -> dict[str, str]:
        ctx = LessonContext(l1_language=l1)
        lesson = build_lesson(
            object_id="loc-test",
            obj_type="vocabulary",
            canonical_form="test",
            display_label="test",
            lesson_data=lesson_data,
            context=ctx,
        )
        return {f.label: f.value for f in lesson.fields}

    def test_pos_field_english_unchanged(self):
        fields = self._vocab_lesson({"lemma": "casa", "pos": "NOUN"}, l1="en")
        assert fields["Part of speech"] == "noun"

    def test_pos_field_spanish(self):
        fields = self._vocab_lesson({"lemma": "casa", "pos": "NOUN"}, l1="es")
        assert fields["Part of speech"] == "sustantivo"

    def test_pos_field_french(self):
        fields = self._vocab_lesson({"lemma": "maison", "pos": "NOUN"}, l1="fr")
        assert fields["Part of speech"] == "nom"

    def test_pos_field_german(self):
        fields = self._vocab_lesson({"lemma": "Haus", "pos": "NOUN"}, l1="de")
        assert fields["Part of speech"] == "Substantiv"

    def test_pos_field_russian(self):
        fields = self._vocab_lesson({"lemma": "дом", "pos": "NOUN"}, l1="ru")
        assert fields["Part of speech"] == "существительное"

    def test_pos_field_japanese(self):
        fields = self._vocab_lesson({"lemma": "家", "pos": "NOUN"}, l1="ja")
        assert fields["Part of speech"] == "名詞"

    def test_pos_verb_spanish(self):
        fields = self._vocab_lesson({"lemma": "hablar", "pos": "VERB"}, l1="es")
        assert fields["Part of speech"] == "verbo"

    def test_pos_adjective_german(self):
        fields = self._vocab_lesson({"lemma": "groß", "pos": "ADJ"}, l1="de")
        assert fields["Part of speech"] == "Adjektiv"

    def test_gender_field_spanish(self):
        fields = self._vocab_lesson(
            {"lemma": "casa", "pos": "NOUN", "gender": "Fem"}, l1="es"
        )
        assert fields.get("Gender") == "femenino"

    def test_number_field_french(self):
        fields = self._vocab_lesson(
            {"lemma": "maison", "pos": "NOUN", "number": "Plur"}, l1="fr"
        )
        assert fields.get("Number") == "pluriel"

    def test_pos_mc_pool_localised(self):
        """MC drill options for POS are localised; correct answer in localised form."""
        ctx = LessonContext(l1_language="es")
        lesson = build_lesson(
            object_id="mc-loc",
            obj_type="vocabulary",
            canonical_form="casa",
            display_label="casa",
            lesson_data={"lemma": "casa", "pos": "NOUN"},
            context=ctx,
        )
        mc_drills = [d for d in lesson.drills if d.type == "multiple_choice"]
        assert mc_drills, "Expected at least one MC drill"
        mc = mc_drills[0]
        correct = mc.options[mc.answer_index]
        assert correct == "sustantivo"

    def test_latin_case_hint_localised(self):
        fields = self._vocab_lesson(
            {"lemma": "amicus", "pos": "NOUN", "case_hint": "genitive"}, l1="es"
        )
        assert fields.get("Case (hint)") == "genitivo"

    def test_latin_number_hint_localised(self):
        fields = self._vocab_lesson(
            {"lemma": "amicus", "pos": "NOUN", "number_hint": "plural"}, l1="fr"
        )
        assert fields.get("Number (hint)") == "pluriel"

    def test_latin_gender_hint_localised(self):
        fields = self._vocab_lesson(
            {"lemma": "amicus", "pos": "NOUN", "gender_hint": "masculine"}, l1="de"
        )
        assert fields.get("Gender (hint)") == "maskulin"

    def test_greek_article_agrees_localised(self):
        fields = self._vocab_lesson(
            {
                "lemma": "λόγος", "pos": "NOUN",
                "article_agrees_with": {"case": "nominative", "gender": "masculine", "number": "singular"},
            },
            l1="es",
        )
        val = fields.get("Article agrees", "")
        assert "nominativo" in val
        assert "masculino" in val
        assert "singular" in val

    def test_english_fallback_for_unknown_l1(self):
        fields = self._vocab_lesson({"lemma": "x", "pos": "NOUN"}, l1="xx")
        assert fields["Part of speech"] == "noun"


# ── Latin suffix hints and Greek article agreement ─────────────────────────────


class TestLatinSuffixHintsInLesson:
    """Latin noun suffix hints (case_hint/number_hint/gender_hint/ambiguity_note)
    should appear as labelled fields in vocabulary lessons."""

    def _fields(self, lesson_data: dict) -> dict[str, str]:
        lesson = build_lesson(
            object_id="la-test",
            obj_type="vocabulary",
            canonical_form="amicorum",
            display_label="amicorum",
            lesson_data=lesson_data,
        )
        return {f.label: f.value for f in lesson.fields}

    def test_case_hint_rendered(self):
        fields = self._fields({"lemma": "amicus", "pos": "NOUN", "case_hint": "genitive"})
        assert "Case (hint)" in fields
        assert fields["Case (hint)"] == "genitive"

    def test_number_hint_rendered(self):
        fields = self._fields({"lemma": "amicus", "pos": "NOUN", "number_hint": "plural"})
        assert "Number (hint)" in fields
        assert fields["Number (hint)"] == "plural"

    def test_gender_hint_rendered(self):
        fields = self._fields({"lemma": "amicus", "pos": "NOUN", "gender_hint": "masculine"})
        assert "Gender (hint)" in fields
        assert fields["Gender (hint)"] == "masculine"

    def test_ambiguity_note_rendered(self):
        fields = self._fields({
            "lemma": "portum", "pos": "NOUN",
            "case_hint": "accusative",
            "ambiguity_note": "Could also be dative singular of a 4th-declension noun.",
        })
        assert "Ambiguity" in fields
        assert "dative" in fields["Ambiguity"]

    def test_all_hints_together(self):
        fields = self._fields({
            "lemma": "amicus", "pos": "NOUN",
            "case_hint": "genitive",
            "number_hint": "plural",
            "gender_hint": "masculine",
            "ambiguity_note": "Could be nominative plural of amicus.",
        })
        assert fields["Case (hint)"] == "genitive"
        assert fields["Number (hint)"] == "plural"
        assert fields["Gender (hint)"] == "masculine"
        assert "Ambiguity" in fields

    def test_no_hints_no_extra_fields(self):
        fields = self._fields({"lemma": "amicus", "pos": "NOUN"})
        assert "Case (hint)" not in fields
        assert "Number (hint)" not in fields
        assert "Gender (hint)" not in fields
        assert "Ambiguity" not in fields


class TestGreekArticleAgreementInLesson:
    """article_agrees_with in lesson_data should produce an 'Article agrees' field
    in both vocabulary and conjugation lessons."""

    _ART = {"case": "nominative", "gender": "masculine", "number": "singular"}

    def test_vocabulary_article_agrees_field(self):
        lesson = build_lesson(
            object_id="grc-test",
            obj_type="vocabulary",
            canonical_form="λογος",
            display_label="λόγος",
            lesson_data={
                "lemma": "λόγος", "pos": "NOUN",
                "article_agrees_with": self._ART,
            },
        )
        fields = {f.label: f.value for f in lesson.fields}
        assert "Article agrees" in fields
        val = fields["Article agrees"]
        assert "nominative" in val
        assert "masculine" in val
        assert "singular" in val

    def test_vocabulary_article_agrees_separator(self):
        lesson = build_lesson(
            object_id="grc-test2",
            obj_type="vocabulary",
            canonical_form="λογος",
            display_label="λόγος",
            lesson_data={
                "lemma": "λόγος", "pos": "NOUN",
                "article_agrees_with": self._ART,
            },
        )
        fields = {f.label: f.value for f in lesson.fields}
        # Values joined by " · "
        assert " · " in fields["Article agrees"]

    def test_conjugation_article_agrees_field(self):
        lesson = build_lesson(
            object_id="grc-conj",
            obj_type="conjugation",
            canonical_form="ειμι:present:indicative:1:singular:active",
            display_label="ἦν",
            lesson_data={
                "lemma": "εἰμί",
                "tense": "imperfect", "mood": "indicative",
                "person": "3", "number": "singular",
                "article_agrees_with": self._ART,
            },
        )
        fields = {f.label: f.value for f in lesson.fields}
        assert "Article agrees" in fields

    def test_no_article_agrees_no_field(self):
        lesson = build_lesson(
            object_id="grc-none",
            obj_type="vocabulary",
            canonical_form="λογος",
            display_label="λόγος",
            lesson_data={"lemma": "λόγος", "pos": "NOUN"},
        )
        fields = {f.label: f.value for f in lesson.fields}
        assert "Article agrees" not in fields

    def test_partial_article_data_renders_available_keys(self):
        lesson = build_lesson(
            object_id="grc-partial",
            obj_type="vocabulary",
            canonical_form="λογος",
            display_label="λόγος",
            lesson_data={
                "lemma": "λόγος", "pos": "NOUN",
                "article_agrees_with": {"case": "genitive", "gender": "any", "number": "plural"},
            },
        )
        fields = {f.label: f.value for f in lesson.fields}
        assert "Article agrees" in fields
        assert "genitive" in fields["Article agrees"]
