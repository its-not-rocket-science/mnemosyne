"""Turkish plugin — morphology-light with agglutinative suffix analysis.

BCP-47 code "tr", LTR, Latin script with Turkish special characters.

What this plugin does reliably
──────────────────────────────
  - Sentence splitting on standard terminal punctuation and newlines.
  - Whitespace tokenisation (Turkish is whitespace-delimited).
  - Turkish dotted-I normalisation (İ→i, I→ı for case folding).
  - Vowel harmony classification: back (a/ı/o/u) vs. front (e/i/ö/ü).
    Most Turkish suffixes alternate based on the last vowel in the stem.
  - Suffix chain hints for morphological features (longest-match first):
    • Infinitive: -mak/-mek
    • Negation + progressive: -mıyor/-miyor/-muyor/-müyor
    • Progressive present: -ıyor/-iyor/-uyor/-üyor
    • Definite past: -dı/-di/-du/-dü/-tı/-ti/-tu/-tü (+ person markings)
    • Evidential/reported past: -mış/-miş/-muş/-müş
    • Future: -ecek/-acak (+ person markings)
    • Conditional: -sak/-sek
    • Plural noun + case: -lardan/-lerden, -larda/-lerde, etc.
    • Singular case: ablative, locative, genitive, comitative/instrumental
    • Aorist 3sg: -ar/-er
  - Words with verb morphology emitted as "conjugation" type with
    tense/mood/person/number fields.
  - Common Turkish function words and particles identified.

Known limitations
─────────────────
  • Turkish agglutinative morphology stacks multiple suffixes on one stem.
    This plugin strips only the outermost suffix; inner suffixes (possessive,
    aspect, evidentiality stacking) are not decomposed.
  • Vowel harmony disambiguation on ambiguous stems may be incorrect.
  • Consonant mutation (t→d, k→ğ after vowel) partially handled.
  • No nominal/verbal compound resolution.
  • No trained NLP model available for Turkish in this deployment.
  • Lemmatisation is NOT performed; canonical_form for conjugations uses
    surface form + morphology tag.
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
    return "back"


def _normalise_turkish(token: str) -> str:
    """Lowercase with Turkish dotted-I correction.

    Turkish has two i-like letters: dotted İ/i and dotless I/ı.
    Python's str.lower() maps I→i, but in Turkish I should map to ı.
    This function applies the Turkish-correct lowercasing for these characters.
    """
    return token.replace("İ", "i").replace("I", "ı").lower()


# ── Function words / closed-class items ──────────────────────────────────────
_FUNCTION_WORDS: frozenset[str] = frozenset({
    "bir", "bu", "şu", "o", "ben", "sen", "biz", "siz", "onlar",
    "ve", "ya", "ama", "fakat", "çünkü", "ki", "ile", "ya da",
    "hem", "ne", "değil", "var", "yok", "gibi", "kadar", "için",
    "mi", "mı", "mu", "mü",
    "de", "da", "dahi", "bile",
    "en", "çok", "az", "daha", "hep", "her", "hiç",
})

# ── Morphological suffix rules (longest match first) ─────────────────────────
# Each entry: (suffix_lower, feature_dict)
# Verb features → emitted as "conjugation"; noun/adj features → "vocabulary".
_SUFFIX_RULES: list[tuple[str, dict]] = [
    # Infinitive
    ("mak",    {"verb_form": "infinitive", "pos": "verb"}),
    ("mek",    {"verb_form": "infinitive", "pos": "verb"}),
    # Evidential/reported past -mış/-miş/-muş/-müş (+ person markings)
    ("mışım",  {"tense": "past_evidential", "person": "first",  "number": "singular", "pos": "verb"}),
    ("mişim",  {"tense": "past_evidential", "person": "first",  "number": "singular", "pos": "verb"}),
    ("muşum",  {"tense": "past_evidential", "person": "first",  "number": "singular", "pos": "verb"}),
    ("müşüm",  {"tense": "past_evidential", "person": "first",  "number": "singular", "pos": "verb"}),
    ("mışsın", {"tense": "past_evidential", "person": "second", "number": "singular", "pos": "verb"}),
    ("mişsin", {"tense": "past_evidential", "person": "second", "number": "singular", "pos": "verb"}),
    ("mış",    {"tense": "past_evidential", "pos": "verb"}),
    ("miş",    {"tense": "past_evidential", "pos": "verb"}),
    ("muş",    {"tense": "past_evidential", "pos": "verb"}),
    ("müş",    {"tense": "past_evidential", "pos": "verb"}),
    # Negation + progressive
    ("mıyor",  {"tense": "progressive", "polarity": "negative", "pos": "verb"}),
    ("miyor",  {"tense": "progressive", "polarity": "negative", "pos": "verb"}),
    ("muyor",  {"tense": "progressive", "polarity": "negative", "pos": "verb"}),
    ("müyor",  {"tense": "progressive", "polarity": "negative", "pos": "verb"}),
    # Progressive present -iyor (four-way vowel harmony)
    ("ıyor",   {"tense": "progressive", "polarity": "affirmative", "pos": "verb"}),
    ("iyor",   {"tense": "progressive", "polarity": "affirmative", "pos": "verb"}),
    ("uyor",   {"tense": "progressive", "polarity": "affirmative", "pos": "verb"}),
    ("üyor",   {"tense": "progressive", "polarity": "affirmative", "pos": "verb"}),
    # Definite past -dı/-di/-du/-dü/-tı/-ti/-tu/-tü (+ person)
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
    # Future -ecek/-acak (+ person endings)
    ("eceksin", {"tense": "future", "person": "second", "number": "singular", "pos": "verb"}),
    ("acaksın", {"tense": "future", "person": "second", "number": "singular", "pos": "verb"}),
    ("eceğim",  {"tense": "future", "person": "first",  "number": "singular", "pos": "verb"}),
    ("acağım",  {"tense": "future", "person": "first",  "number": "singular", "pos": "verb"}),
    ("ecek",    {"tense": "future", "pos": "verb"}),
    ("acak",    {"tense": "future", "pos": "verb"}),
    # Conditional -sa/-se (person-marked only to avoid false positives)
    ("sak",    {"mood": "conditional", "person": "first", "number": "plural", "pos": "verb"}),
    ("sek",    {"mood": "conditional", "person": "first", "number": "plural", "pos": "verb"}),
    # Plural noun + case (must precede bare case suffixes to avoid shadowing)
    ("lardan",  {"number": "plural", "case": "ablative",    "pos": "noun"}),
    ("lerden",  {"number": "plural", "case": "ablative",    "pos": "noun"}),
    ("larda",   {"number": "plural", "case": "locative",    "pos": "noun"}),
    ("lerde",   {"number": "plural", "case": "locative",    "pos": "noun"}),
    ("larla",   {"number": "plural", "case": "comitative",  "pos": "noun"}),
    ("lerle",   {"number": "plural", "case": "comitative",  "pos": "noun"}),
    ("ların",   {"number": "plural", "case": "genitive",    "pos": "noun"}),
    ("lerin",   {"number": "plural", "case": "genitive",    "pos": "noun"}),
    ("ları",    {"number": "plural", "case": "accusative",  "pos": "noun"}),
    ("leri",    {"number": "plural", "case": "accusative",  "pos": "noun"}),
    ("lara",    {"number": "plural", "case": "dative",      "pos": "noun"}),
    ("lere",    {"number": "plural", "case": "dative",      "pos": "noun"}),
    ("lar",     {"number": "plural", "pos": "noun"}),
    ("ler",     {"number": "plural", "pos": "noun"}),
    # Singular cases
    ("dan",    {"case": "ablative",              "pos": "noun_or_adjective"}),
    ("den",    {"case": "ablative",              "pos": "noun_or_adjective"}),
    ("tan",    {"case": "ablative",              "pos": "noun_or_adjective"}),
    ("ten",    {"case": "ablative",              "pos": "noun_or_adjective"}),
    ("da",     {"case": "locative",              "pos": "noun_or_adjective"}),
    ("de",     {"case": "locative",              "pos": "noun_or_adjective"}),
    ("ta",     {"case": "locative",              "pos": "noun_or_adjective"}),
    ("te",     {"case": "locative",              "pos": "noun_or_adjective"}),
    ("ın",     {"case": "genitive",              "pos": "noun"}),
    ("in",     {"case": "genitive",              "pos": "noun"}),
    ("un",     {"case": "genitive",              "pos": "noun"}),
    ("ün",     {"case": "genitive",              "pos": "noun"}),
    ("la",     {"case": "comitative_instrumental", "pos": "noun"}),
    ("le",     {"case": "comitative_instrumental", "pos": "noun"}),
    # Possessive suffixes (1sg/2sg/3sg) — outermost only
    ("ım",     {"possessive": "first_sg",  "pos": "noun"}),
    ("im",     {"possessive": "first_sg",  "pos": "noun"}),
    ("um",     {"possessive": "first_sg",  "pos": "noun"}),
    ("üm",     {"possessive": "first_sg",  "pos": "noun"}),
    ("ın",     {"possessive": "second_sg", "pos": "noun"}),
    ("nın",    {"possessive": "second_sg", "pos": "noun"}),
    ("sı",     {"possessive": "third_sg",  "pos": "noun"}),
    ("si",     {"possessive": "third_sg",  "pos": "noun"}),
    ("su",     {"possessive": "third_sg",  "pos": "noun"}),
    ("sü",     {"possessive": "third_sg",  "pos": "noun"}),
    # Aorist 3sg -ar/-er (short; must follow all longer suffixes above).
    # Min stem length enforced in _extract_morph to reduce false positives.
    ("ar",     {"tense": "aorist", "person": "third", "number": "singular", "pos": "verb"}),
    ("er",     {"tense": "aorist", "person": "third", "number": "singular", "pos": "verb"}),
]

# Words that end in -ar/-er but are NOT aorist verb forms.
# Matching would be a false positive; these are excluded in _extract_morph.
_AORIST_BLOCKLIST: frozenset[str] = frozenset({
    "bir", "her", "ver", "yer", "ger", "mer", "ser", "ber",
    "nar", "bar", "car", "dar", "far", "gar", "har", "jar",
    "kar", "lar", "mar", "par", "sar", "tar", "var", "zar",
    "dolar", "şeker", "pazar", "haber", "yazar", "kamer",
    "noter", "fiber", "laser", "liner", "poker",
})

_CONFIDENCE_NOTE = (
    "Turkish morphology-light: outermost suffix stripped for feature hints. "
    "Inner suffix layers (possessive, aspect stacking, evidentiality) not analysed. "
    "No trained NLP model used. Canonical form uses surface form + morphology tag."
)

_VERB_POS = frozenset({"verb"})


def _extract_morph(token: str) -> dict:
    """Return morphology hints by longest-suffix match.

    Aorist -ar/-er requires a minimum stem length of 3 chars and is
    blocked for known non-verb forms in _AORIST_BLOCKLIST.
    """
    lower = _normalise_turkish(token)
    for suffix, features in _SUFFIX_RULES:
        if not lower.endswith(suffix):
            continue
        stem_len = len(lower) - len(suffix)
        # Standard minimum stem (must have at least 2 chars before suffix)
        if stem_len < 2:
            continue
        # Aorist -ar/-er: require longer stem and blocklist check
        if suffix in ("ar", "er"):
            if stem_len < 3 or lower in _AORIST_BLOCKLIST:
                continue
        return dict(features)
    return {}


class TurkishPlugin:
    """Turkish morphology-light plugin.

    Provides whitespace tokenisation, Turkish-correct I/İ normalisation,
    agglutinative suffix hinting, and conjugation-type emission for detected
    verb forms. Capabilities honestly declared.
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
        tense_pool=["aorist", "progressive", "past_definite", "past_evidential", "future"],
        mood_pool=["conditional"],
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
                "Morphology-light: outermost suffix only for case, tense, plural. "
                "Evidential past (-mış) added. Detected verb forms emitted as "
                "conjugation objects. Vowel harmony detected. "
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
            canonical = _normalise_turkish(token)
            if canonical in seen:
                continue
            seen.add(canonical)

            is_function = canonical in _FUNCTION_WORDS
            morph = _extract_morph(token)
            harmony = _last_vowel_harmony(token)
            is_verb = morph.get("pos") in _VERB_POS

            if is_function:
                candidates.append(CandidateObject(
                    canonical_form=canonical,
                    surface_form=token,
                    type="vocabulary",
                    label=token,
                    lesson_data={
                        "lemma":         canonical,
                        "surface_form":  token,
                        "vowel_harmony": harmony,
                        "pos":           "function_word",
                    },
                    confidence=0.80,
                ))
            elif is_verb and morph:
                # Emit as conjugation with morphological fields
                morph_tag = ":".join(f"{k}={v}" for k, v in sorted(morph.items()))
                conj_canonical = f"{canonical}:{morph_tag}"
                lesson_data: dict = {
                    "surface_form":    token,
                    "vowel_harmony":   harmony,
                    "confidence_note": _CONFIDENCE_NOTE,
                }
                lesson_data.update(morph)
                candidates.append(CandidateObject(
                    canonical_form=conj_canonical,
                    surface_form=token,
                    type="conjugation",
                    label=token,
                    lesson_data=lesson_data,
                    confidence=0.45,
                ))
            else:
                lesson_data = {
                    "lemma":         canonical,
                    "surface_form":  token,
                    "vowel_harmony": harmony,
                }
                if morph:
                    lesson_data.update(morph)
                    lesson_data["confidence_note"] = _CONFIDENCE_NOTE
                else:
                    lesson_data["confidence_note"] = _CONFIDENCE_NOTE
                candidates.append(CandidateObject(
                    canonical_form=canonical,
                    surface_form=token,
                    type="vocabulary",
                    label=token,
                    lesson_data=lesson_data,
                    confidence=0.45 if morph else None,
                ))

        return CandidateSentenceResult(text=sentence, candidates=candidates)

    def get_lesson(self, object_id: str) -> CandidateObject | None:
        return self.lesson_store.get(object_id)


def create_plugin() -> TurkishPlugin:
    return TurkishPlugin()
