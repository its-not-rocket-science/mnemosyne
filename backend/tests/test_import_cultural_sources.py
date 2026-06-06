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
            "short_explanation": "TODO: add explanation",
            "learner_level": "B2",
            "confidence": 0.71,
            "review_status": "draft",
            "register": "literary",
            "variants": ["slings and arrows"],
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
