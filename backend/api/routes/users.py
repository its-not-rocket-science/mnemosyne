"""User preference and account routes.

Routes
──────
GET  /users/me/preferences
    Return all per-language preferences for the current user.
    Returns an empty ``languages`` list when no preferences have been saved.

GET  /users/me/languages/{language_code}/preferences
    Return preferences for one (user, language) pair.
    Returns all-default values when no row exists — callers do not need to
    distinguish "never set" from "set to defaults".

PUT  /users/me/languages/{language_code}/preferences
    Upsert preferences for one (user, language) pair.  The full preference
    object must be supplied; partial-update semantics are not provided to keep
    the schema simple.

GET  /users/me/export
    Return a portable JSON export of all user knowledge and preferences.

DELETE  /users/me
    Permanently delete all personal data for the current user.  Removes rows
    from user_knowledge, user_language_preferences, source_progression, and
    the users table.  Returns 204 No Content.  Existing JWTs continue to pass
    signature verification until they expire; any request they reach will
    simply find no data and will create no new rows under that user_id.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import outerjoin

from backend.api.dependencies import get_current_user, get_db_session
from backend.models import (
    CanonicalObjectRow,
    ReviewEventRow,
    SourceProgressionRow,
    UserKnowledgeRow,
    UserLanguagePreferenceRow,
    UserRow,
)
from backend.schemas.user import (
    KnowledgeExportItem,
    LanguagePreference,
    UserExport,
    UserPreferences,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["users"], prefix="/users")


@router.get("/me/preferences", response_model=UserPreferences)
async def get_my_preferences(
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> UserPreferences:
    """Return all per-language preferences for the current user.

    An empty ``languages`` list is returned when the user has not yet
    customised any language preferences — this is the normal state for a
    new user and should be treated as "all defaults apply".
    """
    try:
        result = await db.execute(
            select(UserLanguagePreferenceRow).where(
                UserLanguagePreferenceRow.user_id == current_user
            )
        )
        rows = result.scalars().all()
    except Exception as exc:
        logger.warning("DB preferences query failed for user %r", current_user, exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    return UserPreferences(
        user_id=current_user,
        languages=[
            LanguagePreference(
                language_code=row.language_code,
                show_transliteration=row.show_transliteration,
                script_preference=row.script_preference,
                lesson_mode_override=row.lesson_mode_override,
            )
            for row in rows
        ],
    )


@router.get(
    "/me/languages/{language_code}/preferences",
    response_model=LanguagePreference,
)
async def get_language_preference(
    language_code: str,
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> LanguagePreference:
    """Return preferences for one (user, language) pair.

    Returns all-default values when no row exists; the response schema is
    the same regardless of whether a row has been explicitly saved.
    """
    try:
        row = await db.get(UserLanguagePreferenceRow, (current_user, language_code))
    except Exception as exc:
        logger.warning(
            "DB preference lookup failed for user=%r lang=%r",
            current_user, language_code,
            exc_info=True,
        )
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    if row is None:
        return LanguagePreference(language_code=language_code)

    return LanguagePreference(
        language_code=row.language_code,
        show_transliteration=row.show_transliteration,
        script_preference=row.script_preference,
        lesson_mode_override=row.lesson_mode_override,
    )


@router.put(
    "/me/languages/{language_code}/preferences",
    response_model=LanguagePreference,
)
async def set_language_preference(
    language_code: str,
    payload: LanguagePreference,
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> LanguagePreference:
    """Upsert preferences for one (user, language) pair.

    The ``language_code`` path parameter must match ``payload.language_code``
    when the payload includes it.  If they differ the path parameter wins
    and the payload field is ignored.
    """
    try:
        row = await db.get(UserLanguagePreferenceRow, (current_user, language_code))
        if row is None:
            row = UserLanguagePreferenceRow(
                user_id=current_user,
                language_code=language_code,
            )
            db.add(row)
        row.show_transliteration = payload.show_transliteration
        row.script_preference = payload.script_preference
        row.lesson_mode_override = payload.lesson_mode_override
        await db.commit()
        await db.refresh(row)
    except Exception as exc:
        logger.warning(
            "DB preference upsert failed for user=%r lang=%r",
            current_user, language_code,
            exc_info=True,
        )
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    return LanguagePreference(
        language_code=row.language_code,
        show_transliteration=row.show_transliteration,
        script_preference=row.script_preference,
        lesson_mode_override=row.lesson_mode_override,
    )


@router.get("/me/export", response_model=UserExport)
async def export_my_data(
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> UserExport:
    """Return a complete portable export of the current user's knowledge state.

    The response is a self-contained JSON document that includes:

    * **knowledge** — every ``user_knowledge`` row for this user, enriched with
      ``canonical_form``, ``type``, and ``display_label`` from the matching
      ``canonical_objects`` row (when present).  Items whose canonical object
      has been deleted are still included; their enrichment fields are ``null``.

    * **language_preferences** — all saved per-language preference overrides.

    This endpoint is intended for data portability.  The ``schema_version``
    field is ``"1"``; it will be bumped on backwards-incompatible changes so
    future import tooling can detect format mismatches.
    """
    try:
        # LEFT OUTER JOIN so knowledge rows without a matching canonical object
        # are still included (no FK between the two tables by design).
        join_clause = outerjoin(
            UserKnowledgeRow,
            CanonicalObjectRow,
            UserKnowledgeRow.object_id == CanonicalObjectRow.id,
        )
        result = await db.execute(
            select(UserKnowledgeRow, CanonicalObjectRow)
            .select_from(join_clause)
            .where(UserKnowledgeRow.user_id == current_user)
            .order_by(UserKnowledgeRow.last_seen.desc())
        )
        knowledge_rows = result.all()

        pref_result = await db.execute(
            select(UserLanguagePreferenceRow).where(
                UserLanguagePreferenceRow.user_id == current_user
            )
        )
        pref_rows = pref_result.scalars().all()
    except Exception as exc:
        logger.warning("DB export query failed for user %r", current_user, exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    knowledge_items = [
        KnowledgeExportItem(
            object_id=uk.object_id,
            language=uk.language,
            canonical_form=co.canonical_form if co else None,
            type=co.type if co else None,
            display_label=co.display_label if co else None,
            fsrs_state=uk.fsrs_state,
            mastery_score=uk.mastery_score,
            first_seen=uk.first_seen,
            last_seen=uk.last_seen,
            total_reviews=uk.total_reviews,
            due_at=uk.due_at,
        )
        for uk, co in knowledge_rows
    ]

    return UserExport(
        exported_at=datetime.now(UTC),
        user_id=current_user,
        knowledge=knowledge_items,
        language_preferences=[
            LanguagePreference(
                language_code=row.language_code,
                show_transliteration=row.show_transliteration,
                script_preference=row.script_preference,
                lesson_mode_override=row.lesson_mode_override,
            )
            for row in pref_rows
        ],
    )


@router.delete("/me", status_code=204)
async def delete_my_account(
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> Response:
    """Permanently delete all personal data for the current user.

    Deletes every row owned by this user across:
      - ``user_knowledge``           — FSRS state and review history
      - ``user_language_preferences``— study preference overrides
      - ``source_progression``       — reading progress per source document
      - ``users``                    — the account row itself (if it exists)

    The operation is idempotent: calling it on a user who has already been
    deleted (or never registered) returns 204 as well.

    Existing JWTs remain cryptographically valid until they expire.  Any
    subsequent authenticated request will simply find no data and will not
    create new rows — the deleted user_id is effectively inert.
    """
    try:
        await db.execute(
            delete(ReviewEventRow).where(ReviewEventRow.user_id == current_user)
        )
        await db.execute(
            delete(UserKnowledgeRow).where(UserKnowledgeRow.user_id == current_user)
        )
        await db.execute(
            delete(UserLanguagePreferenceRow).where(
                UserLanguagePreferenceRow.user_id == current_user
            )
        )
        await db.execute(
            delete(SourceProgressionRow).where(
                SourceProgressionRow.user_id == current_user
            )
        )
        await db.execute(
            delete(UserRow).where(UserRow.id == current_user)
        )
        await db.commit()
    except Exception as exc:
        logger.warning("Account deletion failed for user %r", current_user, exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    logger.info("Account and all personal data deleted for user %r", current_user)
    return Response(status_code=204)
