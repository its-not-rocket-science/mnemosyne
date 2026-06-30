"""Pre-fetch Logeion structured entries for all la/grc vocabulary items
and store them in the SQLite cache at backend/cache/logeion_cache.db.

Usage:
    python scripts/fetch_logeion_enrichment.py [--language la] [--language grc]
           [--limit 200] [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sqlite3
import sys

# Ensure the project root is on the path when run as a script.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

VOCAB_DB_PATHS: dict[str, str] = {
    "la":  "data/lexicons/la_verb_morph.db",
    "grc": "data/lexicons/grc_verb_morph.db",
}

_PUNCT_STRIP = str.maketrans("", "", ",.;:!?\"'()[]{}—–-")


def _collect_lemmas(lang: str) -> list[str]:
    # Verb-morph lemmas first (real dictionary headwords, lowercase).
    verb_lemmas: list[str] = []
    db_path = pathlib.Path(VOCAB_DB_PATHS.get(lang, ""))
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        try:
            for row in conn.execute("SELECT DISTINCT lemma FROM verb_morph ORDER BY lemma"):
                verb_lemmas.append(row[0])
        except sqlite3.OperationalError:
            pass
        finally:
            conn.close()

    # Cultural-reference first words (lowercased, de-duplicated against verb set).
    verb_set = set(verb_lemmas)
    ref_lemmas: set[str] = set()
    json_path = pathlib.Path(f"backend/nuance/data/cultural_references/{lang}.json")
    if json_path.exists():
        data = json.loads(json_path.read_text(encoding="utf-8"))
        for entry in data.get("entries", []):
            ref = entry.get("canonical_reference", "")
            if ref:
                word = ref.split()[0].translate(_PUNCT_STRIP)
                if len(word) >= 3 and word not in verb_set:
                    ref_lemmas.add(word)

    # Verb lemmas first (highest Logeion hit rate), then cultural refs.
    return verb_lemmas + sorted(ref_lemmas)


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--language", action="append", default=[], dest="languages",
                    help="Language code(s) to fetch (default: la grc)")
    ap.add_argument("--limit", type=int, default=200,
                    help="Max lemmas to process per language")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print lemmas that would be fetched without making requests")
    args = ap.parse_args()
    languages = args.languages or ["la", "grc"]

    from backend.dictionary.logeion import fetch_structured, _cache_get

    for lang in languages:
        lemmas = _collect_lemmas(lang)
        print(f"{lang}: {len(lemmas)} lemmas found")
        n_fetched = n_cached = n_error = 0

        for lemma in lemmas[:args.limit]:
            if _cache_get(lemma, lang) is not None:
                n_cached += 1
                continue
            if args.dry_run:
                print(f"  would fetch: {lemma}")
                continue
            try:
                result = await fetch_structured(lemma, lang)
                if result:
                    n_fetched += 1
                    defn = result.get("ls_definition") or ""
                    print(f"  {lemma}: {defn[:60]}...")
                else:
                    print(f"  {lemma}: not found in Logeion")
                await asyncio.sleep(0.5)
            except Exception as exc:
                n_error += 1
                print(f"  {lemma}: ERROR {exc}")
                await asyncio.sleep(1.0)

        print(f"{lang}: fetched={n_fetched} cached={n_cached} errors={n_error}")


if __name__ == "__main__":
    import sys
    # ProactorEventLoop on Windows raises spurious errors during cleanup;
    # SelectorEventLoop is stable for HTTP-only async scripts.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    sys.exit(0)
