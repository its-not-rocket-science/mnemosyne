"""Japanese nuance extractor — keigo (politeness levels), particles, yojijukugo."""
from __future__ import annotations

from typing import Any

from backend.schemas.parse import CandidateObject, RelationHint

_POLITE_ENDINGS = (
    "ます", "ました", "ません", "ませんでした",
    "です", "でした", "でしょう", "ましょう", "ませ",
)

_HONORIFIC_LEMMAS = frozenset({
    "いらっしゃる", "おっしゃる", "ございます", "なさる", "くださる", "めしあがる",
})

_HUMBLE_LEMMAS = frozenset({
    "いたす", "まいる", "おる", "もうす", "いただく",
})

_PARTICLES: dict[str, str] = {
    "は": "topic marker — marks the sentence topic, often implying contrast with は-less versions",
    "が": "subject marker — marks the grammatical subject; contrasts with は for focus and emphasis",
    "を": "direct object marker — marks the object of transitive verbs",
    "に": "indirect object/goal/time/location marker — dative, directional, temporal",
    "で": "location-of-action or means marker — 'at', 'by means of', 'because of'",
    "へ": "directional marker — 'toward'; similar to に for direction but more literary",
    "と": "comitative or quotative marker — 'with', 'and', or introduces direct quotations",
    "から": "source or starting point — 'from', 'because of'",
    "まで": "limit or extent — 'until', 'as far as', 'to'",
    "より": "comparison or source (formal) — 'than', 'from'",
    "の": "genitive or nominalizer — possessive; turns clauses into noun phrases",
    "も": "additive or inclusive — 'also', 'too', 'even'",
    "か": "question marker or disjunction — sentence-final question; between nouns = 'or'",
    "ね": "confirmation or empathy marker — seeks agreement; adds warmth",
    "よ": "assertion marker — adds emphasis; signals information new to the listener",
    "な": "prohibition (verb + na) or gentle assertion; female/soft sentence-final particle",
}

_YOJIJUKUGO: dict[str, str] = {
    "一石二鳥": "kill two birds with one stone",
    "七転八起": "fall seven times, rise eight — perseverance",
    "以心伝心": "unspoken mutual understanding; telepathic communication",
    "四面楚歌": "surrounded by enemies on all sides",
    "自業自得": "reap what you sow",
    "十人十色": "to each their own; everyone differs",
    "弱肉強食": "survival of the fittest",
    "臨機応変": "adapting flexibly to circumstances",
    "一期一会": "once-in-a-lifetime encounter; treasure the moment",
    "無我夢中": "absorbed in something; losing oneself in an activity",
}


def _text(tok: Any) -> str:
    return tok.text if hasattr(tok, "text") else str(tok)


def _lem(tok: Any) -> str:
    return getattr(tok, "lemma_", _text(tok))


class JapaneseNuanceExtractor:
    language = "ja"

    def extract_nuance(
        self,
        sentence: str,
        tokens: list[Any],
        candidates: list[CandidateObject],
        language: str,
    ) -> list[CandidateObject]:
        out: list[CandidateObject] = []
        seen: set[str] = set()
        out.extend(self._keigo(tokens, seen))
        out.extend(self._particles(tokens, seen))
        out.extend(self._yojijukugo(tokens, seen))
        return out

    def _keigo(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for tok in tokens:
            surface = _text(tok)
            lemma = _lem(tok)
            if lemma in _HONORIFIC_LEMMAS:
                keigo_type = "sonkeigo"
                explanation = (
                    f"«{lemma}» is a sonkeigo (尊敬語) honorific verb — used to elevate "
                    "the actions of the person being spoken to or about. "
                    "Never used for one's own actions."
                )
            elif lemma in _HUMBLE_LEMMAS:
                keigo_type = "kenjogo"
                explanation = (
                    f"«{lemma}» is a kenjōgo (謙譲語) humble verb — used to lower one's "
                    "own actions relative to the listener or a respected third party. "
                    "Essential in business and formal service contexts."
                )
            elif any(surface.endswith(e) for e in _POLITE_ENDINGS):
                keigo_type = "teineigo"
                explanation = (
                    "Teineigo (丁寧語) — polite speech using ます/です verb endings. "
                    "Used with strangers, superiors, and in formal contexts. "
                    "The baseline polite register expected of adult speakers."
                )
            else:
                continue
            cf = f"nuance:ja:keigo:{keigo_type}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=surface,
                type="nuance",
                label=surface,
                lesson_data={
                    "nuance_type": "keigo",
                    "keigo_type": keigo_type,
                    "explanation": explanation,
                    "register": "formal",
                    "learner_level": "B2",
                    "source": "heuristic",
                },
                confidence=0.80,
            ))
        return out

    def _particles(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for tok in tokens:
            surface = _text(tok)
            if surface not in _PARTICLES:
                continue
            cf = f"nuance:ja:particle:{surface}"
            if cf in seen:
                continue
            seen.add(cf)
            role = _PARTICLES[surface]
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=surface,
                type="nuance",
                label=surface,
                lesson_data={
                    "nuance_type": "particle",
                    "explanation": f"«{surface}» is a Japanese particle (助詞 joshi): {role}.",
                    "register": "neutral",
                    "learner_level": "A1",
                    "source": "heuristic",
                    "particle": surface,
                },
                confidence=0.90,
            ))
        return out

    def _yojijukugo(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for tok in tokens:
            surface = _text(tok)
            if len(surface) != 4 or surface not in _YOJIJUKUGO:
                continue
            cf = f"nuance:ja:yojijukugo:{surface}"
            if cf in seen:
                continue
            seen.add(cf)
            gloss = _YOJIJUKUGO[surface]
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=surface,
                type="nuance",
                label=surface,
                lesson_data={
                    "nuance_type": "yojijukugo",
                    "explanation": (
                        f"«{surface}» is a yojijukugo (四字熟語), a four-character compound "
                        f"with the meaning: '{gloss}'. "
                        "These compounds, often of Chinese origin, function as fixed expressions "
                        "carrying cultural and literary weight in Japanese."
                    ),
                    "register": "literary",
                    "learner_level": "C1",
                    "source": "heuristic",
                    "yojijukugo": surface,
                    "gloss": gloss,
                },
                confidence=0.90,
            ))
        return out
