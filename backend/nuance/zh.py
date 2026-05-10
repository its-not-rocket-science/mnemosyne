"""Chinese nuance extractor — aspect particles, measure words, chengyu."""
from __future__ import annotations

from typing import Any

from backend.schemas.parse import CandidateObject, RelationHint

_ASPECT_PARTICLES: dict[str, tuple[str, str]] = {
    "了": (
        "aspect_le",
        "«了» (le) marks completion of an action or a change of state. "
        "Verb-final: action is completed (我吃了 — I ate/have eaten). "
        "Sentence-final: a new situation has come about (下雨了 — it's raining now).",
    ),
    "过": (
        "aspect_guo",
        "«过» (guò) marks experiential aspect — an action has been experienced at some "
        "point in one's life: 我去过北京 (I have been to Beijing). "
        "It emphasizes life experience rather than recency.",
    ),
    "着": (
        "aspect_zhe",
        "«着» (zhe) marks a continuous or persistent state: 他笑着说 (he said, smiling). "
        "It often describes a background or concurrent state rather than a main action.",
    ),
}

_MEASURE_WORDS: dict[str, str] = {
    "个": "general classifier (people, objects, abstract units)",
    "本": "bound volumes (books, magazines)",
    "张": "flat objects (paper, tables, faces)",
    "块": "chunks or pieces (bread, money, stone)",
    "条": "long, flexible objects (fish, rope, street, news)",
    "件": "items, events, or garments",
    "只": "small animals or one of a pair",
    "双": "pairs (shoes, chopsticks)",
    "对": "matched pairs",
    "把": "objects with handles; handfuls",
    "杯": "cupfuls or glasses",
    "碗": "bowls of food",
    "盘": "plates or discs",
    "瓶": "bottles",
    "位": "polite classifier for people",
    "匹": "horses or bolts of fabric",
    "口": "mouthfuls; family members (spoken)",
    "套": "sets or suits",
    "辆": "wheeled vehicles",
    "栋": "buildings",
}

_CHENGYU: dict[str, str] = {
    "一石二鸟": "kill two birds with one stone",
    "马到成功": "immediate success upon arrival",
    "画蛇添足": "ruin something by adding superfluous detail",
    "半途而废": "give up halfway through",
    "亡羊补牢": "fix the problem after the loss (better late than never)",
    "守株待兔": "wait passively for luck to arrive",
    "狐假虎威": "bully others by leveraging a powerful backer",
    "叶公好龙": "profess to love something one actually fears",
    "三人成虎": "a lie repeated enough becomes accepted as truth",
    "自相矛盾": "self-contradiction",
    "滥竽充数": "pass oneself off as capable",
    "掩耳盗铃": "deceive oneself",
    "杯弓蛇影": "extreme paranoia over imagined threats",
    "一箭双雕": "kill two birds with one arrow",
    "对牛弹琴": "cast pearls before swine",
}


def _text(tok: Any) -> str:
    return tok.text if hasattr(tok, "text") else str(tok)


def _lemma(c: CandidateObject) -> str:
    return c.lesson_data.get("lemma", c.canonical_form)


# Verbal government — verb + coverb/preposition pairs. Populate via
# gen_verbal_government.py.
_VERBAL_GOV: dict[str, tuple[str, str]] = {}


class ChineseNuanceExtractor:
    language = "zh"

    def extract_nuance(
        self,
        sentence: str,
        tokens: list[Any],
        candidates: list[CandidateObject],
        language: str,
    ) -> list[CandidateObject]:
        out: list[CandidateObject] = []
        seen: set[str] = set()
        out.extend(self._aspect_particles(tokens, seen))
        out.extend(self._measure_words(tokens, seen))
        out.extend(self._verbal_government(candidates, seen))
        out.extend(self._chengyu(tokens, seen))
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
            cf = f"nuance:zh:verbal_government:{lemma}"
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
                        "Chinese verbs combine with coverbs (prepositional verbs: 给 gěi, 对 duì, "
                        "跟 gēn, 在 zài, 从 cóng, 到 dào, 把 bǎ, 被 bèi) to mark the role "
                        "of arguments. The 把-construction fronts the affected object; the "
                        f"被-construction marks passive. Required structure: {required_case}."
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

    def _aspect_particles(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for tok in tokens:
            surface = _text(tok)
            if surface not in _ASPECT_PARTICLES:
                continue
            nuance_type, explanation = _ASPECT_PARTICLES[surface]
            cf = f"nuance:zh:{nuance_type}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=surface,
                type="nuance",
                label=surface,
                lesson_data={
                    "nuance_type": nuance_type,
                    "explanation": explanation,
                    "register": "neutral",
                    "learner_level": "B1",
                    "source": "heuristic",
                    "particle": surface,
                },
                confidence=0.85,
            ))
        return out

    def _measure_words(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for tok in tokens:
            surface = _text(tok)
            if surface not in _MEASURE_WORDS:
                continue
            cf = f"nuance:zh:measure_word:{surface}"
            if cf in seen:
                continue
            seen.add(cf)
            usage = _MEASURE_WORDS[surface]
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=surface,
                type="nuance",
                label=surface,
                lesson_data={
                    "nuance_type": "measure_word",
                    "explanation": (
                        f"«{surface}» is a measure word (量词 liàngcí). Usage: {usage}. "
                        "Chinese requires a classifier between a numeral and a noun: "
                        "三本书 (sān běn shū — three [bound-volume] books). "
                        "Each noun class has a conventional classifier; using the wrong "
                        "one sounds unnatural even if grammatically permissible."
                    ),
                    "register": "neutral",
                    "learner_level": "A2",
                    "source": "heuristic",
                    "measure_word": surface,
                    "usage": usage,
                },
                confidence=0.80,
            ))
        return out

    def _chengyu(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for tok in tokens:
            surface = _text(tok)
            if len(surface) != 4 or surface not in _CHENGYU:
                continue
            cf = f"nuance:zh:chengyu:{surface}"
            if cf in seen:
                continue
            seen.add(cf)
            gloss = _CHENGYU[surface]
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=surface,
                type="nuance",
                label=surface,
                lesson_data={
                    "nuance_type": "chengyu",
                    "explanation": (
                        f"«{surface}» is a chéngyǔ (成语), a four-character classical idiom "
                        f"with the approximate meaning: '{gloss}'. "
                        "Chengyu originate from classical texts and historical anecdotes; "
                        "each encodes an allusion that native speakers recognize. "
                        "They add literary or formal register to speech and writing."
                    ),
                    "register": "literary",
                    "learner_level": "C1",
                    "source": "heuristic",
                    "chengyu": surface,
                    "gloss": gloss,
                },
                confidence=0.90,
            ))
        return out
