#!/usr/bin/env python3
"""
ingest_kaikki_grc_verb_morph.py — build Greek verb morphological SQLite index
from the kaikki.org Ancient Greek Wiktionary dump.

Reads:
  data/lang_capture/raw/kaikki_grc.jsonl.gz

Writes:
  data/lexicons/grc_verb_morph.db  (SQLite3; form → morph features)

Schema
──────
  CREATE TABLE verb_morph (
      form     TEXT PRIMARY KEY,  -- normalised Greek form (diacritics stripped)
      lemma    TEXT NOT NULL,
      tense    TEXT,
      mood     TEXT,
      voice    TEXT,
      person   TEXT,
      number   TEXT,
      verbform TEXT
  )

Tense handling
──────────────
  Unlike Latin kaikki data, Greek kaikki verb paradigm tables do NOT include
  an explicit tense tag on each form.  Instead, the paradigm is divided into
  tense sections marked by a form entry whose tags contain "table-tags".  The
  form text of that entry names the tense (e.g., "present", "aorist", "perfect").
  This script tracks the current tense section as it processes each lemma's
  conjugation table, assigning that tense to all subsequent forms until the
  next section marker.

Coverage
────────
  ~1 750 verb lemmas with paradigm tables from kaikki, ~408 000 unique
  annotated forms.  Expected database: ~25–40 MB.

Source
──────
  kaikki_grc.jsonl.gz — CC BY-SA 3.0 / GFDL, kaikki.org / Wiktionary.

Usage
──────
  python -m scripts.ingest_kaikki_grc_verb_morph
"""
from __future__ import annotations

import gzip
import json
import logging
import sqlite3
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
    """Strip polytonic diacritics and return lowercase NFC for Greek lexicon lookup."""
    nfd = unicodedata.normalize("NFD", token)
    stripped = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", stripped).lower()


# ── Section name → tense ──────────────────────────────────────────────────────
# Tense sections appear as table-tags entries in the conjugation table.
# Matched longest-first to avoid "perfect" matching "pluperfect".

def _section_to_tense(section_name: str) -> str | None:
    """Map a kaikki table-tags section name to a tense string, or None.

    Order matters: check longer/more-specific strings before substrings.
    "imperfect" contains "perfect" so must be checked first.
    "future perfect" contains both "future" and "perfect" so must be first.
    "pluperfect" contains "perfect" so must be checked before "perfect".
    """
    sl = section_name.lower()
    if "pluperfect" in sl:      return "pluperfect"
    if "future perfect" in sl:  return "future_perfect"
    if "imperfect" in sl:       return "imperfect"   # before "perfect"
    if "perfect" in sl:         return "perfect"
    if "aorist" in sl:          return "aorist"
    if "future" in sl:          return "future"
    if "present" in sl:         return "present"
    return None


# ── Tag → morph field mapping ─────────────────────────────────────────────────

_SKIP_TAGS: frozenset[str] = frozenset({
    "table-tags", "inflection-template", "canonical",
    "error-unrecognized-form", "error", "multiword-construction",
})

_MOOD_MAP: dict[str, str] = {
    "indicative":  "indicative",
    "subjunctive": "subjunctive",
    "imperative":  "imperative",
    "optative":    "optative",
    "infinitive":  "infinitive",
    "participle":  "participle",
}
_VOICE_MAP: dict[str, str] = {
    "active":  "active",
    "passive": "passive",
    "middle":  "middle",
    "mediopassive": "middle",
}
_PERSON_MAP: dict[str, str] = {
    "first-person":  "first",
    "second-person": "second",
    "third-person":  "third",
}
_NUMBER_MAP: dict[str, str] = {
    "singular": "singular",
    "plural":   "plural",
    "dual":     "dual",
}


def _extract_feats(tags: list[str]) -> dict[str, str] | None:
    """Extract mood/voice/person/number from a kaikki form tags list."""
    tag_set = set(tags)
    if tag_set & _SKIP_TAGS:
        return None

    feats: dict[str, str] = {}
    for tag in tags:
        if tag in _MOOD_MAP:    feats["mood"]   = _MOOD_MAP[tag]
        if tag in _VOICE_MAP:   feats["voice"]  = _VOICE_MAP[tag]
        if tag in _PERSON_MAP:  feats["person"] = _PERSON_MAP[tag]
        if tag in _NUMBER_MAP:  feats["number"] = _NUMBER_MAP[tag]

    # Need at least mood to be useful (finite or non-finite).
    if "mood" not in feats:
        return None

    # Assign verbform from mood for non-finite forms.
    if feats.get("mood") == "infinitive":
        feats["verbform"] = "infinitive"
    elif feats.get("mood") == "participle":
        feats["verbform"] = "participle"
    else:
        feats["verbform"] = "finite"

    return feats


def build_db(kaikki_path: Path, db_path: Path) -> int:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    con = sqlite3.connect(str(db_path))
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE verb_morph (
            form     TEXT PRIMARY KEY,
            lemma    TEXT NOT NULL,
            tense    TEXT,
            mood     TEXT,
            voice    TEXT,
            person   TEXT,
            number   TEXT,
            verbform TEXT
        )
    """)
    cur.execute("CREATE INDEX idx_form ON verb_morph(form)")

    batch: list[tuple] = []
    BATCH_SIZE = 10_000
    n_lemmas = 0
    n_rows   = 0

    def flush() -> None:
        nonlocal n_rows
        cur.executemany(
            "INSERT OR IGNORE INTO verb_morph VALUES (?,?,?,?,?,?,?,?)",
            batch,
        )
        n_rows += len(batch)
        batch.clear()

    with gzip.open(kaikki_path, "rt", encoding="utf-8") as f:
        for raw_line in f:
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                obj = json.loads(raw_line)
            except json.JSONDecodeError:
                continue

            if obj.get("pos") != "verb":
                continue

            word = obj.get("word", "")
            lemma_key = _normalize(word) if word else ""
            if not lemma_key:
                continue

            forms_src = [
                fm for fm in obj.get("forms", [])
                if fm.get("source") == "conjugation"
            ]
            if not forms_src:
                continue

            n_lemmas += 1
            current_tense: str | None = None

            for fm in forms_src:
                tags = fm.get("tags", [])

                # Update tense context from section marker.
                if "table-tags" in tags:
                    t = _section_to_tense(fm.get("form", ""))
                    if t is not None:
                        current_tense = t
                    continue

                if set(tags) & _SKIP_TAGS:
                    continue

                form_str = fm.get("form", "").strip()
                # Skip blanks, structural markers, alternates.
                if not form_str or "-" in form_str or "/" in form_str:
                    continue

                form_key = _normalize(form_str)
                if not form_key or form_key in {r[0] for r in batch}:
                    continue

                feats = _extract_feats(tags)
                if feats is None:
                    continue

                batch.append((
                    form_key,
                    lemma_key,
                    current_tense,          # may be None if no section seen yet
                    feats.get("mood"),
                    feats.get("voice"),
                    feats.get("person"),
                    feats.get("number"),
                    feats.get("verbform"),
                ))
                if len(batch) >= BATCH_SIZE:
                    flush()

    if batch:
        flush()

    con.commit()
    con.close()

    log.info(
        "Built %s: %d verb lemmas, %d rows, %.1f MB",
        db_path.name, n_lemmas, n_rows, db_path.stat().st_size / 1024 / 1024,
    )
    return n_rows


def main() -> None:
    kaikki_path = RAW / "kaikki_grc.jsonl.gz"
    db_path     = OUT / "grc_verb_morph.db"

    if not kaikki_path.exists():
        log.error("Missing: %s", kaikki_path)
        sys.exit(1)

    log.info("Ingesting kaikki Greek verb conjugation paradigms …")
    build_db(kaikki_path, db_path)
    log.info("Done.")


if __name__ == "__main__":
    main()
