"""Manifest quality checks — license, duplicate detection, language validity, coverage."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from backend.corpus.manifest import ALLOWED_LICENSES, CorpusEntry, CorpusManifest

_ALL_CEFR = ("A1", "A2", "B1", "B2", "C1", "C2")


@dataclass
class QualityIssue:
    title: str
    language: str
    issue_type: Literal[
        "invalid_license",
        "duplicate_url",
        "invalid_language_code",
        "missing_author",
        "unknown_plugin",
        "missing_cefr_level",
        "manual_review_required",
    ]
    message: str
    severity: Literal["error", "warning"]


@dataclass
class QualityReport:
    issues: list[QualityIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[QualityIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[QualityIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors


def check_manifest(
    manifest: CorpusManifest,
    supported_languages: set[str] | None = None,
    require_full_cefr_coverage: bool = False,
) -> QualityReport:
    """Run quality checks over all manifest entries.

    Args:
        manifest:                    Loaded and structurally validated manifest.
        supported_languages:         Set of language codes from the plugin registry.
                                     When provided, entries whose language has no
                                     plugin are flagged as warnings.
        require_full_cefr_coverage:  When True, flag languages that do not have
                                     at least one entry at every CEFR level A1–C2.

    Returns:
        QualityReport with lists of errors and warnings.
    """
    report = QualityReport()
    seen_urls: dict[str, str] = {}

    for entry in manifest.entries:
        # Duplicate URL check (structural check already in CorpusManifest but
        # model_validator raises ValueError on load; this surfaces it as an issue).
        if entry.source_url in seen_urls:
            report.issues.append(QualityIssue(
                title=entry.title,
                language=entry.language,
                issue_type="duplicate_url",
                message=(
                    f"source_url '{entry.source_url}' also used by "
                    f"'{seen_urls[entry.source_url]}'"
                ),
                severity="error",
            ))
        else:
            seen_urls[entry.source_url] = entry.title

        # License check.
        if entry.license not in ALLOWED_LICENSES:
            report.issues.append(QualityIssue(
                title=entry.title,
                language=entry.language,
                issue_type="invalid_license",
                message=f"license '{entry.license}' not in {sorted(ALLOWED_LICENSES)}",
                severity="error",
            ))

        # Author provenance check.
        if not entry.author:
            report.issues.append(QualityIssue(
                title=entry.title,
                language=entry.language,
                issue_type="missing_author",
                message="No author recorded; attribution incomplete",
                severity="warning",
            ))

        # Language code check: must be at least 2 chars, BCP-47-ish.
        if len(entry.language) < 2:
            report.issues.append(QualityIssue(
                title=entry.title,
                language=entry.language,
                issue_type="invalid_language_code",
                message=f"language code '{entry.language}' is too short",
                severity="error",
            ))

        # Plugin availability check.
        if supported_languages is not None:
            if entry.language.lower() not in supported_languages:
                report.issues.append(QualityIssue(
                    title=entry.title,
                    language=entry.language,
                    issue_type="unknown_plugin",
                    message=(
                        f"No loaded plugin for language '{entry.language}'. "
                        "Check that the plugin is registered and the NLP model is downloaded."
                    ),
                    severity="warning",
                ))

        # Manual review flag.
        if entry.manual_review:
            report.issues.append(QualityIssue(
                title=entry.title,
                language=entry.language,
                issue_type="manual_review_required",
                message="Entry flagged manual_review=True; verify URL before ingestion",
                severity="warning",
            ))

    # Per-language CEFR coverage check.
    if require_full_cefr_coverage:
        for lang in manifest.languages():
            missing = manifest.missing_cefr_levels(lang)
            if missing:
                report.issues.append(QualityIssue(
                    title=f"[{lang}] coverage",
                    language=lang,
                    issue_type="missing_cefr_level",
                    message=f"Missing CEFR levels: {missing}",
                    severity="error",
                ))

    return report
