"""Password hashing and verification via bcrypt."""
from __future__ import annotations

import bcrypt

_ROUNDS = 12


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of *plain*."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=_ROUNDS)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches *hashed*."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())
