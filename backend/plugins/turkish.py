"""Turkish plugin — zeyrek morphology with agglutinative suffix fallback.

BCP-47 code "tr", LTR, Latin script with Turkish special characters.

NLP hierarchy (tried in order, lazy-loaded once per process):
  1. zeyrek  — poetry install --extras turkish  (recommended; rule-based FST,
                no neural network, punkt_tab downloaded automatically on first use)
  2. Suffix-rule heuristic — outermost suffix only; no lemmatisation

What this plugin does reliably
──────────────────────────────
  - Sentence splitting on standard terminal punctuation and newlines.
  - Whitespace tokenisation (Turkish is whitespace-delimited).
  - Turkish dotted-I normalisation (İ→i, I→ı for case folding).
  - Vowel harmony classification: back (a/ı/o/u) vs. front (e/i/ö/ü).

With zeyrek (morphology_quality="medium")
─────────────────────────────────────────
  Full lemmatisation + morphological decomposition.
  Canonical forms: verb:{lemma}, noun:{lemma}, adj:{lemma}, adv:{lemma}.
  Conjugation objects: conj:{lemma}:{tense}:{agreement}.
  Features: tense, mood, person, number, case, possessive, negation, verb_form.

Without zeyrek (morphology_quality="low")
─────────────────────────────────────────
  Suffix chain hints (outermost suffix only):
    • Infinitive: -mak/-mek
    • Progressive: -ıyor/-iyor/-uyor/-üyor
    • Definite past: -dı/-di/-du/-dü/-tı/-ti/-tu/-tü (+ person)
    • Evidential past: -mış/-miş/-muş/-müş
    • Future: -ecek/-acak (+ person)
    • Conditional: -sak/-sek
    • Plural + case: -lardan/-lerden, -larda/-lerde, etc.
    • Singular case: ablative, locative, genitive, comitative/instrumental
    • Aorist 3sg: -ar/-er (min stem length enforced)
  Canonical form uses surface form (no lemmatisation).

Canonical form conventions (zeyrek path — IMMUTABLE after first DB write):
  verb:{lemma}               vocabulary item  e.g. verb:gitmek
  noun:{lemma}               noun             e.g. noun:ev
  adj:{lemma}                adjective        e.g. adj:güzel
  adv:{lemma}                adverb           e.g. adv:hızlı
  conj:{lemma}:{tense}:{agr} conjugation      e.g. conj:gitmek:progressive:A1sg
  conj:{lemma}:infinitive    infinitive       e.g. conj:gitmek:infinitive
  conj:{lemma}:{mood}        mood-only        e.g. conj:gitmek:conditional
  {word}                     function word    e.g. bir

Heuristic-path canonical forms (surface-based, used when zeyrek absent):
  {canonical}:{morph_tag}   conjugation
  {canonical}               vocabulary / function word
"""
from __future__ import annotations

import re
from typing import Any

from backend.morphology import tr_adapter as _tr_adapter
from backend.schemas.language import LanguageCapabilities, NuanceCapabilities
from backend.schemas.parse import CandidateObject, CandidateSentenceResult, RelationHint

# ── Sentence splitting ────────────────────────────────────────────────────────
_SENTENCE_RE = re.compile(r"[^.!?\n]+[.!?\n]?")

# ── Word tokenisation ─────────────────────────────────────────────────────────
_WORD_RE = re.compile(r"[A-Za-zÇçĞğİıÖöŞşÜü]+")

# ── Vowel harmony ─────────────────────────────────────────────────────────────
_BACK_VOWELS  = frozenset("aıouAIOU")
_FRONT_VOWELS = frozenset("eiöüEİÖÜ")
_ALL_VOWELS   = _BACK_VOWELS | _FRONT_VOWELS


def _last_vowel_harmony(word: str) -> str:
    for ch in reversed(word):
        if ch in _BACK_VOWELS:
            return "back"
        if ch in _FRONT_VOWELS:
            return "front"
    return "back"


def _normalise_turkish(token: str) -> str:
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

# ── Morphological suffix rules (heuristic fallback only) ─────────────────────
_SUFFIX_RULES: list[tuple[str, dict]] = [
    ("mak",    {"verb_form": "infinitive", "pos": "verb"}),
    ("mek",    {"verb_form": "infinitive", "pos": "verb"}),
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
    ("mıyor",  {"tense": "progressive", "polarity": "negative", "pos": "verb"}),
    ("miyor",  {"tense": "progressive", "polarity": "negative", "pos": "verb"}),
    ("muyor",  {"tense": "progressive", "polarity": "negative", "pos": "verb"}),
    ("müyor",  {"tense": "progressive", "polarity": "negative", "pos": "verb"}),
    ("ıyor",   {"tense": "progressive", "polarity": "affirmative", "pos": "verb"}),
    ("iyor",   {"tense": "progressive", "polarity": "affirmative", "pos": "verb"}),
    ("uyor",   {"tense": "progressive", "polarity": "affirmative", "pos": "verb"}),
    ("üyor",   {"tense": "progressive", "polarity": "affirmative", "pos": "verb"}),
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
    ("eceksin", {"tense": "future", "person": "second", "number": "singular", "pos": "verb"}),
    ("acaksın", {"tense": "future", "person": "second", "number": "singular", "pos": "verb"}),
    ("eceğim",  {"tense": "future", "person": "first",  "number": "singular", "pos": "verb"}),
    ("acağım",  {"tense": "future", "person": "first",  "number": "singular", "pos": "verb"}),
    ("ecek",    {"tense": "future", "pos": "verb"}),
    ("acak",    {"tense": "future", "pos": "verb"}),
    ("sak",    {"mood": "conditional", "person": "first", "number": "plural", "pos": "verb"}),
    ("sek",    {"mood": "conditional", "person": "first", "number": "plural", "pos": "verb"}),
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
    ("ar",     {"tense": "aorist", "person": "third", "number": "singular", "pos": "verb"}),
    ("er",     {"tense": "aorist", "person": "third", "number": "singular", "pos": "verb"}),
]

_AORIST_BLOCKLIST: frozenset[str] = frozenset({
    "bir", "her", "ver", "yer", "ger", "mer", "ser", "ber",
    "nar", "bar", "car", "dar", "far", "gar", "har", "jar",
    "kar", "lar", "mar", "par", "sar", "tar", "var", "zar",
    "dolar", "şeker", "pazar", "haber", "yazar", "kamer",
    "noter", "fiber", "laser", "liner", "poker",
})

_CONFIDENCE_NOTE_HEURISTIC = (
    "Turkish morphology-light: outermost suffix stripped for feature hints. "
    "Inner suffix layers (possessive, aspect stacking, evidentiality) not analysed. "
    "No trained NLP model used. Canonical form uses surface form + morphology tag."
)

_VERB_POS = frozenset({"verb"})


def _extract_morph(token: str) -> dict:
    lower = _normalise_turkish(token)
    for suffix, features in _SUFFIX_RULES:
        if not lower.endswith(suffix):
            continue
        stem_len = len(lower) - len(suffix)
        if stem_len < 2:
            continue
        if suffix in ("ar", "er"):
            if stem_len < 3 or lower in _AORIST_BLOCKLIST:
                continue
        return dict(features)
    return {}


# ── Agreement code builder for conjugation canonical ─────────────────────────

def _agr_code(person: str | None, number: str | None) -> str | None:
    """Convert person/number to UD-style agreement code (A1sg, etc.)."""
    _p = {"first": "1", "second": "2", "third": "3"}
    _n = {"singular": "sg", "plural": "pl"}
    p = _p.get(person or "")
    n = _n.get(number or "")
    if p and n:
        return f"A{p}{n}"
    return None


# ── Plugin ────────────────────────────────────────────────────────────────────

class TurkishPlugin:
    """Turkish plugin — zeyrek primary, suffix-rule fallback.

    morphology_quality reflects zeyrek capability; falls to "low" without it.
    """

    language_code = "tr"
    display_name  = "Turkish"
    direction     = "ltr"
    capabilities  = LanguageCapabilities(
        code="tr",
        display_name="Turkish",
        direction="ltr",
        script_family="latin",
        tokenization_mode="whitespace",
        morphology_depth="shallow",
        lesson_modes_supported=["vocabulary", "dictionary"],
        analysis_depth="morphology_light",
        segmentation_quality="medium",
        tokenization_quality="high",
        morphology_quality="medium",   # with zeyrek; degrades to "low" without it
        syntax_support=False,
        idiom_detection=False,
        tts_lang_tag="tr",
        transliteration_scheme=None,
        tense_pool=["aorist", "progressive", "past_definite", "past_evidential", "future", "present"],
        mood_pool=["conditional", "optative", "imperative", "necessitative"],
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
                "Zeyrek rule-based FST: full lemmatisation + case/tense/person/number. "
                "Falls back to outermost-suffix heuristic without zeyrek. "
                "Vowel harmony detected. Detected verb forms emitted as conjugation objects."
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
        if _tr_adapter.is_available():
            return self._analyze_with_zeyrek(sentence)
        return self._analyze_heuristic(sentence)

    def get_lesson(self, object_id: str) -> CandidateObject | None:
        return self.lesson_store.get(object_id)

    # ------------------------------------------------------------------
    # zeyrek path
    # ------------------------------------------------------------------

    def _analyze_with_zeyrek(self, sentence: str) -> CandidateSentenceResult:
        tokens = _WORD_RE.findall(sentence)
        morph_tokens = _tr_adapter.analyze_tokens(tokens)
        seen: set[str] = set()
        candidates: list[CandidateObject] = []

        for mt in morph_tokens:
            harmony = _last_vowel_harmony(mt.text)
            canonical_lower = _normalise_turkish(mt.text)

            if canonical_lower in _FUNCTION_WORDS:
                cf = canonical_lower
                if cf not in seen:
                    seen.add(cf)
                    candidates.append(CandidateObject(
                        canonical_form=cf,
                        surface_form=mt.text,
                        type="vocabulary",
                        label=mt.text,
                        lesson_data={
                            "lemma": mt.lemma or canonical_lower,
                            "pos": "function_word",
                            "vowel_harmony": harmony,
                        },
                        confidence=0.80,
                    ))
                continue

            pos = mt.pos  # "Verb", "Noun", "Adj", "Adv", etc.
            # Apply Turkish-correct lowercasing to lemma (İ→i, I→ı).
            lemma = _normalise_turkish(mt.lemma) if mt.lemma else canonical_lower

            # Build base lesson_data.
            # C9 contract: conjugation objects must carry both "tense" and "mood"
            # keys (values may be None for mood-only or tense-only forms).
            ld: dict[str, Any] = {
                "lemma": lemma,
                "pos": pos,
                "vowel_harmony": harmony,
                "tense": mt.tense,   # None is acceptable; key must be present
                "mood": mt.mood,     # None is acceptable; key must be present
            }
            if mt.person:
                ld["person"] = mt.person
            if mt.number:
                ld["number"] = mt.number
            if mt.case:
                ld["case"] = mt.case
            if mt.possessive:
                ld["possessive"] = mt.possessive
            if mt.negation:
                ld["negation"] = True
            if mt.verb_form:
                ld["verb_form"] = mt.verb_form

            is_verb = pos == "Verb"
            is_finite_verb = is_verb and (mt.tense or mt.mood) and mt.verb_form != "infinitive"
            is_infinitive = is_verb and mt.verb_form == "infinitive"

            if is_finite_verb or is_infinitive:
                # Vocabulary: verb:{lemma}
                vocab_cf = f"verb:{lemma}"
                if vocab_cf not in seen:
                    seen.add(vocab_cf)
                    vocab_ld: dict[str, Any] = {"lemma": lemma, "pos": "Verb", "vowel_harmony": harmony}
                    candidates.append(CandidateObject(
                        canonical_form=vocab_cf,
                        surface_form=mt.text,
                        type="vocabulary",
                        label=lemma,
                        lesson_data=vocab_ld,
                        confidence=0.85,
                    ))

                # Conjugation: conj:{lemma}:{tense_or_mood}:{agreement}
                if is_infinitive:
                    conj_cf = f"conj:{lemma}:infinitive"
                else:
                    feature = mt.tense or mt.mood or "present"
                    agr = _agr_code(mt.person, mt.number)
                    conj_cf = f"conj:{lemma}:{feature}:{agr}" if agr else f"conj:{lemma}:{feature}"

                if conj_cf not in seen:
                    seen.add(conj_cf)
                    candidates.append(CandidateObject(
                        canonical_form=conj_cf,
                        surface_form=mt.text,
                        type="conjugation",
                        label=mt.text,
                        lesson_data=ld,
                        confidence=0.85,
                        relation_hints=[
                            RelationHint(
                                relation_type="conjugation_of",
                                target_canonical_form=f"verb:{lemma}",
                                target_type="vocabulary",
                            )
                        ],
                    ))
            elif pos == "Noun" and mt.verb_form == "infinitive" and "Verb" in mt.morphemes:
                # Turkish verbal nouns (gitmek = "to go"): zeyrek classifies these
                # as Noun (the infinitive suffix nominalises the verb), but they are
                # pedagogically verb forms.  Emit both a vocabulary item and a
                # conjugation item so learners see the verb root and its infinitive.
                vocab_cf = f"verb:{lemma}"
                if vocab_cf not in seen:
                    seen.add(vocab_cf)
                    candidates.append(CandidateObject(
                        canonical_form=vocab_cf,
                        surface_form=mt.text,
                        type="vocabulary",
                        label=lemma,
                        lesson_data={"lemma": lemma, "pos": "Verb", "vowel_harmony": harmony},
                        confidence=0.85,
                    ))
                conj_cf = f"conj:{lemma}:infinitive"
                if conj_cf not in seen:
                    seen.add(conj_cf)
                    inf_ld = dict(ld)
                    inf_ld["pos"] = "Verb"  # zeyrek classifies infinitive as Noun; override
                    candidates.append(CandidateObject(
                        canonical_form=conj_cf,
                        surface_form=mt.text,
                        type="conjugation",
                        label=mt.text,
                        lesson_data=inf_ld,
                        confidence=0.85,
                        relation_hints=[
                            RelationHint(
                                relation_type="conjugation_of",
                                target_canonical_form=f"verb:{lemma}",
                                target_type="vocabulary",
                            )
                        ],
                    ))
            elif pos == "Noun":
                cf = f"noun:{lemma}"
                if cf not in seen:
                    seen.add(cf)
                    candidates.append(CandidateObject(
                        canonical_form=cf,
                        surface_form=mt.text,
                        type="vocabulary",
                        label=lemma,
                        lesson_data=ld,
                        confidence=0.80,
                    ))
            elif pos == "Adj":
                cf = f"adj:{lemma}"
                if cf not in seen:
                    seen.add(cf)
                    candidates.append(CandidateObject(
                        canonical_form=cf,
                        surface_form=mt.text,
                        type="vocabulary",
                        label=lemma,
                        lesson_data=ld,
                        confidence=0.80,
                    ))
            elif pos == "Adv":
                cf = f"adv:{lemma}"
                if cf not in seen:
                    seen.add(cf)
                    candidates.append(CandidateObject(
                        canonical_form=cf,
                        surface_form=mt.text,
                        type="vocabulary",
                        label=lemma,
                        lesson_data=ld,
                        confidence=0.75,
                    ))
            else:
                # Pronoun, Conj, Det, Num, Interj, Unknown, etc.
                cf = canonical_lower
                if cf not in seen:
                    seen.add(cf)
                    else_ld = dict(ld)
                    else_ld["confidence_note"] = (
                        "Closed-class or unrecognised POS; zeyrek parse used as-is."
                    )
                    candidates.append(CandidateObject(
                        canonical_form=cf,
                        surface_form=mt.text,
                        type="vocabulary",
                        label=mt.text,
                        lesson_data=else_ld,
                        confidence=0.65,
                    ))

        return CandidateSentenceResult(text=sentence, candidates=candidates)

    # ------------------------------------------------------------------
    # Heuristic suffix-rule fallback path (unchanged from original)
    # ------------------------------------------------------------------

    def _analyze_heuristic(self, sentence: str) -> CandidateSentenceResult:
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
                morph_tag = ":".join(f"{k}={v}" for k, v in sorted(morph.items()))
                conj_canonical = f"{canonical}:{morph_tag}"
                lesson_data: dict = {
                    "surface_form":    token,
                    "vowel_harmony":   harmony,
                    "confidence_note": _CONFIDENCE_NOTE_HEURISTIC,
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
                    lesson_data["confidence_note"] = _CONFIDENCE_NOTE_HEURISTIC
                else:
                    lesson_data["confidence_note"] = _CONFIDENCE_NOTE_HEURISTIC
                candidates.append(CandidateObject(
                    canonical_form=canonical,
                    surface_form=token,
                    type="vocabulary",
                    label=token,
                    lesson_data=lesson_data,
                    confidence=0.45 if morph else None,
                ))

        return CandidateSentenceResult(text=sentence, candidates=candidates)


def create_plugin() -> TurkishPlugin:
    return TurkishPlugin()
