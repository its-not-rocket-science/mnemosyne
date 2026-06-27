from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from backend.schemas.parse import ParseResponse


class ParseJobCreated(BaseModel):
    """Response body for POST /parse/jobs."""

    job_id: str
    status: str = "pending"


class ParseJobStatus(BaseModel):
    """Response body for GET /parse/jobs/{job_id}."""

    job_id: str
    status: str = Field(description="pending | running | done | failed")
    progress: float = Field(ge=0.0, le=1.0)
    stage: str
    sentences_done: int = 0
    sentences_total: int = 0
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    # Populated only when status == "done"
    result: ParseResponse | None = None
