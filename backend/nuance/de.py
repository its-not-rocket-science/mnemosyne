"""German nuance extractor — modal particles, separable verbs, Wechselpräpositionen, etymology, phrase families."""
from __future__ import annotations

from typing import Any

from backend.nuance.interface import NuanceExtractorMixin
from backend.schemas.parse import CandidateObject, RelationHint

_MODAL_PARTICLES: dict[str, str] = {
    "ja":         "marks shared assumption or mild surprise; 'you know', 'obviously'",
    "doch":       "contradicts an assumption, adds insistence, or softens a command",
    "mal":        "softens requests or commands; purely conversational, no literal meaning",
    "halt":       "marks resignation or self-evidence (Southern German register); ≈ 'just'",
    "eben":       "marks inevitability or self-evidence; often interchangeable with halt",
    "wohl":       "expresses probability or polite uncertainty; 'probably', 'I suppose'",
    "denn":       "softens questions, expresses curiosity or mild impatience",
    "schon":      "offers reassurance; 'it'll be fine', 'that should count', 'already'",
    "eigentlich": "marks a polite reality-check; 'actually', 'in principle'",
    "bloß":       "adds urgency or warning; 'just', 'don't you dare'",
    "etwa":       "in questions: 'by any chance?', 'surely not?'",
    "ruhig":      "gives permission or encouragement; 'go ahead and', 'feel free to'",
    "nur":        "restricts scope or adds pressure; 'only'; in questions: 'why on earth'",
}

_WECHSEL_PREPS = frozenset({
    "in", "an", "auf", "über", "unter", "vor", "hinter", "neben", "zwischen",
})

# German verbs with non-default case government or fixed prepositional cases.
# Key: verb lemma (or "verb + preposition" for prepositional verbs).
# Value: (case_label, explanation).
_VERBAL_GOV: dict[str, tuple[str, str]] = {
    "helfen":      ("dative",         "«helfen» governs the dative: ich helfe dir (I help you)"),
    "danken":      ("dative",         "«danken» governs the dative: ich danke Ihnen (I thank you)"),
    "gefallen":    ("dative",         "«gefallen» governs the dative: das Buch gefällt mir (the book pleases me / I like the book)"),
    "gehören":     ("dative",         "«gehören» governs the dative: das Buch gehört mir (the book belongs to me)"),

    # ── DE additions (gen_verbal_government.py) ──
    'antworten': ('dative', "«antworten» governs the dative: er antwortet mir (he answers me), antworte deinem Lehrer (answer your teacher). Compare beantworten + accusative: eine Frage beantworten (to answer a question)"),
    'begegnen': ('dative', "«begegnen» governs the dative: ich bin ihm begegnet (I met him), begegnen wir uns morgen (we'll meet tomorrow). Takes auxiliary sein in perfect tense"),
    'vertrauen': ('dative', "«vertrauen» governs the dative: vertraue mir (trust me), ich vertraue meinen Kollegen (I trust my colleagues). Compare vertrauen auf + accusative (to rely on)"),
    'folgen': ('dative', "«folgen» governs the dative: folge mir (follow me), die Polizei folgt dem Verdächtigen (the police follow the suspect). Takes sein in perfect tense"),
    'gratulieren': ('dative', "«gratulieren» governs the dative: ich gratuliere dir zum Geburtstag (I congratulate you on your birthday). Subject of congratulation takes zu + dative"),
    'passen': ('dative', "«passen» governs the dative: das Hemd passt mir (the shirt fits me), passt dir Montag? (does Monday work for you?). Compare passen zu + dative (to match)"),
    'schaden': ('dative', "«schaden» governs the dative: Rauchen schadet der Gesundheit (smoking damages health), das schadet dir nicht (that won't hurt you)"),
    'gleichen': ('dative', "«gleichen» governs the dative: er gleicht seinem Vater (he resembles his father), das gleicht einem Wunder (this is like a miracle)"),
    'ähneln': ('dative', "«ähneln» governs the dative: sie ähnelt ihrer Mutter (she resembles her mother), die Zwillinge ähneln sich (the twins look alike)"),
    'widersprechen': ('dative', "«widersprechen» governs the dative: ich widerspreche dir (I contradict you), das widerspricht der Logik (this contradicts logic)"),
    'zustimmen': ('dative', "«zustimmen» governs the dative: ich stimme dir zu (I agree with you), dem Vorschlag zustimmen (to agree to the proposal). Separable verb"),
    'erlauben': ('dative', "«erlauben» governs the dative of person: ich erlaube dir das (I allow you that). Two-object verb: dative person + accusative thing"),
    'verbieten': ('dative', "«verbieten» governs the dative of person: der Arzt verbietet ihm das Rauchen (the doctor forbids him to smoke). Dative person + accusative thing"),
    'raten': ('dative', "«raten» governs the dative: ich rate dir (I advise you), was rätst du mir? (what do you advise me?). Person advised takes dative"),
    'drohen': ('dative', "«drohen» governs the dative: er droht mir (he threatens me), das Wetter droht uns Regen (the weather threatens us with rain)"),
    'imponieren': ('dative', "«imponieren» governs the dative: das imponiert mir (this impresses me), seine Leistung imponiert mir (his achievement impresses me)"),
    'gehorchen': ('dative', "«gehorchen» governs the dative: das Kind gehorcht den Eltern (the child obeys the parents), gehorche mir! (obey me!)"),
    'fehlen': ('dative', "«fehlen» governs the dative: du fehlst mir (I miss you / you are missing to me), was fehlt dir? (what's wrong with you?). Possessor of the lacking item takes dative"),
    'schmecken': ('dative', "«schmecken» governs the dative: das schmeckt mir (this tastes good to me), schmeckt es dir? (do you like it?). Compare schmecken nach + dative (to taste of)"),
    'gelingen': ('dative', "«gelingen» governs the dative: das ist mir gelungen (I succeeded at this / this succeeded for me), die Überraschung gelang ihr (her surprise worked). Sein-perfect"),
    'misslingen': ('dative', "«misslingen» governs the dative: der Plan ist mir misslungen (my plan failed). Sein-perfect; mirror of gelingen"),
    'gedenken': ('genitive', "«gedenken» governs the genitive (formal/literary): wir gedenken der Toten (we remember the dead), gedenke deiner Vorfahren (remember your ancestors). Largely confined to formal contexts"),
    'bedürfen': ('genitive', "«bedürfen» governs the genitive (formal): das bedarf einer Erklärung (this requires an explanation), keiner Antwort bedürfen (to need no answer). Formal register"),
    'sich erinnern an': ('an+accusative', "«sich erinnern an» governs an + accusative: ich erinnere mich an dich (I remember you), erinnerst du dich an den Sommer? (do you remember the summer?). Reflexive"),
    'denken an': ('an+accusative', "«denken an» governs an + accusative: ich denke an dich (I think of you), denk an deine Mutter (think of your mother). Compare denken über + accusative (to have an opinion about)"),
    'glauben an': ('an+accusative', "«glauben an» governs an + accusative: ich glaube an dich (I believe in you), glaubst du an Gott? (do you believe in God?). Compare glauben + dative (to believe someone)"),
    'sich gewöhnen an': ('an+accusative', "«sich gewöhnen an» governs an + accusative: ich gewöhne mich an das Klima (I'm getting used to the climate). Reflexive; the new habit takes accusative"),
    'sich wenden an': ('an+accusative', "«sich wenden an» governs an + accusative: wenden Sie sich an unseren Service (please contact our service). Reflexive; person addressed takes accusative"),
    'warten auf': ('auf+accusative', "«warten auf» governs auf + accusative: ich warte auf den Bus (I'm waiting for the bus), warte auf mich! (wait for me!). Object awaited takes accusative"),
    'hoffen auf': ('auf+accusative', "«hoffen auf» governs auf + accusative: wir hoffen auf gutes Wetter (we hope for good weather), ich hoffe auf eine Antwort (I hope for an answer)"),
    'sich freuen auf': ('auf+accusative', "«sich freuen auf» governs auf + accusative for future events: ich freue mich auf den Urlaub (I'm looking forward to the holiday). Contrast sich freuen über + accusative (to be happy about something present/past)"),
    'sich freuen über': ('über+accusative', "«sich freuen über» governs über + accusative for present/past events: ich freue mich über das Geschenk (I'm happy about the gift). Contrast sich freuen auf for future"),
    'sich verlassen auf': ('auf+accusative', "«sich verlassen auf» governs auf + accusative: du kannst dich auf mich verlassen (you can rely on me). Reflexive; trusted entity takes accusative"),
    'achten auf': ('auf+accusative', "«achten auf» governs auf + accusative: achte auf den Verkehr (watch out for traffic), achte auf deine Worte (mind your words). Compare achten + accusative (to respect)"),
    'antworten auf': ('auf+accusative', "«antworten auf» governs auf + accusative for the question/topic: er antwortet auf meine Frage (he answers my question). Person answered still takes dative: er antwortet mir auf meine Frage"),
    'sich vorbereiten auf': ('auf+accusative', "«sich vorbereiten auf» governs auf + accusative: ich bereite mich auf die Prüfung vor (I'm preparing for the exam). Separable, reflexive"),
    'sich konzentrieren auf': ('auf+accusative', "«sich konzentrieren auf» governs auf + accusative: konzentriere dich auf die Arbeit (focus on the work). Reflexive"),
    'sich kümmern um': ('um+accusative', "«sich kümmern um» governs um + accusative: ich kümmere mich um die Kinder (I take care of the children). Reflexive; object of care takes accusative"),
    'bitten um': ('um+accusative', "«bitten um» governs um + accusative: ich bitte um Verzeihung (I beg pardon), bitten um Hilfe (to ask for help). Compare fragen nach (to ask about)"),
    'sich bewerben um': ('um+accusative', "«sich bewerben um» governs um + accusative: ich bewerbe mich um die Stelle (I'm applying for the job). Reflexive"),
    'kämpfen um': ('um+accusative', "«kämpfen um» governs um + accusative: kämpfen um die Freiheit (to fight for freedom). Compare kämpfen gegen + accusative (to fight against)"),
    'fragen nach': ('nach+dative', "«fragen nach» governs nach + dative: er fragt nach dir (he is asking about you), fragen nach dem Weg (to ask for directions). Compare fragen + accusative (to ask someone)"),
    'suchen nach': ('nach+dative', "«suchen nach» governs nach + dative: ich suche nach einer Lösung (I'm looking for a solution). Often interchangeable with suchen + accusative for objects"),
    'riechen nach': ('nach+dative', "«riechen nach» governs nach + dative: es riecht nach Kaffee (it smells of coffee), du riechst nach Tabak (you smell of tobacco)"),
    'schmecken nach': ('nach+dative', "«schmecken nach» governs nach + dative for taste-of: das schmeckt nach Zitrone (this tastes of lemon). Distinct from schmecken + dative (to taste good to)"),
    'sich sehnen nach': ('nach+dative', "«sich sehnen nach» governs nach + dative: ich sehne mich nach dir (I long for you). Reflexive; literary register"),
    'streben nach': ('nach+dative', "«streben nach» governs nach + dative: streben nach Erfolg (to strive for success), nach Glück streben (to seek happiness). Formal register"),
    'abhängen von': ('von+dative', "«abhängen von» governs von + dative: das hängt von dir ab (that depends on you). Separable verb"),
    'träumen von': ('von+dative', "«träumen von» governs von + dative: ich träume von dir (I dream of you), von einem Haus träumen (to dream of a house)"),
    'leben von': ('von+dative', "«leben von» governs von + dative: er lebt von seiner Rente (he lives off his pension), wovon lebt sie? (what does she live on?)"),
    'erzählen von': ('von+dative', "«erzählen von» governs von + dative: erzähl mir von deinem Tag (tell me about your day). Compare erzählen über + accusative (more analytical)"),
    'halten von': ('von+dative', "«halten von» governs von + dative for opinions: was hältst du von dem Plan? (what do you think of the plan?), nichts von etwas halten (to think nothing of something)"),
    'bestehen aus': ('aus+dative', "«bestehen aus» governs aus + dative for composition: das Team besteht aus zehn Spielern (the team consists of ten players). Distinct from bestehen auf + dative (to insist)"),
    'bestehen auf': ('auf+dative', "«bestehen auf» governs auf + dative for insistence: ich bestehe auf meiner Meinung (I insist on my opinion). Notable: dative not accusative — the position is static"),
    'teilnehmen an': ('an+dative', "«teilnehmen an» governs an + dative: ich nehme an der Konferenz teil (I'm participating in the conference). Separable; static participation = dative"),
    'leiden an': ('an+dative', "«leiden an» governs an + dative for chronic conditions: er leidet an Diabetes (he suffers from diabetes). Compare leiden unter + dative (to suffer under transient circumstances)"),
    'leiden unter': ('unter+dative', "«leiden unter» governs unter + dative for transient suffering: sie leidet unter dem Lärm (she suffers from the noise). Contrast leiden an for chronic illness"),
    'sterben an': ('an+dative', "«sterben an» governs an + dative for cause of death: er starb an Krebs (he died of cancer), sterben an einem Herzinfarkt (to die of a heart attack)"),
    'arbeiten an': ('an+dative', "«arbeiten an» governs an + dative: ich arbeite an einem Buch (I'm working on a book). Project takes dative — work is static-located"),
    'zweifeln an': ('an+dative', "«zweifeln an» governs an + dative: ich zweifle an dem Erfolg (I doubt the success), zweifeln an sich selbst (to doubt oneself)"),
    'sich beschäftigen mit': ('mit+dative', "«sich beschäftigen mit» governs mit + dative: ich beschäftige mich mit Geschichte (I'm engaged with history). Reflexive"),
    'rechnen mit': ('mit+dative', "«rechnen mit» governs mit + dative: ich rechne mit deiner Hilfe (I'm counting on your help). Compare rechnen + accusative (to calculate)"),
    'umgehen mit': ('mit+dative', "«umgehen mit» governs mit + dative: wie gehst du mit der Situation um? (how do you handle the situation?). Separable"),
    'sich verstehen mit': ('mit+dative', "«sich verstehen mit» governs mit + dative: ich verstehe mich gut mit ihm (I get along well with him). Reflexive"),
    'aufhören mit': ('mit+dative', "«aufhören mit» governs mit + dative: hör mit dem Lärm auf (stop the noise). Separable; activity to stop takes dative"),
    'anfangen mit': ('mit+dative', "«anfangen mit» governs mit + dative: ich fange mit der Arbeit an (I'm starting work). Separable; activity begun takes dative"),
    'sich verlieben in': ('in+accusative', "«sich verlieben in» governs in + accusative: ich habe mich in sie verliebt (I fell in love with her). Reflexive; falling-into = directional = accusative"),
    'sich entschuldigen für': ('für+accusative', "«sich entschuldigen für» governs für + accusative for the offense: ich entschuldige mich für die Verspätung (I apologize for being late). Person apologized to takes bei + dative"),
    'sich bedanken für': ('für+accusative', "«sich bedanken für» governs für + accusative: ich bedanke mich für das Geschenk (I thank you for the gift). Reflexive; person thanked takes bei + dative"),
    'sich interessieren für': ('für+accusative', "«sich interessieren für» governs für + accusative: ich interessiere mich für Musik (I'm interested in music). Reflexive"),
    'sorgen für': ('für+accusative', "«sorgen für» governs für + accusative: er sorgt für seine Familie (he provides for his family). Compare sich sorgen um + accusative (to worry about)"),
    'sich sorgen um': ('um+accusative', "«sich sorgen um» governs um + accusative: ich sorge mich um dich (I'm worried about you). Reflexive — distinct from sorgen für (to provide for)"),
    'sich entscheiden für': ('für+accusative', "«sich entscheiden für» governs für + accusative: ich entscheide mich für die rote Variante (I'm choosing the red one). Reflexive"),
    'sich entscheiden gegen': ('gegen+accusative', "«sich entscheiden gegen» governs gegen + accusative: er entschied sich gegen das Angebot (he decided against the offer). Reflexive; mirror of sich entscheiden für"),
    'kämpfen gegen': ('gegen+accusative', "«kämpfen gegen» governs gegen + accusative: kämpfen gegen den Feind (to fight against the enemy). Compare kämpfen um + accusative (to fight for)"),
    'sich bewegen': ('accusative', "«sich bewegen» — reflexive form taking accusative reflexive pronoun: ich bewege mich (I am moving). Distinguish from bewegen + accusative (to move something)"),
    'lehren': ('double+accusative', "«lehren» governs double accusative (formal/older usage): er lehrt mich Deutsch (he teaches me German) — both person and subject in accusative. Modern usage sometimes uses dative for the person"),
    'kosten': ('double+accusative', "«kosten» governs double accusative for cost: das Buch kostet mich zehn Euro (the book costs me ten euros). Person and amount both accusative"),
    'fragen': ('double+accusative', "«fragen» governs double accusative: ich frage dich etwas (I'm asking you something). Both person and topic in accusative — distinct from fragen nach + dative"),
    'nennen': ('double+accusative', "«nennen» governs double accusative: man nennt ihn einen Helden (people call him a hero). Person and label both accusative"),
}


def _text(tok: Any) -> str:
    return tok.text if hasattr(tok, "text") else str(tok)


def _dep(tok: Any) -> str:
    return getattr(tok, "dep_", "")


def _lemma(c: CandidateObject) -> str:
    return c.lesson_data.get("lemma", c.canonical_form)


class GermanNuanceExtractor(NuanceExtractorMixin):
    language = "de"

    def extract_nuance(
        self,
        sentence: str,
        tokens: list[Any],
        candidates: list[CandidateObject],
        language: str,
    ) -> list[CandidateObject]:
        out: list[CandidateObject] = []
        seen: set[str] = set()
        out.extend(self._modal_particles(tokens, seen))
        out.extend(self._separable_verb(tokens, seen))
        out.extend(self._wechsel_preps(tokens, seen))
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
            cf = f"nuance:de:verbal_government:{lemma}"
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
                        "German verbs govern a specific case for their objects or take "
                        "a fixed preposition — this is an inherent property of the verb, "
                        f"not predictable from context. Required case: {required_case}."
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

    def _modal_particles(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for tok in tokens:
            low = _text(tok).lower()
            if low not in _MODAL_PARTICLES:
                continue
            cf = f"nuance:de:modal_particle:{low}"
            if cf in seen:
                continue
            seen.add(cf)
            meaning = _MODAL_PARTICLES[low]
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=_text(tok),
                type="nuance",
                label=_text(tok),
                lesson_data={
                    "nuance_type": "modal_particle",
                    "explanation": (
                        f"«{low}» as a Modalpartikel (modal/flavoring particle): {meaning}. "
                        "Modal particles are unstressed and resist literal translation — they "
                        "encode the speaker's attitude toward the utterance. Mastering them "
                        "is central to sounding natural in German conversation."
                    ),
                    "register": "neutral",
                    "learner_level": "B2",
                    "source": "heuristic",
                    "particle": low,
                },
                confidence=0.65,
            ))
        return out

    def _separable_verb(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        """Detect detached verb prefixes via spaCy dep=svp label."""
        out = []
        for tok in tokens:
            if _dep(tok) != "svp":
                continue
            surface = _text(tok)
            low = surface.lower()
            cf = f"nuance:de:separable_verb:{low}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=surface,
                type="nuance",
                label=surface,
                lesson_data={
                    "nuance_type": "separable_verb",
                    "explanation": (
                        f"«{surface}» is a separable verb prefix (trennbares Präfix). "
                        "In main clauses the prefix detaches from the verb stem and moves "
                        "to clause-final position: «anrufen» → «Ich rufe dich an». "
                        "The prefix often changes the base verb's meaning fundamentally."
                    ),
                    "register": "neutral",
                    "learner_level": "A2",
                    "source": "plugin",
                    "prefix": low,
                },
                confidence=0.90,
            ))
        return out

    def _wechsel_preps(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for tok in tokens:
            low = _text(tok).lower()
            if low not in _WECHSEL_PREPS:
                continue
            cf = f"nuance:de:wechselpraep:{low}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=_text(tok),
                type="nuance",
                label=_text(tok),
                lesson_data={
                    "nuance_type": "two_way_preposition",
                    "explanation": (
                        f"«{low}» is a Wechselpräposition (two-way preposition). "
                        "It governs the accusative for directed movement (Wohin? — where to?): "
                        "«Ich lege das Buch in die Tasche». "
                        "It governs the dative for static location (Wo? — where?): "
                        "«Das Buch liegt in der Tasche»."
                    ),
                    "register": "neutral",
                    "learner_level": "A2",
                    "source": "heuristic",
                    "preposition": low,
                },
                confidence=0.80,
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
