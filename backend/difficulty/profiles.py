"""Language-specific calibration for sentence difficulty scoring.

Problem
───────
The default scorer treats every language identically: unknown_ratio dominates,
grammar_score counts conjugations and agreements, length_score uses whitespace
tokenization.  This produces systematically unfair results across language
families:

  Morphologically rich languages (German, Russian, Arabic, Finnish):
      Every noun phrase produces agreement objects, every verb a conjugation
      object.  A simple German sentence like "Der alte Mann liest das Buch"
      yields case_agreement objects for both noun phrases plus a conjugation,
      giving a high grammar_score even though the sentence is elementary.
      Without calibration, German always scores harder than Spanish at the
      same comprehension level — unfairly discouraging learners.

  Character-segmented languages (Chinese, Japanese):
      ``text.split()`` returns a single token for most CJK sentences because
      there are no inter-word spaces.  The default length_score is therefore
      near zero for all CJK input, eliminating length as a useful signal.
      A fifteen-character Japanese sentence scores the same length as "Hi."

  Analytic languages (English, Mandarin Chinese):
      These languages use minimal inflection.  Agreement objects are rare.
      The grammar component (weighted 0.25) rarely fires, leaving the score
      driven almost entirely by unknown_ratio.  This is largely correct but
      can over-reward familiarity with common words in opaque ways.

Solution: LanguageScoringProfile
─────────────────────────────────
Each profile has three adjustable knobs:

  grammar_weight_scale (default 1.0):
      A multiplier applied to the raw grammar component before it contributes
      to difficulty.  Set below 1.0 for languages where grammatical object
      density is expected and unremarkable:

          de (German)  → 0.65  — case_agreement objects are ubiquitous;
                                  their presence marks morphological exposure,
                                  not exceptional complexity.
          ar (Arabic)  → 0.60  — triconsonantal morphology produces many
                                  object types per root; density is normal.
          ru (Russian) → 0.60  — six-case system creates dense agreement;
                                  like German but with no articles.
          he (Hebrew)  → 0.65  — similar to Arabic morphological richness.
          en (English) → 0.85  — analytic; slight downscale because even
                                  rare conjugation objects are learnable.

  length_max_words (default 25):
      The word-count ceiling for the length normalisation.  Sentences longer
      than this score 1.0.  For segmented languages, lower this to match
      the shorter typical sentence unit count (measured by object count, not
      whitespace tokens):

          zh (Chinese) → 10   — meaningful units per sentence are shorter;
          ja (Japanese)→ 12     object count is a better proxy than split().
          ko (Korean)  → 15   — morpheme-rich; object count preferred.

  conj_weight / agree_weight / case_agree_weight (defaults 0.70 / 0.30 / 0.0):
      Within-grammar weights summing to the per-object grammar contribution.
      Languages with ``case_agreement`` objects (German, Russian, etc.) need a
      non-zero ``case_agree_weight``; the conjugation and agreement weights
      should be adjusted so the total remains meaningful:

          de: conj=0.40, agree=0.10, case_agree=0.50
              — conjugation and case_agreement both contribute, with case
                carrying more weight than bare agreement.

Fairness principle
──────────────────
Profiles should never make an objectively harder sentence appear easier.  They
calibrate *expectation* — morphological density that is routine for a
language's grammar should not unfairly inflate difficulty compared to a
language where such density is exceptional.  The unknown_ratio component
(weight 0.55) is never profile-adjusted: encountering an unknown word is
equally costly regardless of language.

Extending profiles
──────────────────
Add an entry to ``_PROFILES`` keyed by the two-character BCP-47 prefix.
If no entry exists, ``get_profile()`` returns the default (all defaults →
equivalent to the pre-profile scorer behaviour).  This ensures backward
compatibility when a new plugin language has no explicit profile.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LanguageScoringProfile:
    """Calibration parameters for ``score_sentence`` on a specific language.

    All fields have defaults that reproduce the original scorer behaviour,
    so a default-constructed profile is a safe no-op for any language.
    """

    # ── Length normalisation ───────────────────────────────────────────────────

    length_max_words: int = 25
    """Word / unit count at which the length score reaches 1.0.

    For whitespace-segmented languages use the default (25).
    For character-segmented languages set this to the typical count of
    meaningful units (learnable objects) per sentence.
    """

    # ── Grammar calibration ───────────────────────────────────────────────────

    grammar_weight_scale: float = 1.0
    """Multiplier on the raw grammar component before it enters difficulty.

    Range [0.0, 1.0].  1.0 = no adjustment (baseline).  Set below 1.0 for
    languages where high grammatical object density is expected and does
    not signal exceptional learning challenge.
    """

    conj_weight: float = 0.70
    """Within-grammar weight for ``conjugation`` objects.  Default 0.70."""

    agree_weight: float = 0.30
    """Within-grammar weight for ``agreement`` objects.  Default 0.30."""

    case_agree_weight: float = 0.00
    """Within-grammar weight for ``case_agreement`` objects.  Default 0.0.

    Set this for languages that emit ``case_agreement`` objects (German,
    Russian, Latin, etc.).  The sum ``conj_weight + agree_weight +
    case_agree_weight`` represents the maximum possible raw grammar value
    per object when all objects are of a single grammar type.
    """


# ── Built-in profiles ─────────────────────────────────────────────────────────
# Keyed by two-character BCP-47 language prefix (lower-case).
# Languages not listed fall back to the default profile (all defaults).

_PROFILES: dict[str, LanguageScoringProfile] = {
    # ── Romance / Latin-script ────────────────────────────────────────────────
    "es": LanguageScoringProfile(),           # baseline — default profile
    "fr": LanguageScoringProfile(),           # similar morphological density to es
    "pt": LanguageScoringProfile(),
    "it": LanguageScoringProfile(),
    "ro": LanguageScoringProfile(grammar_weight_scale=0.90),  # richer case system
    "la": LanguageScoringProfile(
        grammar_weight_scale=0.60,
        conj_weight=0.35,
        agree_weight=0.25,
        case_agree_weight=0.40,
    ),

    # ── Germanic ─────────────────────────────────────────────────────────────
    "en": LanguageScoringProfile(grammar_weight_scale=0.85),
    "de": LanguageScoringProfile(
        grammar_weight_scale=0.65,
        # German emits case_agreement for every noun phrase; conjugation is
        # still important but case is the dominant structural challenge.
        conj_weight=0.40,
        agree_weight=0.10,
        case_agree_weight=0.50,
    ),
    "nl": LanguageScoringProfile(grammar_weight_scale=0.90),
    "sv": LanguageScoringProfile(grammar_weight_scale=0.90),
    "no": LanguageScoringProfile(grammar_weight_scale=0.90),
    "da": LanguageScoringProfile(grammar_weight_scale=0.90),

    # ── Slavic ───────────────────────────────────────────────────────────────
    "ru": LanguageScoringProfile(
        grammar_weight_scale=0.60,
        conj_weight=0.35,
        agree_weight=0.25,
        case_agree_weight=0.40,
    ),
    "pl": LanguageScoringProfile(
        grammar_weight_scale=0.62,
        conj_weight=0.35,
        agree_weight=0.25,
        case_agree_weight=0.40,
    ),
    "cs": LanguageScoringProfile(
        grammar_weight_scale=0.62,
        conj_weight=0.35,
        agree_weight=0.25,
        case_agree_weight=0.40,
    ),
    "uk": LanguageScoringProfile(grammar_weight_scale=0.62),

    # ── Semitic ───────────────────────────────────────────────────────────────
    "ar": LanguageScoringProfile(grammar_weight_scale=0.60),
    "he": LanguageScoringProfile(grammar_weight_scale=0.65),

    # ── CJK and segmented scripts ─────────────────────────────────────────────
    # length_max_words is lowered because object_count (the recommended
    # word_count_hint proxy for these languages) is much smaller than the
    # whitespace token count of a typical sentence.
    "zh": LanguageScoringProfile(
        length_max_words=10,
        grammar_weight_scale=0.50,  # analytic — explicit grammar markers are rare
    ),
    "ja": LanguageScoringProfile(
        length_max_words=12,
        grammar_weight_scale=0.55,
    ),
    "ko": LanguageScoringProfile(
        length_max_words=15,
        grammar_weight_scale=0.70,
    ),

    # ── Indic / Devanagari ────────────────────────────────────────────────────
    "hi": LanguageScoringProfile(grammar_weight_scale=0.75),
    "sa": LanguageScoringProfile(
        grammar_weight_scale=0.55,   # Sanskrit: very rich morphology
        conj_weight=0.35,
        agree_weight=0.25,
        case_agree_weight=0.40,
    ),

    # ── Agglutinative ─────────────────────────────────────────────────────────
    "tr": LanguageScoringProfile(
        grammar_weight_scale=0.60,   # Turkish: very high morpheme-per-word ratio
        length_max_words=15,          # agglutinative words are long; fewer per sentence
    ),
    "fi": LanguageScoringProfile(
        grammar_weight_scale=0.58,
        length_max_words=18,
    ),
    "hu": LanguageScoringProfile(
        grammar_weight_scale=0.60,
        length_max_words=18,
    ),
}


def get_profile(language_code: str) -> LanguageScoringProfile:
    """Return the calibration profile for *language_code*.

    Looks up by two-character BCP-47 prefix.  Returns the default profile
    (equivalent to pre-profile scorer behaviour) for any language not listed.
    This is intentionally safe: an uncalibrated language gets the neutral
    baseline, not a broken one.

    Args:
        language_code: BCP-47 tag, e.g. ``"es"``, ``"de"``, ``"zh-TW"``.

    Returns:
        The matching ``LanguageScoringProfile``, or the default profile.
    """
    prefix = language_code[:2].lower()
    return _PROFILES.get(prefix, LanguageScoringProfile())
