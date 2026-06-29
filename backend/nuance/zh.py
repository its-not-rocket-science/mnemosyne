"""Chinese nuance extractor — aspect particles, measure words, chengyu."""
from __future__ import annotations

from typing import Any

from backend.nuance.interface import NuanceExtractorMixin
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
_VERBAL_GOV: dict[str, tuple[str, str]] = {
    # ── ZH additions (gen_verbal_government.py) ──
    '对 说': ('dui', "「对…说」(duì…shuō, to speak to) — coverb 对 + addressee + 说: 我对他说 (I said to him). 对 marks the addressee for speech verbs"),
    '对 感兴趣': ('dui', "「对…感兴趣」(duì…gǎn xìngqù, to be interested in) — 我对历史感兴趣 (I am interested in history). Predicate phrase with 对-marked topic"),
    '对 有信心': ('dui', "「对…有信心」(duì…yǒu xìnxīn, to have confidence in) — 对未来有信心 (have confidence in the future)"),
    '对 友好': ('dui', "「对…友好」(duì…yǒuhǎo, to be friendly to) — 对客人友好 (be friendly to guests). 对 marks the recipient of attitude"),
    '对 满意': ('dui', "「对…满意」(duì…mǎnyì, to be satisfied with) — 对结果满意 (satisfied with the result)"),
    '对 负责': ('dui', "「对…负责」(duì…fùzé, to be responsible for) — 对你负责 (be responsible for you)"),
    '跟 说': ('gen', "「跟…说」(gēn…shuō, to talk with) — 跟朋友说话 (talk with a friend). 跟 emphasizes reciprocity, vs. 对 (one-directional addressing)"),
    '跟 学': ('gen', "「跟…学」(gēn…xué, to learn from) — 跟老师学中文 (learn Chinese from the teacher). 跟 marks the source of learning"),
    '跟 商量': ('gen', "「跟…商量」(gēn…shāngliáng, to discuss with) — 跟父母商量 (discuss with parents)"),
    '跟 结婚': ('gen', "「跟…结婚」(gēn…jiéhūn, to marry) — 跟她结婚 (marry her). Coverb 跟 marks the spouse"),
    '和 一起': ('he', "「和…一起」(hé…yīqǐ, together with) — 和朋友一起去 (go together with friends). 和 functions as the connective preposition for accompaniment"),
    '给 打电话': ('gei', "「给…打电话」(gěi…dǎ diànhuà, to call) — 给妈妈打电话 (call mom). 给 marks the recipient of the action"),
    '给 写信': ('gei', "「给…写信」(gěi…xiě xìn, to write a letter to) — 给朋友写信 (write a letter to a friend)"),
    '给 买': ('gei', "「给…买」(gěi…mǎi, to buy for) — 给孩子买玩具 (buy a toy for the child). 给 = 'for the benefit of'"),
    '给 介绍': ('gei', "「给…介绍」(gěi…jièshào, to introduce to) — 给我介绍一下 (introduce [it/them] to me)"),
    '在 工作': ('zai', "「在…工作」(zài…gōngzuò, to work at) — 在公司工作 (work at the company). 在 marks location of action"),
    '在 学习': ('zai', "「在…学习」(zài…xuéxí, to study at) — 在大学学习 (study at university)"),
    '在 住': ('zai', "「在…住」(zài…zhù, to live in) — 在北京住 (live in Beijing)"),
    '从 来': ('cong', "「从…来」(cóng…lái, to come from) — 从美国来 (come from America). 从 marks origin/source"),
    '从 出发': ('cong', "「从…出发」(cóng…chūfā, to depart from) — 从北京出发 (depart from Beijing)"),
    '到 去': ('dao', "「到…去」(dào…qù, to go to) — 到中国去 (go to China). 到 marks destination/endpoint"),
    '到 来': ('dao', "「到…来」(dào…lái, to come to) — 到我家来 (come to my place)"),
    '把': ('ba', "「把」(bǎ) — fronts the affected object before the verb: 我把书放在桌子上 (I put the book on the table). The 把-construction emphasizes how the object is handled"),
    '被': ('bei', "「被」(bèi) — passive marker: 他被打了 (he was hit). Optional agent: 他被人打了 (he was hit by someone). Often carries adversative connotation"),
    '为 工作': ('wei', "「为…工作」(wèi…gōngzuò, to work for) — 为人民工作 (work for the people). 为 = 'for the benefit/sake of'"),
    '为 高兴': ('wei', "「为…高兴」(wèi…gāoxìng, to be happy for) — 为你高兴 (I'm happy for you)"),
    '为 担心': ('wei', "「为…担心」(wèi…dānxīn, to worry about/for) — 为孩子担心 (worry about the child)"),
    '为了': ('wèile', "「为了」(wèile, in order to) — 为了健康 (for the sake of health), 为了学好中文 (in order to learn Chinese well). Purpose marker, takes nouns or VPs"),
    '向 走': ('xiang', "「向…走」(xiàng…zǒu, to walk toward) — 向前走 (walk forward), 向北走 (head north). 向 marks direction"),
    '向 学习': ('xiang', "「向…学习」(xiàng…xuéxí, to learn from / model after) — 向英雄学习 (learn from heroes). 向 with 学习 means emulation"),
    '关于 谈': ('guanyu', "「关于…谈」(guānyú…tán, to talk about) — 关于这个问题 (regarding this question). 关于 = 'regarding/concerning', topical marker"),
    '由 组成': ('yu', "「由…组成」(yóu…zǔchéng, to be composed of) — 由三部分组成 (composed of three parts). 由 marks source/agent in formal/written register"),
    '等于': ('yu', "「等于」(děngyú, to equal) — 一加一等于二 (one plus one equals two). 于 fuses with 等"),
    '属于': ('yu', "「属于」(shǔyú, to belong to) — 这本书属于我 (this book belongs to me). Verb-yu compound; takes the possessor directly"),
    '适应': ('direct_object', "「适应」(shìyìng, to adapt to) — 适应新环境 (adapt to a new environment). NO coverb; direct object pattern"),
    '习惯': ('direct_object', "「习惯」(xíguàn, to be used to) — 习惯北京的天气 (be used to Beijing's weather). Direct object"),
    '担心': ('direct_object', "「担心」(dānxīn, to worry about) — 担心你的健康 (worry about your health). Takes direct object, not 关于"),
    '想念': ('direct_object', "「想念」(xiǎngniàn, to miss) — 想念家人 (miss family). Direct object — no preposition"),
    '害怕': ('direct_object', "「害怕」(hàipà, to fear) — 害怕黑暗 (fear darkness). Direct object — no preposition like English 'be afraid OF'"),
    '希望': ('direct_object', "「希望」(xīwàng, to hope) — 希望你成功 (hope you succeed). Takes a clausal complement directly"),
    '觉得': ('direct_object', "「觉得」(juéde, to feel/think) — 觉得很好 (think it's good). Takes a clausal complement"),
}


class ChineseNuanceExtractor(NuanceExtractorMixin):
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
        out.extend(self._cultural_references(sentence))
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
