#!/usr/bin/env python3
"""Fetch idiom (and optionally proverb) entries from Wiktionary category pages
for a target language and write them as a CSV in the format expected by
import_cultural_sources.py.

Wiktionary's idiom/proverb category pages are structured, freely licensed
(CC-BY-SA 4.0), and contain thousands of entries per language. This script
queries the public MediaWiki API (no authentication required) to page through
category members, optionally fetches a one-line definition per entry, and
deduplicates against an existing seed YAML before writing output.

Usage:
  python scripts/fetch_wiktionary_idioms.py \\
    --language en \\
    --output data/cultural_sources/en_wiktionary_idioms.csv \\
    [--seed data/cultural_references_seed.yaml] \\
    [--fetch-definitions] \\
    [--include-proverbs] \\
    [--limit 1000]

Downstream usage — import the CSV using the existing pipeline:
  python scripts/import_cultural_sources.py \\
    data/cultural_sources/en_wiktionary_idioms.csv \\
    --output data/cultural_drafts/en_wiktionary_idioms.yaml
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import quote

import requests

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - exercised in minimal environments
    yaml = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEED = ROOT / "data" / "cultural_references_seed.yaml"

# Must match EXPECTED_CSV_HEADER in scripts/import_cultural_sources.py exactly.
EXPECTED_CSV_HEADER = (
    "language,surface_pattern,surface_patterns,variants,canonical_reference,reference_type,"
    "source_work,source_author,source_location,source_quote,source_note,short_explanation,"
    "explanation_key,source_work_key,source_author_key,learner_level,register,confidence,"
    "source_url,source_license,rights_basis,source_dataset,notes"
)
CSV_FIELDS = EXPECTED_CSV_HEADER.split(",")

BASE_URL = "https://en.wiktionary.org/w/api.php"
USER_AGENT = "Mnemosyne-cultural-catalogue-builder/1.0 (educational; contact: see github)"
REQUEST_DELAY_S = 1.0  # Wikimedia enforces ~1 req/s in practice (Retry-After: 58
                        # observed at 4 req/s). 1 req/s matches Wikimedia bot guidelines.

WIKTIONARY_LANG_NAMES: dict[str, str] = {
    "en":  "English",
    "es":  "Spanish",
    "fr":  "French",
    "de":  "German",
    "it":  "Italian",
    "pt":  "Portuguese",
    "ru":  "Russian",
    "ar":  "Arabic",
    "he":  "Hebrew",
    "zh":  "Chinese",
    "ja":  "Japanese",
    "la":  "Latin",
    "ko":  "Korean",
    "hi":  "Hindi",
    "tr":  "Turkish",
    "fa":  "Persian",
    "grc": "Ancient Greek",
    "fi":  "Finnish",
}

# Separate category map for proverbs — add others as confirmed to exist in
# Wiktionary (not every language has a populated "{Language} proverbs" category).
WIKTIONARY_PROVERB_NAMES: dict[str, str] = {
    "en": "English proverbs",
    "es": "Spanish proverbs",
    "fr": "French proverbs",
    "de": "German proverbs",
    "ru": "Russian proverbs",
    "ar": "Arabic proverbs",
    "zh": "Chinese proverbs",
    "ja": "Japanese proverbs",
}

TODO_EXPLANATION = "TODO: add explanation"
LICENSE_COMMENT = (
    "# Source: Wiktionary (https://www.wiktionary.org), licensed CC-BY-SA 4.0. "
    "Attribution and share-alike terms apply to any redistribution of this "
    "content — see https://creativecommons.org/licenses/by-sa/4.0/. "
    "Auto-imported; review before promotion."
)


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    return s


def _api_get(session: requests.Session, params: dict[str, Any], *, max_retries: int = 5) -> dict[str, Any] | None:
    """GET the MediaWiki API with retry/backoff. Returns None (and prints a
    warning to stderr) if every attempt fails — callers must handle that by
    skipping the affected entry/page rather than crashing the whole run.

    429 responses get dedicated handling: honour Retry-After if present,
    otherwise exponential backoff (5s, 10s, 20s, 40s...). Despite Wiktionary's
    documented "200 req/s for anonymous users", live testing showed 429s
    arriving well under that — the real, enforced limit is much stricter
    (and/or shared-IP/gateway-level), so this treats the documented figure
    as unreliable and backs off conservatively instead of trusting it."""
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = session.get(BASE_URL, params=params, timeout=15)
            if resp.status_code == 429:
                retry_after = resp.headers.get("Retry-After")
                wait = float(retry_after) if retry_after and retry_after.isdigit() else 5 * (2 ** attempt)
                if attempt < max_retries - 1:
                    print(f"  [429 rate limited, waiting {wait:.0f}s before retry "
                          f"{attempt + 2}/{max_retries}] ({params.get('action', '?')})", file=sys.stderr)
                    time.sleep(wait)
                    continue
                last_exc = requests.HTTPError("429 Too Many Requests (retries exhausted)")
                break
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                time.sleep(REQUEST_DELAY_S * 10 * (attempt + 1))
    print(f"WARNING: Wiktionary API request failed after {max_retries} attempts "
          f"({params.get('action', '?')}): {last_exc}", file=sys.stderr)
    return None


def fetch_category_members(session: requests.Session, category: str, limit: int | None) -> Iterator[str]:
    """Page through Category:{category} main-namespace members, yielding page titles."""
    cmcontinue: str | None = None
    yielded = 0
    while True:
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": f"Category:{category}",
            "cmlimit": 500,
            "cmnamespace": 0,
            "format": "json",
        }
        if cmcontinue:
            params["cmcontinue"] = cmcontinue
        time.sleep(REQUEST_DELAY_S)
        data = _api_get(session, params)
        if data is None:
            return
        members = data.get("query", {}).get("categorymembers", [])
        for m in members:
            title = m.get("title")
            if not title:
                continue
            yield title
            yielded += 1
            if limit is not None and yielded >= limit:
                return
        cmcontinue = data.get("continue", {}).get("cmcontinue")
        if not cmcontinue:
            return


DEFINITION_BATCH_SIZE = 50  # MediaWiki allows up to 50 titles per query request


def _extract_definition(wikitext: str, lang_name: str) -> str:
    """Parse wikitext and return the first gloss line for lang_name's section."""
    if not wikitext:
        return TODO_EXPLANATION
    lang_marker = f"=={lang_name}=="
    start = wikitext.find(lang_marker)
    if start == -1:
        return TODO_EXPLANATION
    # Must match exactly 2 leading/trailing '=' to avoid matching level-3+ headings.
    next_match = re.search(r"\n==[^=\n][^\n]*==\n", wikitext[start + len(lang_marker):])
    section = (
        wikitext[start: start + len(lang_marker) + next_match.start()]
        if next_match else wikitext[start:]
    )
    for line in section.splitlines():
        line = line.strip()
        if line.startswith("# ") and not line.startswith("#:"):
            gloss = _strip_wikitext_markup(line[2:].strip())
            if gloss:
                return gloss[:300]
    return TODO_EXPLANATION


def fetch_definitions_batch(
    session: requests.Session, titles: list[str], lang_name: str
) -> dict[str, str]:
    """Fetch definitions for up to DEFINITION_BATCH_SIZE titles in one API call.
    Returns a dict mapping title → explanation; missing/failed entries get TODO_EXPLANATION."""
    time.sleep(REQUEST_DELAY_S)
    data = _api_get(session, {
        "action": "query",
        "titles": "|".join(titles),
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
        "format": "json",
    })
    result: dict[str, str] = {}
    if data is not None:
        for page in ((data.get("query") or {}).get("pages") or {}).values():
            title = page.get("title", "")
            revisions = page.get("revisions") or []
            if revisions:
                slots = revisions[0].get("slots") or {}
                wikitext = (slots.get("main") or {}).get("*", "") or revisions[0].get("*", "")
                result[title] = _extract_definition(wikitext, lang_name)
    for t in titles:
        result.setdefault(t, TODO_EXPLANATION)
    return result


def _strip_wikitext_markup(text: str) -> str:
    text = re.sub(r"\{\{[^}]*\}\}", "", text)          # templates
    text = re.sub(r"\[\[([^|\]]*\|)?([^\]]*)\]\]", r"\2", text)  # [[a|b]] -> b, [[a]] -> a
    text = re.sub(r"'{2,}", "", text)                    # ''italic''/'''bold'''
    return text.strip()


def load_seed_canonical_refs(seed_path: Path, language: str) -> set[str]:
    """Casefolded canonical_reference set for *language* from the seed YAML, used
    to skip Wiktionary entries that already exist (dedup is title-based: any
    Wiktionary page title matching an existing seed entry's casefolded
    canonical_reference is skipped)."""
    refs: set[str] = set()
    if not seed_path.exists():
        return refs
    if yaml is None:
        print("WARNING: PyYAML not installed — cannot deduplicate against seed.", file=sys.stderr)
        return refs
    with seed_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or []
    for entry in data:
        if isinstance(entry, dict) and entry.get("language") == language and entry.get("canonical_reference"):
            refs.add(str(entry["canonical_reference"]).casefold())
    return refs


def build_row(title: str, language: str, explanation: str) -> dict[str, str]:
    row = {field: "" for field in CSV_FIELDS}
    row.update({
        "language":            language,
        "surface_pattern":     title,
        "canonical_reference": title,
        "reference_type":      "cultural_reference",
        "source_work":         "Wiktionary",
        "source_author":       "Wiktionary contributors",
        "source_url":          f"https://en.wiktionary.org/wiki/{quote(title.replace(' ', '_'))}",
        "source_license":      "CC-BY-SA-4.0",
        "source_dataset":      f"{language}_wiktionary_idioms",
        "learner_level":       "B1",
        "register":            "common",
        "confidence":          "0.70",
        "short_explanation":   explanation,
        "notes":               "Auto-imported from Wiktionary. Verify explanation and surface_patterns before promotion.",
    })
    return row


def run(
    language: str, output: Path, seed_path: Path | None,
    fetch_definitions: bool, include_proverbs: bool, limit: int | None,
) -> int:
    if language not in WIKTIONARY_LANG_NAMES:
        print(
            f"ERROR: unknown --language '{language}'. Known codes: "
            f"{', '.join(sorted(WIKTIONARY_LANG_NAMES))}",
            file=sys.stderr,
        )
        return 1

    lang_name = WIKTIONARY_LANG_NAMES[language]
    existing = load_seed_canonical_refs(seed_path, language) if seed_path else set()
    session = _session()

    categories = [lang_name + " idioms"]
    if include_proverbs:
        proverb_cat = WIKTIONARY_PROVERB_NAMES.get(language)
        if proverb_cat:
            categories.append(proverb_cat)
        else:
            print(f"WARNING: --include-proverbs requested but no confirmed proverb "
                  f"category for '{language}' — skipping proverbs.", file=sys.stderr)

    seen_titles: set[str] = set()
    valid_titles: list[str] = []
    for category in categories:
        print(f"Fetching Category:{category} ...", file=sys.stderr)
        for title in fetch_category_members(session, category, limit):
            if title in seen_titles:
                continue
            seen_titles.add(title)
            if title.casefold() in existing:
                continue
            valid_titles.append(title)
            if limit is not None and len(valid_titles) >= limit:
                break
        if limit is not None and len(valid_titles) >= limit:
            break

    definitions: dict[str, str] = {}
    if fetch_definitions and valid_titles:
        total = (len(valid_titles) + DEFINITION_BATCH_SIZE - 1) // DEFINITION_BATCH_SIZE
        for i in range(0, len(valid_titles), DEFINITION_BATCH_SIZE):
            batch = valid_titles[i:i + DEFINITION_BATCH_SIZE]
            batch_num = i // DEFINITION_BATCH_SIZE + 1
            print(f"  Fetching definitions batch {batch_num}/{total} ({len(batch)} titles)...", file=sys.stderr)
            definitions.update(fetch_definitions_batch(session, batch, lang_name))

    rows = [
        build_row(title, language, definitions.get(title, TODO_EXPLANATION) if fetch_definitions else TODO_EXPLANATION)
        for title in valid_titles
    ]

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as f:
        f.write(LICENSE_COMMENT + "\n")
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)

    print(f"Wrote {len(rows)} rows to {output}", file=sys.stderr)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--language", required=True, help="BCP-47 code (e.g. en, es, fr)")
    ap.add_argument("--output", required=True, type=Path, help="CSV output path")
    ap.add_argument("--seed", type=Path, default=DEFAULT_SEED,
                     help=f"Seed YAML to deduplicate against (default: {DEFAULT_SEED})")
    ap.add_argument("--fetch-definitions", action="store_true",
                     help="Fetch one-line definitions from Wiktionary (slow, optional, one extra API call per entry)")
    ap.add_argument("--include-proverbs", action="store_true",
                     help="Also fetch from the language's proverbs category, if confirmed to exist")
    ap.add_argument("--limit", type=int, default=None, help="Maximum entries to fetch (default: no limit)")
    args = ap.parse_args()

    return run(
        language=args.language, output=args.output, seed_path=args.seed,
        fetch_definitions=args.fetch_definitions, include_proverbs=args.include_proverbs,
        limit=args.limit,
    )


if __name__ == "__main__":
    sys.exit(main())
