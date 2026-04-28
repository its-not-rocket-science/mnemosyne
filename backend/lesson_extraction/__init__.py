"""Pedagogical lesson extraction layer.

This package enriches plugin-produced CandidateObjects with normalized
pedagogy metadata and optional derived learning objects.

Install by copying this directory to:

    backend/lesson_extraction/

Then call ``enrich(...)`` after ``plugin.analyze_text(...)`` and before UUID
resolution in /parse and /ingest.
"""
from .engine import enrich

__all__ = ["enrich"]
