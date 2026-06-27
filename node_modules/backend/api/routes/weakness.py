"""Weakness profile and object-level review status endpoints.

GET /weakness/object/{object_id}
    Review status for one canonical object: progression stage, FSRS details,
    confusion pairs.  Used by the Review tab in the detail pane.

GET /weakness/profile/{language}
    Aggregated weakness profile for the current user in one language:
    stage distribution, confusion pairs, concept-type accuracy, high-friction
    items.  Used by the weakness graph component on the dashboard.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_user, get_db_session
from backend.models import (
    CanonicalObjectRow,
    ConfusionPairRow,
    ReviewEventRow,
    UserKnowledgeRow,
)
from backend.schemas.reinforcement import (
    ConfusionPairOut,
    ConceptTypeAccuracy,
    ObjectReviewStatus,
    StageDistribution,
    WeaknessProfile,
)
from backend.srs.concept_scheduler import concept_label
from backend.srs.confusion_tracker import get_confusion_pairs

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/weakness", tags=["weakness"])


@router.get("/object/{object_id}", response_model=ObjectReviewStatus)
async def object_review_status(
    object_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> ObjectReviewStatus:
    """Return review status for a single canonical object."""
    now = datetime.now(UTC)

    # UserKnowledge row — authoritative FSRS state
    uk: UserKnowledgeRow | None = None
    try:
        result = await db.execute(
            select(UserKnowledgeRow).where(
                UserKnowledgeRow.user_id == current_user,
                UserKnowledgeRow.object_id == object_id,
            )
        )
        uk = result.scalar_one_or_none()
    except Exception:
        logger.warning("DB error loading knowledge for %r", object_id, exc_info=True)

    # Canonical object type
    obj_type: str | None = None
    try:
        co = await db.get(CanonicalObjectRow, object_id)
        if co:
            obj_type = co.type
    except Exception:
        pass

    # Confusion pairs
    pairs = await get_confusion_pairs(db, current_user, object_id)
    pair_out = [
        ConfusionPairOut(
            object_id=object_id,
            confused_with=p.confused_with,
            confusion_count=p.confusion_count,
            last_confused_at=p.last_confused_at.isoformat(),
            next_contrast_at=p.next_contrast_at.isoformat() if p.next_contrast_at else None,
        )
        for p in pairs
    ]

    # Unpack FSRS state
    stability: float | None = None
    difficulty: float | None = None
    lapses: int | None = None
    if uk and uk.fsrs_state:
        s = uk.fsrs_state
        stability = s.get("stability")
        difficulty = s.get("difficulty")
        lapses = s.get("lapses")

    due_at_iso: str | None = uk.due_at.isoformat() if uk and uk.due_at else None
    days_until_due: int | None = None
    if uk and uk.due_at:
        due = uk.due_at
        if due.tzinfo is None:
            due = due.replace(tzinfo=UTC)
        delta = (due - now).total_seconds() / 86_400
        days_until_due = round(delta)

    progression_stage = (
        (getattr(uk, "progression_stage", None) or "recognition")
        if uk else "recognition"
    )

    return ObjectReviewStatus(
        object_id=object_id,
        object_type=obj_type,
        progression_stage=progression_stage,
        mastery_score=uk.mastery_score if uk else 0.0,
        total_reviews=uk.total_reviews if uk else 0,
        due_at=due_at_iso,
        days_until_due=days_until_due,
        concept_type_label=concept_label(obj_type),
        stability=stability,
        difficulty=difficulty,
        lapses=lapses,
        confusion_pairs=pair_out,
    )


@router.get("/profile/{language}", response_model=WeaknessProfile)
async def weakness_profile(
    language: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> WeaknessProfile:
    """Return aggregated weakness profile for the current user in one language."""

    # ── Stage distribution ────────────────────────────────────────────────────
    stage_dist = StageDistribution()
    total_items = 0
    try:
        result = await db.execute(
            select(UserKnowledgeRow.progression_stage, func.count())
            .where(
                UserKnowledgeRow.user_id == current_user,
                UserKnowledgeRow.language == language,
            )
            .group_by(UserKnowledgeRow.progression_stage)
        )
        for row_stage, count in result:
            key = (row_stage or "recognition").replace("-", "_")
            if hasattr(stage_dist, key):
                setattr(stage_dist, key, int(count))
            total_items += int(count)
    except Exception:
        logger.warning("Stage distribution query failed", exc_info=True)

    # ── Top confusion pairs ───────────────────────────────────────────────────
    confusion_pairs_out: list[ConfusionPairOut] = []
    try:
        # Join through UserKnowledgeRow to filter by language
        result = await db.execute(
            select(ConfusionPairRow)
            .join(
                UserKnowledgeRow,
                (ConfusionPairRow.user_id == UserKnowledgeRow.user_id)
                & (ConfusionPairRow.object_id == UserKnowledgeRow.object_id),
            )
            .where(
                ConfusionPairRow.user_id == current_user,
                UserKnowledgeRow.language == language,
            )
            .order_by(ConfusionPairRow.confusion_count.desc())
            .limit(10)
        )
        for row in result.scalars():
            confusion_pairs_out.append(ConfusionPairOut(
                object_id=row.object_id,
                confused_with=row.confused_with,
                confusion_count=row.confusion_count,
                last_confused_at=row.last_confused_at.isoformat(),
                next_contrast_at=row.next_contrast_at.isoformat() if row.next_contrast_at else None,
            ))
    except Exception:
        logger.warning("Confusion pairs profile query failed", exc_info=True)

    # ── Concept type accuracy ─────────────────────────────────────────────────
    concept_accuracy: list[ConceptTypeAccuracy] = []
    try:
        result = await db.execute(
            select(ReviewEventRow.concept_type, ReviewEventRow.quality)
            .where(
                ReviewEventRow.user_id == current_user,
                ReviewEventRow.concept_type.isnot(None),
            )
        )
        by_type: dict[str, dict[str, int]] = {}
        for concept_type, quality in result:
            if not concept_type:
                continue
            if concept_type not in by_type:
                by_type[concept_type] = {"total": 0, "correct": 0}
            by_type[concept_type]["total"] += 1
            if quality >= 3:
                by_type[concept_type]["correct"] += 1

        for ct, counts in sorted(by_type.items(), key=lambda x: x[1]["total"], reverse=True):
            total = counts["total"]
            correct = counts["correct"]
            concept_accuracy.append(ConceptTypeAccuracy(
                concept_type=ct,
                correct_count=correct,
                total_reviews=total,
                accuracy=round(correct / total, 3) if total else 0.0,
            ))
    except Exception:
        logger.warning("Concept type accuracy query failed", exc_info=True)

    # ── High-friction items ───────────────────────────────────────────────────
    high_friction: list[str] = []
    try:
        result = await db.execute(
            select(UserKnowledgeRow.object_id)
            .where(
                UserKnowledgeRow.user_id == current_user,
                UserKnowledgeRow.language == language,
                UserKnowledgeRow.mastery_score < 0.50,
                UserKnowledgeRow.total_reviews > 3,
            )
            .order_by(UserKnowledgeRow.mastery_score.asc())
            .limit(10)
        )
        high_friction = [row for (row,) in result]
    except Exception:
        pass

    return WeaknessProfile(
        language=language,
        confusion_pairs=confusion_pairs_out,
        stage_distribution=stage_dist,
        concept_type_accuracy=concept_accuracy,
        high_friction_items=high_friction,
        total_items=total_items,
    )
