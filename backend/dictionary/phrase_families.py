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

    # \u2500\u2500 Spanish catalog \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

    "es_meter_la_pata": PhraseFamily(
        id="es_meter_la_pata",
        language="es",
        canonical_form="meter la pata",
        meaning="To make a blunder; to put one\u2019s foot in one\u2019s mouth.",
        register="informal",
        origin=(
            "The image is of a foot (pata = paw/foot/leg) stepping into a trap or "
            "stumbling. Shifted from literal misstep to any social or verbal gaffe."
        ),
        why_it_matters=(
            "One of the most common Spanish colloquialisms for making a mistake. "
            "Learners frequently produce hacer un error instead \u2014 "
            "meter la pata is far more natural in speech."
        ),
        variants=(
            PhraseVariant("meter la pata", MatchType.exact),
            PhraseVariant("met\u00ed la pata", MatchType.inflectional_variant,
                          note="1st-person preterite: I put my foot in it."),
            PhraseVariant("meti\u00f3 la pata", MatchType.inflectional_variant,
                          note="3rd-person preterite: she/he put their foot in it."),
            PhraseVariant("metemos la pata", MatchType.inflectional_variant,
                          note="1st-person plural present: we put our foot in it."),
        ),
        tags=("blunder", "informal", "colloquial"),
    ),

    "es_hacer_las_paces": PhraseFamily(
        id="es_hacer_las_paces",
        language="es",
        canonical_form="hacer las paces",
        meaning="To make peace; to reconcile after a quarrel.",
        register="neutral",
        origin=(
            "From Latin pacem facere \u2018to make peace.\u2019 "
            "The plural las paces (rather than la paz) is idiomatic \u2014 "
            "la paz refers to political or international peace; "
            "las paces is always interpersonal reconciliation."
        ),
        why_it_matters=(
            "The plural las paces is grammatically fixed in this idiom. "
            "Saying *hacer la paz in a personal context sounds formal or political."
        ),
        variants=(
            PhraseVariant("hacer las paces", MatchType.exact),
            PhraseVariant("hicieron las paces", MatchType.inflectional_variant,
                          note="3rd-person plural preterite."),
            PhraseVariant("hizo las paces", MatchType.inflectional_variant,
                          note="3rd-person singular preterite."),
            PhraseVariant("hacer la paz", MatchType.confusable_not_same,
                          note="Refers to political or formal peace, not personal reconciliation."),
        ),
        tags=("reconciliation", "fixed-plural"),
    ),

    "es_matar_dos_pajaros": PhraseFamily(
        id="es_matar_dos_pajaros",
        language="es",
        canonical_form="matar dos p\u00e1jaros de un tiro",
        meaning="To kill two birds with one stone; to achieve two goals with one action.",
        register="neutral",
        origin=(
            "A pan-European idiom attested across Romance and Germanic languages. "
            "The Spanish phrase is the direct equivalent of the English idiom."
        ),
        source_text="Common European idiom; attested in Spanish from the 17th century",
        variants=(
            PhraseVariant("matar dos p\u00e1jaros de un tiro", MatchType.exact),
            PhraseVariant("matar dos p\u00e1jaros de un solo tiro", MatchType.blend,
                          note="\u2018Solo\u2019 (single) inserted as an intensifier."),
            PhraseVariant("matar dos p\u00e1jaros de un golpe", MatchType.orthographic_variant,
                          note="\u2018Golpe\u2019 (blow) replaces \u2018tiro\u2019 (shot)."),
        ),
        tags=("efficiency", "proverb", "universal-idiom"),
    ),

    "es_ser_pan_comido": PhraseFamily(
        id="es_ser_pan_comido",
        language="es",
        canonical_form="ser pan comido",
        meaning="To be a piece of cake; to be very easy.",
        register="informal",
        origin=(
            "Pan comido literally means \u2018eaten bread\u2019 \u2014 something "
            "already consumed, no longer a challenge. "
            "Parallels English \u2018piece of cake\u2019 (something trivially consumed)."
        ),
        why_it_matters=(
            "Always uses ser (permanent attribute), not estar, because ease is framed "
            "as an inherent quality of the task rather than a transient state."
        ),
        variants=(
            PhraseVariant("ser pan comido", MatchType.exact),
            PhraseVariant("es pan comido", MatchType.inflectional_variant,
                          note="Present 3rd-person: \u2018it is a piece of cake.\u2019"),
            PhraseVariant("fue pan comido", MatchType.inflectional_variant,
                          note="Preterite: \u2018it was a piece of cake.\u2019"),
        ),
        tags=("easiness", "colloquial", "food-metaphor"),
    ),

    "es_ponerse_las_pilas": PhraseFamily(
        id="es_ponerse_las_pilas",
        language="es",
        canonical_form="ponerse las pilas",
        meaning="To get one\u2019s act together; to buckle down; to shape up.",
        register="informal",
        origin=(
            "Pilas are batteries. The image is of inserting fresh batteries: "
            "re-energising oneself to resume work. Common in Spain and Latin America."
        ),
        variants=(
            PhraseVariant("ponerse las pilas", MatchType.exact),
            PhraseVariant("ponte las pilas", MatchType.inflectional_variant,
                          note="T\u00fa imperative: \u2018get it together.\u2019"),
            PhraseVariant("ponerte las pilas", MatchType.inflectional_variant,
                          note="Infinitive with 2nd-person clitic: \u2018(you need) to get it together.\u2019"),
            PhraseVariant("p\u00f3ngase las pilas", MatchType.inflectional_variant,
                          note="Usted imperative (formal)."),
        ),
        tags=("motivation", "colloquial", "batteries-metaphor"),
    ),

    "es_costar_un_ojo": PhraseFamily(
        id="es_costar_un_ojo",
        language="es",
        canonical_form="costar un ojo de la cara",
        meaning="To cost an arm and a leg; to be outrageously expensive.",
        register="informal",
        origin=(
            "The face is intimate and irreplaceable; the eye (ojo) its most precious "
            "part. Paying \u2018an eye from one\u2019s face\u2019 is a hyperbole for "
            "extreme cost."
        ),
        variants=(
            PhraseVariant("costar un ojo de la cara", MatchType.exact),
            PhraseVariant("cuesta un ojo de la cara", MatchType.inflectional_variant,
                          note="Present 3rd-person: \u2018it costs an arm and a leg.\u2019"),
            PhraseVariant("cost\u00f3 un ojo de la cara", MatchType.inflectional_variant,
                          note="Preterite: \u2018it cost an arm and a leg.\u2019"),
            PhraseVariant("costar un ri\u00f1\u00f3n", MatchType.orthographic_variant,
                          note="\u2018Ri\u00f1\u00f3n\u2019 (kidney) substituted for \u2018ojo de la cara\u2019; same meaning."),
        ),
        tags=("expense", "hyperbole", "body-metaphor"),
    ),

    "es_no_hay_mal_por_bien": PhraseFamily(
        id="es_no_hay_mal_por_bien",
        language="es",
        canonical_form="no hay mal que por bien no venga",
        meaning="Every cloud has a silver lining; bad things can lead to good outcomes.",
        register="neutral",
        origin=(
            "A Spanish proverb of Latin origin, parallel to English \u2018every cloud "
            "has a silver lining.\u2019 Widely used as consolation in peninsular and "
            "Latin American Spanish."
        ),
        source_text="Spanish proverb; parallel to Latin \u2018Nullum malum sine aliquo bono\u2019",
        variants=(
            PhraseVariant("no hay mal que por bien no venga", MatchType.exact),
            PhraseVariant("no hay mal que no venga por bien", MatchType.misquotation,
                          note="Word order of the relative clause inverted; meaning unchanged."),
        ),
        tags=("proverb", "consolation", "optimism"),
    ),

    "es_no_hay_rosa": PhraseFamily(
        id="es_no_hay_rosa",
        language="es",
        canonical_form="no hay rosa sin espinas",
        meaning="There is no rose without thorns; every good thing comes with some difficulty.",
        register="neutral",
        origin=(
            "A universal proverb found in Latin (Rosa sine spinis esse non potest), "
            "Spanish, French (il n\u2019y a pas de roses sans \u00e9pines), and English. "
            "Used to acknowledge that good things carry their difficulties."
        ),
        source_text="Universal proverb; attested in Latin and Romance languages",
        variants=(
            PhraseVariant("no hay rosa sin espinas", MatchType.exact),
            PhraseVariant("no existe rosa sin espinas", MatchType.orthographic_variant,
                          note="\u2018Existe\u2019 replaces \u2018hay\u2019; slightly more literary."),
        ),
        tags=("proverb", "hardship", "beauty"),
    ),

    "es_echar_agua_al_mar": PhraseFamily(
        id="es_echar_agua_al_mar",
        language="es",
        canonical_form="echar agua al mar",
        meaning="To carry coals to Newcastle; to do something completely unnecessary.",
        register="neutral",
        origin=(
            "The sea already has all the water it needs. "
            "The Spanish equivalent of the English idiom \u2018carry coals to Newcastle\u2019 "
            "\u2014 doing something absurdly redundant."
        ),
        variants=(
            PhraseVariant("echar agua al mar", MatchType.exact),
            PhraseVariant("llevar agua al mar", MatchType.orthographic_variant,
                          note="\u2018Llevar\u2019 (to carry/bring) replaces \u2018echar\u2019 (to throw/pour); same meaning."),
        ),
        tags=("redundancy", "proverb"),
    ),

    "es_llevar_la_contraria": PhraseFamily(
        id="es_llevar_la_contraria",
        language="es",
        canonical_form="llevar la contraria",
        meaning="To go against someone; to contradict or oppose for its own sake.",
        register="neutral",
        origin=(
            "La contraria is a substantivised adjective: \u2018the contrary [position].\u2019 "
            "Llevar (to carry/bear) the contrary position means habitually taking the "
            "opposing stance regardless of merit."
        ),
        why_it_matters=(
            "Unlike contradecir (to contradict a specific claim), llevar la contraria "
            "implies a habitual or petty contrariness \u2014 opposing for its own sake."
        ),
        variants=(
            PhraseVariant("llevar la contraria", MatchType.exact),
            PhraseVariant("lleva la contraria", MatchType.inflectional_variant,
                          note="Present 3rd-person singular."),
            PhraseVariant("llevas la contraria", MatchType.inflectional_variant,
                          note="Present 2nd-person singular (t\u00fa)."),
        ),
        tags=("contradiction", "stubbornness", "colloquial"),
    ),

    # \u2500\u2500 German catalog \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

    "de_schwein_haben": PhraseFamily(
        id="de_schwein_haben",
        language="de",
        canonical_form="Schwein haben",
        meaning="To be lucky; to get away with something by sheer luck.",
        register="informal",
        origin=(
            "Medieval fair custom: the last-place finisher in a contest received a pig "
            "(Schwein) as a consolation prize. Any lucky outcome came to be called "
            "\u2018Schwein haben.\u2019 The porcine association with luck persists in "
            "German gift-giving (Gl\u00fccksschwein \u2014 lucky pig)."
        ),
        why_it_matters=(
            "A frequent colloquialism. Learners mistake it for a negative idiom; "
            "Schwein (pig) carries no negative connotation here \u2014 it is pure luck."
        ),
        variants=(
            PhraseVariant("Schwein haben", MatchType.exact),
            PhraseVariant("Schwein gehabt", MatchType.inflectional_variant,
                          note="Past participle construction: \u2018got lucky.\u2019"),
            PhraseVariant("Schwein gehabt haben", MatchType.inflectional_variant,
                          note="Perfect infinitive."),
            PhraseVariant("Gl\u00fcck haben", MatchType.confusable_not_same,
                          note="\u2018Gl\u00fcck haben\u2019 (to be lucky) is the neutral synonym; Schwein haben is more colloquial."),
        ),
        tags=("luck", "informal", "colloquial"),
    ),

    "de_die_nase_voll_haben": PhraseFamily(
        id="de_die_nase_voll_haben",
        language="de",
        canonical_form="die Nase voll haben",
        meaning="To be fed up; to have had enough of something.",
        register="informal",
        origin=(
            "The nose (Nase) as a metaphor for disgust \u2014 a nose \u2018full\u2019 "
            "of something repugnant. Parallel to English \u2018up to here with it\u2019 "
            "and French \u2018en avoir plein le dos.\u2019"
        ),
        variants=(
            PhraseVariant("die Nase voll haben", MatchType.exact),
            PhraseVariant("die Nase voll", MatchType.inflectional_variant,
                          note="Short form in context, e.g. \u2018Ich habe die Nase voll.\u2019"),
            PhraseVariant("die Schnauze voll haben", MatchType.orthographic_variant,
                          note="Cruder register: Schnauze (snout) for Nase (nose)."),
        ),
        tags=("exasperation", "informal", "body-metaphor"),
    ),

    "de_unter_vier_augen": PhraseFamily(
        id="de_unter_vier_augen",
        language="de",
        canonical_form="unter vier Augen",
        meaning="In private; face-to-face and confidentially.",
        register="neutral",
        origin=(
            "Two people have four eyes between them. Meeting \u2018under four eyes\u2019 "
            "means privately \u2014 only those four eyes are present. "
            "Attested from the 17th century."
        ),
        source_text="Attested in German from the 17th century",
        variants=(
            PhraseVariant("unter vier Augen", MatchType.exact),
            PhraseVariant("unter 4 Augen", MatchType.orthographic_variant,
                          note="Numeral form used in informal writing."),
        ),
        tags=("privacy", "directness"),
    ),

    "de_auf_dem_holzweg": PhraseFamily(
        id="de_auf_dem_holzweg",
        language="de",
        canonical_form="auf dem Holzweg sein",
        meaning="To be on the wrong track; to be completely mistaken.",
        register="neutral",
        origin=(
            "Holzweg (literally \u2018wood path\u2019) was a forestry term for a dead-end "
            "track leading only to a logging site with no through-road. "
            "Travelers who took such a path were heading nowhere useful."
        ),
        why_it_matters=(
            "A productive verb idiom: the \u2018sein\u2019 (to be) conjugates freely "
            "while the \u2018auf dem Holzweg\u2019 core remains fixed."
        ),
        variants=(
            PhraseVariant("auf dem Holzweg sein", MatchType.exact),
            PhraseVariant("auf dem Holzweg", MatchType.inflectional_variant,
                          note="Short form \u2014 \u2018sein\u2019 omitted or conjugated separately."),
            PhraseVariant("auf dem falschen Weg", MatchType.confusable_not_same,
                          note="Literally \u2018on the wrong path\u2019; less idiomatic, weaker image."),
        ),
        tags=("mistake", "error", "forestry-metaphor"),
    ),

    "de_ins_schwarze_treffen": PhraseFamily(
        id="de_ins_schwarze_treffen",
        language="de",
        canonical_form="ins Schwarze treffen",
        meaning="To hit the bull\u2019s-eye; to be exactly right.",
        register="neutral",
        origin=(
            "Das Schwarze is the black circle at the center of a target. "
            "Hitting the black center means a perfect shot. "
            "Used figuratively for any observation or action that is precisely on target."
        ),
        variants=(
            PhraseVariant("ins Schwarze treffen", MatchType.exact),
            PhraseVariant("ins Schwarze getroffen", MatchType.inflectional_variant,
                          note="Perfect participle form."),
            PhraseVariant("ins Schwarze", MatchType.inflectional_variant,
                          note="Short form \u2014 verb omitted or elsewhere in clause."),
        ),
        confusables=("de_den_nagel_treffen",),
        tags=("accuracy", "precision", "target"),
    ),

    "de_katz_und_maus": PhraseFamily(
        id="de_katz_und_maus",
        language="de",
        canonical_form="Katz und Maus spielen",
        meaning="To play cat and mouse; to tease or toy with someone before acting.",
        register="neutral",
        origin=(
            "Direct parallel to the international idiom. "
            "The cat\u2019s habit of catching and releasing prey before the kill "
            "became a universal metaphor for drawn-out pursuits."
        ),
        variants=(
            PhraseVariant("Katz und Maus spielen", MatchType.exact),
            PhraseVariant("Katz und Maus", MatchType.inflectional_variant,
                          note="Short form \u2014 spielen omitted or conjugated separately."),
            PhraseVariant("Katze und Maus spielen", MatchType.orthographic_variant,
                          note="Full noun Katze instead of clipped Katz."),
        ),
        tags=("power", "teasing", "universal-idiom"),
    ),

    "de_auf_den_punkt": PhraseFamily(
        id="de_auf_den_punkt",
        language="de",
        canonical_form="auf den Punkt bringen",
        meaning="To get to the point; to summarise clearly and precisely.",
        register="neutral",
        origin=(
            "Der Punkt (the point, the dot) as the essential core of a matter. "
            "\u2018Bringing something to the point\u2019 means distilling it to its "
            "essence. Common in academic, journalistic, and everyday speech."
        ),
        variants=(
            PhraseVariant("auf den Punkt bringen", MatchType.exact),
            PhraseVariant("auf den Punkt gebracht", MatchType.inflectional_variant,
                          note="Past participle: \u2018put succinctly.\u2019"),
            PhraseVariant("auf den Punkt", MatchType.inflectional_variant,
                          note="Short form \u2014 bringen omitted or elsewhere in clause."),
        ),
        tags=("clarity", "precision"),
    ),

    "de_den_nagel_treffen": PhraseFamily(
        id="de_den_nagel_treffen",
        language="de",
        canonical_form="den Nagel auf den Kopf treffen",
        meaning="To hit the nail on the head; to say or do exactly the right thing.",
        register="neutral",
        origin=(
            "Direct parallel to the English idiom \u2018hit the nail on the head.\u2019 "
            "The carpenter\u2019s image: a well-aimed hammer blow that drives the nail "
            "squarely into the wood."
        ),
        source_text="Pan-European idiom; attested in German from the 18th century",
        variants=(
            PhraseVariant("den Nagel auf den Kopf treffen", MatchType.exact),
            PhraseVariant("den Nagel auf den Kopf getroffen", MatchType.inflectional_variant,
                          note="Perfect participle."),
            PhraseVariant("den Nagel auf den Kopf", MatchType.inflectional_variant,
                          note="Short form \u2014 treffen omitted or elsewhere in clause."),
        ),
        confusables=("de_ins_schwarze_treffen",),
        tags=("accuracy", "precision", "carpentry"),
    ),

    "de_kein_wunder": PhraseFamily(
        id="de_kein_wunder",
        language="de",
        canonical_form="kein Wunder",
        meaning="No wonder; it is not surprising.",
        register="neutral",
        origin=(
            "Wunder (wonder, miracle) from Old High German wuntar. "
            "The construction \u2018kein Wunder, dass...\u2019 is one of the most "
            "frequent discourse markers in everyday German speech."
        ),
        variants=(
            PhraseVariant("kein Wunder", MatchType.exact),
            PhraseVariant("kein Wunder, dass", MatchType.inflectional_variant,
                          note="Full construction with subordinate clause: \u2018no wonder that...\u2019"),
            PhraseVariant("kein Wunder, wenn", MatchType.inflectional_variant,
                          note="Conditional variant: \u2018no wonder if...\u2019"),
        ),
        tags=("discourse-marker", "unsurprising"),
    ),

    "de_hand_aufs_herz": PhraseFamily(
        id="de_hand_aufs_herz",
        language="de",
        canonical_form="Hand aufs Herz",
        meaning="Honestly; hand on heart; speaking sincerely.",
        register="neutral",
        origin=(
            "The gesture of placing one\u2019s hand over the heart as a pledge of "
            "sincerity. Parallel to English \u2018hand on heart\u2019 and French "
            "\u2018la main sur le c\u0153ur.\u2019 Used to preface an honest admission."
        ),
        source_text="Pan-European gesture idiom; attested from the 17th century",
        variants=(
            PhraseVariant("Hand aufs Herz", MatchType.exact),
            PhraseVariant("Hand auf Herz", MatchType.orthographic_variant,
                          note="Omission of definite article (colloquial)."),
        ),
        tags=("honesty", "sincerity", "gesture-idiom"),
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
