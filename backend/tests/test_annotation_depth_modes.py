from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAIN_JS = ROOT / "frontend/js/main.js"
TOP_NAV_JS = ROOT / "frontend/components/mnemosyne-top-nav.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_depth_modes_define_distinct_annotation_categories() -> None:
    text = _read(MAIN_JS)

    assert "const ANNOTATION_DEPTH_MODEL = {" in text
    assert "subtle: new Set(['vocabulary'])" in text
    assert "learning: new Set(['vocabulary', 'conjugation', 'agreement', 'grammar'])" in text
    assert "'nuance'" in text and "'phrase_family'" in text and "'cultural_note'" in text

    # Explicit non-alias guarantees in canonical model.
    assert "subtle: new Set(['vocabulary'])" in text
    assert "learning: new Set(['vocabulary', 'conjugation', 'agreement', 'grammar'])" in text
    assert "deep: new Set([" in text


def test_depth_selection_is_persisted_across_sessions() -> None:
    text = _read(MAIN_JS)
    assert "const ANNOTATION_DEPTH_KEY = 'mn-annotation-depth'" in text
    assert "let currentDepth = localStorage.getItem(ANNOTATION_DEPTH_KEY) || DEPTH_FALLBACK" in text
    assert "localStorage.setItem(ANNOTATION_DEPTH_KEY, currentDepth)" in text


def test_active_mode_has_visual_indicator() -> None:
    text = _read(TOP_NAV_JS)
    assert 'id="mode-indicator"' in text
    assert "nav_mode_label" in text
    assert "this.#updateModeIndicator()" in text
