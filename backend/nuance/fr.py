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


def _text(tok: Any) -> str:
    return tok.text if hasattr(tok, "text") else str(tok)


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
        out.extend(self._etymology(candidates, seen))
        out.extend(self._phrase_families(tokens))
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
