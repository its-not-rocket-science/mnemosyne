#!/usr/bin/env python3
"""Generate a CSV of Chinese xiēhòuyǔ (歇后语) two-part allegorical sayings.

Xiēhòuyǔ cannot be reliably sourced from Wiktionary and LLM discovery treats
them as ordinary entries, missing the canonical_form_full structure. This script
generates entries specifically, with the setup-punchline split, outputting a CSV
importable via import_cultural_sources.py.

Usage:
    python scripts/build_xiehouyu_csv.py \\
        --target 200 \\
        --model deepseek-chat \\
        --output data/cultural_sources/zh_xiehouyu.csv \\
        [--seed data/cultural_references_seed.yaml] \\
        [--estimate-cost]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import unicodedata
from math import ceil
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent
try:
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=_SCRIPT_DIR / ".env")
    load_dotenv(dotenv_path=_SCRIPT_DIR.parent / ".env")
except ImportError:
    pass

try:
    from openai import OpenAI
except ImportError:
    sys.exit("ERROR: openai not installed.  Run: pip install openai")

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

# Token budgets per batch of 15
_XI_IN_PER_BATCH  = 500
_XI_OUT_PER_BATCH = 900

_SYSTEM = (
    "You are a specialist in Chinese folk language and oral tradition. "
    "Xiēhòuyǔ (歇后语) are two-part allegorical sayings where the first part "
    "(setup) describes a scenario and the second part (punchline) gives the "
    "meaning — but the punchline is almost always implied and omitted in speech. "
    "Your task is to identify well-established xiēhòuyǔ in common use."
)

_EXPECTED_CSV_HEADER = (
    "language,surface_pattern,surface_patterns,variants,canonical_reference,reference_type,"
    "source_work,source_author,source_location,source_quote,source_note,short_explanation,"
    "explanation_key,source_work_key,source_author_key,learner_level,register,confidence,"
    "source_url,source_license,rights_basis,source_dataset,notes,"
    "subcategory,is_poetic_citation,canonical_form_full"
)

_CSV_FIELDNAMES = [f for f in _EXPECTED_CSV_HEADER.split(",")]


def make_client() -> OpenAI:
    api_key  = os.environ.get("CULTURAL_CATALOGUE_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("CULTURAL_CATALOGUE_BASE_URL")
    if not api_key:
        sys.exit("ERROR: set CULTURAL_CATALOGUE_API_KEY (or OPENAI_API_KEY) in scripts/.env")
    kwargs: dict = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def load_existing_setups(seed_path: Path) -> set[str]:
    refs: set[str] = set()
    if not seed_path.exists():
        return refs
    text = seed_path.read_text(encoding="utf-8")
    if yaml is not None:
        rows = yaml.safe_load(text) or []
    else:
        rows = []
    for e in rows:
        if isinstance(e, dict) and e.get("language") == "zh":
            refs.add(unicodedata.normalize("NFC", e.get("canonical_reference", "")).casefold())
    return refs


def _chat(client: OpenAI, system: str, user: str, model: str, max_retries: int = 4) -> tuple[str, int, int]:
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                temperature=0.6,
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content or ""
            u = resp.usage
            return content, u.prompt_tokens, u.completion_tokens
        except Exception as exc:
            if "response_format" in str(exc) or "json_object" in str(exc):
                try:
                    resp = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                        temperature=0.6,
                    )
                    content = resp.choices[0].message.content or ""
                    u = resp.usage
                    return content, u.prompt_tokens, u.completion_tokens
                except Exception:
                    pass
            wait = 4 ** (attempt + 1)
            print(f"\n  [retry {attempt+1}/{max_retries}] {exc} -- sleeping {wait}s", file=sys.stderr)
            if attempt < max_retries - 1:
                time.sleep(wait)
            else:
                raise


def generate_batch(client: OpenAI, n: int, existing_sample: list[str], model: str) -> tuple[list[dict], int, int]:
    sample_json = json.dumps(existing_sample[:40], ensure_ascii=False)
    user = (
        f"Generate exactly {n} well-established Chinese xiēhòuyǔ (歇后语).\n"
        f'Return {{"entries": [array of objects]}}.\n\n'
        f"Exclude equivalents of these already-catalogued expressions:\n{sample_json}\n\n"
        "Each object:\n"
        '  "setup"      -- the first part (what appears in speech), in Chinese\n'
        '  "punchline"  -- the second implied part, in Chinese\n'
        '  "meaning"    -- 1-2 sentences in English: what the expression means and when it is used\n'
        '  "register"   -- "common"|"informal"|"proverbial"\n'
        '  "confidence" -- float 0.60-0.85 (xiēhòuyǔ origins are often disputed)\n\n'
        "Return ONLY valid JSON."
    )
    raw, in_tok, out_tok = _chat(client, _SYSTEM, user, model)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        import re
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        parsed = json.loads(m.group()) if m else {}
    entries = parsed.get("entries", []) if isinstance(parsed, dict) else []
    return [e for e in entries if isinstance(e, dict) and e.get("setup") and e.get("punchline")], in_tok, out_tok


def estimate_cost(target: int, model: str) -> None:
    from scripts.extend_cultural_catalogue import PROVIDERS, cost_usd
    n_batches = ceil(target / 15)
    in_tok  = n_batches * _XI_IN_PER_BATCH
    out_tok = n_batches * _XI_OUT_PER_BATCH
    p = PROVIDERS.get(model)
    per_m = (in_tok * (p["in"] if p else 0.15) + out_tok * (p["out"] if p else 0.60)) / 1_000_000
    print(f"Estimate: {target} entries in ~{n_batches} batches")
    print(f"Tokens: ~{in_tok:,} in / ~{out_tok:,} out")
    print(f"Cost ({model}): ~${per_m:.4f}")


def write_csv(rows: list[dict], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as f:
        f.write("# Xiēhòuyǔ (歇后语) — Chinese two-part allegorical sayings.\n")
        f.write("# surface_pattern = spoken setup only. canonical_form_full = setup — punchline.\n")
        f.write("# Source: AI-generated; verify before promotion.\n")
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def run(target: int, model: str, output: Path, seed_path: Path) -> None:
    existing = load_existing_setups(seed_path)
    print(f"Existing zh setups in seed: {len(existing)}")
    print(f"Target: {target} entries")

    client = make_client()
    all_entries: list[dict] = []
    total_in = 0
    total_out = 0
    generated_setups: set[str] = set()

    batch_size = 15
    while len(all_entries) < target:
        still_need = target - len(all_entries)
        ask = min(batch_size, still_need + 3)
        sample = sorted(existing | generated_setups)
        print(f"  -> requesting {ask} xiēhòuyǔ ...", end="", flush=True)
        batch, in_t, out_t = generate_batch(client, ask, sample, model)
        total_in += in_t
        total_out += out_t

        new = 0
        for e in batch:
            key = unicodedata.normalize("NFC", e["setup"]).casefold()
            if key in existing or key in generated_setups:
                continue
            generated_setups.add(key)
            all_entries.append(e)
            new += 1
            if len(all_entries) >= target:
                break

        cost = (total_in * 0.14 + total_out * 0.28) / 1_000_000
        print(f" +{new} ({len(all_entries)}/{target})  ${cost:.4f}")
        time.sleep(0.3)

    rows: list[dict] = []
    for e in all_entries[:target]:
        setup    = e["setup"].strip()
        punchline = e["punchline"].strip()
        rows.append({
            "language":            "zh",
            "surface_pattern":     setup,
            "surface_patterns":    "",
            "variants":            "",
            "canonical_reference": setup,
            "reference_type":      "proverb_tradition",
            "source_work":         "Chinese oral tradition",
            "source_author":       "Folk/oral tradition",
            "source_location":     "",
            "source_quote":        "",
            "source_note":         "",
            "short_explanation":   e.get("meaning", ""),
            "explanation_key":     "",
            "source_work_key":     "",
            "source_author_key":   "",
            "learner_level":       "B2",
            "register":            e.get("register", "common"),
            "confidence":          str(round(float(e.get("confidence", 0.70)), 2)),
            "source_url":          "",
            "source_license":      "not_required",
            "rights_basis":        "common_usage_short_expression",
            "source_dataset":      "zh_xiehouyu_generated",
            "notes":               f"Xiēhòuyǔ: setup only in surface_patterns; full form in canonical_form_full. Punchline: {punchline}",
            "subcategory":         "xiehouyu",
            "is_poetic_citation":  "false",
            "canonical_form_full": f"{setup} — {punchline}",
        })

    write_csv(rows, output)
    total_cost = (total_in * 0.14 + total_out * 0.28) / 1_000_000
    print(f"\nWrote {len(rows)} xiēhòuyǔ entries to {output}")
    print(f"Tokens: {total_in:,} in / {total_out:,} out")
    print(f"Cost: ${total_cost:.4f}  ({model})")
    print(f"\nNext: python scripts/import_cultural_sources.py --source {output} --out data/cultural_drafts/zh_xiehouyu.yaml")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target",   "-t", type=int, required=True, help="Number of xiēhòuyǔ to generate")
    ap.add_argument("--model",    "-m", default="deepseek-chat", help="LLM model (default: deepseek-chat)")
    ap.add_argument("--output",   "-o", type=Path, default=Path("data/cultural_sources/zh_xiehouyu.csv"))
    ap.add_argument("--seed",     type=Path, default=Path("data/cultural_references_seed.yaml"))
    ap.add_argument("--estimate-cost", action="store_true", help="Print cost estimate and exit")
    args = ap.parse_args()

    if args.estimate_cost:
        estimate_cost(args.target, args.model)
        return

    run(args.target, args.model, args.output, args.seed)


if __name__ == "__main__":
    main()
