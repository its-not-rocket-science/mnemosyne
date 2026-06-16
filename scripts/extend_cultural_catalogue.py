#!/usr/bin/env python3
"""
extend_cultural_catalogue.py

Extends the Mnemosyne cultural catalogue using any OpenAI-compatible API.
Outputs a draft YAML for human review, OR runs a full automated pipeline:
  discover -> enrich -> AI review -> promote -> rebuild.

Pipeline phases
---------------
  1. discover     LLM generates candidate canonical references (batched)
  2. enrich       LLM adds source, surface patterns, explanation, metadata
  3. review       second LLM call fact-checks and verdicts each entry (--auto-review)
  4. promote      approved entries appended to seed via promote_cultural_drafts.py (--auto-promote)

Usage
-----
    # Cost estimate before spending anything:
    python scripts/extend_cultural_catalogue.py --estimate-cost --target 500
    python scripts/extend_cultural_catalogue.py --estimate-cost --target 500 --all-languages

    # Generate draft for Spanish (human reviews before promoting):
    python scripts/extend_cultural_catalogue.py --language es --target 150

    # Full automated pipeline:
    python scripts/extend_cultural_catalogue.py --language es --target 150 \\
        --auto-review --auto-promote --reviewed-by "pipeline-v1"

    # Resume interrupted run:
    python scripts/extend_cultural_catalogue.py --language de --target 500 --resume

    # After manual draft generation, promote via existing workflow:
    python scripts/promote_cultural_drafts.py \\
        --draft data/cultural_drafts/es_cultural_references_v1.generated.yaml \\
        --allowlist <your_allowlist.txt> \\
        --seed data/cultural_references_seed.yaml \\
        --reviewed-by <you> --reviewed-at <date>

Provider configuration (.env or environment)
--------------------------------------------
    # Required — one of:
    CULTURAL_CATALOGUE_API_KEY=sk-...        # provider API key
    OPENAI_API_KEY=sk-...                    # fallback

    # Optional — override default (OpenAI):
    CULTURAL_CATALOGUE_BASE_URL=https://api.deepseek.com/v1
    CULTURAL_CATALOGUE_MODEL=deepseek-chat

    # Optional — use a different model for the review phase:
    CULTURAL_CATALOGUE_REVIEW_MODEL=gpt-4o-mini

    # Example: DeepSeek (cheapest non-local option):
    CULTURAL_CATALOGUE_BASE_URL=https://api.deepseek.com/v1
    CULTURAL_CATALOGUE_API_KEY=sk-...
    CULTURAL_CATALOGUE_MODEL=deepseek-chat

    # Example: Gemini via OpenAI-compatible endpoint:
    CULTURAL_CATALOGUE_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
    CULTURAL_CATALOGUE_API_KEY=AIza...
    CULTURAL_CATALOGUE_MODEL=gemini-2.0-flash

    # Example: local Ollama:
    CULTURAL_CATALOGUE_BASE_URL=http://localhost:11434/v1
    CULTURAL_CATALOGUE_API_KEY=ollama
    CULTURAL_CATALOGUE_MODEL=llama3.3:70b

Requirements
------------
    pip install openai python-dotenv pyyaml
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import unicodedata
from datetime import date
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
# Provider pricing table  ($/1M tokens, mid-2025 — verify before running)
# All marked * work via openai Python SDK with CULTURAL_CATALOGUE_BASE_URL set.
# ---------------------------------------------------------------------------

PROVIDERS: dict[str, dict] = {
    # name: {in, out, base_url, sdk_compat, note}
    "gpt-4.1-nano": {
        "in": 0.10, "out": 0.40,
        "url": "https://api.openai.com/v1", "compat": True,
        "note": "cheapest OpenAI; adequate for bulk drafting",
    },
    "gpt-4o-mini": {
        "in": 0.15, "out": 0.60,
        "url": "https://api.openai.com/v1", "compat": True,
        "note": "recommended default",
    },
    "gpt-4.1-mini": {
        "in": 0.40, "out": 1.60,
        "url": "https://api.openai.com/v1", "compat": True,
        "note": "better source accuracy",
    },
    "gpt-4.1": {
        "in": 2.00, "out": 8.00,
        "url": "https://api.openai.com/v1", "compat": True,
        "note": "best OpenAI quality; use for classical/rare languages",
    },
    "gpt-4o": {
        "in": 2.50, "out": 10.00,
        "url": "https://api.openai.com/v1", "compat": True,
        "note": "highest capability; only worthwhile for review phase",
    },
    "deepseek-chat": {
        "in": 0.14, "out": 0.28,
        "url": "https://api.deepseek.com/v1", "compat": True,
        "note": "cheapest overall; excellent CJK, Arabic, multilingual",
    },
    "deepseek-reasoner": {
        "in": 0.55, "out": 2.19,
        "url": "https://api.deepseek.com/v1", "compat": True,
        "note": "DeepSeek R1; stronger attribution but slow + costly",
    },
    "gemini-2.0-flash-lite": {
        "in": 0.025, "out": 0.075,
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/", "compat": True,
        "note": "near-free; free tier available; adequate for discovery",
    },
    "gemini-2.0-flash": {
        "in": 0.10, "out": 0.40,
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/", "compat": True,
        "note": "free tier; strong on non-Latin scripts",
    },
    "mistral-small-latest": {
        "in": 0.10, "out": 0.30,
        "url": "https://api.mistral.ai/v1", "compat": True,
        "note": "good European-language coverage",
    },
    "claude-haiku-4-5": {
        "in": 0.25, "out": 1.25,
        "url": "(requires anthropic SDK or LiteLLM proxy)", "compat": False,
        "note": "not directly OpenAI-compatible; use LiteLLM or own SDK",
    },
    "llama3.3:70b (local)": {
        "in": 0.00, "out": 0.00,
        "url": "http://localhost:11434/v1  (Ollama)", "compat": True,
        "note": "free; ~40 GB VRAM or Q4-quantised ~8 GB; no internet needed",
    },
}

# Calibrated token budgets per entry  (±30%)
_DISC_IN_PER_BATCH  = 600     # discovery input per batch of 25
_DISC_OUT_PER_BATCH = 1_400   # discovery output per batch
_ENRICH_IN_PER_ENT  = 220     # enrichment input per entry
_ENRICH_OUT_PER_ENT = 420     # enrichment output per entry
_REVIEW_IN_PER_ENT  = 360     # review input per entry (entry JSON included)
_REVIEW_OUT_PER_ENT = 90      # review output per entry (verdict + reason only)


# ---------------------------------------------------------------------------
# Language names
# ---------------------------------------------------------------------------

LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",    "es": "Spanish",    "fr": "French",
    "de": "German",     "it": "Italian",    "pt": "Portuguese",
    "ru": "Russian",    "zh": "Chinese",    "ja": "Japanese",
    "ko": "Korean",     "ar": "Arabic",     "hi": "Hindi",
    "la": "Latin",      "grc": "Ancient Greek", "tr": "Turkish",
    "nl": "Dutch",      "pl": "Polish",     "sv": "Swedish",
    "he": "Hebrew",     "fa": "Persian",    "uk": "Ukrainian",
    "cs": "Czech",      "ro": "Romanian",   "hu": "Hungarian",
}


# ---------------------------------------------------------------------------
# Schema constants (match existing draft YAML)
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
# Helpers
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


def cost_usd(input_tokens: int, output_tokens: int, model: str) -> float:
    p = PROVIDERS.get(model)
    if not p:
        # best-effort: search by prefix
        for k, v in PROVIDERS.items():
            if model.startswith(k.split("-")[0]):
                p = v
                break
    if not p:
        p = PROVIDERS["gpt-4o-mini"]
    return (input_tokens * p["in"] + output_tokens * p["out"]) / 1_000_000


def estimate_tokens(
    target: int, discover_batch: int = 25, with_review: bool = False
) -> dict[str, int]:
    n_disc = ceil(target / discover_batch)
    tok = {
        "input":  n_disc * _DISC_IN_PER_BATCH  + target * _ENRICH_IN_PER_ENT,
        "output": n_disc * _DISC_OUT_PER_BATCH + target * _ENRICH_OUT_PER_ENT,
        "review_input":  target * _REVIEW_IN_PER_ENT if with_review else 0,
        "review_output": target * _REVIEW_OUT_PER_ENT if with_review else 0,
    }
    return tok


def load_existing(seed_path: Path, language: str) -> set[str]:
    if not seed_path.exists():
        return set()
    with seed_path.open(encoding="utf-8") as f:
        entries = yaml.safe_load(f) or []
    return {e["canonical_reference"] for e in entries if e.get("language") == language}


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------

def make_client() -> OpenAI:
    api_key  = (os.environ.get("CULTURAL_CATALOGUE_API_KEY")
                or os.environ.get("OPENAI_API_KEY"))
    base_url = os.environ.get("CULTURAL_CATALOGUE_BASE_URL")  # None = use OpenAI default
    if not api_key:
        sys.exit("ERROR: set CULTURAL_CATALOGUE_API_KEY or OPENAI_API_KEY in .env")
    kwargs: dict = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def resolve_model(cli_model: str | None, env_var: str, default: str) -> str:
    return cli_model or os.environ.get(env_var) or default


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_DISCOVER_SYS = """\
You are a specialist in {lang_name} literature, cultural history, and language education.
Identify canonical cultural references: phrases, allusions, and expressions originating from
specific literary works, religious texts, classical mythology, or landmark historical events
central to the {lang_name}-speaking cultural tradition.

Criteria:
  - Traceable to an identifiable source (named author, text, or named tradition)
  - Well-established (at least 50 years old, or classical/ancient)
  - Recognisable to an educated {lang_name} speaker as having a specific cultural/literary origin
  - NOT everyday idioms of unknown origin
  - NOT very obscure or highly specialist references
  - Target CEFR B2-C1 cultural literacy level
  - Each reference must be distinct"""

_DISCOVER_USER = """\
Generate exactly {n} canonical cultural references for {lang_name} (code: {lang}).
Return a JSON object with key "candidates" whose value is a string array.
No explanations or metadata -- just the canonical phrase strings in {lang}.

Exclude equivalents of these already-catalogued references (sample):
{existing_sample}

Format: {{"candidates": ["reference 1", "reference 2", ...]}}"""

_ENRICH_SYS = """\
You are a literary scholar and language specialist for {lang_name}.
Produce accurate, sourced metadata for cultural references in JSON.

Confidence scoring:
  0.85-0.90 -- unambiguous attribution to a specific text and named author
  0.75-0.84 -- strong attribution with minor uncertainty
  0.60-0.74 -- uncertain, disputed, or oral-tradition attribution
Do not overclaim."""

_ENRICH_USER = """\
Enrich the following {lang_name} cultural references.
Return a JSON object with key "entries" containing an array (same order as input).

References:
{candidates_json}

Each object:
  "canonical_reference"  -- string (copy unchanged)
  "reference_type"       -- "literary_reference" | "classical_or_scriptural_allusion" |
                            "proverb_tradition" | "cultural_reference"
  "surface_patterns"     -- array of 2-6 strings: how phrase appears in running text
                            (include morphological variants, with/without articles, short forms)
  "short_explanation"    -- 1-2 sentences in English: meaning and cultural significance
  "learner_level"        -- "A1"|"A2"|"B1"|"B2"|"C1"|"C2"
  "confidence"           -- float 0.60-0.90
  "register"             -- "literary"|"religious"|"proverbial"|"classical"|"formal"|"neutral"
  "source_work"          -- title in original language ("Various" or "Oral tradition" if unknown)
  "source_author"        -- author or tradition
  "source_location"      -- specific location (book/canto/act/verse) or null
  "source_url"           -- URL to free text (Gutenberg, Perseus, Wikisource) or null
  "source_license"       -- "public_domain" for works >100 years old; else SPDX id
  "source_dataset_tag"   -- short snake_case batch tag, e.g. "es_quijote_phrases"
  "variants"             -- optional array of alternate surface forms, or omit

Return ONLY valid JSON, no prose."""

_REVIEW_SYS = """\
You are a strict fact-checker and literary scholar for {lang_name}.
Review cultural reference entries for accuracy before they enter an educational catalogue.
Be conservative: when in doubt, flag or reject rather than approve.

Reject if:
  - Attribution is clearly wrong or appears invented
  - Surface patterns do not match how the phrase actually appears in text
  - Confidence is significantly overclaimed for the available evidence
  - Reference is trivial, anachronistic, or inappropriate for language learners

Flag if:
  - Attribution is plausible but you are not certain
  - Surface patterns are mostly correct but need refinement
  - Confidence needs downward adjustment

Approve if:
  - Attribution is accurate and verifiable from the claimed source
  - Surface patterns correctly capture the phrase in context
  - Entry genuinely benefits advanced language learners"""

_REVIEW_USER = """\
Review the following {lang_name} cultural reference entries.
Return a JSON object with key "reviews" containing an array (same order as input).

Entries:
{entries_json}

For each:
  "canonical_reference"  -- string (copy unchanged)
  "verdict"              -- "approve" | "flag" | "reject"
  "reason"               -- one sentence explaining verdict
  "revised_confidence"   -- float or null (provide only if adjustment needed)

Return ONLY valid JSON, no prose."""


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
            msg = str(exc)
            # Some providers don't support json_object -- retry without it
            if "response_format" in msg or "json_object" in msg:
                try:
                    resp = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": system},
                            {"role": "user",   "content": user},
                        ],
                        temperature=temperature,
                    )
                    content = resp.choices[0].message.content or ""
                    u = resp.usage
                    return content, u.prompt_tokens, u.completion_tokens
                except Exception:
                    pass
            wait = 2 ** (attempt + 1)
            print(f"\n  [retry {attempt+1}/{max_retries}] {exc} -- sleeping {wait}s",
                  file=sys.stderr)
            if attempt < max_retries - 1:
                time.sleep(wait)
            else:
                raise


def _parse_list(raw: str, key: str) -> list:
    import re
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        # attempt to extract first JSON array or object from text
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            try:
                parsed = json.loads(m.group())
            except json.JSONDecodeError:
                return []
        else:
            return []
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        if key in parsed and isinstance(parsed[key], list):
            return parsed[key]
        for v in parsed.values():
            if isinstance(v, list):
                return v
    return []


# ---------------------------------------------------------------------------
# Phase 1: discover
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
    clean = [c for c in candidates if isinstance(c, str) and c.strip() and c not in all_known]
    return clean, in_tok, out_tok


# ---------------------------------------------------------------------------
# Phase 2: enrich
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
# Phase 3: AI review
# ---------------------------------------------------------------------------

def review_batch(
    client: OpenAI,
    lang_name: str,
    entries: list[dict],
    model: str,
) -> tuple[list[dict], int, int]:
    sys_p = _REVIEW_SYS.format(lang_name=lang_name)
    # send only the fields the reviewer needs (keep prompt compact)
    slim = [
        {
            "canonical_reference": e.get("canonical_reference", ""),
            "reference_type":      e.get("reference_type", ""),
            "surface_patterns":    e.get("surface_patterns", []),
            "short_explanation":   e.get("short_explanation", ""),
            "confidence":          e.get("confidence", 0.68),
            "source_work":         e.get("source_work", ""),
            "source_author":       e.get("source_author", ""),
            "source_location":     e.get("source_location"),
        }
        for e in entries
    ]
    usr_p = _REVIEW_USER.format(
        lang_name=lang_name,
        entries_json=json.dumps(slim, ensure_ascii=False, indent=2),
    )
    raw, in_tok, out_tok = _chat(client, sys_p, usr_p, model, temperature=0.1)
    reviews = _parse_list(raw, "reviews")
    valid = [r for r in reviews if isinstance(r, dict) and "canonical_reference" in r]
    return valid, in_tok, out_tok


# ---------------------------------------------------------------------------
# Phase 4: auto-promote
# ---------------------------------------------------------------------------

def auto_promote(
    draft_path: Path,
    seed_path: Path,
    approved: list[str],
    reviewed_by: str,
    promote_script: Path,
) -> tuple[int, int]:
    """Write temp allowlist, call promote script, return (promoted, refused)."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write("\n".join(approved) + "\n")
        allowlist = f.name
    try:
        result = subprocess.run(
            [
                sys.executable, str(promote_script),
                "--draft",      str(draft_path),
                "--seed",       str(seed_path),
                "--allowlist",  allowlist,
                "--reviewed-by", reviewed_by,
                "--reviewed-at", date.today().isoformat(),
                "--skip-existing",
                "--allow-missing-source-location",
                "--min-confidence", "0.60",
            ],
            capture_output=True, text=True, encoding="utf-8",
        )
        promoted = refused = 0
        for line in (result.stdout + result.stderr).splitlines():
            if "promoted:" in line:
                try:
                    promoted = int(line.split(":")[1].strip())
                except ValueError:
                    pass
            elif "refused:" in line:
                try:
                    refused = int(line.split(":")[1].strip())
                except ValueError:
                    pass
        if result.returncode != 0 and not promoted:
            print(result.stderr.strip(), file=sys.stderr)
        return promoted, refused
    finally:
        os.unlink(allowlist)


# ---------------------------------------------------------------------------
# Build YAML entry
# ---------------------------------------------------------------------------

def build_entry(language: str, enriched: dict, review: dict | None = None) -> dict:
    cr  = enriched.get("canonical_reference", "")
    rt  = enriched.get("reference_type", "cultural_reference")
    if rt not in REFERENCE_TYPES:
        rt = "cultural_reference"
    reg = enriched.get("register", "neutral")
    if reg not in REGISTERS:
        reg = "neutral"

    conf = float(enriched.get("confidence", 0.68))
    if review and review.get("revised_confidence") is not None:
        try:
            conf = float(review["revised_confidence"])
        except (ValueError, TypeError):
            pass
    conf = round(max(0.60, min(0.90, conf)), 2)

    dataset_tag = enriched.get("source_dataset_tag", f"{language}_generated")
    verdict = review.get("verdict", "draft") if review else "draft"
    review_note = (
        f" AI review: {verdict} -- {review.get('reason', '')}" if review else ""
    )

    entry: dict = {
        "id":                  make_id(language, rt, cr),
        "language":            language,
        "canonical_reference": cr,
        "reference_type":      rt,
        "surface_patterns":    enriched.get("surface_patterns") or [cr],
        "short_explanation":   enriched.get("short_explanation", ""),
        "learner_level":       enriched.get("learner_level", "B2"),
        "confidence":          conf,
        "review_status":       "draft",
        "register":            reg,
        "explanation_key":     make_key("explanation", language, f"{dataset_tag}.{cr}"),
        "source_work_key":     make_key("work",   language, enriched.get("source_work") or "unknown"),
        "source_author_key":   make_key("author", language, enriched.get("source_author") or "unknown"),
        "source_work":         enriched.get("source_work", ""),
        "source_author":       enriched.get("source_author", ""),
        "source_license":      enriched.get("source_license", "public_domain"),
        "source_dataset":      dataset_tag,
        "notes": (
            "AI-generated; verify attribution and surface patterns before promotion."
            + review_note
        ),
    }

    variants = enriched.get("variants")
    if variants:
        entry["variants"] = variants
    loc = enriched.get("source_location")
    if loc:
        entry["source_location"] = loc
    url = enriched.get("source_url")
    if url:
        entry["source_url"] = url

    ordered: dict = {}
    for k in FIELD_ORDER:
        if k in entry:
            ordered[k] = entry[k]
    for k, v in entry.items():
        if k not in ordered:
            ordered[k] = v
    return ordered


# ---------------------------------------------------------------------------
# Progress file
# ---------------------------------------------------------------------------

def _progress_path(output: Path) -> Path:
    return output.with_suffix(".progress.json")


def load_progress(output: Path) -> dict:
    p = _progress_path(output)
    if p.exists():
        with p.open(encoding="utf-8") as f:
            return json.load(f)
    return {
        "discovered": [], "enriched": [], "reviewed": [],
        "tokens_in": 0, "tokens_out": 0,
    }


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
    review_model: str,
    output: Path,
    seed_path: Path,
    discover_batch: int,
    enrich_batch_size: int,
    review_batch_size: int,
    resume: bool,
    do_review: bool,
    do_promote: bool,
    reviewed_by: str,
) -> None:
    lang_name = LANGUAGE_NAMES.get(language, language)
    existing  = load_existing(seed_path, language)
    need      = max(0, target - len(existing))

    print(f"Language     : {lang_name} ({language})")
    print(f"In seed      : {len(existing)}")
    print(f"Target       : {target}  ->  need {need} new entries")
    print(f"Model        : {model}")
    if do_review:
        print(f"Review model : {review_model}")
    print(f"Output       : {output}")
    print()

    if need == 0:
        print("Target already met.")
        return

    client = make_client()
    state  = load_progress(output) if resume else {
        "discovered": [], "enriched": [], "reviewed": [],
        "tokens_in": 0, "tokens_out": 0,
    }

    enriched_refs  = {e["canonical_reference"] for e in state["enriched"]}
    reviewed_refs  = {r["canonical_reference"] for r in state.get("reviewed", [])}

    # ---- Phase 1: discover ------------------------------------------------
    to_enrich_pool = [c for c in state["discovered"] if c not in enriched_refs]
    total_needed   = need - len(state["enriched"])

    if total_needed > 0 and len(to_enrich_pool) < total_needed:
        still_want = total_needed - len(to_enrich_pool)
        print(f"Phase 1: discover {still_want} candidates  (batch={discover_batch})")
        while len(to_enrich_pool) < total_needed:
            ask = min(discover_batch, total_needed - len(to_enrich_pool) + 5)
            print(f"  -> requesting {ask} ...", end="", flush=True)
            cands, in_t, out_t = discover_candidates(
                client, language, lang_name, ask, existing, model,
                state["discovered"],
            )
            state["tokens_in"] += in_t; state["tokens_out"] += out_t
            new = [c for c in cands if c not in set(state["discovered"]) | existing]
            state["discovered"].extend(new)
            to_enrich_pool.extend(new)
            save_progress(output, state)
            print(f" +{len(new)} ({len(to_enrich_pool)} queued)  ${cost_usd(state['tokens_in'], state['tokens_out'], model):.4f}")
            if not new:
                print("  WARNING: no new candidates returned -- model may be exhausted")
                break
            time.sleep(0.5)

    # ---- Phase 2: enrich --------------------------------------------------
    to_enrich = to_enrich_pool[:total_needed]
    if to_enrich:
        print(f"\nPhase 2: enrich {len(to_enrich)} entries  (batch={enrich_batch_size})")
        for i in range(0, len(to_enrich), enrich_batch_size):
            batch = to_enrich[i:i + enrich_batch_size]
            lo, hi = i + 1, min(i + enrich_batch_size, len(to_enrich))
            print(f"  -> {lo}-{hi} ...", end="", flush=True)
            enriched, in_t, out_t = enrich_batch(client, lang_name, batch, model)
            state["tokens_in"] += in_t; state["tokens_out"] += out_t
            state["enriched"].extend(enriched)
            save_progress(output, state)
            print(f" ok ({len(enriched)})  ${cost_usd(state['tokens_in'], state['tokens_out'], model):.4f}")
            time.sleep(0.3)

    # ---- Phase 3: AI review -----------------------------------------------
    if do_review:
        to_review = [e for e in state["enriched"] if e["canonical_reference"] not in reviewed_refs]
        if to_review:
            print(f"\nPhase 3: AI review {len(to_review)} entries  (model={review_model}, batch={review_batch_size})")
            for i in range(0, len(to_review), review_batch_size):
                batch = to_review[i:i + review_batch_size]
                lo, hi = i + 1, min(i + review_batch_size, len(to_review))
                print(f"  -> reviewing {lo}-{hi} ...", end="", flush=True)
                reviews, in_t, out_t = review_batch(client, lang_name, batch, review_model)
                state["tokens_in"] += in_t; state["tokens_out"] += out_t
                state["reviewed"].extend(reviews)
                save_progress(output, state)
                verdicts = [r.get("verdict", "?") for r in reviews]
                print(f" {verdicts}  ${cost_usd(state['tokens_in'], state['tokens_out'], model):.4f}")
                time.sleep(0.3)

    # ---- Write YAML -------------------------------------------------------
    review_map: dict[str, dict] = {
        r["canonical_reference"]: r for r in state.get("reviewed", [])
    }
    entries = [
        build_entry(language, e, review_map.get(e["canonical_reference"]))
        for e in state["enriched"]
    ]
    write_yaml(entries, output)

    # Write separate files for flagged/rejected if review ran
    if do_review and review_map:
        approved_crs = [
            r["canonical_reference"] for r in state["reviewed"] if r.get("verdict") == "approve"
        ]
        flagged = [
            build_entry(language, e, review_map.get(e["canonical_reference"]))
            for e in state["enriched"]
            if review_map.get(e["canonical_reference"], {}).get("verdict") == "flag"
        ]
        rejected = [
            {"canonical_reference": r["canonical_reference"], "reason": r.get("reason", "")}
            for r in state["reviewed"] if r.get("verdict") == "reject"
        ]
        if flagged:
            flagged_path = output.with_suffix(".flagged.yaml")
            write_yaml(flagged, flagged_path)
        if rejected:
            rejected_path = output.with_suffix(".rejected.json")
            with rejected_path.open("w", encoding="utf-8") as f:
                json.dump(rejected, f, ensure_ascii=False, indent=2)

        n_approve = len(approved_crs)
        n_flag    = len(flagged)
        n_reject  = len(rejected)
        print(f"\nReview results: {n_approve} approved, {n_flag} flagged, {n_reject} rejected")
        if flagged:
            print(f"  Flagged -> {output.with_suffix('.flagged.yaml')}")
        if rejected:
            print(f"  Rejected -> {output.with_suffix('.rejected.json')}")
    else:
        approved_crs = [e["canonical_reference"] for e in state["enriched"]]

    total_cost = cost_usd(state["tokens_in"], state["tokens_out"], model)
    print(f"\nWrote {len(entries)} draft entries -> {output}")
    print(f"Tokens : {state['tokens_in']:,} in / {state['tokens_out']:,} out")
    print(f"Cost   : ${total_cost:.4f}  ({model})")

    # ---- Phase 4: auto-promote --------------------------------------------
    if do_promote:
        if not approved_crs:
            print("\nNo approved entries to promote.")
        else:
            promote_script = Path(__file__).parent / "promote_cultural_drafts.py"
            if not promote_script.exists():
                print(f"\nERROR: promote script not found at {promote_script}", file=sys.stderr)
            else:
                print(f"\nPhase 4: promoting {len(approved_crs)} approved entries ...")
                promoted, refused = auto_promote(
                    output, seed_path, approved_crs, reviewed_by, promote_script
                )
                print(f"  Promoted: {promoted}  Refused (surface conflicts): {refused}")
                print(f"\nNext: rebuild runtime catalogue files:")
                print(f"  python scripts/build_cultural_catalog.py --write")
                print(f"  Update hardcoded counts in backend/tests/test_cultural_catalog.py")
    else:
        print(f"\nNext steps:")
        if do_review:
            print(f"  1. Review {output}  (check approved entries)")
            print(f"  2. Create allowlist and promote:")
        else:
            print(f"  1. Review {output}")
            print(f"  2. Create allowlist and promote:")
        print(f"       python scripts/promote_cultural_drafts.py \\")
        print(f"           --draft {output} \\")
        print(f"           --allowlist <your_allowlist.txt> \\")
        print(f"           --seed {seed_path} \\")
        print(f"           --reviewed-by <you> --reviewed-at <date>")
        print(f"  3. Rebuild: python scripts/build_cultural_catalog.py --write")

    _progress_path(output).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------

def print_cost_estimate(target: int, languages: list[str], with_review: bool) -> None:
    n = len(languages)
    tok   = estimate_tokens(target, with_review=with_review)
    r_tok = {
        "input":  tok["review_input"],
        "output": tok["review_output"],
    } if with_review else {"input": 0, "output": 0}

    label = f"{target} entries x {n} language(s)"
    if with_review:
        label += "  [with AI review]"
    print(f"\nCost estimate -- {label}  (+-30%)")

    def row(name: str, ip: float, op: float, compat: bool, note: str) -> None:
        base = (tok["input"] * ip + tok["output"] * op) / 1_000_000
        rev  = (r_tok["input"] * ip + r_tok["output"] * op) / 1_000_000 if with_review else 0.0
        per  = base + rev
        tot  = per * n
        c = "(SDK compat)" if compat else "(needs proxy)"
        print(f"  {name:<26} ${per:>8.3f}/lang   ${tot:>9.3f} total   {c}  {note}")

    print(f"\n  {'Model':<26} {'$/language':>12}  {'$/all':>12}   compat  notes")
    print(f"  {'-'*90}")
    for name, p in PROVIDERS.items():
        row(name, p["in"], p["out"], p["compat"], p["note"])

    tok_gen_in  = tok["input"]
    tok_gen_out = tok["output"]
    tok_rev_in  = r_tok["input"]
    tok_rev_out = r_tok["output"]
    print(f"""
Token breakdown per language (target={target}):
  Generation : ~{tok_gen_in:,} in / ~{tok_gen_out:,} out""")
    if with_review:
        print(f"  Review     : ~{tok_rev_in:,} in / ~{tok_rev_out:,} out")
    print(f"""
Recommendations:
  cheapest non-local   deepseek-chat + gemini-2.0-flash-lite (discovery only)
  best quality/cost    gpt-4o-mini (generate) + gpt-4o-mini (review)
  classical languages  gpt-4.1 -- better Latin/Greek/Sanskrit attribution
  CJK / Arabic         deepseek-chat or gemini-2.0-flash -- stronger coverage

Notes:
  * Prices as of mid-2025 -- verify at each provider's pricing page
  * Review phase adds ~{int((_REVIEW_IN_PER_ENT*target)/1000)}K in / ~{int((_REVIEW_OUT_PER_ENT*target)/1000)}K out tokens per language
  * Use --discover-batch / --enrich-batch to tune throughput vs cost
  * claude-haiku-4-5 requires LiteLLM proxy or Anthropic SDK (not openai-compat)
  * local models (Ollama) incur no API cost but require capable hardware
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
                    help="Target total entries for this language")
    ap.add_argument("--model", "-m",
                    help="Generation model (overrides CULTURAL_CATALOGUE_MODEL; "
                         "default: gpt-4o-mini)")
    ap.add_argument("--review-model",
                    help="Review model (overrides CULTURAL_CATALOGUE_REVIEW_MODEL; "
                         "default: same as --model)")
    ap.add_argument("--output", "-o", type=Path,
                    help="Output YAML path (default: data/cultural_drafts/<lang>_cultural_references_v1.generated.yaml)")
    ap.add_argument("--seed", type=Path,
                    default=Path("data/cultural_references_seed.yaml"),
                    help="Seed YAML (to exclude already-catalogued entries)")
    ap.add_argument("--discover-batch", type=int, default=25,
                    help="Candidates per discovery call (default: 25)")
    ap.add_argument("--enrich-batch", type=int, default=5,
                    help="Candidates per enrichment call (default: 5)")
    ap.add_argument("--review-batch", type=int, default=5,
                    help="Entries per review call (default: 5)")
    ap.add_argument("--resume", action="store_true",
                    help="Resume from existing .progress.json")
    ap.add_argument("--auto-review", action="store_true",
                    help="Run AI review phase after enrichment")
    ap.add_argument("--auto-promote", action="store_true",
                    help="Promote approved entries automatically (implies --auto-review)")
    ap.add_argument("--reviewed-by", default="AI-review",
                    help="reviewed_by tag for auto-promoted entries (default: AI-review)")
    ap.add_argument("--estimate-cost", action="store_true",
                    help="Print cost estimate and exit (no API calls)")
    ap.add_argument("--with-review", action="store_true",
                    help="Include review-phase tokens in --estimate-cost output")
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
        print_cost_estimate(args.target, langs, args.with_review)
        return

    if not args.language:
        ap.error("--language is required (unless --estimate-cost)")

    if args.language not in LANGUAGE_NAMES:
        print(f"Warning: '{args.language}' not in known languages -- proceeding", file=sys.stderr)
        LANGUAGE_NAMES[args.language] = args.language

    model        = resolve_model(args.model,        "CULTURAL_CATALOGUE_MODEL",        "gpt-4o-mini")
    review_model = resolve_model(args.review_model, "CULTURAL_CATALOGUE_REVIEW_MODEL", model)
    do_review    = args.auto_review or args.auto_promote
    output       = args.output or Path(
        f"data/cultural_drafts/{args.language}_cultural_references_v1.generated.yaml"
    )

    run(
        language=args.language,
        target=args.target,
        model=model,
        review_model=review_model,
        output=output,
        seed_path=args.seed,
        discover_batch=args.discover_batch,
        enrich_batch_size=args.enrich_batch,
        review_batch_size=args.review_batch,
        resume=args.resume,
        do_review=do_review,
        do_promote=args.auto_promote,
        reviewed_by=args.reviewed_by,
    )


if __name__ == "__main__":
    main()
