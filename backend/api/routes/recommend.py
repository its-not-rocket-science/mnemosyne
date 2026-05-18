"""GET /recommend-text — adaptive sentence recommendations.

Returns sentences from the user's parse history at the difficulty level
appropriate for their current knowledge state, following the i+1
comprehensible-input principle.

Query flow
──────────
1. Load all UserKnowledgeRow for the default user → mastery dict.
2. Compute total_mastered + derive the target difficulty window.
3. Fetch sentences (+ objects + source document metadata) for the requested
   language via a single join.
4. Group objects by sentence in Python; score each sentence using the
   language-specific calibration profile (see difficulty.profiles).
5. Deduplicate identical sentence texts (re-parses create new DB rows).
6. Filter to the target window; fall back to closest-to-centre sentences
   when nothing falls in the window.
7. Sort by closeness to the window centre.
8. For each of the top *limit* sentences, fetch adjacent sentences from
   the same parsed text to build a passage context (one extra query).
9. Return up to *limit* results.

Language fairness
─────────────────
Difficulty scores are calibrated per language via ``difficulty.profiles``.
Morphologically rich languages (German, Russian, Arabic) receive a
grammar_weight_scale < 1.0 so that expected morphological density does
not inflate scores relative to analytic languages.  CJK languages receive
a lower length_max_words and use object count as the word-count proxy
because whitespace tokenisation returns ~1 token for unsegmented text.

Passage context
───────────────
When a recommended sentence was ingested via POST /ingest, it belongs to a
SourceDocument.  The response includes the sentence's title and up to two
adjacent sentences (prev + next in the same parsed text).  This lets the
frontend present a coherent passage rather than isolated flashcard-style
sentences — honouring the authentic-text learning vision.
"""
from __future__ import annotations

import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_user, get_db_session
from backend.difficulty.profiles import get_profile
from backend.difficulty.scorer import (
    DifficultyScore,
    ObjectMastery,
    difficulty_label,
    score_sentence,
    target_difficulty_window,
    user_level_label,
)
from backend.models import (
    CanonicalObjectRow,
    ContentGapSignalRow,
    ParsedText,
    Sentence,
    SentenceObjectRow,
    SourceChunkRow,
    SourceDocumentRow,
    SourceProgressionRow,
    UserKnowledgeRow,
)
from backend.schemas.curriculum import (
    PassageSentence,
    RecommendTextResponse,
    SentenceDifficultyItem,
)
from backend.srs.knowledge import (
    MASTERY_SCORE_THRESHOLD,
    MIN_REVIEWS_FOR_MASTERY,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["curriculum"])

# How many surrounding sentences to include in passage context.
# 1 means one sentence before + the focus + one sentence after.
_PASSAGE_CONTEXT_RADIUS: int = 1


@router.get("/recommend", response_model=RecommendTextResponse)
@router.get("/recommend-text", response_model=RecommendTextResponse)
async def recommend_text(
    language: str,
    limit: int = Query(default=10, ge=1, le=50),
    exclude_source_document_id: str | None = Query(default=None),
    exclude_parsed_text_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> RecommendTextResponse:
    """Return sentences at appropriate difficulty for the current user.

    Sentences are sourced from the user's own parse history.  Each sentence
    is scored by unknown vocabulary ratio, grammar density (calibrated for
    the language's morphological richness), and length (normalised per
    language script family).  The target difficulty window is derived from
    the number of items the user has mastered so far.

    When a sentence belongs to a source document (ingested via POST /ingest),
    its response item includes the document title and a surrounding passage
    for reading context.
    """
    # ── 1. Load mastery map ───────────────────────────────────────────────────
    uk_result = await db.execute(
        select(UserKnowledgeRow).where(UserKnowledgeRow.user_id == current_user)
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

    # Load the language-specific scoring calibration.
    profile = get_profile(language)

    # ── 1b. Load in-progress documents for continuation preference ───────────
    # in_progress maps source_document_id → next_position for documents that
    # have been started (next_position > 0) but not yet completed.
    in_progress: dict[str, int] = {}
    try:
        prog_result = await db.execute(
            select(
                SourceProgressionRow.source_document_id,
                SourceProgressionRow.next_position,
                SourceProgressionRow.sentences_total,
            )
            .select_from(SourceProgressionRow)
            .join(
                SourceDocumentRow,
                SourceDocumentRow.id == SourceProgressionRow.source_document_id,
            )
            .where(
                SourceProgressionRow.user_id == current_user,
                SourceProgressionRow.next_position > 0,
                SourceDocumentRow.language == language,
            )
        )
        for prog_row in prog_result.all():
            # Only track documents that are not yet complete.
            if prog_row.next_position < prog_row.sentences_total:
                in_progress[prog_row.source_document_id] = prog_row.next_position
    except Exception:
        logger.debug("SourceProgressionRow query failed — skipping continuation preference")

    # ── 2. Fetch sentences with objects and source-document metadata ──────────
    # LEFT JOIN to SourceChunkRow and SourceDocumentRow so that sentences
    # ingested via the legacy /parse endpoint (no SourceDocument) still appear.
    rows_result = await db.execute(
        select(
            Sentence.id.label("sentence_id"),
            Sentence.text.label("sentence_text"),
            Sentence.position.label("position"),
            Sentence.parsed_text_id.label("parsed_text_id"),
            CanonicalObjectRow.id.label("object_id"),
            CanonicalObjectRow.type.label("obj_type"),
            SourceDocumentRow.id.label("source_document_id"),
            SourceDocumentRow.title.label("source_title"),
        )
        .select_from(Sentence)
        .join(ParsedText,         Sentence.parsed_text_id == ParsedText.id)
        .join(SentenceObjectRow,  SentenceObjectRow.sentence_id == Sentence.id)
        .join(CanonicalObjectRow, CanonicalObjectRow.id == SentenceObjectRow.object_id)
        .outerjoin(SourceChunkRow,    SourceChunkRow.parsed_text_id == Sentence.parsed_text_id)
        .outerjoin(SourceDocumentRow, SourceDocumentRow.id == SourceChunkRow.source_document_id)
        .where(ParsedText.language == language)
        .where(
            or_(
                SourceDocumentRow.id.is_(None),
                SourceDocumentRow.id != exclude_source_document_id,
            )
            if exclude_source_document_id else True
        )
        .where(
            Sentence.parsed_text_id != exclude_parsed_text_id
            if exclude_parsed_text_id else True
        )
        .order_by(Sentence.id)
    )
    rows = rows_result.all()

    # ── 3. Group objects by sentence; collect position and source metadata ────
    sentence_texts:           dict[str, str]       = {}
    sentence_positions:       dict[str, int]       = {}
    sentence_parsed_text_ids: dict[str, str]       = {}
    sentence_source_doc_ids:  dict[str, str | None] = {}
    sentence_source_titles:   dict[str, str | None] = {}
    sentence_objects:         dict[str, list[ObjectMastery]] = defaultdict(list)

    for row in rows:
        sid = row.sentence_id
        sentence_texts[sid]           = row.sentence_text
        sentence_positions[sid]       = row.position
        sentence_parsed_text_ids[sid] = row.parsed_text_id
        # Outer join may return multiple rows if a sentence maps to several
        # chunks (shouldn't happen, but be defensive with last-write-wins).
        sentence_source_doc_ids[sid]  = row.source_document_id
        sentence_source_titles[sid]   = row.source_title

        ms, rev = mastery.get(row.object_id, (0.0, 0))
        sentence_objects[sid].append(
            ObjectMastery(
                object_id=row.object_id,
                obj_type=row.obj_type,
                mastery_score=ms,
                total_reviews=rev,
            )
        )

    # ── 4. Score sentences (deduplicate identical texts) ─────────────────────
    # For segmented-script languages (CJK), object count is a better proxy
    # for sentence length than whitespace tokenisation.
    use_object_count_for_length = profile.length_max_words < 20

    scored: list[tuple[str, str, DifficultyScore]] = []
    seen_texts: set[str] = set()

    for sent_id, sent_text in sentence_texts.items():
        if sent_text in seen_texts:
            continue
        seen_texts.add(sent_text)

        objs = sentence_objects[sent_id]
        word_hint: int | None = len(objs) if use_object_count_for_length else None

        ds = score_sentence(objs, sent_text, word_count_hint=word_hint, profile=profile)
        if ds.total_objects == 0:
            continue  # punctuation-only sentence — nothing to learn
        scored.append((sent_id, sent_text, ds))

    if not scored:
        logger.warning(
            "content_gap language=%s user=%s has_parsed_texts=%s",
            language, current_user, bool(rows),
        )
        try:
            db.add(ContentGapSignalRow(
                language=language,
                user_id=current_user,
                has_parsed_texts=bool(rows),
            ))
            await db.commit()
        except Exception:
            await db.rollback()
            logger.debug("content_gap signal insert failed — non-fatal")
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
        in_window = sorted(scored, key=lambda t: abs(t[2].difficulty - center))
        logger.debug(
            "recommend_text: no sentences in window [%.2f, %.2f]; "
            "returning %d closest (lang=%s, mastered=%d)",
            window[0], window[1], min(limit, len(in_window)), language, total_mastered,
        )

    # Sort: continuation sentences (from in-progress documents, at or after
    # next_position) come first, then by closeness to the window centre.
    def _sort_key(t: tuple[str, str, DifficultyScore]) -> tuple[int, float]:
        sid, _, ds = t
        src_doc = sentence_source_doc_ids.get(sid)
        if src_doc and src_doc in in_progress:
            next_pos = in_progress[src_doc]
            if sentence_positions.get(sid, 0) >= next_pos:
                return (0, abs(ds.difficulty - center))  # continuation first
        return (1, abs(ds.difficulty - center))

    in_window.sort(key=_sort_key)

    # Drop sentences too close to a better-ranked sentence in the same parsed
    # text.  Two focus sentences within (2 × radius + 1) positions produce
    # overlapping passage windows, so the reader sees the same text twice.
    _min_gap = 2 * _PASSAGE_CONTEXT_RADIUS + 1
    _kept_positions: dict[str, list[int]] = defaultdict(list)
    deduped: list[tuple[str, str, DifficultyScore]] = []
    for _sid, _text, _ds in in_window:
        _ptext = sentence_parsed_text_ids.get(_sid)
        _pos   = sentence_positions.get(_sid, 0)
        if _ptext and any(abs(_pos - _p) < _min_gap for _p in _kept_positions[_ptext]):
            continue
        deduped.append((_sid, _text, _ds))
        if _ptext:
            _kept_positions[_ptext].append(_pos)

    top = deduped[:limit]

    # ── 6. Passage context — one extra query for adjacent sentences ───────────
    # Collect the unique parsed_text_ids from the selected sentences.
    # Sentences without a parsed_text_id (shouldn't happen) are skipped.
    selected_ptext_ids: set[str] = {
        sentence_parsed_text_ids[sid]
        for sid, _, _ in top
        if sid in sentence_parsed_text_ids
    }

    # {parsed_text_id: {position: text}}
    passage_by_ptext: dict[str, dict[int, str]] = defaultdict(dict)
    if selected_ptext_ids:
        try:
            passage_q = await db.execute(
                select(
                    Sentence.parsed_text_id,
                    Sentence.position,
                    Sentence.text,
                )
                .where(Sentence.parsed_text_id.in_(selected_ptext_ids))
                .order_by(Sentence.parsed_text_id, Sentence.position)
            )
            for p_row in passage_q.all():
                passage_by_ptext[p_row.parsed_text_id][p_row.position] = p_row.text
        except Exception:
            logger.debug("Passage context query failed — continuing without context")

    # ── 7. Assemble response items ────────────────────────────────────────────
    result_sentences: list[SentenceDifficultyItem] = []

    for sent_id, text, ds in top:
        ptext_id    = sentence_parsed_text_ids.get(sent_id)
        focus_pos   = sentence_positions.get(sent_id, 0)
        source_doc  = sentence_source_doc_ids.get(sent_id)
        source_ttl  = sentence_source_titles.get(sent_id)

        passage: list[PassageSentence] = []
        if ptext_id and ptext_id in passage_by_ptext:
            pos_map = passage_by_ptext[ptext_id]
            if len(pos_map) > 1:
                # Only bother with passage when there is more than one sentence.
                lo = max(0, focus_pos - _PASSAGE_CONTEXT_RADIUS)
                hi = focus_pos + _PASSAGE_CONTEXT_RADIUS + 1
                for p in range(lo, hi):
                    if p in pos_map:
                        passage.append(PassageSentence(
                            position=p,
                            text=pos_map[p],
                            is_focus=(p == focus_pos),
                        ))

        is_continuation = bool(
            source_doc
            and source_doc in in_progress
            and focus_pos >= in_progress[source_doc]
        )

        result_sentences.append(SentenceDifficultyItem(
            sentence_id=sent_id,
            text=text,
            language=language,
            difficulty=ds.difficulty,
            difficulty_label=difficulty_label(ds.unknown_ratio),
            unknown_ratio=ds.unknown_ratio,
            grammar_score=ds.grammar_score,
            length_score=ds.length_score,
            known_count=ds.known_count,
            unknown_count=ds.unknown_count,
            total_objects=ds.total_objects,
            source_document_id=source_doc,
            source_title=source_ttl,
            passage=passage,
            is_continuation=is_continuation,
        ))

    logger.info(
        "recommend_text lang=%s mastered=%d window=[%.2f,%.2f] returned=%d profile_scale=%.2f",
        language, total_mastered, window[0], window[1],
        len(result_sentences), profile.grammar_weight_scale,
    )

    return RecommendTextResponse(
        sentences=result_sentences,
        target_difficulty_min=window[0],
        target_difficulty_max=window[1],
        user_level=level,
        total_mastered=total_mastered,
        total_seen=total_seen,
    )
