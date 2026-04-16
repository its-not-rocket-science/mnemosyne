"""Route integration tests.

Uses the synchronous TestClient throughout.  Database operations in the
app are wrapped in try/except (non-fatal), so all tests here run without
a live PostgreSQL or Redis instance.

Language convention
───────────────────
  "en" (EnglishStubPlugin) — always available, no model download needed.
       Used for tests that exercise route behaviour, not language extraction.
  "es" (SpanishPlugin)      — requires es_core_news_sm.  Only used where
       the test is specifically about the Spanish extraction pipeline.
"""
from __future__ import annotations

import unittest.mock as mock

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


# ── helpers ───────────────────────────────────────────────────────────────────

def _parse(text: str, language: str = "en", **extra) -> dict:
    resp = client.post("/parse", json={"text": text, "language": language, **extra})
    return resp


# ── /health ───────────────────────────────────────────────────────────────────


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# ── /parse — success paths ────────────────────────────────────────────────────


def test_parse_returns_sentences() -> None:
    resp = _parse("Hello world. How are you?")
    assert resp.status_code == 200
    data = resp.json()
    assert "sentences" in data
    assert len(data["sentences"]) >= 1


def test_parse_sentence_shape() -> None:
    resp = _parse("The cat sleeps.")
    assert resp.status_code == 200
    for sentence in resp.json()["sentences"]:
        assert "text" in sentence
        assert "learnable_objects" in sentence
        for obj in sentence["learnable_objects"]:
            assert "id" in obj
            assert "type" in obj
            assert "label" in obj


def test_parse_with_source_url() -> None:
    resp = _parse(
        "The dog runs.",
        source_url="https://example.com/article",
    )
    assert resp.status_code == 200


def test_parse_single_sentence_no_trailing_punctuation() -> None:
    resp = _parse("Hello")
    assert resp.status_code == 200
    assert len(resp.json()["sentences"]) >= 1


# ── /parse — error paths ──────────────────────────────────────────────────────


def test_parse_unsupported_language_returns_404() -> None:
    resp = _parse("你好世界", language="zh")
    assert resp.status_code == 404
    assert "detail" in resp.json()


def test_parse_empty_text_returns_422() -> None:
    resp = _parse("")
    assert resp.status_code == 422


def test_parse_missing_language_returns_422() -> None:
    resp = client.post("/parse", json={"text": "Hello."})
    assert resp.status_code == 422


def test_parse_oversized_text_returns_413() -> None:
    """Text exceeding max_parse_chars is rejected before NLP runs."""
    from backend.core.config import get_settings
    limit = get_settings().max_parse_chars
    oversized = "a " * (limit + 1)  # definitely over the limit
    resp = _parse(oversized)
    assert resp.status_code == 413
    assert "limit" in resp.json()["detail"].lower()


def test_parse_at_limit_returns_200() -> None:
    """Text exactly at the limit is accepted."""
    from backend.core.config import get_settings
    limit = get_settings().max_parse_chars
    text = "Hello world. " * (limit // len("Hello world. "))
    # Trim to exactly the limit
    text = text[:limit]
    resp = _parse(text)
    assert resp.status_code == 200


# ── /parse — cache fault tolerance ───────────────────────────────────────────


def test_parse_cache_read_error_still_returns_result() -> None:
    """A Redis read error must not bubble up to the caller."""
    with mock.patch(
        "backend.api.routes.parse.get_json",
        side_effect=ConnectionError("redis down"),
    ):
        resp = _parse("The bird sings.")
    assert resp.status_code == 200
    assert len(resp.json()["sentences"]) >= 1


def test_parse_cache_write_error_still_returns_result() -> None:
    """A Redis write error must not bubble up to the caller."""
    with (
        mock.patch(
            "backend.api.routes.parse.get_json",
            return_value=None,   # cache miss
        ),
        mock.patch(
            "backend.api.routes.parse.set_json",
            side_effect=ConnectionError("redis down"),
        ),
    ):
        resp = _parse("The fish swims.")
    assert resp.status_code == 200
    assert len(resp.json()["sentences"]) >= 1


def test_parse_cache_hit_returns_same_shape() -> None:
    """A cache hit must return the same schema as a cache miss."""
    text = "The mouse runs."
    # Prime the cache (or plugin memory) with a real parse
    first = _parse(text)
    assert first.status_code == 200

    # Simulate a cache hit by returning the first response body
    with mock.patch(
        "backend.api.routes.parse.get_json",
        return_value=first.json(),
    ):
        second = _parse(text)
    assert second.status_code == 200
    assert second.json() == first.json()


# ── /lesson ───────────────────────────────────────────────────────────────────


def test_lesson_not_found_returns_404() -> None:
    resp = client.get("/lesson/en%3Avocab%3A_zzz_not_real_xyz?language=en")
    assert resp.status_code == 404


def test_lesson_unsupported_language_returns_404() -> None:
    resp = client.get("/lesson/zh%3Avocab%3A%E4%BD%A0%E5%A5%BD?language=zh")
    assert resp.status_code == 404


def test_lesson_available_after_parse() -> None:
    """An object returned by /parse must be fetchable from /lesson."""
    parse_resp = _parse("The doctor speaks slowly.")
    assert parse_resp.status_code == 200

    objects = [
        obj
        for s in parse_resp.json()["sentences"]
        for obj in s["learnable_objects"]
    ]
    assert objects, "Expected at least one learnable object"

    obj_id = objects[0]["id"]
    lesson_resp = client.get(f"/lesson/{obj_id}?language=en")
    assert lesson_resp.status_code == 200
    data = lesson_resp.json()
    assert data["id"] == obj_id
    assert "title" in data
    assert "explanation" in data
    assert isinstance(data["explanation"], str)
    assert len(data["explanation"]) > 0


def test_lesson_response_shape() -> None:
    parse_resp = _parse("The student reads books.")
    assert parse_resp.status_code == 200
    objects = [
        obj
        for s in parse_resp.json()["sentences"]
        for obj in s["learnable_objects"]
    ]
    assert objects
    lesson_resp = client.get(f"/lesson/{objects[0]['id']}?language=en")
    assert lesson_resp.status_code == 200
    data = lesson_resp.json()
    assert set(data.keys()) >= {"id", "type", "title", "explanation", "fields", "examples", "drills"}


def test_lesson_drills_are_present() -> None:
    """Each lesson must include at least one drill."""
    parse_resp = _parse("The teacher writes clearly.")
    objects = [obj for s in parse_resp.json()["sentences"] for obj in s["learnable_objects"]]
    assert objects
    data = client.get(f"/lesson/{objects[0]['id']}?language=en").json()
    assert len(data["drills"]) >= 1
    for drill in data["drills"]:
        assert "type" in drill


def test_lesson_drill_types_are_valid() -> None:
    """Drill type values must be one of the four defined types."""
    valid_types = {"multiple_choice", "fill_blank", "recognition", "shadowing"}
    parse_resp = _parse("The student reads books.")
    objects = [obj for s in parse_resp.json()["sentences"] for obj in s["learnable_objects"]]
    data = client.get(f"/lesson/{objects[0]['id']}?language=en").json()
    for drill in data["drills"]:
        assert drill["type"] in valid_types


def test_lesson_multiple_choice_shape() -> None:
    """Multiple-choice drills must have options and a valid answer_index."""
    parse_resp = _parse("The cat sleeps quietly.")
    objects = [obj for s in parse_resp.json()["sentences"] for obj in s["learnable_objects"]]
    data = client.get(f"/lesson/{objects[0]['id']}?language=en").json()
    mc_drills = [d for d in data["drills"] if d["type"] == "multiple_choice"]
    for drill in mc_drills:
        assert len(drill["options"]) >= 2
        assert 0 <= drill["answer_index"] < len(drill["options"])


def test_lesson_is_deterministic() -> None:
    """Fetching the same lesson twice must return identical content."""
    parse_resp = _parse("The river flows slowly.")
    objects = [obj for s in parse_resp.json()["sentences"] for obj in s["learnable_objects"]]
    assert objects
    obj_id = objects[0]["id"]
    url = f"/lesson/{obj_id}?language=en"
    first  = client.get(url).json()
    second = client.get(url).json()
    assert first == second


# ── /review ───────────────────────────────────────────────────────────────────


def test_review_returns_expected_fields() -> None:
    resp = client.post(
        "/review",
        json={"object_id": "en:vocab:hello", "quality": 3},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["object_id"] == "en:vocab:hello"
    assert data["next_interval_days"] >= 1
    assert "review_state" in data


def test_review_state_is_json_serialisable() -> None:
    import json
    resp = client.post(
        "/review",
        json={"object_id": "en:vocab:world", "quality": 3},
    )
    assert resp.status_code == 200
    json.dumps(resp.json()["review_state"])  # must not raise


def test_review_invalid_quality_too_high_returns_422() -> None:
    resp = client.post(
        "/review",
        json={"object_id": "en:vocab:test", "quality": 5},
    )
    assert resp.status_code == 422


def test_review_invalid_quality_zero_returns_422() -> None:
    resp = client.post(
        "/review",
        json={"object_id": "en:vocab:test", "quality": 0},
    )
    assert resp.status_code == 422


def test_review_all_valid_qualities_accepted() -> None:
    for quality in (1, 2, 3, 4):
        resp = client.post(
            "/review",
            json={"object_id": f"en:vocab:word_{quality}", "quality": quality},
        )
        assert resp.status_code == 200, f"quality={quality} should be accepted"


def test_review_repeated_via_returned_state_increments_counter() -> None:
    """Carrying the returned review_state into the next call should increment
    the reviews counter by 1 each time, even when there is no database."""
    r1 = client.post(
        "/review",
        json={"object_id": "en:vocab:carry_test", "quality": 3},
    )
    assert r1.status_code == 200
    state1 = r1.json()["review_state"]
    assert state1["reviews"] == 1

    r2 = client.post(
        "/review",
        json={
            "object_id": "en:vocab:carry_test",
            "quality": 3,
            "review_state": state1,
        },
    )
    assert r2.status_code == 200
    assert r2.json()["review_state"]["reviews"] == 2

    r3 = client.post(
        "/review",
        json={
            "object_id": "en:vocab:carry_test",
            "quality": 3,
            "review_state": r2.json()["review_state"],
        },
    )
    assert r3.status_code == 200
    assert r3.json()["review_state"]["reviews"] == 3


def test_again_gives_shorter_interval_than_easy() -> None:
    r_again = client.post(
        "/review",
        json={"object_id": "en:vocab:again_word", "quality": 1},
    )
    r_easy = client.post(
        "/review",
        json={"object_id": "en:vocab:easy_word", "quality": 4},
    )
    assert r_again.json()["next_interval_days"] < r_easy.json()["next_interval_days"]


def test_again_interval_is_short() -> None:
    resp = client.post(
        "/review",
        json={"object_id": "en:vocab:hard_word", "quality": 1},
    )
    assert resp.status_code == 200
    # "Again" on a new card should schedule for very soon
    assert resp.json()["next_interval_days"] <= 3


def test_review_due_at_is_in_future() -> None:
    from datetime import UTC, datetime
    resp = client.post(
        "/review",
        json={"object_id": "en:vocab:future_test", "quality": 3},
    )
    assert resp.status_code == 200
    due = datetime.fromisoformat(resp.json()["review_state"]["due_at"])
    assert due > datetime.now(UTC)


def test_review_missing_object_id_returns_422() -> None:
    resp = client.post("/review", json={"quality": 3})
    assert resp.status_code == 422


def test_review_lapse_increments_lapses() -> None:
    r1 = client.post(
        "/review",
        json={"object_id": "en:vocab:lapse_test", "quality": 3},
    )
    state1 = r1.json()["review_state"]
    assert state1["lapses"] == 0

    r2 = client.post(
        "/review",
        json={
            "object_id": "en:vocab:lapse_test",
            "quality": 1,
            "review_state": state1,
        },
    )
    assert r2.json()["review_state"]["lapses"] == 1
