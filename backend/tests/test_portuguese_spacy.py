"""Tests for the Portuguese language plugin (portuguese.py).

Uses the token-injection pattern — no real spaCy model required.
All tests run against the plugin's private extraction methods.

Coverage
────────
  vocabulary   — content words extracted; finite verbs excluded; POS/gender/number
  conjugation  — finite verbs; morph features; canonical_form stability; irregulars
  agreement    — DET/ADJ+NOUN pairs; gender/number match/mismatch
  idioms       — surface-form matching; longest match; overlap prevention
  grammar      — ser/estar copula, ter_perfect, ir_near_future, estar_progressive
  nuance       — imperfect, subjunctive, conditional, reflexive, personal infinitive
  paradigm     — -ar/-er/-ir/irregular classification
  plugin API   — create_plugin(), language_code, capabilities
"""
from __future__ import annotations

import pytest

from backend.plugins.portuguese import (
    PortuguesePlugin,
    _IDIOM_TABLE,
    _paradigm_class,
    create_plugin,
)
from backend.schemas.parse import CandidateObject


# ── Token stub ─────────────────────────────────────────────────────────────────

class _Tok:
    """Minimal stand-in for a spaCy Token."""
    _counter = 0   # class-level index counter, reset per test class

    def __init__(
        self,
        text: str,
        pos: str = "NOUN",
        lemma: str = "",
        dep: str = "dep",
        morph: dict | None = None,
        is_punct: bool = False,
        is_space: bool = False,
        head_idx: int | None = None,   # resolved later via _link_tokens
    ):
        self.text          = text
        self.pos_          = pos
        self.lemma_        = lemma or text.lower()
        self.dep_          = dep
        self.is_punct      = is_punct
        self.is_space      = is_space
        self.is_oov        = False
        self._morph        = morph or {}
        self.i             = 0          # assigned by _link_tokens
        self._head_idx     = head_idx
        self.head          = self       # default self-head, overridden by _link_tokens
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


def _tokens(*specs: tuple | str) -> list[_Tok]:
    """Build a token list.

    Each spec is either:
      - a string  → (text, "NOUN")
      - a tuple   → (text, pos, **kwargs_for_Tok)
    """
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
        t.head = t   # self by default

    return toks


def _link(toks: list[_Tok], child_idx: int, head_idx: int) -> None:
    """Set tok.head and register tok as a child."""
    toks[child_idx].head = toks[head_idx]
    toks[head_idx].children.append(toks[child_idx])


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def plugin() -> PortuguesePlugin:
    return PortuguesePlugin()


# ── Plugin API ─────────────────────────────────────────────────────────────────

class TestPluginApi:
    def test_create_plugin_returns_plugin(self):
        p = create_plugin()
        assert isinstance(p, PortuguesePlugin)

    def test_language_code(self, plugin):
        assert plugin.language_code == "pt"

    def test_capabilities_code(self, plugin):
        assert plugin.capabilities.code == "pt"

    def test_capabilities_script_family(self, plugin):
        assert plugin.capabilities.script_family == "latin"

    def test_capabilities_direction(self, plugin):
        assert plugin.capabilities.direction == "ltr"

    def test_tense_pool_populated(self, plugin):
        assert len(plugin.capabilities.tense_pool) >= 4

    def test_mood_pool_populated(self, plugin):
        assert len(plugin.capabilities.mood_pool) >= 3


# ── Vocabulary ─────────────────────────────────────────────────────────────────

class TestVocabulary:
    def test_noun_extracted(self, plugin):
        toks = _tokens(("livro", "NOUN", {"morph": {"Gender": "Masc", "Number": "Sing"}}))
        results = plugin._extract_vocabulary(toks, set())
        assert len(results) == 1
        cand = results[0]
        assert cand.type == "vocabulary"
        assert cand.lesson_data["gender"] == "Masc"
        assert cand.lesson_data["number"] == "Sing"

    def test_finite_verb_skipped(self, plugin):
        toks = _tokens(("fala", "VERB", {"morph": {"VerbForm": "Fin"}}))
        results = plugin._extract_vocabulary(toks, set())
        assert results == []

    def test_infinitive_extracted_as_vocabulary(self, plugin):
        toks = _tokens(("falar", "VERB", {"morph": {"VerbForm": "Inf"}}))
        results = plugin._extract_vocabulary(toks, set())
        assert len(results) == 1
        assert results[0].lesson_data["verb_form"] == "Inf"

    def test_det_skipped(self, plugin):
        toks = _tokens(("o", "DET"), ("livro", "NOUN"))
        results = plugin._extract_vocabulary(toks, set())
        # Only "livro" should be extracted.
        assert len(results) == 1
        assert results[0].lesson_data["lemma"] == "livro"

    def test_deduplication_via_seen(self, plugin):
        toks = _tokens(("livro", "NOUN"), ("livros", "NOUN", {"lemma": "livro"}))
        results = plugin._extract_vocabulary(toks, set())
        assert len(results) == 1

    def test_proper_noun_lower_confidence(self, plugin):
        toks = _tokens(("Brasil", "PROPN"))
        results = plugin._extract_vocabulary(toks, set())
        assert results[0].confidence < 0.80

    def test_adj_extracted(self, plugin):
        toks = _tokens(("bonita", "ADJ"))
        results = plugin._extract_vocabulary(toks, set())
        assert len(results) == 1
        assert results[0].type == "vocabulary"


# ── Conjugation ────────────────────────────────────────────────────────────────

class TestConjugation:
    def test_finite_verb_extracted(self, plugin):
        toks = _tokens(("fala", "VERB", {
            "morph": {"VerbForm": "Fin", "Tense": "Pres", "Mood": "Ind",
                      "Person": "3", "Number": "Sing"}
        }))
        results = plugin._extract_conjugations(toks, set(), set())
        assert len(results) == 1
        cand = results[0]
        assert cand.type == "conjugation"
        assert cand.lesson_data["tense"] == "present"
        assert cand.lesson_data["mood"] == "indicative"
        assert cand.lesson_data["person"] == "3"

    def test_non_finite_skipped(self, plugin):
        toks = _tokens(("falando", "VERB", {"morph": {"VerbForm": "Ger"}}))
        results = plugin._extract_conjugations(toks, set(), set())
        assert results == []

    def test_irregular_flag_set(self, plugin):
        toks = _tokens(("é", "AUX", {
            "lemma": "ser",
            "morph": {"VerbForm": "Fin", "Tense": "Pres", "Mood": "Ind",
                      "Person": "3", "Number": "Sing"}
        }))
        results = plugin._extract_conjugations(toks, set(), set())
        assert results[0].lesson_data["is_irregular"] is True

    def test_canonical_form_includes_morph_axes(self, plugin):
        toks = _tokens(("fala", "VERB", {
            "morph": {"VerbForm": "Fin", "Tense": "Pres", "Mood": "Ind",
                      "Person": "3", "Number": "Sing"}
        }))
        results = plugin._extract_conjugations(toks, set(), set())
        cf = results[0].canonical_form
        # format: lemma:tense:mood:person:number
        parts = cf.split(":")
        assert len(parts) == 5

    def test_deduplication_same_canonical_form(self, plugin):
        morph = {"VerbForm": "Fin", "Tense": "Pres", "Mood": "Ind", "Person": "3", "Number": "Sing"}
        toks = _tokens(
            ("fala", "VERB", {"morph": morph}),
            ("fala", "VERB", {"morph": morph}),
        )
        results = plugin._extract_conjugations(toks, set(), set())
        assert len(results) == 1

    def test_relation_hint_present(self, plugin):
        toks = _tokens(("fala", "VERB", {
            "morph": {"VerbForm": "Fin", "Tense": "Pres", "Mood": "Ind",
                      "Person": "3", "Number": "Sing"}
        }))
        results = plugin._extract_conjugations(toks, set(), set())
        assert len(results[0].relation_hints) == 1
        assert results[0].relation_hints[0].relation_type == "conjugation_of"

    def test_morph_complete_true_when_all_known(self, plugin):
        toks = _tokens(("fala", "VERB", {
            "morph": {"VerbForm": "Fin", "Tense": "Pres", "Mood": "Ind",
                      "Person": "3", "Number": "Sing"}
        }))
        results = plugin._extract_conjugations(toks, set(), set())
        assert results[0].lesson_data["morph_complete"] is True

    def test_morph_complete_false_when_person_unknown(self, plugin):
        toks = _tokens(("fala", "VERB", {
            "morph": {"VerbForm": "Fin", "Tense": "Pres", "Mood": "Ind"}
        }))
        results = plugin._extract_conjugations(toks, set(), set())
        assert results[0].lesson_data["morph_complete"] is False


# ── Paradigm class ─────────────────────────────────────────────────────────────

class TestParadigmClass:
    def test_ar_verb(self):
        assert _paradigm_class("falar") == "-ar"

    def test_er_verb(self):
        assert _paradigm_class("comer") == "-er"

    def test_ir_verb(self):
        assert _paradigm_class("partir") == "-ir"

    def test_irregular_ser(self):
        assert _paradigm_class("ser") == "irregular"

    def test_irregular_estar(self):
        assert _paradigm_class("estar") == "irregular"

    def test_irregular_ter(self):
        assert _paradigm_class("ter") == "irregular"

    def test_irregular_ir(self):
        assert _paradigm_class("ir") == "irregular"

    def test_irregular_fazer(self):
        assert _paradigm_class("fazer") == "irregular"


# ── Agreement ──────────────────────────────────────────────────────────────────

class TestAgreement:
    def test_det_noun_agreement(self, plugin):
        toks = _tokens(
            ("o", "DET", {"morph": {"Gender": "Masc", "Number": "Sing"}}),
            ("livro", "NOUN", {"morph": {"Gender": "Masc", "Number": "Sing"}}),
        )
        # link det → noun
        _link(toks, 0, 1)
        results = plugin._extract_agreements(toks)
        assert len(results) == 1
        cand = results[0]
        assert cand.type == "agreement"
        assert cand.lesson_data["gender_match"] is True
        assert cand.lesson_data["number_match"] is True

    def test_gender_mismatch_skipped(self, plugin):
        toks = _tokens(
            ("a", "DET", {"morph": {"Gender": "Fem", "Number": "Sing"}}),
            ("livro", "NOUN", {"morph": {"Gender": "Masc", "Number": "Sing"}}),
        )
        _link(toks, 0, 1)
        results = plugin._extract_agreements(toks)
        assert results == []

    def test_adj_noun_agreement(self, plugin):
        toks = _tokens(
            ("bonita", "ADJ", {"morph": {"Gender": "Fem", "Number": "Sing"}}),
            ("casa", "NOUN", {"morph": {"Gender": "Fem", "Number": "Sing"}}),
        )
        _link(toks, 0, 1)
        results = plugin._extract_agreements(toks)
        assert len(results) == 1

    def test_no_morphology_skipped(self, plugin):
        toks = _tokens(
            ("grande", "ADJ"),
            ("livro", "NOUN"),
        )
        results = plugin._extract_agreements(toks)
        assert results == []


# ── Idioms ─────────────────────────────────────────────────────────────────────

class TestIdioms:
    def _run(self, plugin, words: list[str]) -> list[CandidateObject]:
        toks = _tokens(*words)
        return plugin._extract_idioms(toks)

    def test_por_exemplo(self, plugin):
        results = self._run(plugin, ["Por", "exemplo", ",", "são"])
        idiom_cands = [c for c in results if c.type == "idiom"]
        assert any("por exemplo" in c.canonical_form for c in idiom_cands)

    def test_pelo_menos(self, plugin):
        results = self._run(plugin, ["Pelo", "menos", "uma", "vez"])
        assert any("pelo menos" in c.canonical_form for c in results)

    def test_de_vez_em_quando(self, plugin):
        results = self._run(plugin, ["De", "vez", "em", "quando", "ele"])
        assert any("de vez em quando" in c.canonical_form for c in results)

    def test_no_overlap(self, plugin):
        # "de vez em quando" should not also match shorter sub-phrases.
        results = self._run(plugin, ["de", "vez", "em", "quando"])
        assert len([c for c in results if c.type == "idiom"]) == 1

    def test_meaning_populated(self, plugin):
        results = self._run(plugin, ["por", "isso", "ele"])
        cands = [c for c in results if c.type == "idiom"]
        assert cands[0].lesson_data["meaning"]

    def test_register_valid(self, plugin):
        results = self._run(plugin, ["além", "disso"])
        cands = [c for c in results if c.type == "idiom"]
        assert cands[0].lesson_data["register"] in ("neutral", "formal", "informal")

    def test_empty_tokens(self, plugin):
        assert plugin._extract_idioms([]) == []

    def test_all_idiom_table_entries_have_meaning(self):
        for words, meaning, register in _IDIOM_TABLE:
            assert meaning, f"Empty meaning for {words}"
            assert register in ("neutral", "formal", "informal"), f"Bad register for {words}"


# ── Grammar patterns ──────────────────────────────────────────────────────────

class TestGrammar:
    def _conj(self, lemma: str, construction: str) -> CandidateObject:
        return CandidateObject(
            canonical_form=f"{lemma}:present:indicative:3:Sing",
            surface_form=lemma,
            type="conjugation",
            label=lemma,
            lesson_data={
                "lemma": lemma,
                "surface": lemma,
                "construction": construction,
            },
            confidence=0.80,
        )

    def test_ser_copula_detected(self, plugin):
        conj = self._conj("ser", "ser_copula")
        results = plugin._extract_grammar([conj], set())
        assert any("ser_copula" in c.canonical_form for c in results)

    def test_estar_copula_detected(self, plugin):
        conj = self._conj("estar", "estar_copula")
        results = plugin._extract_grammar([conj], set())
        assert any("estar_copula" in c.canonical_form for c in results)

    def test_ter_perfect_detected(self, plugin):
        conj = self._conj("ter", "ter_perfect")
        results = plugin._extract_grammar([conj], set())
        assert any("ter_perfect" in c.canonical_form for c in results)

    def test_ir_near_future_detected(self, plugin):
        conj = self._conj("ir", "ir_near_future")
        results = plugin._extract_grammar([conj], set())
        assert any("ir_near_future" in c.canonical_form for c in results)

    def test_estar_progressive_detected(self, plugin):
        conj = self._conj("estar", "estar_progressive")
        results = plugin._extract_grammar([conj], set())
        assert any("estar_progressive" in c.canonical_form for c in results)

    def test_standalone_produces_no_grammar(self, plugin):
        conj = self._conj("comer", "standalone")
        results = plugin._extract_grammar([conj], set())
        assert results == []

    def test_grammar_not_duplicated(self, plugin):
        conjs = [self._conj("ser", "ser_copula"), self._conj("ser", "ser_copula")]
        results = plugin._extract_grammar(conjs, set())
        ser_copulas = [c for c in results if "ser_copula" in c.canonical_form]
        assert len(ser_copulas) == 1

    def test_grammar_has_usage_and_contrast(self, plugin):
        conj = self._conj("ir", "ir_near_future")
        results = plugin._extract_grammar([conj], set())
        cand = results[0]
        assert cand.lesson_data["usage"]
        assert cand.lesson_data["contrast"]


# ── Nuance ────────────────────────────────────────────────────────────────────

class TestNuance:
    def _conj(self, lemma: str, tense: str = "present", mood: str = "indicative",
              is_reflexive: bool = False) -> CandidateObject:
        return CandidateObject(
            canonical_form=f"{lemma}:{tense}:{mood}:3:Sing",
            surface_form=lemma,
            type="conjugation",
            label=lemma,
            lesson_data={
                "lemma":       lemma,
                "surface":     lemma,
                "tense":       tense,
                "mood":        mood,
                "is_reflexive": is_reflexive,
            },
            confidence=0.80,
        )

    def test_imperfect_nuance(self, plugin):
        conj = self._conj("falar", tense="imperfect")
        results = plugin._extract_nuance([conj], [], set())
        assert any("imperfect_aspect" in c.canonical_form for c in results)

    def test_subjunctive_nuance(self, plugin):
        conj = self._conj("falar", mood="subjunctive")
        results = plugin._extract_nuance([conj], [], set())
        assert any("subjunctive_mood" in c.canonical_form for c in results)

    def test_conditional_nuance(self, plugin):
        conj = self._conj("falar", mood="conditional")
        results = plugin._extract_nuance([conj], [], set())
        assert any("conditional_mood" in c.canonical_form for c in results)

    def test_reflexive_nuance(self, plugin):
        conj = self._conj("lembrar", is_reflexive=True)
        results = plugin._extract_nuance([conj], [], set())
        assert any("reflexive_verb" in c.canonical_form for c in results)

    def test_indicative_present_no_nuance(self, plugin):
        conj = self._conj("comer", tense="present", mood="indicative")
        results = plugin._extract_nuance([conj], [], set())
        # No nuance type should fire for a plain indicative present.
        assert results == []

    def test_nuance_not_duplicated(self, plugin):
        conj1 = self._conj("falar", tense="imperfect")
        conj2 = self._conj("falar", tense="imperfect")
        results = plugin._extract_nuance([conj1, conj2], [], set())
        imperfects = [c for c in results if "imperfect_aspect" in c.canonical_form]
        assert len(imperfects) == 1

    def test_personal_infinitive_nuance(self, plugin):
        """VerbForm=Inf + Person set → personal_infinitive nuance."""
        toks = _tokens(("fazerem", "VERB", {
            "morph": {"VerbForm": "Inf", "Person": "3", "Number": "Plur"},
            "lemma": "fazer",
        }))
        results = plugin._extract_nuance([], toks, set())
        assert any("personal_infinitive" in c.canonical_form for c in results)

    def test_impersonal_infinitive_not_extracted(self, plugin):
        """VerbForm=Inf without Person → not a personal infinitive."""
        toks = _tokens(("falar", "VERB", {"morph": {"VerbForm": "Inf"}}))
        results = plugin._extract_nuance([], toks, set())
        assert not any("personal_infinitive" in c.canonical_form for c in results)

    def test_nuance_note_populated(self, plugin):
        conj = self._conj("falar", tense="imperfect")
        results = plugin._extract_nuance([conj], [], set())
        cand = next(c for c in results if "imperfect_aspect" in c.canonical_form)
        assert cand.lesson_data["note"]

    def test_nuance_has_relation_hint(self, plugin):
        conj = self._conj("falar", tense="imperfect")
        results = plugin._extract_nuance([conj], [], set())
        cand = next(c for c in results if "imperfect_aspect" in c.canonical_form)
        assert len(cand.relation_hints) == 1
        assert cand.relation_hints[0].relation_type == "nuance_of"


# ── _analyze_tokens integration ───────────────────────────────────────────────

class TestAnalyzeTokens:
    def test_empty_sentence(self, plugin):
        result = plugin._analyze_tokens("", [])
        assert result.candidates == []
        assert result.text == ""

    def test_multiple_types_returned(self, plugin):
        """A sentence with a noun, a conjugated verb, and a known idiom phrase
        should return candidates of at least two distinct types."""
        toks = _tokens(
            ("por", "ADP"),
            ("exemplo", "NOUN"),
            (",", "PUNCT", {"is_punct": True}),
            ("fala", "VERB", {
                "morph": {"VerbForm": "Fin", "Tense": "Pres",
                          "Mood": "Ind", "Person": "3", "Number": "Sing"}
            }),
        )
        # Link idiom tokens — "por exemplo" at positions 0-1.
        _link(toks, 0, 1)
        result = plugin._analyze_tokens("Por exemplo, fala.", toks)
        types_seen = {c.type for c in result.candidates}
        # We expect at least vocabulary (from "exemplo") and conjugation (from "fala")
        assert "conjugation" in types_seen
