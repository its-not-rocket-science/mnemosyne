"""Italian language plugin — spaCy ``it_core_news_sm``.

Registers as ``language_code = "it"``.

Read this alongside ``PLUGIN_AUTHOR_GUIDE.md`` and the Portuguese reference
implementation (``portuguese.py``) when building or extending this plugin.

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
  • paradigm_class: -are / -ere / -ire / irregular
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
results.  Covers: essere_copula, avere_perfect, essere_perfect,
andare_near_future, stare_progressive.

  lesson_data keys: pattern_id, pattern, usage, contrast, verb_lemma,
                    surface_verb

**Idiom** — ~30 common fixed Italian expressions detected by surface-form
token matching against a curated table.

  lesson_data keys: phrase, meaning, register

**Nuance** — aspectual and modal observations derived from conjugation results.
Covers: imperfect_aspect, subjunctive_mood, conditional_mood, reflexive_verb.

  lesson_data keys: nuance_type, lemma, surface, note, contrast_tense*

─────────────────────────────────────────────────────────────────────────────
KNOWN MODEL LIMITATIONS (it_core_news_sm)
─────────────────────────────────────────────────────────────────────────────

- ``it_core_news_sm`` is a small model trained on news text.  Subjunctive and
  conditional morphology is less reliable than indicative present/past.
- Enclitic pronouns (e.g. "parlarmene", "dammelo") are resolved into separate
  tokens by the spaCy Italian tokeniser.  The cliticised pronouns appear as
  PRON tokens and do not affect conjugation extraction.
- The conditional tense (condizionale) uses Mood=Cnd in Universal Dependencies;
  this plugin maps it to "conditional" in lesson_data.
- The imperfetto subjunctive (congiuntivo imperfetto) and past subjunctive
  (congiuntivo passato) share Mood=Sub but differ in tense.  Both are emitted
  as subjunctive nuance objects.
- Italian gender is largely predictable from noun suffixes (-o Masc, -a Fem)
  but exceptions abound ("il problema", "la mano").  Rely on model annotation.

─────────────────────────────────────────────────────────────────────────────
MULTILINGUAL ARCHITECTURE NOTES
─────────────────────────────────────────────────────────────────────────────

1. Italian passato prossimo uses either ``avere`` or ``essere`` as auxiliary,
   and the choice is lexically conditioned (transitive → avere; intransitive
   motion/change verbs → essere; all reflexives → essere).  Both are captured
   as grammar patterns with distinct ``pattern_id`` values.
2. ``stare + gerund`` is the Italian progressive (analogous to Portuguese
   ``estar + gerund`` and English ``be + -ing``).  European Spanish uses a
   similar construction.  ``stare + per + infinitive`` is the near-future
   periphrasis; this plugin extracts it as a grammar object but labels it
   ``stare_near_future`` to avoid conflating it with simple-future constructions.
3. Paradigm class convention: -are/-ere/-ire/irregular, matching the Italian
   grammar tradition and consistent with Portuguese (-ar/-er/-ir) and Spanish.
4. Reflexive detection uses model-agnostic ``Reflex=Yes`` morph feature.
"""
from __future__ import annotations

import logging
from functools import cached_property
from typing import Any

from backend.plugins.cefr_vocab import A1 as _CEFR_A1, A2 as _CEFR_A2, B1 as _CEFR_B1
from backend.core.vocab_index import get_cefr_level as _get_cefr_level
from backend.schemas.language import LanguageCapabilities, NuanceCapabilities
from backend.schemas.parse import (
    CandidateObject,
    CandidateSentenceResult,
    RelationHint,
)

logger = logging.getLogger(__name__)

_A1 = _CEFR_A1.get("it", frozenset())
_A2 = _CEFR_A2.get("it", frozenset())
_B1 = _CEFR_B1.get("it", frozenset())

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
    "essere", "avere", "stare", "andare", "fare", "dire", "sapere",
    "potere", "volere", "dovere", "venire", "uscire", "porre", "trarre",
    "bere", "cogliere", "scegliere", "tenere", "rimanere", "apparire",
    "morire", "salire", "sedere", "valere", "udire", "ire", "dare",
    "cogliere", "togliere", "sciogliere", "sporre", "piacere",
})

# ── Idiom table ────────────────────────────────────────────────────────────────
# Each entry: (token_tuple_lowercase, english_meaning, register)
# Sorted longest-first for greedy left-to-right matching.

_IDIOM_TABLE: tuple[tuple[tuple[str, ...], str, str], ...] = (
    # ── 4-word ────────────────────────────────────────────────────────────────
    (("di", "tanto", "in", "tanto"),      "from time to time",                "neutral"),
    (("a", "poco", "a", "poco"),           "little by little",                "neutral"),
    (("da", "un", "lato"),                 "on the one hand",                 "formal"),
    # ── 3-word ────────────────────────────────────────────────────────────────
    (("allo", "stesso", "tempo"),          "at the same time",                "neutral"),
    (("d'", "altra", "parte"),             "on the other hand",               "neutral"),
    (("invece", "di"),                     "instead of",                      "neutral"),
    (("a", "partire", "da"),               "starting from",                   "neutral"),
    (("in", "modo", "da"),                 "so as to / in order to",          "formal"),
    (("per", "quanto", "riguarda"),        "as far as … is concerned",        "formal"),
    (("nel", "senso", "che"),              "in the sense that",               "neutral"),
    (("in", "qualche", "modo"),            "in some way / somehow",           "neutral"),
    (("più", "o", "meno"),                 "more or less / approximately",    "neutral"),
    (("ogni", "tanto"),                    "every now and then",              "neutral"),
    (("a", "volte"),                       "sometimes / at times",            "neutral"),
    (("d'", "accordo"),                    "agreed / okay",                   "neutral"),
    # ── 2-word ────────────────────────────────────────────────────────────────
    (("per", "esempio"),                   "for example",                     "neutral"),
    (("per", "quanto"),                    "as much as / although",           "neutral"),
    (("per", "cui"),                       "therefore / which is why",        "neutral"),
    (("in", "realtà"),                     "in reality / actually",           "neutral"),
    (("almeno",),                          "at least",                        "neutral"),
    (("infatti",),                         "in fact / indeed",                "neutral"),
    (("tuttavia",),                        "however / nevertheless",          "formal"),
    (("eppure",),                          "and yet / nevertheless",          "neutral"),
    (("inoltre",),                         "furthermore / moreover",          "formal"),
    (("comunque",),                        "anyway / in any case",            "neutral"),
    (("quindi",),                          "therefore / so",                  "neutral"),
    (("però",),                            "but / however",                   "neutral"),
    (("anzi",),                            "on the contrary / rather",        "neutral"),
    (("purtroppo",),                       "unfortunately",                   "neutral"),
    (("di", "solito"),                     "usually / as a rule",             "neutral"),
    (("in", "genere"),                     "generally / in general",          "neutral"),
    (("al", "contrario"),                  "on the contrary",                 "neutral"),
    (("in", "seguito"),                    "afterwards / later on",           "neutral"),
    (("buona", "fortuna"),                 "good luck",                       "neutral"),
    (("grazie", "mille"),                  "thanks a lot / many thanks",      "neutral"),
)

# ── Grammar patterns ──────────────────────────────────────────────────────────
# (construction, required_lemma_or_None, pattern_id, pattern_label, usage, contrast)

_GRAMMAR_PATTERNS: tuple[tuple[str, str | None, str, str, str, str], ...] = (
    (
        "copula", "essere",
        "essere_copula",
        "essere + [noun / adjective]",
        "Links a subject to its identity, nationality, profession, or inherent quality: "
        "'Sono studentessa', 'È italiano', 'La casa è grande'. "
        "Unlike Spanish, Italian does not use stare for temporary states — essere covers "
        "both permanent and temporary descriptive states in most contexts.",
        "Use stare for progressive constructions ('sto leggendo') and in fixed "
        "idioms ('come stai?').  Stare is NOT a general alternative to essere for "
        "states — Italian uses essere where Spanish uses estar for temporary states.",
    ),
    (
        "perfect", "avere",
        "avere_perfect",
        "avere + [past participle]",
        "Forms the passato prossimo for transitive verbs: "
        "'ho mangiato' (I ate / I have eaten), 'ha visto il film'. "
        "The past participle agrees in gender and number with a preceding "
        "direct-object clitic (lo, la, li, le).",
        "Intransitive verbs of motion or change of state and all reflexive verbs "
        "use essere as the auxiliary: 'sono andato', 'si è alzata'.",
    ),
    (
        "perfect", "essere",
        "essere_perfect",
        "essere + [past participle]",
        "Forms the passato prossimo for intransitive verbs of motion or state "
        "change (andare, venire, uscire, nascere, morire, etc.) and all reflexive "
        "verbs: 'sono arrivato', 'si è svegliata'. "
        "The past participle agrees with the subject in gender and number.",
        "Transitive verbs use avere as the auxiliary: 'ho mangiato', 'ha visto'. "
        "Memorising which verbs take essere vs avere is one of the core challenges "
        "of Italian grammar.",
    ),
    (
        "stare_progressive", "stare",
        "stare_progressive",
        "stare + [gerund (-ando/-endo)]",
        "Expresses an action in progress at the moment of speaking: "
        "'sto studiando' (I am studying), 'stava dormendo' (he was sleeping). "
        "The gerund is invariable and attaches clitics as enclitic suffixes "
        "('standomi vicino', 'stavo parlandoti').",
        "Unlike Spanish 'estar + gerund', Italian 'stare + gerundo' is mostly "
        "restricted to immediate, ongoing actions.  For repeated or habitual "
        "actions in the present, the simple present ('studio ogni giorno') is used.",
    ),
    (
        "andare_near_future", "andare",
        "andare_near_future",
        "andare + [infinitive]",
        "Expresses an obligation or a future event with a sense of inevitability: "
        "'va detto che' (it should be said that), 'questo va considerato'. "
        "This construction is more restricted than its French/Spanish/Portuguese "
        "cognates — it is most natural with third-person impersonal usage or "
        "modal obligation, not as a general near-future periphrasis.",
        "Italian generally uses the simple future ('parlerò domani') or the "
        "present tense with a time adverb ('parto domani') for near-future meaning.",
    ),
)


# ── Plugin ─────────────────────────────────────────────────────────────────────

class ItalianPlugin:
    language_code = "it"
    display_name  = "Italian"
    direction     = "ltr"
    capabilities  = LanguageCapabilities(
        code="it",
        display_name="Italian",
        direction="ltr",
        script_family="latin",
        tokenization_mode="whitespace",
        morphology_depth="rich",
        lesson_modes_supported=["morphology", "vocabulary"],
        analysis_depth="full",
        segmentation_quality="medium",
        tokenization_quality="high",      # word tokenisation reliable; enclitics split
        morphology_quality="medium",      # small model; subjunctive/conditional less reliable
        syntax_support=True,
        idiom_detection=True,             # curated fixed-expression table (~30 entries)
        tts_lang_tag="it",
        transliteration_scheme=None,
        tense_pool=["present", "imperfect", "past", "future", "pluperfect"],
        mood_pool=["indicative", "subjunctive", "conditional", "imperative"],
        nuance_capabilities=NuanceCapabilities(
            idioms="partial",            # curated ~30-entry fixed-expression table
            phrase_families="partial",   # 15-family curated catalog; extractor wired
            literary_references="none",
            cultural_references="none",
            etymology="partial",         # 50-entry curated catalog; music/art/food terms well-covered
            formality_register="partial", # Lei/tu distinction; extractor wired
            grammar_nuance="partial",    # tense/mood/person/number drilling
            pronunciation_tts="partial", # browser TTS reliable for it
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
            return spacy.load("it_core_news_sm", disable=["ner"])
        except ImportError as exc:
            raise RuntimeError(
                "spaCy is not installed.  Run: pip install spacy"
            ) from exc
        except OSError as exc:
            raise RuntimeError(
                "spaCy model 'it_core_news_sm' not found. "
                "Run: python -m spacy download it_core_news_sm"
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
        candidates.extend(self._extract_nuance(conj_candidates, seen_nuance))

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
            cefr = _get_cefr_level("it", lemma) or ("A1" if lemma in _A1 else "A2" if lemma in _A2 else "B1" if lemma in _B1 else None)
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
        if lemma in _A1 or _get_cefr_level("it", lemma):
            return 0.90, None  # known word — suppress is_oov false-positive
        if lemma in _A2:
            return 0.88, None  # known A2 word
        if lemma in _B1:
            return 0.86, None  # known B1 word
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

        Italian-specific notes:
        - Definite articles undergo phonological changes before vowels and
          certain consonant clusters (il/lo/l'/la/i/gli/le), but spaCy
          normalises them all as DET tokens — no special handling needed.
        - Post-nominal adjectives are the default in Italian; some adjectives
          change meaning when pre-nominal (es. un certo problema / un problema
          certo).  The dep-arc approach handles both positions.
        - Articulated prepositions (del, della, dello, nel, etc.) are tagged ADP
          in Universal Dependencies and are excluded by _SKIP_POS.
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

        lower_texts    = [t.text.lower() for t in tokens]
        n              = len(lower_texts)
        seen_idioms:    set[str] = set()
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
        seen_nuance: set[str],
    ) -> list[CandidateObject]:
        """Emit nuance observations derived from conjugation results.

        Four nuance types:

          imperfect_aspect   — tense == "imperfect"
            The imperfetto describes an ongoing, habitual, or background past
            action.  Confidence 0.78.

          subjunctive_mood   — mood == "subjunctive"
            The congiuntivo expresses doubt, desire, emotion, or hypotheticals.
            Italian uses the subjunctive more widely than French or Spanish.
            Confidence 0.72.

          conditional_mood   — mood == "conditional"
            The condizionale expresses hypotheticals, polite requests, and
            reported speech.  Confidence 0.78.

          reflexive_verb     — is_reflexive == True
            Verbi riflessivi use a reflexive pronoun (mi/ti/si/ci/vi).
            Confidence 0.82.
        """
        candidates: list[CandidateObject] = []

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
                                "The imperfetto describes an ongoing, habitual, or "
                                "background action in the past, or frames a scene "
                                "('Era una bella giornata'). Contrast with the passato "
                                "prossimo, which marks a completed event with a definite "
                                "endpoint ('Ho mangiato alle otto')."
                            ),
                            "contrast_tense": "passato prossimo",
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
                                "The congiuntivo expresses doubt, desire, emotion, "
                                "or hypothetical situations. Italian uses the "
                                "subjunctive more widely than other Romance languages, "
                                "including after 'benché', 'sebbene', 'affinché', "
                                "'prima che', 'nonostante', and after verbs of "
                                "thinking or believing: 'credo che sia vero'."
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
                                "The condizionale expresses hypothetical situations "
                                "('Se avessi tempo, studierei'), polite requests "
                                "('Potrei avere il conto?'), and reported speech "
                                "('Ha detto che sarebbe venuto'). The condizionale "
                                "passato is often used where English uses 'would have'."
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
                                "(mi / ti / si / ci / vi / si). The pronoun "
                                "may signal a reflexive action (the subject acts "
                                "on itself: 'mi lavo'), a reciprocal action "
                                "('ci amiamo'), or is inherent to the verb's meaning "
                                "('mi ricordo', 'si sbaglia'). "
                                "All reflexive verbs form the passato prossimo "
                                "with essere, not avere."
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

        return candidates


# ── Module-level helpers (stateless) ─────────────────────────────────────────

def _detect_construction(tok: Any) -> str:
    """Annotate the periphrastic construction for a conjugated verb token.

    Returns one of:
        "standalone"          — simple finite verb
        "copula"              — essere as copula
        "perfect"             — avere/essere + past participle (passato prossimo)
        "stare_progressive"   — stare + gerund
        "andare_near_future"  — andare + infinitive (modal/obligation)
        "modal"               — modal AUX + infinitive
    """
    if tok.pos_ == "AUX":
        if tok.dep_ == "cop":
            return "copula"
        if tok.dep_ in {"aux", "aux:pass"}:
            head_vf = _morph_first(tok.head, "VerbForm")
            if head_vf == "Part":
                return "perfect"
            if head_vf == "Ger":
                return "stare_progressive"
            if head_vf == "Inf":
                lemma = tok.lemma_.lower()
                return "andare_near_future" if lemma == "andare" else "modal"
    elif tok.pos_ == "VERB":
        lemma = tok.lemma_.lower()
        if lemma == "stare":
            for child in tok.children:
                if (
                    child.pos_ in {"VERB", "AUX"}
                    and _morph_first(child, "VerbForm") == "Ger"
                ):
                    return "stare_progressive"
        if lemma == "andare":
            for child in tok.children:
                if (
                    child.pos_ in {"VERB", "AUX"}
                    and child.dep_ in {"xcomp", "ccomp"}
                    and _morph_first(child, "VerbForm") == "Inf"
                ):
                    return "andare_near_future"
    return "standalone"


def _morph_first(tok: Any, feature: str) -> str | None:
    values = tok.morph.get(feature)
    return values[0] if values else None


def _paradigm_class(lemma: str) -> str:
    """Return the conjugation group of an Italian verb lemma.

    Three groups:
      -are   (1st group; e.g. parlare, mangiare, studiare)
      -ere   (2nd group; e.g. vedere, credere, prendere)
      -ire   (3rd group; e.g. dormire, partire, finire)
      irregular — known irregular verbs regardless of ending
    """
    if lemma in _IRREGULAR_VERBS:
        return "irregular"
    if lemma.endswith("are"):
        return "-are"
    if lemma.endswith("ere"):
        return "-ere"
    if lemma.endswith("ire"):
        return "-ire"
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
    return any(
        t.pos_ == "PRON"
        and t.head.i == tok.i
        and _morph_first(t, "Reflex") == "Yes"
        and t.dep_ not in {"nsubj", "nsubj:pass"}
        for t in tokens
    )


def _find_modifiers(noun: Any, tokens: list[Any]) -> list[Any]:
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


def create_plugin() -> ItalianPlugin:
    return ItalianPlugin()
