#!/usr/bin/env python3
"""Import structured cultural catalogue source files into draft seed YAML.

This script intentionally creates review drafts only. It does not edit the
production seed file and does not generate runtime JSON catalogues.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import unicodedata
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = ROOT / "data" / "cultural_sources"
DEFAULT_DRAFT_DIR = ROOT / "data" / "cultural_drafts"

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - exercised in minimal environments
    yaml = None  # type: ignore[assignment]

# Keep these in sync with scripts/build_cultural_catalog.py so generated drafts
# validate cleanly before they are promoted into the production seed.
SUPPORTED_LANGUAGES = {
    "en",
    "es",
    "fr",
    "de",
    "it",
    "pt",
    "ru",
    "ar",
    "he",
    "zh",
    "ja",
    "la",
    "grc",
    "ko",
    "hi",
    "tr",
    "fi",
}
REFERENCE_TYPES = {
    "literary_reference",
    "cultural_reference",
    "proverb_tradition",
    "classical_or_scriptural_allusion",
}
LEARNER_LEVELS = {"A1", "A2", "B1", "B2", "C1", "C2"}
REGISTERS = {"common", "literary", "formal", "informal", "religious", "classical", "proverbial"}

REQUIRED_FIELDS = (
    "language",
    "canonical_reference",
    "reference_type",
    "learner_level",
    "confidence",
    "source_dataset",
)
OPTIONAL_SCALAR_FIELDS = (
    "source_work",
    "source_author",
    "source_location",
    "register",
    "source_url",
    "source_license",
    "source_dataset",
    "notes",
)


def clean_text(value: Any) -> str:
    """Normalize a source scalar to deterministic single-entry text."""
    return unicodedata.normalize("NFC", str(value)).strip()


def is_blank(value: Any) -> bool:
    return value is None or clean_text(value) == ""


def split_pipe(value: Any) -> list[str]:
    """Split a pipe-delimited scalar, dropping empty tokens while preserving order."""
    if is_blank(value):
        return []
    parts = [clean_text(part) for part in str(value).split("|")]
    return [part for part in parts if part]


def dedupe(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(clean_text(value) for value in values if clean_text(value)))


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).casefold()
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.replace("’", "'").replace("&", " and ")
    slug = []
    previous_was_sep = False
    for ch in value:
        if ch.isalnum() or ch == "_":
            slug.append(ch)
            previous_was_sep = False
        elif not previous_was_sep:
            slug.append("_")
            previous_was_sep = True
    return "".join(slug).strip("_") or "reference"


def stable_generated_id(row: dict[str, Any]) -> str:
    """Generate a deterministic id from stable identifying source fields."""
    canonical = clean_text(row.get("canonical_reference", "reference")) or "reference"
    language = clean_text(row.get("language", "und")) or "und"
    reference_type = clean_text(row.get("reference_type", "reference")) or "reference"
    basis = "|".join(
        clean_text(row.get(field, ""))
        for field in (
            "language",
            "reference_type",
            "canonical_reference",
            "source_work",
            "source_author",
            "source_location",
            "source_dataset",
        )
    )
    digest = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:8]
    return f"{language}_{slugify(reference_type)}_{slugify(canonical)}_{digest}"


def load_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"{path}: CSV must include a header row")
        return [dict(row) for row in reader]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc.msg}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number}: JSONL row must be an object")
            rows.append(row)
    return rows


def load_source(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return load_csv(path)
    if suffix in {".jsonl", ".ndjson"}:
        return load_jsonl(path)
    raise ValueError(f"unsupported source format {suffix!r}; expected .csv, .jsonl, or .ndjson")


def parse_confidence(value: Any, row_number: int) -> float:
    if is_blank(value):
        raise ValueError(f"row {row_number}: missing confidence")
    try:
        confidence = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"row {row_number}: confidence must be a number between 0 and 1") from exc
    if not 0 <= confidence <= 1:
        raise ValueError(f"row {row_number}: confidence must be between 0 and 1")
    return confidence


def validate_choice(
    row: dict[str, Any],
    row_number: int,
    field: str,
    choices: set[str],
    *,
    required: bool = True,
) -> str | None:
    if is_blank(row.get(field)):
        if required:
            raise ValueError(f"row {row_number}: missing {field}")
        return None
    value = clean_text(row[field])
    if value not in choices:
        allowed = ", ".join(sorted(choices))
        raise ValueError(f"row {row_number}: invalid {field} {value!r}; expected one of: {allowed}")
    return value


def convert_row(row: dict[str, Any], row_number: int) -> dict[str, Any]:
    for field in REQUIRED_FIELDS:
        if is_blank(row.get(field)):
            raise ValueError(f"row {row_number}: missing {field}")

    surface_patterns = dedupe(
        [*split_pipe(row.get("surface_pattern")), *split_pipe(row.get("surface_patterns"))]
    )
    if not surface_patterns:
        raise ValueError(
            f"row {row_number}: missing surface_pattern or surface_patterns (pipe-delimited)"
        )

    language = validate_choice(row, row_number, "language", SUPPORTED_LANGUAGES)
    reference_type = validate_choice(row, row_number, "reference_type", REFERENCE_TYPES)
    learner_level = validate_choice(row, row_number, "learner_level", LEARNER_LEVELS)
    register = validate_choice(row, row_number, "register", REGISTERS, required=False)
    confidence = parse_confidence(row.get("confidence"), row_number)

    entry_id = (
        clean_text(row.get("id")) if not is_blank(row.get("id")) else stable_generated_id(row)
    )
    entry: dict[str, Any] = {
        "id": entry_id,
        "language": language,
        "canonical_reference": clean_text(row["canonical_reference"]),
        "reference_type": reference_type,
        "surface_patterns": surface_patterns,
        "short_explanation": "TODO: add explanation",
        "learner_level": learner_level,
        "confidence": confidence,
        "review_status": "draft",
    }

    if register is not None:
        entry["register"] = register

    surface_keys = {pattern.casefold() for pattern in surface_patterns}
    variants = [
        variant
        for variant in dedupe(split_pipe(row.get("variants")))
        if variant.casefold() not in surface_keys
    ]
    if variants:
        entry["variants"] = variants

    for field in OPTIONAL_SCALAR_FIELDS:
        if field == "register":
            continue
        if not is_blank(row.get(field)):
            entry[field] = clean_text(row[field])

    return entry


def convert_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    errors: list[str] = []
    seen_ids: dict[str, int] = {}
    for row_number, row in enumerate(rows, start=1):
        try:
            entry = convert_row(row, row_number)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        entry_id = entry["id"]
        if entry_id in seen_ids:
            original_row = seen_ids[entry_id]
            errors.append(
                f"row {row_number}: duplicate id {entry_id!r} "
                f"(already generated by row {original_row})"
            )
            continue
        seen_ids[entry_id] = row_number
        entries.append(entry)
    if errors:
        raise ValueError("\n".join(errors))
    return entries


def yaml_scalar(value: Any) -> str:
    """Render a scalar in the small YAML subset used for draft catalogues."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if value is None:
        return "null"
    return json.dumps(clean_text(value), ensure_ascii=False)


def dump_minimal_yaml(entries: list[dict[str, Any]]) -> str:
    """Write YAML without requiring PyYAML in lightweight environments."""
    lines: list[str] = []
    for entry in entries:
        first = True
        for key, value in entry.items():
            prefix = "- " if first else "  "
            first = False
            if isinstance(value, list):
                lines.append(f"{prefix}{key}:")
                for item in value:
                    lines.append(f"    - {yaml_scalar(item)}")
            else:
                lines.append(f"{prefix}{key}: {yaml_scalar(value)}")
    return "\n".join(lines) + ("\n" if lines else "[]\n")


def write_yaml(entries: list[dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if yaml is not None:
        text = yaml.dump(
            entries,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
            width=100,
        )
    else:
        text = dump_minimal_yaml(entries)
    out_path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help=f"CSV or JSONL source file, typically under {DEFAULT_SOURCE_DIR}",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help=f"draft YAML output path, typically under {DEFAULT_DRAFT_DIR}",
    )
    args = parser.parse_args()

    try:
        rows = load_source(args.source)
        entries = convert_rows(rows)
        write_yaml(entries, args.out)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    entry_word = "entry" if len(entries) == 1 else "entries"
    print(f"Wrote {len(entries)} draft cultural {entry_word} to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
