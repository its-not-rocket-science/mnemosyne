"""Hebrew nuance extractor — definite prefix, waw conjunction, prefix decomposition, binyan, verb template, Biblical register."""
from __future__ import annotations

import re
from typing import Any

from backend.nuance.interface import NuanceExtractorMixin
from backend.schemas.parse import CandidateObject, RelationHint

# Strip nikud (Hebrew vowel points) and cantillation marks
_NIKUD_RE = re.compile(
    r"[֑-ְ֯-ׇֽֿׁׂׅׄ]"
)

_HEBREW_CONSONANTS = frozenset("אבגדהוזחטיכלמנסעפצקרשת")

# Verbal government — populate via gen_verbal_government.py.
_VERBAL_GOV: dict[str, tuple[str, str]] = {
    # ── HE additions (gen_verbal_government.py) ──
    'חשב על': ('al', "«חשב על» (ḥashav 'al, to think about) takes על + noun: חשבתי עליך (I thought about you), חושב על העתיד (thinks about the future)"),
    'דיבר על': ('al', "«דיבר על» (dibber 'al, to speak about) takes על + noun: מדברים על פוליטיקה (we're talking about politics)"),
    'שמע על': ('al', "«שמע על» (shama 'al, to hear about) takes על + noun: שמעתי עליו (I heard about him). Distinguish from שמע ב (obey)"),
    'סיפר על': ('al', "«סיפר על» (sipper 'al, to tell about) takes על + noun: סיפר לי על המסע (he told me about the trip)"),
    'כתב על': ('al', "«כתב על» (katav 'al, to write about/on) takes על + noun: כותב על המלחמה (writes about the war)"),
    'הסתכל על': ('al', "«הסתכל על» (histakkel 'al, to look at) takes על + noun: הסתכל עליי (he looked at me). Reflexive form of התפעל binyan"),
    'שמר על': ('al', "«שמר על» (shamar 'al, to guard / preserve) takes על + noun: שומר על הילדים (watches the children)"),
    'ויתר על': ('al', "«ויתר על» (vitter 'al, to give up / forgo) takes על + noun: ויתרתי על הזכות (I gave up the right)"),
    'התגבר על': ('al', "«התגבר על» (hitgabber 'al, to overcome) takes על + noun: התגבר על הקושי (he overcame the difficulty)"),
    'השפיע על': ('al', "«השפיע על» (hishpia 'al, to influence) takes על + noun: השפיע על ההחלטה (it influenced the decision)"),
    'הגן על': ('al', "«הגן על» (hegen 'al, to defend) takes על + noun: הגן על המולדת (he defended the homeland)"),
    'ענה על': ('al', "«ענה על» (ana 'al, to answer) takes על + noun: ענה על השאלה (he answered the question). Also: ענה ל (answer to a person)"),
    'הסכים ל': ('le', "«הסכים ל» (hiskim le-, to agree to) takes ל + noun: הסכמתי להצעה (I agreed to the proposal)"),
    'אמר ל': ('le', "«אמר ל» (amar le-, to say to) takes ל + recipient: אמרתי לך (I told you). The recipient is in dative-like ל"),
    'הסביר ל': ('le', "«הסביר ל» (hisbir le-, to explain to) takes ל + recipient: הסבירו לי את הסיבה (they explained the reason to me). Two-object verb"),
    'עזר ל': ('le', "«עזר ל» (azar le-, to help) takes ל + recipient: עזר לי ללמוד (he helped me to study). Distinguish from English 'help someone' (no preposition)"),
    'הודיע ל': ('le', "«הודיע ל» (hodi'a le-, to inform) takes ל + recipient: הודיע למשפחה (he informed the family)"),
    'נתן ל': ('le', "«נתן ל» (natan le-, to give to) takes ל + recipient: נתן לי ספר (he gave me a book). Two-object verb: ל + recipient + accusative + thing"),
    'הציע ל': ('le', "«הציע ל» (hitzia le-, to offer/suggest to) takes ל + recipient: הציע לי עבודה (he offered me a job)"),
    'התקרב ל': ('le', "«התקרב ל» (hitkarev le-, to approach) takes ל + noun: התקרב לבית (he approached the house). Reflexive"),
    'התרגל ל': ('le', "«התרגל ל» (hitragel le-, to get used to) takes ל + noun: התרגלתי למזג האוויר (I got used to the weather)"),
    'הגיע ל': ('le', "«הגיע ל» (higgia le-, to arrive at) takes ל + place: הגעתי לעיר (I arrived in the city)"),
    'חיכה ל': ('le', "«חיכה ל» (ḥikka le-, to wait for) takes ל + object: חיכיתי לך (I waited for you). Distinguish from English 'wait for' (no preposition required in Hebrew without ל)"),
    'קיווה ל': ('le', "«קיווה ל» (kivva le-, to hope for) takes ל + noun: מקווה לשלום (hopes for peace)"),
    'התכוון ל': ('le+infinitive', "«התכוון ל» (hitkavven le-, to intend to) takes ל + infinitive: התכוונתי לבוא (I intended to come)"),
    'השתמש ב': ('be', "«השתמש ב» (hishtammesh be-, to use) takes ב + noun: השתמש במחשב (he used the computer). Reflexive of שימש"),
    'נגע ב': ('be', "«נגע ב» (naga be-, to touch) takes ב + noun: נגע בידי (he touched my hand). Distinguish from נגע ל (concern someone)"),
    'זכה ב': ('be', "«זכה ב» (zakha be-, to win) takes ב + prize: זכה בפרס (he won a prize). Compare זכה ל (deserve)"),
    'בחר ב': ('be', "«בחר ב» (baḥar be-, to choose) takes ב + chosen: בחרו בך (they chose you). Election usage"),
    'בטח ב': ('be', "«בטח ב» (batḥach be-, to trust) takes ב + person: אני בוטח בך (I trust you)"),
    'התעניין ב': ('be', "«התעניין ב» (hit'annyen be-, to be interested in) takes ב + topic: מתעניין במוזיקה (he is interested in music). Reflexive"),
    'השתתף ב': ('be', "«השתתף ב» (hishtatef be-, to participate in) takes ב + activity: השתתף בכנס (he participated in the conference)"),
    'התחיל ב': ('be', "«התחיל ב» (hitḥil be-, to begin with) takes ב + topic: נתחיל בקריאה (let's begin with reading)"),
    'פגש ב': ('be', "«פגש ב» (pagash be-, to meet) takes ב + person (more literary): פגש בחבר (he met a friend). Modern Hebrew often uses direct object: פגש את חברו"),
    'פחד מ': ('mi', "«פחד מ» (paḥad mi-, to fear) takes מ + feared object: פוחד מכלבים (afraid of dogs). Equivalent to English 'be afraid of'"),
    'נמנע מ': ('mi', "«נמנע מ» (nimna mi-, to avoid) takes מ + avoided thing: נמנע מסכסוך (he avoided conflict). Reflexive of mn'"),
    'חשש מ': ('mi', "«חשש מ» (ḥashash mi-, to be wary of) takes מ + feared object: חשש מהשלכות (he feared consequences). Stronger/more formal than פחד מ"),
    'נהנה מ': ('mi', "«נהנה מ» (nehene mi-, to enjoy) takes מ + source: נהניתי מהסרט (I enjoyed the film). Niphal binyan"),
    'קיבל מ': ('mi', "«קיבל מ» (kibbel mi-, to receive from) takes מ + source: קיבלתי מתנה ממנה (I received a gift from her)"),
    'למד מ': ('mi', "«למד מ» (lamad mi-, to learn from) takes מ + source: לומד ממורהו (learns from his teacher)"),
    'התרחק מ': ('mi', "«התרחק מ» (hitraḥek mi-, to move away from) takes מ + noun: התרחק מהבעיה (he moved away from the problem)"),
    'פגש את': ('et', "«פגש את» (pagash et, to meet — modern usage) takes את + direct object: פגשתי אותו (I met him). את marks definite direct object"),
    'אהב את': ('et', "«אהב את» (ahav et, to love) takes את + definite direct object: אני אוהב אותך (I love you). את is the accusative marker for definite objects"),
    'ראה את': ('et', "«ראה את» (ra'a et, to see) takes את + definite direct object: ראיתי את הספר (I saw the book)"),
}


def _strip(s: str) -> str:
    return _NIKUD_RE.sub("", s)


def _tok_text(tok: Any) -> str:
    return tok.text if hasattr(tok, "text") else str(tok)


def _lemma(c: CandidateObject) -> str:
    return c.lesson_data.get("lemma", c.canonical_form)


class HebrewNuanceExtractor(NuanceExtractorMixin):
    language = "he"

    def extract_nuance(
        self,
        sentence: str,
        tokens: list[Any],
        candidates: list[CandidateObject],
        language: str,
    ) -> list[CandidateObject]:
        out: list[CandidateObject] = []
        seen: set[str] = set()
        out.extend(self._phrase_families(tokens))
        out.extend(self._definite_prefix(tokens, seen))
        out.extend(self._waw_conjunction(tokens, seen))
        out.extend(self._prefix_decomposition(candidates, seen))
        out.extend(self._binyan_note(candidates, seen))
        out.extend(self._verb_template(candidates, seen))
        out.extend(self._verbal_government(candidates, seen))
        out.extend(self._biblical_register(sentence, seen))
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
            cf = f"nuance:he:verbal_government:{lemma}"
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
                        "Hebrew verbs often select a specific preposition (ב, ל, על, מ, …) — "
                        "the prepositions are inflected for pronoun objects (לי, לך, לו) "
                        "and the choice is lexically tied to the verb. Required structure: "
                        f"{required_case}."
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

    def _phrase_families(self, tokens: list[Any]) -> list[CandidateObject]:
        from backend.dictionary.phrase_families import match_phrase_families
        sentence_text = " ".join(_tok_text(t) for t in tokens)
        legacy    = match_phrase_families([_tok_text(t) for t in tokens], self.language)
        generated = self._cultural_references(sentence_text)
        return self._merge_candidates(legacy, generated)

    def _definite_prefix(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        cf = "nuance:he:definite_prefix"
        for tok in tokens:
            surface = _tok_text(tok)
            stripped = _strip(surface)
            if len(stripped) < 2:
                continue
            if stripped[0] != "ה" or stripped[1] not in _HEBREW_CONSONANTS:
                continue
            if cf in seen:
                break
            seen.add(cf)
            return [CandidateObject(
                canonical_form=cf,
                surface_form=surface,
                type="nuance",
                label=surface,
                lesson_data={
                    "nuance_type": "definite_prefix",
                    "explanation": (
                        "«ה-» (he) is the Hebrew definite article, a prefix that attaches "
                        "directly to nouns and adjectives: ספר → הספר (the book). "
                        "Adjectives modifying a definite noun must also carry ה-. "
                        "The article triggers vowel changes (dagesh or patah) in the following letter."
                    ),
                    "register": "neutral",
                    "learner_level": "A1",
                    "source": "heuristic",
                },
                confidence=0.75,
            )]
        return []

    def _waw_conjunction(
        self, tokens: list[Any], seen: set[str]
    ) -> list[CandidateObject]:
        cf = "nuance:he:waw_conjunction"
        for tok in tokens:
            surface = _tok_text(tok)
            stripped = _strip(surface)
            if not stripped.startswith("ו") or len(stripped) < 2:
                continue
            if cf in seen:
                break
            seen.add(cf)
            return [CandidateObject(
                canonical_form=cf,
                surface_form=surface,
                type="nuance",
                label=surface,
                lesson_data={
                    "nuance_type": "waw_conjunction",
                    "explanation": (
                        "«ו-» (vav/waw) prefixed to a word is the coordinating conjunction 'and'. "
                        "In Biblical Hebrew the waw-consecutive (וַיִּ / וְ) is a distinctive "
                        "narrative device that sequences verb-clauses. "
                        "In Modern Hebrew it is a simple coordinating conjunction."
                    ),
                    "register": "neutral",
                    "learner_level": "A1",
                    "source": "heuristic",
                },
                confidence=0.80,
            )]
        return []

    _PREFIX_MEANINGS: dict[str, str] = {
        "ב":  "«ב-» (be-) is the inseparable preposition 'in', 'at', 'with', or 'by'. "
              "It attaches directly to nouns without a space: ספר → בספר (in a book).",
        "ו":  "«ו-» (ve-/u-) is the coordinating conjunction 'and'. "
              "It attaches to the following word: ספר → וספר (and a book). "
              "In Biblical Hebrew the waw-consecutive (וַיִּ) sequences narrative verb-clauses.",
        "ה":  "«ה-» (ha-) is the definite article 'the'. "
              "It attaches directly to nouns and adjectives: ספר → הספר (the book). "
              "Adjectives in a definite noun phrase must also carry ה-.",
        "ל":  "«ל-» (le-) is the inseparable preposition 'to', 'for', or 'of'. "
              "It attaches directly to nouns: ספר → לספר (to a book; to read).",
        "כ":  "«כ-» (ke-/ki-) is the inseparable preposition 'like', 'as', or 'approximately'. "
              "It attaches directly: ספר → כספר (like a book).",
        "מ":  "«מ-» (me-/mi-) is the inseparable preposition 'from', 'than', or 'out of'. "
              "It attaches directly: ספר → מספר (from a book).",
        "ש":  "«ש-» (she-) is the relative pronoun / complementiser 'that', 'which', 'who'. "
              "It attaches to the following word: ידעתי שהספר (I knew that the book …).",
        "מה": "«מה-» combines מ- (from) and ה- (the): 'from the'. "
              "It appears before certain consonants: מהבית (from the house).",
        "שה": "«שה-» combines ש- (that/which) and ה- (the): 'that the'. "
              "It introduces relative clauses on definite nouns: שהספר (that the book …).",
        "וה": "«וה-» combines ו- (and) and ה- (the): 'and the'. "
              "Common in coordination: וְהַסֵּפֶר (and the book).",
        "בה": "«בה-» combines ב- (in) and ה- (the): 'in the'. "
              "It attaches before nouns: בהבית (in the house).",
        "כה": "«כה-» combines כ- (like) and ה- (the): 'like the'.",
        "לה": "«לה-» combines ל- (to/for) and ה- (the): 'to the'.",
    }

    def _prefix_decomposition(
        self, candidates: list[CandidateObject], seen: set[str]
    ) -> list[CandidateObject]:
        """Fire when a vocabulary candidate carries a non-empty `prefix` field.

        Works in heuristic fallback mode — HebSpaCy is NOT required.
        """
        out = []
        for c in candidates:
            if c.type != "vocabulary":
                continue
            prefix = c.lesson_data.get("prefix", "")
            if not prefix:
                continue
            cf = f"nuance:he:prefix_decomposition:{prefix}"
            if cf in seen:
                continue
            seen.add(cf)
            explanation = self._PREFIX_MEANINGS.get(
                prefix,
                f"«{prefix}-» is an inseparable Hebrew prefix that attaches "
                "directly to the following word without a space.",
            )
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=c.surface_form,
                type="nuance",
                label=c.label,
                lesson_data={
                    "nuance_type": "prefix_decomposition",
                    "explanation": explanation,
                    "register": "neutral",
                    "learner_level": "A2",
                    "source": "heuristic",
                    "prefix": prefix,
                    "stem": c.lesson_data.get("lemma", ""),
                },
                confidence=0.80,
            ))
        return out

    def _verb_template(
        self, candidates: list[CandidateObject], seen: set[str]
    ) -> list[CandidateObject]:
        """Fire when a vocabulary candidate carries both binyan AND tense (requires HebSpaCy)."""
        out = []
        for c in candidates:
            if c.type != "vocabulary":
                continue
            binyan = c.lesson_data.get("binyan", "")
            tense = c.lesson_data.get("tense", "")
            if not binyan or not tense:
                continue
            cf = f"nuance:he:verb_template:{binyan.lower()}:{tense.lower()}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=c.surface_form,
                type="nuance",
                label=c.label,
                lesson_data={
                    "nuance_type": "verb_template",
                    "explanation": (
                        f"«{c.surface_form}» is a {tense.lower()} verb in the "
                        f"{binyan} binyan. "
                        "Each binyan carries a consistent vowel pattern and semantic role: "
                        "Pa'al (simple active), Pi'el (intensive/denominative), "
                        "Hif'il (causative), Nif'al (passive/reflexive), "
                        "Hitpa'el (reflexive/reciprocal). "
                        "The binyan + tense combination determines the full inflectional paradigm."
                    ),
                    "register": "neutral",
                    "learner_level": "B1",
                    "source": "plugin",
                    "binyan": binyan,
                    "tense": tense,
                },
                confidence=0.85,
                relation_hints=[RelationHint(
                    relation_type="nuance_of",
                    target_canonical_form=c.canonical_form,
                    target_type=c.type,
                )],
            ))
        return out

    def _binyan_note(
        self, candidates: list[CandidateObject], seen: set[str]
    ) -> list[CandidateObject]:
        """Fire when a candidate carries binyan metadata (requires morphological plugin)."""
        out = []
        for c in candidates:
            binyan = c.lesson_data.get("binyan")
            if not binyan:
                continue
            cf = f"nuance:he:binyan:{binyan}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(CandidateObject(
                canonical_form=cf,
                surface_form=c.surface_form,
                type="nuance",
                label=c.label,
                lesson_data={
                    "nuance_type": "binyan",
                    "explanation": (
                        f"«{binyan}» is one of the seven Hebrew verb patterns (בניינים binyanim). "
                        "Each binyan encodes voice and valency: "
                        "Pa'al (simple active), Nif'al (passive/reflexive), "
                        "Pi'el (intensive active), Pu'al (intensive passive), "
                        "Hitpa'el (reflexive/reciprocal), Hif'il (causative active), "
                        "Huf'al (causative passive). "
                        "Knowing the binyan is essential for reading Hebrew verbs correctly."
                    ),
                    "register": "neutral",
                    "learner_level": "B1",
                    "source": "plugin",
                    "binyan": binyan,
                },
                confidence=0.85,
                relation_hints=[RelationHint(
                    relation_type="nuance_of",
                    target_canonical_form=c.canonical_form,
                    target_type=c.type,
                )],
            ))
        return out

    def _biblical_register(
        self, sentence: str, seen: set[str]
    ) -> list[CandidateObject]:
        """Detect cantillation marks → Biblical Hebrew register note."""
        has_cantillation = any("֑" <= ch <= "֯" for ch in sentence)
        if not has_cantillation:
            return []
        cf = "nuance:he:biblical_register"
        if cf in seen:
            return []
        seen.add(cf)
        return [CandidateObject(
            canonical_form=cf,
            surface_form="",
            type="nuance",
            label="biblical register",
            lesson_data={
                "nuance_type": "biblical_register",
                "explanation": (
                    "Cantillation marks (טַעֲמֵי הַמִּקְרָא te'amei hamikra) indicate "
                    "Biblical Hebrew text. Biblical Hebrew differs from Modern Hebrew "
                    "in its verbal system (waw-consecutive), vocabulary, and syntax. "
                    "Cantillation marks serve both as musical notation and syntactic "
                    "punctuation in the Masoretic text."
                ),
                "register": "liturgical",
                "learner_level": "C2",
                "source": "heuristic",
            },
            confidence=0.95,
        )]
