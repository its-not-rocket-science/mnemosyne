"""GET /config — public app configuration consumed by the frontend at startup."""
from __future__ import annotations

from fastapi import APIRouter

from backend.core.config import get_settings

router = APIRouter(tags=["ops"])


@router.get("/config")
async def get_config() -> dict:
    s = get_settings()
    return {"owner_email": s.auth_owner_email}
