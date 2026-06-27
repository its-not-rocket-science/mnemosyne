"""Corpus statistics gathered from the database."""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import (
    CanonicalObjectRow,
    ParsedText,
    Sentence,
    SourceDocumentRow,
)
from backend.parsing.plugin_loader import PluginRegistry


@dataclass
class LanguageStats:
    language: str
    display_name: str
    documents: int = 0
    sentences: int = 0
    objects: int = 0
    object_types: dict[str, int] = field(default_factory=dict)


@dataclass
class CorpusStats:
    total_documents: int = 0
    total_sentences: int = 0
    total_objects: int = 0
    by_language: list[LanguageStats] = field(default_factory=list)
    languages_in_manifest_but_not_db: list[str] = field(default_factory=list)


async def generate_stats(
    db: AsyncSession,
    registry: PluginRegistry,
    manifest_languages: list[str] | None = None,
) -> CorpusStats:
    """Query the DB for corpus coverage statistics.

    Args:
        db:                   Async DB session.
        registry:             Loaded plugin registry (for display names).
        manifest_languages:   Language codes found in the manifest.  Missing
                              ones are reported in the output.

    Returns:
        CorpusStats aggregated per language.
    """
    stats = CorpusStats()
    supported = registry.supported_languages()

    # Documents per language.
    doc_q = await db.execute(
        select(SourceDocumentRow.language, func.count(SourceDocumentRow.id))
        .where(SourceDocumentRow.content_type == "corpus")
        .group_by(SourceDocumentRow.language)
    )
    docs_by_lang: dict[str, int] = {row[0]: row[1] for row in doc_q}

    # Sentences per language (via ParsedText join).
    sent_q = await db.execute(
        select(ParsedText.language, func.count(Sentence.id))
        .join(Sentence, Sentence.parsed_text_id == ParsedText.id)
        .group_by(ParsedText.language)
    )
    sents_by_lang: dict[str, int] = {row[0]: row[1] for row in sent_q}

    # Objects per language.
    obj_q = await db.execute(
        select(
            CanonicalObjectRow.language,
            CanonicalObjectRow.type,
            func.count(CanonicalObjectRow.id),
        )
        .group_by(CanonicalObjectRow.language, CanonicalObjectRow.type)
    )
    obj_by_lang_type: dict[str, dict[str, int]] = {}
    for lang, obj_type, count in obj_q:
        obj_by_lang_type.setdefault(lang, {})[obj_type] = count

    all_languages = sorted(set(docs_by_lang) | set(sents_by_lang) | set(obj_by_lang_type))
    for lang in all_languages:
        caps = supported.get(lang)
        display_name = caps.display_name if caps else lang
        lang_obj_types = obj_by_lang_type.get(lang, {})
        lang_stats = LanguageStats(
            language=lang,
            display_name=display_name,
            documents=docs_by_lang.get(lang, 0),
            sentences=sents_by_lang.get(lang, 0),
            objects=sum(lang_obj_types.values()),
            object_types=lang_obj_types,
        )
        stats.by_language.append(lang_stats)
        stats.total_documents += lang_stats.documents
        stats.total_sentences += lang_stats.sentences
        stats.total_objects += lang_stats.objects

    if manifest_languages:
        db_langs = {s.language for s in stats.by_language}
        stats.languages_in_manifest_but_not_db = sorted(
            lang for lang in manifest_languages if lang not in db_langs
        )

    return stats
