"""Sentence-level spaced-retrieval review API.

Endpoints
─────────
  GET  /review/sentence-items           — due items queue
  GET  /review/sentence-items/stats     — queue stats
  POST /review/sentence-items/mine      — trigger mining from recent parses
  POST /review/sentence-items/{id}/submit — submit quality rating

Sentence review items are independent from the canonical-object review
(POST /review).  They are anchored to specific sentences encountered in
the learner's reading history, providing contextual, sentence-grounded
retrieval practice rather than isolated word/form drills.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_user, get_db_session
from backend.models import (
    CanonicalObjectRow,
    ParsedText,
    Sentence,
    SentenceObjectRow,
    SentenceReviewItemRow,
    SourceChunkRow,
    SourceDocumentRow,
    UserFsrsParamsRow,
    UserSentenceReviewRow,
)
from backend.schemas.sentence_review import (
    MineResult,
    ReviewItemSubmitRequest,
    ReviewItemSubmitResponse,
    ReviewQueueStats,
    SentenceContextResponse,
    SentenceReviewItem,
)
from backend.srs.fsrs import DESIRED_RETENTION, review as fsrs_review
from backend.srs.knowledge import mastery_score
from backend.srs.sentence_miner import mine_sentence

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/review/sentence-items", tags=["sentence-review"])

# Maximum parsed texts to mine per request.
_MINE_MAX_TEXTS: int = 20
# Maximum sentences to process per mine request.
_MINE_MAX_SENTENCES: int = 100


# ── GET /review/sentence-items ────────────────────────────────────────────────


@router.get("", response_model=list[SentenceReviewItem])
async def get_due_items(
    language: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> list[SentenceReviewItem]:
    """Return sentence review items due for review, oldest-due first.

    Items with no ``user_sentence_review`` row are treated as immediately due
    (the learner has never reviewed them).
    """
    now = datetime.now(UTC)

    q = (
        select(
            SentenceReviewItemRow,
            Sentence.text.label("sentence_text"),
            UserSentenceReviewRow.mastery_score.label("u_mastery"),
            UserSentenceReviewRow.total_reviews.label("u_reviews"),
            UserSentenceReviewRow.streak.label("u_streak"),
            UserSentenceReviewRow.due_at.label("u_due_at"),
        )
        .join(Sentence, SentenceReviewItemRow.sentence_id == Sentence.id)
        .outerjoin(
            UserSentenceReviewRow,
            (UserSentenceReviewRow.item_id == SentenceReviewItemRow.id)
            & (UserSentenceReviewRow.user_id == current_user),
        )
        .where(
            or_(
                UserSentenceReviewRow.due_at <= now,
                UserSentenceReviewRow.due_at.is_(None),
            )
        )
    )

    if language:
        q = q.where(SentenceReviewItemRow.language == language)

    q = q.order_by(
        UserSentenceReviewRow.due_at.asc().nulls_first()
    ).limit(limit)

    rows = (await db.execute(q)).all()

    return [
        SentenceReviewItem(
            id=row.SentenceReviewItemRow.id,
            sentence_id=row.SentenceReviewItemRow.sentence_id,
            sentence_text=row.sentence_text,
            language=row.SentenceReviewItemRow.language,
            item_type=row.SentenceReviewItemRow.item_type,
            prompt=row.SentenceReviewItemRow.prompt,
            target_span=row.SentenceReviewItemRow.target_span,
            answer=row.SentenceReviewItemRow.answer,
            distractors=row.SentenceReviewItemRow.distractors or [],
            hint=row.SentenceReviewItemRow.hint,
            grammar_concept=row.SentenceReviewItemRow.grammar_concept,
            cefr_level=row.SentenceReviewItemRow.cefr_level,
            difficulty_score=row.SentenceReviewItemRow.difficulty_score,
            total_reviews=row.u_reviews or 0,
            mastery_score=row.u_mastery or 0.0,
            streak=row.u_streak or 0,
            due_at=row.u_due_at.isoformat() if row.u_due_at else None,
        )
        for row in rows
    ]


# ── GET /review/sentence-items/stats ─────────────────────────────────────────

# NOTE: This route is defined *before* /{item_id}/submit so FastAPI does not
# interpret "stats" as an item_id path segment.


@router.get("/stats", response_model=ReviewQueueStats)
async def get_stats(
    language: str | None = Query(None),
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> ReviewQueueStats:
    """Return queue statistics for the current user."""
    now = datetime.now(UTC)

    base_q = (
        select(SentenceReviewItemRow)
        .outerjoin(
            UserSentenceReviewRow,
            (UserSentenceReviewRow.item_id == SentenceReviewItemRow.id)
            & (UserSentenceReviewRow.user_id == current_user),
        )
    )
    if language:
        base_q = base_q.where(SentenceReviewItemRow.language == language)

    total_rows = (await db.execute(base_q)).scalars().all()
    total = len(total_rows)

    due_q = base_q.where(
        or_(
            UserSentenceReviewRow.due_at <= now,
            UserSentenceReviewRow.due_at.is_(None),
        )
    )
    due_rows = (await db.execute(due_q)).scalars().all()
    due_now = len(due_rows)

    per_type: dict[str, int] = {}
    per_language: dict[str, int] = {}
    for item in total_rows:
        per_type[item.item_type] = per_type.get(item.item_type, 0) + 1
        per_language[item.language] = per_language.get(item.language, 0) + 1

    return ReviewQueueStats(
        due_now=due_now,
        total_items=total,
        per_type=per_type,
        per_language=per_language,
    )


# ── POST /review/sentence-items/mine ─────────────────────────────────────────


@router.post("/mine", response_model=MineResult)
async def trigger_mining(
    language: str | None = Query(None),
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> MineResult:
    """Mine recent parsed texts for the current user and seed review items.

    Scans the most recent ``_MINE_MAX_TEXTS`` parsed texts (optionally filtered
    by language), processes up to ``_MINE_MAX_SENTENCES`` sentences, and
    inserts new review items.  Existing items (same sentence/type/span) are
    skipped.  New items are seeded as due immediately for the current user.
    """
    now = datetime.now(UTC)

    # Load recent parsed texts for this user.
    text_q = (
        select(ParsedText.id, ParsedText.language)
        .where(ParsedText.user_id == current_user)
        .order_by(ParsedText.created_at.desc())
        .limit(_MINE_MAX_TEXTS)
    )
    if language:
        text_q = text_q.where(ParsedText.language == language)

    text_rows = (await db.execute(text_q)).all()
    if not text_rows:
        return MineResult(mined=0, skipped_duplicate=0, sentences_processed=0)

    text_ids = [r.id for r in text_rows]
    lang_by_text = {r.id: r.language for r in text_rows}

    # Load sentences for those texts.
    sent_q = (
        select(Sentence)
        .where(Sentence.parsed_text_id.in_(text_ids))
        .limit(_MINE_MAX_SENTENCES)
    )
    sentences = (await db.execute(sent_q)).scalars().all()

    mined_count = 0
    skip_count = 0

    for sentence in sentences:
        sent_lang = lang_by_text.get(sentence.parsed_text_id, language or "und")

        # Load canonical objects for this sentence.
        obj_q = (
            select(CanonicalObjectRow)
            .join(SentenceObjectRow, CanonicalObjectRow.id == SentenceObjectRow.object_id)
            .where(SentenceObjectRow.sentence_id == sentence.id)
        )
        obj_rows = (await db.execute(obj_q)).scalars().all()

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

        specs = mine_sentence(sentence.id, sentence.text, sent_lang, obj_dicts)

        for spec in specs:
            # Check for existing item (idempotency guard).
            existing = (
                await db.execute(
                    select(SentenceReviewItemRow.id).where(
                        SentenceReviewItemRow.sentence_id == spec.sentence_id,
                        SentenceReviewItemRow.item_type == spec.item_type,
                        SentenceReviewItemRow.target_span == spec.target_span,
                    )
                )
            ).scalar_one_or_none()

            if existing:
                skip_count += 1
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

            # Flush to get the generated ID before creating the user row.
            try:
                await db.flush()
            except Exception:
                await db.rollback()
                logger.warning("Flush failed for mined item, skipping", exc_info=True)
                continue

            user_row = UserSentenceReviewRow(
                user_id=current_user,
                item_id=item_row.id,
                due_at=now,
            )
            db.add(user_row)
            mined_count += 1

    try:
        await db.commit()
    except Exception:
        logger.warning("Commit failed during mining", exc_info=True)
        await db.rollback()
        return MineResult(mined=0, skipped_duplicate=skip_count, sentences_processed=len(sentences))

    return MineResult(
        mined=mined_count,
        skipped_duplicate=skip_count,
        sentences_processed=len(sentences),
    )


# ── GET /review/sentence-items/{item_id}/context ─────────────────────────────

_CONTEXT_WINDOW = 2  # sentences before and after the target


@router.get("/{item_id}/context", response_model=SentenceContextResponse)
async def get_sentence_context(
    item_id: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> SentenceContextResponse:
    """Return up to {_CONTEXT_WINDOW} sentences before and after the review sentence.

    Fetches from the same ``parsed_text`` so context is always from the exact
    passage the learner originally read.  Returns an empty before/after list
    when the sentence is at the start/end of its text, or when no source chunk
    links this text to a saved document.
    """
    item = await db.scalar(
        select(SentenceReviewItemRow).where(SentenceReviewItemRow.id == item_id)
    )
    if item is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Review item not found")

    sent = await db.scalar(
        select(Sentence).where(Sentence.id == item.sentence_id)
    )
    if sent is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Sentence not found")

    # Fetch the surrounding window from the same parsed_text
    lo = max(0, sent.position - _CONTEXT_WINDOW)
    hi = sent.position + _CONTEXT_WINDOW
    neighbors_result = await db.execute(
        select(Sentence)
        .where(
            Sentence.parsed_text_id == sent.parsed_text_id,
            Sentence.position >= lo,
            Sentence.position <= hi,
        )
        .order_by(Sentence.position)
    )
    neighbors = neighbors_result.scalars().all()

    before = [s.text for s in neighbors if s.position < sent.position]
    after  = [s.text for s in neighbors if s.position > sent.position]

    # Best-effort source title via SourceChunkRow → SourceDocumentRow
    source_title: str | None = None
    try:
        chunk = await db.scalar(
            select(SourceChunkRow).where(
                SourceChunkRow.parsed_text_id == sent.parsed_text_id
            ).limit(1)
        )
        if chunk:
            doc = await db.scalar(
                select(SourceDocumentRow).where(
                    SourceDocumentRow.id == chunk.source_document_id
                )
            )
            source_title = doc.title if doc else None
    except Exception as exc:
        logger.warning("get_sentence_context: source title lookup failed: %s", exc)

    return SentenceContextResponse(
        before=before,
        target=sent.text,
        after=after,
        source_title=source_title,
    )


# ── POST /review/sentence-items/{item_id}/submit ──────────────────────────────


@router.post("/{item_id}/submit", response_model=ReviewItemSubmitResponse)
async def submit_item_review(
    item_id: str,
    payload: ReviewItemSubmitRequest,
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> ReviewItemSubmitResponse:
    """Submit a quality rating for a sentence review item.

    Runs FSRS scheduling and updates (or creates) the user's review state.
    Uses the same per-user ``desired_retention`` as the canonical-object
    review endpoint.
    """
    now = datetime.now(UTC)

    user_desired_retention = DESIRED_RETENTION
    try:
        params_row = await db.get(UserFsrsParamsRow, current_user)
        if params_row is not None:
            user_desired_retention = params_row.desired_retention
    except Exception:
        logger.warning("DB fsrs-params load failed for %r", current_user, exc_info=True)

    # Load existing user review state.
    ur: UserSentenceReviewRow | None = None
    try:
        result = await db.execute(
            select(UserSentenceReviewRow).where(
                UserSentenceReviewRow.user_id == current_user,
                UserSentenceReviewRow.item_id == item_id,
            )
        )
        ur = result.scalar_one_or_none()
    except Exception:
        logger.warning("DB user_sentence_review load failed for %r", item_id, exc_info=True)

    prior_state = ur.fsrs_state if ur else None
    score_before = mastery_score(prior_state, now)

    next_days, updated_state = fsrs_review(
        quality=payload.quality,
        state=prior_state,
        now=now,
        desired_retention=user_desired_retention,
    )

    score = mastery_score(updated_state, now)
    due_at = datetime.fromisoformat(updated_state["due_at"])

    new_streak = _next_streak(ur.streak if ur else 0, payload.quality)

    try:
        if ur is None:
            ur = UserSentenceReviewRow(
                user_id=current_user,
                item_id=item_id,
                fsrs_state=updated_state,
                mastery_score=score,
                total_reviews=updated_state["reviews"],
                due_at=due_at,
                last_reviewed_at=now,
                streak=new_streak,
            )
            db.add(ur)
        else:
            ur.fsrs_state = updated_state
            ur.mastery_score = score
            ur.total_reviews = updated_state["reviews"]
            ur.due_at = due_at
            ur.last_reviewed_at = now
            ur.streak = new_streak

        await db.commit()
        await db.refresh(ur)
    except Exception:
        logger.warning("DB persist failed for sentence review item %r", item_id, exc_info=True)
        await db.rollback()

    return ReviewItemSubmitResponse(
        item_id=item_id,
        next_interval_days=next_days,
        mastery_score=round(score, 4),
        mastery_score_before=round(score_before, 4),
        next_review_at=due_at.isoformat(),
        streak=new_streak,
        total_reviews=updated_state["reviews"],
    )


# ── Internal helpers ──────────────────────────────────────────────────────────


def _next_streak(current: int, quality: int) -> int:
    """Increment streak on success (≥ 3); reset to 0 on Again (1)."""
    if quality == 1:
        return 0
    if quality >= 3:
        return current + 1
    return current  # quality 2 (Hard): preserve streak
