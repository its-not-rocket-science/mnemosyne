#!/usr/bin/env python3
"""Promote allowlisted cultural catalogue drafts into the reviewed seed."""
from __future__ import annotations

import argparse
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - exercised in minimal environments
    yaml = None  # type: ignore[assignment]


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DRAFT = ROOT / "data" / "cultural_drafts" / "en_literary_idioms_normalised_v3.generated.yaml"
DEFAULT_SEED = ROOT / "data" / "cultural_references_seed.yaml"
DEFAULT_ALLOWLIST = ROOT / "data" / "cultural_drafts" / "promote_en_literary_idioms_batch_001.txt"
RIGHTS_REVIEW_LICENSE = "copyright_or_rights_review_needed"
TODO_EXPLANATION = "TODO: add a short learner-facing explanation."
PLACEHOLDER_EXPLANATIONS = {
    "todo",
    "tbd",
    "n/a",
    "na",
    "none",
    "placeholder",
    "generic placeholder",
    TODO_EXPLANATION.casefold(),
    "todo: add explanation",
    "todo: add a short explanation",
    "todo: add a short learner-facing explanation",
}

PROMOTED_FIELD_ORDER = (
    "id",
    "language",
    "canonical_reference",
    "reference_type",
    "surface_patterns",
    "short_explanation",
    "learner_level",
    "confidence",
    "review_status",
    "reviewed_by",
    "reviewed_at",
    "register",
    "variants",
    "avoid_if",
    "explanation_key",
    "source_work_key",
    "source_author_key",
    "source_work",
    "source_author",
    "source_location",
    "source_url",
    "source_license",
    "rights_basis",
    "source_dataset",
    "allow_short_pattern",
    "review_notes",
    "notes",
)


class PromotionError(ValueError):
    """Raised when a draft promotion cannot be safely completed."""


@dataclass(frozen=True)
class AllowlistItem:
    canonical_reference: str
    source_dataset: str | None = None

    @property
    def label(self) -> str:
        if self.source_dataset:
            return f"{self.canonical_reference} [{self.source_dataset}]"
        return self.canonical_reference


if yaml is not None:
    class IndentedDumper(yaml.SafeDumper):
        """PyYAML dumper that indents sequence items under their mapping keys."""

        def increase_indent(self, flow: bool = False, indentless: bool = False):  # type: ignore[override]
            return super().increase_indent(flow, False)
else:
    IndentedDumper = None  # type: ignore[assignment]


def clean_text(value: Any) -> str:
    return unicodedata.normalize("NFC", str(value)).strip()


def normalise_key(value: Any) -> str:
    return clean_text(value).casefold()


def parse_scalar(value: str) -> Any:
    import json

    value = value.strip()
    if not value:
        return ""
    if value[0] == '"':
        return json.loads(value)
    if value[0] == "'" and value[-1:] == "'":
        return value[1:-1].replace("''", "'")
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


def load_minimal_yaml_list(text: str, path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    lines = text.splitlines()
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
            raise PromotionError(f"{path}:{idx + 1}: unsupported YAML line {raw!r}")
        if ":" not in content:
            raise PromotionError(f"{path}:{idx + 1}: unsupported YAML line {raw!r}")
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
                if not item_raw.strip() or item_raw.strip().startswith("#"):
                    idx += 1
                    continue
                item_content = None
                if item_raw.startswith("    - "):
                    item_content = item_raw[6:]
                elif item_raw.startswith("  - "):
                    item_content = item_raw[4:]
                if item_content is None:
                    break
                items.append(parse_scalar(item_content))
                idx += 1
            current[key] = items
            continue
        scalar = parse_scalar(value)
        idx += 1
        continuation: list[str] = []
        while idx < len(lines) and lines[idx].startswith("    ") and not lines[idx].startswith("    - "):
            continuation.append(lines[idx].strip())
            idx += 1
        if continuation and isinstance(scalar, str):
            scalar = " ".join([scalar, *continuation])
        current[key] = scalar
    return rows


def load_yaml_list(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        data = yaml.safe_load(text)
    else:
        data = load_minimal_yaml_list(text, path)
    if data is None:
        return []
    if not isinstance(data, list):
        raise PromotionError(f"{path}: expected a YAML list")
    rows: list[dict[str, Any]] = []
    for idx, row in enumerate(data, start=1):
        if not isinstance(row, dict):
            raise PromotionError(f"{path}: row {idx} must be a mapping")
        rows.append(row)
    return rows


def parse_allowlist(path: Path) -> list[AllowlistItem]:
    items: list[AllowlistItem] = []
    seen: set[tuple[str, str | None]] = set()
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        # The documented format is one canonical_reference per line. A tab or
        # pipe suffix is accepted for rare duplicate names where source_dataset
        # is needed to resolve the intended draft row.
        source_dataset: str | None = None
        canonical = line
        if "\t" in line:
            canonical, source_dataset = [part.strip() for part in line.split("\t", 1)]
        elif " | " in line:
            canonical, source_dataset = [part.strip() for part in line.split(" | ", 1)]
        if not canonical:
            raise PromotionError(f"{path}:{line_number}: empty canonical_reference")
        source_dataset = source_dataset or None
        key = (normalise_key(canonical), normalise_key(source_dataset) if source_dataset else None)
        if key in seen:
            raise PromotionError(f"{path}:{line_number}: duplicate allowlist item {canonical!r}")
        seen.add(key)
        items.append(AllowlistItem(canonical, source_dataset))
    if not items:
        raise PromotionError(f"{path}: allowlist did not contain any entries")
    return items


def explanation_is_placeholder(value: Any) -> bool:
    text = clean_text(value)
    if not text:
        return True
    folded = text.casefold().strip(" .!?:;-")
    if folded in PLACEHOLDER_EXPLANATIONS:
        return True
    if "todo" in folded or "placeholder" in folded:
        return True
    generic_phrases = (
        "short learner-facing explanation",
        "add a short explanation",
        "needs explanation",
        "needs a short explanation",
    )
    return any(phrase in folded for phrase in generic_phrases)


def all_surface_patterns(entry: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for field in ("surface_patterns", "variants"):
        field_value = entry.get(field) or []
        if isinstance(field_value, list):
            values.extend(clean_text(value) for value in field_value if clean_text(value))
    return values


def select_entries(draft_rows: list[dict[str, Any]], allowlist: list[AllowlistItem]) -> list[dict[str, Any]]:
    by_canonical: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in draft_rows:
        by_canonical[normalise_key(row.get("canonical_reference", ""))].append(row)

    selected: list[dict[str, Any]] = []
    for item in allowlist:
        matches = by_canonical.get(normalise_key(item.canonical_reference), [])
        if item.source_dataset:
            matches = [
                row
                for row in matches
                if normalise_key(row.get("source_dataset", "")) == normalise_key(item.source_dataset)
            ]
        if not matches:
            raise PromotionError(f"allowlist item {item.label!r} matched zero draft entries")
        if len(matches) > 1:
            datasets = sorted({clean_text(row.get("source_dataset", "")) for row in matches})
            hint = ""
            if len(datasets) > 1:
                hint = " (add a tab or ' | ' source_dataset qualifier to the allowlist line)"
            raise PromotionError(f"allowlist item {item.label!r} matched multiple draft entries{hint}")
        selected.append(matches[0])
    return selected


def existing_indexes(seed_rows: Iterable[dict[str, Any]]) -> tuple[set[str], set[tuple[str, str]], dict[str, list[str]]]:
    ids: set[str] = set()
    canonical: set[tuple[str, str]] = set()
    surfaces: dict[str, list[str]] = defaultdict(list)
    for row in seed_rows:
        lang = normalise_key(row.get("language", ""))
        eid = clean_text(row.get("id", ""))
        if eid:
            ids.add(eid)
        canonical.add((lang, normalise_key(row.get("canonical_reference", ""))))
        for pattern in all_surface_patterns(row):
            surfaces[f"{lang}\0{normalise_key(pattern)}"].append(eid or clean_text(row.get("canonical_reference", "")))
    return ids, canonical, surfaces


def promoted_entry(entry: dict[str, Any], reviewed_by: str, reviewed_at: str) -> dict[str, Any]:
    promoted = dict(entry)
    promoted["review_status"] = "reviewed"
    promoted["reviewed_by"] = reviewed_by
    promoted["reviewed_at"] = reviewed_at
    return {key: promoted[key] for key in PROMOTED_FIELD_ORDER if key in promoted and promoted[key] not in (None, "", [])}


def validate_selected_entries(
    selected: list[dict[str, Any]],
    seed_rows: list[dict[str, Any]],
    *,
    reviewed_by: str,
    reviewed_at: str,
    min_confidence: float,
    allow_missing_source_location: bool,
    allow_rights_review: bool,
    skip_existing: bool,
    allow_duplicate_surface: bool,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    existing_ids, existing_canonicals, existing_surfaces = existing_indexes(seed_rows)
    batch_ids: set[str] = set()
    batch_canonicals: set[tuple[str, str]] = set()
    batch_surfaces: dict[str, list[str]] = defaultdict(list)
    promoted: list[dict[str, Any]] = []
    skipped: list[str] = []
    refused: list[str] = []

    for entry in selected:
        label = clean_text(entry.get("canonical_reference", "<missing canonical_reference>"))
        lang = normalise_key(entry.get("language", ""))
        eid = clean_text(entry.get("id", ""))
        canonical_key = (lang, normalise_key(entry.get("canonical_reference", "")))
        entry_errors: list[str] = []

        if not eid:
            entry_errors.append("missing id")
        elif eid in existing_ids or eid in batch_ids:
            entry_errors.append(f"duplicate id {eid!r}")
        if canonical_key in batch_canonicals:
            entry_errors.append("duplicate language + canonical_reference in selected batch")
        if canonical_key in existing_canonicals:
            if skip_existing:
                skipped.append(f"{label}: already exists in seed")
                continue
            entry_errors.append("language + canonical_reference already exists in seed")
        if clean_text(entry.get("review_status", "draft")) == "rejected":
            entry_errors.append("review_status is rejected")
        if clean_text(entry.get("source_license", "")) == RIGHTS_REVIEW_LICENSE and not allow_rights_review:
            entry_errors.append(f"source_license is {RIGHTS_REVIEW_LICENSE}")
        if explanation_is_placeholder(entry.get("short_explanation")):
            entry_errors.append("short_explanation is missing or placeholder text")
        if not clean_text(entry.get("source_location", "")) and not allow_missing_source_location:
            entry_errors.append("missing source_location")
        try:
            confidence = float(entry.get("confidence"))
        except (TypeError, ValueError):
            entry_errors.append("confidence is not numeric")
        else:
            if confidence < min_confidence:
                entry_errors.append(f"confidence {confidence:.2f} is below minimum {min_confidence:.2f}")
        if not allow_duplicate_surface:
            for pattern in all_surface_patterns(entry):
                surface_key = f"{lang}\0{normalise_key(pattern)}"
                if existing_surfaces.get(surface_key):
                    entry_errors.append(f"surface pattern {pattern!r} already exists in seed")
                if batch_surfaces.get(surface_key):
                    entry_errors.append(f"surface pattern {pattern!r} duplicates another selected entry")
        if entry_errors:
            refused.append(f"{label}: " + "; ".join(dict.fromkeys(entry_errors)))
            continue

        promoted_row = promoted_entry(entry, reviewed_by, reviewed_at)
        promoted.append(promoted_row)
        if eid:
            batch_ids.add(eid)
        batch_canonicals.add(canonical_key)
        for pattern in all_surface_patterns(entry):
            batch_surfaces[f"{lang}\0{normalise_key(pattern)}"].append(eid or label)

    return promoted, skipped, refused


def dump_scalar(value: Any) -> str:
    import json

    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if value is None:
        return "null"
    return json.dumps(clean_text(value), ensure_ascii=False)


def dump_minimal_yaml(entries: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for entry in entries:
        first = True
        for key, value in entry.items():
            prefix = "- " if first else "  "
            first = False
            if isinstance(value, list):
                lines.append(f"{prefix}{key}:")
                lines.extend(f"    - {dump_scalar(item)}" for item in value)
            else:
                lines.append(f"{prefix}{key}: {dump_scalar(value)}")
    return "\n".join(lines) + ("\n" if lines else "")


def dump_yaml_block(entries: list[dict[str, Any]]) -> str:
    if yaml is None:
        return dump_minimal_yaml(entries)
    return yaml.dump(
        entries,
        Dumper=IndentedDumper,
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        width=100,
    )


def append_entries(seed_path: Path, promoted: list[dict[str, Any]]) -> None:
    existing_text = seed_path.read_text(encoding="utf-8")
    separator = "" if existing_text.endswith("\n") else "\n"
    seed_path.write_text(existing_text + separator + dump_yaml_block(promoted), encoding="utf-8")


def summary_text(promoted: list[dict[str, Any]], skipped: list[str], refused: list[str]) -> str:
    counts = Counter(clean_text(entry.get("language", "unknown")) for entry in promoted)
    lines = [
        "Promotion summary:",
        f"  promoted: {len(promoted)}",
        f"  skipped: {len(skipped)}",
        f"  refused: {len(refused)}",
    ]
    if counts:
        lines.append("  promoted_by_language: " + ", ".join(f"{lang}={count}" for lang, count in sorted(counts.items())))
    if promoted:
        lines.append("  promoted_entries:")
        lines.extend(f"    - {entry['canonical_reference']}" for entry in promoted)
    if skipped:
        lines.append("  skipped_entries:")
        lines.extend(f"    - {item}" for item in skipped)
    if refused:
        lines.append("  refused_entries:")
        lines.extend(f"    - {item}" for item in refused)
    return "\n".join(lines)


def promote(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    if not clean_text(args.reviewed_by):
        raise PromotionError("--reviewed-by is required and must not be blank")
    if not clean_text(args.reviewed_at):
        raise PromotionError("--reviewed-at is required and must not be blank")
    if not 0 <= args.min_confidence <= 1:
        raise PromotionError("--min-confidence must be between 0 and 1")

    draft_rows = load_yaml_list(args.draft)
    seed_rows = load_yaml_list(args.seed)
    allowlist = parse_allowlist(args.allowlist)
    selected = select_entries(draft_rows, allowlist)
    promoted, skipped, refused = validate_selected_entries(
        selected,
        seed_rows,
        reviewed_by=clean_text(args.reviewed_by),
        reviewed_at=clean_text(args.reviewed_at),
        min_confidence=args.min_confidence,
        allow_missing_source_location=args.allow_missing_source_location,
        allow_rights_review=args.allow_rights_review,
        skip_existing=args.skip_existing,
        allow_duplicate_surface=args.allow_duplicate_surface,
    )
    if refused:
        raise PromotionError(summary_text(promoted, skipped, refused))
    return promoted, skipped, refused


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft", type=Path, default=DEFAULT_DRAFT)
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--allowlist", type=Path, default=DEFAULT_ALLOWLIST)
    parser.add_argument("--reviewed-by", required=True)
    parser.add_argument("--reviewed-at", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--min-confidence", type=float, default=0.80)
    parser.add_argument("--allow-missing-source-location", action="store_true", default=False)
    parser.add_argument("--allow-rights-review", action="store_true", default=False)
    parser.add_argument("--skip-existing", action="store_true", default=False)
    parser.add_argument("--allow-duplicate-surface", action="store_true", default=False)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        promoted, skipped, refused = promote(args)
        if args.dry_run:
            print("Proposed YAML block:")
            print(dump_yaml_block(promoted), end="")
        elif promoted:
            append_entries(args.seed, promoted)
        print(summary_text(promoted, skipped, refused))
    except PromotionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
