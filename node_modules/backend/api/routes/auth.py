"""Authentication routes.

POST /auth/register
    Create a new account.  Returns a JWT on success.
    409 if the email is already registered.

POST /auth/login
    Verify credentials and return a JWT.
    401 on wrong email or password (deliberately identical message to prevent
    email enumeration).
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Body
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import get_db_session
from backend.auth.passwords import hash_password, verify_password
from backend.auth.tokens import create_access_token
from backend.core.config import get_settings
from backend.core.limiter import limiter
from backend.models import UserRow
from backend.schemas.auth import LoginRequest, RegisterRequest, TokenResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["auth"], prefix="/auth")


@router.post("/register", response_model=TokenResponse, status_code=201)
@limiter.limit(lambda: get_settings().rate_limit_auth)
async def register(
    request: Request,
    payload: RegisterRequest = Body(...),
    db: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """Register a new user account and return a JWT.

    Returns 409 when the email is already in use.  The response body is the
    same ``TokenResponse`` as login so the client code path is uniform.
    """
    email = payload.email.lower().strip()

    try:
        existing = await db.scalar(select(UserRow).where(UserRow.email == email))
    except Exception as exc:
        logger.warning("DB error during register email check", exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    if existing is not None:
        raise HTTPException(status_code=409, detail="Email already registered.")

    user = UserRow(email=email, hashed_password=hash_password(payload.password))
    try:
        db.add(user)
        await db.commit()
        await db.refresh(user)
    except Exception as exc:
        logger.warning("DB error persisting new user", exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    return TokenResponse(
        access_token=create_access_token(user.id),
        user_id=user.id,
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit(lambda: get_settings().rate_limit_auth)
async def login(
    request: Request,
    payload: LoginRequest = Body(...),
    db: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """Verify credentials and return a JWT.

    Returns 401 for both unknown email and wrong password — identical messages
    to prevent email enumeration.
    """
    email = payload.email.lower().strip()
    _INVALID = HTTPException(status_code=401, detail="Invalid email or password.")

    try:
        user = await db.scalar(select(UserRow).where(UserRow.email == email))
    except Exception as exc:
        logger.warning("DB error during login lookup", exc_info=True)
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    if user is None or not verify_password(payload.password, user.hashed_password):
        raise _INVALID

    return TokenResponse(
        access_token=create_access_token(user.id),
        user_id=user.id,
    )
