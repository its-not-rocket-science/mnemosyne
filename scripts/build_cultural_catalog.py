#!/usr/bin/env python3
"""Build deterministic cultural/literary/proverb/allusion catalogues."""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEED = ROOT / "data" / "cultural_references_seed.yaml"
DEFAULT_OUT = ROOT / "backend" / "nuance" / "data" / "cultural_references"
SUPPORTED_LANGUAGES = ("en", "es", "fr", "de", "it", "pt", "ru", "ar", "he", "fa", "zh", "ja", "la", "grc", "ko", "hi", "tr", "fi")
REFERENCE_TYPES = {"literary_reference", "cultural_reference", "proverb_tradition", "classical_or_scriptural_allusion"}
LEARNER_LEVELS = {"A1", "A2", "B1", "B2", "C1", "C2"}
REGISTERS = {"common", "literary", "formal", "informal", "religious", "classical", "proverbial"}
REVIEW_STATUSES = {"draft", "reviewed", "rejected", "needs_native_review"}
PUBLIC_PROVENANCE_FIELDS = ("source_location", "source_quote", "source_note", "source_url", "source_license", "rights_basis", "source_dataset")
LOCALISATION_KEY_FIELDS = ("explanation_key", "source_work_key", "source_author_key")
SHORT_AMBIGUOUS = {
    "logos",
    "λόγος",
    "πίστις",
    "χάρις",
    "ἀγάπη",
    "faust",
    "sampo",
    "गीता",
    "कृष्ण",
    "अर्जुन",
    "جحا",
}
COMMON_WORDS = SHORT_AMBIGUOUS | {"scrooge", "orwellian", "kafkaesque", "saudade", "memento mori", "dolce vita"}
KNOWN_SOURCE_LICENSES = {
    "public_domain",
    "not_required",
    "CC0",
    "CC0-1.0",
    "CC-BY-4.0",
    "CC-BY-SA-4.0",  # Wiktionary (scripts/fetch_wiktionary_idioms.py) — distinct from
                      # CC-BY-4.0: ShareAlike requires derivatives use the same licence.
    "copyright_or_rights_review_needed",
    "common_usage_short_expression",  # legacy accepted seed/source value
}
RIGHTS_BASES = {"common_usage_short_expression", "public_domain_source", "quotation_under_review"}
SOURCE_QUOTE_WARNING_LENGTH = 160

TYPE_PREFIX = {
    "literary_reference": "literary",
    "cultural_reference": "cultural",
    "proverb_tradition": "proverb",
    "classical_or_scriptural_allusion": "classical",
}



def _parse_seed_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    if value[0] in {"'", '"'}:
        return json.loads(value) if value[0] == '"' else value.strip("'")
    if value == "true":
        return True
    if value == "false":
        return False
    if value in {"null", "~"}:
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _load_minimal_seed_yaml(text: str) -> list[dict[str, Any]]:
    """Parse the hand-authored seed YAML when PyYAML is unavailable.

    This intentionally supports only the small YAML subset used by
    data/cultural_references_seed.yaml: a top-level list of mappings, nested
    lists of scalar strings, and folded block scalars for prose fields.
    """
    lines = text.splitlines()
    rows: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    idx = 0
    while idx < len(lines):
        raw = lines[idx]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            idx += 1
            continue
        if raw.startswith("- "):
            current = {}
            rows.append(current)
            content = raw[2:]
        elif raw.startswith("  ") and current is not None:
            content = raw[2:]
        else:
            raise ValueError(f"unsupported seed YAML line {idx + 1}: {raw!r}")

        if ":" not in content:
            raise ValueError(f"unsupported seed YAML line {idx + 1}: {raw!r}")
        key, value = content.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == ">":
            idx += 1
            block: list[str] = []
            while idx < len(lines) and (lines[idx].startswith("    ") or not lines[idx].strip()):
                block.append(lines[idx][4:] if lines[idx].startswith("    ") else "")
                idx += 1
            current[key] = " ".join(part.strip() for part in block if part.strip())
            continue
        if value == "":
            idx += 1
            items: list[Any] = []
            while idx < len(lines):
                item_raw = lines[idx]
                item_stripped = item_raw.strip()
                if not item_stripped or item_stripped.startswith("#"):
                    idx += 1
                    continue
                if item_raw.startswith("    - "):
                    items.append(_parse_seed_scalar(item_raw[6:]))
                elif item_raw.startswith("  - "):
                    items.append(_parse_seed_scalar(item_raw[4:]))
                else:
                    break
                idx += 1
            current[key] = items
            continue
        current[key] = _parse_seed_scalar(value)
        idx += 1
    return rows

def load_seed(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore
        except ImportError:
            data = _load_minimal_seed_yaml(text)
        else:
            data = yaml.safe_load(text)
    if not isinstance(data, list):
        raise ValueError("seed file must contain a list of entries")
    return data


def is_normalized(value: str) -> bool:
    return unicodedata.normalize("NFC", value) == value


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).casefold()
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.replace("’", "'").replace("&", " and ")
    value = re.sub(r"[^\w]+", "_", value, flags=re.UNICODE).strip("_")
    return value or "reference"


def generated_id(entry: dict[str, Any]) -> str:
    return slugify(str(entry["canonical_reference"]))


def clean_text(value: Any) -> str:
    """Return deterministic single-entry text from seed scalar values."""
    return unicodedata.normalize("NFC", str(value)).strip()



def _looks_biblical_or_cross_reference(raw: dict[str, Any]) -> bool:
    if raw.get("reference_type") == "classical_or_scriptural_allusion":
        return True
    haystack = " ".join(
        clean_text(raw.get(field, ""))
        for field in ("source_work", "source_author", "source_location", "reference_type")
    ).casefold()
    biblical_terms = {
        "bible", "biblical", "king james", "kjv", "authorised version", "authorized version",
        "gospel", "psalm", "proverb", "isaiah", "matthew", "mark", "luke", "john",
        "genesis", "exodus", "ecclesiastes", "kings", "micah", "zechariah", "numbers",
        "joshua", "judges", "job", "lamentations",
    }
    if any(term in haystack for term in biblical_terms):
        return True
    location = clean_text(raw.get("source_location", "")).casefold()
    if any(marker in location for marker in ("cf.", "see ", "compare ", "cross-reference")):
        return True
    if any(marker in haystack for marker in ("canto", "inferno", "purgatorio", "paradiso")):
        return True
    # Citing multiple works (source_work lists more than one, comma-separated)
    # legitimately needs one semicolon-separated location per work.
    if "," in clean_text(raw.get("source_work", "")):
        return True
    # Multiple act/scene/chapter/verse references within the *same* work
    # (e.g. "Act 1, Scene 4; Act 2, Scene 5") -- every semicolon-separated
    # segment citing a specific numbered location, not free prose.
    segments = [s.strip() for s in location.split(";") if s.strip()]
    return len(segments) > 1 and all(any(ch.isdigit() for ch in s) for s in segments)


def append_rights_warnings(raw: dict[str, Any], idx: int, lang: str, warnings: list[str]) -> None:
    source_license = clean_text(raw.get("source_license", ""))
    rights_basis = clean_text(raw.get("rights_basis", ""))
    source_quote = clean_text(raw.get("source_quote", ""))
    source_location = clean_text(raw.get("source_location", ""))
    prefix = f"row {idx} ({lang})"

    if source_license and source_license not in KNOWN_SOURCE_LICENSES:
        warnings.append(f"{prefix}: source_license {source_license!r} is not in the known licence/status list")
    if rights_basis and rights_basis not in RIGHTS_BASES:
        warnings.append(f"{prefix}: rights_basis {rights_basis!r} is not recognised")
    if rights_basis and not source_license:
        warnings.append(f"{prefix}: rights_basis is present but source_license is blank")
    if rights_basis == "common_usage_short_expression" and source_license != "not_required":
        warnings.append(f"{prefix}: rights_basis=common_usage_short_expression should use source_license=not_required")
    if source_license == "not_required" and not rights_basis:
        warnings.append(f"{prefix}: source_license=not_required should include rights_basis")
    if len(source_quote) > SOURCE_QUOTE_WARNING_LENGTH:
        warnings.append(f"{prefix}: source_quote is {len(source_quote)} characters; keep quotes short")
    if "source quote:" in source_location.casefold():
        warnings.append(f"{prefix}: source_location contains 'Source quote:'; split quoted text into source_quote")
    if ";" in source_location and not _looks_biblical_or_cross_reference(raw):
        warnings.append(f"{prefix}: source_location contains semicolon prose; consider moving context to source_note")

def validate_and_build(
    rows: list[dict[str, Any]],
    only_language: str | None = None,
    include_drafts: bool = False,
) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    by_lang: dict[str, list[dict[str, Any]]] = {lang: [] for lang in SUPPORTED_LANGUAGES}
    ids: dict[str, set[str]] = defaultdict(set)
    surfaces: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))

    if only_language and only_language not in SUPPORTED_LANGUAGES:
        errors.append(f"unknown --language {only_language!r}")

    for idx, raw in enumerate(rows, start=1):
        if not isinstance(raw, dict):
            errors.append(f"row {idx}: entry must be an object")
            continue
        lang = raw.get("language")
        if lang not in SUPPORTED_LANGUAGES:
            errors.append(f"row {idx}: unknown language {lang!r}")
            continue
        if only_language and lang != only_language:
            continue
        rtype = raw.get("reference_type")
        if rtype not in REFERENCE_TYPES:
            errors.append(f"row {idx} ({lang}): unknown reference_type {rtype!r}")
        patterns = raw.get("surface_patterns")
        if not isinstance(patterns, list) or not patterns or not all(isinstance(p, str) and p.strip() for p in patterns):
            errors.append(f"row {idx} ({lang}): missing surface_patterns")
            patterns = []
        for field in ("canonical_reference", "short_explanation"):
            if not isinstance(raw.get(field), str) or not raw[field].strip():
                errors.append(f"row {idx} ({lang}): missing {field}")
        level = raw.get("learner_level")
        if level not in LEARNER_LEVELS:
            errors.append(f"row {idx} ({lang}): invalid learner_level {level!r}")
        register = raw.get("register")
        if register is not None and register not in REGISTERS:
            errors.append(f"row {idx} ({lang}): invalid register {register!r}")

        # subcategory — optional free string; vocabulary enforced at generation time
        subcategory = clean_text(raw.get("subcategory", "") or "")
        # is_poetic_citation — optional boolean
        is_poetic_citation = bool(raw.get("is_poetic_citation", False))
        # canonical_form_full — optional string for xiēhòuyǔ two-part forms
        canonical_form_full = clean_text(raw.get("canonical_form_full", "") or "")

        review_status = raw.get("review_status", "reviewed")
        if review_status not in REVIEW_STATUSES:
            errors.append(f"row {idx} ({lang}): unknown review_status {review_status!r}")
            review_status = "rejected"
        if raw.get("source_url") and not raw.get("source_license"):
            warnings.append(
                f"row {idx} ({lang}): source_url is present but source_license is missing"
            )
        append_rights_warnings(raw, idx, str(lang), warnings)
        if raw.get("review_status") == "reviewed" and (
            not raw.get("reviewed_by") or not raw.get("reviewed_at")
        ):
            warnings.append(
                f"row {idx} ({lang}): review_status 'reviewed' should include reviewed_by and reviewed_at"
            )
        emit_entry = review_status == "reviewed" or (
            include_drafts and review_status in {"draft", "needs_native_review"}
        )
        try:
            confidence = float(raw.get("confidence"))
            if not (0 <= confidence <= 1):
                raise ValueError
        except (TypeError, ValueError):
            errors.append(f"row {idx} ({lang}): confidence must be between 0 and 1")
            confidence = 0.0
        variants = raw.get("variants") or []
        avoid_if = raw.get("avoid_if") or []
        for field, value in (("variants", variants), ("avoid_if", avoid_if)):
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                errors.append(f"row {idx} ({lang}): {field} must be a list[str]")
                if field == "variants":
                    variants = []
                else:
                    avoid_if = []
        merged_patterns = list(dict.fromkeys(clean_text(p) for p in [*patterns, *variants]))
        eid = str(raw.get("id") or generated_id(raw)).strip()
        if eid in ids[lang]:
            errors.append(f"row {idx} ({lang}): duplicate id {eid!r}")
        ids[lang].add(eid)
        for pat in merged_patterns:
            if not is_normalized(pat):
                errors.append(f"row {idx} ({lang}): pattern is not NFC-normalized: {pat!r}")
            norm_pat = unicodedata.normalize("NFC", pat).casefold()
            if len(pat.strip()) < 3 and not raw.get("allow_short_pattern"):
                errors.append(f"row {idx} ({lang}): very short pattern {pat!r} requires allow_short_pattern: true")
            if norm_pat in SHORT_AMBIGUOUS and not raw.get("allow_short_pattern"):
                errors.append(f"row {idx} ({lang}): ambiguous pattern {pat!r} requires allow_short_pattern: true")
            if confidence > 0.90 and (norm_pat in COMMON_WORDS or len(pat.strip()) < 6):
                warnings.append(f"row {idx} ({lang}): high confidence {confidence:.2f} for ambiguous/common pattern {pat!r}")
            surfaces[lang][norm_pat].append(eid)
        notes = raw.get("notes")
        if isinstance(notes, str):
            notes = clean_text(notes)
        entry = {
            "id": eid,
            "language": lang,
            "surface_patterns": merged_patterns,
            "canonical_reference": clean_text(raw.get("canonical_reference", "")),
            "canonical_form": f"{lang}:{TYPE_PREFIX.get(str(rtype), str(rtype))}:{eid}",
            "reference_type": rtype,
            "source_work": raw.get("source_work"),
            "source_author": raw.get("source_author"),
            "short_explanation": clean_text(raw.get("short_explanation", "")),
            "learner_level": level,
            "register": register,
            "confidence": confidence,
            "variants": variants,
            "avoid_if": avoid_if,
            "notes": notes,
            "allow_short_pattern": bool(raw.get("allow_short_pattern", False)),
            "subcategory":         subcategory or None,
            "is_poetic_citation":  is_poetic_citation or None,
            "canonical_form_full": canonical_form_full or None,
        }
        for field in (*LOCALISATION_KEY_FIELDS, *PUBLIC_PROVENANCE_FIELDS):
            if raw.get(field) not in (None, ""):
                entry[field] = clean_text(raw[field])
        if isinstance(raw.get("i18n_explanations"), dict) and raw["i18n_explanations"]:
            entry["i18n_explanations"] = raw["i18n_explanations"]
        if emit_entry:
            by_lang[lang].append(
                {
                    k: v
                    for k, v in entry.items()
                    if v not in (None, [], False) or k in {"confidence"}
                }
            )

    for lang, per_surface in surfaces.items():
        for pat, entry_ids in per_surface.items():
            if len(entry_ids) > 1:
                warnings.append(f"{lang}: duplicate surface pattern {pat!r} in ids {', '.join(entry_ids)}")

    if errors:
        raise ValueError("\n".join(errors + [*(f"WARNING: {w}" for w in warnings)]))

    for lang in by_lang:
        by_lang[lang].sort(key=lambda e: (e["reference_type"], e["id"]))
    return by_lang, warnings


def selected_languages(only_language: str | None = None) -> list[str]:
    return [only_language] if only_language is not None else list(SUPPORTED_LANGUAGES)


def entry_count(by_lang: dict[str, list[dict[str, Any]]], only_language: str | None = None) -> int:
    return sum(len(by_lang.get(lang, [])) for lang in selected_languages(only_language))


def language_count(only_language: str | None = None) -> int:
    return len(selected_languages(only_language))


def pluralize(count: int, singular: str, plural: str | None = None) -> str:
    return singular if count == 1 else (plural or f"{singular}s")


def summary(
    by_lang: dict[str, list[dict[str, Any]]],
    only_language: str | None = None,
) -> str:
    headers = ["language", "entries", *sorted(REFERENCE_TYPES)]
    lines = [" | ".join(headers), " | ".join("-" * len(h) for h in headers)]
    for lang in selected_languages(only_language):
        entries = by_lang.get(lang, [])
        counts = Counter(e["reference_type"] for e in entries)
        lines.append(
            " | ".join(
                [lang, str(len(entries)), *(str(counts[t]) for t in sorted(REFERENCE_TYPES))]
            )
        )
    return "\n".join(lines)


def write_outputs(
    by_lang: dict[str, list[dict[str, Any]]],
    out_dir: Path,
    only_language: str | None = None,
) -> int:
    out_dir.mkdir(parents=True, exist_ok=True)
    langs = selected_languages(only_language)
    for lang in langs:
        payload = {
            "language": lang,
            "entries": by_lang.get(lang, []),
        }
        target = out_dir / f"{lang}.json"
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return len(langs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--check",
        action="store_true",
        help="validate seed and generated output without writing",
    )
    mode.add_argument("--write", action="store_true", help="write generated runtime JSON files")
    mode.add_argument("--report", action="store_true", help="validate and print summary report")
    parser.add_argument(
        "--language",
        choices=SUPPORTED_LANGUAGES,
        help="limit validation/report/write to one language",
    )
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--include-drafts",
        action="store_true",
        help="include draft and needs_native_review entries in generated output; rejected entries are never emitted",
    )
    args = parser.parse_args()

    try:
        by_lang, warnings = validate_and_build(
            load_seed(args.seed), args.language, include_drafts=args.include_drafts
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    for warning in warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    entries = entry_count(by_lang, args.language)
    if args.check:
        languages = language_count(args.language)
        language_suffix = f" ({args.language})" if args.language else ""
        print(
            f"OK: validated {entries} {pluralize(entries, 'entry', 'entries')} "
            f"across {languages} {pluralize(languages, 'language')}{language_suffix}"
        )
    elif args.report:
        print(summary(by_lang, args.language))
    elif args.write:
        files_written = write_outputs(by_lang, args.out_dir, args.language)
        print(
            f"Wrote {files_written} catalogue {pluralize(files_written, 'file')} to {args.out_dir} "
            f"({entries} {pluralize(entries, 'entry', 'entries')})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
