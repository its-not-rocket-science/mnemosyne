"""Confusion pair tracking.

Records which items a learner confuses with each other and surfaces them
for targeted contrast drilling.  Confusion is recorded when a review is
submitted with quality < 3 and a ``wrong_answer`` label is provided.

Contrast scheduling
───────────────────
After each confusion event, ``next_contrast_at`` is set 2 days ahead.
The weakness endpoint surfaces objects where this date is in the past
so the UI can prompt contrast drills before the next regular FSRS review.

Database strategy
─────────────────
Uses a simple SELECT-then-INSERT/UPDATE pattern rather than a PostgreSQL-
specific UPSERT so the same code works in SQLite (tests) and PostgreSQL
(production).  Concurrent confusion events for the same (user, object,
confused_with) triplet may occasionally produce duplicate inserts in high-
concurrency scenarios, but this is harmless — the confusion_count would
be slightly off, not a correctness issue.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import ConfusionPairRow

logger = logging.getLogger(__name__)

CONTRAST_SCHEDULE_DAYS: int = 2


async def record_confusion(
    db: AsyncSession,
    user_id: str,
    object_id: str,
    wrong_answer: str,
    now: datetime | None = None,
) -> None:
    """Upsert a confusion pair record when a learner picks the wrong answer.

    Silently no-ops when ``wrong_answer`` is empty or ``object_id`` is absent.
    DB errors are caught and logged as warnings — confusion tracking is a
    non-critical enrichment layer, not a required review path.
    """
    if not wrong_answer or not object_id:
        return
    now = now or datetime.now(UTC)
    next_contrast = now + timedelta(days=CONTRAST_SCHEDULE_DAYS)
    truncated = wrong_answer[:500]

    try:
        result = await db.execute(
            select(ConfusionPairRow).where(
                ConfusionPairRow.user_id == user_id,
                ConfusionPairRow.object_id == object_id,
                ConfusionPairRow.confused_with == truncated,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            db.add(ConfusionPairRow(
                user_id=user_id,
                object_id=object_id,
                confused_with=truncated,
                confusion_count=1,
                last_confused_at=now,
                next_contrast_at=next_contrast,
            ))
        else:
            row.confusion_count += 1
            row.last_confused_at = now
            row.next_contrast_at = next_contrast
        await db.commit()
    except Exception:
        logger.warning(
            "Confusion tracking failed for object %r user %r", object_id, user_id,
            exc_info=True,
        )
        try:
            await db.rollback()
        except Exception:
            pass


async def get_confusion_pairs(
    db: AsyncSession,
    user_id: str,
    object_id: str,
    limit: int = 5,
) -> list[ConfusionPairRow]:
    """Return the top ``limit`` confusion pairs for this (user, object).

    Ordered by confusion_count descending so the most persistent confusions
    appear first.
    """
    try:
        result = await db.execute(
            select(ConfusionPairRow)
            .where(
                ConfusionPairRow.user_id == user_id,
                ConfusionPairRow.object_id == object_id,
            )
            .order_by(ConfusionPairRow.confusion_count.desc())
            .limit(limit)
        )
        return list(result.scalars())
    except Exception:
        logger.warning(
            "Confusion pairs query failed for object %r", object_id, exc_info=True
        )
        return []
