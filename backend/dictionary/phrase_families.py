"""Phrase-family catalog and cross-variant surface matcher.

A *phrase family* groups surface variants of the same underlying expression:
alternate spellings, word-order permutations, modernised forms, misquotations,
allusions, blends, and confusable neighbouring expressions.

Data model
──────────
MatchType       — how a surface variant relates to the canonical form.
PhraseVariant   — one surface form, its MatchType, and an optional note.
PhraseFamily    — canonical form, all variants, rich metadata (origin,
                  source_text, why_it_matters), and cross-family confusable IDs.

Confidence is derived automatically from MatchType via _MATCH_TYPE_CONFIDENCE,
so each variant no longer carries an explicit float.

Matching
────────
``match_phrase_families(tokens, language)`` scans a token sequence and returns
one ``CandidateObject`` per matched family (longest-match, no overlaps).
Surface matching is case-insensitive and ignores punctuation tokens.

lesson_data keys emitted
────────────────────────
  canonical_form, matched_variant, match_type (str value of MatchType),
  match_type_note, meaning, register, origin, source_text, why_it_matters,
  variants (list[dict] with surface/match_type/note; excludes confusable_not_same),
  confusable_forms (list[dict] surface/note — within-family confusables),
  confusables (list[str] — IDs of other confusable families),
  tags.

Adding families
───────────────
Add entries to ``_FAMILY_CATALOG``.  Key = family ID (stable slug).
``canonical_form`` should be the most widely cited variant.
All variants must have a ``match_type``; the canonical surface form should use
``MatchType.exact``.
``confusables`` lists IDs of *other* families shown as cross-references.
Within-family confusable surfaces use ``MatchType.confusable_not_same``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from backend.schemas.parse import CandidateObject


# ── Match-type taxonomy ───────────────────────────────────────────────────────

class MatchType(str, Enum):
    """Relationship between a detected surface form and the canonical phrase."""
    exact                = "exact"
    orthographic_variant = "orthographic_variant"   # spelling change only
    modernized_variant   = "modernized_variant"     # archaic → contemporary form
    inflectional_variant = "inflectional_variant"   # morphological change (tense, number)
    misquotation         = "misquotation"           # wrong word order or word substitution
    blend                = "blend"                  # fusion of two different phrases
    allusion             = "allusion"               # indirect / transformed reference
    confusable_not_same  = "confusable_not_same"    # surface-similar but semantically distinct


# Detection confidence keyed by match type.
_MATCH_TYPE_CONFIDENCE: dict[MatchType, float] = {
    MatchType.exact:                0.95,
    MatchType.orthographic_variant: 0.90,
    MatchType.modernized_variant:   0.88,
    MatchType.inflectional_variant: 0.85,
    MatchType.misquotation:         0.70,
    MatchType.blend:                0.62,
    MatchType.allusion:             0.75,
    MatchType.confusable_not_same:  0.65,
}


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class PhraseVariant:
    surface:    str
    match_type: MatchType
    note:       str | None = None   # shown in UI when this variant is matched


@dataclass(frozen=True)
class PhraseFamily:
    id:             str
    language:       str
    canonical_form: str
    variants:       tuple[PhraseVariant, ...]
    meaning:        str
    register:       str             # "neutral" | "literary" | "formal" | "informal" | "archaic"
    origin:         str | None = None
    source_text:    str | None = None   # primary attribution / citation line
    why_it_matters: str | None = None   # learner-facing significance
    confusables:    tuple[str, ...] = field(default_factory=tuple)  # IDs of other families
    tags:           tuple[str, ...] = field(default_factory=tuple)


# ── English catalog ───────────────────────────────────────────────────────────

_FAMILY_CATALOG: dict[str, PhraseFamily] = {

    # ── All that glisters / glitters ─────────────────────────────────────────

    "all_that_glitters": PhraseFamily(
        id="all_that_glitters",
        language="en",
        canonical_form="all that glisters is not gold",
        meaning=(
            "Appearances can be deceptive; surface attractiveness does not "
            "indicate true worth."
        ),
        register="literary",
        origin=(
            "The Prince of Morocco reads the golden-casket inscription: "
            "\u201cAll that glisters is not gold; / Often have you heard that told.\u201d "
            "The verb \u2018glisters\u2019 (archaic for \u2018glitters\u2019) was "
            "standard Elizabethan usage. By the 18th century the modernised "
            "\u2018glitters\u2019 form had entered common circulation, and Tolkien "
            "later inverted the whole proverb to characterise Aragorn."
        ),
        source_text="Shakespeare, Merchant of Venice, II.vii.65 (c.\u202f1596)",
        why_it_matters=(
            "This is one of the most misquoted lines in English literature. "
            "Three independent distortions are documented: (1)\u00a0the archaic "
            "\u2018glisters\u2019 is replaced by \u2018glitters\u2019 (modernisation), "
            "(2)\u00a0the syntax is inverted to \u2018not all that glitters is gold\u2019 "
            "(logical shift), and (3)\u00a0Tolkien deliberately reversed the proverb to "
            "signal that Aragorn\u2019s plain appearance conceals royalty. Identifying "
            "which form you are reading \u2014 and why \u2014 is a marker of close reading."
        ),
        variants=(
            PhraseVariant(
                surface="all that glisters is not gold",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="all that glitters is not gold",
                match_type=MatchType.modernized_variant,
                note="\u2018Glisters\u2019 modernised to \u2018glitters\u2019; now the dominant everyday form.",
            ),
            PhraseVariant(
                surface="not all that glitters is gold",
                match_type=MatchType.misquotation,
                note="Word order inverted: logical emphasis shifts from \u2018not gold\u2019 to \u2018not all\u2019.",
            ),
            PhraseVariant(
                surface="all that is gold does not glitter",
                match_type=MatchType.allusion,
                note="Tolkien\u2019s deliberate reversal in The Fellowship of the Ring (1954), "
                     "used to signal Aragorn\u2019s concealed identity.",
            ),
            PhraseVariant(
                surface="all that shines is not gold",
                match_type=MatchType.blend,
                note="Blends \u2018glisters/glitters\u2019 with \u2018shines\u2019; not attested in classical sources.",
            ),
            # confusable_not_same: matches tokens but inverts the meaning
            PhraseVariant(
                surface="all that glitters is gold",
                match_type=MatchType.confusable_not_same,
                note="Omits \u2018not\u2019 \u2014 inverts the proverb entirely. Often used ironically or in parody.",
            ),
        ),
        confusables=("gild_the_lily",),
        tags=("shakespeare", "proverb", "appearance", "deception", "misquotation"),
    ),

    # ── Of the first water ────────────────────────────────────────────────────

    "of_the_first_water": PhraseFamily(
        id="of_the_first_water",
        language="en",
        canonical_form="of the first water",
        meaning=(
            "Of the highest quality or most extreme degree."
        ),
        register="literary",
        origin=(
            "Gem-graders formerly classified diamond clarity and brilliance in "
            "grades of \u2018water\u2019 (transparency); \u2018first water\u2019 "
            "denoted the finest, most transparent stone. Figurative use spread "
            "through English prose and journalism in the early 19th century."
        ),
        source_text="Lapidary trade terminology; figurative use attested from c.\u202f1820",
        why_it_matters=(
            "The phrase is now largely archaic in everyday speech but survives in "
            "formal, legal, and literary registers. Recognising it prevents "
            "misreading: \u2018water\u2019 here has nothing to do with liquid \u2014 "
            "it is a technical term from the diamond trade."
        ),
        variants=(
            PhraseVariant(
                surface="of the first water",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="of the finest water",
                match_type=MatchType.orthographic_variant,
                note="\u2018First\u2019 replaced by \u2018finest\u2019; shifts emphasis from rank to quality.",
            ),
        ),
        confusables=(),
        tags=("quality", "gemstone", "archaic-idiom"),
    ),

    # ── Hit the nail on the head ──────────────────────────────────────────────

    "hit_the_nail_on_the_head": PhraseFamily(
        id="hit_the_nail_on_the_head",
        language="en",
        canonical_form="hit the nail on the head",
        meaning="To describe or identify something exactly right.",
        register="neutral",
        origin="Common English idiom attested from at least the 16th century.",
        source_text="Attested in English from c.\u202f1500",
        why_it_matters=(
            "One of the most productive idioms for inflectional variation: it "
            "appears freely in all tenses and aspects. Learners should recognise "
            "it across \u2018hit\u2019, \u2018hits\u2019, and \u2018hitting\u2019 forms."
        ),
        variants=(
            PhraseVariant(
                surface="hit the nail on the head",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="hits the nail on the head",
                match_type=MatchType.inflectional_variant,
                note="Third-person singular present.",
            ),
            PhraseVariant(
                surface="hitting the nail on the head",
                match_type=MatchType.inflectional_variant,
                note="Progressive aspect.",
            ),
            PhraseVariant(
                surface="hit the nail right on the head",
                match_type=MatchType.blend,
                note="\u2018Right\u2019 inserted as an intensifier; common in informal speech.",
            ),
        ),
        confusables=(),
        tags=("accuracy", "precision"),
    ),

    # ── Bite the bullet ───────────────────────────────────────────────────────

    "bite_the_bullet": PhraseFamily(
        id="bite_the_bullet",
        language="en",
        canonical_form="bite the bullet",
        meaning="To endure a painful or unpleasant situation that is unavoidable.",
        register="neutral",
        origin=(
            "Possibly from pre-anaesthetic military surgery, where patients "
            "were given a leather strap or bullet to bite during procedures. "
            "Popularised in print by Rudyard Kipling."
        ),
        source_text="19th-century military usage; popularised by Kipling",
        why_it_matters=(
            "Frequently confused with \u2018bite the dust\u2019 (to fail or die). "
            "The distinction matters: \u2018bite the bullet\u2019 implies enduring "
            "hardship with courage, while \u2018bite the dust\u2019 implies defeat "
            "or death."
        ),
        variants=(
            PhraseVariant(
                surface="bite the bullet",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="biting the bullet",
                match_type=MatchType.inflectional_variant,
                note="Participial / progressive form.",
            ),
            PhraseVariant(
                surface="bit the bullet",
                match_type=MatchType.inflectional_variant,
                note="Simple past.",
            ),
            PhraseVariant(
                surface="bite the dust",
                match_type=MatchType.confusable_not_same,
                note="Different phrase: means to fail or die, not to endure hardship with courage.",
            ),
        ),
        confusables=(),
        tags=("endurance", "courage", "military"),
    ),

    # ── Gild the lily ─────────────────────────────────────────────────────────
    # Added as a cross-family confusable for all_that_glitters (both use
    # gold imagery and Shakespeare authorship, but meanings are distinct).

    "gild_the_lily": PhraseFamily(
        id="gild_the_lily",
        language="en",
        canonical_form="gild the lily",
        meaning=(
            "To add unnecessary ornamentation to something already beautiful "
            "or complete; to over-embellish."
        ),
        register="literary",
        origin=(
            "The phrase is itself a misquotation of Shakespeare\u2019s King John, "
            "IV.ii.11: \u201cTo gild refined gold, to paint the lily \u2026 is "
            "wasteful and ridiculous excess.\u201d The popular condensed form "
            "\u2018gild the lily\u2019 blends Shakespeare\u2019s two separate images."
        ),
        source_text="Adapted from Shakespeare, King John, IV.ii.11 (c.\u202f1595)",
        why_it_matters=(
            "The phrase is itself a misquotation \u2014 Shakespeare wrote "
            "\u2018paint the lily\u2019 and \u2018gild refined gold\u2019 as "
            "separate examples. The popular form merges them. It is easily "
            "confused with \u2018all that glitters is not gold\u2019 because "
            "both involve gold imagery and Shakespeare authorship, but the "
            "meanings are distinct: gilding is about excess; glittering is "
            "about deception."
        ),
        variants=(
            PhraseVariant(
                surface="gild the lily",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="gilding the lily",
                match_type=MatchType.inflectional_variant,
                note="Participial form; common as an adjectival phrase.",
            ),
            PhraseVariant(
                surface="gilded the lily",
                match_type=MatchType.inflectional_variant,
                note="Simple past.",
            ),
            PhraseVariant(
                surface="paint the lily",
                match_type=MatchType.allusion,
                note="Shakespeare\u2019s original image; "
                     "the condensed \u2018gild the lily\u2019 is itself a misquotation.",
            ),
        ),
        confusables=("all_that_glitters",),
        tags=("shakespeare", "excess", "embellishment", "misquotation"),
    ),
}


# ── Token normalisation ────────────────────────────────────────────────────────

_PUNCT_RE = re.compile(r"[^\w\s]")


def _normalise(text: str) -> list[str]:
    """Lowercase, strip punctuation, split on whitespace."""
    return _PUNCT_RE.sub("", text.lower()).split()


# Pre-build: variant normalised string → (display surface, family, variant).
_VARIANT_INDEX: dict[str, tuple[str, PhraseFamily, PhraseVariant]] = {}
for _fam in _FAMILY_CATALOG.values():
    for _var in _fam.variants:
        _key = " ".join(_normalise(_var.surface))
        if _key:
            _VARIANT_INDEX[_key] = (_var.surface, _fam, _var)


# ── Public matcher ────────────────────────────────────────────────────────────

def match_phrase_families(
    tokens: list[str],
    language: str,
) -> list[CandidateObject]:
    """Scan *tokens* for phrase-family members and return CandidateObjects.

    Parameters
    ──────────
    tokens
        Surface-form word strings (punctuation tokens accepted; ignored during
        matching).
    language
        BCP-47 code; only families whose ``language`` matches are considered.

    Returns a list of ``CandidateObject`` with ``type="phrase_family"``.
    Results are longest-match, non-overlapping (greedy left-to-right).
    """
    norm_tokens = [_PUNCT_RE.sub("", t.lower()) for t in tokens]
    indexed = [(i, t) for i, t in enumerate(norm_tokens) if t]

    candidates_sorted = sorted(
        (
            (variant_norm, surface, fam, var)
            for variant_norm, (surface, fam, var) in _VARIANT_INDEX.items()
            if fam.language == language
        ),
        key=lambda x: -len(x[0].split()),
    )

    matched: list[CandidateObject] = []
    used_positions: set[int] = set()

    for variant_norm, surface, fam, variant in candidates_sorted:
        vtokens = variant_norm.split()
        vlen    = len(vtokens)
        for start in range(len(indexed) - vlen + 1):
            window    = indexed[start : start + vlen]
            positions = [orig_i for orig_i, _ in window]
            if any(p in used_positions for p in positions):
                continue
            if [t for _, t in window] == vtokens:
                surface_span = " ".join(tokens[p] for p in positions)
                obj = _family_to_candidate(fam, surface_span, variant)
                matched.append(obj)
                used_positions.update(positions)
                break

    return matched


# ── Candidate builder ─────────────────────────────────────────────────────────

def _family_to_candidate(
    fam: PhraseFamily,
    surface_span: str,
    matched_variant: PhraseVariant | None,
) -> CandidateObject:
    match_type = matched_variant.match_type if matched_variant else MatchType.exact
    confidence = _MATCH_TYPE_CONFIDENCE.get(match_type, 0.80)

    # Variants shown in the UI (excludes within-family confusables — those go
    # to confusable_forms so the UI can style them with a warning).
    variant_dicts: list[dict[str, str]] = [
        {
            "surface":    v.surface,
            "match_type": v.match_type.value,
            "note":       v.note or "",
        }
        for v in fam.variants
        if v.match_type != MatchType.confusable_not_same
    ]

    confusable_form_dicts: list[dict[str, str]] = [
        {
            "surface": v.surface,
            "note":    v.note or "",
        }
        for v in fam.variants
        if v.match_type == MatchType.confusable_not_same
    ]

    lesson_data: dict[str, Any] = {
        "family_id":       fam.id,
        "canonical_form":  fam.canonical_form,
        "matched_variant": surface_span,
        "match_type":      match_type.value,
        "meaning":         fam.meaning,
        "register":        fam.register,
        "variants":        variant_dicts,
    }
    if matched_variant and matched_variant.note:
        lesson_data["match_type_note"] = matched_variant.note
    if fam.origin:
        lesson_data["origin"] = fam.origin
    if fam.source_text:
        lesson_data["source_text"] = fam.source_text
    if fam.why_it_matters:
        lesson_data["why_it_matters"] = fam.why_it_matters
    if fam.confusables:
        lesson_data["confusables"] = list(fam.confusables)
        lesson_data["confusable_families"] = [
            {
                "family_id":      cid,
                "canonical_form": _FAMILY_CATALOG[cid].canonical_form,
                "meaning":        _FAMILY_CATALOG[cid].meaning,
                "register":       _FAMILY_CATALOG[cid].register,
            }
            for cid in fam.confusables
            if cid in _FAMILY_CATALOG
        ]
    if confusable_form_dicts:
        lesson_data["confusable_forms"] = confusable_form_dicts
    if fam.tags:
        lesson_data["tags"] = list(fam.tags)

    return CandidateObject(
        canonical_form=fam.id,
        surface_form=surface_span,
        type="phrase_family",
        label=surface_span,
        lesson_data=lesson_data,
        confidence=confidence,
    )


# ── Direct catalog lookup ─────────────────────────────────────────────────────

def lookup_family_by_id(family_id: str) -> "CandidateObject | None":
    """Return a CandidateObject for *family_id* without requiring a parse pass.

    Used by plugins to serve confusable-family lesson requests by ID.
    Returns ``None`` when the ID is not in the catalog.
    """
    fam = _FAMILY_CATALOG.get(family_id)
    if fam is None:
        return None
    exact = next((v for v in fam.variants if v.match_type == MatchType.exact), None)
    surface = exact.surface if exact else fam.canonical_form
    return _family_to_candidate(fam, surface, exact)
