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
  - Postposition detection:
    • Single-word postpositions (ने, को, से, में, पर, के, की, का, …)
      identified from a closed-class list.
    • Common multi-word postpositions (के लिए, के बाद, के पहले, के साथ, …)
      detected by scanning sentence bigrams and trigrams.
  - Verb form detection with conjugation type:
    Words where suffix rules match a tense/mood/aspect feature are emitted
    as "conjugation" objects with morphological fields, not bare vocabulary.
    Detected forms: future (m/f sg/pl), habitual/imperfective (m/f),
    past perfective (m/f), infinitive, subjunctive, imperative, participle.
  - Noun/adjective gender/number hints: oblique, plural, vocative.
  - Function word (copula, auxiliaries, pronouns, particles) identification.
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
  • Lemmatisation is NOT performed; canonical_form uses the surface form.
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
# Single-word postpositions that follow nouns and mark grammatical relations.
_POSTPOSITIONS: frozenset[str] = frozenset({
    "ने", "को", "से", "में", "पर", "के", "की", "का",
    "तक", "द्वारा", "बिना", "जैसे", "सामने",
})

# Multi-word postpositions (bigrams and trigrams).
# Each is a tuple of tokens to match as a consecutive sequence.
_MULTI_WORD_POSTPOSITIONS: list[tuple[str, ...]] = [
    ("के", "लिए"),
    ("के", "बाद"),
    ("के", "पहले"),
    ("के", "साथ"),
    ("के", "ऊपर"),
    ("के", "नीचे"),
    ("के", "अंदर"),
    ("के", "बाहर"),
    ("के", "बिना"),
    ("के", "बारे", "में"),
    ("की", "तरफ"),
    ("की", "ओर"),
]

# Function words — copula/auxiliaries worth tagging.
_FUNCTION_WORDS: frozenset[str] = frozenset({
    # Copula / auxiliaries
    "है", "हैं", "हूँ", "था", "थे", "थी", "थीं",
    "होगा", "होगी", "होंगे", "होंगी", "हो", "हों",
    "हुआ", "हुई", "हुए", "होना", "हो",
    # Personal pronouns
    "यह", "वह", "वे", "ये", "मैं", "तुम", "आप", "हम", "वो",
    # Determiners / particles
    "एक", "कि", "और", "या", "भी", "नहीं", "मत", "न",
    "ही", "तो", "भी", "बस", "सिर्फ", "केवल",
    # Relative / interrogative pronouns
    "जो", "सो", "कि", "इस", "उस", "इन", "उन",
    # Adverbs / discourse particles
    "फिर", "अब", "यहाँ", "वहाँ", "तब", "जब",
    "बहुत", "थोड़ा", "काफी", "बिल्कुल", "शायद",
    # Interrogatives
    "क्या", "कौन", "कहाँ", "कब", "कैसे", "कितना", "किसने",
    # Negation
    "नहीं", "मत", "न",
})

# ── Morphology hints (verb suffixes) ─────────────────────────────────────────
# Ordered longest-match first to avoid partial matches.
# Returns (feature_dict, is_verb_form) where is_verb_form signals conjugation.
_VERB_SUFFIXES: list[tuple[str, dict, int]] = [
    # (suffix, features, min_total_token_len)
    # Longer/more specific suffixes first for longest-match priority.
    # Future (4-way gender × number)
    ("एंगी", {"tense": "future", "gender": "feminine",  "number": "plural"},   4),
    ("एंगे", {"tense": "future", "gender": "masculine", "number": "plural"},   4),
    ("एगी",  {"tense": "future", "gender": "feminine",  "number": "singular"}, 4),
    ("एगा",  {"tense": "future", "gender": "masculine", "number": "singular"}, 4),
    # Habitual + auxiliary (longer forms first)
    ("ती हैं", {"tense": "present_habitual", "gender": "feminine",  "number": "plural"},   4),
    ("ते हैं", {"tense": "present_habitual", "gender": "masculine", "number": "plural"},   4),
    ("ती है", {"tense": "present_habitual", "gender": "feminine",  "number": "singular"}, 4),
    ("ता है", {"tense": "present_habitual", "gender": "masculine", "number": "singular"}, 4),
    # Past perfective auxiliary forms
    ("आए",   {"tense": "past", "gender": "masculine", "number": "plural",   "aspect": "perfective"}, 4),
    ("आई",   {"tense": "past", "gender": "feminine",  "aspect": "perfective"},                       4),
    ("आया",  {"tense": "past", "gender": "masculine", "number": "singular", "aspect": "perfective"}, 4),
    # Habitual / imperfective (bare) — require ≥ 4 chars total to avoid matching nouns
    ("ते",   {"aspect": "habitual", "gender": "masculine", "number": "plural"}, 4),
    ("ती",   {"aspect": "habitual", "gender": "feminine"},                      4),
    ("ता",   {"aspect": "habitual", "gender": "masculine"},                     4),
    # Infinitive
    ("ना",   {"verb_form": "infinitive"}, 4),
    # Imperative
    ("इए",   {"mood": "imperative", "register": "formal"}, 4),
    ("ओ",    {"mood": "imperative", "person": "second"},    4),
    # Subjunctive / polite imperative
    ("ए",    {"mood": "subjunctive_or_imperative"}, 4),
    # Perfective participle (single-char matras — high false-positive risk).
    # Require ≥ 5 chars total so common nouns/adjectives (e.g. "लड़का", "अच्छा")
    # do not match. Confidence set lower; see _extract_verb_morph.
    ("ी",    {"verb_form": "perfective_participle", "gender": "feminine"},  5),
    ("ा",    {"verb_form": "perfective_participle", "gender": "masculine"}, 5),
]

# ── Noun/adjective suffix hints ───────────────────────────────────────────────
_NOUN_SUFFIXES: list[tuple[str, dict, int]] = [
    # (suffix, features, min_total_token_len)
    ("एं",  {"number": "plural", "gender": "feminine"},     4),
    ("ें",  {"number": "plural"},                           4),
    ("ों",  {"number": "plural", "case": "oblique"},        4),
    # Single-char oblique matra — require ≥ 5 chars to reduce false positives
    ("े",   {"case": "oblique", "gender": "masculine"},     5),
]

# ── Simplified IAST-style romanisation ───────────────────────────────────────
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
    # Matras (vowel signs)
    "ा": "ā",  "ि": "i",  "ी": "ī",  "ु": "u",  "ू": "ū",
    "े": "e",  "ै": "ai", "ो": "o",  "ौ": "au",
    "ं": "ṃ",  "ः": "ḥ",  "ँ": "m̐",  "ऽ": "'",
    "्": "",
    "ऩ": "n",  "ऱ": "r",  "ऴ": "ẓ",  "ॽ": "'",
    # Nukta variants (Urdu-origin sounds)
    "क़": "q",  "ख़": "x",  "ग़": "ġ",  "ज़": "z",  "ड़": "ṛ",  "ढ़": "ṛh",
    "फ़": "f",  "य़": "ẏ",
}


def _romanise(word: str) -> str:
    """Approximate IAST romanisation of a single Devanagari token."""
    parts: list[str] = []
    for ch in word:
        if unicodedata.category(ch) == "Mn":
            r = _IAST.get(ch, "")
            if ch == "्":
                if parts and parts[-1].endswith("a"):
                    parts[-1] = parts[-1][:-1]
                continue
            if r:
                if parts and parts[-1].endswith("a"):
                    parts[-1] = parts[-1][:-1] + r
                else:
                    parts.append(r)
        else:
            r = _IAST.get(ch)
            if r is not None:
                if unicodedata.category(ch).startswith("L"):
                    parts.append(r + "a")
                else:
                    parts.append(r)
            else:
                parts.append(ch)
    return "".join(parts)


def _extract_verb_morph(token: str) -> dict | None:
    """Return verb morphology if a verb suffix matches, else None.

    Single-character matra suffixes (ā/ī) require a minimum token length
    to avoid false positives on common nouns and adjectives.
    """
    for suffix, features, min_len in _VERB_SUFFIXES:
        if token.endswith(suffix) and len(token) >= min_len:
            return dict(features)
    return None


def _extract_noun_morph(token: str) -> dict:
    """Return noun/adjective morphology hints; empty dict if no match."""
    for suffix, features, min_len in _NOUN_SUFFIXES:
        if token.endswith(suffix) and len(token) >= min_len:
            return dict(features)
    return {}


def _find_multi_word_postpositions(tokens: list[str]) -> set[int]:
    """Return indices consumed by multi-word postpositions."""
    consumed: set[int] = set()
    for mwp in _MULTI_WORD_POSTPOSITIONS:
        length = len(mwp)
        for i in range(len(tokens) - length + 1):
            if tuple(tokens[i:i + length]) == mwp:
                for j in range(i, i + length):
                    consumed.add(j)
    return consumed


_CONFIDENCE_NOTE = (
    "Hindi morphology-light: suffix-pattern heuristics only. "
    "Morphological features (tense, gender, case) are probable, not certain. "
    "No compound-verb decomposition, sandhi resolution, or loanword analysis. "
    "Lemmatisation not performed; canonical_form is the surface form."
)


class HindiPlugin:
    """Hindi morphology-light plugin.

    Provides Devanagari tokenisation, suffix-based morphology hints with
    conjugation-type emission for detected verb forms, multi-word postposition
    detection, and approximate IAST romanisation. Capabilities honestly declared.
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
        tense_pool=["present_habitual", "past", "future"],
        mood_pool=["imperative", "subjunctive_or_imperative"],
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
                "derived from suffix patterns only. Detected verb forms emitted as "
                "conjugation objects. Multi-word postpositions detected via bigram/"
                "trigram scan. No trained model."
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

        # Multi-word postposition scan — mark indices consumed by MWPs
        mwp_consumed = _find_multi_word_postpositions(deva_tokens)

        for idx, token in enumerate(deva_tokens):
            if token in seen:
                continue

            romanised = _romanise(token)

            # Multi-word postposition participant
            if idx in mwp_consumed:
                # Emit the full sequence only on the first token of each MWP
                # (subsequent tokens within the same MWP are skipped as "seen")
                # Find which MWP starts here
                mwp_surface: str | None = None
                for mwp in _MULTI_WORD_POSTPOSITIONS:
                    if len(mwp) <= len(deva_tokens) - idx:
                        if tuple(deva_tokens[idx:idx + len(mwp)]) == mwp:
                            mwp_surface = " ".join(mwp)
                            canonical = mwp_surface
                            break
                if mwp_surface and canonical not in seen:
                    seen.add(canonical)
                    # Mark component tokens so they aren't re-emitted
                    for mwp in _MULTI_WORD_POSTPOSITIONS:
                        if len(mwp) <= len(deva_tokens) - idx:
                            if tuple(deva_tokens[idx:idx + len(mwp)]) == mwp:
                                for j in range(1, len(mwp)):
                                    seen.add(deva_tokens[idx + j])
                                break
                    candidates.append(CandidateObject(
                        canonical_form=canonical,
                        surface_form=mwp_surface,
                        type="grammar",
                        label=mwp_surface,
                        lesson_data={
                            "surface_form": mwp_surface,
                            "romanized":    _romanise("".join(mwp)),
                            "pos":          "postposition",
                            "note":         "Multi-word grammatical postposition.",
                            "confidence_note": _CONFIDENCE_NOTE,
                        },
                        confidence=0.80,
                    ))
                elif token not in seen:
                    seen.add(token)
                continue

            seen.add(token)

            is_postposition = token in _POSTPOSITIONS
            is_function     = token in _FUNCTION_WORDS

            if is_postposition:
                candidates.append(CandidateObject(
                    canonical_form=token,
                    surface_form=token,
                    type="grammar",
                    label=token,
                    lesson_data={
                        "surface_form":    token,
                        "romanized":       romanised,
                        "pos":             "postposition",
                        "note":            "Grammatical postposition (case marker).",
                        "confidence_note": _CONFIDENCE_NOTE,
                    },
                    confidence=0.85,
                ))
            elif is_function:
                candidates.append(CandidateObject(
                    canonical_form=token,
                    surface_form=token,
                    type="vocabulary",
                    label=token,
                    lesson_data={
                        "lemma":        token,
                        "surface_form": token,
                        "romanized":    romanised,
                        "pos":          "function_word",
                    },
                    confidence=0.80,
                ))
            else:
                verb_morph = _extract_verb_morph(token)
                if verb_morph:
                    # Emit as conjugation — verb form with morphological analysis
                    morph_tag = ":".join(f"{k}={v}" for k, v in sorted(verb_morph.items()))
                    canonical = f"{token}:{morph_tag}"
                    lesson_data: dict = {
                        "surface_form":    token,
                        "romanized":       romanised,
                        "pos":             "verb",
                        "confidence_note": _CONFIDENCE_NOTE,
                    }
                    lesson_data.update(verb_morph)
                    candidates.append(CandidateObject(
                        canonical_form=canonical,
                        surface_form=token,
                        type="conjugation",
                        label=token,
                        lesson_data=lesson_data,
                        confidence=0.45,
                    ))
                else:
                    noun_morph = _extract_noun_morph(token)
                    lesson_data = {
                        "lemma":           token,
                        "surface_form":    token,
                        "romanized":       romanised,
                        "confidence_note": _CONFIDENCE_NOTE,
                    }
                    if noun_morph:
                        lesson_data.update(noun_morph)
                    candidates.append(CandidateObject(
                        canonical_form=token,
                        surface_form=token,
                        type="vocabulary",
                        label=token,
                        lesson_data=lesson_data,
                        confidence=0.45 if noun_morph else None,
                    ))

        # Latin tokens (loanwords/numerals) as low-confidence vocabulary
        for token in latin_tokens:
            canonical_latin = token.lower()
            if canonical_latin in seen or not token.isalpha():
                continue
            seen.add(canonical_latin)
            candidates.append(
                CandidateObject(
                    canonical_form=canonical_latin,
                    surface_form=token,
                    type="vocabulary",
                    label=token,
                    lesson_data={
                        "lemma":        canonical_latin,
                        "surface_form": token,
                        "note":         "Latin-script loanword or technical term.",
                    },
                    confidence=None,
                )
            )

        return CandidateSentenceResult(text=sentence, candidates=candidates)

    def get_lesson(self, object_id: str) -> CandidateObject | None:
        return self.lesson_store.get(object_id)


def create_plugin() -> HindiPlugin:
    return HindiPlugin()
