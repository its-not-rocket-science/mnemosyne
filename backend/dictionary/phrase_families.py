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
        confusables=("fr_avoir_coeur_sur_main",),
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
        confusables=("fr_mettre_les_pieds_dans_le_plat",),
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

    # ── Italian catalog ───────────────────────────────────────────────────────

    "it_fare_bella_figura": PhraseFamily(
        id="it_fare_bella_figura",
        language="it",
        canonical_form="fare bella figura",
        meaning="To make a good impression; to appear competent, elegant, or gracious.",
        register="neutral",
        origin=(
            "Figura in Italian means both 'figure/shape' and 'impression/appearance.' "
            "Making a bella (beautiful) figura is a cornerstone of Italian social values — "
            "the awareness of how one appears to others. Its opposite, fare brutta figura, "
            "is equally powerful and equally common."
        ),
        why_it_matters=(
            "This expression is untranslatable in a single English phrase. "
            "It captures a cultural priority: performing well for one's audience "
            "in dress, manner, speech, and gesture. Learners need both versions to navigate "
            "Italian social commentary."
        ),
        variants=(
            PhraseVariant("fare bella figura", MatchType.exact),
            PhraseVariant("fa bella figura", MatchType.inflectional_variant,
                          note="3rd-person present: he/she makes a good impression."),
            PhraseVariant("fare una bella figura", MatchType.inflectional_variant,
                          note="With indefinite article — equally common."),
        ),
        confusables=("it_fare_brutta_figura",),
        tags=("impression", "appearance", "culture", "social"),
    ),

    "it_fare_brutta_figura": PhraseFamily(
        id="it_fare_brutta_figura",
        language="it",
        canonical_form="fare brutta figura",
        meaning="To make a bad impression; to embarrass oneself in public.",
        register="neutral",
        origin=(
            "The direct opposite of fare bella figura. Brutta (ugly, bad) figura "
            "(impression) — appearing poorly dressed, ill-mannered, or incompetent. "
            "Both expressions are neutral register and used constantly in Italian conversation."
        ),
        why_it_matters=(
            "Equally important as its opposite. Italian speakers use these two expressions "
            "to comment on virtually any social performance. Learners who know only one half "
            "of the pair miss half the cultural commentary."
        ),
        variants=(
            PhraseVariant("fare brutta figura", MatchType.exact),
            PhraseVariant("fa brutta figura", MatchType.inflectional_variant,
                          note="3rd-person present: he/she makes a bad impression."),
            PhraseVariant("fare una brutta figura", MatchType.inflectional_variant,
                          note="With indefinite article — equally common."),
        ),
        confusables=("it_fare_bella_figura",),
        tags=("embarrassment", "impression", "culture", "social"),
    ),

    "it_essere_al_verde": PhraseFamily(
        id="it_essere_al_verde",
        language="it",
        canonical_form="essere al verde",
        meaning="To be broke; to have no money.",
        register="informal",
        origin=(
            "From medieval candles: the candle stub near the green (verde) painted base "
            "meant the candle — and the money — had nearly run out. "
            "The image of the green marking on the lowest part of the candle gave rise "
            "to this expression for financial exhaustion."
        ),
        why_it_matters=(
            "One of the most common informal expressions for lacking money. "
            "Non-compositional: al verde has no obvious meaning from its parts, "
            "making it a classic learner trap. The color verde is the key cultural cue."
        ),
        variants=(
            PhraseVariant("essere al verde", MatchType.exact),
            PhraseVariant("sono al verde", MatchType.inflectional_variant,
                          note="1st-person: I'm broke."),
            PhraseVariant("è al verde", MatchType.inflectional_variant,
                          note="3rd-person: he/she is broke."),
            PhraseVariant("restare al verde", MatchType.inflectional_variant,
                          note="To end up broke."),
        ),
        tags=("money", "informal", "colloquial", "financial"),
    ),

    "it_non_vedo_lora": PhraseFamily(
        id="it_non_vedo_lora",
        language="it",
        canonical_form="non vedo l'ora",
        meaning="I can't wait; I'm looking forward to it eagerly.",
        register="neutral",
        origin=(
            "Literally 'I don't see the hour' — time seems to not pass when one is "
            "eagerly anticipating something. The expression is ancient; the hour "
            "being invisible because impatience makes waiting unbearable."
        ),
        why_it_matters=(
            "An extremely common expression of eager anticipation. The literal meaning "
            "('I don't see the hour') is confusing for learners expecting a logical "
            "construction. It must be learned as a fixed unit."
        ),
        variants=(
            PhraseVariant("non vedo l'ora", MatchType.exact),
            PhraseVariant("non vedo l'ora di", MatchType.inflectional_variant,
                          note="Followed by infinitive: non vedo l'ora di vederti (I can't wait to see you)."),
            PhraseVariant("non vedevo l'ora", MatchType.inflectional_variant,
                          note="Imperfect: I couldn't wait / I had been looking forward to it."),
        ),
        tags=("anticipation", "enthusiasm", "neutral", "time"),
    ),

    "it_in_bocca_al_lupo": PhraseFamily(
        id="it_in_bocca_al_lupo",
        language="it",
        canonical_form="in bocca al lupo",
        meaning="Good luck! (literally: into the wolf's mouth)",
        register="informal",
        origin=(
            "Hunters' expression: going into the wolf's mouth meant a successful hunt. "
            "The ritual response is 'Crepi (il lupo)!' — 'May the wolf die!' "
            "Saying 'grazie' instead is considered bad luck. The expression is used "
            "before exams, performances, and any challenging endeavor."
        ),
        why_it_matters=(
            "The standard colloquial way to wish someone luck. Learners who say "
            "'buona fortuna' instead are understood but sound formal or foreign. "
            "The ritual response 'Crepi!' is equally important to know."
        ),
        variants=(
            PhraseVariant("in bocca al lupo", MatchType.exact),
            PhraseVariant("Crepi!", MatchType.allusion,
                          note="Ritual response: 'May the wolf die!' — required to complete the exchange."),
        ),
        tags=("good-luck", "informal", "ritual", "hunters"),
    ),

    "it_dare_una_mano": PhraseFamily(
        id="it_dare_una_mano",
        language="it",
        canonical_form="dare una mano",
        meaning="To give someone a hand; to help.",
        register="neutral",
        origin=(
            "Direct calque of the giving-of-hands concept found across European languages. "
            "Italian mano (hand) derives from Latin manus. "
            "Dar una mano in Spanish, donner un coup de main in French share the same image."
        ),
        why_it_matters=(
            "An extremely common and natural way to offer or request help. "
            "Learners often use aiutare (to help) which is correct but less idiomatic "
            "in casual speech. Dare una mano sounds more natural in everyday situations."
        ),
        variants=(
            PhraseVariant("dare una mano", MatchType.exact),
            PhraseVariant("mi dai una mano?", MatchType.inflectional_variant,
                          note="Can you give me a hand? — very common request form."),
            PhraseVariant("ti do una mano", MatchType.inflectional_variant,
                          note="I'll give you a hand — offer form."),
            PhraseVariant("dare una mano a", MatchType.inflectional_variant,
                          note="With dative complement: dare una mano a qualcuno."),
        ),
        tags=("help", "assistance", "neutral", "everyday"),
    ),

    "it_perdere_la_testa": PhraseFamily(
        id="it_perdere_la_testa",
        language="it",
        canonical_form="perdere la testa",
        meaning="To lose one's head; to become infatuated or to act irrationally.",
        register="neutral",
        origin=(
            "The image of 'losing the head' is pan-European, but in Italian it has "
            "two distinct uses: losing rational control (acting recklessly) and falling "
            "deeply in love (perdere la testa per qualcuno). Context disambiguates."
        ),
        why_it_matters=(
            "The romantic sense (to fall head over heels for someone) is extremely common "
            "in Italian songs and literature. Learners often encounter it in love songs "
            "before understanding the dual meaning."
        ),
        variants=(
            PhraseVariant("perdere la testa", MatchType.exact),
            PhraseVariant("ho perso la testa", MatchType.inflectional_variant,
                          note="I've lost my head / I've fallen head over heels."),
            PhraseVariant("perdere la testa per", MatchType.inflectional_variant,
                          note="To lose one's head over someone: perdere la testa per lei."),
            PhraseVariant("perdo la testa", MatchType.inflectional_variant,
                          note="Present: I'm losing my mind / I'm head over heels."),
        ),
        tags=("love", "irrationality", "neutral", "emotion"),
    ),

    "it_costare_un_occhio": PhraseFamily(
        id="it_costare_un_occhio",
        language="it",
        canonical_form="costare un occhio della testa",
        meaning="To cost an arm and a leg; to be extremely expensive.",
        register="informal",
        origin=(
            "The eye (occhio) is treated as one of the most precious things one possesses; "
            "paying 'an eye of the head' (un occhio della testa) signifies an absurd, "
            "body-depleting price. A parallel to English 'cost an arm and a leg.'"
        ),
        why_it_matters=(
            "The standard informal hyperbole for expressing that something is very "
            "expensive. Learners need to recognise both the full form and the common "
            "shortening costare un occhio."
        ),
        variants=(
            PhraseVariant("costare un occhio della testa", MatchType.exact),
            PhraseVariant("costa un occhio della testa", MatchType.inflectional_variant,
                          note="It costs an arm and a leg."),
            PhraseVariant("costare un occhio", MatchType.inflectional_variant,
                          note="Shortened form — equally common in speech."),
            PhraseVariant("costa un patrimonio", MatchType.confusable_not_same,
                          note="Near-synonym: costs a fortune — more literal, less vivid."),
        ),
        tags=("expense", "hyperbole", "informal", "money"),
    ),

    "it_prendere_due_piccioni": PhraseFamily(
        id="it_prendere_due_piccioni",
        language="it",
        canonical_form="prendere due piccioni con una fava",
        meaning="To kill two birds with one stone (literally: to catch two pigeons with one bean).",
        register="neutral",
        origin=(
            "Unlike the English bird-killing image, Italian uses pigeons (piccioni) "
            "and a fava bean as bait for a trap. The bean catches both birds simultaneously. "
            "The image reflects Italian pragmatism about resourcefulness."
        ),
        why_it_matters=(
            "Learners who translate from English say 'uccidere due uccelli con una pietra' — "
            "this is understood but sounds foreign. The piccioni/fava version is the "
            "authentic Italian expression."
        ),
        variants=(
            PhraseVariant("prendere due piccioni con una fava", MatchType.exact),
            PhraseVariant("ho preso due piccioni con una fava", MatchType.inflectional_variant,
                          note="Past: I killed two birds with one stone."),
            PhraseVariant("uccidere due uccelli con una pietra", MatchType.confusable_not_same,
                          note="Literal translation from English — understood but foreign-sounding."),
        ),
        tags=("efficiency", "resourcefulness", "neutral", "proverb"),
    ),

    "it_avere_le_mani_in_pasta": PhraseFamily(
        id="it_avere_le_mani_in_pasta",
        language="it",
        canonical_form="avere le mani in pasta",
        meaning="To have a hand in something; to be deeply involved in a matter.",
        register="neutral",
        origin=(
            "The image is of hands kneading dough (pasta = dough, not pasta the food here) — "
            "deeply embedded in the process. 'Avere le mani in pasta' implies both involvement "
            "and influence, often with a slight connotation of insider knowledge or pulling strings."
        ),
        why_it_matters=(
            "The word pasta misleads learners into thinking of the food. "
            "Here pasta means 'dough' — the original meaning. Understanding the "
            "bread-making image unlocks the metaphor: hands deep in dough = deep involvement."
        ),
        variants=(
            PhraseVariant("avere le mani in pasta", MatchType.exact),
            PhraseVariant("ha le mani in pasta", MatchType.inflectional_variant,
                          note="He/she has a hand in it — most common form."),
            PhraseVariant("mettere le mani in pasta", MatchType.inflectional_variant,
                          note="To get involved, to put one's hands in (begin involvement)."),
        ),
        tags=("involvement", "influence", "neutral", "insider"),
    ),

    "it_essere_fuori_strada": PhraseFamily(
        id="it_essere_fuori_strada",
        language="it",
        canonical_form="essere fuori strada",
        meaning="To be on the wrong track; to be mistaken or misguided.",
        register="neutral",
        origin=(
            "Literally 'to be off the road' — the image of having left the intended "
            "path. Used both literally (wrong direction) and figuratively (wrong approach "
            "or mistaken belief). Common in arguments, debates, and reasoning contexts."
        ),
        why_it_matters=(
            "A versatile expression for calling out errors in reasoning or approach. "
            "Learners often use sbagliato (wrong/mistaken) — fuori strada is more vivid "
            "and idiomatic when describing someone's direction of thinking."
        ),
        variants=(
            PhraseVariant("essere fuori strada", MatchType.exact),
            PhraseVariant("sei fuori strada", MatchType.inflectional_variant,
                          note="You're on the wrong track."),
            PhraseVariant("è fuori strada", MatchType.inflectional_variant,
                          note="He/she is on the wrong track."),
            PhraseVariant("andare fuori strada", MatchType.inflectional_variant,
                          note="To go off track — often used for going astray gradually."),
        ),
        tags=("error", "reasoning", "neutral", "direction"),
    ),

    "it_avere_la_luna_di_traverso": PhraseFamily(
        id="it_avere_la_luna_di_traverso",
        language="it",
        canonical_form="avere la luna di traverso",
        meaning="To be in a foul mood; to be cross or irritable (literally: to have the moon sideways).",
        register="informal",
        origin=(
            "The moon (luna) controls moods in Italian superstition; when it's 'sideways' "
            "(di traverso), things go wrong. Also expressed as alzarsi con la luna storta "
            "(to get up with the crooked moon). Directly related to the word lunatic, "
            "which derives from luna."
        ),
        why_it_matters=(
            "The word luna (moon) explaining bad moods connects to lunatic in a way "
            "learners find memorable. A rich cultural footnote for advanced learners: "
            "the same belief that gave English lunatic drives this Italian idiom."
        ),
        variants=(
            PhraseVariant("avere la luna di traverso", MatchType.exact),
            PhraseVariant("ha la luna di traverso", MatchType.inflectional_variant,
                          note="He/she is in a foul mood."),
            PhraseVariant("alzarsi con la luna storta", MatchType.inflectional_variant,
                          note="To get up on the wrong side of the bed — lit. 'crooked moon.'"),
            PhraseVariant("avere la luna storta", MatchType.inflectional_variant,
                          note="Variant with storta (crooked) instead of di traverso."),
        ),
        tags=("mood", "irritability", "informal", "moon-superstition"),
    ),

    "it_tirare_il_fiato": PhraseFamily(
        id="it_tirare_il_fiato",
        language="it",
        canonical_form="tirare il fiato",
        meaning="To catch one's breath; to take a moment to rest or recover.",
        register="neutral",
        origin=(
            "Fiato (breath) from Latin flatus 'blowing, breath.' "
            "Tirare il fiato literally means 'to pull/draw the breath' — "
            "the image of deliberately drawing in air after exertion. "
            "Also used figuratively for a brief respite from stress or pressure."
        ),
        why_it_matters=(
            "Common in both physical and metaphorical contexts. Learners often use "
            "riposarsi (to rest) — tirare il fiato is more idiomatic for a brief pause "
            "rather than full rest."
        ),
        variants=(
            PhraseVariant("tirare il fiato", MatchType.exact),
            PhraseVariant("tiro il fiato", MatchType.inflectional_variant,
                          note="I'm catching my breath."),
            PhraseVariant("prendere fiato", MatchType.inflectional_variant,
                          note="Near-synonym: to take a breath / catch one's breath."),
            PhraseVariant("non avere fiato", MatchType.confusable_not_same,
                          note="To be out of breath — different meaning."),
        ),
        tags=("rest", "breathing", "neutral", "recovery"),
    ),

    "it_dormire_sugli_allori": PhraseFamily(
        id="it_dormire_sugli_allori",
        language="it",
        canonical_form="dormire sugli allori",
        meaning="To rest on one's laurels; to stop making effort after initial success.",
        register="neutral",
        origin=(
            "Allori (laurels) were the crowns awarded to Greek and Roman victors and poets. "
            "The Italian expression, like the English equivalent, warns against using "
            "past success as an excuse for present complacency. Common in motivational "
            "and critical contexts."
        ),
        why_it_matters=(
            "A direct parallel to the English 'rest on one's laurels' — the shared "
            "classical origin makes this an ideal bridge for learners. The allori image "
            "also connects to the historical weight of the laurel in Italian culture "
            "(the laureate / laurea university degree)."
        ),
        variants=(
            PhraseVariant("dormire sugli allori", MatchType.exact),
            PhraseVariant("riposare sugli allori", MatchType.inflectional_variant,
                          note="Variant with riposare (to rest) — equally common."),
            PhraseVariant("non dormire sugli allori", MatchType.inflectional_variant,
                          note="Not to rest on one's laurels — often used as encouragement."),
        ),
        tags=("complacency", "success", "neutral", "classical"),
    ),

    "it_mettere_il_carro_davanti_ai_buoi": PhraseFamily(
        id="it_mettere_il_carro_davanti_ai_buoi",
        language="it",
        canonical_form="mettere il carro davanti ai buoi",
        meaning="To put the cart before the ox; to do things in the wrong order.",
        register="neutral",
        origin=(
            "The Italian version uses buoi (oxen) rather than the English 'horse.' "
            "Historically oxen, not horses, pulled carts in Italian agriculture. "
            "The expression warns against reversing the logical order of things — "
            "acting before planning, or enjoying results before doing the work."
        ),
        why_it_matters=(
            "A common proverb-like expression in planning discussions and arguments. "
            "The oxen (buoi) detail is a useful reminder that Italian idioms often "
            "reflect the agricultural reality of pre-industrial Italy."
        ),
        variants=(
            PhraseVariant("mettere il carro davanti ai buoi", MatchType.exact),
            PhraseVariant("metti il carro davanti ai buoi", MatchType.inflectional_variant,
                          note="You're putting the cart before the ox."),
            PhraseVariant("il carro davanti ai buoi", MatchType.inflectional_variant,
                          note="Elliptical — just the image, commonly understood."),
        ),
        tags=("order", "planning", "neutral", "proverb", "agricultural"),
    ),

    # ── Portuguese catalog ────────────────────────────────────────────────────

    "pt_fazer_vista_grossa": PhraseFamily(
        id="pt_fazer_vista_grossa",
        language="pt",
        canonical_form="fazer vista grossa",
        meaning="To turn a blind eye; to deliberately overlook something.",
        register="neutral",
        origin=(
            "Vista (sight/view) + grossa (thick, coarse): to make one's view 'thick' "
            "or blurry — seeing something but choosing not to see it clearly. "
            "Used in both Brazilian and European Portuguese, especially in contexts "
            "of authority looking away from wrongdoing."
        ),
        why_it_matters=(
            "Common in journalistic and political language. Learners often use "
            "ignorar (to ignore) which is correct but less idiomatic. "
            "Fazer vista grossa implies deliberate choice, not mere inattention."
        ),
        variants=(
            PhraseVariant("fazer vista grossa", MatchType.exact),
            PhraseVariant("fez vista grossa", MatchType.inflectional_variant,
                          note="Past: turned a blind eye."),
            PhraseVariant("fazer vista grossa para", MatchType.inflectional_variant,
                          note="With complement: to turn a blind eye to something."),
        ),
        tags=("complicity", "oversight", "neutral", "authority"),
    ),

    "pt_ficar_a_ver_navios": PhraseFamily(
        id="pt_ficar_a_ver_navios",
        language="pt",
        canonical_form="ficar a ver navios",
        meaning="To be left empty-handed; to miss out (literally: to be left watching ships sail away).",
        register="informal",
        origin=(
            "The image of standing at the dock watching ships leave — the goods, "
            "the opportunity, or the person you expected has departed. "
            "A uniquely Portuguese expression reflecting the nation's seafaring history "
            "and the poignancy of watching departures."
        ),
        why_it_matters=(
            "This expression has no direct English equivalent and is deeply Portuguese — "
            "the ship imagery connects to the Age of Discovery and the emotional weight "
            "of watching departures (related to saudade). A cultural gem."
        ),
        variants=(
            PhraseVariant("ficar a ver navios", MatchType.exact),
            PhraseVariant("ficou a ver navios", MatchType.inflectional_variant,
                          note="He/she was left empty-handed."),
            PhraseVariant("fiquei a ver navios", MatchType.inflectional_variant,
                          note="I was left watching ships / I missed out."),
        ),
        tags=("disappointment", "missing-out", "informal", "seafaring", "cultural"),
    ),

    "pt_cair_como_uma_luva": PhraseFamily(
        id="pt_cair_como_uma_luva",
        language="pt",
        canonical_form="cair como uma luva",
        meaning="To fit like a glove; to be perfectly suited.",
        register="neutral",
        origin=(
            "Luva (glove) from Germanic *lofa (palm of the hand). "
            "The glove that fits perfectly is the pan-European image of exact suitability. "
            "Used in Brazilian and European Portuguese for anything — clothes, plans, "
            "people — that fits a situation exactly."
        ),
        why_it_matters=(
            "A direct parallel to the English 'fits like a glove.' The Portuguese verb "
            "cair (to fall/drop) is the key difference from English: something 'falls' "
            "perfectly into place, rather than 'fitting.'"
        ),
        variants=(
            PhraseVariant("cair como uma luva", MatchType.exact),
            PhraseVariant("caiu como uma luva", MatchType.inflectional_variant,
                          note="It fit like a glove (past)."),
            PhraseVariant("serve como uma luva", MatchType.inflectional_variant,
                          note="Near-synonym with servir (to serve/fit) — also common."),
        ),
        tags=("suitability", "perfect-fit", "neutral", "clothes"),
    ),

    "pt_pagar_o_pato": PhraseFamily(
        id="pt_pagar_o_pato",
        language="pt",
        canonical_form="pagar o pato",
        meaning="To pay the price for something; to take the blame or face consequences.",
        register="informal",
        origin=(
            "Pato (duck) possibly from a historical story about an innocent duck "
            "that suffered for another's mistake. Alternatively, pato may derive from "
            "an older sense of 'misfortune.' Common in Brazil; also used in Portugal "
            "though less frequently."
        ),
        why_it_matters=(
            "The duck (pato) makes this expression memorable and non-compositional. "
            "Learners cannot guess the meaning from the words alone. "
            "A good marker of informal register and Brazilian Portuguese in particular."
        ),
        variants=(
            PhraseVariant("pagar o pato", MatchType.exact),
            PhraseVariant("paguei o pato", MatchType.inflectional_variant,
                          note="I paid the price / I took the blame."),
            PhraseVariant("vai pagar o pato", MatchType.inflectional_variant,
                          note="He/she will face the consequences."),
        ),
        tags=("consequences", "blame", "informal", "Brazilian"),
    ),

    "pt_meter_os_pes_pelas_maos": PhraseFamily(
        id="pt_meter_os_pes_pelas_maos",
        language="pt",
        canonical_form="meter os pés pelas mãos",
        meaning="To make a mess of things; to bungle; to put one's foot in it.",
        register="informal",
        origin=(
            "Literally 'to put feet through/by hands' — the confusion of feet and hands "
            "creates a vivid image of total coordination failure. "
            "Primarily European Portuguese; Brazilian Portuguese prefers meter os pés "
            "pelas mãos or cometer uma gafe."
        ),
        why_it_matters=(
            "The feet-and-hands confusion is visually funny and memorable. "
            "An important informal expression for blundering. "
            "Learners need this alongside English 'put one's foot in one's mouth.'"
        ),
        variants=(
            PhraseVariant("meter os pés pelas mãos", MatchType.exact),
            PhraseVariant("meteu os pés pelas mãos", MatchType.inflectional_variant,
                          note="He/she bungled it."),
            PhraseVariant("meteu o pé", MatchType.inflectional_variant,
                          note="Shortened form — put their foot in it."),
        ),
        tags=("blunder", "mistake", "informal", "coordination"),
    ),

    "pt_matar_dois_coelhos": PhraseFamily(
        id="pt_matar_dois_coelhos",
        language="pt",
        canonical_form="matar dois coelhos de uma cajadada",
        meaning="To kill two birds with one stone (literally: to kill two rabbits with one blow of a staff).",
        register="neutral",
        origin=(
            "Portuguese uses coelhos (rabbits) and cajadada (blow of a shepherd's staff), "
            "not birds and stones. The shepherd's crook image reflects the pastoral "
            "tradition of the Iberian Peninsula. Similar to the Spanish version "
            "but with distinct vocabulary."
        ),
        why_it_matters=(
            "The rabbits-and-staff version sounds strange to English learners who expect "
            "'birds and stones.' Learning this phrase teaches learners that idioms are "
            "language-specific, not universal."
        ),
        variants=(
            PhraseVariant("matar dois coelhos de uma cajadada", MatchType.exact),
            PhraseVariant("matar dois coelhos de uma cajadada só", MatchType.inflectional_variant,
                          note="With só (only) for emphasis — very common."),
            PhraseVariant("matar dois pássaros de uma cajadada", MatchType.inflectional_variant,
                          note="Variant with pássaros (birds) — less common."),
        ),
        tags=("efficiency", "resourcefulness", "neutral", "proverb"),
    ),

    "pt_dar_uma_mao": PhraseFamily(
        id="pt_dar_uma_mao",
        language="pt",
        canonical_form="dar uma mão",
        meaning="To give someone a hand; to help.",
        register="neutral",
        origin=(
            "Mão from Latin manus (hand). The giving-of-the-hand as a metaphor for "
            "help is pan-European. Portuguese dar uma mão parallels Italian dare una mano, "
            "Spanish dar una mano, and French donner un coup de main."
        ),
        why_it_matters=(
            "The most natural way to offer or ask for help in informal speech. "
            "Learners who use only ajudar (to help) are understood but miss "
            "the warmer, more colloquial tone of dar uma mão."
        ),
        variants=(
            PhraseVariant("dar uma mão", MatchType.exact),
            PhraseVariant("me dás uma mão?", MatchType.inflectional_variant,
                          note="EP: Can you give me a hand?"),
            PhraseVariant("me dá uma mão?", MatchType.inflectional_variant,
                          note="BP: Can you give me a hand?"),
            PhraseVariant("dou-te uma mão", MatchType.inflectional_variant,
                          note="EP: I'll give you a hand."),
        ),
        tags=("help", "assistance", "neutral", "everyday"),
    ),

    "pt_engolir_em_seco": PhraseFamily(
        id="pt_engolir_em_seco",
        language="pt",
        canonical_form="engolir em seco",
        meaning="To swallow hard; to react with shock or discomfort without speaking.",
        register="neutral",
        origin=(
            "Literally 'to swallow dry' — the involuntary swallow of anxiety or shock "
            "when the mouth goes dry. Used to describe the physical reaction to bad news, "
            "an uncomfortable situation, or suppressed emotion."
        ),
        why_it_matters=(
            "A precise expression for a very specific physical-emotional moment. "
            "No English single-phrase equivalent captures both the physical sensation "
            "and the emotional suppression. Common in narrative writing and speech."
        ),
        variants=(
            PhraseVariant("engolir em seco", MatchType.exact),
            PhraseVariant("engoliu em seco", MatchType.inflectional_variant,
                          note="He/she swallowed hard (past)."),
            PhraseVariant("engoli em seco", MatchType.inflectional_variant,
                          note="I swallowed hard (past)."),
        ),
        tags=("shock", "anxiety", "physical-reaction", "neutral"),
    ),

    "pt_tirar_o_cavalinho_da_chuva": PhraseFamily(
        id="pt_tirar_o_cavalinho_da_chuva",
        language="pt",
        canonical_form="tirar o cavalinho da chuva",
        meaning="To give up on an unrealistic hope; to abandon a vain expectation.",
        register="informal",
        origin=(
            "Literally 'take the little horse out of the rain' — a vivid image of "
            "letting go of something you'd prepared for but that isn't going to happen. "
            "The diminutive cavalinho (little horse) adds a tone of gentle resignation. "
            "Primarily Brazilian Portuguese."
        ),
        why_it_matters=(
            "The diminutive cavalinho makes this expression particularly charming and Brazilian. "
            "No English equivalent captures the gentle, pragmatic resignation. "
            "The image of the rain-soaked horse awaiting a journey that won't happen "
            "is both funny and melancholy."
        ),
        variants=(
            PhraseVariant("tirar o cavalinho da chuva", MatchType.exact),
            PhraseVariant("pode tirar o cavalinho da chuva", MatchType.inflectional_variant,
                          note="You can forget about it — you can take the horse out of the rain."),
            PhraseVariant("tira o cavalinho da chuva", MatchType.inflectional_variant,
                          note="Imperative: give up that hope."),
        ),
        tags=("resignation", "expectation", "informal", "Brazilian", "diminutive"),
    ),

    "pt_por_a_boca_no_trombone": PhraseFamily(
        id="pt_por_a_boca_no_trombone",
        language="pt",
        canonical_form="pôr a boca no trombone",
        meaning="To speak out publicly; to blow the whistle; to make noise about something.",
        register="informal",
        origin=(
            "Literally 'to put one's mouth to the trombone' — the image of a musician "
            "blowing a loud instrument to be heard. Used for speaking out, complaining "
            "publicly, or raising an alarm. Common in Brazilian Portuguese."
        ),
        why_it_matters=(
            "A colorful Brazilian expression with no direct English equivalent. "
            "The trombone image makes the loudness and deliberateness of the speech "
            "vivid. Contrasts with the silence of engolir em seco."
        ),
        variants=(
            PhraseVariant("pôr a boca no trombone", MatchType.exact),
            PhraseVariant("botar a boca no trombone", MatchType.inflectional_variant,
                          note="BP variant: botar instead of pôr — very common in Brazil."),
            PhraseVariant("pôs a boca no trombone", MatchType.inflectional_variant,
                          note="Past: spoke out publicly."),
        ),
        tags=("speaking-out", "protest", "informal", "Brazilian"),
    ),

    "pt_fazer_as_pazes": PhraseFamily(
        id="pt_fazer_as_pazes",
        language="pt",
        canonical_form="fazer as pazes",
        meaning="To make peace; to reconcile after a quarrel.",
        register="neutral",
        origin=(
            "From Latin pacem facere. The plural as pazes (rather than a paz) is idiomatic — "
            "a paz refers to general/political peace, while as pazes always refers to "
            "interpersonal reconciliation. Identical construction to Spanish hacer las paces."
        ),
        why_it_matters=(
            "The plural is essential — fazer a paz would refer to bringing about world peace, "
            "not patching up a friendship. This distinction trips up learners who translate "
            "literally from English 'make peace.'"
        ),
        variants=(
            PhraseVariant("fazer as pazes", MatchType.exact),
            PhraseVariant("fizemos as pazes", MatchType.inflectional_variant,
                          note="We made up / we reconciled."),
            PhraseVariant("fazer as pazes com", MatchType.inflectional_variant,
                          note="To make up with someone: fazer as pazes com ela."),
            PhraseVariant("fazer a paz", MatchType.confusable_not_same,
                          note="To make (political) peace — not interpersonal reconciliation."),
        ),
        tags=("reconciliation", "friendship", "neutral", "conflict"),
    ),

    "pt_quem_nao_arrisca_nao_petisca": PhraseFamily(
        id="pt_quem_nao_arrisca_nao_petisca",
        language="pt",
        canonical_form="quem não arrisca não petisca",
        meaning="Nothing ventured, nothing gained (literally: who doesn't risk doesn't snack).",
        register="informal",
        origin=(
            "A rhyming proverb: arrisca (risks) rhymes with petisca (nibbles/snacks). "
            "The food imagery is quintessentially Portuguese — reward framed as snacking. "
            "A uniquely playful take on the universal risk-reward principle."
        ),
        why_it_matters=(
            "The rhyme makes it instantly memorable. The petisco (snack) framing "
            "connects to Portuguese food culture — petiscos are the Portuguese equivalent "
            "of tapas. The proverb is fun, colloquial, and very quotable."
        ),
        variants=(
            PhraseVariant("quem não arrisca não petisca", MatchType.exact),
        ),
        tags=("risk", "reward", "proverb", "rhyme", "informal", "food"),
    ),

    "pt_deixar_para_amanha": PhraseFamily(
        id="pt_deixar_para_amanha",
        language="pt",
        canonical_form="deixar para amanhã",
        meaning="To put off until tomorrow; to procrastinate.",
        register="neutral",
        origin=(
            "Often quoted alongside the full proverb: 'Não deixes para amanhã o que "
            "podes fazer hoje' (Don't leave for tomorrow what you can do today). "
            "The short form is widely used alone to describe procrastination."
        ),
        why_it_matters=(
            "The full proverb is the Portuguese equivalent of 'Don't put off until tomorrow.' "
            "Learning the short form first helps learners recognise the full proverb when encountered. "
            "The amanhã (tomorrow) links to the concept of saudade — Portuguese relationship with time."
        ),
        variants=(
            PhraseVariant("deixar para amanhã", MatchType.exact),
            PhraseVariant("não deixes para amanhã", MatchType.inflectional_variant,
                          note="Don't leave it for tomorrow — the imperative/advice form."),
            PhraseVariant("não deixe para amanhã o que pode fazer hoje", MatchType.inflectional_variant,
                          note="Full proverb form."),
        ),
        tags=("procrastination", "time", "proverb", "neutral"),
    ),

    # ── Russian catalog ───────────────────────────────────────────────────────

    "ru_veshat_lapshu_na_ushi": PhraseFamily(
        id="ru_veshat_lapshu_na_ushi",
        language="ru",
        canonical_form="вешать лапшу на уши",
        meaning="To pull someone's leg; to feed someone nonsense; to deceive with false stories.",
        register="informal",
        origin=(
            "Literally 'to hang noodles on ears' — the image of noodles stuck to ears "
            "suggests cluttering someone's hearing with nonsense. "
            "Origin disputed: possibly from theatrical slang or 20th-century colloquial speech. "
            "The expression is vivid, informal, and very Russian in its absurdist image."
        ),
        why_it_matters=(
            "One of the most characteristic Russian idioms for deception through talk. "
            "The noodle-on-ears image has no English equivalent. Knowing this expression "
            "gives learners insight into Russian colloquial humor and wordplay."
        ),
        variants=(
            PhraseVariant("вешать лапшу на уши", MatchType.exact),
            PhraseVariant("не вешай мне лапшу на уши", MatchType.inflectional_variant,
                          note="Don't feed me nonsense — common direct challenge."),
            PhraseVariant("повесил лапшу на уши", MatchType.inflectional_variant,
                          note="Past perfective: he hung noodles on ears (he deceived them)."),
            PhraseVariant("вешал лапшу на уши", MatchType.inflectional_variant,
                          note="Past imperfective: he was feeding them nonsense (ongoing)."),
        ),
        tags=("deception", "nonsense", "informal", "colloquial", "absurdist"),
    ),

    "ru_bit_baklushi": PhraseFamily(
        id="ru_bit_baklushi",
        language="ru",
        canonical_form="бить баклуши",
        meaning="To loaf; to idle; to do nothing productive.",
        register="informal",
        origin=(
            "Баклуши were rough wooden blocks knocked from a log before being shaped "
            "into spoons or ladles — the easiest, most unskilled stage of the work. "
            "Someone given баклуши to knock (бить) was doing the most trivial job. "
            "The expression may also derive from the sounds of billiard balls (billiard = "
            "баллярд) or from splitting kindling."
        ),
        why_it_matters=(
            "The etymology is uncertain but the image — trivial knocking work — gives "
            "the metaphor meaning. One of several Russian idioms where the origin "
            "illuminates the industrial or craft history of the country."
        ),
        variants=(
            PhraseVariant("бить баклуши", MatchType.exact),
            PhraseVariant("бьёт баклуши", MatchType.inflectional_variant,
                          note="He/she is loafing (present imperfective)."),
            PhraseVariant("бил баклуши", MatchType.inflectional_variant,
                          note="He was idling (past masculine)."),
            PhraseVariant("перестать бить баклуши", MatchType.inflectional_variant,
                          note="To stop loafing — often used as an imperative."),
        ),
        tags=("idleness", "laziness", "informal", "colloquial"),
    ),

    "ru_vodit_za_nos": PhraseFamily(
        id="ru_vodit_za_nos",
        language="ru",
        canonical_form="водить за нос",
        meaning="To lead by the nose; to deceive or manipulate someone.",
        register="neutral",
        origin=(
            "The image of leading an animal by a ring through its nose — the animal "
            "follows without understanding where it's going. Used for deliberate, "
            "sustained deception or manipulation, not a one-time lie."
        ),
        why_it_matters=(
            "A vivid metaphor shared with English 'lead by the nose' — the parallel "
            "makes it easy to learn. The imperfective verb водить (to lead repeatedly) "
            "emphasizes the ongoing nature of the deception, reinforcing the aspect "
            "system for learners."
        ),
        variants=(
            PhraseVariant("водить за нос", MatchType.exact),
            PhraseVariant("водит за нос", MatchType.inflectional_variant,
                          note="He/she is leading them by the nose (present ongoing)."),
            PhraseVariant("не дай водить себя за нос", MatchType.inflectional_variant,
                          note="Don't let yourself be led by the nose."),
            PhraseVariant("провести за нос", MatchType.inflectional_variant,
                          note="Perfective: to have successfully deceived — a completed act."),
        ),
        tags=("deception", "manipulation", "neutral", "aspect"),
    ),

    "ru_kak_kot_naplakal": PhraseFamily(
        id="ru_kak_kot_naplakal",
        language="ru",
        canonical_form="как кот наплакал",
        meaning="Next to nothing; a tiny amount (literally: as much as a cat cried).",
        register="informal",
        origin=(
            "Cats don't cry — so 'as much as a cat cried' is zero or as good as zero. "
            "The perfect aspect наплакал (has cried, completely) makes the absence "
            "total and definitive. A memorably absurdist image for scarcity."
        ),
        why_it_matters=(
            "This expression is loved by Russian speakers and sounds authentically "
            "colloquial. The cat image makes it memorable. It also demonstrates the "
            "perfective aspect (наплакал) used to indicate a completed null quantity."
        ),
        variants=(
            PhraseVariant("как кот наплакал", MatchType.exact),
            PhraseVariant("денег — как кот наплакал", MatchType.inflectional_variant,
                          note="Money — next to nothing (with the thing being measured named first)."),
        ),
        tags=("scarcity", "quantity", "informal", "absurdist", "humorous"),
    ),

    "ru_ni_ryba_ni_myaso": PhraseFamily(
        id="ru_ni_ryba_ni_myaso",
        language="ru",
        canonical_form="ни рыба ни мясо",
        meaning="Neither fish nor fowl; someone or something without a distinct character.",
        register="neutral",
        origin=(
            "The fish-and-meat binary was historically significant in Russian Orthodox "
            "culture: fish was the permitted food on fast days; meat was allowed otherwise. "
            "Something that was neither fish nor meat fell outside both categories — "
            "useless and undefined."
        ),
        why_it_matters=(
            "The English 'neither fish nor fowl' shares the same conceptual origin "
            "(religious dietary categories), making the parallel memorable. "
            "The Russian version uses рыба/мясо (fish/meat) instead of fish/fowl, "
            "reflecting Orthodox fasting traditions."
        ),
        variants=(
            PhraseVariant("ни рыба ни мясо", MatchType.exact),
            PhraseVariant("он ни рыба ни мясо", MatchType.inflectional_variant,
                          note="He is neither fish nor fowl."),
        ),
        tags=("indecision", "blandness", "neutral", "Orthodox-culture"),
    ),

    "ru_lomat_golovu": PhraseFamily(
        id="ru_lomat_golovu",
        language="ru",
        canonical_form="ломать голову",
        meaning="To rack one's brains; to think hard about a difficult problem.",
        register="neutral",
        origin=(
            "Literally 'to break the head' — intensive mental effort as a kind of "
            "physical breaking. The imperfective ломать suggests ongoing, prolonged "
            "effort. Found in Pushkin and other classic Russian literature."
        ),
        why_it_matters=(
            "One of the most common expressions for difficult thinking. "
            "The 'breaking' image parallels English 'rack one's brains' (rack = stretch on a rack). "
            "Both metaphors treat hard thinking as physical suffering."
        ),
        variants=(
            PhraseVariant("ломать голову", MatchType.exact),
            PhraseVariant("ломаю голову", MatchType.inflectional_variant,
                          note="I'm racking my brains (present, ongoing effort)."),
            PhraseVariant("ломал голову над", MatchType.inflectional_variant,
                          note="Was racking brains over [problem] — imperfective past."),
            PhraseVariant("сломал голову", MatchType.inflectional_variant,
                          note="Perfective: broke head completely — exhausted thinking about it."),
        ),
        tags=("thinking", "difficulty", "neutral", "mental-effort", "aspect"),
    ),

    "ru_brat_byka_za_roga": PhraseFamily(
        id="ru_brat_byka_za_roga",
        language="ru",
        canonical_form="брать быка за рога",
        meaning="To take the bull by the horns; to tackle a problem head-on.",
        register="neutral",
        origin=(
            "The bull-by-the-horns image is shared with English, Spanish, and French. "
            "In Russian the imperfective брать emphasizes the ongoing resolve to "
            "tackle problems directly. The perfective взять быка за рога is used "
            "for a completed decisive action."
        ),
        why_it_matters=(
            "The English parallel makes this easy to learn. The aspect distinction "
            "(брать / взять) is a perfect teaching example: imperfective = ongoing "
            "tendency to act decisively; perfective = specific decisive action taken."
        ),
        variants=(
            PhraseVariant("брать быка за рога", MatchType.exact),
            PhraseVariant("взять быка за рога", MatchType.inflectional_variant,
                          note="Perfective: to have taken the bull by the horns (one decisive act)."),
            PhraseVariant("берём быка за рога", MatchType.inflectional_variant,
                          note="We take the bull by the horns — determination statement."),
        ),
        tags=("decisiveness", "action", "neutral", "aspect"),
    ),

    "ru_iz_ognya_da_v_polymya": PhraseFamily(
        id="ru_iz_ognya_da_v_polymya",
        language="ru",
        canonical_form="из огня да в полымя",
        meaning="Out of the frying pan into the fire (literally: from the fire into the flame).",
        register="neutral",
        origin=(
            "Полымя is an archaic word for open flame (related to пламя, modern word). "
            "The expression uses the old dative/locative form полымя. "
            "Moving from fire (огонь) into flame (полымя/пламя) means going to "
            "something even worse. The archaic word gives the phrase a proverb-like quality."
        ),
        why_it_matters=(
            "The archaic полымя makes this sound proverbial. Learners who know "
            "только хуже (only worse) can describe the situation, but "
            "из огня да в полымя is far more idiomatic. "
            "The old vocab makes it memorable."
        ),
        variants=(
            PhraseVariant("из огня да в полымя", MatchType.exact),
            PhraseVariant("из огня да в пламя", MatchType.modernized_variant,
                          note="With modern пламя instead of archaic полымя — less common."),
            PhraseVariant("попасть из огня да в полымя", MatchType.inflectional_variant,
                          note="To end up from the fire into the flame — completed misfortune."),
        ),
        tags=("misfortune", "worsening", "neutral", "proverb", "archaic"),
    ),

    "ru_kot_v_meshke": PhraseFamily(
        id="ru_kot_v_meshke",
        language="ru",
        canonical_form="кот в мешке",
        meaning="A pig in a poke; something bought/accepted without knowing what it is.",
        register="neutral",
        origin=(
            "Literally 'a cat in a sack.' The Russian version uses a cat (кот) where "
            "English uses a pig (pig in a poke). Both refer to the medieval market fraud "
            "of selling a cat in a sack instead of the promised suckling pig. "
            "The Russian прoverb покупать кота в мешке means to buy without examining."
        ),
        why_it_matters=(
            "The cat vs. pig difference is a useful lesson in parallel but distinct idioms. "
            "Both languages have the same medieval fraud as origin. "
            "The Russian кот (male cat) is common, specific, and gendered — "
            "a detail worth noting."
        ),
        variants=(
            PhraseVariant("кот в мешке", MatchType.exact),
            PhraseVariant("покупать кота в мешке", MatchType.inflectional_variant,
                          note="To buy a pig in a poke — the fuller verbal form."),
            PhraseVariant("купил кота в мешке", MatchType.inflectional_variant,
                          note="Perfective past: bought without knowing what they got."),
        ),
        tags=("deception", "purchase", "neutral", "proverb"),
    ),

    "ru_derzhat_v_kurse": PhraseFamily(
        id="ru_derzhat_v_kurse",
        language="ru",
        canonical_form="держать в курсе",
        meaning="To keep someone in the loop; to keep informed.",
        register="neutral",
        origin=(
            "Курс was borrowed from French cours or German Kurs (course, direction). "
            "Держать в курсе means to keep someone 'on course' — updated and oriented. "
            "A modern, professional expression used widely in business, journalism, "
            "and everyday communication."
        ),
        why_it_matters=(
            "Essential for professional communication. The phrase держать в курсе "
            "is extremely common in emails and meetings. Learning it gives learners "
            "access to Russian workplace idiom. The курс (course) etymology connects "
            "to the nautical/directional sense."
        ),
        variants=(
            PhraseVariant("держать в курсе", MatchType.exact),
            PhraseVariant("держать в курсе дел", MatchType.inflectional_variant,
                          note="Keep in the loop about things — fuller form."),
            PhraseVariant("держи меня в курсе", MatchType.inflectional_variant,
                          note="Keep me posted — common request."),
            PhraseVariant("быть в курсе", MatchType.inflectional_variant,
                          note="To be in the loop (state) — different verb."),
        ),
        tags=("communication", "information", "neutral", "professional"),
    ),

    "ru_mezhdu_molotom_i_nakovalnei": PhraseFamily(
        id="ru_mezhdu_molotom_i_nakovalnei",
        language="ru",
        canonical_form="между молотом и наковальней",
        meaning="Between a rock and a hard place; in an impossible position.",
        register="neutral",
        origin=(
            "Literally 'between the hammer and the anvil.' The blacksmithing image — "
            "compressed between the striking hammer and the unyielding anvil — "
            "is common across European languages. It was the title of a famous "
            "novel by Friedrich Spielhagen (1868), widely translated."
        ),
        why_it_matters=(
            "The hammer-and-anvil image is more vivid than the English 'rock and hard place.' "
            "Both describe entrapment between two forces. Learning this phrase also "
            "connects to the industrial/craft vocabulary (молот, наковальня) that appears "
            "in Russian songs and literature."
        ),
        variants=(
            PhraseVariant("между молотом и наковальней", MatchType.exact),
            PhraseVariant("оказаться между молотом и наковальней", MatchType.inflectional_variant,
                          note="To find oneself between the hammer and anvil."),
            PhraseVariant("быть между молотом и наковальней", MatchType.inflectional_variant,
                          note="To be in an impossible position."),
        ),
        tags=("dilemma", "impossible-choice", "neutral", "smithing"),
    ),

    "ru_ne_v_brov_a_v_glaz": PhraseFamily(
        id="ru_ne_v_brov_a_v_glaz",
        language="ru",
        canonical_form="не в бровь а в глаз",
        meaning="To hit the nail on the head; to say something precisely and aptly.",
        register="neutral",
        origin=(
            "Literally 'not in the eyebrow but in the eye' — aiming for the eyebrow "
            "but hitting the eye is actually more accurate, not a mistake. "
            "Used to praise a remark that lands exactly right, cuts to the truth, "
            "or precisely describes a situation."
        ),
        why_it_matters=(
            "The anatomy-of-the-face image is characteristically Russian. The paradox "
            "(missing the eyebrow = hitting the eye = success) makes it memorable. "
            "It's used to praise wit or precision, equivalent to 'you hit the nail on the head.'"
        ),
        variants=(
            PhraseVariant("не в бровь а в глаз", MatchType.exact),
            PhraseVariant("попасть не в бровь а в глаз", MatchType.inflectional_variant,
                          note="To hit it not in the eyebrow but in the eye — nailed it."),
        ),
        tags=("accuracy", "wit", "neutral", "praise", "anatomy"),
    ),

    "ru_podnyat_na_smekh": PhraseFamily(
        id="ru_podnyat_na_smekh",
        language="ru",
        canonical_form="поднять на смех",
        meaning="To make fun of; to ridicule; to hold up to public laughter.",
        register="neutral",
        origin=(
            "Literally 'to raise/lift onto laughter' — to hold someone up for others "
            "to laugh at. The perfective поднять suggests a single deliberate act of "
            "public humiliation through mockery. "
            "Used in contexts of ridicule, satire, or social shaming."
        ),
        why_it_matters=(
            "An important expression for social humiliation by laughter. "
            "The aspect is always perfective (поднять, not поднимать) — "
            "the ridicule is a complete, decisive event. "
            "Learners often use смеяться над (to laugh at) — поднять на смех "
            "emphasizes the public, collective nature of the mockery."
        ),
        variants=(
            PhraseVariant("поднять на смех", MatchType.exact),
            PhraseVariant("подняли на смех", MatchType.inflectional_variant,
                          note="They ridiculed him/her (past, 3rd plural)."),
            PhraseVariant("подняли на смех всем классом", MatchType.inflectional_variant,
                          note="The whole class laughed at them — with collective subject."),
        ),
        tags=("ridicule", "mockery", "neutral", "social", "aspect"),
    ),

    "ru_rubit_s_plecha": PhraseFamily(
        id="ru_rubit_s_plecha",
        language="ru",
        canonical_form="рубить с плеча",
        meaning="To act rashly; to decide or speak without thinking (literally: to chop from the shoulder).",
        register="neutral",
        origin=(
            "Literally 'to chop/hack from the shoulder' — a broad, uncontrolled axe-blow "
            "from the shoulder rather than a careful, precise cut. "
            "The image is of undisciplined, powerful action without subtlety. "
            "Used for rash decisions, hasty judgments, or blunt speech."
        ),
        why_it_matters=(
            "The axe imagery connects to Russian cultural history. "
            "The imperfective рубить emphasizes habitual rash behaviour (a character trait) "
            "while рубануть с плеча would describe one specific rash act. "
            "A useful aspect teaching example."
        ),
        variants=(
            PhraseVariant("рубить с плеча", MatchType.exact),
            PhraseVariant("не рубит с плеча", MatchType.inflectional_variant,
                          note="He/she doesn't act rashly — often used as praise."),
            PhraseVariant("рубанул с плеча", MatchType.inflectional_variant,
                          note="Perfective: he made one rash decision."),
            PhraseVariant("рубить сплеча", MatchType.orthographic_variant,
                          note="Merged spelling — also encountered."),
        ),
        tags=("rashness", "impulsiveness", "neutral", "aspect", "axe"),
    ),

    # ── Arabic ───────────────────────────────────────────────────────────────

    "ar_darb_usfourayn": PhraseFamily(
        id="ar_darb_usfourayn",
        language="ar",
        canonical_form="ضرب عصفورين بحجر",
        meaning="To kill two birds with one stone; to accomplish two goals with one action.",
        register="neutral",
        origin=(
            "Literally 'to strike two sparrows with one stone'. "
            "A universal idiom of efficiency existing in Arabic, English, Persian, and other languages. "
            "The verb ضرب (daraba) is one of the most productive roots in Arabic (ض-ر-ب), "
            "appearing in dozens of idioms and fixed phrases."
        ),
        why_it_matters=(
            "A high-frequency idiom in MSA prose and speech. "
            "The dual form عصفورين (usfourayn — two sparrows) is a grammatical feature unique to Arabic, "
            "making this phrase a useful hook for teaching the dual number suffix -ayn. "
            "Learning this phrase also anchors the root ض-ر-ب, which yields ضرب (to strike), "
            "مضروب (struck/product in math), ضريبة (tax — something imposed), and more."
        ),
        variants=(
            PhraseVariant("ضرب عصفورين بحجر", MatchType.exact),
            PhraseVariant("ضرب عصفورين بحجر واحد", MatchType.inflectional_variant,
                          note="With 'one stone' explicit — emphasises the single action."),
        ),
        tags=("efficiency", "decision", "neutral", "dual", "root-pattern"),
    ),

    "ar_ghamdat_ain": PhraseFamily(
        id="ar_ghamdat_ain",
        language="ar",
        canonical_form="في غمضة عين",
        meaning="In the blink of an eye; in an instant; in a very short time.",
        register="neutral",
        origin=(
            "Literally 'in the closing of an eye' — غمضة (ghamda) is the act of lowering the eyelid. "
            "The image of a blink as a unit of very short time is ancient, appearing in Classical "
            "Arabic poetry and the Quran-era literature. A universal temporal metaphor."
        ),
        why_it_matters=(
            "A common temporal idiom in MSA and literary Arabic. "
            "The construction في + مصدر (in + verbal noun) is a productive Arabic pattern "
            "for 'in the act of X'. غمضة is from root غ-م-ض (to close one's eyes), "
            "which also yields أغمض (to close the eyes) and غامض (obscure, dark — "
            "eyes-shut sense extended to mystery). A single phrase reveals root morphology."
        ),
        variants=(
            PhraseVariant("في غمضة عين", MatchType.exact),
            PhraseVariant("في لمح البصر", MatchType.inflectional_variant,
                          note="'In the glance of the eye' — a common near-synonym in MSA."),
        ),
        tags=("time", "speed", "neutral", "idiom", "literary"),
    ),

    "ar_ala_rasi": PhraseFamily(
        id="ar_ala_rasi",
        language="ar",
        canonical_form="على رأسي",
        meaning="On my head; gladly; absolutely; I am honoured to do it.",
        register="informal",
        origin=(
            "Literally 'on my head' — carrying something on the head is a gesture of the highest "
            "respect and willingness in Arab cultural tradition. "
            "The extended form على رأسي وعيني (on my head and my eye) intensifies the expression."
        ),
        why_it_matters=(
            "An essential politeness formula in spoken Arabic across dialects. "
            "The body-part metaphor (head/eye) for deference and honour is culturally important. "
            "على + رأس + possessive suffix ي demonstrates the Arabic suffix-pronoun system. "
            "Understanding this phrase illuminates why رأس (head) appears in رئيس (president — "
            "lit. head person) and رأسمال (capital — lit. head of money)."
        ),
        variants=(
            PhraseVariant("على رأسي", MatchType.exact),
            PhraseVariant("على رأسي وعيني", MatchType.inflectional_variant,
                          note="'On my head and my eye' — intensified, extremely willing."),
        ),
        tags=("politeness", "acceptance", "informal", "cultural", "body-metaphor"),
    ),

    "ar_insha_allah": PhraseFamily(
        id="ar_insha_allah",
        language="ar",
        canonical_form="إن شاء الله",
        meaning="If God wills; God willing; hopefully (expresses hope or polite uncertainty about a future event).",
        register="neutral",
        confusables=("ar_masha_allah",),
        origin=(
            "From إن (if) + شاء (he willed, past of شاء) + الله (God). "
            "The phrase reflects the Islamic principle that all future events are subject to God's will. "
            "It appears in the Quran (Surah Al-Kahf 18:23–24) as a command to always say it "
            "when speaking of future plans."
        ),
        why_it_matters=(
            "One of the most culturally essential Arabic expressions. In practice it ranges "
            "from sincere hope to polite deflection. "
            "The verb شاء (to will) uses the hollow root ش-ي-أ — an irregular paradigm "
            "that learners must recognise. Confusable with ما شاء الله (admiration) — "
            "both contain شاء الله but differ in إن (if) vs ما (what)."
        ),
        variants=(
            PhraseVariant("إن شاء الله", MatchType.exact),
            PhraseVariant("ان شاء الله", MatchType.orthographic_variant,
                          note="Without hamza on إن — common informal spelling."),
        ),
        tags=("future", "religious", "neutral", "formulaic", "Islamic"),
    ),

    "ar_alhamdulillah": PhraseFamily(
        id="ar_alhamdulillah",
        language="ar",
        canonical_form="الحمد لله",
        meaning="Praise be to God; thank God; I am grateful (response to 'how are you?' and more).",
        register="neutral",
        origin=(
            "الحمد (al-hamd — the praise) + لله (lillāh — for God, contraction of ل + الله). "
            "Opens Surah Al-Fatiha (the first chapter of the Quran) and is "
            "one of the most frequently spoken phrases in the Arabic-speaking world."
        ),
        why_it_matters=(
            "Standard response to كيف حالك (how are you?) — الحمد لله means both 'fine' and 'thank God'. "
            "The لام preposition contracts with الله: ل + الله → لله. "
            "Demonstrates Arabic definite article usage: الحمد (al-hamd — the praise). "
            "The root ح-م-د also yields محمود (praiseworthy), أحمد (more praiseworthy — a name), "
            "and حامد (one who praises) — all anchored by learning this phrase."
        ),
        variants=(
            PhraseVariant("الحمد لله", MatchType.exact),
            PhraseVariant("الحمد لله رب العالمين", MatchType.inflectional_variant,
                          note="Full opening of Al-Fatiha: 'praise be to God, Lord of the worlds'."),
        ),
        tags=("gratitude", "religious", "neutral", "formulaic", "Islamic"),
    ),

    "ar_masha_allah": PhraseFamily(
        id="ar_masha_allah",
        language="ar",
        canonical_form="ما شاء الله",
        meaning="What God has willed; how wonderful (expression of admiration, also wards off evil eye).",
        register="neutral",
        confusables=("ar_insha_allah",),
        origin=(
            "From ما (what) + شاء (he willed) + الله (God): 'what God has willed'. "
            "Used to express admiration while acknowledging God as the source of all good. "
            "Culturally, saying ما شاء الله protects the admired person from the evil eye (عين الحسد)."
        ),
        why_it_matters=(
            "Confusable with إن شاء الله: both contain شاء الله but differ in ما vs إن. "
            "ما شاء الله = what God has willed (past admiration of something seen). "
            "إن شاء الله = if God wills (future hope/uncertainty). "
            "The distinction between ما (relative 'what') and إن (conditional 'if') is critical. "
            "Both share the hollow-root verb شاء — a useful paradigm anchor."
        ),
        variants=(
            PhraseVariant("ما شاء الله", MatchType.exact),
            PhraseVariant("ماشاء الله", MatchType.orthographic_variant,
                          note="Common merged spelling — same pronunciation."),
        ),
        tags=("admiration", "religious", "neutral", "formulaic", "Islamic"),
    ),

    "ar_khalas": PhraseFamily(
        id="ar_khalas",
        language="ar",
        canonical_form="خلاص",
        meaning="That's it; enough; it's done; finished; let's stop.",
        register="informal",
        origin=(
            "From root خ-ل-ص (to be free of, to finish). خلاص (khalāṣ) is the noun/interjection "
            "meaning 'liberation/completion'. Originally Classical Arabic (خلص — to be free), "
            "now ubiquitous across all spoken dialects."
        ),
        why_it_matters=(
            "One of the most common words in everyday Arabic across all dialects. "
            "Functions as interjection, sentence adverb, and discourse particle. "
            "The root خ-ل-ص also yields مخلص (sincere, loyal), خلاصة (summary/essence), "
            "and إخلاص (devotion/sincerity) — all sharing the 'free of impurity / complete' meaning. "
            "A key A2-level word for learners."
        ),
        variants=(
            PhraseVariant("خلاص", MatchType.exact),
            PhraseVariant("خلاص بس", MatchType.inflectional_variant,
                          note="With intensifier بس (just/enough) — very emphatic closure."),
        ),
        tags=("closure", "informal", "colloquial", "interjection", "A2"),
    ),

    "ar_yalla": PhraseFamily(
        id="ar_yalla",
        language="ar",
        canonical_form="يلا",
        meaning="Let's go; come on; hurry up (general expression of encouragement or impatience).",
        register="informal",
        origin=(
            "Contracted from يا الله (ya Allah — O God) used as an exclamation to encourage action. "
            "The contraction يلا is now pan-dialectal Arabic, and has been borrowed into "
            "Turkish, Hebrew (יאלה), and other regional languages."
        ),
        why_it_matters=(
            "An essential colloquial Arabic expression heard in virtually all spoken Arabic contexts. "
            "Illustrates contraction and grammaticalisation: يا (vocative) + الله → يالله → يلا. "
            "Its diffusion into Turkish and Hebrew demonstrates Arabic's cultural reach. "
            "Learners encounter it immediately in natural conversation."
        ),
        variants=(
            PhraseVariant("يلا", MatchType.exact),
            PhraseVariant("يالله", MatchType.orthographic_variant,
                          note="Fuller/older form — 'O God' used as encouragement."),
            PhraseVariant("يلا بينا", MatchType.inflectional_variant,
                          note="'Let's go together' — common in Levantine dialects."),
        ),
        tags=("encouragement", "informal", "colloquial", "interjection", "A1"),
    ),

    "ar_mabrook": PhraseFamily(
        id="ar_mabrook",
        language="ar",
        canonical_form="مبروك",
        meaning="Congratulations; blessings upon you (on good news, achievements, or happy occasions).",
        register="neutral",
        origin=(
            "Passive participle of بارك (bāraka — to bless), from root ب-ر-ك (to kneel; to be blessed). "
            "مبروك = 'blessed'. Close variant of مبارك (mubārak — blessed), the more formal form."
        ),
        why_it_matters=(
            "The most common spoken-Arabic congratulation across all dialects. "
            "مبارك is the formal MSA equivalent (same root ب-ر-ك, different morphological pattern). "
            "The root also yields بركة (blessing) and the name مبارك. "
            "Teaching this family reveals the مفعول/مُفاعَل passive-participle contrast "
            "and shows how one root can produce both informal and formal registers."
        ),
        variants=(
            PhraseVariant("مبروك", MatchType.exact),
            PhraseVariant("مبارك", MatchType.inflectional_variant,
                          note="MSA/formal variant — same root, more formal morphological pattern."),
            PhraseVariant("مبروك عليك", MatchType.inflectional_variant,
                          note="'Congratulations to you' — with dative pronoun suffix."),
        ),
        tags=("congratulations", "celebration", "neutral", "blessing", "formulaic"),
    ),

    "ar_sabr_jamil": PhraseFamily(
        id="ar_sabr_jamil",
        language="ar",
        canonical_form="صبر جميل",
        meaning="Beautiful patience; patient endurance is the noble response (counsel of patience).",
        register="formal",
        origin=(
            "From Surah Yusuf (12:18, 12:83): فَصَبْرٌ جَمِيلٌ (fa-ṣabrun jamīl — so patience is beautiful). "
            "The phrase is spoken by the Prophet Jacob when he learns of misfortune. "
            "It entered common Arabic usage as a proverbial counsel to accept hardship with grace."
        ),
        why_it_matters=(
            "A Quranic phrase widely used as everyday counsel. "
            "صبر (ṣabr — patience/endurance) is culturally central in Islamic ethics. "
            "Root ص-ب-ر yields صابر (patient person), صبور (very patient), "
            "and الصبور (the Patient One — a name of God). "
            "جميل (jamīl — beautiful) shares root ج-م-ل with جمال (jamāl — beauty). "
            "The phrase is a minimal nominal clause: 'patience [is] beautiful [thing]' — "
            "a pedagogically clear example of Arabic's verbless equational sentence."
        ),
        variants=(
            PhraseVariant("صبر جميل", MatchType.exact),
            PhraseVariant("فصبر جميل", MatchType.inflectional_variant,
                          note="Quranic form with the fa- consequence/then particle."),
        ),
        tags=("patience", "religious", "formal", "Quranic", "ethics"),
    ),

    # ── Hebrew ───────────────────────────────────────────────────────────────

    "he_kol_hakavod": PhraseFamily(
        id="he_kol_hakavod",
        language="he",
        canonical_form="כל הכבוד",
        meaning="Well done; bravo; hats off (literally: all the honor/respect).",
        register="neutral",
        origin=(
            "כל (kol — all) + הכבוד (ha-kavod — the honor/respect). "
            "כבוד (kavod) is a key Hebrew concept: honor, dignity, and respect. "
            "Closely related to the biblical כָּבֵד (kaved — heavy, weighty, thus worthy). "
            "The phrase expresses sincere praise or admiration for an achievement."
        ),
        why_it_matters=(
            "The standard Israeli Hebrew expression for 'well done'. "
            "כבוד appears across contexts: כבוד הרב (honor of the rabbi), כבוד האדם (human dignity). "
            "Root כ-ב-ד also yields כבד (heavy), כָּבֵד (liver — the 'heavy' organ), "
            "and כיבוד (refreshments — honoring guests with food). A highly productive root."
        ),
        variants=(
            PhraseVariant("כל הכבוד", MatchType.exact),
            PhraseVariant("כל הכבוד לך", MatchType.inflectional_variant,
                          note="'All the honor to you' — addressing a specific person."),
        ),
        tags=("praise", "encouragement", "neutral", "honor", "culture"),
    ),

    "he_mazal_tov": PhraseFamily(
        id="he_mazal_tov",
        language="he",
        canonical_form="מזל טוב",
        meaning="Congratulations; good luck (literally: good fortune/star).",
        register="neutral",
        origin=(
            "מזל (mazal — luck, fortune, constellation) + טוב (tov — good). "
            "מזל originally referred to the zodiac sign under which one was born — "
            "'good star = good fortune'. Used across all Jewish cultures worldwide "
            "and borrowed into many European languages."
        ),
        why_it_matters=(
            "One of the most internationally recognised Hebrew phrases. "
            "מזל (mazal) reached English via Yiddish (as in 'moxie'). "
            "טוב (tov — good) is among the highest-frequency Hebrew adjectives: "
            "טוב מאוד (very good), לילה טוב (good night). "
            "The construct state מזל טוב (good fortune) vs. definite מזל הטוב "
            "demonstrates the smichut (construct) pattern."
        ),
        variants=(
            PhraseVariant("מזל טוב", MatchType.exact),
        ),
        tags=("congratulations", "celebration", "neutral", "Jewish culture", "A1"),
    ),

    "he_shabbat_shalom": PhraseFamily(
        id="he_shabbat_shalom",
        language="he",
        canonical_form="שבת שלום",
        meaning="A peaceful Sabbath (traditional Friday/Saturday greeting).",
        register="neutral",
        origin=(
            "שבת (shabbat — Sabbath, the day of rest) + שלום (shalom — peace/wholeness/hello). "
            "The Shabbat (Friday sunset to Saturday nightfall) is the central Jewish weekly observance. "
            "The greeting expresses the wish for a meaningful, peaceful day of rest."
        ),
        why_it_matters=(
            "An essential greeting in Israeli life and Jewish culture worldwide. "
            "שלום is from root ש-ל-ם (wholeness/completion) — also yielding שלם (whole/paid), "
            "לשלם (to pay), שלמות (perfection), and ירושלים (Jerusalem — city of peace). "
            "Understanding שלום as 'wholeness' not just 'hello' is a key insight for Hebrew learners."
        ),
        variants=(
            PhraseVariant("שבת שלום", MatchType.exact),
            PhraseVariant("שבת שלום ומבורך", MatchType.inflectional_variant,
                          note="'A peaceful and blessed Sabbath' — more traditional/religious form."),
        ),
        tags=("greeting", "religious", "Jewish culture", "Shabbat", "A1"),
    ),

    "he_lo_norah": PhraseFamily(
        id="he_lo_norah",
        language="he",
        canonical_form="לא נורא",
        meaning="Not terrible; it's okay; never mind; don't worry (understated reassurance or dismissal).",
        register="informal",
        origin=(
            "Literally לא (lo — not) + נורא (nora — terrible/awful/fearful). "
            "נורא comes from root י-ר-א (to fear); the adjective originally meant 'fearful, awe-inspiring' "
            "(cf. נוֹרָא עֲלִילוֹת — awesome in deeds, from Rosh Hashana liturgy). "
            "In Modern Hebrew נורא shifted to 'terrible', and its negation became an understated 'it's fine'."
        ),
        why_it_matters=(
            "An everyday Israeli expression for casual reassurance — a classic litotes (understatement). "
            "נורא itself is highly versatile: as intensifier it means 'very' (נורא טוב — very good); "
            "as adjective it means 'terrible'. This dual modern usage is a key feature of spoken Hebrew. "
            "Learners who know נורא = terrible are initially confused by לא נורא = it's fine."
        ),
        variants=(
            PhraseVariant("לא נורא", MatchType.exact),
            PhraseVariant("לא נורא בכלל", MatchType.inflectional_variant,
                          note="'Not terrible at all' — stronger reassurance."),
        ),
        tags=("reassurance", "informal", "colloquial", "litotes", "A2"),
    ),

    "he_yihyeh_beseder": PhraseFamily(
        id="he_yihyeh_beseder",
        language="he",
        canonical_form="יהיה בסדר",
        meaning="It will be okay; everything will work out; don't worry.",
        register="informal",
        origin=(
            "יהיה (yihyeh — it will be, future of להיות) + בסדר (b'seder — in order, okay). "
            "סדר (seder — order/arrangement) also names the Passover Seder ceremony. "
            "The phrase reflects a distinctly Israeli cultural optimism that things will work out."
        ),
        why_it_matters=(
            "A cornerstone of Israeli communication style. "
            "יהיה is the future of the highly irregular verb להיות (to be): "
            "its conjugation (אהיה / תהיה / יהיה / נהיה / יהיו) is essential grammar. "
            "בסדר is used standalone as 'okay/fine/alright' in many contexts. "
            "Together they form one of the most culturally representative Israeli expressions."
        ),
        variants=(
            PhraseVariant("יהיה בסדר", MatchType.exact),
            PhraseVariant("הכל יהיה בסדר", MatchType.inflectional_variant,
                          note="'Everything will be okay' — more emphatic reassurance."),
        ),
        tags=("optimism", "reassurance", "informal", "colloquial", "A2"),
    ),

    "he_en_breira": PhraseFamily(
        id="he_en_breira",
        language="he",
        canonical_form="אין ברירה",
        meaning="There's no choice; what can you do; we have no option.",
        register="neutral",
        origin=(
            "אין (ayn — there is no/none) + ברירה (breirah — choice/option). "
            "ברירה is from root ב-ר-ר (to sift, to select, to make clear). "
            "The existential אין is the negation of יש (there is). "
            "The phrase expresses resigned acceptance of an unavoidable situation."
        ),
        why_it_matters=(
            "The existential pair יש / אין (there is / there is no) is fundamental Hebrew grammar — "
            "Hebrew uses these words rather than a form of 'to be' for existence. "
            "אין ברירה also carries cultural resonance: stoic acceptance associated with "
            "Israeli pragmatism and the concept of ein breira as historical necessity. "
            "ברירה shares root ב-ר-ר with ברור (clear, obvious) — both about 'sifting out' clarity."
        ),
        variants=(
            PhraseVariant("אין ברירה", MatchType.exact),
            PhraseVariant("אין לי ברירה", MatchType.inflectional_variant,
                          note="'I have no choice' — with personal dative pronoun."),
        ),
        tags=("resignation", "pragmatism", "neutral", "existential", "A2"),
    ),

    "he_davka": PhraseFamily(
        id="he_davka",
        language="he",
        canonical_form="דווקא",
        meaning="Specifically; precisely; out of spite; actually (nuance word without a single English equivalent).",
        register="informal",
        origin=(
            "From Aramaic דַּוְקָא (davqa — precisely, exactly) — entered Hebrew via "
            "the Talmudic/rabbinical tradition. In Modern Hebrew it expanded to express "
            "spite, contrariness, or emphasis: 'I'll do it specifically because you don't want me to'."
        ),
        why_it_matters=(
            "דווקא is famously difficult to translate — it carries at least three senses: "
            "1. Emphasis/specificity: דווקא אתה (YOU specifically, not someone else). "
            "2. Spite/contrariness: אני דווקא הולך (I'm going precisely because you told me not to). "
            "3. Unexpectedness: דווקא הוא צדק (it turned out HE was the one who was right). "
            "Mastering דווקא is considered a milestone in Hebrew fluency and cultural comprehension."
        ),
        variants=(
            PhraseVariant("דווקא", MatchType.exact),
        ),
        tags=("emphasis", "spite", "informal", "cultural", "untranslatable", "B1"),
    ),

    "he_balagan": PhraseFamily(
        id="he_balagan",
        language="he",
        canonical_form="בלגן",
        meaning="Chaos; mess; disorder; a big confused situation.",
        register="informal",
        origin=(
            "Borrowed from Russian балаган (balagan — fairground booth, noisy spectacle), "
            "itself from Persian بالاخانه (bālākhāna — upper room/balcony). "
            "In Hebrew it shifted to mean general chaos/mess, becoming one of the most "
            "common colloquial words in Israeli Hebrew."
        ),
        why_it_matters=(
            "A classic example of a borrowed word fully integrated into Hebrew. "
            "Its Russian origin reflects the large Ashkenazi immigration waves of the 20th century. "
            "בלגן functions as noun (יש פה בלגן — there's a mess here), attributive adjective "
            "(מצב בלגן — a messy situation), and denominative verb (לבלגן — to make a mess). "
            "Understanding borrowed words helps learners recognise Hebrew's multilingual layers."
        ),
        variants=(
            PhraseVariant("בלגן", MatchType.exact),
            PhraseVariant("בלגן גדול", MatchType.inflectional_variant,
                          note="'Big chaos' — a very common collocation."),
        ),
        tags=("chaos", "informal", "colloquial", "borrowed", "Russian", "A2"),
    ),

    "he_sababa": PhraseFamily(
        id="he_sababa",
        language="he",
        canonical_form="סבבה",
        meaning="All good; cool; great; fine (informal approval or positive response).",
        register="informal",
        origin=(
            "Borrowed from Arabic سبابة (sabbāba — index finger) via the colloquial expression "
            "كله سبابة (everything's index finger = everything's pointing up = everything's fine). "
            "In Israeli slang it became a general positive response, especially in youth speech."
        ),
        why_it_matters=(
            "An essential Israeli slang term borrowed from Arabic — illustrating the "
            "Arabic-Hebrew cultural and linguistic interchange in Israeli society. "
            "Like English 'cool', it functions as a multi-purpose positive response. "
            "Learners of colloquial Israeli Hebrew encounter it immediately in informal speech "
            "and text messages. Its Arabic origin points to a wider set of Arabic loanwords in Hebrew."
        ),
        variants=(
            PhraseVariant("סבבה", MatchType.exact),
            PhraseVariant("סבבה גמור", MatchType.inflectional_variant,
                          note="'Completely fine/great' — with intensifier גמור (total/complete)."),
        ),
        tags=("approval", "informal", "slang", "borrowed", "Arabic", "A2"),
    ),

    "he_chaval_al_hazman": PhraseFamily(
        id="he_chaval_al_hazman",
        language="he",
        canonical_form="חבל על הזמן",
        meaning="Amazing/incredible (slang) — literally 'a pity about the time'; has undergone ironic reversal.",
        register="informal",
        origin=(
            "Literally חבל (chaval — a pity/shame) + על (al — about) + הזמן (ha-zman — the time). "
            "'A pity about the time' was originally used negatively. In Modern Israeli slang "
            "it underwent ironic reversal — so amazing it's a pity to experience only once. "
            "Both sincere and sarcastic uses are common."
        ),
        why_it_matters=(
            "A classic example of semantic reversal in Israeli slang — like 'sick' or 'wicked' "
            "in English youth speech. Understanding that חבל על הזמן can mean 'incredible' "
            "is essential for comprehending native speech. "
            "חבל (pity) also appears in חבל שלא (it's a shame that not) and חבל על הכסף "
            "(not worth the money). The homonym חֶבֶל (rope/cord) can confuse learners."
        ),
        variants=(
            PhraseVariant("חבל על הזמן", MatchType.exact),
            PhraseVariant("חבל על הזמן שלא", MatchType.inflectional_variant,
                          note="'It's a shame that not…' — original negative sense."),
        ),
        tags=("amazement", "irony", "informal", "slang", "semantic-reversal", "B1"),
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
