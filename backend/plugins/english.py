"""English language plugin — spaCy ``en_core_web_sm``.

Registers as ``language_code = "en"``.

─────────────────────────────────────────────────────────────────────────────
WHAT THE PLUGIN EXTRACTS
─────────────────────────────────────────────────────────────────────────────

**Vocabulary** — open-class content words (NOUN, PROPN, ADJ, ADV, non-finite
VERB).  Cross-tracking (``seen_vocab``) prevents the same lemma from
appearing twice in the same sentence.

  lesson_data keys: lemma, pos

**Conjugation** — finite verb forms where the surface differs from the lemma
(i.e., forms that require morphological knowledge: irregular past tense,
3rd-person singular present, and irregular copula/auxiliary forms).

  Covers:   ran → run (past), went → go (past), am/is/are/was/were → be
            walks → walk (3rd-sg present), has → have (3rd-sg present)
  Skips:    regular -ed forms that are already covered by grammar constructions
            (e.g., "was written" tokens are claimed by be_passive)
  Tenses:   present, past only — English has no synthetic future or
            subjunctive inflection.

  lesson_data keys: lemma, surface, tense, mood, person, number, morph_complete

**Grammar** — periphrastic construction objects derived by scanning spaCy
AUX and MD tokens.  One object per distinct construction type per sentence.
Covers:

  be_progressive       be + -ing       (is running)
  be_passive           be + VBN        (was written)
  have_perfect         have + VBN      (has finished)
  modal_verb           MD + VB         (should leave)
  going_to_future      going to + VB   (going to rain)

  lesson_data keys: pattern_id, pattern, usage, contrast, surface_verb

**Nuance** — via EnglishNuanceExtractor: register (formal/informal markers),
tone (hedging, intensifiers), politeness softeners, idiom transparency
(kick the bucket, etc.), lexical ambiguity, false-friend pitfalls, natural
collocations, regional variation (US/UK), etymology, and phrase families.

  lesson_data keys: nuance_type, explanation, register, learner_level,
                    source, plus type-specific keys

─────────────────────────────────────────────────────────────────────────────
CONFIDENCE SCORES
─────────────────────────────────────────────────────────────────────────────

  0.90  learner pitfalls (false friends) — high-confidence heuristic
  0.88  register markers — curated closed sets
  0.87  collocations — surface pattern match
  0.86  politeness softeners
  0.85  vocabulary (non-PROPN), grammar constructions, nuance/etymology
  0.84  tone markers (hedging, intensifiers)
  0.83  regional variation, conjugation (irregular/marked finite forms)
  0.82  idiom transparency
  0.80  ambiguity annotations
  0.65  PROPN vocabulary — may not generalise

─────────────────────────────────────────────────────────────────────────────
KNOWN LIMITATIONS
─────────────────────────────────────────────────────────────────────────────

- ``en_core_web_sm`` is a small model (~12 MB).  Morphology is sparse for
  irregular forms; POS errors occur in ambiguous constructions.
- Conjugation extraction targets only surface ≠ lemma forms; regular -ed
  past tense verbs whose surface already equals lemma+"ed" are still
  extracted (surface "walked" ≠ lemma "walk"), but their lesson content is
  thin.  Focus is on irregular verbs (went, ran, was, etc.) where the
  surface-to-lemma mapping is non-obvious.
- Tense pool is limited to ["present", "past"] — English has no inflectional
  future or subjunctive; those are expressed periphrastically (will, might).
- Grammar detection is heuristic window-scan, not full dependency analysis.
  "has been running" emits be_progressive rather than perfect-progressive.
- Idiom table covers only two fixed phrases (kick the bucket, piece of cake);
  emits type="nuance" not type="idiom", so idiom_detection=False.
- phrase_families=partial: 49 English entries in the phrase family catalog
  covering common idioms, proverbs, and literary misquotations.
- etymology=none: etymology store has no English entries yet.
- formality_register=partial: 12 curated markers (formal/informal);
  most formal/informal vocabulary is not covered.
- grammar_nuance=partial: 5 construction patterns (progressive, passive,
  perfect, modal, going-to) plus tone/politeness markers.
"""
from __future__ import annotations

import logging
from functools import cached_property
from typing import Any

from backend.dictionary.phrase_families import lookup_family_by_id
from backend.lesson.practice_hooks import hooks_for_language
from backend.nuance.en import EnglishNuanceExtractor
from backend.parsing.plugin_interface import Token
from backend.schemas.language import LanguageCapabilities, NuanceCapabilities
from backend.schemas.parse import CandidateObject, CandidateSentenceResult

logger = logging.getLogger(__name__)

# Universal-Dependencies POS tags excluded from vocabulary extraction.
_SKIP_POS = frozenset({
    "DET", "ADP", "CCONJ", "SCONJ", "CONJ", "PUNCT", "SPACE",
    "X", "SYM", "NUM", "PRON", "AUX", "PART", "INTJ",
})

# VerbForm values that classify a VERB token as non-finite.
_NON_FINITE_FORMS = frozenset({"Inf", "Part", "Ger"})

# Tense code → English display label (English only has two synthetic tenses).
_TENSE_DISPLAY: dict[str, str] = {
    "Past": "past",
    "Pres": "present",
}

# AUX lemmas that are interesting enough to emit as conjugation objects.
_INTERESTING_AUX = frozenset({"be", "have"})

# Grammar patterns: id → (label, usage, contrast)
_GRAMMAR_PATTERNS: dict[str, tuple[str, str, str]] = {
    "be_progressive": (
        "be + [verb-ing]",
        "Expresses an action in progress at a particular moment "
        "(e.g. 'is running' — the action is ongoing now).",
        "The simple present or past describes habitual or completed actions "
        "without emphasising their duration.",
    ),
    "be_passive": (
        "be + [past participle] (passive voice)",
        "Expresses a passive construction where the subject receives the "
        "action (e.g. 'was written by Shakespeare').",
        "The active voice ('Shakespeare wrote it') is more direct; passive "
        "is preferred when the agent is unknown or unimportant.",
    ),
    "have_perfect": (
        "have + [past participle]",
        "Expresses a past action with present relevance "
        "(e.g. 'has finished' — the result is still relevant now).",
        "The simple past ('finished') marks a completed event at a specific "
        "past time with no implied present connection.",
    ),
    "modal_verb": (
        "[modal] + [base verb]",
        "Expresses modality — ability, permission, obligation, or possibility "
        "(e.g. 'can run', 'should finish', 'must leave').",
        "Different modals carry distinct nuances: 'can' = ability, 'must' = "
        "strong obligation, 'should' = advice, 'might' = weak possibility.",
    ),
    "going_to_future": (
        "going to + [base verb]",
        "Expresses a planned or near-future action "
        "(e.g. 'going to leave' — the intention is already formed).",
        "The 'will' future is more spontaneous or predictive; 'going to' "
        "implies existing intention or visible evidence.",
    ),
}


class EnglishPlugin:
    language_code = "en"
    display_name  = "English"
    direction     = "ltr"
    capabilities  = LanguageCapabilities(
        code="en",
        display_name="English",
        direction="ltr",
        script_family="latin",
        tokenization_mode="whitespace",
        morphology_depth="shallow",      # present / past only; no inflectional future or subjunctive
        lesson_modes_supported=["morphology", "vocabulary", "dictionary"],
        analysis_depth="full",           # spaCy pipeline: POS + dep parse + nuance
        segmentation_quality="medium",   # en_core_web_sm sentence splits are reliable
        tokenization_quality="high",     # spaCy English tokenisation is excellent
        morphology_quality="low",        # two tenses, 3rd-sg marking only; agreement absent
        syntax_support=True,             # dep parse used for grammar construction detection
        idiom_detection=False,           # emits nuance type for idioms, not type="idiom"
        tts_lang_tag="en",
        transliteration_scheme=None,
        tense_pool=["present", "past"],  # only two inflectional tenses in English
        mood_pool=["indicative"],        # no inflectional subjunctive; modals handled separately
        nuance_capabilities=NuanceCapabilities(
            idioms="stub",               # 2 hardcoded phrases only (kick the bucket, piece of cake)
            phrase_families="partial",   # 49 English families in catalog; common idioms and proverbs
            literary_references="none",
            cultural_references="none",
            etymology="none",            # etymology store has 0 English entries
            formality_register="partial",# 12 curated formal/informal markers; significant gaps
            grammar_nuance="partial",    # 5 construction patterns + tone/politeness markers
            pronunciation_tts="partial", # browser TTS via lang="en" tag
            transliteration="none",
            proverb_tradition="none",
            classical_or_scriptural_allusion="none",
        ),
    )

    def __init__(self) -> None:
        self.lesson_store: dict[str, CandidateObject] = {}
        self.nuance_extractor = EnglishNuanceExtractor()

    # ------------------------------------------------------------------
    # Model — lazy, loaded at most once per process via cached_property
    # ------------------------------------------------------------------

    @cached_property
    def _nlp(self) -> Any:
        try:
            import spacy  # noqa: PLC0415
            return spacy.load("en_core_web_sm", disable=["ner"])
        except ImportError as exc:
            raise RuntimeError(
                "spaCy is not installed.  Run: pip install spacy"
            ) from exc
        except OSError as exc:
            raise RuntimeError(
                "spaCy model 'en_core_web_sm' not found. "
                "Run: python -m spacy download en_core_web_sm"
            ) from exc

    # ------------------------------------------------------------------
    # LanguagePlugin protocol
    # ------------------------------------------------------------------

    def analyze_text(self, text: str) -> list[CandidateSentenceResult]:
        """Parse full text in a single spaCy call; return one result per sentence."""
        doc = self._nlp(text.strip())
        results = []
        for sent in doc.sents:
            sent_text = sent.text.strip()
            if not sent_text:
                continue
            results.append(self._analyze_tokens(sent_text, list(sent)))
        return results

    def split_sentences(self, text: str) -> list[str]:
        doc = self._nlp(text.strip())
        return [s.text.strip() for s in doc.sents if s.text.strip()]

    def analyze_sentence(self, sentence: str) -> CandidateSentenceResult:
        doc = self._nlp(sentence)
        return self._analyze_tokens(sentence, list(doc))

    def get_lesson(self, object_id: str) -> CandidateObject | None:
        lo = self.lesson_store.get(object_id)
        if lo is not None:
            return lo
        return lookup_family_by_id(object_id)

    def practice_hooks(self):
        return hooks_for_language("en")

    # ------------------------------------------------------------------
    # Analysis
    # ------------------------------------------------------------------

    def _analyze_tokens(
        self, sentence: str, tokens: list[Any]
    ) -> CandidateSentenceResult:
        # Grammar runs first; its surface tokens may overlap with conjugation.
        grammar_candidates = self._extract_grammar(tokens)
        grammar_surfaces = self._phrase_surface_words(grammar_candidates)

        # Conjugation: finite verb forms not already claimed by grammar patterns.
        conj_candidates = self._extract_conjugations(tokens, grammar_surfaces)

        # Build Token objects for nuance extractor compatibility.
        token_objs = [
            Token(text=t.text, lemma=t.lemma_, pos=t.pos_, morph=t.morph.to_dict())
            for t in tokens
        ]

        seen_vocab: set[str] = set()
        vocab_candidates = self._extract_vocabulary(tokens, seen_vocab)

        nuance_candidates = self.nuance_extractor.extract_nuance(
            sentence=sentence,
            tokens=token_objs,
            candidates=vocab_candidates,
            language=self.language_code,
        )

        # Re-extract vocabulary, skipping words already covered by phrases/idioms.
        skip_words = self._phrase_surface_words(grammar_candidates + nuance_candidates)
        if skip_words:
            seen_vocab.clear()
            vocab_candidates = self._extract_vocabulary(tokens, seen_vocab, skip_words=skip_words)
            nuance_candidates = self.nuance_extractor.extract_nuance(
                sentence=sentence,
                tokens=token_objs,
                candidates=vocab_candidates,
                language=self.language_code,
            )

        return CandidateSentenceResult(
            text=sentence,
            candidates=grammar_candidates + conj_candidates + nuance_candidates + vocab_candidates,
        )

    def _extract_conjugations(
        self,
        tokens: list[Any],
        skip_surfaces: set[str],
    ) -> list[CandidateObject]:
        """Extract finite verb forms as conjugation objects.

        Targets forms where the surface differs from the lemma — irregular
        past tense (went, ran, was), 3rd-person singular present (walks,
        has), and irregular copula/auxiliary forms (am, is, are, were).
        Tokens already claimed by grammar constructions are skipped.
        """
        seen_lemmas: set[str] = set()
        candidates: list[CandidateObject] = []

        for token in tokens:
            pos = token.pos_

            if pos not in ("VERB", "AUX"):
                continue

            verb_form = (token.morph.get("VerbForm") or [""])[0]
            if verb_form != "Fin":
                continue

            # Only extract interesting auxiliary verbs (be, have).
            if pos == "AUX" and token.lemma_.lower() not in _INTERESTING_AUX:
                continue

            surface = token.text.lower()
            lemma   = token.lemma_.lower()

            # Only emit when morphology adds information (surface ≠ lemma).
            if surface == lemma:
                continue

            # Skip if the surface word is claimed by a grammar construction.
            if surface in skip_surfaces:
                continue

            # Deduplicate by lemma within the sentence.
            if lemma in seen_lemmas:
                continue
            seen_lemmas.add(lemma)

            tense_code  = (token.morph.get("Tense")  or [""])[0]
            person_code = (token.morph.get("Person") or [""])[0]
            number_code = (token.morph.get("Number") or [""])[0]

            tense = _TENSE_DISPLAY.get(tense_code, "unknown")
            mood  = "indicative" if tense != "unknown" else "unknown"

            morph_complete = bool(tense_code and person_code and number_code)
            canonical = f"{lemma}:{tense}:{mood}:{person_code}:{number_code}"

            candidates.append(CandidateObject(
                canonical_form=canonical,
                surface_form=token.text,
                type="conjugation",
                label=token.text,
                lesson_data={
                    "lemma":          lemma,
                    "surface":        token.text,
                    "tense":          tense if tense != "unknown" else None,
                    "mood":           mood  if mood  != "unknown" else None,
                    "person":         person_code or None,
                    "number":         number_code or None,
                    "morph_complete": morph_complete,
                },
                confidence=0.83,
            ))

        return candidates

    def _extract_vocabulary(
        self,
        tokens: list[Any],
        seen: set[str],
        skip_words: set[str] | None = None,
    ) -> list[CandidateObject]:
        candidates: list[CandidateObject] = []
        for token in tokens:
            pos = token.pos_
            if pos in _SKIP_POS:
                continue
            if pos == "VERB":
                verb_form = (token.morph.get("VerbForm") or [""])[0]
                if verb_form not in _NON_FINITE_FORMS:
                    continue
            lemma = token.lemma_.lower()
            if not lemma or not lemma.isalpha():
                continue
            if skip_words and (lemma in skip_words or token.text.lower() in skip_words):
                continue
            if lemma in seen:
                continue
            seen.add(lemma)
            lesson: dict[str, Any] = {"lemma": lemma, "pos": pos}
            confidence = 0.85
            if pos == "PROPN":
                confidence = 0.72
                lesson["confidence_note"] = "proper noun — may not generalise across contexts"
            candidates.append(CandidateObject(
                canonical_form=lemma,
                surface_form=token.text,
                type="vocabulary",
                label=token.text,
                lesson_data=lesson,
                confidence=confidence,
            ))
        return candidates

    def _extract_grammar(self, tokens: list[Any]) -> list[CandidateObject]:
        seen: set[str] = set()
        grammar: list[CandidateObject] = []
        n = len(tokens)
        toks = [(t.lemma_.lower(), t.pos_, t.tag_) for t in tokens]

        # Pre-pass: going-to future — must run before progressive so that
        # "is going to run" does not also emit be_progressive.
        going_to_vbg: set[int] = set()
        for i, t in enumerate(tokens):
            if (
                t.lemma_.lower() == "go"
                and t.tag_ == "VBG"
                and i + 2 < n
                and tokens[i + 1].tag_ == "TO"
                and tokens[i + 2].tag_ == "VB"
            ):
                going_to_vbg.add(i)
                if "going_to_future" not in seen:
                    seen.add("going_to_future")
                    grammar.append(self._emit_grammar(
                        "going_to_future",
                        f"{t.text} to {tokens[i + 2].text}",
                    ))

        # Main pass
        for i, (lemma, pos, tag) in enumerate(toks):
            # Modal: MD + (adv/neg)* + VB
            if tag == "MD":
                for k in range(i + 1, min(i + 5, n)):
                    if toks[k][2] == "VB":
                        if "modal_verb" not in seen:
                            seen.add("modal_verb")
                            grammar.append(self._emit_grammar(
                                "modal_verb",
                                f"{tokens[i].text} {tokens[k].text}",
                            ))
                        break
                    if toks[k][1] not in ("ADV", "PART"):
                        break
                continue

            if pos != "AUX":
                continue

            # Scan ahead for the nearest relevant verb form.
            found_k: int | None = None
            found_vtag: str | None = None
            for k in range(i + 1, min(i + 5, n)):
                if toks[k][2] in ("VBG", "VBN"):
                    found_k = k
                    found_vtag = toks[k][2]
                    break
                if toks[k][1] not in ("ADV", "PART"):
                    break

            if found_k is None:
                continue

            found_lemma = toks[found_k][0]

            # Progressive: [be] + VBG — skip going-to indices
            if lemma == "be" and found_vtag == "VBG" and found_k not in going_to_vbg:
                if "be_progressive" not in seen:
                    seen.add("be_progressive")
                    grammar.append(self._emit_grammar(
                        "be_progressive",
                        f"{tokens[i].text} {tokens[found_k].text}",
                    ))

            # Passive: [be] + VBN (exclude 'been', which is part of perfect-passive)
            elif lemma == "be" and found_vtag == "VBN" and found_lemma != "be":
                if "be_passive" not in seen:
                    seen.add("be_passive")
                    grammar.append(self._emit_grammar(
                        "be_passive",
                        f"{tokens[i].text} {tokens[found_k].text}",
                    ))

            # Perfect: [have] + VBN (exclude 'been' → perfect-progressive/passive handled above)
            elif lemma == "have" and found_vtag == "VBN" and found_lemma != "be":
                if "have_perfect" not in seen:
                    seen.add("have_perfect")
                    grammar.append(self._emit_grammar(
                        "have_perfect",
                        f"{tokens[i].text} {tokens[found_k].text}",
                    ))

        return grammar

    def _emit_grammar(self, pattern_id: str, surface: str) -> CandidateObject:
        label, usage, contrast = _GRAMMAR_PATTERNS[pattern_id]
        return CandidateObject(
            canonical_form=f"grammar:{pattern_id}",
            surface_form=surface,
            type="grammar",
            label=label,
            lesson_data={
                "pattern_id": pattern_id,
                "pattern": label,
                "usage": usage,
                "contrast": contrast,
                "surface_verb": surface,
            },
            confidence=0.85,
        )

    def _phrase_surface_words(self, candidates: list[CandidateObject]) -> set[str]:
        skip: set[str] = set()
        for candidate in candidates:
            if candidate.type not in {"phrase_family", "idiom", "grammar"}:
                continue
            if not candidate.surface_form:
                continue
            skip.update(word.lower() for word in candidate.surface_form.split())
        return skip


def create_plugin() -> EnglishPlugin:
    return EnglishPlugin()
