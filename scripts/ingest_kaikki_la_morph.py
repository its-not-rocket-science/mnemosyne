#!/usr/bin/env python3
"""
ingest_kaikki_la_morph.py — expand la_morph.json with noun/adjective paradigms
from the kaikki.org Latin Wiktionary dump.

Reads:
  data/lang_capture/raw/kaikki_la.jsonl.gz
  data/lexicons/la_morph.json   (existing UD-treebank data; takes priority)

Writes:
  data/lexicons/la_morph.json   (merged; UD data wins on conflict)

Coverage
────────
  Noun and adjective forms only.  Verb coverage is handled by the existing
  suffix-rule fallback in latin.py plus the ITTB UD data already in la_morph.json.

  Expected output: ~220 000 additional annotated noun/adj forms, growing
  la_morph.json from ~3 400 → ~220 000 entries (~22 MB).

Source
──────
  kaikki_la.jsonl.gz — Wiktionary Latin data harvested by kaikki.org
  (CC BY-SA 3.0 / GFDL, same terms as Wiktionary).  The paradigm tables
  embedded in the forms[] arrays are auto-generated from Wiktionary templates.

Usage
──────
  python -m scripts.ingest_kaikki_la_morph

License
──────
  kaikki.org data is derived from Wiktionary (CC BY-SA 3.0 / GFDL).
  See https://kaikki.org/ for distribution terms.
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

# ── Normalization (mirrors backend/core/classical_normalize.py) ───────────────

_MACRON_TABLE = str.maketrans("āēīōūĀĒĪŌŪ", "aeiouAEIOU")


def _normalize(token: str) -> str:
    nfd = unicodedata.normalize("NFD", token)
    stripped = "".join(ch for ch in nfd if unicodedata.category(ch) != "Mn")
    return stripped.translate(_MACRON_TABLE).casefold()


# ── Tag → morph field mapping ─────────────────────────────────────────────────

# Tags that mark table structure, not form features — skip any form that carries one.
_SKIP_TAGS: frozenset[str] = frozenset({
    "table-tags", "inflection-template", "canonical",
    "error-unrecognized-form", "error", "dummy",
    "multiword-construction",
})

# Direct tag→(field, value) mappings for kaikki tag strings.
_TAG_MAP: dict[str, tuple[str, str]] = {
    # Case
    "nominative": ("case", "nominative"),
    "genitive":   ("case", "genitive"),
    "dative":     ("case", "dative"),
    "accusative": ("case", "accusative"),
    "vocative":   ("case", "vocative"),
    "ablative":   ("case", "ablative"),
    "locative":   ("case", "locative"),
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

# POS tags that appear in kaikki forms[] tags — map to our pos strings.
_POS_TAGS: dict[str, str] = {
    "noun": "noun", "name": "noun",
    "adj":  "adj",  "adjective": "adj",
    "pron": "pron", "pronoun": "pron",
    "num":  "num",
}

_RELEVANT_POS = frozenset({"noun", "adj", "name", "pron", "num"})


def _extract_nominal_feats(tags: list[str]) -> dict[str, str] | None:
    """
    Map a kaikki tags list to a morph features dict.
    Returns None if the form is structural noise (skip-tag present) or has no
    grammatical features we care about.
    """
    tag_set = set(tags)
    if tag_set & _SKIP_TAGS:
        return None

    feats: dict[str, str] = {}
    for tag in tags:
        mapping = _TAG_MAP.get(tag)
        if mapping:
            field, val = mapping
            feats[field] = val

    # Need at least case or number to be useful for nominal morphology.
    if "case" not in feats and "number" not in feats:
        return None

    return feats


def ingest_kaikki_nominal(path: Path) -> dict[str, dict]:
    """
    Parse kaikki_la.jsonl.gz and extract noun/adj paradigm forms.
    Returns {normalised_form: morph_entry} with first-occurrence semantics
    (first Wiktionary paradigm entry wins for any normalised form).
    """
    entries: dict[str, dict] = {}
    n_lemmas = 0
    n_forms   = 0

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

            pos = _POS_TAGS.get(obj.get("pos", ""), "noun")
            n_lemmas += 1

            for fm in obj.get("forms", []):
                if fm.get("source") not in ("declension", "inflection"):
                    continue

                form_str = fm.get("form", "").strip()
                # Skip blanks, hyphens (partial forms), slashes (alternates)
                if not form_str or "-" in form_str or "/" in form_str:
                    continue

                form_key = _normalize(form_str)
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
    kaikki_path = RAW / "kaikki_la.jsonl.gz"
    morph_path  = OUT / "la_morph.json"

    if not kaikki_path.exists():
        log.error("Missing: %s", kaikki_path)
        sys.exit(1)

    # Load existing UD data; it takes priority over kaikki.
    existing: dict[str, dict] = {}
    if morph_path.exists():
        log.info("Loading existing la_morph.json …")
        existing = json.loads(morph_path.read_text("utf-8"))["entries"]
        log.info("  %d existing UD entries (will take priority)", len(existing))

    log.info("Ingesting kaikki noun/adj paradigms …")
    kaikki_entries = ingest_kaikki_nominal(kaikki_path)

    # Merge: existing (UD) wins on conflict.
    merged: dict[str, dict] = dict(kaikki_entries)
    merged.update(existing)  # UD overwrites kaikki where keys overlap

    log.info(
        "Merged: %d kaikki + %d UD → %d total unique forms",
        len(kaikki_entries), len(existing), len(merged),
    )

    sources = [
        "la_ittb-ud-dev.conllu (CC BY-NC-SA 3.0, Index Thomisticus, Universal Dependencies)",
        "kaikki_la.jsonl.gz (CC BY-SA 3.0 / GFDL, kaikki.org / Wiktionary — noun/adj paradigms)",
    ]

    OUT.mkdir(parents=True, exist_ok=True)
    data = {
        "version":  "2",
        "language": "la",
        "sources":  sources,
        "entries":  merged,
    }
    morph_path.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    size_kb = morph_path.stat().st_size / 1024
    log.info("Wrote %s: %d entries, %.1f KB (%.1f MB)", morph_path.name, len(merged), size_kb, size_kb / 1024)


if __name__ == "__main__":
    main()
