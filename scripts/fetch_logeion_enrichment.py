"""Pre-fetch Logeion structured entries for all la/grc vocabulary items
and store them in the SQLite cache at backend/cache/logeion_cache.db.

Lemma sources (priority order):
  1. Verb-morph SQLite DB  (la_verb_morph.db / grc_verb_morph.db)
  2. Noun/adj lemmas from la_morph.json / grc_morph.json
  3. First word of cultural-reference canonical_references

Usage:
    python scripts/fetch_logeion_enrichment.py [--language la] [--language grc]
           [--limit N] [--pos verb|noun|adj|all] [--dry-run]

    --limit 0 means no limit (process all collected lemmas).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sqlite3
import sys
import unicodedata

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Ensure the project root is on the path when run as a script.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

VOCAB_DB_PATHS: dict[str, str] = {
    "la":  "data/lexicons/la_verb_morph.db",
    "grc": "data/lexicons/grc_verb_morph.db",
}

MORPH_JSON_PATHS: dict[str, str] = {
    "la":  "data/lexicons/la_morph.json",
    "grc": "data/lexicons/grc_morph.json",
}

_PUNCT_STRIP = str.maketrans("", "", ",.;:!?\"'()[]{}--")

_POS_FILTER_MAP: dict[str, set[str]] = {
    "verb": {"verb", "aux"},
    "noun": {"noun", "propn"},
    "adj":  {"adj"},
    "all":  set(),  # empty = no filter
}


def _collect_verb_lemmas(lang: str) -> list[str]:
    """Collect verb lemmas from the verb-morph SQLite DB."""
    lemmas: list[str] = []
    db_path = pathlib.Path(VOCAB_DB_PATHS.get(lang, ""))
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        try:
            for row in conn.execute("SELECT DISTINCT lemma FROM verb_morph ORDER BY lemma"):
                lemmas.append(row[0])
        except sqlite3.OperationalError:
            pass
        finally:
            conn.close()
    return lemmas


def _collect_morph_lemmas(lang: str, pos_filter: set[str]) -> list[str]:
    """Collect unique lemmas from la_morph.json / grc_morph.json.

    pos_filter: set of POS tags to include.  Empty set = include all.
    """
    json_path = pathlib.Path(MORPH_JSON_PATHS.get(lang, ""))
    if not json_path.exists():
        return []
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        entries = data.get("entries", {})
        lemma_pos: dict[str, str] = {}
        for form_data in entries.values():
            if not isinstance(form_data, dict):
                continue
            lemma = form_data.get("lemma", "")
            pos = form_data.get("pos", "")
            if not lemma or not pos:
                continue
            if pos_filter and pos not in pos_filter:
                continue
            # Keep first POS seen for each lemma (good enough for filtering)
            if lemma not in lemma_pos:
                lemma_pos[lemma] = pos
        return sorted(lemma_pos.keys())
    except Exception:
        return []


def _collect_lemmas(lang: str, pos_filter: set[str]) -> list[str]:
    """Return ordered list of lemmas to pre-fetch, deduplicating across sources."""
    verb_lemmas = _collect_verb_lemmas(lang)
    seen: set[str] = set(verb_lemmas)

    morph_lemmas = [
        lm for lm in _collect_morph_lemmas(lang, pos_filter)
        if lm not in seen
    ]
    for lm in morph_lemmas:
        seen.add(lm)

    # Cultural-reference first words (last priority).
    ref_lemmas: list[str] = []
    json_path = pathlib.Path(f"backend/nuance/data/cultural_references/{lang}.json")
    if json_path.exists():
        cat = json.loads(json_path.read_text(encoding="utf-8"))
        ref_set: set[str] = set()
        for entry in cat.get("entries", []):
            ref = entry.get("canonical_reference", "")
            if ref:
                word = ref.split()[0].translate(_PUNCT_STRIP)
                if len(word) >= 3 and word not in seen and word not in ref_set:
                    ref_set.add(word)
        ref_lemmas = sorted(ref_set)

    return verb_lemmas + morph_lemmas + ref_lemmas


def _backfill_cached_morphology() -> None:
    """Add part_of_speech/gender to existing cache entries using _extract_morphology.

    Makes no network requests — derives POS from the already-cached gloss text.
    """
    from backend.dictionary.logeion import _open_cache, _extract_morphology

    conn = _open_cache()
    if conn is None:
        print("Cache not available")
        return

    rows = conn.execute(
        "SELECT language, lemma, payload FROM logeion_structured"
    ).fetchall()
    updated = 0
    for lang, lemma, payload in rows:
        d = json.loads(payload)
        if d.get("part_of_speech"):
            continue  # already has morphology
        gloss = d.get("gloss", "")
        morph = _extract_morphology(gloss, lang)
        if not morph:
            continue
        d.update(morph)
        conn.execute(
            "UPDATE logeion_structured SET payload=? WHERE language=? AND lemma=?",
            (json.dumps(d, ensure_ascii=False), lang, lemma),
        )
        updated += 1
    conn.commit()
    print(f"Backfilled morphology for {updated}/{len(rows)} cache entries")


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--language", action="append", default=[], dest="languages",
                    help="Language code(s) to fetch (default: la grc)")
    ap.add_argument("--limit", type=int, default=0,
                    help="Max lemmas per language (0 = no limit)")
    ap.add_argument("--pos", choices=["verb", "noun", "adj", "all"], default="all",
                    help="POS filter for morph-JSON lemmas (default: all)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print lemmas that would be fetched without making requests")
    ap.add_argument("--backfill-morphology", action="store_true",
                    help="Add part_of_speech/gender to existing cache entries (no network)")
    args = ap.parse_args()

    if args.backfill_morphology:
        _backfill_cached_morphology()
        return

    languages = args.languages or ["la", "grc"]
    pos_filter = _POS_FILTER_MAP[args.pos]

    from backend.dictionary.logeion import fetch_structured, _cache_get, _to_polytonic

    for lang in languages:
        lemmas = _collect_lemmas(lang, pos_filter)
        slice_ = lemmas if args.limit == 0 else lemmas[:args.limit]
        print(f"{lang}: {len(lemmas)} lemmas found, processing {len(slice_)}")
        n_fetched = n_cached = n_miss = n_error = n_skip = 0

        for lemma in slice_:
            # Normalize to polytonic for grc before cache check
            lemma_norm = _to_polytonic(lemma, lang)
            # Skip grc monotonic lemmas with no polytonic mapping — Logeion
            # requires polytonic Greek and will never match bare monotonic forms.
            if lang == "grc" and lemma_norm == lemma:
                nfd = unicodedata.normalize("NFD", lemma)
                if not any(unicodedata.category(c) == "Mn" for c in nfd):
                    n_skip += 1
                    continue
            if _cache_get(lemma_norm, lang) is not None:
                n_cached += 1
                continue
            if args.dry_run:
                label = f"{lemma} -> {lemma_norm}" if lemma_norm != lemma else lemma
                print(f"  would fetch: {label}")
                continue
            try:
                result = await fetch_structured(lemma, lang)
                if result:
                    n_fetched += 1
                    pos = result.get("part_of_speech", "")
                    gender = result.get("gender", "")
                    tag = f"{pos}{(' ' + gender) if gender else ''}"
                    defn = (result.get("ls_definition") or "")[:50]
                    display = f"{lemma_norm}" if lemma_norm != lemma else lemma
                    print(f"  {display} [{tag}]: {defn}...")
                else:
                    n_miss += 1
                await asyncio.sleep(0.5)
            except Exception as exc:
                n_error += 1
                print(f"  {lemma}: ERROR {exc}")
                await asyncio.sleep(1.0)

        print(f"{lang}: fetched={n_fetched} cached={n_cached} "
              f"miss={n_miss} skipped={n_skip} errors={n_error}")


if __name__ == "__main__":
    # ProactorEventLoop on Windows raises spurious errors during cleanup;
    # SelectorEventLoop is stable for HTTP-only async scripts.
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    sys.exit(0)
