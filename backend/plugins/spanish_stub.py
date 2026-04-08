"""Stub Spanish plugin (pure-Python, no spaCy dependency).

Uses regex to split sentences and simple heuristics to tag tokens as
vocabulary, conjugation, or agreement candidates.  Suitable as a
lightweight test double and reference implementation.

Deliberately has no ``create_plugin()`` factory so the plugin loader
does not register it — the real ``spanish.py`` (loaded first
alphabetically) takes the "es" slot in the registry.  Import
``SpanishStubPlugin`` directly in tests.
"""
from __future__ import annotations

import re

from backend.parsing.plugin_interface import Token
from backend.schemas.parse import LearnableObject, SentenceResult

# ---------------------------------------------------------------------------
# Regex helpers
# ---------------------------------------------------------------------------

_SENTENCE_RE = re.compile(r"[^.!?¡¿]+[.!?]?")
_WORD_RE = re.compile(r"[A-Za-záéíóúüñÁÉÍÓÚÜÑ]+")

# Common Spanish verb endings ordered longest → shortest so the first match
# consumes as much of the suffix as possible.
_VERB_ENDINGS = (
    "aron", "eron", "ieron",
    "aban", "ían",
    "aré", "arás", "ará", "aremos", "aréis", "arán",
    "eré", "erás", "erá", "eremos", "eréis", "erán",
    "iré", "irás", "irá", "iremos", "iréis", "irán",
    "ando", "iendo",
    "ado", "ido",
    "ar", "er", "ir",
    "as", "es",
    "amos", "emos", "imos",
    "áis", "éis", "ís",
    "an", "en",
    "ó", "é",
    "a", "e",
    "o",
)

# Adjective/determiner endings that suggest gender–number marking.
_ADJ_ENDINGS = ("os", "as", "o", "a")

# Minimum stem length to avoid tagging short words purely by suffix.
_MIN_STEM = 3


def _stem(word: str, endings: tuple[str, ...]) -> str | None:
    """Return the stem if *word* ends with one of *endings*, else None."""
    lower = word.lower()
    for ending in endings:
        if lower.endswith(ending) and len(lower) - len(ending) >= _MIN_STEM:
            return lower[: len(lower) - len(ending)]
    return None


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------


class SpanishStubPlugin:
    language_code = "es"
    display_name = "Spanish (stub)"
    direction = "ltr"

    def __init__(self) -> None:
        self._lesson_store: dict[str, LearnableObject] = {}

    # ------------------------------------------------------------------
    # LanguagePlugin protocol
    # ------------------------------------------------------------------

    def split_sentences(self, text: str) -> list[str]:
        return [
            m.group(0).strip()
            for m in _SENTENCE_RE.finditer(text)
            if m.group(0).strip()
        ]

    def analyze_sentence(self, sentence: str) -> SentenceResult:
        tokens = self._tokenize(sentence)
        objects = self._extract(tokens)
        for obj in objects:
            self._lesson_store[obj.id] = obj
        return SentenceResult(text=sentence, learnable_objects=objects)

    def get_lesson(self, object_id: str) -> LearnableObject | None:
        return self._lesson_store.get(object_id)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _tokenize(self, sentence: str) -> list[Token]:
        tokens: list[Token] = []
        for word in _WORD_RE.findall(sentence):
            lower = word.lower()
            morph: dict[str, str] = {}

            verb_stem = _stem(word, _VERB_ENDINGS)
            adj_stem = _stem(word, _ADJ_ENDINGS)

            if verb_stem is not None:
                pos = "VERB"
                morph["Stem"] = verb_stem
            elif adj_stem is not None:
                pos = "ADJ"
                morph["Stem"] = adj_stem
            else:
                pos = "NOUN"

            tokens.append(Token(text=word, lemma=lower, pos=pos, morph=morph))
        return tokens

    def _extract(self, tokens: list[Token]) -> list[LearnableObject]:
        seen: set[str] = set()
        objects: list[LearnableObject] = []

        for i, token in enumerate(tokens):
            obj: LearnableObject | None = None

            if token.pos == "VERB":
                obj = self._conjugation(token)
            elif token.pos == "ADJ" and i > 0 and tokens[i - 1].pos == "NOUN":
                obj = self._agreement(tokens[i - 1], token)
            else:
                obj = self._vocabulary(token)

            if obj is not None and obj.id not in seen:
                seen.add(obj.id)
                objects.append(obj)

        return objects

    # -- object factories --------------------------------------------------

    def _vocabulary(self, token: Token) -> LearnableObject:
        oid = f"es:vocab:{token.lemma}"
        return LearnableObject(
            id=oid,
            type="vocabulary",
            label=token.text,
            lesson_data={"lemma": token.lemma},
            confidence=0.5,
        )

    def _conjugation(self, token: Token) -> LearnableObject:
        stem = token.morph.get("Stem", token.lemma)
        oid = f"es:conj:{token.lemma}"
        return LearnableObject(
            id=oid,
            type="conjugation",
            label=token.text,
            lesson_data={"stem": stem, "form": token.text.lower()},
            confidence=0.55,
        )

    def _agreement(self, noun: Token, adj: Token) -> LearnableObject:
        oid = f"es:agree:{noun.lemma}+{adj.lemma}"
        return LearnableObject(
            id=oid,
            type="agreement",
            label=f"{noun.text} {adj.text}",
            lesson_data={"noun": noun.text, "adjective": adj.text},
            confidence=0.5,
        )
