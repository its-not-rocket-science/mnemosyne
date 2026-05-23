"""Machine-readable language coverage matrix derived from the nuance inventory.

Usage::

    from backend.nuance.coverage import build_matrix
    matrix = build_matrix()
    # matrix["es"]["dimensions"] → ["argument_marking", "aspect", "mood", "register"]

    # CLI: python -m backend.nuance.coverage > coverage_matrix.json
"""
from __future__ import annotations

import json
import sys

from backend.nuance.dimensions import all_languages, get_inventory

_CEFR_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]


def _cefr_min(levels: list[str]) -> str:
    return min(levels, key=_CEFR_ORDER.index)


def _cefr_max(levels: list[str]) -> str:
    return max(levels, key=_CEFR_ORDER.index)


def build_matrix() -> dict[str, object]:
    """Return coverage data for every language in the inventory."""
    languages: dict[str, object] = {}
    for lang in sorted(all_languages()):
        inv = get_inventory(lang)
        all_lo = [s.cefr_range[0] for s in inv]
        all_hi = [s.cefr_range[1] for s in inv]
        languages[lang] = {
            "system_count": len(inv),
            "dimensions": sorted({s.dimension for s in inv}),
            "cefr_min": _cefr_min(all_lo),
            "cefr_max": _cefr_max(all_hi),
            "has_discourse_effects": any(s.discourse_effects for s in inv),
            "systems": [
                {
                    "name": s.name,
                    "dimension": s.dimension,
                    "cefr_range": list(s.cefr_range),
                    "contrast_concept": s.contrast_concept,
                    "native_term": s.native_term,
                }
                for s in inv
            ],
        }
    return {"languages": languages}


if __name__ == "__main__":
    json.dump(build_matrix(), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
