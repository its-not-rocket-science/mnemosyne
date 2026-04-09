"""Spanish language plugin — spaCy ``es_core_news_sm``.

Registers as ``language_code = "es"``.

Extraction model
────────────────
Three categories are extracted from each sentence:

**Vocabulary** — open-class words (NOUN, ADJ, ADV, VERB/AUX in non-finite
forms).  Finite VERB and AUX tokens are *excluded* from vocabulary because
they are already represented by a conjugation object; emitting the same
lemma in both categories would create redundant learning items.
Cross-tracking between conjugation and vocabulary also prevents the same
lemma from appearing twice within a single sentence (e.g. "voy a ir" —
the infinitive "ir" is suppressed once "ir" has been emitted as a
conjugation entry for "voy").
Lemmas that contain a space are silently dropped; they arise from enclitic
fusion tokens that the model fails to split (e.g. "hacerlo" → "hacer él").

**Conjugation** — finite VERB and AUX tokens, each annotated with:
  - morphological features (tense, mood, person, number)
  - ``construction`` (standalone / progressive / perfect / passive /
    near_future / modal / copula)
  - ``is_reflexive`` (True when a reflexive or pronominal clitic is a
    non-subject dependent of the verb)
  - ``morph_complete`` (True when tense, mood, and person are all known)
  - optional ``confidence_note`` explaining any score penalty

**Agreement** — DET+NOUN and ADJ+NOUN pairs where at least one
morphological feature (gender or number) can be positively confirmed to
match.  Pairs with a *confirmed mismatch* on any available feature are
silently dropped; they indicate a model error rather than a valid teaching
object.

Known limitations
─────────────────
- ``es_core_news_sm`` is a small model (~12 MB).  Morphology is often
  incomplete for irregular verbs, clitic clusters, enclitic pronouns,
  and archaic or literary forms.  Nearly every surface token is marked
  out-of-vocabulary (``is_oov=True``) by this model.
- A verb at the start of a sentence is sometimes mis-tagged as PROPN.
  We do not re-tag; the sentence is silently under-extracted.
- Subjunctive detection is unreliable for present-subjunctive forms that
  are homographic with indicative forms (e.g. "hable").
- Reflexive detection relies on the dependency parse.  Parse errors
  produce missed or spurious results.
- Confidence scores are heuristic proxies, not calibrated probabilities.
- ``_nlp`` is called once per text via ``analyze_text``; ``split_sentences``
  and ``analyze_sentence`` are kept for direct use in tests and tooling.
"""
from __future__ import annotations

import logging
from functools import cached_property
from typing import Any

from backend.schemas.parse import (
    CandidateObject,
    CandidateSentenceResult,
    LearnableObject,
    RelationHint,
)

logger = logging.getLogger(__name__)

# ── POS filter ────────────────────────────────────────────────────────────────

# Universal-Dependencies POS tags excluded from vocabulary extraction.
# PRON is excluded because reflexive/clitic pronouns ("me", "te", "se", "nos")
# lemmatise to misleading forms (e.g. "me" → "yo") and represent a closed
# class better taught as part of the verb construction they modify.
_SKIP_POS = frozenset(
    {"DET", "ADP", "CCONJ", "SCONJ", "CONJ", "PUNCT", "SPACE",
     "X", "SYM", "NUM", "PRON"}
)

# VerbForm feature values that classify a VERB/AUX token as non-finite.
# Non-finite forms go to vocabulary; finite forms go to conjugation only.
_NON_FINITE_FORMS = frozenset({"Inf", "Part", "Ger"})

# Spanish reflexive/clitic pronoun surface forms.
_REFLEXIVE_CLITICS = frozenset({"me", "te", "se", "nos", "os"})

# ── display maps ──────────────────────────────────────────────────────────────

_TENSE_DISPLAY: dict[str, str] = {
    "Pres": "present",
    "Past": "preterite",
    "Imp":  "imperfect",
    "Fut":  "future",
    "Cnd":  "conditional",
}

_MOOD_DISPLAY: dict[str, str] = {
    "Ind": "indicative",
    "Sub": "subjunctive",
    "Imp": "imperative",
}


# ── plugin ────────────────────────────────────────────────────────────────────

class SpanishPlugin:
    language_code = "es"
    display_name  = "Spanish"
    direction     = "ltr"

    def __init__(self) -> None:
        self.lesson_store: dict[str, LearnableObject] = {}

    # ------------------------------------------------------------------
    # Model — lazy, loaded at most once per process via cached_property
    # ------------------------------------------------------------------

    @cached_property
    def _nlp(self) -> Any:
        try:
            import spacy  # noqa: PLC0415
            return spacy.load("es_core_news_sm", disable=["ner"])
        except ImportError as exc:
            raise RuntimeError(
                "spaCy is not installed.  Run: pip install spacy"
            ) from exc
        except OSError as exc:
            raise RuntimeError(
                "spaCy model 'es_core_news_sm' not found. "
                "Run: python -m spacy download es_core_news_sm"
            ) from exc

    # ------------------------------------------------------------------
    # LanguagePlugin protocol
    # ------------------------------------------------------------------

    def analyze_text(self, text: str) -> list[CandidateSentenceResult]:
        """Parse full text in a single spaCy call; return one result per sentence."""
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

    def _analyze_tokens(self, sentence: str, tokens: list[Any]) -> CandidateSentenceResult:
        # seen_vocab is shared: conjugation populates it with verb lemmas so
        # that the same lemma is not also emitted as a vocabulary item.
        seen_vocab: set[str] = set()
        seen_conj:  set[str] = set()

        candidates: list[CandidateObject] = []
        # Conjugation must run first to pre-populate seen_vocab before
        # vocabulary extraction consults it.
        candidates.extend(self._extract_conjugations(tokens, seen_conj, seen_vocab))
        candidates.extend(self._extract_vocabulary(tokens, seen_vocab))
        candidates.extend(self._extract_agreements(tokens))

        return CandidateSentenceResult(text=sentence, candidates=candidates)

    def get_lesson(self, object_id: str) -> LearnableObject | None:
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

            # Finite VERB/AUX tokens are covered exclusively by conjugation
            # extraction; including them here as well would create duplicate
            # learning items for the same lemma.
            if tok.pos_ in {"VERB", "AUX"} and verb_form not in _NON_FINITE_FORMS:
                continue

            lemma = tok.lemma_.lower()

            # Enclitic fusion: the model sometimes cannot split clitics from
            # their host verb, yielding multi-word lemmas like "hacer él".
            # These are model artifacts, not learnable vocabulary.
            if " " in lemma:
                continue

            if len(lemma) < 2 or lemma in seen:
                continue
            seen.add(lemma)

            confidence, confidence_note = self._vocab_confidence(tok)
            data: dict[str, Any] = {"lemma": lemma, "pos": tok.pos_}

            # Record the non-finite form type for VERB/AUX vocabulary entries
            # so the frontend can label them as "infinitive", "gerund", etc.
            if tok.pos_ in {"VERB", "AUX"} and verb_form:
                data["verb_form"] = verb_form

            if confidence_note is not None:
                data["confidence_note"] = confidence_note

            candidates.append(CandidateObject(
                canonical_form=lemma,
                type="vocabulary",
                label=tok.text,
                lesson_data=data,
                confidence=confidence,
            ))
        return candidates

    def _vocab_confidence(self, tok: Any) -> tuple[float, str | None]:
        if tok.pos_ == "PROPN":
            return 0.60, "proper noun — may not represent general vocabulary"
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
                continue  # infinitives, participles, gerunds → vocabulary

            lemma = tok.lemma_.lower()

            # Skip enclitic-fusion lemmas (contain a space, e.g. "hacer él").
            if " " in lemma:
                continue

            feats = self._verb_morph(tok)
            canonical_form = _conj_canonical_form(lemma, feats)
            if canonical_form in seen_conj:
                continue
            seen_conj.add(canonical_form)
            # Prevent the same lemma from also appearing as a vocabulary item
            # within this sentence (e.g. suppresses the infinitive "ir" after
            # a conjugation entry has been generated for "voy").
            seen_vocab.add(lemma)

            construction    = _detect_construction(tok)
            is_reflexive    = _has_reflexive_clitic(tok, tokens)
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
                "construction":   construction,
                "is_reflexive":   is_reflexive,
            }
            if "verb_form" in feats:
                lesson["verb_form"] = feats["verb_form"]
            if confidence_note is not None:
                lesson["confidence_note"] = confidence_note

            candidates.append(CandidateObject(
                canonical_form=canonical_form,
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
            "tense":  (
                _TENSE_DISPLAY.get(tense_raw or "", "")
                or _fallback_tense(tok)
                or "unknown"
            ),
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
        base = 0.55 + known * 0.10
        if tok.is_oov:
            base -= 0.10
        return round(min(base, 0.85), 2)

    # ------------------------------------------------------------------
    # Agreement
    # ------------------------------------------------------------------

    def _extract_agreements(self, tokens: list[Any]) -> list[CandidateObject]:
        """Find DET+NOUN and ADJ+NOUN gender/number agreement pairs.

        Emission rules:
        - At least one morphological feature (gender or number) must be
          *positively confirmed* to match (value is True, not None).
        - A pair with a *confirmed mismatch* on any available feature is
          silently dropped; it indicates a model parse error rather than a
          valid grammatical pattern worth teaching.
        - Primary signal: spaCy dependency arcs (dep_ in {det, amod}).
        - Fallback: single-position adjacency, skipping pairs separated by a
          CCONJ (coordination) to avoid spurious pairs like "inglés y español".
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

                # Need at least one positive confirmation.
                if gender_match is None and number_match is None:
                    continue
                # Drop confirmed mismatches — model error, not a teaching object.
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


# ── module-level helpers (stateless) ─────────────────────────────────────────

def _morph_first(tok: Any, feature: str) -> str | None:
    """Return the first value for a morph feature, or None if absent."""
    values = tok.morph.get(feature)
    return values[0] if values else None


def _conj_canonical_form(lemma: str, feats: dict[str, str]) -> str:
    """Stable conjugation canonical_form: lemma + the four morphological axes."""
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
    """Human-readable rationale for conjugation confidence.  None when nominal."""
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


def _detect_construction(tok: Any) -> str:
    """Annotate the periphrastic construction for a conjugated verb token.

    Returns one of:
        "standalone"   — simple finite verb, not part of a periphrasis
        "progressive"  — estar + gerund  (estoy comiendo)
        "perfect"      — haber + participle  (he comido)
        "passive"      — ser/estar + participle  (fue escrito)
        "near_future"  — ir a + infinitive  (voy a estudiar)
        "modal"        — modal AUX + infinitive  (debo estudiar)
        "copula"       — ser/estar as copula  (soy médico)
    """
    if tok.pos_ != "AUX":
        return "standalone"
    if tok.dep_ == "cop":
        return "copula"
    if tok.dep_ == "ROOT":
        # AUX as sentence root with no accompanying VERB.
        return "standalone"
    if tok.dep_ == "aux":
        head_vf = _morph_first(tok.head, "VerbForm")
        if head_vf == "Ger":
            return "progressive"
        if head_vf == "Part":
            return "perfect" if tok.lemma_.lower() == "haber" else "passive"
        if head_vf == "Inf":
            return "near_future" if tok.lemma_.lower() == "ir" else "modal"
    return "standalone"


def _has_reflexive_clitic(tok: Any, tokens: list[Any]) -> bool:
    """True when *tok* has a reflexive or pronominal clitic as a dependent.

    Covers proclitic pronouns ("me levanto", "se llama") via dependency
    arcs where the PRON's head is the verb.  The subject relation (nsubj)
    is excluded because a subject pronoun like "yo" or "ella" is not a
    clitic even when it happens to be in _REFLEXIVE_CLITICS.
    """
    return any(
        t.pos_ == "PRON"
        and t.head.i == tok.i
        and t.text.lower() in _REFLEXIVE_CLITICS
        and t.dep_ not in {"nsubj", "nsubj:pass"}
        for t in tokens
    )


def _fallback_tense(tok: Any) -> str | None:
    """Heuristic tense from suffix when the model's morphology is empty."""
    w = tok.text.lower()
    if w.endswith(("aba", "abas", "\u00e1bamos", "aban")):
        return "imperfect"
    if w.endswith(("\u00eda", "\u00edas", "\u00edamos", "\u00edan")):
        return "imperfect"
    if w.endswith(("r\u00e9", "r\u00e1s", "r\u00e1", "remos", "r\u00e9is", "r\u00e1n")):
        return "future"
    if w.endswith(("r\u00eda", "r\u00edas", "r\u00edamos", "r\u00edan")):
        return "conditional"
    return None


def _find_modifiers(noun: Any, tokens: list[Any]) -> list[Any]:
    """Return DET and ADJ tokens that modify *noun*.

    Primary: spaCy dependency arcs (head == noun and dep not in coordinating
    relations).  Coordinated elements (dep_=conj or flat) are excluded because
    spaCy sometimes attaches a conjoined ADJ to the head noun of the other
    conjunct, which would create spurious agreement objects.

    Fallback: immediate adjacency (distance == 1), skipping pairs that have
    a CCONJ between them to avoid "inglés y español" false pairs.
    """
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


def create_plugin() -> SpanishPlugin:
    return SpanishPlugin()
