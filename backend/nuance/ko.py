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
    """Learner-facing Korean grammar nuance extractor.

    The extractor deliberately favours a narrow set of high-value, explainable
    Korean grammar features.  Kiwipiepy morpheme tags receive higher confidence;
    plain text suffix checks are capped at medium/low confidence so short,
    ambiguous syllables do not become overconfident lessons.
    """

    language = "ko"

    _PARTICLE_META: dict[str, tuple[str, str, str, str, list[str]]] = {
        "은": ("ko:particle:topic", "topic", "particles_case", "은/는", ["는"]),
        "는": ("ko:particle:topic", "topic", "particles_case", "은/는", ["은"]),
        "이": ("ko:particle:subject", "subject", "particles_case", "이/가", ["가"]),
        "가": ("ko:particle:subject", "subject", "particles_case", "이/가", ["이"]),
        "을": ("ko:particle:object", "object", "particles_case", "을/를", ["를"]),
        "를": ("ko:particle:object", "object", "particles_case", "을/를", ["을"]),
        "에": ("ko:particle:location_time", "location_time", "particles_case", "에", []),
        "에서": ("ko:particle:direction_source", "direction_source", "particles_case", "에서", []),
        "의": ("ko:particle:possessive", "possessive", "particles_case", "의", []),
        "와": ("ko:particle:comitative", "comitative", "particles_case", "와/과/하고/랑/이랑", ["과", "하고", "랑", "이랑"]),
        "과": ("ko:particle:comitative", "comitative", "particles_case", "와/과/하고/랑/이랑", ["와", "하고", "랑", "이랑"]),
        "하고": ("ko:particle:comitative", "comitative", "particles_case", "와/과/하고/랑/이랑", ["와", "과", "랑", "이랑"]),
        "랑": ("ko:particle:comitative", "comitative", "particles_case", "와/과/하고/랑/이랑", ["와", "과", "하고", "이랑"]),
        "이랑": ("ko:particle:comitative", "comitative", "particles_case", "와/과/하고/랑/이랑", ["와", "과", "하고", "랑"]),
    }
    _PARTICLE_EXPLANATIONS: dict[str, str] = {
        "topic": "은/는 marks the sentence topic or contrast: what the sentence is about, not necessarily the grammatical subject.",
        "subject": "이/가 marks the grammatical subject or newly focused information in the clause.",
        "object": "을/를 marks the direct object affected by the verb.",
        "location_time": "에 marks a destination, static location, or time point; learners often contrast it with 에서 for where an action happens.",
        "direction_source": "에서 marks the place where an action occurs or a source meaning ‘from’. It is not the same as static-location 에.",
        "possessive": "의 links nouns possessively or relationally, similar to ‘of’; in speech it may be reduced or omitted.",
        "comitative": "와/과/하고/랑/이랑 links nouns as ‘and’ or ‘with’; 와/과 is more written/formal, while 하고/랑 are common in speech.",
    }

    _ENDING_PATTERNS: tuple[tuple[str, str, str, str, str, float, str], ...] = (
        ("ko:ending:formal_hapsyo", "politeness", "speech_level", "formal_hapsyo", "습니다", 0.82, "합쇼체 formal-polite endings such as -습니다/-ㅂ니다 are used in announcements, workplaces, and formal public speech."),
        ("ko:ending:formal_hapsyo", "politeness", "speech_level", "formal_hapsyo", "ㅂ니다", 0.82, "합쇼체 formal-polite endings such as -습니다/-ㅂ니다 are used in announcements, workplaces, and formal public speech."),
        ("ko:ending:formal_hapsyo", "politeness", "speech_level", "formal_hapsyo", "니다", 0.76, "A sentence-final -니다 usually signals 합쇼체, but the exact stem allomorph is clearer with morphological analysis."),
        ("ko:ending:polite_haeyo", "politeness", "speech_level", "polite_haeyo", "해요", 0.82, "해요체 is the default polite spoken style for adult learners; -해요 is the 하다-verb form."),
        ("ko:ending:polite_haeyo", "politeness", "speech_level", "polite_haeyo", "어요", 0.82, "해요체 polite endings such as -어요/-아요 make speech polite without sounding highly formal."),
        ("ko:ending:polite_haeyo", "politeness", "speech_level", "polite_haeyo", "아요", 0.82, "해요체 polite endings such as -어요/-아요 make speech polite without sounding highly formal."),
        ("ko:ending:polite_haeyo", "politeness", "speech_level", "polite_haeyo", "예요", 0.78, "예요/이에요 is the polite copula pattern; it belongs with 해요체 but depends on the preceding noun shape."),
        ("ko:ending:polite_haeyo", "politeness", "speech_level", "polite_haeyo", "요", 0.76, "Sentence-final -요 is the broad 해요체 politeness marker, including contracted forms such as 가요 that do not end in -어요/-아요."),
        ("ko:ending:plain_informal", "politeness", "speech_level", "plain_informal", "어", 0.48, "Final -어 can be plain informal 해체, but it is short and context-sensitive; treat this as a low-confidence hint."),
        ("ko:ending:plain_informal", "politeness", "speech_level", "plain_informal", "아", 0.48, "Final -아 can be plain informal 해체, but it is short and context-sensitive; treat this as a low-confidence hint."),
        ("ko:ending:plain_declarative", "politeness", "speech_level", "plain_declarative", "다", 0.55, "Final -다 often marks plain written/declarative style, but dictionary citation forms also end in 다; confidence is intentionally low."),
    )

    _CONNECTIVE_META: dict[str, tuple[str, str, str]] = {
        "고": ("ko:connective:go", "connective_sequence", "-고 links actions or clauses in sequence or coordination: ‘and/then’."),
        "지만": ("ko:connective:jiman", "connective_contrast", "-지만 links clauses with contrast: ‘but/although’."),
        "아서": ("ko:connective:aseo_eoseo", "connective_reason_sequence", "-아서/-어서 gives a reason or a natural sequence; it often explains why the next clause happens."),
        "어서": ("ko:connective:aseo_eoseo", "connective_reason_sequence", "-아서/-어서 gives a reason or a natural sequence; it often explains why the next clause happens."),
        "면": ("ko:connective:myeon", "connective_condition", "-(으)면 marks a condition: ‘if/when’."),
        "으면": ("ko:connective:myeon", "connective_condition", "-(으)면 marks a condition: ‘if/when’."),
        "니까": ("ko:connective:nikka", "connective_reason", "-(으)니까 gives a reason or basis, often with a speaker-oriented nuance: ‘because/since’."),
        "으니까": ("ko:connective:nikka", "connective_reason", "-(으)니까 gives a reason or basis, often with a speaker-oriented nuance: ‘because/since’."),
    }

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

        out.extend(self._particles(tokens, sentence, seen, kiwi_mode))
        out.extend(self._endings(tokens, sentence, seen, kiwi_mode))
        out.extend(self._tense_aspect_modality(tokens, sentence, seen, kiwi_mode))
        out.extend(self._negation(tokens, sentence, seen, kiwi_mode))
        out.extend(self._honorific(tokens, sentence, seen, kiwi_mode))
        out.extend(self._connectives(tokens, sentence, seen, kiwi_mode))
        out.extend(self._verbal_government(candidates, seen))
        return out

    # ------------------------------------------------------------------
    # Feature extractors
    # ------------------------------------------------------------------

    def _particles(self, tokens: list[Any], sentence: str, seen: set[str], kiwi_mode: bool) -> list[CandidateObject]:
        out: list[CandidateObject] = []
        if kiwi_mode:
            for tok in tokens:
                tag = str(tok.tag)
                form = tok.form
                if tag in _PARTICLE_TAGS and form in self._PARTICLE_META:
                    cf, role, axis, citation, alternatives = self._PARTICLE_META[form]
                    if cf not in seen:
                        seen.add(cf)
                        out.append(self._make_candidate(
                            cf, form, form, "particle", axis,
                            self._PARTICLE_EXPLANATIONS[role], "A1", 0.93,
                            confidence_note="High confidence: kiwipiepy exposed this as a particle attached to a noun/pronoun.",
                            alternatives=alternatives,
                            extra={"particle": citation, "particle_role": role, "source": "kiwipiepy"},
                        ))
            return out

        strip = str.maketrans("", "", ".,!?。、·\"'()[]{}~")
        for raw in sentence.split():
            word = raw.translate(strip)
            if not word:
                continue
            for surface in sorted(self._PARTICLE_META, key=len, reverse=True):
                if word == surface:
                    # A standalone one-syllable particle is too ambiguous in heuristic mode.
                    if len(surface) <= 1:
                        continue
                    stem = ""
                elif word.endswith(surface):
                    stem = word[:-len(surface)]
                    if len(stem) < 1:
                        continue
                else:
                    continue
                cf, role, axis, citation, alternatives = self._PARTICLE_META[surface]
                if cf not in seen:
                    seen.add(cf)
                    out.append(self._make_candidate(
                        cf, surface, surface, "particle", axis,
                        self._PARTICLE_EXPLANATIONS[role], "A1", 0.72,
                        confidence_note="Medium confidence: detected by a Korean word-final suffix pattern without morpheme tags.",
                        alternatives=alternatives,
                        extra={"particle": citation, "particle_role": role, "source": "heuristic", "host": stem},
                    ))
                break
        return out

    def _endings(self, tokens: list[Any], sentence: str, seen: set[str], kiwi_mode: bool) -> list[CandidateObject]:
        text = sentence.rstrip(" .,!?。、·\"'")
        surfaces = [t.form for t in tokens if kiwi_mode and str(t.tag) == "EF"] or [text]
        out: list[CandidateObject] = []
        for candidate_surface in surfaces:
            for cf, nt, axis, subtype, suffix, confidence, explanation in self._ENDING_PATTERNS:
                if not candidate_surface.endswith(suffix):
                    continue
                if cf in seen:
                    return out
                # Avoid low-value false positives on bare one-syllable input.
                if len(text) <= 1 and suffix in {"어", "아", "다"}:
                    continue
                seen.add(cf)
                note = None if confidence >= 0.8 and kiwi_mode else "Heuristic suffix match; Korean endings can be ambiguous without full clause context."
                out.append(self._make_candidate(
                    cf, suffix, suffix, nt, axis, explanation, "A2", confidence,
                    confidence_note=note,
                    extra={"ending_type": subtype, "source": "kiwipiepy" if kiwi_mode else "heuristic"},
                ))
                return out
        return out

    def _tense_aspect_modality(self, tokens: list[Any], sentence: str, seen: set[str], kiwi_mode: bool) -> list[CandidateObject]:
        forms = [t.form for t in tokens] if kiwi_mode else []
        tags = [str(t.tag) for t in tokens] if kiwi_mode else []
        text = sentence.rstrip(" .,!?。、·\"'")
        out: list[CandidateObject] = []

        past = (kiwi_mode and any(tag == "EP" and form in {"었", "았", "였", "했", "셨"} for form, tag in zip(forms, tags))) or any(x in text for x in ("었", "았", "했"))
        if past:
            self._append_once(out, seen, "ko:tense:past", "았/었/했", "past", "tense_aspect_modality", "Past tense is commonly marked with -았-/-었-; 하다 contracts to 했-. Polite endings can follow it, as in 먹었어요 or 했어요.", "A2", 0.84 if kiwi_mode else 0.74, "Medium confidence: detected from a common past-tense surface pattern." if not kiwi_mode else None)

        progressive = (kiwi_mode and any(forms[i] == "고" and i + 1 < len(forms) and forms[i + 1] == "있" for i in range(len(forms) - 1))) or ("고 있" in text or "고있" in text)
        if progressive:
            self._append_once(out, seen, "ko:aspect:progressive", "고 있다", "progressive", "tense_aspect_modality", "-고 있다 marks an action in progress or an ongoing state, similar to ‘be V-ing’. The 있다 part still conjugates for speech level.", "A2", 0.86 if kiwi_mode else 0.76, "Medium confidence: detected from the common -고 있다 sequence." if not kiwi_mode else None)

        future = (kiwi_mode and any(tag == "EP" and form == "겠" for form, tag in zip(forms, tags))) or "겠" in text or " 거예요" in sentence or " 것이다" in sentence or " 거야" in sentence
        if future:
            surface = "겠" if "겠" in text else "(으)ㄹ 것이다"
            self._append_once(out, seen, "ko:tense:future_prospective", surface, "future_prospective", "tense_aspect_modality", "Korean future/prospective meaning can be marked by -겠- or by -(으)ㄹ 것이다/거예요. -겠- can also express intention or conjecture, so context matters.", "A2", 0.80 if kiwi_mode else 0.70, "Medium confidence: future/prospective forms overlap with intention or conjecture depending on context.")
        return out

    def _negation(self, tokens: list[Any], sentence: str, seen: set[str], kiwi_mode: bool) -> list[CandidateObject]:
        forms = [t.form for t in tokens] if kiwi_mode else []
        tags = [str(t.tag) for t in tokens] if kiwi_mode else []
        words = sentence.replace(".", " ").replace("?", " ").replace("!", " ").split()
        out: list[CandidateObject] = []

        short_an = (kiwi_mode and any(form == "안" and tag == "MAG" for form, tag in zip(forms, tags))) or "안" in words
        if short_an:
            self._append_once(out, seen, "ko:negation:short", "안", "negation", "negation", "안 before a verb/adjective is short negation. It is common in speech and often means the subject does not do the action by choice.", "A2", 0.86 if kiwi_mode else 0.76, "Medium confidence: standalone 안 was detected; scope still depends on the following predicate." if not kiwi_mode else None, {"negation_type": "short_an"})

        short_mot = (kiwi_mode and any(form == "못" and tag == "MAG" for form, tag in zip(forms, tags))) or "못" in words
        if short_mot:
            self._append_once(out, seen, "ko:negation:inability_short", "못", "ability_impossibility", "negation", "못 before a verb means inability or external prevention: ‘cannot / be unable to’. It contrasts with volitional 안.", "A2", 0.86 if kiwi_mode else 0.76, "Medium confidence: standalone 못 was detected; scope still depends on the following predicate." if not kiwi_mode else None, {"negation_type": "short_mot"})

        long_an = (kiwi_mode and any(forms[i] == "지" and i + 1 < len(forms) and forms[i + 1] == "않" for i in range(len(forms) - 1))) or "지 않" in sentence
        if long_an:
            self._append_once(out, seen, "ko:negation:long", "지 않다", "negation", "negation", "-지 않다 is long negation. It attaches after a verb/adjective stem and is often more formal or written than short 안.", "A2", 0.88 if kiwi_mode else 0.78, "Medium confidence: detected from the -지 않- sequence." if not kiwi_mode else None, {"negation_type": "long_anta"})

        long_mot = (kiwi_mode and any(forms[i] == "지" and i + 1 < len(forms) and forms[i + 1] == "못하" for i in range(len(forms) - 1))) or "지 못" in sentence
        if long_mot:
            self._append_once(out, seen, "ko:negation:inability_long", "지 못하다", "ability_impossibility", "negation", "-지 못하다 is the long/formal inability pattern, equivalent to ‘cannot / fail to’. It is common in writing and formal speech.", "A2", 0.88 if kiwi_mode else 0.78, "Medium confidence: detected from the -지 못- sequence." if not kiwi_mode else None, {"negation_type": "long_motda"})
        return out

    def _honorific(self, tokens: list[Any], sentence: str, seen: set[str], kiwi_mode: bool) -> list[CandidateObject]:
        forms = [t.form for t in tokens] if kiwi_mode else []
        tags = [str(t.tag) for t in tokens] if kiwi_mode else []
        hit = (kiwi_mode and any(tag == "EP" and form in _HONORIFIC_EP for form, tag in zip(forms, tags))) or any(x in sentence for x in ("세요", "으세요", "십니다", "으십니다"))
        if not hit or "ko:honorific:si" in seen:
            return []
        seen.add("ko:honorific:si")
        return [self._make_candidate(
            "ko:honorific:si", "시", "시", "honorific", "honorific", "-(으)시- is the subject-honorific marker. It elevates the grammatical subject, as in 선생님이 오세요, and should not be used for the speaker’s own actions.", "B1", 0.90 if kiwi_mode else 0.68,
            confidence_note=None if kiwi_mode else "Medium-low confidence: detected from common honorific surface endings such as -세요; full morphology is safer.",
            extra={"honorific_marker": "-(으)시-", "source": "kiwipiepy" if kiwi_mode else "heuristic"},
        )]

    def _connectives(self, tokens: list[Any], sentence: str, seen: set[str], kiwi_mode: bool) -> list[CandidateObject]:
        out: list[CandidateObject] = []
        if kiwi_mode:
            surfaces = [(t.form, str(t.tag)) for t in tokens]
            for form, tag in surfaces:
                if tag != "EC" or form not in self._CONNECTIVE_META:
                    continue
                cf, nt, explanation = self._CONNECTIVE_META[form]
                self._append_once(out, seen, cf, form, nt, "connective_endings", explanation, "A2", 0.88, None)
            return out

        strip = str.maketrans("", "", ".,!?。、·\"'()[]{}~")
        for raw in sentence.split():
            word = raw.translate(strip)
            for surface in sorted(self._CONNECTIVE_META, key=len, reverse=True):
                if len(word) <= len(surface) or not word.endswith(surface):
                    continue
                cf, nt, explanation = self._CONNECTIVE_META[surface]
                self._append_once(out, seen, cf, surface, nt, "connective_endings", explanation, "A2", 0.70, "Medium confidence: detected by suffix pattern; some endings need clause context.")
                break
        return out

    def _verbal_government(self, candidates: list[CandidateObject], seen: set[str]) -> list[CandidateObject]:
        out = []
        for c in candidates:
            if c.type not in ("vocabulary", "conjugation"):
                continue
            lemma = _lemma(c)
            if lemma not in _VERBAL_GOV:
                continue
            required_case, example = _VERBAL_GOV[lemma]
            cf = f"ko:verbal_government:{lemma}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(self._make_candidate(
                cf, c.surface_form or c.label, c.label, "verbal_government", "particles_case",
                f"{example}. This verb commonly selects a specific Korean particle/case frame: {required_case}.",
                "B1", 0.82,
                extra={"lemma": lemma, "required_case": required_case, "source": "lexical_table"},
            ))
        return out

    # ------------------------------------------------------------------
    # Builders
    # ------------------------------------------------------------------

    def _append_once(
        self,
        out: list[CandidateObject],
        seen: set[str],
        cf: str,
        surface: str,
        nuance_type: str,
        grammar_axis: str,
        explanation: str,
        learner_level: str,
        confidence: float,
        confidence_note: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        if cf in seen:
            return
        seen.add(cf)
        out.append(self._make_candidate(cf, surface, surface, nuance_type, grammar_axis, explanation, learner_level, confidence, confidence_note=confidence_note, extra=extra))

    def _make_candidate(
        self,
        cf: str,
        surface: str,
        label: str,
        nuance_type: str,
        grammar_axis: str,
        explanation: str,
        learner_level: str,
        confidence: float,
        confidence_note: str | None = None,
        drill_prompt: str | None = None,
        drill_answer: str | None = None,
        alternatives: list[str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> CandidateObject:
        lesson_data: dict[str, Any] = {
            "nuance_type": nuance_type,
            "grammar_axis": grammar_axis,
            "surface": surface,
            "explanation": explanation,
            "learner_level": learner_level,
            "drill_prompt": drill_prompt or f"What does «{surface}» signal in this Korean sentence?",
            "drill_answer": drill_answer or explanation,
        }
        if confidence_note:
            lesson_data["confidence_note"] = confidence_note
        if alternatives:
            lesson_data["alternatives"] = alternatives
        if extra:
            lesson_data.update(extra)
        return CandidateObject(
            canonical_form=cf,
            surface_form=surface,
            type="nuance",
            label=label,
            lesson_data=lesson_data,
            confidence=confidence,
        )
