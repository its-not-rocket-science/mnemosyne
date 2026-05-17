"""Persistence service for parsed text, canonical objects, and source documents.

Extracted from backend/api/routes/ingest.py to allow reuse by the offline
corpus build pipeline without going through the FastAPI route layer.

Public API
----------
persist_ingest                 — single-chunk convenience wrapper (POST /ingest)
create_source_document_row     — insert SourceDocumentRow, flush only
persist_chunk                  — persist one parsed chunk, flush only
create_source_progression_row  — insert SourceProgressionRow, flush only
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    CanonicalObjectRow,
    ObjectRelationRow,
    ParsedText,
    Sentence,
    SentenceObjectRow,
    SourceChunkRow,
    SourceDocumentRow,
    SourceProgressionRow,
    UserKnowledgeRow,
)
from backend.parsing.canonical import canonical_object_id
from backend.schemas.parse import (
    CandidateObject,
    CandidateSentenceResult,
    SentenceResult,
)
from backend.srs.knowledge import DEFAULT_USER_ID

logger = logging.getLogger(__name__)


async def create_source_document_row(
    db: AsyncSession,
    *,
    source_document_id: str,
    language: str,
    content_type: str,
    char_count: int,
    script_hint: str | None,
    title: str | None = None,
    author: str | None = None,
    source_url: str | None = None,
    filename: str | None = None,
) -> None:
    """Insert a SourceDocumentRow and flush (does not commit)."""
    db.add(SourceDocumentRow(
        id=source_document_id,
        language=language,
        content_type=content_type,
        title=title,
        author=author,
        source_url=source_url,
        filename=filename,
        char_count=char_count,
        script_hint=script_hint,
    ))
    await db.flush()


async def persist_chunk(
    db: AsyncSession,
    *,
    source_document_id: str,
    language: str,
    chunk_index: int,
    char_start: int,
    char_end: int,
    chunk_text: str,
    source_url: str | None,
    candidate_results: list[CandidateSentenceResult],
    sentences: list[SentenceResult],
    uuid_to_candidate: dict[str, tuple[str, CandidateObject]],
    user_id: str = DEFAULT_USER_ID,
) -> None:
    """Persist one parsed chunk. Flush but do not commit.

    Writes: ParsedText, Sentence rows, CanonicalObjectRows (upsert),
    UserKnowledgeRows (seed/update last_seen), SentenceObjectRows,
    ObjectRelationRows (upsert), SourceChunkRow.
    """
    now = datetime.now(UTC)

    # ParsedText — audit record for this parse run.
    parsed = ParsedText(
        language=language,
        source_text=chunk_text,
        source_url=source_url,
        user_id=user_id,
    )
    db.add(parsed)
    await db.flush()

    # Sentence rows.
    sentence_rows: list[Sentence] = []
    for pos, result in enumerate(sentences):
        row = Sentence(parsed_text_id=parsed.id, position=pos, text=result.text)
        db.add(row)
        sentence_rows.append(row)
    await db.flush()

    # Upsert canonical objects.
    all_ids = list(uuid_to_candidate.keys())
    if all_ids:
        result_q = await db.execute(
            select(CanonicalObjectRow).where(CanonicalObjectRow.id.in_(all_ids))
        )
        existing: dict[str, CanonicalObjectRow] = {
            row.id: row for row in result_q.scalars()
        }
    else:
        existing = {}

    for obj_id, (canonical_form, cand) in uuid_to_candidate.items():
        if obj_id in existing:
            row = existing[obj_id]
            row.display_label = cand.label
            row.lesson_data = cand.lesson_data
            row.confidence = cand.confidence
            if cand.surface_form:
                current = list(row.surface_forms or [])
                if cand.surface_form not in current:
                    row.surface_forms = current + [cand.surface_form]
        else:
            db.add(CanonicalObjectRow(
                id=obj_id,
                language=language,
                type=cand.type,
                canonical_form=canonical_form,
                display_label=cand.label,
                surface_forms=[cand.surface_form] if cand.surface_form else [],
                lesson_data=cand.lesson_data,
                confidence=cand.confidence,
            ))
    await db.flush()

    # Seed UserKnowledge for new objects; update last_seen for existing.
    if all_ids:
        uk_result = await db.execute(
            select(UserKnowledgeRow).where(
                UserKnowledgeRow.user_id == user_id,
                UserKnowledgeRow.object_id.in_(all_ids),
            )
        )
        existing_uk: dict[str, UserKnowledgeRow] = {
            row.object_id: row for row in uk_result.scalars()
        }
        for obj_id in all_ids:
            if obj_id in existing_uk:
                existing_uk[obj_id].last_seen = now
            else:
                db.add(UserKnowledgeRow(
                    user_id=user_id,
                    object_id=obj_id,
                    language=language,
                    fsrs_state=None,
                    mastery_score=0.0,
                    first_seen=now,
                    last_seen=now,
                    total_reviews=0,
                    due_at=now,
                ))

    # Sentence–object join rows.
    for sent_row, sent_result in zip(sentence_rows, sentences):
        for pos, lo in enumerate(sent_result.learnable_objects):
            db.add(SentenceObjectRow(
                sentence_id=sent_row.id,
                object_id=lo.id,
                position=pos,
            ))

    # Upsert object relations.
    desired_relations: set[tuple[str, str, str]] = set()
    for cand_result in candidate_results:
        for cand in cand_result.candidates:
            src_id = canonical_object_id(language, cand.type, cand.canonical_form)
            for hint in cand.relation_hints:
                tgt_id = canonical_object_id(
                    language, hint.target_type, hint.target_canonical_form
                )
                if tgt_id not in uuid_to_candidate:
                    continue
                desired_relations.add((src_id, tgt_id, hint.relation_type))

    if desired_relations:
        src_ids = list({r[0] for r in desired_relations})
        rel_q = await db.execute(
            select(ObjectRelationRow).where(ObjectRelationRow.source_id.in_(src_ids))
        )
        existing_rels: set[tuple[str, str, str]] = {
            (r.source_id, r.target_id, r.relation_type) for r in rel_q.scalars()
        }
        for triple in desired_relations:
            if triple not in existing_rels:
                db.add(ObjectRelationRow(
                    source_id=triple[0],
                    target_id=triple[1],
                    relation_type=triple[2],
                ))

    # SourceChunk — links SourceDocument to this parse run.
    db.add(SourceChunkRow(
        source_document_id=source_document_id,
        parsed_text_id=parsed.id,
        chunk_index=chunk_index,
        char_start=char_start,
        char_end=char_end,
    ))
    await db.flush()


async def create_source_progression_row(
    db: AsyncSession,
    *,
    user_id: str,
    source_document_id: str,
    sentences_total: int,
) -> None:
    """Insert a SourceProgressionRow and flush (does not commit)."""
    db.add(SourceProgressionRow(
        user_id=user_id,
        source_document_id=source_document_id,
        next_position=0,
        sentences_total=sentences_total,
        avg_comprehension=0.0,
        completion_fraction=0.0,
    ))
    await db.flush()


async def persist_ingest(
    db: AsyncSession,
    *,
    language: str,
    content_type: str,
    normalized_text: str,
    script_hint: str | None,
    source_document_id: str,
    candidate_results: list[CandidateSentenceResult],
    sentences: list[SentenceResult],
    uuid_to_candidate: dict[str, tuple[str, CandidateObject]],
    title: str | None = None,
    author: str | None = None,
    source_url: str | None = None,
    filename: str | None = None,
    user_id: str = DEFAULT_USER_ID,
) -> None:
    """Single-chunk ingest convenience wrapper. Commits at end.

    Used by POST /ingest for single-passage submissions.  For multi-chunk
    corpus builds, call create_source_document_row / persist_chunk /
    create_source_progression_row directly and manage the commit yourself.
    """
    await create_source_document_row(
        db,
        source_document_id=source_document_id,
        language=language,
        content_type=content_type,
        char_count=len(normalized_text),
        script_hint=script_hint,
        title=title,
        author=author,
        source_url=source_url,
        filename=filename,
    )
    await persist_chunk(
        db,
        source_document_id=source_document_id,
        language=language,
        chunk_index=0,
        char_start=0,
        char_end=len(normalized_text),
        chunk_text=normalized_text,
        source_url=source_url,
        candidate_results=candidate_results,
        sentences=sentences,
        uuid_to_candidate=uuid_to_candidate,
        user_id=user_id,
    )
    await create_source_progression_row(
        db,
        user_id=user_id,
        source_document_id=source_document_id,
        sentences_total=len(sentences),
    )
    await db.commit()
