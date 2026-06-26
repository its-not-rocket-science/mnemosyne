#!/usr/bin/env python3
"""Flag cross-language cognates between Chinese, Japanese, and Korean catalogues.

Japanese yojijukugo (四字熟語) and Korean sajaseong-eo (四字成語) are often
cognates of Chinese chéngyǔ with the same characters but different cultural
resonance. This script compares the catalogues and identifies cognate pairs,
outputting a JSON file the backend lesson API can use.

Usage:
    python scripts/flag_cross_language_cognates.py \\
        --catalogue-dir backend/nuance/data/cultural_references \\
        --output backend/nuance/data/cross_language_cognates.json \\
        [--min-similarity 0.85]
"""
from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


def _is_cjk(ch: str) -> bool:
    cp = ord(ch)
    return (0x4E00 <= cp <= 0x9FFF) or (0x3400 <= cp <= 0x4DBF)


def _all_cjk(text: str) -> bool:
    return bool(text) and all(_is_cjk(c) for c in unicodedata.normalize("NFC", text))


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def _jaccard(a: str, b: str) -> float:
    sa = set(_nfc(a))
    sb = set(_nfc(b))
    if not sa and not sb:
        return 1.0
    inter = sa & sb
    union = sa | sb
    return len(inter) / len(union)


def _word_overlap(a: str, b: str) -> float:
    wa = set(w.lower() for w in a.split() if len(w) >= 3)
    wb = set(w.lower() for w in b.split() if len(w) >= 3)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / max(len(wa), len(wb))


def load_catalogue(path: Path, language: str) -> list[dict]:
    if not path.exists():
        print(f"WARNING: catalogue not found for {language}: {path}", file=sys.stderr)
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("entries", [])


def _cjk_forms(entry: dict) -> list[str]:
    """Return all CJK-script forms for an entry: canonical_reference if all-CJK,
    plus any surface_patterns that are all-CJK.  Korean sajaseong-eo entries
    typically have a hangul canonical_reference but hanja in surface_patterns."""
    forms: list[str] = []
    ref = entry.get("canonical_reference", "")
    if _all_cjk(ref):
        forms.append(ref)
    for s in entry.get("surface_patterns", []):
        if _all_cjk(s) and s not in forms:
            forms.append(s)
    return forms


def find_cognates(
    zh_entries: list[dict],
    other_entries: list[dict],
    other_lang: str,
    min_similarity: float,
) -> list[dict]:
    pairs: list[dict] = []
    matched_other: set[str] = set()
    matched_zh: set[str] = set()

    # Index zh entries by canonical_reference and surface_patterns
    zh_by_nfc: dict[str, dict] = {}
    zh_surfaces: dict[str, list[dict]] = {}
    for e in zh_entries:
        ref_nfc = _nfc(e.get("canonical_reference", ""))
        if ref_nfc:
            zh_by_nfc[ref_nfc] = e
        for s in e.get("surface_patterns", []):
            sn = _nfc(s)
            zh_surfaces.setdefault(sn, []).append(e)

    # Pass 1: exact NFC match — canonical_reference OR any all-CJK surface pattern
    for other in other_entries:
        for cjk_ref in _cjk_forms(other):
            ref_nfc = _nfc(cjk_ref)
            if ref_nfc not in zh_by_nfc:
                continue
            zh = zh_by_nfc[ref_nfc]
            pair_id = f"{other['id']}|{zh['id']}"
            if pair_id in matched_other:
                continue
            matched_other.add(pair_id)
            matched_zh.add(zh["id"])
            pairs.append({
                "source_id":   other["id"],
                "source_lang": other_lang,
                "source_ref":  other.get("canonical_reference", cjk_ref),
                "source_hanja": cjk_ref,
                "target_id":   zh["id"],
                "target_lang": "zh",
                "target_ref":  zh["canonical_reference"],
                "match_type":  "exact",
                "similarity":  1.0,
                "note":        "Chinese cognate: semantic drift may apply",
            })

    # Pass 2: character-level Jaccard similarity on all CJK forms
    for other in other_entries:
        cjk_forms = _cjk_forms(other)
        if not cjk_forms:
            continue
        best_sim = 0.0
        best_zh: dict | None = None
        best_form: str = cjk_forms[0]
        for cjk_ref in cjk_forms:
            ref_nfc = _nfc(cjk_ref)
            for zh in zh_entries:
                zh_ref = zh.get("canonical_reference", "")
                if not zh_ref:
                    continue
                pair_id = f"{other['id']}|{zh['id']}"
                if pair_id in matched_other:
                    continue
                sim = _jaccard(ref_nfc, _nfc(zh_ref))
                if sim >= min_similarity and sim > best_sim:
                    best_sim = sim
                    best_zh = zh
                    best_form = cjk_ref
        if best_zh:
            pair_id = f"{other['id']}|{best_zh['id']}"
            if pair_id not in matched_other:
                matched_other.add(pair_id)
                pairs.append({
                    "source_id":   other["id"],
                    "source_lang": other_lang,
                    "source_ref":  other.get("canonical_reference", best_form),
                    "source_hanja": best_form,
                    "target_id":   best_zh["id"],
                    "target_lang": "zh",
                    "target_ref":  best_zh["canonical_reference"],
                    "match_type":  "similar",
                    "similarity":  round(best_sim, 3),
                    "note":        "Chinese cognate: semantic drift may apply",
                })

    # Pass 3: surface pattern overlap (catches remaining CJK surface ↔ zh surface)
    for other in other_entries:
        for other_surf in other.get("surface_patterns", []):
            sn = _nfc(other_surf)
            if sn not in zh_surfaces:
                continue
            for zh in zh_surfaces[sn]:
                pair_id = f"{other['id']}|{zh['id']}"
                if pair_id in matched_other:
                    continue
                matched_other.add(pair_id)
                pairs.append({
                    "source_id":   other["id"],
                    "source_lang": other_lang,
                    "source_ref":  other.get("canonical_reference", ""),
                    "source_hanja": other_surf if _all_cjk(other_surf) else None,
                    "target_id":   zh["id"],
                    "target_lang": "zh",
                    "target_ref":  zh["canonical_reference"],
                    "match_type":  "surface_overlap",
                    "similarity":  0.9,
                    "note":        "Chinese cognate: semantic drift may apply",
                })

    return pairs


def semantic_drift_pairs(pairs: list[dict], zh_entries: list[dict], other_entries: list[dict]) -> list[dict]:
    zh_by_id = {e["id"]: e for e in zh_entries}
    other_by_id: dict[str, dict] = {}
    for e in other_entries:
        other_by_id[e["id"]] = e

    drifts = []
    for p in pairs:
        src = other_by_id.get(p["source_id"], {})
        tgt = zh_by_id.get(p["target_id"], {})
        src_exp = src.get("short_explanation", "")
        tgt_exp = tgt.get("short_explanation", "")
        if src_exp and tgt_exp and _word_overlap(src_exp, tgt_exp) < 0.2:
            drifts.append(p)
    return drifts


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--catalogue-dir", type=Path,
                    default=Path("backend/nuance/data/cultural_references"))
    ap.add_argument("--output", type=Path,
                    default=Path("backend/nuance/data/cross_language_cognates.json"))
    ap.add_argument("--min-similarity", type=float, default=0.85)
    args = ap.parse_args()

    zh_entries = load_catalogue(args.catalogue_dir / "zh.json", "zh")
    ja_entries = load_catalogue(args.catalogue_dir / "ja.json", "ja")
    ko_entries = load_catalogue(args.catalogue_dir / "ko.json", "ko")

    if not zh_entries:
        print("ERROR: no Chinese catalogue entries found — cannot flag cognates", file=sys.stderr)
        sys.exit(1)

    all_pairs: list[dict] = []
    all_other: list[dict] = []

    ja_pairs = find_cognates(zh_entries, ja_entries, "ja", args.min_similarity)
    ko_pairs = find_cognates(zh_entries, ko_entries, "ko", args.min_similarity)
    all_pairs = ja_pairs + ko_pairs
    all_other = ja_entries + ko_entries

    by_type: dict[str, int] = {"exact": 0, "similar": 0, "surface_overlap": 0}
    for p in all_pairs:
        by_type[p["match_type"]] = by_type.get(p["match_type"], 0) + 1

    print(f"Found {len(all_pairs)} cognate pairs:")
    for mt, n in by_type.items():
        print(f"  {mt:<20} {n}")

    sorted_pairs = sorted(all_pairs, key=lambda p: -p["similarity"])
    print(f"\nTop 10 by similarity:")
    for p in sorted_pairs[:10]:
        print(f"  {p['source_lang']} {p['source_ref']} ↔ zh {p['target_ref']}  ({p['match_type']}, sim={p['similarity']:.3f})")

    drift = semantic_drift_pairs(all_pairs, zh_entries, all_other)
    if drift:
        print(f"\nPairs flagged for semantic drift review ({len(drift)}):")
        for p in drift[:10]:
            print(f"  {p['source_lang']} {p['source_ref']} ↔ zh {p['target_ref']}")

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_pairs":  len(all_pairs),
        "cognates":     all_pairs,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWrote {len(all_pairs)} cognate pairs to {args.output}")


if __name__ == "__main__":
    main()
