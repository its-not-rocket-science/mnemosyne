from __future__ import annotations

import re
from collections.abc import Iterable

from backend.parsing.plugin_interface import Token
from backend.schemas.parse import LearnableObject, SentenceResult

SENTENCE_RE = re.compile(r"[^.!?¡¿]+[.!?¡¿]?")
WORD_RE = re.compile(r"[A-Za-zÁÉÍÓÚáéíóúÑñÜü]+")

VERB_ENDINGS = (
    "ar",
    "er",
    "ir",
    "o",
    "as",
    "a",
    "amos",
    "áis",
    "an",
    "es",
    "emos",
    "éis",
    "en",
    "imos",
    "ís",
)

COMMON_TRANSLATIONS = {
    "hola": "hello",
    "adios": "goodbye",
    "gracias": "thanks",
    "yo": "I",
    "tu": "you",
    "él": "he",
    "ella": "she",
    "nosotros": "we",
    "casa": "house",
    "libro": "book",
    "comer": "to eat",
    "hablar": "to speak",
    "vivir": "to live",
    "rojo": "red",
    "grande": "big",
}

ARTICLE_GENDER = {
    "el": ("masculine", "singular"),
    "la": ("feminine", "singular"),
    "los": ("masculine", "plural"),
    "las": ("feminine", "plural"),
    "un": ("masculine", "singular"),
    "una": ("feminine", "singular"),
    "unos": ("masculine", "plural"),
    "unas": ("feminine", "plural"),
}


class SpanishMVPPlugin:
    language_code = "es"
    display_name = "Spanish"
    direction = "ltr"

    def __init__(self) -> None:
        self._lesson_store: dict[str, LearnableObject] = {}

    def split_sentences(self, text: str) -> list[str]:
        sentences = [match.group(0).strip() for match in SENTENCE_RE.finditer(text)]
        return [sentence for sentence in sentences if sentence]

    def tokenize(self, sentence: str) -> list[Token]:
        tokens: list[Token] = []
        for raw in WORD_RE.findall(sentence):
            word = raw.strip()
            lower = word.lower()
            pos = self._guess_pos(lower)
            morph = self._guess_morph(lower, pos)
            lemma = self._guess_lemma(lower, pos)
            tokens.append(Token(text=word, lemma=lemma, pos=pos, morph=morph))
        return tokens

    def analyze_sentence(self, sentence: str) -> SentenceResult:
        tokens = self.tokenize(sentence)
        learnable_objects = []
        learnable_objects.extend(self._extract_vocabulary(tokens))
        learnable_objects.extend(self._extract_conjugations(tokens))
        learnable_objects.extend(self._extract_agreements(tokens))
        for obj in learnable_objects:
            self._lesson_store[obj.id] = obj
        return SentenceResult(text=sentence, learnable_objects=learnable_objects)

    def get_lesson(self, object_id: str) -> LearnableObject | None:
        return self._lesson_store.get(object_id)

    def _guess_pos(self, word: str) -> str:
        if word in ARTICLE_GENDER:
            return "DET"
        if self._looks_like_verb(word):
            return "VERB"
        if word.endswith(("o", "a", "os", "as", "e", "es")):
            return "ADJ_OR_NOUN"
        return "X"

    def _guess_morph(self, word: str, pos: str) -> dict[str, str]:
        morph: dict[str, str] = {}
        if pos == "DET":
            gender, number = ARTICLE_GENDER[word]
            morph["Gender"] = gender
            morph["Number"] = number
            return morph

        if pos == "VERB":
            person_map = {
                "o": "1",
                "as": "2",
                "a": "3",
                "amos": "1",
                "an": "3",
                "es": "2",
                "emos": "1",
                "en": "3",
                "imos": "1",
            }
            for ending, person in person_map.items():
                if word.endswith(ending):
                    morph["Person"] = person
                    break
            morph["Tense"] = "present"
            morph["Mood"] = "indicative"
            return morph

        if pos == "ADJ_OR_NOUN":
            if word.endswith(("os", "as")):
                morph["Number"] = "plural"
            else:
                morph["Number"] = "singular"

            if word.endswith(("a", "as")):
                morph["Gender"] = "feminine"
            elif word.endswith(("o", "os")):
                morph["Gender"] = "masculine"
            return morph

        return morph

    def _guess_lemma(self, word: str, pos: str) -> str:
        if pos == "VERB":
            for ending, infinitive in (
                ("o", "ar"),
                ("as", "ar"),
                ("a", "ar"),
                ("amos", "ar"),
                ("an", "ar"),
                ("es", "er"),
                ("emos", "er"),
                ("en", "er"),
                ("imos", "ir"),
            ):
                if word.endswith(ending) and len(word) > len(ending) + 1:
                    stem = word[: -len(ending)]
                    candidate = stem + infinitive
                    return candidate
        return word

    def _extract_vocabulary(self, tokens: Iterable[Token]) -> list[LearnableObject]:
        objects: list[LearnableObject] = []
        seen: set[str] = set()
        for token in tokens:
            if token.pos == "DET":
                continue
            if token.lemma in seen:
                continue
            seen.add(token.lemma)
            object_id = f"es:vocab:{token.lemma}"
            gloss = COMMON_TRANSLATIONS.get(token.lemma, "translation pending")
            objects.append(
                LearnableObject(
                    id=object_id,
                    type="vocabulary",
                    label=token.text,
                    lesson_data={
                        "kind": "vocabulary",
                        "lemma": token.lemma,
                        "gloss": gloss,
                        "part_of_speech": token.pos,
                    },
                    confidence=0.9 if gloss != "translation pending" else 0.65,
                )
            )
        return objects

    def _extract_conjugations(self, tokens: Iterable[Token]) -> list[LearnableObject]:
        objects: list[LearnableObject] = []
        for token in tokens:
            if token.pos != "VERB":
                continue
            object_id = f"es:conj:{token.text.lower()}"
            objects.append(
                LearnableObject(
                    id=object_id,
                    type="conjugation",
                    label=token.text,
                    lesson_data={
                        "kind": "conjugation",
                        "lemma": token.lemma,
                        "surface": token.text,
                        "tense": token.morph.get("Tense", "unknown"),
                        "mood": token.morph.get("Mood", "unknown"),
                        "person": token.morph.get("Person", "unknown"),
                    },
                    confidence=0.7,
                )
            )
        return objects

    def _extract_agreements(self, tokens: list[Token]) -> list[LearnableObject]:
        objects: list[LearnableObject] = []
        for index in range(len(tokens) - 1):
            left = tokens[index]
            right = tokens[index + 1]
            if left.pos != "DET":
                continue
            if right.pos != "ADJ_OR_NOUN":
                continue
            gender_match = left.morph.get("Gender") == right.morph.get("Gender")
            number_match = left.morph.get("Number") == right.morph.get("Number")
            if not gender_match and not number_match:
                continue
            label = f"{left.text} {right.text}"
            object_id = f"es:agreement:{left.text.lower()}_{right.text.lower()}"
            objects.append(
                LearnableObject(
                    id=object_id,
                    type="agreement",
                    label=label,
                    lesson_data={
                        "kind": "agreement",
                        "determiner": left.text,
                        "word": right.text,
                        "gender": right.morph.get("Gender", "unknown"),
                        "number": right.morph.get("Number", "unknown"),
                        "matches": {
                            "gender": gender_match,
                            "number": number_match,
                        },
                    },
                    confidence=0.78,
                )
            )
        return objects

    def _looks_like_verb(self, word: str) -> bool:
        # Require a stem of at least 4 characters so short nouns ending in
        # "a"/"o" (casa, rojo) are not mis-tagged as verbs.
        return any(
            word.endswith(ending) and len(word) - len(ending) > 3
            for ending in VERB_ENDINGS
        )


# create_plugin intentionally absent — SpanishMVPPlugin is superseded by
# SpanishPlugin (spanish.py).  The class is retained for tests that import
# it directly.
