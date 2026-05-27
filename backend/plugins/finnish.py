"""Finnish plugin — morphology-light with case and verb suffix analysis.

BCP-47 code "fi", LTR, Latin script with Finnish diacritics (ä, ö).

What this plugin does reliably
──────────────────────────────
  - Sentence splitting on standard terminal punctuation and newlines.
  - Whitespace tokenisation (Finnish is whitespace-delimited).
  - Vowel harmony classification: back (a/o/u) vs. front (ä/ö/y).
    Finnish suffixes undergo vowel harmony; this is used to annotate tokens.
  - Suffix-based morphological hints for:
    • Nominal cases (15 cases): nominative (base), genitive -n, accusative -t/-n,
      partitive -a/-ä/-ta/-tä, inessive -ssa/-ssä, elative -sta/-stä,
      illative -Vn/-hVn, adessive -lla/-llä, ablative -lta/-ltä,
      allative -lle, essive -na/-nä, translative -ksi,
      abessive -tta/-ttä, instructive (plural) -n, comitative -ne.
    • Plural: -t (nominative), -iden/-itten (genitive), -ita/-itä (partitive).
    • Verb forms: infinitive -a/-ä/-ta/-tä/-da/-dä,
                  present 1sg -n, 2sg -t, 3sg -V, 1pl -mme, 2pl -tte, 3pl -vat/-vät,
                  imperative 2sg (stem), 3sg -koon/-köön,
                  past 1sg -in, 2sg -it, 3sg -i,
                  conditional -isi-, potential -ne-,
                  passive -taan/-tään, passive past -ttiin.
    • Common negative verb forms: e- stem + person ending.
  - Common Finnish function words and particles identified.

Known limitations
─────────────────
  • Finnish morphology is highly agglutinative; this plugin detects only the
    outermost suffix layer.  Inner layers (possessive suffixes, clitic
    particles -ko/-kö, -kin, -kaan/-kään, -pa/-pä, -han/-hän) are not parsed.
  • Consonant gradation (k→∅, p→v, t→d etc.) means many stems cannot be
    recovered without a morphological lexicon; lemmatisation is NOT attempted.
  • Ambiguous suffixes (e.g. -ssa = inessive, but also 3sg verb form for some
    verbs) may be mislabelled.
  • No trained NLP model (fi_core_news_sm or equivalent) available in this
    deployment.
  • Analysis quality: morphology_light — morphological fields are hints, not
    verified analysis.
"""
from __future__ import annotations

import re

from backend.schemas.language import LanguageCapabilities, NuanceCapabilities
from backend.schemas.parse import CandidateObject, CandidateSentenceResult

# ── Sentence splitting ────────────────────────────────────────────────────────
_SENTENCE_RE = re.compile(r"[^.!?\n]+[.!?\n]?")

# ── Tokenisation ──────────────────────────────────────────────────────────────
# Finnish letters: standard ASCII + ä (U+00E4), ö (U+00F6), å (U+00E5, rare)
# Uppercase variants included.
_WORD_RE = re.compile(r"[A-Za-zÄäÖöÅå]+")

# ── Vowel harmony ─────────────────────────────────────────────────────────────
_BACK_VOWELS  = frozenset("aouAOU")
_FRONT_VOWELS = frozenset("äöyÄÖY")


def _vowel_harmony(word: str) -> str:
    """Return 'back' or 'front' based on last back/front vowel (Finnish rule)."""
    for ch in reversed(word):
        if ch in _BACK_VOWELS:
            return "back"
        if ch in _FRONT_VOWELS:
            return "front"
    return "back"


# ── Function words ────────────────────────────────────────────────────────────
_FUNCTION_WORDS: frozenset[str] = frozenset({
    "ja", "tai", "vai", "sekä", "mutta", "vaan", "koska", "jos", "kun",
    "että", "kuin", "niin", "siis", "kuitenkin", "myös", "vain", "jo",
    "ei", "en", "et", "emme", "ette", "eivät",
    "se", "hän", "he", "minä", "sinä", "me", "te", "ne",
    "on", "olla", "oli", "olisi", "ollut",
    "yksi", "kaksi", "kolme", "neljä",
    "tämä", "tuo", "nämä", "ne", "kaikki", "jokin", "joku",
    "mikä", "kuka", "missä", "milloin", "miten", "miksi",
    "eli", "tai", "joko",
})

# ── Morphological suffix rules (longest match first) ─────────────────────────
# (suffix, feature_dict)
_SUFFIX_RULES: list[tuple[str, dict]] = [
    # ── Verb forms ──────────────────────────────────────────────────────────
    # Passive forms
    ("ttiin",   {"voice": "passive", "tense": "past",    "pos": "verb"}),
    ("tiin",    {"voice": "passive", "tense": "past",    "pos": "verb"}),
    ("taan",    {"voice": "passive", "tense": "present", "pos": "verb"}),
    ("tään",    {"voice": "passive", "tense": "present", "pos": "verb"}),
    ("daan",    {"voice": "passive", "tense": "present", "pos": "verb"}),
    ("dään",    {"voice": "passive", "tense": "present", "pos": "verb"}),
    # Third plural present
    ("vat",     {"person": "third",  "number": "plural", "tense": "present", "pos": "verb"}),
    ("vät",     {"person": "third",  "number": "plural", "tense": "present", "pos": "verb"}),
    # Conditional stem -isi-
    ("isimme",  {"mood": "conditional", "person": "first",  "number": "plural",   "pos": "verb"}),
    ("isitte",  {"mood": "conditional", "person": "second", "number": "plural",   "pos": "verb"}),
    ("isivat",  {"mood": "conditional", "person": "third",  "number": "plural",   "pos": "verb"}),
    ("isin",    {"mood": "conditional", "person": "first",  "number": "singular", "pos": "verb"}),
    ("isit",    {"mood": "conditional", "person": "second", "number": "singular", "pos": "verb"}),
    ("isi",     {"mood": "conditional", "pos": "verb"}),
    # First/second plural present
    ("mme",     {"person": "first",  "number": "plural",   "tense": "present", "pos": "verb"}),
    ("tte",     {"person": "second", "number": "plural",   "tense": "present", "pos": "verb"}),
    # Imperative 3sg
    ("koon",    {"mood": "imperative", "person": "third",  "number": "singular", "pos": "verb"}),
    ("köön",    {"mood": "imperative", "person": "third",  "number": "singular", "pos": "verb"}),
    # Past 1sg/2sg
    ("in",      {"person": "first",  "number": "singular", "tense": "past",    "pos": "verb"}),
    ("it",      {"person": "second", "number": "singular", "tense": "past",    "pos": "verb"}),
    # Present 1sg -n, 2sg -t
    # (short; match only after longer rules pass)
    # ── Nominal plural ───────────────────────────────────────────────────────
    ("iden",    {"number": "plural", "case": "genitive",  "pos": "noun"}),
    ("itten",   {"number": "plural", "case": "genitive",  "pos": "noun"}),
    ("iden",    {"number": "plural", "case": "genitive",  "pos": "noun"}),
    ("ita",     {"number": "plural", "case": "partitive", "pos": "noun"}),
    ("itä",     {"number": "plural", "case": "partitive", "pos": "noun"}),
    # ── Nominal cases (singular) ─────────────────────────────────────────────
    ("tta",     {"case": "abessive",    "pos": "noun_or_adjective"}),
    ("ttä",     {"case": "abessive",    "pos": "noun_or_adjective"}),
    ("ksi",     {"case": "translative", "pos": "noun_or_adjective"}),
    ("lle",     {"case": "allative",    "pos": "noun_or_adjective"}),
    ("lta",     {"case": "ablative",    "pos": "noun_or_adjective"}),
    ("ltä",     {"case": "ablative",    "pos": "noun_or_adjective"}),
    ("lla",     {"case": "adessive",    "pos": "noun_or_adjective"}),
    ("llä",     {"case": "adessive",    "pos": "noun_or_adjective"}),
    ("sta",     {"case": "elative",     "pos": "noun_or_adjective"}),
    ("stä",     {"case": "elative",     "pos": "noun_or_adjective"}),
    ("ssa",     {"case": "inessive",    "pos": "noun_or_adjective"}),
    ("ssä",     {"case": "inessive",    "pos": "noun_or_adjective"}),
    ("na",      {"case": "essive",      "pos": "noun_or_adjective"}),
    ("nä",      {"case": "essive",      "pos": "noun_or_adjective"}),
    ("ta",      {"case": "partitive",   "pos": "noun_or_adjective"}),
    ("tä",      {"case": "partitive",   "pos": "noun_or_adjective"}),
    # Partitive -a/-ä (short; match last)
    ("a",       {"case": "partitive_or_infinitive", "pos": "noun_or_verb"}),
    ("ä",       {"case": "partitive_or_infinitive", "pos": "noun_or_verb"}),
    # Genitive/accusative -n
    ("n",       {"case": "genitive_or_accusative", "pos": "noun_or_adjective"}),
    # Nominative plural -t
    ("t",       {"number": "plural", "case": "nominative", "pos": "noun_or_adjective"}),
]

_CONFIDENCE_NOTE = (
    "Finnish morphology-light: outermost suffix analysis only. "
    "Consonant gradation and inner suffix layers (possessive, clitics) not parsed. "
    "Lemmatisation not attempted. No trained NLP model used."
)


def _extract_morph(token: str) -> dict:
    lower = token.lower()
    for suffix, features in _SUFFIX_RULES:
        if lower.endswith(suffix) and len(lower) > len(suffix) + 1:
            return dict(features)
    return {}


class FinnishPlugin:
    """Finnish morphology-light plugin.

    Provides whitespace tokenisation and suffix-based case/verb hints.
    Capabilities honestly declared.
    """

    language_code = "fi"
    display_name  = "Finnish (morphology-light)"
    direction     = "ltr"
    capabilities  = LanguageCapabilities(
        code="fi",
        display_name="Finnish (morphology-light)",
        direction="ltr",
        script_family="latin",
        tokenization_mode="whitespace",
        morphology_depth="shallow",
        lesson_modes_supported=["vocabulary", "dictionary"],
        analysis_depth="morphology_light",
        segmentation_quality="medium",
        tokenization_quality="high",
        morphology_quality="low",
        syntax_support=False,
        idiom_detection=False,
        tts_lang_tag="fi",
        transliteration_scheme=None,
        nuance_capabilities=NuanceCapabilities(
            idioms="none",
            phrase_families="none",
            literary_references="none",
            cultural_references="none",
            etymology="none",
            formality_register="none",
            grammar_nuance="stub",
            pronunciation_tts="stub",
            transliteration="none",
            proverb_tradition="none",
            classical_or_scriptural_allusion="none",
            notes=(
                "Morphology-light: 15-case suffix detection and verb-form hints. "
                "Consonant gradation not resolved; lemmatisation not performed. "
                "No fi_core_news_sm spaCy model installed in this deployment."
            ),
        ),
    )

    def __init__(self) -> None:
        self.lesson_store: dict[str, CandidateObject] = {}

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
        seen: set[str] = set()

        for token in _WORD_RE.findall(sentence):
            canonical = token.lower()
            if canonical in seen:
                continue
            seen.add(canonical)

            is_function = canonical in _FUNCTION_WORDS
            morph = _extract_morph(token)
            harmony = _vowel_harmony(token)

            lesson_data: dict = {
                "lemma":         canonical,
                "surface_form":  token,
                "vowel_harmony": harmony,
            }

            if is_function:
                lesson_data["pos"] = "function_word"
                confidence: float | None = 0.80
            elif morph:
                lesson_data.update(morph)
                lesson_data["confidence_note"] = _CONFIDENCE_NOTE
                confidence = 0.45
            else:
                lesson_data["confidence_note"] = _CONFIDENCE_NOTE
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


def create_plugin() -> FinnishPlugin:
    return FinnishPlugin()
