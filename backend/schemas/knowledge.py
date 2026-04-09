from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from backend.srs.knowledge import KnowledgeStatus


class KnowledgeObject(BaseModel):
    object_id: str
    status: KnowledgeStatus
    mastery_score: float
    total_reviews: int
    last_seen: datetime
    due_at: datetime


class DashboardResponse(BaseModel):
    """Summary of a learner's knowledge state.

    known          — MASTERED objects.
    weak           — LEARNING and FORGOTTEN objects (seen but not mastered).
    new            — Objects encountered via /parse but never reviewed.
    due_for_review — Objects whose next scheduled review is now or overdue.
    total_objects  — Total canonical objects ever encountered by this user.
    """
    known: list[KnowledgeObject]
    weak: list[KnowledgeObject]
    new: list[KnowledgeObject]
    due_for_review: list[KnowledgeObject]
    total_objects: int
