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
from scripts.build_cultural_catalog import (
    REFERENCE_TYPES,
    SUPPORTED_LANGUAGES,
    load_seed,
    validate_and_build,
)

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


def _base_catalog_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "language": "en",
        "surface_patterns": ["Test allusion"],
        "canonical_reference": "Test Allusion",
        "reference_type": "literary_reference",
        "short_explanation": "A test-only cultural catalogue entry.",
        "learner_level": "B2",
        "confidence": 0.8,
    }
    row.update(overrides)
    return row


def test_seed_schema_validation_accepts_starter_catalogue():
    by_lang, warnings = validate_and_build(load_seed(SEED))
    assert not warnings
    assert set(by_lang) == set(SUPPORTED_LANGUAGES)
    assert all(by_lang[lang] for lang in SUPPORTED_LANGUAGES)


def test_missing_review_status_behaves_as_reviewed():
    by_lang, warnings = validate_and_build([_base_catalog_row()])

    assert not warnings
    assert [entry["canonical_reference"] for entry in by_lang["en"]] == [
        "Test Allusion"
    ]
    assert "review_status" not in by_lang["en"][0]


def test_draft_excluded_by_default():
    by_lang, warnings = validate_and_build([_base_catalog_row(review_status="draft")])

    assert not warnings
    assert by_lang["en"] == []


def test_needs_native_review_excluded_by_default():
    by_lang, warnings = validate_and_build(
        [_base_catalog_row(review_status="needs_native_review")]
    )

    assert not warnings
    assert by_lang["en"] == []


def test_draft_included_with_include_drafts():
    by_lang, warnings = validate_and_build(
        [_base_catalog_row(review_status="draft")], include_drafts=True
    )

    assert not warnings
    assert [entry["canonical_reference"] for entry in by_lang["en"]] == [
        "Test Allusion"
    ]


def test_needs_native_review_included_with_include_drafts():
    by_lang, warnings = validate_and_build(
        [_base_catalog_row(review_status="needs_native_review")],
        include_drafts=True,
    )

    assert not warnings
    assert [entry["canonical_reference"] for entry in by_lang["en"]] == [
        "Test Allusion"
    ]


def test_rejected_excluded_even_with_include_drafts():
    by_lang, warnings = validate_and_build(
        [_base_catalog_row(review_status="rejected")], include_drafts=True
    )

    assert not warnings
    assert by_lang["en"] == []


def test_unknown_review_status_fails_validation():
    with pytest.raises(ValueError, match="unknown review_status"):
        validate_and_build([_base_catalog_row(review_status="published")])


def test_review_and_provenance_warnings_do_not_fail_validation():
    by_lang, warnings = validate_and_build(
        [
            _base_catalog_row(
                review_status="reviewed",
                source_url="https://example.invalid/reference-list",
            )
        ]
    )

    assert by_lang["en"]
    assert any(
        "source_url is present but source_license is missing" in warning
        for warning in warnings
    )
    assert any(
        "review_status 'reviewed' should include reviewed_by and reviewed_at" in warning
        for warning in warnings
    )


def test_provenance_fields_are_preserved_in_generated_json(tmp_path):
    row = _base_catalog_row(
        source_location="row 42",
        source_url="https://example.invalid/reference-list",
        source_license="CC0-1.0",
        source_dataset="test cultural references",
        review_status="reviewed",
        reviewed_by="tester",
        reviewed_at="2026-06-06",
        review_notes="Internal note that should not be emitted.",
    )
    by_lang, warnings = validate_and_build([row])
    write_count = import_module("scripts.build_cultural_catalog").write_outputs(
        by_lang, tmp_path, "en"
    )

    payload = json.loads((tmp_path / "en.json").read_text(encoding="utf-8"))
    entry = payload["entries"][0]
    assert write_count == 1
    assert warnings == []
    assert entry["source_location"] == "row 42"
    assert entry["source_url"] == "https://example.invalid/reference-list"
    assert entry["source_license"] == "CC0-1.0"
    assert entry["source_dataset"] == "test cultural references"
    assert "review_status" not in entry
    assert "review_notes" not in entry
    assert "reviewed_by" not in entry
    assert "reviewed_at" not in entry


def test_localisation_key_fields_are_preserved_in_generated_json(tmp_path):
    row = _base_catalog_row(
        explanation_key="mnemosyne.en.explanation.test_dataset.test_allusion",
        source_work="Test Work",
        source_work_key="mnemosyne.en.work.test_work",
        source_author="Test Author",
        source_author_key="mnemosyne.en.author.test_author",
    )
    by_lang, warnings = validate_and_build([row])
    write_count = import_module("scripts.build_cultural_catalog").write_outputs(
        by_lang, tmp_path, "en"
    )

    payload = json.loads((tmp_path / "en.json").read_text(encoding="utf-8"))
    entry = payload["entries"][0]
    assert write_count == 1
    assert warnings == []
    assert entry["short_explanation"] == "A test-only cultural catalogue entry."
    assert entry["explanation_key"] == "mnemosyne.en.explanation.test_dataset.test_allusion"
    assert entry["source_work"] == "Test Work"
    assert entry["source_work_key"] == "mnemosyne.en.work.test_work"
    assert entry["source_author"] == "Test Author"
    assert entry["source_author_key"] == "mnemosyne.en.author.test_author"


def test_seed_scalar_whitespace_is_normalized():
    by_lang, warnings = validate_and_build([
        {
            "language": "en",
            "canonical_reference": "Orwellian\n",
            "reference_type": "literary_reference",
            "surface_patterns": ["Orwellian\n"],
            "short_explanation": (
                "Describes manipulative, authoritarian, or truth-distorting political language.\n"
            ),
            "learner_level": "B2",
            "register": "literary",
            "confidence": 0.86,
        }
    ])

    assert not warnings
    entry = by_lang["en"][0]
    assert entry["canonical_reference"] == "Orwellian"
    assert entry["surface_patterns"] == ["Orwellian"]
    assert entry["short_explanation"] == (
        "Describes manipulative, authoritarian, or truth-distorting political language."
    )


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


def test_build_check_prints_concise_ok_not_report_table():
    result = subprocess.run(
        [sys.executable, "scripts/build_cultural_catalog.py", "--check"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "OK: validated 310 entries across 17 languages"
    assert "language | entries" not in result.stdout
    assert result.stderr == ""


def test_build_check_language_scope_reports_only_requested_language():
    result = subprocess.run(
        [sys.executable, "scripts/build_cultural_catalog.py", "--check", "--language", "fi"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "OK: validated 10 entries across 1 language (fi)"
    assert "language | entries" not in result.stdout


def test_build_report_prints_full_table_for_every_supported_language():
    result = subprocess.run(
        [sys.executable, "scripts/build_cultural_catalog.py", "--report"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    lines = result.stdout.splitlines()

    assert lines[0].split(" | ") == ["language", "entries", *sorted(REFERENCE_TYPES)]
    report_languages = {line.split(" | ", 1)[0] for line in lines[2:] if line.strip()}
    assert report_languages == set(SUPPORTED_LANGUAGES)
    assert len(report_languages) == 17


def test_write_out_dir_writes_files_and_prints_concise_summary(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_cultural_catalog.py",
            "--write",
            "--out-dir",
            str(tmp_path),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert {p.stem for p in tmp_path.glob("*.json")} == set(SUPPORTED_LANGUAGES)
    assert result.stdout.strip() == f"Wrote 17 catalogue files to {tmp_path} (310 entries)"
    assert "language | entries" not in result.stdout


def test_language_write_targets_only_requested_language(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "scripts/build_cultural_catalog.py",
            "--language",
            "fi",
            "--write",
            "--out-dir",
            str(tmp_path),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert {p.name for p in tmp_path.glob("*.json")} == {"fi.json"}
    assert result.stdout.strip() == f"Wrote 1 catalogue file to {tmp_path} (10 entries)"


def test_build_invalid_seed_exits_non_zero(tmp_path):
    bad_seed = tmp_path / "bad_seed.json"
    bad_seed.write_text(
        json.dumps([
            {
                "language": "xx",
                "surface_patterns": ["abc"],
                "canonical_reference": "abc",
                "reference_type": "literary_reference",
                "short_explanation": "x",
                "learner_level": "B1",
                "confidence": 0.8,
            }
        ]),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "scripts/build_cultural_catalog.py", "--check", "--seed", str(bad_seed)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "ERROR:" in result.stderr
    assert "unknown language" in result.stderr


def test_generated_json_determinism_in_temp_dir(tmp_path):
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"

    first = subprocess.run(
        [
            sys.executable,
            "scripts/build_cultural_catalog.py",
            "--write",
            "--out-dir",
            str(first_dir),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    second = subprocess.run(
        [
            sys.executable,
            "scripts/build_cultural_catalog.py",
            "--write",
            "--out-dir",
            str(second_dir),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    first_payloads = {
        p.name: p.read_text(encoding="utf-8") for p in sorted(first_dir.glob("*.json"))
    }
    second_payloads = {
        p.name: p.read_text(encoding="utf-8") for p in sorted(second_dir.glob("*.json"))
    }
    assert first.stdout.strip() == f"Wrote 17 catalogue files to {first_dir} (310 entries)"
    assert second.stdout.strip() == f"Wrote 17 catalogue files to {second_dir} (310 entries)"
    assert first_payloads == second_payloads


def test_committed_generated_catalogues_are_up_to_date(tmp_path):
    generated = tmp_path / "generated"
    subprocess.run(
        [
            sys.executable,
            "scripts/build_cultural_catalog.py",
            "--write",
            "--out-dir",
            str(generated),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    for lang in SUPPORTED_LANGUAGES:
        expected = (generated / f"{lang}.json").read_text(encoding="utf-8")
        committed = (OUT / f"{lang}.json").read_text(encoding="utf-8")
        assert committed == expected, (
            f"{lang}.json is stale; run scripts/build_cultural_catalog.py --write"
        )


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


def test_detector_includes_localisation_keys_and_fallbacks(monkeypatch, tmp_path):
    _write_runtime_catalog(tmp_path, "en", [{
        "id": "test_allusion",
        "language": "en",
        "canonical_form": "en:literary:test_allusion",
        "canonical_reference": "Test Allusion",
        "reference_type": "literary_reference",
        "surface_patterns": ["Test Allusion"],
        "short_explanation": "Fallback explanation.",
        "explanation_key": "mnemosyne.en.explanation.test_dataset.test_allusion",
        "source_work": "Fallback Work",
        "source_work_key": "mnemosyne.en.work.test_work",
        "source_author": "Fallback Author",
        "source_author_key": "mnemosyne.en.author.test_author",
        "learner_level": "B2",
        "confidence": 0.8,
    }])
    _use_runtime_catalog(monkeypatch, tmp_path)

    matches = extract_cultural_references("This is a Test Allusion.", "en")

    assert len(matches) == 1
    assert matches[0].lesson_data["explanation"] == "Fallback explanation."
    assert matches[0].lesson_data["explanation_key"] == "mnemosyne.en.explanation.test_dataset.test_allusion"
    assert matches[0].lesson_data["source_work"] == "Fallback Work"
    assert matches[0].lesson_data["source_work_key"] == "mnemosyne.en.work.test_work"
    assert matches[0].lesson_data["source_author"] == "Fallback Author"
    assert matches[0].lesson_data["source_author_key"] == "mnemosyne.en.author.test_author"


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


def test_builder_preserves_new_public_provenance_fields() -> None:
    by_lang, warnings = validate_and_build(
        [
            _base_catalog_row(
                review_status="reviewed",
                reviewed_by="paul",
                reviewed_at="2026-06-07",
                source_location="Act II Scene 2",
                source_quote="That which we call a rose by any other name would smell as sweet.",
                source_note="Short source context note.",
                source_license="not_required",
                rights_basis="common_usage_short_expression",
                source_dataset="unit_test_dataset",
            )
        ]
    )

    assert warnings == []
    [entry] = by_lang["en"]
    assert entry["source_quote"] == "That which we call a rose by any other name would smell as sweet."
    assert entry["source_note"] == "Short source context note."
    assert entry["rights_basis"] == "common_usage_short_expression"


def test_builder_warns_on_rights_mismatches() -> None:
    _, warnings = validate_and_build(
        [
            _base_catalog_row(
                source_location="Act II Scene 2; Source quote: embedded text",
                source_license="public_domain",
                rights_basis="common_usage_short_expression",
                source_quote="x" * 161,
            )
        ],
        include_drafts=True,
    )

    assert any("source_license=not_required" in warning for warning in warnings)
    assert any("source_quote is 161 characters" in warning for warning in warnings)
    assert any("Source quote:" in warning for warning in warnings)


def test_detector_lesson_data_includes_new_provenance_fields(tmp_path, monkeypatch) -> None:
    out_dir = tmp_path / "catalog"
    _write_runtime_catalog(
        out_dir,
        "en",
        [
            {
                "id": "test_allusion",
                "language": "en",
                "surface_patterns": ["Test allusion"],
                "canonical_reference": "Test Allusion",
                "canonical_form": "en:literary:test_allusion",
                "reference_type": "literary_reference",
                "short_explanation": "A test-only cultural catalogue entry.",
                "learner_level": "B2",
                "confidence": 0.8,
                "source_quote": "Short supporting quote.",
                "source_note": "Context note.",
                "rights_basis": "common_usage_short_expression",
            }
        ],
    )
    _use_runtime_catalog(monkeypatch, out_dir)

    [match] = extract_cultural_references("This is a Test allusion.", "en")

    assert match.lesson_data["source_quote"] == "Short supporting quote."
    assert match.lesson_data["source_note"] == "Context note."
    assert match.lesson_data["rights_basis"] == "common_usage_short_expression"
