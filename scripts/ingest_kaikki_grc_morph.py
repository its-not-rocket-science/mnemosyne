#!/usr/bin/env python3
"""
ingest_kaikki_grc_morph.py — expand grc_morph.json with noun/adjective paradigms
from the kaikki.org Ancient Greek Wiktionary dump.

Reads:
  data/lang_capture/raw/kaikki_grc.jsonl.gz
  data/lexicons/grc_morph.json   (existing PROIEL+MorphGNT data; takes priority)

Writes:
  data/lexicons/grc_morph.json   (merged; existing data wins on conflict)

Notes
──────
  Greek kaikki noun entries include the definite article in their form strings
  (e.g., "ἡ κύων" for nominative singular).  This script extracts the final
  word token, discarding the article prefix.

  Verb coverage is handled by grc_verb_morph.db (see ingest_kaikki_grc_verb_morph.py).

Coverage
────────
  ~7 400 noun/adj/pron/num lemmas with paradigm tables, ~88 000 unique
  normalised forms expected.  grc_morph.json grows from ~27 000 → ~100 000
  entries (~10 MB).

Source
──────
  kaikki_grc.jsonl.gz — CC BY-SA 3.0 / GFDL, kaikki.org / Wiktionary.

Usage
──────
  python -m scripts.ingest_kaikki_grc_morph
"""
from __future__ import annotations

import gzip
import json
import logging
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).parents[1]
RAW  = ROOT / "data" / "lang_capture" / "raw"
OUT  = ROOT / "data" / "lexicons"

sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-8s  %(message)s")
log = logging.getLogger(__name__)


def _normalize(token: str) -> str:
    nfd = unicodedata.normalize("NFD", token)
    stripped = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", stripped).lower()


_SKIP_TAGS: frozenset[str] = frozenset({
    "table-tags", "inflection-template", "canonical",
    "error-unrecognized-form", "error", "multiword-construction", "class",
})

_TAG_MAP: dict[str, tuple[str, str]] = {
    # Case
    "nominative": ("case", "nominative"),
    "genitive":   ("case", "genitive"),
    "dative":     ("case", "dative"),
    "accusative": ("case", "accusative"),
    "vocative":   ("case", "vocative"),
    # Number
    "singular":   ("number", "singular"),
    "plural":     ("number", "plural"),
    "dual":       ("number", "dual"),
    # Gender
    "masculine":  ("gender", "masculine"),
    "feminine":   ("gender", "feminine"),
    "neuter":     ("gender", "neuter"),
    # Degree (adjectives)
    "positive":     ("degree", "positive"),
    "comparative":  ("degree", "comparative"),
    "superlative":  ("degree", "superlative"),
}

_POS_MAP: dict[str, str] = {
    "noun": "noun", "name": "noun",
    "adj":  "adj",
    "pron": "pron",
    "num":  "num",
}

_RELEVANT_POS = frozenset({"noun", "adj", "name", "pron", "num"})


def _extract_nominal_feats(tags: list[str]) -> dict[str, str] | None:
    tag_set = set(tags)
    if tag_set & _SKIP_TAGS:
        return None

    feats: dict[str, str] = {}
    for tag in tags:
        mapping = _TAG_MAP.get(tag)
        if mapping:
            field, val = mapping
            feats[field] = val

    if "case" not in feats and "number" not in feats:
        return None

    return feats


def ingest_kaikki_nominal(path: Path) -> dict[str, dict]:
    entries: dict[str, dict] = {}
    n_lemmas = 0
    n_forms  = 0

    with gzip.open(path, "rt", encoding="utf-8") as f:
        for raw_line in f:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                obj = json.loads(raw_line)
            except json.JSONDecodeError:
                continue

            if obj.get("pos") not in _RELEVANT_POS:
                continue

            word = obj.get("word", "")
            lemma_key = _normalize(word) if word else ""
            if not lemma_key:
                continue

            pos = _POS_MAP.get(obj.get("pos", ""), "noun")
            n_lemmas += 1

            for fm in obj.get("forms", []):
                if fm.get("source") not in ("declension", "inflection"):
                    continue

                form_str = fm.get("form", "").strip()
                if not form_str:
                    continue

                # Greek noun forms often include definite article prefix.
                # Take the last space-separated word to strip it.
                last_word = form_str.split()[-1]
                if "-" in last_word or "/" in last_word:
                    continue

                form_key = _normalize(last_word)
                if not form_key or form_key in entries:
                    continue  # first occurrence wins

                feats = _extract_nominal_feats(fm.get("tags", []))
                if feats is None:
                    continue

                entry: dict[str, str] = {"lemma": lemma_key, "pos": pos}
                entry.update(feats)
                entries[form_key] = entry
                n_forms += 1

    log.info(
        "kaikki nominal: %d lemmas processed, %d unique annotated forms extracted",
        n_lemmas, n_forms,
    )
    return entries


def main() -> None:
    kaikki_path = RAW / "kaikki_grc.jsonl.gz"
    morph_path  = OUT / "grc_morph.json"

    if not kaikki_path.exists():
        log.error("Missing: %s", kaikki_path)
        sys.exit(1)

    existing: dict[str, dict] = {}
    if morph_path.exists():
        log.info("Loading existing grc_morph.json …")
        existing = json.loads(morph_path.read_text("utf-8"))["entries"]
        log.info("  %d existing entries (will take priority)", len(existing))

    log.info("Ingesting kaikki Greek noun/adj paradigms …")
    kaikki_entries = ingest_kaikki_nominal(kaikki_path)

    merged: dict[str, dict] = dict(kaikki_entries)
    merged.update(existing)  # existing wins on conflict

    log.info(
        "Merged: %d kaikki + %d existing → %d total",
        len(kaikki_entries), len(existing), len(merged),
    )

    sources = [
        "grc_proiel-ud-dev.conllu (CC BY-NC-SA, PROIEL, Universal Dependencies)",
        "morphgnt_sblgnt.txt (CC BY-SA 3.0, MorphGNT; SBL GNT non-commercial)",
        "kaikki_grc.jsonl.gz (CC BY-SA 3.0 / GFDL, kaikki.org / Wiktionary — noun/adj paradigms)",
    ]

    OUT.mkdir(parents=True, exist_ok=True)
    data = {
        "version":  "2",
        "language": "grc",
        "sources":  sources,
        "entries":  merged,
    }
    morph_path.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    size_kb = morph_path.stat().st_size / 1024
    log.info(
        "Wrote %s: %d entries, %.1f KB (%.1f MB)",
        morph_path.name, len(merged), size_kb, size_kb / 1024,
    )


if __name__ == "__main__":
    main()
