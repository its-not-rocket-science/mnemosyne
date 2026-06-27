"""Privacy-conscious learning analytics service.

Only aggregate, non-identifiable events are recorded (session counts,
feature engagement totals). No text snippets, review answers, or
canonical-form values are stored.

Usage:
    await record_event(db, user_id, "review_session", language="es", count=12)

The caller is responsible for checking analytics_opt_out before calling.
Use ``maybe_record_event`` to have that check done here.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.models import LearningEventRow, UserRow

logger = logging.getLogger(__name__)

_VALID_EVENT_TYPES = frozenset({
    "review_session",
    "text_ingested",
    "recommend_served",
    "practice_drill",
})


async def record_event(
    db: AsyncSession,
    user_id: str,
    event_type: str,
    *,
    language: str | None = None,
    count: int = 1,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Write one LearningEventRow. No opt-out check — caller must gate."""
    if event_type not in _VALID_EVENT_TYPES:
        logger.warning("analytics: unknown event_type %r — skipped", event_type)
        return
    if metadata is not None:
        _sanitize_metadata(metadata)
    try:
        db.add(LearningEventRow(
            user_id=user_id,
            event_type=event_type,
            language=language,
            count=max(1, count),
            metadata_json=metadata,
        ))
        await db.flush()
    except Exception:
        logger.debug("analytics: event write failed — non-fatal", exc_info=True)


async def maybe_record_event(
    db: AsyncSession,
    user_id: str,
    event_type: str,
    *,
    language: str | None = None,
    count: int = 1,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Write event only if the user has not opted out. Non-fatal on any error."""
    try:
        result = await db.execute(
            select(UserRow.analytics_opt_out).where(UserRow.id == user_id)
        )
        row = result.scalar_one_or_none()
        if row is True:
            return
    except Exception:
        logger.debug("analytics: opt-out check failed — skipping event", exc_info=True)
        return
    await record_event(db, user_id, event_type, language=language, count=count, metadata=metadata)


def _sanitize_metadata(meta: dict[str, Any]) -> None:
    """Remove keys that could contain identifiable text. Mutates in place."""
    _BANNED_KEYS = {"text", "sentence", "canonical_form", "surface_form", "answer", "hint"}
    for key in _BANNED_KEYS:
        meta.pop(key, None)


async def delete_user_events(db: AsyncSession, user_id: str) -> int:
    """Delete all learning events for a user (GDPR right-to-erasure support).

    Returns the number of deleted rows.
    """
    from sqlalchemy import delete as sa_delete
    result = await db.execute(
        sa_delete(LearningEventRow).where(LearningEventRow.user_id == user_id)
    )
    await db.flush()
    return result.rowcount
