from __future__ import annotations

import json

from scripts import import_cultural_sources as importer


def test_convert_rows_from_csv_shape() -> None:
    rows = [
        {
            "language": "en",
            "surface_pattern": "to be or not to be",
            "surface_patterns": "the slings and arrows|sea of troubles",
            "variants": "slings and arrows|to be or not to be",
            "canonical_reference": "To be or not to be",
            "reference_type": "literary_reference",
            "source_work": "Hamlet",
            "source_author": "William Shakespeare",
            "source_location": "Act 3 Scene 1",
            "short_explanation": "A soliloquy about existence and choice.",
            "learner_level": "B2",
            "register": "literary",
            "confidence": "0.71",
            "source_url": "https://example.org/hamlet",
            "source_license": "CC0",
            "source_dataset": "unit_test_dataset",
            "notes": "Needs a native-speaker review.",
        }
    ]

    entries = importer.convert_rows(rows)

    assert entries == [
        {
            "id": "en_literary_reference_to_be_or_not_to_be_72b94f13",
            "language": "en",
            "canonical_reference": "To be or not to be",
            "reference_type": "literary_reference",
            "surface_patterns": [
                "to be or not to be",
                "the slings and arrows",
                "sea of troubles",
            ],
            "short_explanation": "A soliloquy about existence and choice.",
            "learner_level": "B2",
            "confidence": 0.71,
            "review_status": "draft",
            "register": "literary",
            "variants": ["slings and arrows"],
            "explanation_key": "mnemosyne.en.explanation.unit_test_dataset.to_be_or_not_to_be",
            "source_work_key": "mnemosyne.en.work.hamlet",
            "source_author_key": "mnemosyne.en.author.william_shakespeare",
            "source_work": "Hamlet",
            "source_author": "William Shakespeare",
            "source_location": "Act 3 Scene 1",
            "source_url": "https://example.org/hamlet",
            "source_license": "CC0",
            "source_dataset": "unit_test_dataset",
            "notes": "Needs a native-speaker review.",
        }
    ]


def test_load_jsonl_and_minimal_yaml_dump(tmp_path) -> None:
    source = tmp_path / "sources.jsonl"
    out = tmp_path / "draft.yaml"
    source.write_text(
        json.dumps(
            {
                "language": "es",
                "surface_pattern": "molinos de viento",
                "canonical_reference": "molinos de viento",
                "reference_type": "literary_reference",
                "source_work": "Don Quijote de la Mancha",
                "learner_level": "B2",
                "confidence": 0.8,
                "source_dataset": "unit_test_jsonl",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    entries = importer.convert_rows(importer.load_source(source))
    importer.write_yaml(entries, out)

    text = out.read_text(encoding="utf-8")
    assert 'review_status: "draft"' in text or "review_status: draft" in text
    assert "source_dataset" in text
    assert "runtime" not in text


def test_missing_source_dataset_is_rejected() -> None:
    rows = [
        {
            "language": "en",
            "surface_pattern": "Big Brother",
            "canonical_reference": "Big Brother",
            "reference_type": "literary_reference",
            "learner_level": "B2",
            "confidence": "0.5",
        }
    ]

    try:
        importer.convert_rows(rows)
    except ValueError as exc:
        assert "missing source_dataset" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected missing source_dataset to fail")


def _minimal_row(**overrides: str) -> dict[str, str]:
    row = {
        "language": "en",
        "surface_pattern": "break the ice",
        "surface_patterns": "",
        "variants": "broke the ice|breaking the ice",
        "canonical_reference": "break the ice",
        "reference_type": "literary_reference",
        "source_work": "The Taming of the Shrew",
        "source_author": "William Shakespeare",
        "source_location": "Act I Scene 2",
        "short_explanation": (
            "To reduce social tension or begin interaction in an awkward situation."
        ),
        "explanation_key": "",
        "source_work_key": "",
        "source_author_key": "",
        "learner_level": "B2",
        "register": "literary",
        "confidence": "0.84",
        "source_url": "",
        "source_license": "public_domain",
        "source_dataset": "en_shakespeare_phrases",
        "notes": "review attribution",
    }
    row.update(overrides)
    return row


def test_missing_short_explanation_uses_todo_but_still_suggests_stable_key() -> None:
    [entry] = importer.convert_rows([_minimal_row(short_explanation="")])

    assert entry["short_explanation"] == importer.TODO_EXPLANATION
    assert (
        entry["explanation_key"]
        == "mnemosyne.en.explanation.en_shakespeare_phrases.break_the_ice"
    )


def test_user_provided_localisation_keys_are_preserved() -> None:
    [entry] = importer.convert_rows(
        [
            _minimal_row(
                explanation_key="mnemosyne.en.explanation.custom.break_the_ice",
                source_work_key="mnemosyne.en.work.custom_taming",
                source_author_key="mnemosyne.en.author.custom_shakespeare",
            )
        ]
    )

    assert entry["explanation_key"] == "mnemosyne.en.explanation.custom.break_the_ice"
    assert entry["source_work_key"] == "mnemosyne.en.work.custom_taming"
    assert entry["source_author_key"] == "mnemosyne.en.author.custom_shakespeare"


def test_generated_draft_yaml_includes_localisation_keys(tmp_path) -> None:
    out = tmp_path / "draft.yaml"
    entries = importer.convert_rows([_minimal_row()])

    importer.write_yaml(entries, out)

    text = out.read_text(encoding="utf-8")
    assert "short_explanation" in text
    assert "mnemosyne.en.explanation.en_shakespeare_phrases.break_the_ice" in text
    assert "mnemosyne.en.work.the_taming_of_the_shrew" in text
    assert "mnemosyne.en.author.william_shakespeare" in text


def test_l10n_out_creates_mappings(tmp_path) -> None:
    out = tmp_path / "en.json"
    entries = importer.convert_rows([_minimal_row()])

    warnings = importer.write_l10n(entries, out)

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert warnings == []
    assert payload == {
        "mnemosyne.en.explanation.en_shakespeare_phrases.break_the_ice": (
            "To reduce social tension or begin interaction in an awkward situation."
        ),
        "mnemosyne.en.author.william_shakespeare": "William Shakespeare",
        "mnemosyne.en.work.the_taming_of_the_shrew": (
            "The Taming of the Shrew"
        ),
    }


def test_l10n_out_preserves_existing_values_and_warns_on_conflicts(tmp_path) -> None:
    out = tmp_path / "en.json"
    out.write_text(
        json.dumps(
            {
                "mnemosyne.en.explanation.en_shakespeare_phrases.break_the_ice": (
                    "Existing explanation."
                ),
                "z.existing": "Keep me.",
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    entries = importer.convert_rows([_minimal_row()])

    warnings = importer.write_l10n(entries, out)

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert (
        payload["mnemosyne.en.explanation.en_shakespeare_phrases.break_the_ice"]
        == "Existing explanation."
    )
    assert payload["z.existing"] == "Keep me."
    assert payload["mnemosyne.en.author.william_shakespeare"] == "William Shakespeare"
    assert any("l10n conflict" in warning for warning in warnings)


def test_deprecated_explicit_localisation_keys_are_migrated_with_warnings() -> None:
    entries, warnings = importer.convert_rows_with_warnings(
        [
            _minimal_row(
                explanation_key="cultural.explanation.en.en_shakespeare_phrases.break_the_ice",
                source_work_key=(
                    "cultural.source_work.en_shakespeare_phrases."
                    "the_taming_of_the_shrew"
                ),
                source_author_key="cultural.source_author.william_shakespeare",
            )
        ]
    )

    [entry] = entries
    assert (
        entry["explanation_key"]
        == "mnemosyne.en.explanation.en_shakespeare_phrases.break_the_ice"
    )
    assert entry["source_work_key"] == "mnemosyne.en.work.the_taming_of_the_shrew"
    assert entry["source_author_key"] == "mnemosyne.en.author.william_shakespeare"
    assert len(warnings) == 3
    assert all("migrated deprecated localisation key" in warning for warning in warnings)


def test_l10n_out_removes_deprecated_cultural_keys(tmp_path) -> None:
    out = tmp_path / "en.json"
    out.write_text(
        json.dumps(
            {
                "cultural.source_author.william_shakespeare": "William Shakespeare",
                "mnemosyne.en.author.william_shakespeare": "William Shakespeare",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    warnings = importer.write_l10n(importer.convert_rows([_minimal_row()]), out)

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert "cultural.source_author.william_shakespeare" not in payload
    assert payload["mnemosyne.en.author.william_shakespeare"] == "William Shakespeare"
    assert any("removed 1 deprecated cultural.*" in warning for warning in warnings)
