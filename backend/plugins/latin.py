"""Latin (Classical) dictionary-mode scaffold.

BCP-47 code ``"la"``.  Provides whitespace tokenisation against an embedded
mini-lexicon of ~90 common Latin headwords.  This is an honest scaffold for
the dictionary-mode pathway — it is NOT a morphological parser.

What this plugin does
─────────────────────
  - Sentence splitting on standard terminal punctuation.
  - Whitespace tokenisation with punctuation stripping.
  - Macron-normalised lookup (``amāre`` → ``amare``) so texts with and
    without macrons resolve to the same canonical form.
  - For recognised citation forms: emits ``gloss``, ``citation_form``, and
    ``grammar_note`` fields so the dictionary builder produces a structured
    lesson entry.
  - For unrecognised tokens (most inflected forms): emits a minimal
    vocabulary candidate with a ``confidence_note`` explaining the limit.

What this plugin does NOT claim
────────────────────────────────
  - Morphological analysis.  Latin has a rich inflectional system; reliable
    automated parsing requires a dedicated tool (CLTK, Whitaker's Words,
    stanza-la, etc.).  This plugin makes no attempt to parse inflected forms.
  - POS tagging.
  - Lemmatisation of inflected forms.  Only citation forms (nominative
    singular for nouns/adjectives, 1st-person singular present active for
    verbs) are in the lexicon.

Upgrade path
────────────
  When CLTK (``pip install cltk``) or a comparable library is available,
  this plugin can be promoted:
    morphology_depth      → shallow / rich
    analysis_depth        → morphology_light / full
    lesson_modes_supported → ["morphology", "vocabulary", "dictionary"]

Pedagogical note on citation forms
────────────────────────────────────
  Classical Latin dictionaries cite:
    Nouns:      nominative singular, genitive singular, gender
                e.g.  ``amor, amōris m.``
    Verbs:      principal parts (1sg present, infinitive, 1sg perfect, supine)
                e.g.  ``amō, amāre, amāvī, amātum``
    Adjectives: masculine, feminine, neuter nominative singular
                e.g.  ``bonus, bona, bonum``
  These forms are stored in ``lesson_data["citation_form"]`` so the
  dictionary lesson can display them to learners.
"""
from __future__ import annotations

import re
import unicodedata

from backend.schemas.language import LanguageCapabilities, NuanceCapabilities
from backend.schemas.parse import CandidateObject, CandidateSentenceResult

# ── Sentence splitting ─────────────────────────────────────────────────────────

_SENTENCE_RE = re.compile(r"[^.!?\n]+[.!?\n]?")

# ── Token cleaning ─────────────────────────────────────────────────────────────
# Strip leading/trailing Latin prose punctuation before lexicon lookup.

_STRIP_PUNCT = re.compile(r"^[.,;:!?()\[\]\"'«»—\-]+|[.,;:!?()\[\]\"'«»—\-]+$")

# ── Macron normalisation ───────────────────────────────────────────────────────
# Map composed Latin letters with macrons to their base ASCII equivalents so
# texts with macrons (``āmō``) and without (``amo``) hit the same lexicon key.

_MACRON_TABLE = str.maketrans(
    "āēīōūĀĒĪŌŪ",
    "aeiouAEIOU",
)


def _normalise(token: str) -> str:
    """Strip macrons and return lowercase ASCII for lexicon lookup."""
    # NFD decomposition separates combining marks, then we remove them.
    nfd = unicodedata.normalize("NFD", token)
    # Remove combining macron (U+0304) and any other combining chars.
    stripped = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    # Translate any remaining precomposed macron letters just in case.
    stripped = stripped.translate(_MACRON_TABLE)
    return stripped.lower()


# ── Lexicon ────────────────────────────────────────────────────────────────────
# Keys are normalised (macron-free, lowercase) citation forms.
# Values are tuples: (citation_with_macrons, gloss, grammar_note, pos)
#
# Entries cover the ~90 most commonly encountered headwords in introductory
# Classical Latin texts.  Inflected forms are NOT included — learners are
# directed to a full parser for those.

_LexEntry = tuple[str, str, str, str]   # (citation, gloss, grammar, pos)

_LEXICON: dict[str, _LexEntry] = {

    # ── Esse (be) — highly irregular ─────────────────────────────────────────
    "sum":    ("sum, esse, fuī, futūrum",
               "be, exist",
               "highly irregular verb; principal parts: sum, esse, fuī, futūrum",
               "verb"),
    "esse":   ("sum, esse, fuī, futūrum",
               "be, exist (infinitive of sum)",
               "present infinitive of sum (esse); most common Latin verb",
               "verb"),

    # ── 1st conjugation verbs (-āre) ─────────────────────────────────────────
    "amo":    ("amō, amāre, amāvī, amātum",
               "love, like, be fond of",
               "1st conjugation; principal parts: amō amāre amāvī amātum",
               "verb"),
    "laudo":  ("laudō, laudāre, laudāvī, laudātum",
               "praise, commend, approve",
               "1st conjugation; principal parts: laudō laudāre laudāvī laudātum",
               "verb"),
    "porto":  ("portō, portāre, portāvī, portātum",
               "carry, bear, bring",
               "1st conjugation; principal parts: portō portāre portāvī portātum",
               "verb"),
    "voco":   ("vocō, vocāre, vocāvī, vocātum",
               "call, summon, name, invite",
               "1st conjugation; principal parts: vocō vocāre vocāvī vocātum",
               "verb"),
    "narro":  ("narrō, narrāre, narrāvī, narrātum",
               "tell, relate, narrate",
               "1st conjugation; principal parts: narrō narrāre narrāvī narrātum",
               "verb"),
    "paro":   ("parō, parāre, parāvī, parātum",
               "prepare, make ready, obtain",
               "1st conjugation; principal parts: parō parāre parāvī parātum",
               "verb"),
    "clamo":  ("clāmō, clāmāre, clāmāvī, clāmātum",
               "shout, cry out, proclaim",
               "1st conjugation; principal parts: clāmō clāmāre clāmāvī clāmātum",
               "verb"),
    "servo":  ("servō, servāre, servāvī, servātum",
               "save, preserve, guard, keep",
               "1st conjugation; principal parts: servō servāre servāvī servātum",
               "verb"),
    "specto": ("spectō, spectāre, spectāvī, spectātum",
               "watch, observe, look at",
               "1st conjugation; principal parts: spectō spectāre spectāvī spectātum",
               "verb"),

    # ── 2nd conjugation verbs (-ēre) ─────────────────────────────────────────
    "video":  ("videō, vidēre, vīdī, vīsum",
               "see, look at, observe, understand",
               "2nd conjugation; principal parts: videō vidēre vīdī vīsum",
               "verb"),
    "habeo":  ("habeō, habēre, habuī, habitum",
               "have, hold, consider, regard",
               "2nd conjugation; principal parts: habeō habēre habuī habitum",
               "verb"),
    "moneo":  ("moneō, monēre, monuī, monitum",
               "warn, advise, remind, teach",
               "2nd conjugation; principal parts: moneō monēre monuī monitum",
               "verb"),
    "teneo":  ("teneō, tenēre, tenuī, tentum",
               "hold, keep, grasp, maintain",
               "2nd conjugation; principal parts: teneō tenēre tenuī tentum",
               "verb"),
    "timeo":  ("timeō, timēre, timuī",
               "fear, be afraid of",
               "2nd conjugation (no supine); principal parts: timeō timēre timuī",
               "verb"),
    "doceo":  ("doceō, docēre, docuī, doctum",
               "teach, instruct, inform",
               "2nd conjugation; principal parts: doceō docēre docuī doctum",
               "verb"),
    "maneo":  ("maneō, manēre, mānsī, mānsum",
               "remain, stay, wait for, endure",
               "2nd conjugation; principal parts: maneō manēre mānsī mānsum",
               "verb"),

    # ── 3rd conjugation verbs (-ere) ─────────────────────────────────────────
    "lego":   ("legō, legere, lēgī, lēctum",
               "read, choose, gather, collect",
               "3rd conjugation; principal parts: legō legere lēgī lēctum",
               "verb"),
    "dico":   ("dīcō, dīcere, dīxī, dictum",
               "say, speak, tell, call",
               "3rd conjugation; principal parts: dīcō dīcere dīxī dictum",
               "verb"),
    "facio":  ("faciō, facere, fēcī, factum",
               "make, do, cause, perform",
               "3rd conjugation (io-stem); principal parts: faciō facere fēcī factum",
               "verb"),
    "pono":   ("pōnō, pōnere, posuī, positum",
               "put, place, set down, lay",
               "3rd conjugation; principal parts: pōnō pōnere posuī positum",
               "verb"),
    "curro":  ("currō, currere, cucurrī, cursum",
               "run, hurry, move quickly",
               "3rd conjugation; principal parts: currō currere cucurrī cursum",
               "verb"),
    "duco":   ("dūcō, dūcere, dūxī, ductum",
               "lead, guide, draw, think",
               "3rd conjugation; principal parts: dūcō dūcere dūxī ductum",
               "verb"),
    "scribo": ("scrībō, scrībere, scrīpsī, scrīptum",
               "write, draw, compose",
               "3rd conjugation; principal parts: scrībō scrībere scrīpsī scrīptum",
               "verb"),
    "mitto":  ("mittō, mittere, mīsī, missum",
               "send, let go, throw",
               "3rd conjugation; principal parts: mittō mittere mīsī missum",
               "verb"),
    "capio":  ("capiō, capere, cēpī, captum",
               "take, seize, capture, choose",
               "3rd conjugation (io-stem); principal parts: capiō capere cēpī captum",
               "verb"),
    "credo":  ("crēdō, crēdere, crēdidī, crēditum",
               "believe, trust, entrust",
               "3rd conjugation; principal parts: crēdō crēdere crēdidī crēditum",
               "verb"),

    # ── 4th conjugation verbs (-īre) ─────────────────────────────────────────
    "audio":  ("audiō, audīre, audīvī, audītum",
               "hear, listen to",
               "4th conjugation; principal parts: audiō audīre audīvī audītum",
               "verb"),
    "venio":  ("veniō, venīre, vēnī, ventum",
               "come, arrive, appear",
               "4th conjugation; principal parts: veniō venīre vēnī ventum",
               "verb"),
    "sentio": ("sentiō, sentīre, sēnsī, sēnsum",
               "feel, perceive, experience, think",
               "4th conjugation; principal parts: sentiō sentīre sēnsī sēnsum",
               "verb"),

    # ── 1st declension nouns (feminine, -a -ae) ──────────────────────────────
    "aqua":    ("aqua, aquae f.", "water",
                "1st declension feminine noun; gen. sg. aquae", "noun"),
    "terra":   ("terra, terrae f.", "land, earth, ground, country",
                "1st declension feminine noun; gen. sg. terrae", "noun"),
    "vita":    ("vīta, vītae f.", "life",
                "1st declension feminine noun; gen. sg. vītae", "noun"),
    "puella":  ("puella, puellae f.", "girl",
                "1st declension feminine noun; gen. sg. puellae", "noun"),
    "femina":  ("fēmina, fēminae f.", "woman",
                "1st declension feminine noun; gen. sg. fēminae", "noun"),
    "via":     ("via, viae f.", "road, way, path, journey",
                "1st declension feminine noun; gen. sg. viae", "noun"),
    "lingua":  ("lingua, linguae f.", "language, tongue",
                "1st declension feminine noun; gen. sg. linguae", "noun"),
    "silva":   ("silva, silvae f.", "forest, woods",
                "1st declension feminine noun; gen. sg. silvae", "noun"),
    "patria":  ("patria, patriae f.", "homeland, fatherland",
                "1st declension feminine noun; gen. sg. patriae", "noun"),
    "luna":    ("lūna, lūnae f.", "moon",
                "1st declension feminine noun; gen. sg. lūnae", "noun"),
    "gloria":  ("glōria, glōriae f.", "glory, fame, renown",
                "1st declension feminine noun; gen. sg. glōriae", "noun"),
    "porta":   ("porta, portae f.", "gate, door, entrance",
                "1st declension feminine noun; gen. sg. portae", "noun"),
    "filia":   ("fīlia, fīliae f.", "daughter",
                "1st declension feminine noun; gen. sg. fīliae", "noun"),

    # ── 2nd declension nouns (masculine, -us -ī) ─────────────────────────────
    "amicus":  ("amīcus, amīcī m.", "friend, ally",
                "2nd declension masculine noun; gen. sg. amīcī", "noun"),
    "dominus": ("dominus, dominī m.", "lord, master, owner",
                "2nd declension masculine noun; gen. sg. dominī", "noun"),
    "filius":  ("fīlius, fīliī m.", "son",
                "2nd declension masculine noun; gen. sg. fīliī", "noun"),
    "puer":    ("puer, puerī m.", "boy, child",
                "2nd declension masculine noun (nom. -er, no -us); gen. sg. puerī",
                "noun"),
    "servus":  ("servus, servī m.", "slave, servant",
                "2nd declension masculine noun; gen. sg. servī", "noun"),
    "vir":     ("vir, virī m.", "man, husband, hero",
                "2nd declension masculine noun; gen. sg. virī", "noun"),
    "deus":    ("deus, deī m.", "god, deity",
                "2nd declension masculine noun; gen. sg. deī", "noun"),

    # ── 2nd declension nouns (neuter, -um -ī) ────────────────────────────────
    "bellum":  ("bellum, bellī n.", "war",
                "2nd declension neuter noun; gen. sg. bellī", "noun"),
    "verbum":  ("verbum, verbī n.", "word, verb",
                "2nd declension neuter noun; gen. sg. verbī", "noun"),
    "regnum":  ("regnum, regnī n.", "kingdom, realm, royal power",
                "2nd declension neuter noun; gen. sg. regnī", "noun"),
    "templum": ("templum, templī n.", "temple, shrine",
                "2nd declension neuter noun; gen. sg. templī", "noun"),
    "oppidum": ("oppidum, oppidī n.", "town, fortified town",
                "2nd declension neuter noun; gen. sg. oppidī", "noun"),

    # ── 3rd declension nouns ──────────────────────────────────────────────────
    "rex":     ("rēx, rēgis m.", "king",
                "3rd declension masculine noun; gen. sg. rēgis", "noun"),
    "pax":     ("pāx, pācis f.", "peace",
                "3rd declension feminine noun; gen. sg. pācis", "noun"),
    "lex":     ("lēx, lēgis f.", "law, rule, statute",
                "3rd declension feminine noun; gen. sg. lēgis", "noun"),
    "vox":     ("vōx, vōcis f.", "voice, word, sound",
                "3rd declension feminine noun; gen. sg. vōcis", "noun"),
    "homo":    ("homō, hominis m.", "person, human being, man",
                "3rd declension masculine noun; gen. sg. hominis", "noun"),
    "amor":    ("amor, amōris m.", "love, desire, passion",
                "3rd declension masculine noun; gen. sg. amōris", "noun"),
    "corpus":  ("corpus, corporis n.", "body",
                "3rd declension neuter noun (s-stem); gen. sg. corporis", "noun"),
    "tempus":  ("tempus, temporis n.", "time, season",
                "3rd declension neuter noun (s-stem); gen. sg. temporis", "noun"),
    "nomen":   ("nōmen, nōminis n.", "name, noun",
                "3rd declension neuter noun; gen. sg. nōminis", "noun"),
    "urbs":    ("urbs, urbis f.", "city",
                "3rd declension feminine noun (i-stem); gen. sg. urbis", "noun"),
    "mons":    ("mōns, montis m.", "mountain, hill",
                "3rd declension masculine noun (i-stem); gen. sg. montis", "noun"),
    "pater":   ("pater, patris m.", "father",
                "3rd declension masculine noun; gen. sg. patris", "noun"),
    "mater":   ("māter, mātris f.", "mother",
                "3rd declension feminine noun; gen. sg. mātris", "noun"),
    "miles":   ("mīles, mīlitis m.", "soldier",
                "3rd declension masculine noun; gen. sg. mīlitis", "noun"),
    "caput":   ("caput, capitis n.", "head, leader, source",
                "3rd declension neuter noun; gen. sg. capitis", "noun"),
    "dux":     ("dux, ducis m.", "leader, general, guide",
                "3rd declension masculine noun; gen. sg. ducis", "noun"),

    # ── Adjectives (1st/2nd declension) ──────────────────────────────────────
    "bonus":    ("bonus, bona, bonum", "good, kind, brave",
                 "1st/2nd declension adjective; masc. nom. sg.", "adjective"),
    "malus":    ("malus, mala, malum", "bad, evil, wicked",
                 "1st/2nd declension adjective; masc. nom. sg.", "adjective"),
    "magnus":   ("magnus, magna, magnum", "great, large, important",
                 "1st/2nd declension adjective; masc. nom. sg.", "adjective"),
    "parvus":   ("parvus, parva, parvum", "small, little, unimportant",
                 "1st/2nd declension adjective; masc. nom. sg.", "adjective"),
    "multus":   ("multus, multa, multum", "much, many, great in number",
                 "1st/2nd declension adjective; masc. nom. sg.", "adjective"),
    "novus":    ("novus, nova, novum", "new, young, fresh, unusual",
                 "1st/2nd declension adjective; masc. nom. sg.", "adjective"),
    "longus":   ("longus, longa, longum", "long, tall, far",
                 "1st/2nd declension adjective; masc. nom. sg.", "adjective"),
    "altus":    ("altus, alta, altum", "high, deep, tall, lofty",
                 "1st/2nd declension adjective; masc. nom. sg.", "adjective"),
    "sanctus":  ("sānctus, sāncta, sānctum", "holy, sacred, venerable",
                 "1st/2nd declension adjective; masc. nom. sg.", "adjective"),
    "antiquus": ("antīquus, antīqua, antīquum", "ancient, old, former",
                 "1st/2nd declension adjective; masc. nom. sg.", "adjective"),
    "clarus":   ("clārus, clāra, clārum", "clear, bright, famous, illustrious",
                 "1st/2nd declension adjective; masc. nom. sg.", "adjective"),
    "liber":    ("līber, lībera, līberum", "free, unrestricted",
                 "1st/2nd declension adjective (nom. -er form); masc. nom. sg.",
                 "adjective"),
    "pulcher":  ("pulcher, pulchra, pulchrum", "beautiful, handsome, fine",
                 "1st/2nd declension adjective (nom. -er form); masc. nom. sg.",
                 "adjective"),

    # ── Personal pronouns ─────────────────────────────────────────────────────
    "ego":  ("ego (nōs)", "I, me",
             "1st person pronoun, singular; plural nōs", "pronoun"),
    "tu":   ("tū (vōs)", "you (singular)",
             "2nd person pronoun, singular; plural vōs", "pronoun"),
    "nos":  ("nōs", "we, us",
             "1st person pronoun, plural; singular ego", "pronoun"),
    "vos":  ("vōs", "you, you all (plural)",
             "2nd person pronoun, plural; singular tū", "pronoun"),

    # ── Prepositions ─────────────────────────────────────────────────────────
    "in":   ("in (+ abl. / + acc.)",
             "in, on (+ abl.); into, onto (+ acc.)",
             "preposition: + ablative for location, + accusative for motion toward",
             "preposition"),
    "ad":   ("ad (+ acc.)", "to, toward, near, at",
             "preposition governing accusative", "preposition"),
    "cum":  ("cum (+ abl.)", "with, together with, in company of",
             "preposition governing ablative", "preposition"),
    "per":  ("per (+ acc.)", "through, throughout, by means of, during",
             "preposition governing accusative", "preposition"),
    "ex":   ("ex / ē (+ abl.)", "out of, from, since, after",
             "preposition governing ablative; ex before consonants, ē before vowels",
             "preposition"),
    "de":   ("dē (+ abl.)", "about, concerning, from, down from",
             "preposition governing ablative", "preposition"),
    "sub":  ("sub (+ abl. / + acc.)",
             "under, below (+ abl.); up to, toward (+ acc.)",
             "preposition: + ablative for rest beneath, + accusative for motion under",
             "preposition"),
    "ante": ("ante (+ acc.)", "before, in front of, earlier than",
             "preposition governing accusative", "preposition"),
    "post": ("post (+ acc.)", "after, behind, later than",
             "preposition governing accusative", "preposition"),
    "sine": ("sine (+ abl.)", "without",
             "preposition governing ablative", "preposition"),
    "pro":  ("prō (+ abl.)", "for, on behalf of, in front of, instead of",
             "preposition governing ablative", "preposition"),
    "ab":   ("ab / ā (+ abl.)", "from, away from, by (agent)",
             "preposition governing ablative; ab before vowels/h, ā before consonants",
             "preposition"),

    # ── Conjunctions & adverbs ────────────────────────────────────────────────
    "et":    ("et", "and, also, even", "coordinating conjunction", "conjunction"),
    "sed":   ("sed", "but, however, yet", "adversative conjunction", "conjunction"),
    "aut":   ("aut", "or, either", "disjunctive conjunction", "conjunction"),
    "non":   ("nōn", "not", "negation adverb", "adverb"),
    "iam":   ("iam", "now, already, soon, by now",
              "temporal adverb", "adverb"),
    "sic":   ("sīc", "thus, so, in this way",
              "demonstrative adverb", "adverb"),
    "nec":   ("nec / neque", "and not, nor, neither",
              "negative copulative conjunction; variant neque", "conjunction"),
    "neque": ("neque / nec", "nor, and not",
              "negative copulative conjunction; variant nec", "conjunction"),
    "nam":   ("nam", "for, because, indeed (explanatory)",
              "causal/explanatory particle", "conjunction"),
    "ubi":   ("ubi", "where, when",
              "relative/interrogative adverb of place/time", "adverb"),
    "nunc":  ("nunc", "now, at present",
              "temporal adverb", "adverb"),
    "tum":   ("tum / tunc", "then, at that time, at this point",
              "temporal adverb; variant tunc in some texts", "adverb"),
    "tunc":  ("tunc / tum", "then, at that time",
              "temporal adverb; variant tum", "adverb"),
    "semper":("semper", "always, ever, at all times",
              "temporal adverb", "adverb"),
    "saepe": ("saepe", "often, frequently",
              "temporal adverb", "adverb"),
    "numquam":("numquam", "never",
               "negative temporal adverb", "adverb"),
    "si":    ("sī", "if, in case that",
              "conditional conjunction", "conjunction"),
    "ut":    ("ut", "as, when, in order that, that",
              "conjunction (multiple uses: final, consecutive, temporal, comparative)",
              "conjunction"),
    "quod":  ("quod", "because, that, the fact that",
              "causal/substantive conjunction; also neut. nom./acc. of quī",
              "conjunction"),
    "ergo":  ("ergō", "therefore, consequently",
              "inferential adverb/conjunction", "adverb"),

    # ── Numerals ──────────────────────────────────────────────────────────────
    "unus":   ("ūnus, ūna, ūnum", "one",
               "numeral adjective, 1st/2nd declension (irregular gen. -īus, dat. -ī)",
               "numeral"),
    "duo":    ("duo, duae, duo", "two",
               "numeral adjective, irregular declension", "numeral"),
    "tres":   ("trēs, tria", "three",
               "numeral adjective, 3rd declension", "numeral"),
    "decem":  ("decem", "ten", "indeclinable numeral", "numeral"),
    "centum": ("centum", "one hundred", "indeclinable numeral", "numeral"),
    "mille":  ("mīlle (pl. mīlia, mīlium)", "one thousand",
               "singular indeclinable adjective; plural mīlia (3rd decl. neuter noun)",
               "numeral"),
}

# Confidence note appended when the token is NOT in the lexicon.
_UNKNOWN_NOTE = (
    "Latin dictionary scaffold \u2014 citation forms only. "
    "Inflected forms (e.g. am\u0101mus, r\u0113gem, puell\u0101rum) are not "
    "recognised. Use a full Latin morphological analyser (CLTK, Whitaker\u2019s "
    "Words) for complete parsing."
)


class LatinPlugin:
    """Classical Latin dictionary-mode plugin.

    Provides sentence splitting and whitespace tokenisation against a small
    embedded lexicon.  This is a foundation scaffold for the dead-language
    dictionary pathway — not a replacement for a full Latin parser.

    See module docstring for honest-claims details and upgrade path.
    """

    language_code = "la"
    display_name  = "Latin (Classical \u2014 dictionary scaffold)"
    direction     = "ltr"
    capabilities  = LanguageCapabilities(
        code="la",
        display_name="Latin (Classical \u2014 dictionary scaffold)",
        direction="ltr",
        script_family="latin",
        tokenization_mode="whitespace",
        morphology_depth="none",
        lesson_modes_supported=["dictionary"],
        # ── v2 fields ──────────────────────────────────────────────────────
        analysis_depth="dictionary",          # citation-form lookup only
        segmentation_quality="medium",        # standard sentence punctuation
        tokenization_quality="medium",        # whitespace; punctuation stripped
        morphology_quality="none",            # no inflectional analysis
        syntax_support=False,
        idiom_detection=False,
        tts_lang_tag="la",                    # browser TTS for Latin (varies)
        transliteration_scheme=None,          # Latin already uses Latin script
        nuance_capabilities=NuanceCapabilities(
            idioms="none",
            phrase_families="none",
            literary_references="none",
            cultural_references="none",
            etymology="none",
            formality_register="none",
            grammar_nuance="none",
            pronunciation_tts="stub",         # la TTS unreliable across browsers
            transliteration="none",
            proverb_tradition="none",
            classical_or_scriptural_allusion="none",
        ),
    )

    def __init__(self) -> None:
        self.lesson_store: dict[str, CandidateObject] = {}

    # ── LanguagePlugin protocol ─────────────────────────────────────────────────

    def analyze_text(self, text: str) -> list[CandidateSentenceResult]:
        return [self.analyze_sentence(s) for s in self.split_sentences(text)]

    def split_sentences(self, text: str) -> list[str]:
        return [
            m.group(0).strip()
            for m in _SENTENCE_RE.finditer(text)
            if m.group(0).strip()
        ]

    def analyze_sentence(self, sentence: str) -> CandidateSentenceResult:
        candidates: list[CandidateObject] = []
        seen_canonical: set[str] = set()

        for raw_token in sentence.split():
            # Strip surrounding punctuation, then normalise for lookup.
            token = _STRIP_PUNCT.sub("", raw_token)
            if not token:
                continue
            canonical = _normalise(token)
            if not canonical or canonical in seen_canonical:
                continue
            seen_canonical.add(canonical)

            entry = _LEXICON.get(canonical)
            if entry is not None:
                citation, gloss, grammar, pos = entry
                lesson_data: dict = {
                    "citation_form": citation,
                    "gloss": gloss,
                    "grammar_note": grammar,
                    "pos": pos.upper(),
                    "cefr_level": "A1",
                }
                confidence = 0.85
            else:
                lesson_data = {"confidence_note": _UNKNOWN_NOTE}
                confidence = None

            candidates.append(
                CandidateObject(
                    canonical_form=canonical,
                    surface_form=token,
                    type="vocabulary",
                    label=token,
                    lesson_data=lesson_data,
                    confidence=confidence,
                )
            )

        return CandidateSentenceResult(text=sentence, candidates=candidates)

    def get_lesson(self, object_id: str) -> CandidateObject | None:
        return self.lesson_store.get(object_id)


def create_plugin() -> LatinPlugin:
    return LatinPlugin()
