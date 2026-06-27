"""Framework-to-CEFR level normalisation and sort key helpers."""
from __future__ import annotations

# Canonical CEFR order (index = difficulty rank, 0 = easiest).
CEFR_ORDER: dict[str, int] = {
    "A1": 0, "A2": 1, "B1": 2, "B2": 3, "C1": 4, "C2": 5,
}

JLPT_TO_CEFR: dict[str, str] = {
    "N5": "A1",
    "N4": "A2",
    "N3": "B1",
    "N2": "B2",
    "N1": "C1",
}

HSK_TO_CEFR: dict[str, str] = {
    "HSK1": "A1",
    "HSK2": "A1",
    "HSK3": "A2",
    "HSK4": "B1",
    "HSK5": "B2",
    "HSK6": "C1",
}

# Granular TOPIK levels 1-6.  TOPIK-I and TOPIK-II are kept for backward
# compatibility with manifests written before the granular scale was adopted.
TOPIK_TO_CEFR: dict[str, str] = {
    "TOPIK-I":  "A2",  # backward compat — maps to TOPIK1/TOPIK2 range
    "TOPIK-II": "B2",  # backward compat — maps to TOPIK3-TOPIK6 range
    "TOPIK1": "A1",
    "TOPIK2": "A2",
    "TOPIK3": "B1",
    "TOPIK4": "B2",
    "TOPIK5": "C1",
    "TOPIK6": "C2",
}

# ClassicalReading: pedagogical framework for classical Latin texts.
# Levels are standard CEFR codes; the framework name identifies the tradition.
CLASSICAL_READING_TO_CEFR: dict[str, str] = {
    "A1": "A1",
    "A2": "A2",
    "B1": "B1",
    "B2": "B2",
    "C1": "C1",
    "C2": "C2",
}

# KoineReading: pedagogical framework for Koine Greek texts.
# Same level codes as CEFR; framework name identifies the tradition.
KOINE_READING_TO_CEFR: dict[str, str] = {
    "A1": "A1",
    "A2": "A2",
    "B1": "B1",
    "B2": "B2",
    "C1": "C1",
    "C2": "C2",
}

_FRAMEWORK_MAPS: dict[str, dict[str, str]] = {
    "JLPT":           JLPT_TO_CEFR,
    "HSK":            HSK_TO_CEFR,
    "TOPIK":          TOPIK_TO_CEFR,
    "ClassicalReading": CLASSICAL_READING_TO_CEFR,
    "KoineReading":   KOINE_READING_TO_CEFR,
}


def to_cefr(framework: str, level: str) -> str | None:
    """Return the CEFR equivalent for a framework-specific level, or None."""
    if framework == "CEFR":
        return level if level in CEFR_ORDER else None
    return _FRAMEWORK_MAPS.get(framework, {}).get(level)


def difficulty_rank(framework: str, level: str) -> int:
    """Integer sort key (0 = easiest). Unknown levels sort last (99)."""
    cefr = to_cefr(framework, level)
    if cefr is None:
        return 99
    return CEFR_ORDER.get(cefr, 99)
