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

    # \u2500\u2500 Spanish catalog \u2014 extended \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

    "es_valer_la_pena": PhraseFamily(
        id="es_valer_la_pena",
        language="es",
        canonical_form="valer la pena",
        meaning="To be worth it; to be worthwhile.",
        register="neutral",
        origin=(
            "Pena originally meant \u2018toil, suffering, effort.\u2019 "
            "\u2018Valer la pena\u2019 asks whether something is worth the suffering or effort. "
            "A pan-Hispanic idiom of very high frequency."
        ),
        why_it_matters=(
            "One of the most frequent collocations in Spanish. "
            "The idiom is stable: pena does not shift to other body-cost nouns. "
            "The infinitive valer la pena serves as a gerund, infinitive, and nominal freely."
        ),
        variants=(
            PhraseVariant("valer la pena", MatchType.exact),
            PhraseVariant("vale la pena", MatchType.inflectional_variant,
                          note="3rd-person singular present: \u2018it is worth it.\u2019"),
            PhraseVariant("vali\u00f3 la pena", MatchType.inflectional_variant,
                          note="3rd-person singular preterite: \u2018it was worth it.\u2019"),
            PhraseVariant("valdr\u00e1 la pena", MatchType.inflectional_variant,
                          note="Future: \u2018it will be worth it.\u2019"),
            PhraseVariant("merecer la pena", MatchType.confusable_not_same,
                          note="Synonym in Peninsular Spanish; less common in Latin America."),
        ),
        tags=("value", "effort", "neutral"),
    ),

    "es_quedarse_en_blanco": PhraseFamily(
        id="es_quedarse_en_blanco",
        language="es",
        canonical_form="quedarse en blanco",
        meaning="To go blank; to draw a blank; to suddenly forget something entirely.",
        register="neutral",
        origin=(
            "Blanco (blank, white) as the metaphor for an empty mind: "
            "the white page equals total absence of thought or memory."
        ),
        variants=(
            PhraseVariant("quedarse en blanco", MatchType.exact),
            PhraseVariant("qued\u00e9 en blanco", MatchType.inflectional_variant,
                          note="1st-person preterite: \u2018I went blank.\u2019"),
            PhraseVariant("qued\u00f3 en blanco", MatchType.inflectional_variant,
                          note="3rd-person preterite: \u2018she/he went blank.\u2019"),
            PhraseVariant("me qued\u00e9 en blanco", MatchType.inflectional_variant,
                          note="With explicit reflexive pronoun, 1st person."),
        ),
        tags=("memory", "confusion", "neutral"),
    ),

    "es_andarse_por_las_ramas": PhraseFamily(
        id="es_andarse_por_las_ramas",
        language="es",
        canonical_form="andarse por las ramas",
        meaning="To beat around the bush; to avoid getting to the point.",
        register="neutral",
        origin=(
            "The image of wandering among the branches (ramas) of a tree "
            "rather than going straight to the trunk. "
            "Parallel to English \u2018beat around the bush.\u2019"
        ),
        variants=(
            PhraseVariant("andarse por las ramas", MatchType.exact),
            PhraseVariant("andarte por las ramas", MatchType.inflectional_variant,
                          note="2nd-person reflexive (t\u00fa)."),
            PhraseVariant("ir por las ramas", MatchType.orthographic_variant,
                          note="\u2018Ir\u2019 replaces \u2018andarse\u2019; slightly more neutral."),
        ),
        tags=("indirectness", "avoidance"),
    ),

    "es_tener_mano_izquierda": PhraseFamily(
        id="es_tener_mano_izquierda",
        language="es",
        canonical_form="tener mano izquierda",
        meaning="To be tactful; to handle delicate situations with skill and diplomacy.",
        register="neutral",
        origin=(
            "In fencing and horsemanship the left hand (mano izquierda) guided with subtle "
            "finesse while the right acted overtly. Figurative: skill at handling people or "
            "difficult situations delicately."
        ),
        why_it_matters=(
            "Distinct from \u2018tener mano dura\u2019 (to rule with an iron fist) or "
            "\u2018tener buena mano\u2019 (to be skilled with one\u2019s hands). "
            "The left-hand quality specifically connotes indirect, diplomatic skill."
        ),
        variants=(
            PhraseVariant("tener mano izquierda", MatchType.exact),
            PhraseVariant("tiene mano izquierda", MatchType.inflectional_variant,
                          note="3rd-person singular present."),
            PhraseVariant("tener mano dura", MatchType.confusable_not_same,
                          note="\u2018Mano dura\u2019 (iron fist) means strict or harsh authority, not tact."),
        ),
        tags=("diplomacy", "tact", "body-metaphor"),
    ),

    "es_entre_la_espada_y_la_pared": PhraseFamily(
        id="es_entre_la_espada_y_la_pared",
        language="es",
        canonical_form="entre la espada y la pared",
        meaning="Between a rock and a hard place; caught between two equally bad options.",
        register="neutral",
        origin=(
            "A vivid martial image: standing with a sword at your front and a wall at your back, "
            "with no way out. First widely attested in Quevedo (17th c.). "
            "The English equivalent \u2018between a rock and a hard place\u2019 emerged later."
        ),
        source_text="Attested in Spanish from the 17th century; cf. Quevedo",
        variants=(
            PhraseVariant("entre la espada y la pared", MatchType.exact),
            PhraseVariant("entre la espada y el muro", MatchType.orthographic_variant,
                          note="\u2018Muro\u2019 (wall) for \u2018pared\u2019; less common but attested."),
        ),
        tags=("dilemma", "difficulty", "military-metaphor"),
    ),

    "es_poner_al_dia": PhraseFamily(
        id="es_poner_al_dia",
        language="es",
        canonical_form="ponerse al d\u00eda",
        meaning="To get up to speed; to catch up on information or tasks.",
        register="neutral",
        origin=(
            "\u2018Al d\u00eda\u2019 (up to the day) means current. "
            "\u2018Ponerse al d\u00eda\u2019 means putting oneself back in sync with the present. "
            "Common in professional and academic contexts."
        ),
        variants=(
            PhraseVariant("ponerse al d\u00eda", MatchType.exact),
            PhraseVariant("poner al d\u00eda", MatchType.inflectional_variant,
                          note="Transitive form: \u2018to bring someone up to speed.\u2019"),
            PhraseVariant("ponerse al corriente", MatchType.confusable_not_same,
                          note="Synonym; \u2018al corriente\u2019 also collocates with bills and accounts."),
        ),
        tags=("information", "currency", "everyday"),
    ),

    # \u2500\u2500 German catalog \u2014 extended \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

    "de_mit_dem_feuer_spielen": PhraseFamily(
        id="de_mit_dem_feuer_spielen",
        language="de",
        canonical_form="mit dem Feuer spielen",
        meaning="To play with fire; to take dangerous risks carelessly.",
        register="neutral",
        origin=(
            "A direct parallel to the English idiom, attested in German from the 19th century. "
            "The image of children playing with matches as a symbol of reckless provocation of danger."
        ),
        variants=(
            PhraseVariant("mit dem Feuer spielen", MatchType.exact),
            PhraseVariant("mit dem Feuer spielt", MatchType.inflectional_variant,
                          note="3rd-person singular present."),
            PhraseVariant("mit dem Feuer gespielt", MatchType.inflectional_variant,
                          note="Past participle."),
        ),
        tags=("danger", "recklessness", "universal-idiom"),
    ),

    "de_eulen_nach_athen": PhraseFamily(
        id="de_eulen_nach_athen",
        language="de",
        canonical_form="Eulen nach Athen tragen",
        meaning="To carry coals to Newcastle; to do something completely redundant.",
        register="neutral",
        origin=(
            "Owls (Eulen) were sacred to Athena and the symbol of Athens; "
            "sending owls there would be pointless. "
            "The expression originates with Aristophanes and entered German via Erasmus\u2019s Adages (1500)."
        ),
        source_text="Aristophanes, Birds (414\u202fBCE); Erasmus, Adages (1500); in German from the 16th century",
        why_it_matters=(
            "German\u2019s equivalent of English \u2018carry coals to Newcastle\u2019 and "
            "Spanish \u2018echar agua al mar\u2019. All three cultures use superfluous transportation "
            "as their rhetorical image, but from different local resources (coal, water, owls)."
        ),
        variants=(
            PhraseVariant("Eulen nach Athen tragen", MatchType.exact),
            PhraseVariant("Eulen nach Athen", MatchType.inflectional_variant,
                          note="Short form \u2014 tragen omitted or conjugated separately."),
        ),
        tags=("redundancy", "proverb", "classical-allusion"),
    ),

    "de_auf_gutem_fuss": PhraseFamily(
        id="de_auf_gutem_fuss",
        language="de",
        canonical_form="auf gutem Fu\u00df stehen",
        meaning="To be on good terms with someone; to have a positive relationship.",
        register="neutral",
        origin=(
            "Fu\u00df (foot) as the foundation of a relationship. "
            "Standing on a \u2018good foot\u2019 with someone means the ground between you is stable. "
            "Attested from the 17th century."
        ),
        variants=(
            PhraseVariant("auf gutem Fu\u00df stehen", MatchType.exact),
            PhraseVariant("auf gutem Fu\u00df", MatchType.inflectional_variant,
                          note="Short form \u2014 stehen conjugated separately."),
            PhraseVariant("auf gutem Fuss stehen", MatchType.orthographic_variant,
                          note="Swiss/Austrian spelling without \u00df."),
            PhraseVariant("auf schlechtem Fu\u00df stehen", MatchType.confusable_not_same,
                          note="\u2018Schlechter Fu\u00df\u2019 = on bad terms \u2014 inverse meaning."),
        ),
        tags=("relationship", "diplomacy", "body-metaphor"),
    ),

    "de_mit_allen_wassern_gewaschen": PhraseFamily(
        id="de_mit_allen_wassern_gewaschen",
        language="de",
        canonical_form="mit allen Wassern gewaschen",
        meaning="Streetwise; experienced in all tricks; cunning and not easily fooled.",
        register="neutral",
        origin=(
            "A sailor who had sailed all the world\u2019s waters was assumed to have encountered "
            "every trick and hazard. Washed in all waters = hardened by all experiences. "
            "Sailors\u2019 idiom, attested from the 18th century."
        ),
        source_text="Sailors\u2019 idiom; attested in German from the 18th century",
        variants=(
            PhraseVariant("mit allen Wassern gewaschen", MatchType.exact),
            PhraseVariant("mit allen Wassern gewaschen sein", MatchType.inflectional_variant,
                          note="With copula: \u2018to be streetwise.\u2019"),
        ),
        tags=("cunning", "experience", "sailors-idiom"),
    ),

    "de_den_mund_aufmachen": PhraseFamily(
        id="de_den_mund_aufmachen",
        language="de",
        canonical_form="den Mund aufmachen",
        meaning="To speak up; to open one\u2019s mouth; to say something.",
        register="neutral",
        origin=(
            "Aufmachen (to open) applied to Mund (mouth) \u2014 a direct bodily image for breaking silence. "
            "Contrasted with \u2018den Mund halten\u2019 (to keep quiet)."
        ),
        variants=(
            PhraseVariant("den Mund aufmachen", MatchType.exact),
            PhraseVariant("den Mund aufgemacht", MatchType.inflectional_variant,
                          note="Past participle."),
            PhraseVariant("den Mund halten", MatchType.confusable_not_same,
                          note="\u2018Den Mund halten\u2019 = to keep quiet \u2014 the direct opposite."),
        ),
        tags=("speech", "courage", "silence"),
    ),

    "de_im_dunkeln_tappen": PhraseFamily(
        id="de_im_dunkeln_tappen",
        language="de",
        canonical_form="im Dunkeln tappen",
        meaning="To be in the dark; to proceed without information; to grope for answers.",
        register="neutral",
        origin=(
            "Tappen originally meant to walk carefully while groping in the dark. "
            "\u2018Im Dunkeln tappen\u2019 describes acting without sufficient knowledge \u2014 fumbling blindly."
        ),
        why_it_matters=(
            "Distinct from \u2018im Dunkeln lassen\u2019 (to leave someone in the dark, i.e. to withhold "
            "information from them). \u2018Im Dunkeln tappen\u2019 = one\u2019s own ignorance; "
            "\u2018im Dunkeln lassen\u2019 = someone else\u2019s deliberate withholding."
        ),
        variants=(
            PhraseVariant("im Dunkeln tappen", MatchType.exact),
            PhraseVariant("tappen im Dunkeln", MatchType.inflectional_variant,
                          note="V2 word order \u2014 verb in second position."),
            PhraseVariant("tappt im Dunkeln", MatchType.inflectional_variant,
                          note="3rd-person singular, V2."),
            PhraseVariant("im Dunkeln lassen", MatchType.confusable_not_same,
                          note="\u2018Im Dunkeln lassen\u2019 = to leave someone in the dark (withhold information)."),
        ),
        tags=("ignorance", "uncertainty", "darkness-metaphor"),
    ),

    # \u2500\u2500 French catalog \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

    "fr_casser_les_pieds": PhraseFamily(
        id="fr_casser_les_pieds",
        language="fr",
        canonical_form="casser les pieds \u00e0 quelqu\u2019un",
        meaning="To annoy or bore someone intensely; to be a pain.",
        register="informal",
        origin=(
            "The image is of stamping on someone\u2019s feet \u2014 an intrusive, "
            "physical imposition. Casser (to break) intensifies the metaphor beyond "
            "mere nuisance. A fixture of everyday colloquial French since the 19th century."
        ),
        why_it_matters=(
            "Learners reach for ennuyer or agacer as neutral equivalents, but those "
            "lack the emphatic, exasperated register of casser les pieds. "
            "The indirect object (\u00e0 quelqu\u2019un) inflects freely; "
            "the feet phrase stays fixed."
        ),
        variants=(
            PhraseVariant("casser les pieds \u00e0 quelqu\u2019un", MatchType.exact),
            PhraseVariant("tu me casses les pieds", MatchType.inflectional_variant,
                          note="You\u2019re really annoying me \u2014 direct 2nd-person address."),
            PhraseVariant("il me casse les pieds", MatchType.inflectional_variant,
                          note="3rd-person singular, 1st-person indirect object."),
            PhraseVariant("elle m\u2019a cass\u00e9 les pieds", MatchType.inflectional_variant,
                          note="Past: she really got on my nerves."),
            PhraseVariant("casser les oreilles", MatchType.confusable_not_same,
                          note="\u2018Casser les oreilles\u2019 = to make an unbearable noise, not to bore/annoy."),
        ),
        tags=("annoyance", "informal", "body-metaphor"),
    ),

    "fr_poser_un_lapin": PhraseFamily(
        id="fr_poser_un_lapin",
        language="fr",
        canonical_form="poser un lapin \u00e0 quelqu\u2019un",
        meaning="To stand someone up; to fail to show for an appointment.",
        register="informal",
        origin=(
            "19th-century French slang: lapin (rabbit) was argot for a debt unpaid "
            "or a service rendered without payment. \u2018Poser un lapin\u2019 originally "
            "meant to leave without paying; by extension it shifted to leaving someone "
            "waiting \u2014 i.e., abandoning them. Attested from c.\u202f1880."
        ),
        source_text="Argot attested from c.\u202f1880; cf. \u00c9mile Zola\u2019s correspondence",
        why_it_matters=(
            "The rabbit has nothing to do with the meaning \u2014 this is pure argot. "
            "Learners who parse it literally will be baffled. "
            "The indirect object (\u00e0 quelqu\u2019un) is essential; "
            "\u2018poser un lapin\u2019 without it is incomplete."
        ),
        variants=(
            PhraseVariant("poser un lapin \u00e0 quelqu\u2019un", MatchType.exact),
            PhraseVariant("il m\u2019a pos\u00e9 un lapin", MatchType.inflectional_variant,
                          note="He stood me up \u2014 past tense, 1st-person object."),
            PhraseVariant("elle lui a pos\u00e9 un lapin", MatchType.inflectional_variant,
                          note="She stood him/her up \u2014 3rd-person past."),
            PhraseVariant("se faire poser un lapin", MatchType.inflectional_variant,
                          note="Passive construction: to get stood up."),
        ),
        tags=("appointment", "slang", "argot", "rabbit"),
    ),

    "fr_avoir_le_cafard": PhraseFamily(
        id="fr_avoir_le_cafard",
        language="fr",
        canonical_form="avoir le cafard",
        meaning="To feel down, depressed, or blue.",
        register="neutral",
        origin=(
            "Cafard (cockroach) entered this sense through Charles Baudelaire\u2019s "
            "Les Fleurs du Mal (1857), where the insect symbolised the oppressive "
            "ennui and spleen of modern life. The poet\u2019s usage fixed the metaphor "
            "in French. Cafard also separately means \u2018snitch\u2019 (from Arabic kaffir, "
            "infidel, via colonial usage) \u2014 an unrelated homograph."
        ),
        source_text="Popularised by Baudelaire, Les Fleurs du Mal (1857)",
        why_it_matters=(
            "The cockroach-depression metaphor is opaque to learners who know cafard "
            "only as \u2018snitch.\u2019 Context resolves ambiguity: avoir le cafard "
            "is always the emotional state. The two senses never overlap in practice."
        ),
        variants=(
            PhraseVariant("avoir le cafard", MatchType.exact),
            PhraseVariant("j\u2019ai le cafard", MatchType.inflectional_variant,
                          note="1st-person: I\u2019m feeling blue."),
            PhraseVariant("il a le cafard", MatchType.inflectional_variant,
                          note="3rd-person singular present."),
            PhraseVariant("avoir le blues", MatchType.confusable_not_same,
                          note="Anglicism with the same meaning; more recent and informal."),
        ),
        tags=("depression", "emotion", "baudelaire", "informal"),
    ),

    "fr_tomber_dans_les_pommes": PhraseFamily(
        id="fr_tomber_dans_les_pommes",
        language="fr",
        canonical_form="tomber dans les pommes",
        meaning="To faint; to pass out.",
        register="informal",
        origin=(
            "Origin disputed. One credible theory: from a letter by George Sand "
            "(c.\u202f1833) using \u2018\u00eatre dans les pommes cuites\u2019 (to be in cooked "
            "apples) to describe extreme exhaustion \u2014 the soft, pulpy texture "
            "suggesting complete limpness. The expression contracted and shifted to "
            "the act of fainting by the late 19th century."
        ),
        source_text="Possibly related to George Sand\u2019s correspondence, c.\u202f1833; "
                    "attested as a fainting idiom by the late 19th century",
        why_it_matters=(
            "One of the most colourful French idioms for fainting, alongside "
            "s\u2019\u00e9vanouir (neutral medical term) and tourner de l\u2019\u0153il "
            "(also informal). Tomber dans les pommes is distinctly colloquial "
            "and conveys surprise or drama around the event."
        ),
        variants=(
            PhraseVariant("tomber dans les pommes", MatchType.exact),
            PhraseVariant("elle est tomb\u00e9e dans les pommes", MatchType.inflectional_variant,
                          note="3rd-person feminine past: she fainted."),
            PhraseVariant("il est tomb\u00e9 dans les pommes", MatchType.inflectional_variant,
                          note="3rd-person masculine past: he fainted."),
            PhraseVariant("tomber dans les vapes", MatchType.confusable_not_same,
                          note="Even more informal synonym; vapes = vapours (dizziness)."),
        ),
        tags=("fainting", "informal", "colloquial", "food-metaphor"),
    ),

    "fr_revenons_a_nos_moutons": PhraseFamily(
        id="fr_revenons_a_nos_moutons",
        language="fr",
        canonical_form="revenons \u00e0 nos moutons",
        meaning="Let\u2019s get back to the subject; back to the matter at hand.",
        register="neutral",
        origin=(
            "From La Farce de Ma\u00eetre Pathelin (c.\u202f1460), a medieval French comedy "
            "in which a judge repeatedly interrupts a lawsuit to redirect a confused "
            "witness: \u201cMais revenons \u00e0 ces moutons\u201d "
            "(but let us return to these sheep). The sheep were the original subject "
            "of the dispute. The phrase entered general use as a discourse marker "
            "for returning to the point."
        ),
        source_text="La Farce de Ma\u00eetre Pathelin, c.\u202f1460",
        why_it_matters=(
            "One of the oldest documented French idioms, still fully alive in "
            "contemporary speech and writing. The moutons (sheep) are purely "
            "historical \u2014 the phrase is a discourse marker with no animal connotation today. "
            "The imperative form revenons is fixed; the phrase is highly formulaic."
        ),
        variants=(
            PhraseVariant("revenons \u00e0 nos moutons", MatchType.exact),
            PhraseVariant("revenons \u00e0 nos moutons", MatchType.exact),
            PhraseVariant("mais revenons \u00e0 ces moutons", MatchType.modernized_variant,
                          note="The original medieval form with \u2018ces\u2019 (these) for \u2018nos\u2019 (our)."),
            PhraseVariant("revenons au sujet", MatchType.confusable_not_same,
                          note="Neutral paraphrase; lacks the idiomatic flavour."),
        ),
        confusables=("fr_noyer_le_poisson",),
        tags=("discourse-marker", "subject", "medieval", "sheep"),
    ),

    "fr_noyer_le_poisson": PhraseFamily(
        id="fr_noyer_le_poisson",
        language="fr",
        canonical_form="noyer le poisson",
        meaning="To muddy the waters; to dodge an issue by creating confusion.",
        register="neutral",
        origin=(
            "The angler\u2019s technique of exhausting a fish by playing it on the "
            "line until it is too tired to resist \u2014 drowning it in its own "
            "element by keeping it struggling. Figurative: wearing down an opponent "
            "or obscuring an issue by generating so much complexity that the real "
            "point is lost."
        ),
        why_it_matters=(
            "Often confused with \u2018revenons \u00e0 nos moutons\u2019 because both involve "
            "digression. But noyer le poisson is deliberate obfuscation \u2014 an active "
            "strategy \u2014 while \u2018revenons\u2019 is a neutral call to refocus."
        ),
        variants=(
            PhraseVariant("noyer le poisson", MatchType.exact),
            PhraseVariant("il noie le poisson", MatchType.inflectional_variant,
                          note="3rd-person singular present: he\u2019s dodging the issue."),
            PhraseVariant("noyant le poisson", MatchType.inflectional_variant,
                          note="Participial form."),
            PhraseVariant("noyer le poisson dans l\u2019eau", MatchType.blend,
                          note="Pleonastic extension sometimes heard in speech; non-standard."),
        ),
        confusables=("fr_revenons_a_nos_moutons",),
        tags=("obfuscation", "deception", "fishing-metaphor"),
    ),

    "fr_avoir_du_pain_sur_la_planche": PhraseFamily(
        id="fr_avoir_du_pain_sur_la_planche",
        language="fr",
        canonical_form="avoir du pain sur la planche",
        meaning="To have a lot of work ahead; to have a lot on one\u2019s plate.",
        register="neutral",
        origin=(
            "Originally (18th century) the phrase meant to have resources stored "
            "for the future \u2014 bread on the board was a sign of prosperity and "
            "security. By the 20th century the meaning reversed: the bread now "
            "represents work awaiting completion rather than wealth in reserve. "
            "A rare case of semantic inversion without formal change."
        ),
        source_text="Attested in its modern sense from the early 20th century; "
                    "original sense (prosperity) is 18th century",
        why_it_matters=(
            "The semantic reversal is a trap: historical texts use the phrase to "
            "mean \u2018well-provided for,\u2019 while modern texts use it for "
            "\u2018overwhelmed with work.\u2019 Always context-check when reading texts "
            "from different eras."
        ),
        variants=(
            PhraseVariant("avoir du pain sur la planche", MatchType.exact),
            PhraseVariant("j\u2019ai du pain sur la planche", MatchType.inflectional_variant,
                          note="1st-person: I have a lot to do."),
            PhraseVariant("on a du pain sur la planche", MatchType.inflectional_variant,
                          note="Collective: we have a lot on our plate."),
            PhraseVariant("avoir beaucoup de pain sur la planche", MatchType.blend,
                          note="\u2018Beaucoup\u2019 inserted as intensifier; heard in speech."),
        ),
        tags=("workload", "bread-metaphor", "semantic-inversion"),
    ),

    "fr_les_carottes_sont_cuites": PhraseFamily(
        id="fr_les_carottes_sont_cuites",
        language="fr",
        canonical_form="les carottes sont cuites",
        meaning="It\u2019s all over; the die is cast; there\u2019s no way out now.",
        register="informal",
        origin=(
            "A cooked carrot cannot be un-cooked: the irreversibility of the culinary "
            "transformation became a metaphor for any situation that has passed the "
            "point of no return. Popularised in France during WWII as the code phrase "
            "used by the BBC French Service on 5 June 1944 to signal that D-Day "
            "was imminent. This historical use cemented the phrase in French memory."
        ),
        source_text="BBC French Service, 5 June 1944 (D-Day code phrase); "
                    "in general figurative use from the 19th century",
        why_it_matters=(
            "The WWII radio context means the phrase carries historical resonance "
            "beyond its literal meaning. Learners who know this will understand "
            "why it appears in historical fiction and films set in the Occupation."
        ),
        variants=(
            PhraseVariant("les carottes sont cuites", MatchType.exact),
            PhraseVariant("c\u2019est cuit", MatchType.modernized_variant,
                          note="Shortened modern form: it\u2019s done for."),
            PhraseVariant("les jeux sont faits", MatchType.confusable_not_same,
                          note="\u2018Les jeux sont faits\u2019 = the bets are placed (gambling); similar finality but different register."),
        ),
        tags=("finality", "WWII", "food-metaphor", "irreversibility"),
    ),

    "fr_mettre_les_pieds_dans_le_plat": PhraseFamily(
        id="fr_mettre_les_pieds_dans_le_plat",
        language="fr",
        canonical_form="mettre les pieds dans le plat",
        meaning="To put one\u2019s foot in it; to blunder tactlessly into a sensitive situation.",
        register="informal",
        origin=(
            "The image of stepping (pieds = feet) into a serving dish (plat = dish, plate): "
            "an act of gross clumsiness at table, the ultimate social faux pas. "
            "The idiom generalised from literal gaucherie to any tactless intrusion."
        ),
        why_it_matters=(
            "Distinct from \u2018casser les pieds\u2019 (to annoy someone deliberately): "
            "mettre les pieds dans le plat implies unintentional blundering, not malice. "
            "Both involve pieds (feet) \u2014 a common source of confusion for learners."
        ),
        variants=(
            PhraseVariant("mettre les pieds dans le plat", MatchType.exact),
            PhraseVariant("il a mis les pieds dans le plat", MatchType.inflectional_variant,
                          note="He put his foot in it \u2014 past tense."),
            PhraseVariant("elle a mis les pieds dans le plat", MatchType.inflectional_variant,
                          note="She put her foot in it \u2014 past tense."),
            PhraseVariant("en mettant les pieds dans le plat", MatchType.inflectional_variant,
                          note="Gerund: by blundering in."),
            PhraseVariant("casser les pieds", MatchType.confusable_not_same,
                          note="\u2018Casser les pieds\u2019 = to annoy intentionally; not the same blunder idiom."),
        ),
        confusables=("fr_casser_les_pieds",),
        tags=("blunder", "tact", "informal", "body-metaphor"),
    ),

    "fr_avoir_dautres_chats": PhraseFamily(
        id="fr_avoir_dautres_chats",
        language="fr",
        canonical_form="avoir d\u2019autres chats \u00e0 fouetter",
        meaning="To have bigger fish to fry; to have more important things to deal with.",
        register="neutral",
        origin=(
            "Fouetter (to whip) applied to chats (cats): the image of a person with "
            "so many cats to whip that the current one can wait. "
            "The idiom appears as early as the 17th century in French and was noted "
            "by Henri Estienne. The English equivalent uses fish rather than cats."
        ),
        source_text="Attested in French from the 17th century; noted by Henri Estienne",
        variants=(
            PhraseVariant("avoir d\u2019autres chats \u00e0 fouetter", MatchType.exact),
            PhraseVariant("j\u2019ai d\u2019autres chats \u00e0 fouetter", MatchType.inflectional_variant,
                          note="1st-person: I have more important things to do."),
            PhraseVariant("on a d\u2019autres chats \u00e0 fouetter", MatchType.inflectional_variant,
                          note="Collective 1st-person."),
            PhraseVariant("avoir d\u2019autres poissons \u00e0 frire", MatchType.confusable_not_same,
                          note="Calque of the English idiom; less idiomatic in French."),
        ),
        tags=("priority", "dismissal", "cat-metaphor"),
    ),

    "fr_cest_la_croix_et_la_banniere": PhraseFamily(
        id="fr_cest_la_croix_et_la_banniere",
        language="fr",
        canonical_form="c\u2019est la croix et la banni\u00e8re",
        meaning="It\u2019s a real ordeal; it takes enormous effort to get something done.",
        register="informal",
        origin=(
            "In medieval religious processions, the cross and banner were the most "
            "ceremonially elaborate elements \u2014 heavy, difficult to carry, and "
            "requiring special effort to deploy. Getting the cross and banner out "
            "came to mean mounting a disproportionate effort for something that "
            "should be simple."
        ),
        why_it_matters=(
            "A vivid hyperbolic idiom with no English structural equivalent. "
            "Learners need to understand the religious-procession origin to "
            "appreciate why two church objects signal extreme difficulty."
        ),
        variants=(
            PhraseVariant("c\u2019est la croix et la banni\u00e8re", MatchType.exact),
            PhraseVariant("c\u2019\u00e9tait la croix et la banni\u00e8re", MatchType.inflectional_variant,
                          note="Past tense: it was a real ordeal."),
            PhraseVariant("quelle croix et banni\u00e8re", MatchType.modernized_variant,
                          note="Exclamatory ellipsis common in speech."),
        ),
        tags=("effort", "ordeal", "religious-origin", "informal"),
    ),

    "fr_ne_pas_vendre_la_peau": PhraseFamily(
        id="fr_ne_pas_vendre_la_peau",
        language="fr",
        canonical_form="il ne faut pas vendre la peau de l\u2019ours avant de l\u2019avoir tu\u00e9",
        meaning="Don\u2019t count your chickens before they hatch; don\u2019t sell the bearskin before you\u2019ve killed the bear.",
        register="neutral",
        origin=(
            "A fable-derived proverb. La Fontaine\u2019s L\u2019Ours et les deux Compagnons "
            "(Fables, V.20, 1668) tells of two men who sell a bear\u2019s skin before "
            "hunting it, then nearly die in the attempt. The moral gave French its "
            "canonical form of this universal proverb."
        ),
        source_text="La Fontaine, Fables V.20 (1668)",
        why_it_matters=(
            "Contrasts instructively with the English \u2018count your chickens\u2019: "
            "same lesson, completely different animal. Knowing the La Fontaine source "
            "gives learners insight into how French proverbs often trace back to "
            "classical fable tradition."
        ),
        variants=(
            PhraseVariant(
                "il ne faut pas vendre la peau de l\u2019ours avant de l\u2019avoir tu\u00e9",
                MatchType.exact,
            ),
            PhraseVariant(
                "vendre la peau de l\u2019ours",
                MatchType.inflectional_variant,
                note="Short form \u2014 full proverb implied by context.",
            ),
            PhraseVariant(
                "ne vendons pas la peau de l\u2019ours",
                MatchType.inflectional_variant,
                note="Hortative: let\u2019s not count our chickens.",
            ),
        ),
        tags=("proverb", "la-fontaine", "caution", "anticipation"),
    ),

    "fr_tenir_la_chandelle": PhraseFamily(
        id="fr_tenir_la_chandelle",
        language="fr",
        canonical_form="tenir la chandelle",
        meaning="To be a third wheel; to be the unwanted extra presence when two people want to be alone.",
        register="informal",
        origin=(
            "Before electric lighting, a servant holding a candle (chandelle) was "
            "present in intimate situations not from choice but from necessity. "
            "The holder of the candle was an awkward, passive witness. "
            "The idiom transferred to anyone who occupies a similarly unwanted "
            "role in a romantic context."
        ),
        why_it_matters=(
            "The English \u2018third wheel\u2019 and the French \u2018tenir la chandelle\u2019 "
            "share the same social dynamic but completely different images. "
            "The French version emphasises passive witnessing; the English emphasises "
            "mechanical redundancy."
        ),
        variants=(
            PhraseVariant("tenir la chandelle", MatchType.exact),
            PhraseVariant("je tiens la chandelle", MatchType.inflectional_variant,
                          note="1st-person: I\u2019m the third wheel here."),
            PhraseVariant("tenu la chandelle", MatchType.inflectional_variant,
                          note="Past participle."),
            PhraseVariant("tenir le bougeoir", MatchType.orthographic_variant,
                          note="Bougeoir (candlestick holder) for chandelle; rare variant."),
        ),
        tags=("romance", "social", "candle-metaphor", "informal"),
    ),

    "fr_avoir_le_vent_en_poupe": PhraseFamily(
        id="fr_avoir_le_vent_en_poupe",
        language="fr",
        canonical_form="avoir le vent en poupe",
        meaning="To have the wind in one\u2019s sails; to be riding high; to be on a roll.",
        register="neutral",
        origin=(
            "Poupe (poop deck, the stern of a ship) catches the wind from behind, "
            "propelling the vessel without effort. A ship with the wind en poupe "
            "sails effortlessly. Figuratively: circumstances are favourable and "
            "progress comes without resistance."
        ),
        why_it_matters=(
            "A nautical idiom that remains common in journalism and formal writing, "
            "unlike many sailing metaphors that have become archaic. "
            "Learners should recognise it in economic and political contexts: "
            "\u2018l\u2019\u00e9conomie a le vent en poupe\u2019 = the economy is booming."
        ),
        variants=(
            PhraseVariant("avoir le vent en poupe", MatchType.exact),
            PhraseVariant("il a le vent en poupe", MatchType.inflectional_variant,
                          note="3rd-person singular: he\u2019s on a roll."),
            PhraseVariant("l\u2019entreprise a le vent en poupe", MatchType.inflectional_variant,
                          note="Institutional subject: the company is doing well."),
            PhraseVariant("avoir le vent favorable", MatchType.confusable_not_same,
                          note="Literal sailing phrase; lacks the idiomatic sense of sustained success."),
        ),
        tags=("success", "momentum", "nautical-metaphor"),
    ),

    "fr_prendre_ses_jambes_a_son_cou": PhraseFamily(
        id="fr_prendre_ses_jambes_a_son_cou",
        language="fr",
        canonical_form="prendre ses jambes \u00e0 son cou",
        meaning="To take to one\u2019s heels; to run away as fast as possible.",
        register="neutral",
        origin=(
            "The image is physically impossible and deliberately so: wrapping one\u2019s "
            "legs around one\u2019s own neck to run faster. The absurdity of the image "
            "communicates the urgency and desperation of the flight. "
            "Attested in French from the 17th century."
        ),
        source_text="Attested in French from the 17th century",
        variants=(
            PhraseVariant("prendre ses jambes \u00e0 son cou", MatchType.exact),
            PhraseVariant("il a pris ses jambes \u00e0 son cou", MatchType.inflectional_variant,
                          note="He took to his heels \u2014 past tense."),
            PhraseVariant("elle a pris ses jambes \u00e0 son cou", MatchType.inflectional_variant,
                          note="She took to her heels \u2014 past tense."),
            PhraseVariant("prendre la fuite", MatchType.confusable_not_same,
                          note="Neutral synonym \u2018to flee\u2019; lacks the vividness of the leg-neck image."),
        ),
        tags=("flight", "speed", "body-metaphor", "urgency"),
    ),

    "fr_il_pleut_des_cordes": PhraseFamily(
        id="fr_il_pleut_des_cordes",
        language="fr",
        canonical_form="il pleut des cordes",
        meaning="It\u2019s raining cats and dogs; it\u2019s pouring heavily.",
        register="neutral",
        origin=(
            "Cordes (ropes) evoke the thick, vertical columns of heavy rain: "
            "sheets of water falling as straight and dense as ropes. "
            "The image is one of the most widespread in European weather idioms "
            "and appears in French from the 17th century."
        ),
        why_it_matters=(
            "French uses ropes where English uses cats and dogs and German uses "
            "ropes too (es regnet Stricke). Cross-language comparison reveals that "
            "the \u2018rope\u2019 image is pan-European; the English version is the outlier."
        ),
        variants=(
            PhraseVariant("il pleut des cordes", MatchType.exact),
            PhraseVariant("il pleut \u00e0 cordes", MatchType.orthographic_variant,
                          note="Without \u2018des\u2019 \u2014 older form; slightly archaic."),
            PhraseVariant("il pleut des hallebardes", MatchType.orthographic_variant,
                          note="\u2018Hallebardes\u2019 (halberds, polearms) for cordes; more vivid and archaic."),
            PhraseVariant("il tombe des cordes", MatchType.inflectional_variant,
                          note="\u2018Tomber\u2019 for \u2018pleuvoir\u2019; common regional variant."),
        ),
        tags=("weather", "rain", "universal-idiom", "rope-metaphor"),
    ),

    "fr_faire_la_fine_bouche": PhraseFamily(
        id="fr_faire_la_fine_bouche",
        language="fr",
        canonical_form="faire la fine bouche",
        meaning="To be picky or fussy; to turn one\u2019s nose up at something.",
        register="neutral",
        origin=(
            "Fine bouche (refined mouth) describes a person who purses their lips "
            "in delicate disdain, refusing what is offered. Originally a culinary "
            "metaphor for a finicky eater; extended to any fastidious refusal. "
            "Often used with negation in a persuasive context: "
            "\u2018ne faites pas la fine bouche\u2019 = don\u2019t be difficult."
        ),
        variants=(
            PhraseVariant("faire la fine bouche", MatchType.exact),
            PhraseVariant("ne faites pas la fine bouche", MatchType.inflectional_variant,
                          note="Imperative with negation: don\u2019t be fussy."),
            PhraseVariant("il fait la fine bouche", MatchType.inflectional_variant,
                          note="3rd-person: he\u2019s being picky."),
            PhraseVariant("elle fait la fine bouche", MatchType.inflectional_variant,
                          note="3rd-person feminine."),
            PhraseVariant("faire le difficile", MatchType.confusable_not_same,
                          note="Neutral synonym; less vivid, no food connotation."),
        ),
        tags=("fussiness", "food-metaphor", "register", "refusal"),
    ),

    "fr_avoir_coeur_sur_main": PhraseFamily(
        id="fr_avoir_coeur_sur_main",
        language="fr",
        canonical_form="avoir le c\u0153ur sur la main",
        meaning="To be very generous; to be open-handed; to give freely.",
        register="neutral",
        origin=(
            "The heart (c\u0153ur) held in or upon the open hand (main): "
            "an image of offering one\u2019s innermost self freely to others. "
            "Parallels the German \u2018Hand aufs Herz\u2019 but inverts the direction: "
            "in the French idiom the heart is given outward; in the German the "
            "hand pledges inward sincerity."
        ),
        why_it_matters=(
            "Cross-language comparison with German \u2018Hand aufs Herz\u2019 reveals "
            "how both cultures use the heart-hand combination for sincerity, "
            "but in opposite directions. French = outward generosity; "
            "German = inward pledge."
        ),
        variants=(
            PhraseVariant("avoir le c\u0153ur sur la main", MatchType.exact),
            PhraseVariant("il a le c\u0153ur sur la main", MatchType.inflectional_variant,
                          note="3rd-person singular: he\u2019s very generous."),
            PhraseVariant("elle a le c\u0153ur sur la main", MatchType.inflectional_variant,
                          note="3rd-person feminine."),
            PhraseVariant("avoir la main sur le c\u0153ur", MatchType.confusable_not_same,
                          note="Inverted form; less standard. Can mean the same but sometimes signals formality pledge (cf. German Hand aufs Herz)."),
        ),
        confusables=("de_hand_aufs_herz",),
        tags=("generosity", "heart-metaphor", "sincerity"),
    ),

    "fr_poser_les_jalons": PhraseFamily(
        id="fr_poser_les_jalons",
        language="fr",
        canonical_form="poser les jalons",
        meaning="To lay the groundwork; to set the stage; to prepare the foundation for something.",
        register="neutral",
        origin=(
            "Jalons are surveying stakes \u2014 the markers driven into the ground to "
            "define a line before construction begins. \u2018Poser les jalons\u2019 "
            "entered figurative use in the 19th century for any preparatory action "
            "that defines the path of a project. Common in political, journalistic, "
            "and business French."
        ),
        why_it_matters=(
            "A formal-neutral idiom with no quirky image: it simply means laying "
            "groundwork. Learners often reach for pr\u00e9parer le terrain (prepare "
            "the ground) instead, which is an acceptable synonym \u2014 but poser les jalons "
            "is more specific to marking out a planned path."
        ),
        variants=(
            PhraseVariant("poser les jalons", MatchType.exact),
            PhraseVariant("poser les jalons de", MatchType.inflectional_variant,
                          note="With genitive complement: \u2018lay the groundwork for X.\u2019"),
            PhraseVariant("il a pos\u00e9 les jalons", MatchType.inflectional_variant,
                          note="Past: he laid the groundwork."),
            PhraseVariant("pr\u00e9parer le terrain", MatchType.confusable_not_same,
                          note="Near-synonym \u2018prepare the ground\u2019; less precise about "
                               "marking a specific path."),
        ),
        tags=("preparation", "planning", "formal", "surveying-metaphor"),
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
