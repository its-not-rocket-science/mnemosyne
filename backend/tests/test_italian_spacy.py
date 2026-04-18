"""Tests for the Italian language plugin (italian.py).

Uses the token-injection pattern — no real spaCy model required.

Coverage
────────
  vocabulary   — content words extracted; finite verbs excluded; POS/gender/number
  conjugation  — finite verbs; morph features; canonical_form; irregulars
  agreement    — DET/ADJ+NOUN pairs; gender/number match/mismatch
  idioms       — surface-form matching; longest match; overlap prevention
  grammar      — essere_copula, avere_perfect, essere_perfect,
                  stare_progressive, andare_near_future
  nuance       — imperfect, subjunctive, conditional, reflexive
  paradigm     — -are/-ere/-ire/irregular classification
  plugin API   — create_plugin(), language_code, capabilities
"""
from __future__ import annotations

import pytest

from backend.plugins.italian import (
    ItalianPlugin,
    _IDIOM_TABLE,
    _paradigm_class,
    create_plugin,
)
from backend.schemas.parse import CandidateObject


# ── Token stub ─────────────────────────────────────────────────────────────────

class _Tok:
    def __init__(
        self,
        text: str,
        pos: str = "NOUN",
        lemma: str = "",
        dep: str = "dep",
        morph: dict | None = None,
        is_punct: bool = False,
        is_space: bool = False,
    ):
        self.text          = text
        self.pos_          = pos
        self.lemma_        = lemma or text.lower()
        self.dep_          = dep
        self.is_punct      = is_punct
        self.is_space      = is_space
        self.is_oov        = False
        self._morph        = morph or {}
        self.i             = 0
        self.head          = self
        self.children: list[_Tok] = []
        self.is_sent_start = False

    class _Morph:
        def __init__(self, d: dict):
            self._d = d
        def get(self, feat: str) -> list[str]:
            val = self._d.get(feat)
            return [val] if val else []

    @property
    def morph(self):
        return self._Morph(self._morph)

    def __repr__(self):
        return f"<Tok {self.text!r} {self.pos_}>"


def _tokens(*specs) -> list[_Tok]:
    toks: list[_Tok] = []
    for spec in specs:
        if isinstance(spec, str):
            toks.append(_Tok(spec))
        elif len(spec) == 2:
            toks.append(_Tok(spec[0], pos=spec[1]))
        else:
            text, pos, *rest = spec
            kwargs = rest[0] if rest else {}
            toks.append(_Tok(text, pos=pos, **kwargs))
    for i, t in enumerate(toks):
        t.i = i
        t.head = t
    return toks


def _link(toks: list[_Tok], child_idx: int, head_idx: int) -> None:
    toks[child_idx].head = toks[head_idx]
    toks[head_idx].children.append(toks[child_idx])


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def plugin() -> ItalianPlugin:
    return ItalianPlugin()


# ── Plugin API ─────────────────────────────────────────────────────────────────

class TestPluginApi:
    def test_create_plugin_returns_plugin(self):
        assert isinstance(create_plugin(), ItalianPlugin)

    def test_language_code(self, plugin):
        assert plugin.language_code == "it"

    def test_capabilities_script_family(self, plugin):
        assert plugin.capabilities.script_family == "latin"

    def test_capabilities_direction(self, plugin):
        assert plugin.capabilities.direction == "ltr"

    def test_tense_pool_populated(self, plugin):
        assert len(plugin.capabilities.tense_pool) >= 4

    def test_mood_pool_includes_subjunctive(self, plugin):
        assert "subjunctive" in plugin.capabilities.mood_pool


# ── Vocabulary ─────────────────────────────────────────────────────────────────

class TestVocabulary:
    def test_noun_with_gender_and_number(self, plugin):
        toks = _tokens(("libro", "NOUN", {"morph": {"Gender": "Masc", "Number": "Sing"}}))
        results = plugin._extract_vocabulary(toks, set())
        assert len(results) == 1
        data = results[0].lesson_data
        assert data["gender"] == "Masc"
        assert data["number"] == "Sing"

    def test_finite_verb_not_extracted(self, plugin):
        toks = _tokens(("parla", "VERB", {"morph": {"VerbForm": "Fin"}}))
        assert plugin._extract_vocabulary(toks, set()) == []

    def test_infinitive_extracted(self, plugin):
        toks = _tokens(("parlare", "VERB", {"morph": {"VerbForm": "Inf"}}))
        results = plugin._extract_vocabulary(toks, set())
        assert len(results) == 1
        assert results[0].lesson_data["verb_form"] == "Inf"

    def test_gerund_extracted(self, plugin):
        toks = _tokens(("parlando", "VERB", {"morph": {"VerbForm": "Ger"}}))
        results = plugin._extract_vocabulary(toks, set())
        assert len(results) == 1

    def test_det_skipped(self, plugin):
        toks = _tokens(("il", "DET"), ("libro", "NOUN"))
        results = plugin._extract_vocabulary(toks, set())
        assert len(results) == 1
        assert results[0].lesson_data["lemma"] == "libro"

    def test_proper_noun_lower_confidence(self, plugin):
        toks = _tokens(("Roma", "PROPN"))
        results = plugin._extract_vocabulary(toks, set())
        assert results[0].confidence < 0.80

    def test_deduplication(self, plugin):
        toks = _tokens(
            ("libro", "NOUN"),
            ("libri", "NOUN", {"lemma": "libro"}),
        )
        results = plugin._extract_vocabulary(toks, set())
        assert len(results) == 1


# ── Conjugation ────────────────────────────────────────────────────────────────

class TestConjugation:
    def test_finite_verb_extracted(self, plugin):
        toks = _tokens(("parla", "VERB", {
            "morph": {"VerbForm": "Fin", "Tense": "Pres", "Mood": "Ind",
                      "Person": "3", "Number": "Sing"}
        }))
        results = plugin._extract_conjugations(toks, set(), set())
        assert len(results) == 1
        data = results[0].lesson_data
        assert data["tense"] == "present"
        assert data["mood"] == "indicative"
        assert data["person"] == "3"

    def test_non_finite_skipped(self, plugin):
        toks = _tokens(("parlando", "VERB", {"morph": {"VerbForm": "Ger"}}))
        assert plugin._extract_conjugations(toks, set(), set()) == []

    def test_irregular_essere_flagged(self, plugin):
        toks = _tokens(("è", "AUX", {
            "lemma": "essere",
            "morph": {"VerbForm": "Fin", "Tense": "Pres", "Mood": "Ind",
                      "Person": "3", "Number": "Sing"}
        }))
        results = plugin._extract_conjugations(toks, set(), set())
        assert results[0].lesson_data["is_irregular"] is True

    def test_canonical_form_five_parts(self, plugin):
        toks = _tokens(("parla", "VERB", {
            "morph": {"VerbForm": "Fin", "Tense": "Pres", "Mood": "Ind",
                      "Person": "3", "Number": "Sing"}
        }))
        results = plugin._extract_conjugations(toks, set(), set())
        assert len(results[0].canonical_form.split(":")) == 5

    def test_relation_hint_conjugation_of(self, plugin):
        toks = _tokens(("parla", "VERB", {
            "morph": {"VerbForm": "Fin", "Tense": "Pres", "Mood": "Ind",
                      "Person": "3", "Number": "Sing"}
        }))
        results = plugin._extract_conjugations(toks, set(), set())
        assert results[0].relation_hints[0].relation_type == "conjugation_of"

    def test_morph_complete_true(self, plugin):
        toks = _tokens(("parla", "VERB", {
            "morph": {"VerbForm": "Fin", "Tense": "Pres", "Mood": "Ind",
                      "Person": "3", "Number": "Sing"}
        }))
        results = plugin._extract_conjugations(toks, set(), set())
        assert results[0].lesson_data["morph_complete"] is True

    def test_morph_complete_false_missing_person(self, plugin):
        toks = _tokens(("parla", "VERB", {
            "morph": {"VerbForm": "Fin", "Tense": "Pres", "Mood": "Ind"}
        }))
        results = plugin._extract_conjugations(toks, set(), set())
        assert results[0].lesson_data["morph_complete"] is False

    def test_deduplication(self, plugin):
        morph = {"VerbForm": "Fin", "Tense": "Pres", "Mood": "Ind",
                 "Person": "3", "Number": "Sing"}
        toks = _tokens(
            ("parla", "VERB", {"morph": morph}),
            ("parla", "VERB", {"morph": morph}),
        )
        assert len(plugin._extract_conjugations(toks, set(), set())) == 1


# ── Paradigm class ─────────────────────────────────────────────────────────────

class TestParadigmClass:
    def test_are_verb(self):     assert _paradigm_class("parlare") == "-are"
    def test_ere_verb(self):     assert _paradigm_class("vedere") == "-ere"
    def test_ire_verb(self):     assert _paradigm_class("dormire") == "-ire"
    def test_essere_irregular(self): assert _paradigm_class("essere") == "irregular"
    def test_avere_irregular(self):  assert _paradigm_class("avere") == "irregular"
    def test_fare_irregular(self):   assert _paradigm_class("fare") == "irregular"
    def test_andare_irregular(self): assert _paradigm_class("andare") == "irregular"
    def test_stare_irregular(self):  assert _paradigm_class("stare") == "irregular"


# ── Agreement ──────────────────────────────────────────────────────────────────

class TestAgreement:
    def test_det_noun_matched(self, plugin):
        toks = _tokens(
            ("il", "DET",  {"morph": {"Gender": "Masc", "Number": "Sing"}}),
            ("libro", "NOUN", {"morph": {"Gender": "Masc", "Number": "Sing"}}),
        )
        _link(toks, 0, 1)
        results = plugin._extract_agreements(toks)
        assert len(results) == 1
        assert results[0].lesson_data["gender_match"] is True

    def test_gender_mismatch_dropped(self, plugin):
        toks = _tokens(
            ("la", "DET",  {"morph": {"Gender": "Fem", "Number": "Sing"}}),
            ("libro", "NOUN", {"morph": {"Gender": "Masc", "Number": "Sing"}}),
        )
        _link(toks, 0, 1)
        assert plugin._extract_agreements(toks) == []

    def test_adj_post_nominal(self, plugin):
        toks = _tokens(
            ("libro", "NOUN", {"morph": {"Gender": "Masc", "Number": "Sing"}}),
            ("bello", "ADJ",  {"morph": {"Gender": "Masc", "Number": "Sing"}}),
        )
        _link(toks, 1, 0)
        results = plugin._extract_agreements(toks)
        assert len(results) == 1

    def test_no_morphology_skipped(self, plugin):
        toks = _tokens(("grande", "ADJ"), ("libro", "NOUN"))
        assert plugin._extract_agreements(toks) == []


# ── Idioms ─────────────────────────────────────────────────────────────────────

class TestIdioms:
    def _run(self, plugin, words: list[str]) -> list[CandidateObject]:
        toks = _tokens(*words)
        return plugin._extract_idioms(toks)

    def test_per_esempio(self, plugin):
        results = self._run(plugin, ["Per", "esempio", ",", "è"])
        assert any("per esempio" in c.canonical_form for c in results)

    def test_tuttavia_single_token(self, plugin):
        results = self._run(plugin, ["Tuttavia", ",", "parla"])
        assert any("tuttavia" in c.canonical_form for c in results)

    def test_di_tanto_in_tanto_four_token(self, plugin):
        results = self._run(plugin, ["di", "tanto", "in", "tanto", "va"])
        assert any("di tanto in tanto" in c.canonical_form for c in results)

    def test_no_overlap(self, plugin):
        results = self._run(plugin, ["di", "tanto", "in", "tanto"])
        idioms = [c for c in results if c.type == "idiom"]
        assert len(idioms) == 1

    def test_meaning_populated(self, plugin):
        results = self._run(plugin, ["quindi", "parla"])
        cands = [c for c in results if c.type == "idiom"]
        assert cands[0].lesson_data["meaning"]

    def test_register_valid(self, plugin):
        results = self._run(plugin, ["tuttavia"])
        cands = [c for c in results if c.type == "idiom"]
        assert cands[0].lesson_data["register"] in ("neutral", "formal", "informal")

    def test_empty_tokens(self, plugin):
        assert plugin._extract_idioms([]) == []

    def test_all_entries_have_meaning_and_valid_register(self):
        for words, meaning, register in _IDIOM_TABLE:
            assert meaning, f"Empty meaning for {words}"
            assert register in ("neutral", "formal", "informal"), \
                f"Bad register for {words}"


# ── Grammar patterns ──────────────────────────────────────────────────────────

class TestGrammar:
    def _conj(self, lemma: str, construction: str) -> CandidateObject:
        return CandidateObject(
            canonical_form=f"{lemma}:present:indicative:3:Sing",
            surface_form=lemma,
            type="conjugation",
            label=lemma,
            lesson_data={"lemma": lemma, "surface": lemma, "construction": construction},
            confidence=0.80,
        )

    def test_essere_copula(self, plugin):
        results = plugin._extract_grammar([self._conj("essere", "copula")], set())
        assert any("essere_copula" in c.canonical_form for c in results)

    def test_avere_perfect(self, plugin):
        results = plugin._extract_grammar([self._conj("avere", "perfect")], set())
        assert any("avere_perfect" in c.canonical_form for c in results)

    def test_essere_perfect(self, plugin):
        results = plugin._extract_grammar([self._conj("essere", "perfect")], set())
        assert any("essere_perfect" in c.canonical_form for c in results)

    def test_stare_progressive(self, plugin):
        results = plugin._extract_grammar([self._conj("stare", "stare_progressive")], set())
        assert any("stare_progressive" in c.canonical_form for c in results)

    def test_andare_near_future(self, plugin):
        results = plugin._extract_grammar([self._conj("andare", "andare_near_future")], set())
        assert any("andare_near_future" in c.canonical_form for c in results)

    def test_standalone_no_grammar(self, plugin):
        assert plugin._extract_grammar([self._conj("mangiare", "standalone")], set()) == []

    def test_not_duplicated(self, plugin):
        conjs = [self._conj("essere", "copula"), self._conj("essere", "copula")]
        results = plugin._extract_grammar(conjs, set())
        assert len([c for c in results if "essere_copula" in c.canonical_form]) == 1

    def test_usage_and_contrast_present(self, plugin):
        results = plugin._extract_grammar([self._conj("avere", "perfect")], set())
        cand = results[0]
        assert cand.lesson_data["usage"]
        assert cand.lesson_data["contrast"]


# ── Nuance ─────────────────────────────────────────────────────────────────────

class TestNuance:
    def _conj(self, lemma: str, tense: str = "present", mood: str = "indicative",
              is_reflexive: bool = False) -> CandidateObject:
        return CandidateObject(
            canonical_form=f"{lemma}:{tense}:{mood}:3:Sing",
            surface_form=lemma,
            type="conjugation",
            label=lemma,
            lesson_data={
                "lemma": lemma, "surface": lemma,
                "tense": tense, "mood": mood,
                "is_reflexive": is_reflexive,
            },
            confidence=0.80,
        )

    def test_imperfect(self, plugin):
        results = plugin._extract_nuance([self._conj("parlare", tense="imperfect")], set())
        assert any("imperfect_aspect" in c.canonical_form for c in results)

    def test_subjunctive(self, plugin):
        results = plugin._extract_nuance([self._conj("parlare", mood="subjunctive")], set())
        assert any("subjunctive_mood" in c.canonical_form for c in results)

    def test_conditional(self, plugin):
        results = plugin._extract_nuance([self._conj("parlare", mood="conditional")], set())
        assert any("conditional_mood" in c.canonical_form for c in results)

    def test_reflexive(self, plugin):
        results = plugin._extract_nuance([self._conj("alzare", is_reflexive=True)], set())
        assert any("reflexive_verb" in c.canonical_form for c in results)

    def test_plain_indicative_no_nuance(self, plugin):
        results = plugin._extract_nuance([self._conj("mangiare")], set())
        assert results == []

    def test_not_duplicated(self, plugin):
        c1 = self._conj("parlare", tense="imperfect")
        c2 = self._conj("parlare", tense="imperfect")
        results = plugin._extract_nuance([c1, c2], set())
        assert len([c for c in results if "imperfect_aspect" in c.canonical_form]) == 1

    def test_note_populated(self, plugin):
        results = plugin._extract_nuance([self._conj("parlare", mood="subjunctive")], set())
        cand = next(c for c in results if "subjunctive_mood" in c.canonical_form)
        assert cand.lesson_data["note"]

    def test_relation_hint_present(self, plugin):
        results = plugin._extract_nuance([self._conj("parlare", tense="imperfect")], set())
        cand = next(c for c in results if "imperfect_aspect" in c.canonical_form)
        assert cand.relation_hints[0].relation_type == "nuance_of"

    def test_reflexive_note_mentions_essere(self, plugin):
        """Reflexive nuance note should mention essere (auxiliary rule)."""
        results = plugin._extract_nuance([self._conj("alzare", is_reflexive=True)], set())
        cand = next(c for c in results if "reflexive_verb" in c.canonical_form)
        assert "essere" in cand.lesson_data["note"]


# ── _analyze_tokens integration ───────────────────────────────────────────────

class TestAnalyzeTokens:
    def test_empty(self, plugin):
        result = plugin._analyze_tokens("", [])
        assert result.candidates == []

    def test_conjugation_and_vocabulary_extracted(self, plugin):
        toks = _tokens(
            ("il", "DET"),
            ("libro", "NOUN", {"morph": {"Gender": "Masc", "Number": "Sing"}}),
            ("è", "AUX", {
                "lemma": "essere",
                "morph": {"VerbForm": "Fin", "Tense": "Pres", "Mood": "Ind",
                          "Person": "3", "Number": "Sing"},
                "dep": "cop",
            }),
            ("bello", "ADJ", {"morph": {"Gender": "Masc", "Number": "Sing"}}),
            (".", "PUNCT", {"is_punct": True}),
        )
        result = plugin._analyze_tokens("Il libro è bello.", toks)
        types = {c.type for c in result.candidates}
        assert "conjugation" in types
        assert "vocabulary" in types
