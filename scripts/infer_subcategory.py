#!/usr/bin/env python3
"""Infer subcategory and is_poetic_citation from existing seed fields (rule-based, free).

Usage:
  python scripts/infer_subcategory.py [--seed data/cultural_references_seed.yaml]
                                      [--dry-run] [--report]

Rules are deterministic; first match per entry wins.  Existing non-null values
are never overwritten.  Entries where no rule matches are left unchanged (consider
the LLM backfill pass in extend_cultural_catalogue.py --backfill-subcategory).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEED = ROOT / "data" / "cultural_references_seed.yaml"


def _all_cjk(s: str) -> bool:
    return bool(s) and all(
        "一" <= c <= "鿿" or "㐀" <= c <= "䶿"
        for c in s
    )


def infer_subcategory(entry: dict) -> tuple[str | None, bool]:
    """Return (subcategory, is_poetic_citation).  Returns (None, False) if no rule matches."""
    lang = entry.get("language", "")
    sw   = entry.get("source_work") or ""
    cr   = entry.get("canonical_reference") or ""
    rt   = entry.get("reference_type") or ""
    reg  = entry.get("register") or ""

    # ── ALL LANGUAGES (checked first — highest specificity overrides later) ──

    _ALL_BIBLE = ("Bible", "Genesis", "Psalms", "Proverbs", "Exodus",
                  "Isaiah", "Matthew", "Luke", "John", "Revelation",
                  "Old Testament", "New Testament", "King James")
    if any(k in sw for k in _ALL_BIBLE):
        return ("biblical", True)

    _ALL_SHAKES = ("Shakespeare", "Hamlet", "Macbeth", "King Lear",
                   "Othello", "Romeo and Juliet", "Midsummer", "Tempest",
                   "Merchant of Venice", "As You Like It")
    if any(k in sw for k in _ALL_SHAKES):
        return ("shakespearean", True)

    # ── PERSIAN ──────────────────────────────────────────────────────────────
    if lang == "fa":
        if "شاهنامه" in sw:
            return ("shahnameh", True)
        if "دیوان حافظ" in sw or "حافظ" in sw:
            return ("hafez", True)
        if "مثنوی" in sw:
            return ("rumi", True)
        if "گلستان" in sw or "بوستان" in sw:
            return ("saadi", True)
        if "خیام" in sw or "رباعیات" in sw:
            return ("khayyam", True)
        if "قرآن" in sw:
            return ("quranic", True)
        if sw in ("Various", "Wiktionary", "Oral tradition", ""):
            return (None, False)
        if reg in ("literary", "classical"):
            return (None, True)

    # ── ARABIC ───────────────────────────────────────────────────────────────
    elif lang == "ar":
        if "القرآن" in sw or "قرآن" in sw:
            return ("quranic", True)
        if "المتنبي" in sw or "متنبي" in sw:
            return ("muallaqat", True)
        if "المعلقات" in sw:
            return ("muallaqat", True)
        if "كليلة" in sw:
            return ("abbasid", False)
        if "ألف ليلة" in sw:
            return ("abbasid", False)
        if "ديوان" in sw:
            return ("muallaqat", False)

    # ── HINDI ────────────────────────────────────────────────────────────────
    elif lang == "hi":
        if "भगवद्गीता" in sw or "गीता" in sw:
            return ("bhagavad_gita", True)
        if "रामचरितमानस" in sw:
            return ("ramcharitmanas", True)
        if "रामायण" in sw or "वाल्मीकि" in sw:
            return ("ramcharitmanas", False)
        if "महाभारत" in sw:
            return ("bhagavad_gita", False)
        if "पंचतंत्र" in sw or "पञ्चतन्त्र" in sw:
            return ("panchatantra", False)
        if "कबीर" in sw:
            return ("doha_kabir", True)
        if "रहीम" in sw:
            return ("doha_rahim", True)
        if "।" in cr and len(cr) < 80 and reg in ("literary", "classical"):
            return (None, True)

    # ── CHINESE ──────────────────────────────────────────────────────────────
    elif lang == "zh":
        if rt == "proverb_tradition" and len(cr) == 4:
            return ("chengyu", False)
        if rt == "proverb_tradition" and "—" in cr:
            return ("xiehouyu", False)
        if "論語" in sw or "论语" in sw or "Analects" in sw:
            return ("chengyu", False)
        if "史記" in sw or "史记" in sw:
            return ("chengyu", False)
        if "孟子" in sw:
            return ("chengyu", False)
        if "三國演義" in sw or "三国演义" in sw:
            return ("chengyu", False)
        if sw == "Wiktionary" and len(cr) == 4:
            return ("chengyu", False)

    # ── JAPANESE ─────────────────────────────────────────────────────────────
    elif lang == "ja":
        if len(cr) == 4 and _all_cjk(cr):
            return ("yojijukugo", False)
        if "源氏物語" in sw:
            return ("kotowaza", False)
        if "平家物語" in sw:
            return ("kotowaza", False)
        if "般若心経" in sw:
            return ("zen_koan", True)

    # ── KOREAN ───────────────────────────────────────────────────────────────
    elif lang == "ko":
        if len(cr) == 4 and _all_cjk(cr):
            return ("sajaseong_eo", False)
        if "속담" in sw:
            return ("korean_proverb", False)
        if "판소리" in sw:
            return ("pansori", False)

    return (None, False)


def _load_yaml(path: Path) -> list[dict]:
    try:
        from ruamel.yaml import YAML
        yaml = YAML()
        yaml.preserve_quotes = True
        with open(path, encoding="utf-8") as f:
            return yaml.load(f)
    except ImportError:
        import yaml as pyyaml
        with open(path, encoding="utf-8") as f:
            return pyyaml.safe_load(f)


def _write_yaml(entries: list[dict], path: Path) -> None:
    try:
        from ruamel.yaml import YAML
        yaml = YAML()
        yaml.preserve_quotes = True
        yaml.default_flow_style = False
        yaml.width = 10000
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(entries, f)
    except ImportError:
        import yaml as pyyaml
        with open(path, "w", encoding="utf-8") as f:
            pyyaml.dump(entries, f, allow_unicode=True, default_flow_style=False,
                        sort_keys=False)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=Path, default=DEFAULT_SEED,
                    help=f"Seed file to read and update (default: {DEFAULT_SEED})")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print what would change without writing")
    ap.add_argument("--report", action="store_true",
                    help="Print coverage stats by language after applying rules")
    args = ap.parse_args()

    if not args.seed.exists():
        sys.exit(f"ERROR: seed not found: {args.seed}")

    print(f"Loading {args.seed} ...", flush=True)
    entries = _load_yaml(args.seed)
    if not isinstance(entries, list):
        sys.exit("ERROR: seed YAML root must be a list")

    print(f"Loaded {len(entries):,} entries.", flush=True)

    updated = 0
    skipped_already_set = 0
    no_rule = 0

    lang_stats: dict[str, dict] = {}

    for entry in entries:
        lang = entry.get("language", "??")
        if lang not in lang_stats:
            lang_stats[lang] = {"total": 0, "updated": 0, "already": 0, "no_rule": 0}
        lang_stats[lang]["total"] += 1

        has_sub    = entry.get("subcategory") is not None and entry.get("subcategory") != ""
        has_poetic = "is_poetic_citation" in entry

        if has_sub and has_poetic:
            skipped_already_set += 1
            lang_stats[lang]["already"] += 1
            continue

        inferred_sub, inferred_poetic = infer_subcategory(entry)

        if inferred_sub is None and not inferred_poetic:
            no_rule += 1
            lang_stats[lang]["no_rule"] += 1
            continue

        changed = False
        if not has_sub and inferred_sub is not None:
            if not args.dry_run:
                entry["subcategory"] = inferred_sub
            changed = True
        if not has_poetic and inferred_poetic:
            if not args.dry_run:
                entry["is_poetic_citation"] = inferred_poetic
            changed = True

        if changed:
            updated += 1
            lang_stats[lang]["updated"] += 1
        else:
            no_rule += 1
            lang_stats[lang]["no_rule"] += 1

    print(f"\nUpdated:           {updated:,}")
    print(f"Already had value: {skipped_already_set:,}")
    print(f"No rule matched:   {no_rule:,} (consider LLM pass for these)")

    if args.report:
        print("\nCoverage by language:")
        print(f"  {'lang':<6} {'total':>8} {'updated':>9} {'already':>9} {'no_rule':>9}")
        for lang, s in sorted(lang_stats.items()):
            print(f"  {lang:<6} {s['total']:>8,} {s['updated']:>9,} {s['already']:>9,} {s['no_rule']:>9,}")

    if not args.dry_run:
        print(f"\nWriting {args.seed} ...", flush=True)
        _write_yaml(entries, args.seed)
        print("Done.")
    else:
        print("\n(dry-run: no file written)")


if __name__ == "__main__":
    main()
