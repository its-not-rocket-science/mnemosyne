"""JWT token creation and verification.

Uses HS256 via python-jose.  The signing secret and algorithm come from
``Settings``; call ``create_access_token`` after a successful login and
``decode_access_token`` inside the ``get_current_user`` dependency.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

from backend.core.config import get_settings

_SUBJECT_KEY = "sub"
_EXPIRY_KEY = "exp"


def create_access_token(user_id: str) -> str:
    """Return a signed JWT for *user_id*.

    The token expires after ``settings.jwt_expire_minutes`` minutes from now.
    The ``sub`` claim holds the user's UUID string.
    """
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {_SUBJECT_KEY: user_id, _EXPIRY_KEY: expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    """Decode *token* and return the ``sub`` (user_id), or ``None`` on any failure.

    Returns ``None`` for expired tokens, bad signatures, or malformed input so
    the caller can fall back gracefully rather than propagating a 500.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id: str | None = payload.get(_SUBJECT_KEY)
        return user_id if user_id else None
    except JWTError:
        return None
