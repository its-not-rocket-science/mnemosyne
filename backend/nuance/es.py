"""Spanish nuance extractor — ser/estar, por/para, subjunctive, diminutives, etymology, phrase families."""
from __future__ import annotations

from typing import Any

from backend.schemas.parse import CandidateObject, RelationHint

_DIMINUTIVE_SUFFIXES = (
    "ito", "ita", "itos", "itas",
    "illo", "illa", "illos", "illas",
    "cito", "cita", "citos", "citas",
    "ecito", "ecita",
)

# Verbal government — populate via gen_verbal_government.py.
# Keys: verb lemma (or "verb + preposition" for prepositional verbs).
_VERBAL_GOV: dict[str, tuple[str, str]] = {
    # ── ES additions (gen_verbal_government.py) ──
    'depender de': ('de', "«depender de» (depend on) takes 'de': depende de ti (it depends on you), todo depende del tiempo (everything depends on the weather)"),
    'hablar de': ('de', "«hablar de» (talk about) takes 'de': hablamos de política (we talked about politics). Compare hablar con (talk with) and hablar a (speak to)"),
    'acordarse de': ('de', "«acordarse de» (remember) takes 'de': me acuerdo de ti (I remember you). Reflexive — distinguish from recordar + acc (also: to remember, but transitive)"),
    'olvidarse de': ('de', "«olvidarse de» (forget) takes 'de': me olvidé de la cita (I forgot the appointment). Reflexive — mirror of acordarse de"),
    'darse cuenta de': ('de', "«darse cuenta de» (realize) takes 'de': me di cuenta del error (I realized the error). High-frequency idiomatic phrase"),
    'enamorarse de': ('de', "«enamorarse de» (fall in love with) takes 'de': se enamoró de ella (he fell in love with her). Reflexive"),
    'alegrarse de': ('de', "«alegrarse de» (be glad about) takes 'de': me alegro de verte (I'm happy to see you). Reflexive"),
    'quejarse de': ('de', "«quejarse de» (complain about) takes 'de': se queja del trabajo (he complains about work). Reflexive"),
    'arrepentirse de': ('de', "«arrepentirse de» (regret) takes 'de': me arrepiento de mis palabras (I regret my words). Reflexive — moral/religious register"),
    'burlarse de': ('de', "«burlarse de» (mock) takes 'de': se burla de todos (he mocks everyone). Reflexive"),
    'tratarse de': ('de', "«tratarse de» (be a question of) takes 'de': se trata de un error (it's a matter of an error). Impersonal reflexive"),
    'encargarse de': ('de', "«encargarse de» (take charge of) takes 'de': me encargo de los pagos (I handle the payments). Reflexive"),
    'atreverse a': ('a+infinitive', "«atreverse a» (dare to) takes 'a + infinitive': se atreve a decirlo (he dares to say it). Reflexive"),
    'decidirse a': ('a+infinitive', "«decidirse a» (decide to) takes 'a + infinitive': se decidió a viajar (he decided to travel). Reflexive — distinguish from decidir + infinitive (no preposition)"),
    'comenzar a': ('a+infinitive', "«comenzar a» (begin to) takes 'a + infinitive': comencé a llover (it began to rain). Same pattern as empezar a"),
    'empezar a': ('a+infinitive', "«empezar a» (start to) takes 'a + infinitive': empezó a llover (it started to rain)"),
    'aprender a': ('a+infinitive', "«aprender a» (learn to) takes 'a + infinitive': aprendió a nadar (he learned to swim)"),
    'enseñar a': ('a+infinitive', "«enseñar a» (teach to) takes 'a + infinitive': me enseñó a cocinar (he taught me to cook)"),
    'ayudar a': ('a+infinitive', "«ayudar a» (help to) takes 'a + infinitive': te ayudo a estudiar (I'll help you study)"),
    'negarse a': ('a+infinitive', "«negarse a» (refuse to) takes 'a + infinitive': se negó a hablar (he refused to speak). Reflexive"),
    'acostumbrarse a': ('a+infinitive', "«acostumbrarse a» (get used to) takes 'a + infinitive' or 'a + noun': me acostumbré al frío (I got used to the cold). Reflexive"),
    'tratar de': ('de+infinitive', "«tratar de» (try to) takes 'de + infinitive': trato de entender (I try to understand). Distinguish from tratarse de (be about)"),
    'dejar de': ('de+infinitive', "«dejar de» (stop) takes 'de + infinitive': dejó de fumar (he stopped smoking)"),
    'terminar de': ('de+infinitive', "«terminar de» (finish) takes 'de + infinitive': terminé de leer (I finished reading)"),
    'acabar de': ('de+infinitive', "«acabar de» (have just done) takes 'de + infinitive': acabo de llegar (I just arrived). Idiomatic recent-past construction"),
    'consistir en': ('en', "«consistir en» (consist of) takes 'en': la dieta consiste en frutas (the diet consists of fruits)"),
    'pensar en': ('en', "«pensar en» (think of/about) takes 'en': pienso en ti (I think of you). Distinguish from pensar de (have an opinion about) and pensar + infinitive (intend to)"),
    'confiar en': ('en', "«confiar en» (trust) takes 'en': confío en ti (I trust you)"),
    'insistir en': ('en', "«insistir en» (insist on) takes 'en': insiste en pagar (he insists on paying)"),
    'fijarse en': ('en', "«fijarse en» (notice) takes 'en': fíjate en eso (notice that). Reflexive"),
    'tardar en': ('en+infinitive', "«tardar en» (take long to) takes 'en + infinitive': tardó en llegar (he took a long time to arrive)"),
    'casarse con': ('con', "«casarse con» (marry) takes 'con': se casó con María (he married María). Reflexive — note: marry WITH, not marry someone direct"),
    'soñar con': ('con', "«soñar con» (dream of) takes 'con': sueña con viajar (he dreams of traveling). Distinguish from English 'dream OF' (preposition differs)"),
    'contar con': ('con', "«contar con» (count on) takes 'con': cuento contigo (I count on you)"),
    'encontrarse con': ('con', "«encontrarse con» (run into, meet) takes 'con': me encontré con Juan (I ran into Juan). Reflexive"),
    'preocuparse por': ('por', "«preocuparse por» (worry about) takes 'por': me preocupo por ti (I worry about you). Reflexive"),
    'interesarse por': ('por', "«interesarse por» (be interested in) takes 'por': se interesa por la música (he is interested in music). Reflexive"),
    'luchar por': ('por', "«luchar por» (fight for) takes 'por': lucha por la libertad (he fights for freedom)"),
    'esforzarse por': ('por', "«esforzarse por» (strive to) takes 'por + infinitive': se esfuerza por mejorar (he strives to improve). Reflexive"),
    'asistir a': ('a', "«asistir a» (attend) takes 'a': asistí al concierto (I attended the concert). Spanish 'asistir' = attend, NOT assist (false friend warning)"),
    'renunciar a': ('a', "«renunciar a» (give up, renounce) takes 'a': renunció al cargo (he resigned from the post)"),
    'oler a': ('a', "«oler a» (smell of) takes 'a': huele a café (it smells of coffee)"),
    'saber a': ('a', "«saber a» (taste of) takes 'a': sabe a limón (it tastes of lemon)"),
    'parecerse a': ('a', "«parecerse a» (resemble) takes 'a': se parece a su padre (he looks like his father). Reflexive"),
}


def _text(tok: Any) -> str:
    return tok.text if hasattr(tok, "text") else str(tok)


def _lemma(c: CandidateObject) -> str:
    return c.lesson_data.get("lemma", c.canonical_form)


class SpanishNuanceExtractor:
    language = "es"

    def extract_nuance(
        self,
        sentence: str,
        tokens: list[Any],
        candidates: list[CandidateObject],
        language: str,
    ) -> list[CandidateObject]:
        out: list[CandidateObject] = []
        seen: set[str] = set()
        out.extend(self._ser_estar(candidates, seen))
        out.extend(self._por_para(tokens, seen))
        out.extend(self._subjunctive(candidates, seen))
        out.extend(self._diminutive(tokens, seen))
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
            cf = f"nuance:es:verbal_government:{lemma}"
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
                        "Spanish prepositional verbs select a fixed preposition that often "
                        "shifts the verb's meaning — quedar (to remain) vs. quedar en (to agree to). "
                        f"Required structure: {required_case}."
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
            cf = f"nuance:es:ser_estar:{lemma}"
            if cf in seen:
                continue
            seen.add(cf)
            if lemma == "ser":
                explanation = (
                    "«ser» marks stable, defining qualities: identity, origin, occupation, "
                    "nationality, material. It answers what something fundamentally *is*."
                )
            else:
                explanation = (
                    "«estar» marks transient states, conditions, locations, and results of "
                    "change. It describes how something currently *is*, not what it inherently is."
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

    def _por_para(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for tok in tokens:
            surface = _text(tok)
            low = surface.lower()
            if low not in ("por", "para"):
                continue
            cf = f"nuance:es:por_para:{low}"
            if cf in seen:
                continue
            seen.add(cf)
            if low == "por":
                explanation = (
                    "«por» marks cause/reason, means/instrument, exchange, "
                    "duration, agent in passives, and movement through a space."
                )
            else:
                explanation = (
                    "«para» marks purpose/goal, recipient, destination, deadline, "
                    "and standards or comparisons."
                )
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=surface,
                type="nuance",
                label=surface,
                lesson_data={
                    "nuance_type": "por_para",
                    "explanation": explanation,
                    "register": "neutral",
                    "learner_level": "B1",
                    "source": "heuristic",
                    "preposition": low,
                },
                confidence=0.80,
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
            cf = f"nuance:es:subjunctive:{lemma}"
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
                        "The subjunctive expresses doubt, desire, emotion, or hypothetical "
                        "situations. It appears in subordinate clauses after triggers like "
                        "«querer que», «es posible que», «aunque» (hypothetical), "
                        "«antes de que», «para que»."
                    ),
                    "register": "neutral",
                    "learner_level": "B2",
                    "source": "heuristic",
                    "lemma": lemma,
                },
                confidence=0.75,
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
            cf = f"nuance:es:diminutive:{low}"
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
                        "Spanish diminutive suffixes (-ito/-ita, -illo/-illa) express smallness, "
                        "affection, or informality, and soften requests in casual speech. "
                        "They are extremely frequent in conversational Spanish."
                    ),
                    "register": "informal",
                    "learner_level": "B1",
                    "source": "heuristic",
                    "surface": surface,
                },
                confidence=0.70,
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
        return match_phrase_families([_text(t) for t in tokens], self.language)
