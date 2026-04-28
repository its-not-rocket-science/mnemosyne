#!/usr/bin/env python3
"""
capture_lang_data.py
====================
Downloads and processes linguistic data for Mnemosyne stub language plugins.

Run once outside Claude sessions to harvest the grammar/vocab data needed to
implement Russian (partial→full), Japanese, Chinese, Arabic, Hebrew, Latin,
and Koine Greek plugins.

Usage
-----
    python capture_lang_data.py          # all languages
    python capture_lang_data.py ru ja    # specific languages
    python capture_lang_data.py --list   # show what will be fetched

Output
------
    data/lang_capture/
        {lang}_summary.json   ← structured data for plugin implementation
        raw/                  ← downloaded source files (kept for re-runs)

Sources (all public-domain or open licence)
-------------------------------------------
    Universal Dependencies treebanks  CC BY-SA 4.0
    OpenRussian dictionary             CC BY-SA 4.0
    JMdict / JMnedict                  CC BY-SA 4.0 (EDRDG)
    kaikki.org Wiktionary extracts     CC BY-SA 4.0
    CC-CEDICT                          CC BY-SA 4.0
    HSK word lists                     public domain
    MorphGNT (Koine Greek)             CC BY-SA 3.0
    Whitaker's WORDS Latin forms       public domain
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import os
import re
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from urllib.error import URLError, HTTPError
from urllib.request import urlopen, Request

# ── Paths ─────────────────────────────────────────────────────────────────────

ROOT    = Path(__file__).parent
RAW_DIR = ROOT / "data" / "lang_capture" / "raw"
OUT_DIR = ROOT / "data" / "lang_capture"
RAW_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────

# Sent with every request so servers don't 403 the default Python UA.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}


def _fetch(url: str) -> bytes:
    """GET url with browser-like headers, return response bytes."""
    req = Request(url, headers=_HEADERS)
    with urlopen(req, timeout=60) as resp:
        return resp.read()


def _dl(url: str, dest: Path, label: str = "") -> Path:
    """Download url → dest, skip if dest already exists."""
    if dest.exists():
        log.info("  skip (cached): %s", dest.name)
        return dest
    label = label or dest.name
    log.info("  downloading: %s", label)
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    try:
        tmp.write_bytes(_fetch(url))
        tmp.rename(dest)
    except (URLError, HTTPError) as exc:
        log.error("  FAILED %s: %s", url, exc)
        if tmp.exists():
            tmp.unlink()
        raise
    return dest


def _dl_first(candidates: list[tuple[str, str]], dest: Path, label: str = "") -> Path:
    """Try each (url, format_hint) in candidates; use first that succeeds.

    Skips cached dest only if it is non-empty (guards against corrupt files
    left by an interrupted previous run).  Catches all exceptions per
    candidate so a network error, timeout, or HTTP error never aborts the
    loop — it just moves on to the next URL.
    """
    if dest.exists() and dest.stat().st_size > 10:
        log.info("  skip (cached): %s", dest.name)
        return dest
    if dest.exists():
        dest.unlink()   # remove empty/corrupt cached file
    label = label or dest.name
    tmp = dest.with_suffix(dest.suffix + ".tmp")
    errors: list[str] = []
    for url, hint in candidates:
        log.info("  trying %s [%s]: %s", label, hint, url)
        try:
            data = _fetch(url)
            if len(data) < 10:
                raise ValueError(f"response too small ({len(data)} bytes)")
            tmp.write_bytes(data)
            tmp.rename(dest)
            log.info("  ok (%s, %d bytes)", hint, dest.stat().st_size)
            return dest
        except Exception as exc:          # broad: covers HTTPError, timeout, SSL, etc.
            if tmp.exists():
                tmp.unlink()
            errors.append(f"{hint}: {exc}")
            log.warning("  %s failed: %s", hint, exc)
    raise RuntimeError(f"All candidates failed for {label}: " + "; ".join(errors))


def _parse_kaikki(
    gz_path: Path,
    *,
    pos_filter: str | None = "verb",
    max_entries: int = 1000,
    max_lines: int = 300_000,
) -> list[dict]:
    """Stream-parse a kaikki.org JSONL.gz, capping both lines read and entries
    collected.  Stops early on either limit so large files (Arabic: 3M+ lines)
    don't stall the script.  Returns list of dicts with keys:
        lemma, en, pos, forms (list of {form, tags})
    """
    results: list[dict] = []
    with gzip.open(gz_path, "rt", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= max_lines:
                break
            try:
                entry = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            pos = entry.get("pos", "")
            if pos_filter and pos != pos_filter:
                continue
            word = entry.get("word", "")
            if not word:
                continue
            senses = entry.get("senses", [])
            gloss = next((s["glosses"][0] for s in senses if s.get("glosses")), "")
            forms = [
                {"form": fm.get("form", ""), "tags": fm.get("tags", [])}
                for fm in entry.get("forms", [])[:8]
            ]
            extra: dict = {}
            cats = entry.get("categories", [])
            if cats:
                extra["categories"] = cats[:3]
            results.append({"lemma": word, "en": gloss, "pos": pos, "forms": forms, **extra})
            if len(results) >= max_entries:
                break
    return results


def _gunzip(gz_path: Path) -> Path:
    """Decompress .gz → same path without .gz extension."""
    out = gz_path.with_suffix("")
    if out.exists():
        return out
    log.info("  decompressing: %s", gz_path.name)
    with gzip.open(gz_path, "rb") as fin, open(out, "wb") as fout:
        fout.write(fin.read())
    return out


def _unzip(zip_path: Path, member: str) -> Path:
    """Extract a single member from a zip to RAW_DIR."""
    out = RAW_DIR / member.split("/")[-1]
    if out.exists():
        return out
    log.info("  extracting: %s", member)
    with zipfile.ZipFile(zip_path) as zf:
        data = zf.read(member)
    out.write_bytes(data)
    return out


def _save(data: dict, lang: str) -> Path:
    """Write summary JSON for a language."""
    dest = OUT_DIR / f"{lang}_summary.json"
    dest.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("  wrote: %s (%d bytes)", dest.name, dest.stat().st_size)
    return dest


# ── Universal Dependencies helpers ───────────────────────────────────────────

_UD_BASE = "https://raw.githubusercontent.com/UniversalDependencies/{repo}/master/{file}"

_UD_CORPORA = {
    "ru":  ("UD_Russian-SynTagRus",  "ru_syntagrus-ud-dev.conllu"),
    "ja":  ("UD_Japanese-GSD",       "ja_gsd-ud-dev.conllu"),
    "zh":  ("UD_Chinese-GSD",        "zh_gsd-ud-dev.conllu"),
    "ar":  ("UD_Arabic-PADT",        "ar_padt-ud-dev.conllu"),
    "he":  ("UD_Hebrew-HTB",         "he_htb-ud-dev.conllu"),
    "la":  ("UD_Latin-ITTB",         "la_ittb-ud-dev.conllu"),
    "grc": ("UD_Ancient_Greek-PROIEL", "grc_proiel-ud-dev.conllu"),
}


def _fetch_ud(lang: str) -> Path:
    repo, fname = _UD_CORPORA[lang]
    dest = RAW_DIR / fname
    url  = _UD_BASE.format(repo=repo, file=fname)
    return _dl(url, dest, f"UD {repo} dev")


def _parse_conllu(path: Path) -> list[list[dict]]:
    """Parse a CoNLL-U file into sentences (list of token dicts)."""
    sentences, current = [], []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            continue
        if not line.strip():
            if current:
                sentences.append(current)
                current = []
            continue
        parts = line.split("\t")
        if len(parts) < 10 or "-" in parts[0] or "." in parts[0]:
            continue
        current.append({
            "id":    parts[0],
            "form":  parts[1],
            "lemma": parts[2],
            "upos":  parts[3],
            "xpos":  parts[4],
            "feats": dict(kv.split("=") for kv in parts[5].split("|") if "=" in kv),
            "head":  parts[6],
            "deprel":parts[7],
        })
    if current:
        sentences.append(current)
    return sentences


def _ud_verb_patterns(sentences: list[list[dict]]) -> dict:
    """Extract verb-centred patterns from parsed CoNLL-U sentences."""
    gov   = Counter()   # (verb_lemma, deprel, case_of_child) — verbal government
    deps  = Counter()   # deprel distribution
    feats = Counter()   # morphological feature values on VERBs

    for sent in sentences:
        by_id = {t["id"]: t for t in sent}
        for tok in sent:
            if tok["upos"] in ("VERB", "AUX"):
                # morph features on this verb
                for k, v in tok["feats"].items():
                    feats[f"{k}={v}"] += 1
                # children of this verb
                for child in sent:
                    if child["head"] == tok["id"]:
                        deps[child["deprel"]] += 1
                        case = child["feats"].get("Case", "")
                        if child["deprel"] in ("obj", "iobj", "obl", "nsubj") and case:
                            gov[(tok["lemma"], child["deprel"], case)] += 1

    # top-50 verbal government patterns
    top_gov = [
        {"verb": v, "deprel": d, "case": c, "count": n}
        for (v, d, c), n in gov.most_common(50)
    ]
    top_deps = [{"deprel": d, "count": n} for d, n in deps.most_common(20)]
    top_feats = [{"feature": f, "count": n} for f, n in feats.most_common(30)]

    return {
        "top_verbal_government": top_gov,
        "top_dep_relations":     top_deps,
        "top_verb_features":     top_feats,
        "sentence_count":        len(sentences),
    }


# ── Russian ───────────────────────────────────────────────────────────────────

def capture_ru() -> None:
    log.info("=== Russian ===")
    summary: dict = {}

    # OpenRussian — verb aspect pairs + noun case data
    _dl(
        "https://github.com/Badestrand/russian-dictionary/raw/master/verbs.csv",
        RAW_DIR / "openrussian_verbs.csv",
        "OpenRussian verbs",
    )
    _dl(
        "https://github.com/Badestrand/russian-dictionary/raw/master/nouns.csv",
        RAW_DIR / "openrussian_nouns.csv",
        "OpenRussian nouns",
    )
    _dl(
        "https://github.com/Badestrand/russian-dictionary/raw/master/adjectives.csv",
        RAW_DIR / "openrussian_adjectives.csv",
        "OpenRussian adjectives",
    )

    # Parse verbs CSV → aspect pairs
    import csv
    aspect_pairs = []
    verb_rows = []
    with open(RAW_DIR / "openrussian_verbs.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            verb_rows.append(row)
            imp = row.get("imperfective", "").strip()
            prf = row.get("perfective", "").strip()
            if imp and prf:
                aspect_pairs.append({
                    "imperfective": imp,
                    "perfective":   prf,
                    "en":           row.get("translations_en", ""),
                })

    summary["aspect_pairs"] = aspect_pairs
    summary["verb_count"] = len(verb_rows)
    log.info("  aspect pairs: %d  verbs total: %d", len(aspect_pairs), len(verb_rows))

    # Parse conjugation columns — build conjugation template per verb
    conj_keys = ["sg1", "sg2", "sg3", "pl1", "pl2", "pl3"]
    conjugations = []
    for row in verb_rows[:500]:  # first 500 common verbs
        entry = {"lemma": row.get("bare", ""), "en": row.get("translations_en", "")}
        for k in conj_keys:
            v = row.get(k, "").strip()
            if v:
                entry[k] = v
        if entry.get("lemma"):
            conjugations.append(entry)
    summary["conjugation_samples"] = conjugations

    # UD patterns
    ud_path   = _fetch_ud("ru")
    sentences = _parse_conllu(ud_path)
    summary["ud_patterns"] = _ud_verb_patterns(sentences)

    # Aspect feature distribution from UD
    aspect_dist: Counter = Counter()
    for sent in sentences:
        for tok in sent:
            if tok["upos"] == "VERB":
                asp = tok["feats"].get("Aspect", "")
                if asp:
                    aspect_dist[asp] += 1
    summary["ud_aspect_distribution"] = dict(aspect_dist)

    _save(summary, "ru")


# ── Japanese ──────────────────────────────────────────────────────────────────

def capture_ja() -> None:
    log.info("=== Japanese ===")
    summary: dict = {}

    # JMdict simplified JSON (scriptin's pre-parsed version)
    jmdict_tgz = RAW_DIR / "jmdict-eng.json.tgz"
    _dl(
        "https://github.com/scriptin/jmdict-simplified/releases/download/3.6.2%2B20260427133054/jmdict-eng-3.6.2+20260427133054.json.tgz",
        jmdict_tgz,
        "JMdict simplified JSON",
    )
    jmdict_path = _gunzip(jmdict_tgz)

    log.info("  parsing JMdict ...")
    with open(jmdict_path, encoding="utf-8") as f:
        jmdict = json.load(f)

    # Verb type buckets (JMdict pos tags)
    # v1=ichidan, v5*=godan variants, vk=kuru, vs-i=suru
    verb_types: dict[str, list] = defaultdict(list)
    jlpt_vocab: dict[str, list] = defaultdict(list)

    for word in jmdict.get("words", []):
        kanji_forms  = [k["text"] for k in word.get("kanji", [])]
        kana_forms   = [k["text"] for k in word.get("kana", [])]
        lemma        = kanji_forms[0] if kanji_forms else (kana_forms[0] if kana_forms else "")
        reading      = kana_forms[0] if kana_forms else ""
        if not lemma:
            continue

        senses = word.get("sense", [])
        en_gloss = "; ".join(
            g["text"] for s in senses[:1] for g in s.get("gloss", [])[:2]
        )

        # JLPT level
        for tag_list in (word.get("kanji", []) + word.get("kana", [])):
            for tag in tag_list.get("tags", []):
                if tag.startswith("jlpt"):
                    level = tag.upper().replace("JLPT", "N")
                    jlpt_vocab[level].append({
                        "lemma": lemma, "reading": reading, "en": en_gloss
                    })

        # Verb type from part-of-speech
        all_pos = [p for s in senses for p in s.get("partOfSpeech", [])]
        for pos in all_pos:
            if pos.startswith("v"):
                vtype = pos.split("-")[0] if "-" in pos else pos
                # Store first 200 per type
                if len(verb_types[vtype]) < 200:
                    verb_types[vtype].append({
                        "lemma": lemma, "reading": reading,
                        "en": en_gloss, "pos_full": pos,
                    })
                break

    summary["verb_types"] = {k: v for k, v in sorted(verb_types.items())}
    summary["jlpt_vocab"]  = {
        k: v[:300] for k, v in sorted(jlpt_vocab.items())
    }
    log.info("  verb types: %s", {k: len(v) for k, v in summary["verb_types"].items()})
    log.info("  JLPT vocab: %s", {k: len(v) for k, v in summary["jlpt_vocab"].items()})

    # UD patterns
    ud_path   = _fetch_ud("ja")
    sentences = _parse_conllu(ud_path)
    summary["ud_patterns"] = _ud_verb_patterns(sentences)

    # Conjugation suffix rules derived from verb types
    # These are systematic — document them so the plugin can generate forms
    summary["conjugation_rules"] = {
        "v1_ichidan": {
            "description": "Remove -る, add suffix",
            "forms": {
                "masu":       "-ます",  "masen":     "-ません",
                "te":         "-て",    "ta":        "-た",
                "nai":        "-ない",  "ba":        "-れば",
                "volitional": "-よう",  "potential": "-られる",
                "passive":    "-られる", "causative": "-させる",
            },
        },
        "v5_godan_u":  {"description": "u→i before ます; u→っ before て/た", "stem_change": "u-row"},
        "v5_godan_ku": {"description": "ku→ki before ます; ku→いて before て/た", "stem_change": "ku-row"},
        "v5_godan_gu": {"description": "gu→gi before ます; gu→いで before て/た", "stem_change": "gu-row"},
        "v5_godan_su": {"description": "su→shi before ます; su→して before て/た", "stem_change": "su-row"},
        "v5_godan_tsu":{"description": "tsu→chi before ます; tsu→って before て/た", "stem_change": "tsu-row"},
        "v5_godan_nu": {"description": "nu→ni before ます; nu→んで before て/た", "stem_change": "nu-row"},
        "v5_godan_bu": {"description": "bu→bi before ます; bu→んで before て/た", "stem_change": "bu-row"},
        "v5_godan_mu": {"description": "mu→mi before ます; mu→んで before て/た", "stem_change": "mu-row"},
        "v5_godan_ru": {"description": "ru→ri before ます; ru→って before て/た", "stem_change": "ru-row"},
        "vk_kuru":     {"description": "Irregular: くる/きます/きて/きた/こない/こよう", "irregular": True},
        "vs_i_suru":   {"description": "Irregular: する/します/して/した/しない/しよう", "irregular": True},
    }

    _save(summary, "ja")


# ── Chinese ───────────────────────────────────────────────────────────────────

def capture_zh() -> None:
    log.info("=== Chinese ===")
    summary: dict = {}

    # CC-CEDICT
    cedict_zip = RAW_DIR / "cedict_utf8.zip"
    _dl(
        "https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.zip",
        cedict_zip,
        "CC-CEDICT",
    )
    cedict_path = _unzip(cedict_zip, "cedict_ts.u8")

    log.info("  parsing CC-CEDICT ...")
    entries = []
    pattern = re.compile(r"^(\S+)\s+(\S+)\s+\[([^\]]+)\]\s+/(.+)/$")
    for line in cedict_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            continue
        m = pattern.match(line)
        if m:
            trad, simp, pinyin, defs_raw = m.groups()
            defs = [d for d in defs_raw.split("/") if d]
            entries.append({
                "traditional": trad, "simplified": simp,
                "pinyin": pinyin, "defs": defs[:3],
            })
    summary["cedict_count"] = len(entries)
    log.info("  CC-CEDICT entries: %d", len(entries))

    # HSK 1-6 word lists — four candidate sources per level tried in order.
    # Any 404 / error skips to the next source automatically.
    # Source A: clem109/hsk-vocabulary  (txt, one simplified word per line)
    # Source B: kfkf33/hsk              (txt, tab-separated simplified/traditional/pinyin)
    # Source C: gigamonkey/hsk          (JSON array of strings)
    # Source D: nicklockwood/CHSK       (JSON array of objects with "Simplified" key)
    hsk_vocab: dict[str, list] = {}
    for level in range(1, 7):
        dest = RAW_DIR / f"hsk_{level}.raw"
        candidates = [
            (
                f"https://raw.githubusercontent.com/clem109/hsk-vocabulary/refs/heads/master/"
                f"hsk-vocab-json/hsk-level-{level}.json"
                "clem109-json",
            ),
            # (
            #     f"https://raw.githubusercontent.com/kfkf33/hsk/master/hsk{level}.csv",
            #     "kfkf33-csv",
            # ),
            # (
            #     f"https://raw.githubusercontent.com/gigamonkey/hsk/master/hsk{level}.json",
            #     "gigamonkey-json",
            # ),
            # (
            #     f"https://raw.githubusercontent.com/nicklockwood/CHSK/master/CHSK-{level}.json",
            #     "nicklockwood-json",
            # ),
        ]
        try:
            _dl_first(candidates, dest, f"HSK {level}")
            raw = dest.read_text(encoding="utf-8").strip()
            # Detect format and parse
            if raw.startswith("[") or raw.startswith("{"):
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    if parsed and isinstance(parsed[0], str):
                        words = parsed
                    elif parsed and isinstance(parsed[0], dict):
                        # nicklockwood format: [{Simplified, Traditional, Pinyin, ...}]
                        words = [
                            e.get("Simplified") or e.get("simplified") or e.get("word", "")
                            for e in parsed if isinstance(e, dict)
                        ]
                    else:
                        words = [str(x) for x in parsed]
                else:
                    words = list(parsed.keys())
            else:
                # plain text or CSV — first field on each line is the simplified form
                words = []
                for line in raw.splitlines():
                    # handles tab-separated, comma-separated, or bare word per line
                    w = re.split(r"[\t,]", line)[0].strip()
                    if w and not w.startswith("#"):
                        words.append(w)
            hsk_vocab[f"HSK{level}"] = [w for w in words if w]
        except Exception as exc:
            log.warning("  HSK %d all sources failed: %s", level, exc)
    summary["hsk_vocab"] = hsk_vocab
    log.info("  HSK vocab: %s", {k: len(v) for k, v in hsk_vocab.items()})

    # Aspect particles and grammar marker inventory
    summary["grammar_markers"] = {
        "aspect_particles": {
            "了": {"pinyin": "le", "function": "perfective aspect / change of state"},
            "着": {"pinyin": "zhe", "function": "progressive / continuous aspect"},
            "过": {"pinyin": "guo", "function": "experiential aspect (ever done)"},
        },
        "structural_particles": {
            "的": {"pinyin": "de", "function": "attributive / nominaliser"},
            "地": {"pinyin": "de", "function": "adverbial marker (verb/adj → adverb)"},
            "得": {"pinyin": "de", "function": "potential/resultative complement marker"},
        },
        "disposal_passive": {
            "把": {"function": "disposal construction: moves direct object pre-verb"},
            "被": {"function": "passive marker"},
            "让": {"function": "passive / causative"},
            "叫": {"function": "passive / causative (colloquial)"},
        },
        "measure_words_common": {
            "个": "general (人,东西)",  "本": "bound objects (书,杂志)",
            "张": "flat objects (纸,桌子)", "条": "long/flexible (路,鱼,裤子)",
            "只": "small animals, one of a pair", "辆": "vehicles",
            "件": "clothes/matters", "块": "pieces/chunks",
            "瓶": "bottles", "杯": "cups/glasses",
        },
    }

    # UD patterns
    ud_path   = _fetch_ud("zh")
    sentences = _parse_conllu(ud_path)
    summary["ud_patterns"] = _ud_verb_patterns(sentences)

    _save(summary, "zh")


# ── Arabic ────────────────────────────────────────────────────────────────────

def capture_ar() -> None:
    log.info("=== Arabic ===")
    summary: dict = {}

    # UD patterns — primary source for case/morphology patterns
    ud_path   = _fetch_ud("ar")
    sentences = _parse_conllu(ud_path)
    summary["ud_patterns"] = _ud_verb_patterns(sentences)

    # Morphological feature distribution from UD
    feat_dist: dict[str, Counter] = defaultdict(Counter)
    for sent in sentences:
        for tok in sent:
            for k, v in tok["feats"].items():
                feat_dist[k][v] += 1
    summary["morphological_features"] = {
        k: dict(v.most_common(10)) for k, v in sorted(feat_dist.items())
    }

    # Arabic verb form (binyan) reference table
    summary["verb_forms"] = {
        "Form_I":    {"pattern": "فَعَلَ", "trans_pattern": "CaCaCa", "meaning": "base action"},
        "Form_II":   {"pattern": "فَعَّلَ", "trans_pattern": "CaCCaCa", "meaning": "intensification / causative"},
        "Form_III":  {"pattern": "فَاعَلَ", "trans_pattern": "CāCaCa", "meaning": "reciprocal action"},
        "Form_IV":   {"pattern": "أَفْعَلَ", "trans_pattern": "ʔaCCaCa", "meaning": "causative"},
        "Form_V":    {"pattern": "تَفَعَّلَ", "trans_pattern": "taCaCCaCa", "meaning": "reflexive of II"},
        "Form_VI":   {"pattern": "تَفَاعَلَ", "trans_pattern": "taCāCaCa", "meaning": "reflexive of III"},
        "Form_VII":  {"pattern": "اِنْفَعَلَ", "trans_pattern": "inCaCaCa", "meaning": "passive/reflexive"},
        "Form_VIII": {"pattern": "اِفْتَعَلَ", "trans_pattern": "iCtaCaCa", "meaning": "reflexive / reciprocal"},
        "Form_X":    {"pattern": "اِسْتَفْعَلَ", "trans_pattern": "istaCCaCa", "meaning": "to consider/seek"},
    }

    # Kaikki.org Wiktionary extract — Arabic verbs sample
    kaikki_gz = RAW_DIR / "kaikki_ar.jsonl.gz"
    try:
        _dl(
            "https://kaikki.org/dictionary/Arabic/kaikki.org-dictionary-Arabic.jsonl.gz",
            kaikki_gz,
            "Wiktionary Arabic (kaikki.org)",
        )
        log.info("  parsing Wiktionary Arabic verbs (max 300k lines) ...")
        verbs = _parse_kaikki(kaikki_gz, pos_filter="verb", max_entries=1000, max_lines=300_000)
        summary["wiktionary_verbs_sample"] = verbs
        log.info("  Arabic verbs extracted: %d", len(verbs))
    except Exception as exc:
        log.warning("  Wiktionary Arabic skipped: %s", exc)

    # Prefix clitics reference
    summary["prefix_clitics"] = {
        "و": "wa- (and)",  "ف": "fa- (so/then)", "ب": "bi- (in/with/by)",
        "ل": "li- (for/to)", "ك": "ka- (like/as)", "ال": "al- (the, definite article)",
    }

    _save(summary, "ar")


# ── Hebrew ────────────────────────────────────────────────────────────────────

def capture_he() -> None:
    log.info("=== Hebrew ===")
    summary: dict = {}

    # UD patterns
    ud_path   = _fetch_ud("he")
    sentences = _parse_conllu(ud_path)
    summary["ud_patterns"] = _ud_verb_patterns(sentences)

    # Morphological feature distribution
    feat_dist: dict[str, Counter] = defaultdict(Counter)
    for sent in sentences:
        for tok in sent:
            for k, v in tok["feats"].items():
                feat_dist[k][v] += 1
    summary["morphological_features"] = {
        k: dict(v.most_common(10)) for k, v in sorted(feat_dist.items())
    }

    # Hebrew binyan reference table
    summary["binyanim"] = {
        "Pa'al (Qal)":   {"pattern": "פָּעַל", "voice": "simple active", "example": "כתב (katav) to write"},
        "Nif'al":        {"pattern": "נִפְעַל", "voice": "simple passive/reflexive", "example": "נכתב (niktav) to be written"},
        "Pi'el":         {"pattern": "פִּעֵל", "voice": "intensive active", "example": "דיבר (diber) to speak"},
        "Pu'al":         {"pattern": "פֻּעַל", "voice": "intensive passive", "example": "דובר (dubar) to be spoken"},
        "Hif'il":        {"pattern": "הִפְעִיל", "voice": "causative active", "example": "הכניס (hiknis) to insert"},
        "Huf'al":        {"pattern": "הֻפְעַל", "voice": "causative passive", "example": "הוכנס (huknas) to be inserted"},
        "Hitpa'el":      {"pattern": "הִתְפַּעֵל", "voice": "reflexive/reciprocal", "example": "התלבש (hitlabesh) to get dressed"},
    }

    # Common inseparable prefixes
    summary["prefix_particles"] = {
        "ב": "be- (in/with/by/at)",  "כ": "ke- (like/as/about)",
        "ל": "le- (to/for)",          "מ": "mi-/me- (from/of)",
        "ש": "she- (that/which/who)", "ה": "ha- (the, definite)",
        "ו": "ve- (and)",             "ר": "prefix in some forms",
    }

    # Kaikki.org Wiktionary extract — Hebrew verbs sample
    kaikki_gz = RAW_DIR / "kaikki_he.jsonl.gz"
    try:
        _dl(
            "https://kaikki.org/dictionary/Hebrew/kaikki.org-dictionary-Hebrew.jsonl.gz",
            kaikki_gz,
            "Wiktionary Hebrew (kaikki.org)",
        )
        log.info("  parsing Wiktionary Hebrew verbs (max 300k lines) ...")
        verbs = _parse_kaikki(kaikki_gz, pos_filter="verb", max_entries=1000, max_lines=300_000)
        # annotate binyan from categories field where present
        for v in verbs:
            cats = v.pop("categories", [])
            v["binyan"] = next((c for c in cats if "binyan" in c.lower() or "פעל" in c), "")
        summary["wiktionary_verbs_sample"] = verbs
        log.info("  Hebrew verbs extracted: %d", len(verbs))
    except Exception as exc:
        log.warning("  Wiktionary Hebrew skipped: %s", exc)

    _save(summary, "he")


# ── Latin ─────────────────────────────────────────────────────────────────────

def capture_la() -> None:
    log.info("=== Latin ===")
    summary: dict = {}

    # UD patterns
    ud_path   = _fetch_ud("la")
    sentences = _parse_conllu(ud_path)
    summary["ud_patterns"] = _ud_verb_patterns(sentences)

    # Morphological feature distribution
    feat_dist: dict[str, Counter] = defaultdict(Counter)
    for sent in sentences:
        for tok in sent:
            for k, v in tok["feats"].items():
                feat_dist[k][v] += 1
    summary["morphological_features"] = {
        k: dict(v.most_common(10)) for k, v in sorted(feat_dist.items())
    }

    # Declension paradigms (all 5 Latin declensions)
    summary["declension_paradigms"] = {
        "1st_a_stem": {
            "example": "puella (girl)",
            "endings": {
                "nom_sg": "a",   "gen_sg": "ae",  "dat_sg": "ae",
                "acc_sg": "am",  "abl_sg": "ā",   "voc_sg": "a",
                "nom_pl": "ae",  "gen_pl": "ārum", "dat_pl": "īs",
                "acc_pl": "ās",  "abl_pl": "īs",
            },
        },
        "2nd_o_stem_m": {
            "example": "servus (slave)",
            "endings": {
                "nom_sg": "us",  "gen_sg": "ī",   "dat_sg": "ō",
                "acc_sg": "um",  "abl_sg": "ō",   "voc_sg": "e",
                "nom_pl": "ī",   "gen_pl": "ōrum", "dat_pl": "īs",
                "acc_pl": "ōs",  "abl_pl": "īs",
            },
        },
        "2nd_o_stem_n": {
            "example": "bellum (war)",
            "endings": {
                "nom_sg": "um",  "gen_sg": "ī",   "dat_sg": "ō",
                "acc_sg": "um",  "abl_sg": "ō",
                "nom_pl": "a",   "gen_pl": "ōrum", "dat_pl": "īs",
                "acc_pl": "a",   "abl_pl": "īs",
            },
        },
        "3rd_consonant": {
            "example": "rex (king)",
            "note": "Stem found by removing -is from genitive",
            "endings": {
                "nom_sg": "(variable)", "gen_sg": "is", "dat_sg": "ī",
                "acc_sg": "em",         "abl_sg": "e",
                "nom_pl": "ēs",         "gen_pl": "um/ium", "dat_pl": "ibus",
                "acc_pl": "ēs",         "abl_pl": "ibus",
            },
        },
        "4th_u_stem": {
            "example": "manus (hand)",
            "endings": {
                "nom_sg": "us", "gen_sg": "ūs", "dat_sg": "uī",
                "acc_sg": "um", "abl_sg": "ū",
                "nom_pl": "ūs", "gen_pl": "uum", "dat_pl": "ibus",
                "acc_pl": "ūs", "abl_pl": "ibus",
            },
        },
        "5th_e_stem": {
            "example": "res (thing/matter)",
            "endings": {
                "nom_sg": "ēs", "gen_sg": "eī", "dat_sg": "eī",
                "acc_sg": "em", "abl_sg": "ē",
                "nom_pl": "ēs", "gen_pl": "ērum", "dat_pl": "ēbus",
                "acc_pl": "ēs", "abl_pl": "ēbus",
            },
        },
    }

    # Conjugation paradigms (4 conjugations + esse)
    summary["conjugation_paradigms"] = {
        "1st_are": {
            "example": "amare (to love)", "stem": "ama-",
            "present_active": ["amō", "amās", "amat", "amāmus", "amātis", "amant"],
            "imperfect_active": ["amābam", "amābās", "amābat", "amābāmus", "amābātis", "amābant"],
            "future_active": ["amābō", "amābis", "amābit", "amābimus", "amābitis", "amābunt"],
            "perfect_active": ["amāvī", "amāvistī", "amāvit", "amāvimus", "amāvistis", "amāvērunt"],
        },
        "2nd_ere_long": {
            "example": "monēre (to warn)", "stem": "monē-",
            "present_active": ["moneō", "monēs", "monet", "monēmus", "monētis", "monent"],
            "imperfect_active": ["monēbam", "monēbās", "monēbat", "monēbāmus", "monēbātis", "monēbant"],
        },
        "3rd_ere_short": {
            "example": "regere (to rule)", "stem": "reg-",
            "present_active": ["regō", "regis", "regit", "regimus", "regitis", "regunt"],
            "imperfect_active": ["regēbam", "regēbās", "regēbat", "regēbāmus", "regēbātis", "regēbant"],
        },
        "4th_ire": {
            "example": "audīre (to hear)", "stem": "audī-",
            "present_active": ["audiō", "audīs", "audit", "audīmus", "audītis", "audiunt"],
            "imperfect_active": ["audiēbam", "audiēbās", "audiēbat", "audiēbāmus", "audiēbātis", "audiēbant"],
        },
        "esse_irregular": {
            "present": ["sum", "es", "est", "sumus", "estis", "sunt"],
            "imperfect": ["eram", "erās", "erat", "erāmus", "erātis", "erant"],
            "future": ["erō", "eris", "erit", "erimus", "eritis", "erunt"],
            "perfect": ["fuī", "fuistī", "fuit", "fuimus", "fuistis", "fuērunt"],
        },
    }

    # Kaikki.org Latin verbs
    kaikki_gz = RAW_DIR / "kaikki_la.jsonl.gz"
    try:
        _dl(
            "https://kaikki.org/dictionary/Latin/kaikki.org-dictionary-Latin.jsonl.gz",
            kaikki_gz,
            "Wiktionary Latin (kaikki.org)",
        )
        log.info("  parsing Wiktionary Latin (max 300k lines) ...")
        all_entries = _parse_kaikki(kaikki_gz, pos_filter=None, max_entries=1600, max_lines=300_000)
        verbs = [e for e in all_entries if e["pos"] == "verb"][:800]
        nouns = [e for e in all_entries if e["pos"] == "noun"][:800]
        summary["wiktionary_verbs"] = verbs
        summary["wiktionary_nouns"] = nouns
        log.info("  Latin verbs: %d  nouns: %d", len(verbs), len(nouns))
    except Exception as exc:
        log.warning("  Wiktionary Latin skipped: %s", exc)

    _save(summary, "la")


# ── Koine Greek ───────────────────────────────────────────────────────────────

def capture_grc() -> None:
    log.info("=== Koine Greek ===")
    summary: dict = {}

    # UD Ancient Greek patterns
    ud_path   = _fetch_ud("grc")
    sentences = _parse_conllu(ud_path)
    summary["ud_patterns"] = _ud_verb_patterns(sentences)

    # Morphological feature distribution
    feat_dist: dict[str, Counter] = defaultdict(Counter)
    for sent in sentences:
        for tok in sent:
            for k, v in tok["feats"].items():
                feat_dist[k][v] += 1
    summary["morphological_features"] = {
        k: dict(v.most_common(10)) for k, v in sorted(feat_dist.items())
    }

    # MorphGNT — per-word morphological codes for entire Greek NT
    morphgnt_gz = RAW_DIR / "morphgnt_sblgnt.txt.gz"
    try:
        _dl(
            "https://github.com/morphgnt/sblgnt/raw/master/MorphGNT_SBLGNT.txt",
            RAW_DIR / "morphgnt_sblgnt.txt",
            "MorphGNT SBLGNT",
        )
        morphgnt_path = RAW_DIR / "morphgnt_sblgnt.txt"
        log.info("  parsing MorphGNT ...")
        # Format: book ch:vs CCAT-POS CCAT-Parse text normalised lemma
        morph_counts: dict[str, Counter] = defaultdict(Counter)
        lemma_pos: dict[str, Counter] = defaultdict(Counter)
        for line in morphgnt_path.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) < 7:
                continue
            pos_code = parts[2]      # e.g. V- N- A- etc.
            parse    = parts[3]      # e.g. PAI3S (Present Active Indicative 3rd Singular)
            lemma    = parts[6] if len(parts) > 6 else ""
            if lemma:
                lemma_pos[lemma][pos_code] += 1
            if pos_code.startswith("V") and len(parse) >= 5:
                tense  = parse[0]    # P/I/F/A/X/Y
                voice  = parse[1]    # A/M/P
                mood   = parse[2]    # I/D/S/O/N/P (indicative/imperative/subjunctive/optative/infinitive/participle)
                person = parse[3]    # 1/2/3/-
                number = parse[4]    # S/P/D/-
                morph_counts["tense"][tense] += 1
                morph_counts["voice"][voice] += 1
                morph_counts["mood"][mood]   += 1

        summary["morphgnt_verb_distribution"] = {
            k: dict(v) for k, v in morph_counts.items()
        }
        # Top 500 most frequent lemmas by POS
        summary["top_lemmas"] = [
            {"lemma": lem, "pos": dict(pos_counts.most_common(3))}
            for lem, pos_counts in sorted(
                lemma_pos.items(), key=lambda x: -sum(x[1].values())
            )[:500]
        ]
        log.info("  MorphGNT lemmas: %d", len(lemma_pos))
    except Exception as exc:
        log.warning("  MorphGNT skipped: %s", exc)

    # Kaikki.org Ancient Greek verbs
    kaikki_gz = RAW_DIR / "kaikki_grc.jsonl.gz"
    try:
        _dl(
            "https://kaikki.org/dictionary/Ancient%20Greek/kaikki.org-dictionary-AncientGreek.jsonl.gz",
            kaikki_gz,
            "Wiktionary Ancient Greek (kaikki.org)",
        )
        log.info("  parsing Wiktionary Ancient Greek (max 300k lines) ...")
        verbs = _parse_kaikki(kaikki_gz, pos_filter="verb", max_entries=1000, max_lines=300_000)
        summary["wiktionary_verbs"] = verbs
        log.info("  Greek verbs extracted: %d", len(verbs))
    except Exception as exc:
        log.warning("  Wiktionary Greek skipped: %s", exc)

    # Greek paradigm reference
    summary["verb_paradigm_omega"] = {
        "description": "ω-verb (thematic): λύω (to loosen)",
        "present_active_indicative": ["λύω", "λύεις", "λύει", "λύομεν", "λύετε", "λύουσι(ν)"],
        "imperfect_active_indicative": ["ἔλυον", "ἔλυες", "ἔλυε", "ἐλύομεν", "ἐλύετε", "ἔλυον"],
        "aorist_active_indicative": ["ἔλυσα", "ἔλυσας", "ἔλυσε", "ἐλύσαμεν", "ἐλύσατε", "ἔλυσαν"],
        "perfect_active_indicative": ["λέλυκα", "λέλυκας", "λέλυκε", "λελύκαμεν", "λελύκατε", "λελύκασι"],
        "present_middle_passive_indicative": ["λύομαι", "λύῃ", "λύεται", "λυόμεθα", "λύεσθε", "λύονται"],
    }

    _save(summary, "grc")


# ── Dispatch ──────────────────────────────────────────────────────────────────

HANDLERS = {
    "ru":  capture_ru,
    "ja":  capture_ja,
    "zh":  capture_zh,
    "ar":  capture_ar,
    "he":  capture_he,
    "la":  capture_la,
    "grc": capture_grc,
}

DESCRIPTIONS = {
    "ru":  "Russian — aspect pairs, conjugations, case government (OpenRussian + UD SynTagRus)",
    "ja":  "Japanese — verb types, JLPT vocab, conjugation rules (JMdict + UD GSD)",
    "zh":  "Chinese — CC-CEDICT, HSK 1-6, grammar markers (CC-CEDICT + UD GSD)",
    "ar":  "Arabic — verb forms I-X, morphology, clitics (UD PADT + kaikki Wiktionary)",
    "he":  "Hebrew — binyanim, prefixes, verb forms (UD HTB + kaikki Wiktionary)",
    "la":  "Latin — declension/conjugation paradigms, lemmas (UD ITTB + kaikki Wiktionary)",
    "grc": "Koine Greek — MorphGNT morphological codes, lemmas (UD PROIEL + MorphGNT + kaikki)",
}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download linguistic data for Mnemosyne plugin implementation."
    )
    parser.add_argument(
        "langs", nargs="*",
        help="Language codes to capture (default: all). Choices: " + " ".join(HANDLERS),
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List what will be fetched and exit.",
    )
    args = parser.parse_args()

    if args.list:
        print("\nLanguages and data sources:")
        for code, desc in DESCRIPTIONS.items():
            out = OUT_DIR / f"{code}_summary.json"
            status = "[done]   " if out.exists() else "[pending]"
            print(f"  {code:4s} {status}  {desc}")
        print(f"\nOutput directory: {OUT_DIR}")
        return

    targets = args.langs if args.langs else list(HANDLERS)
    unknown = set(targets) - set(HANDLERS)
    if unknown:
        print(f"Unknown language codes: {unknown}. Valid: {list(HANDLERS)}")
        sys.exit(1)

    for lang in targets:
        try:
            HANDLERS[lang]()
        except Exception as exc:
            log.error("FAILED %s: %s", lang, exc, exc_info=True)

    print("\nDone. Summaries written to:", OUT_DIR)
    for lang in targets:
        out = OUT_DIR / f"{lang}_summary.json"
        if out.exists():
            size = out.stat().st_size
            print(f"  {lang}_summary.json  {size:,} bytes")


if __name__ == "__main__":
    main()
