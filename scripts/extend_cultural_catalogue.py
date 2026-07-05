#!/usr/bin/env python3
"""
extend_cultural_catalogue.py

Extends the Mnemosyne cultural catalogue using any OpenAI-compatible API.
Never overwrites existing entries in the seed or an existing draft YAML.

Pipeline phases
---------------
  1. discover     LLM generates candidate canonical references (batched)
  2. enrich       LLM adds source, surface patterns, explanation, metadata
  3. i18n         LLM translates short_explanation into 11 UI languages (--with-i18n)
  4. review       second LLM call fact-checks each entry (--auto-review)
  5. promote      approved entries appended to seed (--auto-promote)

See scripts/.env.example for full provider setup and usage instructions.

Requirements: pip install openai python-dotenv pyyaml
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

# Load from scripts/.env first, then fall back to project-root .env
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


# ---------------------------------------------------------------------------
# Provider pricing  ($/1M tokens, mid-2025 — verify before running)
# ---------------------------------------------------------------------------

PROVIDERS: dict[str, dict] = {
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
        "note": "best for classical / rare languages",
    },
    "gpt-4o": {
        "in": 2.50, "out": 10.00,
        "url": "https://api.openai.com/v1", "compat": True,
        "note": "highest capability; only worthwhile for review",
    },
    "deepseek-chat": {
        "in": 0.14, "out": 0.28,
        "url": "https://api.deepseek.com/v1", "compat": True,
        "note": "cheapest overall; excellent CJK, Arabic, multilingual",
    },
    "deepseek-reasoner": {
        "in": 0.55, "out": 2.19,
        "url": "https://api.deepseek.com/v1", "compat": True,
        "note": "DeepSeek R1; strongest attribution but slow",
    },
    "gemini-2.0-flash-lite": {
        "in": 0.025, "out": 0.075,
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/", "compat": True,
        "note": "near-free; free tier; adequate for discovery only",
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
        "url": "(requires LiteLLM proxy)", "compat": False,
        "note": "not OpenAI-compatible natively; use LiteLLM or Anthropic SDK",
    },
    "llama3.3:70b (local)": {
        "in": 0.00, "out": 0.00,
        "url": "http://localhost:11434/v1  (Ollama)", "compat": True,
        "note": "free; ~40 GB VRAM or Q4-quantised ~8 GB",
    },
}

# Token budgets per entry  (±30%)
_DISC_IN_PER_BATCH  = 600     # discovery input per batch of 25
_DISC_OUT_PER_BATCH = 1_400
_ENRICH_IN_PER_ENT  = 220     # enrichment per entry
_ENRICH_OUT_PER_ENT = 650    # calibrated for languages with 4-10 surface_pattern variants
_I18N_IN_PER_ENT    = 250     # i18n translation per entry (11 UI languages)
_I18N_OUT_PER_ENT   = 450     # ~11 langs × ~40 tokens each
_REVIEW_IN_PER_ENT  = 360     # review per entry
_REVIEW_OUT_PER_ENT = 90


# ---------------------------------------------------------------------------
# UI languages  (must match frontend/js/i18n.js UI_LANGUAGES)
# ---------------------------------------------------------------------------

UI_LANGUAGES = ["en", "es", "fr", "de", "it", "pt", "ru", "ja", "zh", "ar", "he"]

LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",    "es": "Spanish",    "fr": "French",
    "de": "German",     "it": "Italian",    "pt": "Portuguese",
    "ru": "Russian",    "zh": "Chinese",    "ja": "Japanese",
    "ko": "Korean",     "ar": "Arabic",     "hi": "Hindi",
    "la": "Latin",      "grc": "Ancient Greek", "tr": "Turkish",
    "nl": "Dutch",      "pl": "Polish",     "sv": "Swedish",
    "he": "Hebrew",     "fa": "Persian",    "uk": "Ukrainian",
    "cs": "Czech",      "ro": "Romanian",   "hu": "Hungarian",
    "fi": "Finnish",
}

# A single open-ended "give me N more not already in this list" discover
# prompt reliably plateaus well under most languages' real corpus size --
# the model converges on its single most-salient cluster of answers and
# starts repeating itself. Cycling through these themes resets what's
# "salient" each round and forces exploration of different knowledge
# clusters instead.
DISCOVERY_THEMES = [
    "classical/ancient literature and poetry",
    "historical figures and landmark events",
    "religious or scriptural texts and traditions",
    "mythology and folklore",
    "proverbs and oral tradition",
    "modern literature (20th century onward)",
    "theatre, opera, and performing arts",
    "philosophy and classical thought",
    "art, music, and visual culture",
    "idiomatic expressions tied to a specific named source",
]

# Theme rotation for --mode idiom (everyday expressions of any/unknown
# origin, as opposed to DISCOVERY_THEMES' literary/traceable focus above).
IDIOM_DISCOVERY_THEMES = [
    "body parts and physical actions (hand, foot, eye, heart, back, face)",
    "animals and nature (dog, cat, horse, bird, fish, rain, sun, wind)",
    "food and drink (bread, water, salt, cake, soup, coffee)",
    "time and speed (fast, slow, early, late, time, moment)",
    "money and value (cost, price, pay, earn, spend, cheap, expensive)",
    "success and failure (win, lose, fall, rise, pass, fail)",
    "communication and honesty (say, speak, lie, truth, secret, promise)",
    "emotions and mental states (anger, fear, love, worry, calm, surprise)",
    "work and effort (hard work, lazy, busy, tired, effort, task)",
    "relationships and social situations (friend, enemy, trust, betray, help)",
]


# Subcategories where AI review is insufficient and human/native review
# is required before promotion to seed.
NATIVE_REVIEW_REQUIRED_SUBCATEGORIES = {
    "hadith",       # Attribution to specific hadith collection needs verification
    "filmi",        # Modern Bollywood/film dialogue has active copyright
    "modern_media", # Modern Arabic TV/cinema has active copyright
    "pansori",      # Regional oral tradition; attribution is often contested
}

# ---------------------------------------------------------------------------
# Schema constants
# ---------------------------------------------------------------------------

REFERENCE_TYPES = {
    "literary_reference", "classical_or_scriptural_allusion",
    "proverb_tradition", "cultural_reference",
}
REGISTERS = {"common", "literary", "formal", "informal", "religious", "classical", "proverbial"}
KNOWN_SOURCE_LICENSES = {
    "public_domain", "not_required", "CC0", "CC0-1.0", "CC-BY-4.0", "CC-BY-SA-4.0",
    "copyright_or_rights_review_needed", "common_usage_short_expression",
}
# Languages where 2-4 character surface patterns are normal citation length,
# not ambiguous fragments. CJK characters carry full semantic weight at short
# lengths; Arabic/Persian/Hebrew roots do the same in Semitic script;
# Hindi sacred-text citations are typically 1-3 words in Devanagari.
SHORT_PATTERN_OK_LANGUAGES = {"zh", "ja", "ko", "he", "ar", "fa", "hi"}

FIELD_ORDER = [
    "id", "language", "canonical_reference", "reference_type",
    "surface_patterns", "short_explanation", "i18n_explanations",
    "learner_level", "confidence", "review_status", "register",
    "subcategory", "is_poetic_citation",
    "allow_short_pattern", "variants", "canonical_form_full",
    "explanation_key", "source_work_key", "source_author_key",
    "source_work", "source_author", "source_location",
    "source_url", "source_license", "rights_basis", "source_dataset",
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
        for k, v in PROVIDERS.items():
            if model.split("-")[0] in k:
                p = v
                break
    if not p:
        p = PROVIDERS["gpt-4o-mini"]
    return (input_tokens * p["in"] + output_tokens * p["out"]) / 1_000_000


def estimate_tokens(
    target: int,
    discover_batch: int = 25,
    with_i18n: bool = False,
    with_review: bool = False,
) -> dict[str, int]:
    n_disc = ceil(target / discover_batch)
    tok = {
        "disc_in":   n_disc * _DISC_IN_PER_BATCH,
        "disc_out":  n_disc * _DISC_OUT_PER_BATCH,
        "enrich_in":  target * _ENRICH_IN_PER_ENT,
        "enrich_out": target * _ENRICH_OUT_PER_ENT,
        "i18n_in":    target * _I18N_IN_PER_ENT    if with_i18n   else 0,
        "i18n_out":   target * _I18N_OUT_PER_ENT   if with_i18n   else 0,
        "review_in":  target * _REVIEW_IN_PER_ENT  if with_review else 0,
        "review_out": target * _REVIEW_OUT_PER_ENT if with_review else 0,
    }
    tok["total_in"]  = tok["disc_in"]  + tok["enrich_in"]  + tok["i18n_in"]  + tok["review_in"]
    tok["total_out"] = tok["disc_out"] + tok["enrich_out"] + tok["i18n_out"] + tok["review_out"]
    return tok


def load_existing(seed_path: Path, language: str, extra_yaml: Path | None = None) -> set[str]:
    """Canonical references already in seed OR in an existing draft YAML."""
    refs: set[str] = set()
    if seed_path.exists():
        with seed_path.open(encoding="utf-8") as f:
            for e in (yaml.safe_load(f) or []):
                if isinstance(e, dict) and e.get("language") == language:
                    refs.add(e["canonical_reference"])
    if extra_yaml and extra_yaml.exists():
        try:
            with extra_yaml.open(encoding="utf-8") as f:
                for e in (yaml.safe_load(f) or []):
                    if isinstance(e, dict) and e.get("canonical_reference"):
                        refs.add(e["canonical_reference"])
        except Exception:
            pass
    return refs


# ---------------------------------------------------------------------------
# Client factory
# ---------------------------------------------------------------------------

def _provider_url(model: str) -> str | None:
    """Return the API base URL for a known model, or None for OpenAI default."""
    entry = PROVIDERS.get(model, {})
    url = entry.get("url", "")
    if url.startswith("http"):
        return url
    return None


def make_client(model: str = "") -> OpenAI:
    api_key  = os.environ.get("CULTURAL_CATALOGUE_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("CULTURAL_CATALOGUE_BASE_URL") or _provider_url(model)
    if not api_key:
        sys.exit("ERROR: set CULTURAL_CATALOGUE_API_KEY (or OPENAI_API_KEY) in scripts/.env")
    kwargs: dict = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def make_review_client(model: str = "") -> OpenAI:
    """Review can run against a different provider than generation (e.g.
    Mistral for discover/enrich breadth, DeepSeek for review judgment) by
    setting CULTURAL_CATALOGUE_REVIEW_API_KEY / _BASE_URL. Falls back to
    the main client's credentials when unset."""
    api_key = os.environ.get("CULTURAL_CATALOGUE_REVIEW_API_KEY")
    base_url = os.environ.get("CULTURAL_CATALOGUE_REVIEW_BASE_URL") or _provider_url(model)
    if not api_key and not base_url:
        return make_client(model)
    api_key = api_key or os.environ.get("CULTURAL_CATALOGUE_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit("ERROR: set CULTURAL_CATALOGUE_REVIEW_API_KEY (or CULTURAL_CATALOGUE_API_KEY) in scripts/.env")
    kwargs: dict = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def resolve_model(cli_val: str | None, env_var: str, default: str) -> str:
    return cli_val or os.environ.get(env_var) or default


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
  - Recognisable to educated {lang_name} speakers as having a specific cultural/literary origin
  - NOT everyday idioms of unknown origin; NOT highly specialist references
  - Target CEFR B2-C1 cultural literacy level; each reference must be distinct"""

_DISCOVER_USER = """\
Generate exactly {n} canonical cultural references for {lang_name} (code: {lang}).{theme_clause}
Return {{"candidates": [array of strings]}} -- canonical phrase strings in {lang} only, no metadata.

Exclude equivalents of these already-catalogued references (sample of {nexist}):
{existing_sample}

Format: {{"candidates": ["reference 1", "reference 2", ...]}}"""

_ENRICH_SYS = """\
You are a literary scholar and language specialist for {lang_name}.
Produce accurate, sourced metadata for cultural references in JSON.

Confidence: 0.85-0.90 = unambiguous attribution to specific text + author;
0.75-0.84 = strong with minor uncertainty; 0.60-0.74 = uncertain/disputed/oral.
Do not overclaim."""

_ENRICH_USER = """\
Enrich the following {lang_name} cultural references.
Return {{"entries": [array of objects, same order as input]}}.

References: {candidates_json}

Each object:
  "canonical_reference"  -- string (copy unchanged)
  "reference_type"       -- "literary_reference"|"classical_or_scriptural_allusion"|
                            "proverb_tradition"|"cultural_reference"
  "surface_patterns"     -- {variant_instruction}
  "short_explanation"    -- 1-2 sentences English: meaning and cultural significance
  "learner_level"        -- "A1"|"A2"|"B1"|"B2"|"C1"|"C2"
  "confidence"           -- float 0.60-0.90
  "register"             -- "common"|"literary"|"religious"|"proverbial"|"classical"|"formal"|"informal"
  "subcategory"          -- most specific classification within this language's
                            idiom ecology. Use exactly one value from:
                            chengyu, xiehouyu, suyv, yanyu (Chinese);
                            quranic, hadith, muallaqat, abbasid, modern_media (Arabic);
                            shahnameh, hafez, rumi, saadi, khayyam,
                            persian_proverb (Persian);
                            yojijukugo, kanyoku, kotowaza, zen_koan (Japanese);
                            sajaseong_eo, pansori, sijo, korean_proverb (Korean);
                            doha_kabir, doha_rahim, ramcharitmanas, bhagavad_gita,
                            panchatantra, filmi, hindi_muhavare, hindi_lokokti (Hindi);
                            biblical, shakespearean, latin_tag, greek_tag,
                            literary_allusion, proverb (all other languages).
                            Omit if none apply.
  "is_poetic_citation"   -- true if this entry is a verbatim quotation from a
                            named classical poem or scripture; false or omit
                            otherwise. Arabic Quranic entries are always true.
                            Persian hemistich entries from named poets are always
                            true. Hindi doha entries from named saint-poets are
                            always true.
  "source_work"          -- title in original language ("Various"/"Oral tradition" if unknown)
  "source_author"        -- author or tradition
  "source_location"      -- location (book/act/verse) or null
  "source_url"           -- URL to free text (Gutenberg/Perseus/Wikisource) or null
  "source_license"       -- one of: "public_domain" (>100yr old works),
                            "CC0"|"CC0-1.0", "CC-BY-4.0", "not_required" (common
                            short expression, no quoted text), or
                            "copyright_or_rights_review_needed" (modern in-copyright
                            work, or any uncertainty) -- use no other value
  "source_dataset_tag"   -- snake_case batch tag e.g. "es_quijote_phrases"
  "variants"             -- optional alternate surface forms or omit
  "canonical_form_full"  -- for Chinese xiēhòuyǔ (歇后语) entries ONLY: the
                            complete two-part form including the implied punchline,
                            formatted as "setup — punchline". The canonical_reference
                            and surface_patterns should contain only the setup
                            (first part), which is what appears in speech.
                            Example: if canonical_reference is "骑驴看唱本",
                            canonical_form_full is "骑驴看唱本 — 走着瞧".
                            Omit for all non-xiēhòuyǔ entries.

Return ONLY valid JSON."""

# Per-language additions to the surface_patterns field instruction in
# _ENRICH_USER. Morphologically rich languages need far more than the 2-6
# variants that suffice for English/fixed-form languages (Latin, Koine Greek,
# chéngyǔ, yojijukugo) — without them the backend NLP matcher misses most
# real-text occurrences of an idiom even when it's in the catalogue.
_ENRICH_VARIANT_ADDENDUM: dict[str, str] = {
    # Arabic: article attachment, case endings, clitic pronouns, no-vowel form
    "ar": (
        "For Arabic entries, surface_patterns MUST include: "
        "(1) the form without tashkeel (vowel marks), "
        "(2) the form with definite article ال attached where natural, "
        "(3) at least one form with a clitic pronoun (ـه، ـها، ـك) if the "
        "phrase takes one, (4) both MSA and common colloquial form if they differ. "
        "Aim for 4-8 patterns. Do NOT include fully vowelled and unvowelled "
        "versions as separate patterns — prefer the unvowelled form only."
    ),
    # Persian: ezafe, verb conjugation, colloquial contraction, poetic citation rules
    "fa": (
        "For Persian entries sourced from classical poetry (Hafez Divan, Rumi "
        "Masnavi, Saadi Golestan/Bustan, Ferdowsi Shahnameh, Omar Khayyam "
        "Rubaiyat): list the complete hemistich (half-line of verse) as the "
        "FIRST surface pattern. Do NOT generate truncated or shortened variants "
        "of poetic hemistichs — Persian citations are quoted verbatim or not at "
        "all. The second surface pattern should be the full couplet (bayt) where "
        "both hemistichs are sometimes quoted together. Add colloquial and "
        "non-poetic idioms normally (4-8 patterns with verb conjugations). "
        "Set is_poetic_citation: true for any entry whose canonical_reference "
        "is a direct quotation from a named classical poem. "
        "For Shahnameh entries, source_location must name the dastan "
        "(story/section) e.g. 'داستان سیاوش' not just a line number."
    ),
    # Russian: aspect pairs, key conjugations, short-form adjectives
    "ru": (
        "For Russian entries, surface_patterns MUST include: "
        "(1) imperfective and perfective aspect forms if the phrase contains "
        "a verb (e.g. идти на попятную AND пойти на попятную), "
        "(2) at least past tense and infinitive forms, "
        "(3) instrumental and genitive case variants if the phrase contains "
        "a noun that case-marks in usage. "
        "Aim for 5-10 patterns for verb-containing idioms."
    ),
    # Turkish: key case suffixes, possessed forms
    "tr": (
        "For Turkish entries, surface_patterns MUST include: "
        "(1) nominative base form, "
        "(2) accusative (-ı/-i/-u/-ü) form if the phrase takes a direct object, "
        "(3) locative (-da/-de/-ta/-te) and ablative (-dan/-den/-tan/-ten) "
        "if the idiom uses these cases, "
        "(4) 3rd person possessed form (-ı/-i suffix on noun) if natural. "
        "Aim for 4-8 patterns."
    ),
    # Japanese: conjugation forms for kanyōku verbs
    "ja": (
        "For Japanese entries, surface_patterns MUST include verb conjugation "
        "forms for kanyōku (慣用句): "
        "(1) dictionary form (する), "
        "(2) te-form (して), "
        "(3) ta-form (した), "
        "(4) negative (しない), "
        "(5) potential (できる) if naturally used. "
        "For yojijukugo (四字熟語) the form is fixed — 2-3 patterns suffice "
        "(with and without の/する). "
        "Aim for 4-8 patterns for kanyōku; 2-4 for yojijukugo."
    ),
    # Hindi: postposition variants, verb agreement forms, poetic citation rules
    "hi": (
        "For Hindi entries in doha format (Kabir, Rahim, Surdas, Mirabai, "
        "Tulsidas Ramcharitmanas): list the complete first line of the doha as "
        "the FIRST surface pattern. Do NOT truncate doha-format entries. The "
        "second surface pattern should be the full doha (both lines) where "
        "both are commonly quoted together. For Ramcharitmanas entries, "
        "source_location must name the kand (book: Bal Kand, Ayodhya Kand, "
        "Aranya Kand, Kishkindha Kand, Sundar Kand, Lanka Kand, Uttar Kand) "
        "and chaupai number where known. Set is_poetic_citation: true for any "
        "entry that is a direct doha or chaupai quotation. "
        "For muhavare (idiomatic phrases) and lokokti (proverbs), generate "
        "normally: 4-8 patterns with postposition and verb conjugation variants."
    ),
    # Korean: verb ending variants, topic/subject marker variants
    "ko": (
        "For Korean entries, surface_patterns MUST include: "
        "(1) the base form, "
        "(2) key verb ending variants (아/어서, 는, ㄴ, 았/었) for verb-final "
        "idiomatic expressions, "
        "(3) topic marker (은/는) and subject marker (이/가) variants if "
        "the idiom head noun takes them in usage. "
        "Aim for 3-6 patterns."
    ),
}

_I18N_SYS = """\
You are a professional literary translator.
Translate short cultural-reference explanations into multiple languages.
Preserve meaning, register, and conciseness. Use conventional target-language
terms for cultural concepts. 1-2 sentences maximum per translation."""

_I18N_USER = """\
Translate the short_explanation of each entry into all 11 UI languages.
Return {{"translations": [array of objects, same order as input]}}.

Entries: {entries_json}

Each object:
  "canonical_reference" -- string (copy unchanged)
  "i18n_explanations"   -- object with keys: en, es, fr, de, it, pt, ru, ja, zh, ar, he
                           "en": keep original unchanged
                           "es": Spanish
                           "fr": French
                           "de": German
                           "it": Italian
                           "pt": Brazilian Portuguese
                           "ru": Russian
                           "ja": Japanese
                           "zh": Simplified Chinese
                           "ar": Modern Standard Arabic
                           "he": Hebrew

Return ONLY valid JSON."""

_REVIEW_SYS = """\
You are a strict fact-checker and literary scholar for {lang_name}.
Review cultural reference entries for accuracy before they enter an educational catalogue.
Be conservative: when in doubt, flag or reject rather than approve.

Reject: attribution clearly wrong/invented; surface patterns don't match text; confidence
significantly overclaimed; reference trivial/anachronistic/inappropriate.
Flag: attribution plausible but uncertain; surface patterns need refinement.
Approve: attribution accurate+verifiable; surface patterns correct; genuinely useful for learners."""

_REVIEW_USER = """\
Review the following {lang_name} entries.
Return {{"reviews": [array of objects, same order as input]}}.

Entries: {entries_json}

Each object:
  "canonical_reference"  -- string (copy unchanged)
  "verdict"              -- "approve"|"flag"|"reject"
  "reason"               -- one sentence
  "revised_confidence"   -- float or null

Return ONLY valid JSON."""

# ---------------------------------------------------------------------------
# Idiom-mode prompts (--mode idiom) — everyday idiomatic expressions of any
# origin, as opposed to the literary/classical references the prompts above
# target. The review and i18n phases (_REVIEW_SYS/_REVIEW_USER/_I18N_SYS/
# _I18N_USER above) are mode-agnostic and shared between both modes.
# ---------------------------------------------------------------------------

_DISCOVER_IDIOM_SYS = """\
You are a language specialist and lexicographer for {lang_name}.
Identify established idiomatic expressions: fixed phrases used figuratively
whose combined meaning cannot be derived from the individual words.

Criteria:
  - In common use for at least 30 years (well-established, not slang)
  - Used figuratively: meaning is NOT literal
  - Fixed or near-fixed form: the phrase is recognisable as a set expression
  - Origin may be unknown, folk etymology, or disputed — that is fine
  - Recognisable to any adult {lang_name} speaker without specialist education
  - NOT proverbs (complete sentences of wisdom), NOT single-word slang
  - Target CEFR B1-B2: phrases a learner at intermediate level must know"""

_DISCOVER_IDIOM_USER = """\
Generate exactly {n} established {lang_name} idiomatic expressions.{theme_clause}
Return {{"candidates": [array of strings]}} -- phrases in {lang} only, no metadata.

Each phrase must be a fixed idiomatic expression used figuratively, NOT a
literary quotation or proverb. Body-part idioms, animal idioms, colour idioms,
weather idioms, and idioms from everyday activities are all in scope.

Exclude equivalents of these already-catalogued expressions (sample of {nexist}):
{existing_sample}

Format: {{"candidates": ["expression 1", "expression 2", ...]}}"""

_ENRICH_IDIOM_SYS = """\
You are a lexicographer and language specialist for {lang_name}.
Produce accurate metadata for idiomatic expressions in JSON.

Confidence for idioms: 0.85-0.90 = meaning universally agreed, widely attested;
0.75-0.84 = well-established with minor regional variation;
0.60-0.74 = regional or register-restricted use.
Do not attempt to assign a specific literary source to idioms of unknown origin —
use source_work: "Unknown origin" and source_author: "Folk/oral tradition"."""

_ENRICH_IDIOM_USER = """\
Enrich the following {lang_name} idiomatic expressions.
Return {{"entries": [array of objects, same order as input]}}.

Expressions: {candidates_json}

Each object:
  "canonical_reference"  -- the most common/dictionary form of the idiom
  "reference_type"       -- always "cultural_reference" for idioms
  "surface_patterns"     -- array 4-8: the phrase as it appears in text
                            (different verb forms, with/without articles,
                            common shortened forms, regional variants)
  "short_explanation"    -- 1-2 sentences: literal meaning, then figurative
                            meaning and when it is used
  "learner_level"        -- "A2"|"B1"|"B2"|"C1" (most common idioms are B1-B2)
  "confidence"           -- float 0.60-0.90
  "register"             -- "common"|"informal"|"formal"|"proverbial"
  "source_work"          -- "Unknown origin" OR specific source if traceable
  "source_author"        -- "Folk/oral tradition" OR specific author
  "source_location"      -- null for unknown-origin idioms
  "source_license"       -- "not_required" (short expressions, no quoted text)
  "rights_basis"         -- "common_usage_short_expression"
  "source_dataset_tag"   -- snake_case e.g. "en_everyday_idioms"
  "variants"             -- optional alternate surface forms or omit

Return ONLY valid JSON."""


# ---------------------------------------------------------------------------
# API wrapper
# ---------------------------------------------------------------------------

def _chat(
    client: OpenAI, system: str, user: str, model: str,
    temperature: float = 0.4, max_retries: int = 4,
) -> tuple[str, int, int]:
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system},
                          {"role": "user",   "content": user}],
                temperature=temperature,
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
                        messages=[{"role": "system", "content": system},
                                  {"role": "user",   "content": user}],
                        temperature=temperature,
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


def _parse_list(raw: str, key: str) -> list:
    import re
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
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
    client: OpenAI, language: str, lang_name: str, n: int,
    existing: set[str], model: str, already_discovered: list[str],
    theme: str | None = None,
    sys_tmpl: str = _DISCOVER_SYS, user_tmpl: str = _DISCOVER_USER,
) -> tuple[list[str], int, int]:
    all_known = existing | set(already_discovered)
    sample = sorted(all_known)[:80]
    sys_p = sys_tmpl.format(lang_name=lang_name)
    theme_clause = f" Focus specifically on this theme: {theme}." if theme else ""
    usr_p = user_tmpl.format(
        n=n, lang_name=lang_name, lang=language, theme_clause=theme_clause,
        nexist=len(sample),
        existing_sample=json.dumps(sample, ensure_ascii=False),
    )
    raw, in_tok, out_tok = _chat(client, sys_p, usr_p, model, temperature=0.75)
    candidates = _parse_list(raw, "candidates")
    return [c for c in candidates if isinstance(c, str) and c.strip() and c not in all_known], in_tok, out_tok


# ---------------------------------------------------------------------------
# Phase 2: enrich
# ---------------------------------------------------------------------------

def enrich_batch(
    client: OpenAI, lang_name: str, candidates: list[str], model: str,
    language: str = "",
    sys_tmpl: str = _ENRICH_SYS, user_tmpl: str = _ENRICH_USER,
) -> tuple[list[dict], int, int]:
    # variant_instruction is only referenced by the literary template
    # (_ENRICH_USER); passed unconditionally since str.format() ignores
    # extra kwargs the idiom template (_ENRICH_IDIOM_USER) doesn't reference.
    variant_addendum = _ENRICH_VARIANT_ADDENDUM.get(language, "")
    if variant_addendum:
        variant_instruction = f"array 4-10: {variant_addendum}"
    else:
        variant_instruction = "array 2-6: how phrase appears in running text (variants, with/without articles, short forms)"
    sys_p = sys_tmpl.format(lang_name=lang_name)
    usr_p = user_tmpl.format(
        lang_name=lang_name,
        candidates_json=json.dumps(candidates, ensure_ascii=False, indent=2),
        variant_instruction=variant_instruction,
    )
    raw, in_tok, out_tok = _chat(client, sys_p, usr_p, model, temperature=0.2)
    entries = _parse_list(raw, "entries")
    return [e for e in entries if isinstance(e, dict) and "canonical_reference" in e], in_tok, out_tok


# ---------------------------------------------------------------------------
# Phase 3: i18n translations
# ---------------------------------------------------------------------------

def i18n_batch(
    client: OpenAI, entries: list[dict], model: str,
) -> tuple[list[dict], int, int]:
    slim = [{"canonical_reference": e.get("canonical_reference", ""),
             "short_explanation":   e.get("short_explanation", "")}
            for e in entries]
    sys_p = _I18N_SYS
    usr_p = _I18N_USER.format(entries_json=json.dumps(slim, ensure_ascii=False, indent=2))
    raw, in_tok, out_tok = _chat(client, sys_p, usr_p, model, temperature=0.1)
    results = _parse_list(raw, "translations")
    return [r for r in results if isinstance(r, dict) and "canonical_reference" in r], in_tok, out_tok


# ---------------------------------------------------------------------------
# Phase 4: AI review
# ---------------------------------------------------------------------------

def review_batch(
    client: OpenAI, lang_name: str, entries: list[dict], model: str,
) -> tuple[list[dict], int, int]:
    slim = [{"canonical_reference": e.get("canonical_reference", ""),
             "reference_type":      e.get("reference_type", ""),
             "surface_patterns":    e.get("surface_patterns", []),
             "short_explanation":   e.get("short_explanation", ""),
             "confidence":          e.get("confidence", 0.68),
             "source_work":         e.get("source_work", ""),
             "source_author":       e.get("source_author", ""),
             "source_location":     e.get("source_location")}
            for e in entries]
    sys_p = _REVIEW_SYS.format(lang_name=lang_name)
    usr_p = _REVIEW_USER.format(
        lang_name=lang_name,
        entries_json=json.dumps(slim, ensure_ascii=False, indent=2),
    )
    raw, in_tok, out_tok = _chat(client, sys_p, usr_p, model, temperature=0.1)
    reviews = _parse_list(raw, "reviews")
    return [r for r in reviews if isinstance(r, dict) and "canonical_reference" in r], in_tok, out_tok


# ---------------------------------------------------------------------------
# Phase 5: auto-promote
# ---------------------------------------------------------------------------

def _run_promote_once(
    draft_path: Path, seed_path: Path, approved: list[str],
    reviewed_by: str, promote_script: Path,
) -> subprocess.CompletedProcess:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        f.write("\n".join(dict.fromkeys(approved)) + "\n")
        allowlist = f.name
    try:
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        return subprocess.run(
            [sys.executable, str(promote_script),
             "--draft", str(draft_path), "--seed", str(seed_path),
             "--allowlist", allowlist,
             "--reviewed-by", reviewed_by,
             "--reviewed-at", date.today().isoformat(),
             "--skip-existing", "--allow-missing-source-location",
             "--min-confidence", "0.60"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env=env,
        )
    finally:
        os.unlink(allowlist)


def _parse_refused_names(output: str, candidates: list[str]) -> list[str]:
    """Promotion output lists refused entries as '- {canonical_reference}: {reason}'.
    canonical_reference itself may contain ': ', so match against known
    candidate strings (longest first) rather than splitting on the colon."""
    by_length = sorted(set(candidates), key=len, reverse=True)
    refused: list[str] = []
    in_section = False
    for line in output.splitlines():
        stripped = line.strip()
        if stripped == "refused_entries:":
            in_section = True
            continue
        if stripped.endswith("_entries:"):
            in_section = False
            continue
        if in_section and stripped.startswith("- "):
            content = stripped[2:]
            match = next((c for c in by_length if content.startswith(c)), None)
            if match:
                refused.append(match)
    return refused


def _prefer_canonical_form(a: str, b: str) -> str:
    """Two strings that are case/NFC-equivalent -- pick the more conventional
    citation form: fewer uppercase letters wins (mid-sentence idiom/proverb
    citation is normally all-lowercase except internal proper nouns; a
    sentence-initial or over-capitalised duplicate has more uppercase
    letters). Ties keep the first-seen form."""
    a_upper = sum(1 for c in a if c.isupper())
    b_upper = sum(1 for c in b if c.isupper())
    return b if b_upper < a_upper else a


def _merge_case_variants(approved: list[str]) -> list[str]:
    """Two AI-generated entries sometimes share a canonical_reference that
    differs only by capitalisation (e.g. 'Die Geschichte' / 'die geschichte').
    promote_cultural_drafts.py's allowlist lookup is casefold-normalised, so
    it treats these as an ambiguous duplicate and aborts the whole batch.
    Keep one per casefold key."""
    by_key: dict[str, str] = {}
    for cr in approved:
        key = unicodedata.normalize("NFC", cr).casefold()
        by_key[key] = _prefer_canonical_form(by_key[key], cr) if key in by_key else cr
    return list(by_key.values())


def _dedupe_entries_by_canonical_reference(entries: list[dict]) -> list[dict]:
    """Same casefold-collision problem as _merge_case_variants, but applied
    to full draft entries before they're ever written to disk -- without
    this, promote_cultural_drafts.py's draft lookup finds two rows matching
    one allowlist name and refuses to guess which one was meant, even if
    the allowlist itself only names it once."""
    by_key: dict[str, dict] = {}
    for e in entries:
        key = unicodedata.normalize("NFC", e["canonical_reference"]).casefold()
        if key not in by_key:
            by_key[key] = e
        else:
            kept_cr = _prefer_canonical_form(
                by_key[key]["canonical_reference"], e["canonical_reference"]
            )
            by_key[key] = e if kept_cr == e["canonical_reference"] else by_key[key]
    return list(by_key.values())


def auto_promote(
    draft_path: Path, seed_path: Path, approved: list[str],
    reviewed_by: str, promote_script: Path, max_retries: int = 10,
) -> tuple[int, int]:
    """promote_cultural_drafts.py aborts the *entire* batch (writes nothing)
    if any single entry is refused — so retry with refused entries stripped
    until the batch is clean or nothing is left to promote."""
    remaining = _merge_case_variants(list(dict.fromkeys(approved)))
    total_promoted = 0
    last_refused_count = 0

    for _ in range(max_retries):
        if not remaining:
            break
        result = _run_promote_once(draft_path, seed_path, remaining, reviewed_by, promote_script)
        output = (result.stdout or "") + (result.stderr or "")

        if result.returncode == 0:
            for line in output.splitlines():
                if "promoted:" in line:
                    try: total_promoted += int(line.split(":")[1].strip())
                    except ValueError: pass
            return total_promoted, last_refused_count

        refused_names = _parse_refused_names(output, remaining)
        if not refused_names:
            print(output.strip(), file=sys.stderr)
            return total_promoted, last_refused_count
        last_refused_count += len(refused_names)
        remaining = [c for c in remaining if c not in set(refused_names)]

    return total_promoted, last_refused_count


# ---------------------------------------------------------------------------
# Build YAML entry
# ---------------------------------------------------------------------------

def _dedupe_case_variants(values: list[str], seen: set[str] | None = None) -> list[str]:
    """Drop later entries that are case/NFC-equivalent to an earlier one.

    build_cultural_catalog.py treats surface patterns as duplicates after
    NFC-normalising and casefolding them, regardless of which field
    (surface_patterns or variants) they came from -- so the same dedup
    must happen here, before the entry ever reaches the seed file.
    """
    seen = set() if seen is None else {unicodedata.normalize("NFC", s).casefold() for s in seen}
    out: list[str] = []
    for v in values:
        key = unicodedata.normalize("NFC", v).casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(v)
    return out


def build_entry(language: str, enriched: dict,
                i18n: dict | None = None, review: dict | None = None) -> dict:
    cr  = enriched.get("canonical_reference", "")
    rt  = enriched.get("reference_type", "cultural_reference")
    if rt not in REFERENCE_TYPES:
        rt = "cultural_reference"
    reg = enriched.get("register", "common")
    if reg not in REGISTERS:
        reg = "common"
    lic = enriched.get("source_license", "public_domain")
    if lic not in KNOWN_SOURCE_LICENSES:
        lic = "copyright_or_rights_review_needed"
    rights_basis = "common_usage_short_expression" if lic == "not_required" else None

    surface_patterns = _dedupe_case_variants(enriched.get("surface_patterns") or [cr])
    allow_short_pattern = (
        language in SHORT_PATTERN_OK_LANGUAGES
        and any(len(p.strip()) < 3 for p in surface_patterns)
    )

    conf = float(enriched.get("confidence", 0.68))
    if review and review.get("revised_confidence") is not None:
        try:
            conf = float(review["revised_confidence"])
        except (ValueError, TypeError):
            pass
    conf = round(max(0.60, min(0.90, conf)), 2)

    dataset_tag = enriched.get("source_dataset_tag", f"{language}_generated")
    verdict = review.get("verdict", "draft") if review else "draft"
    review_note = f" AI review: {verdict} -- {review.get('reason', '')}" if review else ""

    subcategory = enriched.get("subcategory", "") or ""
    if subcategory in NATIVE_REVIEW_REQUIRED_SUBCATEGORIES:
        if verdict == "approve":
            verdict = "flag"
            review_note += f" [auto-flagged: subcategory={subcategory!r} requires human review]"

    entry: dict = {
        "id":                  make_id(language, rt, cr),
        "language":            language,
        "canonical_reference": cr,
        "reference_type":      rt,
        "surface_patterns":    surface_patterns,
        "short_explanation":   enriched.get("short_explanation", ""),
        "learner_level":       enriched.get("learner_level", "B2"),
        "confidence":          conf,
        "review_status":       "draft",
        "register":            reg,
        "subcategory":         subcategory or None,
        "is_poetic_citation":  bool(enriched.get("is_poetic_citation", False)),
        "explanation_key":     make_key("explanation", language, f"{dataset_tag}.{cr}"),
        "source_work_key":     make_key("work",   language, enriched.get("source_work") or "unknown"),
        "source_author_key":   make_key("author", language, enriched.get("source_author") or "unknown"),
        "source_work":         enriched.get("source_work", ""),
        "source_author":       enriched.get("source_author", ""),
        "source_license":      lic,
        "source_dataset":      dataset_tag,
        "notes": "AI-generated; verify attribution and surface patterns before promotion." + review_note,
    }

    if i18n and isinstance(i18n.get("i18n_explanations"), dict):
        entry["i18n_explanations"] = i18n["i18n_explanations"]

    raw_variants = enriched.get("variants") or []
    if isinstance(raw_variants, str):
        raw_variants = [raw_variants]
    if not isinstance(raw_variants, list):
        raw_variants = []
    variants = _dedupe_case_variants(
        [v for v in raw_variants if isinstance(v, str)], seen=surface_patterns
    )
    if variants:
        entry["variants"] = variants
    loc = enriched.get("source_location")
    if loc:
        entry["source_location"] = loc
    url = enriched.get("source_url")
    if url:
        entry["source_url"] = url
    if rights_basis:
        entry["rights_basis"] = rights_basis
    if allow_short_pattern:
        entry["allow_short_pattern"] = True
    cfull = enriched.get("canonical_form_full", "")
    if cfull:
        entry["canonical_form_full"] = str(cfull).strip()

    ordered: dict = {}
    for k in FIELD_ORDER:
        if k in entry:
            ordered[k] = entry[k]
    for k, v in entry.items():
        if k not in ordered:
            ordered[k] = v
    return ordered


# ---------------------------------------------------------------------------
# Progress / YAML
# ---------------------------------------------------------------------------

def _progress_path(output: Path) -> Path:
    return output.with_suffix(".progress.json")


def load_progress(output: Path) -> dict:
    p = _progress_path(output)
    if p.exists():
        with p.open(encoding="utf-8") as f:
            return json.load(f)
    return {"discovered": [], "enriched": [], "i18n": [], "reviewed": [],
            "tokens_in": 0, "tokens_out": 0}


def save_progress(output: Path, state: dict) -> None:
    with _progress_path(output).open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def write_yaml(entries: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.dump(entries, f, allow_unicode=True, default_flow_style=False,
                  sort_keys=False, width=100)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run(
    language: str, target: int, model: str, review_model: str,
    output: Path, seed_path: Path,
    discover_batch: int, enrich_batch_size: int,
    i18n_batch_size: int, review_batch_size: int,
    resume: bool, do_i18n: bool, do_review: bool, do_promote: bool,
    reviewed_by: str,
    mode: str = "literary",
) -> None:
    lang_name = LANGUAGE_NAMES.get(language, language)

    # Mode selects which prompt templates and discovery theme rotation drive
    # phases 1-2 below. Review (_REVIEW_SYS/_REVIEW_USER) and i18n (_I18N_SYS/
    # _I18N_USER) are mode-agnostic and used unchanged regardless of mode.
    if mode == "idiom":
        discover_sys_tmpl  = _DISCOVER_IDIOM_SYS
        discover_user_tmpl = _DISCOVER_IDIOM_USER
        enrich_sys_tmpl    = _ENRICH_IDIOM_SYS
        enrich_user_tmpl   = _ENRICH_IDIOM_USER
        themes             = IDIOM_DISCOVERY_THEMES
    else:
        discover_sys_tmpl  = _DISCOVER_SYS
        discover_user_tmpl = _DISCOVER_USER
        enrich_sys_tmpl    = _ENRICH_SYS
        enrich_user_tmpl   = _ENRICH_USER
        themes             = DISCOVERY_THEMES

    # existing = seed entries + any already in the output draft (never overwrite)
    existing = load_existing(seed_path, language, extra_yaml=output if output.exists() else None)
    need = max(0, target - len(existing))

    print(f"Language     : {lang_name} ({language})")
    print(f"In seed/draft: {len(existing)}  (these will not be regenerated)")
    print(f"Target       : {target}  ->  need {need} new entries")
    print(f"Model        : {model}")
    if do_i18n:    print(f"i18n model   : {model}  (11 UI languages)")
    if do_review:  print(f"Review model : {review_model}")
    print(f"Output       : {output}\n")

    pending_progress = resume and _progress_path(output).exists()
    if need == 0 and not pending_progress:
        print("Target already met -- nothing to generate.")
        return
    if need == 0:
        print("Target already met for generation -- resuming to finish remaining phases (i18n/review/promote).")

    client = make_client(model)
    review_client = make_review_client(review_model)
    state  = load_progress(output) if resume else {
        "discovered": [], "enriched": [], "i18n": [], "reviewed": [],
        "tokens_in": 0, "tokens_out": 0,
    }

    enriched_refs  = {e["canonical_reference"] for e in state["enriched"]}
    i18n_refs      = {r["canonical_reference"] for r in state.get("i18n", [])}
    reviewed_refs  = {r["canonical_reference"] for r in state.get("reviewed", [])}
    to_enrich_pool = [c for c in state["discovered"]
                      if c not in enriched_refs and c not in existing]
    total_needed   = max(0, need - len(state["enriched"]))

    # ---- Phase 1: discover ------------------------------------------------
    if total_needed > 0 and len(to_enrich_pool) < total_needed:
        still_want = total_needed - len(to_enrich_pool)
        print(f"Phase 1: discover {still_want} candidates  (batch={discover_batch})")
        theme_idx = 0
        stale_themes = 0
        while len(to_enrich_pool) < total_needed and stale_themes < len(themes):
            theme = themes[theme_idx % len(themes)]
            ask = min(discover_batch, total_needed - len(to_enrich_pool) + 5)
            print(f"  -> requesting {ask} [{theme}] ...", end="", flush=True)
            cands, in_t, out_t = discover_candidates(
                client, language, lang_name, ask, existing, model, state["discovered"], theme=theme,
                sys_tmpl=discover_sys_tmpl, user_tmpl=discover_user_tmpl)
            state["tokens_in"] += in_t; state["tokens_out"] += out_t
            new = [c for c in cands if c not in set(state["discovered"]) | existing]
            state["discovered"].extend(new)
            to_enrich_pool.extend(new)
            save_progress(output, state)
            print(f" +{len(new)} ({len(to_enrich_pool)} queued)  ${cost_usd(state['tokens_in'], state['tokens_out'], model):.4f}")
            theme_idx += 1
            stale_themes = 0 if new else stale_themes + 1
            time.sleep(0.5)
        if len(to_enrich_pool) < total_needed:
            print("  WARNING: exhausted all discovery themes -- model may be exhausted for this language")

    # ---- Phase 2: enrich --------------------------------------------------
    to_enrich = [c for c in to_enrich_pool if c not in enriched_refs][:total_needed]
    if to_enrich:
        print(f"\nPhase 2: enrich {len(to_enrich)} entries  (batch={enrich_batch_size})")
        for i in range(0, len(to_enrich), enrich_batch_size):
            batch = to_enrich[i:i + enrich_batch_size]
            print(f"  -> {i+1}-{min(i+enrich_batch_size, len(to_enrich))} ...", end="", flush=True)
            enriched, in_t, out_t = enrich_batch(client, lang_name, batch, model, language=language,
                                                  sys_tmpl=enrich_sys_tmpl, user_tmpl=enrich_user_tmpl)
            state["tokens_in"] += in_t; state["tokens_out"] += out_t
            state["enriched"].extend(enriched)
            save_progress(output, state)
            print(f" ok ({len(enriched)})  ${cost_usd(state['tokens_in'], state['tokens_out'], model):.4f}")
            time.sleep(0.3)

    # ---- Phase 3: i18n translations ---------------------------------------
    if do_i18n:
        to_translate = [e for e in state["enriched"] if e["canonical_reference"] not in i18n_refs]
        if to_translate:
            print(f"\nPhase 3: translate {len(to_translate)} entries into {len(UI_LANGUAGES)} UI languages  (batch={i18n_batch_size})")
            for i in range(0, len(to_translate), i18n_batch_size):
                batch = to_translate[i:i + i18n_batch_size]
                print(f"  -> {i+1}-{min(i+i18n_batch_size, len(to_translate))} ...", end="", flush=True)
                results, in_t, out_t = i18n_batch(client, batch, model)
                state["tokens_in"] += in_t; state["tokens_out"] += out_t
                state["i18n"].extend(results)
                save_progress(output, state)
                print(f" ok ({len(results)})  ${cost_usd(state['tokens_in'], state['tokens_out'], model):.4f}")
                time.sleep(0.3)

    # ---- Phase 4: AI review -----------------------------------------------
    if do_review:
        to_review = [e for e in state["enriched"] if e["canonical_reference"] not in reviewed_refs]
        if to_review:
            print(f"\nPhase 4: AI review {len(to_review)} entries  (model={review_model}, batch={review_batch_size})")
            for i in range(0, len(to_review), review_batch_size):
                batch = to_review[i:i + review_batch_size]
                print(f"  -> reviewing {i+1}-{min(i+review_batch_size, len(to_review))} ...", end="", flush=True)
                reviews, in_t, out_t = review_batch(review_client, lang_name, batch, review_model)
                state["tokens_in"] += in_t; state["tokens_out"] += out_t
                state["reviewed"].extend(reviews)
                save_progress(output, state)
                verdicts = [r.get("verdict", "?")[0].upper() for r in reviews]
                print(f" {''.join(verdicts)}  ${cost_usd(state['tokens_in'], state['tokens_out'], model):.4f}")
                time.sleep(0.3)

    # ---- Write YAML -------------------------------------------------------
    i18n_map    = {r["canonical_reference"]: r for r in state.get("i18n", [])}
    review_map  = {r["canonical_reference"]: r for r in state.get("reviewed", [])}
    entries = [
        build_entry(language, e,
                    i18n=i18n_map.get(e["canonical_reference"]),
                    review=review_map.get(e["canonical_reference"]))
        for e in state["enriched"]
    ]
    entries = _dedupe_entries_by_canonical_reference(entries)
    kept_crs = {e["canonical_reference"] for e in entries}
    write_yaml(entries, output)

    # ---- Side files from review ------------------------------------------
    approved_crs: list[str] = []
    if do_review and review_map:
        approved_crs = list(dict.fromkeys(
            r["canonical_reference"] for r in state["reviewed"]
            if r.get("verdict") == "approve" and r["canonical_reference"] in kept_crs
        ))
        flagged = [e for e in entries if review_map.get(e["canonical_reference"], {}).get("verdict") == "flag"]
        rejected = [{"canonical_reference": r["canonical_reference"], "reason": r.get("reason", "")}
                    for r in state["reviewed"] if r.get("verdict") == "reject"]
        if flagged:
            write_yaml(flagged, output.with_suffix(".flagged.yaml"))
        if rejected:
            with output.with_suffix(".rejected.json").open("w", encoding="utf-8") as f:
                json.dump(rejected, f, ensure_ascii=False, indent=2)
        n_a, n_f, n_r = len(approved_crs), len(flagged), len(rejected)
        print(f"\nReview: {n_a} approved  {n_f} flagged  {n_r} rejected")
        if flagged:   print(f"  Flagged  -> {output.with_suffix('.flagged.yaml')}")
        if rejected:  print(f"  Rejected -> {output.with_suffix('.rejected.json')}")
    else:
        approved_crs = [e["canonical_reference"] for e in state["enriched"]]

    total_cost = cost_usd(state["tokens_in"], state["tokens_out"], model)
    print(f"\nWrote {len(entries)} draft entries -> {output}")
    print(f"Tokens : {state['tokens_in']:,} in / {state['tokens_out']:,} out")
    print(f"Cost   : ${total_cost:.4f}  ({model})")

    # ---- Phase 5: auto-promote -------------------------------------------
    if do_promote:
        if not approved_crs:
            print("\nNo approved entries to promote.")
        else:
            promote_script = _SCRIPT_DIR / "promote_cultural_drafts.py"
            if not promote_script.exists():
                print(f"\nERROR: promote script not found at {promote_script}", file=sys.stderr)
            else:
                print(f"\nPhase 5: promoting {len(approved_crs)} approved entries ...")
                promoted, refused = auto_promote(output, seed_path, approved_crs, reviewed_by, promote_script)
                print(f"  Promoted: {promoted}  Refused (surface conflicts): {refused}")
                print(f"\nNext: python scripts/build_cultural_catalog.py --write")
                print(f"      Update counts in backend/tests/test_cultural_catalog.py")
    else:
        print(f"\nNext: review {output}, create allowlist, then:")
        print(f"  python scripts/promote_cultural_drafts.py --draft {output} \\")
        print(f"      --allowlist <list.txt> --seed {seed_path} \\")
        print(f"      --reviewed-by <you> --reviewed-at <date>")
        print(f"  python scripts/build_cultural_catalog.py --write")

    _progress_path(output).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Cost estimation
# ---------------------------------------------------------------------------

def print_cost_estimate(target: int, languages: list[str], with_i18n: bool, with_review: bool) -> None:
    n   = len(languages)
    tok = estimate_tokens(target, with_i18n=with_i18n, with_review=with_review)

    flags = []
    if with_i18n:   flags.append("+i18n")
    if with_review: flags.append("+review")
    label = f"{target} entries x {n} language(s)" + (f"  [{', '.join(flags)}]" if flags else "")
    print(f"\nCost estimate -- {label}  (+-30%)")

    print(f"\n  {'Model':<26} {'$/language':>12}  {'$/all':>12}   notes")
    print(f"  {'-'*80}")
    for name, p in PROVIDERS.items():
        per = (tok["total_in"] * p["in"] + tok["total_out"] * p["out"]) / 1_000_000
        tot = per * n
        c   = "(needs proxy)" if not p["compat"] else ""
        print(f"  {name:<26} ${per:>10.3f}   ${tot:>10.3f}   {c}{p['note']}")

    print(f"\nToken breakdown per language:")
    print(f"  Discovery  : ~{tok['disc_in']:>7,} in / ~{tok['disc_out']:>7,} out")
    print(f"  Enrichment : ~{tok['enrich_in']:>7,} in / ~{tok['enrich_out']:>7,} out")
    if with_i18n:
        print(f"  i18n       : ~{tok['i18n_in']:>7,} in / ~{tok['i18n_out']:>7,} out  (11 UI languages)")
    if with_review:
        print(f"  Review     : ~{tok['review_in']:>7,} in / ~{tok['review_out']:>7,} out")
    print(f"  Total      : ~{tok['total_in']:>7,} in / ~{tok['total_out']:>7,} out")

    print(f"""
Recommendations:
  cheapest non-local  deepseek-chat (generate) -- ~${(tok['total_in']*0.14+tok['total_out']*0.28)/1e6:.3f}/lang
  best quality/cost   gpt-4o-mini -- ~${(tok['total_in']*0.15+tok['total_out']*0.60)/1e6:.3f}/lang
  classical languages gpt-4.1 (better Latin/Greek/Sanskrit attribution)
  CJK / Arabic        deepseek-chat or gemini-2.0-flash
  i18n only           use cheapest model for translation phase (low creativity needed)
  mixed               --model deepseek-chat --review-model gpt-4o-mini

Notes:
  * Prices mid-2025 -- verify at each provider's pricing page
  * claude-haiku-4-5 requires LiteLLM proxy (not openai-compat natively)
  * Local Ollama incurs no API cost; needs capable hardware
  * See scripts/.env.example for full provider setup instructions
""")


# ---------------------------------------------------------------------------
# Subcategory backfill
# ---------------------------------------------------------------------------

_SUBCATEGORY_VALUES: dict[str, list[str]] = {
    "zh": ["chengyu", "xiehouyu", "suyv", "yanyu"],
    "ar": ["quranic", "hadith", "muallaqat", "abbasid", "sufi_poetry", "proverb", "modern_media"],
    "fa": ["shahnameh", "hafez", "rumi", "saadi", "khayyam", "attar", "nizami",
           "sufi_poetry", "quranic", "historical", "persian_proverb", "modern_literature"],
    "ja": ["yojijukugo", "kanyoku", "kotowaza", "zen_koan", "classical_literature",
           "buddhist_text", "mythology", "historical", "modern_literature", "film_tv", "music"],
    "ko": ["sajaseong_eo", "pansori", "sijo", "korean_proverb", "classical_literature",
           "buddhist_text", "confucian_text", "historical", "modern_literature", "film_tv",
           "music", "folk_tale"],
    "hi": ["doha_kabir", "doha_rahim", "ramcharitmanas", "bhagavad_gita", "mahabharata",
           "panchatantra", "vedic_scripture", "sufi_poetry", "filmi", "hindi_muhavare",
           "hindi_lokokti", "historical", "mythology"],
    "en": ["biblical", "shakespearean", "arthurian", "greek_mythology", "roman_mythology",
           "norse_mythology", "literary_allusion", "modern_literature", "visual_art",
           "historical", "film_tv", "music", "proverb", "folk_tale"],
    "es": ["biblical", "golden_age", "latin_american_literature", "quijote",
           "greek_mythology", "roman_mythology", "literary_allusion", "modern_literature",
           "visual_art", "historical", "film_tv", "music", "refran", "folk_tale"],
    "pt": ["camoniano", "biblical", "roman_mythology", "greek_mythology",
           "literary_allusion", "brazilian_literature", "modern_literature",
           "visual_art", "historical", "film_tv", "music", "proverb", "folk_tale"],
    "fr": ["classical_tragedy", "enlightenment", "biblical", "latin_tag",
           "greek_mythology", "roman_mythology", "literary_allusion", "modern_literature",
           "visual_art", "historical", "film_tv", "music", "proverbe", "folk_tale"],
    "de": ["goethe_schiller", "fairy_tale", "nibelungen", "opera_libretto", "biblical",
           "latin_tag", "greek_mythology", "norse_mythology", "literary_allusion",
           "modern_literature", "visual_art", "historical", "film_tv", "music", "sprichwort"],
    "it": ["dantesque", "opera_libretto", "biblical", "latin_tag", "roman_mythology",
           "greek_mythology", "renaissance_literature", "literary_allusion",
           "modern_literature", "visual_art", "historical", "film_tv", "music", "proverbio"],
    "ru": ["pushkin", "classical_literature", "biblical", "folk_tale",
           "greek_mythology", "literary_allusion", "modern_literature",
           "historical", "film_tv", "music", "poslovitsa", "mythology"],
    "tr": ["ottoman_literature", "divan_poetry", "sufi_poetry", "folk_poetry",
           "quranic", "greek_mythology", "literary_allusion", "modern_literature",
           "historical", "film_tv", "music", "atassözü"],
    "fi": ["kalevala", "biblical", "norse_mythology", "greek_mythology",
           "literary_allusion", "modern_literature", "historical",
           "film_tv", "music", "sananlasku", "folk_tale"],
    "he": ["biblical", "talmudic", "kabbalistic", "liturgical", "modern_hebrew",
           "literary_allusion", "historical", "proverb"],
}
_SUBCATEGORY_DEFAULT = ["biblical", "latin_tag", "greek_mythology", "roman_mythology",
                        "literary_allusion", "modern_literature", "historical",
                        "film_tv", "music", "proverb", "folk_tale", "visual_art"]

_BACKFILL_SYS = (
    "You are a cultural catalogue specialist. For each entry, assign the most "
    "specific subcategory value and determine if is_poetic_citation is true. "
    "Return ONLY a JSON array in the same order as input."
)

_BACKFILL_USER = """\
Assign subcategory and is_poetic_citation for these {lang_name} entries.
Return [{{"subcategory": "...", "is_poetic_citation": true/false}}, ...] in the same order.
Use null for subcategory if none of the defined values fit.

Valid subcategory values for {lang_name}:
{subcategory_values}

Entries:
{entries_json}"""


def run_backfill_subcategory(
    language: str,
    model: str,
    seed_path: Path,
    batch_size: int = 20,
) -> None:
    import json as _json

    lang_name = LANGUAGE_NAMES.get(language, language)
    subcategory_values = ", ".join(
        _SUBCATEGORY_VALUES.get(language, _SUBCATEGORY_DEFAULT)
    )

    _lock_path = seed_path.with_suffix(".yaml.lock")

    try:
        from filelock import FileLock as _FileLock
        _has_filelock = True
    except ImportError:
        _has_filelock = False

    def _load_seed():
        try:
            from ruamel.yaml import YAML as _RY
            _ry = _RY()
            _ry.preserve_quotes = True
            with open(seed_path, encoding="utf-8") as _f:
                return _ry.load(_f), True, _ry
        except ImportError:
            import yaml as _py
            with open(seed_path, encoding="utf-8") as _f:
                return _py.safe_load(_f), False, None

    def _write_seed(entries, use_ruamel, ryaml_instance):
        if use_ruamel:
            from ruamel.yaml import YAML as _RY2
            _ry2 = _RY2()
            _ry2.preserve_quotes = True
            _ry2.default_flow_style = False
            _ry2.width = 10000
            with open(seed_path, "w", encoding="utf-8") as _f:
                _ry2.dump(entries, _f)
        else:
            import yaml as _py2
            with open(seed_path, "w", encoding="utf-8") as _f:
                _py2.dump(entries, _f, allow_unicode=True,
                          default_flow_style=False, sort_keys=False)

    # Read seed to discover targets (no lock needed — read-only)
    all_entries, _use_ruamel, _ryaml = _load_seed()
    targets = [
        (i, e) for i, e in enumerate(all_entries)
        if e.get("language") == language
        and not (e.get("subcategory") or "")
    ]
    print(f"Language: {lang_name} ({language})")
    print(f"Entries needing subcategory: {len(targets):,}")
    if not targets:
        print("Nothing to backfill.")
        return

    # Collect API results keyed by canonical_reference (no file I/O during loop)
    updates: dict[str, dict] = {}  # canonical_reference → {subcategory, is_poetic_citation}
    client = make_client(model)
    total_in = total_out = 0
    batches = [targets[i:i + batch_size] for i in range(0, len(targets), batch_size)]

    for b_idx, batch in enumerate(batches):
        entries_payload = _json.dumps(
            [
                {
                    "canonical_reference": e.get("canonical_reference"),
                    "source_work": e.get("source_work"),
                    "register": e.get("register"),
                    "short_explanation": (e.get("short_explanation") or "")[:80],
                }
                for _, e in batch
            ],
            ensure_ascii=False,
        )
        user_msg = _BACKFILL_USER.format(
            lang_name=lang_name,
            subcategory_values=subcategory_values,
            entries_json=entries_payload,
        )
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _BACKFILL_SYS},
                    {"role": "user",   "content": user_msg},
                ],
                temperature=0,
            )
        except Exception as exc:
            print(f"  batch {b_idx+1}: API error — {exc}", file=sys.stderr)
            continue

        total_in  += resp.usage.prompt_tokens
        total_out += resp.usage.completion_tokens

        raw = resp.choices[0].message.content or ""
        start = raw.find("[")
        end   = raw.rfind("]") + 1
        if start < 0 or end <= start:
            print(f"  batch {b_idx+1}: could not parse JSON array", file=sys.stderr)
            continue

        try:
            results = _json.loads(raw[start:end])
        except _json.JSONDecodeError as exc:
            print(f"  batch {b_idx+1}: JSON parse error — {exc}", file=sys.stderr)
            continue

        if len(results) != len(batch):
            print(f"  batch {b_idx+1}: expected {len(batch)} results, got {len(results)}", file=sys.stderr)
            continue

        for (_, entry), result in zip(batch, results):
            canon = entry.get("canonical_reference")
            if not canon:
                continue
            sub = result.get("subcategory")
            poetic = bool(result.get("is_poetic_citation", False))
            if sub or poetic:
                updates[canon] = {"subcategory": sub, "is_poetic_citation": poetic}

        print(f"  batch {b_idx+1}/{len(batches)}: processed {len(batch)} entries", flush=True)

    cost_in  = total_in  / 1_000_000
    cost_out = total_out / 1_000_000
    provider = PROVIDERS.get(model, {})
    price_in  = provider.get("in",  0.15)
    price_out = provider.get("out", 0.60)
    cost = cost_in * price_in + cost_out * price_out
    print(f"\nTokens: {total_in:,} in / {total_out:,} out  ~=  ${cost:.4f}")

    if not updates:
        print("No updates to write.")
        return

    # Write updates to a small per-language JSON file (atomic, no lock needed).
    # Run --merge-backfill-updates afterwards to apply all pending updates to seed.
    updates_path = seed_path.parent / f".backfill_updates_{language}.json"
    tmp_path = updates_path.with_suffix(".tmp")
    tmp_path.write_text(
        _json.dumps(updates, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    tmp_path.replace(updates_path)
    print(f"Updates staged -> {updates_path}")
    print("Run --merge-backfill-updates to apply to seed.")
    print("Done.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--language", "-l", help="Target language code (e.g. es, fr, de, zh)")
    ap.add_argument("--target",   "-t", type=int, default=None,
                    help="Target total entries for this language (required unless --backfill-subcategory)")
    ap.add_argument("--backfill-subcategory", action="store_true",
                    help="Enrich existing seed entries that lack a subcategory field, "
                         "rather than generating new entries. Reads entries from --seed, "
                         "sends them to the LLM in batches requesting subcategory and "
                         "is_poetic_citation, and stages results to a per-language JSON "
                         "file. Run --merge-backfill-updates to apply all staged updates.")
    ap.add_argument("--merge-backfill-updates", action="store_true",
                    help="Apply all staged .backfill_updates_<lang>.json files to the seed "
                         "in one pass and delete the temp files. Run after --backfill-subcategory.")
    ap.add_argument("--model", "-m",
                    help="Generation + i18n model (overrides CULTURAL_CATALOGUE_MODEL; default: gpt-4o-mini)")
    ap.add_argument("--review-model",
                    help="Review model (overrides CULTURAL_CATALOGUE_REVIEW_MODEL; default: same as --model)")
    ap.add_argument("--output", "-o", type=Path,
                    help="Output YAML path (default: data/cultural_drafts/<lang>_cultural_references_v1.generated.yaml)")
    ap.add_argument("--seed", type=Path, default=Path("data/cultural_references_seed.yaml"),
                    help="Seed YAML (entries here are never regenerated)")
    ap.add_argument("--discover-batch", type=int, default=25)
    ap.add_argument("--enrich-batch",   type=int, default=5)
    ap.add_argument("--i18n-batch",     type=int, default=5,
                    help="Entries per i18n call (default: 5)")
    ap.add_argument("--review-batch",   type=int, default=5)
    ap.add_argument("--resume", action="store_true",
                    help="Resume from existing .progress.json")
    ap.add_argument("--with-i18n", action="store_true",
                    help="Phase 3: translate short_explanation into 11 UI languages")
    ap.add_argument("--auto-review", action="store_true",
                    help="Phase 4: AI fact-check each entry after enrichment")
    ap.add_argument("--auto-promote", action="store_true",
                    help="Phase 5: promote approved entries automatically (implies --auto-review)")
    ap.add_argument("--reviewed-by", default="AI-review",
                    help="reviewed_by tag for auto-promoted entries (default: AI-review)")
    ap.add_argument("--estimate-cost", action="store_true",
                    help="Print cost estimate and exit -- no API calls")
    ap.add_argument("--with-review", action="store_true",
                    help="Include review tokens in --estimate-cost")
    ap.add_argument("--all-languages", action="store_true",
                    help="With --estimate-cost: show totals for all supported languages")
    ap.add_argument("--mode", choices=["literary", "idiom"], default="literary",
                    help="Discovery mode: 'literary' (default) = cultural/literary "
                         "references traceable to a named source; 'idiom' = "
                         "established everyday idiomatic expressions of any origin")
    args = ap.parse_args()

    if args.estimate_cost:
        langs = list(LANGUAGE_NAMES.keys()) if args.all_languages else ([args.language] if args.language else ["(1 language)"])
        mode_note = ("everyday idioms" if args.mode == "idiom" else "literary references")
        print(f"Mode: {args.mode} ({mode_note})\n")
        print_cost_estimate(args.target, langs, args.with_i18n, args.with_review)
        return

    if not args.language and not args.merge_backfill_updates:
        ap.error("--language is required (unless --estimate-cost or --merge-backfill-updates)")
    if args.language not in LANGUAGE_NAMES:
        print(f"Warning: '{args.language}' not in known languages -- proceeding", file=sys.stderr)
        LANGUAGE_NAMES[args.language] = args.language

    model        = resolve_model(args.model,        "CULTURAL_CATALOGUE_MODEL",        "gpt-4o-mini")
    review_model = resolve_model(args.review_model, "CULTURAL_CATALOGUE_REVIEW_MODEL", model)

    if args.merge_backfill_updates:
        import json as _json
        update_files = sorted(args.seed.parent.glob(".backfill_updates_*.json"))
        if not update_files:
            print("No staged update files found.")
            return
        all_updates: dict[str, dict] = {}
        for uf in update_files:
            data = _json.loads(uf.read_text(encoding="utf-8"))
            all_updates.update(data)
            print(f"  loaded {len(data):,} updates from {uf.name}")
        print(f"Applying {len(all_updates):,} total updates to {args.seed} ...")
        try:
            from ruamel.yaml import YAML as _RY
            _ry = _RY(); _ry.preserve_quotes = True
            with open(args.seed, encoding="utf-8") as _f:
                entries = _ry.load(_f)
            use_ruamel = True
        except ImportError:
            import yaml as _py
            with open(args.seed, encoding="utf-8") as _f:
                entries = _py.safe_load(_f)
            use_ruamel = False
        applied = 0
        for entry in entries:
            canon = entry.get("canonical_reference")
            if canon in all_updates:
                u = all_updates[canon]
                if u.get("subcategory"):
                    entry["subcategory"] = u["subcategory"]
                if u.get("is_poetic_citation"):
                    entry["is_poetic_citation"] = True
                applied += 1
        print(f"Applied {applied:,} entries. Writing seed ...")
        if use_ruamel:
            from ruamel.yaml import YAML as _RY2
            _ry2 = _RY2(); _ry2.preserve_quotes = True
            _ry2.default_flow_style = False; _ry2.width = 10000
            with open(args.seed, "w", encoding="utf-8") as _f:
                _ry2.dump(entries, _f)
        else:
            import yaml as _py2
            with open(args.seed, "w", encoding="utf-8") as _f:
                _py2.dump(entries, _f, allow_unicode=True,
                          default_flow_style=False, sort_keys=False)
        for uf in update_files:
            uf.unlink()
        print(f"Done. Deleted {len(update_files)} temp file(s).")
        return

    if args.backfill_subcategory:
        run_backfill_subcategory(
            language=args.language,
            model=model,
            seed_path=args.seed,
        )
        return

    if args.target is None:
        ap.error("--target is required (unless --backfill-subcategory or --estimate-cost)")

    output       = args.output or Path(
        f"data/cultural_drafts/{args.language}_cultural_references_v1.generated.yaml"
    )

    run(
        language=args.language, target=args.target,
        model=model, review_model=review_model,
        output=output, seed_path=args.seed,
        discover_batch=args.discover_batch,
        enrich_batch_size=args.enrich_batch,
        i18n_batch_size=args.i18n_batch,
        review_batch_size=args.review_batch,
        resume=args.resume,
        do_i18n=args.with_i18n,
        do_review=args.auto_review or args.auto_promote,
        do_promote=args.auto_promote,
        reviewed_by=args.reviewed_by,
        mode=args.mode,
    )


if __name__ == "__main__":
    main()
