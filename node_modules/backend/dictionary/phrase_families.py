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
    # ── De (generated) ────────────────────────────────────────

    "de_den_spiess_umdrehen": PhraseFamily(
        id="de_den_spiess_umdrehen",
        language="de",
        canonical_form="den Spieß umdrehen",
        meaning="To turn the tables; to reverse the argument against one's opponent.",
        register="neutral",
        origin=(
            "Spieß (spear or spit): reversing the pointed weapon so it faces the "
            "attacker. Military imagery applied to argumentation. Attested in German "
            "since the early modern period."
        ),
        variants=(
            PhraseVariant(
                surface="den Spieß umdrehen",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="den Spieß umkehren",
                match_type=MatchType.inflectional_variant,
                note="Variant with 'umkehren' (to reverse) instead of 'umdrehen'.",
            ),
            PhraseVariant(
                surface="er hat den Spieß umgedreht",
                match_type=MatchType.inflectional_variant,
                note="He turned the tables — past tense.",
            ),
        ),
    ),

    "de_einen_korb_geben": PhraseFamily(
        id="de_einen_korb_geben",
        language="de",
        canonical_form="jemandem einen Korb geben",
        meaning="To reject someone; to turn someone down romantically.",
        register="neutral",
        origin=(
            "Medieval legend: a woman lowering a suitor in a basket (Korb) through a "
            "window, then leaving him dangling — giving him the basket (rejection). "
            "The image entered German as a standard expression for romantic refusal."
        ),
        why_it_matters=(
            "One of the most common German expressions for rejection. Understanding "
            "the basket image makes the phrase memorable."
        ),
        variants=(
            PhraseVariant(
                surface="jemandem einen Korb geben",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="einen Korb bekommen",
                match_type=MatchType.inflectional_variant,
                note="To get the basket — to be rejected (passive perspective).",
            ),
            PhraseVariant(
                surface="sie hat ihm einen Korb gegeben",
                match_type=MatchType.inflectional_variant,
                note="She turned him down — past tense.",
            ),
        ),
    ),

    "de_das_handtuch_werfen": PhraseFamily(
        id="de_das_handtuch_werfen",
        language="de",
        canonical_form="das Handtuch werfen",
        meaning="To throw in the towel; to give up.",
        register="neutral",
        origin=(
            "From boxing: a trainer throwing a towel into the ring concedes the "
            "match. Borrowed directly from English boxing culture into German, "
            "retaining the same image."
        ),
        variants=(
            PhraseVariant(
                surface="das Handtuch werfen",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="er hat das Handtuch geworfen",
                match_type=MatchType.inflectional_variant,
                note="He threw in the towel — past tense.",
            ),
            PhraseVariant(
                surface="das Handtuch schmeißen",
                match_type=MatchType.inflectional_variant,
                note="Colloquial variant with 'schmeißen' (to chuck).",
            ),
        ),
    ),

    "de_ins_fettnaepfchen_treten": PhraseFamily(
        id="de_ins_fettnaepfchen_treten",
        language="de",
        canonical_form="ins Fettnäpfchen treten",
        meaning="To put one's foot in it; to make an embarrassing blunder.",
        register="neutral",
        origin=(
            "Fettnäpfchen (small grease dish): small pots of grease were placed near "
            "doors or under chairs for polishing boots. Stepping into one was a "
            "social embarrassment — the word stuck as a metaphor for unintentional "
            "offense."
        ),
        why_it_matters=(
            "A quintessentially German idiom with no clean English parallel. The "
            "Fettnäpfchen image is opaque and impossible to guess — a learner who "
            "knows it has unlocked genuine cultural vocabulary."
        ),
        variants=(
            PhraseVariant(
                surface="ins Fettnäpfchen treten",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="er ist ins Fettnäpfchen getreten",
                match_type=MatchType.inflectional_variant,
                note="He put his foot in it — past tense.",
            ),
        ),
    ),

    "de_blau_machen": PhraseFamily(
        id="de_blau_machen",
        language="de",
        canonical_form="blaumachen",
        meaning="To skip work; to play hooky; to take an unauthorized day off.",
        register="informal",
        origin=(
            "Possibly from woad dyeing (Blaufärben), where cloth soaked in blue dye "
            "had to rest — workers could take the day off while the vat sat idle. "
            "Alternatively, from Blue Monday (Saint Monday), the tradition of taking "
            "Mondays off."
        ),
        variants=(
            PhraseVariant(
                surface="blaumachen",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="blau machen",
                match_type=MatchType.orthographic_variant,
                note="Written as two words — both spellings are common.",
            ),
            PhraseVariant(
                surface="er macht heute blau",
                match_type=MatchType.inflectional_variant,
                note="He's taking the day off — present tense.",
            ),
        ),
    ),

    "de_seinen_senf_dazugeben": PhraseFamily(
        id="de_seinen_senf_dazugeben",
        language="de",
        canonical_form="seinen Senf dazugeben",
        meaning="To give one's two cents; to add an unsolicited opinion.",
        register="informal",
        origin=(
            "Mustard (Senf) was a pungent, widely used condiment that was added to "
            "food even when unwanted. 'Adding your mustard' to a conversation "
            "suggests imposing a strong-flavored opinion where it wasn't sought."
        ),
        variants=(
            PhraseVariant(
                surface="seinen Senf dazugeben",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="seinen Senf hinzufügen",
                match_type=MatchType.inflectional_variant,
                note="To add one's mustard — slightly more formal verb.",
            ),
            PhraseVariant(
                surface="muss er immer seinen Senf dazugeben",
                match_type=MatchType.inflectional_variant,
                note="He always has to put his two cents in.",
            ),
        ),
    ),

    "de_tomaten_auf_den_augen": PhraseFamily(
        id="de_tomaten_auf_den_augen",
        language="de",
        canonical_form="Tomaten auf den Augen haben",
        meaning="To be blind to what's obvious; to not see what's right in front of one.",
        register="informal",
        origin=(
            "Tomatoes (Tomaten) on the eyes — large round objects blocking the view. "
            "A comic image emphasizing willful or oblivious blindness. More colorful "
            "than the English 'scales on one's eyes.'"
        ),
        why_it_matters=(
            "Strikingly visual and playful. Unique to German among major European "
            "languages. Learning it builds awareness of German's penchant for "
            "vegetable-based idiom."
        ),
        variants=(
            PhraseVariant(
                surface="Tomaten auf den Augen haben",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="du hast wohl Tomaten auf den Augen",
                match_type=MatchType.inflectional_variant,
                note="You must have tomatoes on your eyes — direct address, exasperated.",
            ),
        ),
    ),

    "de_um_den_heissen_brei": PhraseFamily(
        id="de_um_den_heissen_brei",
        language="de",
        canonical_form="um den heißen Brei herumreden",
        meaning="To beat around the hot porridge; to avoid the subject.",
        register="neutral",
        origin=(
            "Hot porridge (heißer Brei) cannot be eaten immediately — one circles "
            "around it, blowing on it, waiting. The image of circling without "
            "committing is used for evasive speech. Compare French 'tourner autour du "
            "pot'."
        ),
        variants=(
            PhraseVariant(
                surface="um den heißen Brei herumreden",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="um den heißen Brei herumgehen",
                match_type=MatchType.inflectional_variant,
                note="To walk around the hot porridge — motion variant.",
            ),
            PhraseVariant(
                surface="rede nicht um den heißen Brei herum",
                match_type=MatchType.inflectional_variant,
                note="Don't beat around the bush — imperative.",
            ),
        ),
    ),

    "de_durch_dick_und_dunn": PhraseFamily(
        id="de_durch_dick_und_dunn",
        language="de",
        canonical_form="durch dick und dünn",
        meaning="Through thick and thin; in good times and bad.",
        register="neutral",
        origin=(
            "Thick (dick) and thin (dünn) referred to thick and thin forest terrain — "
            "alternating dense thicket and open paths. Through both kinds of terrain "
            "suggests loyalty regardless of conditions. Parallel to English 'through "
            "thick and thin.'"
        ),
        variants=(
            PhraseVariant(
                surface="durch dick und dünn",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="durch dick und dünn gehen",
                match_type=MatchType.inflectional_variant,
                note="To go through thick and thin — with verb.",
            ),
        ),
    ),

    "de_das_fuenfte_rad_am_wagen": PhraseFamily(
        id="de_das_fuenfte_rad_am_wagen",
        language="de",
        canonical_form="das fünfte Rad am Wagen",
        meaning="The fifth wheel; an unnecessary person.",
        register="neutral",
        origin=(
            "A wagon needs four wheels — a fifth is purely superfluous. The "
            "expression captures the feeling of being unwanted or redundant in a "
            "group. Found in early modern German. The English 'fifth wheel' shares "
            "the same image."
        ),
        variants=(
            PhraseVariant(
                surface="das fünfte Rad am Wagen",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="das fünfte Rad am Wagen sein",
                match_type=MatchType.inflectional_variant,
                note="To be the fifth wheel — with sein (to be).",
            ),
            PhraseVariant(
                surface="er ist das fünfte Rad am Wagen",
                match_type=MatchType.inflectional_variant,
                note="He's the odd one out.",
            ),
        ),
    ),

    "de_hinter_dem_mond": PhraseFamily(
        id="de_hinter_dem_mond",
        language="de",
        canonical_form="hinter dem Mond leben",
        meaning="To live behind the moon; to be out of touch with reality.",
        register="informal",
        origin=(
            "The moon's far side (the dark side) was invisible — living there means "
            "existing beyond what the world can see or know. A person 'behind the "
            "moon' is ignorant of current events and modern life."
        ),
        variants=(
            PhraseVariant(
                surface="hinter dem Mond leben",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="du lebst wohl hinter dem Mond",
                match_type=MatchType.inflectional_variant,
                note="You must be living on the moon — direct address.",
            ),
            PhraseVariant(
                surface="hinterm Mond leben",
                match_type=MatchType.inflectional_variant,
                note="Colloquial contraction with 'hinterm'.",
            ),
        ),
    ),

    "de_wie_aus_der_pistole": PhraseFamily(
        id="de_wie_aus_der_pistole",
        language="de",
        canonical_form="wie aus der Pistole geschossen",
        meaning="Like a shot from a pistol; immediately; instantaneously.",
        register="neutral",
        origin=(
            "The speed of a bullet fired from a pistol: as fast as possible. Used to "
            "describe instant responses, especially verbal ones. 'Er antwortete wie "
            "aus der Pistole geschossen' — he answered without a moment's hesitation."
        ),
        variants=(
            PhraseVariant(
                surface="wie aus der Pistole geschossen",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="er antwortete wie aus der Pistole geschossen",
                match_type=MatchType.inflectional_variant,
                note="He answered like a shot.",
            ),
        ),
    ),

    "de_auf_der_kippe_stehen": PhraseFamily(
        id="de_auf_der_kippe_stehen",
        language="de",
        canonical_form="auf der Kippe stehen",
        meaning="To hang in the balance; to be on the verge; to be uncertain.",
        register="neutral",
        origin=(
            "Kippe can mean a tipping point, a see-saw, or the edge of a surface. "
            "Something balanced on the Kippe can fall either way — an apt metaphor "
            "for an undecided situation."
        ),
        variants=(
            PhraseVariant(
                surface="auf der Kippe stehen",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="es steht auf der Kippe",
                match_type=MatchType.inflectional_variant,
                note="It's hanging in the balance.",
            ),
            PhraseVariant(
                surface="auf Kante stehen",
                match_type=MatchType.inflectional_variant,
                note="Variant using Kante (edge) — same meaning.",
            ),
        ),
    ),

    "de_die_katze_im_sack": PhraseFamily(
        id="de_die_katze_im_sack",
        language="de",
        canonical_form="die Katze im Sack kaufen",
        meaning="To buy a pig in a poke; to buy something without examining it first.",
        register="neutral",
        origin=(
            "Medieval market fraud: merchants sold a (presumably valuable) cat in a "
            "bag instead of the promised pig. Letting the cat out of the bag (den "
            "Braten riechen) revealed the trick. Compare English 'pig in a poke' and "
            "French 'acheter chat en poche.'"
        ),
        variants=(
            PhraseVariant(
                surface="die Katze im Sack kaufen",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="eine Katze im Sack kaufen",
                match_type=MatchType.inflectional_variant,
                note="Indefinite article variant — slightly more generic.",
            ),
        ),
    ),

    "de_einen_zahn_zulegen": PhraseFamily(
        id="de_einen_zahn_zulegen",
        language="de",
        canonical_form="einen Zahn zulegen",
        meaning="To step on the gas; to speed up; to increase effort.",
        register="informal",
        origin=(
            "Zahn (tooth) as slang for speed — possibly from cycling, where adding a "
            "gear (Zahn = tooth on a cog) means pedaling faster. The image is "
            "mechanical: adding a cog increases velocity."
        ),
        variants=(
            PhraseVariant(
                surface="einen Zahn zulegen",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="leg mal einen Zahn zu",
                match_type=MatchType.inflectional_variant,
                note="Speed it up — imperative.",
            ),
            PhraseVariant(
                surface="noch einen Zahn zulegen",
                match_type=MatchType.inflectional_variant,
                note="To step it up a notch further.",
            ),
        ),
    ),

    "de_zwei_fliegen_mit_einer_klappe": PhraseFamily(
        id="de_zwei_fliegen_mit_einer_klappe",
        language="de",
        canonical_form="zwei Fliegen mit einer Klappe schlagen",
        meaning="To kill two birds with one stone.",
        register="neutral",
        origin=(
            "Klappe (flap, shutter) rather than stone: German uses a fly swatter or "
            "door flap hitting two flies. The same concept as English but with an "
            "indoor domestic image. Also attested in Dutch and other Germanic "
            "languages."
        ),
        variants=(
            PhraseVariant(
                surface="zwei Fliegen mit einer Klappe schlagen",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="zwei Fliegen mit einer Klappe",
                match_type=MatchType.inflectional_variant,
                note="Elliptical — the verb often dropped in parenthetical use.",
            ),
        ),
    ),

    "de_alle_ueber_einen_kamm": PhraseFamily(
        id="de_alle_ueber_einen_kamm",
        language="de",
        canonical_form="alle über einen Kamm scheren",
        meaning=(
            "To tar everyone with the same brush; to treat everyone identically"
            "without distinction."
        ),
        register="neutral",
        origin=(
            "Scheren (to shear, to comb) + Kamm (comb): running one comb over "
            "everyone flattens all differences. The shearing image evokes sheep — "
            "treating people as undifferentiated flock."
        ),
        variants=(
            PhraseVariant(
                surface="alle über einen Kamm scheren",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="alle über einen Kamm",
                match_type=MatchType.inflectional_variant,
                note="Elliptical — verb dropped in informal use.",
            ),
            PhraseVariant(
                surface="man kann nicht alle über einen Kamm scheren",
                match_type=MatchType.inflectional_variant,
                note="You can't treat everyone the same — negated form.",
            ),
        ),
    ),

    "de_ins_wasser_fallen": PhraseFamily(
        id="de_ins_wasser_fallen",
        language="de",
        canonical_form="ins Wasser fallen",
        meaning="To fall through; to not happen; to come to nothing.",
        register="neutral",
        origin=(
            "Something that falls into water disappears or is ruined — a plan 'fallen "
            "into water' has dissolved. The aquatic metaphor for failure is common "
            "across Germanic languages."
        ),
        variants=(
            PhraseVariant(
                surface="ins Wasser fallen",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="der Plan ist ins Wasser gefallen",
                match_type=MatchType.inflectional_variant,
                note="The plan fell through — past tense.",
            ),
            PhraseVariant(
                surface="ins Wasser gefallen",
                match_type=MatchType.inflectional_variant,
                note="Fallen through — participial use.",
            ),
        ),
    ),

    "de_die_kuh_vom_eis": PhraseFamily(
        id="de_die_kuh_vom_eis",
        language="de",
        canonical_form="die Kuh vom Eis bringen",
        meaning="To get the cow off the ice; to solve a tricky problem.",
        register="neutral",
        origin=(
            "A cow on ice is in a precarious, almost comic predicament — heavy, "
            "unstable, unable to walk safely. Getting it off requires ingenuity and "
            "care. The image encodes both the difficulty and the urgency of problem- "
            "solving."
        ),
        why_it_matters=(
            "Unique to German. Learners of German often encounter it and find it "
            "initially baffling — a perfect example of opaque cultural metaphor."
        ),
        variants=(
            PhraseVariant(
                surface="die Kuh vom Eis bringen",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="wir müssen die Kuh vom Eis bringen",
                match_type=MatchType.inflectional_variant,
                note="We need to get the cow off the ice — urgent form.",
            ),
            PhraseVariant(
                surface="die Kuh ist vom Eis",
                match_type=MatchType.inflectional_variant,
                note="The cow is off the ice — the problem is solved.",
            ),
        ),
    ),

    "de_mit_kanonen_auf_spatzen": PhraseFamily(
        id="de_mit_kanonen_auf_spatzen",
        language="de",
        canonical_form="mit Kanonen auf Spatzen schießen",
        meaning="To use a sledgehammer to crack a nut; to use disproportionate means.",
        register="neutral",
        origin=(
            "Firing a cannon (Kanone) at sparrows (Spatzen) is absurdly excessive. "
            "The expression critiques the mismatch between powerful means and trivial "
            "ends. Common in business, politics, and everyday critique."
        ),
        variants=(
            PhraseVariant(
                surface="mit Kanonen auf Spatzen schießen",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="mit Kanonen auf Spatzen",
                match_type=MatchType.inflectional_variant,
                note="Elliptical parenthetical.",
            ),
            PhraseVariant(
                surface="das ist mit Kanonen auf Spatzen geschossen",
                match_type=MatchType.inflectional_variant,
                note="That's using a sledgehammer to crack a nut.",
            ),
        ),
    ),

    "de_auf_grossem_fuss": PhraseFamily(
        id="de_auf_grossem_fuss",
        language="de",
        canonical_form="auf großem Fuß leben",
        meaning="To live large; to live extravagantly; to live beyond one's means.",
        register="neutral",
        origin=(
            "In medieval times, long pointed shoe tips (Schnabelschuhe) indicated "
            "social rank — longer tips = higher status. Living on a 'large foot' "
            "referenced the conspicuous luxury of aristocratic footwear."
        ),
        why_it_matters=(
            "Contrast with 'auf gutem Fuß stehen' (to be on good terms with someone) "
            "— same Fuß, different meaning. Distinguishing these builds lexical "
            "precision."
        ),
        variants=(
            PhraseVariant(
                surface="auf großem Fuß leben",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="auf großem Fuße leben",
                match_type=MatchType.orthographic_variant,
                note="With dative -e ending — older, still seen in formal writing.",
            ),
            PhraseVariant(
                surface="er lebt auf großem Fuß",
                match_type=MatchType.inflectional_variant,
                note="He's living large.",
            ),
        ),
    ),

    "de_jemandem_den_daumen_drucken": PhraseFamily(
        id="de_jemandem_den_daumen_drucken",
        language="de",
        canonical_form="jemandem den Daumen drücken",
        meaning="To keep one's fingers crossed for someone; to wish someone luck.",
        register="neutral",
        origin=(
            "In Roman gladiatorial combat, pressing the thumb down (or closing the "
            "fist around it) was a gesture of mercy or good will. The Germanic "
            "tradition adopted the thumb-pressing gesture as a luck charm. Compare "
            "English 'fingers crossed.'"
        ),
        variants=(
            PhraseVariant(
                surface="jemandem den Daumen drücken",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="ich drücke dir den Daumen",
                match_type=MatchType.inflectional_variant,
                note="I'm crossing my fingers for you.",
            ),
            PhraseVariant(
                surface="Daumen drücken",
                match_type=MatchType.inflectional_variant,
                note="Elliptical imperative or standalone expression.",
            ),
        ),
    ),

    "de_das_kind_beim_namen": PhraseFamily(
        id="de_das_kind_beim_namen",
        language="de",
        canonical_form="das Kind beim Namen nennen",
        meaning="To call a spade a spade; to name something clearly and directly.",
        register="neutral",
        origin=(
            "Naming the child (das Kind) by its name — a metaphor for honest, direct "
            "identification of something others might hesitate to name. Attested in "
            "early modern German and parallel to Erasmian humanist rhetoric about "
            "plain speech."
        ),
        variants=(
            PhraseVariant(
                surface="das Kind beim Namen nennen",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="das Kind beim richtigen Namen nennen",
                match_type=MatchType.inflectional_variant,
                note="Call the child by its right name — with emphasis on 'right'.",
            ),
        ),
    ),

    "de_auf_dem_sprung": PhraseFamily(
        id="de_auf_dem_sprung",
        language="de",
        canonical_form="auf dem Sprung sein",
        meaning="To be on the go; to be about to leave; to be in a hurry.",
        register="neutral",
        origin=(
            "Sprung (jump, leap) — being on the verge of jumping suggests imminent "
            "motion. The expression captures a moment of readiness before departure, "
            "widely used in casual German."
        ),
        variants=(
            PhraseVariant(
                surface="auf dem Sprung sein",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="ich bin auf dem Sprung",
                match_type=MatchType.inflectional_variant,
                note="I'm just on my way out.",
            ),
            PhraseVariant(
                surface="er ist auf dem Sprung",
                match_type=MatchType.inflectional_variant,
                note="He's about to leave.",
            ),
        ),
    ),

    "de_keinen_finger_krumm_machen": PhraseFamily(
        id="de_keinen_finger_krumm_machen",
        language="de",
        canonical_form="keinen Finger krumm machen",
        meaning="Not to lift a finger; to make no effort whatsoever.",
        register="informal",
        origin=(
            "Making a finger crooked (krumm machen) is the smallest possible physical "
            "movement. Refusing even that gesture emphasizes total passivity. The "
            "negation 'keinen' + minimal action = maximal laziness."
        ),
        variants=(
            PhraseVariant(
                surface="keinen Finger krumm machen",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="er macht keinen Finger krumm",
                match_type=MatchType.inflectional_variant,
                note="He won't lift a finger.",
            ),
        ),
    ),

    "de_die_flinte_ins_korn_werfen": PhraseFamily(
        id="de_die_flinte_ins_korn_werfen",
        language="de",
        canonical_form="die Flinte ins Korn werfen",
        meaning="To give up; to throw in the towel; to abandon one's efforts.",
        register="neutral",
        origin=(
            "Flinte (musket, rifle) + Korn (grain field): a soldier who throws their "
            "weapon into a grain field has surrendered or deserted. The battlefield "
            "image evokes hopeless retreat. More vivid than English 'throw in the "
            "towel.'"
        ),
        variants=(
            PhraseVariant(
                surface="die Flinte ins Korn werfen",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="er hat die Flinte ins Korn geworfen",
                match_type=MatchType.inflectional_variant,
                note="He's given up — past tense.",
            ),
            PhraseVariant(
                surface="wirf nicht gleich die Flinte ins Korn",
                match_type=MatchType.inflectional_variant,
                note="Don't give up so quickly — imperative.",
            ),
        ),
    ),

    "de_jemanden_auf_dem_kieker": PhraseFamily(
        id="de_jemanden_auf_dem_kieker",
        language="de",
        canonical_form="jemanden auf dem Kieker haben",
        meaning=(
            "To have someone in one's sights; to be watching someone closely with"
            "suspicion."
        ),
        register="informal",
        origin=(
            "Kieker (telescope, binoculars) from maritime and military use. 'Having "
            "someone through the telescope' means tracking them closely. The "
            "expression implies sustained surveillance and mild hostility."
        ),
        variants=(
            PhraseVariant(
                surface="jemanden auf dem Kieker haben",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="er hat mich auf dem Kieker",
                match_type=MatchType.inflectional_variant,
                note="He's got me in his sights.",
            ),
        ),
    ),

    "de_sich_in_die_nesseln_setzen": PhraseFamily(
        id="de_sich_in_die_nesseln_setzen",
        language="de",
        canonical_form="sich in die Nesseln setzen",
        meaning="To get oneself into a mess; to land oneself in trouble.",
        register="informal",
        origin=(
            "Nesseln (stinging nettles): sitting down in a nettle patch causes "
            "immediate, painful consequences. A visceral image for the result of "
            "reckless action. Common in Austrian and South German usage."
        ),
        variants=(
            PhraseVariant(
                surface="sich in die Nesseln setzen",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="er hat sich in die Nesseln gesetzt",
                match_type=MatchType.inflectional_variant,
                note="He got himself into trouble.",
            ),
        ),
    ),

    "de_den_braten_riechen": PhraseFamily(
        id="de_den_braten_riechen",
        language="de",
        canonical_form="den Braten riechen",
        meaning="To smell a rat; to sense that something is not right.",
        register="neutral",
        origin=(
            "Braten (roast meat): the smell of something cooking alerts you to what "
            "is happening before you see it. 'Smelling the roast' = detecting a "
            "situation before it is revealed. Related to the 'cat in the bag' cluster "
            "of medieval marketplace fraud idioms."
        ),
        variants=(
            PhraseVariant(
                surface="den Braten riechen",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="ich habe den Braten gerochen",
                match_type=MatchType.inflectional_variant,
                note="I smelled a rat — past tense.",
            ),
            PhraseVariant(
                surface="er hat den Braten schnell gerochen",
                match_type=MatchType.inflectional_variant,
                note="He caught on quickly.",
            ),
        ),
    ),

    "de_eine_lanze_brechen": PhraseFamily(
        id="de_eine_lanze_brechen",
        language="de",
        canonical_form="eine Lanze für jemanden brechen",
        meaning=(
            "To go to bat for someone; to stand up for someone; to make a case on"
            "their behalf."
        ),
        register="neutral",
        origin=(
            "Medieval jousting: breaking a lance in tournament combat for someone's "
            "honor was an act of personal advocacy and loyalty. The expression "
            "retains the chivalric register of active, public defense of another."
        ),
        variants=(
            PhraseVariant(
                surface="eine Lanze für jemanden brechen",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="eine Lanze für ihn brechen",
                match_type=MatchType.inflectional_variant,
                note="Go to bat for him — with pronoun.",
            ),
            PhraseVariant(
                surface="er brach eine Lanze für sie",
                match_type=MatchType.inflectional_variant,
                note="He stood up for her — past tense.",
            ),
        ),
    ),

    "de_mit_haut_und_haaren": PhraseFamily(
        id="de_mit_haut_und_haaren",
        language="de",
        canonical_form="mit Haut und Haaren",
        meaning="Hook, line, and sinker; completely; lock, stock, and barrel.",
        register="neutral",
        origin=(
            "Skin (Haut) and hair (Haare) represent the whole person — external "
            "covering included. 'With skin and hair' = entirely, without leaving "
            "anything behind. Used of both consuming something completely and being "
            "completely ensnared."
        ),
        variants=(
            PhraseVariant(
                surface="mit Haut und Haaren",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="er hat es mit Haut und Haaren geglaubt",
                match_type=MatchType.inflectional_variant,
                note="He swallowed it hook, line, and sinker.",
            ),
            PhraseVariant(
                surface="sie ist mit Haut und Haaren verliebt",
                match_type=MatchType.inflectional_variant,
                note="She's head over heels in love.",
            ),
        ),
    ),

    "de_ueber_den_berg_sein": PhraseFamily(
        id="de_ueber_den_berg_sein",
        language="de",
        canonical_form="über den Berg sein",
        meaning="To be over the worst; to be out of the woods; to have passed the crisis.",
        register="neutral",
        origin=(
            "The mountain (Berg) as an obstacle to be surmounted: once you're over "
            "the peak, the worst of the climb is behind you. Applied to illness, "
            "crisis, and difficulty. Compare English 'over the hill' (though German's "
            "meaning is more positive)."
        ),
        variants=(
            PhraseVariant(
                surface="über den Berg sein",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="er ist über den Berg",
                match_type=MatchType.inflectional_variant,
                note="He's over the worst.",
            ),
            PhraseVariant(
                surface="noch nicht über den Berg",
                match_type=MatchType.inflectional_variant,
                note="Not out of the woods yet.",
            ),
        ),
    ),

    "de_auf_den_leim_gehen": PhraseFamily(
        id="de_auf_den_leim_gehen",
        language="de",
        canonical_form="auf den Leim gehen",
        meaning="To be taken in; to fall for a trick; to be fooled.",
        register="neutral",
        origin=(
            "Leim (glue, birdlime): hunters coated branches with sticky birdlime to "
            "catch birds — they landed and stuck. 'Going onto the glue' = being "
            "trapped by a deception. The image is ancient and appears across European "
            "languages."
        ),
        variants=(
            PhraseVariant(
                surface="auf den Leim gehen",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="er ist auf den Leim gegangen",
                match_type=MatchType.inflectional_variant,
                note="He fell for it — past tense.",
            ),
            PhraseVariant(
                surface="jemandem auf den Leim gehen",
                match_type=MatchType.inflectional_variant,
                note="To be taken in by someone — with dative agent.",
            ),
        ),
    ),

    "de_auf_dem_trockenen_sitzen": PhraseFamily(
        id="de_auf_dem_trockenen_sitzen",
        language="de",
        canonical_form="auf dem Trockenen sitzen",
        meaning="To be stranded; to be in a fix; to have run out of resources.",
        register="neutral",
        origin=(
            "Trockenen (dry land): a fish or boat stranded on dry land cannot move. "
            "The image captures helplessness from lack of the usual medium — a sailor "
            "without water, or a person without money or support."
        ),
        variants=(
            PhraseVariant(
                surface="auf dem Trockenen sitzen",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="auf dem Trocknen sitzen",
                match_type=MatchType.orthographic_variant,
                note="Contracted form without -en, also common.",
            ),
            PhraseVariant(
                surface="er sitzt auf dem Trockenen",
                match_type=MatchType.inflectional_variant,
                note="He's high and dry.",
            ),
        ),
    ),

    # ── Es (generated) ────────────────────────────────────────

    "es_a_buenas_horas": PhraseFamily(
        id="es_a_buenas_horas",
        language="es",
        canonical_form="a buenas horas mangas verdes",
        meaning=(
            "Too little, too late. Help or action that comes when it is no longer"
            "useful."
        ),
        register="informal",
        origin=(
            "Historical reference to the Holy Brotherhood (Santa Hermandad), rural "
            "police who arrived too late to prevent crimes. Their green sleeves "
            "(mangas verdes) became a symbol of belated intervention."
        ),
        why_it_matters=(
            "Used ironically when help or a solution arrives after the problem has "
            "passed."
        ),
        variants=(
            PhraseVariant(
                surface="a buenas horas mangas verdes",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="ya a buenas horas",
                match_type=MatchType.allusion,
                note="Shortened form omitting mangas verdes.",
            ),
        ),
    ),

    "es_a_quien_madruga": PhraseFamily(
        id="es_a_quien_madruga",
        language="es",
        canonical_form="a quien madruga dios le ayuda",
        meaning="The early bird catches the worm. God helps those who rise early.",
        register="neutral",
        origin=(
            "Spanish proverb attested since the medieval period. Reflects the "
            "agricultural value of rising at dawn."
        ),
        variants=(
            PhraseVariant(
                surface="a quien madruga dios le ayuda",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="el que madruga dios le ayuda",
                match_type=MatchType.orthographic_variant,
                note="Alternative pronoun form.",
            ),
        ),
    ),

    "es_al_pan_pan": PhraseFamily(
        id="es_al_pan_pan",
        language="es",
        canonical_form="al pan pan y al vino vino",
        meaning="Call a spade a spade. Speak plainly and directly.",
        register="neutral",
        origin=(
            "Ancient proverb found in Cervantes and earlier sources. The parallelism "
            "(bread is bread, wine is wine) insists on calling things by their true "
            "name."
        ),
        variants=(
            PhraseVariant(
                surface="al pan pan y al vino vino",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="llamar al pan pan y al vino vino",
                match_type=MatchType.inflectional_variant,
                note="With explicit verb llamar.",
            ),
        ),
    ),

    "es_buscar_tres_pies": PhraseFamily(
        id="es_buscar_tres_pies",
        language="es",
        canonical_form="buscar tres pies al gato",
        meaning="Look for trouble; overcomplicate something that is simple.",
        register="informal",
        origin=(
            "A cat has four paws; looking for only three means ignoring reality and "
            "creating unnecessary difficulty."
        ),
        why_it_matters=(
            "Used as a warning not to overthink or complicate straightforward "
            "matters."
        ),
        variants=(
            PhraseVariant(
                surface="buscar tres pies al gato",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="buscarle tres pies al gato",
                match_type=MatchType.inflectional_variant,
                note="With clitic le (dative).",
            ),
        ),
    ),

    "es_caer_chuzos": PhraseFamily(
        id="es_caer_chuzos",
        language="es",
        canonical_form="caer chuzos de punta",
        meaning="Rain cats and dogs; pour down heavily.",
        register="informal",
        origin=(
            "Chuzo is a pointed pike or spike. Raining pointed spikes emphasizes the "
            "violence and intensity of the downpour."
        ),
        variants=(
            PhraseVariant(
                surface="caer chuzos de punta",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="llover chuzos",
                match_type=MatchType.orthographic_variant,
                note="With llover (to rain) instead of caer.",
            ),
        ),
    ),

    "es_coger_el_toro": PhraseFamily(
        id="es_coger_el_toro",
        language="es",
        canonical_form="coger el toro por los cuernos",
        meaning="Take the bull by the horns; deal with a difficult problem head-on.",
        register="neutral",
        variants=(
            PhraseVariant(
                surface="coger el toro por los cuernos",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="agarrar el toro por los cuernos",
                match_type=MatchType.orthographic_variant,
                note="agarrar preferred in Latin America over coger.",
            ),
        ),
    ),

    "es_dar_en_el_clavo": PhraseFamily(
        id="es_dar_en_el_clavo",
        language="es",
        canonical_form="dar en el clavo",
        meaning="Hit the nail on the head; be exactly right.",
        register="neutral",
        origin=(
            "Carpentry metaphor: hitting the nail precisely versus bending it. "
            "Cervantes used it in Don Quijote."
        ),
        variants=(
            PhraseVariant(
                surface="dar en el clavo",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="dar en el clavo con algo",
                match_type=MatchType.inflectional_variant,
                note="With prepositional complement.",
            ),
        ),
    ),

    "es_echar_en_saco_roto": PhraseFamily(
        id="es_echar_en_saco_roto",
        language="es",
        canonical_form="echar en saco roto",
        meaning="In one ear and out the other; pay no attention to advice.",
        register="neutral",
        origin=(
            "A broken sack (saco roto) cannot hold what is put in it — advice or "
            "information poured in leaks straight out."
        ),
        variants=(
            PhraseVariant(
                surface="echar en saco roto",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="caer en saco roto",
                match_type=MatchType.orthographic_variant,
                note="With caer (to fall); same meaning.",
            ),
        ),
    ),

    "es_el_que_rie_ultimo": PhraseFamily(
        id="es_el_que_rie_ultimo",
        language="es",
        canonical_form="el que ríe último ríe mejor",
        meaning="He who laughs last laughs best.",
        register="neutral",
        variants=(
            PhraseVariant(
                surface="el que ríe último ríe mejor",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="quien ríe último ríe mejor",
                match_type=MatchType.orthographic_variant,
                note="quien instead of el que.",
            ),
        ),
    ),

    "es_en_boca_cerrada": PhraseFamily(
        id="es_en_boca_cerrada",
        language="es",
        canonical_form="en boca cerrada no entran moscas",
        meaning="Silence is golden; loose lips sink ships. Keeping quiet avoids trouble.",
        register="neutral",
        origin=(
            "Flies cannot enter a closed mouth — silence prevents unwanted intrusions "
            "and regrettable words."
        ),
        variants=(
            PhraseVariant(
                surface="en boca cerrada no entran moscas",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="boca cerrada no entran moscas",
                match_type=MatchType.orthographic_variant,
                note="Without introductory en.",
            ),
        ),
    ),

    "es_estar_en_las_nubes": PhraseFamily(
        id="es_estar_en_las_nubes",
        language="es",
        canonical_form="estar en las nubes",
        meaning="Have one's head in the clouds; be daydreaming or distracted.",
        register="informal",
        variants=(
            PhraseVariant(
                surface="estar en las nubes",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="andar en las nubes",
                match_type=MatchType.orthographic_variant,
                note="andar instead of estar; implies ongoing state.",
            ),
        ),
    ),

    "es_hacer_de_tripas_corazon": PhraseFamily(
        id="es_hacer_de_tripas_corazon",
        language="es",
        canonical_form="hacer de tripas corazón",
        meaning="Put on a brave face; summon courage despite fear or difficulty.",
        register="informal",
        origin=(
            "Transform intestines (tripas, associated with fear and nausea) into a "
            "heart (corazón, associated with courage). Making bravery out of fear."
        ),
        variants=(
            PhraseVariant(
                surface="hacer de tripas corazón",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "es_hablar_por_los_codos": PhraseFamily(
        id="es_hablar_por_los_codos",
        language="es",
        canonical_form="hablar por los codos",
        meaning="Talk an ear off; be a chatterbox; talk excessively.",
        register="informal",
        origin=(
            "Speaking through one's elbows (codos) implies uncontrolled, overflowing "
            "speech that comes from every part of the body."
        ),
        variants=(
            PhraseVariant(
                surface="hablar por los codos",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="habla por los codos",
                match_type=MatchType.inflectional_variant,
                note="Third-person present indicative.",
            ),
        ),
    ),

    "es_ir_al_grano": PhraseFamily(
        id="es_ir_al_grano",
        language="es",
        canonical_form="ir al grano",
        meaning="Get to the point; cut to the chase.",
        register="neutral",
        origin=(
            "Grain (grano) is the essential part of wheat after the husk is removed. "
            "Going to the grain means getting to the essential matter."
        ),
        variants=(
            PhraseVariant(
                surface="ir al grano",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="vamos al grano",
                match_type=MatchType.inflectional_variant,
                note="Let's get to the point (first person plural).",
            ),
        ),
    ),

    "es_la_gota_que_colma": PhraseFamily(
        id="es_la_gota_que_colma",
        language="es",
        canonical_form="la gota que colmó el vaso",
        meaning=(
            "The straw that broke the camel's back; the final thing that made a bad"
            "situation unbearable."
        ),
        register="neutral",
        origin=(
            "A drop that overflows a full glass. The vessel was already full; any "
            "additional drop causes overflow."
        ),
        variants=(
            PhraseVariant(
                surface="la gota que colmó el vaso",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="la gota que derramó el vaso",
                match_type=MatchType.orthographic_variant,
                note="With derramar (to spill) instead of colmar.",
            ),
            PhraseVariant(
                surface="la última gota",
                match_type=MatchType.allusion,
                note="Shortened allusion.",
            ),
        ),
    ),

    "es_no_hay_dos_sin_tres": PhraseFamily(
        id="es_no_hay_dos_sin_tres",
        language="es",
        canonical_form="no hay dos sin tres",
        meaning="Things come in threes; bad luck or events tend to happen three times.",
        register="neutral",
        variants=(
            PhraseVariant(
                surface="no hay dos sin tres",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "es_pagar_los_platos_rotos": PhraseFamily(
        id="es_pagar_los_platos_rotos",
        language="es",
        canonical_form="pagar los platos rotos",
        meaning="Take the blame; be the scapegoat; pay for someone else's mistakes.",
        register="informal",
        origin=(
            "Paying for broken plates even when you did not break them — suffering "
            "the consequences of others' actions."
        ),
        variants=(
            PhraseVariant(
                surface="pagar los platos rotos",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="pagar el pato",
                match_type=MatchType.allusion,
                note="Separate but related idiom also meaning to take the blame.",
            ),
        ),
    ),

    "es_perder_los_papeles": PhraseFamily(
        id="es_perder_los_papeles",
        language="es",
        canonical_form="perder los papeles",
        meaning="Lose one's cool; lose self-control; go off the rails.",
        register="informal",
        origin=(
            "Losing one's papers (documents) means losing one's identity or "
            "credentials. Metaphorically, losing control of oneself."
        ),
        variants=(
            PhraseVariant(
                surface="perder los papeles",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="se le fueron los papeles",
                match_type=MatchType.inflectional_variant,
                note="Third person — he/she lost it.",
            ),
        ),
    ),

    "es_poner_los_puntos": PhraseFamily(
        id="es_poner_los_puntos",
        language="es",
        canonical_form="poner los puntos sobre las íes",
        meaning="Dot the i's and cross the t's; be precise and leave nothing to chance.",
        register="neutral",
        variants=(
            PhraseVariant(
                surface="poner los puntos sobre las íes",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="poner los puntos sobre las ies",
                match_type=MatchType.orthographic_variant,
                note="Without accent on í.",
            ),
        ),
    ),

    "es_querer_es_poder": PhraseFamily(
        id="es_querer_es_poder",
        language="es",
        canonical_form="querer es poder",
        meaning="Where there is a will there is a way.",
        register="neutral",
        variants=(
            PhraseVariant(
                surface="querer es poder",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "es_salir_el_tiro": PhraseFamily(
        id="es_salir_el_tiro",
        language="es",
        canonical_form="salir el tiro por la culata",
        meaning="Backfire; have the opposite of the intended effect.",
        register="informal",
        origin=(
            "A gun that fires backward through the stock (culata) instead of forward "
            "harms the shooter. Plans that backfire follow the same logic."
        ),
        variants=(
            PhraseVariant(
                surface="salir el tiro por la culata",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="le salió el tiro por la culata",
                match_type=MatchType.inflectional_variant,
                note="Third person — it backfired on him/her.",
            ),
        ),
    ),

    "es_ser_una_y_carne": PhraseFamily(
        id="es_ser_una_y_carne",
        language="es",
        canonical_form="ser uña y carne",
        meaning="Be thick as thieves; be inseparable.",
        register="informal",
        origin=(
            "Nail (uña) and flesh (carne) are so close they cannot be separated "
            "without pain."
        ),
        variants=(
            PhraseVariant(
                surface="ser uña y carne",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="son uña y carne",
                match_type=MatchType.inflectional_variant,
                note="Third person plural.",
            ),
        ),
    ),

    "es_tener_la_sarten": PhraseFamily(
        id="es_tener_la_sarten",
        language="es",
        canonical_form="tener la sartén por el mango",
        meaning="Hold the reins; call the shots; be the one in control.",
        register="informal",
        origin=(
            "Holding the handle (mango) of a frying pan (sartén) gives control over "
            "its direction. Whoever holds the handle decides where it goes."
        ),
        variants=(
            PhraseVariant(
                surface="tener la sartén por el mango",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="llevar la sartén por el mango",
                match_type=MatchType.orthographic_variant,
                note="llevar (to carry) instead of tener.",
            ),
        ),
    ),

    "es_tirar_la_toalla": PhraseFamily(
        id="es_tirar_la_toalla",
        language="es",
        canonical_form="tirar la toalla",
        meaning="Throw in the towel; give up; admit defeat.",
        register="neutral",
        origin=(
            "Boxing term: a trainer throws a towel into the ring to stop a fight and "
            "concede defeat."
        ),
        variants=(
            PhraseVariant(
                surface="tirar la toalla",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="arrojar la toalla",
                match_type=MatchType.orthographic_variant,
                note="arrojar (to throw) instead of tirar.",
            ),
        ),
    ),

    "es_tomar_el_pelo": PhraseFamily(
        id="es_tomar_el_pelo",
        language="es",
        canonical_form="tomar el pelo",
        meaning="Pull someone's leg; tease or make fun of someone.",
        register="informal",
        origin=(
            "Taking someone's hair (pelo) is an annoyance and mockery. "
            "Metaphorically, to mess with someone playfully or deceitfully."
        ),
        variants=(
            PhraseVariant(
                surface="tomar el pelo",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="me está tomando el pelo",
                match_type=MatchType.inflectional_variant,
                note="He/she is pulling my leg.",
            ),
        ),
    ),

    "es_ver_los_toros_desde_la_barrera": PhraseFamily(
        id="es_ver_los_toros_desde_la_barrera",
        language="es",
        canonical_form="ver los toros desde la barrera",
        meaning="Watch from the sidelines; stay safe while others take risks.",
        register="neutral",
        origin=(
            "Bullfighting metaphor: watching from behind the protective barrier "
            "(barrera) rather than entering the ring with the bull."
        ),
        variants=(
            PhraseVariant(
                surface="ver los toros desde la barrera",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="ver los toros desde fuera",
                match_type=MatchType.allusion,
                note="Simplified form without barrera.",
            ),
        ),
    ),

    "es_vivir_de_las_rentas": PhraseFamily(
        id="es_vivir_de_las_rentas",
        language="es",
        canonical_form="vivir de las rentas",
        meaning="Live off one's laurels; rely on past achievements without new effort.",
        register="neutral",
        origin=(
            "Living off rental income (rentas) without working — extended "
            "metaphorically to coasting on past successes."
        ),
        variants=(
            PhraseVariant(
                surface="vivir de las rentas",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "es_a_mal_tiempo_buena_cara": PhraseFamily(
        id="es_a_mal_tiempo_buena_cara",
        language="es",
        canonical_form="a mal tiempo buena cara",
        meaning="Keep smiling in adversity; put on a brave face when things go wrong.",
        register="neutral",
        variants=(
            PhraseVariant(
                surface="a mal tiempo buena cara",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="ante el mal tiempo buena cara",
                match_type=MatchType.orthographic_variant,
                note="With ante instead of a.",
            ),
        ),
    ),

    "es_de_mal_en_peor": PhraseFamily(
        id="es_de_mal_en_peor",
        language="es",
        canonical_form="ir de mal en peor",
        meaning="Go from bad to worse; deteriorate steadily.",
        register="neutral",
        variants=(
            PhraseVariant(
                surface="ir de mal en peor",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="de mal en peor",
                match_type=MatchType.allusion,
                note="Shortened form without verb.",
            ),
        ),
    ),

    "es_quedarse_con_las_ganas": PhraseFamily(
        id="es_quedarse_con_las_ganas",
        language="es",
        canonical_form="quedarse con las ganas",
        meaning="Be left wanting; not get what you hoped for.",
        register="informal",
        variants=(
            PhraseVariant(
                surface="quedarse con las ganas",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="me quedé con las ganas",
                match_type=MatchType.inflectional_variant,
                note="First person past — I was left wanting.",
            ),
        ),
    ),

    "es_no_dar_pie_con_bola": PhraseFamily(
        id="es_no_dar_pie_con_bola",
        language="es",
        canonical_form="no dar pie con bola",
        meaning="Not get anything right; mess everything up.",
        register="informal",
        origin=(
            "Football/ball-game metaphor: not even managing to kick (dar pie) the "
            "ball (bola) — missing completely."
        ),
        variants=(
            PhraseVariant(
                surface="no dar pie con bola",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="no doy pie con bola",
                match_type=MatchType.inflectional_variant,
                note="First person — I can't get anything right.",
            ),
        ),
    ),

    "es_echar_balones_fuera": PhraseFamily(
        id="es_echar_balones_fuera",
        language="es",
        canonical_form="echar balones fuera",
        meaning="Dodge the question; avoid responsibility; deflect blame.",
        register="informal",
        origin=(
            "Football term: kicking the ball out of bounds to relieve pressure. "
            "Metaphorically, evading a difficult topic."
        ),
        variants=(
            PhraseVariant(
                surface="echar balones fuera",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "es_poner_el_dedo_en_la_llaga": PhraseFamily(
        id="es_poner_el_dedo_en_la_llaga",
        language="es",
        canonical_form="poner el dedo en la llaga",
        meaning="Put one's finger on the sore spot; touch on a painful truth.",
        register="neutral",
        origin=(
            "Biblical reference to doubting Thomas touching Christ's wounds (llagas). "
            "Pointing to the exact painful or sensitive issue."
        ),
        variants=(
            PhraseVariant(
                surface="poner el dedo en la llaga",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="tocar la llaga",
                match_type=MatchType.allusion,
                note="Shorter form — to touch the wound.",
            ),
        ),
    ),

    "es_a_falta_de_pan": PhraseFamily(
        id="es_a_falta_de_pan",
        language="es",
        canonical_form="a falta de pan buenas son tortas",
        meaning="Beggars can't be choosers; make do with what you have.",
        register="neutral",
        origin=(
            "If there is no bread, corn cakes (tortas) are welcome. Accept what is "
            "available."
        ),
        variants=(
            PhraseVariant(
                surface="a falta de pan buenas son tortas",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="a falta de pan tortas",
                match_type=MatchType.allusion,
                note="Shortened proverb form.",
            ),
        ),
    ),

    # ── Fr (generated) ────────────────────────────────────────

    "fr_cest_du_gateau": PhraseFamily(
        id="fr_cest_du_gateau",
        language="fr",
        canonical_form="c'est du gâteau",
        meaning="It's a piece of cake; it's easy.",
        register="informal",
        origin=(
            "Gâteau (cake) as a metaphor for something pleasurable and easily "
            "obtained dates to 19th-century French slang. Cake requires no effort to "
            "eat, so 'it's cake' came to mean effortless."
        ),
        why_it_matters=(
            "The exact parallel to English 'piece of cake' makes this idiom "
            "accessible, but French uses 'c'est du gâteau' (uncountable) rather than "
            "'un morceau de gâteau'."
        ),
        variants=(
            PhraseVariant(
                surface="c'est du gâteau",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="c'est du gateau",
                match_type=MatchType.orthographic_variant,
                note="Without the circumflex, common in informal digital writing.",
            ),
            PhraseVariant(
                surface="c'est pas du gâteau",
                match_type=MatchType.inflectional_variant,
                note="Negation: it's no picnic; it's harder than it looks.",
            ),
        ),
    ),

    "fr_avoir_la_tete_dans_les_nuages": PhraseFamily(
        id="fr_avoir_la_tete_dans_les_nuages",
        language="fr",
        canonical_form="avoir la tête dans les nuages",
        meaning="To have one's head in the clouds; to be a daydreamer.",
        register="neutral",
        origin=(
            "Clouds as a symbol of vagueness and unreality is cross-cultural. The "
            "French expression maps directly onto the English idiom, both rooted in "
            "the image of someone whose thoughts float above the mundane world."
        ),
        variants=(
            PhraseVariant(
                surface="avoir la tête dans les nuages",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="la tête dans les nuages",
                match_type=MatchType.inflectional_variant,
                note="Elliptical form, predicate position.",
            ),
            PhraseVariant(
                surface="il a la tête dans les nuages",
                match_type=MatchType.inflectional_variant,
                note="Third-person conjugated form.",
            ),
        ),
    ),

    "fr_en_avoir_ras_le_bol": PhraseFamily(
        id="fr_en_avoir_ras_le_bol",
        language="fr",
        canonical_form="en avoir ras le bol",
        meaning="To be fed up; to have had it up to here.",
        register="informal",
        origin=(
            "Bol (bowl) filled to the brim (ras = level with the edge): the bowl of "
            "patience is completely full. Emerged in 20th-century colloquial French, "
            "used across France and Quebec."
        ),
        why_it_matters=(
            "Very high frequency in spoken French. The intensified form 'ras-le-bol' "
            "is also used as a noun ('un ras-le-bol général') meaning widespread "
            "discontent."
        ),
        variants=(
            PhraseVariant(
                surface="en avoir ras le bol",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="j'en ai ras le bol",
                match_type=MatchType.inflectional_variant,
                note="First-person: I've had it up to here.",
            ),
            PhraseVariant(
                surface="ras-le-bol",
                match_type=MatchType.inflectional_variant,
                note="Noun form: widespread exasperation.",
            ),
        ),
    ),

    "fr_vendre_la_meche": PhraseFamily(
        id="fr_vendre_la_meche",
        language="fr",
        canonical_form="vendre la mèche",
        meaning="To spill the beans; to let the cat out of the bag; to reveal a secret.",
        register="informal",
        origin=(
            "Mèche (fuse, or wick) referred to the fuse on a bomb or cannon. 'Selling "
            "the fuse' to the enemy would reveal the plan of attack. The expression "
            "entered civilian speech as a metaphor for betraying a secret."
        ),
        variants=(
            PhraseVariant(
                surface="vendre la mèche",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="vendre la meche",
                match_type=MatchType.orthographic_variant,
                note="Without accent, common in informal writing.",
            ),
            PhraseVariant(
                surface="a vendu la mèche",
                match_type=MatchType.inflectional_variant,
                note="He/she sold the fuse — past tense usage.",
            ),
        ),
    ),

    "fr_sauter_du_coq_a_lane": PhraseFamily(
        id="fr_sauter_du_coq_a_lane",
        language="fr",
        canonical_form="sauter du coq à l'âne",
        meaning="To jump from topic to topic; to change subjects abruptly.",
        register="neutral",
        origin=(
            "From coq (rooster) to âne (donkey): two unrelated animals, emphasizing "
            "the absurdity of the leap. The expression appears in Rabelais (16th "
            "century) and reflects medieval comic traditions of nonsense discourse."
        ),
        why_it_matters=(
            "A colorful image with no direct English equivalent. Reveals how French "
            "idioms often use barnyard animals as vehicles for abstract ideas."
        ),
        variants=(
            PhraseVariant(
                surface="sauter du coq à l'âne",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="sauter du coq a l'ane",
                match_type=MatchType.orthographic_variant,
                note="Without grave accent.",
            ),
            PhraseVariant(
                surface="passer du coq à l'âne",
                match_type=MatchType.inflectional_variant,
                note="Variant using 'passer' (to pass) instead of 'sauter'.",
            ),
        ),
    ),

    "fr_faire_dune_pierre_deux_coups": PhraseFamily(
        id="fr_faire_dune_pierre_deux_coups",
        language="fr",
        canonical_form="faire d'une pierre deux coups",
        meaning="To kill two birds with one stone.",
        register="neutral",
        origin=(
            "Strikingly parallel to English. Both French and English use the image of "
            "a single projectile achieving two results. The stone (pierre) replaces "
            "the English bird metaphor with a more tool-oriented image."
        ),
        variants=(
            PhraseVariant(
                surface="faire d'une pierre deux coups",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="d'une pierre deux coups",
                match_type=MatchType.inflectional_variant,
                note="Elliptical form, often used as a parenthetical.",
            ),
            PhraseVariant(
                surface="faire une pierre deux coups",
                match_type=MatchType.orthographic_variant,
                note="Without the elided 'de', rare but attested.",
            ),
        ),
    ),

    "fr_mettre_son_grain_de_sel": PhraseFamily(
        id="fr_mettre_son_grain_de_sel",
        language="fr",
        canonical_form="mettre son grain de sel",
        meaning="To put in one's two cents; to add an unwanted opinion.",
        register="neutral",
        origin=(
            "Salt was a valuable commodity in medieval France (gabelle = salt tax). A "
            "grain of salt (grain de sel) is the smallest addition. To sprinkle one's "
            "salt onto others' conversations suggests unsolicited seasoning of the "
            "discussion."
        ),
        variants=(
            PhraseVariant(
                surface="mettre son grain de sel",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="il faut toujours qu'il mette son grain de sel",
                match_type=MatchType.inflectional_variant,
                note="He always has to put his two cents in.",
            ),
        ),
    ),

    "fr_avoir_le_bras_long": PhraseFamily(
        id="fr_avoir_le_bras_long",
        language="fr",
        canonical_form="avoir le bras long",
        meaning="To have a long arm; to be well-connected; to have influence.",
        register="neutral",
        origin=(
            "A long arm reaches further — an image of power and access. Common in "
            "French since the 17th century. Parallel expressions exist in Italian "
            "('avere le mani lunghe') and Spanish ('tener mucho brazo')."
        ),
        variants=(
            PhraseVariant(
                surface="avoir le bras long",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="il a le bras long",
                match_type=MatchType.inflectional_variant,
                note="He has connections — most common contextualized form.",
            ),
        ),
    ),

    "fr_ramener_sa_fraise": PhraseFamily(
        id="fr_ramener_sa_fraise",
        language="fr",
        canonical_form="ramener sa fraise",
        meaning="To butt in; to show one's face where uninvited; to impose oneself.",
        register="informal",
        origin=(
            "Fraise (strawberry, but also an archaic ruff collar) was slang for "
            "'face' or 'head' in 19th-century argot. 'Ramener sa fraise' means "
            "literally 'bring one's face along' into a situation where it wasn't "
            "requested."
        ),
        why_it_matters=(
            "A distinctly argot expression that illustrates how French slang often "
            "repurposes object names for body parts. Very colloquial and typically "
            "humorous."
        ),
        variants=(
            PhraseVariant(
                surface="ramener sa fraise",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="ramène pas ta fraise",
                match_type=MatchType.inflectional_variant,
                note="Don't show your face here — imperative negation.",
            ),
        ),
    ),

    "fr_ne_pas_tourner_autour_du_pot": PhraseFamily(
        id="fr_ne_pas_tourner_autour_du_pot",
        language="fr",
        canonical_form="ne pas tourner autour du pot",
        meaning="To not beat around the bush; to get straight to the point.",
        register="neutral",
        origin=(
            "Pot (cooking pot): circling around the pot without touching it suggests "
            "approaching something without committing. Attested since the 16th "
            "century in French. Compare English 'beat around the bush' (stirring up "
            "game without entering the bush)."
        ),
        variants=(
            PhraseVariant(
                surface="ne pas tourner autour du pot",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="tourner autour du pot",
                match_type=MatchType.inflectional_variant,
                note="Positive form: to beat around the bush (pejorative).",
            ),
            PhraseVariant(
                surface="sans tourner autour du pot",
                match_type=MatchType.inflectional_variant,
                note="Without beating around the bush.",
            ),
        ),
    ),

    "fr_avoir_un_poil_dans_la_main": PhraseFamily(
        id="fr_avoir_un_poil_dans_la_main",
        language="fr",
        canonical_form="avoir un poil dans la main",
        meaning="To be lazy; to have hands not used to work.",
        register="informal",
        origin=(
            "The idea that someone so unaccustomed to work has grown a hair (poil) in "
            "their hand. A comic image implying that the hand has not been clenched "
            "in useful effort long enough to prevent the growth. Typically French in "
            "its earthy sarcasm."
        ),
        why_it_matters=(
            "One of the most characteristic French expressions for laziness. The "
            "image is absurdist and impossible to guess — a classic example of opaque "
            "idiom."
        ),
        variants=(
            PhraseVariant(
                surface="avoir un poil dans la main",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="il a un poil dans la main",
                match_type=MatchType.inflectional_variant,
                note="He's got a hair in his hand — he's lazy.",
            ),
        ),
    ),

    "fr_mettre_les_voiles": PhraseFamily(
        id="fr_mettre_les_voiles",
        language="fr",
        canonical_form="mettre les voiles",
        meaning="To clear off; to take off; to make oneself scarce.",
        register="informal",
        origin=(
            "Voiles (sails): setting sail suggests departure. The maritime image "
            "became general slang for leaving quickly. Related to 'se faire la voile' "
            "(same meaning). Common in contemporary spoken French."
        ),
        variants=(
            PhraseVariant(
                surface="mettre les voiles",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="il a mis les voiles",
                match_type=MatchType.inflectional_variant,
                note="He took off — past tense.",
            ),
            PhraseVariant(
                surface="je vais mettre les voiles",
                match_type=MatchType.inflectional_variant,
                note="I'm going to split — future intent.",
            ),
        ),
    ),

    "fr_battre_le_fer": PhraseFamily(
        id="fr_battre_le_fer",
        language="fr",
        canonical_form="battre le fer pendant qu'il est chaud",
        meaning="Strike while the iron is hot; act at the opportune moment.",
        register="neutral",
        origin=(
            "Blacksmiths must hammer iron while it's hot enough to shape. Ancient "
            "proverb with parallels in Latin ('Dum ferrum candet, tundito'), attested "
            "in French at least since the 14th century. Identical in form to the "
            "English expression."
        ),
        variants=(
            PhraseVariant(
                surface="battre le fer pendant qu'il est chaud",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="battre le fer quand il est chaud",
                match_type=MatchType.inflectional_variant,
                note="Shortened form, still common.",
            ),
            PhraseVariant(
                surface="il faut battre le fer",
                match_type=MatchType.inflectional_variant,
                note="One must strike the iron — directive phrasing.",
            ),
        ),
    ),

    "fr_se_lever_du_pied_gauche": PhraseFamily(
        id="fr_se_lever_du_pied_gauche",
        language="fr",
        canonical_form="se lever du pied gauche",
        meaning="To get up on the wrong side of the bed; to start the day in a bad mood.",
        register="neutral",
        origin=(
            "The left side (gauche) carried negative connotations across European "
            "cultures — from Latin 'sinister' (left = ominous) to folk belief that "
            "getting out of bed on the left foot would bring bad luck to the day."
        ),
        why_it_matters=(
            "Reveals the deep cultural history of left-handedness stigma encoded in "
            "idiom. Gauche in French also means 'awkward' — the double meaning "
            "enriches the phrase."
        ),
        variants=(
            PhraseVariant(
                surface="se lever du pied gauche",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="il s'est levé du pied gauche",
                match_type=MatchType.inflectional_variant,
                note="He got up on the wrong side — past tense.",
            ),
            PhraseVariant(
                surface="levé du mauvais pied",
                match_type=MatchType.inflectional_variant,
                note="Variant using 'mauvais pied' instead of 'pied gauche'.",
            ),
        ),
    ),

    "fr_faire_la_tete": PhraseFamily(
        id="fr_faire_la_tete",
        language="fr",
        canonical_form="faire la tête",
        meaning="To sulk; to give someone the silent treatment; to pout.",
        register="informal",
        origin=(
            "Literally 'make the head' — a visual image of the sulker presenting a "
            "stiff or turned-away head. The expression captures the physical posture "
            "of sulking and is widely used in casual French speech."
        ),
        variants=(
            PhraseVariant(
                surface="faire la tête",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="faire la tete",
                match_type=MatchType.orthographic_variant,
                note="Without circumflex, common in digital writing.",
            ),
            PhraseVariant(
                surface="il fait la tête",
                match_type=MatchType.inflectional_variant,
                note="He's sulking — present tense.",
            ),
            PhraseVariant(
                surface="arrête de faire la tête",
                match_type=MatchType.inflectional_variant,
                note="Stop sulking — imperative.",
            ),
        ),
    ),

    "fr_casser_du_sucre": PhraseFamily(
        id="fr_casser_du_sucre",
        language="fr",
        canonical_form="casser du sucre sur le dos de quelqu'un",
        meaning=(
            "To badmouth someone behind their back; to speak ill of someone in their"
            "absence."
        ),
        register="informal",
        origin=(
            "Sucre (sugar) was a precious, brittle commodity. Breaking sugar on "
            "someone's back is a vivid image of crushing something valuable against "
            "another person — a physical metaphor for verbal attack done covertly."
        ),
        variants=(
            PhraseVariant(
                surface="casser du sucre sur le dos de quelqu'un",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="casser du sucre sur son dos",
                match_type=MatchType.inflectional_variant,
                note="Shortened form with pronoun.",
            ),
            PhraseVariant(
                surface="ils cassent du sucre sur son dos",
                match_type=MatchType.inflectional_variant,
                note="They're talking behind his back.",
            ),
        ),
    ),

    "fr_tourner_de_loeil": PhraseFamily(
        id="fr_tourner_de_loeil",
        language="fr",
        canonical_form="tourner de l'œil",
        meaning="To faint; to pass out.",
        register="informal",
        origin=(
            "The eye 'turning' (rotating) refers to the roll of the eyes that often "
            "precedes fainting. The expression captures the visible physiological "
            "sign of loss of consciousness in a striking image."
        ),
        variants=(
            PhraseVariant(
                surface="tourner de l'œil",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="tourner de l'oeil",
                match_type=MatchType.orthographic_variant,
                note="Without the ligature œ, common in informal writing.",
            ),
            PhraseVariant(
                surface="il a tourné de l'œil",
                match_type=MatchType.inflectional_variant,
                note="He fainted — past tense.",
            ),
        ),
    ),

    "fr_prendre_la_tangente": PhraseFamily(
        id="fr_prendre_la_tangente",
        language="fr",
        canonical_form="prendre la tangente",
        meaning="To dodge; to take the easy way out; to slip away.",
        register="neutral",
        origin=(
            "From mathematics: a tangent line touches a curve at one point then flies "
            "off. Prendre la tangente = to take the line of least resistance and veer "
            "away from the main issue. Common in educated and general French."
        ),
        variants=(
            PhraseVariant(
                surface="prendre la tangente",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="il a pris la tangente",
                match_type=MatchType.inflectional_variant,
                note="He dodged the issue — past tense.",
            ),
        ),
    ),

    "fr_avoir_les_pieds_sur_terre": PhraseFamily(
        id="fr_avoir_les_pieds_sur_terre",
        language="fr",
        canonical_form="avoir les pieds sur terre",
        meaning="To be down-to-earth; to be realistic and practical.",
        register="neutral",
        origin=(
            "Feet firmly on the ground as a positive contrast to 'avoir la tête dans "
            "les nuages' (head in the clouds). The binary opposition — earth vs. "
            "clouds — organizes a broader conceptual field of realism vs. fantasy."
        ),
        why_it_matters=(
            "Often paired with or contrasted against 'avoir la tête dans les nuages'. "
            "Learners who know both can immediately grasp the French conceptual axis "
            "between grounded and dreamy."
        ),
        variants=(
            PhraseVariant(
                surface="avoir les pieds sur terre",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="les pieds sur terre",
                match_type=MatchType.inflectional_variant,
                note="Elliptical predicate use.",
            ),
            PhraseVariant(
                surface="rester les pieds sur terre",
                match_type=MatchType.inflectional_variant,
                note="To stay grounded — with rester.",
            ),
        ),
    ),

    "fr_manger_les_pissenlits": PhraseFamily(
        id="fr_manger_les_pissenlits",
        language="fr",
        canonical_form="manger les pissenlits par la racine",
        meaning="To push up daisies; to be dead and buried.",
        register="informal",
        origin=(
            "Pissenlit (dandelion, literally 'wet-the-bed') grows above ground — but "
            "someone buried beneath would be eating its roots from below. A dark "
            "comic image of death expressed through the perspective of the corpse."
        ),
        why_it_matters=(
            "Distinctly French in its macabre humor. The word 'pissenlit' itself is "
            "already colloquial and earthy, which sets the register. No direct "
            "English equivalent uses the same image."
        ),
        variants=(
            PhraseVariant(
                surface="manger les pissenlits par la racine",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="bouffer les pissenlits par la racine",
                match_type=MatchType.inflectional_variant,
                note="More vulgar form with 'bouffer' (to scoff).",
            ),
        ),
    ),

    "fr_ne_pas_casser_trois_pattes": PhraseFamily(
        id="fr_ne_pas_casser_trois_pattes",
        language="fr",
        canonical_form="ne pas casser trois pattes à un canard",
        meaning=(
            "Nothing special; not particularly impressive; won't set the world on"
            "fire."
        ),
        register="informal",
        origin=(
            "A duck has two legs — breaking three is impossible. The expression "
            "implies that something isn't even accomplishing the impossible, i.e., "
            "it's quite ordinary. The image highlights underachievement through "
            "impossible arithmetic."
        ),
        variants=(
            PhraseVariant(
                surface="ne pas casser trois pattes à un canard",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="ça ne casse pas trois pattes à un canard",
                match_type=MatchType.inflectional_variant,
                note="It won't set the world on fire.",
            ),
            PhraseVariant(
                surface="ça casse pas des briques",
                match_type=MatchType.inflectional_variant,
                note="Variant using bricks instead of duck legs — same meaning, more common in modern speech.",
            ),
        ),
    ),

    "fr_avoir_mal_aux_cheveux": PhraseFamily(
        id="fr_avoir_mal_aux_cheveux",
        language="fr",
        canonical_form="avoir mal aux cheveux",
        meaning="To have a hangover; to have aching hair (from drinking).",
        register="informal",
        origin=(
            "A playful, hyperbolic complaint: even one's hair hurts after a night of "
            "drinking. Hair normally feels no pain — the absurdity signals the excess "
            "of the situation. A classically French understatement-through- "
            "exaggeration."
        ),
        why_it_matters=(
            "A charming idiom for learners. The literal meaning 'my hair hurts' is "
            "obviously comic, and understanding it builds confidence with French "
            "comic logic."
        ),
        variants=(
            PhraseVariant(
                surface="avoir mal aux cheveux",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="j'ai mal aux cheveux",
                match_type=MatchType.inflectional_variant,
                note="My hair hurts — I'm hungover.",
            ),
        ),
    ),

    "fr_faire_les_yeux_doux": PhraseFamily(
        id="fr_faire_les_yeux_doux",
        language="fr",
        canonical_form="faire les yeux doux",
        meaning="To make eyes at someone; to look at someone with desire or flattery.",
        register="neutral",
        origin=(
            "Doux (soft, gentle) applied to eyes suggests a softened, inviting gaze. "
            "The expression captures the physical act of flirting through eye "
            "contact. Attested since at least the 17th century in French literature."
        ),
        variants=(
            PhraseVariant(
                surface="faire les yeux doux",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="il lui fait les yeux doux",
                match_type=MatchType.inflectional_variant,
                note="He's making eyes at her.",
            ),
        ),
    ),

    "fr_casser_la_croute": PhraseFamily(
        id="fr_casser_la_croute",
        language="fr",
        canonical_form="casser la croûte",
        meaning="To have a bite to eat; to grab a snack.",
        register="informal",
        origin=(
            "Croûte (crust) is the hardest part of bread, requiring effort to break. "
            "'Breaking the crust' was the act of beginning a meal when bread was the "
            "staple. The expression preserves the old physicality of eating in a "
            "modern casual idiom."
        ),
        variants=(
            PhraseVariant(
                surface="casser la croûte",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="casser la croute",
                match_type=MatchType.orthographic_variant,
                note="Without circumflex.",
            ),
            PhraseVariant(
                surface="on va casser la croûte",
                match_type=MatchType.inflectional_variant,
                note="We're going to grab a bite.",
            ),
        ),
    ),

    "fr_aller_a_la_peche": PhraseFamily(
        id="fr_aller_a_la_peche",
        language="fr",
        canonical_form="aller à la pêche",
        meaning="To go fishing for something; to fish for compliments or information.",
        register="neutral",
        origin=(
            "Pêche (fishing) as a metaphor for seeking something indirectly. 'Aller à "
            "la pêche aux compliments' (fishing for compliments) is a common "
            "elaboration. The image implies patience and indirectness in obtaining "
            "something."
        ),
        variants=(
            PhraseVariant(
                surface="aller à la pêche",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="aller a la peche",
                match_type=MatchType.orthographic_variant,
                note="Without accents.",
            ),
            PhraseVariant(
                surface="pêcher des compliments",
                match_type=MatchType.inflectional_variant,
                note="To fish for compliments — verb form.",
            ),
        ),
    ),

    "fr_avoir_du_bol": PhraseFamily(
        id="fr_avoir_du_bol",
        language="fr",
        canonical_form="avoir du bol",
        meaning="To be lucky; to have good fortune.",
        register="informal",
        origin=(
            "Bol (bowl) as slang for luck derives from bol as rhyming slang or from "
            "the earlier sense of 'portion' — your share of fortune. Common in French "
            "slang since the 20th century. 'Avoir du pot' is a synonymous expression."
        ),
        variants=(
            PhraseVariant(
                surface="avoir du bol",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="t'as du bol!",
                match_type=MatchType.inflectional_variant,
                note="You're lucky! — exclamatory.",
            ),
            PhraseVariant(
                surface="pas de bol",
                match_type=MatchType.inflectional_variant,
                note="No luck; bad luck — negated form used as an interjection.",
            ),
        ),
    ),

    "fr_cest_du_chinois": PhraseFamily(
        id="fr_cest_du_chinois",
        language="fr",
        canonical_form="c'est du chinois",
        meaning="It's all Greek to me; it's incomprehensible.",
        register="informal",
        origin=(
            "Where English uses Greek as the paradigmatic incomprehensible language, "
            "French uses Chinese (chinois). Both reflect 18th–19th century European "
            "attitudes toward distant linguistic systems. Compare Italian 'è tutto "
            "greco' and Spanish 'es chino para mí'."
        ),
        why_it_matters=(
            "The cross-linguistic comparison (English: Greek / French: Chinese) "
            "illustrates how idioms encode cultural reference points differently "
            "across languages while expressing the same concept."
        ),
        variants=(
            PhraseVariant(
                surface="c'est du chinois",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="pour moi c'est du chinois",
                match_type=MatchType.inflectional_variant,
                note="To me, it's all Chinese — with personal framing.",
            ),
            PhraseVariant(
                surface="c'est du charabia",
                match_type=MatchType.inflectional_variant,
                note="It's gibberish — synonym using charabia (from Turkish).",
            ),
        ),
    ),

    "fr_se_casser_la_tete": PhraseFamily(
        id="fr_se_casser_la_tete",
        language="fr",
        canonical_form="se casser la tête",
        meaning="To rack one's brain; to think hard about something.",
        register="neutral",
        origin=(
            "Casser (to break) applied to the head suggests the strain of intense "
            "thought — thinking so hard it feels like breaking something. A visceral "
            "metaphor for cognitive effort, widely used across registers."
        ),
        variants=(
            PhraseVariant(
                surface="se casser la tête",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="je me casse la tête",
                match_type=MatchType.inflectional_variant,
                note="I'm racking my brain.",
            ),
            PhraseVariant(
                surface="ne te casse pas la tête",
                match_type=MatchType.inflectional_variant,
                note="Don't overthink it — imperative.",
            ),
        ),
    ),

    "fr_ne_pas_avoir_froid_aux_yeux": PhraseFamily(
        id="fr_ne_pas_avoir_froid_aux_yeux",
        language="fr",
        canonical_form="ne pas avoir froid aux yeux",
        meaning="To be bold; to have nerve; to not be faint-hearted.",
        register="neutral",
        origin=(
            "Cold in the eyes = fear causing the gaze to freeze. Someone who does not "
            "have cold in their eyes faces situations with unwavering gaze. The "
            "metaphor connects physical sensation (cold, fear) with ocular expression "
            "of courage."
        ),
        variants=(
            PhraseVariant(
                surface="ne pas avoir froid aux yeux",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="il n'a pas froid aux yeux",
                match_type=MatchType.inflectional_variant,
                note="He doesn't lack nerve.",
            ),
            PhraseVariant(
                surface="elle n'a pas froid aux yeux",
                match_type=MatchType.inflectional_variant,
                note="She's fearless.",
            ),
        ),
    ),

    "fr_arriver_comme_un_cheveu_sur_la_soupe": PhraseFamily(
        id="fr_arriver_comme_un_cheveu_sur_la_soupe",
        language="fr",
        canonical_form="arriver comme un cheveu sur la soupe",
        meaning=(
            "To turn up at the wrong moment; to arrive inopportunely; to come out of"
            "nowhere."
        ),
        register="informal",
        origin=(
            "A hair in the soup (cheveu sur la soupe) is an unwelcome intrusion into "
            "something otherwise pleasant. Someone who 'arrives like a hair in the "
            "soup' is similarly misplaced and unwelcome."
        ),
        why_it_matters=(
            "Highly image-driven and memorable. The hygiene-disgust image is "
            "instantly visceral. Illustrates how French idiom encodes social "
            "awkwardness through concrete domestic scenes."
        ),
        variants=(
            PhraseVariant(
                surface="arriver comme un cheveu sur la soupe",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="tomber comme un cheveu sur la soupe",
                match_type=MatchType.inflectional_variant,
                note="Fall like a hair in the soup — with tomber.",
            ),
            PhraseVariant(
                surface="comme un cheveu sur la soupe",
                match_type=MatchType.inflectional_variant,
                note="Elliptical: like a hair in the soup — adverbial use.",
            ),
        ),
    ),

    "fr_se_jeter_dans_la_gueule_du_loup": PhraseFamily(
        id="fr_se_jeter_dans_la_gueule_du_loup",
        language="fr",
        canonical_form="se jeter dans la gueule du loup",
        meaning="To jump into the lion's den; to walk knowingly into danger.",
        register="neutral",
        origin=(
            "Gueule du loup (wolf's mouth): throwing oneself into the wolf's open "
            "jaws — a vivid image of deliberately entering a dangerous situation. "
            "Compare English 'into the lion's den' and 'beard the lion.' French uses "
            "the wolf, a historically more feared predator in rural France than the "
            "lion."
        ),
        variants=(
            PhraseVariant(
                surface="se jeter dans la gueule du loup",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="entrer dans la gueule du loup",
                match_type=MatchType.inflectional_variant,
                note="To walk into the lion's den — with entrer instead of se jeter.",
            ),
        ),
    ),

    # ── It (generated) ────────────────────────────────────────

    "it_avere_le_mani_bucate": PhraseFamily(
        id="it_avere_le_mani_bucate",
        language="it",
        canonical_form="avere le mani bucate",
        meaning="To be a spendthrift; to have money slip through one's fingers.",
        register="informal",
        origin=(
            "Literally 'to have holes in one's hands' — money falls out as if through "
            "holes in the palms. A vivid tactile image for someone who cannot hold "
            "onto money. Compare English 'money burns a hole in one's pocket.'"
        ),
        variants=(
            PhraseVariant(
                surface="avere le mani bucate",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="ha le mani bucate",
                match_type=MatchType.inflectional_variant,
                note="He/she has holes in their hands — most common contextualized form.",
            ),
        ),
    ),

    "it_togliersi_un_sassolino": PhraseFamily(
        id="it_togliersi_un_sassolino",
        language="it",
        canonical_form="togliersi un sassolino dalla scarpa",
        meaning="To get something off one's chest; to remove a grievance.",
        register="neutral",
        origin=(
            "Sassolino (small stone): a pebble in the shoe is a small but persistent "
            "irritation. Removing it brings relief. The expression captures the "
            "satisfaction of finally airing a minor grievance that has been bothering "
            "you."
        ),
        why_it_matters=(
            "Uniquely Italian in its image. The diminutive sassolino emphasizes the "
            "pettiness of the grievance, adding a self-aware, slightly ironic "
            "register."
        ),
        variants=(
            PhraseVariant(
                surface="togliersi un sassolino dalla scarpa",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="mi tolgo un sassolino dalla scarpa",
                match_type=MatchType.inflectional_variant,
                note="I need to get something off my chest — first person.",
            ),
        ),
    ),

    "it_andare_a_vuoto": PhraseFamily(
        id="it_andare_a_vuoto",
        language="it",
        canonical_form="andare a vuoto",
        meaning="To come to nothing; to draw a blank; to fail to achieve a result.",
        register="neutral",
        origin=(
            "Vuoto (empty, void): to go toward emptiness — an action that leads "
            "nowhere. A neutral, versatile expression for any failed effort or "
            "unproductive attempt."
        ),
        variants=(
            PhraseVariant(
                surface="andare a vuoto",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="il tentativo è andato a vuoto",
                match_type=MatchType.inflectional_variant,
                note="The attempt came to nothing — past tense.",
            ),
            PhraseVariant(
                surface="andare a vuoto di nuovo",
                match_type=MatchType.inflectional_variant,
                note="To draw a blank again.",
            ),
        ),
    ),

    "it_prendere_fischi_per_fiaschi": PhraseFamily(
        id="it_prendere_fischi_per_fiaschi",
        language="it",
        canonical_form="prendere fischi per fiaschi",
        meaning=(
            "To get hold of the wrong end of the stick; to confuse two things"
            "completely."
        ),
        register="informal",
        origin=(
            "Fischi (whistles/hisses) vs fiaschi (flasks/failures): the near-rhyme of "
            "the two words (typical Italian wordplay) captures the confusion of "
            "mistaking one thing for another. Fiasco also means failure — the "
            "expression plays on dual resonance."
        ),
        why_it_matters=(
            "A memorable phonetic play. The near-rhyme fischi/fiaschi is "
            "untranslatable — the expression teaches the Italian ear for wordplay "
            "built into idiom."
        ),
        variants=(
            PhraseVariant(
                surface="prendere fischi per fiaschi",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="scambiare fischi per fiaschi",
                match_type=MatchType.inflectional_variant,
                note="Variant with 'scambiare' (to swap) — same meaning.",
            ),
        ),
    ),

    "it_rompere_il_ghiaccio": PhraseFamily(
        id="it_rompere_il_ghiaccio",
        language="it",
        canonical_form="rompere il ghiaccio",
        meaning="To break the ice; to ease tension in a new social situation.",
        register="neutral",
        origin=(
            "The image of breaking through ice to allow passage is shared across "
            "European languages — from Latin sources through French and Italian. In "
            "all versions, the frozen surface represents awkward social stiffness."
        ),
        variants=(
            PhraseVariant(
                surface="rompere il ghiaccio",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="ha rotto il ghiaccio",
                match_type=MatchType.inflectional_variant,
                note="He/she broke the ice — past tense.",
            ),
            PhraseVariant(
                surface="serve qualcosa per rompere il ghiaccio",
                match_type=MatchType.inflectional_variant,
                note="Something is needed to break the ice.",
            ),
        ),
    ),

    "it_fare_orecchie_da_mercante": PhraseFamily(
        id="it_fare_orecchie_da_mercante",
        language="it",
        canonical_form="fare orecchie da mercante",
        meaning="To turn a deaf ear; to pretend not to hear.",
        register="neutral",
        origin=(
            "Mercante (merchant): a merchant at market would selectively hear only "
            "what suited him — ignoring pleas, complaints, and unfavorable "
            "information. The expression captures deliberate rather than accidental "
            "deafness."
        ),
        variants=(
            PhraseVariant(
                surface="fare orecchie da mercante",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="fa orecchie da mercante",
                match_type=MatchType.inflectional_variant,
                note="He/she turns a deaf ear — present tense.",
            ),
        ),
    ),

    "it_avere_il_dente_avvelenato": PhraseFamily(
        id="it_avere_il_dente_avvelenato",
        language="it",
        canonical_form="avere il dente avvelenato",
        meaning="To bear a grudge; to have poisoned feelings toward someone.",
        register="neutral",
        origin=(
            "Dente avvelenato (poisoned tooth): like a snake's venom-delivering fang, "
            "the person with a poisoned tooth harbors hidden hostility. The "
            "expression implies resentment that has been nursing quietly."
        ),
        variants=(
            PhraseVariant(
                surface="avere il dente avvelenato",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="ce l'ha con me — ha il dente avvelenato",
                match_type=MatchType.inflectional_variant,
                note="He has it in for me — he's holding a grudge.",
            ),
        ),
    ),

    "it_essere_tra_lincudine_e_il_martello": PhraseFamily(
        id="it_essere_tra_lincudine_e_il_martello",
        language="it",
        canonical_form="essere tra l'incudine e il martello",
        meaning=(
            "To be between the anvil and the hammer; to be between a rock and a hard"
            "place."
        ),
        register="neutral",
        origin=(
            "The blacksmith's anvil (incudine) below and hammer (martello) above — "
            "someone caught between them is struck from both sides. A more vivid "
            "mechanistic image than the English 'rock and a hard place.'"
        ),
        variants=(
            PhraseVariant(
                surface="essere tra l'incudine e il martello",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="tra l'incudine e il martello",
                match_type=MatchType.inflectional_variant,
                note="Elliptical — predicative use.",
            ),
            PhraseVariant(
                surface="mi trovo tra l'incudine e il martello",
                match_type=MatchType.inflectional_variant,
                note="I'm caught between the devil and the deep blue sea.",
            ),
        ),
    ),

    "it_gettare_la_spugna": PhraseFamily(
        id="it_gettare_la_spugna",
        language="it",
        canonical_form="gettare la spugna",
        meaning="To throw in the sponge; to give up.",
        register="neutral",
        origin=(
            "From boxing: the sponge (spugna) used to clean a fighter's wounds — "
            "throwing it in signals surrender. Italian borrowed this directly from "
            "English boxing culture. Note: Italian uses spugna (sponge) where German "
            "uses Handtuch (towel)."
        ),
        variants=(
            PhraseVariant(
                surface="gettare la spugna",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="ha gettato la spugna",
                match_type=MatchType.inflectional_variant,
                note="He threw in the sponge — past tense.",
            ),
            PhraseVariant(
                surface="buttare la spugna",
                match_type=MatchType.inflectional_variant,
                note="Colloquial variant with 'buttare' (to throw/chuck).",
            ),
        ),
    ),

    "it_vedere_tutto_rosa": PhraseFamily(
        id="it_vedere_tutto_rosa",
        language="it",
        canonical_form="vedere tutto rosa",
        meaning="To see everything through rose-colored glasses; to be overly optimistic.",
        register="neutral",
        origin=(
            "Rosa (pink/rose) as the color of optimism and idealism — seeing the "
            "world through a rosy filter. The expression parallels English 'rose- "
            "tinted glasses' and French 'voir la vie en rose.' The cultural root is "
            "the same Romantic-era metaphor."
        ),
        variants=(
            PhraseVariant(
                surface="vedere tutto rosa",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="vede tutto rosa",
                match_type=MatchType.inflectional_variant,
                note="He/she sees everything through rose-colored glasses.",
            ),
            PhraseVariant(
                surface="non tutto è rosa e fiori",
                match_type=MatchType.inflectional_variant,
                note="Not everything is rosy — negated contrast form.",
            ),
        ),
    ),

    "it_tirare_acqua_al_proprio_mulino": PhraseFamily(
        id="it_tirare_acqua_al_proprio_mulino",
        language="it",
        canonical_form="tirare acqua al proprio mulino",
        meaning="To feather one's nest; to advance one's own interests.",
        register="neutral",
        origin=(
            "Mulino (mill): water diverted to one's own mill powers it at others' "
            "expense. Mills were a central economic institution in medieval Italy; "
            "control of water rights was literally a matter of prosperity."
        ),
        variants=(
            PhraseVariant(
                surface="tirare acqua al proprio mulino",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="portare acqua al proprio mulino",
                match_type=MatchType.inflectional_variant,
                note="Variant with portare (to bring) — same meaning.",
            ),
            PhraseVariant(
                surface="tira sempre acqua al suo mulino",
                match_type=MatchType.inflectional_variant,
                note="He always looks out for himself.",
            ),
        ),
    ),

    "it_avere_la_coda_di_paglia": PhraseFamily(
        id="it_avere_la_coda_di_paglia",
        language="it",
        canonical_form="avere la coda di paglia",
        meaning="To have a guilty conscience; to feel accused by innocent remarks.",
        register="neutral",
        origin=(
            "Coda di paglia (tail of straw): a tail that catches fire easily — "
            "someone sensitive to accusation, quick to feel targeted by any mention "
            "of wrongdoing, because they know they've done wrong."
        ),
        why_it_matters=(
            "Uniquely Italian. The straw-tail image has no English equivalent. "
            "Understanding it builds cultural fluency around how Italians encode "
            "guilt and sensitivity."
        ),
        variants=(
            PhraseVariant(
                surface="avere la coda di paglia",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="ha la coda di paglia",
                match_type=MatchType.inflectional_variant,
                note="He/she is overly defensive — has a guilty conscience.",
            ),
        ),
    ),

    "it_buttare_il_bambino_con_lacqua": PhraseFamily(
        id="it_buttare_il_bambino_con_lacqua",
        language="it",
        canonical_form="buttare il bambino con l'acqua sporca",
        meaning="To throw the baby out with the bathwater.",
        register="neutral",
        origin=(
            "Shared proverb across European languages — traced to Thomas Murner's "
            "1512 German pamphlet but quickly absorbed into Italian usage. The image "
            "is identical: discarding the valuable (child) along with the wasteable "
            "(dirty bathwater)."
        ),
        variants=(
            PhraseVariant(
                surface="buttare il bambino con l'acqua sporca",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="non buttiamo il bambino con l'acqua sporca",
                match_type=MatchType.inflectional_variant,
                note="Let's not throw the baby out with the bathwater — negated warning.",
            ),
            PhraseVariant(
                surface="gettare il bambino con l'acqua sporca",
                match_type=MatchType.inflectional_variant,
                note="Variant with gettare instead of buttare.",
            ),
        ),
    ),

    "it_fare_il_passo_piu_lungo_della_gamba": PhraseFamily(
        id="it_fare_il_passo_piu_lungo_della_gamba",
        language="it",
        canonical_form="fare il passo più lungo della gamba",
        meaning="To bite off more than one can chew; to overextend oneself.",
        register="neutral",
        origin=(
            "Taking a step (passo) longer than one's leg (gamba) can reach will cause "
            "a fall. The image is physically immediate: overreach in a literal stride "
            "becomes a metaphor for any overambitious action."
        ),
        variants=(
            PhraseVariant(
                surface="fare il passo più lungo della gamba",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="ha fatto il passo più lungo della gamba",
                match_type=MatchType.inflectional_variant,
                note="He bit off more than he could chew — past tense.",
            ),
        ),
    ),

    "it_non_ce_due_senza_tre": PhraseFamily(
        id="it_non_ce_due_senza_tre",
        language="it",
        canonical_form="non c'è due senza tre",
        meaning="There's no two without three; things always happen in threes.",
        register="neutral",
        origin=(
            "The folk belief that events — especially misfortunes — come in threes is "
            "widespread across European cultures. Italian encodes it in this pithy "
            "formula. Compare English 'bad things come in threes' and similar "
            "expressions in French and German."
        ),
        variants=(
            PhraseVariant(
                surface="non c'è due senza tre",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "it_dare_i_numeri": PhraseFamily(
        id="it_dare_i_numeri",
        language="it",
        canonical_form="dare i numeri",
        meaning="To be off one's rocker; to act crazy; to give out random numbers.",
        register="informal",
        origin=(
            "Dare i numeri (to give numbers): the image of randomly calling out "
            "numbers suggests disordered thinking. May derive from lotto number- "
            "calling, where random numbers follow no logical sequence."
        ),
        variants=(
            PhraseVariant(
                surface="dare i numeri",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="stai dando i numeri",
                match_type=MatchType.inflectional_variant,
                note="You're going crazy — second person.",
            ),
            PhraseVariant(
                surface="da i numeri",
                match_type=MatchType.inflectional_variant,
                note="He's acting mad — present tense.",
            ),
        ),
    ),

    "it_andare_a_gonfie_vele": PhraseFamily(
        id="it_andare_a_gonfie_vele",
        language="it",
        canonical_form="andare a gonfie vele",
        meaning="To be going swimmingly; to proceed smoothly and successfully.",
        register="neutral",
        origin=(
            "Gonfie vele (full sails): a ship sailing with full, billowing sails is "
            "making maximum progress in ideal conditions. Italy's long maritime "
            "tradition makes nautical imagery especially natural in everyday speech."
        ),
        variants=(
            PhraseVariant(
                surface="andare a gonfie vele",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="le cose vanno a gonfie vele",
                match_type=MatchType.inflectional_variant,
                note="Things are going smoothly.",
            ),
            PhraseVariant(
                surface="procede a gonfie vele",
                match_type=MatchType.inflectional_variant,
                note="It's proceeding swimmingly.",
            ),
        ),
    ),

    "it_mettersi_nei_panni": PhraseFamily(
        id="it_mettersi_nei_panni",
        language="it",
        canonical_form="mettersi nei panni di qualcuno",
        meaning="To put oneself in someone else's shoes.",
        register="neutral",
        origin=(
            "Panni (clothes, garments): putting on someone's clothes = inhabiting "
            "their situation. Italian uses garments (panni) where English uses shoes "
            "— both capture the idea of inhabiting another perspective through "
            "physical substitution."
        ),
        variants=(
            PhraseVariant(
                surface="mettersi nei panni di qualcuno",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="mettiti nei miei panni",
                match_type=MatchType.inflectional_variant,
                note="Put yourself in my shoes — direct address.",
            ),
            PhraseVariant(
                surface="non riesco a mettermi nei suoi panni",
                match_type=MatchType.inflectional_variant,
                note="I can't imagine what it's like for them.",
            ),
        ),
    ),

    "it_lavarsi_le_mani": PhraseFamily(
        id="it_lavarsi_le_mani",
        language="it",
        canonical_form="lavarsi le mani di qualcosa",
        meaning="To wash one's hands of something; to disclaim responsibility.",
        register="neutral",
        origin=(
            "From the Gospel account of Pontius Pilate washing his hands before the "
            "crowd — a gesture of disclaiming responsibility for Jesus's execution. "
            "The biblical reference gave the expression immediate cultural currency "
            "across Catholic Europe."
        ),
        why_it_matters=(
            "Directly traceable to a specific biblical scene, giving learners "
            "cultural-historical depth. The expression is used across all major "
            "European languages in nearly identical form."
        ),
        variants=(
            PhraseVariant(
                surface="lavarsi le mani di qualcosa",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="me ne lavo le mani",
                match_type=MatchType.inflectional_variant,
                note="I wash my hands of it — first person.",
            ),
            PhraseVariant(
                surface="se ne è lavato le mani",
                match_type=MatchType.inflectional_variant,
                note="He/she washed their hands of it — past tense.",
            ),
        ),
    ),

    "it_non_fare_una_piega": PhraseFamily(
        id="it_non_fare_una_piega",
        language="it",
        canonical_form="non fare una piega",
        meaning=(
            "Not to bat an eye; to remain completely unperturbed; to be perfectly"
            "smooth."
        ),
        register="neutral",
        origin=(
            "Piega (fold, crease): a perfectly ironed garment has no wrinkles. "
            "'Without making a fold' = without showing any sign of disturbance. A "
            "cool, unruffled composure — literally and metaphorically smooth."
        ),
        variants=(
            PhraseVariant(
                surface="non fare una piega",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="non ha fatto una piega",
                match_type=MatchType.inflectional_variant,
                note="He/she didn't bat an eye — past tense.",
            ),
            PhraseVariant(
                surface="senza fare una piega",
                match_type=MatchType.inflectional_variant,
                note="Without batting an eye — adverbial.",
            ),
        ),
    ),

    "it_avere_un_diavolo_per_capello": PhraseFamily(
        id="it_avere_un_diavolo_per_capello",
        language="it",
        canonical_form="avere un diavolo per capello",
        meaning="To be furious; to be in a foul mood; to have the devil in every hair.",
        register="informal",
        origin=(
            "Capello (hair, single strand): every hair harboring a devil — an image "
            "of total possession by anger, so many devils that even individual hairs "
            "are inhabited. A vivid hyperbole of extreme bad temper."
        ),
        variants=(
            PhraseVariant(
                surface="avere un diavolo per capello",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="aveva un diavolo per capello",
                match_type=MatchType.inflectional_variant,
                note="She was furious — past tense.",
            ),
            PhraseVariant(
                surface="con un diavolo per capello",
                match_type=MatchType.inflectional_variant,
                note="Fuming — adverbial phrase.",
            ),
        ),
    ),

    "it_cadere_dalla_padella_nella_brace": PhraseFamily(
        id="it_cadere_dalla_padella_nella_brace",
        language="it",
        canonical_form="cadere dalla padella nella brace",
        meaning="Out of the frying pan into the fire.",
        register="neutral",
        origin=(
            "Padella (frying pan) → brace (embers): Italian uses the same physical "
            "cooking metaphor as English. Both involve escaping one source of heat "
            "only to land in a worse one. The image is ancient and cross-cultural."
        ),
        variants=(
            PhraseVariant(
                surface="cadere dalla padella nella brace",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="dalla padella nella brace",
                match_type=MatchType.inflectional_variant,
                note="Elliptical — often used as a standalone commentary.",
            ),
            PhraseVariant(
                surface="è caduto dalla padella nella brace",
                match_type=MatchType.inflectional_variant,
                note="He went from the frying pan into the fire — past tense.",
            ),
        ),
    ),

    "it_fare_buon_viso_a_cattivo_gioco": PhraseFamily(
        id="it_fare_buon_viso_a_cattivo_gioco",
        language="it",
        canonical_form="fare buon viso a cattivo gioco",
        meaning="To put a brave face on a bad situation; to grin and bear it.",
        register="neutral",
        origin=(
            "Card-playing imagery: gioco (game/hand of cards) — making a good face "
            "(buon viso) despite holding bad cards (cattivo gioco). The gambling "
            "metaphor for facing adversity stoically is widely used in Italian."
        ),
        variants=(
            PhraseVariant(
                surface="fare buon viso a cattivo gioco",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="ha fatto buon viso a cattivo gioco",
                match_type=MatchType.inflectional_variant,
                note="He put a brave face on it — past tense.",
            ),
        ),
    ),

    "it_avere_i_grilli_per_la_testa": PhraseFamily(
        id="it_avere_i_grilli_per_la_testa",
        language="it",
        canonical_form="avere i grilli per la testa",
        meaning="To be full of fancies; to have bees in one's bonnet; to be whimsical.",
        register="neutral",
        origin=(
            "Grillo (cricket): crickets in the head produce incessant, distracting "
            "noise — the chirping of restless thoughts or unrealistic ideas. Italian "
            "uses crickets where English uses bees; both capture the buzzing of idle "
            "fancy."
        ),
        variants=(
            PhraseVariant(
                surface="avere i grilli per la testa",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="ha sempre i grilli per la testa",
                match_type=MatchType.inflectional_variant,
                note="He's always full of whims.",
            ),
        ),
    ),

    "it_camminare_sulle_uova": PhraseFamily(
        id="it_camminare_sulle_uova",
        language="it",
        canonical_form="camminare sulle uova",
        meaning="To tread on eggshells; to walk carefully around a sensitive topic.",
        register="neutral",
        origin=(
            "Uova (eggs): eggs break under the slightest misstep — walking on them "
            "requires extreme delicacy. The expression parallels English 'walking on "
            "eggshells' exactly, suggesting a common metaphorical logic across "
            "cultures."
        ),
        variants=(
            PhraseVariant(
                surface="camminare sulle uova",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="ci cammino sulle uova",
                match_type=MatchType.inflectional_variant,
                note="I'm treading on eggshells here.",
            ),
            PhraseVariant(
                surface="stare sulle uova",
                match_type=MatchType.inflectional_variant,
                note="To be on eggshells — with stare (to stay/be).",
            ),
        ),
    ),

    "it_menare_il_can_per_laia": PhraseFamily(
        id="it_menare_il_can_per_laia",
        language="it",
        canonical_form="menare il can per l'aia",
        meaning="To beat around the bush; to avoid coming to the point.",
        register="neutral",
        origin=(
            "Aia (threshing floor) + can (dog): leading a dog around the threshing "
            "floor endlessly without accomplishing anything. The rural agricultural "
            "setting roots the expression in peasant life — circular, unproductive "
            "motion."
        ),
        variants=(
            PhraseVariant(
                surface="menare il can per l'aia",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="non menare il can per l'aia",
                match_type=MatchType.inflectional_variant,
                note="Don't beat around the bush — negated imperative.",
            ),
            PhraseVariant(
                surface="smettila di menare il can per l'aia",
                match_type=MatchType.inflectional_variant,
                note="Stop going around in circles.",
            ),
        ),
    ),

    "it_toccata_e_fuga": PhraseFamily(
        id="it_toccata_e_fuga",
        language="it",
        canonical_form="toccata e fuga",
        meaning="A fleeting visit; in and out; a brief and swift appearance.",
        register="neutral",
        origin=(
            "A direct borrowing from musical terminology: the toccata-and-fugue form "
            "(toccata = touch, fuga = flight) suggests a brief touch followed by "
            "rapid departure. The musical connotation adds a cultured, slightly "
            "ironic register."
        ),
        why_it_matters=(
            "A beautiful example of Italian using musical vocabulary in everyday "
            "metaphor — showing the depth of Italy's musical culture on the language."
        ),
        variants=(
            PhraseVariant(
                surface="toccata e fuga",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="è stata una toccata e fuga",
                match_type=MatchType.inflectional_variant,
                note="It was a flying visit.",
            ),
        ),
    ),

    "it_finire_in_bellezza": PhraseFamily(
        id="it_finire_in_bellezza",
        language="it",
        canonical_form="finire in bellezza",
        meaning="To end on a high note; to finish beautifully.",
        register="neutral",
        origin=(
            "Bellezza (beauty) as the ideal culmination — finishing in beauty means "
            "ending at one's best. Often used ironically when something ends badly: "
            "'abbiamo finito in bellezza' after a disaster."
        ),
        variants=(
            PhraseVariant(
                surface="finire in bellezza",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="abbiamo finito in bellezza",
                match_type=MatchType.inflectional_variant,
                note="We finished in style — often ironic.",
            ),
            PhraseVariant(
                surface="chiudere in bellezza",
                match_type=MatchType.inflectional_variant,
                note="Variant with chiudere (to close) — to close on a high note.",
            ),
        ),
    ),

    "it_partire_in_quarta": PhraseFamily(
        id="it_partire_in_quarta",
        language="it",
        canonical_form="partire in quarta",
        meaning="To start at full speed; to come out of the gate strong.",
        register="informal",
        origin=(
            "Quarta (fourth gear): starting in fourth gear (the highest on older "
            "manual transmissions) means launching immediately at maximum speed. A "
            "20th-century idiom rooted in car culture."
        ),
        variants=(
            PhraseVariant(
                surface="partire in quarta",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="è partito in quarta",
                match_type=MatchType.inflectional_variant,
                note="He came out of the gate at full speed — past tense.",
            ),
            PhraseVariant(
                surface="parte sempre in quarta",
                match_type=MatchType.inflectional_variant,
                note="He always jumps in headfirst.",
            ),
        ),
    ),

    "it_essere_in_ballo": PhraseFamily(
        id="it_essere_in_ballo",
        language="it",
        canonical_form="essere in ballo",
        meaning="To be involved; to be committed; once you're in, you're in.",
        register="neutral",
        origin=(
            "Ballo (ball, dance): once on the dance floor, you can't easily leave — "
            "the dance must be finished. The expression encodes commitment through "
            "the social obligation of the dance, a central institution in Italian "
            "social life."
        ),
        why_it_matters=(
            "Often used in the proverb 'chi è in ballo deve ballare' — if you're in "
            "the dance, you must dance. Knowing the fuller form enriches the "
            "standalone idiom."
        ),
        variants=(
            PhraseVariant(
                surface="essere in ballo",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="ci sono in ballo molti interessi",
                match_type=MatchType.inflectional_variant,
                note="Many interests are at stake.",
            ),
            PhraseVariant(
                surface="chi è in ballo deve ballare",
                match_type=MatchType.inflectional_variant,
                note="If you're in, you're in — the full proverb form.",
            ),
        ),
    ),

    "it_stare_fresco": PhraseFamily(
        id="it_stare_fresco",
        language="it",
        canonical_form="stare fresco",
        meaning=(
            "To be kidding oneself; to be in for a nasty surprise; to have another"
            "thing coming."
        ),
        register="informal",
        origin=(
            "Fresco (cool, fresh) used ironically: the 'coolness' is delusional "
            "comfort that will soon be shattered. Used to warn someone that their "
            "optimism is misplaced — 'stai fresco se credi che funziona' (you're "
            "dreaming if you think that works)."
        ),
        variants=(
            PhraseVariant(
                surface="stare fresco",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="stai fresco!",
                match_type=MatchType.inflectional_variant,
                note="You've got another thing coming! — exclamatory warning.",
            ),
            PhraseVariant(
                surface="se aspetta quello, sta fresco",
                match_type=MatchType.inflectional_variant,
                note="If he's waiting for that, he's dreaming.",
            ),
        ),
    ),

    "it_mandare_a_monte": PhraseFamily(
        id="it_mandare_a_monte",
        language="it",
        canonical_form="mandare a monte",
        meaning="To cause to fall through; to wreck a plan.",
        register="neutral",
        origin=(
            "Monte (mountain): sending something up the mountain — away from its goal "
            "— means scuppering it. A deal 'sent to the mountain' never returns to "
            "fruition. Widely used in business and everyday speech."
        ),
        variants=(
            PhraseVariant(
                surface="mandare a monte",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="ha mandato tutto a monte",
                match_type=MatchType.inflectional_variant,
                note="He wrecked everything — past tense.",
            ),
            PhraseVariant(
                surface="andare a monte",
                match_type=MatchType.inflectional_variant,
                note="To fall through — intransitive (the plan itself fails).",
            ),
        ),
    ),

    "it_aria_fritta": PhraseFamily(
        id="it_aria_fritta",
        language="it",
        canonical_form="aria fritta",
        meaning="Fried air; empty talk; nothing substantial.",
        register="informal",
        origin=(
            "Aria (air) + fritta (fried): you cannot fry air — it has no substance. "
            "'Selling fried air' means offering empty words, hollow promises, or "
            "useless content. A biting dismissal of verbosity without content."
        ),
        why_it_matters=(
            "Captures the Italian cultural value of substance over form — a culture "
            "with strong rhetorical tradition also has sharp idioms for calling out "
            "its absence."
        ),
        variants=(
            PhraseVariant(
                surface="aria fritta",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="vendere aria fritta",
                match_type=MatchType.inflectional_variant,
                note="To sell fried air — to peddle empty promises.",
            ),
            PhraseVariant(
                surface="è tutta aria fritta",
                match_type=MatchType.inflectional_variant,
                note="It's all hot air.",
            ),
        ),
    ),

    "it_fare_la_cresta": PhraseFamily(
        id="it_fare_la_cresta",
        language="it",
        canonical_form="fare la cresta sul burro",
        meaning="To skim off the top; to pocket a small cut; to help oneself quietly.",
        register="informal",
        origin=(
            "Cresta (crest, ridge) + burro (butter): when buying butter by weight, a "
            "dishonest vendor would build up a crest of extra butter, pocket it, and "
            "return the rest. The expression describes small-scale dishonest "
            "extraction — skimming without being caught."
        ),
        variants=(
            PhraseVariant(
                surface="fare la cresta sul burro",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="fare la cresta",
                match_type=MatchType.inflectional_variant,
                note="Shortened form — to take a little cut.",
            ),
        ),
    ),

    "it_avere_scheletri_nell_armadio": PhraseFamily(
        id="it_avere_scheletri_nell_armadio",
        language="it",
        canonical_form="avere scheletri nell'armadio",
        meaning="To have skeletons in the closet; to have shameful secrets.",
        register="neutral",
        origin=(
            "Scheletri nell'armadio (skeletons in the wardrobe): an image borrowed "
            "from English 'skeletons in the closet' — hidden shameful secrets. The "
            "Italian form uses 'armadio' (wardrobe/cupboard) rather than 'closet,' "
            "reflecting Italian domestic architecture."
        ),
        variants=(
            PhraseVariant(
                surface="avere scheletri nell'armadio",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="ha degli scheletri nell'armadio",
                match_type=MatchType.inflectional_variant,
                note="He/she has skeletons in the closet.",
            ),
            PhraseVariant(
                surface="scheletri nell'armadio",
                match_type=MatchType.inflectional_variant,
                note="Noun-phrase form — closet skeletons.",
            ),
        ),
    ),

    # ── Pt (generated) ────────────────────────────────────────

    "pt_agua_mole_em_pedra_dura": PhraseFamily(
        id="pt_agua_mole_em_pedra_dura",
        language="pt",
        canonical_form="água mole em pedra dura tanto bate até que fura",
        meaning=(
            "Persistence wears away resistance; soft water on hard stone will"
            "eventually bore through."
        ),
        register="neutral",
        origin=(
            "A proverb encoding the physical truth that water, though soft, erodes "
            "stone over time. Widely used in Portuguese and Brazilian culture to "
            "encourage perseverance. Parallel to English 'constant dripping wears "
            "away the stone.'"
        ),
        variants=(
            PhraseVariant(
                surface="água mole em pedra dura tanto bate até que fura",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="água mole em pedra dura",
                match_type=MatchType.inflectional_variant,
                note="Elliptical — the first half alone, understood to imply the full proverb.",
            ),
        ),
    ),

    "pt_nao_ha_bela_sem_serao": PhraseFamily(
        id="pt_nao_ha_bela_sem_serao",
        language="pt",
        canonical_form="não há bela sem senão",
        meaning="Every rose has its thorn; nothing is perfect.",
        register="neutral",
        origin=(
            "Bela (beautiful) + senão (but/however): every beautiful thing has a "
            "'but.' The wordplay — bela/senão forming a near-rhyme — makes this a "
            "memorable proverb. Common in Portugal and Brazil."
        ),
        variants=(
            PhraseVariant(
                surface="não há bela sem senão",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="nao ha bela sem senao",
                match_type=MatchType.orthographic_variant,
                note="Without diacritics, common in informal digital writing.",
            ),
        ),
    ),

    "pt_dar_com_a_lingua_nos_dentes": PhraseFamily(
        id="pt_dar_com_a_lingua_nos_dentes",
        language="pt",
        canonical_form="dar com a língua nos dentes",
        meaning="To let the cat out of the bag; to reveal a secret inadvertently.",
        register="informal",
        origin=(
            "Língua (tongue) + dentes (teeth): the tongue hits the teeth and produces "
            "sound — involuntary speech that gives away information. The "
            "physiological image captures how secrets escape through uncontrolled "
            "talking."
        ),
        variants=(
            PhraseVariant(
                surface="dar com a língua nos dentes",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="deu com a língua nos dentes",
                match_type=MatchType.inflectional_variant,
                note="He/she let the cat out of the bag — past tense.",
            ),
            PhraseVariant(
                surface="não vás dar com a língua nos dentes",
                match_type=MatchType.inflectional_variant,
                note="Don't go spilling the beans — warning.",
            ),
        ),
    ),

    "pt_falar_pelos_cotovelos": PhraseFamily(
        id="pt_falar_pelos_cotovelos",
        language="pt",
        canonical_form="falar pelos cotovelos",
        meaning="To talk one's ear off; to be a chatterbox.",
        register="informal",
        origin=(
            "Cotovelos (elbows): talking through one's elbows suggests such a volume "
            "of speech that it comes out from unexpected parts of the body. Spanish "
            "has the same image ('hablar por los codos'). Both Iberian languages "
            "share this vivid hyperbole."
        ),
        variants=(
            PhraseVariant(
                surface="falar pelos cotovelos",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="ela fala pelos cotovelos",
                match_type=MatchType.inflectional_variant,
                note="She never stops talking.",
            ),
        ),
    ),

    "pt_estar_com_os_azeites": PhraseFamily(
        id="pt_estar_com_os_azeites",
        language="pt",
        canonical_form="estar com os azeites",
        meaning="To be in a bad mood; to be irritable.",
        register="informal",
        origin=(
            "Azeites (olive oils): the expression is specifically Portuguese in "
            "origin. Olive oil turns rancid and becomes sharp and unpleasant — 'being "
            "with the oils' means being in a sour, irritable state."
        ),
        why_it_matters=(
            "Exclusively European Portuguese. Brazilian Portuguese uses different "
            "expressions for the same mood. Useful for learners differentiating "
            "registers across the two standard varieties."
        ),
        variants=(
            PhraseVariant(
                surface="estar com os azeites",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="hoje está com os azeites",
                match_type=MatchType.inflectional_variant,
                note="He/she's in a foul mood today.",
            ),
        ),
    ),

    "pt_em_bocas_fechadas_nao_entram_moscas": PhraseFamily(
        id="pt_em_bocas_fechadas_nao_entram_moscas",
        language="pt",
        canonical_form="em bocas fechadas não entram moscas",
        meaning="Loose lips sink ships; into closed mouths flies don't enter.",
        register="neutral",
        origin=(
            "Moscas (flies) + boca fechada (closed mouth): closing your mouth keeps "
            "out flies — and prevents you from saying things better left unsaid. A "
            "universal proverb found across Romance languages: Spanish 'en boca "
            "cerrada no entran moscas.'"
        ),
        variants=(
            PhraseVariant(
                surface="em bocas fechadas não entram moscas",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="boca fechada não pega mosca",
                match_type=MatchType.inflectional_variant,
                note="Brazilian variant — a closed mouth catches no flies.",
            ),
        ),
    ),

    "pt_comprar_gato_por_lebre": PhraseFamily(
        id="pt_comprar_gato_por_lebre",
        language="pt",
        canonical_form="comprar gato por lebre",
        meaning=(
            "To buy a pig in a poke; to be fooled into buying something other than"
            "what was promised."
        ),
        register="neutral",
        origin=(
            "Gato (cat) for lebre (hare): a swindler substituting a worthless cat for "
            "a prized hare. This is the same medieval market-fraud scenario as German "
            "'die Katze im Sack kaufen' — each language uses local animals to encode "
            "the deception."
        ),
        variants=(
            PhraseVariant(
                surface="comprar gato por lebre",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="vender gato por lebre",
                match_type=MatchType.inflectional_variant,
                note="To sell cat for hare — from the deceiver's perspective.",
            ),
        ),
    ),

    "pt_nao_ha_fumo_sem_fogo": PhraseFamily(
        id="pt_nao_ha_fumo_sem_fogo",
        language="pt",
        canonical_form="não há fumo sem fogo",
        meaning="There's no smoke without fire.",
        register="neutral",
        origin=(
            "A universal proverb found in virtually all European languages. "
            "Portuguese is 'não há fumo sem fogo,' matching English, French ('il n'y "
            "a pas de fumée sans feu'), and Spanish ('no hay humo sin fuego') exactly "
            "in structure."
        ),
        variants=(
            PhraseVariant(
                surface="não há fumo sem fogo",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="nao ha fumo sem fogo",
                match_type=MatchType.orthographic_variant,
                note="Without diacritics.",
            ),
        ),
    ),

    "pt_fazer_tempestade_num_copo_dagua": PhraseFamily(
        id="pt_fazer_tempestade_num_copo_dagua",
        language="pt",
        canonical_form="fazer tempestade num copo d'água",
        meaning="To make a mountain out of a molehill; to make a storm in a teacup.",
        register="neutral",
        origin=(
            "Tempestade (storm) in a copo d'água (glass of water): the impossibility "
            "of a storm in a glass emphasizes the absurd exaggeration of the fuss. "
            "Compare English 'storm in a teacup,' French 'tempête dans un verre "
            "d'eau.'"
        ),
        variants=(
            PhraseVariant(
                surface="fazer tempestade num copo d'água",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="tempestade em copo d'água",
                match_type=MatchType.inflectional_variant,
                note="Elliptical noun-phrase form.",
            ),
        ),
    ),

    "pt_o_habito_nao_faz_o_monge": PhraseFamily(
        id="pt_o_habito_nao_faz_o_monge",
        language="pt",
        canonical_form="o hábito não faz o monge",
        meaning="The habit does not make the monk; don't judge a book by its cover.",
        register="neutral",
        origin=(
            "A medieval European proverb in many languages: wearing a monk's habit "
            "doesn't make someone pious. The Latin source ('cucullus non facit "
            "monachum') was rendered into Portuguese as a warning against surface- "
            "level judgment."
        ),
        variants=(
            PhraseVariant(
                surface="o hábito não faz o monge",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="o habito nao faz o monge",
                match_type=MatchType.orthographic_variant,
                note="Without diacritics.",
            ),
        ),
    ),

    "pt_quem_semeia_ventos_colhe_tempestades": PhraseFamily(
        id="pt_quem_semeia_ventos_colhe_tempestades",
        language="pt",
        canonical_form="quem semeia ventos colhe tempestades",
        meaning=(
            "Sow the wind, reap the whirlwind; reckless actions bring severe"
            "consequences."
        ),
        register="neutral",
        origin=(
            "Biblical origin (Hosea 8:7). The agricultural metaphor of sowing and "
            "reaping — what you plant grows — applied to moral causality. Identical "
            "in structure across Romance languages."
        ),
        variants=(
            PhraseVariant(
                surface="quem semeia ventos colhe tempestades",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="semear ventos, colher tempestades",
                match_type=MatchType.inflectional_variant,
                note="Infinitive form used as a title or heading.",
            ),
        ),
    ),

    "pt_dor_de_cotovelo": PhraseFamily(
        id="pt_dor_de_cotovelo",
        language="pt",
        canonical_form="dor de cotovelo",
        meaning="Jealousy; heartburn of envy (especially romantic); feeling sidelined.",
        register="informal",
        origin=(
            "Cotovelo (elbow): 'elbow pain' — from the image of watching others "
            "succeed from the sidelines, leaning on your elbow. Primarily used in "
            "Brazil; the expression encodes envy, especially at another's success in "
            "love or career."
        ),
        why_it_matters=(
            "Quintessentially Brazilian in usage. 'Dor de cotovelo' music is a whole "
            "genre of sentimental Brazilian songs about heartbreak and jealousy."
        ),
        variants=(
            PhraseVariant(
                surface="dor de cotovelo",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="está com dor de cotovelo",
                match_type=MatchType.inflectional_variant,
                note="He/she is green with envy.",
            ),
            PhraseVariant(
                surface="música de dor de cotovelo",
                match_type=MatchType.inflectional_variant,
                note="Heartbreak music — extended collocational use.",
            ),
        ),
    ),

    "pt_meter_a_colher": PhraseFamily(
        id="pt_meter_a_colher",
        language="pt",
        canonical_form="meter a colher",
        meaning="To stick one's oar in; to butt in; to interfere in others' business.",
        register="informal",
        origin=(
            "Colher (spoon, ladle): inserting a spoon into someone else's cooking — "
            "interfering where you haven't been invited. The domestic kitchen image "
            "captures unwanted involvement in others' affairs."
        ),
        variants=(
            PhraseVariant(
                surface="meter a colher",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="não metas a colher",
                match_type=MatchType.inflectional_variant,
                note="Don't stick your nose in — imperative.",
            ),
            PhraseVariant(
                surface="sempre a meter a colher",
                match_type=MatchType.inflectional_variant,
                note="Always butting in.",
            ),
        ),
    ),

    "pt_bater_a_bota": PhraseFamily(
        id="pt_bater_a_bota",
        language="pt",
        canonical_form="bater a bota",
        meaning="To kick the bucket; to die.",
        register="informal",
        origin=(
            "Bota (boot): 'to hit the boot' is Portuguese slang for dying, parallel "
            "to English 'kick the bucket.' The exact origin of the boot image is "
            "uncertain, but it functions as an informal euphemism for death in both "
            "varieties of Portuguese."
        ),
        variants=(
            PhraseVariant(
                surface="bater a bota",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="bateu a bota",
                match_type=MatchType.inflectional_variant,
                note="He/she kicked the bucket — past tense.",
            ),
        ),
    ),

    "pt_estar_nas_nuvens": PhraseFamily(
        id="pt_estar_nas_nuvens",
        language="pt",
        canonical_form="estar nas nuvens",
        meaning="To have one's head in the clouds; to be daydreaming.",
        register="neutral",
        origin=(
            "Nuvens (clouds): to be in the clouds = to be mentally absent, floating "
            "above the practical world. Parallel expressions exist in Spanish ('estar "
            "en las nubes'), French ('avoir la tête dans les nuages'), and Italian."
        ),
        variants=(
            PhraseVariant(
                surface="estar nas nuvens",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="está nas nuvens",
                match_type=MatchType.inflectional_variant,
                note="He/she is daydreaming — present tense.",
            ),
            PhraseVariant(
                surface="anda nas nuvens",
                match_type=MatchType.inflectional_variant,
                note="He/she walks with head in clouds — with andar (to walk/go).",
            ),
        ),
    ),

    "pt_mais_vale_um_passaro_na_mao": PhraseFamily(
        id="pt_mais_vale_um_passaro_na_mao",
        language="pt",
        canonical_form="mais vale um pássaro na mão do que dois a voar",
        meaning="A bird in the hand is worth two in the bush.",
        register="neutral",
        origin=(
            "Portuguese version of the universal proverb. Pássaro (bird) + mão (hand) "
            "+ voar (flying): a secure possession is more valuable than uncertain "
            "prospects. Identical in logic to English, French, Spanish, and Italian "
            "equivalents."
        ),
        variants=(
            PhraseVariant(
                surface="mais vale um pássaro na mão do que dois a voar",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="mais vale um passaro na mao",
                match_type=MatchType.orthographic_variant,
                note="Elliptical form without diacritics.",
            ),
        ),
    ),

    "pt_dar_voltas_ao_miolo": PhraseFamily(
        id="pt_dar_voltas_ao_miolo",
        language="pt",
        canonical_form="dar voltas ao miolo",
        meaning="To rack one's brain; to think hard and go in circles.",
        register="informal",
        origin=(
            "Miolo (brain, crumb): 'turning the brain around' — the mental spinning "
            "of trying to solve a difficult problem. Miolo colloquially means both "
            "brain and the soft interior of bread, giving the expression earthy, "
            "familiar quality."
        ),
        why_it_matters=(
            "Characteristically Portuguese. The word miolo (instead of the more "
            "formal cérebro) anchors the expression in informal, everyday speech."
        ),
        variants=(
            PhraseVariant(
                surface="dar voltas ao miolo",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="dei muitas voltas ao miolo",
                match_type=MatchType.inflectional_variant,
                note="I racked my brain a lot — past tense.",
            ),
        ),
    ),

    "pt_por_em_pratos_limpos": PhraseFamily(
        id="pt_por_em_pratos_limpos",
        language="pt",
        canonical_form="pôr em pratos limpos",
        meaning="To lay the cards on the table; to clear things up; to get to the truth.",
        register="neutral",
        origin=(
            "Pratos limpos (clean plates): serving on clean plates means presenting "
            "things clearly, without the residue of prior meals/conversations "
            "clouding the view. A metaphor for clarity and directness."
        ),
        variants=(
            PhraseVariant(
                surface="pôr em pratos limpos",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="por em pratos limpos",
                match_type=MatchType.orthographic_variant,
                note="Without the circumflex on 'por' — common in informal writing.",
            ),
            PhraseVariant(
                surface="vamos pôr isto em pratos limpos",
                match_type=MatchType.inflectional_variant,
                note="Let's lay this on the table.",
            ),
        ),
    ),

    "pt_de_mal_a_pior": PhraseFamily(
        id="pt_de_mal_a_pior",
        language="pt",
        canonical_form="de mal a pior",
        meaning="From bad to worse.",
        register="neutral",
        origin=(
            "A direct and concise expression of deterioration. Parallel to English, "
            "French ('de mal en pis'), Spanish ('de mal en peor'). The simplicity of "
            "the phrase gives it wide applicability across contexts."
        ),
        variants=(
            PhraseVariant(
                surface="de mal a pior",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="vai de mal a pior",
                match_type=MatchType.inflectional_variant,
                note="It keeps going from bad to worse.",
            ),
        ),
    ),

    "pt_bater_o_pe": PhraseFamily(
        id="pt_bater_o_pe",
        language="pt",
        canonical_form="bater o pé",
        meaning="To put one's foot down; to insist firmly; to refuse to budge.",
        register="neutral",
        origin=(
            "Pé (foot): stomping one's foot is a universal physical gesture of "
            "insistence and refusal to yield. The expression captures the determined "
            "physical act as a metaphor for resolute verbal assertion."
        ),
        variants=(
            PhraseVariant(
                surface="bater o pé",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="bate o pé",
                match_type=MatchType.inflectional_variant,
                note="He/she is putting their foot down — present tense.",
            ),
            PhraseVariant(
                surface="bateu o pé",
                match_type=MatchType.inflectional_variant,
                note="He/she put their foot down — past tense.",
            ),
        ),
    ),

    "pt_estar_com_a_corda_no_pescoco": PhraseFamily(
        id="pt_estar_com_a_corda_no_pescoco",
        language="pt",
        canonical_form="estar com a corda no pescoço",
        meaning="To have a noose around one's neck; to be in a very tight spot.",
        register="neutral",
        origin=(
            "Corda no pescoço (rope around the neck): the image of imminent hanging — "
            "extreme pressure or danger. Used for financial crises, impossible "
            "deadlines, or hopeless situations. More vivid than English 'between a "
            "rock and a hard place.'"
        ),
        variants=(
            PhraseVariant(
                surface="estar com a corda no pescoço",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="está com a corda no pescoço",
                match_type=MatchType.inflectional_variant,
                note="He/she is in a real bind.",
            ),
        ),
    ),

    "pt_pregar_uma_rasteira": PhraseFamily(
        id="pt_pregar_uma_rasteira",
        language="pt",
        canonical_form="pregar uma rasteira",
        meaning="To trip someone up; to trick someone; to do something underhand.",
        register="informal",
        origin=(
            "Rasteira (trip, leg sweep): a fighting move that sweeps someone's legs "
            "from under them. Metaphorically, causing someone to fall or fail by "
            "means they didn't see coming — sabotage or treachery."
        ),
        variants=(
            PhraseVariant(
                surface="pregar uma rasteira",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="pregou-me uma rasteira",
                match_type=MatchType.inflectional_variant,
                note="He tripped me up / pulled a fast one on me.",
            ),
            PhraseVariant(
                surface="dar uma rasteira",
                match_type=MatchType.inflectional_variant,
                note="To trip up — with dar instead of pregar.",
            ),
        ),
    ),

    "pt_a_cavalo_dado_nao_se_olha_o_dente": PhraseFamily(
        id="pt_a_cavalo_dado_nao_se_olha_o_dente",
        language="pt",
        canonical_form="a cavalo dado não se olha o dente",
        meaning="Don't look a gift horse in the mouth.",
        register="neutral",
        origin=(
            "Cavalo (horse) + dente (tooth): a horse's age and health are assessed by "
            "its teeth — inspecting a gift horse's teeth implies ingratitude. "
            "Universal proverb: Latin 'noli equi dentes inspicere donati,' French 'à "
            "cheval donné on ne regarde pas les dents.'"
        ),
        variants=(
            PhraseVariant(
                surface="a cavalo dado não se olha o dente",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="a cavalo dado nao se olha o dente",
                match_type=MatchType.orthographic_variant,
                note="Without diacritics.",
            ),
        ),
    ),

    "pt_virar_a_mesa": PhraseFamily(
        id="pt_virar_a_mesa",
        language="pt",
        canonical_form="virar a mesa",
        meaning="To turn the tables; to completely reverse a situation.",
        register="neutral",
        origin=(
            "Mesa (table): to flip/turn the table — a dramatic reversal. Associated "
            "with card games or negotiations where overturning the table resets all "
            "terms. Common in Brazilian Portuguese especially in sports and business "
            "contexts."
        ),
        variants=(
            PhraseVariant(
                surface="virar a mesa",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="virou a mesa",
                match_type=MatchType.inflectional_variant,
                note="He/she turned the tables — past tense.",
            ),
        ),
    ),

    "pt_caiu_o_pano": PhraseFamily(
        id="pt_caiu_o_pano",
        language="pt",
        canonical_form="caiu o pano",
        meaning="The curtain fell; it's all over; the show is finished.",
        register="neutral",
        origin=(
            "Pano (curtain, cloth): theatrical metaphor — when the curtain drops, the "
            "performance ends. 'O pano caiu' signals an irreversible conclusion to "
            "any situation, not just theatrical ones."
        ),
        variants=(
            PhraseVariant(
                surface="caiu o pano",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="o pano caiu",
                match_type=MatchType.inflectional_variant,
                note="The curtain has fallen — word-order variant, same meaning.",
            ),
        ),
    ),

    "pt_pagar_com_a_mesma_moeda": PhraseFamily(
        id="pt_pagar_com_a_mesma_moeda",
        language="pt",
        canonical_form="pagar com a mesma moeda",
        meaning="To pay someone back in kind; tit for tat.",
        register="neutral",
        origin=(
            "Moeda (coin, currency): repaying with the same denomination — returning "
            "the exact same treatment received. The financial metaphor for "
            "reciprocity is universal across European languages."
        ),
        variants=(
            PhraseVariant(
                surface="pagar com a mesma moeda",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="pagou-lhe com a mesma moeda",
                match_type=MatchType.inflectional_variant,
                note="He paid him back in kind — past tense.",
            ),
        ),
    ),

    "pt_ir_ao_fundo_da_questao": PhraseFamily(
        id="pt_ir_ao_fundo_da_questao",
        language="pt",
        canonical_form="ir ao fundo da questão",
        meaning="To get to the bottom of the matter; to investigate thoroughly.",
        register="neutral",
        origin=(
            "Fundo (bottom, depth): the bottom of the question is where the truth "
            "lies. The spatial metaphor — depth = truth — is common across European "
            "languages. 'Getting to the bottom' implies rigorous investigation."
        ),
        variants=(
            PhraseVariant(
                surface="ir ao fundo da questão",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="ir ao fundo do assunto",
                match_type=MatchType.inflectional_variant,
                note="Variant with 'assunto' (matter/subject) instead of 'questão'.",
            ),
            PhraseVariant(
                surface="chegou ao fundo da questão",
                match_type=MatchType.inflectional_variant,
                note="He/she got to the bottom of it — past tense.",
            ),
        ),
    ),

    "pt_ter_os_nervos_a_flor_da_pele": PhraseFamily(
        id="pt_ter_os_nervos_a_flor_da_pele",
        language="pt",
        canonical_form="ter os nervos à flor da pele",
        meaning=(
            "To be on edge; to be hypersensitive; to have one's nerves right at the"
            "skin's surface."
        ),
        register="neutral",
        origin=(
            "Flor da pele (flower of the skin, skin's surface): nerves so close to "
            "the surface that any touch triggers a reaction. A beautiful anatomical "
            "metaphor for heightened emotional sensitivity. The flor (flower) image "
            "adds a delicate quality to what is essentially raw vulnerability."
        ),
        variants=(
            PhraseVariant(
                surface="ter os nervos à flor da pele",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="com os nervos à flor da pele",
                match_type=MatchType.inflectional_variant,
                note="With nerves on edge — adverbial.",
            ),
            PhraseVariant(
                surface="está com os nervos à flor da pele",
                match_type=MatchType.inflectional_variant,
                note="He/she is on edge.",
            ),
        ),
    ),

    "pt_estar_de_pedra_e_cal": PhraseFamily(
        id="pt_estar_de_pedra_e_cal",
        language="pt",
        canonical_form="estar de pedra e cal",
        meaning="To be set in stone; absolutely certain; fixed and immovable.",
        register="neutral",
        origin=(
            "Pedra e cal (stone and lime mortar): the combination used to build walls "
            "that last centuries. Something 'of stone and mortar' cannot be shifted. "
            "The construction metaphor conveys absolute permanence of a decision or "
            "fact."
        ),
        variants=(
            PhraseVariant(
                surface="estar de pedra e cal",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="é de pedra e cal",
                match_type=MatchType.inflectional_variant,
                note="It's set in stone.",
            ),
            PhraseVariant(
                surface="isso é pedra e cal",
                match_type=MatchType.inflectional_variant,
                note="That's final — emphatic.",
            ),
        ),
    ),

    "pt_nem_de_proposito": PhraseFamily(
        id="pt_nem_de_proposito",
        language="pt",
        canonical_form="nem de propósito",
        meaning=(
            "As if on purpose; what a coincidence; it couldn't have been planned"
            "better."
        ),
        register="informal",
        origin=(
            "Propósito (purpose, intention): 'not even on purpose' describes a "
            "coincidence so perfect it seems intentional. Often used with exclamation "
            "to express surprised delight or irony at an apt coincidence."
        ),
        variants=(
            PhraseVariant(
                surface="nem de propósito",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="nem de proposito",
                match_type=MatchType.orthographic_variant,
                note="Without accent — common in digital writing.",
            ),
            PhraseVariant(
                surface="parece que foi de propósito",
                match_type=MatchType.inflectional_variant,
                note="It seems like it was done on purpose — related expression.",
            ),
        ),
    ),

    "pt_andar_na_crista_da_onda": PhraseFamily(
        id="pt_andar_na_crista_da_onda",
        language="pt",
        canonical_form="andar na crista da onda",
        meaning="To be riding the crest of a wave; to be at the top of one's game.",
        register="neutral",
        origin=(
            "Crista da onda (wave crest): surfing on the highest point of a wave — "
            "maximum momentum and visibility. Portugal's Atlantic coastline makes "
            "wave imagery natural and resonant. Used of careers, trends, and "
            "popularity."
        ),
        variants=(
            PhraseVariant(
                surface="andar na crista da onda",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="está na crista da onda",
                match_type=MatchType.inflectional_variant,
                note="He/she is on top of the world right now.",
            ),
        ),
    ),

    "pt_quem_nao_chora_nao_mama": PhraseFamily(
        id="pt_quem_nao_chora_nao_mama",
        language="pt",
        canonical_form="quem não chora não mama",
        meaning="The squeaky wheel gets the grease; you have to ask for what you want.",
        register="neutral",
        origin=(
            "Mamar (to nurse/suckle): the baby who doesn't cry doesn't get fed. A "
            "proverb about the necessity of expressing needs. Common in Brazil "
            "especially. Contrasts with more reserved cultural ideals about not "
            "complaining."
        ),
        why_it_matters=(
            "A particularly useful expression for learners navigating Brazilian "
            "professional culture, where self-advocacy is important."
        ),
        variants=(
            PhraseVariant(
                surface="quem não chora não mama",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="quem nao chora nao mama",
                match_type=MatchType.orthographic_variant,
                note="Without diacritics.",
            ),
        ),
    ),

    "pt_tirar_o_sono": PhraseFamily(
        id="pt_tirar_o_sono",
        language="pt",
        canonical_form="tirar o sono a alguém",
        meaning="To keep someone up at night; to worry someone greatly.",
        register="neutral",
        origin=(
            "Sono (sleep): to remove someone's sleep = to be a source of such anxiety "
            "that they cannot rest. The expression captures both the physiological "
            "(sleeplessness) and emotional (worry) dimensions of a problem."
        ),
        variants=(
            PhraseVariant(
                surface="tirar o sono a alguém",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="isso tira-me o sono",
                match_type=MatchType.inflectional_variant,
                note="That keeps me up at night.",
            ),
            PhraseVariant(
                surface="não vou deixar isso tirar-me o sono",
                match_type=MatchType.inflectional_variant,
                note="I won't lose sleep over it.",
            ),
        ),
    ),

    "pt_colocar_os_pontos_nos_is": PhraseFamily(
        id="pt_colocar_os_pontos_nos_is",
        language="pt",
        canonical_form="colocar os pontos nos i's",
        meaning="To dot the i's and cross the t's; to be precise and thorough.",
        register="neutral",
        origin=(
            "Pontos nos i's (dots on the i's): the typographic act of completing "
            "letters carefully. In Portuguese, only the i's are mentioned (unlike "
            "English 'dot the i's and cross the t's'), but the meaning — thoroughness "
            "— is identical."
        ),
        variants=(
            PhraseVariant(
                surface="colocar os pontos nos i's",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="pôr os pontos nos i's",
                match_type=MatchType.inflectional_variant,
                note="Variant with pôr (to put) instead of colocar.",
            ),
        ),
    ),

    "pt_dar_a_volta_por_cima": PhraseFamily(
        id="pt_dar_a_volta_por_cima",
        language="pt",
        canonical_form="dar a volta por cima",
        meaning="To bounce back; to make a comeback after a setback.",
        register="neutral",
        origin=(
            "Volta por cima (turn from above): overcoming the obstacle by rising "
            "above it and coming out on top. Specifically Brazilian in flavor, "
            "associated with resilience and comeback narratives in sports, politics, "
            "and personal life."
        ),
        why_it_matters=(
            "Highly frequent in Brazilian media and everyday speech. Captures the "
            "Brazilian cultural value of resilience and positivity in the face of "
            "adversity — closely related to the concept of jogo bonito."
        ),
        variants=(
            PhraseVariant(
                surface="dar a volta por cima",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="deu a volta por cima",
                match_type=MatchType.inflectional_variant,
                note="He/she bounced back — past tense.",
            ),
        ),
    ),

    "pt_estar_entre_a_espada_e_a_parede": PhraseFamily(
        id="pt_estar_entre_a_espada_e_a_parede",
        language="pt",
        canonical_form="estar entre a espada e a parede",
        meaning="To be between a rock and a hard place; caught between two bad options.",
        register="neutral",
        origin=(
            "Espada (sword) + parede (wall): pressed against a wall with a sword at "
            "your front — no escape route, forced to choose the lesser of two "
            "dangers. More physically vivid than English's geological metaphor."
        ),
        variants=(
            PhraseVariant(
                surface="estar entre a espada e a parede",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="entre a espada e a parede",
                match_type=MatchType.inflectional_variant,
                note="Elliptical predicative use.",
            ),
            PhraseVariant(
                surface="estou entre a espada e a parede",
                match_type=MatchType.inflectional_variant,
                note="I'm between a rock and a hard place.",
            ),
        ),
    ),

    "pt_mandar_as_favas": PhraseFamily(
        id="pt_mandar_as_favas",
        language="pt",
        canonical_form="mandar às favas",
        meaning="To tell someone to get lost; to dismiss rudely.",
        register="informal",
        origin=(
            "Favas (broad beans): a remote, insignificant place associated with "
            "peasant food. Sending someone 'to the beans' dismisses them as "
            "worthless. Parallel to English 'go fly a kite' or Spanish 'mandar a "
            "paseo.' The bean imagery is distinctively Iberian."
        ),
        variants=(
            PhraseVariant(
                surface="mandar às favas",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="vai às favas",
                match_type=MatchType.inflectional_variant,
                note="Get lost — imperative.",
            ),
            PhraseVariant(
                surface="mandou-o às favas",
                match_type=MatchType.inflectional_variant,
                note="He/she told him to get lost — past tense.",
            ),
        ),
    ),

    # ── Ru (generated) ────────────────────────────────────────

    "ru_sdelat_iz_mukhi_slona": PhraseFamily(
        id="ru_sdelat_iz_mukhi_slona",
        language="ru",
        canonical_form="делать из мухи слона",
        meaning=(
            "To make a mountain out of a molehill; to blow something out of"
            "proportion."
        ),
        register="informal",
        origin=(
            "Муха (fly) → слон (elephant): turning the tiniest insect into the "
            "largest land animal. A satirical image of grotesque exaggeration. "
            "Attributed to Lucian of Samosata (2nd century AD) in his essay 'The Fly' "
            "— one of the oldest recorded idioms still in common use."
        ),
        why_it_matters=(
            "One of the most beloved Russian idioms. The extreme contrast (fly vs. "
            "elephant) makes it instantly memorable. The animal pairing reflects "
            "Russian fondness for vivid, asymmetric animal-based metaphors."
        ),
        variants=(
            PhraseVariant(
                surface="делать из мухи слона",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="делает из мухи слона",
                match_type=MatchType.inflectional_variant,
                note="He/she makes a mountain out of a molehill — present tense.",
            ),
            PhraseVariant(
                surface="не надо делать из мухи слона",
                match_type=MatchType.inflectional_variant,
                note="Don't blow it out of proportion.",
            ),
        ),
    ),

    "ru_vyvesti_na_chistuyu_vodu": PhraseFamily(
        id="ru_vyvesti_na_chistuyu_vodu",
        language="ru",
        canonical_form="вывести на чистую воду",
        meaning="To bring to light; to expose someone's wrongdoing; to unmask.",
        register="neutral",
        origin=(
            "Чистая вода (clean water): bringing something out of murky depths into "
            "clear, transparent water where it can be seen clearly. The fishing "
            "metaphor — pulling hidden things to the surface — implies that deception "
            "cannot survive scrutiny."
        ),
        variants=(
            PhraseVariant(
                surface="вывести на чистую воду",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="вывел его на чистую воду",
                match_type=MatchType.inflectional_variant,
                note="He exposed him — past tense.",
            ),
        ),
    ),

    "ru_kak_grom_sredi_yasnogo_neba": PhraseFamily(
        id="ru_kak_grom_sredi_yasnogo_neba",
        language="ru",
        canonical_form="как гром среди ясного неба",
        meaning="Like a bolt from the blue; completely unexpected.",
        register="neutral",
        origin=(
            "Гром (thunder) среди ясного неба (clear sky): thunder without visible "
            "clouds is impossible — a natural impossibility used to describe total "
            "surprise. Parallel to English 'bolt from the blue.'"
        ),
        variants=(
            PhraseVariant(
                surface="как гром среди ясного неба",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="гром среди ясного неба",
                match_type=MatchType.inflectional_variant,
                note="Elliptical — without the simile marker 'как'.",
            ),
            PhraseVariant(
                surface="как гром с ясного неба",
                match_type=MatchType.inflectional_variant,
                note="Variant with genitive 'с ясного неба' — from a clear sky.",
            ),
        ),
    ),

    "ru_khorosho_smeyotsya_kto_smeyotsya_posled": PhraseFamily(
        id="ru_khorosho_smeyotsya_kto_smeyotsya_posled",
        language="ru",
        canonical_form="хорошо смеётся тот, кто смеётся последним",
        meaning="He who laughs last laughs best.",
        register="neutral",
        origin=(
            "A proverb warning against premature celebration. Found across European "
            "languages. The Russian form emphasizes the quality of the final laugh "
            "('хорошо смеётся' = laughs well) rather than just its timing."
        ),
        variants=(
            PhraseVariant(
                surface="хорошо смеётся тот, кто смеётся последним",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="смеётся тот, кто смеётся последним",
                match_type=MatchType.inflectional_variant,
                note="Shortened form without 'хорошо'.",
            ),
        ),
    ),

    "ru_ne_pluy_v_kolodets": PhraseFamily(
        id="ru_ne_pluy_v_kolodets",
        language="ru",
        canonical_form="не плюй в колодец — пригодится воды напиться",
        meaning=(
            "Don't bite the hand that feeds you; don't spit in the well you may need"
            "to drink from."
        ),
        register="neutral",
        origin=(
            "Колодец (well): the village well was a common resource — fouling it "
            "harmed everyone, including yourself. The proverb encodes prudence and "
            "community interdependence. The folk wisdom is almost universally "
            "recognized in Russian culture."
        ),
        variants=(
            PhraseVariant(
                surface="не плюй в колодец — пригодится воды напиться",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="не плюй в колодец",
                match_type=MatchType.inflectional_variant,
                note="Elliptical — the first half alone, well understood.",
            ),
        ),
    ),

    "ru_snyat_slivki": PhraseFamily(
        id="ru_snyat_slivki",
        language="ru",
        canonical_form="снять сливки",
        meaning="To skim the cream; to take the best part for oneself.",
        register="neutral",
        origin=(
            "Сливки (cream): cream rises to the top of fresh milk. Skimming it off "
            "first gets the richest, most valuable portion. The expression applies to "
            "taking the best opportunities, the most profitable deals, or the most "
            "desirable partners."
        ),
        variants=(
            PhraseVariant(
                surface="снять сливки",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="снял сливки",
                match_type=MatchType.inflectional_variant,
                note="He skimmed the cream — took the best for himself.",
            ),
            PhraseVariant(
                surface="снимать сливки",
                match_type=MatchType.inflectional_variant,
                note="Imperfective form — habitually skimming.",
            ),
        ),
    ),

    "ru_okazatsya_u_razbitogo_koryta": PhraseFamily(
        id="ru_okazatsya_u_razbitogo_koryta",
        language="ru",
        canonical_form="оказаться у разбитого корыта",
        meaning=(
            "To end up back at square one with nothing; to be left with a broken"
            "trough."
        ),
        register="neutral",
        origin=(
            "From Pushkin's 'The Tale of the Fisherman and the Fish' (1833): the "
            "greedy old woman demands ever more from the magic fish until it takes "
            "everything back, leaving her at the broken trough (разбитое корыто) she "
            "started with."
        ),
        why_it_matters=(
            "Directly from Pushkin — one of the most literate Russian idioms. Knowing "
            "its source shows the depth of classical literature in Russian everyday "
            "speech."
        ),
        variants=(
            PhraseVariant(
                surface="оказаться у разбитого корыта",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="у разбитого корыта",
                match_type=MatchType.inflectional_variant,
                note="Elliptical — back to square one, having lost everything.",
            ),
            PhraseVariant(
                surface="остаться у разбитого корыта",
                match_type=MatchType.inflectional_variant,
                note="To be left with nothing — with 'остаться' (to be left).",
            ),
        ),
    ),

    "ru_toloch_vodu_v_stupe": PhraseFamily(
        id="ru_toloch_vodu_v_stupe",
        language="ru",
        canonical_form="толочь воду в ступе",
        meaning="To pound water in a mortar; to do pointless, unproductive work.",
        register="neutral",
        origin=(
            "Ступа (mortar): pounding water — which cannot be ground — is the "
            "ultimate futile task. The image is ancient, appearing in Erasmus's "
            "Adages ('in aqua scribis') and Russian folk usage. The mortar evokes "
            "traditional village life."
        ),
        variants=(
            PhraseVariant(
                surface="толочь воду в ступе",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="это всё равно что толочь воду в ступе",
                match_type=MatchType.inflectional_variant,
                note="It's like pounding water in a mortar — this is useless.",
            ),
        ),
    ),

    "ru_kak_syr_v_masle": PhraseFamily(
        id="ru_kak_syr_v_masle",
        language="ru",
        canonical_form="как сыр в масле кататься",
        meaning="Like cheese rolling in butter; to live in luxury and comfort.",
        register="informal",
        origin=(
            "Сыр (cheese) rolling in масло (butter) — immersed in richness, "
            "effortlessly gliding through plenty. A deliciously food-centered image "
            "of prosperity. The verb 'кататься' (to roll/ride) suggests effortless "
            "movement through wealth."
        ),
        variants=(
            PhraseVariant(
                surface="как сыр в масле кататься",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="живёт как сыр в масле",
                match_type=MatchType.inflectional_variant,
                note="He/she lives like a king — like cheese in butter.",
            ),
            PhraseVariant(
                surface="как сыр в масле",
                match_type=MatchType.inflectional_variant,
                note="Elliptical adverbial form.",
            ),
        ),
    ),

    "ru_myt_kosti": PhraseFamily(
        id="ru_myt_kosti",
        language="ru",
        canonical_form="мыть кости",
        meaning="To gossip about someone; to wash someone's bones behind their back.",
        register="informal",
        origin=(
            "From the ancient ritual of washing the bones of the dead before reburial "
            "— a practice that involved the whole community discussing the deceased's "
            "life and character. 'Washing bones' transferred to talking about living "
            "people behind their backs."
        ),
        variants=(
            PhraseVariant(
                surface="мыть кости",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="перемывать кости",
                match_type=MatchType.inflectional_variant,
                note="To re-wash the bones — to gossip repeatedly, more intensive form.",
            ),
            PhraseVariant(
                surface="моют ему кости",
                match_type=MatchType.inflectional_variant,
                note="They're gossiping about him.",
            ),
        ),
    ),

    "ru_ne_v_konya_korm": PhraseFamily(
        id="ru_ne_v_konya_korm",
        language="ru",
        canonical_form="не в коня корм",
        meaning=(
            "The fodder is wasted on that horse; effort wasted on someone who doesn't"
            "appreciate it."
        ),
        register="informal",
        origin=(
            "Конь (horse) + корм (fodder/feed): expensive feed given to a horse that "
            "cannot benefit from it is wasted. The expression implies that education, "
            "generosity, or quality are squandered on someone unworthy or "
            "unappreciative."
        ),
        variants=(
            PhraseVariant(
                surface="не в коня корм",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="ему не в коня корм",
                match_type=MatchType.inflectional_variant,
                note="It's wasted on him — he doesn't appreciate it.",
            ),
        ),
    ),

    "ru_rezat_pravdu_matku": PhraseFamily(
        id="ru_rezat_pravdu_matku",
        language="ru",
        canonical_form="резать правду-матку",
        meaning="To tell it like it is; to speak blunt, unvarnished truth.",
        register="informal",
        origin=(
            "Правда-матка: 'mother truth' — the raw, unembellished truth in its most "
            "potent form. 'Резать' (to cut) suggests the sharpness and directness of "
            "such speech. A characteristically Russian valorization of blunt honesty "
            "over diplomatic softening."
        ),
        why_it_matters=(
            "The compound 'правда-матка' is itself culturally rich — matka (mother) "
            "here suggests the pure, original form of truth, not dressed up or "
            "softened."
        ),
        variants=(
            PhraseVariant(
                surface="резать правду-матку",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="режет правду-матку",
                match_type=MatchType.inflectional_variant,
                note="He/she tells it straight — present tense.",
            ),
            PhraseVariant(
                surface="говорить правду-матку в глаза",
                match_type=MatchType.inflectional_variant,
                note="To tell the truth to someone's face — direct confrontation form.",
            ),
        ),
    ),

    "ru_kogda_rak_na_gore_svistnet": PhraseFamily(
        id="ru_kogda_rak_na_gore_svistnet",
        language="ru",
        canonical_form="когда рак на горе свистнет",
        meaning="When pigs fly; when the crayfish whistles on the mountain.",
        register="informal",
        origin=(
            "Рак (crayfish) + гора (mountain) + свистнуть (to whistle): crayfish "
            "cannot whistle, especially not on a mountain (their natural habitat is "
            "water). An impossible scenario encodes 'never.' Compare English 'when "
            "pigs fly,' German 'wenn Schweine fliegen.'"
        ),
        why_it_matters=(
            "Each culture has its own 'impossible animal scenario' for 'never.' The "
            "Russian crayfish is one of the most recognizable and beloved. It "
            "highlights how absurdist animal imagery is a cross-cultural mechanism "
            "for expressing impossibility."
        ),
        variants=(
            PhraseVariant(
                surface="когда рак на горе свистнет",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="когда рак свистнет",
                match_type=MatchType.inflectional_variant,
                note="Shortened form — when the crayfish whistles.",
            ),
        ),
    ),

    "ru_brosit_perchatku": PhraseFamily(
        id="ru_brosit_perchatku",
        language="ru",
        canonical_form="бросить перчатку",
        meaning="To throw down the gauntlet; to issue a challenge.",
        register="neutral",
        origin=(
            "Перчатка (glove, gauntlet): in medieval European knight culture, "
            "throwing a glove was a formal challenge to a duel. The expression "
            "entered Russian via French chivalric culture and retains its combative "
            "connotation in modern usage."
        ),
        variants=(
            PhraseVariant(
                surface="бросить перчатку",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="бросить кому-то перчатку",
                match_type=MatchType.inflectional_variant,
                note="To throw down the gauntlet to someone — with dative recipient.",
            ),
            PhraseVariant(
                surface="подобрать перчатку",
                match_type=MatchType.inflectional_variant,
                note="To pick up the gauntlet — to accept the challenge.",
            ),
        ),
    ),

    "ru_za_dvumya_zaycami": PhraseFamily(
        id="ru_za_dvumya_zaycami",
        language="ru",
        canonical_form="за двумя зайцами погонишься — ни одного не поймаешь",
        meaning=(
            "Chase two hares and you'll catch neither; don't try to do two things at"
            "once."
        ),
        register="neutral",
        origin=(
            "Заяц (hare): a fast, evasive animal. Chasing two simultaneously splits "
            "one's focus and dooms both pursuits. A proverb of singular focus and the "
            "danger of divided attention. Parallel to Chinese and Latin proverbial "
            "wisdom on the same theme."
        ),
        variants=(
            PhraseVariant(
                surface="за двумя зайцами погонишься — ни одного не поймаешь",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="за двумя зайцами",
                match_type=MatchType.inflectional_variant,
                note="Elliptical — the first clause alone, understood to imply the full proverb.",
            ),
            PhraseVariant(
                surface="гнаться за двумя зайцами",
                match_type=MatchType.inflectional_variant,
                note="To chase two hares — infinitive form.",
            ),
        ),
    ),

    "ru_staraya_pesnya_na_novyy_lad": PhraseFamily(
        id="ru_staraya_pesnya_na_novyy_lad",
        language="ru",
        canonical_form="старая песня на новый лад",
        meaning="Old wine in new bottles; the same old story in a new guise.",
        register="neutral",
        origin=(
            "Старая песня (old song) на новый лад (in a new style/tune): the song "
            "hasn't changed, only its arrangement. The expression captures "
            "superficial novelty over fundamental sameness — a new style masking "
            "unchanged content."
        ),
        variants=(
            PhraseVariant(
                surface="старая песня на новый лад",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="всё та же старая песня",
                match_type=MatchType.inflectional_variant,
                note="Same old story — same old song.",
            ),
        ),
    ),

    "ru_golyi_kak_sokol": PhraseFamily(
        id="ru_golyi_kak_sokol",
        language="ru",
        canonical_form="гол как сокол",
        meaning="Stone broke; penniless; bare as a falcon.",
        register="informal",
        origin=(
            "Сокол (falcon) + гол (naked/bare): falcons have smooth, streamlined "
            "plumage — nothing hidden in their feathers. But the expression may also "
            "derive from 'сокол' as a medieval battering ram of bare metal. Either "
            "way, 'bare as a falcon' = having nothing."
        ),
        variants=(
            PhraseVariant(
                surface="гол как сокол",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="гол как сокол остался",
                match_type=MatchType.inflectional_variant,
                note="Left without a penny to his name.",
            ),
        ),
    ),

    "ru_v_tikhom_omute_cherti_vodyatsya": PhraseFamily(
        id="ru_v_tikhom_omute_cherti_vodyatsya",
        language="ru",
        canonical_form="в тихом омуте черти водятся",
        meaning="Still waters run deep; beware the quiet ones.",
        register="neutral",
        origin=(
            "Омут (still pool, deep water) + черти (devils): in Russian folklore, "
            "devils and water spirits (водяные) lurk in deep, still pools — not in "
            "noisy rapids. The expression warns that quiet exteriors hide dark "
            "depths."
        ),
        why_it_matters=(
            "The Russian version is notably darker than English 'still waters run "
            "deep' — explicitly mentioning devils. It reveals the folk-superstition "
            "layer underlying everyday Russian idiom."
        ),
        variants=(
            PhraseVariant(
                surface="в тихом омуте черти водятся",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="в тихом омуте черти",
                match_type=MatchType.inflectional_variant,
                note="Elliptical — still waters run deep.",
            ),
        ),
    ),

    "ru_u_semi_nyanek_ditya_bez_glaza": PhraseFamily(
        id="ru_u_semi_nyanek_ditya_bez_glaza",
        language="ru",
        canonical_form="у семи нянек дитя без глаза",
        meaning=(
            "Too many cooks spoil the broth; with seven nannies the child is left"
            "unsupervised."
        ),
        register="neutral",
        origin=(
            "Нянька (nanny) + дитя (child): seven nannies for one child — each "
            "assumes the others are watching, and the child is left without "
            "supervision. The proverb encodes collective irresponsibility through "
            "distributed accountability."
        ),
        variants=(
            PhraseVariant(
                surface="у семи нянек дитя без глаза",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="семь нянек",
                match_type=MatchType.inflectional_variant,
                note="Shorthand reference — seven nannies (implying the full proverb).",
            ),
        ),
    ),

    "ru_rvat_na_sebe_volosy": PhraseFamily(
        id="ru_rvat_na_sebe_volosy",
        language="ru",
        canonical_form="рвать на себе волосы",
        meaning="To tear one's hair out; to be in extreme distress or regret.",
        register="neutral",
        origin=(
            "Physically tearing one's hair is an ancient grief gesture documented "
            "across Middle Eastern and classical cultures (Jeremiah, Ezra, Homer). "
            "Russian preserves the image as a metaphor for any extreme self-reproach "
            "or regret."
        ),
        variants=(
            PhraseVariant(
                surface="рвать на себе волосы",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="рвёт на себе волосы",
                match_type=MatchType.inflectional_variant,
                note="He/she is tearing their hair out — present tense.",
            ),
            PhraseVariant(
                surface="теперь рви на себе волосы",
                match_type=MatchType.inflectional_variant,
                note="Now you can tear your hair out — done out of regret.",
            ),
        ),
    ),

    "ru_sidet_na_dvukh_stulyakh": PhraseFamily(
        id="ru_sidet_na_dvukh_stulyakh",
        language="ru",
        canonical_form="сидеть на двух стульях",
        meaning=(
            "To sit on two chairs; to try to please two opposing parties; to have it"
            "both ways."
        ),
        register="neutral",
        origin=(
            "Стул (chair): sitting between two chairs — with each buttock on a "
            "different seat — is physically precarious and ultimately untenable. The "
            "image captures the impossibility of simultaneously serving two "
            "incompatible masters."
        ),
        variants=(
            PhraseVariant(
                surface="сидеть на двух стульях",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="нельзя сидеть на двух стульях",
                match_type=MatchType.inflectional_variant,
                note="You can't have it both ways — negated form.",
            ),
            PhraseVariant(
                surface="сидит на двух стульях",
                match_type=MatchType.inflectional_variant,
                note="He's trying to please everyone.",
            ),
        ),
    ),

    "ru_stavit_telegu_vperedi_loshadi": PhraseFamily(
        id="ru_stavit_telegu_vperedi_loshadi",
        language="ru",
        canonical_form="ставить телегу впереди лошади",
        meaning="To put the cart before the horse.",
        register="neutral",
        origin=(
            "Телега (cart) + лошадь (horse): placing the cart before the horse "
            "reverses the proper order. Russian shares this proverb with virtually "
            "all European languages — a logical error made vivid through concrete "
            "imagery."
        ),
        variants=(
            PhraseVariant(
                surface="ставить телегу впереди лошади",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="телегу поставил впереди лошади",
                match_type=MatchType.inflectional_variant,
                note="He put the cart before the horse — past tense.",
            ),
        ),
    ),

    "ru_net_dyma_bez_ognya": PhraseFamily(
        id="ru_net_dyma_bez_ognya",
        language="ru",
        canonical_form="нет дыма без огня",
        meaning="There's no smoke without fire.",
        register="neutral",
        origin=(
            "A universal European proverb. Дым (smoke) + огонь (fire): smoke cannot "
            "exist without fire — rumors typically have some basis in truth. The "
            "Russian form exactly parallels English, French, German, Spanish, "
            "Italian, and Portuguese equivalents."
        ),
        variants=(
            PhraseVariant(
                surface="нет дыма без огня",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="без огня дыма не бывает",
                match_type=MatchType.inflectional_variant,
                note="Variant word order: without fire there is no smoke.",
            ),
        ),
    ),

    "ru_ne_govori_gop": PhraseFamily(
        id="ru_ne_govori_gop",
        language="ru",
        canonical_form="не говори «гоп», пока не перепрыгнешь",
        meaning=(
            "Don't count your chickens before they hatch; don't say 'hop' until"
            "you've jumped."
        ),
        register="neutral",
        origin=(
            "Гоп (hop) is the exclamation made when jumping over an obstacle. Saying "
            "it before completing the jump tempts fate — the proverb warns against "
            "premature celebration of future success."
        ),
        variants=(
            PhraseVariant(
                surface="не говори «гоп», пока не перепрыгнешь",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="не говори гоп",
                match_type=MatchType.inflectional_variant,
                note="Shortened imperative — don't count your chickens.",
            ),
        ),
    ),

    "ru_za_semiyu_zamkami": PhraseFamily(
        id="ru_za_semiyu_zamkami",
        language="ru",
        canonical_form="за семью замками",
        meaning="Under seven locks; deeply secret; heavily guarded.",
        register="neutral",
        origin=(
            "Семь замков (seven locks): seven is the number of completeness in Slavic "
            "folk tradition. Something sealed with seven locks is maximally secured — "
            "the number emphasizes total inaccessibility rather than a literal count "
            "of locks."
        ),
        why_it_matters=(
            "The number seven recurs in Russian folklore ('за семью морями,' 'семь "
            "пятниц') in ways that differ from English. Understanding this helps "
            "learners recognize the cultural weight of 'семь' in Russian idiom."
        ),
        variants=(
            PhraseVariant(
                surface="за семью замками",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="держать за семью замками",
                match_type=MatchType.inflectional_variant,
                note="To keep under seven locks — to keep deeply secret.",
            ),
            PhraseVariant(
                surface="под семью замками",
                match_type=MatchType.inflectional_variant,
                note="Under seven locks — variant with 'под' (under).",
            ),
        ),
    ),

    "ru_razbit_v_pukh_i_prak": PhraseFamily(
        id="ru_razbit_v_pukh_i_prak",
        language="ru",
        canonical_form="разбить в пух и прах",
        meaning="To smash to smithereens; to utterly destroy or defeat.",
        register="neutral",
        origin=(
            "Пух (down, fluff) + прах (dust, ashes): reducing something to feathers "
            "and ash — the lightest, most dissipated substances. A total destruction "
            "so complete nothing substantial remains. Used of military defeats, "
            "arguments, and business failures."
        ),
        variants=(
            PhraseVariant(
                surface="разбить в пух и прах",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="разнести в пух и прах",
                match_type=MatchType.inflectional_variant,
                note="Variant with 'разнести' (to scatter/blast) — same meaning.",
            ),
            PhraseVariant(
                surface="разбит в пух и прах",
                match_type=MatchType.inflectional_variant,
                note="Was smashed to smithereens — passive/past.",
            ),
        ),
    ),

    "ru_odin_v_pole_ne_voin": PhraseFamily(
        id="ru_odin_v_pole_ne_voin",
        language="ru",
        canonical_form="один в поле не воин",
        meaning="One man in a field is not a warrior; no man is an island.",
        register="neutral",
        origin=(
            "A military proverb: a single soldier on a battlefield cannot fight "
            "effectively alone. The expression encodes the cultural value of "
            "collective action over individual heroism — a recurring theme in Russian "
            "communal tradition."
        ),
        variants=(
            PhraseVariant(
                surface="один в поле не воин",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="один в поле не воин, а в добрых людях — сила",
                match_type=MatchType.inflectional_variant,
                note="Extended form: one alone is not a warrior, but in good people lies strength.",
            ),
        ),
    ),

    "ru_sem_pyatnic_na_nedele": PhraseFamily(
        id="ru_sem_pyatnic_na_nedele",
        language="ru",
        canonical_form="семь пятниц на неделе",
        meaning="Seven Fridays in a week; someone who constantly changes their mind.",
        register="informal",
        origin=(
            "Пятница (Friday): in old Russian markets, Friday was the traditional day "
            "for settling debts and completing deals. Someone with 'seven Fridays a "
            "week' constantly renegotiated — a scathing characterization of "
            "unreliability. The number seven again signals completeness/excess."
        ),
        variants=(
            PhraseVariant(
                surface="семь пятниц на неделе",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="у него семь пятниц на неделе",
                match_type=MatchType.inflectional_variant,
                note="He changes his mind all the time.",
            ),
        ),
    ),

    "ru_v_chuzhom_glazu_solominku": PhraseFamily(
        id="ru_v_chuzhom_glazu_solominku",
        language="ru",
        canonical_form="в чужом глазу соломинку видишь, а в своём бревна не замечаешь",
        meaning="You see the mote in another's eye but not the beam in your own.",
        register="neutral",
        origin=(
            "From the Sermon on the Mount (Matthew 7:3-5). Соломинка (straw) in "
            "another's eye vs. бревно (log/beam) in one's own — the biblical contrast "
            "between hypocritical perception of others' small faults while ignoring "
            "one's own enormous ones. Universally known in Orthodox Christian "
            "culture."
        ),
        variants=(
            PhraseVariant(
                surface="в чужом глазу соломинку видишь, а в своём бревна не замечаешь",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="в чужом глазу соломинку видит",
                match_type=MatchType.inflectional_variant,
                note="He sees the speck in another's eye — third person, truncated.",
            ),
        ),
    ),

    "ru_delit_shkuru_neubitogo_medvedya": PhraseFamily(
        id="ru_delit_shkuru_neubitogo_medvedya",
        language="ru",
        canonical_form="делить шкуру неубитого медведя",
        meaning=(
            "To count one's chickens before they hatch; to divide the skin of an"
            "unshot bear."
        ),
        register="neutral",
        origin=(
            "Медведь (bear) + шкура (skin/pelt): dividing the bear's valuable fur "
            "before it has been killed. The bear-hunting context is distinctly "
            "Russian — replacing the general European 'counting chickens' with a "
            "vivid image from the forest economy."
        ),
        why_it_matters=(
            "The bear is Russia's iconic animal — its appearance here is not "
            "accidental. The phrase connects to a deep cultural layer of bear-hunting "
            "folklore and the practical economy of the Russian forest."
        ),
        variants=(
            PhraseVariant(
                surface="делить шкуру неубитого медведя",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="не дели шкуру неубитого медведя",
                match_type=MatchType.inflectional_variant,
                note="Don't count your chickens — imperative.",
            ),
            PhraseVariant(
                surface="продавать шкуру неубитого медведя",
                match_type=MatchType.inflectional_variant,
                note="Variant with 'продавать' (to sell) — to sell the bear's skin before it's caught.",
            ),
        ),
    ),

    "ru_ne_vse_zoloto_chto_blestit": PhraseFamily(
        id="ru_ne_vse_zoloto_chto_blestit",
        language="ru",
        canonical_form="не всё золото, что блестит",
        meaning="All that glitters is not gold.",
        register="neutral",
        origin=(
            "From a medieval Latin proverb ('non omne quod nitet aurum est'), "
            "popularized in Western Europe by Chaucer and Shakespeare. The Russian "
            "version is identical in meaning and is equally universal. The image "
            "warns against mistaking surface appeal for genuine value."
        ),
        variants=(
            PhraseVariant(
                surface="не всё золото, что блестит",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="не всё то золото, что блестит",
                match_type=MatchType.inflectional_variant,
                note="Variant with emphatic 'то' — not everything that gleams is gold.",
            ),
        ),
    ),

    "ru_veshat_sobak": PhraseFamily(
        id="ru_veshat_sobak",
        language="ru",
        canonical_form="вешать собак на кого-то",
        meaning="To lay the blame on someone; to put the dogs on someone.",
        register="informal",
        origin=(
            "Собака (dog): 'hanging dogs' on someone — loading them with accusations. "
            "The image is of dogs being strapped to a person as a form of punishment "
            "or humiliation. Historically, being beaten with a dead dog was a ritual "
            "public shaming."
        ),
        why_it_matters=(
            "Learners often confuse this with 'вешать лапшу на уши' (to bamboozle). "
            "The verbs overlap but the objects (собаки vs. лапша) signal completely "
            "different meanings: blame vs. deception."
        ),
        variants=(
            PhraseVariant(
                surface="вешать собак на кого-то",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="на меня вешают собак",
                match_type=MatchType.inflectional_variant,
                note="They're pinning the blame on me.",
            ),
            PhraseVariant(
                surface="навешали собак",
                match_type=MatchType.inflectional_variant,
                note="They laid all the blame — perfective past.",
            ),
        ),
    ),

    "ru_na_miru_i_smert_krasna": PhraseFamily(
        id="ru_na_miru_i_smert_krasna",
        language="ru",
        canonical_form="на миру и смерть красна",
        meaning=(
            "Even death is beautiful in company; there is strength and dignity in"
            "shared fate."
        ),
        register="neutral",
        origin=(
            "Мир (here: community, world): a proverb encoding the Russian cultural "
            "value of collective solidarity. Even the most terrible experience "
            "(death) becomes bearable — even beautiful — when shared. A deep "
            "expression of communal ethos over individualism."
        ),
        why_it_matters=(
            "Encodes one of the most fundamental values in Russian folk culture: "
            "collective over individual. Understanding it gives insight into how "
            "Russian culture frames suffering and heroism differently from "
            "individualist Western norms."
        ),
        variants=(
            PhraseVariant(
                surface="на миру и смерть красна",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "ru_perevesti_dukh": PhraseFamily(
        id="ru_perevesti_dukh",
        language="ru",
        canonical_form="перевести дух",
        meaning="To catch one's breath; to take a breather; to pause and recover.",
        register="neutral",
        origin=(
            "Дух (spirit, breath): 'translating' or shifting one's breath — a pause "
            "that allows recovery. The verb перевести (to transfer, to translate) "
            "applied to breath creates a subtle image of breath moving from exertion "
            "to rest."
        ),
        variants=(
            PhraseVariant(
                surface="перевести дух",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="дайте перевести дух",
                match_type=MatchType.inflectional_variant,
                note="Let me catch my breath — first-person request.",
            ),
            PhraseVariant(
                surface="едва успел перевести дух",
                match_type=MatchType.inflectional_variant,
                note="Barely had time to catch his breath.",
            ),
        ),
    ),

    "ru_vezet_kak_utoplenniku": PhraseFamily(
        id="ru_vezet_kak_utoplenniku",
        language="ru",
        canonical_form="везёт как утопленнику",
        meaning="As lucky as a drowned man; having terrible luck.",
        register="informal",
        origin=(
            "Утопленник (drowned man): a drowned man's fate is the worst possible — "
            "ironic understatement for terrible luck. Russian has a tradition of "
            "dark, ironic expressions of misfortune. The expression uses the same "
            "'везти' (to be lucky) as positive luck expressions, inverting them "
            "sardonically."
        ),
        why_it_matters=(
            "Russian irony often works by using positive vocabulary in maximally "
            "negative contexts. 'Везёт' (lucky) applied to a drowned man epitomizes "
            "this darkly comic register."
        ),
        variants=(
            PhraseVariant(
                surface="везёт как утопленнику",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="везёт ему как утопленнику",
                match_type=MatchType.inflectional_variant,
                note="He's as lucky as a drowned man — with explicit subject.",
            ),
        ),
    ),

    "ru_zhit_kak_koshka_s_sobakou": PhraseFamily(
        id="ru_zhit_kak_koshka_s_sobakou",
        language="ru",
        canonical_form="жить как кошка с собакой",
        meaning="To live like cat and dog; to be constantly at odds.",
        register="informal",
        origin=(
            "Кошка (cat) + собака (dog): the proverbial enmity of cats and dogs is a "
            "cross-cultural metaphor for constant quarreling. Russian uses the same "
            "animal pairing as English and most European languages to encode domestic "
            "conflict."
        ),
        variants=(
            PhraseVariant(
                surface="жить как кошка с собакой",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="живут как кошка с собакой",
                match_type=MatchType.inflectional_variant,
                note="They live like cat and dog — constant fighting.",
            ),
            PhraseVariant(
                surface="как кошка с собакой",
                match_type=MatchType.inflectional_variant,
                note="Like cat and dog — adverbial shorthand.",
            ),
        ),
    ),

    # ── Ar (generated) ────────────────────────────────────────

    "ar_min_alfammi_ila_aludhun": PhraseFamily(
        id="ar_min_alfammi_ila_aludhun",
        language="ar",
        canonical_form="من الفم إلى الأذن",
        meaning=(
            "From the mouth to the ear — said of secrets passed quietly between"
            "trusted parties."
        ),
        register="neutral",
        origin="Common Arabic idiom across MSA and dialects.",
        variants=(
            PhraseVariant(
                surface="من الفم إلى الأذن",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "ar_albaytu_baytuk": PhraseFamily(
        id="ar_albaytu_baytuk",
        language="ar",
        canonical_form="البيت بيتك",
        meaning=(
            "The house is your house — formal Arabic hospitality phrase, mirror of"
            "Spanish 'mi casa es tu casa.'"
        ),
        register="neutral",
        origin=(
            "Pan-Arab hospitality formula; the welcoming host's standard utterance to "
            "a guest."
        ),
        why_it_matters="Captures Arab hospitality (ḍiyāfa) as a cultural norm.",
        variants=(
            PhraseVariant(
                surface="البيت بيتك",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "ar_sahtain": PhraseFamily(
        id="ar_sahtain",
        language="ar",
        canonical_form="صحتين",
        meaning=(
            "Double health — said before/after meals, equivalent to bon appétit and"
            "'cheers to your health.'"
        ),
        register="informal",
        origin=(
            "Dialectal Arabic (especially Levantine and Egyptian); literally 'two "
            "healths' — wishing the eater double the benefit."
        ),
        variants=(
            PhraseVariant(
                surface="صحتين",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="صحة",
                match_type=MatchType.allusion,
                note="Single-word health-wish (Maghrebi).",
            ),
        ),
    ),

    "ar_haram_alayk": PhraseFamily(
        id="ar_haram_alayk",
        language="ar",
        canonical_form="حرام عليك",
        meaning=(
            "Shame on you / it's a sin on you — moral reproach with religious"
            "overtones."
        ),
        register="informal",
        origin=(
            "Common spoken Arabic across regions; ḥarām invokes the religious sense "
            "of forbidden."
        ),
        variants=(
            PhraseVariant(
                surface="حرام عليك",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="حرام عليكي",
                match_type=MatchType.inflectional_variant,
                note="Feminine-addressee form.",
            ),
        ),
    ),

    "ar_law_samaht": PhraseFamily(
        id="ar_law_samaht",
        language="ar",
        canonical_form="لو سمحت",
        meaning="If you would permit / please.",
        register="formal",
        origin="Formal polite request formula in MSA and most dialects.",
        variants=(
            PhraseVariant(
                surface="لو سمحت",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="لو سمحتي",
                match_type=MatchType.inflectional_variant,
                note="Feminine-addressee form.",
            ),
        ),
    ),

    "ar_min_fadlak": PhraseFamily(
        id="ar_min_fadlak",
        language="ar",
        canonical_form="من فضلك",
        meaning="From your favor / please. Slightly more elevated than law samaḥt.",
        register="formal",
        origin="Standard Arabic polite request formula; faḍl = favor/grace.",
        variants=(
            PhraseVariant(
                surface="من فضلك",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="من فضلكم",
                match_type=MatchType.inflectional_variant,
                note="Plural/respectful form.",
            ),
        ),
    ),

    "ar_taht_amrak": PhraseFamily(
        id="ar_taht_amrak",
        language="ar",
        canonical_form="تحت أمرك",
        meaning="Under your command / at your service. Formal courtesy.",
        register="formal",
        origin="Levantine and Egyptian Arabic; literally 'beneath your order.'",
        variants=(
            PhraseVariant(
                surface="تحت أمرك",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "ar_kif_halak": PhraseFamily(
        id="ar_kif_halak",
        language="ar",
        canonical_form="كيف حالك",
        meaning="How is your state / how are you.",
        register="neutral",
        origin="MSA and dialectal greeting; ḥāl = state, condition.",
        variants=(
            PhraseVariant(
                surface="كيف حالك",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="كيف الحال",
                match_type=MatchType.inflectional_variant,
                note="Without explicit 2nd-person possessive.",
            ),
        ),
    ),

    "ar_ala_kaifak": PhraseFamily(
        id="ar_ala_kaifak",
        language="ar",
        canonical_form="على كيفك",
        meaning="As you like / suit yourself / take it easy.",
        register="informal",
        origin=(
            "Levantine and Egyptian Arabic; kayf = mood, pleasure (also gives English "
            "'kif')."
        ),
        variants=(
            PhraseVariant(
                surface="على كيفك",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "ar_walaw": PhraseFamily(
        id="ar_walaw",
        language="ar",
        canonical_form="ولو",
        meaning="Even so / even if / used as deflective 'don't mention it.'",
        register="informal",
        origin="Common conversational Arabic; literally 'and-if.'",
        variants=(
            PhraseVariant(
                surface="ولو",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "ar_la_taqlaq": PhraseFamily(
        id="ar_la_taqlaq",
        language="ar",
        canonical_form="لا تقلق",
        meaning="Don't worry.",
        register="neutral",
        origin="MSA and dialectal reassurance.",
        variants=(
            PhraseVariant(
                surface="لا تقلق",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="ما تقلقش",
                match_type=MatchType.inflectional_variant,
                note="Egyptian dialectal negation.",
            ),
        ),
    ),

    "ar_kullu_shay_tamam": PhraseFamily(
        id="ar_kullu_shay_tamam",
        language="ar",
        canonical_form="كل شيء تمام",
        meaning="Everything is fine/complete.",
        register="informal",
        origin="Egyptian and Levantine Arabic; tamām = complete, perfect.",
        variants=(
            PhraseVariant(
                surface="كل شيء تمام",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "ar_ala_alhabba_walhabbatain": PhraseFamily(
        id="ar_ala_alhabba_walhabbatain",
        language="ar",
        canonical_form="على الحبة والحبتين",
        meaning="Down to the last grain — exhaustively, thoroughly.",
        register="informal",
        origin="Egyptian Arabic; literally 'on one bean and two beans.'",
        variants=(
            PhraseVariant(
                surface="على الحبة والحبتين",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "ar_ya_salam": PhraseFamily(
        id="ar_ya_salam",
        language="ar",
        canonical_form="يا سلام",
        meaning="O peace! — exclamation of admiration or surprise.",
        register="informal",
        origin="Pan-Arab exclamation.",
        variants=(
            PhraseVariant(
                surface="يا سلام",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "ar_walla_balla": PhraseFamily(
        id="ar_walla_balla",
        language="ar",
        canonical_form="والله بالله",
        meaning="By God by God — strong oath/affirmation.",
        register="informal",
        origin=(
            "Levantine spoken Arabic; rhyming intensifier of the standard 'wallahi' "
            "oath."
        ),
        variants=(
            PhraseVariant(
                surface="والله بالله",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "ar_la_hawla_wa_la_quwwata_illa_billah": PhraseFamily(
        id="ar_la_hawla_wa_la_quwwata_illa_billah",
        language="ar",
        canonical_form="لا حول ولا قوة إلا بالله",
        meaning="There is no power and no strength except in God.",
        register="formal",
        origin=(
            "Quranic-style invocation said in moments of distress or witnessing "
            "trouble."
        ),
        why_it_matters="Religiously potent expression of fatalistic acceptance.",
        variants=(
            PhraseVariant(
                surface="لا حول ولا قوة إلا بالله",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="لا حول ولا قوة",
                match_type=MatchType.allusion,
                note="Shortened form.",
            ),
        ),
    ),

    "ar_baraka_allahu_fik": PhraseFamily(
        id="ar_baraka_allahu_fik",
        language="ar",
        canonical_form="بارك الله فيك",
        meaning="May God bless you in/through you. Formal thanks/blessing.",
        register="formal",
        origin="Quranic-style blessing formula.",
        variants=(
            PhraseVariant(
                surface="بارك الله فيك",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="بارك الله فيكم",
                match_type=MatchType.inflectional_variant,
                note="Plural form.",
            ),
        ),
    ),

    "ar_alhamdu_lillah_ala_kulli_hal": PhraseFamily(
        id="ar_alhamdu_lillah_ala_kulli_hal",
        language="ar",
        canonical_form="الحمد لله على كل حال",
        meaning="Praise be to God in every state — gratitude in good and bad alike.",
        register="formal",
        origin="Pan-Islamic theological formula expressing acceptance.",
        variants=(
            PhraseVariant(
                surface="الحمد لله على كل حال",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "ar_in_kana_kheir": PhraseFamily(
        id="ar_in_kana_kheir",
        language="ar",
        canonical_form="إن كان خير",
        meaning=(
            "If it be good / hopefully it is good — said when mentioning a planned"
            "event whose outcome depends on God."
        ),
        register="informal",
        origin="Levantine Arabic; cultural marker of fatalistic optimism.",
        variants=(
            PhraseVariant(
                surface="إن كان خير",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "ar_kullu_aam_wa_anta_bikhair": PhraseFamily(
        id="ar_kullu_aam_wa_anta_bikhair",
        language="ar",
        canonical_form="كل عام وأنت بخير",
        meaning=(
            "Every year, and you in good health — universal Arabic greeting for"
            "holidays, birthdays, anniversaries."
        ),
        register="neutral",
        origin="Standard Arabic festive greeting.",
        variants=(
            PhraseVariant(
                surface="كل عام وأنت بخير",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="كل سنة وأنت طيب",
                match_type=MatchType.modernized_variant,
                note="Egyptian dialectal form.",
            ),
        ),
    ),

    "ar_aakidan": PhraseFamily(
        id="ar_aakidan",
        language="ar",
        canonical_form="أكيدا",
        meaning="Certainly / for sure.",
        register="neutral",
        origin="MSA emphatic.",
        variants=(
            PhraseVariant(
                surface="أكيدا",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="أكيد",
                match_type=MatchType.inflectional_variant,
                note="Adjective form.",
            ),
        ),
    ),

    "ar_ala_fikra": PhraseFamily(
        id="ar_ala_fikra",
        language="ar",
        canonical_form="على فكرة",
        meaning="By the way / incidentally.",
        register="informal",
        origin="Pan-Arab spoken; literally 'on a thought.'",
        variants=(
            PhraseVariant(
                surface="على فكرة",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "ar_ya_rabb": PhraseFamily(
        id="ar_ya_rabb",
        language="ar",
        canonical_form="يا رب",
        meaning="O Lord! — exclamation of plea or distress.",
        register="informal",
        origin="Pan-Arab; rabb is one of the names of God.",
        variants=(
            PhraseVariant(
                surface="يا رب",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "ar_wallahil_aazim": PhraseFamily(
        id="ar_wallahil_aazim",
        language="ar",
        canonical_form="والله العظيم",
        meaning="By God the Great — strongest oath form.",
        register="formal",
        origin="Strongest Arabic oath formula, often used in serious assertions.",
        variants=(
            PhraseVariant(
                surface="والله العظيم",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "ar_min_zaman": PhraseFamily(
        id="ar_min_zaman",
        language="ar",
        canonical_form="من زمان",
        meaning=(
            "From a long time / it's been ages — said when meeting someone after a"
            "long separation."
        ),
        register="informal",
        origin="Pan-Arab spoken.",
        variants=(
            PhraseVariant(
                surface="من زمان",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "ar_ish_wallah": PhraseFamily(
        id="ar_ish_wallah",
        language="ar",
        canonical_form="إيش والله",
        meaning="What, by God! — exclamation of surprise.",
        register="informal",
        origin="Levantine and Gulf dialect; ish = what (dialectal).",
        variants=(
            PhraseVariant(
                surface="إيش والله",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "ar_inta_jad": PhraseFamily(
        id="ar_inta_jad",
        language="ar",
        canonical_form="إنت جاد",
        meaning="Are you serious? / really?",
        register="informal",
        origin="Pan-Arab spoken; jadd = serious/grandfather.",
        variants=(
            PhraseVariant(
                surface="إنت جاد",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="أنت جاد",
                match_type=MatchType.orthographic_variant,
                note="MSA formal pronoun.",
            ),
        ),
    ),

    "ar_yaani": PhraseFamily(
        id="ar_yaani",
        language="ar",
        canonical_form="يعني",
        meaning="I mean / so / sort of — pervasive discourse filler in spoken Arabic.",
        register="informal",
        origin="Pan-Arab discourse particle from yaʿnī (literally 'it means').",
        why_it_matters="Yaʿnī fills the same conversational role as English 'like' or 'I mean.'",
        variants=(
            PhraseVariant(
                surface="يعني",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "ar_alhayat_hilwa": PhraseFamily(
        id="ar_alhayat_hilwa",
        language="ar",
        canonical_form="الحياة حلوة",
        meaning="Life is sweet — affirmation of life's goodness.",
        register="informal",
        origin=(
            "Egyptian Arabic; cultural attitude of finding sweetness in life despite "
            "hardship."
        ),
        variants=(
            PhraseVariant(
                surface="الحياة حلوة",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "ar_safi_wa_yali": PhraseFamily(
        id="ar_safi_wa_yali",
        language="ar",
        canonical_form="صافي ويالي",
        meaning="Clear and that's it — done, settled, agreed.",
        register="informal",
        origin="Levantine/Gulf spoken Arabic.",
        variants=(
            PhraseVariant(
                surface="صافي ويالي",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "ar_la_baas": PhraseFamily(
        id="ar_la_baas",
        language="ar",
        canonical_form="لا بأس",
        meaning="No harm / not bad.",
        register="neutral",
        origin="MSA standard reassurance.",
        variants=(
            PhraseVariant(
                surface="لا بأس",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "ar_ahlan_wa_sahlan": PhraseFamily(
        id="ar_ahlan_wa_sahlan",
        language="ar",
        canonical_form="أهلا وسهلا",
        meaning="Welcome / be at ease — formal welcome formula.",
        register="neutral",
        origin="Pan-Arab formal welcoming phrase, very ancient.",
        variants=(
            PhraseVariant(
                surface="أهلا وسهلا",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="أهلا",
                match_type=MatchType.allusion,
                note="Shortened informal greeting.",
            ),
        ),
    ),

    "ar_marhaba": PhraseFamily(
        id="ar_marhaba",
        language="ar",
        canonical_form="مرحبا",
        meaning="Welcome / hello.",
        register="neutral",
        origin="Pan-Arab universal greeting.",
        variants=(
            PhraseVariant(
                surface="مرحبا",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="مرحبتين",
                match_type=MatchType.inflectional_variant,
                note="Doubled form: 'two welcomes'.",
            ),
        ),
    ),

    "ar_aalik_yatba": PhraseFamily(
        id="ar_aalik_yatba",
        language="ar",
        canonical_form="عليك يا طبا",
        meaning="Said as encouragement / 'come on, you can do it!'",
        register="informal",
        origin="Levantine cheering phrase.",
        variants=(
            PhraseVariant(
                surface="عليك يا طبا",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "ar_lan_yansak": PhraseFamily(
        id="ar_lan_yansak",
        language="ar",
        canonical_form="لن ينساك",
        meaning=(
            "He/it will not forget you — said as comforting reassurance, especially"
            "of God's care."
        ),
        register="literary",
        origin="Quranic-style reassurance.",
        variants=(
            PhraseVariant(
                surface="لن ينساك",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "ar_kullu_shai_qadar": PhraseFamily(
        id="ar_kullu_shai_qadar",
        language="ar",
        canonical_form="كل شيء قدر",
        meaning="Everything is fate.",
        register="neutral",
        origin="Theological/cultural attitude expressing acceptance of God's decree.",
        variants=(
            PhraseVariant(
                surface="كل شيء قدر",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="كل شي قدر",
                match_type=MatchType.orthographic_variant,
                note="Dialectal spelling of 'shay' as 'shi'.",
            ),
        ),
    ),

    "ar_inna_lillahi_wa_inna_ilayhi_rajiun": PhraseFamily(
        id="ar_inna_lillahi_wa_inna_ilayhi_rajiun",
        language="ar",
        canonical_form="إنا لله وإنا إليه راجعون",
        meaning=(
            "We belong to God and to Him we return — Quranic verse 2:156, said upon"
            "hearing of a death."
        ),
        register="formal",
        origin="Quran 2:156; the standard Islamic phrase upon learning of death.",
        why_it_matters="Religiously prescribed; universally recognized across Muslims.",
        variants=(
            PhraseVariant(
                surface="إنا لله وإنا إليه راجعون",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="إنا لله",
                match_type=MatchType.allusion,
                note="Shortened form, very common.",
            ),
        ),
    ),

    "ar_jazaka_allahu_khairan": PhraseFamily(
        id="ar_jazaka_allahu_khairan",
        language="ar",
        canonical_form="جزاك الله خيرا",
        meaning="May God reward you with good — religious thanks formula.",
        register="formal",
        origin="Hadith-derived; preferred by religious speakers over plain 'shukran.'",
        variants=(
            PhraseVariant(
                surface="جزاك الله خيرا",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="جزاك الله",
                match_type=MatchType.allusion,
                note="Shortened form.",
            ),
        ),
    ),

    "ar_la_ilaha_illa_allah": PhraseFamily(
        id="ar_la_ilaha_illa_allah",
        language="ar",
        canonical_form="لا إله إلا الله",
        meaning="There is no god but God — first half of the shahāda (Islamic creed).",
        register="formal",
        origin="Quran 47:19; the foundational Islamic creedal statement.",
        why_it_matters="Most foundational sentence in Islam; tawḥīd (oneness of God) condensed.",
        variants=(
            PhraseVariant(
                surface="لا إله إلا الله",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "ar_subhana_allah": PhraseFamily(
        id="ar_subhana_allah",
        language="ar",
        canonical_form="سبحان الله",
        meaning="Glory to God — pious exclamation upon witnessing something amazing.",
        register="formal",
        origin="Quranic phrase; standard pious utterance.",
        variants=(
            PhraseVariant(
                surface="سبحان الله",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "ar_allahu_akbar": PhraseFamily(
        id="ar_allahu_akbar",
        language="ar",
        canonical_form="الله أكبر",
        meaning=(
            "God is greater — the takbīr; said in prayer, in moments of awe, victory,"
            "or distress."
        ),
        register="formal",
        origin="Foundational Islamic phrase; opens the call to prayer.",
        why_it_matters=(
            "Universally recognized Islamic phrase; theologically asserts God's "
            "greatness over all things."
        ),
        variants=(
            PhraseVariant(
                surface="الله أكبر",
                match_type=MatchType.exact,
            ),
        ),
    ),

    # ── He (generated) ────────────────────────────────────────

    "he_ein_li_musag": PhraseFamily(
        id="he_ein_li_musag",
        language="he",
        canonical_form="אין לי מושג",
        meaning="I have no idea / no clue.",
        register="informal",
        origin="Modern Hebrew idiom; musag = concept.",
        variants=(
            PhraseVariant(
                surface="אין לי מושג",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "he_lehitraot": PhraseFamily(
        id="he_lehitraot",
        language="he",
        canonical_form="להתראות",
        meaning="See you / goodbye (literally 'to see each other').",
        register="neutral",
        origin="Modern Hebrew standard farewell; reflexive form of l'rot (to see).",
        variants=(
            PhraseVariant(
                surface="להתראות",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "he_boker_tov": PhraseFamily(
        id="he_boker_tov",
        language="he",
        canonical_form="בוקר טוב",
        meaning="Good morning.",
        register="neutral",
        origin="Standard morning greeting.",
        variants=(
            PhraseVariant(
                surface="בוקר טוב",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="בוקר אור",
                match_type=MatchType.inflectional_variant,
                note="Response form: 'morning of light.'",
            ),
        ),
    ),

    "he_layla_tov": PhraseFamily(
        id="he_layla_tov",
        language="he",
        canonical_form="לילה טוב",
        meaning="Good night.",
        register="neutral",
        origin="Standard night farewell.",
        variants=(
            PhraseVariant(
                surface="לילה טוב",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "he_toda_raba": PhraseFamily(
        id="he_toda_raba",
        language="he",
        canonical_form="תודה רבה",
        meaning="Many thanks (literally 'much thanks').",
        register="neutral",
        origin="Standard Hebrew thanks; raba = many/much (feminine).",
        variants=(
            PhraseVariant(
                surface="תודה רבה",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="תודה",
                match_type=MatchType.allusion,
                note="Shortened standalone form.",
            ),
        ),
    ),

    "he_bevakasha": PhraseFamily(
        id="he_bevakasha",
        language="he",
        canonical_form="בבקשה",
        meaning="Please / you're welcome (used both ways).",
        register="neutral",
        origin="Modern Hebrew formula; literally 'in request.'",
        variants=(
            PhraseVariant(
                surface="בבקשה",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "he_slicha": PhraseFamily(
        id="he_slicha",
        language="he",
        canonical_form="סליחה",
        meaning="Excuse me / sorry / pardon.",
        register="neutral",
        origin=(
            "Hebrew slicha = forgiveness; productive in everyday apology and "
            "attention-getting."
        ),
        variants=(
            PhraseVariant(
                surface="סליחה",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "he_betei_hen": PhraseFamily(
        id="he_betei_hen",
        language="he",
        canonical_form="תני חן",
        meaning="Look favorably / smile upon — 'find grace in your eyes.'",
        register="literary",
        origin="Biblical idiom: matza ḥen be-eineiha (he found favor in her eyes).",
        variants=(
            PhraseVariant(
                surface="תני חן",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "he_sof_sof": PhraseFamily(
        id="he_sof_sof",
        language="he",
        canonical_form="סוף סוף",
        meaning="Finally / at last (literally 'end-end').",
        register="informal",
        origin="Modern Hebrew reduplication; reduplication for emphasis is common.",
        variants=(
            PhraseVariant(
                surface="סוף סוף",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "he_lo_baseder": PhraseFamily(
        id="he_lo_baseder",
        language="he",
        canonical_form="לא בסדר",
        meaning="Not okay / not right.",
        register="informal",
        origin="Mirror of 'beseder' (okay); literally 'not in order.'",
        variants=(
            PhraseVariant(
                surface="לא בסדר",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "he_eich_holech": PhraseFamily(
        id="he_eich_holech",
        language="he",
        canonical_form="איך הולך",
        meaning="How's it going (literally 'how does it go').",
        register="informal",
        origin="Modern Hebrew casual greeting.",
        variants=(
            PhraseVariant(
                surface="איך הולך",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="מה נשמע",
                match_type=MatchType.inflectional_variant,
                note="Alternative greeting: 'what is heard.'",
            ),
        ),
    ),

    "he_yom_yom": PhraseFamily(
        id="he_yom_yom",
        language="he",
        canonical_form="יום יום",
        meaning="Day-day / daily / every day.",
        register="informal",
        origin="Reduplication for distributive meaning.",
        variants=(
            PhraseVariant(
                surface="יום יום",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "he_ein_dvarim_kaeleh": PhraseFamily(
        id="he_ein_dvarim_kaeleh",
        language="he",
        canonical_form="אין דברים כאלה",
        meaning="No such things — used as denial/rejection.",
        register="informal",
        origin="Modern Hebrew dismissive idiom.",
        variants=(
            PhraseVariant(
                surface="אין דברים כאלה",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "he_az_ma": PhraseFamily(
        id="he_az_ma",
        language="he",
        canonical_form="אז מה",
        meaning="So what / what now.",
        register="informal",
        origin="Modern Hebrew dismissive/inquisitive.",
        variants=(
            PhraseVariant(
                surface="אז מה",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "he_ma_inyanim": PhraseFamily(
        id="he_ma_inyanim",
        language="he",
        canonical_form="מה עניינים",
        meaning="What's up / how are things (literally 'what matters').",
        register="informal",
        origin="Modern Hebrew greeting; inyanim = matters/affairs.",
        variants=(
            PhraseVariant(
                surface="מה עניינים",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "he_yalla_balagan": PhraseFamily(
        id="he_yalla_balagan",
        language="he",
        canonical_form="יאללה בלגן",
        meaning="Come on, chaos! — said when accepting that things will be messy.",
        register="informal",
        origin=(
            "Modern Hebrew slang combining Arabic-derived yalla (let's go) and "
            "Russian/Yiddish-derived balagan (chaos)."
        ),
        variants=(
            PhraseVariant(
                surface="יאללה בלגן",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "he_betsel": PhraseFamily(
        id="he_betsel",
        language="he",
        canonical_form="בצל",
        meaning=(
            "Onion — but idiomatically 'in the shade' (b'tsel) or 'small thing.'"
            "Note: same surface for two unrelated meanings."
        ),
        register="informal",
        origin="Hebrew homograph; context distinguishes.",
        variants=(
            PhraseVariant(
                surface="בצל",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "he_ein_li_koach": PhraseFamily(
        id="he_ein_li_koach",
        language="he",
        canonical_form="אין לי כוח",
        meaning="I have no strength / I can't be bothered.",
        register="informal",
        origin="Modern Hebrew exhaustion idiom.",
        variants=(
            PhraseVariant(
                surface="אין לי כוח",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "he_ze_lo_kashe": PhraseFamily(
        id="he_ze_lo_kashe",
        language="he",
        canonical_form="זה לא קשה",
        meaning="It's not hard.",
        register="informal",
        origin="Modern Hebrew reassurance.",
        variants=(
            PhraseVariant(
                surface="זה לא קשה",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "he_kol_tuv": PhraseFamily(
        id="he_kol_tuv",
        language="he",
        canonical_form="כל טוב",
        meaning="All good / all the best — farewell/well-wishing.",
        register="neutral",
        origin="Modern Hebrew farewell.",
        variants=(
            PhraseVariant(
                surface="כל טוב",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "he_be_atzlachah": PhraseFamily(
        id="he_be_atzlachah",
        language="he",
        canonical_form="בהצלחה",
        meaning="With success / good luck (literally 'in success').",
        register="neutral",
        origin="Standard Hebrew well-wishing for ventures.",
        variants=(
            PhraseVariant(
                surface="בהצלחה",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "he_refuah_shlemah": PhraseFamily(
        id="he_refuah_shlemah",
        language="he",
        canonical_form="רפואה שלמה",
        meaning="Complete recovery — said to the sick.",
        register="neutral",
        origin="Traditional Jewish blessing; refuah = healing, shleimah = complete.",
        variants=(
            PhraseVariant(
                surface="רפואה שלמה",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "he_be_ezrat_hashem": PhraseFamily(
        id="he_be_ezrat_hashem",
        language="he",
        canonical_form="בעזרת השם",
        meaning="With God's help — pious phrase before mentioning a future event.",
        register="formal",
        origin="Religious Hebrew phrase, parallel to Arabic in shā' Allāh.",
        variants=(
            PhraseVariant(
                surface="בעזרת השם",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="בעז\"ה",
                match_type=MatchType.orthographic_variant,
                note="Common abbreviation.",
            ),
        ),
    ),

    "he_baruch_hashem": PhraseFamily(
        id="he_baruch_hashem",
        language="he",
        canonical_form="ברוך השם",
        meaning="Blessed is the Name (of God) — 'thank God' / 'praise God.'",
        register="formal",
        origin="Religious Hebrew gratitude phrase, parallel to Arabic alhamdulillah.",
        variants=(
            PhraseVariant(
                surface="ברוך השם",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="ב\"ה",
                match_type=MatchType.orthographic_variant,
                note="Common abbreviation.",
            ),
        ),
    ),

    "he_im_yirtzeh_hashem": PhraseFamily(
        id="he_im_yirtzeh_hashem",
        language="he",
        canonical_form="אם ירצה השם",
        meaning="If God wills — pious conditional.",
        register="formal",
        origin="Religious Hebrew, parallel to Arabic in shā' Allāh.",
        variants=(
            PhraseVariant(
                surface="אם ירצה השם",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="אי\"ה",
                match_type=MatchType.orthographic_variant,
                note="Common abbreviation.",
            ),
        ),
    ),

    "he_le_chaim": PhraseFamily(
        id="he_le_chaim",
        language="he",
        canonical_form="לחיים",
        meaning="To life! — toast.",
        register="neutral",
        origin="Traditional Jewish toast; le-ḥayyim = 'to lives' (always plural).",
        why_it_matters="Universally recognized Jewish toast.",
        variants=(
            PhraseVariant(
                surface="לחיים",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "he_chag_sameach": PhraseFamily(
        id="he_chag_sameach",
        language="he",
        canonical_form="חג שמח",
        meaning="Happy holiday.",
        register="neutral",
        origin="Standard Hebrew holiday greeting; ḥag = pilgrimage festival.",
        variants=(
            PhraseVariant(
                surface="חג שמח",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "he_shana_tova": PhraseFamily(
        id="he_shana_tova",
        language="he",
        canonical_form="שנה טובה",
        meaning="Good year — Rosh Hashanah greeting.",
        register="neutral",
        origin="Standard Jewish New Year greeting.",
        variants=(
            PhraseVariant(
                surface="שנה טובה",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="שנה טובה ומתוקה",
                match_type=MatchType.inflectional_variant,
                note="Extended form: 'good and sweet year.'",
            ),
        ),
    ),

    "he_lehitraot_macheraim": PhraseFamily(
        id="he_lehitraot_macheraim",
        language="he",
        canonical_form="להתראות מחר",
        meaning="See you tomorrow.",
        register="neutral",
        origin="Modern Hebrew farewell with temporal specifier.",
        variants=(
            PhraseVariant(
                surface="להתראות מחר",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "he_be_kef": PhraseFamily(
        id="he_be_kef",
        language="he",
        canonical_form="בכיף",
        meaning="With pleasure / no problem (literally 'in fun').",
        register="informal",
        origin="Modern Hebrew slang; kef from Arabic kayf (mood, pleasure).",
        variants=(
            PhraseVariant(
                surface="בכיף",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "he_titzaref": PhraseFamily(
        id="he_titzaref",
        language="he",
        canonical_form="תצטרף",
        meaning="Join us / join in.",
        register="informal",
        origin="Modern Hebrew imperative; reflexive of tziraf (to join).",
        variants=(
            PhraseVariant(
                surface="תצטרף",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "he_pashut": PhraseFamily(
        id="he_pashut",
        language="he",
        canonical_form="פשוט",
        meaning="Simply / it's simple.",
        register="informal",
        origin="Modern Hebrew adverb; root p-sh-t (simple, plain).",
        variants=(
            PhraseVariant(
                surface="פשוט",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "he_taluy": PhraseFamily(
        id="he_taluy",
        language="he",
        canonical_form="תלוי",
        meaning="It depends.",
        register="informal",
        origin="Modern Hebrew; root t-l-h (to hang, depend).",
        variants=(
            PhraseVariant(
                surface="תלוי",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "he_eich_zot": PhraseFamily(
        id="he_eich_zot",
        language="he",
        canonical_form="איך זאת",
        meaning="How so / what do you mean?",
        register="informal",
        origin="Modern Hebrew interrogative.",
        variants=(
            PhraseVariant(
                surface="איך זאת",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "he_zeh_ze": PhraseFamily(
        id="he_zeh_ze",
        language="he",
        canonical_form="זה זה",
        meaning="This is it / that's the thing.",
        register="informal",
        origin="Modern Hebrew demonstrative reduplication.",
        variants=(
            PhraseVariant(
                surface="זה זה",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "he_yofi": PhraseFamily(
        id="he_yofi",
        language="he",
        canonical_form="יופי",
        meaning="Great / beauty / nice work.",
        register="informal",
        origin="Modern Hebrew exclamation; yofi = beauty.",
        variants=(
            PhraseVariant(
                surface="יופי",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "he_eze_hatza_atza": PhraseFamily(
        id="he_eze_hatza_atza",
        language="he",
        canonical_form="איזה הצעה",
        meaning="What an offer / what a deal — exclamation.",
        register="informal",
        origin="Modern Hebrew exclamatory pattern.",
        variants=(
            PhraseVariant(
                surface="איזה הצעה",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "he_ein_breiyra_acheret": PhraseFamily(
        id="he_ein_breiyra_acheret",
        language="he",
        canonical_form="אין ברירה אחרת",
        meaning="There is no other choice — fuller form of ein breira.",
        register="neutral",
        origin="Modern Hebrew fatalistic formula; breira = choice.",
        variants=(
            PhraseVariant(
                surface="אין ברירה אחרת",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "he_ze_taluyi_bi": PhraseFamily(
        id="he_ze_taluyi_bi",
        language="he",
        canonical_form="זה תלוי בי",
        meaning="It depends on me.",
        register="informal",
        origin="Modern Hebrew first-person dependency.",
        variants=(
            PhraseVariant(
                surface="זה תלוי בי",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "he_eshtdaeshtdaef": PhraseFamily(
        id="he_eshtdaeshtdaef",
        language="he",
        canonical_form="אשתדל",
        meaning="I'll try.",
        register="informal",
        origin="Modern Hebrew first-person future of hishtadel (to try).",
        variants=(
            PhraseVariant(
                surface="אשתדל",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "he_kacha_ze": PhraseFamily(
        id="he_kacha_ze",
        language="he",
        canonical_form="ככה זה",
        meaning="That's how it is — fatalistic acceptance.",
        register="informal",
        origin="Modern Hebrew fatalism formula.",
        variants=(
            PhraseVariant(
                surface="ככה זה",
                match_type=MatchType.exact,
            ),
        ),
    ),

    # ── En (generated) ────────────────────────────────────────

    "en_a_stitch_in_time": PhraseFamily(
        id="en_a_stitch_in_time",
        language="en",
        canonical_form="a stitch in time saves nine",
        meaning="Timely correction prevents bigger problems later.",
        register="neutral",
        origin=(
            "Recorded since Thomas Fuller's Gnomologia, 1732. Sewing metaphor: one "
            "stitch now spares nine repairs later."
        ),
        variants=(
            PhraseVariant(
                surface="a stitch in time saves nine",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "en_dont_count_your_chickens": PhraseFamily(
        id="en_dont_count_your_chickens",
        language="en",
        canonical_form="don't count your chickens before they hatch",
        meaning="Don't assume success before it has happened.",
        register="neutral",
        origin="Aesopian fable tradition; English form attested since the 16th century.",
        variants=(
            PhraseVariant(
                surface="don't count your chickens before they hatch",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="counting chickens",
                match_type=MatchType.allusion,
                note="Allusive shortening, used to chide premature claims.",
            ),
        ),
    ),

    "en_the_early_bird": PhraseFamily(
        id="en_the_early_bird",
        language="en",
        canonical_form="the early bird catches the worm",
        meaning="Those who act first gain the advantage.",
        register="neutral",
        origin="Recorded since 1605 in William Camden's Remains.",
        variants=(
            PhraseVariant(
                surface="the early bird catches the worm",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="the early bird",
                match_type=MatchType.allusion,
                note="Allusive shortening: 'be the early bird.'",
            ),
        ),
    ),

    "en_when_in_rome": PhraseFamily(
        id="en_when_in_rome",
        language="en",
        canonical_form="when in Rome do as the Romans do",
        meaning="Adapt to local customs.",
        register="neutral",
        origin=(
            "Attributed to St. Ambrose's advice to Augustine (4th c.); the proverbial "
            "English form by 17th c."
        ),
        variants=(
            PhraseVariant(
                surface="when in Rome do as the Romans do",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="when in Rome",
                match_type=MatchType.allusion,
                note="Allusive shortening, very common.",
            ),
        ),
    ),

    "en_the_pen_is_mightier": PhraseFamily(
        id="en_the_pen_is_mightier",
        language="en",
        canonical_form="the pen is mightier than the sword",
        meaning="Writing/argument has greater power than violence.",
        register="literary",
        origin="Edward Bulwer-Lytton, Richelieu (1839). Now globally proverbial.",
        variants=(
            PhraseVariant(
                surface="the pen is mightier than the sword",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "en_actions_speak_louder": PhraseFamily(
        id="en_actions_speak_louder",
        language="en",
        canonical_form="actions speak louder than words",
        meaning="Behavior reveals more than rhetoric.",
        register="neutral",
        origin="Attested since 1736; possibly from St. Anthony of Padua.",
        variants=(
            PhraseVariant(
                surface="actions speak louder than words",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "en_a_picture_is_worth": PhraseFamily(
        id="en_a_picture_is_worth",
        language="en",
        canonical_form="a picture is worth a thousand words",
        meaning="Visual information conveys more than verbal description.",
        register="neutral",
        origin=(
            "Attributed to Frederick R. Barnard, 1921 (advertising). Often "
            "misattributed to Confucius."
        ),
        variants=(
            PhraseVariant(
                surface="a picture is worth a thousand words",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "en_too_many_cooks": PhraseFamily(
        id="en_too_many_cooks",
        language="en",
        canonical_form="too many cooks spoil the broth",
        meaning="Too many people involved leads to bad results.",
        register="neutral",
        origin="Attested since 1575; English proverb.",
        variants=(
            PhraseVariant(
                surface="too many cooks spoil the broth",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="too many cooks",
                match_type=MatchType.allusion,
                note="Allusive shortening.",
            ),
        ),
    ),

    "en_dont_put_all_eggs": PhraseFamily(
        id="en_dont_put_all_eggs",
        language="en",
        canonical_form="don't put all your eggs in one basket",
        meaning="Diversify; don't risk everything on one bet.",
        register="neutral",
        origin=(
            "Spanish origin (Don Quixote, 1605: 'no aventures todo tu caudal a una "
            "galera'); English by 17th c."
        ),
        variants=(
            PhraseVariant(
                surface="don't put all your eggs in one basket",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "en_better_late_than_never": PhraseFamily(
        id="en_better_late_than_never",
        language="en",
        canonical_form="better late than never",
        meaning="Late action is preferable to no action.",
        register="neutral",
        origin="Attested since Chaucer (Canterbury Tales).",
        variants=(
            PhraseVariant(
                surface="better late than never",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "en_blood_is_thicker": PhraseFamily(
        id="en_blood_is_thicker",
        language="en",
        canonical_form="blood is thicker than water",
        meaning="Family bonds outweigh other ties.",
        register="neutral",
        origin=(
            "Attested since 12th c. in Reynard the Fox tradition; the modern reading "
            "prioritizes family."
        ),
        why_it_matters=(
            "Some etymological folklore claims original meaning was opposite ('blood "
            "of the covenant is thicker than water of the womb'); historians dispute "
            "this revisionist claim."
        ),
        variants=(
            PhraseVariant(
                surface="blood is thicker than water",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "en_a_rolling_stone": PhraseFamily(
        id="en_a_rolling_stone",
        language="en",
        canonical_form="a rolling stone gathers no moss",
        meaning=(
            "Constant movement prevents accumulation (interpreted positively or"
            "negatively)."
        ),
        register="neutral",
        origin=(
            "Erasmus, Adagia (1500); from earlier Greek source. Famously ambiguous — "
            "moss as good (achievement) or bad (stagnation)."
        ),
        variants=(
            PhraseVariant(
                surface="a rolling stone gathers no moss",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="rolling stone",
                match_type=MatchType.allusion,
                note="The Rolling Stones band; the magazine.",
            ),
        ),
    ),

    "en_birds_of_a_feather": PhraseFamily(
        id="en_birds_of_a_feather",
        language="en",
        canonical_form="birds of a feather flock together",
        meaning="Similar people associate with each other.",
        register="neutral",
        origin="16th c. English proverb.",
        variants=(
            PhraseVariant(
                surface="birds of a feather flock together",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="birds of a feather",
                match_type=MatchType.allusion,
                note="Allusive shortening.",
            ),
        ),
    ),

    "en_the_grass_is_always_greener": PhraseFamily(
        id="en_the_grass_is_always_greener",
        language="en",
        canonical_form="the grass is always greener on the other side",
        meaning="Other people's situations seem better than your own.",
        register="neutral",
        origin="Modern English proverb; 20th c. crystallization.",
        variants=(
            PhraseVariant(
                surface="the grass is always greener on the other side",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="the grass is always greener",
                match_type=MatchType.allusion,
                note="Allusive shortening.",
            ),
        ),
    ),

    "en_let_sleeping_dogs_lie": PhraseFamily(
        id="en_let_sleeping_dogs_lie",
        language="en",
        canonical_form="let sleeping dogs lie",
        meaning="Don't disturb a settled situation.",
        register="neutral",
        origin="Chaucer (Troilus and Criseyde); proverbial since.",
        variants=(
            PhraseVariant(
                surface="let sleeping dogs lie",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "en_kill_two_birds": PhraseFamily(
        id="en_kill_two_birds",
        language="en",
        canonical_form="kill two birds with one stone",
        meaning="Accomplish two goals with one action.",
        register="neutral",
        origin="Attested since the 17th century; likely earlier.",
        variants=(
            PhraseVariant(
                surface="kill two birds with one stone",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "en_the_last_straw": PhraseFamily(
        id="en_the_last_straw",
        language="en",
        canonical_form="the last straw that broke the camel's back",
        meaning="The final small thing that causes a system to collapse.",
        register="neutral",
        origin=(
            "Attested since 1755 (Charles Dickens used it); from Arabic-Persian "
            "camel-loading metaphor."
        ),
        variants=(
            PhraseVariant(
                surface="the last straw that broke the camel's back",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="the last straw",
                match_type=MatchType.allusion,
                note="Allusive shortening, very common.",
            ),
            PhraseVariant(
                surface="straw that broke the camel's back",
                match_type=MatchType.inflectional_variant,
            ),
        ),
    ),

    "en_speak_of_the_devil": PhraseFamily(
        id="en_speak_of_the_devil",
        language="en",
        canonical_form="speak of the devil and he shall appear",
        meaning="When you mention someone, they often appear.",
        register="neutral",
        origin=(
            "16th-c. English proverb; the religious tone has been lost in modern "
            "usage."
        ),
        variants=(
            PhraseVariant(
                surface="speak of the devil and he shall appear",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="speak of the devil",
                match_type=MatchType.allusion,
                note="Most common modern shortening.",
            ),
        ),
    ),

    "en_break_a_leg": PhraseFamily(
        id="en_break_a_leg",
        language="en",
        canonical_form="break a leg",
        meaning="Good luck (theatrical superstition).",
        register="informal",
        origin=(
            "Theater superstition; multiple competing etymologies (1920s-30s American "
            "theatre, possibly from Yiddish 'hatslokhe un brokhe')."
        ),
        variants=(
            PhraseVariant(
                surface="break a leg",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "en_jumping_the_shark": PhraseFamily(
        id="en_jumping_the_shark",
        language="en",
        canonical_form="jumping the shark",
        meaning="The moment a TV show / cultural phenomenon declines into absurdity.",
        register="informal",
        origin=(
            "Coined 1985 by radio personality Jon Hein referring to a 1977 Happy Days "
            "episode where Fonzie jumped a shark on water skis. Now standard "
            "cultural-criticism vocabulary."
        ),
        variants=(
            PhraseVariant(
                surface="jumping the shark",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="jumped the shark",
                match_type=MatchType.inflectional_variant,
                note="Past-tense form, the most common usage.",
            ),
        ),
    ),

    "en_paint_the_town_red": PhraseFamily(
        id="en_paint_the_town_red",
        language="en",
        canonical_form="paint the town red",
        meaning="Go out and have a wild time, often involving drinking.",
        register="informal",
        origin=(
            "Late 19th-c. American slang; possibly from the Marquis of Waterford's "
            "1837 drunken rampage in Melton Mowbray, where buildings were literally "
            "painted red."
        ),
        variants=(
            PhraseVariant(
                surface="paint the town red",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "en_under_the_weather": PhraseFamily(
        id="en_under_the_weather",
        language="en",
        canonical_form="under the weather",
        meaning="Feeling slightly ill.",
        register="informal",
        origin=(
            "Nautical: sailors who were ill were sent below deck (under the weather "
            "rail)."
        ),
        variants=(
            PhraseVariant(
                surface="under the weather",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "en_burn_the_midnight_oil": PhraseFamily(
        id="en_burn_the_midnight_oil",
        language="en",
        canonical_form="burn the midnight oil",
        meaning="Work or study late into the night.",
        register="neutral",
        origin=(
            "Francis Quarles (1635); from the era when scholars literally burned oil "
            "lamps for nighttime reading."
        ),
        variants=(
            PhraseVariant(
                surface="burn the midnight oil",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="burning the midnight oil",
                match_type=MatchType.inflectional_variant,
            ),
        ),
    ),

    "en_cut_to_the_chase": PhraseFamily(
        id="en_cut_to_the_chase",
        language="en",
        canonical_form="cut to the chase",
        meaning="Get to the point; skip preliminaries.",
        register="informal",
        origin=(
            "Hollywood film editing slang from the silent-era practice of cutting "
            "straight to the action/chase scene. Recorded since 1929."
        ),
        variants=(
            PhraseVariant(
                surface="cut to the chase",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "en_pull_someones_leg": PhraseFamily(
        id="en_pull_someones_leg",
        language="en",
        canonical_form="pull someone's leg",
        meaning="Tease, deceive playfully.",
        register="informal",
        origin=(
            "Recorded since the 1880s; etymological origin uncertain (one theory: "
            "18th-c. London thieves tripping victims)."
        ),
        variants=(
            PhraseVariant(
                surface="pull someone's leg",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="pulling your leg",
                match_type=MatchType.inflectional_variant,
                note="Common second-person form.",
            ),
        ),
    ),

    "en_caught_red_handed": PhraseFamily(
        id="en_caught_red_handed",
        language="en",
        canonical_form="caught red-handed",
        meaning="Caught in the act, with evidence on you.",
        register="neutral",
        origin=(
            "Scottish legal term 'red-hand,' attested since 15th c. — caught with the "
            "victim's blood still on the murderer's hands."
        ),
        variants=(
            PhraseVariant(
                surface="caught red-handed",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="caught red handed",
                match_type=MatchType.orthographic_variant,
                note="Without hyphen.",
            ),
        ),
    ),

    "en_devils_advocate": PhraseFamily(
        id="en_devils_advocate",
        language="en",
        canonical_form="devil's advocate",
        meaning="One who argues a contrary position for the sake of debate.",
        register="neutral",
        origin=(
            "From the Catholic Church's pre-1983 'advocatus diaboli' role, who argued "
            "against canonization of saints."
        ),
        variants=(
            PhraseVariant(
                surface="devil's advocate",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "en_through_the_grapevine": PhraseFamily(
        id="en_through_the_grapevine",
        language="en",
        canonical_form="heard it through the grapevine",
        meaning="Learned through informal channels / gossip.",
        register="informal",
        origin=(
            "American Civil War-era; 'grapevine telegraph' was the informal soldiers' "
            "news network."
        ),
        variants=(
            PhraseVariant(
                surface="heard it through the grapevine",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="through the grapevine",
                match_type=MatchType.allusion,
            ),
        ),
    ),

    "en_jump_on_the_bandwagon": PhraseFamily(
        id="en_jump_on_the_bandwagon",
        language="en",
        canonical_form="jump on the bandwagon",
        meaning="Adopt a popular position once it has clearly succeeded.",
        register="neutral",
        origin=(
            "American 19th-c. political campaigning: literal bandwagons led parades; "
            "politicians jumped on to associate with momentum."
        ),
        variants=(
            PhraseVariant(
                surface="jump on the bandwagon",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "en_back_to_the_drawing_board": PhraseFamily(
        id="en_back_to_the_drawing_board",
        language="en",
        canonical_form="back to the drawing board",
        meaning="Time to start over.",
        register="informal",
        origin=(
            "1941 New Yorker cartoon by Peter Arno: an engineer carrying his rolled "
            "plans walks away from a crashed plane, saying the line."
        ),
        variants=(
            PhraseVariant(
                surface="back to the drawing board",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "en_at_the_drop_of_a_hat": PhraseFamily(
        id="en_at_the_drop_of_a_hat",
        language="en",
        canonical_form="at the drop of a hat",
        meaning="Without hesitation; at the slightest provocation.",
        register="informal",
        origin=(
            "American 19th c.; dropping a hat was a starter signal for a fight or "
            "race."
        ),
        variants=(
            PhraseVariant(
                surface="at the drop of a hat",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "en_costs_an_arm_and_a_leg": PhraseFamily(
        id="en_costs_an_arm_and_a_leg",
        language="en",
        canonical_form="costs an arm and a leg",
        meaning="Is very expensive.",
        register="informal",
        origin="American post-WWII; possibly from veteran-pension language.",
        variants=(
            PhraseVariant(
                surface="costs an arm and a leg",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="an arm and a leg",
                match_type=MatchType.allusion,
            ),
        ),
    ),

    "en_piece_of_cake": PhraseFamily(
        id="en_piece_of_cake",
        language="en",
        canonical_form="piece of cake",
        meaning="Very easy.",
        register="informal",
        origin=(
            "1930s American slang; possibly from the cakewalk dance contests where "
            "the prize was a cake."
        ),
        variants=(
            PhraseVariant(
                surface="piece of cake",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "en_when_pigs_fly": PhraseFamily(
        id="en_when_pigs_fly",
        language="en",
        canonical_form="when pigs fly",
        meaning="Never (used to express skepticism).",
        register="informal",
        origin="16th-c. English; the impossible scenario as the marker of 'never.'",
        variants=(
            PhraseVariant(
                surface="when pigs fly",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="pigs might fly",
                match_type=MatchType.inflectional_variant,
                note="British variant.",
            ),
        ),
    ),

    "en_curiosity_killed_the_cat": PhraseFamily(
        id="en_curiosity_killed_the_cat",
        language="en",
        canonical_form="curiosity killed the cat",
        meaning="Excessive curiosity leads to harm.",
        register="neutral",
        origin=(
            "Modern proverb (early 20th c.); evolved from older 'care killed the cat' "
            "(Shakespeare, Much Ado About Nothing)."
        ),
        variants=(
            PhraseVariant(
                surface="curiosity killed the cat",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "en_close_but_no_cigar": PhraseFamily(
        id="en_close_but_no_cigar",
        language="en",
        canonical_form="close but no cigar",
        meaning="Almost succeeded, but not quite.",
        register="informal",
        origin=(
            "American 20th c.; from carnival games where cigars were prizes for "
            "hitting a target."
        ),
        variants=(
            PhraseVariant(
                surface="close but no cigar",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "en_like_two_peas_in_a_pod": PhraseFamily(
        id="en_like_two_peas_in_a_pod",
        language="en",
        canonical_form="like two peas in a pod",
        meaning="Strikingly similar; inseparable.",
        register="neutral",
        origin="Attested since 16th c.; the visual metaphor of identical peas.",
        variants=(
            PhraseVariant(
                surface="like two peas in a pod",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="two peas in a pod",
                match_type=MatchType.allusion,
            ),
        ),
    ),

    "en_the_devil_is_in_the_details": PhraseFamily(
        id="en_the_devil_is_in_the_details",
        language="en",
        canonical_form="the devil is in the details",
        meaning="Small details cause problems / matter most.",
        register="neutral",
        origin=(
            "Attributed to architect Mies van der Rohe (\"God is in the details\") — "
            "the devil version is a 20th-c. inversion."
        ),
        variants=(
            PhraseVariant(
                surface="the devil is in the details",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "en_throw_in_the_towel": PhraseFamily(
        id="en_throw_in_the_towel",
        language="en",
        canonical_form="throw in the towel",
        meaning="Give up / concede defeat.",
        register="informal",
        origin=(
            "Boxing terminology: the cornerman throws a towel into the ring to signal "
            "surrender."
        ),
        variants=(
            PhraseVariant(
                surface="throw in the towel",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="throwing in the towel",
                match_type=MatchType.inflectional_variant,
            ),
        ),
    ),

    "en_a_blessing_in_disguise": PhraseFamily(
        id="en_a_blessing_in_disguise",
        language="en",
        canonical_form="a blessing in disguise",
        meaning="Something seemingly bad that turns out beneficial.",
        register="neutral",
        origin="James Hervey's 1746 hymn; entered general English use.",
        variants=(
            PhraseVariant(
                surface="a blessing in disguise",
                match_type=MatchType.exact,
            ),
        ),
    ),

    "en_elephant_in_the_room": PhraseFamily(
        id="en_elephant_in_the_room",
        language="en",
        canonical_form="the elephant in the room",
        meaning="An obvious problem everyone is avoiding discussing.",
        register="neutral",
        origin=(
            "Mid-20th-c. American; the obvious-but-unspoken thing as a giant "
            "elephant."
        ),
        variants=(
            PhraseVariant(
                surface="the elephant in the room",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="elephant in the room",
                match_type=MatchType.allusion,
            ),
        ),
    ),

    "en_burn_bridges": PhraseFamily(
        id="en_burn_bridges",
        language="en",
        canonical_form="burn bridges",
        meaning="Cut off relationships permanently; eliminate retreat options.",
        register="neutral",
        origin=(
            "Military strategy of burning bridges to prevent retreat (Caesar at the "
            "Rubicon, Cortés in Mexico)."
        ),
        variants=(
            PhraseVariant(
                surface="burn bridges",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="burning bridges",
                match_type=MatchType.inflectional_variant,
            ),
        ),
    ),

    "en_cant_judge_a_book": PhraseFamily(
        id="en_cant_judge_a_book",
        language="en",
        canonical_form="you can't judge a book by its cover",
        meaning="Don't form opinions based on appearance.",
        register="neutral",
        origin=(
            "Mid-20th c. English; before mass-market book covers, this would have "
            "made little sense."
        ),
        variants=(
            PhraseVariant(
                surface="you can't judge a book by its cover",
                match_type=MatchType.exact,
            ),
            PhraseVariant(
                surface="don't judge a book by its cover",
                match_type=MatchType.inflectional_variant,
            ),
        ),
    ),

    "en_easier_said_than_done": PhraseFamily(
        id="en_easier_said_than_done",
        language="en",
        canonical_form="easier said than done",
        meaning="It's harder to do than to talk about.",
        register="neutral",
        origin="Attested since 15th c.",
        variants=(
            PhraseVariant(
                surface="easier said than done",
                match_type=MatchType.exact,
            ),
        ),
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
