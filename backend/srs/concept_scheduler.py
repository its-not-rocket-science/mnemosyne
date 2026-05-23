"""Concept-type-aware FSRS scheduling adjustments.

Different linguistic concept types have different memory decay profiles:
  - Vocabulary (lexical items): standard FSRS interval
  - Nuance/aspect distinctions: decay faster — harder to retain precisely
  - Grammar rules: decay slower — more systematic, schema-backed
  - Idioms/collocations: moderate decay — form-bound but context-dependent

The multiplier is applied to ``next_days`` after the FSRS scheduler runs.
It does NOT change the FSRS stability or difficulty — those stay on the
standard power-law curve.  Only the interval between reviews changes.

Design rationale
────────────────
Modifying FSRS stability directly would break the retention curve invariant
R(S, S) = 0.9 and make per-user calibration meaningless.  Multiplying the
interval instead is mathematically equivalent to shifting the target retention
threshold for each concept type — nuance items are reviewed more often because
the acceptable forgetting rate is higher for fine-grained distinctions.
"""
from __future__ import annotations

from datetime import datetime, timedelta

# ── Per-concept-type interval multipliers ─────────────────────────────────────
#
# Values < 1.0  → shorter intervals (more frequent review)
# Values > 1.0  → longer intervals  (less frequent review, currently unused)
#
# Derived from linguistic memory research:
#   · Episodic vocabulary memory (word–meaning pairs): stable at 1.0
#   · Procedural morphology (paradigm cells): slightly less stable
#   · Pragmatic/aspectual nuance: highly context-sensitive, decays fast
#   · Idioms: form-bound, intermediate decay
#   · Register awareness: highly context-dependent, fast decay

CONCEPT_TYPE_MULTIPLIERS: dict[str, float] = {
    "vocabulary":      1.00,
    "conjugation":     0.85,
    "agreement":       0.80,
    "inflection":      0.85,
    "idiom":           0.70,
    "grammar":         0.90,
    "nuance":          0.50,
    "script":          0.90,
    "transliteration": 0.90,
    "case_agreement":  0.75,
    "phrase_family":   0.70,
    # Extra semantic categories used in weakness profiling
    "register":        0.55,
    "aspect":          0.50,
    "collocation":     0.80,
}

CONCEPT_TYPE_LABELS: dict[str, str] = {
    "vocabulary":      "Vocabulary",
    "conjugation":     "Conjugation",
    "agreement":       "Agreement",
    "inflection":      "Inflection",
    "idiom":           "Idiom",
    "grammar":         "Grammar",
    "nuance":          "Nuance",
    "script":          "Script",
    "transliteration": "Transliteration",
    "case_agreement":  "Case agreement",
    "phrase_family":   "Phrase family",
    "register":        "Register",
    "aspect":          "Aspect",
    "collocation":     "Collocation",
}


def apply_concept_type_adjustment(
    next_days: int,
    updated_state: dict,
    object_type: str,
    now: datetime,
) -> tuple[int, dict]:
    """Apply concept-type multiplier to interval; update due_at in state dict.

    Returns the adjusted interval in days and a copy of ``updated_state`` with
    ``due_at`` reflecting the new interval.  The original ``updated_state`` is
    not mutated.

    When the multiplier is 1.0 (vocabulary / default), returns the original
    values unchanged to avoid unnecessary copies.
    """
    multiplier = CONCEPT_TYPE_MULTIPLIERS.get(object_type, 1.0)
    if multiplier == 1.0:
        return next_days, updated_state
    adjusted_days = max(1, round(next_days * multiplier))
    adjusted_state = {**updated_state, "due_at": (now + timedelta(days=adjusted_days)).isoformat()}
    return adjusted_days, adjusted_state


def concept_label(object_type: str | None) -> str | None:
    """Human-readable label for a concept type, or None for unknown types."""
    if object_type is None:
        return None
    return CONCEPT_TYPE_LABELS.get(object_type)
