"""Post-parse dictionary enrichment.

After the NLP pipeline has extracted and persisted canonical objects, this
module optionally fetches English glosses from Wiktionary and stores them in
``canonical_objects.lesson_data["gloss"]``.

Design rationale
────────────────
Glosses are stored in ``lesson_data`` rather than a separate table so that
the lesson engine can consume them with zero schema changes — ``_build_vocabulary``
and ``_build_dictionary`` already read ``lesson_data.get("gloss")``.

Attempt tracking
────────────────
To avoid refetching on every parse, a ``"gloss_attempted"`` boolean flag is
written to ``lesson_data`` after each lookup attempt (regardless of outcome).
The absence of this flag means "never tried"; its presence means "already tried
— do not retry".  A found gloss is stored as ``lesson_data["gloss"] = <str>``.

Scope
─────
Only objects of type ``"vocabulary"`` are enriched.  Conjugations, agreements,
case-agreements, and other derived types do not have standalone Wiktionary
entries; their parent vocabulary lemma carries the relevant gloss.

Concurrency
───────────
A semaphore limits parallel Wiktionary requests to ``MAX_CONCURRENT_FETCHES``.
The per-request timeout is set in ``backend.dictionary.wiktionary``.

Network failures (timeout, DNS, unexpected HTTP status) are logged at WARNING
level and the object is left without ``"gloss_attempted"`` so it will be
retried the next time it appears in a parse.

404 responses (word not in Wiktionary) set ``"gloss_attempted": True`` without
a ``"gloss"`` key, preventing future retries for genuinely absent words.
"""
from __future__ import annotations

import asyncio
import logging

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dictionary.wiktionary import fetch_definition
from backend.models import CanonicalObjectRow

logger = logging.getLogger(__name__)

#: Only enrich objects of these types.
ENRICHMENT_TYPES: frozenset[str] = frozenset({"vocabulary"})

#: Maximum number of concurrent Wiktionary HTTP requests per enrichment batch.
MAX_CONCURRENT_FETCHES: int = 5


async def enrich_objects(
    db: AsyncSession,
    object_ids: list[str],
) -> None:
    """Fetch and store Wiktionary glosses for canonical objects in *object_ids*.

    Silently skips:
    - Objects not found in the database.
    - Objects whose type is not in ENRICHMENT_TYPES.
    - Objects that already have ``lesson_data["gloss"]`` set.
    - Objects that already have ``lesson_data["gloss_attempted"]`` set.

    Parameters
    ----------
    db:
        Async SQLAlchemy session.  ``db.commit()`` is called after all updates.
    object_ids:
        List of canonical object UUIDs to consider for enrichment.
        Typically the full list from a single ``/parse`` call.
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

    # Filter to rows that have not yet been attempted.
    pending = [
        row for row in rows
        if not (row.lesson_data or {}).get("gloss")
        and not (row.lesson_data or {}).get("gloss_attempted")
    ]

    if not pending:
        return

    sem = asyncio.Semaphore(MAX_CONCURRENT_FETCHES)
    dirty: list[CanonicalObjectRow] = []

    async def _fetch_one(row: CanonicalObjectRow) -> None:
        async with sem:
            try:
                gloss = await fetch_definition(row.canonical_form, row.language or "")
            except httpx.HTTPStatusError as exc:
                # Unexpected HTTP error — leave un-attempted so we can retry.
                logger.warning(
                    "wiktionary HTTP %d for lemma=%r lang=%s",
                    exc.response.status_code,
                    row.canonical_form,
                    row.language,
                )
                return
            except (httpx.RequestError, Exception) as exc:
                # Network failure — leave un-attempted so we can retry.
                logger.warning(
                    "wiktionary fetch failed lemma=%r lang=%s: %s",
                    row.canonical_form,
                    row.language,
                    exc,
                )
                return

            # Persist the result (including "not found" so we skip on future parses).
            updated = dict(row.lesson_data or {})
            updated["gloss_attempted"] = True
            if gloss:
                updated["gloss"] = gloss
                logger.debug(
                    "wiktionary gloss found lemma=%r lang=%s",
                    row.canonical_form,
                    row.language,
                )
            else:
                logger.debug(
                    "wiktionary no gloss lemma=%r lang=%s",
                    row.canonical_form,
                    row.language,
                )
            row.lesson_data = updated
            dirty.append(row)

    await asyncio.gather(*[_fetch_one(row) for row in pending])

    if dirty:
        try:
            await db.commit()
            logger.info(
                "dictionary enrichment: %d/%d objects updated",
                len(dirty),
                len(pending),
            )
        except Exception:
            logger.warning("dictionary enrichment DB commit failed", exc_info=True)
