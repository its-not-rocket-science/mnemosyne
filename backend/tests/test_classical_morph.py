"""Tests for Latin and Koine Greek morphological annotation improvements.

Covers:
1. la_morph.json and grc_morph.json are generated and loadable.
2. Latin plugin emits morphological features for annotated forms.
3. Koine Greek plugin emits morphological features for annotated forms.
4. Confidence adjusts based on morph data presence.
5. Unknown forms fall back gracefully.
6. Plugin capabilities reflect updated depth.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT    = Path(__file__).parents[2]
LEXICONS = ROOT / "data" / "lexicons"


# ── Morph file sanity checks ──────────────────────────────────────────────────

class TestMorphFiles:

    def test_la_morph_exists(self):
        assert (LEXICONS / "la_morph.json").exists(), \
            "Run: python -m scripts.ingest_classical_morph --lang la"

    def test_grc_morph_exists(self):
        assert (LEXICONS / "grc_morph.json").exists(), \
            "Run: python -m scripts.ingest_classical_morph --lang grc"

    def test_la_morph_structure(self):
        data = json.loads((LEXICONS / "la_morph.json").read_text("utf-8"))
        assert data["version"] == "1"
        assert data["language"] == "la"
        assert isinstance(data["entries"], dict)
        assert len(data["entries"]) > 0

    def test_grc_morph_structure(self):
        data = json.loads((LEXICONS / "grc_morph.json").read_text("utf-8"))
        assert data["version"] == "1"
        assert data["language"] == "grc"
        assert isinstance(data["entries"], dict)
        assert len(data["entries"]) > 0

    def test_la_morph_has_noun_entry(self):
        entries = json.loads((LEXICONS / "la_morph.json").read_text("utf-8"))["entries"]
        # Find at least one entry with a case feature
        has_case = any("case" in v for v in entries.values())
        assert has_case, "Expected at least one Latin entry with case annotation"

    def test_la_morph_has_verb_entry(self):
        entries = json.loads((LEXICONS / "la_morph.json").read_text("utf-8"))["entries"]
        has_tense = any("tense" in v for v in entries.values())
        assert has_tense, "Expected at least one Latin entry with tense annotation"

    def test_grc_morph_has_noun_entry(self):
        entries = json.loads((LEXICONS / "grc_morph.json").read_text("utf-8"))["entries"]
        has_case = any("case" in v for v in entries.values())
        assert has_case, "Expected at least one Greek entry with case annotation"

    def test_grc_morph_has_verb_entry(self):
        entries = json.loads((LEXICONS / "grc_morph.json").read_text("utf-8"))["entries"]
        has_tense = any("tense" in v for v in entries.values())
        assert has_tense, "Expected at least one Greek entry with tense annotation"

    def test_grc_morph_larger_than_la_morph(self):
        # Greek has MorphGNT (full NT) + PROIEL; Latin only has ITTB dev set
        la_count  = len(json.loads((LEXICONS / "la_morph.json").read_text("utf-8"))["entries"])
        grc_count = len(json.loads((LEXICONS / "grc_morph.json").read_text("utf-8"))["entries"])
        assert grc_count > la_count, \
            f"Expected grc_morph ({grc_count}) > la_morph ({la_count})"


# ── Latin plugin morphological output ─────────────────────────────────────────

class TestLatinMorphAnnotations:

    @pytest.fixture(autouse=True)
    def plugin(self):
        from backend.plugins.latin import LatinPlugin
        self.plugin = LatinPlugin()

    def test_capabilities_updated(self):
        caps = self.plugin.capabilities
        assert caps.analysis_depth    == "morphology_light"
        assert caps.morphology_depth  == "shallow"
        assert caps.morphology_quality == "low"
        assert "vocabulary" in caps.lesson_modes_supported

    def test_curated_word_has_confidence(self):
        # "amor" is a curated entry — should have confidence regardless of morph index
        result = self.plugin.analyze_sentence("amor")
        c = result.candidates[0]
        assert c.confidence is not None
        assert c.confidence >= 0.7

    def test_unknown_word_confidence_none(self):
        # A nonsense Latin string should have no confidence
        result = self.plugin.analyze_sentence("xyzqwerty")
        if result.candidates:
            assert result.candidates[0].confidence is None

    def test_known_entry_in_lexicon(self):
        result = self.plugin.analyze_sentence("terra")
        c = result.candidates[0]
        assert "gloss" in c.lesson_data
        assert "lemma" in c.lesson_data

    def test_morph_fields_present_when_morph_available(self):
        # Load the morph index directly to find a token that has morph data
        morph_path = LEXICONS / "la_morph.json"
        if not morph_path.exists():
            pytest.skip("la_morph.json not present")
        entries = json.loads(morph_path.read_text("utf-8"))["entries"]
        # Pick a form that has case annotation
        form_with_case = next(
            (form for form, feat in entries.items() if "case" in feat),
            None,
        )
        if not form_with_case:
            pytest.skip("No form with case in la_morph.json")
        result = self.plugin.analyze_sentence(form_with_case)
        if not result.candidates:
            pytest.skip(f"Token {form_with_case!r} produced no candidates")
        c = result.candidates[0]
        assert "case" in c.lesson_data, \
            f"Expected 'case' in lesson_data for {form_with_case!r}"

    def test_confidence_higher_with_morph_than_dict_only(self):
        # When morph data exists, confidence should be 0.80; dict-only = 0.70
        morph_path = LEXICONS / "la_morph.json"
        if not morph_path.exists():
            pytest.skip("la_morph.json not present")
        entries = json.loads(morph_path.read_text("utf-8"))["entries"]
        form_with_morph = next(
            (f for f, v in entries.items() if "case" in v or "tense" in v),
            None,
        )
        if not form_with_morph:
            pytest.skip("No annotated form in la_morph.json")
        result = self.plugin.analyze_sentence(form_with_morph)
        if not result.candidates:
            pytest.skip(f"No candidates for {form_with_morph!r}")
        c = result.candidates[0]
        # If dict entry found + morph: 0.80; if only morph (no dict): 0.50
        if c.lesson_data.get("gloss"):
            assert c.confidence == pytest.approx(0.80), \
                "Expected 0.80 for dict+morph annotated form"


# ── Koine Greek plugin morphological output ───────────────────────────────────

class TestGreekMorphAnnotations:

    @pytest.fixture(autouse=True)
    def plugin(self):
        from backend.plugins.greek_koine import KoineGreekPlugin
        self.plugin = KoineGreekPlugin()

    def test_capabilities_updated(self):
        caps = self.plugin.capabilities
        assert caps.analysis_depth    == "morphology_light"
        assert caps.morphology_depth  == "shallow"
        assert caps.morphology_quality == "medium"
        assert "vocabulary" in caps.lesson_modes_supported

    def test_romanized_present(self):
        # "λόγος" → normalises to "λογος"; romanized should be present
        result = self.plugin.analyze_sentence("λόγος")
        c = result.candidates[0]
        assert "romanized" in c.lesson_data
        assert len(c.lesson_data["romanized"]) > 0

    def test_curated_word_has_confidence(self):
        result = self.plugin.analyze_sentence("λόγος")
        c = result.candidates[0]
        assert c.confidence is not None
        assert c.confidence >= 0.7

    def test_unknown_word_confidence_none(self):
        result = self.plugin.analyze_sentence("xyzqwerty")
        if result.candidates:
            assert result.candidates[0].confidence is None

    def test_morph_fields_present_when_morph_available(self):
        morph_path = LEXICONS / "grc_morph.json"
        if not morph_path.exists():
            pytest.skip("grc_morph.json not present")
        entries = json.loads(morph_path.read_text("utf-8"))["entries"]
        form_with_case = next(
            (form for form, feat in entries.items() if "case" in feat),
            None,
        )
        if not form_with_case:
            pytest.skip("No form with case in grc_morph.json")
        result = self.plugin.analyze_sentence(form_with_case)
        if not result.candidates:
            pytest.skip(f"Token {form_with_case!r} produced no candidates")
        c = result.candidates[0]
        assert "case" in c.lesson_data, \
            f"Expected 'case' in lesson_data for {form_with_case!r}"

    def test_morphgnt_verb_form_annotated(self):
        # "ειπεν" (he said, aorist 3sg) is common in NT and in MorphGNT
        morph_path = LEXICONS / "grc_morph.json"
        if not morph_path.exists():
            pytest.skip("grc_morph.json not present")
        entries = json.loads(morph_path.read_text("utf-8"))["entries"]
        # Find an entry with tense AND person (verb)
        verb_form = next(
            (f for f, v in entries.items() if "tense" in v and "person" in v),
            None,
        )
        if not verb_form:
            pytest.skip("No verb entry with tense+person in grc_morph.json")
        result = self.plugin.analyze_sentence(verb_form)
        if not result.candidates:
            pytest.skip(f"No candidates for {verb_form!r}")
        c = result.candidates[0]
        assert "tense" in c.lesson_data or "person" in c.lesson_data

    def test_confidence_higher_with_morph_than_dict_only(self):
        morph_path = LEXICONS / "grc_morph.json"
        if not morph_path.exists():
            pytest.skip("grc_morph.json not present")
        entries = json.loads(morph_path.read_text("utf-8"))["entries"]
        form_with_morph = next(
            (f for f, v in entries.items() if "case" in v or "tense" in v),
            None,
        )
        if not form_with_morph:
            pytest.skip("No annotated form in grc_morph.json")
        result = self.plugin.analyze_sentence(form_with_morph)
        if not result.candidates:
            pytest.skip(f"No candidates for {form_with_morph!r}")
        c = result.candidates[0]
        if c.lesson_data.get("gloss"):
            assert c.confidence == pytest.approx(0.80)
