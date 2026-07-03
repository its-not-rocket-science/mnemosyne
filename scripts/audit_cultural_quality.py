#!/usr/bin/env python3
"""Audit the built cultural catalogue JSON files for quality issues.

Read-only: identifies suspect entries and writes a plain-text report.
Does NOT modify any files.

Usage:
  python scripts/audit_cultural_quality.py \
    [--catalogue-dir backend/nuance/data/cultural_references] \
    [--language en] \
    [--output audit_quality_report.txt]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "backend" / "nuance" / "data" / "cultural_references"

# Suffixes that signal specialist/technical terms — not common CEFR A2 words
_SPECIALIST_SUFFIXES = ("-tion", "-ism", "-ist", "-ity", "-ness", "-ment",
                        "-ance", "-ence", "-ology", "-graphy", "-metry")

# Common English function words / prepositions that are obviously not cultural refs
_FUNCTION_WORDS = frozenset({
    "a", "an", "the", "and", "but", "or", "for", "nor", "so", "yet",
    "at", "by", "in", "of", "on", "to", "up", "as", "it", "is",
    "be", "to", "do", "go", "he", "we", "me", "my", "no",
})


def _is_common_word(word: str) -> bool:
    """Heuristic: True if word looks like a common CEFR A2-B1 vocabulary item
    (not a proper noun, not a specialist term, not a past tense of an irregular)."""
    if not word or not word.isalpha():
        return False
    if word[0].isupper():
        return False  # Proper noun — legitimate cultural reference
    w = word.lower()
    if w in _FUNCTION_WORDS:
        return True
    # Specialist/technical suffix → not a common word false positive
    for suf in _SPECIALIST_SUFFIXES:
        if w.endswith(suf):
            return False
    # Length heuristic: 3–10 letters, no capitals
    if 3 <= len(w) <= 10 and w.isalpha() and w == w.lower():
        return True
    return False


def _all_single_lower(surface_patterns: list[str]) -> bool:
    return bool(surface_patterns) and all(
        len(p.split()) == 1 and p == p.lower() and p.isalpha()
        for p in surface_patterns
    )


def audit_language(lang: str, entries: list[dict]) -> dict:
    n = len(entries)
    remove_recommended: list[dict] = []
    review_needed: list[dict]      = []
    duplicates: list[dict]         = []
    high_fp_risk: list[dict]       = []

    # Check 1: single-word lowercase entries
    for e in entries:
        pats = e.get("surface_patterns") or []
        conf = float(e.get("confidence") or 1.0)
        cr   = e.get("canonical_reference") or ""
        eid  = e.get("id", "?")
        expl = (e.get("short_explanation") or "")[:60]

        if _all_single_lower(pats):
            if conf < 0.80:
                if _is_common_word(cr):
                    remove_recommended.append({
                        "id": eid, "confidence": conf,
                        "canonical_reference": cr, "explanation": expl,
                    })
                else:
                    review_needed.append({
                        "id": eid, "confidence": conf,
                        "canonical_reference": cr, "explanation": expl,
                    })

    # Check 2: duplicate canonical references
    cr_counts: dict[str, list[str]] = defaultdict(list)
    for e in entries:
        cr = (e.get("canonical_reference") or "").strip().lower()
        if cr:
            cr_counts[cr].append(e.get("id", "?"))
    for cr, ids in cr_counts.items():
        if len(ids) > 1:
            duplicates.append({"canonical_reference": cr, "ids": ids})

    # Check 3: very short patterns, low confidence, no avoid_if guard
    for e in entries:
        pats   = e.get("surface_patterns") or []
        conf   = float(e.get("confidence") or 1.0)
        avoid  = e.get("avoid_if")
        short  = [p for p in pats if len(p.split()) <= 2]
        if short and conf < 0.75 and not avoid:
            high_fp_risk.append({
                "id": e.get("id", "?"),
                "confidence": conf,
                "patterns": short,
                "canonical_reference": e.get("canonical_reference") or "",
            })

    return {
        "lang": lang, "total": n,
        "remove_recommended": remove_recommended,
        "review_needed": review_needed,
        "duplicates": duplicates,
        "high_fp_risk": high_fp_risk,
    }


def format_report(results: list[dict]) -> str:
    lines: list[str] = ["CULTURAL CATALOGUE QUALITY AUDIT",
                         "================================="]
    grand = {"remove": 0, "review": 0, "dup": 0, "fp": 0}

    for r in results:
        lang  = r["lang"]
        total = r["total"]
        lines.append("")
        lines.append(f"Language: {lang}  Total entries: {total}")
        lines.append("-" * 50)

        rr = r["remove_recommended"]
        rv = r["review_needed"]
        dp = r["duplicates"]
        fp = r["high_fp_risk"]

        lines.append("")
        lines.append("CHECK 1 — Suspect single-word lowercase entries")
        lines.append("-" * 48)

        if rr:
            lines.append("REMOVE RECOMMENDED:")
            for e in rr:
                lines.append(
                    f"  {e['canonical_reference']!r}  "
                    f"(id={e['id']}, confidence={e['confidence']:.2f}, "
                    f"explanation={e['explanation']!r})"
                )
        else:
            lines.append("REMOVE RECOMMENDED: (none)")

        if rv:
            lines.append("REVIEW NEEDED:")
            for e in rv:
                lines.append(
                    f"  {e['canonical_reference']!r}  "
                    f"(id={e['id']}, confidence={e['confidence']:.2f}, "
                    f"explanation={e['explanation']!r})"
                )
        else:
            lines.append("REVIEW NEEDED: (none)")

        lines.append("")
        lines.append("CHECK 2 — Duplicate canonical references")
        lines.append("-" * 41)
        if dp:
            for d in dp:
                lines.append(f"  {d['canonical_reference']!r}: {', '.join(d['ids'])}")
        else:
            lines.append("(none)")

        lines.append("")
        lines.append("CHECK 3 — High false-positive risk")
        lines.append("-" * 36)
        if fp:
            shown = fp[:30]
            for e in shown:
                lines.append(
                    f"  {e['canonical_reference']!r}  "
                    f"(id={e['id']}, confidence={e['confidence']:.2f}, "
                    f"patterns={e['patterns']!r})"
                )
            if len(fp) > 30:
                lines.append(f"  ... and {len(fp) - 30} more")
        else:
            lines.append("(none)")

        lines.append("")
        lines.append("SUMMARY")
        lines.append("-------")
        lines.append(f"Remove recommended:  {len(rr)}")
        lines.append(f"Review needed:       {len(rv)}")
        lines.append(f"Duplicates:          {len(dp)}")
        lines.append(f"High FP risk:        {len(fp)}")

        grand["remove"] += len(rr)
        grand["review"] += len(rv)
        grand["dup"]    += len(dp)
        grand["fp"]     += len(fp)

    if len(results) > 1:
        lines.append("")
        lines.append("=" * 50)
        lines.append("GRAND TOTAL")
        lines.append(f"Remove recommended:  {grand['remove']}")
        lines.append(f"Review needed:       {grand['review']}")
        lines.append(f"Duplicates:          {grand['dup']}")
        lines.append(f"High FP risk:        {grand['fp']}")

    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--catalogue-dir", type=Path, default=DEFAULT_DIR,
                    help=f"Directory of per-language JSON files (default: {DEFAULT_DIR})")
    ap.add_argument("--language", "-l",
                    help="Audit only this language code (default: all)")
    ap.add_argument("--output", "-o", type=Path,
                    help="Write report to this file (default: stdout)")
    args = ap.parse_args()

    if not args.catalogue_dir.is_dir():
        sys.exit(f"ERROR: catalogue-dir not found: {args.catalogue_dir}")

    if args.language:
        paths = [args.catalogue_dir / f"{args.language}.json"]
        if not paths[0].exists():
            sys.exit(f"ERROR: no catalogue found for language: {args.language}")
    else:
        paths = sorted(args.catalogue_dir.glob("*.json"))
        if not paths:
            sys.exit(f"ERROR: no JSON files in {args.catalogue_dir}")

    results = []
    for p in paths:
        lang = p.stem
        try:
            data    = json.loads(p.read_text(encoding="utf-8"))
            entries = data.get("entries", [])
        except Exception as exc:
            print(f"Warning: could not read {p}: {exc}", file=sys.stderr)
            continue
        results.append(audit_language(lang, entries))

    report = format_report(results)

    if args.output:
        args.output.write_text(report, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
