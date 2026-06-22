from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
# ANNOTATION_DEPTH_MODEL/ANNOTATION_DEPTH_KEY moved to js/reading-state.js
# when Session 1 of the frontend refactor split the former monolithic
# js/main.js — they're shared mutable state read/written by multiple mode
# coordinators, not owned by any single one.
MAIN_JS = ROOT / "frontend/js/reading-state.js"
TOP_NAV_JS = ROOT / "frontend/components/mnemosyne-top-nav.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_depth_modes_define_distinct_annotation_categories() -> None:
    text = _read(MAIN_JS)

    assert "const ANNOTATION_DEPTH_MODEL = {" in text
    assert "subtle: new Set(['vocabulary'])" in text
    assert "learning: new Set(['vocabulary', 'conjugation', 'agreement', 'inflection', 'grammar'])" in text
    assert "'nuance'" in text and "'phrase_family'" in text and "'cultural_note'" in text

    # Explicit non-alias guarantees in canonical model.
    assert "subtle: new Set(['vocabulary'])" in text
    assert "learning: new Set(['vocabulary', 'conjugation', 'agreement', 'inflection', 'grammar'])" in text
    assert "deep: new Set([" in text


def test_depth_selection_is_persisted_across_sessions() -> None:
    text = _read(MAIN_JS)
    assert "const ANNOTATION_DEPTH_KEY = 'mn-annotation-depth'" in text
    # currentDepth became the _currentDepth/currentDepth()/setCurrentDepth()
    # accessor pattern in Session 1's split — ES module `let` bindings are
    # read-only from the importer's side, so plain mutable state shared
    # across coordinators (explorer.js, lesson.js, review.js, shared.js)
    # needed accessor functions instead of a bare exported `let`.
    assert "let _currentDepth = localStorage.getItem(ANNOTATION_DEPTH_KEY) || DEPTH_FALLBACK" in text
    # The actual persist-on-change call lives in js/shared.js, which owns
    # the depth-change event listener (global keyboard shortcuts / top-nav
    # wiring), not in reading-state.js's pure state module.
    shared_js = _read(MAIN_JS.parent / "shared.js")
    assert "localStorage.setItem(ANNOTATION_DEPTH_KEY, detail.depth)" in shared_js


def test_active_mode_has_visual_indicator() -> None:
    text = _read(TOP_NAV_JS)
    assert 'id="mode-indicator"' in text
    assert "nav_mode_label" in text
    assert "this.#updateModeIndicator()" in text
