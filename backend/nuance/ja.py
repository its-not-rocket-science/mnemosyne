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

from backend.nuance.interface import NuanceExtractorMixin
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
    # ── perseverance / effort ────────────────────────────────────────────────
    "一石二鳥": "kill two birds with one stone",
    "七転八起": "fall seven times, rise eight — perseverance through adversity",
    "臥薪嘗胆": "endure hardship for a greater goal; bide one's time for revenge",
    "不撓不屈": "indomitable spirit; never giving up no matter how hard",
    "一意専心": "devotion to a single purpose; undivided dedication",
    "粉骨砕身": "spare no effort; work to the bone",
    "七転八倒": "writhing in agony; rolling about in pain or distress",
    "起死回生": "revival from the brink of death; a comeback against all odds",
    # ── fate / consequences ──────────────────────────────────────────────────
    "自業自得": "reap what you sow; face the consequences of one's own actions",
    "因果応報": "karma; good and bad deeds return to the doer",
    "一期一会": "once-in-a-lifetime encounter; treasure every meeting",
    "自縄自縛": "bound by one's own rope; trapped by one's own words or actions",
    "自画自賛": "praising one's own work; blowing one's own trumpet",
    # ── situation / environment ──────────────────────────────────────────────
    "四面楚歌": "surrounded by enemies on all sides; completely isolated",
    "風前灯火": "a candle in the wind; precarious situation on the verge of extinction",
    "前途多難": "a long and difficult road ahead; the future is full of obstacles",
    "一触即発": "one touch and it explodes; a hair-trigger situation on the brink",
    "危機一髪": "by a hair's breadth; a close call; in the nick of time",
    "焦眉之急": "an emergency as urgent as eyebrows on fire; critical urgency",
    "四苦八苦": "struggling with all kinds of hardship; in great distress",
    # ── communication / understanding ───────────────────────────────────────
    "以心伝心": "unspoken mutual understanding; heart-to-heart communication",
    "言語道断": "beyond words; utterly outrageous; inexcusable",
    "一言居士": "someone who always has a comment; a person full of opinions",
    "単刀直入": "cutting straight to the point; getting directly to the matter",
    "有言実行": "keeping one's word; doing what one says",
    "不言実行": "acting without words; deeds speak louder than words",
    # ── diversity / individuality ────────────────────────────────────────────
    "十人十色": "to each their own; ten people, ten colors — everyone differs",
    "千差万別": "infinite variety; great diversity among things or people",
    "百花繚乱": "a riot of flowers; a dazzling display of talent or beauty",
    "百花斉放": "let a hundred flowers bloom; free expression of ideas",
    # ── adaptability / skill ────────────────────────────────────────────────
    "臨機応変": "adapting flexibly to circumstances; thinking on one's feet",
    "融通無碍": "complete freedom and adaptability; no obstacles to free movement",
    "変幻自在": "protean; transforming freely and at will",
    "縦横無尽": "moving freely in all directions; without restraint",
    # ── absorption / dedication ──────────────────────────────────────────────
    "無我夢中": "completely absorbed in something; losing oneself in an activity",
    "一心不乱": "with single-minded focus; undivided concentration",
    "熱中夢中": "passionately absorbed; fully engrossed",
    # ── power / competition ──────────────────────────────────────────────────
    "弱肉強食": "survival of the fittest; the strong prey on the weak",
    "天下無双": "unrivaled under heaven; the best in the world",
    "天下泰平": "peace and tranquility throughout the land",
    "勇猛果敢": "brave and bold; courageous and decisive",
    # ── human nature / character ─────────────────────────────────────────────
    "温故知新": "learn from the past to understand the present; revisit the old to discover the new",
    "知足安分": "contentment with one's lot; knowing when enough is enough",
    "喜怒哀楽": "the full range of human emotions — joy, anger, sorrow, pleasure",
    "清廉潔白": "upright and pure; clean hands and a clear conscience",
    "明鏡止水": "a still mirror and clear water; a serene and unclouded mind",
    "初志貫徹": "sticking to one's original goal; seeing a resolution through to the end",
    # ── appearance vs reality ────────────────────────────────────────────────
    "羊頭狗肉": "hanging a sheep's head while selling dog meat; false advertising",
    "表裏一体": "two sides of the same coin; inseparably connected front and back",
    "有名無実": "famous in name but not in substance; an empty title",
    # ── time / opportunity ───────────────────────────────────────────────────
    "今是昨非": "today right, yesterday wrong — realizing past errors; reformed thinking",
    "一朝一夕": "overnight; in a single morning and evening — a short time",
}


def _text(tok: Any) -> str:
    return tok.text if hasattr(tok, "text") else str(tok)


def _lem(tok: Any) -> str:
    return getattr(tok, "lemma_", _text(tok))


def _lemma(c: CandidateObject) -> str:
    return c.lesson_data.get("lemma", c.canonical_form)


# Verbal government — verb + particle pairs. Populate via
# gen_verbal_government.py.
_VERBAL_GOV: dict[str, tuple[str, str]] = {
    # ── JA additions (gen_verbal_government.py) ──
    '会う': ('ni', "「会う」(au, to meet) takes に + person: 友達に会う (meet a friend). Note: not を — 'meet' takes the dative-like に for the encountered person"),
    '似る': ('ni', "「似る」(niru, to resemble) takes に: 父に似ている (resembles father). Always used in -ている form for the state"),
    '似合う': ('ni', "「似合う」(niau, to suit) takes に: 君に似合う (it suits you). Subject is the clothing/style; に marks the wearer"),
    '勝つ': ('ni', "「勝つ」(katsu, to win) takes に + opponent: 試合に勝つ (win a match), 敵に勝つ (defeat the enemy). The opponent/competition takes に"),
    '負ける': ('ni', "「負ける」(makeru, to lose) takes に: 試合に負けた (lost the match). Mirror of 勝つ"),
    '慣れる': ('ni', "「慣れる」(nareru, to get used to) takes に: 新しい仕事に慣れる (get used to the new job)"),
    '反対する': ('ni', "「反対する」(hantai-suru, to oppose) takes に + opposed-thing: 計画に反対する (oppose the plan)"),
    '賛成する': ('ni', "「賛成する」(sansei-suru, to agree with) takes に: 意見に賛成する (agree with the opinion). Mirror of 反対する"),
    '出会う': ('ni', "「出会う」(deau, to encounter) takes に: 偶然彼に出会った (I encountered him by chance). Less planned than 会う"),
    '気づく': ('ni', "「気づく」(kizuku, to notice) takes に: 間違いに気づいた (I noticed the mistake). Compound of 気 + つく"),
    '触る': ('ni', "「触る」(sawaru, to touch) takes に: 触らないで (don't touch). Surface-level contact takes に. Compare 触れる + に (lighter touch)"),
    '乗る': ('ni', "「乗る」(noru, to ride/board) takes に: 電車に乗る (board the train). Vehicle/conveyance takes に"),
    '入る': ('ni', "「入る」(hairu, to enter) takes に: 部屋に入る (enter the room). Distinguish from へ (directional) — に for static endpoint"),
    '住む': ('ni', "「住む」(sumu, to live/reside) takes に: 東京に住んでいる (I live in Tokyo). Permanent residence takes に, not で"),
    '泊まる': ('ni', "「泊まる」(tomaru, to stay overnight) takes に: ホテルに泊まる (stay at a hotel). Lodging location takes に"),
    '勤める': ('ni', "「勤める」(tsutomeru, to work for) takes に + company: 会社に勤めている (works for a company). Note: long-term employment, not 'be working' (which uses で)"),
    '通う': ('ni', "「通う」(kayou, to commute) takes に: 学校に通う (commute to school)"),
    '答える': ('ni', "「答える」(kotaeru, to answer) takes に + question: 質問に答える (answer the question). Distinguish from 答える + person (rare)"),
    '頼む': ('ni', "「頼む」(tanomu, to request) takes に + person + を + thing: 友達に頼む (ask a friend). Two-object: に for person, を for request"),
    '送る': ('ni', "「送る」(okuru, to send) takes に + recipient + を + thing: 母に手紙を送る (send a letter to mother). Two-object pattern"),
    'あげる': ('ni', "「あげる」(ageru, to give) takes に + recipient + を + thing: 友達に本をあげる (give a book to a friend). Speaker/closer-to-speaker giving"),
    'もらう': ('ni', "「もらう」(morau, to receive) takes に or から + giver + を + thing: 友達に本をもらった (I got a book from a friend)"),
    '見る': ('wo', "「見る」(miru, to see/watch) takes を: 映画を見る (watch a movie). Standard transitive object marker"),
    '聞く': ('wo', "「聞く」(kiku, to hear/listen/ask) takes を: 音楽を聞く (listen to music). When meaning 'ask' takes に + person"),
    '待つ': ('wo', "「待つ」(matsu, to wait for) takes を: バスを待つ (wait for the bus). NOTE: を not に — the awaited object is direct, not dative"),
    '守る': ('wo', "「守る」(mamoru, to protect/keep) takes を: 約束を守る (keep a promise), 法律を守る (obey the law)"),
    '求める': ('wo', "「求める」(motomeru, to seek/demand) takes を: 助けを求める (seek help)"),
    '始める': ('wo', "「始める」(hajimeru, transitive: to begin) takes を: 仕事を始める (start the job). Mirror: 始まる (intransitive) takes が"),
    '戦う': ('to', "「戦う」(tatakau, to fight) takes と + opponent: 敵と戦う (fight the enemy). と marks reciprocal/co-participant"),
    '結婚する': ('to', "「結婚する」(kekkon-suru, to marry) takes と: 彼女と結婚する (marry her). NOT を — Japanese marriage takes と for partner"),
    '話す': ('to', "「話す」(hanasu, to talk with) takes と + interlocutor: 友達と話す (talk with a friend). Distinguish from 話す + を (tell a story)"),
    '会う と': ('to', "「会う」alternative form takes と: 友達と会う (meet with a friend). と is more reciprocal/social; に is more directional"),
    '比べる': ('to', "「比べる」(kuraberu, to compare) takes と + compared item: 兄と比べる (compare with elder brother)"),
    '別れる': ('to', "「別れる」(wakareru, to part with) takes と + person: 彼と別れた (I broke up with him)"),
    '相談する': ('to', "「相談する」(soudan-suru, to consult with) takes と: 先生と相談する (consult with the teacher)"),
    '出る': ('kara', "「出る」(deru, to exit) takes から + place: 家から出る (exit the house). Mirror of 入る + に"),
    'もらう から': ('kara', "「もらう」(morau) alternative pattern takes から + source: 先生から本をもらった (I got a book from the teacher). から emphasizes origin more than に"),
    '学ぶ': ('kara', "「学ぶ」(manabu, to learn from) takes から: 先生から学ぶ (learn from the teacher). Source-of-learning takes から"),
    '始まる': ('kara', "「始まる」(hajimaru, intransitive: to begin) takes から for starting time: 9時から始まる (starts at 9). Static event onset"),
    '成る': ('ni', "「成る」(naru, to become) takes に + new state: 大人になる (become an adult), 医者になる (become a doctor). Distinct from と+naru in formal contexts"),
    'なる': ('to+naru', "「と+なる」(to-naru, to formally/publicly become) takes と: 結果となる (it becomes the result), 力となる (becomes a force). Formal register"),
    '知り合う': ('to', "「知り合う」(shiriau, to become acquainted with) takes と: 新しい人と知り合う (meet someone new). Reciprocal -au compound"),
    '間違える': ('wo', "「間違える」(machigaeru, to mistake/get wrong) takes を: 答えを間違える (get the answer wrong)"),
}


class JapaneseNuanceExtractor(NuanceExtractorMixin):
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
