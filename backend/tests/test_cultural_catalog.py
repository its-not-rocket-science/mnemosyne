from __future__ import annotations

import json
import subprocess
import sys
from importlib import import_module
from pathlib import Path

import pytest

from backend.lesson_extraction.engine import enrich
import backend.nuance.cultural as cultural
from backend.nuance.cultural import extract_cultural_references
from backend.schemas.parse import CandidateSentenceResult
from scripts.build_cultural_catalog import SUPPORTED_LANGUAGES, load_seed, validate_and_build

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / "data" / "cultural_references_seed.yaml"
OUT = ROOT / "backend" / "nuance" / "data" / "cultural_references"


@pytest.fixture(autouse=True)
def _clear_cultural_catalog_caches():
    cultural.load_catalog.cache_clear()
    cultural._patterns.cache_clear()
    yield
    cultural.load_catalog.cache_clear()
    cultural._patterns.cache_clear()


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


def _write_runtime_catalog(out_dir: Path, language: str, entries: list[dict[str, object]]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{language}.json").write_text(
        json.dumps({"language": language, "entries": entries}, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _use_runtime_catalog(monkeypatch: pytest.MonkeyPatch, out_dir: Path) -> None:
    monkeypatch.setattr(cultural, "DATA_DIR", out_dir)
    cultural.load_catalog.cache_clear()
    cultural._patterns.cache_clear()


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


def test_build_check_succeeds():
    subprocess.run([sys.executable, "scripts/build_cultural_catalog.py", "--check"], cwd=ROOT, check=True, capture_output=True, text=True)


def test_build_report_includes_every_supported_language():
    result = subprocess.run([sys.executable, "scripts/build_cultural_catalog.py", "--report"], cwd=ROOT, check=True, capture_output=True, text=True)
    report_languages = {line.split(" | ", 1)[0] for line in result.stdout.splitlines()[2:] if line.strip()}
    assert report_languages == set(SUPPORTED_LANGUAGES)


def test_language_write_targets_only_requested_language(tmp_path):
    subprocess.run(
        [sys.executable, "scripts/build_cultural_catalog.py", "--language", "fi", "--write", "--out-dir", str(tmp_path)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert {p.name for p in tmp_path.glob("*.json")} == {"fi.json"}


def test_generated_json_determinism():
    first = subprocess.run([sys.executable, "scripts/build_cultural_catalog.py", "--write"], cwd=ROOT, check=True, capture_output=True, text=True)
    before = {p.name: p.read_text(encoding="utf-8") for p in sorted(OUT.glob("*.json"))}
    second = subprocess.run([sys.executable, "scripts/build_cultural_catalog.py", "--write"], cwd=ROOT, check=True, capture_output=True, text=True)
    after = {p.name: p.read_text(encoding="utf-8") for p in sorted(OUT.glob("*.json"))}
    assert first.stdout == second.stdout
    assert before == after


def test_generated_file_exists_for_every_supported_language():
    required = {
        "canonical_form",
        "canonical_reference",
        "reference_type",
        "surface_patterns",
        "short_explanation",
        "learner_level",
        "confidence",
    }
    assert {p.stem for p in OUT.glob("*.json")} == set(SUPPORTED_LANGUAGES)
    for lang in SUPPORTED_LANGUAGES:
        payload = json.loads((OUT / f"{lang}.json").read_text(encoding="utf-8"))
        assert payload["language"] == lang
        assert payload["entries"]
        for entry in payload["entries"]:
            assert required <= entry.keys()


def test_longest_match_and_overlap_suppression():
    matches = extract_cultural_references("luchar contra molinos de viento", "es")
    surfaces = [m.surface_form for m in matches]
    assert "luchar contra molinos de viento" in surfaces
    assert surfaces.count("molinos de viento") == 0


def test_false_positive_suppression_for_short_ambiguous_entries():
    # Latin-script languages use word boundaries, so Sampo should not fire inside a longer token.
    assert extract_cultural_references("Sampola is a place name here.", "fi") == []


def test_english_case_insensitive_match():
    matches = extract_cultural_references("that loophole is his ACHILLES HEEL.", "en")
    assert any(m.canonical_form == "en:classical:achilles_heel" for m in matches)


def test_casefold_match_preserves_original_span_for_german_sharp_s(monkeypatch, tmp_path):
    _write_runtime_catalog(tmp_path, "de", [{
        "id": "strasse",
        "language": "de",
        "canonical_form": "de:cultural:strasse",
        "canonical_reference": "Straße",
        "reference_type": "cultural_reference",
        "surface_patterns": ["straße"],
        "short_explanation": "A German street word used to exercise casefold matching.",
        "learner_level": "B1",
        "confidence": 0.8,
    }])
    _use_runtime_catalog(monkeypatch, tmp_path)

    matches = extract_cultural_references("DIE STRASSE IST HIER.", "de")

    assert [m.surface_form for m in matches] == ["STRASSE"]


def test_turkish_casefold_dotted_i_preserves_original_span(monkeypatch, tmp_path):
    _write_runtime_catalog(tmp_path, "tr", [{
        "id": "ince_memed",
        "language": "tr",
        "canonical_form": "tr:literary:ince_memed",
        "canonical_reference": "İnce Memed",
        "reference_type": "literary_reference",
        "surface_patterns": ["İnce Memed"],
        "short_explanation": "A Turkish literary reference used to exercise dotted-I casefolding.",
        "learner_level": "B2",
        "confidence": 0.8,
    }])
    _use_runtime_catalog(monkeypatch, tmp_path)

    matches = extract_cultural_references("i̇nce memed okudum.", "tr")

    assert [m.surface_form for m in matches] == ["i̇nce memed"]


def test_script_sensitive_languages_remain_case_sensitive():
    assert extract_cultural_references("هذه قصة من أَلْف لَيْلَة وَلَيْلَة.", "ar") == []


@pytest.mark.parametrize("language,text", sorted(SAMPLES.items()))
def test_one_positive_detection_per_language(language, text):
    matches = extract_cultural_references(text, language)
    assert matches, language
    assert matches[0].type == "nuance"
    assert matches[0].lesson_data["reference_type"] in {
        "literary_reference", "cultural_reference", "proverb_tradition", "classical_or_scriptural_allusion"
    }



def test_variants_are_merged_into_generated_surface_patterns_without_duplicates():
    row = {
        "language": "es",
        "surface_patterns": ["Don Quijote", "Don Quixote"],
        "variants": ["Don Quixote", "quijotesco"],
        "canonical_reference": "Don Quijote",
        "reference_type": "literary_reference",
        "short_explanation": "A test-only entry for variant handling.",
        "learner_level": "B2",
        "confidence": 0.8,
    }

    by_lang, warnings = validate_and_build([row])

    assert not warnings
    assert by_lang["es"][0]["surface_patterns"] == ["Don Quijote", "Don Quixote", "quijotesco"]


def test_variant_surface_is_detected_at_runtime(monkeypatch, tmp_path):
    row = {
        "language": "es",
        "surface_patterns": ["Don Quijote"],
        "variants": ["quijotesco"],
        "canonical_reference": "Don Quijote",
        "reference_type": "literary_reference",
        "short_explanation": "A test-only entry for variant handling.",
        "learner_level": "B2",
        "confidence": 0.8,
    }
    by_lang, _ = validate_and_build([row])
    _write_runtime_catalog(tmp_path, "es", by_lang["es"])
    _use_runtime_catalog(monkeypatch, tmp_path)

    matches = extract_cultural_references("Tiene un gesto quijotesco.", "es")

    assert [m.canonical_form for m in matches] == ["es:literary:don_quijote"]
    assert [m.surface_form for m in matches] == ["quijotesco"]


def test_duplicate_surface_warning_includes_variant_collisions():
    rows = [
        {
            "language": "es",
            "surface_patterns": ["Don Quijote"],
            "variants": ["quijotesco"],
            "canonical_reference": "Don Quijote",
            "reference_type": "literary_reference",
            "short_explanation": "A test-only entry for variant handling.",
            "learner_level": "B2",
            "confidence": 0.8,
        },
        {
            "language": "es",
            "surface_patterns": ["quijotesco"],
            "canonical_reference": "Quijotesco",
            "reference_type": "cultural_reference",
            "short_explanation": "A test-only duplicate surface entry.",
            "learner_level": "B2",
            "confidence": 0.8,
        },
    ]

    _, warnings = validate_and_build(rows)

    assert any("duplicate surface pattern 'quijotesco'" in warning for warning in warnings)


def test_matches_are_returned_in_sentence_order():
    matches = extract_cultural_references("Big Brother found an Achilles heel.", "en")

    assert [m.canonical_form for m in matches[:2]] == [
        "en:literary:big_brother",
        "en:classical:achilles_heel",
    ]


def test_cultural_detector_integrates_with_lesson_extraction():
    result = enrich("en", [CandidateSentenceResult(text="Big Brother is watching.", candidates=[])])[0]
    assert any(c.canonical_form == "en:literary:big_brother" for c in result.candidates)


@pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
def test_capability_update_for_implemented_reference_types(language):
    plugin_classes = {
        "en": ("backend.plugins.english", "EnglishPlugin"),
        "es": ("backend.plugins.spanish", "SpanishPlugin"),
        "fr": ("backend.plugins.french", "FrenchPlugin"),
        "de": ("backend.plugins.german", "GermanPlugin"),
        "it": ("backend.plugins.italian", "ItalianPlugin"),
        "pt": ("backend.plugins.portuguese", "PortuguesePlugin"),
        "ru": ("backend.plugins.russian", "RussianPlugin"),
        "ar": ("backend.plugins.arabic", "ArabicPlugin"),
        "he": ("backend.plugins.hebrew", "HebrewPlugin"),
        "zh": ("backend.plugins.chinese", "MandarinChinesePlugin"),
        "ja": ("backend.plugins.japanese", "JapanesePlugin"),
        "la": ("backend.plugins.latin", "LatinPlugin"),
        "grc": ("backend.plugins.greek_koine", "KoineGreekPlugin"),
        "ko": ("backend.plugins.korean", "KoreanPlugin"),
        "hi": ("backend.plugins.hindi", "HindiPlugin"),
        "tr": ("backend.plugins.turkish", "TurkishPlugin"),
        "fi": ("backend.plugins.finnish", "FinnishPlugin"),
    }
    module_name, class_name = plugin_classes[language]
    plugin_class = getattr(import_module(module_name), class_name)
    caps = plugin_class.capabilities.nuance_capabilities
    assert caps.literary_references == "partial"
    assert caps.cultural_references == "partial"
    assert caps.proverb_tradition == "partial"
    assert caps.classical_or_scriptural_allusion == "partial"


def test_docs_no_longer_claim_literary_cultural_none_for_every_language():
    text = (ROOT / "docs" / "NUANCE_COVERAGE.md").read_text(encoding="utf-8")
    assert "all are `none` for every language" not in text
    assert "Generated cultural catalogue" in text
