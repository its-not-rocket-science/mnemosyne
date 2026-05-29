#!/usr/bin/env python3
"""
ingest_kaikki_la_verb_morph.py — build Latin verb morphological SQLite index
from the kaikki.org Latin Wiktionary dump.

Reads:
  data/lang_capture/raw/kaikki_la.jsonl.gz
  data/lexicons/la_lemmas.json   (filter: only verbs with known lemmas)

Writes:
  data/lexicons/la_verb_morph.db  (SQLite3; form → morph features)

Schema
──────
  CREATE TABLE verb_morph (
      form     TEXT PRIMARY KEY,  -- normalised Latin form (macrons stripped)
      lemma    TEXT NOT NULL,
      tense    TEXT,
      mood     TEXT,
      voice    TEXT,
      person   TEXT,
      number   TEXT,
      verbform TEXT
  )

Coverage
────────
  Verb forms only.  All finite + non-finite forms from kaikki paradigm tables
  for verb lemmas that appear in la_lemmas.json (~5 500 lemmas).
  Expected: ~540 000 unique annotated forms, ~30 MB database.

  Noun/adj morphology is handled by la_morph.json (JSON, loaded at startup).
  Verbs are too numerous for startup-load JSON, hence SQLite with per-token
  indexed lookup.

Source
──────
  kaikki_la.jsonl.gz — CC BY-SA 3.0 / GFDL, kaikki.org / Wiktionary.

Usage
──────
  python -m scripts.ingest_kaikki_la_verb_morph
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

_MACRON_TABLE = str.maketrans("āēīōūĀĒĪŌŪ", "aeiouAEIOU")


def _normalize(token: str) -> str:
    nfd = unicodedata.normalize("NFD", token)
    stripped = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    return stripped.translate(_MACRON_TABLE).casefold()


_SKIP_TAGS: frozenset[str] = frozenset({
    "table-tags", "inflection-template", "canonical",
    "error-unrecognized-form", "error", "multiword-construction",
})

_TENSE_MAP: dict[str, str] = {
    "present": "present", "imperfect": "imperfect", "future": "future",
    "perfect": "perfect", "pluperfect": "pluperfect",
    "future-perfect": "future_perfect", "aorist": "aorist",
}
_MOOD_MAP: dict[str, str] = {
    "indicative": "indicative", "subjunctive": "subjunctive",
    "imperative": "imperative", "optative": "optative",
}
_VOICE_MAP: dict[str, str] = {
    "active": "active", "passive": "passive", "middle": "middle",
}
_PERSON_MAP: dict[str, str] = {
    "first-person": "first", "second-person": "second", "third-person": "third",
}
_NUMBER_MAP: dict[str, str] = {
    "singular": "singular", "plural": "plural",
}
_VERBFORM_MAP: dict[str, str] = {
    "infinitive": "infinitive", "participle": "participle",
    "gerund": "gerund", "gerundive": "gerundive", "supine": "supine",
}


def _extract_verb_feats(tags: list[str]) -> dict[str, str] | None:
    tag_set = set(tags)
    if tag_set & _SKIP_TAGS:
        return None

    feats: dict[str, str] = {}
    for tag in tags:
        if tag in _TENSE_MAP:    feats["tense"]    = _TENSE_MAP[tag]
        if tag in _MOOD_MAP:     feats["mood"]      = _MOOD_MAP[tag]
        if tag in _VOICE_MAP:    feats["voice"]     = _VOICE_MAP[tag]
        if tag in _PERSON_MAP:   feats["person"]    = _PERSON_MAP[tag]
        if tag in _NUMBER_MAP:   feats["number"]    = _NUMBER_MAP[tag]
        if tag in _VERBFORM_MAP: feats["verbform"]  = _VERBFORM_MAP[tag]

    if not feats:
        return None

    # Finite forms need at least one of tense/mood to be useful.
    if "verbform" not in feats and "tense" not in feats and "mood" not in feats:
        return None

    # Assign verbform=finite when mood is set but no explicit verbform tag.
    if "mood" in feats and "verbform" not in feats:
        feats["verbform"] = "finite"

    return feats


def build_db(kaikki_path: Path, lemma_set: set[str], db_path: Path) -> int:
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
    n_rows = 0

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
            if not lemma_key or lemma_key not in lemma_set:
                continue

            forms_src = [
                fm for fm in obj.get("forms", [])
                if fm.get("source") == "conjugation"
            ]
            if not forms_src:
                continue

            n_lemmas += 1

            for fm in forms_src:
                form_str = fm.get("form", "").strip()
                if not form_str or "-" in form_str or "/" in form_str:
                    continue

                form_key = _normalize(form_str)
                if not form_key:
                    continue

                feats = _extract_verb_feats(fm.get("tags", []))
                if feats is None:
                    continue

                batch.append((
                    form_key,
                    lemma_key,
                    feats.get("tense"),
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
    kaikki_path = RAW / "kaikki_la.jsonl.gz"
    db_path     = OUT / "la_verb_morph.db"

    if not kaikki_path.exists():
        log.error("Missing: %s", kaikki_path)
        sys.exit(1)

    log.info("Loading la_lemmas.json for verb lemma filter …")
    with open(OUT / "la_lemmas.json", encoding="utf-8") as f:
        la_data = json.load(f)

    verb_lemmas: set[str] = {
        k for k, v in la_data["entries"].items() if v.get("pos") == "verb"
    }
    log.info("  %d verb lemmas in la_lemmas.json", len(verb_lemmas))

    log.info("Ingesting kaikki verb conjugation paradigms …")
    build_db(kaikki_path, verb_lemmas, db_path)
    log.info("Done.")


if __name__ == "__main__":
    main()
