"""Generate and insert PhraseFamily entries from JSON spec files.

Usage:
    python scripts/gen_phrase_families.py [--lang LANG] [--dry-run] [--validate-only]

Each JSON spec file lives at scripts/data/phrase_families_{lang}.json and contains
a list of family objects with this schema:

    {
      "id": "es_ir_al_grano",
      "canonical": "ir al grano",
      "meaning": "Get to the point.",
      "register": "neutral",
      "origin": "Optional origin note.",
      "why_it_matters": "Optional learner note.",
      "variants": [
        {"surface": "ir al grano", "type": "exact"},
        {"surface": "yendo al grano", "type": "inflectional_variant", "note": "Gerund form."}
      ],
      "confusables": []
    }

The script:
  1. Loads and validates all spec files for the requested language(s).
  2. Checks for duplicate IDs, missing exact variants, and normalised-surface
     collisions across the entire catalog (existing + new).
  3. Generates Python code and appends it before the closing ``}`` of
     ``_FAMILY_CATALOG`` in backend/dictionary/phrase_families.py.
  4. Runs the phrase_families module's own integrity checks to confirm.

The script is idempotent: if an ID already exists in the catalog it is skipped
with a warning rather than duplicated.
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
TARGET = ROOT / "backend" / "dictionary" / "phrase_families.py"

VALID_REGISTERS = {"neutral", "literary", "formal", "informal", "archaic"}
VALID_MATCH_TYPES = {
    "exact", "orthographic_variant", "modernized_variant",
    "inflectional_variant", "misquotation", "blend", "allusion",
    "confusable_not_same",
}

_STRIP_PUNCT = re.compile(r"[^\w\s]")


def _normalize(surface: str) -> str:
    return _STRIP_PUNCT.sub("", surface.lower()).strip()


def _load_spec(lang: str) -> list[dict]:
    path = DATA_DIR / f"phrase_families_{lang}.json"
    if not path.exists():
        sys.exit(f"[error] no spec file for lang={lang!r}: {path}")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _existing_ids() -> set[str]:
    src = TARGET.read_text(encoding="utf-8")
    return set(re.findall(r'"([\w]+)":\s*PhraseFamily\(', src))


def _existing_normalized_surfaces() -> set[str]:
    """Extract all normalized variant surfaces already in the catalog."""
    src = TARGET.read_text(encoding="utf-8")
    surfaces = re.findall(r'surface\s*=\s*"([^"]+)"', src)
    return {_normalize(s) for s in surfaces}


def _validate(specs: list[dict], lang: str, existing_ids: set[str],
               existing_norms: set[str]) -> tuple[list[dict], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    seen_ids: set[str] = set()
    seen_norms: set[str] = set(existing_norms)
    valid: list[dict] = []

    for fam in specs:
        fid = fam.get("id", "")
        if not fid:
            errors.append(f"  family missing 'id': {fam}")
            continue
        if not fid.startswith(f"{lang}_"):
            errors.append(f"  [{fid}] id must start with '{lang}_'")
        if fid in existing_ids:
            warnings.append(f"  [{fid}] already in catalog — skipping")
            continue
        if fid in seen_ids:
            errors.append(f"  [{fid}] duplicate id in spec file")
            continue
        seen_ids.add(fid)

        variants = fam.get("variants", [])
        if not variants:
            errors.append(f"  [{fid}] has no variants")
            continue

        exact_count = sum(1 for v in variants if v.get("type") == "exact")
        if exact_count == 0:
            errors.append(f"  [{fid}] has no exact variant")
        elif exact_count > 1:
            errors.append(f"  [{fid}] has multiple exact variants")

        register = fam.get("register", "")
        if register not in VALID_REGISTERS:
            errors.append(f"  [{fid}] invalid register {register!r}; must be one of {sorted(VALID_REGISTERS)}")

        for v in variants:
            mt = v.get("type", "")
            if mt not in VALID_MATCH_TYPES:
                errors.append(f"  [{fid}] invalid match_type {mt!r}")
            norm = _normalize(v.get("surface", ""))
            if norm in seen_norms:
                errors.append(f"  [{fid}] normalized surface collision: {v['surface']!r}")
            else:
                seen_norms.add(norm)

        if not errors:
            valid.append(fam)

    return valid, errors, warnings


def _escape(s: str | None) -> str:
    if s is None:
        return "None"
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def _esc(s: str) -> str:
    """Escape backslash and double-quote for inclusion inside a Python "..." literal."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _render_family(fam: dict) -> str:
    fid = fam["id"]
    lang = fid.split("_")[0]
    canonical = fam["canonical"]
    meaning = fam["meaning"]
    register = fam["register"]
    origin = fam.get("origin")
    why = fam.get("why_it_matters")
    confusables = fam.get("confusables", [])

    lines: list[str] = []
    lines.append(f'    "{fid}": PhraseFamily(')
    lines.append(f'        id="{fid}",')
    lines.append(f'        language="{lang}",')
    lines.append(f'        canonical_form="{_esc(canonical)}",')
    # meaning — wrap at 80 chars
    wrapped_meaning = textwrap.fill(meaning, width=72, subsequent_indent="            ")
    if "\n" in wrapped_meaning:
        lines.append(f'        meaning=(')
        for part in textwrap.wrap(meaning, width=72):
            lines.append(f'            "{_esc(part)}"')
        lines.append(f'        ),')
    else:
        lines.append(f'        meaning="{_esc(meaning)}",')
    lines.append(f'        register="{register}",')
    if origin:
        wrapped = textwrap.wrap(origin, width=72)
        if len(wrapped) == 1:
            lines.append(f'        origin="{_esc(origin)}",')
        else:
            lines.append(f'        origin=(')
            for i, part in enumerate(wrapped):
                sep = "" if i == len(wrapped) - 1 else " "
                lines.append(f'            "{_esc(part)}{sep}"')
            lines.append(f'        ),')
    if why:
        wrapped = textwrap.wrap(why, width=72)
        if len(wrapped) == 1:
            lines.append(f'        why_it_matters="{_esc(why)}",')
        else:
            lines.append(f'        why_it_matters=(')
            for i, part in enumerate(wrapped):
                sep = "" if i == len(wrapped) - 1 else " "
                lines.append(f'            "{_esc(part)}{sep}"')
            lines.append(f'        ),')
    if confusables:
        conf_str = ", ".join(f'"{_esc(c)}"' for c in confusables)
        lines.append(f'        confusables=({conf_str},),')
    lines.append(f'        variants=(')
    for v in fam["variants"]:
        surface = v["surface"]
        mt = v["type"]
        note = v.get("note")
        lines.append(f'            PhraseVariant(')
        lines.append(f'                surface="{_esc(surface)}",')
        lines.append(f'                match_type=MatchType.{mt},')
        if note:
            lines.append(f'                note="{_esc(note)}",')
        lines.append(f'            ),')
    lines.append(f'        ),')
    lines.append(f'    ),')
    return "\n".join(lines)


def _patch_file(new_families: list[dict], lang: str, dry_run: bool) -> int:
    src = TARGET.read_text(encoding="utf-8")

    # Find insertion point: last closing } of _FAMILY_CATALOG
    # Strategy: find the last PhraseFamily(...), closing ), then insert before the
    # final closing } of the dict.
    lang_header = f"# ── {lang.upper()}"
    # Find the last occurrence of a family closing "),\n" then insert
    # new block before the closing "}" of _FAMILY_CATALOG.

    # Locate the end of _FAMILY_CATALOG: the sole '}' on its own line after
    # the last PhraseFamily block.
    match = re.search(r'\n\}\s*\n', src)
    if not match:
        sys.exit("[error] cannot locate closing '}' of _FAMILY_CATALOG")

    # We want the LAST occurrence
    last_close = max(m.start() for m in re.finditer(r'\n\}\s*\n', src))
    insert_pos = last_close  # insert before the \n}

    code_blocks: list[str] = []

    # Group families by language section header
    code_blocks.append(f"\n    # ── {lang.title()} (generated) {'─' * 40}")
    for fam in new_families:
        code_blocks.append("\n" + _render_family(fam))

    insertion = "\n".join(code_blocks) + "\n"

    new_src = src[:insert_pos] + insertion + src[insert_pos:]

    if dry_run:
        print("[dry-run] would insert:")
        print(insertion[:2000])
        if len(insertion) > 2000:
            print(f"  ... ({len(insertion) - 2000} more chars)")
        return len(new_families)

    TARGET.write_text(new_src, encoding="utf-8")
    return len(new_families)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate PhraseFamily entries from JSON specs")
    parser.add_argument("--lang", nargs="+",
                        help="Language code(s) to process (default: all with spec files)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print generated code without modifying phrase_families.py")
    parser.add_argument("--validate-only", action="store_true",
                        help="Validate spec files without generating any code")
    args = parser.parse_args()

    if args.lang:
        langs = args.lang
    else:
        langs = sorted(p.stem.replace("phrase_families_", "") for p in DATA_DIR.glob("phrase_families_*.json"))

    if not langs:
        sys.exit(f"[error] no spec files found in {DATA_DIR}")

    existing_ids = _existing_ids()
    existing_norms = _existing_normalized_surfaces()
    print(f"Existing catalog: {len(existing_ids)} families, {len(existing_norms)} normalized surfaces")

    all_valid: dict[str, list[dict]] = {}
    all_errors: list[str] = []

    for lang in langs:
        specs = _load_spec(lang)
        valid, errors, warnings = _validate(specs, lang, existing_ids, existing_norms)
        for w in warnings:
            print(f"[warn]  {lang}: {w}")
        if errors:
            print(f"[ERROR] {lang}: {len(errors)} validation error(s):")
            for e in errors:
                print(e)
            all_errors.extend(errors)
        else:
            print(f"[ok]    {lang}: {len(valid)} new families validated")
            all_valid[lang] = valid
        # update seen norms for cross-lang validation (norms are per-language, but IDs are global)
        for fam in valid:
            existing_ids.add(fam["id"])

    if all_errors:
        sys.exit(f"\n{len(all_errors)} validation error(s). Aborting.")

    if args.validate_only:
        print("\nValidation passed. (--validate-only: no files written)")
        return

    total = 0
    for lang, families in all_valid.items():
        if not families:
            continue
        n = _patch_file(families, lang, dry_run=args.dry_run)
        total += n
        if not args.dry_run:
            print(f"[wrote] {lang}: {n} families appended to phrase_families.py")

    if args.dry_run:
        print(f"\n[dry-run] {total} families would be appended.")
        return

    # Verify by importing the module
    print("\nVerifying module import...")
    import subprocess
    result = subprocess.run(
        [sys.executable, "-c",
         "from backend.dictionary.phrase_families import _FAMILY_CATALOG; "
         "print(f'catalog size: {len(_FAMILY_CATALOG)}')"],
        capture_output=True, text=True, cwd=str(ROOT)
    )
    if result.returncode != 0:
        print("[ERROR] import failed:")
        print(result.stderr)
        sys.exit(1)
    print(result.stdout.strip())
    print(f"\nDone. {total} new families added.")


if __name__ == "__main__":
    main()
