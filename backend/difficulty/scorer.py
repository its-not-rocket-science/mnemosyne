"""Sentence difficulty scoring and curriculum progression.

All functions are pure (no I/O, no global state) so they can be tested
without a database and called cheaply in hot paths.

Difficulty model
────────────────
Each sentence receives a composite difficulty score in [0.0, 1.0] from
three components:

  unknown_ratio  (weight 0.55)
      Fraction of the sentence's learnable objects whose mastery score is
      below KNOWN_THRESHOLD.  This is the dominant signal: a sentence where
      the learner cannot recall most words is harder than one they know well
      regardless of grammar or length.

  grammar_score  (weight 0.25)
      Normalised density of grammatically complex object types relative to
      the total number of objects.  Supported types and their default weights:
        conjugation   → 0.70 (verb morphology; central to acquisition)
        agreement     → 0.30 (det/adj/noun agreement)
        case_agreement→ 0.00 (language-specific; see profiles.py)
      Pure vocabulary sentences score 0.  Weights and overall scale are
      calibrated per language via LanguageScoringProfile (see below).

  length_score   (weight 0.20)
      Sentence word count normalised to LENGTH_MAX_WORDS (25).  Longer
      sentences impose a higher working-memory load even when all words
      are known.  The ceiling is profile-adjustable for segmented scripts.

Multilingual fairness
─────────────────────
A plain scorer treats every language identically, which produces unfair
results.  German and Russian sentences are morphologically dense by design,
not by complexity — every noun phrase yields case_agreement objects, every
finite verb a conjugation.  Without calibration these languages always
score harder than Spanish at the same comprehension level.

Similarly, Chinese and Japanese text cannot be tokenised by whitespace, so
``text.split()`` returns ~1 token regardless of sentence length.  The
length signal collapses to near-zero for all CJK input.

The solution is ``LanguageScoringProfile`` (defined in ``difficulty.profiles``):
pass one to ``score_sentence()`` and it adjusts:

  grammar_weight_scale  — scales down grammar density for morphologically
                          rich languages where density is expected.
  length_max_words      — lowers the normalisation ceiling for segmented
                          scripts; use with word_count_hint=len(objects).
  conj_weight / agree_weight / case_agree_weight — per-type grammar weights
                          so case_agreement is counted for German etc.

The unknown_ratio component is NEVER profile-adjusted.  Encountering an
unknown word costs the same in every language.

Progression model
─────────────────
  Bootstrap (< 5 mastered): target the shortest, simplest sentences.  At
  this stage mastery=0 for all objects so unknown_ratio=1.0 everywhere;
  only grammar and length vary.  Window [0.50, 0.75] selects short/plain
  sentences while excluding long complex ones.

  Active learning (≥ 5 mastered): follow the i+1 principle — ~20% of
  objects should be new.  As the user masters more items the sentences that
  achieve this ratio are necessarily longer and more grammatically rich, so
  the target window shifts upward from [0.03, 0.27] to [0.28, 0.52].
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from backend.difficulty.profiles import LanguageScoringProfile

# ── Constants ────────────────────────────────────────────────────────────────

# Objects below this mastery score count as "unknown" for difficulty scoring.
# Mirrors FORGOTTEN_SCORE_THRESHOLD in srs.knowledge (kept inline to avoid
# coupling this pure module to the rest of the application).
KNOWN_THRESHOLD: float = 0.30

# Grammar-type weights: conjugations are harder than agreements, vocabulary
# contributes nothing to grammar complexity.
_CONJ_WEIGHT: float = 0.70
_AGREE_WEIGHT: float = 0.30

# Length normalisation ceiling: sentences longer than this score 1.0.
_LENGTH_MAX_WORDS: int = 25

# Component weights — must sum to 1.0.
_W_UNKNOWN: float = 0.55
_W_GRAMMAR: float = 0.25
_W_LENGTH:  float = 0.20

# Bootstrap threshold: fewer than this many mastered items → bootstrap mode.
_BOOTSTRAP_THRESHOLD: int = 5

# Progression bounds: minimum and maximum target-window centre.
_ACTIVE_CENTER_MIN: float = 0.15  # at _BOOTSTRAP_THRESHOLD mastered
_ACTIVE_CENTER_MAX: float = 0.40  # at _PROGRESSION_CAP mastered
_PROGRESSION_CAP:   int   = 100   # mastered count at which window stops moving
_HALF_WIDTH:        float = 0.12  # half-width of the active window


# ── Data types ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ObjectMastery:
    """Mastery snapshot for one learnable object in a sentence."""
    object_id: str
    obj_type: str    # "vocabulary" | "conjugation" | "agreement" | ...
    mastery_score: float
    total_reviews: int


@dataclass(frozen=True)
class DifficultyScore:
    """Composite difficulty score for a single sentence."""
    difficulty: float      # composite 0.0–1.0
    unknown_ratio: float   # fraction of objects below KNOWN_THRESHOLD
    grammar_score: float   # grammatical complexity 0.0–1.0
    length_score: float    # normalised sentence length 0.0–1.0
    known_count: int
    unknown_count: int
    total_objects: int


# ── Scoring ───────────────────────────────────────────────────────────────────


def score_sentence(
    objects: list[ObjectMastery],
    text: str,
    word_count_hint: int | None = None,
    profile: "LanguageScoringProfile | None" = None,
) -> DifficultyScore:
    """Score a sentence's difficulty given the user's current mastery of its objects.

    Parameters
    ----------
    objects:
        One ``ObjectMastery`` per learnable object extracted from the sentence.
        May be empty for punctuation-only sentences.
    text:
        Raw sentence text; used for word-count estimation when
        *word_count_hint* is not provided.
    word_count_hint:
        Optional override for the word count used in the length score.
        Supply this for languages where ``text.split()`` is meaningless —
        notably CJK and other segmented-script languages.  Plugins can pass
        ``len(objects)`` as a conservative proxy, or a model-derived token
        count.  When ``None``, the function falls back to ``len(text.split())``.
    profile:
        Optional ``LanguageScoringProfile`` from ``difficulty.profiles``.
        When supplied, grammar weights, length ceiling, and the grammar
        contribution scale are taken from the profile.  When ``None`` the
        module-level defaults apply, preserving backward compatibility.

    Returns
    -------
    DifficultyScore
        All components are in [0.0, 1.0].  When *objects* is empty, difficulty
        is 0.0 (the sentence contributes nothing to the learning agenda).

    Notes
    -----
    The ``unknown_ratio`` component is never profile-adjusted.  Encountering
    an unknown word costs equally regardless of language.
    """
    length_max = profile.length_max_words if profile is not None else _LENGTH_MAX_WORDS
    ls = _length_score(text, word_count_hint, length_max)

    if not objects:
        return DifficultyScore(
            difficulty=0.0,
            unknown_ratio=0.0,
            grammar_score=0.0,
            length_score=ls,
            known_count=0,
            unknown_count=0,
            total_objects=0,
        )

    total = len(objects)
    unknown = sum(1 for o in objects if o.mastery_score < KNOWN_THRESHOLD)

    conj_count       = sum(1 for o in objects if o.obj_type == "conjugation")
    agree_count      = sum(1 for o in objects if o.obj_type == "agreement")
    case_agree_count = sum(1 for o in objects if o.obj_type == "case_agreement")

    # Resolve per-type weights from profile or module defaults.
    if profile is not None:
        conj_w       = profile.conj_weight
        agree_w      = profile.agree_weight
        case_agree_w = profile.case_agree_weight
        gw_scale     = profile.grammar_weight_scale
    else:
        conj_w       = _CONJ_WEIGHT
        agree_w      = _AGREE_WEIGHT
        case_agree_w = 0.0
        gw_scale     = 1.0

    unknown_ratio = unknown / total
    grammar_raw = (
        (conj_count       / total) * conj_w
        + (agree_count    / total) * agree_w
        + (case_agree_count / total) * case_agree_w
    )
    # Apply the language-specific scale: morphologically dense languages get
    # their grammar contribution discounted toward the expected baseline.
    grammar_score = min(grammar_raw * gw_scale, 1.0)

    difficulty = round(
        _W_UNKNOWN * unknown_ratio
        + _W_GRAMMAR * grammar_score
        + _W_LENGTH  * ls,
        4,
    )

    return DifficultyScore(
        difficulty=min(difficulty, 1.0),
        unknown_ratio=round(unknown_ratio, 4),
        grammar_score=round(grammar_score, 4),
        length_score=ls,
        known_count=total - unknown,
        unknown_count=unknown,
        total_objects=total,
    )


def _length_score(
    text: str,
    word_count_hint: int | None = None,
    length_max: int = _LENGTH_MAX_WORDS,
) -> float:
    word_count = word_count_hint if word_count_hint is not None else len(text.split())
    return round(min(word_count / length_max, 1.0), 4)


# ── Difficulty labels ─────────────────────────────────────────────────────────

DifficultyLabel = Literal["easy", "ideal", "hard"]


def difficulty_label(unknown_ratio: float) -> DifficultyLabel:
    """Classify a sentence's challenge level for the current user.

    Maps the fraction of unknown objects to a named band:

      easy   — <15% unknown (>85% known): very little new material,
               safe for extensive reading but limited learning value.
      ideal  — 15–40% unknown (60–85% known): follows the i+1
               comprehensible-input principle; controlled novelty.
      hard   — >40% unknown (<60% known): too much new material to
               sustain comprehension without heavy lookup support.

    The 15% / 40% thresholds are slightly widened from the spec's
    10% / 30% to give the "ideal" band a broader, more forgiving range
    that accommodates the scorer's grammar and length components.
    """
    if unknown_ratio < 0.15:
        return "easy"
    if unknown_ratio <= 0.40:
        return "ideal"
    return "hard"


# ── Progression ───────────────────────────────────────────────────────────────

UserLevel = Literal["beginner", "elementary", "intermediate", "advanced"]


def target_difficulty_window(total_mastered: int) -> tuple[float, float]:
    """Return the (min, max) difficulty window appropriate for the user's level.

    See module docstring for the full progression model.
    """
    if total_mastered < _BOOTSTRAP_THRESHOLD:
        return (0.50, 0.75)

    # progress: 0.0 when total_mastered == _BOOTSTRAP_THRESHOLD,
    #           1.0 when total_mastered == _PROGRESSION_CAP
    progress = min(
        (total_mastered - _BOOTSTRAP_THRESHOLD) / (_PROGRESSION_CAP - _BOOTSTRAP_THRESHOLD),
        1.0,
    )
    center = _ACTIVE_CENTER_MIN + progress * (_ACTIVE_CENTER_MAX - _ACTIVE_CENTER_MIN)
    low  = round(max(0.0, center - _HALF_WIDTH), 4)
    high = round(min(1.0, center + _HALF_WIDTH), 4)
    return (low, high)


def user_level_label(total_mastered: int) -> UserLevel:
    """Map mastered-item count to a human-readable proficiency label."""
    if total_mastered < 5:
        return "beginner"
    if total_mastered < 20:
        return "elementary"
    if total_mastered < 60:
        return "intermediate"
    return "advanced"
