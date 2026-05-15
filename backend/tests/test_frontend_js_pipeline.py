"""Run frontend JS regression tests via Node.js subprocess.

Each test function invokes one .mjs test file and asserts exit-code 0.
The JS test files use node:assert — any assertion failure causes non-zero exit.

Test files:
  lesson-pipeline.test.mjs          — payload-builder invariants (word salad, URL,
                                       French leakage, pill attribute shape)
  recommended-reading-language-guard.test.mjs — next-up panel language isolation
  adaptive-policy.test.mjs          — adaptive reader policy computations
  reader-render.test.mjs            — DOM-level rendering: mnemosyne-pill and
                                       mnemosyne-text-panel rendered structure,
                                       events, RTL, confidence tiers, overlaps
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS_DIR = ROOT / "frontend" / "tests"


def _run_js(test_file: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["node", str(test_file)],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )


def _assert_passes(test_file: Path) -> None:
    result = _run_js(test_file)
    if result.returncode != 0:
        output = (result.stdout + result.stderr).strip()
        raise AssertionError(
            f"Frontend JS test failed ({test_file.name}):\n{output}"
        )


def test_lesson_pipeline_source_text_invariants() -> None:
    """Source text must never be replaced by extracted terms (Spanish sample regression)."""
    _assert_passes(TESTS_DIR / "lesson-pipeline.test.mjs")


def test_recommended_reading_language_guard() -> None:
    """Next Up panel must not surface items from the wrong language session."""
    _assert_passes(TESTS_DIR / "recommended-reading-language-guard.test.mjs")


def test_adaptive_policy() -> None:
    _assert_passes(TESTS_DIR / "adaptive-policy.test.mjs")


def test_reader_render() -> None:
    """DOM-level rendering: pill badges, labels, events, RTL, confidence tiers;
    text-panel line structure, annotation spans, gaps, events, setActiveLine."""
    _assert_passes(TESTS_DIR / "reader-render.test.mjs")
