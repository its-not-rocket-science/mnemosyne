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


def _text(tok: Any) -> str:
    return tok.text if hasattr(tok, "text") else str(tok)


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
        out.extend(self._etymology(candidates, seen))
        out.extend(self._phrase_families(tokens))
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
