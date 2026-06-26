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
TODO_EXPLANATION = "TODO: add explanation"
EXPECTED_CSV_HEADER = (
    "language,surface_pattern,surface_patterns,variants,canonical_reference,reference_type,"
    "source_work,source_author,source_location,source_quote,source_note,short_explanation,"
    "explanation_key,source_work_key,source_author_key,learner_level,register,confidence,"
    "source_url,source_license,rights_basis,source_dataset,notes,"
    "subcategory,is_poetic_citation,canonical_form_full"
)

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
    "fa",
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

KNOWN_SOURCE_LICENSES = {
    "public_domain",
    "not_required",
    "CC0",
    "CC0-1.0",
    "CC-BY-4.0",
    "CC-BY-SA-4.0",  # Wiktionary (scripts/fetch_wiktionary_idioms.py) — distinct from
                      # CC-BY-4.0: ShareAlike requires derivatives use the same licence.
    "copyright_or_rights_review_needed",
    "common_usage_short_expression",  # legacy v4 value; kept accepted for older source files
}
RIGHTS_BASES = {
    "common_usage_short_expression",
    "public_domain_source",
    "quotation_under_review",
}
SOURCE_QUOTE_WARNING_LENGTH = 160

OPTIONAL_SCALAR_FIELDS = (
    "source_work",
    "source_author",
    "source_location",
    "source_quote",
    "source_note",
    "short_explanation",
    "explanation_key",
    "source_work_key",
    "source_author_key",
    "register",
    "source_url",
    "source_license",
    "rights_basis",
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


OLD_LOCALISATION_PREFIXES = (
    "cultural.explanation.",
    "cultural.source_work.",
    "cultural.source_author.",
)
CANONICAL_LOCALISATION_PREFIXES = (
    "mnemosyne.en.explanation.",
    "mnemosyne.en.work.",
    "mnemosyne.en.author.",
)


def is_old_localisation_key(value: str) -> bool:
    return value.startswith(OLD_LOCALISATION_PREFIXES)


def is_canonical_localisation_key(value: str) -> bool:
    return value.startswith(CANONICAL_LOCALISATION_PREFIXES)


def key_or_generated(
    row: dict[str, Any],
    field: str,
    generated: str | None,
    row_number: int,
    warnings: list[str],
) -> str | None:
    """Return a canonical user-provided localisation key or deterministic suggestion."""
    if is_blank(row.get(field)):
        return generated

    explicit = clean_text(row[field])
    if is_canonical_localisation_key(explicit):
        return explicit
    if is_old_localisation_key(explicit):
        if generated is None:
            raise ValueError(
                f"row {row_number}: old localisation key {explicit!r} for {field} cannot be "
                "migrated automatically because the row is missing data needed to build the "
                "canonical mnemosyne.en.* key"
            )
        warnings.append(
            f"row {row_number}: migrated deprecated localisation key {explicit!r} "
            f"for {field} to {generated!r}"
        )
        return generated
    raise ValueError(
        f"row {row_number}: invalid localisation key {explicit!r} for {field}; "
        "expected mnemosyne.en.* key"
    )


def has_real_explanation(value: Any) -> bool:
    return not is_blank(value) and clean_text(value) != TODO_EXPLANATION


def explanation_key(row: dict[str, Any]) -> str | None:
    language = clean_text(row.get("language", ""))
    dataset = clean_text(row.get("source_dataset", ""))
    canonical = clean_text(row.get("canonical_reference", ""))
    entry_basis = canonical or (
        split_pipe(row.get("surface_pattern")) or split_pipe(row.get("surface_patterns")) or [""]
    )[0]
    if not language or not dataset or not entry_basis:
        return None
    return f"mnemosyne.en.explanation.{slugify(dataset)}.{slugify(entry_basis)}"


def source_work_key(row: dict[str, Any]) -> str | None:
    work = clean_text(row.get("source_work", ""))
    if not work:
        return None
    return f"mnemosyne.en.work.{slugify(work)}"


def source_author_key(row: dict[str, Any]) -> str | None:
    author = clean_text(row.get("source_author", ""))
    if not author:
        return None
    return f"mnemosyne.en.author.{slugify(author)}"


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
        # Skip leading '#'-prefixed comment lines (e.g. the license/attribution
        # note scripts/fetch_wiktionary_idioms.py writes before the header) so
        # csv.DictReader sees the real header row first, not the comment.
        lines = handle.readlines()
        first_data_line = next((i for i, l in enumerate(lines) if not l.startswith("#")), 0)
        reader = csv.DictReader(lines[first_data_line:])
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


def looks_biblical_or_cross_reference(row: dict[str, Any]) -> bool:
    haystack = " ".join(
        clean_text(row.get(field, ""))
        for field in ("source_work", "source_author", "source_location", "reference_type")
    ).casefold()
    biblical_terms = {
        "bible",
        "biblical",
        "king james",
        "kjv",
        "authorised version",
        "authorized version",
        "gospel",
        "psalm",
        "proverb",
        "isaiah",
        "matthew",
        "mark",
        "luke",
        "john",
        "genesis",
        "exodus",
        "ecclesiastes",
    }
    if any(term in haystack for term in biblical_terms):
        return True
    location = clean_text(row.get("source_location", "")).casefold()
    return any(marker in location for marker in ("cf.", "see ", "compare ", "cross-reference"))


def validate_rights_and_source_fields(
    row: dict[str, Any], row_number: int, warnings: list[str]
) -> None:
    source_license = clean_text(row.get("source_license", ""))
    rights_basis = clean_text(row.get("rights_basis", ""))
    source_quote = clean_text(row.get("source_quote", ""))
    source_location = clean_text(row.get("source_location", ""))

    if source_license and source_license not in KNOWN_SOURCE_LICENSES:
        warnings.append(
            f"row {row_number}: source_license {source_license!r} is not in the known licence/status list"
        )
    if rights_basis and rights_basis not in RIGHTS_BASES:
        warnings.append(f"row {row_number}: rights_basis {rights_basis!r} is not recognised")
    if rights_basis and not source_license:
        warnings.append(f"row {row_number}: rights_basis is present but source_license is blank")
    if rights_basis == "common_usage_short_expression" and source_license != "not_required":
        warnings.append(
            f"row {row_number}: rights_basis=common_usage_short_expression should use source_license=not_required"
        )
    if source_license == "not_required" and not rights_basis:
        warnings.append(f"row {row_number}: source_license=not_required should include rights_basis")
    if len(source_quote) > SOURCE_QUOTE_WARNING_LENGTH:
        warnings.append(
            f"row {row_number}: source_quote is {len(source_quote)} characters; keep quotes short"
        )
    if "source quote:" in source_location.casefold():
        warnings.append(
            f"row {row_number}: source_location contains 'Source quote:'; split quoted text into source_quote"
        )
    if ";" in source_location and not looks_biblical_or_cross_reference(row):
        warnings.append(
            f"row {row_number}: source_location contains semicolon prose; consider moving context to source_note"
        )


def convert_row(
    row: dict[str, Any], row_number: int, warnings: list[str] | None = None
) -> dict[str, Any]:
    if warnings is None:
        warnings = []
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
    validate_rights_and_source_fields(row, row_number, warnings)

    entry_id = (
        clean_text(row.get("id")) if not is_blank(row.get("id")) else stable_generated_id(row)
    )
    entry: dict[str, Any] = {
        "id": entry_id,
        "language": language,
        "canonical_reference": clean_text(row["canonical_reference"]),
        "reference_type": reference_type,
        "surface_patterns": surface_patterns,
        "short_explanation": (
            clean_text(row.get("short_explanation"))
            if has_real_explanation(row.get("short_explanation"))
            else TODO_EXPLANATION
        ),
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

    generated_keys = {
        "explanation_key": explanation_key(row),
        "source_work_key": source_work_key(row),
        "source_author_key": source_author_key(row),
    }
    for field, generated in generated_keys.items():
        value = key_or_generated(row, field, generated, row_number, warnings)
        if value:
            entry[field] = value

    for field in OPTIONAL_SCALAR_FIELDS:
        if field in {
            "register",
            "short_explanation",
            "explanation_key",
            "source_work_key",
            "source_author_key",
        }:
            continue
        if not is_blank(row.get(field)):
            entry[field] = clean_text(row[field])

    entry["subcategory"]         = clean_text(row.get("subcategory", "") or "")
    entry["is_poetic_citation"]  = str(row.get("is_poetic_citation", "")).strip().lower() == "true"
    entry["canonical_form_full"] = clean_text(row.get("canonical_form_full", "") or "")

    return entry


def convert_rows_with_warnings(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    entries: list[dict[str, Any]] = []
    warnings: list[str] = []
    errors: list[str] = []
    seen_ids: dict[str, int] = {}
    for row_number, row in enumerate(rows, start=1):
        try:
            entry = convert_row(row, row_number, warnings)
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
    return entries, warnings


def convert_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entries, _warnings = convert_rows_with_warnings(rows)
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


def l10n_candidates(entries: list[dict[str, Any]]) -> dict[str, str]:
    candidates: dict[str, str] = {}
    for entry in entries:
        if entry.get("explanation_key") and has_real_explanation(entry.get("short_explanation")):
            candidates[clean_text(entry["explanation_key"])] = clean_text(
                entry["short_explanation"]
            )
        if entry.get("source_work_key") and not is_blank(entry.get("source_work")):
            candidates[clean_text(entry["source_work_key"])] = clean_text(entry["source_work"])
        if entry.get("source_author_key") and not is_blank(entry.get("source_author")):
            candidates[clean_text(entry["source_author_key"])] = clean_text(entry["source_author"])
    return dict(sorted(candidates.items()))


def write_l10n(entries: list[dict[str, Any]], out_path: Path) -> list[str]:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, str] = {}
    if out_path.exists():
        payload = json.loads(out_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in payload.items()
        ):
            raise ValueError(
                f"{out_path}: l10n file must be a JSON object mapping strings to strings"
            )
        existing = dict(payload)

    warnings: list[str] = []
    merged = {key: value for key, value in existing.items() if not is_old_localisation_key(key)}
    removed_old = sorted(key for key in existing if is_old_localisation_key(key))
    if removed_old:
        warnings.append(
            f"removed {len(removed_old)} deprecated cultural.* localisation keys from {out_path}"
        )
    for key, value in l10n_candidates(entries).items():
        if key in merged:
            if merged[key] != value:
                warnings.append(
                    f"l10n conflict for {key!r}: existing={merged[key]!r}, imported={value!r}"
                )
            continue
        merged[key] = value

    out_path.write_text(
        json.dumps(dict(sorted(merged.items())), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return warnings


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
    parser.add_argument(
        "--l10n-out",
        type=Path,
        help=(
            "optional cultural localisation JSON output path to create/update, "
            "e.g. backend/lesson/l10n/cultural_references/en.json"
        ),
    )
    parser.epilog = f"Expected CSV header: {EXPECTED_CSV_HEADER}"
    args = parser.parse_args()

    try:
        rows = load_source(args.source)
        entries, l10n_warnings = convert_rows_with_warnings(rows)
        write_yaml(entries, args.out)
        if args.l10n_out is not None:
            l10n_warnings.extend(write_l10n(entries, args.l10n_out))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    for warning in l10n_warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    entry_word = "entry" if len(entries) == 1 else "entries"
    print(f"Wrote {len(entries)} draft cultural {entry_word} to {args.out}")
    if args.l10n_out is not None:
        print(f"Updated cultural localisation resource {args.l10n_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
