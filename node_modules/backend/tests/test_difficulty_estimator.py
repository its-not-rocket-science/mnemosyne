"""Tests for the text difficulty estimator service and route."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import app
from backend.services.difficulty_estimator import (
    COVERAGE_THRESHOLD,
    CEFR_LEVELS,
    MIN_TOKENS_CONFIDENT,
    estimate,
)


# ── Unit tests: estimate() ────────────────────────────────────────────────────

# Fake vocab index: maps (lang, word) → CEFR level
_FAKE_INDEX = {
    ("es", "el"): "A1", ("es", "la"): "A1", ("es", "gato"): "A1",
    ("es", "casa"): "A1", ("es", "hombre"): "A1",
    ("es", "ciudad"): "A2", ("es", "trabajo"): "A2", ("es", "dinero"): "A2",
    ("es", "empresa"): "B1", ("es", "mercado"): "B1", ("es", "gobierno"): "B1",
    ("es", "legislación"): "B2", ("es", "infraestructura"): "B2",
    ("es", "paradigma"): "C1", ("es", "epistemología"): "C2",
}


def _fake_cefr(language: str, lemma: str) -> str | None:
    return _FAKE_INDEX.get((language, lemma.lower()))


@pytest.fixture(autouse=True)
def patch_vocab_index():
    with patch("backend.services.difficulty_estimator.get_cefr_level", side_effect=_fake_cefr):
        yield


class TestEstimateBasics:
    def test_empty_text_returns_none(self):
        result = estimate("", "es")
        assert result.estimated_cefr is None
        assert result.word_count == 0

    def test_whitespace_only_returns_none(self):
        result = estimate("   \n\t  ", "es")
        assert result.estimated_cefr is None

    def test_language_preserved(self):
        result = estimate("gato casa", "es")
        assert result.language == "es"

    def test_word_count_reflects_tokens(self):
        result = estimate("gato casa hombre", "es")
        assert result.word_count == 3

    def test_distribution_sums_to_one(self):
        result = estimate("gato ciudad empresa legislación paradigma", "es")
        total = sum(result.distribution.values())
        assert abs(total - 1.0) < 0.001


class TestCoverageThreshold:
    def test_all_a1_text_estimated_a1(self):
        # 5 A1 words — cumulative A1 fraction = 1.0 ≥ 0.90
        text = "el la gato casa hombre"
        result = estimate(text, "es")
        assert result.estimated_cefr == "A1"

    def test_a2_heavy_text_estimated_a2(self):
        # 1 A1 + 9 A2 → cumulative at A1 = 0.1, at A2 = 1.0 → A2
        text = "gato " + " ".join(["ciudad", "trabajo", "dinero"] * 3)
        result = estimate(text, "es")
        assert result.estimated_cefr == "A2"

    def test_high_unknown_pushes_to_c2(self):
        # Mostly unknown words — never reaches 90% threshold until C2
        text = " ".join(["xyzabc"] * 50)  # all unknown
        result = estimate(text, "es")
        # All unknown → no level reaches 90% → falls to C2
        assert result.estimated_cefr == "C2"

    def test_mixed_b1_text(self):
        # Enough A1+A2+B1 together to reach 90%
        words = (
            ["gato"] * 20          # A1
            + ["ciudad"] * 20      # A2
            + ["empresa"] * 20     # B1
            + ["epistemología"] * 3  # C2 (small fraction)
        )
        result = estimate(" ".join(words), "es")
        assert result.estimated_cefr in ("A2", "B1")


class TestUnknownRatio:
    def test_unknown_ratio_all_known(self):
        result = estimate("gato casa hombre", "es")
        assert result.unknown_ratio == 0.0

    def test_unknown_ratio_half_unknown(self):
        result = estimate("gato xyzabc", "es")
        assert abs(result.unknown_ratio - 0.5) < 0.01

    def test_unknown_in_distribution(self):
        result = estimate("gato xyzabc", "es")
        assert "unknown" in result.distribution
        assert result.distribution["unknown"] > 0


class TestConfidence:
    def test_short_text_not_confident(self):
        result = estimate("gato", "es")
        assert not result.confident
        assert result.note != ""

    def test_long_text_confident(self):
        text = " ".join(["gato"] * MIN_TOKENS_CONFIDENT)
        result = estimate(text, "es")
        assert result.confident

    def test_confidence_boundary(self):
        text = " ".join(["gato"] * (MIN_TOKENS_CONFIDENT - 1))
        assert not estimate(text, "es").confident

        text2 = " ".join(["gato"] * MIN_TOKENS_CONFIDENT)
        assert estimate(text2, "es").confident


class TestDistribution:
    def test_all_levels_present_in_distribution(self):
        result = estimate("gato ciudad empresa", "es")
        for level in CEFR_LEVELS:
            assert level in result.distribution

    def test_zero_fraction_for_unused_levels(self):
        result = estimate("gato", "es")  # only A1 word
        assert result.distribution["B2"] == 0.0
        assert result.distribution["C1"] == 0.0
        assert result.distribution["C2"] == 0.0


# ── Route tests ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_route_returns_200():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/estimate-difficulty",
            json={"text": "el gato casa hombre ciudad", "language": "es"},
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_route_response_shape():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/estimate-difficulty",
            json={"text": "el gato casa hombre ciudad", "language": "es"},
        )
    data = resp.json()
    assert "estimated_cefr" in data
    assert "distribution" in data
    assert "unknown_ratio" in data
    assert "word_count" in data
    assert "confident" in data
    assert "note" in data


@pytest.mark.asyncio
async def test_route_empty_text_returns_422():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/estimate-difficulty",
            json={"text": "", "language": "es"},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_route_missing_language_returns_422():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/estimate-difficulty",
            json={"text": "some text here"},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_route_unknown_language_returns_result_not_error():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/estimate-difficulty",
            json={"text": "some words here today", "language": "xx"},
        )
    assert resp.status_code == 200
    data = resp.json()
    # All tokens unknown → unknown_ratio = 1.0 (or close)
    assert data["unknown_ratio"] >= 0.8
