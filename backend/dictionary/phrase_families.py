"""Phrase-family catalog and cross-variant surface matcher.

A *phrase family* groups surface variants of the same underlying expression:
alternate spellings, word-order permutations, extended/truncated forms, and
confusable neighboring expressions.

Data model
──────────
PhraseVariant   — one surface form that belongs to a family, with optional notes.
PhraseFamily    — the full family record: canonical form, all variants, metadata,
                  and a list of IDs of confusable families.

Matching
────────
``match_phrase_families(tokens, language)`` scans a token sequence and returns
one ``CandidateObject`` per matched family (longest-match, no overlaps).
Surface matching is case-insensitive and ignores punctuation tokens so that
"All that glitters is not gold." hits the same family as the bare phrase.

Adding families
───────────────
Add entries to ``_FAMILY_CATALOG``.  Key = family ID (stable slug).
``canonical_form`` should be the most widely cited variant.
``variants`` must include every form you want to detect.
``confusables`` is a list of other family IDs — shown in the lesson so learners
understand the distinction.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from backend.schemas.parse import CandidateObject


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PhraseVariant:
    surface: str
    canonical: bool = False
    notes: str | None = None


@dataclass(frozen=True)
class PhraseFamily:
    id: str
    language: str
    canonical_form: str
    variants: tuple[PhraseVariant, ...]
    meaning: str
    register: str           # "neutral" | "literary" | "formal" | "informal" | "archaic"
    origin: str | None = None
    confusables: tuple[str, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)


# ── English catalog ───────────────────────────────────────────────────────────

_FAMILY_CATALOG: dict[str, PhraseFamily] = {

    "all_that_glitters": PhraseFamily(
        id="all_that_glitters",
        language="en",
        canonical_form="all that glitters is not gold",
        variants=(
            PhraseVariant(
                surface="all that glitters is not gold",
                canonical=True,
            ),
            PhraseVariant(
                surface="all that glisters is not gold",
                notes="original spelling — Shakespeare, Merchant of Venice (1596)",
            ),
            PhraseVariant(
                surface="not all that glitters is gold",
                notes="word-order inversion — same meaning, more emphatic",
            ),
            PhraseVariant(
                surface="all that is gold does not glitter",
                notes="Tolkien reversal — The Fellowship of the Ring (1954); inverts the proverb",
            ),
        ),
        meaning="Appearances can be deceptive; something attractive may not be valuable.",
        register="literary",
        origin="Shakespeare, Merchant of Venice (1596); modernised spelling entered common use by the 18th century.",
        confusables=("of_the_first_water",),
        tags=("proverb", "appearance", "deception"),
    ),

    "of_the_first_water": PhraseFamily(
        id="of_the_first_water",
        language="en",
        canonical_form="of the first water",
        variants=(
            PhraseVariant(
                surface="of the first water",
                canonical=True,
            ),
            PhraseVariant(
                surface="of the finest water",
                notes="variant — emphasises quality rather than rank",
            ),
        ),
        meaning="Of the highest quality or most extreme degree (originally of gemstones, especially diamonds).",
        register="literary",
        origin="Gem-grading terminology — diamond clarity formerly classified by 'water' (transparency); "
               "figurative use from early 19th century.",
        confusables=("all_that_glitters",),
        tags=("quality", "gemstone", "archaic-idiom"),
    ),

    "hit_the_nail_on_the_head": PhraseFamily(
        id="hit_the_nail_on_the_head",
        language="en",
        canonical_form="hit the nail on the head",
        variants=(
            PhraseVariant(
                surface="hit the nail on the head",
                canonical=True,
            ),
            PhraseVariant(
                surface="hits the nail on the head",
                notes="third-person inflection",
            ),
            PhraseVariant(
                surface="hitting the nail on the head",
                notes="progressive aspect",
            ),
        ),
        meaning="To describe or identify something exactly right.",
        register="neutral",
        origin="Common English idiom; attested from at least the 16th century.",
        confusables=(),
        tags=("accuracy", "precision"),
    ),

    "bite_the_bullet": PhraseFamily(
        id="bite_the_bullet",
        language="en",
        canonical_form="bite the bullet",
        variants=(
            PhraseVariant(
                surface="bite the bullet",
                canonical=True,
            ),
            PhraseVariant(
                surface="biting the bullet",
                notes="participial form",
            ),
            PhraseVariant(
                surface="bit the bullet",
                notes="past tense",
            ),
        ),
        meaning="To endure a painful or unpleasant situation that is unavoidable.",
        register="neutral",
        origin="Possibly from pre-anaesthetic surgery where patients were given a bullet to clench; "
               "popularised through military literature.",
        confusables=(),
        tags=("endurance", "courage"),
    ),
}


# ── Token normalisation ────────────────────────────────────────────────────────

_PUNCT_RE = re.compile(r"[^\w\s]")


def _normalise(text: str) -> list[str]:
    """Lowercase, strip punctuation, split on whitespace."""
    return _PUNCT_RE.sub("", text.lower()).split()


# Pre-build normalised token lists for every variant so matching is O(1) per lookup.
_VARIANT_INDEX: dict[str, tuple[str, PhraseFamily]] = {}
for _fam in _FAMILY_CATALOG.values():
    for _var in _fam.variants:
        _key = " ".join(_normalise(_var.surface))
        if _key:
            _VARIANT_INDEX[_key] = (_var.surface, _fam)


# ── Public matcher ────────────────────────────────────────────────────────────

def match_phrase_families(
    tokens: list[str],
    language: str,
) -> list[CandidateObject]:
    """Scan *tokens* for phrase-family members and return CandidateObjects.

    Parameters
    ──────────
    tokens
        Sequence of surface-form word strings from the sentence (not yet
        normalised; punctuation tokens are accepted and will be ignored during
        matching).
    language
        BCP-47 language code used to filter the catalog (only families whose
        ``language`` matches are considered).

    Returns a list of ``CandidateObject`` with ``type="phrase_family"``.
    Results are longest-match, non-overlapping (greedy left-to-right).
    """
    norm_tokens = [_PUNCT_RE.sub("", t.lower()) for t in tokens]
    # Filter out empty strings produced by pure-punctuation tokens.
    # Keep original index mapping so we can reconstruct the surface span.
    indexed = [(i, t) for i, t in enumerate(norm_tokens) if t]

    # Collect family variants for this language, sorted longest-first.
    candidates_sorted = sorted(
        (
            (variant_norm, surface, fam)
            for variant_norm, (surface, fam) in _VARIANT_INDEX.items()
            if fam.language == language
        ),
        key=lambda x: -len(x[0].split()),
    )

    matched: list[CandidateObject] = []
    used_positions: set[int] = set()

    for variant_norm, surface, fam in candidates_sorted:
        vtokens = variant_norm.split()
        vlen = len(vtokens)
        # Slide a window of vlen over the sentence tokens.
        for start in range(len(indexed) - vlen + 1):
            window = indexed[start : start + vlen]
            positions = [orig_i for orig_i, _ in window]
            if any(p in used_positions for p in positions):
                continue
            window_text = [t for _, t in window]
            if window_text == vtokens:
                # Match found — find which variant this is for notes.
                matched_variant = next(
                    (v for v in fam.variants if " ".join(_normalise(v.surface)) == variant_norm),
                    None,
                )
                surface_span = " ".join(tokens[p] for p in positions)
                obj = _family_to_candidate(fam, surface_span, matched_variant)
                matched.append(obj)
                used_positions.update(positions)
                break  # move to next variant pattern

    return matched


def _family_to_candidate(
    fam: PhraseFamily,
    surface_span: str,
    matched_variant: PhraseVariant | None,
) -> CandidateObject:
    all_variants = [v.surface for v in fam.variants]
    lesson_data: dict[str, Any] = {
        "family_id":       fam.id,
        "canonical_form":  fam.canonical_form,
        "matched_variant": surface_span,
        "meaning":         fam.meaning,
        "register":        fam.register,
        "variants":        all_variants,
    }
    if fam.origin:
        lesson_data["origin"] = fam.origin
    if fam.confusables:
        lesson_data["confusables"] = list(fam.confusables)
    if matched_variant and matched_variant.notes:
        lesson_data["variant_note"] = matched_variant.notes
    if fam.tags:
        lesson_data["tags"] = list(fam.tags)

    is_canonical = matched_variant.canonical if matched_variant else False
    confidence = 0.92 if is_canonical else 0.85

    return CandidateObject(
        canonical_form=fam.id,
        surface_form=surface_span,
        type="phrase_family",
        label=surface_span,
        lesson_data=lesson_data,
        confidence=confidence,
    )
