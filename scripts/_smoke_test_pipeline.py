"""Pipeline smoke tests for gap-closure sessions 1-5.

Calls the NLP pipeline components directly (no web server required).
Run from project root:
    python scripts/_smoke_test_pipeline.py
"""
from __future__ import annotations
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Force UTF-8 output on Windows (avoids cp1252 UnicodeEncodeError for CJK/Arabic chars).
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PASS = "[PASS]"
FAIL = "[FAIL]"
results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    mark = PASS if ok else FAIL
    print(f"  {mark} {name}" + (f"  ({detail})" if detail else ""))


from backend.nuance.cultural import extract_cultural_references  # noqa: E402

# ── 1. English ────────────────────────────────────────────────────────────────
print("\n[1] English cultural_reference: Achilles heel")
cands = extract_cultural_references("That loophole is his Achilles heel.", "en")
check("candidate returned", len(cands) >= 1, f"{len(cands)} matches")
if cands:
    ld = cands[0].lesson_data or {}
    check("has canonical_reference", bool(ld.get("canonical_reference")),
          ld.get("canonical_reference", ""))
    check("has explanation", bool(ld.get("explanation")))

# ── 2. Chinese ────────────────────────────────────────────────────────────────
print("\n[2] Chinese chengyu: wells-frog idiom")
cands = extract_cultural_references("He acted like a jingdi zhiwa.", "zh")
# Try with the actual Chinese text
cands2 = extract_cultural_references("不要做井底之蛙。", "zh")
cands = cands or cands2
check("candidate returned", len(cands) >= 1, f"{len(cands)} matches")
if cands:
    ld = cands[0].lesson_data or {}
    check("has explanation", bool(ld.get("explanation")))
    check("has canonical_reference", bool(ld.get("canonical_reference")),
          ld.get("canonical_reference", ""))

# ── 3. Persian ────────────────────────────────────────────────────────────────
print("\n[3] Persian: cultural reference fires on known surface pattern")
# Use a literal surface pattern from backend/nuance/data/cultural_references/fa.json
test_texts = [
    "آتش دین را در دل خود روشن کردن",  # first entry in catalogue
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

# ── 4. Latin ─────────────────────────────────────────────────────────────────
print("\n[4] Latin cultural_reference: carpe diem")
cands = extract_cultural_references("carpe diem, amice.", "la")
check("carpe diem candidate", len(cands) >= 1, f"{len(cands)} matches")
if cands:
    ld = cands[0].lesson_data or {}
    check("has explanation", bool(ld.get("explanation")))
    check("has source_author", bool(ld.get("source_author")),
          ld.get("source_author", ""))

# Logeion cache
try:
    from backend.dictionary.logeion import _cache_get
    # Try a few common Latin lemmas that should have been pre-seeded
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

# ── 5. i18n filter-bar keys ───────────────────────────────────────────────────
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

# ── summary ───────────────────────────────────────────────────────────────────
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
