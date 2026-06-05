#!/usr/bin/env python3
"""Audit CEFR vocabulary table coverage for Mnemosyne language plugins.

The CEFR tables are hand-curated, so this script checks the invariants that are
most likely to regress during manual fill work:

* required language/level tables exist;
* each table meets the agreed minimum size for that level;
* entries are non-empty strings; and
* no lemma is duplicated across levels for the same language.

By default the audit focuses on Finnish, Turkish, and Hindi because those tables
are newer dictionary-mode fills with independent morphology paths. Pass
``--languages`` to audit another subset, or ``--all-languages`` to audit every
language present in the CEFR maps.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_level_tables() -> dict[str, dict[str, frozenset[str]]]:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    from backend.plugins.cefr_vocab import A1, A2, B1, B2, C1, C2

    return {
        "A1": A1,
        "A2": A2,
        "B1": B1,
        "B2": B2,
        "C1": C1,
        "C2": C2,
    }

# The existing tests require A2/B1 to be broad enough for direct level tagging,
# while upper bands primarily suppress OOV false positives for advanced words.
MIN_COUNTS = {
    "A1": 90,
    "A2": 200,
    "B1": 200,
    "B2": 55,
    "C1": 55,
    "C2": 55,
}

DEFAULT_LANGUAGES = ("fi", "tr", "hi")


@dataclass(frozen=True)
class AuditResult:
    language: str
    level: str
    count: int
    minimum: int
    status: str


def _languages_for_args(args: argparse.Namespace) -> tuple[str, ...]:
    if args.all_languages:
        level_tables = _load_level_tables()
        langs = sorted(set().union(*(table.keys() for table in level_tables.values())))
        return tuple(langs)
    return tuple(args.languages or DEFAULT_LANGUAGES)


def audit_languages(languages: Iterable[str]) -> tuple[list[AuditResult], list[str]]:
    """Return per-level counts and human-readable audit failures."""
    results: list[AuditResult] = []
    failures: list[str] = []

    level_tables = _load_level_tables()

    for lang in languages:
        seen_by_level: dict[str, frozenset[str]] = {}
        for level, table in level_tables.items():
            words = table.get(lang)
            minimum = MIN_COUNTS[level]
            if words is None:
                results.append(AuditResult(lang, level, 0, minimum, "missing"))
                failures.append(f"{lang} {level}: table is missing")
                seen_by_level[level] = frozenset()
                continue

            bad_entries = [word for word in words if not isinstance(word, str) or not word]
            if bad_entries:
                failures.append(f"{lang} {level}: contains empty/non-string entries: {bad_entries[:5]!r}")

            status = "ok" if len(words) >= minimum and not bad_entries else "short"
            if len(words) < minimum:
                failures.append(f"{lang} {level}: {len(words)} entries < required {minimum}")
            results.append(AuditResult(lang, level, len(words), minimum, status))
            seen_by_level[level] = words

        level_names = list(level_tables)
        for index, left_level in enumerate(level_names):
            for right_level in level_names[index + 1:]:
                overlap = seen_by_level[left_level] & seen_by_level[right_level]
                if overlap:
                    sample = ", ".join(sorted(overlap)[:8])
                    failures.append(
                        f"{lang}: {left_level}/{right_level} overlap has "
                        f"{len(overlap)} entries: {sample}"
                    )

    return results, failures


def _print_results(results: list[AuditResult], failures: list[str]) -> None:
    print("Language  Level  Count  Min  Status")
    print("--------  -----  -----  ---  ------")
    for result in results:
        print(
            f"{result.language:<8}  {result.level:<5}  "
            f"{result.count:>5}  {result.minimum:>3}  {result.status}"
        )

    if failures:
        print("\nFailures:")
        for failure in failures:
            print(f"- {failure}")
    else:
        print("\nCEFR vocabulary audit passed.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--languages",
        nargs="+",
        metavar="LANG",
        help="Language codes to audit (default: fi tr hi).",
    )
    parser.add_argument(
        "--all-languages",
        action="store_true",
        help="Audit every language present in the CEFR vocabulary maps.",
    )
    args = parser.parse_args(argv)

    results, failures = audit_languages(_languages_for_args(args))
    _print_results(results, failures)
    return 1 if failures else 0


if __name__ == "__main__":  # pragma: no cover - exercised by CLI smoke checks
    sys.exit(main())
