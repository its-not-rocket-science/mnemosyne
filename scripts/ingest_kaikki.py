#!/usr/bin/env python3
"""
ingest_kaikki.py — build Latin and Greek lexicon JSON files from kaikki dumps.

Input:  data/lang_capture/raw/kaikki_la.jsonl.gz
        data/lang_capture/raw/kaikki_grc.jsonl.gz
Output: data/lexicons/la_lemmas.json
        data/lexicons/la_inflections.json
        data/lexicons/grc_lemmas.json
        data/lexicons/grc_inflections.json

Kaikki (https://kaikki.org) is a machine-readable extraction of Wiktionary.
License: CC BY-SA 4.0 (same as Wiktionary).

Usage:
    python -m scripts.ingest_kaikki [--lang la|grc|all]
"""
from __future__ import annotations

import argparse
import gzip
import json
import logging
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
RAW  = ROOT / "data" / "lang_capture" / "raw"
OUT  = ROOT / "data" / "lexicons"

sys.path.insert(0, str(ROOT))
from backend.core.classical_normalize import normalize_latin, normalize_greek  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
log = logging.getLogger(__name__)

# ── POS values to keep (skip name/suffix/prefix/character/phrase) ─────────────
_KEEP_POS = frozenset({
    "verb", "noun", "adj", "adv", "pron", "conj",
    "prep", "intj", "num", "particle", "det",
})

# ── Head-template names that mark real lemma entries ─────────────────────────
# Entries whose head_template name ends in "-form" or "-participle" are
# inflected-form entries with form-of glosses, not headwords.
_FORM_SUFFIX = re.compile(r"-(form|participle|decl)$")

# Gloss patterns that still indicate form-of even after the name filter.
_GLOSS_FORM_OF = re.compile(
    r"(^|\s)(form of|inflection of|alternative form of|"
    r"genitive of|plural of|singular of|dative of|accusative of|"
    r"vocative of|ablative of|nominative of|"
    r"first-person|second-person|third-person|"
    r"present active|present passive|"
    r"perfect active|perfect passive)\b",
    re.I,
)

_WIKI_LINK = re.compile(r"\[\[([^\]|]+)\|([^\]]+)\]\]|\[\[([^\]]+)\]\]")


def _clean_gloss(gloss: str) -> str:
    def _sub(m: re.Match) -> str:
        return m.group(2) if m.group(2) else m.group(3)
    return _WIKI_LINK.sub(_sub, gloss).strip()


def _is_lemma_entry(d: dict) -> bool:
    """True if entry is a headword (not an inflected form)."""
    hts = d.get("head_templates", [])
    if hts:
        name = hts[0].get("name", "")
        if _FORM_SUFFIX.search(name):
            return False
    # Secondary check: all glosses are form-of
    senses = d.get("senses", [])
    for s in senses:
        gs = s.get("glosses", [])
        if gs and not _GLOSS_FORM_OF.search(gs[0]):
            return True
    return False


def _first_gloss(senses: list) -> str | None:
    for s in senses:
        gs = s.get("glosses", [])
        if gs and not _GLOSS_FORM_OF.search(gs[0]):
            return _clean_gloss(gs[0])
    return None


def _citation_and_grammar(d: dict) -> tuple[str, str]:
    hts = d.get("head_templates", [])
    if not hts:
        return d.get("word", ""), ""
    expansion = hts[0].get("expansion", "")
    if not expansion:
        return d.get("word", ""), ""
    # Strip romanization bullet: "amor • (amor)"
    expansion = re.sub(r"\s*•\s*\([^)]+\)", "", expansion)
    citation = expansion.split("\n")[0].strip()
    # Grammar note = everything after first semicolon
    grammar = expansion.split(";", 1)[1].strip()[:200] if ";" in expansion else ""
    return citation, grammar


def process(gz_path: Path, lang: str, normalize) -> tuple[dict, dict]:
    log.info("Processing %s …", gz_path.name)
    lemmas: dict[str, dict] = {}
    inflections: dict[str, str] = {}
    skipped_pos = 0
    skipped_form = 0
    n = 0

    with gzip.open(gz_path, "rt", encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            pos = d.get("pos", "")
            if pos not in _KEEP_POS:
                skipped_pos += 1
                continue
            if not _is_lemma_entry(d):
                skipped_form += 1
                continue
            gloss = _first_gloss(d.get("senses", []))
            if not gloss:
                skipped_form += 1
                continue

            word = d.get("word", "").strip()
            key = normalize(word)
            if not key:
                continue

            citation, grammar = _citation_and_grammar(d)

            # First occurrence wins (most common / best-known sense)
            if key not in lemmas:
                lemmas[key] = {
                    "citation": citation or word,
                    "gloss": gloss,
                    "pos": pos,
                    "grammar_note": grammar,
                    "source": "kaikki",
                }
                n += 1

            # Inflection table: map every form → this lemma key
            for form_entry in d.get("forms", []):
                form = form_entry.get("form", "").strip()
                tags = form_entry.get("tags", [])
                # Skip meta rows and romanizations
                if not form or any(t in ("table-tags", "inflection-template", "class") for t in tags):
                    continue
                if form_entry.get("roman"):
                    # Skip if entry is itself a romanization
                    pass
                fkey = normalize(form)
                if fkey and fkey != key and fkey not in inflections:
                    inflections[fkey] = key

    log.info("  %d lemmas, %d inflection mappings (skipped %d form-of, %d wrong-pos)",
             len(lemmas), len(inflections), skipped_form, skipped_pos)
    return lemmas, inflections


def write(path: Path, data: dict, description: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log.info("Wrote %s (%d entries, %.1f KB)", path.name, len(data), path.stat().st_size / 1024)


def ingest_latin() -> None:
    gz = RAW / "kaikki_la.jsonl.gz"
    lemmas, inflections = process(gz, "la", normalize_latin)
    write(OUT / "la_lemmas.json", {"version": "1", "language": "la", "entries": lemmas}, "Latin lemmas")
    write(OUT / "la_inflections.json", inflections, "Latin inflections")


def ingest_greek() -> None:
    gz = RAW / "kaikki_grc.jsonl.gz"
    lemmas, inflections = process(gz, "grc", normalize_greek)
    write(OUT / "grc_lemmas.json", {"version": "1", "language": "grc", "entries": lemmas}, "Greek lemmas")
    write(OUT / "grc_inflections.json", inflections, "Greek inflections")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lang", choices=["la", "grc", "all"], default="all")
    args = ap.parse_args()
    if args.lang in ("la", "all"):
        ingest_latin()
    if args.lang in ("grc", "all"):
        ingest_greek()


if __name__ == "__main__":
    main()
