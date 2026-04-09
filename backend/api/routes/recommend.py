"""GET /recommend-text — adaptive sentence recommendations.

Returns sentences from the user's parse history at the difficulty level
appropriate for their current knowledge state, following the i+1
comprehensible-input principle.

Query flow
──────────
1. Load all UserKnowledgeRow for the default user → mastery dict.
2. Compute total_mastered + derive the target difficulty window.
3. Fetch sentences (+ their canonical objects) for the requested language
   via a single 4-way join.
4. Group objects by sentence in Python; score each sentence.
5. Deduplicate identical sentence texts (re-parses create new DB rows).
6. Filter to the target window; fall back to closest-to-centre sentences
   when nothing falls in the window.
7. Sort by closeness to the window centre; return up to *limit* results.
"""
from __future__ import annotations

import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_db_session
from backend.difficulty.scorer import (
    DifficultyScore,
    ObjectMastery,
    score_sentence,
    target_difficulty_window,
    user_level_label,
)
from backend.models import (
    CanonicalObjectRow,
    ParsedText,
    Sentence,
    SentenceObjectRow,
    UserKnowledgeRow,
)
from backend.schemas.curriculum import RecommendTextResponse, SentenceDifficultyItem
from backend.srs.knowledge import (
    DEFAULT_USER_ID,
    MASTERY_SCORE_THRESHOLD,
    MIN_REVIEWS_FOR_MASTERY,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["curriculum"])


@router.get("/recommend-text", response_model=RecommendTextResponse)
async def recommend_text(
    language: str,
    limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
) -> RecommendTextResponse:
    """Return sentences at appropriate difficulty for the current user.

    Sentences are sourced from the user's own parse history.  Each sentence
    is scored by unknown vocabulary ratio, grammar density, and length.
    The target difficulty window is derived from the number of items the user
    has mastered so far.
    """
    # ── 1. Load mastery map ───────────────────────────────────────────────────
    uk_result = await db.execute(
        select(UserKnowledgeRow).where(UserKnowledgeRow.user_id == DEFAULT_USER_ID)
    )
    mastery: dict[str, tuple[float, int]] = {
        row.object_id: (row.mastery_score or 0.0, row.total_reviews)
        for row in uk_result.scalars()
    }

    total_mastered = sum(
        1
        for ms, rev in mastery.values()
        if ms >= MASTERY_SCORE_THRESHOLD and rev >= MIN_REVIEWS_FOR_MASTERY
    )
    total_seen = len(mastery)

    window = target_difficulty_window(total_mastered)
    level  = user_level_label(total_mastered)

    # ── 2. Fetch sentences with objects ───────────────────────────────────────
    rows_result = await db.execute(
        select(
            Sentence.id.label("sentence_id"),
            Sentence.text.label("sentence_text"),
            CanonicalObjectRow.id.label("object_id"),
            CanonicalObjectRow.type.label("obj_type"),
        )
        .select_from(Sentence)
        .join(ParsedText,        Sentence.parsed_text_id == ParsedText.id)
        .join(SentenceObjectRow, SentenceObjectRow.sentence_id == Sentence.id)
        .join(CanonicalObjectRow, CanonicalObjectRow.id == SentenceObjectRow.object_id)
        .where(ParsedText.language == language)
        .order_by(Sentence.id)
    )
    rows = rows_result.all()

    # ── 3. Group objects by sentence ─────────────────────────────────────────
    sentence_texts: dict[str, str] = {}
    sentence_objects: dict[str, list[ObjectMastery]] = defaultdict(list)

    for row in rows:
        sentence_texts[row.sentence_id] = row.sentence_text
        ms, rev = mastery.get(row.object_id, (0.0, 0))
        sentence_objects[row.sentence_id].append(
            ObjectMastery(
                object_id=row.object_id,
                obj_type=row.obj_type,
                mastery_score=ms,
                total_reviews=rev,
            )
        )

    # ── 4. Score sentences (deduplicate identical texts) ──────────────────────
    scored: list[tuple[str, str, DifficultyScore]] = []  # (id, text, score)
    seen_texts: set[str] = set()

    for sent_id, sent_text in sentence_texts.items():
        if sent_text in seen_texts:
            continue
        seen_texts.add(sent_text)
        ds = score_sentence(sentence_objects[sent_id], sent_text)
        if ds.total_objects == 0:
            continue  # punctuation-only sentence — nothing to learn
        scored.append((sent_id, sent_text, ds))

    if not scored:
        return RecommendTextResponse(
            sentences=[],
            target_difficulty_min=window[0],
            target_difficulty_max=window[1],
            user_level=level,
            total_mastered=total_mastered,
            total_seen=total_seen,
        )

    # ── 5. Filter to target window; fall back to closest ─────────────────────
    center = (window[0] + window[1]) / 2.0

    in_window = [t for t in scored if window[0] <= t[2].difficulty <= window[1]]
    if not in_window:
        # Nothing in window — return closest sentences so the user always gets
        # something actionable rather than an empty recommendation.
        in_window = sorted(scored, key=lambda t: abs(t[2].difficulty - center))
        logger.debug(
            "recommend_text: no sentences in window [%.2f, %.2f]; "
            "returning %d closest (lang=%s, mastered=%d)",
            window[0], window[1], min(limit, len(in_window)), language, total_mastered,
        )

    # Sort within the window by closeness to the centre.
    in_window.sort(key=lambda t: abs(t[2].difficulty - center))

    result_sentences = [
        SentenceDifficultyItem(
            sentence_id=sent_id,
            text=text,
            language=language,
            difficulty=ds.difficulty,
            unknown_ratio=ds.unknown_ratio,
            grammar_score=ds.grammar_score,
            length_score=ds.length_score,
            known_count=ds.known_count,
            unknown_count=ds.unknown_count,
            total_objects=ds.total_objects,
        )
        for sent_id, text, ds in in_window[:limit]
    ]

    logger.info(
        "recommend_text lang=%s mastered=%d window=[%.2f,%.2f] returned=%d",
        language, total_mastered, window[0], window[1], len(result_sentences),
    )

    return RecommendTextResponse(
        sentences=result_sentences,
        target_difficulty_min=window[0],
        target_difficulty_max=window[1],
        user_level=level,
        total_mastered=total_mastered,
        total_seen=total_seen,
    )
