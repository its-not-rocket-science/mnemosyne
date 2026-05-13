from __future__ import annotations

from typing import Any, Literal

from backend.schemas.lesson import LessonField, LessonResponse, PracticeActivity


ActivityType = Literal[
    "comprehension_questions",
    "sentence_level_vocabulary_recall",
    "cloze_completion",
    "term_to_meaning_matching",
    "sentence_recombination",
    "transformation_drills",
    "short_retell_prompts",
]


def build_practice_activities(
    lesson: LessonResponse,
    *,
    highlighted_terms: list[str] | None = None,
    grammar_notes: list[str] | None = None,
    annotations: list[str] | None = None,
    learner_progress: dict[str, Any] | None = None,
) -> list[PracticeActivity]:
    """Build language-scoped practice activities from lesson content.

    The function is deterministic and only uses data present on the lesson model,
    plus optional enrichment lists (which may be unavailable when plugin support
    is missing). Missing optional data degrades gracefully.
    """
    text_basis = " ".join(lesson.examples) if lesson.examples else lesson.title
    terms = [t for t in (highlighted_terms or _terms_from_fields(lesson.fields)) if t]
    notes = [n for n in (grammar_notes or _grammar_from_lesson_data(lesson.lesson_data)) if n]
    anns = [a for a in (annotations or _annotations_from_lesson_data(lesson.lesson_data)) if a]
    lp = learner_progress or {}
    difficulty = _difficulty_from_progress(lp)

    target_term = terms[0] if terms else lesson.title
    sentence_basis = _sentence_for_term(lesson.examples, target_term) or text_basis
    comprehension_checks = _build_comprehension_checks(lesson, difficulty, sentence_basis, target_term)
    activities: list[PracticeActivity] = [
        *comprehension_checks,
        _activity(
            "sentence_level_vocabulary_recall", lesson, difficulty, target_term,
            prompt=f"Type the highlighted term that best completes this sentence context: {sentence_basis}",
            expected=target_term,
            alternatives=_answer_forms(target_term, _first_field_value(lesson.fields, "Lemma")),
            feedback="If recall is hard, rehearse the example sentence aloud once, then retry.",
        ),
        _activity(
            "cloze_completion", lesson, difficulty, target_term,
            prompt=_cloze_prompt(sentence_basis, target_term),
            expected=target_term,
            alternatives=_answer_forms(target_term, _first_field_value(lesson.fields, "Lemma")),
            feedback="Use agreement/tense cues from surrounding words to fill the blank.",
        ),
        _activity(
            "term_to_meaning_matching", lesson, difficulty, target_term,
            prompt=f"Match '{target_term}' to its meaning.",
            expected=_first_field_value(lesson.fields, "Translation") or _first_field_value(lesson.fields, "Gloss") or lesson.explanation,
            alternatives=[lesson.explanation],
            feedback="Prioritize contextual meaning from this lesson, not every dictionary sense.",
        ),
        _activity(
            "sentence_recombination", lesson, difficulty, target_term,
            prompt=f"Recombine these elements into the lesson sentence: {text_basis}",
            expected=text_basis,
            alternatives=[s for s in lesson.examples if s != text_basis],
            feedback="Keep original meaning and grammar; minor punctuation variation is acceptable.",
        ),
        _activity(
            "transformation_drills", lesson, difficulty, notes[0] if notes else target_term,
            prompt=(f"Transform the sentence using this grammar note: {notes[0]}" if notes else f"Transform '{text_basis}' to a close paraphrase."),
            expected=(notes[0] if notes else text_basis),
            alternatives=notes[1:3] if len(notes) > 1 else [text_basis],
            feedback="Maintain meaning while applying the requested morphology/syntax change.",
        ),
        _activity(
            "short_retell_prompts", lesson, difficulty, target_term,
            prompt=f"Retell this in 1-2 sentences: {text_basis}",
            expected=lesson.explanation,
            alternatives=anns[:2] or [text_basis],
            feedback="Mention key term(s) and the main message; exact wording is flexible.",
        ),
    ]

    return activities


def _build_comprehension_checks(lesson: LessonResponse, difficulty: str, text_basis: str, target_term: str) -> list[PracticeActivity]:
    meaning = _first_field_value(lesson.fields, "Translation") or _first_field_value(lesson.fields, "Gloss") or lesson.explanation
    checks = [
        _activity(
            "comprehension_questions", lesson, difficulty, target_term,
            prompt=f"Who did what? Pick the best meaning for: {text_basis}",
            expected=meaning,
            alternatives=[lesson.explanation, text_basis],
            feedback="Focus on the actor/action meaning before grammar details.",
        ),
        _activity(
            "comprehension_questions", lesson, difficulty, target_term,
            prompt=f"Choose the best summary of this passage: {text_basis}",
            expected=lesson.explanation or meaning,
            alternatives=[meaning, f"Only grammar is being explained here."],
            feedback="A good summary keeps the core message in one short idea.",
        ),
        _activity(
            "comprehension_questions", lesson, difficulty, target_term,
            prompt=f"True or false: this sentence means \"{meaning}\".",
            expected="True",
            alternatives=["False"],
            feedback="Check whether the statement matches the lesson meaning.",
        ),
    ]
    return checks


def _activity(t: ActivityType, lesson: LessonResponse, difficulty: str, target: str, *, prompt: str, expected: str, alternatives: list[str], feedback: str) -> PracticeActivity:
    return PracticeActivity(
        type=t,
        language=lesson.language_code or "und",
        difficulty=difficulty,
        target_term_or_pattern=target,
        prompt=prompt,
        expected_answer=expected,
        acceptable_alternatives=[a for a in alternatives if a and a != expected],
        feedback_text=feedback,
    )


def _terms_from_fields(fields: list[LessonField]) -> list[str]:
    out: list[str] = []
    for f in fields:
        if f.label.lower() in {"lemma", "word", "form"}:
            out.append(f.value)
    return out


def _grammar_from_lesson_data(data: dict[str, Any] | None) -> list[str]:
    if not isinstance(data, dict):
        return []
    notes = data.get("grammar_notes")
    if isinstance(notes, list):
        return [str(n) for n in notes]
    return []


def _annotations_from_lesson_data(data: dict[str, Any] | None) -> list[str]:
    if not isinstance(data, dict):
        return []
    anns = data.get("annotations")
    if isinstance(anns, list):
        return [str(a) for a in anns]
    return []


def _difficulty_from_progress(progress: dict[str, Any]) -> str:
    mastery = progress.get("mastery_score")
    if isinstance(mastery, (float, int)):
        if mastery >= 0.75:
            return "hard"
        if mastery >= 0.4:
            return "medium"
    return "easy"


def _first_field_value(fields: list[LessonField], label: str) -> str | None:
    for f in fields:
        if f.label == label and f.value:
            return f.value
    return None


def _cloze_prompt(text: str, answer: str) -> str:
    if answer and answer in text:
        return text.replace(answer, "____", 1)
    return f"Complete the blank: ____ ({answer})"


def _sentence_for_term(examples: list[str], term: str) -> str | None:
    if not examples:
        return None
    for sentence in examples:
        if term and term.lower() in sentence.lower():
            return sentence
    return examples[0]


def _answer_forms(term: str, lemma: str | None) -> list[str]:
    forms = [term]
    if lemma and lemma not in forms:
        forms.append(lemma)
    return forms
