"""Koine/Classical Greek nuance extractor — discourse particles, negation, definite article."""
from __future__ import annotations

import unicodedata
from typing import Any

from backend.schemas.parse import CandidateObject, RelationHint


def _normalize(s: str) -> str:
    """Strip polytonic diacriticals and return lowercase for matching."""
    nfd = unicodedata.normalize("NFD", s)
    return "".join(
        ch for ch in nfd
        if unicodedata.category(ch) not in ("Mn", "Lm")
    ).lower()


_DISCOURSE_PARTICLES: dict[str, str] = {
    "μεν":    "affirmative/anticipatory — introduces a clause to be contrasted by δέ",
    "δε":     "mild adversative/continuative — 'but', 'and', 'then' (postpositive)",
    "γαρ":    "causal/explanatory — 'for', 'because', 'indeed' (postpositive)",
    "ουν":    "inferential — 'therefore', 'then', 'accordingly' (postpositive)",
    "αλλα":   "strong adversative — 'but', 'rather', 'on the contrary'",
    "και":    "additive — 'and', 'also', 'even', 'indeed'",
    "τε":     "additive/connective — 'and'; paired as τε…καί ('both…and')",
    "η":      "disjunctive — 'or'; in comparisons: 'than'",
    "οτι":    "declarative/causal — 'that' (indirect statement); 'because'",
    "ει":     "conditional — 'if'; introduces indirect question",
    "αρα":    "inferential — 'then', 'therefore', 'so' (draws a conclusion)",
    "γε":     "intensive/limitative — 'at least', 'indeed', 'even' (emphatic focus)",
    "δη":     "temporal/emphatic — 'indeed', 'now', 'clearly' (adds narrative vividness)",
    "που":    "modal — 'presumably', 'I suppose', 'somewhere' (approximative hedging)",
    "μεντοι": "adversative — 'however', 'and yet' (stronger than μέν alone)",
    "ωστε":   "consecutive/result — 'so that', 'with the result that', 'therefore'",
    "ινα":    "purpose — 'so that', 'in order that' (governs subjunctive/optative)",
}

_NEGATION: dict[str, tuple[str, str]] = {
    "ου": (
        "negation_ou",
        "«οὐ» (οὐκ before smooth vowels, οὐχ before rough breathing) negates indicative "
        "statements of fact. It is the standard negation for assertions. "
        "Example: οὐκ οἶδα (I do not know).",
    ),
    "μη": (
        "negation_me",
        "«μή» negates non-indicative moods (subjunctive, optative, imperative, infinitive, "
        "participle) and introduces negated purpose clauses. "
        "Example: μὴ ποιεῖ τοῦτο (do not do this). "
        "The οὐ/μή distinction is the most systematic feature of Greek negation.",
    ),
}

# Greek verbs with non-accusative case government — verbs of perception
# (gen of source), verbs of memory/desire/sharing (gen), verbs of helping/
# trusting/obeying (dat), verbs of accusation (acc + gen of charge).
_VERBAL_GOV: dict[str, tuple[str, str]] = {
    "ἀκούω":   ("genitive",      "«ἀκούω» takes genitive of the sound source (the person heard) and accusative of the thing heard: ἀκούω σου (I hear you)"),
    "μέμνημαι": ("genitive",     "«μέμνημαι» (remember) governs the genitive: μέμνημαι τοῦ πατρός (I remember my father)"),
    "πιστεύω": ("dative",        "«πιστεύω» (trust/believe) governs the dative of person: πιστεύω σοι (I trust you). Compare πιστεύω εἰς + acc (Christian usage: believe in)"),
    "χράομαι": ("dative",        "«χράομαι» (use) governs the dative — a key middle-voice verb: χρῆται βιβλίοις (he uses books)"),

    # ── GRC additions (gen_verbal_government.py) ──
    'ἄρχω': ('genitive', "«ἄρχω» (rule over, begin) governs the genitive: ἄρχει τῶν Ἑλλήνων (he rules the Greeks). Source of English 'monarch' (sole ruler)"),
    'ἐπιθυμέω': ('genitive', "«ἐπιθυμέω» (desire) governs the genitive: ἐπιθυμεῖ τῆς δόξης (he desires glory). Verbs of desire take the gen of object desired"),
    'ἐπιμελέομαι': ('genitive', "«ἐπιμελέομαι» (care for, attend to) — middle voice, governs the genitive: ἐπιμελεῖται τῶν παίδων (he cares for the children)"),
    'κρατέω': ('genitive', "«κρατέω» (be master of) governs the genitive: κρατεῖ τῆς πόλεως (he is master of the city). Hence English 'democracy' (rule by the demos)"),
    'μετέχω': ('genitive', "«μετέχω» (share in, partake of) governs the genitive: μετέχει τῆς ἀρχῆς (he shares in the rule). Verbs of partition take gen"),
    'ἐράω': ('genitive', "«ἐράω» (love passionately) governs the genitive: ἐρᾷ τῆς γυναικός (he is in love with the woman). Distinct from φιλέω + acc"),
    'δέομαι': ('genitive', "«δέομαι» (need, beg) — middle, governs the genitive: δέομαί σου (I beg you / I have need of you)"),
    'ἀναμιμνῄσκω': ('genitive', "«ἀναμιμνῄσκω» (remind) governs acc of person + gen of thing: ἀναμιμνῄσκω σε τῶν ὅρκων (I remind you of the oaths)"),
    'ψεύδομαι': ('genitive', "«ψεύδομαι» (deceive, deprive of by lies) — middle, governs acc + gen: ψεύδεταί σε τῆς ἐλπίδος (he deceives you of your hope)"),
    'γεύομαι': ('genitive', "«γεύομαι» (taste) — middle, governs the genitive: γεύεται τοῦ οἴνου (he tastes the wine). Verbs of perception take gen of source"),
    'ἁπτω': ('genitive', "«ἅπτομαι» (touch) — middle, governs the genitive: ἅπτεται τῆς χειρός (he touches the hand). Verbs of contact take gen"),
    'πληρόω': ('genitive', "«πληρόω» (fill) governs acc of thing filled + gen of filler: πληροῖ τὴν ναῦν στρατιωτῶν (he fills the ship with soldiers)"),
    'κενόω': ('genitive', "«κενόω» (empty) governs acc + gen: κενοῖ τὴν ναῦν τῶν στρατιωτῶν (he empties the ship of soldiers)"),
    'στερέω': ('genitive', "«στερέω» (deprive) governs acc of person + gen of thing: στερεῖ με τοῦ φωτός (he deprives me of the light)"),
    'παύω': ('genitive', "«παύω» (stop, cause to cease) governs acc of person + gen of activity: παύει με τοῦ ἔργου (he stops me from the work)"),
    'κωλύω': ('genitive', "«κωλύω» (hinder) governs acc + gen: κωλύει με τῆς ὁδοῦ (he hinders me from the road). Verbs of separation take gen"),
    'διαφέρω': ('genitive', "«διαφέρω» (differ from, be superior to) governs the genitive of comparison: διαφέρει τῶν ἄλλων (he differs from / surpasses the others)"),
    'ἕπομαι': ('dative', "«ἕπομαι» (follow) — middle, governs the dative: ἕπεται τῷ στρατηγῷ (he follows the general)"),
    'εἴκω': ('dative', "«εἴκω» (yield to) governs the dative: εἴκει τοῖς πολεμίοις (he yields to the enemies)"),
    'ὑπακούω': ('dative', "«ὑπακούω» (obey, listen to) governs the dative: ὑπακούει τῷ πατρί (he obeys his father). Compound of ὑπό + ἀκούω"),
    'συμφέρω': ('dative', "«συμφέρω» (be useful for, profit) governs the dative: συμφέρει σοι σιγᾶν (it is profitable for you to keep silent)"),
    'ὁμολογέω': ('dative', "«ὁμολογέω» (agree with, confess) governs the dative: ὁμολογεῖ τοῖς ἄλλοις (he agrees with the others). Source of NT 'confession'"),
    'ἥδομαι': ('dative', "«ἥδομαι» (rejoice in, take pleasure in) — middle, governs the dative: ἥδεται τῇ νίκῃ (he rejoices in the victory). Hence hedonism"),
    'ὁμιλέω': ('dative', "«ὁμιλέω» (associate with, converse with) governs the dative: ὁμιλεῖ τοῖς φιλοσόφοις (he associates with the philosophers). Source of 'homily'"),
    'φθονέω': ('dative', "«φθονέω» (envy, begrudge) governs the dative: φθονεῖ τοῖς εὐτυχοῦσιν (he envies the fortunate)"),
    'μάχομαι': ('dative', "«μάχομαι» (fight against) — middle, governs the dative: μάχεται τοῖς πολεμίοις (he fights the enemies)"),
    'ἀνταγωνίζομαι': ('dative', "«ἀνταγωνίζομαι» (struggle against) — middle, governs the dative: ἀνταγωνίζεται τοῖς ἄλλοις (he competes against the others). Source of 'antagonist'"),
    'ἀπαντάω': ('dative', "«ἀπαντάω» (meet) governs the dative: ἀπήντησεν αὐτῷ (he met him)"),
    'ἀρέσκω': ('dative', "«ἀρέσκω» (please) governs the dative: ἀρέσκει μοι ὁ λόγος (the speech pleases me). Mirror of Latin placeo"),
    'διαλέγομαι': ('dative', "«διαλέγομαι» (converse with) — middle, governs the dative: διαλέγεται τοῖς μαθηταῖς (he converses with the disciples). Source of 'dialogue'"),
    'ἐναντιόομαι': ('dative', "«ἐναντιόομαι» (oppose) — middle, governs the dative: ἐναντιοῦται τοῖς νόμοις (he opposes the laws)"),
    'βοηθέω': ('dative', "«βοηθέω» (help, aid) governs the dative: βοηθεῖ τοῖς πτωχοῖς (he helps the poor). Compound of βοή + θέω = run-to-the-shout"),
    'ἀκολουθέω': ('dative', "«ἀκολουθέω» (follow, accompany) governs the dative: ἀκολουθεῖ τῷ διδασκάλῳ (he follows the teacher). Source of 'acolyte'"),
    'πρέπει': ('dative', "«πρέπει» (it is fitting — impersonal) governs the dative: πρέπει σοι σιγᾶν (it befits you to be silent)"),
    'δοκέω': ('dative', "«δοκέω» (seem, think) governs the dative when impersonal: δοκεῖ μοι (it seems to me / I think). The whole 'consensus' of Greek thought is structured in dat-of-person + verb"),
    'δίδωμι': ('accusative+dative', "«δίδωμι» (give) governs acc of thing + dat of recipient: δίδωμί σοι τὸ βιβλίον (I give you the book). The classic ditransitive pattern"),
    'λέγω': ('accusative+dative', "«λέγω» (say to) governs acc of thing said + dat of person: λέγει μοι τὸν λόγον (he says the word to me). With ὅτι + indicative for indirect statement"),
    'διδάσκω': ('double+accusative', "«διδάσκω» (teach) governs double accusative: διδάσκει με τὴν τέχνην (he teaches me the art). Person and subject both in acc"),
    'ἐρωτάω': ('double+accusative', "«ἐρωτάω» (ask) governs double accusative: ἐρωτᾷ με τοῦτο (he asks me this). Person and question both in acc"),
    'αἰτέω': ('double+accusative', "«αἰτέω» (ask for) governs double accusative: αἰτεῖ με τὸ ἀργύριον (he asks me for the money). Person and request both in acc"),
    'κρίνω': ('double+accusative', "«κρίνω» (judge) governs acc of person + gen of charge: κρίνει με προδοσίας (he judges me on a charge of treason). Source of 'critic'"),
    'αἰτιάομαι': ('double+accusative', "«αἰτιάομαι» (charge, accuse) — middle, governs acc + gen: αἰτιᾶταί με προδοσίας (he charges me with treason). Source of 'aetiology' (study of causes)"),
    'διώκω': ('double+accusative', "«διώκω» (prosecute, pursue) governs acc of defendant + gen of charge: διώκει με κλοπῆς (he prosecutes me for theft)"),
    'νικάω': ('accusative', "«νικάω» (conquer, defeat) governs accusative: νικᾷ τοὺς πολεμίους (he defeats the enemies). Hence Νίκη (Nike, victory)"),
    'λοιδορέω': ('accusative', "«λοιδορέω» (revile, abuse) governs accusative: λοιδορεῖ τὸν φίλον (he reviles his friend). Active voice"),
    'λοιδορέομαι': ('dative', "«λοιδορέομαι» (quarrel with) — middle, governs the dative: λοιδορεῖται τῷ ἀδελφῷ (he quarrels with his brother). Note voice/case shift from active"),
    'συγγίγνομαι': ('dative', "«συγγίγνομαι» (associate with) — middle, governs the dative: συγγίγνεται τοῖς σοφισταῖς (he keeps company with the sophists). Source of συγγένεια (kinship)"),
    'θαυμάζω': ('genitive', "«θαυμάζω» (wonder at, admire) governs the gen of cause: θαυμάζω σου τῆς σοφίας (I admire you for your wisdom). Source of 'thauma' = wonder"),
    'καταγιγνώσκω': ('genitive', "«καταγιγνώσκω» (condemn) governs gen of person + acc of thing: κατέγνω αὐτοῦ θάνατον (he condemned him to death)"),
    'ἁμαρτάνω': ('genitive', "«ἁμαρτάνω» (miss, fail of) governs the genitive: ἁμαρτάνει τοῦ σκοποῦ (he misses the mark). NT word for 'sin' = missing the mark"),
    'τυγχάνω': ('genitive', "«τυγχάνω» (obtain, hit upon) governs the genitive: ἔτυχε νίκης (he obtained victory). Distinct from τυγχάνω + participle (happen to be)"),
    'λαγχάνω': ('genitive', "«λαγχάνω» (obtain by lot) governs the genitive: ἔλαχε τῆς ἀρχῆς (he obtained the office by lot). Important verb in democratic Athens"),
    'ψαύω': ('genitive', "«ψαύω» (touch lightly) governs the genitive: ψαύει τῆς γῆς (it touches the ground). Verbs of contact regularly take gen"),
}


# Normalized forms of the Greek definite article (all cases/numbers/genders)
_ARTICLE_FORMS = frozenset({
    "ο", "η", "το",           # Nom sg M/F/N
    "τον", "την", "το",       # Acc sg M/F/N
    "του", "της", "του",      # Gen sg M/F/N
    "τω",                     # Dat sg M/N (contracted)
    "τη",                     # Dat sg F
    "οι", "αι", "τα",         # Nom pl M/F/N
    "τους", "τας", "τα",      # Acc pl M/F/N
    "των",                    # Gen pl all genders
    "τοις", "ταις", "τοις",   # Dat pl M/N, F
})


def _text(tok: Any) -> str:
    return tok.text if hasattr(tok, "text") else str(tok)


def _lemma(c: CandidateObject) -> str:
    return c.lesson_data.get("lemma", c.canonical_form)


class AncientGreekNuanceExtractor:
    language = "grc"

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
        out.extend(self._negation(tokens, seen))
        out.extend(self._verbal_government(candidates, seen))
        out.extend(self._article_note(tokens, seen))
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
            cf = f"nuance:grc:verbal_government:{lemma}"
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
                        "Greek verbs of perception, memory, desire, and sharing typically take "
                        "the genitive; verbs of helping, trusting, obeying, and using take the "
                        f"dative. Required case: {required_case}."
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
            surface = _text(tok)
            norm = _normalize(surface)
            if norm not in _DISCOURSE_PARTICLES:
                continue
            cf = f"nuance:grc:particle:{norm}"
            if cf in seen:
                continue
            seen.add(cf)
            meaning = _DISCOURSE_PARTICLES[norm]
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=surface,
                type="nuance",
                label=surface,
                lesson_data={
                    "nuance_type": "discourse_particle",
                    "explanation": (
                        f"«{surface}» (norm: {norm}): {meaning}. "
                        "Greek discourse particles encode the speaker's logical stance and "
                        "pragmatic intent. Postpositive particles (δέ, γάρ, οὖν, τε) "
                        "cannot stand first in their clause — a critical reading skill."
                    ),
                    "register": "neutral",
                    "learner_level": "B1",
                    "source": "heuristic",
                    "particle": norm,
                },
                confidence=0.85,
            ))
        return out

    def _negation(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        out = []
        for tok in tokens:
            surface = _text(tok)
            norm = _normalize(surface)
            # ουκ / ουχ variants: strip trailing κ/χ
            base = norm
            if norm.startswith("ου") and norm not in _NEGATION:
                base = "ου"
            if base not in _NEGATION:
                continue
            nuance_type, explanation = _NEGATION[base]
            cf = f"nuance:grc:{nuance_type}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=surface,
                type="nuance",
                label=surface,
                lesson_data={
                    "nuance_type": nuance_type,
                    "explanation": explanation,
                    "register": "neutral",
                    "learner_level": "A2",
                    "source": "heuristic",
                    "particle": surface,
                },
                confidence=0.85,
            ))
        return out

    def _article_note(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        cf = "nuance:grc:definite_article"
        if cf in seen:
            return []
        for tok in tokens:
            norm = _normalize(_text(tok))
            if norm not in _ARTICLE_FORMS:
                continue
            seen.add(cf)
            return [CandidateObject(
                canonical_form=cf,
                surface_form=_text(tok),
                type="nuance",
                label=_text(tok),
                lesson_data={
                    "nuance_type": "definite_article",
                    "explanation": (
                        "The Greek definite article (ὁ/ἡ/τό) declines for case, number, "
                        "and gender — 24 forms in classical Greek. Unlike English 'the', "
                        "Greek uses the article with abstract nouns, proper names, "
                        "and to substantivize adjectives: ὁ ἀγαθός = 'the good man'. "
                        "Its absence is as meaningful as its presence."
                    ),
                    "register": "neutral",
                    "learner_level": "A2",
                    "source": "heuristic",
                },
                confidence=0.85,
            )]
        return []
