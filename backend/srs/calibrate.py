"""FSRS per-user desired-retention calibration.

Given a user's review history (predicted retrievability at review time +
actual recall outcome), estimate the ``desired_retention`` value that
minimises the gap between predicted and actual recall.

Algorithm
─────────
Reviews are bucketed by predicted retrievability in 0.1-wide bins.  For each
bucket we compute the actual recall rate (quality ≥ 2).  The calibration
*bias* is the weighted mean difference between actual recall rate and the
predicted retrievability at the bin midpoint.

A positive bias (actual > predicted) means the user's memory is consistently
stronger than the FSRS model assumes — reviews are happening more often than
necessary.  Lowering ``desired_retention`` extends the inter-review interval
while keeping the actual recall rate at the target level.

Formula
───────
    bias   = Σ (actual_i − predicted_i) × w_i  /  Σ w_i
    new_dr = DESIRED_RETENTION − bias

    w_i = bin_count_i × max(0.1, 1 − |bin_midpoint_i − DESIRED_RETENTION|)

Bins close to the current ``DESIRED_RETENTION`` are weighted more heavily
because they are most relevant to scheduled-review accuracy.

The result is clamped to [DR_MIN, DR_MAX] and requires at least
MIN_REVIEWS_FOR_CALIBRATION data points.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from backend.srs.fsrs import DESIRED_RETENTION

#: Minimum review events required before calibration is attempted.
MIN_REVIEWS_FOR_CALIBRATION: int = 30

#: Acceptable range for desired_retention.
DR_MIN: float = 0.70
DR_MAX: float = 0.97


@dataclass(frozen=True, slots=True)
class CalibrationResult:
    """Output of a single calibration run.

    Attributes
    ----------
    desired_retention:
        Calibrated value clamped to [DR_MIN, DR_MAX].
    reviews_used:
        Number of review events consumed.
    calibration_rmse:
        Root-mean-square error between predicted and actual recall rates
        across bins that had ≥ 3 reviews.  Lower is a better fit.
        ``None`` when fewer than two bins were sufficiently populated.
    """
    desired_retention: float
    reviews_used: int
    calibration_rmse: float | None


def calibrate(
    events: list[tuple[float, int]],
) -> CalibrationResult | None:
    """Estimate the user's optimal desired_retention from their review history.

    Parameters
    ----------
    events:
        List of ``(mastery_score_before, quality)`` tuples sourced from
        ``ReviewEventRow``.  ``mastery_score_before`` is the FSRS
        retrievability R ∈ [0, 1] at review time; ``quality`` is the
        learner's 1–4 self-rating (2–4 = successful recall).

    Returns
    -------
    ``CalibrationResult`` or ``None`` when there are fewer than
    ``MIN_REVIEWS_FOR_CALIBRATION`` events.
    """
    n = len(events)
    if n < MIN_REVIEWS_FOR_CALIBRATION:
        return None

    # ── Build 0.1-wide bins ────────────────────────────────────────────────────
    # bin 0: [0.0, 0.1), bin 1: [0.1, 0.2), ..., bin 9: [0.9, 1.0]
    bin_count:   list[int] = [0] * 10
    bin_recalls: list[int] = [0] * 10
    for r_pred, quality in events:
        b = min(9, int(r_pred * 10))
        bin_count[b]   += 1
        bin_recalls[b] += 1 if quality >= 2 else 0

    # ── Compute weighted calibration bias ─────────────────────────────────────
    # Weight = bin_count × proximity to DESIRED_RETENTION, so that bins at
    # the scheduling threshold matter most.
    bias_numer: float = 0.0
    bias_denom: float = 0.0
    rmse_sum:   float = 0.0
    rmse_bins:  int   = 0

    for b in range(10):
        count = bin_count[b]
        if count == 0:
            continue
        r_mid     = (b + 0.5) / 10.0
        r_actual  = bin_recalls[b] / count
        deviation = r_actual - r_mid
        proximity = 1.0 - abs(r_mid - DESIRED_RETENTION)  # ∈ (-0.45, 1.0]
        weight    = count * max(0.1, proximity)            # always positive
        bias_numer += deviation * weight
        bias_denom += weight
        if count >= 3:
            rmse_sum  += deviation ** 2
            rmse_bins += 1

    if bias_denom == 0.0:
        return None

    bias   = bias_numer / bias_denom
    new_dr = DESIRED_RETENTION - bias
    new_dr = max(DR_MIN, min(DR_MAX, new_dr))

    rmse = math.sqrt(rmse_sum / rmse_bins) if rmse_bins >= 2 else None

    return CalibrationResult(
        desired_retention=round(new_dr, 4),
        reviews_used=n,
        calibration_rmse=round(rmse, 4) if rmse is not None else None,
    )
