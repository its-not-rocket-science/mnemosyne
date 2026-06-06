from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from backend.lesson_extraction.engine import enrich
from backend.nuance.cultural import extract_cultural_references
from backend.schemas.parse import CandidateSentenceResult
from scripts.build_cultural_catalog import SUPPORTED_LANGUAGES, load_seed, validate_and_build

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "data" / "cultural_references_seed.yaml"
OUT = ROOT / "backend" / "nuance" / "data" / "cultural_references"

SAMPLES = {
    "en": "That loophole is his Achilles heel.",
    "es": "Eso parece una lucha contra molinos de viento.",
    "fr": "Ce parfum est une madeleine de Proust.",
    "de": "Das ist eine echte Gretchenfrage.",
    "it": "Questa è la dolce vita.",
    "pt": "Sinto muita saudade.",
    "ru": "Это Потёмкинская деревня.",
    "ar": "هذه قصة من ألف ليلة وليلة.",
    "he": "זה סיפור של דוד וגוליית.",
    "zh": "不要做井底之蛙。",
    "ja": "彼は桃太郎のようだ。",
    "la": "carpe diem, amice.",
    "grc": "ἄλφα καὶ ὦ",
    "ko": "이건 춘향전 이야기다.",
    "hi": "रामायण एक महान कथा है।",
    "tr": "Bu bir Truva atı olabilir.",
    "fi": "Kalevala on tärkeä.",
}


def test_seed_schema_validation_accepts_starter_catalogue():
    by_lang, warnings = validate_and_build(load_seed(SEED))
    assert not warnings
    assert set(by_lang) == set(SUPPORTED_LANGUAGES)
    assert all(by_lang[lang] for lang in SUPPORTED_LANGUAGES)


@pytest.mark.parametrize(
    "bad_row, message",
    [
        ({"language": "xx", "surface_patterns": ["abc"], "canonical_reference": "abc", "reference_type": "literary_reference", "short_explanation": "x", "learner_level": "B1", "confidence": 0.8}, "unknown language"),
        ({"language": "en", "surface_patterns": ["abc"], "canonical_reference": "abc", "reference_type": "bad", "short_explanation": "x", "learner_level": "B1", "confidence": 0.8}, "unknown reference_type"),
        ({"language": "en", "canonical_reference": "abc", "reference_type": "literary_reference", "short_explanation": "x", "learner_level": "B1", "confidence": 0.8}, "missing surface_patterns"),
        ({"language": "en", "surface_patterns": ["go"], "canonical_reference": "go", "reference_type": "literary_reference", "short_explanation": "x", "learner_level": "B1", "confidence": 0.8}, "very short pattern"),
    ],
)
def test_seed_schema_validation_rejects_bad_rows(bad_row, message):
    with pytest.raises(ValueError, match=message):
        validate_and_build([bad_row])


def test_generated_json_determinism():
    first = subprocess.run([sys.executable, "scripts/build_cultural_catalog.py", "--write"], cwd=ROOT, check=True, capture_output=True, text=True)
    before = {p.name: p.read_text(encoding="utf-8") for p in sorted(OUT.glob("*.json"))}
    second = subprocess.run([sys.executable, "scripts/build_cultural_catalog.py", "--write"], cwd=ROOT, check=True, capture_output=True, text=True)
    after = {p.name: p.read_text(encoding="utf-8") for p in sorted(OUT.glob("*.json"))}
    assert first.stdout == second.stdout
    assert before == after


def test_generated_file_exists_for_every_supported_language():
    assert {p.stem for p in OUT.glob("*.json")} == set(SUPPORTED_LANGUAGES)
    for lang in SUPPORTED_LANGUAGES:
        payload = json.loads((OUT / f"{lang}.json").read_text(encoding="utf-8"))
        assert payload["language"] == lang
        assert payload["entries"]


def test_longest_match_and_overlap_suppression():
    matches = extract_cultural_references("luchar contra molinos de viento", "es")
    surfaces = [m.surface_form for m in matches]
    assert "luchar contra molinos de viento" in surfaces
    assert surfaces.count("molinos de viento") == 0


def test_false_positive_suppression_for_short_ambiguous_entries():
    # Latin-script languages use word boundaries, so Sampo should not fire inside a longer token.
    assert extract_cultural_references("Sampola is a place name here.", "fi") == []


@pytest.mark.parametrize("language,text", sorted(SAMPLES.items()))
def test_one_positive_detection_per_language(language, text):
    matches = extract_cultural_references(text, language)
    assert matches, language
    assert matches[0].type == "nuance"
    assert matches[0].lesson_data["reference_type"] in {
        "literary_reference", "cultural_reference", "proverb_tradition", "classical_or_scriptural_allusion"
    }


def test_cultural_detector_integrates_with_lesson_extraction():
    result = enrich("en", [CandidateSentenceResult(text="Big Brother is watching.", candidates=[])])[0]
    assert any(c.canonical_form == "en:literary:big_brother" for c in result.candidates)


def test_capability_update_for_implemented_reference_types():
    from backend.plugins.english import EnglishPlugin
    caps = EnglishPlugin.capabilities.nuance_capabilities
    assert caps.literary_references == "partial"
    assert caps.cultural_references == "partial"
    assert caps.proverb_tradition == "partial"
    assert caps.classical_or_scriptural_allusion == "partial"


def test_docs_no_longer_claim_literary_cultural_none_for_every_language():
    text = (ROOT / "docs" / "NUANCE_COVERAGE.md").read_text(encoding="utf-8")
    assert "all are `none` for every language" not in text
    assert "Generated cultural catalogue" in text
