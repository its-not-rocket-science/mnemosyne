#!/usr/bin/env python3
"""Audit nuance coverage across all supported language plugins.

Prints a table:
    language | idioms | phrase families | etymology | grammar nuance |
    literary/cultural | tests

Exits 1 if any supported language lacks a declared nuance_capabilities block,
so this can run as a CI gate.

Usage (from project root):
    PYTHONPATH=. python scripts/audit_nuance_coverage.py [--no-color]
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

# ── Language registry ─────────────────────────────────────────────────────────

# (lang_code, plugin_module, plugin_class)
SUPPORTED_LANGUAGES: list[tuple[str, str, str]] = [
    ("en",  "backend.plugins.stub_en",      "EnglishStubPlugin"),
    ("es",  "backend.plugins.spanish",       "SpanishPlugin"),
    ("fr",  "backend.plugins.french",        "FrenchPlugin"),
    ("de",  "backend.plugins.german",        "GermanPlugin"),
    ("it",  "backend.plugins.italian",       "ItalianPlugin"),
    ("pt",  "backend.plugins.portuguese",    "PortuguesePlugin"),
    ("ru",  "backend.plugins.russian",       "RussianPlugin"),
    ("ar",  "backend.plugins.arabic",        "ArabicPlugin"),
    ("he",  "backend.plugins.hebrew",        "HebrewPlugin"),
    ("zh",  "backend.plugins.chinese",       "MandarinChinesePlugin"),
    ("ja",  "backend.plugins.japanese",      "JapanesePlugin"),
    ("la",  "backend.plugins.latin",         "LatinPlugin"),
    ("grc", "backend.plugins.greek_koine",   "KoineGreekPlugin"),
    ("hi",  "backend.plugins.hindi",         "HindiPlugin"),
    ("tr",  "backend.plugins.turkish",       "TurkishPlugin"),
    ("fi",  "backend.plugins.finnish",       "FinnishPlugin"),
]

FIXTURE_DIR = Path(__file__).parent.parent / "backend" / "tests" / "fixtures" / "nuance_gold"

# Columns shown in the table (nuance_capabilities field names + derived columns)
DIMENSIONS = [
    ("idioms",           "Idioms"),
    ("phrase_families",  "Phrase fam."),
    ("etymology",        "Etymology"),
    ("grammar_nuance",   "Grammar"),
    ("formality_register","Register"),
]
LITERARY_FIELDS = [
    "literary_references",
    "cultural_references",
    "proverb_tradition",
    "classical_or_scriptural_allusion",
]

# ── Terminal color helpers ────────────────────────────────────────────────────

_USE_COLOR = True

_LEVEL_COLOR: dict[str | None, str] = {
    None:      "\033[31m",   # red   — missing declaration
    "none":    "\033[90m",   # dark grey
    "stub":    "\033[33m",   # yellow
    "partial": "\033[36m",   # cyan
    "strong":  "\033[32m",   # green
    "gold":    "\033[93m",   # bright yellow
}
_RESET = "\033[0m"


def _color(level: str | None, text: str) -> str:
    if not _USE_COLOR:
        return text
    return f"{_LEVEL_COLOR.get(level, '')}{text}{_RESET}"


# ── Plugin loading ────────────────────────────────────────────────────────────

def _load_plugin(module_path: str, class_name: str):
    try:
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
        return cls()
    except Exception:
        return None


# ── Fixture case count ────────────────────────────────────────────────────────

def _fixture_case_count(lang: str) -> int:
    p = FIXTURE_DIR / f"{lang}.json"
    if not p.exists():
        return 0
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return len(data.get("cases", []))
    except Exception:
        return 0


# ── Literary/cultural collapse ────────────────────────────────────────────────

def _best_literary(caps) -> str | None:
    order = ["none", "stub", "partial", "strong", "gold"]
    best = "none"
    for field in LITERARY_FIELDS:
        val = getattr(caps, field, None)
        if val is None:
            return None
        if order.index(val) > order.index(best):
            best = val
    return best


# ── Table rendering ───────────────────────────────────────────────────────────

_COL_WIDTHS = {
    "lang":     6,
    "dim":      10,
    "literary": 10,
    "tests":    6,
}

_HEADER_LANG     = "Lang"
_HEADER_LITERARY = "Lit/cult"
_HEADER_TESTS    = "Tests"


def _row(
    lang: str,
    caps,
    case_count: int,
    missing: bool,
) -> str:
    cells: list[str] = [lang.ljust(_COL_WIDTHS["lang"])]

    if caps is None or missing:
        marker = _color(None, "MISSING")
        cells.append(marker)
        return " | ".join(cells)

    for field, _ in DIMENSIONS:
        val: str | None = getattr(caps, field, None)
        display = val if val is not None else "?"
        cells.append(_color(val, display.ljust(_COL_WIDTHS["dim"])))

    lit = _best_literary(caps)
    cells.append(_color(lit, (lit or "?").ljust(_COL_WIDTHS["literary"])))
    cells.append(str(case_count).rjust(_COL_WIDTHS["tests"]))
    return " | ".join(cells)


def _separator(ncols: int) -> str:
    parts = ["-" * _COL_WIDTHS["lang"]]
    for _ in range(ncols - 2):
        parts.append("-" * _COL_WIDTHS["dim"])
    parts.append("-" * _COL_WIDTHS["tests"])
    return "-+-".join(parts)


def _header() -> str:
    cells = [_HEADER_LANG.ljust(_COL_WIDTHS["lang"])]
    for _, label in DIMENSIONS:
        cells.append(label.ljust(_COL_WIDTHS["dim"]))
    cells.append(_HEADER_LITERARY.ljust(_COL_WIDTHS["literary"]))
    cells.append(_HEADER_TESTS.rjust(_COL_WIDTHS["tests"]))
    return " | ".join(cells)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    global _USE_COLOR

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI colors")
    args = parser.parse_args()
    if args.no_color:
        _USE_COLOR = False

    failures: list[str] = []
    rows: list[str] = []
    ncols = 1 + len(DIMENSIONS) + 2  # lang + dims + literary + tests

    for lang, module_path, class_name in SUPPORTED_LANGUAGES:
        plugin = _load_plugin(module_path, class_name)
        case_count = _fixture_case_count(lang)

        if plugin is None:
            failures.append(f"  {lang}: plugin {class_name} failed to import")
            rows.append(_row(lang, None, case_count, missing=True))
            continue

        caps = getattr(plugin.capabilities, "nuance_capabilities", None)
        if caps is None:
            failures.append(
                f"  {lang}: {class_name}.capabilities.nuance_capabilities not declared"
            )
            rows.append(_row(lang, None, case_count, missing=True))
            continue

        rows.append(_row(lang, caps, case_count, missing=False))

    print()
    print(_header())
    print(_separator(ncols))
    for row in rows:
        print(row)
    print()

    if failures:
        print("FAIL — missing nuance_capabilities declarations:", file=sys.stderr)
        for msg in failures:
            print(msg, file=sys.stderr)
        print(file=sys.stderr)
        return 1

    total_tests = sum(_fixture_case_count(lang) for lang, _, _ in SUPPORTED_LANGUAGES)
    print(f"OK — {len(SUPPORTED_LANGUAGES)} languages · {total_tests} gold-test cases")
    return 0


if __name__ == "__main__":
    sys.exit(main())
