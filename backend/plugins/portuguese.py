"""Portuguese language plugin — spaCy ``pt_core_news_sm``.

Registers as ``language_code = "pt"``.

Read this alongside ``PLUGIN_AUTHOR_GUIDE.md`` and the French reference
implementation (``french.py``) when building or extending this plugin.

─────────────────────────────────────────────────────────────────────────────
WHAT THIS PLUGIN EXTRACTS
─────────────────────────────────────────────────────────────────────────────

**Vocabulary** — open-class content words (NOUN, ADJ, ADV, non-finite
VERB/AUX).  Finite verbs are excluded here; they appear as conjugation objects.
Gender and number are included for NOUN entries when the model provides them.

  lesson_data keys: lemma, pos, gender*, number*, verb_form*, confidence_note*

**Conjugation** — finite VERB and AUX tokens (VerbForm=Fin), annotated with:
  • morphological features: tense, mood, person, number
  • is_reflexive: True when a child PRON carries Reflex=Yes
  • morph_complete: True when tense + mood + person are all resolved
  • paradigm_class: -ar / -er / -ir / irregular
  • is_irregular: True for known irregular verb stems
  • construction: periphrastic annotation (see below)

  lesson_data keys: lemma, surface, tense, mood, person, number,
                    morph_complete, is_reflexive, paradigm_class,
                    is_irregular, construction, confidence_note*

**Agreement** — DET+NOUN and ADJ+NOUN pairs with at least one positively
confirmed morphological match (gender or number).

  lesson_data keys: modifier, modifier_pos, noun, gender, number,
                    gender_match, number_match, confidence_note

─────────────────────────────────────────────────────────────────────────────
GRAMMAR PATTERNS
─────────────────────────────────────────────────────────────────────────────

**Grammar** — periphrastic construction objects derived from conjugation
results.  Covers: ser_copula, estar_copula, ter_perfect, ir_near_future,
estar_progressive.

  lesson_data keys: pattern_id, pattern, usage, contrast, verb_lemma,
                    surface_verb

**Idiom** — ~30 common fixed Portuguese expressions detected by surface-form
token matching against a curated table.

  lesson_data keys: phrase, meaning, register

**Nuance** — aspectual and modal observations derived from conjugation results.
Covers: imperfect_aspect, subjunctive_mood, conditional_mood, reflexive_verb,
personal_infinitive (unique to Portuguese: inflected infinitive with person).

  lesson_data keys: nuance_type, lemma, surface, note, contrast_tense*

─────────────────────────────────────────────────────────────────────────────
KNOWN MODEL LIMITATIONS (pt_core_news_sm)
─────────────────────────────────────────────────────────────────────────────

- ``pt_core_news_sm`` is a small model trained primarily on news text.
  Subjunctive and conditional morphology is less reliable than indicative.
  morph_complete and confidence ratings reflect this.
- European vs Brazilian Portuguese: the model covers both registers but
  was trained predominantly on news, which skews toward formal BP (Brazilian
  Portuguese).  European orthographic differences (e.g. "facto" vs "fato")
  may affect tokenisation and lemmatisation.
- The personal infinitive (infinitivo pessoal, e.g. "para eles falarem") is
  extracted as a nuance observation when VerbForm=Inf and Person is set.
  The small model may not tag Person on all personal infinitives.
- ``clitic_climbing`` (e.g. "vou fazê-lo") splits into "vou fazer lo" by
  the tokeniser; the cliticised pronoun is handled as a separate token and
  does not affect conjugation extraction.

─────────────────────────────────────────────────────────────────────────────
MULTILINGUAL ARCHITECTURE NOTES
─────────────────────────────────────────────────────────────────────────────

1. Portuguese has two copulas: ``ser`` (identity, origin, permanent states) and
   ``estar`` (temporary states, location, progressive). Both are extracted as
   grammar pattern objects with distinct ``pattern_id`` values.
2. The ``paradigm_class`` convention (-ar / -er / -ir / irregular) matches
   Spanish and is documented in PLUGIN_AUTHOR_GUIDE.md.
3. Personal infinitive (Portuguese-unique): recorded as a ``nuance`` object
   rather than a separate conjugation type, because the FSRS system already
   distinguishes it via the ``nuance_of`` relation pointing at the relevant
   vocabulary lemma.
4. Reflexive detection uses model-agnostic ``Reflex=Yes`` — same approach as
   the French plugin.
"""
from __future__ import annotations

import logging
from functools import cached_property
from typing import Any

from backend.plugins.cefr_vocab import A1 as _CEFR_A1
from backend.core.vocab_index import get_cefr_level as _get_cefr_level
from backend.schemas.language import LanguageCapabilities, NuanceCapabilities
from backend.schemas.parse import (
    CandidateObject,
    CandidateSentenceResult,
    RelationHint,
)

logger = logging.getLogger(__name__)

_A1 = _CEFR_A1.get("pt", frozenset())

# ── POS filter ────────────────────────────────────────────────────────────────

_SKIP_POS = frozenset({
    "DET", "ADP", "CCONJ", "SCONJ", "CONJ", "PUNCT", "SPACE",
    "X", "SYM", "NUM", "PRON", "INTJ",
})

_NON_FINITE_FORMS = frozenset({"Inf", "Part", "Ger"})

# ── Display maps ──────────────────────────────────────────────────────────────

_TENSE_DISPLAY: dict[str, str] = {
    "Pres": "present",
    "Imp":  "imperfect",
    "Fut":  "future",
    "Past": "past",
    "Pqp":  "pluperfect",
}

_MOOD_DISPLAY: dict[str, str] = {
    "Ind": "indicative",
    "Sub": "subjunctive",
    "Cnd": "conditional",
    "Imp": "imperative",
}

# ── Irregular verbs ────────────────────────────────────────────────────────────

_IRREGULAR_VERBS: frozenset[str] = frozenset({
    "ser", "estar", "ter", "haver", "ir", "vir", "pôr", "saber",
    "poder", "querer", "fazer", "dar", "ver", "ler", "trazer",
    "dizer", "caber", "crer", "rir", "ouvir", "pedir", "perder",
    "medir", "sentir", "dormir", "subir", "fugir", "cobrir",
    "abrir", "descobrir", "escrever", "viver", "seguir",
})

# ── Idiom table ────────────────────────────────────────────────────────────────
# Each entry: (token_tuple_lowercase, english_meaning, register)
# Sorted longest-first for greedy left-to-right matching.

_IDIOM_TABLE: tuple[tuple[tuple[str, ...], str, str], ...] = (
    # ── 4-word ────────────────────────────────────────────────────────────────
    (("de", "vez", "em", "quando"),        "from time to time",                "neutral"),
    (("cada", "vez", "mais"),              "more and more",                    "neutral"),
    (("de", "forma", "que"),               "in such a way that",               "formal"),
    # ── 3-word ────────────────────────────────────────────────────────────────
    (("ao", "mesmo", "tempo"),             "at the same time",                 "neutral"),
    (("por", "outro", "lado"),             "on the other hand",                "neutral"),
    (("em", "vez", "de"),                  "instead of",                       "neutral"),
    (("a", "partir", "de"),               "starting from / from",              "neutral"),
    (("em", "torno", "de"),               "around / approximately",            "neutral"),
    (("ao", "longo", "de"),               "throughout / along",                "neutral"),
    (("por", "sua", "vez"),               "in turn / for their part",          "formal"),
    (("de", "acordo", "com"),             "according to / in accordance with",  "formal"),
    (("em", "relação", "a"),              "regarding / with respect to",        "formal"),
    (("nesse", "sentido"),                 "in that sense / in that regard",    "formal"),
    (("de", "certa", "forma"),            "in a certain way / to some extent",  "neutral"),
    # ── 2-word ────────────────────────────────────────────────────────────────
    (("por", "exemplo"),                   "for example",                      "neutral"),
    (("por", "isso"),                      "therefore / that's why",           "neutral"),
    (("por", "fim"),                       "finally / in the end",             "neutral"),
    (("de", "fato"),                       "in fact / indeed",                 "neutral"),
    (("pelo", "menos"),                    "at least",                         "neutral"),
    (("mais", "ou"),                       "more or less / so-so",             "neutral"),
    (("às", "vezes"),                      "sometimes / at times",             "neutral"),
    (("no", "entanto"),                    "however / nevertheless",           "neutral"),
    (("além", "disso"),                    "besides / moreover",               "neutral"),
    (("em", "geral"),                      "in general / generally",           "neutral"),
    (("ao", "contrário"),                  "on the contrary",                  "neutral"),
    (("de", "repente"),                    "suddenly",                         "neutral"),
    (("em", "breve"),                      "soon / shortly",                   "neutral"),
    (("com", "certeza"),                   "certainly / for sure",             "neutral"),
    (("de", "acordo"),                     "agreed / in agreement",            "neutral"),
    (("em", "seguida"),                    "then / right after",               "neutral"),
    (("boa", "sorte"),                     "good luck",                        "neutral"),
    (("de", "nada"),                       "you're welcome",                   "neutral"),
)

# ── Grammar patterns ──────────────────────────────────────────────────────────
# (construction, required_lemma_or_None, pattern_id, pattern_label, usage, contrast)

_GRAMMAR_PATTERNS: tuple[tuple[str, str | None, str, str, str, str], ...] = (
    (
        "ser_copula", "ser",
        "ser_copula",
        "ser + [noun / adjective]",
        "Expresses essential or permanent characteristics: identity, nationality, "
        "origin, profession, material composition, and inherent qualities. "
        "'Ela é médica', 'O livro é de madeira', 'Somos brasileiros'.",
        "Use estar for temporary states, moods, and locations: "
        "'Ela está cansada' (she is tired right now), not 'é cansada'.",
    ),
    (
        "estar_copula", "estar",
        "estar_copula",
        "estar + [adjective / location]",
        "Expresses temporary states, current conditions, moods, and location: "
        "'Estou feliz hoje', 'Ele está em casa'. "
        "Also used to form the progressive with the gerund.",
        "Use ser for permanent or defining characteristics: "
        "'Ela é inteligente' (she is an intelligent person, inherently).",
    ),
    (
        "ter_perfect", "ter",
        "ter_perfect",
        "ter + [past participle]",
        "Forms the compound perfect tenses in modern Brazilian and European Portuguese: "
        "'Tenho comido bem' (I have been eating well). "
        "In colloquial BP, this construction has progressive-like nuance; "
        "in EP it signals a completed repeated or habitual action.",
        "The simple past (pretérito perfeito simples — 'comi') is more common "
        "in BP for a single completed event. The compound perfect is rare in BP speech.",
    ),
    (
        "ir_near_future", "ir",
        "ir_near_future",
        "ir + [infinitive]",
        "Expresses a planned or imminent future action: "
        "'Vou estudar amanhã' (I am going to study tomorrow). "
        "Widely used in speech as an alternative to the simple future tense.",
        "The synthetic future ('estudarei') is more formal and marks more "
        "distant or hypothetical events.",
    ),
    (
        "estar_progressive", "estar",
        "estar_progressive",
        "estar + [gerund (-ando/-endo/-indo)]",
        "Expresses an ongoing action at the time of speaking or at a specified "
        "past moment: 'Estou estudando' (I am studying). "
        "This construction is dominant in Brazilian Portuguese; "
        "European Portuguese uses 'estar a + infinitive' instead.",
        "In European Portuguese, the progressive is 'estar a + infinitivo' "
        "('Estou a estudar') — the gerund construction is considered Brazilianism "
        "in formal European contexts.",
    ),
)


# ── Plugin ─────────────────────────────────────────────────────────────────────

class PortuguesePlugin:
    language_code = "pt"
    display_name  = "Portuguese"
    direction     = "ltr"
    capabilities  = LanguageCapabilities(
        code="pt",
        display_name="Portuguese",
        direction="ltr",
        script_family="latin",
        tokenization_mode="whitespace",
        morphology_depth="rich",
        lesson_modes_supported=["morphology", "vocabulary"],
        analysis_depth="full",
        segmentation_quality="medium",    # pt_core_news_sm sentence splitting is adequate
        tokenization_quality="high",      # word tokenisation reliable; clitic splitting varies
        morphology_quality="medium",      # small model; subjunctive/conditional less reliable
        syntax_support=True,              # dep parse used for modifier / reflexive detection
        idiom_detection=True,             # curated fixed-expression table (~30 entries)
        tts_lang_tag="pt",
        transliteration_scheme=None,
        tense_pool=["present", "imperfect", "past", "future", "pluperfect"],
        mood_pool=["indicative", "subjunctive", "conditional", "imperative"],
        nuance_capabilities=NuanceCapabilities(
            idioms="partial",            # curated ~30-entry fixed-expression table
            phrase_families="stub",      # no phrase catalog yet; extractor wired
            literary_references="none",
            cultural_references="none",
            etymology="none",
            formality_register="partial", # você/tu distinction; extractor wired
            grammar_nuance="partial",    # tense/mood/person/number drilling
            pronunciation_tts="partial", # browser TTS reliable for pt
            transliteration="none",
            proverb_tradition="none",
            classical_or_scriptural_allusion="none",
        ),
    )

    def __init__(self) -> None:
        self.lesson_store: dict[str, CandidateObject] = {}

    # ------------------------------------------------------------------
    # Model — lazy, loaded at most once per process
    # ------------------------------------------------------------------

    @cached_property
    def _nlp(self) -> Any:
        try:
            import spacy  # noqa: PLC0415
            return spacy.load("pt_core_news_sm", disable=["ner"])
        except ImportError as exc:
            raise RuntimeError(
                "spaCy is not installed.  Run: pip install spacy"
            ) from exc
        except OSError as exc:
            raise RuntimeError(
                "spaCy model 'pt_core_news_sm' not found. "
                "Run: python -m spacy download pt_core_news_sm"
            ) from exc

    # ------------------------------------------------------------------
    # LanguagePlugin protocol
    # ------------------------------------------------------------------

    def analyze_text(self, text: str) -> list[CandidateSentenceResult]:
        doc = self._nlp(text.strip())
        results = []
        for sent in doc.sents:
            sent_text = sent.text.strip()
            if not sent_text:
                continue
            results.append(self._analyze_tokens(sent_text, list(sent)))
        return results

    def split_sentences(self, text: str) -> list[str]:
        doc = self._nlp(text.strip())
        return [s.text.strip() for s in doc.sents if s.text.strip()]

    def analyze_sentence(self, sentence: str) -> CandidateSentenceResult:
        doc = self._nlp(sentence)
        return self._analyze_tokens(sentence, list(doc))

    def _analyze_tokens(
        self, sentence: str, tokens: list[Any]
    ) -> CandidateSentenceResult:
        seen_vocab: set[str] = set()
        seen_conj:  set[str] = set()

        candidates: list[CandidateObject] = []

        conj_candidates = self._extract_conjugations(tokens, seen_conj, seen_vocab)
        candidates.extend(conj_candidates)
        candidates.extend(self._extract_vocabulary(tokens, seen_vocab))
        candidates.extend(self._extract_agreements(tokens))
        candidates.extend(self._extract_idioms(tokens))

        seen_grammar: set[str] = set()
        seen_nuance:  set[str] = set()
        candidates.extend(self._extract_grammar(conj_candidates, seen_grammar))
        candidates.extend(self._extract_nuance(conj_candidates, tokens, seen_nuance))

        return CandidateSentenceResult(text=sentence, candidates=candidates)

    def get_lesson(self, object_id: str) -> CandidateObject | None:
        return self.lesson_store.get(object_id)

    # ------------------------------------------------------------------
    # Vocabulary
    # ------------------------------------------------------------------

    def _extract_vocabulary(
        self,
        tokens: list[Any],
        seen: set[str],
    ) -> list[CandidateObject]:
        candidates: list[CandidateObject] = []
        for tok in tokens:
            if tok.pos_ in _SKIP_POS or tok.is_punct or tok.is_space:
                continue

            verb_form = _morph_first(tok, "VerbForm")

            if tok.pos_ in {"VERB", "AUX"} and verb_form not in _NON_FINITE_FORMS:
                continue

            lemma = tok.lemma_.lower()
            if " " in lemma or len(lemma) < 2 or lemma in seen:
                continue
            seen.add(lemma)

            confidence, confidence_note = self._vocab_confidence(tok, lemma)
            data: dict[str, Any] = {"lemma": lemma, "pos": tok.pos_}
            cefr = _get_cefr_level("pt", lemma) or ("A1" if lemma in _A1 else None)
            if cefr:
                data["cefr_level"] = cefr

            if tok.pos_ == "NOUN":
                if gender := _morph_first(tok, "Gender"):
                    data["gender"] = gender
                if number := _morph_first(tok, "Number"):
                    data["number"] = number

            if tok.pos_ in {"VERB", "AUX"} and verb_form:
                data["verb_form"] = verb_form

            if confidence_note is not None:
                data["confidence_note"] = confidence_note

            candidates.append(CandidateObject(
                canonical_form=lemma,
                surface_form=tok.text,
                type="vocabulary",
                label=tok.text,
                lesson_data=data,
                confidence=confidence,
            ))
        return candidates

    def _vocab_confidence(self, tok: Any, lemma: str) -> tuple[float, str | None]:
        if tok.pos_ == "PROPN":
            return 0.60, "proper noun — may not represent general vocabulary"
        if lemma in _A1 or _get_cefr_level("pt", lemma):
            return 0.90, None  # known word — suppress is_oov false-positive
        if tok.is_oov:
            return 0.50, "word not found in model vocabulary — form may be incorrect"
        return 0.85, None

    # ------------------------------------------------------------------
    # Conjugation
    # ------------------------------------------------------------------

    def _extract_conjugations(
        self,
        tokens: list[Any],
        seen_conj: set[str],
        seen_vocab: set[str],
    ) -> list[CandidateObject]:
        candidates: list[CandidateObject] = []
        for tok in tokens:
            if tok.pos_ not in {"VERB", "AUX"}:
                continue
            verb_form = _morph_first(tok, "VerbForm")
            if verb_form in _NON_FINITE_FORMS:
                continue

            lemma = tok.lemma_.lower()
            if " " in lemma:
                continue

            feats = self._verb_morph(tok)
            canonical_form = _conj_canonical_form(lemma, feats)
            if canonical_form in seen_conj:
                continue
            seen_conj.add(canonical_form)
            seen_vocab.add(lemma)

            is_reflexive    = _has_reflexive_clitic(tok, tokens)
            construction    = _detect_construction(tok)
            confidence      = self._conj_confidence(tok, feats)
            confidence_note = _conj_confidence_note(feats, tok.is_oov)

            lesson: dict[str, Any] = {
                "lemma":          lemma,
                "surface":        tok.text,
                "tense":          feats["tense"],
                "mood":           feats["mood"],
                "person":         feats["person"],
                "number":         feats["number"],
                "morph_complete": _conj_is_complete(feats),
                "is_reflexive":   is_reflexive,
                "construction":   construction,
                "paradigm_class": _paradigm_class(lemma),
                "is_irregular":   lemma in _IRREGULAR_VERBS,
            }
            if "verb_form" in feats:
                lesson["verb_form"] = feats["verb_form"]
            if confidence_note is not None:
                lesson["confidence_note"] = confidence_note

            candidates.append(CandidateObject(
                canonical_form=canonical_form,
                surface_form=tok.text,
                type="conjugation",
                label=tok.text,
                lesson_data=lesson,
                confidence=confidence,
                relation_hints=[
                    RelationHint(
                        relation_type="conjugation_of",
                        target_canonical_form=lemma,
                        target_type="vocabulary",
                    )
                ],
            ))
        return candidates

    def _verb_morph(self, tok: Any) -> dict[str, str]:
        tense_raw = _morph_first(tok, "Tense")
        mood_raw  = _morph_first(tok, "Mood")
        person    = _morph_first(tok, "Person")
        number    = _morph_first(tok, "Number")
        verb_form = _morph_first(tok, "VerbForm")

        feats: dict[str, str] = {
            "tense":  _TENSE_DISPLAY.get(tense_raw or "", tense_raw or "unknown"),
            "mood":   _MOOD_DISPLAY.get(mood_raw or "", mood_raw or "unknown"),
            "person": person or "unknown",
            "number": number or "unknown",
        }
        if verb_form:
            feats["verb_form"] = verb_form
        return feats

    def _conj_confidence(self, tok: Any, feats: dict[str, str]) -> float:
        known = sum(
            1 for k in ("tense", "mood", "person")
            if feats.get(k) not in (None, "unknown")
        )
        base = 0.50 + known * 0.10
        if tok.is_oov:
            base -= 0.10
        return round(min(base, 0.80), 2)

    # ------------------------------------------------------------------
    # Agreement
    # ------------------------------------------------------------------

    def _extract_agreements(self, tokens: list[Any]) -> list[CandidateObject]:
        """Find DET+NOUN and ADJ+NOUN agreement pairs.

        Portuguese adjectives may precede or follow the noun.
        ``bom`` / ``boa``, ``grande``, etc. are common pre-nominal adjectives.
        Contractions like ``no`` (= em + o) and ``do`` (= de + o) are ADP
        in spaCy's Universal Dependencies tagging and are naturally excluded.
        """
        candidates: list[CandidateObject] = []
        seen_pairs: set[tuple[str, str, str]] = set()

        nouns = [t for t in tokens if t.pos_ == "NOUN"]
        for noun in nouns:
            noun_gender = _morph_first(noun, "Gender")
            noun_number = _morph_first(noun, "Number")
            if not noun_gender and not noun_number:
                continue

            for cand in _find_modifiers(noun, tokens):
                cand_gender = _morph_first(cand, "Gender")
                cand_number = _morph_first(cand, "Number")

                gender_match = (
                    cand_gender == noun_gender
                    if cand_gender and noun_gender else None
                )
                number_match = (
                    cand_number == noun_number
                    if cand_number and noun_number else None
                )

                if gender_match is None and number_match is None:
                    continue
                if gender_match is False or number_match is False:
                    continue

                pair_key = (cand.pos_, cand.lemma_.lower(), noun.lemma_.lower())
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                noun_lemma = noun.lemma_.lower()
                cand_lemma = cand.lemma_.lower()
                label = (
                    f"{cand.text} {noun.text}"
                    if cand.i < noun.i
                    else f"{noun.text} {cand.text}"
                )
                canonical_form = f"{cand.pos_.lower()}:{cand_lemma}_{noun_lemma}"
                confidence      = _agreement_confidence(gender_match, number_match)
                confidence_note = _agreement_confidence_note(gender_match, number_match)

                candidates.append(CandidateObject(
                    canonical_form=canonical_form,
                    surface_form=label,
                    type="agreement",
                    label=label,
                    lesson_data={
                        "modifier":        cand.text,
                        "modifier_pos":    cand.pos_,
                        "noun":            noun.text,
                        "gender":          noun_gender or "unknown",
                        "number":          noun_number or "unknown",
                        "gender_match":    gender_match,
                        "number_match":    number_match,
                        "confidence_note": confidence_note,
                    },
                    confidence=confidence,
                    relation_hints=[
                        RelationHint(
                            relation_type="agreement_of",
                            target_canonical_form=noun_lemma,
                            target_type="vocabulary",
                        )
                    ],
                ))
        return candidates

    # ------------------------------------------------------------------
    # Idioms
    # ------------------------------------------------------------------

    def _extract_idioms(self, tokens: list[Any]) -> list[CandidateObject]:
        if not tokens:
            return []

        lower_texts  = [t.text.lower() for t in tokens]
        n            = len(lower_texts)
        seen_idioms: set[str]  = set()
        used_positions: set[int] = set()
        candidates: list[CandidateObject] = []

        for words, meaning, register in _IDIOM_TABLE:
            wlen = len(words)
            for start in range(n - wlen + 1):
                if any(start + k in used_positions for k in range(wlen)):
                    continue
                if lower_texts[start : start + wlen] == list(words):
                    phrase = " ".join(words)
                    if phrase in seen_idioms:
                        continue
                    seen_idioms.add(phrase)
                    used_positions.update(range(start, start + wlen))
                    surface = " ".join(t.text for t in tokens[start : start + wlen])
                    candidates.append(CandidateObject(
                        canonical_form=phrase,
                        surface_form=surface,
                        type="idiom",
                        label=surface,
                        lesson_data={
                            "phrase":   phrase,
                            "meaning":  meaning,
                            "register": register,
                        },
                        confidence=0.90,
                    ))

        return candidates

    # ------------------------------------------------------------------
    # Grammar patterns
    # ------------------------------------------------------------------

    def _extract_grammar(
        self,
        conj_candidates: list[CandidateObject],
        seen_grammar: set[str],
    ) -> list[CandidateObject]:
        candidates: list[CandidateObject] = []

        for conj in conj_candidates:
            construction = conj.lesson_data.get("construction", "standalone")
            lemma        = conj.lesson_data.get("lemma", "")
            surface_verb = conj.lesson_data.get("surface", conj.label)

            for (
                expected_construction,
                expected_lemma,
                pattern_id,
                pattern,
                usage,
                contrast,
            ) in _GRAMMAR_PATTERNS:
                if construction != expected_construction:
                    continue
                if expected_lemma is not None and lemma != expected_lemma:
                    continue

                canonical_form = f"grammar:{pattern_id}"
                if canonical_form in seen_grammar:
                    continue
                seen_grammar.add(canonical_form)

                candidates.append(CandidateObject(
                    canonical_form=canonical_form,
                    surface_form=surface_verb,
                    type="grammar",
                    label=surface_verb,
                    lesson_data={
                        "pattern_id":   pattern_id,
                        "pattern":      pattern,
                        "usage":        usage,
                        "contrast":     contrast,
                        "verb_lemma":   lemma,
                        "surface_verb": surface_verb,
                    },
                    confidence=0.85,
                    relation_hints=[
                        RelationHint(
                            relation_type="instance_of",
                            target_canonical_form=conj.canonical_form,
                            target_type="conjugation",
                        )
                    ],
                ))

        return candidates

    # ------------------------------------------------------------------
    # Nuance
    # ------------------------------------------------------------------

    def _extract_nuance(
        self,
        conj_candidates: list[CandidateObject],
        tokens: list[Any],
        seen_nuance: set[str],
    ) -> list[CandidateObject]:
        """Emit nuance observations derived from conjugation results.

        Five nuance types:

          imperfect_aspect     — tense == "imperfect"
            The pretérito imperfeito signals ongoing, habitual, or background
            past action.  Confidence 0.78.

          subjunctive_mood     — mood == "subjunctive"
            The subjuntivo signals doubt, desire, emotion, or hypotheticals.
            Confidence 0.72.

          conditional_mood     — mood == "conditional"
            The condicional signals hypothesis, polite requests, or reported
            speech.  Confidence 0.78.

          reflexive_verb       — is_reflexive == True
            Verbos reflexivos use a reflexive pronoun (me/te/se/nos/vos).
            Confidence 0.82.

          personal_infinitive  — extracted from non-conjugated VerbForm=Inf tokens
            with Person set.  Unique to Portuguese: 'para eles fazerem',
            'ao chegarmos'.  Confidence 0.75.
        """
        candidates: list[CandidateObject] = []

        # -- Nuances derived from conjugation candidates ------------------------
        for conj in conj_candidates:
            tense        = conj.lesson_data.get("tense")
            mood         = conj.lesson_data.get("mood")
            is_reflexive = conj.lesson_data.get("is_reflexive", False)
            lemma        = conj.lesson_data.get("lemma", "")
            surface      = conj.lesson_data.get("surface", conj.label)

            if tense == "imperfect":
                cf = f"nuance:imperfect_aspect:{lemma}"
                if cf not in seen_nuance:
                    seen_nuance.add(cf)
                    candidates.append(CandidateObject(
                        canonical_form=cf,
                        surface_form=surface,
                        type="nuance",
                        label=surface,
                        lesson_data={
                            "nuance_type":    "imperfect_aspect",
                            "lemma":          lemma,
                            "surface":        surface,
                            "note": (
                                "The pretérito imperfeito describes an ongoing, habitual, "
                                "or background past action, or sets the scene in a narrative. "
                                "Contrast with the pretérito perfeito simples, which marks "
                                "a completed event with a definite endpoint."
                            ),
                            "contrast_tense": "pretérito perfeito simples",
                        },
                        confidence=0.78,
                        relation_hints=[
                            RelationHint(
                                relation_type="nuance_of",
                                target_canonical_form=conj.canonical_form,
                                target_type="conjugation",
                            )
                        ],
                    ))

            if mood == "subjunctive":
                cf = f"nuance:subjunctive_mood:{lemma}"
                if cf not in seen_nuance:
                    seen_nuance.add(cf)
                    candidates.append(CandidateObject(
                        canonical_form=cf,
                        surface_form=surface,
                        type="nuance",
                        label=surface,
                        lesson_data={
                            "nuance_type": "subjunctive_mood",
                            "lemma":       lemma,
                            "surface":     surface,
                            "note": (
                                "The subjuntivo expresses doubt, desire, emotion, or "
                                "hypothetical situations. It typically appears after "
                                "verbs of wanting, fearing, or doubting, and after "
                                "conjunctions such as 'para que', 'embora', 'ainda que', "
                                "and 'quando' (in future contexts)."
                            ),
                        },
                        confidence=0.72,
                        relation_hints=[
                            RelationHint(
                                relation_type="nuance_of",
                                target_canonical_form=conj.canonical_form,
                                target_type="conjugation",
                            )
                        ],
                    ))

            if mood == "conditional":
                cf = f"nuance:conditional_mood:{lemma}"
                if cf not in seen_nuance:
                    seen_nuance.add(cf)
                    candidates.append(CandidateObject(
                        canonical_form=cf,
                        surface_form=surface,
                        type="nuance",
                        label=surface,
                        lesson_data={
                            "nuance_type": "conditional_mood",
                            "lemma":       lemma,
                            "surface":     surface,
                            "note": (
                                "The condicional is used for hypothetical situations "
                                "('se tivesse tempo, estudaria'), polite requests "
                                "('poderia me ajudar?'), and reported speech "
                                "('ele disse que viria')."
                            ),
                        },
                        confidence=0.78,
                        relation_hints=[
                            RelationHint(
                                relation_type="nuance_of",
                                target_canonical_form=conj.canonical_form,
                                target_type="conjugation",
                            )
                        ],
                    ))

            if is_reflexive:
                cf = f"nuance:reflexive_verb:{lemma}"
                if cf not in seen_nuance:
                    seen_nuance.add(cf)
                    candidates.append(CandidateObject(
                        canonical_form=cf,
                        surface_form=surface,
                        type="nuance",
                        label=surface,
                        lesson_data={
                            "nuance_type": "reflexive_verb",
                            "lemma":       lemma,
                            "surface":     surface,
                            "note": (
                                "This verb uses a reflexive pronoun "
                                "(me / te / se / nos / vos / se). The pronoun may signal "
                                "a reflexive action (the subject acts on itself), a "
                                "reciprocal action (two subjects act on each other), "
                                "or is intrinsic to the meaning of the verb "
                                "(e.g. lembrar-se de, queixar-se de)."
                            ),
                        },
                        confidence=0.82,
                        relation_hints=[
                            RelationHint(
                                relation_type="nuance_of",
                                target_canonical_form=conj.canonical_form,
                                target_type="conjugation",
                            )
                        ],
                    ))

        # -- Personal infinitive — scanned directly from tokens ----------------
        # VerbForm=Inf + Person set → personal (inflected) infinitive.
        # Unique to Portuguese and Galician among major Romance languages.
        for tok in tokens:
            if tok.pos_ not in {"VERB", "AUX"}:
                continue
            verb_form = _morph_first(tok, "VerbForm")
            if verb_form != "Inf":
                continue
            person = _morph_first(tok, "Person")
            if person is None:
                continue  # impersonal infinitive — skip

            lemma = tok.lemma_.lower()
            cf = f"nuance:personal_infinitive:{lemma}"
            if cf in seen_nuance:
                continue
            seen_nuance.add(cf)

            candidates.append(CandidateObject(
                canonical_form=cf,
                surface_form=tok.text,
                type="nuance",
                label=tok.text,
                lesson_data={
                    "nuance_type": "personal_infinitive",
                    "lemma":       lemma,
                    "surface":     tok.text,
                    "note": (
                        "The infinitivo pessoal (personal/inflected infinitive) is unique "
                        "to Portuguese. It conjugates for person and number like a finite "
                        "verb but retains the infinitive meaning. It appears in "
                        "subordinate clauses with explicit subjects and after some "
                        "prepositions: 'para eles fazerem', 'ao chegarmos'."
                    ),
                },
                confidence=0.75,
                relation_hints=[
                    RelationHint(
                        relation_type="nuance_of",
                        target_canonical_form=lemma,
                        target_type="vocabulary",
                    )
                ],
            ))

        return candidates


# ── Module-level helpers (stateless) ─────────────────────────────────────────

def _detect_construction(tok: Any) -> str:
    """Annotate the periphrastic construction for a conjugated verb token.

    Returns one of:
        "standalone"         — simple finite verb, no known periphrasis
        "ser_copula"         — ser as copula
        "estar_copula"       — estar as copula or before gerund
        "ter_perfect"        — ter + past participle
        "ir_near_future"     — ir + infinitive
        "estar_progressive"  — estar + gerund
        "modal"              — modal AUX + infinitive
    """
    if tok.pos_ == "AUX":
        if tok.dep_ == "cop":
            lemma = tok.lemma_.lower()
            return "ser_copula" if lemma == "ser" else "estar_copula"
        if tok.dep_ in {"aux", "aux:pass"}:
            head_vf = _morph_first(tok.head, "VerbForm")
            if head_vf == "Part":
                return "ter_perfect"
            if head_vf == "Ger":
                return "estar_progressive"
            if head_vf == "Inf":
                lemma = tok.lemma_.lower()
                return "ir_near_future" if lemma == "ir" else "modal"
    elif tok.pos_ == "VERB":
        lemma = tok.lemma_.lower()
        if lemma == "ir":
            for child in tok.children:
                if (
                    child.pos_ in {"VERB", "AUX"}
                    and child.dep_ in {"xcomp", "ccomp"}
                    and _morph_first(child, "VerbForm") == "Inf"
                ):
                    return "ir_near_future"
        if lemma == "estar":
            for child in tok.children:
                if (
                    child.pos_ in {"VERB", "AUX"}
                    and _morph_first(child, "VerbForm") == "Ger"
                ):
                    return "estar_progressive"
    return "standalone"


def _morph_first(tok: Any, feature: str) -> str | None:
    values = tok.morph.get(feature)
    return values[0] if values else None


def _paradigm_class(lemma: str) -> str:
    """Return the conjugation group of a Portuguese verb lemma.

    Three groups based on infinitive ending, matching Spanish convention:
      -ar  (1st group — most regular; e.g. falar, cantar, comprar)
      -er  (2nd group; e.g. comer, beber, vender)
      -ir  (3rd group; e.g. partir, abrir, sentir)
      irregular — known irregular verbs regardless of ending
    """
    if lemma in _IRREGULAR_VERBS:
        return "irregular"
    if lemma.endswith("ar"):
        return "-ar"
    if lemma.endswith("er"):
        return "-er"
    if lemma.endswith("ir"):
        return "-ir"
    return "irregular"


def _conj_canonical_form(lemma: str, feats: dict[str, str]) -> str:
    return (
        f"{lemma}"
        f":{feats.get('tense', 'unk')}"
        f":{feats.get('mood', 'unk')}"
        f":{feats.get('person', 'unk')}"
        f":{feats.get('number', 'unk')}"
    )


def _conj_is_complete(feats: dict[str, str]) -> bool:
    return all(
        feats.get(k) not in (None, "unknown")
        for k in ("tense", "mood", "person")
    )


def _conj_confidence_note(feats: dict[str, str], is_oov: bool) -> str | None:
    unknown = [
        k for k in ("tense", "mood", "person")
        if feats.get(k) in (None, "unknown")
    ]
    parts: list[str] = []
    if unknown:
        parts.append(f"morphology unavailable for: {', '.join(unknown)}")
    if is_oov:
        parts.append("word not found in model vocabulary")
    return "; ".join(parts) if parts else None


def _has_reflexive_clitic(tok: Any, tokens: list[Any]) -> bool:
    """True when *tok* has a reflexive pronoun as a syntactic child.

    Uses Reflex=Yes morphological feature — same approach as the French plugin.
    """
    return any(
        t.pos_ == "PRON"
        and t.head.i == tok.i
        and _morph_first(t, "Reflex") == "Yes"
        and t.dep_ not in {"nsubj", "nsubj:pass"}
        for t in tokens
    )


def _find_modifiers(noun: Any, tokens: list[Any]) -> list[Any]:
    """Return DET and ADJ tokens that modify *noun* via dep arcs or adjacency."""
    dep_based: list[Any] = [
        t for t in tokens
        if t.pos_ in {"DET", "ADJ"}
        and t.head.i == noun.i
        and t.i != noun.i
        and t.dep_ not in {"conj", "flat"}
    ]
    if dep_based:
        return dep_based

    adjacent: list[Any] = []
    for t in tokens:
        if t.pos_ not in {"DET", "ADJ"} or t.i == noun.i:
            continue
        if abs(t.i - noun.i) != 1:
            continue
        lo, hi = min(t.i, noun.i), max(t.i, noun.i)
        if any(
            tokens[k].is_sent_start or tokens[k].pos_ == "CCONJ"
            for k in range(lo + 1, hi)
        ):
            continue
        adjacent.append(t)
    return adjacent


def _agreement_confidence(
    gender_match: bool | None,
    number_match: bool | None,
) -> float:
    if gender_match is True and number_match is True:
        return 0.85
    if gender_match is True or number_match is True:
        return 0.72
    return 0.55


def _agreement_confidence_note(
    gender_match: bool | None,
    number_match: bool | None,
) -> str:
    if gender_match is True and number_match is True:
        return "gender and number both confirmed"
    if gender_match is True:
        return "gender confirmed; number unavailable"
    if number_match is True:
        return "number confirmed; gender unavailable"
    return "agreement inferred from adjacency — morphology incomplete"


def create_plugin() -> PortuguesePlugin:
    return PortuguesePlugin()
