"""Sentence mining: extract spaced-retrieval items from parsed sentences.

For each sentence + its canonical objects, this module produces a short list
of SentenceReviewItemSpec instances — the caller is responsible for persisting
them.  All logic is pure (no I/O, no DB), making it straightforward to test.

Item types generated
────────────────────
  cloze                Blank one target word/phrase in the sentence context.
  chunk_recall         Show the stem of an idiomatic chunk; elide the tail.
  grammar_transform    Ask the learner to transform a conjugated verb to a
                       different tense (self-graded production).
  meaning_discrimination
                       Present two confusable forms; learner picks the correct
                       one for the given sentence context.

Filtering / priority rules
──────────────────────────
  · Skip sentences shorter than _MIN_SENTENCE_CHARS or longer than
    _MAX_SENTENCE_CHARS — too short = degenerate context; too long = cognitive
    overload.
  · Skip objects with confidence below _MIN_CONFIDENCE (parser was uncertain).
  · Maximum _MAX_PER_SENTENCE items per sentence to avoid over-mining the
    same context.
  · Objects sorted by descending confidence so the highest-quality candidates
    are picked first when the cap is reached.
  · Idiom objects are tried for chunk_recall before falling through to cloze.
  · Conjugation objects are tried for grammar_transform (rich morphology
    required) and meaning_discrimination (contrast data required) before cloze.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_MAX_PER_SENTENCE: int = 3
_MIN_SENTENCE_CHARS: int = 15
_MAX_SENTENCE_CHARS: int = 280
_MIN_CONFIDENCE: float = 0.50

_CLOZE_ELIGIBLE: frozenset[str] = frozenset({"vocabulary", "conjugation", "idiom"})
_TRANSFORM_ELIGIBLE: frozenset[str] = frozenset({"conjugation"})

# Supported tense transforms: source → target (both directions matter for
# preterite/imperfect distinction, which is a major L2 learning challenge).
_TENSE_TRANSFORMS: dict[str, str] = {
    "present":     "preterite",
    "preterite":   "imperfect",
    "imperfect":   "preterite",
    "future":      "conditional",
    "conditional": "future",
}


# ── Public data types ─────────────────────────────────────────────────────────


@dataclass
class SentenceReviewItemSpec:
    """Blueprint for one review item — not yet persisted to the database."""

    sentence_id: str
    language: str

    #: "cloze" | "chunk_recall" | "grammar_transform" | "meaning_discrimination"
    item_type: str

    #: Human-readable prompt displayed to the learner.
    prompt: str

    #: Word / phrase targeted (used as idempotency key together with
    #: sentence_id + item_type in the DB unique constraint).
    target_span: str

    #: Expected answer (case-insensitive match for cloze / chunk items;
    #: displayed as a reference answer for self-graded transform items).
    answer: str

    distractors: list[str] = field(default_factory=list)
    hint: str | None = None
    grammar_concept: str | None = None
    cefr_level: str | None = None
    difficulty_score: float | None = None
    target_object_ids: list[str] = field(default_factory=list)


# ── Public API ────────────────────────────────────────────────────────────────


def mine_sentence(
    sentence_id: str,
    sentence_text: str,
    language: str,
    objects: list[dict[str, Any]],
    *,
    max_items: int = _MAX_PER_SENTENCE,
) -> list[SentenceReviewItemSpec]:
    """Mine review items from one parsed sentence.

    Parameters
    ----------
    sentence_id:
        UUID of the ``Sentence`` row in the database.
    sentence_text:
        Full sentence text as a plain string.
    language:
        BCP-47 language code (e.g. ``"es"``).
    objects:
        Dicts with at minimum: id, type, display_label, surface_forms (list),
        lesson_data (dict), confidence (float).  Extra keys are ignored.
    max_items:
        Hard cap on items generated from this sentence.

    Returns a (possibly empty) list of ``SentenceReviewItemSpec``.  The list
    contains at most ``max_items`` entries with unique (item_type, target_span)
    pairs.
    """
    if not _sentence_eligible(sentence_text):
        return []

    mining_objs = [_wrap(o) for o in objects]
    # Highest confidence first; idioms before other types at equal confidence.
    mining_objs.sort(key=lambda o: (-o.confidence, 0 if o.obj_type == "idiom" else 1))

    seen_spans: set[tuple[str, str]] = set()  # (item_type, target_span)
    items: list[SentenceReviewItemSpec] = []

    for obj in mining_objs:
        if len(items) >= max_items:
            break
        if obj.confidence < _MIN_CONFIDENCE:
            continue
        if obj.obj_type not in _CLOZE_ELIGIBLE:
            continue

        spec: SentenceReviewItemSpec | None = None

        if obj.obj_type == "idiom":
            spec = _chunk_recall(sentence_id, sentence_text, language, obj)

        # Prefer discrimination when explicit contrast data exists — more targeted.
        if spec is None and obj.obj_type in _TRANSFORM_ELIGIBLE:
            spec = _meaning_discrimination(sentence_id, sentence_text, language, obj)

        if spec is None and obj.obj_type in _TRANSFORM_ELIGIBLE:
            spec = _grammar_transform(sentence_id, sentence_text, language, obj)

        if spec is None:
            spec = _cloze(sentence_id, sentence_text, language, obj)

        if spec is None:
            continue

        key = (spec.item_type, spec.target_span.lower())
        if key in seen_spans:
            continue
        seen_spans.add(key)
        items.append(spec)

    return items


# ── Internal representation ───────────────────────────────────────────────────


@dataclass
class _Obj:
    object_id: str
    obj_type: str
    display_label: str
    surface_forms: list[str]
    lesson_data: dict[str, Any]
    confidence: float
    cefr_level: str | None


def _wrap(o: dict[str, Any]) -> _Obj:
    ld = o.get("lesson_data") or {}
    return _Obj(
        object_id=str(o.get("id", "")),
        obj_type=str(o.get("type", "")),
        display_label=str(o.get("display_label", "")),
        surface_forms=[s for s in (o.get("surface_forms") or []) if s],
        lesson_data=ld,
        confidence=float(o.get("confidence") or 0.0),
        cefr_level=ld.get("cefr_level") or o.get("cefr_level"),
    )


# ── Sentence eligibility ──────────────────────────────────────────────────────


def _sentence_eligible(text: str) -> bool:
    stripped = text.strip()
    return _MIN_SENTENCE_CHARS <= len(stripped) <= _MAX_SENTENCE_CHARS


# ── Span-finding helpers ──────────────────────────────────────────────────────


def _find_span(text: str, candidates: list[str]) -> str | None:
    """Return the first candidate found as a whole word in *text* (case-insensitive).

    Whole-word matching prevents accidentally blanking part of a longer word
    (e.g. "el" inside "ella").  For languages without whitespace boundaries
    (CJK, Arabic) the \\b anchor is effectively a no-op but still correct.
    """
    for form in candidates:
        if not form:
            continue
        # Use word-boundary anchors; escape special regex chars in the form.
        pattern = re.compile(r"(?<!\w)" + re.escape(form) + r"(?!\w)", re.IGNORECASE)
        m = pattern.search(text)
        if m:
            return m.group(0)
    return None


def _blank_first(text: str, span: str) -> str:
    """Replace the first verbatim occurrence of *span* in *text* with ___."""
    return re.sub(re.escape(span), "___", text, count=1, flags=re.IGNORECASE)


def _difficulty(confidence: float, bonus: float = 0.0) -> float:
    return round(min(1.0, max(0.0, 1.0 - confidence + bonus)), 2)


# ── Item generators ───────────────────────────────────────────────────────────


def _cloze(
    sentence_id: str,
    sentence_text: str,
    language: str,
    obj: _Obj,
) -> SentenceReviewItemSpec | None:
    candidates = list(dict.fromkeys(obj.surface_forms))
    if obj.display_label:
        candidates.append(obj.display_label)

    span = _find_span(sentence_text, candidates)
    if not span:
        return None

    blanked = _blank_first(sentence_text, span)
    lemma = obj.lesson_data.get("lemma") or obj.lesson_data.get("noun")
    hint: str | None = None
    if lemma and lemma.lower() != span.lower():
        hint = f"lemma: {lemma}"

    return SentenceReviewItemSpec(
        sentence_id=sentence_id,
        language=language,
        item_type="cloze",
        prompt=blanked,
        target_span=span,
        answer=span,
        hint=hint,
        cefr_level=obj.cefr_level,
        difficulty_score=_difficulty(obj.confidence),
        target_object_ids=[obj.object_id],
    )


def _chunk_recall(
    sentence_id: str,
    sentence_text: str,
    language: str,
    obj: _Obj,
) -> SentenceReviewItemSpec | None:
    """Show the stem of a multi-word expression; blank the completion."""
    label = obj.display_label
    if not label or " " not in label:
        return None

    span = _find_span(sentence_text, [label] + obj.surface_forms)
    if not span:
        return None

    words = span.split()
    if len(words) < 2:
        return None

    cut = max(1, len(words) // 2)
    stem = " ".join(words[:cut])
    tail = " ".join(words[cut:])

    context_snippet = sentence_text[:80].rstrip()
    return SentenceReviewItemSpec(
        sentence_id=sentence_id,
        language=language,
        item_type="chunk_recall",
        prompt=f"{stem} ___",
        target_span=span,
        answer=tail,
        hint=f"Context: {context_snippet}",
        cefr_level=obj.cefr_level,
        difficulty_score=_difficulty(obj.confidence),
        target_object_ids=[obj.object_id],
    )


def _grammar_transform(
    sentence_id: str,
    sentence_text: str,
    language: str,
    obj: _Obj,
) -> SentenceReviewItemSpec | None:
    """Ask the learner to transform a verb to a different tense."""
    ld = obj.lesson_data
    tense = ld.get("tense")
    lemma = ld.get("lemma")
    if not tense or not lemma:
        return None

    target_tense = _TENSE_TRANSFORMS.get(tense)
    if not target_tense:
        return None

    span = _find_span(sentence_text, obj.surface_forms + [obj.display_label])
    if not span:
        return None

    concept = f"{tense}_to_{target_tense}"
    note = ""
    if {tense, target_tense} == {"preterite", "imperfect"}:
        concept = "preterite_imperfect"
        note = "\n(Is the action completed or ongoing?)"

    prompt = (
        f"Rewrite, changing «{span}» ({tense}) → {target_tense}:\n"
        f"{sentence_text}{note}"
    )

    return SentenceReviewItemSpec(
        sentence_id=sentence_id,
        language=language,
        item_type="grammar_transform",
        prompt=prompt,
        target_span=span,
        answer=f"[{lemma} → {target_tense}]",
        grammar_concept=concept,
        hint=f"Lemma: {lemma} | Target: {target_tense}",
        cefr_level=obj.cefr_level,
        difficulty_score=_difficulty(obj.confidence, bonus=0.15),
        target_object_ids=[obj.object_id],
    )


def _meaning_discrimination(
    sentence_id: str,
    sentence_text: str,
    language: str,
    obj: _Obj,
) -> SentenceReviewItemSpec | None:
    """Present two confusable forms; learner picks the correct one for context."""
    contrasts = obj.lesson_data.get("contrasts")
    if not isinstance(contrasts, list) or not contrasts:
        return None

    contrast = contrasts[0]
    form_a = contrast.get("form_a") or obj.display_label
    form_b = contrast.get("form_b")
    note = contrast.get("note", "")
    if not form_b:
        return None

    span = _find_span(sentence_text, [form_a] + obj.surface_forms)
    if not span:
        return None

    prompt = (
        f"Which form fits this context?\n"
        f"«{sentence_text}»\n"
        f"A) {form_a}  B) {form_b}"
    )
    if note:
        prompt += f"\nHint: {note[:100]}"

    return SentenceReviewItemSpec(
        sentence_id=sentence_id,
        language=language,
        item_type="meaning_discrimination",
        prompt=prompt,
        target_span=span,
        answer=form_a,
        distractors=[form_b],
        hint=note[:120] if note else None,
        cefr_level=obj.cefr_level,
        difficulty_score=_difficulty(obj.confidence, bonus=0.10),
        target_object_ids=[obj.object_id],
    )
