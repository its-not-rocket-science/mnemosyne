"""Tests for idiom and nuance extraction in German and Russian plugins.

Uses the token-injection pattern (bypass spaCy) so tests run without
a loaded model and in constant time.
"""
from __future__ import annotations

import types
import pytest

from backend.plugins.german import GermanPlugin, _IDIOM_TABLE as DE_IDIOMS, create_plugin as de_plugin
from backend.plugins.russian import RussianPlugin, _IDIOM_TABLE as RU_IDIOMS, create_plugin as ru_plugin
from backend.schemas.parse import CandidateObject


# ── Token stub ────────────────────────────────────────────────────────────────

class _Tok:
    """Minimal stand-in for a spaCy Token with the attributes our code reads."""
    def __init__(
        self, text: str, pos: str = "NOUN", lemma: str = "",
        dep: str = "dep",
        morph: dict | None = None,
        is_punct: bool = False,
        is_space: bool = False,
    ):
        self.text     = text
        self.pos_     = pos
        self.lemma_   = lemma or text.lower()
        self.dep_     = dep
        self.is_punct = is_punct
        self.is_space = is_space
        self.is_oov   = False
        self._morph   = morph or {}
        # head / children — not used by idiom extraction so stub them
        self.head     = self
        self.children = []

    def morph_get(self, feat: str) -> list[str]:
        val = self._morph.get(feat)
        return [val] if val else []

    def __repr__(self):
        return f"<Tok {self.text!r}>"


def _tok(text: str, pos: str = "NOUN", **kw) -> _Tok:
    return _Tok(text, pos=pos, **kw)


# ── German idiom extraction ────────────────────────────────────────────────────

class TestGermanIdioms:
    @pytest.fixture()
    def plugin(self):
        return GermanPlugin()

    def _run(self, plugin, words: list[str]) -> list[CandidateObject]:
        tokens = [_tok(w) for w in words]
        return plugin._extract_idioms(tokens)

    def test_zum_beispiel(self, plugin):
        results = self._run(plugin, ["Zum", "Beispiel", "ist", "das", "gut"])
        idiom_cands = [c for c in results if c.type == "idiom"]
        assert any("zum beispiel" in c.canonical_form for c in idiom_cands)

    def test_auf_jeden_fall(self, plugin):
        results = self._run(plugin, ["Auf", "jeden", "Fall", "komme", "ich"])
        assert any("auf jeden fall" in c.canonical_form for c in results)

    def test_trotzdem_single_token(self, plugin):
        results = self._run(plugin, ["Er", "kam", "trotzdem"])
        assert any("trotzdem" in c.canonical_form for c in results)

    def test_meaning_and_register_populated(self, plugin):
        results = self._run(plugin, ["trotzdem"])
        assert len(results) == 1
        cand = results[0]
        assert cand.lesson_data["meaning"]
        assert cand.lesson_data["register"] in ("neutral", "formal", "informal")

    def test_no_overlap(self, plugin):
        # "zum beispiel" should not also extract "zum" or "beispiel" separately.
        results = self._run(plugin, ["Zum", "Beispiel"])
        assert len(results) == 1

    def test_empty_tokens(self, plugin):
        assert self._run(plugin, []) == []

    def test_no_match_returns_empty(self, plugin):
        results = self._run(plugin, ["Hund", "läuft", "schnell"])
        assert results == []

    def test_confidence_0_90(self, plugin):
        results = self._run(plugin, ["trotzdem"])
        assert results[0].confidence == pytest.approx(0.90)

    def test_all_table_entries_are_lowercase(self):
        for words, _meaning, _register in DE_IDIOMS:
            for w in words:
                assert w == w.lower(), f"Not lowercase: {w!r}"

    def test_idiom_detection_capability(self, plugin):
        assert plugin.capabilities.idiom_detection is True


# ── Russian idiom extraction ───────────────────────────────────────────────────

class TestRussianIdioms:
    @pytest.fixture()
    def plugin(self):
        return RussianPlugin()

    def _run(self, plugin, words: list[str]) -> list[CandidateObject]:
        tokens = [_tok(w) for w in words]
        return plugin._extract_idioms(tokens)

    def test_konechno_single(self, plugin):
        results = self._run(plugin, ["Он", "конечно", "придёт"])
        assert any("конечно" in c.canonical_form for c in results)

    def test_na_samom_dele(self, plugin):
        results = self._run(plugin, ["на", "самом", "деле", "это", "правда"])
        assert any("на самом деле" in c.canonical_form for c in results)

    def test_do_svidaniya(self, plugin):
        results = self._run(plugin, ["до", "свидания"])
        assert any("до свидания" in c.canonical_form for c in results)

    def test_meaning_populated(self, plugin):
        results = self._run(plugin, ["конечно"])
        assert results[0].lesson_data["meaning"]

    def test_confidence_0_90(self, plugin):
        results = self._run(plugin, ["конечно"])
        assert results[0].confidence == pytest.approx(0.90)

    def test_idiom_type(self, plugin):
        results = self._run(plugin, ["конечно"])
        assert results[0].type == "idiom"

    def test_all_table_entries_are_lowercase(self):
        for words, _meaning, _register in RU_IDIOMS:
            for w in words:
                assert w == w.lower(), f"Not lowercase: {w!r}"

    def test_idiom_detection_capability(self, plugin):
        assert plugin.capabilities.idiom_detection is True


# ── Russian nuance extraction ─────────────────────────────────────────────────

def _make_conj(lemma: str, surface: str, aspect: str) -> CandidateObject:
    return CandidateObject(
        canonical_form=f"conj:{lemma}:{aspect}",
        surface_form=surface,
        type="conjugation",
        label=surface,
        lesson_data={"lemma": lemma, "surface": surface, "aspect": aspect},
        confidence=0.80,
    )


class TestRussianNuance:
    @pytest.fixture()
    def plugin(self):
        return RussianPlugin()

    def test_perfective_emits_nuance(self, plugin):
        conj = [_make_conj("сказать", "сказал", "perfective")]
        results = plugin._extract_nuance(conj, set())
        assert len(results) == 1
        assert results[0].lesson_data["nuance_type"] == "perfective_aspect"

    def test_imperfective_emits_nuance(self, plugin):
        conj = [_make_conj("говорить", "говорит", "imperfective")]
        results = plugin._extract_nuance(conj, set())
        assert len(results) == 1
        assert results[0].lesson_data["nuance_type"] == "imperfective_aspect"

    def test_deduplicates_same_lemma(self, plugin):
        conj = [
            _make_conj("говорить", "говорю", "imperfective"),
            _make_conj("говорить", "говорит", "imperfective"),
        ]
        results = plugin._extract_nuance(conj, set())
        # Only one nuance per (type, lemma) pair.
        assert len(results) == 1

    def test_note_field_populated(self, plugin):
        conj = [_make_conj("читать", "читает", "imperfective")]
        results = plugin._extract_nuance(conj, set())
        assert results[0].lesson_data.get("note")

    def test_unknown_aspect_skipped(self, plugin):
        conj = [_make_conj("быть", "есть", "unknown")]
        results = plugin._extract_nuance(conj, set())
        assert results == []

    def test_nuance_type_field(self, plugin):
        conj = [_make_conj("сказать", "сказал", "perfective")]
        results = plugin._extract_nuance(conj, set())
        assert results[0].type == "nuance"

    def test_relation_hint_present(self, plugin):
        conj = [_make_conj("читать", "читал", "imperfective")]
        results = plugin._extract_nuance(conj, set())
        assert len(results[0].relation_hints) == 1
        assert results[0].relation_hints[0].relation_type == "nuance_of"
