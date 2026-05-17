"""Tests for corpus manifest loading and validation."""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from backend.corpus.manifest import (
    ALLOWED_LICENSES,
    CorpusEntry,
    CorpusManifest,
    Framework,
    load_manifest,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_entry(**kwargs) -> dict:
    base = {
        "language": "en",
        "framework": "CEFR",
        "level": "B2",
        "cefr_equivalent": "B2",
        "title": "Test Book",
        "author": "Test Author",
        "year": 1900,
        "source_url": "https://example.com/test.txt",
        "source_name": "Test Source",
        "license": "public_domain",
    }
    base.update(kwargs)
    return base


# ── CorpusEntry validation ────────────────────────────────────────────────────

def test_valid_entry_parses():
    entry = CorpusEntry.model_validate(_make_entry())
    assert entry.language == "en"
    assert entry.level == "B2"
    assert entry.framework == Framework.CEFR


def test_jlpt_level_valid():
    entry = CorpusEntry.model_validate(_make_entry(
        language="ja",
        framework="JLPT",
        level="N3",
        cefr_equivalent="B1",
    ))
    assert entry.level == "N3"


def test_jlpt_level_invalid():
    with pytest.raises(Exception, match="invalid for framework"):
        CorpusEntry.model_validate(_make_entry(
            framework="JLPT",
            level="B1",  # B1 is CEFR, not valid for JLPT
        ))


def test_hsk_level_valid():
    entry = CorpusEntry.model_validate(_make_entry(
        language="zh",
        framework="HSK",
        level="HSK4",
        cefr_equivalent="B1",
    ))
    assert entry.level == "HSK4"


def test_invalid_license_rejected():
    with pytest.raises(Exception, match="license"):
        CorpusEntry.model_validate(_make_entry(license="all_rights_reserved"))


def test_allowed_licenses_all_valid():
    for lic in ALLOWED_LICENSES:
        entry = CorpusEntry.model_validate(_make_entry(license=lic))
        assert entry.license == lic


def test_invalid_cefr_equivalent_rejected():
    with pytest.raises(Exception, match="cefr_equivalent"):
        CorpusEntry.model_validate(_make_entry(cefr_equivalent="X5"))


def test_notes_default_empty():
    entry = CorpusEntry.model_validate(_make_entry())
    assert entry.notes == []


def test_notes_stored():
    entry = CorpusEntry.model_validate(_make_entry(notes=["check this"]))
    assert entry.notes == ["check this"]


# ── CorpusManifest validation ─────────────────────────────────────────────────

def test_manifest_parses_empty():
    m = CorpusManifest.model_validate({"entries": []})
    assert m.entries == []


def test_manifest_duplicate_url_rejected():
    entries = [_make_entry(), _make_entry(title="Other Book")]
    with pytest.raises(Exception, match="Duplicate source_url"):
        CorpusManifest.model_validate({"entries": entries})


def test_manifest_for_language():
    entries = [
        _make_entry(language="en", source_url="https://a.com/1.txt"),
        _make_entry(language="es", source_url="https://a.com/2.txt"),
        _make_entry(language="en", title="Other", source_url="https://a.com/3.txt"),
    ]
    m = CorpusManifest.model_validate({"entries": entries})
    assert len(m.for_language("en")) == 2
    assert len(m.for_language("es")) == 1
    assert m.for_language("fr") == []


def test_manifest_languages():
    entries = [
        _make_entry(language="en", source_url="https://a.com/1.txt"),
        _make_entry(language="es", source_url="https://a.com/2.txt"),
        _make_entry(language="en", title="Other", source_url="https://a.com/3.txt"),
    ]
    m = CorpusManifest.model_validate({"entries": entries})
    assert m.languages() == ["en", "es"]


# ── load_manifest ─────────────────────────────────────────────────────────────

def test_load_manifest_from_file(tmp_path: Path):
    content = {
        "entries": [_make_entry()]
    }
    manifest_file = tmp_path / "manifest.yaml"
    manifest_file.write_text(yaml.dump(content), encoding="utf-8")
    m = load_manifest(manifest_file)
    assert len(m.entries) == 1
    assert m.entries[0].title == "Test Book"


def test_load_manifest_empty_file(tmp_path: Path):
    manifest_file = tmp_path / "manifest.yaml"
    manifest_file.write_text("", encoding="utf-8")
    m = load_manifest(manifest_file)
    assert m.entries == []


def test_load_real_manifest():
    """The shipped manifest should parse without errors."""
    real_path = Path("corpora/manifest.yaml")
    if not real_path.exists():
        pytest.skip("corpora/manifest.yaml not found")
    m = load_manifest(real_path)
    assert len(m.entries) > 0
    # All licenses must be valid.
    for entry in m.entries:
        assert entry.license in ALLOWED_LICENSES
