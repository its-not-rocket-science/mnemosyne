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
_VERBAL_GOV: dict[str, tuple[str, str]] = {}


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
