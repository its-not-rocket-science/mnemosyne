from backend.srs.fsrs import default_state, review


def test_review_returns_positive_interval() -> None:
    state = default_state().to_dict()
    next_days, updated = review(quality=3, state=state)
    assert next_days >= 1
    assert updated["reviews"] == 1


def test_low_quality_reduces_stability() -> None:
    state = default_state().to_dict()
    _, low = review(quality=1, state=state)
    _, high = review(quality=4, state=state)
    assert low["stability"] < high["stability"]
