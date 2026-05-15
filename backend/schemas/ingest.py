"""Schemas for the /ingest endpoint.

``ContentType`` defines the full extensibility surface for ingestion paths.
Only ``pasted_text`` and ``uploaded_file`` are implemented now; the remaining
values stake out the design space for article extraction, ebook parsing,
subtitle import, and curated corpora — all without future schema changes.

``IngestRequest`` is a superset of ``ParseRequest`` that adds source metadata.
``IngestResponse`` extends ``ParseResponse`` with a ``source_document_id``
that clients can reference for repeated-exposure tracking and reading
progression.
"""
from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field

from backend.schemas.parse import ParseResponse


class ContentType(str, Enum):
    """Describes how text entered the system.

    Implemented:
        pasted_text    — typed or pasted directly into the UI textarea
        uploaded_file  — read from a .txt file on the user's device

    Planned (infrastructure defined, not yet built):
        article   — fetched from a URL and extracted with a readability pass
        ebook     — parsed from EPUB / MOBI; chapters become chunks
        subtitle  — imported from SRT / VTT / ASS; timestamps stripped
        corpus    — manually curated multi-document collection (TSV / ZIP)
    """
    PASTED_TEXT   = "pasted_text"
    UPLOADED_FILE = "uploaded_file"
    # ── Planned ────────────────────────────────────────────────────────────────
    ARTICLE  = "article"   # URL fetch + readability extraction
    EBOOK    = "ebook"     # EPUB / MOBI; chapters → chunks
    SUBTITLE = "subtitle"  # SRT / VTT / ASS; dialogue lines → chunks
    CORPUS   = "corpus"    # curated multi-document collection


class IngestRequest(BaseModel):
    """Request body for ``POST /ingest``.

    *text* is the body of the document after any client-side preprocessing
    (file reading, copy-paste).  Source metadata fields are all optional;
    clients should populate what they know.  The server never fetches
    ``source_url``.
    """
    language: str = Field(min_length=2, max_length=10)
    text: str = Field(min_length=1)
    content_type: ContentType = ContentType.PASTED_TEXT
    title: Annotated[str | None, Field(max_length=512)] = None
    author: Annotated[str | None, Field(max_length=256)] = None
    source_url: str | None = Field(
        default=None,
        description=(
            "Provenance URL stored as attribution metadata. "
            "The server never fetches this URL."
        ),
    )
    # Original filename when content_type is uploaded_file.
    filename: Annotated[str | None, Field(max_length=256)] = None


class IngestResponse(ParseResponse):
    """``ParseResponse`` extended with ingestion metadata.

    ``source_document_id`` uniquely identifies the ``SourceDocument`` row
    created for this ingestion.  It persists across re-parses of the same
    document and is the stable reference for recommendation, repeated
    exposure, and reading-progression features.

    ``warnings`` is inherited from ``ParseResponse`` and carries non-fatal
    validation notices — for example, a probable language or script mismatch.
    The frontend should display these to the user without blocking lesson display.
    """
    source_document_id: str
