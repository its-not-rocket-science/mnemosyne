"""Text difficulty estimation route.

POST /estimate-difficulty
    Estimate the CEFR difficulty level of a text snippet without running the
    full NLP parse pipeline.  Returns a distribution across CEFR levels and an
    overall estimate based on 90-% vocabulary coverage.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.services.difficulty_estimator import DifficultyEstimate, estimate

router = APIRouter(tags=["difficulty"])


class DifficultyRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=50_000)
    language: str = Field(..., min_length=2, max_length=10)


class DifficultyResponse(BaseModel):
    language: str
    estimated_cefr: str | None
    distribution: dict[str, float]
    unknown_ratio: float
    word_count: int
    analyzed_tokens: int
    confident: bool
    note: str


@router.post("/estimate-difficulty", response_model=DifficultyResponse)
async def estimate_difficulty(body: DifficultyRequest) -> DifficultyResponse:
    """Estimate CEFR difficulty of *text* using vocabulary coverage analysis.

    The estimate is based on the 90-% coverage rule: the response
    ``estimated_cefr`` is the lowest CEFR band at which at least 90 % of the
    text's content words are covered by the in-memory vocabulary index.

    The ``distribution`` field breaks down the fraction of tokens at each level
    plus ``"unknown"`` (words absent from the index).

    ``confident`` is ``false`` when fewer than 30 tokens were analysed; treat
    the result as indicative only in that case.

    This endpoint does **not** run the NLP pipeline — it is intentionally cheap
    so it can be called on paste or keystroke without server load.
    """
    result: DifficultyEstimate = estimate(body.text, body.language)
    return DifficultyResponse(
        language=result.language,
        estimated_cefr=result.estimated_cefr,
        distribution=result.distribution,
        unknown_ratio=result.unknown_ratio,
        word_count=result.word_count,
        analyzed_tokens=result.analyzed_tokens,
        confident=result.confident,
        note=result.note,
    )
