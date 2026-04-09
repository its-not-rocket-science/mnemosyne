"""Structured lesson and drill schemas.

Lessons are typed, structured objects — not markdown strings — so the
frontend can render each drill type with the appropriate interactive
widget.

Drill types
───────────
  multiple_choice  Prompt + shuffled options.  ``answer_index`` is the
                   index of the correct option in ``options``.
  fill_blank       A sentence with a blank (___).  ``answer`` is the
                   expected response (compared case-insensitively).
  recognition      A claim about the item.  ``correct`` is the ground
                   truth (True = the claim is accurate).
  shadowing        Text for the learner to read aloud; no graded
                   response.

NOTE: ``answer_index``, ``answer``, and ``correct`` are sent to the
client.  This is intentional for a self-study tool — the learner
reveals answers to check their own recall.  A future server-graded mode
would omit these fields from the response.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from backend.schemas.parse import LearnableType


class LessonField(BaseModel):
    """One fact about a learnable object, rendered as a key-value row."""
    label: str
    value: str


class MultipleChoiceDrill(BaseModel):
    type: Literal["multiple_choice"]
    prompt: str
    options: list[str]          # deterministically shuffled
    answer_index: int           # index into options


class FillBlankDrill(BaseModel):
    type: Literal["fill_blank"]
    prompt: str                 # contains ___ where the blank is
    answer: str                 # expected response (case-insensitive match)
    hint: str | None = None


class RecognitionDrill(BaseModel):
    type: Literal["recognition"]
    statement: str              # claim to evaluate
    correct: bool               # True = statement is accurate


class ShadowingDrill(BaseModel):
    type: Literal["shadowing"]
    text: str                   # text to read aloud


# Pydantic v2 discriminated union — serialises/deserialises via "type" field.
Drill = Annotated[
    MultipleChoiceDrill | FillBlankDrill | RecognitionDrill | ShadowingDrill,
    Field(discriminator="type"),
]


class LessonResponse(BaseModel):
    """Structured lesson returned by GET /lesson/{object_id}.

    Replaces the old ``content_markdown`` string.  All fields are
    deterministically derived from the canonical object's stored
    ``lesson_data``; no LLM or external call is needed.
    """
    id: str
    type: LearnableType
    title: str
    explanation: str            # one human-readable sentence
    fields: list[LessonField]   # key-value fact rows (lemma, tense, …)
    examples: list[str]         # surface forms for TTS / display
    drills: list[Drill]         # ordered practice items
