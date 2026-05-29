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

GET  /users/me/fsrs-params
    Return the current FSRS scheduling parameters (desired_retention and
    calibration metadata).  Returns factory defaults when no row exists.

PATCH  /users/me/fsrs-params
    Manually set desired_retention.  Clears calibration metadata so the UI
    can distinguish manual from auto-calibrated values.

POST  /users/me/calibrate
    Run auto-calibration from the user's review history.  Requires at least
    30 review events.  Persists the calibrated desired_retention and returns
    it along with calibration quality metrics.

GET  /users/me/export
    Return a portable JSON export of all user knowledge and preferences.

DELETE  /users/me
    Permanently delete all personal data for the current user.  Removes rows
    from user_knowledge, user_language_preferences, source_progression,
    user_fsrs_params, and the users table.  Returns 204 No Content.
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
    ParsedText,
    ReviewEventRow,
    Sentence,
    SentenceObjectRow,
    SourceChunkRow,
    SourceDocumentRow,
    SourceProgressionRow,
    UserFsrsParamsRow,
    UserKnowledgeRow,
    UserLanguagePreferenceRow,
    UserRow,
)
from backend.schemas.user import (
    FsrsParams,
    FsrsParamsUpdate,
    KnowledgeExportItem,
    LanguagePreference,
    UserExport,
    UserPreferences,
)
from backend.srs.calibrate import MIN_REVIEWS_FOR_CALIBRATION, calibrate

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


@router.get("/me/fsrs-params", response_model=FsrsParams)
async def get_fsrs_params(
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> FsrsParams:
    """Return the current FSRS scheduling parameters for the user.

    Returns factory defaults when the user has never calibrated or set params.
    """
    try:
        row = await db.get(UserFsrsParamsRow, current_user)
    except Exception as exc:
        logger.warning("DB fsrs-params lookup failed for user %r", current_user, exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    if row is None:
        return FsrsParams()

    return FsrsParams(
        desired_retention=row.desired_retention,
        last_calibrated_at=row.last_calibrated_at,
        reviews_used=row.reviews_used,
        calibration_rmse=row.calibration_rmse,
    )


@router.patch("/me/fsrs-params", response_model=FsrsParams)
async def set_fsrs_params(
    payload: FsrsParamsUpdate,
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> FsrsParams:
    """Manually set the desired_retention for the current user.

    Clears calibration metadata so the UI can distinguish a manual value
    from an auto-calibrated one.
    """
    try:
        row = await db.get(UserFsrsParamsRow, current_user)
        if row is None:
            row = UserFsrsParamsRow(user_id=current_user)
            db.add(row)
        row.desired_retention    = payload.desired_retention
        row.last_calibrated_at   = None
        row.reviews_used         = None
        row.calibration_rmse     = None
        await db.commit()
        await db.refresh(row)
    except Exception as exc:
        logger.warning("DB fsrs-params update failed for user %r", current_user, exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    return FsrsParams(desired_retention=row.desired_retention)


@router.post("/me/calibrate", response_model=FsrsParams)
async def calibrate_fsrs_params(
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> FsrsParams:
    """Run auto-calibration and update the user's desired_retention.

    Reads all ``review_events`` for this user and applies the bias-correction
    algorithm from ``backend.srs.calibrate`` to estimate the optimal
    ``desired_retention``.

    Returns 422 when the user has fewer than the minimum required reviews
    (currently {min_reviews}).
    """.format(min_reviews=MIN_REVIEWS_FOR_CALIBRATION)
    try:
        result = await db.execute(
            select(ReviewEventRow.mastery_score_before, ReviewEventRow.quality).where(
                ReviewEventRow.user_id == current_user
            )
        )
        events: list[tuple[float, int]] = [(r, q) for r, q in result.all()]
    except Exception as exc:
        logger.warning("DB review_events query failed for user %r", current_user, exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    cal = calibrate(events)
    if cal is None:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Not enough review history for calibration. "
                f"Need at least {MIN_REVIEWS_FOR_CALIBRATION} reviews; "
                f"found {len(events)}."
            ),
        )

    now = datetime.now(UTC)
    try:
        row = await db.get(UserFsrsParamsRow, current_user)
        if row is None:
            row = UserFsrsParamsRow(user_id=current_user)
            db.add(row)
        row.desired_retention  = cal.desired_retention
        row.last_calibrated_at = now
        row.reviews_used       = cal.reviews_used
        row.calibration_rmse   = cal.calibration_rmse
        await db.commit()
        await db.refresh(row)
    except Exception as exc:
        logger.warning("DB fsrs-params persist failed for user %r", current_user, exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    logger.info(
        "Calibrated desired_retention=%.4f rmse=%s reviews=%d user=%r",
        cal.desired_retention,
        cal.calibration_rmse,
        cal.reviews_used,
        current_user,
    )

    return FsrsParams(
        desired_retention=row.desired_retention,
        last_calibrated_at=row.last_calibrated_at,
        reviews_used=row.reviews_used,
        calibration_rmse=row.calibration_rmse,
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


@router.get("/me/analytics-opt-out", response_model=dict)
async def get_analytics_opt_out(
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> dict:
    """Return the current analytics opt-out preference for the current user."""
    row = await db.scalar(select(UserRow).where(UserRow.id == current_user))
    opt_out = bool(row.analytics_opt_out) if row else False
    return {"opt_out": opt_out}


@router.patch("/me/analytics-opt-out", response_model=dict)
async def set_analytics_opt_out(
    payload: dict,
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> dict:
    """Set analytics opt-out preference. Body: ``{"opt_out": true|false}``."""
    opt_out = bool(payload.get("opt_out", False))
    row = await db.scalar(select(UserRow).where(UserRow.id == current_user))
    if row:
        row.analytics_opt_out = opt_out
        await db.commit()
    return {"opt_out": opt_out}


@router.delete("/me", status_code=204)
async def delete_my_account(
    db: AsyncSession = Depends(get_db_session),
    current_user: str = Depends(get_current_user),
) -> Response:
    """Permanently delete all personal data for the current user.

    Deletes every row owned by this user across:
      - ``parsed_texts``             — submitted source text (GDPR: user content)
      - ``sentences``                — sentences derived from parsed_texts
      - ``sentence_objects``         — join rows for those sentences
      - ``source_documents``         — attribution metadata (title, author, URL)
      - ``source_chunks``            — chunks linking source_documents → parsed_texts
      - ``review_events``            — full review history
      - ``user_knowledge``           — FSRS state
      - ``user_language_preferences``— study preference overrides
      - ``source_progression``       — per-document reading progress
      - ``user_fsrs_params``         — calibration parameters
      - ``users``                    — the account row itself

    Deletion order respects FK constraints: child rows are removed before
    parents.  The subqueries are evaluated at SQL execution time so no
    intermediate state is needed.

    The operation is idempotent: returns 204 even when the user no longer
    exists.  Existing JWTs remain cryptographically valid until they expire;
    subsequent requests will find no data and will not create new rows.
    """
    try:
        # ── Subquery handles for FK-ordered bulk deletes ──────────────────────
        pt_ids = select(ParsedText.id).where(ParsedText.user_id == current_user)
        sent_ids = select(Sentence.id).where(Sentence.parsed_text_id.in_(pt_ids))
        sd_ids = select(SourceProgressionRow.source_document_id).where(
            SourceProgressionRow.user_id == current_user
        )

        # 1. Children of sentences
        await db.execute(
            delete(SentenceObjectRow).where(SentenceObjectRow.sentence_id.in_(sent_ids))
        )
        # 2. Sentences → parsed_texts
        await db.execute(delete(Sentence).where(Sentence.parsed_text_id.in_(pt_ids)))
        await db.execute(delete(ParsedText).where(ParsedText.user_id == current_user))

        # 3. Children of source_documents (chunks ref both source_documents and parsed_texts)
        await db.execute(
            delete(SourceChunkRow).where(SourceChunkRow.source_document_id.in_(sd_ids))
        )
        await db.execute(
            delete(SourceDocumentRow).where(SourceDocumentRow.id.in_(sd_ids))
        )

        # 4. User-keyed tables
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
            delete(UserFsrsParamsRow).where(UserFsrsParamsRow.user_id == current_user)
        )
        await db.execute(delete(UserRow).where(UserRow.id == current_user))
        await db.commit()
    except Exception as exc:
        logger.warning("Account deletion failed for user %r", current_user, exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    logger.info("Account and all personal data deleted for user %r", current_user)
    return Response(status_code=204)
