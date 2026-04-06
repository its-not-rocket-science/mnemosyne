"""Spanish language plugin — spaCy ``es_core_news_sm``.

Registers as ``language_code = "es"``, replacing the regex-based MVP stub.

Known limitations
-----------------
- *es_core_news_sm* is a small model (~12 MB).  Morphology is often
  incomplete for irregular verbs, clitic clusters (se lo doy), enclitic
  pronouns (dámelo), and archaic or literary forms.
- Sentence segmentation works best on well-formed prose.  Dialogue,
  social-media text, and mid-sentence line breaks may produce
  over-/under-split results.
- Confidence scores are heuristic proxies, not calibrated probabilities.
- Reflexive and pronominal verbs are not yet decomposed; the whole surface
  form is treated as a single conjugation.
- Subjunctive detection is unreliable for present subjunctive forms that
  are homographic with indicative forms (e.g. "hable").
- The agreement extractor relies on the dependency parse; parsing errors
  will produce missed or spurious pairs.
- ``_nlp`` is called twice per text when the route calls
  ``split_sentences`` then ``analyze_sentence`` for each result.  This is
  a consequence of the current two-method protocol; acceptable at MVP scale.
"""
from __future__ import annotations

import logging
from functools import cached_property
from typing import Any

from backend.schemas.parse import LearnableObject, SentenceResult

logger = logging.getLogger(__name__)

# Universal-Dependencies POS tags that carry no learnable content for L2 learners.
_SKIP_POS = frozenset(
    {"DET", "ADP", "CCONJ", "SCONJ", "CONJ", "PUNCT", "SPACE", "X", "SYM", "NUM"}
)

# VerbForm values handled as vocabulary entries, not conjugation exercises.
_NON_FINITE_FORMS = frozenset({"Inf", "Part", "Ger"})

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


class SpanishPlugin:
    language_code = "es"
    display_name  = "Spanish"
    direction     = "ltr"

    def __init__(self) -> None:
        self._lesson_store: dict[str, LearnableObject] = {}

    # ------------------------------------------------------------------
    # Model — lazy, loaded at most once per process via cached_property
    # ------------------------------------------------------------------

    @cached_property
    def _nlp(self) -> Any:
        try:
            import spacy  # noqa: PLC0415 (local import is intentional)
            return spacy.load("es_core_news_sm", disable=["ner"])
        except ImportError as exc:
            raise RuntimeError("spaCy is not installed.  Run: pip install spacy") from exc
        except OSError as exc:
            raise RuntimeError(
                "spaCy model 'es_core_news_sm' not found. "
                "Run: python -m spacy download es_core_news_sm"
            ) from exc

    # ------------------------------------------------------------------
    # LanguagePlugin protocol
    # ------------------------------------------------------------------

    def split_sentences(self, text: str) -> list[str]:
        doc = self._nlp(text.strip())
        return [s.text.strip() for s in doc.sents if s.text.strip()]

    def analyze_sentence(self, sentence: str) -> SentenceResult:
        doc = self._nlp(sentence)
        tokens = list(doc)

        seen_vocab: set[str] = set()
        seen_conj:  set[str] = set()

        objects: list[LearnableObject] = []
        objects.extend(self._extract_vocabulary(tokens, seen_vocab))
        objects.extend(self._extract_conjugations(tokens, seen_conj))
        objects.extend(self._extract_agreements(tokens))

        for obj in objects:
            self._lesson_store[obj.id] = obj

        return SentenceResult(text=sentence, learnable_objects=objects)

    def get_lesson(self, object_id: str) -> LearnableObject | None:
        return self._lesson_store.get(object_id)

    # ------------------------------------------------------------------
    # Vocabulary
    # ------------------------------------------------------------------

    def _extract_vocabulary(
        self,
        tokens: list[Any],
        seen: set[str],
    ) -> list[LearnableObject]:
        objects: list[LearnableObject] = []
        for tok in tokens:
            if tok.pos_ in _SKIP_POS or tok.is_punct or tok.is_space:
                continue
            lemma = tok.lemma_.lower()
            if len(lemma) < 2 or lemma in seen:
                continue
            seen.add(lemma)

            confidence, note = self._vocab_confidence(tok)
            data: dict[str, Any] = {"lemma": lemma, "pos": tok.pos_}
            if note:
                data["note"] = note

            objects.append(LearnableObject(
                id=f"es:vocab:{lemma}",
                type="vocabulary",
                label=tok.text,
                lesson_data=data,
                confidence=confidence,
            ))
        return objects

    def _vocab_confidence(self, tok: Any) -> tuple[float, str | None]:
        if tok.pos_ == "PROPN":
            return 0.60, "proper noun — may not be general vocabulary"
        if tok.is_oov:
            return 0.50, "out-of-vocabulary for this model"
        return 0.85, None

    # ------------------------------------------------------------------
    # Conjugation
    # ------------------------------------------------------------------

    def _extract_conjugations(
        self,
        tokens: list[Any],
        seen: set[str],
    ) -> list[LearnableObject]:
        objects: list[LearnableObject] = []
        for tok in tokens:
            if tok.pos_ not in {"VERB", "AUX"}:
                continue
            verb_form = _morph_first(tok, "VerbForm")
            if verb_form in _NON_FINITE_FORMS:
                continue  # infinitives, participles, gerunds → vocabulary

            feats = self._verb_morph(tok)
            oid = _conj_id(tok.lemma_.lower(), feats)
            if oid in seen:
                continue
            seen.add(oid)

            objects.append(LearnableObject(
                id=oid,
                type="conjugation",
                label=tok.text,
                lesson_data={
                    "lemma":          tok.lemma_.lower(),
                    "surface":        tok.text,
                    "tense":          feats["tense"],
                    "mood":           feats["mood"],
                    "person":         feats["person"],
                    "number":         feats["number"],
                    "morph_complete": _conj_is_complete(feats),
                    **({"verb_form": feats["verb_form"]} if "verb_form" in feats else {}),
                },
                confidence=self._conj_confidence(tok, feats),
            ))
        return objects

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

    def _extract_agreements(self, tokens: list[Any]) -> list[LearnableObject]:
        """Find DET+NOUN and ADJ+NOUN gender/number agreement pairs.

        Primary signal: spaCy dependency parse (det, amod arcs into the noun).
        Fallback: adjacency within one position for when the parse is wrong.
        Only emits objects when at least one feature (gender or number) can
        be compared.
        """
        objects: list[LearnableObject] = []
        seen_pairs: set[tuple[str, str, str]] = set()

        nouns = [t for t in tokens if t.pos_ == "NOUN"]
        for noun in nouns:
            noun_gender = _morph_first(noun, "Gender")
            noun_number = _morph_first(noun, "Number")
            if not noun_gender and not noun_number:
                continue

            modifiers = _find_modifiers(noun, tokens)
            for cand in modifiers:
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

                pair_key = (cand.pos_, cand.lemma_.lower(), noun.lemma_.lower())
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                # Order label by surface position
                label = (
                    f"{cand.text} {noun.text}"
                    if cand.i < noun.i
                    else f"{noun.text} {cand.text}"
                )
                oid = f"es:agreement:{cand.pos_.lower()}:{cand.lemma_.lower()}_{noun.lemma_.lower()}"

                objects.append(LearnableObject(
                    id=oid,
                    type="agreement",
                    label=label,
                    lesson_data={
                        "modifier":     cand.text,
                        "modifier_pos": cand.pos_,
                        "noun":         noun.text,
                        "gender":       noun_gender or "unknown",
                        "number":       noun_number or "unknown",
                        "gender_match": gender_match,
                        "number_match": number_match,
                    },
                    confidence=_agreement_confidence(gender_match, number_match),
                ))
        return objects


# ------------------------------------------------------------------
# Module-level helpers (stateless, no self)
# ------------------------------------------------------------------

def _morph_first(tok: Any, feature: str) -> str | None:
    """Return the first value for a morph feature, or None if absent."""
    values = tok.morph.get(feature)
    return values[0] if values else None


def _conj_id(lemma: str, feats: dict[str, str]) -> str:
    """Stable conjugation ID: lemma + the four morphological axes."""
    return (
        f"es:conj:{lemma}"
        f":{feats.get('tense', 'unk')}"
        f":{feats.get('mood', 'unk')}"
        f":{feats.get('person', 'unk')}"
        f":{feats.get('number', 'unk')}"
    )


def _conj_is_complete(feats: dict[str, str]) -> bool:
    return all(feats.get(k) not in (None, "unknown") for k in ("tense", "mood", "person"))


def _fallback_tense(tok: Any) -> str | None:
    """Heuristic tense from suffix when the model's morphology is empty."""
    w = tok.text.lower()
    if w.endswith(("aba", "abas", "ábamos", "aban")):
        return "imperfect"
    if w.endswith(("ía", "ías", "íamos", "ían")):
        return "imperfect"
    if w.endswith(("ré", "rás", "rá", "remos", "réis", "rán")):
        return "future"
    if w.endswith(("ría", "rías", "ríamos", "rían")):
        return "conditional"
    return None


def _find_modifiers(noun: Any, tokens: list[Any]) -> list[Any]:
    """Return DET and ADJ tokens that modify *noun*.

    First tries dependency arcs (dep_ in {det, amod}), then falls back
    to single-position adjacency so that parsing errors don't silently
    drop all agreement data.
    """
    dep_based: list[Any] = [
        t for t in tokens
        if t.pos_ in {"DET", "ADJ"}
        and t.head.i == noun.i
        and t.i != noun.i
    ]
    if dep_based:
        return dep_based

    # Adjacency fallback: up to 2 positions away, same clause (no PUNCT between)
    adjacent: list[Any] = []
    for t in tokens:
        if t.pos_ not in {"DET", "ADJ"} or t.i == noun.i:
            continue
        distance = abs(t.i - noun.i)
        if distance > 2:
            continue
        # Skip if a sentence-boundary punctuation sits between them
        lo, hi = min(t.i, noun.i), max(t.i, noun.i)
        if any(tokens[k].is_sent_start for k in range(lo + 1, hi)):
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


def create_plugin() -> SpanishPlugin:
    return SpanishPlugin()
