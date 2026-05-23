"""Adaptive acquisition stage progression.

Tracks learner advancement through six stages of language acquisition:

  recognition              → Identifying the item on encounter.
  guided_recall            → Recalling with contextual support.
  partial_production       → Producing with scaffolding (sentence starters, etc.).
  transformation           → Applying patterns under instruction (drills).
  free_production          → Using the item independently in context.
  contextual_interpretation → Interpreting subtle discourse nuances.

Stage advances when the FSRS mastery score meets or exceeds the threshold
for the current stage.  Stage never regresses — a lapse increases review
frequency but does not undo demonstrated learning.

Thresholds are conservative: advancing to free_production requires 85 %
mastery, which corresponds to approximately 6–8 successful spaced reviews
in the FSRS-5 model with desired_retention = 0.90.
"""
from __future__ import annotations

STAGES: list[str] = [
    "recognition",
    "guided_recall",
    "partial_production",
    "transformation",
    "free_production",
    "contextual_interpretation",
]

# Mastery score threshold to advance FROM this stage.
# None = terminal stage; no further advancement.
STAGE_THRESHOLDS: dict[str, float | None] = {
    "recognition":               0.60,
    "guided_recall":             0.70,
    "partial_production":        0.75,
    "transformation":            0.80,
    "free_production":           0.85,
    "contextual_interpretation": None,
}

STAGE_LABELS: dict[str, str] = {
    "recognition":               "Recognition",
    "guided_recall":             "Guided recall",
    "partial_production":        "Partial production",
    "transformation":            "Transformation",
    "free_production":           "Free production",
    "contextual_interpretation": "Contextual interpretation",
}

STAGE_DESCRIPTIONS: dict[str, str] = {
    "recognition":               "Identifying this item on encounter.",
    "guided_recall":             "Recalling with contextual support.",
    "partial_production":        "Producing with scaffolding.",
    "transformation":            "Applying patterns under instruction.",
    "free_production":           "Using this item independently in context.",
    "contextual_interpretation": "Interpreting subtle discourse nuances.",
}


def advance_stage(current_stage: str, mastery_score: float) -> str:
    """Return the next stage if mastery meets the threshold, else current.

    Parameters
    ----------
    current_stage:
        The learner's current acquisition stage for this item.
        If unknown or invalid, treated as "recognition".
    mastery_score:
        FSRS-derived mastery score ∈ [0, 1].

    Returns
    -------
    str
        The (possibly advanced) stage label.
    """
    if current_stage not in STAGE_THRESHOLDS:
        current_stage = STAGES[0]
    threshold = STAGE_THRESHOLDS[current_stage]
    if threshold is None:
        return current_stage
    if mastery_score >= threshold:
        try:
            idx = STAGES.index(current_stage)
            return STAGES[idx + 1] if idx + 1 < len(STAGES) else current_stage
        except ValueError:
            pass
    return current_stage


def stage_index(stage: str) -> int:
    """0-based index of the stage in the progression sequence (0 if unknown)."""
    try:
        return STAGES.index(stage)
    except ValueError:
        return 0


def stage_fraction(stage: str) -> float:
    """Stage progress as a fraction ∈ [0, 1] for UI progress indicators."""
    n = len(STAGES)
    return stage_index(stage) / max(1, n - 1)
