"""Portuguese nuance extractor — você/tu register, ser/estar, subjunctive, diminutives, personal infinitive."""
from __future__ import annotations

from typing import Any

from backend.nuance.interface import NuanceExtractorMixin
from backend.schemas.parse import CandidateObject, RelationHint

_DIMINUTIVE_SUFFIXES = (
    "inho", "inha", "inhos", "inhas",
    "zinho", "zinha", "zinhos", "zinhas",
    "ito", "ita", "itos", "itas",
)

_INFORMAL_PRONOUNS = frozenset({"tu", "te", "teu", "tua", "teus", "tuas"})
_FORMAL_PRONOUNS = frozenset({"você", "voce", "o senhor", "a senhora", "vossa"})

_PERSONAL_INF_SUFFIXES = ("ares", "ermos", "erdes", "erem", "irmos", "irdes", "irem", "armos", "ardes", "arem")

# Verbal government — populate via gen_verbal_government.py.
_VERBAL_GOV: dict[str, tuple[str, str]] = {
    # ── PT additions (gen_verbal_government.py) ──
    'gostar de': ('de', "«gostar de» (like) takes 'de': gosto de café (I like coffee). Portuguese requires 'de' where Spanish gustar uses dative inversion"),
    'depender de': ('de', "«depender de» (depend on) takes 'de': depende de você (it depends on you)"),
    'precisar de': ('de', "«precisar de» (need) takes 'de' (PT-PT) or no preposition (BR): preciso de ajuda (I need help). BR usage often drops 'de': preciso ajuda"),
    'lembrar-se de': ('de', "«lembrar-se de» (remember) takes 'de': lembro-me de você (I remember you). Reflexive — non-reflexive lembrar uses no preposition"),
    'esquecer-se de': ('de', "«esquecer-se de» (forget) takes 'de': esqueci-me da chave (I forgot the key). Reflexive"),
    'queixar-se de': ('de', "«queixar-se de» (complain about) takes 'de': queixa-se do trabalho (he complains about work). Reflexive"),
    'despedir-se de': ('de', "«despedir-se de» (say goodbye to) takes 'de': despediu-se da família (he said goodbye to the family). Reflexive"),
    'aproveitar-se de': ('de', "«aproveitar-se de» (take advantage of) takes 'de': aproveitou-se da situação (he took advantage of the situation). Reflexive"),
    'rir-se de': ('de', "«rir-se de» (laugh at) takes 'de': ri-se de mim (he laughed at me). Reflexive — non-reflexive rir uses 'de' too"),
    'abusar de': ('de', "«abusar de» (abuse, overuse) takes 'de': não abuse do álcool (don't abuse alcohol)"),
    'desistir de': ('de+infinitive', "«desistir de» (give up) takes 'de + infinitive': desistiu de tentar (he gave up trying)"),
    'parar de': ('de+infinitive', "«parar de» (stop doing) takes 'de + infinitive': parou de fumar (he stopped smoking)"),
    'deixar de': ('de+infinitive', "«deixar de» (stop, cease to) takes 'de + infinitive': deixou de chover (it stopped raining)"),
    'terminar de': ('de+infinitive', "«terminar de» (finish doing) takes 'de + infinitive': terminei de comer (I finished eating)"),
    'acabar de': ('de+infinitive', "«acabar de» (have just done) takes 'de + infinitive': acabo de chegar (I just arrived). Idiomatic recent-past"),
    'tratar de': ('de+infinitive', "«tratar de» (try to / deal with) takes 'de + infinitive': trate de estudar (try to study). Also: tratar de + noun (handle)"),
    'pensar em': ('em', "«pensar em» (think of/about) takes 'em': penso em você (I think of you). Distinguish from pensar de (have an opinion)"),
    'acreditar em': ('em', "«acreditar em» (believe in) takes 'em': acredito em você (I believe in you)"),
    'confiar em': ('em', "«confiar em» (trust) takes 'em': confio em você (I trust you)"),
    'insistir em': ('em', "«insistir em» (insist on) takes 'em': insiste em pagar (he insists on paying)"),
    'consistir em': ('em', "«consistir em» (consist of) takes 'em': consiste em frutas (it consists of fruits)"),
    'tocar em': ('em', "«tocar em» (touch / bring up) takes 'em': não toque em mim (don't touch me), tocar no assunto (raise the topic)"),
    'contar com': ('com', "«contar com» (count on) takes 'com': conto com você (I count on you)"),
    'casar com': ('com', "«casar com» (marry) takes 'com': casou-se com Maria (he married Maria). Spanish casarse con — same pattern"),
    'comparar com': ('com', "«comparar com» (compare with) takes 'com': compare com isto (compare with this). Also comparar a (more formal)"),
    'sonhar com': ('com', "«sonhar com» (dream of) takes 'com': sonhei contigo (I dreamed of you). Same pattern as Spanish soñar con"),
    'preocupar-se com': ('com', "«preocupar-se com» (worry about) takes 'com': preocupo-me com você (I worry about you). Reflexive"),
    'dar-se com': ('com', "«dar-se com» (get along with) takes 'com': dou-me bem com ele (I get along well with him). Reflexive"),
    'dirigir-se a': ('a', "«dirigir-se a» (address oneself to / head to) takes 'a': dirigiu-se ao público (he addressed the public). Reflexive"),
    'recorrer a': ('a', "«recorrer a» (resort to) takes 'a': recorreu à violência (he resorted to violence)"),
    'dedicar-se a': ('a', "«dedicar-se a» (dedicate oneself to) takes 'a': dedica-se à música (he dedicates himself to music). Reflexive"),
    'habituar-se a': ('a', "«habituar-se a» (get used to) takes 'a': habituei-me ao clima (I got used to the climate). Reflexive"),
    'atrever-se a': ('a+infinitive', "«atrever-se a» (dare to) takes 'a + infinitive': atreveu-se a falar (he dared to speak). Reflexive"),
    'começar a': ('a+infinitive', "«começar a» (start to) takes 'a + infinitive': começou a chover (it started raining)"),
    'ensinar a': ('a+infinitive', "«ensinar a» (teach to) takes 'a + infinitive': ensinou-me a cozinhar (he taught me to cook)"),
    'aprender a': ('a+infinitive', "«aprender a» (learn to) takes 'a + infinitive': aprendi a nadar (I learned to swim)"),
    'ajudar a': ('a+infinitive', "«ajudar a» (help to) takes 'a + infinitive': ajudo-te a estudar (I help you study)"),
    'obrigar a': ('a+infinitive', "«obrigar a» (force to) takes 'a + infinitive': obrigou-me a partir (he forced me to leave)"),
    'decidir-se a': ('a+infinitive', "«decidir-se a» (decide to) takes 'a + infinitive': decidiu-se a viajar (he decided to travel). Reflexive — distinguish from decidir + infinitive (no prep)"),
    'esforçar-se por': ('por+infinitive', "«esforçar-se por» (strive to) takes 'por + infinitive': esforça-se por aprender (he strives to learn). Reflexive — alternative: esforçar-se em"),
    'optar por': ('por', "«optar por» (opt for) takes 'por': optou pelo silêncio (he opted for silence)"),
    'lutar por': ('por', "«lutar por» (fight for) takes 'por': luta pela liberdade (she fights for freedom)"),
    'esperar por': ('por', "«esperar por» (wait for) takes 'por': espero por ti (I'm waiting for you). Distinguish from esperar (hope) without prep"),
    'interessar-se por': ('por', "«interessar-se por» (be interested in) takes 'por': interessa-se por arte (he is interested in art). Reflexive"),
    'perguntar por': ('por', "«perguntar por» (ask about/after) takes 'por': perguntou por ti (he asked about you). Distinguish from perguntar a alguém (ask someone)"),
    'orgulhar-se de': ('de', "«orgulhar-se de» (be proud of) takes 'de': orgulha-se dos filhos (he is proud of his children). Reflexive"),
}


def _text(tok: Any) -> str:
    return tok.text if hasattr(tok, "text") else str(tok)


def _lemma(c: CandidateObject) -> str:
    return c.lesson_data.get("lemma", c.canonical_form)


class PortugueseNuanceExtractor(NuanceExtractorMixin):
    language = "pt"

    def extract_nuance(
        self,
        sentence: str,
        tokens: list[Any],
        candidates: list[CandidateObject],
        language: str,
    ) -> list[CandidateObject]:
        out: list[CandidateObject] = []
        seen: set[str] = set()
        out.extend(self._register(tokens, seen))
        out.extend(self._ser_estar(candidates, seen))
        out.extend(self._subjunctive(candidates, seen))
        out.extend(self._diminutive(tokens, seen))
        out.extend(self._personal_infinitive(tokens, seen))
        out.extend(self._verbal_government(candidates, seen))
        out.extend(self._etymology(candidates, seen))
        out.extend(self._phrase_families(tokens))
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
            cf = f"nuance:pt:verbal_government:{lemma}"
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
                        "Portuguese prepositional verbs select a fixed preposition (a, de, em, "
                        "com, …) that shifts meaning — gostar de (to like), depender de (to "
                        f"depend on). BR/PT regional differences exist for some verbs. Required structure: {required_case}."
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

    def _register(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for tok in tokens:
            low = _text(tok).lower()
            if low in _INFORMAL_PRONOUNS:
                register = "informal"
            elif low in _FORMAL_PRONOUNS:
                register = "formal"
            else:
                continue
            cf = f"nuance:pt:register:{register}"
            if cf in seen:
                continue
            seen.add(cf)
            if register == "informal":
                explanation = (
                    "«tu» is the informal second-person singular used with friends, "
                    "family, and peers, primarily in European Portuguese. In Brazilian "
                    "Portuguese, «você» is used even in informal contexts where European "
                    "Portuguese would use «tu»."
                )
            else:
                explanation = (
                    "«você» is the standard second-person form in Brazilian Portuguese, "
                    "functioning as both formal and informal 'you'. In European Portuguese "
                    "it retains a more formal or distancing register. «o senhor»/«a senhora» "
                    "are the most formal equivalents."
                )
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=_text(tok),
                type="nuance",
                label=_text(tok),
                lesson_data={
                    "nuance_type": "voce_tu_register",
                    "explanation": explanation,
                    "register": register,
                    "learner_level": "A2",
                    "source": "heuristic",
                    "pronoun": low,
                },
                confidence=0.85,
            ))
        return out

    def _ser_estar(
        self, candidates: list[CandidateObject], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for c in candidates:
            if c.type != "conjugation":
                continue
            lemma = c.lesson_data.get("lemma", "")
            if lemma not in ("ser", "estar"):
                continue
            cf = f"nuance:pt:ser_estar:{lemma}"
            if cf in seen:
                continue
            seen.add(cf)
            if lemma == "ser":
                explanation = (
                    "«ser» marks permanent or defining qualities: identity, nationality, "
                    "occupation, origin, material, and intrinsic characteristics. "
                    "It answers what something fundamentally is."
                )
            else:
                explanation = (
                    "«estar» marks transient states, moods, conditions, locations, and the "
                    "progressive aspect (estar + gerúndio / estar a + infinitivo in EP). "
                    "It describes how something currently is, not what it inherently is."
                )
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=c.surface_form,
                type="nuance",
                label=c.label,
                lesson_data={
                    "nuance_type": "ser_estar",
                    "explanation": explanation,
                    "register": "neutral",
                    "learner_level": "A2",
                    "source": "heuristic",
                    "lemma": lemma,
                },
                confidence=0.85,
                relation_hints=[RelationHint(
                    relation_type="nuance_of",
                    target_canonical_form=lemma,
                    target_type="vocabulary",
                )],
            ))
        return out

    def _subjunctive(
        self, candidates: list[CandidateObject], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for c in candidates:
            if c.type != "conjugation":
                continue
            mood = str(c.lesson_data.get("mood", "")).lower()
            mood_raw = str(c.lesson_data.get("mood_raw", ""))
            if "sub" not in mood and "Sub" not in mood_raw:
                continue
            lemma = c.lesson_data.get("lemma", c.canonical_form)
            cf = f"nuance:pt:subjunctive:{lemma}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=c.surface_form,
                type="nuance",
                label=c.label,
                lesson_data={
                    "nuance_type": "subjunctive_trigger",
                    "explanation": (
                        "The Portuguese subjunctive (conjuntivo/subjuntivo) is required "
                        "after verbs of wanting (querer que), emotion (ficar feliz que), "
                        "doubt (duvidar que), and conjunctions like «para que», «embora», "
                        "«antes que», «caso». Portuguese uses the subjunctive more "
                        "frequently than Spanish, including in temporal clauses with «quando» "
                        "for future events: «quando chegar» (when you arrive)."
                    ),
                    "register": "neutral",
                    "learner_level": "B2",
                    "source": "heuristic",
                    "lemma": lemma,
                },
                confidence=0.80,
                relation_hints=[RelationHint(
                    relation_type="nuance_of",
                    target_canonical_form=lemma,
                    target_type="vocabulary",
                )],
            ))
        return out

    def _diminutive(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for tok in tokens:
            surface = _text(tok)
            low = surface.lower()
            if len(low) < 6:
                continue
            if not any(low.endswith(suf) for suf in _DIMINUTIVE_SUFFIXES):
                continue
            cf = f"nuance:pt:diminutive:{low}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=surface,
                type="nuance",
                label=surface,
                lesson_data={
                    "nuance_type": "diminutive",
                    "explanation": (
                        "Portuguese diminutive suffixes (-inho/-inha, -zinho/-zinha) express "
                        "smallness, affection, or soften requests. They are particularly "
                        "frequent in Brazilian Portuguese, where they extend beyond size to "
                        "politeness, endearment, and even irony."
                    ),
                    "register": "informal",
                    "learner_level": "B1",
                    "source": "heuristic",
                    "surface": surface,
                },
                confidence=0.70,
            ))
        return out

    def _personal_infinitive(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        """Flag inflected infinitives — a feature unique to Portuguese among Romance languages."""
        out = []
        for tok in tokens:
            surface = _text(tok)
            low = surface.lower()
            if len(low) < 5:
                continue
            if not any(low.endswith(suf) for suf in _PERSONAL_INF_SUFFIXES):
                continue
            cf = f"nuance:pt:personal_infinitive:{low}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=surface,
                type="nuance",
                label=surface,
                lesson_data={
                    "nuance_type": "personal_infinitive",
                    "explanation": (
                        "The inflected (personal) infinitive is unique to Portuguese among "
                        "Romance languages. It agrees with its own subject in person and number: "
                        "«para eles chegarem» (for them to arrive) vs «para eu chegar». "
                        "It is obligatory when the infinitive clause has a different subject "
                        "from the main clause, and optional when subjects are the same."
                    ),
                    "register": "neutral",
                    "learner_level": "B2",
                    "source": "heuristic",
                    "surface": surface,
                },
                confidence=0.65,
            ))
        return out

    def _etymology(
        self, candidates: list[CandidateObject], seen: set[str]
    ) -> list[CandidateObject]:
        from backend.dictionary.etymology import DEFAULT_STORE
        out = []
        for c in candidates:
            if c.type != "vocabulary":
                continue
            lemma = c.lesson_data.get("lemma") or c.canonical_form
            entry = DEFAULT_STORE.get(self.language, lemma)
            if not entry:
                continue
            cf = f"nuance:{self.language}:etymology:{lemma.lower()}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=c.surface_form,
                type="nuance",
                label=c.label,
                lesson_data={
                    "nuance_type": "etymology",
                    "explanation": entry.origin_summary,
                    "register": "neutral",
                    "learner_level": "B1",
                    "source": entry.source_type,
                    "etymology": entry.to_lesson_data(),
                },
                confidence=0.85,
                relation_hints=[RelationHint(
                    relation_type="nuance_of",
                    target_canonical_form=lemma,
                    target_type="vocabulary",
                )],
            ))
        return out

    def _phrase_families(self, tokens: list[Any]) -> list[CandidateObject]:
        from backend.dictionary.phrase_families import match_phrase_families
        sentence_text = " ".join(_text(t) for t in tokens)
        legacy    = match_phrase_families([_text(t) for t in tokens], self.language)
        generated = self._cultural_references(sentence_text)
        return self._merge_candidates(legacy, generated)
