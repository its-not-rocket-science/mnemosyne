"""Hindi plugin — morphology-light with Devanagari-aware tokenisation.

BCP-47 code "hi", LTR, Devanagari script.

What this plugin does reliably
──────────────────────────────
  - Sentence splitting on Devanagari danda (।), double danda (॥), and
    standard Western terminal punctuation + newlines.
  - Devanagari-aware tokenisation: each token captures a consonant/vowel
    cluster with attached matras, chandrabindu, and anusvara so that
    combining marks are never separated from their base character.
  - ASCII-only Latin loanwords are preserved as separate tokens.
  - Basic morphology hints extracted by suffix pattern matching:
    • Verb aspect/tense: infinitive -ना, past m/f -ा/-ी, habitual m/f -ता/-ती,
      future m/f -एगा/-एगी, subjunctive -ए/-ें, imperative -ो/-ओ/-इए.
    • Noun/adjective gender/number: oblique -े/-ों, plural -एं/-ें, vocative -ो.
    • Postposition detection: ने/को/से/में/पर/के/की/का/एक/कि/यह/वह/है/हैं/था/थे.
  - Romanisation using a simplified IAST-style scheme (informational; not
    phonetically precise for all dialects).

Known limitations
─────────────────
  • Suffix matching has false positives: Hindi has considerable homography
    and suffix ambiguity that requires full morphological analysis.
  • No compound-verb (conjunct verb) decomposition.
  • No sandhi resolution.
  • Loanwords (English, Urdu, Sanskrit tatsama) may get incorrect morphology.
  • Romanisation is approximate; IPA would require trained models.
  • No CEFR level data available for Hindi in this release.
  • Analysis quality: morphology_light — do not rely on morphological fields
    for precise linguistic annotation.
"""
from __future__ import annotations

import re
import unicodedata

from backend.schemas.language import LanguageCapabilities, NuanceCapabilities
from backend.schemas.parse import CandidateObject, CandidateSentenceResult

# ── Sentence splitting ────────────────────────────────────────────────────────
# ।  U+0964 Devanagari danda  (primary sentence boundary)
# ॥  U+0965 Devanagari double danda
# Standard Western punctuation handled for mixed prose.
_SENTENCE_RE = re.compile(
    r"[^।॥!?\n.]+[।॥!?\n.]?"
)

# ── Devanagari tokenisation ───────────────────────────────────────────────────
# Core Devanagari block: U+0900–U+097F
# Vedic extensions (rarely present in modern prose): U+1CD0–U+1CFF
# Combining marks included: vowel signs (matras), anusvara, visarga, nukta,
# chandrabindu, virama — so that "क + ा" is captured as one unit.
_DEVA_WORD_RE = re.compile(
    # Exclude U+0964 (।, danda) and U+0965 (॥, double danda) which fall
    # inside the Devanagari block but are sentence punctuation, not letters.
    r"[ऀ-ॣ०-ॿ᳐-᳿]+"
)
# Latin loanwords / numerals / transliterations in otherwise Hindi text.
_LATIN_WORD_RE = re.compile(r"[A-Za-z0-9]+")

# ── Postpositions (case markers / function words) ─────────────────────────────
# These attach to noun phrases and mark grammatical relations; surface always
# as separate orthographic words in modern standard Hindi.
_POSTPOSITIONS: frozenset[str] = frozenset({
    "ने", "को", "से", "में", "पर", "के", "की", "का",
    "के लिए", "तक", "के बाद", "के पहले", "के साथ",
    "के बारे में", "के ऊपर", "के नीचे",
})

# Function words — copula/auxiliaries worth tagging.
_FUNCTION_WORDS: frozenset[str] = frozenset({
    "है", "हैं", "हूँ", "था", "थे", "थी", "थीं",
    "होगा", "होगी", "होंगे", "होंगी", "हो", "हों",
    "यह", "वह", "वे", "ये", "मैं", "तुम", "आप", "हम",
    "एक", "कि", "और", "या", "भी", "नहीं", "मत",
})

# ── Morphology hints (verb suffixes) ─────────────────────────────────────────
# Ordered longest-match first to avoid partial matches.
_VERB_SUFFIXES: list[tuple[str, dict]] = [
    # Future
    ("एगा",  {"tense": "future", "gender": "masculine", "number": "singular"}),
    ("एगी",  {"tense": "future", "gender": "feminine",  "number": "singular"}),
    ("एंगे", {"tense": "future", "gender": "masculine", "number": "plural"}),
    ("एंगी", {"tense": "future", "gender": "feminine",  "number": "plural"}),
    # Habitual / imperfective
    ("ता है", {"tense": "present_habitual", "gender": "masculine", "number": "singular"}),
    ("ती है", {"tense": "present_habitual", "gender": "feminine",  "number": "singular"}),
    ("ते हैं", {"tense": "present_habitual", "gender": "masculine", "number": "plural"}),
    ("ती हैं", {"tense": "present_habitual", "gender": "feminine",  "number": "plural"}),
    ("ता",   {"aspect": "habitual", "gender": "masculine"}),
    ("ती",   {"aspect": "habitual", "gender": "feminine"}),
    ("ते",   {"aspect": "habitual", "gender": "masculine", "number": "plural"}),
    # Past perfective
    ("आया",  {"tense": "past", "gender": "masculine"}),
    ("आई",   {"tense": "past", "gender": "feminine"}),
    ("आए",   {"tense": "past", "gender": "masculine", "number": "plural"}),
    # Infinitive
    ("ना",   {"verb_form": "infinitive"}),
    # Subjunctive / imperative
    ("ए",    {"mood": "subjunctive_or_imperative"}),
    ("ओ",    {"mood": "imperative", "person": "second"}),
    ("इए",   {"mood": "imperative", "register": "formal"}),
    ("ो",    {"mood": "imperative_or_oblique"}),
    # Perfective participle
    ("ा",    {"verb_form": "perfective_participle", "gender": "masculine"}),
    ("ी",    {"verb_form": "perfective_participle", "gender": "feminine"}),
]

# ── Noun/adjective suffix hints ───────────────────────────────────────────────
_NOUN_SUFFIXES: list[tuple[str, dict]] = [
    ("एं",  {"number": "plural", "gender": "feminine"}),
    ("ें",  {"number": "plural"}),
    ("ों",  {"number": "plural", "case": "oblique"}),
    ("े",   {"case": "oblique", "gender": "masculine"}),
]

# ── Simplified IAST-style romanisation ───────────────────────────────────────
# Maps each relevant Devanagari code point to its approximate romanisation.
# This is informational only — not a full phonemic transcription.
_IAST: dict[str, str] = {
    "अ": "a",  "आ": "ā",  "इ": "i",  "ई": "ī",  "उ": "u",  "ऊ": "ū",
    "ए": "e",  "ऐ": "ai", "ओ": "o",  "औ": "au", "ऋ": "ṛ",  "ॠ": "ṝ",
    "क": "k",  "ख": "kh", "ग": "g",  "घ": "gh", "ङ": "ṅ",
    "च": "c",  "छ": "ch", "ज": "j",  "झ": "jh", "ञ": "ñ",
    "ट": "ṭ",  "ठ": "ṭh", "ड": "ḍ",  "ढ": "ḍh", "ण": "ṇ",
    "त": "t",  "थ": "th", "द": "d",  "ध": "dh", "न": "n",
    "प": "p",  "फ": "ph", "ब": "b",  "भ": "bh", "म": "m",
    "य": "y",  "र": "r",  "ल": "l",  "व": "v",
    "श": "ś",  "ष": "ṣ",  "स": "s",  "ह": "h",
    "ळ": "ḷ",
    # Matras (vowel signs — attached to consonants)
    "ा": "ā",  "ि": "i",  "ी": "ī",  "ु": "u",  "ू": "ū",
    "े": "e",  "ै": "ai", "ो": "o",  "ौ": "au",
    "ं": "ṃ",  "ः": "ḥ",  "ँ": "m̐",  "ऽ": "'",
    "्": "",   # virama — suppresses inherent a
    "ऩ": "n",  "ऱ": "r",  "ऴ": "ẓ",  "ॽ": "'",
    # Nukta variants (for Urdu-origin sounds)
    "क़": "q",  "ख़": "x",  "ग़": "ġ",  "ज़": "z",  "ड़": "ṛ",  "ढ़": "ṛh",
    "फ़": "f",  "य़": "ẏ",  "ऱ": "r",
}


def _romanise(word: str) -> str:
    """Approximate IAST romanisation of a single Devanagari token."""
    parts: list[str] = []
    prev_consonant = False
    for ch in word:
        if unicodedata.category(ch) == "Mn":
            # Combining mark — matra or virama
            r = _IAST.get(ch, "")
            if r == "" and ch == "्":
                # virama removes the inherent 'a' from previous consonant
                if parts and parts[-1] == "a":
                    parts.pop()
                prev_consonant = False
                continue
            if r:
                # Replace implicit 'a' written for previous consonant
                if parts and parts[-1] == "a":
                    parts[-1] = r
                else:
                    parts.append(r)
            prev_consonant = False
        else:
            r = _IAST.get(ch)
            if r is not None:
                if unicodedata.category(ch).startswith("L"):
                    # Consonant — add with implicit 'a'
                    parts.append(r + "a")
                    prev_consonant = True
                else:
                    parts.append(r)
                    prev_consonant = False
            else:
                parts.append(ch)
                prev_consonant = False
    # Remove trailing implicit 'a' on final consonant (common in citation forms)
    if parts and parts[-1].endswith("a") and len(parts[-1]) > 1:
        # only remove if it seems to be a trailing inherent vowel
        pass  # conservative: leave it
    return "".join(parts)


def _extract_morph(token: str) -> dict:
    """Apply suffix pattern rules; return morphology dict (may be empty)."""
    morph: dict = {}
    for suffix, features in _VERB_SUFFIXES:
        if token.endswith(suffix) and len(token) > len(suffix):
            morph.update(features)
            morph["pos"] = "verb"
            break
    if not morph:
        for suffix, features in _NOUN_SUFFIXES:
            if token.endswith(suffix) and len(token) > len(suffix):
                morph.update(features)
                morph["pos"] = "noun_or_adjective"
                break
    return morph


_CONFIDENCE_NOTE = (
    "Hindi morphology-light: suffix-pattern heuristics only. "
    "Morphological features (tense, gender, case) are probable, not certain. "
    "No compound-verb decomposition, sandhi resolution, or loanword analysis."
)


class HindiPlugin:
    """Hindi morphology-light plugin.

    Provides Devanagari tokenisation, suffix-based morphology hints,
    and approximate IAST romanisation. Capabilities honestly declared.
    """

    language_code = "hi"
    display_name  = "Hindi (morphology-light)"
    direction     = "ltr"
    capabilities  = LanguageCapabilities(
        code="hi",
        display_name="Hindi (morphology-light)",
        direction="ltr",
        script_family="devanagari",
        tokenization_mode="whitespace",
        morphology_depth="shallow",
        lesson_modes_supported=["vocabulary", "dictionary"],
        analysis_depth="morphology_light",
        segmentation_quality="medium",
        tokenization_quality="medium",
        morphology_quality="low",
        syntax_support=False,
        idiom_detection=False,
        tts_lang_tag="hi",
        transliteration_scheme="iast_approximate",
        nuance_capabilities=NuanceCapabilities(
            idioms="none",
            phrase_families="none",
            literary_references="none",
            cultural_references="none",
            etymology="none",
            formality_register="stub",
            grammar_nuance="stub",
            pronunciation_tts="stub",
            transliteration="partial",
            proverb_tradition="none",
            classical_or_scriptural_allusion="none",
            notes=(
                "Morphology-light: verb tense/aspect/gender and noun case hints "
                "derived from suffix patterns only. No trained model. Postpositions "
                "and function words identified by closed-class list."
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

        deva_tokens = _DEVA_WORD_RE.findall(sentence)
        latin_tokens = _LATIN_WORD_RE.findall(sentence) if re.search(r"[A-Za-z]", sentence) else []

        for token in deva_tokens:
            if token in seen:
                continue
            seen.add(token)

            romanised = _romanise(token)
            morph = _extract_morph(token)

            is_postposition = token in _POSTPOSITIONS
            is_function     = token in _FUNCTION_WORDS

            if is_postposition:
                obj_type = "grammar"
                lesson_data: dict = {
                    "surface_form": token,
                    "romanized":    romanised,
                    "pos":          "postposition",
                    "note":         "Grammatical postposition (case marker).",
                }
                confidence: float | None = 0.85
            elif is_function:
                obj_type = "vocabulary"
                lesson_data = {
                    "surface_form": token,
                    "romanized":    romanised,
                    "pos":          "function_word",
                }
                confidence = 0.80
            else:
                obj_type = "vocabulary"
                lesson_data = {
                    "surface_form": token,
                    "romanized":    romanised,
                    "confidence_note": _CONFIDENCE_NOTE,
                }
                if morph:
                    lesson_data.update(morph)
                confidence = 0.45 if morph else None

            candidates.append(
                CandidateObject(
                    canonical_form=token,
                    surface_form=token,
                    type=obj_type,
                    label=token,
                    lesson_data=lesson_data,
                    confidence=confidence,
                )
            )

        # Latin tokens (loanwords/numerals) as low-confidence vocabulary
        for token in latin_tokens:
            if token in seen or not token.isalpha():
                continue
            seen.add(token)
            candidates.append(
                CandidateObject(
                    canonical_form=token.lower(),
                    surface_form=token,
                    type="vocabulary",
                    label=token,
                    lesson_data={
                        "surface_form": token,
                        "note": "Latin-script loanword or technical term.",
                    },
                    confidence=None,
                )
            )

        return CandidateSentenceResult(text=sentence, candidates=candidates)

    def get_lesson(self, object_id: str) -> CandidateObject | None:
        return self.lesson_store.get(object_id)


def create_plugin() -> HindiPlugin:
    return HindiPlugin()
