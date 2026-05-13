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
    assert len(lesson.practice_activities) == 9
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
    assert len(lesson.practice_activities) == 9
    assert all(a.language for a in lesson.practice_activities)
