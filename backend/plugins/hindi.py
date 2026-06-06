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
  • Compound-verb (conjunct verb) detection is limited to adjacent light-verb pairs.
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
from typing import Any

from backend.morphology import hi_adapter as _hi_adapter
from backend.plugins.cefr_vocab import (
    A1 as _CEFR_A1, A2 as _CEFR_A2, B1 as _CEFR_B1,
    B2 as _CEFR_B2, C1 as _CEFR_C1, C2 as _CEFR_C2,
)
from backend.schemas.language import LanguageCapabilities, NuanceCapabilities
from backend.schemas.parse import CandidateObject, CandidateSentenceResult, RelationHint

_HI_A1 = _CEFR_A1.get("hi", frozenset())
_HI_A2 = _CEFR_A2.get("hi", frozenset())
_HI_B1 = _CEFR_B1.get("hi", frozenset())
_HI_B2 = _CEFR_B2.get("hi", frozenset())
_HI_C1 = _CEFR_C1.get("hi", frozenset())
_HI_C2 = _CEFR_C2.get("hi", frozenset())

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
    "Compound-verb detection is limited to adjacent light-verb pairs; "
    "no sandhi resolution or loanword analysis. "
    "Lemmatisation not performed; canonical_form is the surface form."
)


def _make_conj_canonical(lemma: str, mt: "Any") -> str:
    """Build a stable conjugation canonical from a stanza HiMorphToken."""
    from backend.morphology.hi_adapter import HiMorphToken  # noqa: PLC0415
    # Primary pedagogical feature
    if mt.verb_form == "infinitive":
        primary = "infinitive"
    elif mt.verb_form == "converb":
        primary = "converb"
    elif mt.tense == "future":
        primary = "future"
    elif mt.aspect:
        primary = mt.aspect         # habitual | perfective | progressive
    elif mt.mood and mt.mood != "indicative":
        primary = mt.mood           # imperative | subjunctive | …
    elif mt.tense:
        primary = mt.tense          # present | past
    elif mt.verb_form:
        primary = mt.verb_form      # participle | finite
    else:
        primary = "finite"
    # Append gender+number when both are known (participle agreement)
    if mt.gender and mt.number:
        short_g = "masc" if mt.gender == "masculine" else "fem"
        short_n = "sing" if mt.number == "singular" else "pl"
        return f"conj:{lemma}:{primary}:{short_g}:{short_n}"
    return f"conj:{lemma}:{primary}"


# ── Compound verbs (V+V constructions) ───────────────────────────────────────
# Vector (light) verbs that form compound verbs with a main verb stem.
# Stanza Hindi lemmatisation is not fully stable across model versions: vector
# verbs may appear as infinitives (लेना), bare stems (ले), or inflected surfaces
# when the model cannot recover a lemma.  Keep the accepted forms narrow and
# limited to closed-class light verbs so compound detection survives those
# model differences without broadening to arbitrary V+V sequences.
_VECTOR_VERB_FORMS: dict[str, str] = {
    # to go — completion / direction
    "जाना": "जाना", "जा": "जा", "गया": "जा", "गई": "जा", "गए": "जा",
    # to give — other-benefit (causative)
    "देना": "देना", "दे": "दे", "दिया": "दे", "दी": "दे", "दिए": "दे",
    # to take — self-benefit (reflexive)
    "लेना": "लेना", "ले": "ले", "लिया": "ले", "ली": "ले", "लिए": "ले",
    # to come — involuntary / resultant action
    "आना": "आना", "आ": "आ",
    # to fall / befall — compulsion
    "पड़ना": "पड़ना", "पड़": "पड़",
    # can / be able — modality
    "सकना": "सकना", "सक": "सक",
    # to remain — continuous aspect
    "रहना": "रहना", "रह": "रह",
    # to sit — inadvertent or undesirable action
    "बैठना": "बैठना", "बैठ": "बैठ",
    # to rise — inceptive / sudden action
    "उठना": "उठना", "उठ": "उठ",
    # to finish — completion (anterior)
    "चुकना": "चुकना", "चुक": "चुक",
    # to throw — forceful / sudden completion
    "डालना": "डालना", "डाल": "डाल",
}


def _normalise_vector_verb(*forms: str | None) -> str | None:
    """Return a stable vector-verb label for a stanza lemma/surface pair."""
    for form in forms:
        if form in _VECTOR_VERB_FORMS:
            return _VECTOR_VERB_FORMS[form]
    return None


def _hi_cefr_confidence(lemma: str, base: float) -> tuple[float, str | None]:
    """Return adjusted (confidence, cefr_level|None) using the CEFR chain."""
    if lemma in _HI_A1:
        return 0.90, "A1"
    if lemma in _HI_A2:
        return 0.88, "A2"
    if lemma in _HI_B1:
        return 0.86, "B1"
    if lemma in _HI_B2:
        return 0.84, "B2"
    if lemma in _HI_C1:
        return 0.82, "C1"
    if lemma in _HI_C2:
        return 0.80, "C2"
    return base, None


class HindiPlugin:
    """Hindi morphology-light plugin.

    Provides Devanagari tokenisation, suffix-based morphology hints with
    conjugation-type emission for detected verb forms, multi-word postposition
    detection, and approximate IAST romanisation. Capabilities honestly declared.
    """

    language_code = "hi"
    display_name  = "Hindi"
    direction     = "ltr"
    capabilities  = LanguageCapabilities(
        code="hi",
        display_name="Hindi",
        direction="ltr",
        script_family="devanagari",
        tokenization_mode="whitespace",
        morphology_depth="shallow",
        lesson_modes_supported=["vocabulary", "dictionary"],
        analysis_depth="morphology_light",
        segmentation_quality="medium",
        tokenization_quality="medium",
        morphology_quality="medium",   # stanza; degrades to "low" without it
        syntax_support=False,
        idiom_detection=False,
        tts_lang_tag="hi",
        transliteration_scheme="iast_approximate",
        tense_pool=["present", "past", "future", "present_habitual"],
        mood_pool=["imperative", "subjunctive", "subjunctive_or_imperative"],
        nuance_capabilities=NuanceCapabilities(
            idioms="none",
            phrase_families="none",
            literary_references="partial",
            cultural_references="partial",
            etymology="none",
            formality_register="stub",
            grammar_nuance="stub",
            pronunciation_tts="stub",
            transliteration="partial",
            proverb_tradition="partial",
            classical_or_scriptural_allusion="partial",
            notes=(
                "Stanza UD model: full lemmatisation + UD POS + morphological "
                "features (Aspect, Tense, Gender, Number, Case, Mood, VerbForm). "
                "Falls back to suffix-rule heuristics without stanza. "
                "Verb forms emitted as conjugation objects with RelationHint. "
                "Multi-word postpositions detected via bigram/trigram scan."
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
        if _hi_adapter.is_available():
            return self._analyze_with_stanza(sentence)
        return self._analyze_heuristic(sentence)

    # ------------------------------------------------------------------
    # Stanza path
    # ------------------------------------------------------------------

    def _analyze_with_stanza(self, sentence: str) -> CandidateSentenceResult:
        morph_tokens = _hi_adapter.analyze_sentence(sentence)
        if not morph_tokens:
            return self._analyze_heuristic(sentence)

        seen: set[str] = set()
        candidates: list[CandidateObject] = []

        for i, mt in enumerate(morph_tokens):
            if mt.upos == "PUNCT":
                continue

            romanized = _romanise(mt.text)
            text_lower = mt.text.lower()
            is_latin = all(c.isascii() for c in mt.text)
            lemma = (mt.lemma or mt.text).lower() if is_latin else (mt.lemma or mt.text)

            # Postpositions (ADP)
            if mt.upos == "ADP" or mt.text in _POSTPOSITIONS:
                cf = mt.text
                if cf not in seen:
                    seen.add(cf)
                    candidates.append(CandidateObject(
                        canonical_form=cf,
                        surface_form=mt.text,
                        type="grammar",
                        label=mt.text,
                        lesson_data={
                            "lemma":     lemma,
                            "romanized": romanized,
                            "pos":       "postposition",
                        },
                        confidence=0.85,
                    ))
                continue

            # Function words: AUX or closed-class surface matches
            if mt.upos == "AUX" or mt.text in _FUNCTION_WORDS:
                cf = mt.text
                if cf not in seen:
                    seen.add(cf)
                    candidates.append(CandidateObject(
                        canonical_form=cf,
                        surface_form=mt.text,
                        type="vocabulary",
                        label=mt.text,
                        lesson_data={
                            "lemma":     lemma,
                            "romanized": romanized,
                            "pos":       "function_word",
                        },
                        confidence=0.80,
                    ))
                continue

            # Latin loanwords — keep surface-based canonical
            if is_latin and mt.text.isalpha():
                cf = text_lower
                if cf not in seen:
                    seen.add(cf)
                    candidates.append(CandidateObject(
                        canonical_form=cf,
                        surface_form=mt.text,
                        type="vocabulary",
                        label=mt.text,
                        lesson_data={
                            "lemma":     cf,
                            "romanized": mt.text,
                            "pos":       mt.upos.lower(),
                            "note":      "Latin-script loanword or technical term.",
                        },
                        confidence=None,
                    ))
                continue

            # Build shared lesson_data (C9: tense+mood always present as keys)
            base_ld: dict[str, Any] = {
                "lemma":     lemma,
                "pos":       mt.upos,
                "romanized": romanized,
                "tense":     mt.tense,
                "mood":      mt.mood,
            }
            if mt.aspect:   base_ld["aspect"]    = mt.aspect
            if mt.gender:   base_ld["gender"]    = mt.gender
            if mt.number:   base_ld["number"]    = mt.number
            if mt.person:   base_ld["person"]    = mt.person
            if mt.case:     base_ld["case"]      = mt.case
            if mt.verb_form: base_ld["verb_form"] = mt.verb_form

            # Confidence: None when stanza has no features (morphologically opaque)
            has_feats = mt.feats_raw is not None

            # VERB tokens → vocabulary + conjugation
            if mt.upos == "VERB":
                vocab_cf = f"verb:{lemma}"
                if vocab_cf not in seen:
                    seen.add(vocab_cf)
                    base_v_conf = 0.85 if has_feats else 0.65
                    v_conf, v_cefr = _hi_cefr_confidence(lemma, base_v_conf)
                    v_ld: dict[str, Any] = {"lemma": lemma, "pos": "VERB", "romanized": romanized}
                    if v_cefr:
                        v_ld["cefr_level"] = v_cefr
                    candidates.append(CandidateObject(
                        canonical_form=vocab_cf,
                        surface_form=mt.text,
                        type="vocabulary",
                        label=lemma,
                        lesson_data=v_ld,
                        confidence=v_conf,
                    ))

                conj_cf = _make_conj_canonical(lemma, mt)
                if conj_cf not in seen:
                    seen.add(conj_cf)
                    candidates.append(CandidateObject(
                        canonical_form=conj_cf,
                        surface_form=mt.text,
                        type="conjugation",
                        label=mt.text,
                        lesson_data=dict(base_ld),
                        confidence=0.85 if has_feats else 0.65,
                        relation_hints=[
                            RelationHint(
                                relation_type="conjugation_of",
                                target_canonical_form=f"verb:{lemma}",
                                target_type="vocabulary",
                            )
                        ],
                    ))
                continue

            # NOUN that looks like an infinitive (ends in ना, ≥ 4 chars)
            if mt.upos == "NOUN" and mt.text.endswith("ना") and len(mt.text) >= 4:
                # Emit infinitive conjugation first (test compatibility), then vocabulary
                conj_cf = f"conj:{lemma}:infinitive"
                if conj_cf not in seen:
                    seen.add(conj_cf)
                    inf_ld = dict(base_ld)
                    inf_ld["verb_form"] = "infinitive"
                    candidates.append(CandidateObject(
                        canonical_form=conj_cf,
                        surface_form=mt.text,
                        type="conjugation",
                        label=mt.text,
                        lesson_data=inf_ld,
                        confidence=0.70,
                        relation_hints=[
                            RelationHint(
                                relation_type="conjugation_of",
                                target_canonical_form=f"verb:{lemma}",
                                target_type="vocabulary",
                            )
                        ],
                    ))
                vocab_cf = f"noun:{lemma}"
                if vocab_cf not in seen:
                    seen.add(vocab_cf)
                    inf_n_conf, inf_n_cefr = _hi_cefr_confidence(lemma, 0.70 if has_feats else 0.50)
                    inf_n_ld = dict(base_ld)
                    if inf_n_cefr:
                        inf_n_ld["cefr_level"] = inf_n_cefr
                    candidates.append(CandidateObject(
                        canonical_form=vocab_cf,
                        surface_form=mt.text,
                        type="vocabulary",
                        label=lemma,
                        lesson_data=inf_n_ld,
                        confidence=inf_n_conf if has_feats else None,
                    ))
                continue

            # NOUN → vocabulary
            if mt.upos in ("NOUN", "PROPN"):
                cf = f"noun:{lemma}"
                if cf not in seen:
                    seen.add(cf)
                    n_conf, n_cefr = _hi_cefr_confidence(lemma, 0.80 if has_feats else 0.50)
                    n_ld = dict(base_ld)
                    if n_cefr:
                        n_ld["cefr_level"] = n_cefr
                    # Ergative: NOUN/PROPN followed by ने marks the ergative subject
                    next_mt = morph_tokens[i + 1] if i + 1 < len(morph_tokens) else None
                    if next_mt is not None and next_mt.text == "ने":
                        n_ld["ergative_subject"] = True
                        n_ld["case"] = "ergative"
                    candidates.append(CandidateObject(
                        canonical_form=cf,
                        surface_form=mt.text,
                        type="vocabulary",
                        label=lemma,
                        lesson_data=n_ld,
                        confidence=n_conf if has_feats else None,
                    ))
                continue

            # ADJ → vocabulary
            if mt.upos == "ADJ":
                cf = f"adj:{lemma}"
                if cf not in seen:
                    seen.add(cf)
                    a_conf, a_cefr = _hi_cefr_confidence(lemma, 0.75 if has_feats else 0.50)
                    a_ld = dict(base_ld)
                    if a_cefr:
                        a_ld["cefr_level"] = a_cefr
                    candidates.append(CandidateObject(
                        canonical_form=cf,
                        surface_form=mt.text,
                        type="vocabulary",
                        label=lemma,
                        lesson_data=a_ld,
                        confidence=a_conf if has_feats else None,
                    ))
                continue

            # ADV → vocabulary
            if mt.upos == "ADV":
                cf = f"adv:{lemma}"
                if cf not in seen:
                    seen.add(cf)
                    candidates.append(CandidateObject(
                        canonical_form=cf,
                        surface_form=mt.text,
                        type="vocabulary",
                        label=lemma,
                        lesson_data=dict(base_ld),
                        confidence=0.70 if has_feats else None,
                    ))
                continue

            # Everything else (PRON, DET, PART, NUM, CCONJ, SCONJ, X, …)
            cf = mt.text
            if cf not in seen:
                seen.add(cf)
                else_ld = dict(base_ld)
                else_ld["confidence_note"] = "Closed-class or low-resource POS; stanza parse."
                candidates.append(CandidateObject(
                    canonical_form=cf,
                    surface_form=mt.text,
                    type="vocabulary",
                    label=mt.text,
                    lesson_data=else_ld,
                    confidence=0.65 if has_feats else None,
                ))

        # Compound verb detection: V+V/AUX bigrams where V2 is a vector (light) verb.
        # Stanza tags vector verbs as AUX in perfective compounds (चला गया) and
        # as VERB in benefactive/completive compounds (खा लिया).
        for j in range(len(morph_tokens) - 1):
            mt1, mt2 = morph_tokens[j], morph_tokens[j + 1]
            v2_lem = _normalise_vector_verb(mt2.lemma, mt2.text)
            if (
                mt1.upos == "VERB"
                and mt2.upos in ("VERB", "AUX")
                and v2_lem is not None
            ):
                v1_lem = mt1.lemma or mt1.text
                compound_cf = f"compound:{v1_lem}+{v2_lem}"
                if compound_cf not in seen:
                    seen.add(compound_cf)
                    candidates.append(CandidateObject(
                        canonical_form=compound_cf,
                        surface_form=f"{mt1.text} {mt2.text}",
                        type="vocabulary",
                        label=f"{mt1.text} {mt2.text}",
                        lesson_data={
                            "pos": "compound_verb",
                            "main_verb": v1_lem,
                            "vector_verb": v2_lem,
                            "romanized": f"{_romanise(mt1.text)} {_romanise(mt2.text)}",
                            "note": f"Compound verb: {v1_lem} + vector verb {v2_lem}",
                        },
                        confidence=0.82,
                    ))

        return CandidateSentenceResult(text=sentence, candidates=candidates)

    # ------------------------------------------------------------------
    # Heuristic suffix-rule fallback path
    # ------------------------------------------------------------------

    def _analyze_heuristic(self, sentence: str) -> CandidateSentenceResult:
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

                    # Ergative subject heuristic: a noun/proper noun immediately
                    # before the postposition "ने" is the ergative-marked
                    # subject (e.g. "राम ने सेब खाया").
                    next_token = deva_tokens[idx + 1] if idx + 1 < len(deva_tokens) else None
                    if next_token == "ने":
                        lesson_data["ergative_subject"] = True
                        lesson_data["case"] = "ergative"

                    candidates.append(CandidateObject(
                        canonical_form=token,
                        surface_form=token,
                        type="vocabulary",
                        label=token,
                        lesson_data=lesson_data,
                        confidence=0.45 if noun_morph else None,
                    ))

        # Compound verb detection for the heuristic path.  This is intentionally
        # conservative: only adjacent Devanagari bigrams whose second token is a
        # closed-class vector form are emitted.
        for idx in range(len(deva_tokens) - 1):
            main_form, vector_form = deva_tokens[idx], deva_tokens[idx + 1]
            vector_lemma = _normalise_vector_verb(vector_form)
            if (
                vector_lemma is None
                or main_form in _POSTPOSITIONS
                or main_form in _FUNCTION_WORDS
            ):
                continue

            compound_cf = f"compound:{main_form}+{vector_lemma}"
            if compound_cf in seen:
                continue

            seen.add(compound_cf)
            candidates.append(CandidateObject(
                canonical_form=compound_cf,
                surface_form=f"{main_form} {vector_form}",
                type="vocabulary",
                label=f"{main_form} {vector_form}",
                lesson_data={
                    "pos": "compound_verb",
                    "main_verb": main_form,
                    "vector_verb": vector_lemma,
                    "romanized": f"{_romanise(main_form)} {_romanise(vector_form)}",
                    "note": f"Compound verb: {main_form} + vector verb {vector_lemma}",
                    "confidence_note": _CONFIDENCE_NOTE,
                },
                confidence=0.55,
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
