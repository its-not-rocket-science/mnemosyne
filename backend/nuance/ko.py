"""Korean nuance extractor — politeness register, particles, negation, subject honorific.

Two operating modes, selected automatically by inspecting the token type:

  kiwipiepy mode  tokens have a .tag attribute (kiwipiepy Token objects)
                  Near-zero false positives; reads morpheme-level JK*/EF tags.

  heuristic mode  tokens are plain objects with .text OR any str-able object
                  (e.g. the _Tok stubs used in gold tests, or whitespace words).
                  Uses sentence-final suffix matching and word-boundary checks.

Canonical forms emitted (IMMUTABLE):

  Politeness
    nuance:ko:politeness:formal_polite    합쇼체 — -습니다/-ㅂ니다/-십시오
    nuance:ko:politeness:informal_polite  해요체 — sentence-final 요
    nuance:ko:politeness:plain_informal   해체  — -어/-아/-해  (no 요)
    nuance:ko:politeness:plain_formal     해라체 — -(는)다/-ㄴ다 (written)

  Particles (citation form normalises vowel-harmony allomorphs)
    nuance:ko:particle:이/가              subject marker
    nuance:ko:particle:을/를             object marker
    nuance:ko:particle:은/는             topic/contrast marker
    nuance:ko:particle:에                locative/dative
    nuance:ko:particle:에서              locative-of-action / source
    nuance:ko:particle:으로/로           directional / instrumental
    nuance:ko:particle:와/과             comitative (formal)
    nuance:ko:particle:도                additive ("too / also / even")
    nuance:ko:particle:만                exclusive ("only")
    nuance:ko:particle:에게/한테         animate dative

  Negation
    nuance:ko:negation:short_an          안 — colloquial negation
    nuance:ko:negation:short_mot         못 — inability negation
    nuance:ko:negation:long_anta         -지 않다 — long negation (kiwipiepy only)
    nuance:ko:negation:long_motda        -지 못하다 — inability long form (kiwipiepy only)

  Honorific
    nuance:ko:honorific:subject_si       -(으)시- EP — subject elevation (kiwipiepy only)
"""
from __future__ import annotations

from typing import Any

from backend.schemas.parse import CandidateObject

# ── Politeness — sentence-final surface patterns ──────────────────────────────

# EF morpheme surfaces for kiwipiepy mode (substring check on tok.form).
# Longer strings first so a partial shorter string does not shadow them.
_EF_FORMAL_POLITE = (
    "십시오", "으십시오", "십니다",
    "습니까", "ㅂ니까",
    "습니다", "ㅂ니다",
)
_EF_INFORMAL_POLITE = (
    "겠어요", "겠습니까",
    "었어요", "았어요", "였어요",
    "이에요", "예요",
    "네요", "군요",
    "셔요", "봐요", "와요",   # contracted: 마시+어요→마셔요, 보+아요→봐요, 오+아요→와요
    "어요", "아요", "해요", "여요",
)
_EF_PLAIN_INFORMAL = (
    "겠어", "었어", "았어",
    "어", "아", "해",
)
_EF_PLAIN_FORMAL = (
    "겠다", "었다", "았다",
    "는다", "ㄴ다",
)

# ── Particles ──────────────────────────────────────────────────────────────────
# surface → (citation_form, role_description)
# Longer surfaces first to avoid "에" matching before "에서" in suffix scan.
_PARTICLES: dict[str, tuple[str, str]] = {
    "에서": ("에서",      "locative-of-action or source — 'at', 'in', 'from'"),
    "으로": ("으로/로",   "directional / instrumental / causative (after consonant except ㄹ)"),
    "에게": ("에게/한테", "animate dative (formal) — 'to (a person)'"),
    "한테": ("에게/한테", "animate dative (informal) — 'to (a person)'"),
    "와":   ("와/과",     "comitative conjunction (formal) — 'and / with'; after vowel-final noun"),
    "과":   ("와/과",     "comitative conjunction (formal) — 'and / with'; after consonant-final noun"),
    "로":   ("으로/로",   "directional / instrumental / causative (after vowel or ㄹ)"),
    "에":   ("에",        "locative / dative — location, destination, time point"),
    "을":   ("을/를",     "object marker — accusative; after consonant-final noun"),
    "를":   ("을/를",     "object marker — accusative; after vowel-final noun"),
    "은":   ("은/는",     "topic / contrast marker; after consonant-final noun"),
    "는":   ("은/는",     "topic / contrast marker; after vowel-final noun"),
    "이":   ("이/가",     "subject marker — nominative; after consonant-final noun"),
    "가":   ("이/가",     "subject marker — nominative; after vowel-final noun"),
    "도":   ("도",        "additive particle — 'too', 'also', 'even'"),
    "만":   ("만",        "exclusive particle — 'only', 'just'"),
}

# kiwipiepy JK/JX tags that carry particles
_PARTICLE_TAGS = frozenset({
    "JKS", "JKC", "JKO", "JKB", "JKG", "JKV", "JKQ", "JX", "JC",
})

# ── Negation ──────────────────────────────────────────────────────────────────

_SHORT_NEG: dict[str, str] = {"안": "short_an", "못": "short_mot"}
_LONG_NEG_NEXT: dict[str, str] = {
    "않": "long_anta",
    "못하": "long_motda",
}

# ── Honorific ──────────────────────────────────────────────────────────────────

_HONORIFIC_EP = frozenset({"시", "으시"})

# Verbal government — verb + particle pairs. Populate via
# gen_verbal_government.py.
_VERBAL_GOV: dict[str, tuple[str, str]] = {
    # ── KO additions (gen_verbal_government.py) ──
    '가다': ('e', "「가다」(gada, to go) takes 에 + destination: 학교에 가다 (go to school). Distinguish from 에서 (location of action)"),
    '오다': ('e', "「오다」(oda, to come) takes 에 + destination: 집에 오다 (come home). Mirror of 가다"),
    '도착하다': ('e', "「도착하다」(dochakhada, to arrive) takes 에 + place: 공항에 도착했다 (I arrived at the airport)"),
    '들어가다': ('e', "「들어가다」(deureogada, to enter) takes 에 + place: 방에 들어가다 (enter the room). Compound of 들다 + 가다"),
    '살다': ('e', "「살다」(salda, to live) takes 에 + location: 서울에 살다 (live in Seoul). Permanent residence takes 에"),
    '가입하다': ('e', "「가입하다」(gaipada, to join) takes 에 + group: 동아리에 가입하다 (join a club)"),
    '참가하다': ('e', "「참가하다」(chamgahada, to participate in) takes 에 + event: 회의에 참가하다 (participate in the meeting)"),
    '관심이 있다': ('e', "「관심이 있다」(gwansim-i itda, to be interested in) takes 에 + topic: 음악에 관심이 있다 (interested in music)"),
    '익숙하다': ('e', "「익숙하다」(iksukhada, to be accustomed to) takes 에 + habituated thing: 한국 음식에 익숙하다 (used to Korean food)"),
    '적응하다': ('e', "「적응하다」(jeokeunghada, to adapt to) takes 에 + new context: 새 환경에 적응하다 (adapt to a new environment)"),
    '의지하다': ('e', "「의지하다」(uijihada, to rely on) takes 에 + supporter: 친구에 의지하다 (rely on a friend)"),
    '열중하다': ('e', "「열중하다」(yeoljunghada, to concentrate on) takes 에 + activity: 공부에 열중하다 (concentrate on study)"),
    '성공하다': ('e', "「성공하다」(seonggonghada, to succeed in) takes 에 + endeavor: 사업에 성공하다 (succeed in business)"),
    '실패하다': ('e', "「실패하다」(silpaehada, to fail in) takes 에 + endeavor: 시험에 실패하다 (fail in the exam). Mirror of 성공하다"),
    '공부하다': ('eseo', "「공부하다」(gongbuhada, to study) takes 에서 for location of action: 도서관에서 공부하다 (study at the library). Distinguish from 에 (static residence)"),
    '일하다': ('eseo', "「일하다」(ilhada, to work) takes 에서 + workplace: 회사에서 일하다 (work at a company)"),
    '출발하다': ('eseo', "「출발하다」(chulbalhada, to depart) takes 에서 + origin: 서울에서 출발하다 (depart from Seoul). Mirror: 도착하다 + 에"),
    '오다 에서': ('eseo', "「오다」alternate: 에서 + origin: 미국에서 왔다 (came from America). Source/origin takes 에서"),
    '왔다': ('buteo', "「부터」particle pattern: 9시부터 시작했다 (started from 9 o'clock). Temporal origin takes 부터"),
    '보다': ('eul_reul', "「보다」(boda, to see/watch) takes 을/를 + direct object: 영화를 보다 (watch a movie). Standard transitive"),
    '먹다': ('eul_reul', "「먹다」(meokda, to eat) takes 을/를: 밥을 먹다 (eat rice/a meal). Direct object marker"),
    '마시다': ('eul_reul', "「마시다」(masida, to drink) takes 을/를: 커피를 마시다 (drink coffee)"),
    '읽다': ('eul_reul', "「읽다」(ikda, to read) takes 을/를: 책을 읽다 (read a book)"),
    '쓰다': ('eul_reul', "「쓰다」(sseuda, to write) takes 을/를: 편지를 쓰다 (write a letter). Multi-meaning verb: also 'use', 'wear (hat)', 'be bitter'"),
    '좋아하다': ('eul_reul', "「좋아하다」(joahada, to like) takes 을/를 — NOT 이/가: 음악을 좋아하다 (like music). Distinct from descriptive 좋다 (be good) which takes 이/가"),
    '싫어하다': ('eul_reul', "「싫어하다」(silhohada, to dislike) takes 을/를: 운동을 싫어하다 (dislike exercise). Mirror of 좋아하다"),
    '원하다': ('eul_reul', "「원하다」(wonhada, to want) takes 을/를: 평화를 원하다 (want peace)"),
    '기다리다': ('eul_reul', "「기다리다」(gidarida, to wait for) takes 을/를: 친구를 기다리다 (wait for a friend). Direct object — not Korean equivalent of 'for'"),
    '결혼하다': ('wa_gwa', "「결혼하다」(gyeolhonhada, to marry) takes 와/과 + partner: 그녀와 결혼하다 (marry her). Same pattern as Japanese と"),
    '만나다': ('wa_gwa', "「만나다」(mannada, to meet) often takes 와/과: 친구와 만나다 (meet with a friend). Also takes 을/를 directly: 친구를 만나다"),
    '싸우다': ('wa_gwa', "「싸우다」(ssauda, to fight) takes 와/과 + opponent: 친구와 싸웠다 (fought with a friend)"),
    '비교하다': ('wa_gwa', "「비교하다」(bigyohada, to compare) takes 을/를 + 와/과: A를 B와 비교하다 (compare A with B). Two-object structure"),
    '이야기하다': ('wa_gwa', "「이야기하다」(iyagihada, to talk with) takes 와/과 + interlocutor: 친구와 이야기하다 (talk with a friend)"),
    '약속하다': ('wa_gwa', "「약속하다」(yaksokhada, to promise / make appointment with) takes 와/과 + person: 친구와 약속하다 (make a promise with a friend)"),
    '헤어지다': ('wa_gwa', "「헤어지다」(heeojida, to part with / break up) takes 와/과: 그와 헤어졌다 (broke up with him)"),
    '가다 로': ('euro_ro', "「가다」alternate: 으로/로 + means/direction: 버스로 가다 (go by bus), 학교로 가다 (head toward school). Means/instrumental case"),
    '만들다': ('euro_ro', "「만들다」(mandeulda, to make from) takes 으로/로 + material: 나무로 만들다 (make from wood)"),
    '변하다': ('euro_ro', "「변하다」(byeonhada, to change into) takes 으로/로 + new state: 어른으로 변하다 (change into an adult)"),
    '주다': ('ege', "「주다」(juda, to give) takes 에게 + recipient + 을/를 + thing: 친구에게 책을 주다 (give a book to a friend). Two-object pattern with 에게 for animate recipients"),
    '보내다': ('ege', "「보내다」(bonaeda, to send) takes 에게 + recipient: 어머니에게 편지를 보내다 (send a letter to mother). Animate recipient takes 에게"),
    '말하다': ('ege', "「말하다」(malhada, to say to) takes 에게 + recipient: 친구에게 말하다 (tell a friend). Distinguish from 와/과 (talk WITH)"),
    '전화하다': ('ege', "「전화하다」(jeonhwahada, to call/phone) takes 에게: 친구에게 전화하다 (call a friend)"),
    '묻다': ('ege', "「묻다」(mutda, to ask) takes 에게 + person + 을/를 + thing: 친구에게 길을 묻다 (ask a friend for directions)"),
}


def _lemma(c: CandidateObject) -> str:
    return c.lesson_data.get("lemma", c.canonical_form)


class KoreanNuanceExtractor:
    language = "ko"

    def extract_nuance(
        self,
        sentence: str,
        tokens: list[Any],
        candidates: list[CandidateObject],
        language: str,
    ) -> list[CandidateObject]:
        out: list[CandidateObject] = []
        seen: set[str] = set()
        kiwi_mode = bool(tokens) and hasattr(tokens[0], "tag")

        if kiwi_mode:
            out.extend(self._politeness_kiwi(tokens, seen))
            out.extend(self._particles_kiwi(tokens, seen))
            out.extend(self._negation_kiwi(tokens, seen))
            out.extend(self._honorific_kiwi(tokens, seen))
        else:
            out.extend(self._politeness_heuristic(sentence, seen))
            out.extend(self._particles_heuristic(sentence, seen))
            out.extend(self._negation_heuristic(tokens, seen))

        out.extend(self._verbal_government(candidates, seen))
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
            cf = f"nuance:ko:verbal_government:{lemma}"
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
                        "Korean verbs require specific case particles for their arguments — "
                        "이/가 (subject), 을/를 (object), 에 (location/time), 에서 (source/"
                        "location of action), 에게 (animate goal). Vowel/consonant allomorphy "
                        f"determines particle form. Required structure: {required_case}."
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

    # ------------------------------------------------------------------
    # kiwipiepy-mode
    # ------------------------------------------------------------------

    def _politeness_kiwi(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for tok in tokens:
            if str(tok.tag) != "EF":
                continue
            register = self._classify_ef_surface(tok.form)
            if register is None:
                continue
            cf = f"nuance:ko:politeness:{register}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(self._make_politeness(cf, tok.form, register))
        return out

    def _particles_kiwi(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for tok in tokens:
            if str(tok.tag) not in _PARTICLE_TAGS:
                continue
            entry = _PARTICLES.get(tok.form)
            if entry is None:
                continue
            citation, role = entry
            cf = f"nuance:ko:particle:{citation}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(self._make_particle(cf, tok.form, citation, role))
        return out

    def _negation_kiwi(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        forms = [t.form for t in tokens]
        tags  = [str(t.tag) for t in tokens]
        for i, (form, tag) in enumerate(zip(forms, tags)):
            # Short: MAG 안/못 followed immediately by a verb
            if tag == "MAG" and form in _SHORT_NEG:
                nxt = tags[i + 1] if i + 1 < len(tags) else ""
                if nxt in {"VV", "VA", "VX", "VCP", "VCN"}:
                    neg_type = _SHORT_NEG[form]
                    cf = f"nuance:ko:negation:{neg_type}"
                    if cf not in seen:
                        seen.add(cf)
                        out.append(self._make_negation(cf, form, neg_type))
            # Long: EC 지 followed by VX 않/못하
            if tag == "EC" and form == "지":
                nxt_form = forms[i + 1] if i + 1 < len(forms) else ""
                neg_type = _LONG_NEG_NEXT.get(nxt_form)
                if neg_type:
                    cf = f"nuance:ko:negation:{neg_type}"
                    if cf not in seen:
                        seen.add(cf)
                        out.append(self._make_negation(
                            cf, f"지 {nxt_form}다", neg_type,
                        ))
        return out

    def _honorific_kiwi(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        cf = "nuance:ko:honorific:subject_si"
        if cf in seen:
            return []
        for tok in tokens:
            if str(tok.tag) == "EP" and tok.form in _HONORIFIC_EP:
                seen.add(cf)
                return [CandidateObject(
                    canonical_form=cf,
                    surface_form=tok.form,
                    type="nuance",
                    label=tok.form,
                    lesson_data={
                        "nuance_type": "honorific",
                        "explanation": (
                            f"«-{tok.form}-» is the subject-honorific suffix (주체 높임법). "
                            "Elevates the grammatical subject of the clause — "
                            "used when the subject is a respected person (teacher, elder, customer). "
                            "Never used for the speaker's own actions."
                        ),
                        "register": "formal",
                        "learner_level": "B1",
                        "source": "heuristic",
                    },
                    confidence=0.92,
                )]
        return []

    # ------------------------------------------------------------------
    # Heuristic mode
    # ------------------------------------------------------------------

    def _politeness_heuristic(
        self, sentence: str, seen: set[str]
    ) -> list[CandidateObject]:
        """Detect politeness register from sentence-final morphology.

        Checks the stripped sentence ending — the most reliable signal without
        morphological analysis because Korean register is always sentence-final.
        """
        text = sentence.rstrip(" .,!?。、·\"'")
        if not text:
            return []

        out: list[CandidateObject] = []

        # Formal polite: -십시오/-으십시오 (imperative), -습니다/-ㅂ니다 (declarative)
        if (text.endswith("십시오") or text.endswith("으십시오")
                or text.endswith("니다")):
            register = "formal_polite"
            surface = "니다" if text.endswith("니다") else "십시오"
            cf = f"nuance:ko:politeness:{register}"
            if cf not in seen:
                seen.add(cf)
                out.append(self._make_politeness(cf, surface, register))

        # Informal polite: sentence ends in 요 (covers 어요/아요/해요/셔요/etc.)
        if text.endswith("요"):
            cf = "nuance:ko:politeness:informal_polite"
            if cf not in seen:
                seen.add(cf)
                out.append(self._make_politeness(cf, "요", "informal_polite"))

        # Plain informal: ends in 어/아/해 WITHOUT 요
        if (not text.endswith("요")
                and (text.endswith("어") or text.endswith("아") or text.endswith("해"))):
            cf = "nuance:ko:politeness:plain_informal"
            if cf not in seen:
                seen.add(cf)
                out.append(self._make_politeness(cf, text[-1], "plain_informal"))

        # Plain formal (written): ends in 는다/ㄴ다/었다/았다/겠다
        _plain_formal_ends = ("는다", "ㄴ다", "었다", "았다", "겠다")
        if any(text.endswith(e) for e in _plain_formal_ends):
            cf = "nuance:ko:politeness:plain_formal"
            if cf not in seen:
                seen.add(cf)
                matched = next(e for e in _plain_formal_ends if text.endswith(e))
                out.append(self._make_politeness(cf, matched, "plain_formal"))

        return out

    def _particles_heuristic(
        self, sentence: str, seen: set[str]
    ) -> list[CandidateObject]:
        """Detect particles by suffix-matching whitespace-split words.

        Particles in Korean are postpositional and appear word-finally — suffix
        matching on space-delimited tokens is sufficient for the most common cases.
        Punctuation is stripped before matching.
        """
        out: list[CandidateObject] = []
        _STRIP = str.maketrans("", "", ".,!?。、·\"'()[]{}~")
        for word_raw in sentence.split():
            word = word_raw.translate(_STRIP)
            if not word:
                continue
            # Direct standalone match (particle alone)
            if word in _PARTICLES:
                citation, role = _PARTICLES[word]
                cf = f"nuance:ko:particle:{citation}"
                if cf not in seen:
                    seen.add(cf)
                    out.append(self._make_particle(cf, word, citation, role))
                continue
            # Suffix match — particle attached to preceding noun (normal Korean)
            for surface, (citation, role) in _PARTICLES.items():
                if word.endswith(surface) and len(word) > len(surface):
                    cf = f"nuance:ko:particle:{citation}"
                    if cf not in seen:
                        seen.add(cf)
                        out.append(self._make_particle(cf, surface, citation, role))
                    break   # longest-first order in dict ensures best match
        return out

    def _negation_heuristic(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        """Detect short negation from standalone 안/못 tokens."""
        if not tokens:
            return []
        out: list[CandidateObject] = []
        for tok in tokens:
            word = getattr(tok, "text", None) or str(tok)
            neg_type = _SHORT_NEG.get(word)
            if neg_type:
                cf = f"nuance:ko:negation:{neg_type}"
                if cf not in seen:
                    seen.add(cf)
                    out.append(self._make_negation(cf, word, neg_type))
        return out

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _classify_ef_surface(self, surface: str) -> str | None:
        for ef in _EF_FORMAL_POLITE:
            if surface.endswith(ef):
                return "formal_polite"
        for ef in _EF_INFORMAL_POLITE:
            if surface.endswith(ef):
                return "informal_polite"
        for ef in _EF_PLAIN_INFORMAL:
            if surface.endswith(ef):
                return "plain_informal"
        for ef in _EF_PLAIN_FORMAL:
            if surface.endswith(ef):
                return "plain_formal"
        return None

    _POLITENESS_META: dict[str, tuple[str, str]] = {
        "formal_polite":   (
            "합쇼체 (formal polite speech)",
            "Used in news broadcasts, formal addresses, and business writing. "
            "Verb endings: -습니다/-ㅂ니다 (declarative), -십시오 (imperative). "
            "Highest register in everyday speech.",
        ),
        "informal_polite": (
            "해요체 (polite informal speech)",
            "The default adult register — used with strangers, in shops, and with teachers. "
            "Marked by sentence-final 요. Most common spoken register for adult learners.",
        ),
        "plain_informal":  (
            "해체 (plain / intimate speech)",
            "Used with close friends, younger people, and in private writing. "
            "Endings: -어/-아/-해 without 요. Using this with strangers or elders is rude.",
        ),
        "plain_formal":    (
            "해라체 (plain formal / literary speech)",
            "Appears in written language, narration, and newspaper headlines. "
            "Endings: -(는)다/-ㄴ다. Direct address in this register can sound harsh.",
        ),
    }

    def _make_politeness(
        self, cf: str, surface: str, register: str
    ) -> CandidateObject:
        label, explanation = self._POLITENESS_META[register]
        return CandidateObject(
            canonical_form=cf,
            surface_form=surface,
            type="nuance",
            label=surface,
            lesson_data={
                "nuance_type": "politeness",
                "register_label": label,
                "explanation": explanation,
                "register": register,
                "learner_level": "A2",
                "source": "heuristic",
            },
            confidence=0.88,
        )

    def _make_particle(
        self, cf: str, surface: str, citation: str, role: str
    ) -> CandidateObject:
        return CandidateObject(
            canonical_form=cf,
            surface_form=surface,
            type="nuance",
            label=surface,
            lesson_data={
                "nuance_type": "particle",
                "explanation": (
                    f"«{citation}» is a Korean postpositional particle (조사): {role}."
                ),
                "register": "neutral",
                "learner_level": "A1",
                "source": "heuristic",
                "particle": citation,
            },
            confidence=0.90,
        )

    _NEG_META: dict[str, tuple[str, str]] = {
        "short_an": (
            "안",
            "Short negation — «안» precedes the verb. Colloquial and natural in speech. "
            "Cannot be used with 하다-compound verbs (공부하다 → 공부 안 하다, not 안 공부하다). "
            "Marks volitional negation: the subject chooses not to act.",
        ),
        "short_mot": (
            "못",
            "Short ability-negation — «못» precedes the verb. "
            "Means the subject is unable to perform the action (lack of ability or external prevention). "
            "Contrast with 안 (volitional) vs 못 (inability).",
        ),
        "long_anta": (
            "지 않다",
            "Long negation — «-지 않다» attaches to the verb stem after removing the citation 다. "
            "More formal and versatile than short 안; works with all verb classes including 하다-compounds. "
            "Preferred in writing and formal speech.",
        ),
        "long_motda": (
            "지 못하다",
            "Long ability-negation — «-지 못하다» is the formal equivalent of short 못. "
            "Used in writing and formal contexts to express inability.",
        ),
    }

    def _make_negation(
        self, cf: str, surface: str, neg_type: str
    ) -> CandidateObject:
        _, explanation = self._NEG_META[neg_type]
        return CandidateObject(
            canonical_form=cf,
            surface_form=surface,
            type="nuance",
            label=surface,
            lesson_data={
                "nuance_type": "negation",
                "explanation": explanation,
                "register": "neutral",
                "learner_level": "A2",
                "source": "heuristic",
                "negation_type": neg_type,
            },
            confidence=0.85,
        )
