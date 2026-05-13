from __future__ import annotations

from typing import Any, Literal

from backend.lesson.practice_hooks import hooks_for_language
from backend.schemas.lesson import LessonField, LessonResponse, PracticeActivity


ActivityType = Literal[
    "comprehension_questions",
    "sentence_level_vocabulary_recall",
    "cloze_completion",
    "term_to_meaning_matching",
    "sentence_recombination",
    "transformation_drills",
    "short_retell_prompts",
    "notice_the_pattern",
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

    hooks = hooks_for_language(lesson.language_code)
    target_term = hooks.normalize_term(terms[0] if terms else lesson.title)
    sentence_basis = _sentence_for_term(lesson.examples, target_term) or text_basis
    comprehension_checks = _build_comprehension_checks(lesson, difficulty, sentence_basis, target_term)
    fb = hooks.feedback_text
    activities: list[PracticeActivity] = [
        *comprehension_checks,
        _activity(
            "sentence_level_vocabulary_recall", lesson, difficulty, target_term,
            prompt=f"Type the highlighted term that best completes this sentence context: {sentence_basis}",
            expected=target_term,
            alternatives=hooks.answer_variants(target_term, _first_field_value(lesson.fields, "Lemma")),
            feedback=fb("sentence_level_vocabulary_recall", "If recall is hard, rehearse the example sentence aloud once, then retry."),
        ),
        _activity(
            "cloze_completion", lesson, difficulty, target_term,
            prompt=hooks.cloze_prompt(sentence_basis, target_term),
            expected=target_term,
            alternatives=hooks.answer_variants(target_term, _first_field_value(lesson.fields, "Lemma")),
            feedback=fb("cloze_completion", "Use agreement/tense cues from surrounding words to fill the blank."),
        ),
        _activity(
            "term_to_meaning_matching", lesson, difficulty, target_term,
            prompt=f"Match '{target_term}' to its meaning.",
            expected=_first_field_value(lesson.fields, "Translation") or _first_field_value(lesson.fields, "Gloss") or lesson.explanation,
            alternatives=hooks.distractors(target_term, lesson.explanation, text_basis),
            feedback=fb("term_to_meaning_matching", "Prioritize contextual meaning from this lesson, not every dictionary sense."),
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

    activities.extend(_build_pattern_drills(lesson, difficulty, anns, lesson.examples, lp, hooks.detect_pattern))

    return activities




def _build_pattern_drills(
    lesson: LessonResponse,
    difficulty: str,
    annotations: list[str],
    examples: list[str],
    learner_progress: dict[str, Any],
    detect_pattern: Any,
) -> list[PracticeActivity]:
    pattern = detect_pattern(annotations)
    if not pattern:
        return []

    matching_examples = [s for s in examples if pattern.lower() in s.lower()]
    if len(matching_examples) < 2:
        return []

    contrast = next((s for s in examples if s not in matching_examples), matching_examples[0])
    progress_hint = ""
    if learner_progress.get("pattern_progress_supported"):
        progress_hint = " Your result can update this pattern's progress."

    base_feedback = f"Pattern '{pattern}' marks a meaning choice in context; notice how it changes interpretation rather than isolated grammar.{progress_hint}"

    return [
        _activity(
            "notice_the_pattern", lesson, difficulty, pattern,
            prompt=(
                f"Notice the pattern: '{pattern}'. Which sentence uses it? "
                f"A) {matching_examples[0]} B) {contrast}"
            ),
            expected=matching_examples[0],
            alternatives=[contrast],
            feedback=base_feedback,
        ),
        _activity(
            "notice_the_pattern", lesson, difficulty, pattern,
            prompt=(
                f"Highlight the repeated structure '{pattern}' in these examples: "
                f"{matching_examples[0]} | {matching_examples[1]}"
            ),
            expected=pattern,
            alternatives=[matching_examples[0], matching_examples[1]],
            feedback=f"The repeated structure '{pattern}' signals a recurring meaning relationship in the passage.",
        ),
        _activity(
            "notice_the_pattern", lesson, difficulty, pattern,
            prompt=f"Compare: '{matching_examples[0]}' vs '{contrast}'. What changed in meaning when '{pattern}' appears?",
            expected=f"{pattern} adds a distinct meaning nuance in context.",
            alternatives=["No meaning change", "Only punctuation changed"],
            feedback=f"Tie your answer to comprehension: '{pattern}' changes how the message is understood.",
        ),
    ]


def _detect_pattern_from_annotations(annotations: list[str]) -> str | None:
    for annotation in annotations:
        tokens = [tok.strip(".,;:!?()[]{}\"'") for tok in annotation.split()]
        counts: dict[str, int] = {}
        for tok in tokens:
            low = tok.lower()
            if len(low) < 2:
                continue
            counts[low] = counts.get(low, 0) + 1
        repeated = [tok for tok, count in counts.items() if count > 1]
        if repeated:
            return repeated[0]
    return None

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
