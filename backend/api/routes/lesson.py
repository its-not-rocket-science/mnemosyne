from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_current_user, get_db_session, get_plugin_registry
from backend.lesson.context import LessonContext
from backend.lesson.enrichment import LessonEnrichmentContext
from backend.lesson.generators import build_lesson
from backend.lesson.providers import LessonProviders, VocabIndexGlossProvider
from backend.models import (
    CanonicalObjectRow,
    ObjectRelationRow,
    SentenceObjectRow,
    TermProgressRow,
    UserKnowledgeRow,
)
from backend.parsing.plugin_loader import PluginRegistry
from backend.schemas.language import LessonMode, best_lesson_mode
from backend.schemas.lesson import EncounteredVocabularySummary, LessonResponse

_PROVIDERS = LessonProviders(gloss=VocabIndexGlossProvider())
_VOCAB_RELATION_TYPES = frozenset({"conjugation_of", "agreement_of", "nuance_of"})
_SENTENCE_VOCAB_TYPES = frozenset({"vocabulary", "conjugation", "inflection"})

logger = logging.getLogger(__name__)
router = APIRouter(tags=["lesson"])


def _mode_for_language(registry: PluginRegistry, language: str) -> LessonMode:
    """Return the richest lesson mode the plugin for *language* supports.

    Falls back to ``"morphology"`` (the historic default) if the plugin
    pre-dates the capabilities system or if the language is not registered.
    """
    try:
        plugin = registry.get(language)
        caps = getattr(plugin, "capabilities", None)
        if caps is not None:
            return best_lesson_mode(caps.lesson_modes_supported)
    except KeyError:
        pass
    return "morphology"


def _context_for_language(
    registry: PluginRegistry, language: str, l1_language: str = "en"
) -> LessonContext:
    """Build a ``LessonContext`` from the registered plugin's capabilities.

    Falls back to ``LessonContext.unknown()`` when the language is not
    registered or the plugin pre-dates the capabilities system.
    """
    try:
        plugin = registry.get(language)
        caps = getattr(plugin, "capabilities", None)
        if caps is not None:
            return LessonContext.from_capabilities(caps, l1_language=l1_language)
    except KeyError:
        pass
    return LessonContext.unknown(l1_language=l1_language)


async def _load_enrichment(
    db: AsyncSession,
    row: CanonicalObjectRow,
    user_id: str,
) -> LessonEnrichmentContext:
    """Load user-specific progress data for *row* from the database.

    Queries UserKnowledgeRow (FSRS mastery), TermProgressRow (exposure
    count), and ObjectRelationRow (linked vocabulary for
    encountered_vocabulary).  All queries are scoped to *user_id* so
    no cross-user data can leak.
    """
    # FSRS mastery for this exact object.
    uk = await db.get(UserKnowledgeRow, (user_id, row.id))
    mastery_score: float | None = uk.mastery_score if uk is not None else None

    # Exposure count from term-level tracking (keyed on display_label as the term).
    tp = await db.get(TermProgressRow, (user_id, row.language, row.display_label))
    exposure_count: int = (tp.exposure_count or 0) if tp is not None else 0

    # Relation-linked vocabulary objects (lemmas, base forms, …).
    rel_result = await db.execute(
        select(ObjectRelationRow).where(
            ObjectRelationRow.source_id == row.id,
            ObjectRelationRow.relation_type.in_(list(_VOCAB_RELATION_TYPES)),
        )
    )
    rel_rows = list(rel_result.scalars())

    related: list[EncounteredVocabularySummary] = []
    relation_target_ids: set[str] = set()
    if rel_rows:
        target_ids = [r.target_id for r in rel_rows]
        relation_target_ids = set(target_ids)
        tgt_result = await db.execute(
            select(CanonicalObjectRow).where(CanonicalObjectRow.id.in_(target_ids))
        )
        for tgt in tgt_result.scalars():
            ld = tgt.lesson_data or {}
            related.append(EncounteredVocabularySummary(
                form=tgt.display_label,
                lemma=ld.get("lemma") or tgt.canonical_form,
                gloss=ld.get("gloss") or ld.get("translation"),
                pos=ld.get("pos"),
                is_high_frequency=bool(ld.get("is_high_frequency")),
            ))

    # Sentence-context vocabulary — objects co-occurring in the same sentence(s).
    sent_q = await db.execute(
        select(SentenceObjectRow.sentence_id).where(
            SentenceObjectRow.object_id == row.id
        )
    )
    sentence_ids = list(sent_q.scalars())

    if sentence_ids:
        co_q = await db.execute(
            select(SentenceObjectRow.object_id).where(
                SentenceObjectRow.sentence_id.in_(sentence_ids),
                SentenceObjectRow.object_id != row.id,
            )
        )
        # Deduplicate by object_id; exclude objects already covered by relations.
        co_ids = [
            oid for oid in {oid for oid in co_q.scalars()}
            if oid not in relation_target_ids
        ]

        if co_ids:
            co_rows_q = await db.execute(
                select(CanonicalObjectRow).where(
                    CanonicalObjectRow.id.in_(co_ids),
                    CanonicalObjectRow.type.in_(list(_SENTENCE_VOCAB_TYPES)),
                )
            )
            for tgt in co_rows_q.scalars():
                ld = tgt.lesson_data or {}
                related.append(EncounteredVocabularySummary(
                    form=tgt.display_label,
                    lemma=ld.get("lemma") or tgt.canonical_form,
                    gloss=ld.get("gloss") or ld.get("translation"),
                    pos=ld.get("pos"),
                    is_high_frequency=bool(ld.get("is_high_frequency")),
                ))

    return LessonEnrichmentContext(
        mastery_score=mastery_score,
        exposure_count=exposure_count,
        related_vocabulary=related,
    )


@router.get("/lesson/{object_id}", response_model=LessonResponse)
async def get_lesson(
    object_id: str,
    language: str,
    l1_language: str = "en",
    registry: PluginRegistry = Depends(get_plugin_registry),
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> LessonResponse:
    # 1. Database lookup — authoritative when the object has been parsed.
    try:
        row = await db.get(CanonicalObjectRow, object_id)
        if row is not None:
            mode    = _mode_for_language(registry, row.language)
            context = _context_for_language(registry, row.language, l1_language)
            enrichment: LessonEnrichmentContext | None = None
            try:
                enrichment = await _load_enrichment(db, row, current_user)
            except Exception:
                logger.warning(
                    "Enrichment load failed for object %r / user %r",
                    object_id, current_user, exc_info=True,
                )
            return build_lesson(
                object_id=row.id,
                obj_type=row.type,
                canonical_form=row.canonical_form,
                display_label=row.display_label,
                lesson_data=row.lesson_data or {},
                lesson_mode=mode,
                context=context,
                providers=_PROVIDERS,
                enrichment=enrichment,
            )
    except Exception:
        logger.warning("DB lesson lookup failed for %r", object_id, exc_info=True)

    # 2. Fall back to the plugin's in-memory store (populated during /parse).
    try:
        plugin = registry.get(language)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    lo = plugin.get_lesson(object_id)
    if lo is None:
        raise HTTPException(status_code=404, detail="Lesson object not found")

    mode    = _mode_for_language(registry, language)
    context = _context_for_language(registry, language, l1_language)
    return build_lesson(
        object_id=object_id,
        obj_type=lo.type,
        canonical_form=lo.canonical_form,
        display_label=lo.label,
        lesson_data=lo.lesson_data or {},
        lesson_mode=mode,
        context=context,
        providers=_PROVIDERS,
        # No enrichment on plugin fallback path — no DB row to query against.
    )
