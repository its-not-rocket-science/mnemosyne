#!/usr/bin/env python3
"""
ingest_classical_morph.py — build morphological indices for Latin and Koine Greek.

Sources
────────
  Latin:      data/lang_capture/raw/la_ittb-ud-dev.conllu
              (Index Thomisticus Treebank dev split; Universal Dependencies)
  Greek:      data/lang_capture/raw/grc_proiel-ud-dev.conllu
              (PROIEL Ancient Greek dev split; Universal Dependencies)
              data/lang_capture/raw/morphgnt_sblgnt.txt
              (MorphGNT: morphologically annotated Greek NT, SBL Greek NT text)

Outputs
────────
  data/lexicons/la_morph.json
  data/lexicons/grc_morph.json

Schema per output
────────────────
  {
    "version": "1",
    "language": "la"|"grc",
    "source": ["la_ittb-ud-dev.conllu", "..."],
    "entries": {
      "<normalised_form>": {
        "lemma": "<normalised_lemma>",
        "pos":   "<upos_lower>",
        "case":  "nominative"|"genitive"|...,   // if present
        "number": "singular"|"plural"|...,
        "gender": "masculine"|"feminine"|"neuter",
        "tense":  "present"|"past"|"future"|...,
        "mood":   "indicative"|"subjunctive"|...,
        "voice":  "active"|"passive"|"middle"|...,
        "person": "first"|"second"|"third",
        "aspect": "imperfective"|"perfective"|...,
        "verbform": "finite"|"infinitive"|"participle"|...
      }
    }
  }

Usage
──────
  python -m scripts.ingest_classical_morph [--lang la|grc|all]

License notes
──────────────
  la_ittb-ud-dev.conllu — CC BY-NC-SA 3.0 (Index Thomisticus, E. Cecchini et al.)
                           Universal Dependencies project.
  grc_proiel-ud-dev.conllu — CC BY-NC-SA (PROIEL, Dag Haug et al.)
                              Universal Dependencies project.
  morphgnt_sblgnt.txt — CC BY-SA 3.0 (MorphGNT; James Tauber et al.;
                         SBL Greek New Testament © 2010 Society of Biblical Literature
                         and Logos Bible Software — non-commercial use).
"""
from __future__ import annotations

import argparse
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

# ── Universal Dependencies FEATS key normalisation ────────────────────────────
_UD_KEY_MAP: dict[str, str] = {
    "Case":     "case",
    "Number":   "number",
    "Gender":   "gender",
    "Tense":    "tense",
    "Mood":     "mood",
    "Voice":    "voice",
    "Person":   "person",
    "Aspect":   "aspect",
    "VerbForm": "verbform",
    "Degree":   "degree",
}

_UD_VAL_MAP: dict[str, str] = {
    # Case
    "Nom": "nominative", "Gen": "genitive", "Dat": "dative",
    "Acc": "accusative", "Voc": "vocative", "Abl": "ablative",
    "Loc": "locative",   "Ins": "instrumental",
    # Number
    "Sing": "singular", "Plur": "plural", "Dual": "dual",
    # Gender
    "Masc": "masculine", "Fem": "feminine", "Neut": "neuter",
    # Tense
    "Pres": "present", "Past": "past", "Fut": "future",
    "Imp":  "imperfect", "Pqp": "pluperfect",
    # Mood
    "Ind": "indicative", "Sub": "subjunctive", "Imp": "imperfect",
    "Opt": "optative",
    # Voice
    "Act": "active", "Pass": "passive", "Mid": "middle",
    # Person
    "1": "first", "2": "second", "3": "third",
    # Aspect
    "Imp": "imperfective", "Perf": "perfective",
    # VerbForm
    "Fin": "finite", "Inf": "infinitive", "Part": "participle",
    "Ger": "gerund", "Gdv": "gerundive",
    # Degree
    "Pos": "positive", "Cmp": "comparative", "Sup": "superlative",
    # Mood (imperative missing from above)
    "Imp": "imperfect",  # overloaded — context-dependent; tense wins
}

# Separate clean mapping to avoid the Imp ambiguity:
_CASE_VALS  = {"Nom": "nominative", "Gen": "genitive", "Dat": "dative",
               "Acc": "accusative", "Voc": "vocative", "Abl": "ablative",
               "Loc": "locative",   "Ins": "instrumental"}
_NUM_VALS   = {"Sing": "singular", "Plur": "plural", "Dual": "dual"}
_GEN_VALS   = {"Masc": "masculine", "Fem": "feminine", "Neut": "neuter"}
_TENSE_VALS = {"Pres": "present", "Past": "past", "Fut": "future",
               "Imp": "imperfect", "Pqp": "pluperfect"}
_MOOD_VALS  = {"Ind": "indicative", "Sub": "subjunctive", "Imp": "imperative",
               "Opt": "optative"}
_VOICE_VALS = {"Act": "active", "Pass": "passive", "Mid": "middle"}
_PERSON_VALS = {"1": "first", "2": "second", "3": "third"}
_ASPECT_VALS = {"Imp": "imperfective", "Perf": "perfective"}
_VERBFORM_VALS = {"Fin": "finite", "Inf": "infinitive", "Part": "participle",
                  "Ger": "gerund", "Gdv": "gerundive"}


def _parse_ud_feats(feats: str) -> dict[str, str]:
    """Parse a UD FEATS string like 'Case=Nom|Number=Sing|Gender=Masc'."""
    if feats == "_" or not feats:
        return {}
    result: dict[str, str] = {}
    for kv in feats.split("|"):
        if "=" not in kv:
            continue
        k, v = kv.split("=", 1)
        if k == "Case" and v in _CASE_VALS:
            result["case"] = _CASE_VALS[v]
        elif k == "Number" and v in _NUM_VALS:
            result["number"] = _NUM_VALS[v]
        elif k == "Gender" and v in _GEN_VALS:
            result["gender"] = _GEN_VALS[v]
        elif k == "Tense" and v in _TENSE_VALS:
            result["tense"] = _TENSE_VALS[v]
        elif k == "Mood" and v in _MOOD_VALS:
            result["mood"] = _MOOD_VALS[v]
        elif k == "Voice" and v in _VOICE_VALS:
            result["voice"] = _VOICE_VALS[v]
        elif k == "Person" and v in _PERSON_VALS:
            result["person"] = _PERSON_VALS[v]
        elif k == "Aspect" and v in _ASPECT_VALS:
            result["aspect"] = _ASPECT_VALS[v]
        elif k == "VerbForm" and v in _VERBFORM_VALS:
            result["verbform"] = _VERBFORM_VALS[v]
    return result


def ingest_conllu(path: Path, normalize) -> dict[str, dict]:
    """
    Parse a CoNLL-U file.  Returns {normalised_form: morph_entry}.
    First occurrence of each form wins (preserves the most common annotation).
    """
    entries: dict[str, dict] = {}
    n_tokens = 0

    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.rstrip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 6:
                continue
            tok_id = parts[0]
            if not tok_id.isdigit():
                continue  # skip multi-word / empty tokens
            form   = parts[1]
            lemma  = parts[2]
            upos   = parts[3].lower()
            feats  = parts[5]

            form_key  = normalize(form)
            lemma_key = normalize(lemma)
            if not form_key or not lemma_key:
                continue

            n_tokens += 1

            if form_key in entries:
                continue  # first occurrence wins

            feat_dict = _parse_ud_feats(feats)
            if not feat_dict and upos not in ("verb", "noun", "adj", "pron"):
                continue  # skip uninformative entries

            entry: dict[str, str] = {"lemma": lemma_key, "pos": upos}
            entry.update(feat_dict)
            entries[form_key] = entry

    log.info("  %s: %d tokens, %d unique annotated forms", path.name, n_tokens, len(entries))
    return entries


# ── MorphGNT decoder ─────────────────────────────────────────────────────────
# Format: book-chapter-verse POS morph word word_capped lemma lemma_capped
# morph is an 8-char code: [person][tense][voice][mood][case][number][gender][degree]
# Each position uses '-' for not-applicable.

_MORPHGNT_PERSON = {"-": None, "1": "first", "2": "second", "3": "third"}
_MORPHGNT_TENSE  = {"-": None, "P": "present", "I": "imperfect", "F": "future",
                    "A": "aorist", "X": "perfect", "Y": "pluperfect"}
_MORPHGNT_VOICE  = {"-": None, "A": "active", "M": "middle", "P": "passive",
                    "E": "middle", "D": "middle", "O": "passive", "N": "middle",
                    "Q": "passive"}
_MORPHGNT_MOOD   = {"-": None, "I": "indicative", "D": "imperative", "S": "subjunctive",
                    "O": "optative", "N": "infinitive", "P": "participle"}
_MORPHGNT_CASE   = {"-": None, "N": "nominative", "G": "genitive", "D": "dative",
                    "A": "accusative", "V": "vocative"}
_MORPHGNT_NUMBER = {"-": None, "S": "singular", "P": "plural", "D": "dual"}
_MORPHGNT_GENDER = {"-": None, "M": "masculine", "F": "feminine", "N": "neuter"}


def _decode_morphgnt(morph: str) -> dict[str, str]:
    """Decode an 8-char MorphGNT morph code to a features dict."""
    if len(morph) != 8:
        return {}
    result: dict[str, str] = {}
    person = _MORPHGNT_PERSON.get(morph[0])
    tense  = _MORPHGNT_TENSE.get(morph[1])
    voice  = _MORPHGNT_VOICE.get(morph[2])
    mood   = _MORPHGNT_MOOD.get(morph[3])
    case   = _MORPHGNT_CASE.get(morph[4])
    number = _MORPHGNT_NUMBER.get(morph[5])
    gender = _MORPHGNT_GENDER.get(morph[6])
    if person: result["person"] = person
    if tense:  result["tense"]  = tense
    if voice:  result["voice"]  = voice
    if mood:   result["mood"]   = mood
    if case:   result["case"]   = case
    if number: result["number"] = number
    if gender: result["gender"] = gender
    return result


_MORPHGNT_POS = {
    "N-": "noun", "A-": "adj", "F-": "noun",  # F = substantivized / particle
    "V-": "verb", "P-": "pron", "R-": "pron",
    "C-": "conj", "X-": "verb",  # X = verbal form
    "I-": "pron", "D-": "adv", "T-": "det",  # T = article
    "Pp": "pron",  # personal pronoun
}


def ingest_morphgnt(path: Path, normalize) -> dict[str, dict]:
    """
    Parse a MorphGNT file.  Returns {normalised_form: morph_entry}.
    First occurrence wins; this effectively gives the most common form
    (MorphGNT is ordered by book-chapter-verse).
    """
    entries: dict[str, dict] = {}
    n_tokens = 0

    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.rstrip()
            if not line:
                continue
            parts = line.split()
            # Expected: bcv POS morph word word_capped lemma lemma_capped
            # Some lines have 7 or 8 fields.
            if len(parts) < 7:
                continue
            pos_code = parts[1]   # e.g. "N-", "V-", "Pp"
            morph    = parts[2]   # e.g. "----NSF-"
            word     = parts[3]   # surface form (lowercase)
            lemma    = parts[5]   # lemma

            form_key  = normalize(word)
            lemma_key = normalize(lemma)
            if not form_key or not lemma_key:
                continue

            n_tokens += 1
            if form_key in entries:
                continue

            feats = _decode_morphgnt(morph)
            if not feats:
                continue

            pos = _MORPHGNT_POS.get(pos_code, "unknown")
            entry: dict[str, str] = {"lemma": lemma_key, "pos": pos}
            entry.update(feats)
            entries[form_key] = entry

    log.info("  morphgnt: %d tokens, %d unique annotated forms", n_tokens, len(entries))
    return entries


def merge_entries(base: dict, extra: dict) -> dict:
    """Merge extra into base; base wins on conflict (keep first occurrence)."""
    result = dict(base)
    for k, v in extra.items():
        if k not in result:
            result[k] = v
    return result


def write_morph(path: Path, language: str, sources: list[str], entries: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = {
        "version":  "1",
        "language": language,
        "sources":  sources,
        "entries":  entries,
    }
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    log.info("Wrote %s (%d entries, %.1f KB)", path.name, len(entries), path.stat().st_size / 1024)


def ingest_latin() -> None:
    conllu = RAW / "la_ittb-ud-dev.conllu"
    entries = ingest_conllu(conllu, normalize_latin)
    write_morph(
        OUT / "la_morph.json",
        "la",
        ["la_ittb-ud-dev.conllu (CC BY-NC-SA 3.0, Index Thomisticus, Universal Dependencies)"],
        entries,
    )


def ingest_greek() -> None:
    conllu  = RAW / "grc_proiel-ud-dev.conllu"
    morphgnt = RAW / "morphgnt_sblgnt.txt"

    entries_ud     = ingest_conllu(conllu, normalize_greek)
    entries_gnt    = ingest_morphgnt(morphgnt, normalize_greek)
    merged         = merge_entries(entries_ud, entries_gnt)

    write_morph(
        OUT / "grc_morph.json",
        "grc",
        [
            "grc_proiel-ud-dev.conllu (CC BY-NC-SA, PROIEL, Universal Dependencies)",
            "morphgnt_sblgnt.txt (CC BY-SA 3.0, MorphGNT; SBL GNT non-commercial)",
        ],
        merged,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lang", choices=["la", "grc", "all"], default="all")
    args = ap.parse_args()
    if args.lang in ("la", "all"):
        ingest_latin()
    if args.lang in ("grc", "all"):
        ingest_greek()
    log.info("Done.")


if __name__ == "__main__":
    main()
