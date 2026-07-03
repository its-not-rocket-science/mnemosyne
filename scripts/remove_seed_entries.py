#!/usr/bin/env python3
"""Remove entries by id from the cultural references seed YAML.

Usage:
  python scripts/remove_seed_entries.py \
    --ids <id1> [<id2> ...] \
    [--seed data/cultural_references_seed.yaml] \
    [--dry-run]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEED = ROOT / "data" / "cultural_references_seed.yaml"


def _load_yaml(path: Path):
    try:
        from ruamel.yaml import YAML
        y = YAML()
        y.preserve_quotes = True
        with open(path, encoding="utf-8") as f:
            return y.load(f), True
    except ImportError:
        import yaml
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f), False


def _write_yaml(entries, path: Path, use_ruamel: bool) -> None:
    if use_ruamel:
        from ruamel.yaml import YAML
        y = YAML()
        y.preserve_quotes = True
        y.default_flow_style = False
        y.width = 10000
        with open(path, "w", encoding="utf-8") as f:
            y.dump(entries, f)
    else:
        import yaml
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(entries, f, allow_unicode=True,
                      default_flow_style=False, sort_keys=False)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ids", nargs="+", required=True,
                    help="One or more entry ids to remove")
    ap.add_argument("--seed", type=Path, default=DEFAULT_SEED,
                    help=f"Seed file (default: {DEFAULT_SEED})")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print what would be removed without writing")
    args = ap.parse_args()

    if not args.seed.exists():
        sys.exit(f"ERROR: seed not found: {args.seed}")

    target_ids = set(args.ids)

    print(f"Loading {args.seed} ...", flush=True)
    entries, use_ruamel = _load_yaml(args.seed)
    if not isinstance(entries, list):
        sys.exit("ERROR: seed YAML root must be a list")

    kept    = []
    removed = []
    for entry in entries:
        if entry.get("id") in target_ids:
            removed.append(entry.get("id"))
        else:
            kept.append(entry)

    not_found = target_ids - set(removed)
    if not_found:
        print(f"Warning: ids not found in seed: {', '.join(sorted(not_found))}",
              file=sys.stderr)

    if args.dry_run:
        print(f"Would remove {len(removed)} entr{'y' if len(removed) == 1 else 'ies'}: "
              f"{', '.join(removed)}")
        return

    if not removed:
        print("Nothing to remove.")
        return

    print(f"Removed {len(removed)} entr{'y' if len(removed) == 1 else 'ies'}: "
          f"{', '.join(removed)}")
    print(f"Writing {args.seed} ...", flush=True)
    _write_yaml(kept, args.seed, use_ruamel)
    print("Done.")


if __name__ == "__main__":
    main()
