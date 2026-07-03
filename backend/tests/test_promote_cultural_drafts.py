from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from scripts import promote_cultural_drafts as promoter
from scripts.build_cultural_catalog import validate_and_build


def _entry(**overrides: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "id": "en_literary_reference_break_the_ice_abc12345",
        "language": "en",
        "canonical_reference": "break the ice",
        "reference_type": "literary_reference",
        "surface_patterns": ["break the ice"],
        "short_explanation": "To ease tension at the start of a social interaction.",
        "learner_level": "B2",
        "confidence": 0.84,
        "review_status": "draft",
        "register": "literary",
        "variants": ["broke the ice"],
        "avoid_if": ["literal ice-breaking"],
        "explanation_key": "mnemosyne.en.explanation.test.break_the_ice",
        "source_work_key": "mnemosyne.en.work.the_taming_of_the_shrew",
        "source_author_key": "mnemosyne.en.author.william_shakespeare",
        "source_work": "The Taming of the Shrew",
        "source_author": "William Shakespeare",
        "source_location": "Act I Scene 2",
        "source_url": "https://example.org/shrew",
        "source_license": "public_domain",
        "source_dataset": "unit_test_dataset",
    }
    entry.update(overrides)
    return entry


def _write_yaml(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(promoter.dump_yaml_block(rows), encoding="utf-8")


def _paths(tmp_path: Path, draft_rows: list[dict[str, object]], allowlist_text: str) -> tuple[Path, Path, Path]:
    draft = tmp_path / "draft.yaml"
    seed = tmp_path / "seed.yaml"
    allowlist = tmp_path / "allowlist.txt"
    _write_yaml(draft, draft_rows)
    _write_yaml(seed, [])
    allowlist.write_text(allowlist_text, encoding="utf-8")
    return draft, seed, allowlist


def _args(draft: Path, seed: Path, allowlist: Path, **overrides: object) -> Namespace:
    args = Namespace(
        draft=draft,
        seed=seed,
        allowlist=allowlist,
        reviewed_by="paul",
        reviewed_at="2026-06-07",
        dry_run=False,
        min_confidence=0.80,
        allow_missing_source_location=False,
        allow_rights_review=False,
        skip_existing=False,
        allow_duplicate_surface=False,
    )
    for key, value in overrides.items():
        setattr(args, key, value)
    return args


def test_dry_run_does_not_modify_seed(tmp_path, capsys) -> None:
    draft, seed, allowlist = _paths(tmp_path, [_entry()], "break the ice\n")
    before = seed.read_text(encoding="utf-8")

    rc = promoter.main(
        [
            "--draft",
            str(draft),
            "--seed",
            str(seed),
            "--allowlist",
            str(allowlist),
            "--reviewed-by",
            "paul",
            "--reviewed-at",
            "2026-06-07",
            "--dry-run",
        ]
    )

    assert rc == 0
    assert seed.read_text(encoding="utf-8") == before
    assert "Proposed YAML block" in capsys.readouterr().out


def test_allowlist_selects_only_named_entries(tmp_path) -> None:
    draft, seed, allowlist = _paths(
        tmp_path,
        [
            _entry(),
            _entry(
                id="en_literary_reference_wild_goose_chase_def67890",
                canonical_reference="wild-goose chase",
                surface_patterns=["wild-goose chase"],
                source_location="Romeo and Juliet, Act II Scene 4",
            ),
        ],
        "break the ice\n",
    )

    promoted, skipped, refused = promoter.promote(_args(draft, seed, allowlist))

    assert skipped == []
    assert refused == []
    assert [entry["canonical_reference"] for entry in promoted] == ["break the ice"]


def test_missing_allowlist_item_fails(tmp_path) -> None:
    draft, seed, allowlist = _paths(tmp_path, [_entry()], "not in draft\n")

    with pytest.raises(promoter.PromotionError, match="matched zero"):
        promoter.promote(_args(draft, seed, allowlist))


def test_duplicate_canonical_reference_fails(tmp_path) -> None:
    draft, seed, allowlist = _paths(
        tmp_path,
        [
            _entry(),
            _entry(
                id="en_literary_reference_break_the_ice_def67890",
                source_dataset="another_dataset",
            ),
        ],
        "break the ice\n",
    )

    with pytest.raises(promoter.PromotionError, match="matched multiple"):
        promoter.promote(_args(draft, seed, allowlist))


def test_rights_review_rows_are_refused_by_default(tmp_path) -> None:
    draft, seed, allowlist = _paths(
        tmp_path,
        [_entry(source_license="copyright_or_rights_review_needed")],
        "break the ice\n",
    )

    with pytest.raises(promoter.PromotionError, match="source_license"):
        promoter.promote(_args(draft, seed, allowlist))


def test_generic_placeholder_explanations_are_refused(tmp_path) -> None:
    draft, seed, allowlist = _paths(
        tmp_path,
        [_entry(short_explanation="TODO: add a short learner-facing explanation.")],
        "break the ice\n",
    )

    with pytest.raises(promoter.PromotionError, match="placeholder"):
        promoter.promote(_args(draft, seed, allowlist))


def test_missing_source_location_is_refused_by_default(tmp_path) -> None:
    draft, seed, allowlist = _paths(tmp_path, [_entry(source_location="")], "break the ice\n")

    with pytest.raises(promoter.PromotionError, match="missing source_location"):
        promoter.promote(_args(draft, seed, allowlist))


def test_reviewed_by_reviewed_at_are_required(tmp_path) -> None:
    draft, seed, allowlist = _paths(tmp_path, [_entry()], "break the ice\n")

    with pytest.raises(promoter.PromotionError, match="--reviewed-by"):
        promoter.promote(_args(draft, seed, allowlist, reviewed_by=""))
    with pytest.raises(promoter.PromotionError, match="--reviewed-at"):
        promoter.promote(_args(draft, seed, allowlist, reviewed_at=""))


def test_promoted_entries_are_marked_reviewed(tmp_path) -> None:
    draft, seed, allowlist = _paths(tmp_path, [_entry()], "break the ice\n")

    promoted, _, _ = promoter.promote(_args(draft, seed, allowlist))

    assert promoted[0]["review_status"] == "reviewed"
    assert promoted[0]["reviewed_by"] == "paul"
    assert promoted[0]["reviewed_at"] == "2026-06-07"


def test_existing_seed_duplicate_is_refused(tmp_path) -> None:
    draft, seed, allowlist = _paths(tmp_path, [_entry()], "break the ice\n")
    _write_yaml(seed, [_entry(review_status="reviewed", reviewed_by="paul", reviewed_at="2026-06-01")])

    with pytest.raises(promoter.PromotionError, match="duplicate id"):
        promoter.promote(_args(draft, seed, allowlist))


def test_output_validates_with_build_cultural_catalog(tmp_path) -> None:
    draft, seed, allowlist = _paths(tmp_path, [_entry()], "break the ice\n")
    promoted, _, _ = promoter.promote(_args(draft, seed, allowlist))

    by_lang, warnings, _ = validate_and_build(promoted)

    assert warnings == []
    assert [entry["canonical_reference"] for entry in by_lang["en"]] == ["break the ice"]


def test_rights_basis_preserved_through_promotion(tmp_path) -> None:
    entry = _entry(source_license="not_required", rights_basis="common_usage_short_expression")
    entry.pop("source_location", None)
    draft, seed, allowlist = _paths(tmp_path, [entry], "break the ice\n")

    promoted, _, _ = promoter.promote(
        _args(draft, seed, allowlist, allow_missing_source_location=True, min_confidence=0.80)
    )

    assert promoted[0]["rights_basis"] == "common_usage_short_expression"

    by_lang, warnings, _ = validate_and_build(promoted)
    assert warnings == []

