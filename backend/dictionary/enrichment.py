"""Post-parse dictionary and translation enrichment.

After the NLP pipeline has extracted and persisted canonical objects, this
module optionally fetches English glosses from Wiktionary and/or machine
translations from the configured provider, storing the results in
``canonical_objects.lesson_data``.

Fields written
──────────────
``lesson_data["gloss"]``
    English dictionary definition from Wiktionary.  Set by ``enrich_objects``
    when ``ENABLE_DICTIONARY_LOOKUP=true``.

``lesson_data["gloss_attempted"]``
    Boolean sentinel.  Set to ``True`` after any Wiktionary lookup attempt
    (successful or 404).  Left absent on network failures so the next parse
    triggers a retry.

``lesson_data["translation"]``
    Short machine-translated English equivalent.  Set by ``enrich_objects``
    when ``ENABLE_TRANSLATION_ENRICHMENT=true`` and a provider is configured.

``lesson_data["translation_attempted"]``
    Same sentinel pattern as ``gloss_attempted``.

Scope
─────
Only objects of type ``"vocabulary"`` are enriched.  Conjugations, agreements,
case-agreements, and other derived types do not have standalone dictionary or
translation entries at the lemma level.

Concurrency
───────────
A single semaphore ``MAX_CONCURRENT_FETCHES`` caps the total number of
in-flight HTTP requests for both Wiktionary and the translation provider.
"""
from __future__ import annotations

import asyncio
import logging

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dictionary import logeion
from backend.dictionary.wiktionary import fetch_definition
from backend.models import CanonicalObjectRow

logger = logging.getLogger(__name__)

#: Only enrich objects of these types.
ENRICHMENT_TYPES: frozenset[str] = frozenset({"vocabulary"})

#: Maximum number of concurrent HTTP requests per enrichment batch (shared
#: between Wiktionary and translation provider).
MAX_CONCURRENT_FETCHES: int = 5


async def enrich_objects(
    db: AsyncSession,
    object_ids: list[str],
    *,
    enable_gloss: bool = True,
    translation_provider: str = "none",
    translation_api_url: str | None = None,
    translation_api_key: str | None = None,
) -> None:
    """Fetch glosses and/or translations for canonical objects in *object_ids*.

    Silently skips:
    - Objects not in the DB or not in ENRICHMENT_TYPES.
    - Objects whose relevant ``*_attempted`` sentinel is already set.
    - Objects that already have the target field populated.

    Parameters
    ----------
    db:
        Async SQLAlchemy session.  ``db.commit()`` is called after all updates.
    object_ids:
        Canonical object UUIDs to consider.  Typically from one ``/parse`` call.
    enable_gloss:
        When ``True``, fetch Wiktionary glosses for objects without one.
    translation_provider:
        Backend for machine translation: ``"libretranslate"``, ``"mymemory"``,
        or ``"none"`` (disables translation enrichment).
    translation_api_url:
        Override the translation provider's default API URL.
    translation_api_key:
        API key / email for the translation provider (optional for some tiers).
    """
    if not object_ids:
        return

    result = await db.execute(
        select(CanonicalObjectRow).where(
            CanonicalObjectRow.id.in_(object_ids),
            CanonicalObjectRow.type.in_(list(ENRICHMENT_TYPES)),
        )
    )
    rows = result.scalars().all()

    do_translation = translation_provider != "none"

    # Filter rows that still need work.
    pending_gloss = [
        row for row in rows
        if enable_gloss
        and not (row.lesson_data or {}).get("gloss")
        and not (row.lesson_data or {}).get("gloss_attempted")
    ]
    pending_translation = [
        row for row in rows
        if do_translation
        and not (row.lesson_data or {}).get("translation")
        and not (row.lesson_data or {}).get("translation_attempted")
    ]

    if not pending_gloss and not pending_translation:
        return

    sem = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)
    dirty: list[CanonicalObjectRow] = []

    # ── Gloss tasks ───────────────────────────────────────────────────────────

    async def _fetch_gloss(row: CanonicalObjectRow) -> None:
        lang = row.language or ""
        async with sem:
            gloss: str | None = None

            # Wiktionary — primary source for most languages.
            try:
                gloss = await fetch_definition(row.canonical_form, lang)
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "wiktionary HTTP %d lemma=%r lang=%s",
                    exc.response.status_code, row.canonical_form, lang,
                )
                return
            except Exception as exc:
                logger.warning(
                    "wiktionary fetch failed lemma=%r lang=%s: %s",
                    row.canonical_form, lang, exc,
                )
                return

            # Logeion fallback for Latin and Koine Greek (LSJ / Lewis & Short).
            logeion_data: dict | None = None
            if lang in logeion.SUPPORTED_LANGUAGES:
                try:
                    logeion_data = await logeion.fetch_structured(row.canonical_form, lang)
                    if logeion_data and gloss is None:
                        gloss = logeion_data.get("gloss")
                except httpx.HTTPStatusError as exc:
                    logger.warning(
                        "logeion HTTP %d lemma=%r lang=%s",
                        exc.response.status_code, row.canonical_form, lang,
                    )
                except Exception as exc:
                    logger.warning(
                        "logeion fetch failed lemma=%r lang=%s: %s",
                        row.canonical_form, lang, exc,
                    )

            updated = dict(row.lesson_data or {})
            updated["gloss_attempted"] = True
            if gloss:
                updated["gloss"] = gloss
            if logeion_data:
                updated["ls_definition"]       = logeion_data.get("ls_definition")
                updated["classical_citations"] = logeion_data.get("classical_citations", [])
                updated["compound_words"]      = logeion_data.get("compound_words", [])
                updated["lexicon_source"]      = logeion_data.get("lexicon_source")
                if logeion_data.get("part_of_speech"):
                    updated["part_of_speech"] = logeion_data["part_of_speech"]
                if logeion_data.get("gender"):
                    updated["gender"] = logeion_data["gender"]
            row.lesson_data = updated
            dirty.append(row)

    # ── Translation tasks ─────────────────────────────────────────────────────

    async def _fetch_translation(row: CanonicalObjectRow) -> None:
        from backend.dictionary.translation import translate
        async with sem:
            try:
                translation = await translate(
                    row.canonical_form,
                    row.language or "",
                    provider=translation_provider,
                    api_url=translation_api_url,
                    api_key=translation_api_key,
                )
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "translation HTTP %d lemma=%r lang=%s provider=%s",
                    exc.response.status_code, row.canonical_form,
                    row.language, translation_provider,
                )
                return
            except Exception as exc:
                logger.warning(
                    "translation failed lemma=%r lang=%s provider=%s: %s",
                    row.canonical_form, row.language, translation_provider, exc,
                )
                return

            updated = dict(row.lesson_data or {})
            updated["translation_attempted"] = True
            if translation:
                updated["translation"] = translation
                # Store which provider supplied the translation for attribution.
                updated["translation_provider"] = translation_provider
            row.lesson_data = updated
            if row not in dirty:
                dirty.append(row)

    tasks = [_fetch_gloss(r) for r in pending_gloss] + \
            [_fetch_translation(r) for r in pending_translation]
    await asyncio.gather(*tasks)

    if dirty:
        try:
            await db.commit()
            logger.info(
                "enrichment: %d objects updated (gloss_pending=%d translation_pending=%d)",
                len(dirty), len(pending_gloss), len(pending_translation),
            )
        except Exception:
            logger.warning("enrichment DB commit failed", exc_info=True)
