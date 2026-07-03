"""End-to-end smoke tests for the Mnemosyne NLP pipeline.

Tests the full cultural-reference detection path (parse → lesson data),
the Logeion SQLite cache, and the i18n lesson.js bundle completeness.
No web server required — runs directly against the Python backend.

Usage:
  python scripts/smoke_test_pipeline.py [--language LANG]

  --language LANG   Run only the check for the given BCP-47 language code
                    (default: run all checks).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PASS = "[PASS]"
FAIL = "[FAIL]"
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    mark = PASS if ok else FAIL
    print(f"  {mark} {name}" + (f"  ({detail})" if detail else ""))


def run_checks(language: str | None = None) -> None:
    from backend.nuance.cultural import extract_cultural_references

    if language is None or language == "en":
        print("\n[1] English cultural_reference: Achilles heel")
        cands = extract_cultural_references("That loophole is his Achilles heel.", "en")
        check("candidate returned", len(cands) >= 1, f"{len(cands)} matches")
        if cands:
            ld = cands[0].lesson_data or {}
            check("has canonical_reference", bool(ld.get("canonical_reference")),
                  ld.get("canonical_reference", ""))
            check("has explanation", bool(ld.get("explanation")))

    if language is None or language == "zh":
        print("\n[2] Chinese chengyu: wells-frog idiom")
        cands = extract_cultural_references("不要做井底之蛙。", "zh")
        check("candidate returned", len(cands) >= 1, f"{len(cands)} matches")
        if cands:
            ld = cands[0].lesson_data or {}
            check("has explanation", bool(ld.get("explanation")))
            check("has canonical_reference", bool(ld.get("canonical_reference")),
                  ld.get("canonical_reference", ""))

    if language is None or language == "fa":
        print("\n[3] Persian: cultural reference fires on known surface pattern")
        test_texts = [
            "آتش دین را در دل خود روشن کردن",
            "آذرخش بهرام",
            "آیات قرآن",
        ]
        found = []
        for text in test_texts:
            cands = extract_cultural_references(text, "fa")
            found.extend(cands)
            if cands:
                break
        check("candidate returned", len(found) >= 1,
              f"{len(found)} matches (tried {len(test_texts)} texts)")
        if found:
            ld = found[0].lesson_data or {}
            check("has canonical_reference", bool(ld.get("canonical_reference")),
                  ld.get("canonical_reference", "")[:40])

    if language is None or language == "la":
        print("\n[4] Latin cultural_reference: carpe diem")
        cands = extract_cultural_references("carpe diem, amice.", "la")
        check("carpe diem candidate", len(cands) >= 1, f"{len(cands)} matches")
        if cands:
            ld = cands[0].lesson_data or {}
            check("has explanation", bool(ld.get("explanation")))
            check("has source_author", bool(ld.get("source_author")),
                  ld.get("source_author", ""))

        try:
            from backend.dictionary.logeion import _cache_get
            cached = None
            for lemma in ("amo", "amor", "carpe", "dico", "facio"):
                cached = _cache_get(lemma, "la")
                if cached:
                    break
            check(
                "Logeion SQLite cache has entries",
                cached is not None,
                f"lemma={lemma!r} gloss={str(cached.get('gloss',''))[:40]}"
                if cached else "run fetch_logeion_enrichment.py --language la",
            )
        except Exception as exc:
            check("Logeion cache accessible", False, str(exc))

    if language is None:
        print("\n[5] i18n filter-bar keys in lesson.js bundle")
        bundle = Path("frontend/js/i18n/lesson.js")
        if bundle.exists():
            text = bundle.read_text(encoding="utf-8")
            expected = [
                "filter_vocab", "filter_grammar", "filter_idioms",
                "filter_literary", "filter_etymology", "filter_verse",
                "filter_custom", "filter_placeholder", "filter_add_btn",
            ]
            missing = [k for k in expected if k not in text]
            check("all filter keys present", not missing,
                  "missing: " + str(missing) if missing else "all 9 keys found")
            check("Spanish 'Verso'", "Verso" in text)
            check("Spanish 'Vocabulario'", "Vocabulario" in text)
            check("French 'Poesie' or 'Vers'", "Vers" in text)
        else:
            check("bundle file exists", False, str(bundle))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--language", "-l",
                    help="Run only checks for this BCP-47 language code (default: all)")
    args = ap.parse_args()

    run_checks(args.language)

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"\n{'='*50}")
    print(f"  {passed}/{total} checks passed")
    if passed < total:
        print("  FAILED:")
        for name, ok, detail in results:
            if not ok:
                print(f"  {FAIL} {name}: {detail}")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
