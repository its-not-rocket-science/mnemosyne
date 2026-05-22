from backend.lesson.generators import build_lesson
from backend.lesson.context import LessonContext


def _build_fixture(language_code: str, label: str, canonical: str, translation: str):
    return build_lesson(
        object_id=f"obj-{language_code}",
        obj_type="vocabulary",
        canonical_form=canonical,
        display_label=label,
        lesson_data={
            "lemma": canonical,
            "pos": "VERB",
            "translation": translation,
            "examples": [f"{label} sample sentence"],
            "grammar_notes": ["Use present tense in neutral register."],
            "annotations": ["Frequent in everyday speech."],
        },
        context=LessonContext(language_code=language_code, language_name=language_code, direction="ltr"),
    )


def test_practice_activities_generated_from_lesson_content_english():
    lesson = _build_fixture("en", "speak", "speak", "to talk")
    assert len(lesson.practice_activities) >= 9
    assert all(a.language == "en" for a in lesson.practice_activities)
    assert len([a for a in lesson.practice_activities if a.type == "comprehension_questions"]) >= 3
    assert any("speak" in a.prompt or "speak" == a.expected_answer for a in lesson.practice_activities)


def test_practice_activities_generated_from_lesson_content_spanish():
    lesson = _build_fixture("es", "hablar", "hablar", "hablar/to speak")
    types = {a.type for a in lesson.practice_activities}
    assert "cloze_completion" in types
    assert "term_to_meaning_matching" in types
    assert all(a.expected_answer for a in lesson.practice_activities)
    cloze = next(a for a in lesson.practice_activities if a.type == "cloze_completion")
    assert "____" in cloze.prompt
    assert "sample sentence" in cloze.prompt
    recall = next(a for a in lesson.practice_activities if a.type == "sentence_level_vocabulary_recall")
    assert "sentence context" in recall.prompt
    assert "hablar" in recall.acceptable_alternatives


def test_practice_activities_generated_from_lesson_content_french():
    lesson = _build_fixture("fr", "parler", "parler", "to speak")
    transform = next(a for a in lesson.practice_activities if a.type == "transformation_drills")
    assert "Use present tense" in transform.prompt or "Use present tense" in transform.expected_answer


def test_missing_plugin_support_falls_back_gracefully():
    lesson = build_lesson(
        object_id="obj-und",
        obj_type="vocabulary",
        canonical_form="token",
        display_label="token",
        lesson_data={"lemma": "token", "pos": "WORD"},
    )
    assert len(lesson.practice_activities) >= 9
    assert all(a.language for a in lesson.practice_activities)


def test_notice_pattern_drills_generated_when_examples_support_pattern():
    lesson = build_lesson(
        object_id="obj-pattern",
        obj_type="vocabulary",
        canonical_form="hablar",
        display_label="hablar",
        lesson_data={
            "lemma": "hablar",
            "pos": "VERB",
            "translation": "to speak",
            "examples": [
                "Yo voy a hablar ahora.",
                "Ella va a hablar mañana.",
                "Nosotros comemos luego.",
            ],
            "annotations": ["Pattern: hablar hablar marks infinitive construction in Spanish"],
        },
        context=LessonContext(language_code="es", language_name="Spanish", direction="ltr"),
    )
    pattern_activities = [a for a in lesson.practice_activities if a.type == "notice_the_pattern"]
    assert len(pattern_activities) == 3
    assert any("Which sentence uses it" in a.prompt for a in pattern_activities)
    assert any("Highlight the repeated structure" in a.prompt for a in pattern_activities)
    assert any("What changed in meaning" in a.prompt for a in pattern_activities)


def test_notice_pattern_drills_not_generated_without_suitable_examples():
    lesson = build_lesson(
        object_id="obj-no-pattern",
        obj_type="vocabulary",
        canonical_form="speak",
        display_label="speak",
        lesson_data={
            "lemma": "speak",
            "pos": "VERB",
            "translation": "to talk",
            "examples": ["I speak now.", "We talk later."],
            "annotations": ["No repeated token here."],
        },
        context=LessonContext(language_code="en", language_name="English", direction="ltr"),
    )
    assert all(a.type != "notice_the_pattern" for a in lesson.practice_activities)


def test_spanish_and_french_use_language_variants_for_answers():
    es = _build_fixture("es", "hablarse", "hablarse", "to speak")
    fr = _build_fixture("fr", "se parler", "se parler", "to speak")
    es_recall = next(a for a in es.practice_activities if a.type == "sentence_level_vocabulary_recall")
    fr_recall = next(a for a in fr.practice_activities if a.type == "sentence_level_vocabulary_recall")
    assert "hablar" in es_recall.acceptable_alternatives
    assert any(v in fr_recall.acceptable_alternatives for v in ["se parler", "parler"])


def test_unsupported_language_uses_safe_default_practice_hooks():
    lesson = _build_fixture("xx", "token", "Token", "token meaning")
    cloze = next(a for a in lesson.practice_activities if a.type == "cloze_completion")
    assert "____" in cloze.prompt
    assert any("Not:" in alt for alt in next(a for a in lesson.practice_activities if a.type == "term_to_meaning_matching").acceptable_alternatives)
