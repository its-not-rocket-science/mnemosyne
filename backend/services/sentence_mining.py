"""Shared sentence-mining service: mine a freshly-persisted parsed text.

Called as a background step after every successful /parse, /parse/jobs, and
/ingest request so that new sentence review items are available immediately
without a separate manual mining call.

The core algorithm is the same as POST /review/sentence-items/mine but scoped
to a single ``parsed_text_id`` rather than scanning the N most-recent texts.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    CanonicalObjectRow,
    Sentence,
    SentenceObjectRow,
    SentenceReviewItemRow,
    UserSentenceReviewRow,
)
from backend.srs.sentence_miner import mine_sentence

logger = logging.getLogger(__name__)


async def mine_parsed_text(
    db: AsyncSession,
    *,
    parsed_text_id: str,
    language: str,
    user_id: str,
    now: datetime | None = None,
) -> tuple[int, int]:
    """Mine sentence review items from a single parsed text.

    Loads all sentences for ``parsed_text_id``, calls ``mine_sentence`` for
    each, and persists new ``SentenceReviewItemRow`` + ``UserSentenceReviewRow``
    pairs (due immediately).  Existing items (same sentence/type/span) are
    skipped for idempotency.

    Parameters
    ----------
    db:
        Active async session.  The function commits on success.
    parsed_text_id:
        Primary key of the ``ParsedText`` row to mine.
    language:
        BCP-47 language code of the parsed text.
    user_id:
        Owner user ID — used for the ``UserSentenceReviewRow``.
    now:
        Review anchor time; defaults to ``datetime.now(UTC)``.

    Returns
    -------
    (mined, skipped_duplicate)
    """
    if now is None:
        now = datetime.now(UTC)

    sentences = (
        await db.execute(
            select(Sentence).where(Sentence.parsed_text_id == parsed_text_id)
        )
    ).scalars().all()

    mined = 0
    skipped = 0

    for sent in sentences:
        obj_rows = (
            await db.execute(
                select(CanonicalObjectRow)
                .join(SentenceObjectRow, CanonicalObjectRow.id == SentenceObjectRow.object_id)
                .where(SentenceObjectRow.sentence_id == sent.id)
            )
        ).scalars().all()

        obj_dicts = [
            {
                "id": o.id,
                "type": o.type,
                "display_label": o.display_label,
                "surface_forms": o.surface_forms or [],
                "lesson_data": o.lesson_data or {},
                "confidence": o.confidence or 0.0,
            }
            for o in obj_rows
        ]

        specs = mine_sentence(sent.id, sent.text, language, obj_dicts)

        for spec in specs:
            existing = await db.scalar(
                select(SentenceReviewItemRow.id).where(
                    SentenceReviewItemRow.sentence_id == spec.sentence_id,
                    SentenceReviewItemRow.item_type == spec.item_type,
                    SentenceReviewItemRow.target_span == spec.target_span,
                )
            )
            if existing is not None:
                skipped += 1
                continue

            item_row = SentenceReviewItemRow(
                sentence_id=spec.sentence_id,
                language=spec.language,
                item_type=spec.item_type,
                prompt=spec.prompt,
                target_span=spec.target_span,
                answer=spec.answer,
                distractors=spec.distractors,
                hint=spec.hint,
                grammar_concept=spec.grammar_concept,
                cefr_level=spec.cefr_level,
                difficulty_score=spec.difficulty_score,
                target_object_ids=spec.target_object_ids,
            )
            db.add(item_row)

            try:
                await db.flush()
            except Exception:
                await db.rollback()
                logger.warning(
                    "mine_parsed_text: flush failed for sentence=%s item_type=%s",
                    spec.sentence_id, spec.item_type, exc_info=True,
                )
                continue

            db.add(UserSentenceReviewRow(
                user_id=user_id,
                item_id=item_row.id,
                due_at=now,
            ))
            mined += 1

    try:
        await db.commit()
    except Exception:
        logger.warning(
            "mine_parsed_text: commit failed for parsed_text_id=%s", parsed_text_id, exc_info=True
        )
        await db.rollback()
        return 0, skipped

    logger.info(
        "mine_parsed_text parsed_text_id=%s lang=%s user=%s mined=%d skipped=%d",
        parsed_text_id, language, user_id, mined, skipped,
    )
    return mined, skipped
