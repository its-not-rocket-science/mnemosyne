#!/usr/bin/env python3
"""
extend_cultural_catalogue.py

Extends the Mnemosyne cultural catalogue for a given language using OpenAI.
Outputs a draft YAML file in the same schema as the existing cultural drafts,
ready for human review and promotion via promote_cultural_drafts.py.

Pipeline
--------
  1. discover  — LLM generates candidate canonical references (batched)
  2. enrich    — LLM generates source, surface patterns, metadata per entry
  3. write     — outputs draft YAML + progress file (resume-safe)

Usage
-----
    # Estimate costs before spending anything:
    python scripts/extend_cultural_catalogue.py --estimate-cost --target 150
    python scripts/extend_cultural_catalogue.py --estimate-cost --target 500 --all-languages

    # Generate a draft for Spanish (150 entries, cheap model):
    python scripts/extend_cultural_catalogue.py --language es --target 150

    # Generate with better-quality model:
    python scripts/extend_cultural_catalogue.py --language fr --target 150 --model gpt-4o

    # Resume a previously interrupted run:
    python scripts/extend_cultural_catalogue.py --language de --target 150 --resume

    # After generation, promote via existing pipeline:
    python scripts/promote_cultural_drafts.py \\
        --draft data/cultural_drafts/es_cultural_references_v1.generated.yaml \\
        --allowlist <your_allowlist.txt> \\
        --seed data/cultural_references_seed.yaml \\
        --reviewed-by <you> --reviewed-at <date>

Requirements
------------
    pip install openai python-dotenv pyyaml

Environment
-----------
    OPENAI_API_KEY  — required (or set in .env)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import unicodedata
from math import ceil
from pathlib import Path

import yaml

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from openai import OpenAI
except ImportError:
    sys.exit("ERROR: openai not installed.  Run: pip install openai")


# ---------------------------------------------------------------------------
# Pricing  ($/1M tokens, mid-2025 — verify at platform.openai.com/docs/pricing)
# ---------------------------------------------------------------------------

MODEL_PRICES: dict[str, dict[str, float]] = {
    "gpt-4o-mini":  {"input": 0.15,  "output":  0.60},   # recommended default
    "gpt-4.1-nano": {"input": 0.10,  "output":  0.40},   # cheapest OpenAI
    "gpt-4.1-mini": {"input": 0.40,  "output":  1.60},
    "gpt-4.1":      {"input": 2.00,  "output":  8.00},
    "gpt-4o":       {"input": 2.50,  "output": 10.00},
    "o4-mini":      {"input": 1.10,  "output":  4.40},
}

# Calibrated rough per-entry token budget
_DISC_IN_PER_BATCH  = 600    # discovery: input per batch of 25
_DISC_OUT_PER_BATCH = 1_400  # discovery: output per batch
_ENRICH_IN_PER_ENT  = 220    # enrichment: input per entry (inside a batch of 5)
_ENRICH_OUT_PER_ENT = 420    # enrichment: output per entry

CHEAP_ALTERNATIVES = [
    # (display name, $/1M in, $/1M out, note)
    ("Claude Haiku 4.5",         0.25,  1.25,  "Anthropic: fast, cheap, strong multilingual"),
    ("Gemini 2.0 Flash",         0.10,  0.40,  "Google: free-tier available; excellent non-Latin"),
    ("DeepSeek V3",              0.14,  0.28,  "DeepSeek: very cheap; strong on CJK and Arabic"),
    ("Llama 3.3 70B (local)",    0.00,  0.00,  "Free if self-hosted; ~40 GB VRAM or Q4 quantised"),
]


# ---------------------------------------------------------------------------
# Language names
# ---------------------------------------------------------------------------

LANGUAGE_NAMES: dict[str, str] = {
    "en":  "English",         "es":  "Spanish",        "fr":  "French",
    "de":  "German",          "it":  "Italian",         "pt":  "Portuguese",
    "ru":  "Russian",         "zh":  "Chinese",         "ja":  "Japanese",
    "ko":  "Korean",          "ar":  "Arabic",          "hi":  "Hindi",
    "la":  "Latin",           "grc": "Ancient Greek",   "tr":  "Turkish",
    "nl":  "Dutch",           "pl":  "Polish",          "sv":  "Swedish",
    "he":  "Hebrew",          "fa":  "Persian (Farsi)", "uk":  "Ukrainian",
    "cs":  "Czech",           "ro":  "Romanian",        "hu":  "Hungarian",
}


# ---------------------------------------------------------------------------
# Schema constants  (match existing draft YAML)
# ---------------------------------------------------------------------------

REFERENCE_TYPES = {
    "literary_reference",
    "classical_or_scriptural_allusion",
    "proverb_tradition",
    "cultural_reference",
}

REGISTERS = {"literary", "religious", "proverbial", "classical", "formal", "neutral"}

FIELD_ORDER = [
    "id", "language", "canonical_reference", "reference_type",
    "surface_patterns", "short_explanation", "learner_level",
    "confidence", "review_status", "register",
    "variants",
    "explanation_key", "source_work_key", "source_author_key",
    "source_work", "source_author", "source_location",
    "source_url", "source_license", "source_dataset",
    "notes",
]


# ---------------------------------------------------------------------------
# ID / key helpers
# ---------------------------------------------------------------------------

def _slug(text: str, maxlen: int = 60) -> str:
    norm = unicodedata.normalize("NFC", text).casefold()
    parts = ("".join(c if c.isalnum() else "_" for c in norm)).split("_")
    return "_".join(p for p in parts if p)[:maxlen]


def make_id(language: str, reference_type: str, canonical_reference: str) -> str:
    h = hashlib.sha256(canonical_reference.encode()).hexdigest()[:8]
    return f"{language}_{reference_type}_{_slug(canonical_reference)}_{h}"


def make_key(namespace: str, language: str, value: str, maxlen: int = 50) -> str:
    return f"mnemosyne.{language}.{namespace}.{_slug(value, maxlen)}"


# ---------------------------------------------------------------------------
# Cost helpers
# ---------------------------------------------------------------------------

def cost_usd(input_tokens: int, output_tokens: int, model: str) -> float:
    p = MODEL_PRICES.get(model, MODEL_PRICES["gpt-4o-mini"])
    return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000


def estimate_tokens(target: int, discover_batch: int = 25) -> dict[str, int]:
    n_disc = ceil(target / discover_batch)
    return {
        "input":  n_disc * _DISC_IN_PER_BATCH  + target * _ENRICH_IN_PER_ENT,
        "output": n_disc * _DISC_OUT_PER_BATCH + target * _ENRICH_OUT_PER_ENT,
    }


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def load_existing(seed_path: Path, language: str) -> set[str]:
    if not seed_path.exists():
        return set()
    with seed_path.open(encoding="utf-8") as f:
        entries = yaml.safe_load(f) or []
    return {e["canonical_reference"] for e in entries if e.get("language") == language}


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_DISCOVER_SYS = """\
You are a specialist in {lang_name} literature, cultural history, and language education.
You identify canonical cultural references: phrases, allusions, and expressions that originate
from specific literary works, religious texts, classical mythology, or landmark historical
events central to the {lang_name}-speaking cultural tradition.

Selection criteria:
  - Traceable to an identifiable source (named author, text, or named tradition)
  - Well-established (at least 50 years old, or from ancient / classical sources)
  - Recognisable to an educated {lang_name} speaker as having a specific cultural/literary origin
  - NOT everyday idioms of unknown origin
  - NOT very obscure or highly specialist references
  - Target CEFR B2–C1 cultural literacy level
  - Each reference must be distinct from the others"""

_DISCOVER_USER = """\
Generate exactly {n} canonical cultural references for {lang_name} (language code: {lang}).

Return a JSON object with key "candidates" whose value is an array of strings.
Each string is the canonical form of one reference in {lang}.
No explanations or metadata — just the strings.

Exclude anything semantically equivalent to these already-catalogued references
(show first 80 only):
{existing_sample}

Required format:
{{"candidates": ["reference 1", "reference 2", ...]}}"""

_ENRICH_SYS = """\
You are a literary scholar and language specialist for {lang_name}.
Produce accurate, sourced metadata for cultural references in JSON.

Confidence scoring:
  0.85–0.90  — unambiguous attribution to a specific text and named author
  0.75–0.84  — strong attribution with minor uncertainty
  0.60–0.74  — uncertain, disputed, or oral-tradition attribution

Do not overclaim attribution certainty."""

_ENRICH_USER = """\
Enrich the following {lang_name} cultural references with metadata.
Return a JSON object with key "entries" whose value is an array of objects (same order as input).

References to enrich:
{candidates_json}

Each object must contain:
  "canonical_reference"  — string (copy from input, unchanged)
  "reference_type"       — one of: "literary_reference", "classical_or_scriptural_allusion",
                           "proverb_tradition", "cultural_reference"
  "surface_patterns"     — array of 2–6 strings showing how this phrase appears in running text
                           (include morphological variants, with/without articles, short forms)
  "short_explanation"    — 1–2 sentences in English: meaning and cultural significance
  "learner_level"        — CEFR: "A1" | "A2" | "B1" | "B2" | "C1" | "C2"
  "confidence"           — float 0.60–0.90 per scoring guide above
  "register"             — one of: "literary" | "religious" | "proverbial" | "classical" |
                           "formal" | "neutral"
  "source_work"          — title of originating work in original language
                           (or "Various" / "Oral tradition" if genuinely uncertain)
  "source_author"        — author name, translator, or tradition
  "source_location"      — specific location (book/canto/act/verse) or null if unknown
  "source_url"           — URL to free online text (Project Gutenberg, Perseus, Wikisource) or null
  "source_license"       — "public_domain" for works >100 years old; else appropriate SPDX id
  "source_dataset_tag"   — short snake_case tag for this batch, e.g. "es_quijote_phrases",
                           "fr_classical_allusions", "de_goethe_phrases", "zh_tang_poetry"
  "variants"             — optional array of alternate surface forms worth indexing, or omit

Return ONLY a valid JSON object. No prose outside the JSON."""


# ---------------------------------------------------------------------------
# API wrapper
# ---------------------------------------------------------------------------

def _chat(
    client: OpenAI,
    system: str,
    user: str,
    model: str,
    temperature: float = 0.4,
    max_retries: int = 4,
) -> tuple[str, int, int]:
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content or ""
            u = resp.usage
            return content, u.prompt_tokens, u.completion_tokens
        except Exception as exc:
            wait = 2 ** (attempt + 1)
            print(f"\n  [retry {attempt+1}/{max_retries}] {exc} — sleeping {wait}s",
                  file=sys.stderr)
            if attempt < max_retries - 1:
                time.sleep(wait)
            else:
                raise


def _parse_list(raw: str, key: str) -> list:
    """Extract a list from a JSON object by preferred key."""
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"\n  WARNING: JSON parse error — {exc}", file=sys.stderr)
        return []
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        if key in parsed and isinstance(parsed[key], list):
            return parsed[key]
        # fallback: first list value
        for v in parsed.values():
            if isinstance(v, list):
                return v
    return []


# ---------------------------------------------------------------------------
# Phase 1: discovery
# ---------------------------------------------------------------------------

def discover_candidates(
    client: OpenAI,
    language: str,
    lang_name: str,
    n: int,
    existing: set[str],
    model: str,
    already_discovered: list[str],
) -> tuple[list[str], int, int]:
    all_known = existing | set(already_discovered)
    sample = sorted(all_known)[:80]
    sys_p = _DISCOVER_SYS.format(lang_name=lang_name)
    usr_p = _DISCOVER_USER.format(
        n=n, lang_name=lang_name, lang=language,
        existing_sample=json.dumps(sample, ensure_ascii=False),
    )
    raw, in_tok, out_tok = _chat(client, sys_p, usr_p, model, temperature=0.75)
    candidates = _parse_list(raw, "candidates")
    # keep strings only; drop already-known
    clean = [c for c in candidates if isinstance(c, str) and c not in all_known]
    return clean, in_tok, out_tok


# ---------------------------------------------------------------------------
# Phase 2: enrichment
# ---------------------------------------------------------------------------

def enrich_batch(
    client: OpenAI,
    lang_name: str,
    candidates: list[str],
    model: str,
) -> tuple[list[dict], int, int]:
    sys_p = _ENRICH_SYS.format(lang_name=lang_name)
    usr_p = _ENRICH_USER.format(
        lang_name=lang_name,
        candidates_json=json.dumps(candidates, ensure_ascii=False, indent=2),
    )
    raw, in_tok, out_tok = _chat(client, sys_p, usr_p, model, temperature=0.2)
    entries = _parse_list(raw, "entries")
    valid = [e for e in entries if isinstance(e, dict) and "canonical_reference" in e]
    return valid, in_tok, out_tok


# ---------------------------------------------------------------------------
# Build YAML entry
# ---------------------------------------------------------------------------

def build_entry(language: str, enriched: dict) -> dict:
    cr  = enriched.get("canonical_reference", "")
    rt  = enriched.get("reference_type", "cultural_reference")
    if rt not in REFERENCE_TYPES:
        rt = "cultural_reference"
    reg = enriched.get("register", "neutral")
    if reg not in REGISTERS:
        reg = "neutral"
    dataset_tag = enriched.get("source_dataset_tag", f"{language}_generated")

    entry: dict = {
        "id":                  make_id(language, rt, cr),
        "language":            language,
        "canonical_reference": cr,
        "reference_type":      rt,
        "surface_patterns":    enriched.get("surface_patterns") or [cr],
        "short_explanation":   enriched.get("short_explanation", ""),
        "learner_level":       enriched.get("learner_level", "B2"),
        "confidence":          round(float(enriched.get("confidence", 0.68)), 2),
        "review_status":       "draft",
        "register":            reg,
        "explanation_key":     make_key("explanation", language, f"{dataset_tag}.{cr}"),
        "source_work_key":     make_key("work",   language, enriched.get("source_work", "unknown")),
        "source_author_key":   make_key("author", language, enriched.get("source_author", "unknown")),
        "source_work":         enriched.get("source_work", ""),
        "source_author":       enriched.get("source_author", ""),
        "source_license":      enriched.get("source_license", "public_domain"),
        "source_dataset":      dataset_tag,
        "notes":               "AI-generated; verify attribution and surface patterns before promotion.",
    }

    # optional fields — only include when present
    variants = enriched.get("variants")
    if variants:
        entry["variants"] = variants
    loc = enriched.get("source_location")
    if loc:
        entry["source_location"] = loc
    url = enriched.get("source_url")
    if url:
        entry["source_url"] = url

    # enforce field order
    ordered: dict = {}
    for k in FIELD_ORDER:
        if k in entry:
            ordered[k] = entry[k]
    for k, v in entry.items():
        if k not in ordered:
            ordered[k] = v
    return ordered


# ---------------------------------------------------------------------------
# Progress file (resume-safe)
# ---------------------------------------------------------------------------

def _progress_path(output: Path) -> Path:
    return output.with_suffix(".progress.json")


def load_progress(output: Path) -> dict:
    p = _progress_path(output)
    if p.exists():
        with p.open(encoding="utf-8") as f:
            return json.load(f)
    return {"discovered": [], "enriched": [], "tokens_in": 0, "tokens_out": 0}


def save_progress(output: Path, state: dict) -> None:
    with _progress_path(output).open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# YAML writer
# ---------------------------------------------------------------------------

def write_yaml(entries: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(entries, f, allow_unicode=True, default_flow_style=False,
                  sort_keys=False, width=100)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run(
    language: str,
    target: int,
    model: str,
    output: Path,
    seed_path: Path,
    discover_batch: int,
    enrich_batch: int,
    resume: bool,
) -> None:
    lang_name = LANGUAGE_NAMES.get(language, language)
    existing  = load_existing(seed_path, language)
    need      = max(0, target - len(existing))

    print(f"Language        : {lang_name} ({language})")
    print(f"In seed already : {len(existing)}")
    print(f"Target          : {target}  →  need {need} new entries")
    print(f"Model           : {model}")
    print(f"Output          : {output}")

    if need == 0:
        print("Target already met — nothing to generate.")
        return

    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("ERROR: OPENAI_API_KEY not set in environment or .env")

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    state  = load_progress(output) if resume else {
        "discovered": [], "enriched": [], "tokens_in": 0, "tokens_out": 0,
    }

    enriched_refs  = {e["canonical_reference"] for e in state["enriched"]}
    to_enrich_pool = [c for c in state["discovered"] if c not in enriched_refs]

    # ---- Phase 1: discover ------------------------------------------------
    total_needed = need - len(state["enriched"])
    if total_needed > 0 and len(to_enrich_pool) < total_needed:
        still_want = total_needed - len(to_enrich_pool)
        print(f"\nPhase 1: discover {still_want} candidates  (batch={discover_batch})")
        while len(to_enrich_pool) < total_needed:
            ask = min(discover_batch, total_needed - len(to_enrich_pool) + 5)
            print(f"  → requesting {ask} …", end="", flush=True)
            cands, in_tok, out_tok = discover_candidates(
                client, language, lang_name, ask, existing, model,
                state["discovered"],
            )
            state["tokens_in"]  += in_tok
            state["tokens_out"] += out_tok
            new = [c for c in cands if c not in set(state["discovered"]) | existing]
            state["discovered"].extend(new)
            to_enrich_pool.extend(new)
            save_progress(output, state)
            c = cost_usd(state["tokens_in"], state["tokens_out"], model)
            print(f" +{len(new)} ({len(to_enrich_pool)} queued)  ${c:.4f}")
            if not new:
                print("  WARNING: no new candidates — model may be exhausted for this language")
                break
            time.sleep(0.5)

    # ---- Phase 2: enrich --------------------------------------------------
    to_enrich = to_enrich_pool[:total_needed]
    if to_enrich:
        print(f"\nPhase 2: enrich {len(to_enrich)} entries  (batch={enrich_batch})")
        for i in range(0, len(to_enrich), enrich_batch):
            batch = to_enrich[i:i + enrich_batch]
            lo, hi = i + 1, min(i + enrich_batch, len(to_enrich))
            print(f"  → {lo}–{hi} …", end="", flush=True)
            enriched, in_tok, out_tok = enrich_batch_fn(client, lang_name, batch, model)
            state["tokens_in"]  += in_tok
            state["tokens_out"] += out_tok
            state["enriched"].extend(enriched)
            save_progress(output, state)
            c = cost_usd(state["tokens_in"], state["tokens_out"], model)
            print(f" ok ({len(enriched)} entries, ${c:.4f} total)")
            time.sleep(0.3)

    # ---- Write YAML -------------------------------------------------------
    entries = [build_entry(language, e) for e in state["enriched"]]
    write_yaml(entries, output)

    total_cost = cost_usd(state["tokens_in"], state["tokens_out"], model)
    print(f"\n{'─'*60}")
    print(f"Wrote {len(entries)} draft entries → {output}")
    print(f"Tokens : {state['tokens_in']:,} in / {state['tokens_out']:,} out")
    print(f"Cost   : ${total_cost:.4f}  ({model})")
    print(f"\nNext steps:")
    print(f"  1. Review {output}")
    print(f"  2. Create an allowlist of entries you approve:")
    print(f"       data/cultural_drafts/{language}_catalogue_batch_001.txt")
    print(f"  3. Promote:")
    print(f"       python scripts/promote_cultural_drafts.py \\")
    print(f"           --draft {output} \\")
    print(f"           --allowlist data/cultural_drafts/{language}_catalogue_batch_001.txt \\")
    print(f"           --seed data/cultural_references_seed.yaml \\")
    print(f"           --reviewed-by <you> --reviewed-at <date>")

    _progress_path(output).unlink(missing_ok=True)


# name alias so both call sites work
enrich_batch_fn = enrich_batch


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------

def print_cost_estimate(target: int, languages: list[str]) -> None:
    n = len(languages)
    tok = estimate_tokens(target)
    tot_in  = tok["input"]  * n
    tot_out = tok["output"] * n

    print(f"\nCost estimate -- {target} entries x {n} language(s)  (+-30%)")
    print(f"\nOpenAI models")
    print(f"  {'Model':<20} {'$/language':>12}  {'$/all langs':>12}")
    print(f"  {'-'*48}")
    for model, prices in MODEL_PRICES.items():
        per = cost_usd(tok["input"], tok["output"], model)
        tot = cost_usd(tot_in, tot_out, model)
        print(f"  {model:<20} ${per:>10.3f}   ${tot:>10.3f}")

    print(f"\nCheaper alternatives (not OpenAI)")
    print(f"  {'Provider':<30} {'$/language':>12}  {'$/all langs':>12}  Notes")
    print(f"  {'-'*80}")
    for name, ip, op, note in CHEAP_ALTERNATIVES:
        if ip == 0:
            print(f"  {name:<30} {'free':>12}   {'free':>12}   {note}")
        else:
            per = (tok["input"] * ip + tok["output"] * op) / 1_000_000
            tot = per * n
            print(f"  {name:<30} ${per:>10.3f}   ${tot:>10.3f}   {note}")

    print(f"""
Notes
  * Token estimates: ~{tok['input']:,} in / ~{tok['output']:,} out per language
  * Discovery batch=25, enrich batch=5 (adjust with --discover-batch / --enrich-batch)
  * gpt-4o-mini recommended for drafting; gpt-4o for better source accuracy
  * Prices as of mid-2025 -- verify at platform.openai.com/docs/pricing
  * Generated YAML requires human review before promotion (same workflow as en batches)
""")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--language", "-l",
                    help="Target language code (e.g. es, fr, de, zh)")
    ap.add_argument("--target", "-t", type=int, required=True,
                    help="Target number of entries for the language")
    ap.add_argument("--model", "-m", default="gpt-4o-mini",
                    choices=list(MODEL_PRICES),
                    help="OpenAI model (default: gpt-4o-mini)")
    ap.add_argument("--output", "-o", type=Path,
                    help="Output YAML path (default: data/cultural_drafts/<lang>_cultural_references_v1.generated.yaml)")
    ap.add_argument("--seed", type=Path,
                    default=Path("data/cultural_references_seed.yaml"),
                    help="Seed YAML to exclude already-catalogued entries")
    ap.add_argument("--discover-batch", type=int, default=25,
                    help="Candidates per discovery API call (default: 25)")
    ap.add_argument("--enrich-batch", type=int, default=5,
                    help="Candidates per enrichment API call (default: 5)")
    ap.add_argument("--resume", action="store_true",
                    help="Resume from existing .progress.json")
    ap.add_argument("--estimate-cost", action="store_true",
                    help="Print cost estimate and exit — no API calls made")
    ap.add_argument("--all-languages", action="store_true",
                    help="With --estimate-cost: show totals for all supported languages")
    args = ap.parse_args()

    if args.estimate_cost:
        if args.all_languages:
            langs = list(LANGUAGE_NAMES.keys())
        elif args.language:
            langs = [args.language]
        else:
            langs = ["(one language)"]
            LANGUAGE_NAMES["(one language)"] = "(one language)"
        print_cost_estimate(args.target, langs)
        return

    if not args.language:
        ap.error("--language is required (unless --estimate-cost)")

    if args.language not in LANGUAGE_NAMES:
        print(f"Warning: '{args.language}' not in known languages — proceeding anyway",
              file=sys.stderr)
        LANGUAGE_NAMES[args.language] = args.language

    output = args.output or Path(
        f"data/cultural_drafts/{args.language}_cultural_references_v1.generated.yaml"
    )

    run(
        language=args.language,
        target=args.target,
        model=args.model,
        output=output,
        seed_path=args.seed,
        discover_batch=args.discover_batch,
        enrich_batch=args.enrich_batch,
        resume=args.resume,
    )


if __name__ == "__main__":
    main()
