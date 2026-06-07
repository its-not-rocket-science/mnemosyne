#!/usr/bin/env python3
"""Interactively review generated cultural catalogue draft YAML files.

This tool updates review-critical metadata in a generated draft and writes a
reviewed copy. It never promotes rows into data/cultural_references_seed.yaml.

Output naming convention: when the input filename ends in ``.generated.yaml``,
``_reviewed`` is inserted before the final ``.yaml`` suffix (for example,
``foo.generated.yaml`` becomes ``foo.generated_reviewed.yaml``). Other ``.yaml``
or ``.yml`` files become ``foo_reviewed.yaml``/``foo_reviewed.yml``.
"""
from __future__ import annotations

import argparse
import builtins
import os
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Callable

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - exercised in minimal environments
    yaml = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parents[1]
RIGHTS_REVIEW_LICENSE = "copyright_or_rights_review_needed"
PLACEHOLDER_EXPLANATIONS = {
    "todo",
    "tbd",
    "n/a",
    "na",
    "none",
    "placeholder",
    "generic placeholder",
    "todo: add explanation",
    "todo: add a short explanation",
    "todo: add a short learner-facing explanation",
    "todo: add a short learner-facing explanation.",
    "a biblical/kjv expression or allusion used figuratively in modern english.",
    "a shakespearean phrase or quotation still used allusively.",
}
FIELD_ORDER = (
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
    "source_dataset",
    "allow_short_pattern",
    "review_notes",
    "notes",
)
RIGHTS_REVIEW_CONFIRMED_NOTE = "Rights-review flag explicitly retained"


class ReviewError(ValueError):
    """Raised when a draft cannot be safely reviewed or written."""


@dataclass
class ReviewStats:
    entries_loaded: int = 0
    entries_reviewed: int = 0
    entries_left_draft: int = 0
    entries_skipped: int = 0
    source_location_filled: int = 0
    source_url_filled: int = 0
    rights_review_retained: int = 0
    generic_explanations_replaced: int = 0
    warnings: list[str] = field(default_factory=list)
    quit_requested: bool = False


class IndentedDumper(yaml.SafeDumper if yaml is not None else object):  # type: ignore[misc]
    """PyYAML dumper that emits readable block-style nested sequences."""

    def increase_indent(self, flow: bool = False, indentless: bool = False):  # type: ignore[override]
        return super().increase_indent(flow, False)  # type: ignore[misc]


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return unicodedata.normalize("NFC", str(value)).strip()


def is_blank(value: Any) -> bool:
    return clean_text(value) == ""


def is_generic_explanation(value: Any) -> bool:
    text = clean_text(value).casefold()
    return not text or text in PLACEHOLDER_EXPLANATIONS


def default_output_path(draft: Path) -> Path:
    name = draft.name
    if name.endswith(".generated.yaml"):
        return draft.with_name(f"{name[:-len('.yaml')]}_reviewed.yaml")
    if name.endswith(".generated.yml"):
        return draft.with_name(f"{name[:-len('.yml')]}_reviewed.yml")
    if draft.suffix in {".yaml", ".yml"}:
        return draft.with_name(f"{draft.stem}_reviewed{draft.suffix}")
    return draft.with_name(f"{draft.name}_reviewed.yaml")


def require_yaml() -> None:
    if yaml is None:
        raise ReviewError("PyYAML is required for interactive draft review. Install pyyaml.")


def load_yaml_list(path: Path) -> list[dict[str, Any]]:
    require_yaml()
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ReviewError("draft YAML must contain a list of entries")
    for idx, row in enumerate(data, start=1):
        if not isinstance(row, dict):
            raise ReviewError(f"row {idx}: entry must be a mapping")
    return data


def ordered_entry(entry: dict[str, Any]) -> dict[str, Any]:
    ordered: dict[str, Any] = {}
    for key in FIELD_ORDER:
        if key in entry:
            ordered[key] = entry[key]
    for key, value in entry.items():
        if key not in ordered:
            ordered[key] = value
    return ordered


def dump_yaml(rows: list[dict[str, Any]]) -> str:
    require_yaml()
    ordered = [ordered_entry(row) for row in rows]
    return yaml.dump(
        ordered,
        Dumper=IndentedDumper,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=100,
    )


def write_yaml(path: Path, rows: list[dict[str, Any]], overwrite: bool = False) -> None:
    if path.exists() and not overwrite:
        raise ReviewError(f"output file already exists: {path} (use --overwrite to replace it)")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_yaml(rows), encoding="utf-8")


def append_review_note(entry: dict[str, Any], note: str) -> None:
    existing = entry.get("review_notes")
    if is_blank(existing):
        entry["review_notes"] = note
        return
    text = clean_text(existing)
    if note not in text:
        entry["review_notes"] = f"{text}\n{note}"


def accepted_missing_location_note(reviewer: str, reviewed_at: str) -> str:
    return f"Reviewed with missing source_location accepted by {reviewer} on {reviewed_at}."


def accepted_missing_url_note(reviewer: str, reviewed_at: str) -> str:
    return f"Reviewed with missing source_url accepted by {reviewer} on {reviewed_at}."


def confirmed_rights_note(reviewer: str, reviewed_at: str) -> str:
    return f"{RIGHTS_REVIEW_CONFIRMED_NOTE} by {reviewer} on {reviewed_at}."


def has_missing_location_acceptance(entry: dict[str, Any]) -> bool:
    return "missing source_location accepted" in clean_text(entry.get("review_notes")).casefold()


def has_missing_url_acceptance(entry: dict[str, Any]) -> bool:
    return "missing source_url accepted" in clean_text(entry.get("review_notes")).casefold()


def has_rights_confirmation(entry: dict[str, Any]) -> bool:
    return RIGHTS_REVIEW_CONFIRMED_NOTE.casefold() in clean_text(entry.get("review_notes")).casefold()


def source_license_missing_and_sensitive(entry: dict[str, Any]) -> bool:
    """Return True for rows whose blank licence needs human rights review.

    The tool does not infer copyright status; this heuristic only identifies
    rows with source metadata but no explicit licence as review-sensitive.
    """
    return is_blank(entry.get("source_license")) and (
        not is_blank(entry.get("source_work")) or not is_blank(entry.get("source_author"))
    )


def needs_action(entry: dict[str, Any], skip_rights_review: bool = False) -> bool:
    if is_blank(entry.get("source_location")) and not has_missing_location_acceptance(entry):
        return True
    if is_generic_explanation(entry.get("short_explanation")):
        return True
    if clean_text(entry.get("source_license")) == RIGHTS_REVIEW_LICENSE and not skip_rights_review:
        return True
    if source_license_missing_and_sensitive(entry) and not skip_rights_review:
        return True
    if clean_text(entry.get("source_license")) == "public_domain" and is_blank(entry.get("source_url")) and not has_missing_url_acceptance(entry):
        return True
    return False


def set_reviewed(entry: dict[str, Any], reviewer: str, reviewed_at: str) -> None:
    entry["review_status"] = "reviewed"
    entry["reviewed_by"] = reviewer
    entry["reviewed_at"] = reviewed_at


def set_draft(entry: dict[str, Any]) -> None:
    if clean_text(entry.get("review_status")) not in {"needs_native_review", "rejected"}:
        entry["review_status"] = "draft"


def format_list(values: Any) -> str:
    if isinstance(values, list) and values:
        return "\n".join(f"  - {value}" for value in values)
    return "  <missing>"


def display_entry_summary(entry: dict[str, Any]) -> None:
    print("-" * 60)
    print(f"ID: {clean_text(entry.get('id')) or '<missing>'}")
    print(f"Canonical: {clean_text(entry.get('canonical_reference')) or '<missing>'}")
    print(f"Type: {clean_text(entry.get('reference_type')) or '<missing>'}")
    print("Surface patterns:")
    print(format_list(entry.get("surface_patterns")))
    print("Variants:")
    print(format_list(entry.get("variants")))
    print(f"Source work: {clean_text(entry.get('source_work')) or '<missing>'}")
    print(f"Source author: {clean_text(entry.get('source_author')) or '<missing>'}")
    print(f"Source location: {clean_text(entry.get('source_location')) or '<missing>'}")
    print(f"Source URL: {clean_text(entry.get('source_url')) or '<missing>'}")
    print(f"Source licence: {clean_text(entry.get('source_license')) or '<missing>'}")
    print(f"Confidence: {entry.get('confidence', '<missing>')}")
    print(f"Explanation: {clean_text(entry.get('short_explanation')) or '<missing>'}")
    print(f"Current review_status: {clean_text(entry.get('review_status')) or 'draft'}")
    print("-" * 60)


def prompt_missing_source_location(
    entry: dict[str, Any], reviewer: str, reviewed_at: str, stats: ReviewStats, input_fn: Callable[[str], str]
) -> str:
    print(f"Entry: {clean_text(entry.get('canonical_reference')) or '<missing>'}")
    print(f"Source work: {clean_text(entry.get('source_work')) or '<missing>'}")
    print(f"Source author: {clean_text(entry.get('source_author')) or '<missing>'}")
    print(f"Surface patterns: {', '.join(entry.get('surface_patterns') or []) or '<missing>'}")
    print(f"Short explanation: {clean_text(entry.get('short_explanation')) or '<missing>'}\n")
    answer = clean_text(input_fn("source_location is missing.\nEnter source_location, or type:\n  s = skip entry\n  a = allow missing location for this entry\n  q = quit and save progress\n> "))
    if answer == "q":
        return "quit"
    if answer == "s":
        return "skip"
    if answer == "a":
        append_review_note(entry, accepted_missing_location_note(reviewer, reviewed_at))
        return "continue"
    if answer:
        entry["source_location"] = answer
        stats.source_location_filled += 1
        return "continue"
    return "skip"


def prompt_rights_review(
    entry: dict[str, Any], reviewer: str, reviewed_at: str, stats: ReviewStats, input_fn: Callable[[str], str]
) -> str:
    current = clean_text(entry.get("source_license")) or "<missing>"
    print(f"Entry: {clean_text(entry.get('canonical_reference')) or '<missing>'}")
    print(f"Source work: {clean_text(entry.get('source_work')) or '<missing>'}")
    print(f"Source author: {clean_text(entry.get('source_author')) or '<missing>'}")
    print(f"Current source_license: {current}\n")
    answer = clean_text(input_fn("Rights review is needed.\nChoose:\n  k = keep as rights-review-needed and leave draft\n  r = mark reviewed despite rights flag\n  l = replace source_license\n  s = skip\n  q = quit and save progress\n> "))
    if answer == "q":
        return "quit"
    if answer in {"k", "s", ""}:
        if answer == "k":
            entry["source_license"] = RIGHTS_REVIEW_LICENSE
            entry["review_status"] = "needs_native_review"
            stats.rights_review_retained += 1
        return "skip"
    if answer == "r":
        confirm = clean_text(input_fn("Type REVIEWED_RIGHTS to confirm.\n> "))
        if confirm != "REVIEWED_RIGHTS":
            return "skip"
        if is_blank(entry.get("source_license")):
            entry["source_license"] = RIGHTS_REVIEW_LICENSE
        append_review_note(entry, confirmed_rights_note(reviewer, reviewed_at))
        stats.rights_review_retained += 1
        return "continue"
    if answer == "l":
        replacement = clean_text(input_fn("Enter replacement source_license (for example public_domain, CC0, CC-BY-4.0):\n> "))
        if not replacement:
            return "skip"
        entry["source_license"] = replacement
        return "continue"
    return "skip"


def prompt_generic_explanation(entry: dict[str, Any], stats: ReviewStats, input_fn: Callable[[str], str]) -> str:
    answer = clean_text(input_fn("short_explanation appears generic.\nEnter improved short_explanation, or type:\n  s = skip entry\n  q = quit and save progress\n> "))
    if answer == "q":
        return "quit"
    if answer == "s" or is_generic_explanation(answer):
        return "skip"
    entry["short_explanation"] = answer
    stats.generic_explanations_replaced += 1
    return "continue"


def prompt_missing_source_url(
    entry: dict[str, Any], reviewer: str, reviewed_at: str, stats: ReviewStats, input_fn: Callable[[str], str]
) -> str:
    answer = clean_text(input_fn("source_url is blank for a public-domain entry.\nEnter source_url, or type:\n  a = allow missing URL\n  s = skip\n  q = quit and save progress\n> "))
    if answer == "q":
        return "quit"
    if answer == "s" or not answer:
        return "skip"
    if answer == "a":
        append_review_note(entry, accepted_missing_url_note(reviewer, reviewed_at))
        return "continue"
    entry["source_url"] = answer
    stats.source_url_filled += 1
    return "continue"


def review_entry_interactive(
    entry: dict[str, Any], args: argparse.Namespace, stats: ReviewStats, input_fn: Callable[[str], str]
) -> str:
    display_entry_summary(entry)
    reviewer = args.reviewed_by
    reviewed_at = args.reviewed_at

    while is_blank(entry.get("source_location")) and not has_missing_location_acceptance(entry):
        if args.allow_missing_source_location:
            append_review_note(entry, accepted_missing_location_note(reviewer, reviewed_at))
            break
        result = prompt_missing_source_location(entry, reviewer, reviewed_at, stats, input_fn)
        if result != "continue":
            return result

    while is_generic_explanation(entry.get("short_explanation")):
        result = prompt_generic_explanation(entry, stats, input_fn)
        if result != "continue":
            return result

    if args.skip_rights_review and (
        clean_text(entry.get("source_license")) == RIGHTS_REVIEW_LICENSE
        or source_license_missing_and_sensitive(entry)
    ):
        if clean_text(entry.get("source_license")) == RIGHTS_REVIEW_LICENSE:
            entry["review_status"] = "needs_native_review"
        else:
            set_draft(entry)
        return "skip"

    while (
        clean_text(entry.get("source_license")) == RIGHTS_REVIEW_LICENSE
        or source_license_missing_and_sensitive(entry)
    ) and not args.skip_rights_review:
        result = prompt_rights_review(entry, reviewer, reviewed_at, stats, input_fn)
        if result != "continue":
            return result
        if clean_text(entry.get("source_license")) == RIGHTS_REVIEW_LICENSE and has_rights_confirmation(entry):
            break

    while clean_text(entry.get("source_license")) == "public_domain" and is_blank(entry.get("source_url")) and not has_missing_url_acceptance(entry):
        result = prompt_missing_source_url(entry, reviewer, reviewed_at, stats, input_fn)
        if result != "continue":
            return result

    set_reviewed(entry, reviewer, reviewed_at)
    stats.entries_reviewed += 1
    return "reviewed"


def can_auto_review(entry: dict[str, Any], args: argparse.Namespace) -> bool:
    if is_generic_explanation(entry.get("short_explanation")):
        return False
    if is_blank(entry.get("source_location")) and not (
        args.allow_missing_source_location or has_missing_location_acceptance(entry)
    ):
        return False
    if clean_text(entry.get("source_license")) == RIGHTS_REVIEW_LICENSE:
        return has_rights_confirmation(entry)
    if source_license_missing_and_sensitive(entry):
        return False
    if clean_text(entry.get("source_license")) == "public_domain" and is_blank(entry.get("source_url")) and not has_missing_url_acceptance(entry):
        return False
    return True


def review_rows(
    rows: list[dict[str, Any]], args: argparse.Namespace, input_fn: Callable[[str], str] | None = None
) -> ReviewStats:
    if input_fn is None:
        input_fn = builtins.input
    stats = ReviewStats(entries_loaded=len(rows))
    start_seen = args.start_at is None
    for entry in rows:
        if not start_seen:
            ident = clean_text(entry.get("id"))
            canonical = clean_text(entry.get("canonical_reference"))
            if args.start_at in {ident, canonical}:
                start_seen = True
            else:
                continue
        if args.limit is not None and stats.entries_reviewed >= args.limit:
            break

        action_needed = needs_action(entry, skip_rights_review=args.skip_rights_review)
        if args.only_missing and not action_needed:
            continue

        if args.non_interactive:
            if can_auto_review(entry, args):
                if args.allow_missing_source_location and is_blank(entry.get("source_location")):
                    append_review_note(entry, accepted_missing_location_note(args.reviewed_by, args.reviewed_at))
                set_reviewed(entry, args.reviewed_by, args.reviewed_at)
                stats.entries_reviewed += 1
            else:
                set_draft(entry)
                stats.entries_left_draft += 1
                stats.entries_skipped += 1
            continue

        if action_needed or not args.only_missing:
            result = review_entry_interactive(entry, args, stats, input_fn)
            if result == "quit":
                stats.quit_requested = True
                break
            if result == "skip":
                set_draft(entry)
                stats.entries_skipped += 1
                stats.entries_left_draft += 1
        else:
            stats.entries_left_draft += 1

    reviewed_count = sum(1 for row in rows if clean_text(row.get("review_status")) == "reviewed")
    stats.entries_left_draft = sum(1 for row in rows if clean_text(row.get("review_status")) != "reviewed")
    # Preserve the number newly processed in entries_reviewed; if none was counted
    # but rows already reviewed exist, keep the summary intuitive for CLI runs.
    if stats.entries_reviewed == 0 and reviewed_count:
        stats.entries_reviewed = reviewed_count
    return stats


def validate_reviewed_rows(rows: list[dict[str, Any]]) -> list[str]:
    if not isinstance(rows, list):
        raise ReviewError("draft YAML must contain a list of entries")
    warnings: list[str] = []
    for idx, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ReviewError(f"row {idx}: entry must be a mapping")
        if clean_text(row.get("review_status")) != "reviewed":
            continue
        label = clean_text(row.get("id")) or f"row {idx}"
        for field_name in ("reviewed_by", "reviewed_at"):
            if is_blank(row.get(field_name)):
                raise ReviewError(f"{label}: reviewed row is missing {field_name}")
        if is_generic_explanation(row.get("short_explanation")):
            raise ReviewError(f"{label}: reviewed row has generic short_explanation")
        if clean_text(row.get("source_license")) == RIGHTS_REVIEW_LICENSE and not has_rights_confirmation(row):
            raise ReviewError(f"{label}: unresolved {RIGHTS_REVIEW_LICENSE} without explicit confirmation")
        if is_blank(row.get("source_location")):
            if has_missing_location_acceptance(row):
                warnings.append(f"{label}: source_location missing with reviewer acceptance")
            else:
                raise ReviewError(f"{label}: reviewed row is missing source_location")
        if clean_text(row.get("source_license")) == "public_domain" and is_blank(row.get("source_url")):
            if has_missing_url_acceptance(row):
                warnings.append(f"{label}: source_url missing with reviewer acceptance")
            else:
                raise ReviewError(f"{label}: public-domain row missing source_url")
    return warnings


def summary_text(out_path: Path, stats: ReviewStats) -> str:
    lines = [
        f"Reviewed draft written to {out_path}",
        "",
        "Summary:",
        f"  entries loaded: {stats.entries_loaded}",
        f"  entries reviewed: {stats.entries_reviewed}",
        f"  entries left draft: {stats.entries_left_draft}",
        f"  entries skipped: {stats.entries_skipped}",
        f"  source_location filled: {stats.source_location_filled}",
        f"  source_url filled: {stats.source_url_filled}",
        f"  rights-review retained: {stats.rights_review_retained}",
        f"  generic explanations replaced: {stats.generic_explanations_replaced}",
    ]
    if stats.warnings:
        lines.append("Warnings:")
        lines.extend(f"  - {warning}" for warning in stats.warnings)
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft", required=True, type=Path)
    parser.add_argument("--reviewed-by", default=os.environ.get("MNEMOSYNE_REVIEWER"))
    parser.add_argument("--reviewed-at", default=date.today().isoformat())
    parser.add_argument("--out", type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--start-at")
    parser.add_argument("--only-missing", action="store_true")
    parser.add_argument("--non-interactive", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-rights-review", action="store_true")
    parser.add_argument("--allow-missing-source-location", action="store_true")
    return parser


def run(args: argparse.Namespace, input_fn: Callable[[str], str] | None = None) -> tuple[list[dict[str, Any]], ReviewStats, Path]:
    if not args.reviewed_by:
        raise ReviewError("--reviewed-by is required unless MNEMOSYNE_REVIEWER is set")
    rows = load_yaml_list(args.draft)
    out_path = args.out or default_output_path(args.draft)
    if out_path == args.draft and not args.overwrite:
        raise ReviewError("refusing to overwrite input file without --overwrite")
    stats = review_rows(rows, args, input_fn=input_fn)
    stats.warnings.extend(validate_reviewed_rows(rows))
    if not args.dry_run:
        write_yaml(out_path, rows, overwrite=args.overwrite)
    return rows, stats, out_path


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        rows, stats, out_path = run(args)
        if args.dry_run:
            print("Dry run; reviewed draft was not written.")
            print("Proposed YAML:")
            print(dump_yaml(rows), end="")
        print(summary_text(out_path, stats))
    except ReviewError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
