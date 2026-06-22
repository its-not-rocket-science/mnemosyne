from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# help_/adaptive_-prefixed keys live in js/i18n/lesson.js since Session 5 of
# the frontend refactor split the former monolithic js/i18n.js (now a thin
# re-export shim) into js/i18n/{core,annotations,lesson,library,review}.js.
I18N_JS = ROOT / "frontend/js/i18n/lesson.js"
SNAPSHOT = Path(__file__).with_name("snapshots_memory_map_i18n.json")
LANGS = ["en", "es", "fr", "de", "it", "pt", "ru", "ja", "zh", "ar", "he"]
KEYS = [
    "help_intelligence_summary",
    "adaptive_memory_weak",
    "adaptive_memory_learning",
    "adaptive_memory_known",
    "adaptive_memory_weak_stat",
    "adaptive_memory_fading_stat",
    "adaptive_memory_strong_stat",
]


def _extract_lang_block(text: str, lang: str) -> str:
    m = re.search(rf"\n\s*{lang}:\s*\{{", text)
    assert m, f"language block missing: {lang}"
    start = m.end()
    depth = 1
    i = start
    while i < len(text) and depth > 0:
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        i += 1
    return text[start : i - 1]


def _extract_key(block: str, key: str) -> str:
    m = re.search(rf'{key}\s*:\s*"([^"]+)"', block)
    assert m, f"key missing: {key}"
    return m.group(1)


def _current_snapshot() -> dict[str, dict[str, str]]:
    text = I18N_JS.read_text(encoding="utf-8")
    out: dict[str, dict[str, str]] = {}
    for lang in LANGS:
        block = _extract_lang_block(text, lang)
        out[lang] = {k: _extract_key(block, k) for k in KEYS}
    return out


def test_memory_map_i18n_snapshot_matches_expected() -> None:
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert _current_snapshot() == expected
