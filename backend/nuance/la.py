"""Latin nuance extractor — discourse particles, enclitic -que, classical register."""
from __future__ import annotations

from typing import Any

from backend.nuance.interface import NuanceExtractorMixin
from backend.schemas.parse import CandidateObject, RelationHint

_DISCOURSE_PARTICLES: dict[str, str] = {
    "autem":   "adversative/continuative — 'however', 'but', 'on the other hand' (postpositive)",
    "enim":    "explanatory — 'for', 'indeed', 'you see' (postpositive; explains what precedes)",
    "igitur":  "inferential — 'therefore', 'consequently', 'so then'",
    "ergo":    "inferential — 'therefore', 'then', 'consequently'",
    "itaque":  "inferential — 'and so', 'accordingly', 'therefore'",
    "sed":     "adversative — 'but', 'however', 'yet'",
    "nam":     "causal — 'for', 'for indeed' (introduces an explanation; typically clause-initial)",
    "dum":     "temporal/conditional — 'while', 'as long as', 'until', 'provided that'",
    "tamen":   "concessive — 'nevertheless', 'yet', 'still', 'however'",
    "quidem":  "restrictive/emphatic — 'indeed', 'at least', 'to be sure' (postpositive)",
    "vero":    "emphatic/adversative — 'indeed', 'truly', 'but in fact' (postpositive)",
    "nisi":    "conditional/exceptive — 'unless', 'if not', 'except'",
    "vel":     "disjunctive — 'or' (free choice); intensifying: 'even', 'or rather'",
    "aut":     "disjunctive — 'or' (exclusive); 'either…or' in aut…aut constructions",
    "sic":     "demonstrative adverb — 'thus', 'in this way', 'so'",
    "ita":     "demonstrative adverb — 'so', 'thus', 'in this way' (often correlative with ut)",
    "nunc":    "temporal — 'now', 'at this time'",
    "iam":     "temporal — 'already', 'now', 'soon', 'by now'",
    "etiam":   "additive — 'also', 'even', 'yet', 'still'",
    "quoque":  "additive — 'also', 'too', 'likewise' (postpositive)",
    "neque":   "negative conjunction — 'and not', 'nor'",
    "nec":     "negative conjunction — 'and not', 'nor' (shortened form of neque)",
    "at":      "strong adversative — 'but', 'yet', 'but at least' (introduces counterargument)",
    "atque":   "additive — 'and', 'and also', 'and even' (stronger than et)",
    "ac":      "additive — 'and', 'and also' (shortened form of atque, used before consonants)",
    "et":      "additive — 'and'; also intensive: 'even', 'and in fact'",
    "ut":      "subordinating — purpose ('so that'), comparison ('as'), temporal ('when')",
    "cum":     "temporal/causal/concessive — 'when', 'since', 'although'",
    "si":      "conditional — 'if'",
}

_MACRON_CHARS = frozenset("āēīōūĀĒĪŌŪ")

# Latin verbs with non-default case government (deponents requiring abl,
# special verbs taking dat or gen, double-acc patterns, etc.).
_VERBAL_GOV: dict[str, tuple[str, str]] = {
    "iuvo":     ("accusative",     "«iuvo» (juvo) governs the accusative — unlike most 'help' verbs in Romance/Germanic: iuvabit te (he will help you)"),
    "parco":    ("dative",         "«parco» governs the dative: parce mihi (spare me). Latin 'spare/forgive' verbs typically take dative"),
    "noceo":    ("dative",         "«noceo» governs the dative: nocet inimicis (he harms his enemies). Verbs of harm/help take dative"),
    "studeo":   ("dative",         "«studeo» governs the dative: studere litteris (to study letters / be devoted to literature)"),

    # ── LA additions (gen_verbal_government.py) ──
    'faveo': ('dative', "«faveo» (favor) governs the dative: faveo tibi (I favor you). Verbs of attitude/disposition take the dative of the person affected"),
    'placeo': ('dative', "«placeo» (please) governs the dative: hoc mihi placet (this pleases me). Mirror of English 'X is pleasing to Y'"),
    'displiceo': ('dative', "«displiceo» (displease) governs the dative: hoc mihi displicet (this displeases me). Mirror of placeo"),
    'pareo': ('dative', "«pareo» (obey/be visible to) governs the dative: pareo legi (I obey the law). Common in Roman political/military contexts"),
    'suadeo': ('dative', "«suadeo» (advise) governs the dative of person + acc/infinitive of advice: suadeo tibi hoc facere (I advise you to do this)"),
    'persuadeo': ('dative', "«persuadeo» (persuade) governs the dative — strikingly NOT accusative: persuasi ei (I persuaded him). Verb of influence on the dative person"),
    'ignosco': ('dative', "«ignosco» (forgive) governs the dative: ignosce mihi (forgive me). Double construction: ignosce mihi peccatum meum (forgive me my sin) — dat of person + acc of offense"),
    'invideo': ('dative', "«invideo» (envy) governs the dative: invideo tibi (I envy you). The envied person takes the dative — counterintuitive for English speakers"),
    'indulgeo': ('dative', "«indulgeo» (indulge/be lenient toward) governs the dative: indulget filio (he is lenient with his son)"),
    'irascor': ('dative', "«irascor» (be angry at) — deponent, governs the dative: irascor tibi (I am angry at you)"),
    'minor': ('dative', "«minor» (threaten) — deponent, governs the dative of person threatened + acc of threat: mihi mortem minatur (he threatens me with death)"),
    'fido': ('dative', "«fido» (trust) governs dative or ablative: fidit amicis (he trusts his friends). Compare confido"),
    'confido': ('dative', "«confido» (trust strongly) governs dative or ablative: confido tibi (I trust you). Slight stylistic variation between cases"),
    'diffido': ('dative', "«diffido» (distrust) governs the dative: diffidit sibi (he distrusts himself). Mirror of confido"),
    'praecipio': ('dative', "«praecipio» (instruct/command) governs dative of person + acc of thing: praecipio tibi hoc (I instruct you in this)"),
    'impero': ('dative', "«impero» (command) governs the dative: impero militibus (I command the soldiers). Hence imperator (commander) — one who commands those in dative position"),
    'praesum': ('dative', "«praesum» (be in charge of) governs the dative: praesum exercitui (I am in command of the army). Compound of prae + sum"),
    'praeficio': ('dative', "«praeficio» (put X in charge of Y) governs acc of X + dat of Y: praefecit eum exercitui (he put him in command of the army)"),
    'supplico': ('dative', "«supplico» (beg/supplicate) governs the dative: supplicat deis (he supplicates the gods)"),
    'resisto': ('dative', "«resisto» (resist) governs the dative: resistit hostibus (he resists the enemies). Verbs of opposition take dat"),
    'repugno': ('dative', "«repugno» (oppose, fight against) governs the dative: repugnat consilio (he opposes the plan)"),
    'occurro': ('dative', "«occurro» (meet, run into) governs the dative: mihi in via occurrit (he met me on the road)"),
    'obtempero': ('dative', "«obtempero» (obey, comply with) governs the dative: obtempero legibus (I obey the laws)"),
    'oboedio': ('dative', "«oboedio» (obey) governs the dative: oboedit mihi (he obeys me). Source of English 'obey' with the same case logic in OF/OE"),
    'servio': ('dative', "«servio» (serve, be a slave to) governs the dative: servit domino (he serves his master)"),
    'prosum': ('dative', "«prosum» (benefit, be useful to) governs the dative: prodest patriae (it benefits the fatherland). Compound of pro + sum"),
    'obsum': ('dative', "«obsum» (be a hindrance to) governs the dative: obest mihi (it harms me). Compound of ob + sum, mirror of prosum"),
    'desum': ('dative', "«desum» (be lacking to) governs the dative: deest mihi pecunia (I lack money / money is lacking to me). The lacking thing in nom, the lacker in dat"),
    'adsum': ('dative', "«adsum» (be present to / help) governs the dative when meaning 'help': adsum tibi (I am here for you / I support you)"),
    'memini': ('genitive', "«memini» (remember) governs the genitive of persons and abstract things: memini patris (I remember father). Acc for concrete present things"),
    'obliviscor': ('genitive', "«obliviscor» (forget) — deponent, governs the genitive: oblitus est mei (he has forgotten me). Mirror of memini"),
    'recordor': ('genitive', "«recordor» (recall) — deponent, governs genitive or accusative: recordor temporum (I recall the times). Cor (heart) + re- = bring back to heart"),
    'miseret': ('genitive', "«miseret» (it pities — impersonal) governs acc of person feeling pity + gen of object: miseret me tui (I pity you / it pities me of you)"),
    'paenitet': ('genitive', "«paenitet» (it repents — impersonal) governs acc of person + gen of cause: paenitet me peccati (I repent of the sin)"),
    'pudet': ('genitive', "«pudet» (it shames — impersonal) governs acc of ashamed person + gen of cause: pudet me dicere (I am ashamed to say). One of the five impersonal feeling-verbs"),
    'taedet': ('genitive', "«taedet» (it wearies — impersonal) governs acc of weary person + gen of cause: taedet me vitae (I am weary of life)"),
    'piget': ('genitive', "«piget» (it irks — impersonal) governs acc of irked person + gen of cause: piget me stultitiae meae (I am vexed by my foolishness)"),
    'indigeo': ('genitive', "«indigeo» (need, lack) governs gen or abl: indiget pecuniae (he needs money). Both cases attested"),
    'egeo': ('genitive', "«egeo» (lack, be in need of) governs gen or abl: eget consilii (he lacks counsel). Either case is acceptable"),
    'accuso': ('genitive', "«accuso» (accuse) governs acc of person + gen of charge: accuso eum proditionis (I accuse him of treason). Charge takes the gen"),
    'damno': ('genitive', "«damno» (condemn) governs acc of person + gen of charge: damnat eum capitis (he condemns him to death — of life/head)"),
    'condemno': ('genitive', "«condemno» (condemn) governs acc of person + gen of charge: condemnat eum furti (he condemns him for theft)"),
    'arguo': ('genitive', "«arguo» (charge with, prove) governs acc of person + gen of accusation: arguo te falsi (I accuse you of falsehood)"),
    'absolvo': ('genitive', "«absolvo» (acquit) governs acc of person + gen or abl of charge: absolvo te culpae (I absolve you of guilt). Mirror of damno"),
    'utor': ('ablative', "«utor» (use) — deponent, governs the ablative: utor libro (I use a book). Source of English 'use' but with ABL government — counterintuitive"),
    'fruor': ('ablative', "«fruor» (enjoy) — deponent, governs the ablative: fruor vita (I enjoy life). Hence English 'fruit' (what one enjoys)"),
    'fungor': ('ablative', "«fungor» (perform, discharge a duty) — deponent, governs the ablative: fungitur officio (he discharges his office)"),
    'potior': ('ablative', "«potior» (gain control of) — deponent, governs ablative or genitive: potitur urbe (he gains the city). Hence 'potent' (one who has gained power)"),
    'vescor': ('ablative', "«vescor» (feed on) — deponent, governs the ablative: vescitur carne (he feeds on meat). Active form vesco does not exist in classical Latin"),
    'careo': ('ablative', "«careo» (lack) governs the ablative: careo amicis (I lack friends). The five 'utor-fruor-fungor-potior-vescor' deponents + careo are the canonical abl-government set"),
    'abundo': ('ablative', "«abundo» (have in abundance, abound in) governs the ablative: abundat divitiis (he abounds in wealth)"),
    'nitor': ('ablative', "«nitor» (rely on, lean on) — deponent, governs the ablative: nititur baculo (he leans on a staff). Also acc + inf for 'strive to'"),
    'glorior': ('ablative', "«glorior» (boast, take pride in) — deponent, governs the ablative or de + abl: gloriatur victoriis (he boasts of his victories)"),
    'dignor': ('ablative', "«dignor» (deem worthy of) — deponent, governs acc of person + abl of thing: dignor te honore (I deem you worthy of the honor)"),
    'doceo': ('double+accusative', "«doceo» (teach) governs double accusative: doceo te grammaticam (I teach you grammar). Both person and subject in acc — distinctive Latin pattern"),
    'celo': ('double+accusative', "«celo» (conceal) governs double accusative: celo te consilium meum (I conceal my plan from you). The person concealed-from in acc — counterintuitive"),
    'rogo': ('double+accusative', "«rogo» (ask) governs double accusative: rogo te sententiam (I ask you your opinion). Person and request both in acc"),
    'peto': ('double+accusative', "«peto» (seek, request) governs acc of thing + ab + abl of person: peto pacem ab eo (I seek peace from him). With acc/acc only in archaic usage"),
    'posco': ('double+accusative', "«posco» (demand) governs double accusative: posco te pecuniam (I demand money from you). Forceful version of rogo"),
    'oro': ('double+accusative', "«oro» (beg, pray) governs double accusative: oro te auxilium (I beg you for help). Source of English 'orator', 'oration'"),
    'flagito': ('double+accusative', "«flagito» (demand insistently) governs double accusative: flagitat eum responsum (he demands an answer from him)"),
}


def _text(tok: Any) -> str:
    return tok.text if hasattr(tok, "text") else str(tok)


def _lemma(c: CandidateObject) -> str:
    return c.lesson_data.get("lemma", c.canonical_form)


class LatinNuanceExtractor(NuanceExtractorMixin):
    language = "la"

    def extract_nuance(
        self,
        sentence: str,
        tokens: list[Any],
        candidates: list[CandidateObject],
        language: str,
    ) -> list[CandidateObject]:
        out: list[CandidateObject] = []
        seen: set[str] = set()
        out.extend(self._discourse_particles(tokens, seen))
        out.extend(self._enclitic_que(tokens, seen))
        out.extend(self._verbal_government(candidates, seen))
        out.extend(self._classical_register(sentence, seen))
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
            cf = f"nuance:la:verbal_government:{lemma}"
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
                        "Latin verbs govern specific cases for objects — many deponent verbs "
                        "and specialized transitives (favere, nocere, parcere, uti, frui, etc.) "
                        f"take dative or ablative rather than accusative. Required case: {required_case}."
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

    def _discourse_particles(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for tok in tokens:
            low = _text(tok).lower().rstrip(".,;:!?")
            if low not in _DISCOURSE_PARTICLES:
                continue
            cf = f"nuance:la:discourse_particle:{low}"
            if cf in seen:
                continue
            seen.add(cf)
            meaning = _DISCOURSE_PARTICLES[low]
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=_text(tok),
                type="nuance",
                label=_text(tok),
                lesson_data={
                    "nuance_type": "discourse_particle",
                    "explanation": (
                        f"«{low}»: {meaning}. "
                        "Latin discourse particles and conjunctions structure argument and "
                        "narrative logic. Postpositive particles (autem, enim, quidem, vero, "
                        "quoque) cannot stand first in their clause — an important reading signal."
                    ),
                    "register": "neutral",
                    "learner_level": "B1",
                    "source": "heuristic",
                    "particle": low,
                },
                confidence=0.85,
            ))
        return out

    def _enclitic_que(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for tok in tokens:
            raw = _text(tok)
            low = raw.lower().rstrip(".,;:!?")
            if not low.endswith("que") or len(low) <= 3:
                continue
            host = low[:-3]
            if not host:
                continue
            cf = f"nuance:la:enclitic_que:{low}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=raw,
                type="nuance",
                label=raw,
                lesson_data={
                    "nuance_type": "enclitic_que",
                    "explanation": (
                        f"«-que» enclitic on «{host}»: this suffix meaning 'and' attaches "
                        "to the second of two closely connected elements. "
                        "«Senatus Populusque Romanus» (SPQR) = 'the Senate and People of Rome'. "
                        "-que is more formal than et and implies close logical or semantic connection."
                    ),
                    "register": "formal",
                    "learner_level": "A2",
                    "source": "heuristic",
                    "host_word": host,
                },
                confidence=0.80,
            ))
        return out

    def _classical_register(
        self, sentence: str, seen: set[str]
    ) -> list[CandidateObject]:
        if not any(ch in _MACRON_CHARS for ch in sentence):
            return []
        cf = "nuance:la:classical_register"
        if cf in seen:
            return []
        seen.add(cf)
        return [CandidateObject(
            canonical_form=cf,
            surface_form="",
            type="nuance",
            label="macron notation",
            lesson_data={
                "nuance_type": "classical_register",
                "explanation": (
                    "This text uses macrons (ā, ē, ī, ō, ū) to mark long vowels, "
                    "a feature of Classical Latin pedagogical and critical editions. "
                    "Vowel quantity was phonemically contrastive in Classical Latin: "
                    "mālum (apple) vs. malum (evil). "
                    "Medieval and Church Latin texts typically omit macrons."
                ),
                "register": "classical",
                "learner_level": "B1",
                "source": "heuristic",
            },
            confidence=0.90,
        )]
