"""Manifest quality checks — license, duplicate detection, language validity."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from backend.corpus.manifest import ALLOWED_LICENSES, CorpusEntry, CorpusManifest


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
) -> QualityReport:
    """Run quality checks over all manifest entries.

    Args:
        manifest:             Loaded and structurally validated manifest.
        supported_languages:  Set of language codes from the plugin registry.
                              When provided, entries whose language has no
                              plugin are flagged as warnings.

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

    return report
