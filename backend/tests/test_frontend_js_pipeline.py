"""Run frontend JS regression tests via Node.js subprocess.

Each test function invokes one .mjs test file and asserts exit-code 0.
The JS test files use node:assert — any assertion failure causes non-zero exit.
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
