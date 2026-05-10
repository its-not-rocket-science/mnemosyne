"""French nuance extractor — tu/vous register, ne explétif, subjunctive, liaison, etymology."""
from __future__ import annotations

from typing import Any

from backend.schemas.parse import CandidateObject, RelationHint

_NE_NEG_PAIRS = frozenset({
    "pas", "jamais", "point", "guère", "rien", "plus",
    "personne", "aucun", "aucune", "nul", "nulle",
})

_INFORMAL_PRONOUNS = frozenset({"tu", "ton", "ta", "tes", "toi"})
_FORMAL_PRONOUNS = frozenset({"vous", "votre", "vos"})

_LIAISON_TRIGGERS = frozenset({
    "vous", "nous", "on", "les", "des", "mes", "ses", "tes", "ces",
    "mon", "ton", "son", "en", "un", "aux",
})
_VOWELS = frozenset("aeiouéàèùêîôûœæ")

# Verbal government — populate via gen_verbal_government.py.
_VERBAL_GOV: dict[str, tuple[str, str]] = {
    # ── FR additions (gen_verbal_government.py) ──
    'penser à': ('à', "«penser à» (think of) takes 'à': je pense à toi (I think of you). Distinguish from penser de (have an opinion about): que penses-tu de ce film? (what do you think of this film?)"),
    'réfléchir à': ('à', "«réfléchir à» (reflect on) takes 'à': je réfléchis à la question (I'm thinking about the question). Stronger and more deliberate than penser à"),
    'jouer à': ('à', "«jouer à» (play a game) takes 'à': jouer au tennis, à la corde (play tennis, jump rope). Distinguish from jouer de + instrument (play music)"),
    'jouer de': ('de', "«jouer de» (play an instrument) takes 'de': jouer du piano (play piano), jouer de la guitare. Mirror of jouer à"),
    'croire à': ('à', "«croire à» (believe in the existence of) takes 'à': croire au père Noël (believe in Santa). Distinguish from croire en (have faith in): croire en Dieu, en soi-même"),
    'ressembler à': ('à', "«ressembler à» (resemble) takes 'à': il ressemble à son père (he looks like his father)"),
    'faire attention à': ('à', "«faire attention à» (pay attention to) takes 'à': fais attention à toi (take care of yourself)"),
    "s'attendre à": ('à', "«s'attendre à» (expect) takes 'à': je m'attendais à mieux (I expected better). Reflexive — distinguish from attendre + COD (wait for)"),
    "s'habituer à": ('à', "«s'habituer à» (get used to) takes 'à': je m'habitue au climat (I'm getting used to the climate). Reflexive"),
    "s'intéresser à": ('à', "«s'intéresser à» (be interested in) takes 'à': il s'intéresse à la musique (he is interested in music). Reflexive"),
    'tenir à': ('à', "«tenir à» (be attached to / insist on) takes 'à': je tiens à toi (I care about you), je tiens à le faire (I insist on doing it)"),
    'renoncer à': ('à', "«renoncer à» (give up) takes 'à': il a renoncé à son rêve (he gave up his dream)"),
    'réussir à': ('à+infinitive', "«réussir à» (succeed in) takes 'à + infinitive': il a réussi à finir (he managed to finish). With noun: réussir un examen (no preposition)"),
    'parvenir à': ('à+infinitive', "«parvenir à» (manage to / reach) takes 'à': je parviens à comprendre (I manage to understand). Formal register"),
    'hésiter à': ('à+infinitive', "«hésiter à» (hesitate to) takes 'à + infinitive': il hésite à parler (he hesitates to speak)"),
    'commencer à': ('à+infinitive', "«commencer à» (begin to) takes 'à + infinitive': il commence à pleuvoir (it's starting to rain). Also commencer par + infinitive (begin by)"),
    'apprendre à': ('à+infinitive', "«apprendre à» (learn to) takes 'à + infinitive': il apprend à nager (he is learning to swim)"),
    'aider à': ('à+infinitive', "«aider à» (help to) takes 'à + infinitive': je l'aide à étudier (I help him study)"),
    'inviter à': ('à+infinitive', "«inviter à» (invite to) takes 'à + infinitive': il m'a invité à dîner (he invited me to dinner)"),
    'obliger à': ('à+infinitive', "«obliger à» (force to) takes 'à + infinitive': il m'oblige à partir (he forces me to leave)"),
    'parler de': ('de', "«parler de» (talk about) takes 'de': nous parlons de politique (we're talking about politics). Distinguish from parler à (speak to a person)"),
    'rêver de': ('de', "«rêver de» (dream of) takes 'de': il rêve de partir (he dreams of leaving)"),
    'profiter de': ('de', "«profiter de» (take advantage of) takes 'de': profite des vacances (enjoy your vacation)"),
    'douter de': ('de', "«douter de» (doubt) takes 'de': je doute de ses paroles (I doubt his words). Distinguish from se douter de (suspect)"),
    'se servir de': ('de', "«se servir de» (use) takes 'de': je me sers d'un ordinateur (I use a computer). Reflexive"),
    'se souvenir de': ('de', "«se souvenir de» (remember) takes 'de': je me souviens de toi (I remember you). Reflexive"),
    'se moquer de': ('de', "«se moquer de» (make fun of) takes 'de': il se moque de moi (he's making fun of me). Reflexive"),
    "s'occuper de": ('de', "«s'occuper de» (take care of) takes 'de': il s'occupe des enfants (he takes care of the children). Reflexive"),
    'se rendre compte de': ('de', "«se rendre compte de» (realize) takes 'de': je me rends compte de l'erreur (I realize the error). Reflexive"),
    'avoir besoin de': ('de', "«avoir besoin de» (need) takes 'de': j'ai besoin de toi (I need you). Idiomatic possessive construction"),
    'avoir envie de': ('de', "«avoir envie de» (feel like / want) takes 'de': j'ai envie de partir (I feel like leaving)"),
    'finir de': ('de+infinitive', "«finir de» (finish) takes 'de + infinitive': j'ai fini de manger (I finished eating). Distinguish from finir par (end up doing)"),
    'essayer de': ('de+infinitive', "«essayer de» (try to) takes 'de + infinitive': j'essaie de comprendre (I try to understand)"),
    'décider de': ('de+infinitive', "«décider de» (decide to) takes 'de + infinitive': il a décidé de partir (he decided to leave). Reflexive form se décider à uses 'à'"),
    'refuser de': ('de+infinitive', "«refuser de» (refuse to) takes 'de + infinitive': il refuse de parler (he refuses to speak)"),
    'regretter de': ('de+infinitive', "«regretter de» (regret) takes 'de + infinitive': je regrette de l'avoir dit (I regret having said it)"),
    'venir de': ('de+infinitive', "«venir de» (have just done) takes 'de + infinitive': je viens d'arriver (I just arrived). Idiomatic recent-past construction"),
    'manquer de': ('de', "«manquer de» (lack) takes 'de': je manque de temps (I lack time). Distinguish from manquer à (miss someone)"),
    'compter sur': ('sur', "«compter sur» (count on) takes 'sur': je compte sur toi (I'm counting on you). Distinguish from compter + COD (count, calculate)"),
    'insister sur': ('sur', "«insister sur» (insist on) takes 'sur': il insiste sur ce point (he insists on this point)"),
    'donner sur': ('sur', "«donner sur» (look out onto) takes 'sur': la fenêtre donne sur le jardin (the window opens onto the garden)"),
    'voter pour': ('pour', "«voter pour» (vote for) takes 'pour': il a voté pour Macron (he voted for Macron). Mirror of voter contre"),
    'se battre pour': ('pour', "«se battre pour» (fight for) takes 'pour': elle se bat pour ses droits (she fights for her rights). Reflexive"),
    'se passionner pour': ('pour', "«se passionner pour» (be passionate about) takes 'pour': il se passionne pour le cinéma (he is passionate about cinema). Reflexive"),
}


def _text(tok: Any) -> str:
    return tok.text if hasattr(tok, "text") else str(tok)


def _lemma(c: CandidateObject) -> str:
    return c.lesson_data.get("lemma", c.canonical_form)


class FrenchNuanceExtractor:
    language = "fr"

    def extract_nuance(
        self,
        sentence: str,
        tokens: list[Any],
        candidates: list[CandidateObject],
        language: str,
    ) -> list[CandidateObject]:
        out: list[CandidateObject] = []
        seen: set[str] = set()
        out.extend(self._tu_vous(tokens, seen))
        out.extend(self._ne_expletif(tokens, seen))
        out.extend(self._subjunctive(candidates, seen))
        out.extend(self._liaison(tokens, seen))
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
            cf = f"nuance:fr:verbal_government:{lemma}"
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
                        "French prepositional verbs select a fixed preposition (à, de, en, …) "
                        "that often shifts the verb's meaning. The infinitive complement "
                        f"pattern (penser à vs. penser de) is especially error-prone for learners. Required structure: {required_case}."
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

    def _tu_vous(
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
            cf = f"nuance:fr:tu_vous:{register}"
            if cf in seen:
                continue
            seen.add(cf)
            if register == "informal":
                explanation = (
                    "«tu» (tutoiement) is the singular informal 'you', used with friends, "
                    "family, children, and peers. Using «tu» with strangers or in formal "
                    "contexts can feel overfamiliar or rude."
                )
            else:
                explanation = (
                    "«vous» (vouvoiement) is the polite singular 'you' used with strangers, "
                    "superiors, and in formal settings, as well as the standard plural 'you'. "
                    "Switching to «tu» signals a social shift toward familiarity."
                )
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=_text(tok),
                type="nuance",
                label=_text(tok),
                lesson_data={
                    "nuance_type": "tu_vous_register",
                    "explanation": explanation,
                    "register": register,
                    "learner_level": "A2",
                    "source": "heuristic",
                    "pronoun": low,
                },
                confidence=0.90,
            ))
        return out

    def _ne_expletif(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        """Flag «ne» not followed by a negation complement within 3 tokens."""
        out = []
        texts = [_text(t).lower() for t in tokens]
        for i, low in enumerate(texts):
            if low != "ne":
                continue
            window = texts[i + 1:i + 4]
            if any(w in _NE_NEG_PAIRS for w in window):
                continue
            cf = "nuance:fr:ne_expletif"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=_text(tokens[i]),
                type="nuance",
                label=_text(tokens[i]),
                lesson_data={
                    "nuance_type": "ne_expletif",
                    "explanation": (
                        "The pleonastic «ne» (ne explétif) appears in formal/literary French "
                        "in subordinate clauses after verbs of fearing, preventing, or doubting, "
                        "and in comparisons. It carries no negative meaning: «j'ai peur qu'il "
                        "ne parte» = 'I fear he will leave', not 'will not leave'. "
                        "It is regularly omitted in spoken French."
                    ),
                    "register": "formal",
                    "learner_level": "C1",
                    "source": "heuristic",
                },
                confidence=0.55,
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
            if "sub" not in mood:
                continue
            lemma = c.lesson_data.get("lemma", c.canonical_form)
            cf = f"nuance:fr:subjunctive:{lemma}"
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
                        "The French subjonctif is required after triggers: verbs of wanting "
                        "(vouloir que), emotion (être content que), doubt (douter que), "
                        "impersonal expressions (il faut que), and conjunctions like "
                        "«bien que», «pour que», «avant que»."
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

    def _liaison(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        """Flag mandatory liaison contexts (trigger word before vowel-initial word)."""
        out = []
        surfaces = [_text(t) for t in tokens]
        for i, surface in enumerate(surfaces):
            if surface.lower() not in _LIAISON_TRIGGERS:
                continue
            if i + 1 >= len(surfaces):
                continue
            next_word = surfaces[i + 1].lstrip("'\"«»")
            if not next_word or next_word[0].lower() not in _VOWELS:
                continue
            cf = f"nuance:fr:liaison:{surface.lower()}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=surface,
                type="nuance",
                label=surface,
                lesson_data={
                    "nuance_type": "liaison",
                    "explanation": (
                        f"Mandatory liaison: «{surface}» precedes a vowel-initial word. "
                        "The normally-silent final consonant is pronounced and linked to "
                        "the next syllable. This is obligatory in formal and standard speech."
                    ),
                    "register": "neutral",
                    "learner_level": "A2",
                    "source": "heuristic",
                    "trigger": surface.lower(),
                    "next_word": surfaces[i + 1],
                },
                confidence=0.75,
            ))
        return out
