"""Japanese nuance extractor — keigo (politeness levels), particles, yojijukugo.

Yojijukugo detection uses a two-pass hybrid:
  1. Pre-scan the raw sentence string left-to-right in 4-char windows.
     This catches compounds that SudachiPy splits into sub-tokens (e.g.
     一石二鳥 → [一石][二鳥]).  Advance by 4 on a match, 1 otherwise.
  2. Token-surface fallback — fires when spaCy keeps the compound intact.

The two passes share a `seen` set so the same compound is never emitted twice.
"""
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
    # perseverance / effort
    "一石二鳥": "kill two birds with one stone",
    "七転八起": "fall seven times, rise eight — perseverance through adversity",
    "臥薪嘗胆": "endure hardship for a greater goal; bide one's time for revenge",
    "不撓不屈": "indomitable spirit; never giving up no matter how hard",
    # fate / consequences
    "自業自得": "reap what you sow; face the consequences of one's own actions",
    "因果応報": "karma; good and bad deeds return to the doer",
    "一期一会": "once-in-a-lifetime encounter; treasure every meeting",
    # situation / environment
    "四面楚歌": "surrounded by enemies on all sides; completely isolated",
    "風前灯火": "a candle in the wind; precarious situation on the verge of extinction",
    "前途多難": "a long and difficult road ahead; the future is full of obstacles",
    # communication / understanding
    "以心伝心": "unspoken mutual understanding; heart-to-heart communication",
    "言語道断": "beyond words; utterly outrageous; inexcusable",
    # diversity / individuality
    "十人十色": "to each their own; ten people, ten colors — everyone differs",
    "千差万別": "infinite variety; great diversity among things or people",
    # adaptability / skill
    "臨機応変": "adapting flexibly to circumstances; thinking on one's feet",
    "融通無碍": "complete freedom and adaptability; no obstacles to free movement",
    # absorption / dedication
    "無我夢中": "completely absorbed in something; losing oneself in an activity",
    "一心不乱": "with single-minded focus; undivided concentration",
    # power / competition
    "弱肉強食": "survival of the fittest; the strong prey on the weak",
    "天下無双": "unrivaled under heaven; the best in the world",
}


def _text(tok: Any) -> str:
    return tok.text if hasattr(tok, "text") else str(tok)


def _lem(tok: Any) -> str:
    return getattr(tok, "lemma_", _text(tok))


def _lemma(c: CandidateObject) -> str:
    return c.lesson_data.get("lemma", c.canonical_form)


# Verbal government — verb + particle pairs. Populate via
# gen_verbal_government.py.
_VERBAL_GOV: dict[str, tuple[str, str]] = {}


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
        out.extend(self._verbal_government(candidates, seen))
        out.extend(self._yojijukugo(sentence, tokens, seen))
        return out

    def _verbal_government(
        self, candidates: list[CandidateObject], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for c in candidates:
            if c.type not in ("vocabulary", "conjugation"):
                continue
            lemma = _lemma(c)
            if lemma not in _VERBAL_GOV:
                continue
            required_case, example = _VERBAL_GOV[lemma]
            cf = f"nuance:ja:verbal_government:{lemma}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=c.surface_form,
                type="nuance",
                label=c.label,
                lesson_data={
                    "nuance_type": "verbal_government",
                    "explanation": (
                        f"{example}. "
                        "Japanese verbs select specific particles for their core arguments — "
                        "に (ni), を (wo), で (de), へ (e), と (to). Particle choice often "
                        f"shifts the meaning (会う meets に, 待つ waits for を). Required structure: {required_case}."
                    ),
                    "register": "neutral",
                    "learner_level": "B1",
                    "source": "heuristic",
                    "lemma": lemma,
                    "required_case": required_case,
                },
                confidence=0.85,
                relation_hints=[RelationHint(
                    relation_type="nuance_of",
                    target_canonical_form=lemma,
                    target_type="vocabulary",
                )],
            ))
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
        self, sentence: str, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        out = []

        # Pass 1 — sentence-string pre-scan (left-to-right, 4-char windows).
        # Catches compounds SudachiPy splits into sub-tokens (e.g. 一石|二鳥).
        i = 0
        n = len(sentence)
        while i <= n - 4:
            chunk = sentence[i:i + 4]
            if chunk in _YOJIJUKUGO:
                cf = f"nuance:ja:yojijukugo:{chunk}"
                if cf not in seen:
                    seen.add(cf)
                    out.append(self._make_yoji_candidate(chunk))
                i += 4  # skip the matched span — no overlap possible at same offset
            else:
                i += 1

        # Pass 2 — token-surface fallback.
        # Fires when spaCy happens to preserve the compound as a single token.
        for tok in tokens:
            surface = _text(tok)
            if len(surface) != 4 or surface not in _YOJIJUKUGO:
                continue
            cf = f"nuance:ja:yojijukugo:{surface}"
            if cf not in seen:
                seen.add(cf)
                out.append(self._make_yoji_candidate(surface))

        return out

    def _make_yoji_candidate(self, surface: str) -> CandidateObject:
        gloss = _YOJIJUKUGO[surface]
        return CandidateObject(
            canonical_form=f"nuance:ja:yojijukugo:{surface}",
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
        )
