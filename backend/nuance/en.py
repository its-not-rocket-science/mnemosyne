"""English nuance extractor — register, tone, politeness, idiom transparency, ambiguity, pitfalls, collocation, and regional variation."""
from __future__ import annotations

from typing import Any

from backend.nuance.interface import NuanceExtractorMixin
from backend.schemas.parse import CandidateObject, RelationHint

_FORMAL_MARKERS = frozenset({"therefore", "moreover", "thus", "hence", "shall", "whom"})
_INFORMAL_MARKERS = frozenset({"gonna", "wanna", "kinda", "sorta", "ain't", "y'all"})
_POLITE_MARKERS = frozenset({"please", "could", "would", "mind"})
_HEDGING_MARKERS = frozenset({"maybe", "perhaps", "probably", "seems", "apparently"})
_INTENSIFIERS = frozenset({"really", "very", "absolutely", "totally", "so"})
_AMBIGUOUS_WORDS = {
    "since": "can mean either 'because' (cause) or 'from a past time until now' (time).",
    "while": "can mark time overlap or contrast ('whereas').",
    "quite": "can mean 'fairly' (US tendency) or 'completely' in some UK contexts.",
    "mean": "can be adjective ('unkind') or verb ('signify').",
}
_FALSE_FRIENDS = {
    "actually": "means 'in fact', not Spanish/French *actualmente/actuellement* ('currently').",
    "eventually": "means 'in the end', not *eventualmente/éventuellement* ('possibly').",
    "sensible": "means 'practical/reasonable', not *sensible/sensibile* ('sensitive').",
}
_COLLOCATIONS = {
    "make a decision": "English prefers 'make a decision', not *do a decision*.",
    "take a photo": "English prefers 'take a photo/picture', not *make a photo*.",
    "heavy rain": "Natural collocation is 'heavy rain' (not *strong rain*).",
    "strong coffee": "Natural collocation is 'strong coffee' (not *powerful coffee*).",
}
_REGIONAL = {
    "apartment": "US-preferred; UK equivalent is usually 'flat'.",
    "flat": "UK-preferred; US equivalent is usually 'apartment'.",
    "truck": "US-preferred; UK equivalent is 'lorry'.",
    "lorry": "UK-preferred; US equivalent is 'truck'.",
    "fries": "US-preferred; UK often says 'chips'.",
    "chips": "UK 'chips' = US 'fries'; US 'chips' = UK 'crisps'.",
}


def _text(tok: Any) -> str:
    return tok.text if hasattr(tok, "text") else str(tok)


def _lemma(c: CandidateObject) -> str:
    return c.lesson_data.get("lemma", c.canonical_form)


class EnglishNuanceExtractor(NuanceExtractorMixin):
    language = "en"

    def extract_nuance(
        self,
        sentence: str,
        tokens: list[Any],
        candidates: list[CandidateObject],
        language: str,
    ) -> list[CandidateObject]:
        out: list[CandidateObject] = []
        seen: set[str] = set()
        texts = [_text(t) for t in tokens]
        out.extend(self._register(texts, seen))
        out.extend(self._tone(texts, seen))
        out.extend(self._politeness(texts, seen))
        out.extend(self._idiom_transparency(texts, seen))
        out.extend(self._ambiguity(texts, seen))
        out.extend(self._learner_pitfalls(texts, seen))
        out.extend(self._collocation(texts, seen))
        out.extend(self._regional_variation(texts, seen))
        out.extend(self._etymology(candidates, seen))
        out.extend(self._phrase_families(tokens))
        return out

    def _emit(self, cf: str, surface: str, label: str, nuance_type: str, explanation: str,
              register: str, learner_level: str, confidence: float, extra: dict[str, Any] | None = None,
              lemma: str | None = None) -> CandidateObject:
        lesson = {
            "nuance_type": nuance_type,
            "explanation": explanation,
            "register": register,
            "learner_level": learner_level,
            "source": "heuristic",
        }
        if extra:
            lesson.update(extra)
        hints = []
        if lemma:
            hints = [RelationHint(relation_type="nuance_of", target_canonical_form=lemma, target_type="vocabulary")]
        return CandidateObject(
            canonical_form=cf,
            surface_form=surface,
            type="nuance",
            label=label,
            lesson_data=lesson,
            confidence=confidence,
            relation_hints=hints,
        )

    def _register(self, texts: list[str], seen: set[str]) -> list[CandidateObject]:
        out = []
        for raw in texts:
            low = raw.lower()
            if low in _FORMAL_MARKERS:
                reg = "formal"
            elif low in _INFORMAL_MARKERS:
                reg = "informal"
            else:
                continue
            cf = f"nuance:en:register:{reg}:{low}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(self._emit(cf, raw, raw, "register", f"‘{raw}’ is a {reg} marker in English discourse.", reg, "A2", 0.88, {"marker": low}))
        return out

    def _tone(self, texts: list[str], seen: set[str]) -> list[CandidateObject]:
        out = []
        for raw in texts:
            low = raw.lower()
            if low in _HEDGING_MARKERS:
                kind, reg = "hedging", "neutral"
            elif low in _INTENSIFIERS:
                kind, reg = "intensifier", "neutral"
            else:
                continue
            cf = f"nuance:en:tone:{kind}:{low}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(self._emit(cf, raw, raw, "tone", f"‘{raw}’ adjusts tone via {kind}.", reg, "B1", 0.84, {"tone_marker": low, "tone_kind": kind}))
        return out

    def _politeness(self, texts: list[str], seen: set[str]) -> list[CandidateObject]:
        out = []
        for raw in texts:
            low = raw.lower()
            if low not in _POLITE_MARKERS:
                continue
            cf = f"nuance:en:politeness:{low}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(self._emit(cf, raw, raw, "politeness", "Politeness softeners reduce directness and improve pragmatic appropriateness.", "polite", "A2", 0.86, {"politeness_marker": low}))
        return out

    def _idiom_transparency(self, texts: list[str], seen: set[str]) -> list[CandidateObject]:
        out = []
        low_text = [t.lower() for t in texts]
        phrases = {
            ("kick", "the", "bucket"): "idiomatic meaning is 'to die', not literal kicking.",
            ("piece", "of", "cake"): "means 'very easy', not literal dessert.",
        }
        for seq, gloss in phrases.items():
            if " ".join(seq) in " ".join(low_text):
                key = "_".join(seq)
                cf = f"nuance:en:idiom:{key}"
                if cf in seen:
                    continue
                seen.add(cf)
                out.append(self._emit(cf, " ".join(seq), " ".join(seq), "idiom", f"This expression is non-compositional: {gloss}", "informal", "B1", 0.82, {"idiom": " ".join(seq)}))
        return out

    def _ambiguity(self, texts: list[str], seen: set[str]) -> list[CandidateObject]:
        out = []
        for raw in texts:
            low = raw.lower()
            if low not in _AMBIGUOUS_WORDS:
                continue
            cf = f"nuance:en:ambiguity:{low}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(self._emit(cf, raw, raw, "ambiguity", f"‘{raw}’ is ambiguous and { _AMBIGUOUS_WORDS[low] }", "neutral", "B1", 0.8, {"ambiguous_item": low}))
        return out

    def _learner_pitfalls(self, texts: list[str], seen: set[str]) -> list[CandidateObject]:
        out = []
        for raw in texts:
            low = raw.lower()
            if low not in _FALSE_FRIENDS:
                continue
            cf = f"nuance:en:learner_pitfall:{low}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(self._emit(cf, raw, raw, "learner_pitfall", f"Common learner pitfall: '{raw}' {_FALSE_FRIENDS[low]}", "neutral", "B1", 0.9, {"pitfall": low}))
        return out

    def _collocation(self, texts: list[str], seen: set[str]) -> list[CandidateObject]:
        out = []
        joined = " ".join(t.lower() for t in texts)
        for phrase, expl in _COLLOCATIONS.items():
            if phrase not in joined:
                continue
            key = phrase.replace(" ", "_")
            cf = f"nuance:en:collocation:{key}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(self._emit(cf, phrase, phrase, "collocation", expl, "neutral", "A2", 0.87, {"collocation": phrase}))
        return out

    def _regional_variation(self, texts: list[str], seen: set[str]) -> list[CandidateObject]:
        out = []
        for raw in texts:
            low = raw.lower()
            if low not in _REGIONAL:
                continue
            cf = f"nuance:en:regional_variation:{low}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(self._emit(cf, raw, raw, "regional_variation", _REGIONAL[low], "regional", "A2", 0.83, {"regional_item": low}))
        return out

    def _etymology(self, candidates: list[CandidateObject], seen: set[str]) -> list[CandidateObject]:
        from backend.dictionary.etymology import DEFAULT_STORE
        out = []
        for c in candidates:
            if c.type != "vocabulary":
                continue
            lemma = _lemma(c)
            entry = DEFAULT_STORE.get(self.language, lemma)
            if not entry:
                continue
            cf = f"nuance:en:etymology:{lemma.lower()}"
            if cf in seen:
                continue
            seen.add(cf)
            out.append(self._emit(cf, c.surface_form, c.label, "etymology", entry.origin_summary, "neutral", "B1", 0.85, {"etymology": entry.to_lesson_data()}, lemma=lemma))
        return out

    def _phrase_families(self, tokens: list[Any]) -> list[CandidateObject]:
        from backend.dictionary.phrase_families import match_phrase_families
        sentence_text = " ".join(_text(t) for t in tokens)
        legacy    = match_phrase_families([_text(t) for t in tokens], self.language)
        generated = self._cultural_references(sentence_text)
        return self._merge_candidates(legacy, generated)
