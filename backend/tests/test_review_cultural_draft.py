from __future__ import annotations

from pathlib import Path

import importlib.util

import pytest

yaml = pytest.importorskip("yaml") if importlib.util.find_spec("yaml") else None
pytestmark = pytest.mark.skipif(yaml is None, reason="PyYAML is required for review tool tests")

from scripts import review_cultural_draft as reviewer
from scripts.build_cultural_catalog import validate_and_build


def _entry(**overrides: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "id": "en_literary_reference_big_brother_abc12345",
        "language": "en",
        "canonical_reference": "Big Brother",
        "reference_type": "literary_reference",
        "surface_patterns": ["Big Brother"],
        "variants": ["Big Brother is watching"],
        "short_explanation": "An intrusive, all-seeing authority or surveillance state.",
        "learner_level": "B2",
        "confidence": 0.84,
        "review_status": "draft",
        "register": "literary",
        "source_work": "Nineteen Eighty-Four",
        "source_author": "George Orwell",
        "source_location": "Part 1, Chapter 1",
        "source_url": "https://example.org/1984",
        "source_license": "public_domain",
        "source_dataset": "unit_test_dataset",
    }
    entry.update(overrides)
    return entry


def _write_yaml(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(reviewer.dump_yaml(rows), encoding="utf-8")


def _load_yaml(path: Path) -> list[dict[str, object]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    return data


def test_output_filename_inserts_reviewed_for_generated_yaml(tmp_path) -> None:
    draft = tmp_path / "en_literary_idioms_normalised_v3.generated.yaml"

    assert reviewer.default_output_path(draft) == tmp_path / "en_literary_idioms_normalised_v3.generated_reviewed.yaml"


def test_reviewed_entries_get_review_metadata(tmp_path) -> None:
    draft = tmp_path / "draft.generated.yaml"
    out = tmp_path / "reviewed.yaml"
    _write_yaml(draft, [_entry()])

    rc = reviewer.main([
        "--draft",
        str(draft),
        "--out",
        str(out),
        "--reviewed-by",
        "paul",
        "--reviewed-at",
        "2026-06-07",
        "--non-interactive",
    ])

    assert rc == 0
    row = _load_yaml(out)[0]
    assert row["review_status"] == "reviewed"
    assert row["reviewed_by"] == "paul"
    assert row["reviewed_at"] == "2026-06-07"


def test_missing_source_location_triggers_prompt_and_can_be_filled(tmp_path, monkeypatch, capsys) -> None:
    draft = tmp_path / "draft.generated.yaml"
    out = tmp_path / "reviewed.yaml"
    _write_yaml(draft, [_entry(source_location="")])
    answers = iter(["Part 1, Chapter 1"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))

    rc = reviewer.main([
        "--draft",
        str(draft),
        "--out",
        str(out),
        "--reviewed-by",
        "paul",
        "--reviewed-at",
        "2026-06-07",
    ])

    assert rc == 0
    assert "Source location: <missing>" in capsys.readouterr().out
    row = _load_yaml(out)[0]
    assert row["source_location"] == "Part 1, Chapter 1"
    assert row["review_status"] == "reviewed"


def test_accepting_missing_source_location_appends_review_note(tmp_path, monkeypatch) -> None:
    draft = tmp_path / "draft.generated.yaml"
    out = tmp_path / "reviewed.yaml"
    _write_yaml(draft, [_entry(source_location="")])
    answers = iter(["a"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))

    assert reviewer.main([
        "--draft",
        str(draft),
        "--out",
        str(out),
        "--reviewed-by",
        "paul",
        "--reviewed-at",
        "2026-06-07",
    ]) == 0

    row = _load_yaml(out)[0]
    assert row["review_status"] == "reviewed"
    assert "missing source_location accepted by paul on 2026-06-07" in row["review_notes"]


def test_copyright_or_rights_review_needed_is_not_silently_changed(tmp_path, monkeypatch) -> None:
    draft = tmp_path / "draft.generated.yaml"
    out = tmp_path / "reviewed.yaml"
    _write_yaml(draft, [_entry(source_license=reviewer.RIGHTS_REVIEW_LICENSE)])
    answers = iter(["k"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))

    assert reviewer.main([
        "--draft",
        str(draft),
        "--out",
        str(out),
        "--reviewed-by",
        "paul",
        "--reviewed-at",
        "2026-06-07",
    ]) == 0

    row = _load_yaml(out)[0]
    assert row["source_license"] == reviewer.RIGHTS_REVIEW_LICENSE
    assert row["review_status"] == "needs_native_review"


def test_rights_review_entries_not_marked_reviewed_unless_confirmed(tmp_path, monkeypatch) -> None:
    draft = tmp_path / "draft.generated.yaml"
    out = tmp_path / "reviewed.yaml"
    _write_yaml(draft, [_entry(source_license=reviewer.RIGHTS_REVIEW_LICENSE)])
    answers = iter(["r", "not the confirmation"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))

    assert reviewer.main([
        "--draft",
        str(draft),
        "--out",
        str(out),
        "--reviewed-by",
        "paul",
        "--reviewed-at",
        "2026-06-07",
    ]) == 0

    row = _load_yaml(out)[0]
    assert row["source_license"] == reviewer.RIGHTS_REVIEW_LICENSE
    assert row["review_status"] == "draft"

    out2 = tmp_path / "reviewed2.yaml"
    _write_yaml(draft, [_entry(source_license=reviewer.RIGHTS_REVIEW_LICENSE)])
    answers = iter(["r", "REVIEWED_RIGHTS"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    assert reviewer.main([
        "--draft",
        str(draft),
        "--out",
        str(out2),
        "--reviewed-by",
        "paul",
        "--reviewed-at",
        "2026-06-07",
    ]) == 0
    confirmed = _load_yaml(out2)[0]
    assert confirmed["review_status"] == "reviewed"
    assert reviewer.RIGHTS_REVIEW_LICENSE == confirmed["source_license"]
    assert "Rights-review flag explicitly retained" in confirmed["review_notes"]


def test_generic_placeholder_explanation_is_refused_unless_replaced(tmp_path, monkeypatch) -> None:
    draft = tmp_path / "draft.generated.yaml"
    out = tmp_path / "reviewed.yaml"
    _write_yaml(draft, [_entry(short_explanation="TODO: add explanation")])
    answers = iter(["s"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))

    assert reviewer.main([
        "--draft",
        str(draft),
        "--out",
        str(out),
        "--reviewed-by",
        "paul",
        "--reviewed-at",
        "2026-06-07",
    ]) == 0
    assert _load_yaml(out)[0]["review_status"] == "draft"

    out2 = tmp_path / "reviewed2.yaml"
    answers = iter(["A symbol of intrusive surveillance and authoritarian control."])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))
    assert reviewer.main([
        "--draft",
        str(draft),
        "--out",
        str(out2),
        "--reviewed-by",
        "paul",
        "--reviewed-at",
        "2026-06-07",
    ]) == 0
    row = _load_yaml(out2)[0]
    assert row["review_status"] == "reviewed"
    assert row["short_explanation"] == "A symbol of intrusive surveillance and authoritarian control."


def test_missing_public_domain_source_url_can_be_accepted_with_note(tmp_path, monkeypatch) -> None:
    draft = tmp_path / "draft.generated.yaml"
    out = tmp_path / "reviewed.yaml"
    _write_yaml(draft, [_entry(source_url="")])
    answers = iter(["a"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))

    assert reviewer.main([
        "--draft",
        str(draft),
        "--out",
        str(out),
        "--reviewed-by",
        "paul",
        "--reviewed-at",
        "2026-06-07",
    ]) == 0

    row = _load_yaml(out)[0]
    assert row["review_status"] == "reviewed"
    assert "missing source_url accepted by paul on 2026-06-07" in row["review_notes"]


def test_non_interactive_reviews_only_entries_that_pass_checks(tmp_path) -> None:
    draft = tmp_path / "draft.generated.yaml"
    out = tmp_path / "reviewed.yaml"
    _write_yaml(
        draft,
        [
            _entry(id="en_literary_reference_big_brother_abc12345"),
            _entry(id="en_literary_reference_missing_def67890", canonical_reference="Missing", surface_patterns=["Missing"], source_location=""),
        ],
    )

    assert reviewer.main([
        "--draft",
        str(draft),
        "--out",
        str(out),
        "--reviewed-by",
        "paul",
        "--reviewed-at",
        "2026-06-07",
        "--non-interactive",
    ]) == 0

    rows = _load_yaml(out)
    assert rows[0]["review_status"] == "reviewed"
    assert rows[1]["review_status"] == "draft"


def test_dry_run_does_not_write_output(tmp_path) -> None:
    draft = tmp_path / "draft.generated.yaml"
    out = tmp_path / "reviewed.yaml"
    _write_yaml(draft, [_entry()])

    assert reviewer.main([
        "--draft",
        str(draft),
        "--out",
        str(out),
        "--reviewed-by",
        "paul",
        "--reviewed-at",
        "2026-06-07",
        "--non-interactive",
        "--dry-run",
    ]) == 0

    assert not out.exists()


def test_q_saves_progress_and_exits_cleanly(tmp_path, monkeypatch) -> None:
    draft = tmp_path / "draft.generated.yaml"
    out = tmp_path / "reviewed.yaml"
    _write_yaml(
        draft,
        [
            _entry(id="en_literary_reference_one_abc12345", canonical_reference="One", surface_patterns=["One"]),
            _entry(id="en_literary_reference_two_def67890", canonical_reference="Two", surface_patterns=["Two"], source_location=""),
        ],
    )
    answers = iter(["q"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))

    assert reviewer.main([
        "--draft",
        str(draft),
        "--out",
        str(out),
        "--reviewed-by",
        "paul",
        "--reviewed-at",
        "2026-06-07",
    ]) == 0

    rows = _load_yaml(out)
    assert rows[0]["review_status"] == "reviewed"
    assert rows[1]["review_status"] == "draft"


def test_output_yaml_validates_with_build_cultural_catalog(tmp_path) -> None:
    draft = tmp_path / "draft.generated.yaml"
    out = tmp_path / "reviewed.yaml"
    _write_yaml(draft, [_entry()])

    assert reviewer.main([
        "--draft",
        str(draft),
        "--out",
        str(out),
        "--reviewed-by",
        "paul",
        "--reviewed-at",
        "2026-06-07",
        "--non-interactive",
    ]) == 0

    rows = _load_yaml(out)
    by_lang, warnings = validate_and_build(rows, include_drafts=True)
    assert len(by_lang["en"]) == 1
    assert warnings == []
