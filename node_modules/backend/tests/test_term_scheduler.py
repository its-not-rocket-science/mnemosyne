from __future__ import annotations

from datetime import UTC, datetime, timedelta

from backend.srs.term_scheduler import classify_term, schedule_after_review


NOW = datetime(2026, 1, 1, tzinfo=UTC)


def test_classify_new_due_learning_fading_and_strong() -> None:
    assert classify_term(review_count=0, mastery_score=0.0, next_review_at=None, now=NOW) == "new"
    assert classify_term(review_count=2, mastery_score=0.4, next_review_at=NOW - timedelta(days=1), now=NOW) == "due"
    assert classify_term(review_count=1, mastery_score=0.4, next_review_at=NOW + timedelta(days=1), now=NOW) == "learning"
    assert classify_term(review_count=3, mastery_score=0.7, next_review_at=NOW + timedelta(days=1), now=NOW) == "fading"
    assert classify_term(review_count=4, mastery_score=0.9, next_review_at=NOW + timedelta(days=2), now=NOW) == "strong"


def test_incorrect_review_reduces_mastery_and_schedules_early() -> None:
    mastery, due = schedule_after_review(
        review_count=3,
        mastery_score=0.6,
        correct=False,
        now=NOW,
        next_review_at=NOW + timedelta(days=5),
    )
    assert mastery < 0.6
    assert due == NOW + timedelta(days=1)


def test_overdue_penalty_applies_before_success_update() -> None:
    mastery, due = schedule_after_review(
        review_count=2,
        mastery_score=0.5,
        correct=True,
        now=NOW,
        next_review_at=NOW - timedelta(days=3),
    )
    assert mastery < 0.65
    assert due > NOW
