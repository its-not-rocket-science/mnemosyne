"""Tests for corpus manifest coverage, new frameworks, and idempotency helpers."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

from backend.corpus.levels import (
    TOPIK_TO_CEFR,
    CLASSICAL_READING_TO_CEFR,
    KOINE_READING_TO_CEFR,
    to_cefr,
    difficulty_rank,
)
from backend.corpus.manifest import (
    CorpusEntry,
    CorpusManifest,
    Framework,
    load_manifest,
)
from backend.corpus.build import (
    _source_identity,
    _manifest_entry_hash,
    _content_hash,
    corpus_source_document_id,
)
from backend.corpus.lockfile import (
    load_lockfile,
    save_lockfile,
    update_lock_entry,
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


def _entry(**kwargs) -> CorpusEntry:
    return CorpusEntry.model_validate(_make_entry(**kwargs))


# ── Full manifest CEFR coverage ───────────────────────────────────────────────

def test_real_manifest_full_cefr_coverage():
    """Every language in the shipped manifest must cover A1–C2."""
    real_path = Path("corpora/manifest.yaml")
    if not real_path.exists():
        pytest.skip("corpora/manifest.yaml not found")
    manifest = load_manifest(real_path)
    for lang in manifest.languages():
        missing = manifest.missing_cefr_levels(lang)
        assert not missing, (
            f"Language '{lang}' missing CEFR levels: {missing}"
        )


def test_real_manifest_entry_count():
    real_path = Path("corpora/manifest.yaml")
    if not real_path.exists():
        pytest.skip("corpora/manifest.yaml not found")
    manifest = load_manifest(real_path)
    # 14 languages × 6 levels minimum; en has extra B2 entry.
    assert len(manifest.entries) >= 84


# ── TOPIK level normalization ─────────────────────────────────────────────────

def test_topik_granular_levels_all_map():
    for level, cefr in TOPIK_TO_CEFR.items():
        assert to_cefr("TOPIK", level) == cefr


def test_topik1_is_a1():
    assert to_cefr("TOPIK", "TOPIK1") == "A1"


def test_topik6_is_c2():
    assert to_cefr("TOPIK", "TOPIK6") == "C2"


def test_topik_legacy_levels_still_work():
    assert to_cefr("TOPIK", "TOPIK-I") == "A2"
    assert to_cefr("TOPIK", "TOPIK-II") == "B2"


def test_topik_granular_progression():
    levels = ["TOPIK1", "TOPIK2", "TOPIK3", "TOPIK4", "TOPIK5", "TOPIK6"]
    ranks = [difficulty_rank("TOPIK", lvl) for lvl in levels]
    assert ranks == sorted(ranks), "TOPIK1-6 must map to non-decreasing difficulty"


def test_topik_manifest_level_valid():
    entry = CorpusEntry.model_validate(_make_entry(
        language="ko",
        framework="TOPIK",
        level="TOPIK4",
        cefr_equivalent="B2",
    ))
    assert entry.level == "TOPIK4"


def test_topik_old_level_rejected():
    """TOPIK-II is still valid (backward compat)."""
    entry = CorpusEntry.model_validate(_make_entry(
        language="ko",
        framework="TOPIK",
        level="TOPIK-II",
        cefr_equivalent="B2",
    ))
    assert entry.level == "TOPIK-II"


# ── ClassicalReading framework ────────────────────────────────────────────────

def test_classical_reading_all_cefr_levels_map():
    for level, cefr in CLASSICAL_READING_TO_CEFR.items():
        assert to_cefr("ClassicalReading", level) == cefr


def test_classical_reading_manifest_level_valid():
    entry = CorpusEntry.model_validate(_make_entry(
        language="la",
        framework="ClassicalReading",
        level="C1",
        cefr_equivalent="C1",
    ))
    assert entry.framework == Framework.CLASSICAL_READING
    assert entry.level == "C1"


def test_classical_reading_invalid_level_rejected():
    with pytest.raises(Exception, match="invalid for framework"):
        CorpusEntry.model_validate(_make_entry(
            language="la",
            framework="ClassicalReading",
            level="Intermediate",  # descriptive name not accepted
        ))


def test_classical_reading_difficulty_order():
    levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
    ranks = [difficulty_rank("ClassicalReading", lvl) for lvl in levels]
    assert ranks == sorted(ranks)


# ── KoineReading framework ────────────────────────────────────────────────────

def test_koine_reading_all_cefr_levels_map():
    for level, cefr in KOINE_READING_TO_CEFR.items():
        assert to_cefr("KoineReading", level) == cefr


def test_koine_reading_manifest_level_valid():
    entry = CorpusEntry.model_validate(_make_entry(
        language="grc",
        framework="KoineReading",
        level="A2",
        cefr_equivalent="A2",
    ))
    assert entry.framework == Framework.KOINE_READING


def test_koine_reading_c2_valid():
    entry = CorpusEntry.model_validate(_make_entry(
        language="grc",
        framework="KoineReading",
        level="C2",
        cefr_equivalent="C2",
    ))
    assert entry.level == "C2"


# ── manifest_id generation ────────────────────────────────────────────────────

def test_manifest_id_auto_generated():
    entry = _entry()
    assert entry.manifest_id is not None
    assert "en:CEFR:B2:" in entry.manifest_id


def test_manifest_id_deterministic():
    e1 = _entry()
    e2 = _entry()
    assert e1.manifest_id == e2.manifest_id


def test_manifest_id_format():
    entry = _entry(language="ko", framework="TOPIK", level="TOPIK4", cefr_equivalent="B2",
                   title="흥부전", source_url="https://ko.wikisource.org/wiki/test")
    mid = entry.manifest_id
    assert mid is not None
    parts = mid.split(":")
    assert parts[0] == "ko"
    assert parts[1] == "TOPIK"
    assert parts[2] == "TOPIK4"


def test_manifest_id_explicit_preserved():
    entry = CorpusEntry.model_validate(_make_entry(manifest_id="my-custom-id"))
    assert entry.manifest_id == "my-custom-id"


# ── manual_review field ───────────────────────────────────────────────────────

def test_manual_review_default_false():
    entry = _entry()
    assert entry.manual_review is False


def test_manual_review_true():
    entry = _entry(manual_review=True)
    assert entry.manual_review is True


# ── Hashing helpers ───────────────────────────────────────────────────────────

def test_source_identity_stable():
    entry = _entry()
    h1 = _source_identity(entry)
    h2 = _source_identity(entry)
    assert h1 == h2
    assert len(h1) == 64


def test_source_identity_changes_with_url():
    e1 = _entry(source_url="https://example.com/a.txt")
    e2 = _entry(source_url="https://example.com/b.txt")
    assert _source_identity(e1) != _source_identity(e2)


def test_manifest_entry_hash_detects_metadata_change():
    e1 = _entry(title="Title A")
    e2 = _entry(title="Title B", source_url="https://example.com/b.txt")
    assert _manifest_entry_hash(e1) != _manifest_entry_hash(e2)


def test_content_hash_stable():
    text = "Hello, world!"
    h = _content_hash(text)
    assert _content_hash(text) == h
    assert len(h) == 64


def test_corpus_source_document_id_stable():
    entry = _entry()
    assert corpus_source_document_id(entry) == corpus_source_document_id(entry)


# ── Idempotency: skip on unchanged content ────────────────────────────────────

def test_manifest_no_duplicate_urls():
    real_path = Path("corpora/manifest.yaml")
    if not real_path.exists():
        pytest.skip("corpora/manifest.yaml not found")
    manifest = load_manifest(real_path)
    urls = [e.source_url for e in manifest.entries]
    assert len(urls) == len(set(urls)), "Duplicate source URLs found in manifest"


# ── Lockfile ──────────────────────────────────────────────────────────────────

def test_lockfile_round_trip(tmp_path: Path):
    lf = tmp_path / "manifest.lock.json"
    data: dict = {}
    update_lock_entry(data, "en:CEFR:B2:test:abc123",
                      manifest_entry_hash="abc", ingestion_status="ok")
    save_lockfile(data, lf)
    loaded = load_lockfile(lf)
    assert loaded["en:CEFR:B2:test:abc123"]["ingestion_status"] == "ok"


def test_lockfile_missing_returns_empty(tmp_path: Path):
    lf = tmp_path / "nonexistent.lock.json"
    assert load_lockfile(lf) == {}


def test_lockfile_update_preserves_other_keys(tmp_path: Path):
    lf = tmp_path / "manifest.lock.json"
    data: dict = {"id1": {"ingestion_status": "ok", "cached_path": "/some/path"}}
    update_lock_entry(data, "id1", manifest_entry_hash="newhash")
    assert data["id1"]["cached_path"] == "/some/path"
    assert data["id1"]["manifest_entry_hash"] == "newhash"
    assert data["id1"]["ingestion_status"] == "ok"


# ── Quality: coverage check ───────────────────────────────────────────────────

def test_check_manifest_coverage_warns_on_missing_level():
    from backend.corpus.quality import check_manifest

    entries = [
        _make_entry(language="fr", level="B1", cefr_equivalent="B1",
                    source_url="https://example.com/1.txt"),
        _make_entry(language="fr", level="C1", cefr_equivalent="C1",
                    source_url="https://example.com/2.txt"),
    ]
    manifest = CorpusManifest.model_validate({"entries": entries})
    report = check_manifest(manifest, require_full_cefr_coverage=True)
    coverage_warnings = [i for i in report.warnings if i.issue_type == "missing_cefr_level"]
    assert len(coverage_warnings) == 1
    assert "fr" == coverage_warnings[0].language
    assert "A1" in coverage_warnings[0].message


def test_check_manifest_coverage_ok_when_complete():
    from backend.corpus.quality import check_manifest

    levels = ["A1", "A2", "B1", "B2", "C1", "C2"]
    entries = [
        _make_entry(level=lvl, cefr_equivalent=lvl, source_url=f"https://ex.com/{i}.txt")
        for i, lvl in enumerate(levels)
    ]
    manifest = CorpusManifest.model_validate({"entries": entries})
    report = check_manifest(manifest, require_full_cefr_coverage=True)
    coverage_issues = [i for i in report.issues if i.issue_type == "missing_cefr_level"]
    assert not coverage_issues


# ── cefr_coverage / missing_cefr_levels helpers ───────────────────────────────

def test_cefr_coverage_topik():
    entries = [
        _make_entry(language="ko", framework="TOPIK", level="TOPIK4",
                    cefr_equivalent="B2", source_url="https://ex.com/1.txt"),
    ]
    manifest = CorpusManifest.model_validate({"entries": entries})
    assert "B2" in manifest.cefr_coverage("ko")


def test_missing_cefr_levels_partial():
    entries = [
        _make_entry(level="A1", cefr_equivalent="A1", source_url="https://ex.com/1.txt"),
        _make_entry(level="B1", cefr_equivalent="B1", source_url="https://ex.com/2.txt"),
    ]
    manifest = CorpusManifest.model_validate({"entries": entries})
    missing = manifest.missing_cefr_levels("en")
    assert "A2" in missing
    assert "B2" in missing
    assert "A1" not in missing
    assert "B1" not in missing


# ── --dry-run flag: no side effects ──────────────────────────────────────────

def test_build_entry_dry_run_returns_dry_run_status(tmp_path: Path):
    """build_entry with dry_run=True and no cached text returns dry_run status."""
    from backend.corpus.build import build_entry

    entry = _entry(language="en", source_url="https://example.com/test.txt")
    registry = MagicMock()
    registry.get.return_value = MagicMock()
    db = AsyncMock()

    async def _run():
        return await build_entry(
            entry, registry, db,
            dry_run=True,
            force=False,
            cache_dir=tmp_path / "cache",
            lockfile_path=tmp_path / "manifest.lock.json",
        )

    import asyncio
    result = asyncio.run(_run())
    # No cached text → dry_run result with warning about missing cache.
    assert result.status == "dry_run"


# ── --only-new flag ───────────────────────────────────────────────────────────

def test_build_entry_only_new_skips_existing(tmp_path: Path):
    """When --only-new and lockfile shows 'ok', entry is skipped."""
    from backend.corpus.build import build_entry

    lf = tmp_path / "manifest.lock.json"
    entry = _entry(language="en", source_url="https://example.com/test.txt")
    mid = entry.manifest_id or ""
    data: dict = {mid: {"ingestion_status": "ok"}}
    save_lockfile(data, lf)

    registry = MagicMock()
    registry.get.return_value = MagicMock()
    db = AsyncMock()

    async def _run():
        return await build_entry(
            entry, registry, db,
            dry_run=False,
            only_new=True,
            lockfile_path=lf,
        )

    import asyncio
    result = asyncio.run(_run())
    assert result.status == "skipped"


# ── manual_review flag ────────────────────────────────────────────────────────

def test_build_entry_manual_review_skips(tmp_path: Path):
    """build_entry skips entries with manual_review=True without touching network or DB."""
    from backend.corpus.build import build_entry

    entry = _entry(language="en", source_url="https://example.com/test.txt",
                   manual_review=True)
    registry = MagicMock()
    registry.get.return_value = MagicMock()
    db = AsyncMock()

    async def _run():
        return await build_entry(
            entry, registry, db,
            dry_run=False,
            force=False,
            cache_dir=tmp_path / "cache",
            lockfile_path=tmp_path / "manifest.lock.json",
        )

    import asyncio
    result = asyncio.run(_run())
    assert result.status == "skipped"
    assert any("manual_review" in w for w in result.warnings)
    db.execute.assert_not_called()
