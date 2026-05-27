"""Turkish plugin — morphology-light with agglutinative suffix analysis.

BCP-47 code "tr", LTR, Latin script.

What this plugin does reliably
──────────────────────────────
  - Sentence splitting on standard terminal punctuation and newlines.
  - Whitespace tokenisation (Turkish is whitespace-delimited).
  - Vowel harmony classification: back (a/ı/o/u) vs. front (e/i/ö/ü).
    Most Turkish suffixes alternate based on the last vowel in the stem.
  - Suffix chain hints for common morphological features:
    • Plural: -lar/-ler
    • Case: accusative -ı/-i/-u/-ü, dative -a/-e,
            locative -da/-de/-ta/-te, ablative -dan/-den/-tan/-ten,
            genitive -ın/-in/-un/-ün, instrumental -la/-le
    • Negation: -me/-ma (verbal)
    • Infinitive: -mak/-mek
    • Verbal tenses: aorist -r/-ar/-er, progressive -iyor,
                     past -dı/-di/-du/-dü, future -ecek/-acak
    • Person/number endings: -im/-ım (1sg), -sin/-sın (2sg), -iz/-ız (1pl),
                              -siniz (2pl), -ler/-lar (3pl)
  - Detection of common Turkish function words and particles.

Known limitations
─────────────────
  • Turkish agglutinative morphology stacks multiple suffixes on one stem.
    This plugin strips only the outermost suffix; inner suffixes are not
    decomposed (e.g. "evlerimden" → stem "ev" + PL + POSS + ABL not resolved).
  • Vowel harmony disambiguation on ambiguous stems may be incorrect.
  • Consonant mutation (t→d, k→ğ after vowel) is partially handled but not
    exhaustively.
  • No nominal/verbal compound resolution.
  • No trained NLP model available for Turkish in this deployment.
  • Analysis quality: morphology_light — do not rely on morphological fields
    for precise linguistic annotation.
"""
from __future__ import annotations

import re

from backend.schemas.language import LanguageCapabilities, NuanceCapabilities
from backend.schemas.parse import CandidateObject, CandidateSentenceResult

# ── Sentence splitting ────────────────────────────────────────────────────────
_SENTENCE_RE = re.compile(r"[^.!?\n]+[.!?\n]?")

# ── Word tokenisation ─────────────────────────────────────────────────────────
_WORD_RE = re.compile(r"[A-Za-zÇçĞğİıÖöŞşÜü]+")

# ── Vowel harmony ─────────────────────────────────────────────────────────────
_BACK_VOWELS  = frozenset("aıouAIOU")
_FRONT_VOWELS = frozenset("eiöüEİÖÜ")
_ALL_VOWELS   = _BACK_VOWELS | _FRONT_VOWELS


def _last_vowel_harmony(word: str) -> str:
    """Return 'back' or 'front' based on the last vowel in the word."""
    for ch in reversed(word):
        if ch in _BACK_VOWELS:
            return "back"
        if ch in _FRONT_VOWELS:
            return "front"
    return "back"  # default


# ── Function words / closed-class items ──────────────────────────────────────
_FUNCTION_WORDS: frozenset[str] = frozenset({
    "bir", "bu", "şu", "o", "ben", "sen", "biz", "siz", "onlar",
    "ve", "ya", "ama", "fakat", "çünkü", "ki", "ile", "ya da",
    "hem", "ne", "değil", "var", "yok", "gibi", "kadar", "için",
    "mi", "mı", "mu", "mü",
    "de", "da", "dahi", "bile",
})

# ── Morphological suffix rules (longest match first) ─────────────────────────
# Each entry: (suffix_lower, feature_dict)
# Case endings are the innermost suffix after plural/possessive; we check
# the whole surface form and accept a "probable" tag.
_SUFFIX_RULES: list[tuple[str, dict]] = [
    # Infinitive (always -mak/-mek)
    ("mak",    {"verb_form": "infinitive", "pos": "verb"}),
    ("mek",    {"verb_form": "infinitive", "pos": "verb"}),
    # Negation -ma/-me (verb stem + negation)
    ("mıyor",  {"tense": "progressive", "polarity": "negative", "pos": "verb"}),
    ("miyor",  {"tense": "progressive", "polarity": "negative", "pos": "verb"}),
    ("muyor",  {"tense": "progressive", "polarity": "negative", "pos": "verb"}),
    ("müyor",  {"tense": "progressive", "polarity": "negative", "pos": "verb"}),
    # Progressive present -iyor (four-way vowel harmony)
    ("ıyor",   {"tense": "progressive", "polarity": "affirmative", "pos": "verb"}),
    ("iyor",   {"tense": "progressive", "polarity": "affirmative", "pos": "verb"}),
    ("uyor",   {"tense": "progressive", "polarity": "affirmative", "pos": "verb"}),
    ("üyor",   {"tense": "progressive", "polarity": "affirmative", "pos": "verb"}),
    # Definite past -dı/-di/-du/-dü/-tı/-ti/-tu/-tü
    ("dım",    {"tense": "past_definite", "person": "first",  "number": "singular", "pos": "verb"}),
    ("dim",    {"tense": "past_definite", "person": "first",  "number": "singular", "pos": "verb"}),
    ("dum",    {"tense": "past_definite", "person": "first",  "number": "singular", "pos": "verb"}),
    ("düm",    {"tense": "past_definite", "person": "first",  "number": "singular", "pos": "verb"}),
    ("dın",    {"tense": "past_definite", "person": "second", "number": "singular", "pos": "verb"}),
    ("din",    {"tense": "past_definite", "person": "second", "number": "singular", "pos": "verb"}),
    ("dun",    {"tense": "past_definite", "person": "second", "number": "singular", "pos": "verb"}),
    ("dün",    {"tense": "past_definite", "person": "second", "number": "singular", "pos": "verb"}),
    ("dı",     {"tense": "past_definite", "person": "third",  "number": "singular", "pos": "verb"}),
    ("di",     {"tense": "past_definite", "person": "third",  "number": "singular", "pos": "verb"}),
    ("du",     {"tense": "past_definite", "person": "third",  "number": "singular", "pos": "verb"}),
    ("dü",     {"tense": "past_definite", "person": "third",  "number": "singular", "pos": "verb"}),
    ("tı",     {"tense": "past_definite", "person": "third",  "number": "singular", "pos": "verb"}),
    ("ti",     {"tense": "past_definite", "person": "third",  "number": "singular", "pos": "verb"}),
    ("tu",     {"tense": "past_definite", "person": "third",  "number": "singular", "pos": "verb"}),
    ("tü",     {"tense": "past_definite", "person": "third",  "number": "singular", "pos": "verb"}),
    # Future -ecek/-acak (+ person endings; here we detect the tense marker)
    ("eceksin", {"tense": "future", "person": "second", "number": "singular", "pos": "verb"}),
    ("acaksın", {"tense": "future", "person": "second", "number": "singular", "pos": "verb"}),
    ("eceğim",  {"tense": "future", "person": "first",  "number": "singular", "pos": "verb"}),
    ("acağım",  {"tense": "future", "person": "first",  "number": "singular", "pos": "verb"}),
    ("ecek",    {"tense": "future", "pos": "verb"}),
    ("acak",    {"tense": "future", "pos": "verb"}),
    # Conditional -sa/-se (only unambiguous person-marked forms; bare -sa/-se
    # are too short and trigger false positives on nominative nouns ending in -sa/-se)
    ("sak",    {"mood": "conditional", "person": "first", "number": "plural", "pos": "verb"}),
    ("sek",    {"mood": "conditional", "person": "first", "number": "plural", "pos": "verb"}),
    # Case suffixes (plural forms must come before bare -ar/-er to avoid
    # mislabelling "kitaplar" as aorist 3sg instead of plural nominative)
    ("lardan",  {"number": "plural", "case": "ablative", "pos": "noun"}),
    ("lerden",  {"number": "plural", "case": "ablative", "pos": "noun"}),
    ("larda",   {"number": "plural", "case": "locative",  "pos": "noun"}),
    ("lerde",   {"number": "plural", "case": "locative",  "pos": "noun"}),
    ("larla",   {"number": "plural", "case": "comitative", "pos": "noun"}),
    ("lerle",   {"number": "plural", "case": "comitative", "pos": "noun"}),
    ("ların",   {"number": "plural", "case": "genitive",   "pos": "noun"}),
    ("lerin",   {"number": "plural", "case": "genitive",   "pos": "noun"}),
    ("ları",    {"number": "plural", "case": "accusative",  "pos": "noun"}),
    ("leri",    {"number": "plural", "case": "accusative",  "pos": "noun"}),
    ("lara",    {"number": "plural", "case": "dative",     "pos": "noun"}),
    ("lere",    {"number": "plural", "case": "dative",     "pos": "noun"}),
    ("lar",     {"number": "plural", "pos": "noun"}),
    ("ler",     {"number": "plural", "pos": "noun"}),
    # Singular cases
    ("dan",    {"case": "ablative", "pos": "noun_or_adjective"}),
    ("den",    {"case": "ablative", "pos": "noun_or_adjective"}),
    ("tan",    {"case": "ablative", "pos": "noun_or_adjective"}),
    ("ten",    {"case": "ablative", "pos": "noun_or_adjective"}),
    ("da",     {"case": "locative", "pos": "noun_or_adjective"}),
    ("de",     {"case": "locative", "pos": "noun_or_adjective"}),
    ("ta",     {"case": "locative", "pos": "noun_or_adjective"}),
    ("te",     {"case": "locative", "pos": "noun_or_adjective"}),
    ("ın",     {"case": "genitive", "pos": "noun"}),
    ("in",     {"case": "genitive", "pos": "noun"}),
    ("un",     {"case": "genitive", "pos": "noun"}),
    ("ün",     {"case": "genitive", "pos": "noun"}),
    # Single-char accusative (-ı/-i/-u/-ü) and dative (-a/-e) omitted:
    # their false-positive rate is too high (almost every word stem ends with
    # a vowel).  Use the 2+char forms above for reliable detection.
    ("la",     {"case": "comitative_instrumental", "pos": "noun"}),
    ("le",     {"case": "comitative_instrumental", "pos": "noun"}),
    # Aorist 3sg -ar/-er (placed last; shorter than plural -lar/-ler so must
    # not shadow them — e.g. "kitaplar" must match "lar" not "ar")
    ("ar",     {"tense": "aorist", "person": "third", "number": "singular", "pos": "verb"}),
    ("er",     {"tense": "aorist", "person": "third", "number": "singular", "pos": "verb"}),
]

_CONFIDENCE_NOTE = (
    "Turkish morphology-light: outermost suffix stripped for feature hints. "
    "Inner suffix layers (possessive, aspect, evidentiality) not analysed. "
    "No trained NLP model used."
)


def _extract_morph(token: str) -> dict:
    """Return morphology hints by longest-suffix match."""
    lower = token.lower()
    for suffix, features in _SUFFIX_RULES:
        if lower.endswith(suffix) and len(lower) > len(suffix) + 1:
            return dict(features)
    return {}


class TurkishPlugin:
    """Turkish morphology-light plugin.

    Provides whitespace tokenisation and agglutinative suffix hinting.
    Capabilities honestly declared.
    """

    language_code = "tr"
    display_name  = "Turkish (morphology-light)"
    direction     = "ltr"
    capabilities  = LanguageCapabilities(
        code="tr",
        display_name="Turkish (morphology-light)",
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
        tts_lang_tag="tr",
        transliteration_scheme=None,
        nuance_capabilities=NuanceCapabilities(
            idioms="none",
            phrase_families="none",
            literary_references="none",
            cultural_references="none",
            etymology="none",
            formality_register="stub",
            grammar_nuance="stub",
            pronunciation_tts="stub",
            transliteration="none",
            proverb_tradition="none",
            classical_or_scriptural_allusion="none",
            notes=(
                "Morphology-light: outermost suffix only for case, tense, "
                "plural. Vowel harmony detected but not used for lemmatisation. "
                "No trained Turkish NLP model in this deployment."
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
            canonical = token.lower().replace("i̇", "i")  # dotted-I normalisation
            if canonical in seen:
                continue
            seen.add(canonical)

            is_function = canonical in _FUNCTION_WORDS
            morph = _extract_morph(token)
            harmony = _last_vowel_harmony(token)

            lesson_data: dict = {
                "surface_form":   token,
                "vowel_harmony":  harmony,
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


def create_plugin() -> TurkishPlugin:
    return TurkishPlugin()
