"""Generate and insert EtymologyEntry objects from JSON spec files.

Usage:
    python scripts/gen_etymology.py [--lang LANG [LANG ...]] [--dry-run] [--validate-only]

Each JSON spec file lives at scripts/data/etymology_{lang}.json and contains
a list of entry objects with this schema:

    {
      "language": "it",
      "lemma": "crescendo",
      "origin_summary": "From Latin crescere (to grow)...",
      "roots": ["Latin crescere (to grow)"],
      "cognates": ["English 'increase' (same root)"],
      "semantic_shift": "'growing' → musical term for gradually increasing volume"
    }

All fields except cognates and semantic_shift are required.
confidence defaults to 1.0, source_type to "curated".

The script:
  1. Loads and validates all spec files for the requested language(s).
  2. Checks for duplicate (language, lemma) pairs against existing entries.
  3. Generates Python EtymologyEntry(...) code and inserts it before the
     closing ']' of _CURATED in backend/dictionary/etymology.py.
  4. Verifies the module imports cleanly after patching.

Idempotent: existing (language, lemma) pairs are skipped with a warning.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(__file__).resolve().parent / "data"
TARGET = ROOT / "backend" / "dictionary" / "etymology.py"


def _load_spec(lang: str) -> list[dict]:
    path = DATA_DIR / f"etymology_{lang}.json"
    if not path.exists():
        sys.exit(f"[error] no spec file for lang={lang!r}: {path}")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _existing_keys() -> set[tuple[str, str]]:
    """Return (language, lemma) pairs already in etymology.py."""
    src = TARGET.read_text(encoding="utf-8")
    pairs = re.findall(r'language="([^"]+)",\s+lemma="([^"]+)"', src)
    return {(lang, lemma) for lang, lemma in pairs}


def _validate(specs: list[dict], lang: str,
              existing: set[tuple[str, str]]) -> tuple[list[dict], list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    seen: set[tuple[str, str]] = set()
    valid: list[dict] = []

    for entry in specs:
        language = entry.get("language", "").strip()
        lemma = entry.get("lemma", "").strip()
        origin = entry.get("origin_summary", "").strip()
        roots = entry.get("roots", [])

        if not language or not lemma:
            errors.append(f"  entry missing language or lemma: {entry}")
            continue
        if language != lang:
            errors.append(f"  [{lemma}] language {language!r} does not match file lang {lang!r}")
            continue
        if not origin:
            errors.append(f"  [{lemma}] missing origin_summary")
        if not roots:
            errors.append(f"  [{lemma}] missing roots (must be non-empty list)")
        key = (language, lemma)
        if key in existing:
            warnings.append(f"  [{lemma}] already in etymology store — skipping")
            continue
        if key in seen:
            errors.append(f"  [{lemma}] duplicate entry in spec file")
            continue
        seen.add(key)

        if not errors:
            valid.append(entry)

    return valid, errors, warnings


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _render_string(s: str, indent: int = 8) -> str:
    """Render a string as a Python string literal, wrapping long values."""
    ind = " " * indent
    ind2 = " " * (indent + 4)
    wrapped = textwrap.wrap(s, width=72 - indent)
    if len(wrapped) <= 1:
        return f'"{_esc(s)}"'
    # Multi-line string concatenation
    parts = []
    for i, part in enumerate(wrapped):
        sep = "" if i == len(wrapped) - 1 else " "
        parts.append(f'{ind2}"{_esc(part)}{sep}"')
    return "(\n" + "\n".join(parts) + f"\n{ind})"


def _render_entry(entry: dict) -> str:
    lang = entry["language"]
    lemma = entry["lemma"]
    origin = entry["origin_summary"]
    roots = entry.get("roots", [])
    cognates = entry.get("cognates", [])
    shift = entry.get("semantic_shift")

    lines = ["    EtymologyEntry("]
    lines.append(f'        language="{lang}", lemma="{_esc(lemma)}",')

    # origin_summary
    origin_rendered = _render_string(origin, indent=8)
    lines.append(f"        origin_summary={origin_rendered},")

    # roots
    root_items = ", ".join(f'"{_esc(r)}"' for r in roots)
    if len(root_items) < 60:
        lines.append(f"        roots=[{root_items}],")
    else:
        lines.append("        roots=[")
        for r in roots:
            lines.append(f'            "{_esc(r)}",')
        lines.append("        ],")

    # cognates (optional)
    if cognates:
        cog_items = ", ".join(f'"{_esc(c)}"' for c in cognates)
        if len(cog_items) < 60:
            lines.append(f"        cognates=[{cog_items}],")
        else:
            lines.append("        cognates=[")
            for c in cognates:
                lines.append(f'            "{_esc(c)}",')
            lines.append("        ],")

    # semantic_shift (optional)
    if shift:
        shift_rendered = _render_string(shift, indent=8)
        lines.append(f"        semantic_shift={shift_rendered},")

    lines.append("    ),")
    return "\n".join(lines)


def _patch_file(new_entries: list[dict], lang: str, dry_run: bool) -> int:
    src = TARGET.read_text(encoding="utf-8")

    # Find the closing ']' of _CURATED (the last standalone ']' before
    # the DEFAULT_STORE assignment)
    marker = re.search(r'\n\]\s*\n\s*\n#', src)
    if not marker:
        sys.exit("[error] cannot locate closing ']' of _CURATED in etymology.py")

    insert_pos = marker.start() + 1  # after the '\n', before ']'

    header = f"\n    # ── {lang.upper()} additions (generated by gen_etymology.py) ──"
    code_blocks = [header]
    for entry in new_entries:
        code_blocks.append(_render_entry(entry))

    insertion = "\n".join(code_blocks) + "\n"

    new_src = src[:insert_pos] + insertion + src[insert_pos:]

    if dry_run:
        print("[dry-run] would insert:")
        print(insertion[:2000])
        if len(insertion) > 2000:
            print(f"  ... ({len(insertion) - 2000} more chars)")
        return len(new_entries)

    TARGET.write_text(new_src, encoding="utf-8")
    return len(new_entries)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate EtymologyEntry objects from JSON specs")
    parser.add_argument("--lang", nargs="+",
                        help="Language code(s) to process (default: all with spec files)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    if args.lang:
        langs = args.lang
    else:
        langs = sorted(
            p.stem.replace("etymology_", "")
            for p in DATA_DIR.glob("etymology_*.json")
        )

    if not langs:
        sys.exit(f"[error] no etymology spec files found in {DATA_DIR}")

    existing = _existing_keys()
    print(f"Existing etymology store: {len(existing)} entries")

    all_valid: dict[str, list[dict]] = {}
    all_errors: list[str] = []

    for lang in langs:
        specs = _load_spec(lang)
        valid, errors, warnings = _validate(specs, lang, existing)
        for w in warnings:
            print(f"[warn]  {lang}: {w}")
        if errors:
            print(f"[ERROR] {lang}: {len(errors)} validation error(s):")
            for e in errors:
                print(e)
            all_errors.extend(errors)
        else:
            print(f"[ok]    {lang}: {len(valid)} new entries validated")
            all_valid[lang] = valid
        for entry in valid:
            existing.add((entry["language"], entry["lemma"]))

    if all_errors:
        sys.exit(f"\n{len(all_errors)} validation error(s). Aborting.")

    if args.validate_only:
        print("\nValidation passed. (--validate-only: no files written)")
        return

    total = 0
    for lang, entries in all_valid.items():
        if not entries:
            continue
        n = _patch_file(entries, lang, dry_run=args.dry_run)
        total += n
        if not args.dry_run:
            print(f"[wrote] {lang}: {n} entries appended to etymology.py")

    if args.dry_run:
        print(f"\n[dry-run] {total} entries would be appended.")
        return

    import subprocess
    result = subprocess.run(
        [sys.executable, "-c",
         "from backend.dictionary.etymology import DEFAULT_STORE; "
         "print(f'etymology store size: {len(DEFAULT_STORE._data)}')"],
        capture_output=True, text=True, cwd=str(ROOT)
    )
    if result.returncode != 0:
        print("[ERROR] import failed:")
        print(result.stderr)
        sys.exit(1)
    print(result.stdout.strip())
    print(f"\nDone. {total} new etymology entries added.")


if __name__ == "__main__":
    main()
