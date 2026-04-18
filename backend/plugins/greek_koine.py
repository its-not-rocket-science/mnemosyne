"""Koine Greek dictionary-mode scaffold.

BCP-47 code ``"grc"``.  Provides sentence splitting and whitespace
tokenisation against an embedded lexicon of ~100 core New Testament /
Koine Greek headwords.  This is an honest scaffold for the dead-language
dictionary pathway — it is NOT a morphological parser.

What this plugin does
─────────────────────
  - Sentence splitting on terminal Greek or ASCII punctuation (including
    the Greek full stop ·, the middle dot ·, and the Greek question mark ;).
  - Whitespace tokenisation with punctuation stripping.
  - Diacritic normalisation: strips polytonic accents (acute, grave,
    circumflex), breathing marks (rough ῾ and smooth ᾿), iota subscript,
    and diaeresis before lexicon lookup — so ``λόγος``, ``λογος``, and
    ``ΛΟΓΟΣ`` all resolve to the key ``λογος``.
  - For recognised lemmas: emits ``gloss``, ``citation_form``, and
    ``grammar_note`` fields so the dictionary lesson builder produces a
    structured lesson entry.
  - For unrecognised tokens: emits a minimal vocabulary candidate with a
    ``confidence_note`` explaining the limit.

What this plugin does NOT claim
────────────────────────────────
  - Morphological analysis.  Koine Greek has a rich inflectional system
    (5 cases, 3 numbers, 4 moods, 3 voices, 3 persons, 3 genders).  Reliable
    automated parsing requires a dedicated tool (CLTK, Morpheus, GlobaLeaks).
  - Lemmatisation of inflected forms.  The lexicon contains only
    dictionary headword (lexical) forms.
  - POS tagging.

Upgrade path
────────────
  When CLTK (``pip install cltk``) or stanza Greek is available:
    morphology_depth      → shallow / rich
    analysis_depth        → morphology_light / full
    lesson_modes_supported → ["morphology", "vocabulary", "dictionary"]

Transliteration
───────────────
  The plugin exports a ``transliterate()`` helper (Society of Biblical
  Literature / beta-code-inspired scheme) so the frontend can display a
  Latin-script reading hint alongside the Greek text.  This is reported in
  ``lesson_data["romanized"]`` for every token and surfaced via the
  script-view toggle (native / romanized / both).

Citation form conventions
─────────────────────────
  Nouns:      nominative singular, genitive singular, article
              e.g. ``λόγος, λόγου, ὁ``
  Verbs:      1st person singular present active indicative
              e.g. ``λύω``
  Adjectives: masculine, feminine, neuter nominative singular
              e.g. ``ἀγαθός, ἀγαθή, ἀγαθόν``
  Pronouns:   nominative form
  Particles / conjunctions / adverbs: undeclined form
"""
from __future__ import annotations

import re
import unicodedata

from backend.schemas.language import LanguageCapabilities
from backend.schemas.parse import CandidateObject, CandidateSentenceResult

# ── Sentence splitting ────────────────────────────────────────────────────────
# Greek terminal punctuation: ASCII .!?, Greek semicolon ; (U+003B, looks the
# same but is used as a question mark in ancient texts), middle dot · (U+00B7
# used as comma in some editions), Greek full stop (·), and line breaks.
# We treat the semicolon as sentence-final when it appears at a word boundary.

_SENTENCE_RE = re.compile(r"[^.!?;\n·]+[.!?;\n·]?")

# ── Token cleaning ────────────────────────────────────────────────────────────
# Strip leading/trailing punctuation before lookup.  Includes both ASCII and
# common Greek editorial punctuation.

_STRIP_PUNCT = re.compile(r"^[.,;:!?()\[\]\"'«»—\-·\u037e\u00b7]+|[.,;:!?()\[\]\"'«»—\-·\u037e\u00b7]+$")

# Greek semicolon / question mark U+037E looks identical to ASCII ; but is a
# separate Unicode point — add both to the strip pattern.


# ── Diacritic normalisation ───────────────────────────────────────────────────
# Polytonic Greek diacritics are Unicode combining characters.  NFD
# decomposition separates them from their base letters so we can strip them.
#
# Categories stripped (all fall under Unicode "Mn" = non-spacing mark):
#   U+0301 combining acute accent
#   U+0300 combining grave accent
#   U+0342 combining Greek perispomeni (circumflex)
#   U+0313 combining comma above (smooth breathing)
#   U+0314 combining reversed comma above (rough breathing)
#   U+0308 combining diaeresis
#   U+0345 combining Greek ypogegrammeni (iota subscript)

def _normalise(token: str) -> str:
    """Return the lowercase base-letter form of *token* for lexicon lookup."""
    nfd = unicodedata.normalize("NFD", token)
    # Remove every combining character (category Mn).
    stripped = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    return stripped.lower()


# ── Simple transliteration ───────────────────────────────────────────────────
# SBL-style romanisation (simplified — no aspirate or accent diacritics on the
# output).  Used only for the ``romanized`` field so the script-view toggle has
# something to show; this is not a phonological reconstruction.

_TRANSLIT: dict[str, str] = {
    "α": "a",  "β": "b",  "γ": "g",  "δ": "d",  "ε": "e",
    "ζ": "z",  "η": "ē",  "θ": "th", "ι": "i",  "κ": "k",
    "λ": "l",  "μ": "m",  "ν": "n",  "ξ": "x",  "ο": "o",
    "π": "p",  "ρ": "r",  "σ": "s",  "ς": "s",  "τ": "t",
    "υ": "y",  "φ": "ph", "χ": "ch", "ψ": "ps", "ω": "ō",
}


def transliterate(word: str) -> str:
    """Return a simplified SBL-style romanisation of *word*."""
    base = _normalise(word)
    return "".join(_TRANSLIT.get(ch, ch) for ch in base)


# ── Lexicon ───────────────────────────────────────────────────────────────────
# Keys are normalised (diacritic-free, lowercase) lexical forms.
# Values: (citation_with_diacritics, gloss, grammar_note, pos)
#
# Covers the ~100 highest-frequency headwords in the Greek New Testament
# (based on the Mounce / UBS GNT frequency lists).  Inflected forms are NOT
# included; learners are directed to a full morphological analyser for those.

_LexEntry = tuple[str, str, str, str]  # (citation, gloss, grammar, pos)

_LEXICON: dict[str, _LexEntry] = {

    # ── εἰμί — be (most common Greek verb) ────────────────────────────────────
    "ειμι": ("εἰμί",
             "be, exist, am",
             "highly irregular verb; principal parts: εἰμί, ἔσομαι; "
             "2sg εἶ, 3sg ἐστίν, 1pl ἐσμέν, 3pl εἰσίν",
             "verb"),

    # ── Common verbs ──────────────────────────────────────────────────────────
    "λεγω":  ("λέγω",
              "say, speak, tell",
              "1st aorist εἶπον (suppletive); fut. ἐρῶ; "
              "most frequent NT verb after εἰμί",
              "verb"),
    "εχω":   ("ἔχω",
              "have, hold, possess",
              "2nd aorist ἔσχον; fut. ἕξω",
              "verb"),
    "γινομαι": ("γίνομαι",
                "become, be, happen, come to be",
                "deponent; 2nd aorist ἐγενόμην; pf. γέγονα",
                "verb"),
    "ερχομαι": ("ἔρχομαι",
                "come, go",
                "highly irregular; 2nd aorist ἦλθον; fut. ἐλεύσομαι",
                "verb"),
    "ποιεω":  ("ποιέω",
               "do, make, cause",
               "contracted -έω verb; aorist ἐποίησα",
               "verb"),
    "ακουω":  ("ἀκούω",
               "hear, listen to",
               "aorist ἤκουσα; takes genitive of person, accusative of thing",
               "verb"),
    "βλεπω":  ("βλέπω",
               "see, look at",
               "aorist ἔβλεψα",
               "verb"),
    "οραω":   ("ὁράω",
               "see, perceive",
               "suppletive: pres. ὁράω, aorist εἶδον, pf. ἑώρακα",
               "verb"),
    "γινωσκω": ("γινώσκω",
                "know, come to know, understand",
                "2nd aorist ἔγνων; pf. ἔγνωκα",
                "verb"),
    "πιστευω": ("πιστεύω",
                "believe, trust, have faith in",
                "takes dative of person or εἰς + accusative",
                "verb"),
    "λαμβανω": ("λαμβάνω",
                "take, receive",
                "2nd aorist ἔλαβον; pf. εἴληφα",
                "verb"),
    "αγαπαω":  ("ἀγαπάω",
                "love (unconditionally), regard highly",
                "contracted -άω verb; aorist ἠγάπησα",
                "verb"),
    "αποστελλω": ("ἀποστέλλω",
                  "send (out), commission",
                  "compound of ἀπό + στέλλω; aorist ἀπέστειλα; pf. ἀπέσταλκα",
                  "verb"),
    "εισερχομαι": ("εἰσέρχομαι",
                   "enter, go into",
                   "compound deponent; 2nd aorist εἰσῆλθον",
                   "verb"),
    "εξερχομαι": ("ἐξέρχομαι",
                  "go out, come out",
                  "compound deponent; 2nd aorist ἐξῆλθον",
                  "verb"),
    "λυω":    ("λύω",
               "loose, release, dissolve; (gram.) the paradigm verb",
               "aorist ἔλυσα; pf. λέλυκα; standard example in Greek grammars",
               "verb"),
    "γραφω":  ("γράφω",
               "write, record",
               "aorist ἔγραψα; pf. γέγραφα",
               "verb"),
    "ζαω":    ("ζάω",
               "live, be alive",
               "contracted -άω verb; fut. ζήσω",
               "verb"),
    "θελω":   ("θέλω",
               "will, wish, want, desire",
               "also spelled ἐθέλω in some texts; aorist ἠθέλησα",
               "verb"),
    "δυναμαι": ("δύναμαι",
                "be able, can, have power",
                "deponent; always middle/passive forms",
                "verb"),
    "απολλυμι": ("ἀπόλλυμι",
                 "destroy; (mid.) perish, be lost",
                 "compound of ἀπό + ὄλλυμι; 2nd aorist ἀπωλόμην (mid.)",
                 "verb"),

    # ── Key nouns ─────────────────────────────────────────────────────────────
    "θεος":   ("θεός, θεοῦ, ὁ",
               "God, god, deity",
               "2nd declension masculine; with article ὁ θεός = the God",
               "noun"),
    "κυριος": ("κύριος, κυρίου, ὁ",
               "Lord, master, owner",
               "2nd declension masculine; frequent title for Jesus and God",
               "noun"),
    "λογος":  ("λόγος, λόγου, ὁ",
               "word, message, reason, account",
               "2nd declension masculine; opening of John's Gospel: ἐν ἀρχῇ ἦν ὁ λόγος",
               "noun"),
    "ανθρωπος": ("ἄνθρωπος, ἀνθρώπου, ὁ",
                 "person, human being, man",
                 "2nd declension masculine",
                 "noun"),
    "υιος":   ("υἱός, υἱοῦ, ὁ",
               "son",
               "2nd declension masculine; υἱὸς τοῦ θεοῦ = Son of God",
               "noun"),
    "πατηρ":  ("πατήρ, πατρός, ὁ",
               "father",
               "3rd declension masculine; voc. πάτερ",
               "noun"),
    "αρχη":   ("ἀρχή, ἀρχῆς, ἡ",
               "beginning, origin, rule, authority",
               "1st declension feminine; ἐν ἀρχῇ = in the beginning",
               "noun"),
    "ημερα":  ("ἡμέρα, ἡμέρας, ἡ",
               "day",
               "1st declension feminine",
               "noun"),
    "οικος":  ("οἶκος, οἴκου, ὁ",
               "house, home, household",
               "2nd declension masculine",
               "noun"),
    "καρδια": ("καρδία, καρδίας, ἡ",
               "heart (physical and metaphorical)",
               "1st declension feminine",
               "noun"),
    "κοσμος": ("κόσμος, κόσμου, ὁ",
               "world, universe, order, adornment",
               "2nd declension masculine",
               "noun"),
    "ζωη":    ("ζωή, ζωῆς, ἡ",
               "life",
               "1st declension feminine; ζωὴ αἰώνιος = eternal life",
               "noun"),
    "αιων":   ("αἰών, αἰῶνος, ὁ",
               "age, eternity; εἰς τὸν αἰῶνα = forever",
               "3rd declension masculine",
               "noun"),
    "δουλος": ("δοῦλος, δούλου, ὁ",
               "slave, servant",
               "2nd declension masculine",
               "noun"),
    "αδελφος": ("ἀδελφός, ἀδελφοῦ, ὁ",
                "brother",
                "2nd declension masculine; fem. ἀδελφή",
                "noun"),
    "αδελφη": ("ἀδελφή, ἀδελφῆς, ἡ",
               "sister",
               "1st declension feminine",
               "noun"),
    "εκκλησια": ("ἐκκλησία, ἐκκλησίας, ἡ",
                 "assembly, church, congregation",
                 "1st declension feminine; from ἐκκαλέω (call out)",
                 "noun"),
    "γη":     ("γῆ, γῆς, ἡ",
               "earth, land, soil",
               "1st declension feminine",
               "noun"),
    "φωνη":   ("φωνή, φωνῆς, ἡ",
               "voice, sound",
               "1st declension feminine",
               "noun"),
    "ονομα":  ("ὄνομα, ὀνόματος, τό",
               "name",
               "3rd declension neuter",
               "noun"),
    "πνευμα": ("πνεῦμα, πνεύματος, τό",
               "spirit, wind, breath",
               "3rd declension neuter; τὸ ἅγιον πνεῦμα = the Holy Spirit",
               "noun"),
    "αιμα":   ("αἷμα, αἵματος, τό",
               "blood",
               "3rd declension neuter",
               "noun"),
    "σωμα":   ("σῶμα, σώματος, τό",
               "body",
               "3rd declension neuter",
               "noun"),
    "πιστις": ("πίστις, πίστεως, ἡ",
               "faith, belief, trust",
               "3rd declension feminine (i-stem); gen. πίστεως",
               "noun"),
    "αγαπη":  ("ἀγάπη, ἀγάπης, ἡ",
               "love (unconditional, self-giving)",
               "1st declension feminine; used extensively in NT",
               "noun"),
    "χαρα":   ("χαρά, χαρᾶς, ἡ",
               "joy, gladness",
               "1st declension feminine",
               "noun"),
    "χαρις":  ("χάρις, χάριτος, ἡ",
               "grace, favour, thankfulness",
               "3rd declension feminine",
               "noun"),
    "ειρηνη": ("εἰρήνη, εἰρήνης, ἡ",
               "peace",
               "1st declension feminine",
               "noun"),
    "αληθεια": ("ἀλήθεια, ἀληθείας, ἡ",
                "truth",
                "1st declension feminine",
                "noun"),
    "νομος":  ("νόμος, νόμου, ὁ",
               "law, Torah",
               "2nd declension masculine",
               "noun"),
    "βασιλεια": ("βασιλεία, βασιλείας, ἡ",
                 "kingdom, reign",
                 "1st declension feminine; ἡ βασιλεία τοῦ θεοῦ = the kingdom of God",
                 "noun"),
    "αμαρτια": ("ἁμαρτία, ἁμαρτίας, ἡ",
                "sin, error (missing the mark)",
                "1st declension feminine",
                "noun"),
    "εργον":  ("ἔργον, ἔργου, τό",
               "work, deed, action",
               "2nd declension neuter",
               "noun"),
    "δικαιοσυνη": ("δικαιοσύνη, δικαιοσύνης, ἡ",
                   "righteousness, justice",
                   "1st declension feminine",
                   "noun"),

    # ── Pronouns ─────────────────────────────────────────────────────────────
    "εγω":    ("ἐγώ",
               "I",
               "1st person singular pronoun; gen. ἐμοῦ / μου",
               "pronoun"),
    "συ":     ("σύ",
               "you (singular)",
               "2nd person singular pronoun; gen. σοῦ / σου",
               "pronoun"),
    "αυτος":  ("αὐτός, αὐτή, αὐτό",
               "he/she/it (3rd person); same, himself (intensive)",
               "pronoun / intensive adjective; also used as 3rd person pronoun",
               "pronoun"),
    "ουτος":  ("οὗτος, αὕτη, τοῦτο",
               "this (near demonstrative)",
               "demonstrative pronoun/adjective",
               "pronoun"),
    "εκεινος": ("ἐκεῖνος, ἐκείνη, ἐκεῖνο",
                "that (far demonstrative)",
                "demonstrative pronoun/adjective",
                "pronoun"),
    "ος":     ("ὅς, ἥ, ὅ",
               "who, which, that (relative pronoun)",
               "relative pronoun, declines like article but with rough breathing",
               "pronoun"),
    "τις":    ("τίς, τί",
               "who? what? (interrogative)",
               "3rd declension; accent marks interrogative vs. τις = someone (enclitic)",
               "pronoun"),

    # ── Article ──────────────────────────────────────────────────────────────
    "ο":      ("ὁ, ἡ, τό",
               "the (definite article)",
               "declines in 3 genders, 2 numbers, 5 cases; no vocative",
               "article"),

    # ── Prepositions ─────────────────────────────────────────────────────────
    "εν":     ("ἐν (+ dat.)",
               "in, on, among, by means of",
               "preposition governing dative",
               "preposition"),
    "εις":    ("εἰς (+ acc.)",
               "into, to, toward, for (purpose)",
               "preposition governing accusative",
               "preposition"),
    "εκ":     ("ἐκ / ἐξ (+ gen.)",
               "out of, from",
               "ἐκ before consonants, ἐξ before vowels; governs genitive",
               "preposition"),
    "απο":    ("ἀπό (+ gen.)",
               "from, away from",
               "preposition governing genitive",
               "preposition"),
    "προς":   ("πρός (+ acc.)",
               "to, toward, with (in company of)",
               "most common with accusative; also dative (at) and genitive (rare)",
               "preposition"),
    "κατα":   ("κατά (+ gen. / + acc.)",
               "against, down from (+ gen.); according to, throughout (+ acc.)",
               "elides before vowels: κατ᾿, καθ᾿",
               "preposition"),
    "περι":   ("περί (+ gen. / + acc.)",
               "about, concerning (+ gen.); around, about (+ acc.)",
               "preposition",
               "preposition"),
    "μετα":   ("μετά (+ gen. / + acc.)",
               "with, among (+ gen.); after (+ acc.)",
               "preposition",
               "preposition"),
    "δια":    ("διά (+ gen. / + acc.)",
               "through, by means of (+ gen.); because of, for the sake of (+ acc.)",
               "preposition",
               "preposition"),
    "επι":    ("ἐπί (+ gen. / dat. / acc.)",
               "on, at, over, against",
               "takes all three oblique cases with different meanings",
               "preposition"),
    "παρα":   ("παρά (+ gen. / dat. / acc.)",
               "from (+ gen.); beside, with (+ dat.); alongside (+ acc.)",
               "preposition",
               "preposition"),
    "υπο":    ("ὑπό (+ gen. / + acc.)",
               "by (agent, + gen.); under (+ acc.)",
               "preposition governing genitive for agent, accusative for position",
               "preposition"),
    "συν":    ("σύν (+ dat.)",
               "with, together with",
               "preposition governing dative",
               "preposition"),
    "υπερ":   ("ὑπέρ (+ gen. / + acc.)",
               "on behalf of, for (+ gen.); above (+ acc.)",
               "preposition",
               "preposition"),

    # ── Conjunctions / particles ───────────────────────────────────────────────
    "και":    ("καί",
               "and, also, even, too",
               "most common word in NT; also καί … καί = both … and",
               "conjunction"),
    "δε":     ("δέ",
               "but, and, now (mild contrast or continuation)",
               "postpositive particle; never first in clause",
               "conjunction"),
    "γαρ":    ("γάρ",
               "for, because, indeed (explanatory)",
               "postpositive particle; never first in clause",
               "conjunction"),
    "αλλα":   ("ἀλλά",
               "but (strong adversative)",
               "coordinating conjunction",
               "conjunction"),
    "οτι":    ("ὅτι",
               "that (indirect statement); because",
               "subordinating conjunction",
               "conjunction"),
    "ει":     ("εἰ",
               "if (conditional)",
               "conditional conjunction; εἰ + indicative = simple condition",
               "conjunction"),
    "ιδου":   ("ἰδού",
               "behold! look! see!",
               "interjection / particle (2nd aorist middle imperative of ὁράω)",
               "particle"),
    "ναι":    ("ναί",
               "yes, indeed, certainly",
               "affirmative particle",
               "particle"),
    "ου":     ("οὐ / οὐκ / οὐχ",
               "not (negation)",
               "οὐ before consonants, οὐκ before smooth vowels, οὐχ before rough breathing",
               "particle"),
    "μη":     ("μή",
               "not (with non-indicative moods, in questions expecting no)",
               "negation particle; contrasts with οὐ",
               "particle"),
    "αμην":   ("ἀμήν",
               "truly, verily, amen",
               "Hebrew loanword; ἀμὴν λέγω ὑμῖν = truly I say to you",
               "particle"),

    # ── Adjectives ───────────────────────────────────────────────────────────
    "αγαθος": ("ἀγαθός, ἀγαθή, ἀγαθόν",
               "good (morally good, useful, beneficial)",
               "1st/2nd declension adjective",
               "adjective"),
    "καλος":  ("καλός, καλή, καλόν",
               "good, beautiful, fine",
               "1st/2nd declension adjective; more aesthetic than ἀγαθός",
               "adjective"),
    "πιστος": ("πιστός, πιστή, πιστόν",
               "faithful, trustworthy, believing",
               "1st/2nd declension adjective",
               "adjective"),
    "αγιος":  ("ἅγιος, ἁγία, ἅγιον",
               "holy, set apart, sacred",
               "1st/2nd declension adjective; τὸ ἅγιον πνεῦμα = the Holy Spirit",
               "adjective"),
    "μεγας":  ("μέγας, μεγάλη, μέγα",
               "great, large, important",
               "irregular adjective; gen. μεγάλου",
               "adjective"),
    "πας":    ("πᾶς, πᾶσα, πᾶν",
               "all, every, whole",
               "3rd/1st declension adjective (mixed); very frequent in NT",
               "adjective"),
    "αιωνιος": ("αἰώνιος, αἰώνιον",
                "eternal, everlasting",
                "2-termination adjective (masc./fem. same form); ζωὴ αἰώνιος = eternal life",
                "adjective"),
    "αλλος":  ("ἄλλος, ἄλλη, ἄλλο",
               "other, another (of the same kind)",
               "1st/2nd declension adjective; compare ἕτερος (different kind)",
               "adjective"),
    "πολυς":  ("πολύς, πολλή, πολύ",
               "many, much, great",
               "irregular adjective; gen. πολλοῦ, πολλῆς",
               "adjective"),

    # ── Numbers ───────────────────────────────────────────────────────────────
    "εις_num": ("εἷς, μία, ἕν",
                "one",
                "irregular numeral adjective (nom. only listed); gen. ἑνός, μιᾶς, ἑνός",
                "numeral"),
    "δυο":    ("δύο",
               "two",
               "indeclinable (some forms: gen./dat. δυοῖν in older texts)",
               "numeral"),
    "τρεις":  ("τρεῖς, τρία",
               "three",
               "3rd declension numeral adjective",
               "numeral"),
}

# Confidence note for unrecognised tokens.
_UNKNOWN_NOTE = (
    "Koine Greek dictionary scaffold \u2014 citation (lexical) forms only. "
    "Inflected forms (e.g. \u03bb\u03cc\u03b3\u03bf\u03bd, \u03b8\u03b5\u03bf\u1fe6, "
    "\u03b5\u1fd0\u03c0\u03bf\u03bd) are not recognised. "
    "Use a full Greek morphological analyser (CLTK, Morpheus, "
    "GlobaLeaks / Koine-tools) for complete parsing."
)


class KoineGreekPlugin:
    """Koine Greek dictionary-mode plugin.

    Provides sentence splitting and whitespace tokenisation against an embedded
    New Testament Greek lexicon.  This is a foundation scaffold for the
    dead-language dictionary pathway — not a replacement for a full Greek parser.

    See module docstring for honest-claims details and upgrade path.
    """

    language_code = "grc"
    display_name  = "Koine Greek (NT Greek \u2014 dictionary scaffold)"
    direction     = "ltr"
    capabilities  = LanguageCapabilities(
        code="grc",
        display_name="Koine Greek (NT Greek \u2014 dictionary scaffold)",
        direction="ltr",
        script_family="greek",
        tokenization_mode="whitespace",
        morphology_depth="none",
        lesson_modes_supported=["dictionary"],
        analysis_depth="dictionary",
        segmentation_quality="medium",
        tokenization_quality="medium",
        morphology_quality="none",
        syntax_support=False,
        idiom_detection=False,
        tts_lang_tag="el",           # Modern Greek TTS is the closest available
        transliteration_scheme="sbl-simplified",
    )

    def __init__(self) -> None:
        self.lesson_store: dict[str, CandidateObject] = {}

    # ── LanguagePlugin protocol ───────────────────────────────────────────────

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
            token = _STRIP_PUNCT.sub("", raw_token)
            if not token:
                continue
            canonical = _normalise(token)
            if not canonical or canonical in seen_canonical:
                continue
            seen_canonical.add(canonical)

            romanized = transliterate(token)

            entry = _LEXICON.get(canonical)
            if entry is not None:
                citation, gloss, grammar, pos = entry
                lesson_data: dict = {
                    "citation_form": citation,
                    "gloss": gloss,
                    "grammar_note": grammar,
                    "pos": pos.upper(),
                    "cefr_level": "A1",
                    "romanized": romanized,
                }
                confidence = 0.85
            else:
                lesson_data = {
                    "confidence_note": _UNKNOWN_NOTE,
                    "romanized": romanized,
                }
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


def create_plugin() -> KoineGreekPlugin:
    return KoineGreekPlugin()
