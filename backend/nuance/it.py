"""Italian nuance extractor — Lei/tu register, essere/avere, subjunctive, diminutives."""
from __future__ import annotations

from typing import Any

from backend.schemas.parse import CandidateObject, RelationHint

_DIMINUTIVE_SUFFIXES = (
    "ino", "ina", "ini", "ine",
    "etto", "etta", "etti", "ette",
    "ello", "ella", "elli", "elle",
    "uccio", "uccia", "ucci", "ucce",
    "olino", "olina",
)

_INFORMAL_PRONOUNS = frozenset({"tu", "ti", "tuo", "tua", "tuoi", "tue", "te"})
_FORMAL_PRONOUNS = frozenset({"lei", "ella", "suo", "sua", "suoi", "sue"})

# Verbal government — populate via gen_verbal_government.py.
_VERBAL_GOV: dict[str, tuple[str, str]] = {
    # ── IT additions (gen_verbal_government.py) ──
    'pensare a': ('a', "«pensare a» (think of) takes 'a': penso a te (I think of you). Distinguish from pensare di + infinitive (intend to): penso di partire (I plan to leave)"),
    'credere a': ('a', "«credere a» (believe in/trust) takes 'a': non credo a queste storie (I don't believe these stories). Distinguish from credere in (have faith in): credere in Dio"),
    'giocare a': ('a', "«giocare a» (play a game) takes 'a': gioco a tennis (I play tennis). Distinguish from suonare (play music) — Italian splits the verbs unlike English/French"),
    'assomigliare a': ('a', "«assomigliare a» (resemble) takes 'a': assomiglia a sua madre (he resembles his mother)"),
    'rivolgersi a': ('a', "«rivolgersi a» (turn to / address oneself to) takes 'a': mi rivolgo a te (I'm addressing you). Reflexive"),
    'abituarsi a': ('a', "«abituarsi a» (get used to) takes 'a': mi sono abituato al freddo (I got used to the cold). Reflexive"),
    'appartenere a': ('a', "«appartenere a» (belong to) takes 'a': questo libro appartiene a me (this book belongs to me)"),
    'rinunciare a': ('a', "«rinunciare a» (give up) takes 'a': ha rinunciato al lavoro (he gave up the job)"),
    'partecipare a': ('a', "«partecipare a» (participate in) takes 'a': partecipo alla riunione (I'm participating in the meeting)"),
    'assistere a': ('a', "«assistere a» (attend, witness) takes 'a': ho assistito al concerto (I attended the concert). Italian assistere is mostly attendance, not assistance"),
    'riuscire a': ('a+infinitive', "«riuscire a» (succeed in) takes 'a + infinitive': sono riuscito a finire (I managed to finish)"),
    'decidersi a': ('a+infinitive', "«decidersi a» (decide to) takes 'a + infinitive': si è deciso a parlare (he decided to speak). Reflexive — distinguish from decidere di (no reflexive)"),
    'cominciare a': ('a+infinitive', "«cominciare a» (begin to) takes 'a + infinitive': comincia a piovere (it's starting to rain). Same as iniziare a"),
    'imparare a': ('a+infinitive', "«imparare a» (learn to) takes 'a + infinitive': imparo a nuotare (I'm learning to swim)"),
    'insegnare a': ('a+infinitive', "«insegnare a» (teach to) takes 'a + infinitive': mi ha insegnato a cucinare (he taught me to cook)"),
    'aiutare a': ('a+infinitive', "«aiutare a» (help to) takes 'a + infinitive': ti aiuto a studiare (I'll help you study)"),
    'invitare a': ('a+infinitive', "«invitare a» (invite to) takes 'a + infinitive': mi ha invitato a cena (he invited me to dinner)"),
    'andare a': ('a+infinitive', "«andare a» (go to do) takes 'a + infinitive': vado a comprare il pane (I'm going to buy bread)"),
    'venire a': ('a+infinitive', "«venire a» (come to do) takes 'a + infinitive': è venuto a trovarmi (he came to visit me)"),
    'provare a': ('a+infinitive', "«provare a» (try to) takes 'a + infinitive': prova a capire (try to understand). Distinguish from provare + COD (try a thing)"),
    'mettersi a': ('a+infinitive', "«mettersi a» (set about doing) takes 'a + infinitive': si è messo a piangere (he started crying). Reflexive — emphasizes onset"),
    'costringere a': ('a+infinitive', "«costringere a» (force to) takes 'a + infinitive': mi ha costretto a partire (he forced me to leave)"),
    'parlare di': ('di', "«parlare di» (talk about) takes 'di': parliamo di politica (we're talking about politics). Compare parlare a (speak to) and parlare con (speak with)"),
    'ricordarsi di': ('di', "«ricordarsi di» (remember) takes 'di': mi ricordo di te (I remember you). Reflexive — also: ricordare + COD without reflexive"),
    'dimenticarsi di': ('di', "«dimenticarsi di» (forget) takes 'di': mi sono dimenticato dell'appuntamento (I forgot the appointment). Reflexive form"),
    'rendersi conto di': ('di', "«rendersi conto di» (realize) takes 'di': mi rendo conto dell'errore (I realize the error). Reflexive idiom"),
    'accorgersi di': ('di', "«accorgersi di» (notice) takes 'di': mi sono accorto del rumore (I noticed the noise). Reflexive"),
    'fidarsi di': ('di', "«fidarsi di» (trust) takes 'di': mi fido di te (I trust you). Reflexive"),
    'occuparsi di': ('di', "«occuparsi di» (take care of, deal with) takes 'di': mi occupo dei bambini (I take care of the children). Reflexive"),
    'lamentarsi di': ('di', "«lamentarsi di» (complain about) takes 'di': si lamenta del lavoro (he complains about work). Reflexive"),
    'vergognarsi di': ('di', "«vergognarsi di» (be ashamed of) takes 'di': mi vergogno di me stesso (I'm ashamed of myself). Reflexive"),
    'vantarsi di': ('di', "«vantarsi di» (boast about) takes 'di': si vanta della sua ricchezza (he boasts of his wealth). Reflexive"),
    'innamorarsi di': ('di', "«innamorarsi di» (fall in love with) takes 'di': si è innamorato di lei (he fell in love with her). Reflexive"),
    'finire di': ('di+infinitive', "«finire di» (finish doing) takes 'di + infinitive': ho finito di lavorare (I finished working)"),
    'smettere di': ('di+infinitive', "«smettere di» (stop doing) takes 'di + infinitive': ha smesso di fumare (he stopped smoking)"),
    'cercare di': ('di+infinitive', "«cercare di» (try to) takes 'di + infinitive': cerco di capire (I try to understand). Distinguish from cercare + COD (look for)"),
    'decidere di': ('di+infinitive', "«decidere di» (decide to) takes 'di + infinitive': ho deciso di partire (I decided to leave). Mirror of decidersi a (reflexive)"),
    'sperare di': ('di+infinitive', "«sperare di» (hope to) takes 'di + infinitive': spero di rivederti (I hope to see you again)"),
    'evitare di': ('di+infinitive', "«evitare di» (avoid doing) takes 'di + infinitive': evito di parlarne (I avoid talking about it)"),
    'credere di': ('di+infinitive', "«credere di» (believe one is/does) takes 'di + infinitive' for same-subject belief: credo di averlo visto (I believe I saw him)"),
    'contare su': ('su', "«contare su» (count on) takes 'su': conto su di te (I count on you). Note: 'su di te' with personal pronouns, 'su' alone with nouns"),
    'riflettere su': ('su', "«riflettere su» (reflect on) takes 'su': rifletto sulla questione (I reflect on the question)"),
    'scommettere su': ('su', "«scommettere su» (bet on) takes 'su': scommetto su di lui (I bet on him)"),
    'sperare in': ('in', "«sperare in» (hope for) takes 'in': spero in un cambiamento (I hope for change). Distinct from sperare di + infinitive"),
    'credere in': ('in', "«credere in» (have faith in) takes 'in': credo in Dio (I believe in God). Mirror of credere a (give credence to)"),
}


def _text(tok: Any) -> str:
    return tok.text if hasattr(tok, "text") else str(tok)


def _lemma(c: CandidateObject) -> str:
    return c.lesson_data.get("lemma", c.canonical_form)


class ItalianNuanceExtractor:
    language = "it"

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
        out.extend(self._essere_avere(candidates, seen))
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
            cf = f"nuance:it:verbal_government:{lemma}"
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
                        "Italian prepositional verbs select a fixed preposition (a, di, in, …) "
                        "that often shifts meaning. Infinitive complements with a vs. di are a "
                        f"persistent learner stumbling block. Required structure: {required_case}."
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
            cf = f"nuance:it:register:{register}"
            if cf in seen:
                continue
            seen.add(cf)
            if register == "informal":
                explanation = (
                    "«tu» (dare del tu) is the singular informal 'you', used with friends, "
                    "family, peers, and in casual settings. Using «tu» with strangers or "
                    "superiors may feel overfamiliar."
                )
            else:
                explanation = (
                    "«Lei» (dare del Lei) is the formal polite 'you' used with strangers, "
                    "in professional contexts, and when addressing elders or superiors. "
                    "It takes third-person-singular verb forms: «Lei viene» (you come)."
                )
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=_text(tok),
                type="nuance",
                label=_text(tok),
                lesson_data={
                    "nuance_type": "lei_tu_register",
                    "explanation": explanation,
                    "register": register,
                    "learner_level": "A2",
                    "source": "heuristic",
                    "pronoun": low,
                },
                confidence=0.85,
            ))
        return out

    def _essere_avere(
        self, candidates: list[CandidateObject], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for c in candidates:
            if c.type != "conjugation":
                continue
            lemma = c.lesson_data.get("lemma", "")
            if lemma not in ("essere", "avere"):
                continue
            cf = f"nuance:it:essere_avere:{lemma}"
            if cf in seen:
                continue
            seen.add(cf)
            if lemma == "essere":
                explanation = (
                    "«essere» serves as copula (linking verb) and as the passato prossimo "
                    "auxiliary for intransitive motion/change verbs and all reflexives: "
                    "«sono andato», «si è alzata». Unlike Spanish, Italian uses «essere» "
                    "for both permanent and temporary states — there is no estar equivalent."
                )
            else:
                explanation = (
                    "«avere» is the passato prossimo auxiliary for most transitive verbs: "
                    "«ho mangiato», «hai visto». Choosing between «essere» and «avere» "
                    "is one of the central challenges of Italian verb morphology."
                )
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=c.surface_form,
                type="nuance",
                label=c.label,
                lesson_data={
                    "nuance_type": "essere_avere",
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
            cf = f"nuance:it:subjunctive:{lemma}"
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
                        "The Italian congiuntivo (subjunctive) is required after verbs of "
                        "wanting (volere che), emotion (essere felice che), doubt (dubitare che), "
                        "and impersonal expressions (bisogna che, è importante che). "
                        "It also follows conjunctions like «benché», «sebbene», «affinché», "
                        "«prima che». The congiuntivo is more commonly used in Italian "
                        "than the subjunctive in modern English or even French."
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
            if len(low) < 5:
                continue
            if not any(low.endswith(suf) for suf in _DIMINUTIVE_SUFFIXES):
                continue
            cf = f"nuance:it:diminutive:{low}"
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
                        "Italian diminutive suffixes (-ino/-ina, -etto/-etta, -ello/-ella) "
                        "express smallness, affection, or endearment. They are extremely "
                        "productive and carry a range of pragmatic effects from literal "
                        "smallness to irony or softening of requests."
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
