"""SQLAlchemy 2.0 async ORM models for Mnemosyne.

Table overview
──────────────
  parsed_texts        One row per /parse call; stores raw input for audit.
  sentences           One row per sentence within a ParsedText, in order.
  learnable_objects   Canonical record per learnable item, keyed by the
                      deterministic ID produced by the plugin (e.g.
                      "es:vocab:hola").  Upserted on each /parse so
                      lesson_data stays fresh.
  review_states       One row per learnable_object; stores the FSRS
                      scheduling state.  No FK to learnable_objects so
                      that a review can be submitted even if the object
                      has not been parsed in the current session.

JSON columns use the dialect-neutral ``JSON`` type.  PostgreSQL will map
this to ``jsonb`` in a future Alembic migration if index support is needed.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class ParsedText(Base):
    __tablename__ = "parsed_texts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    language: Mapped[str] = mapped_column(String(10))
    source_text: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    sentences: Mapped[list[Sentence]] = relationship(
        "Sentence", back_populates="parsed_text", cascade="all, delete-orphan"
    )


class Sentence(Base):
    __tablename__ = "sentences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    parsed_text_id: Mapped[str] = mapped_column(String(36), ForeignKey("parsed_texts.id"))
    position: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)

    parsed_text: Mapped[ParsedText] = relationship("ParsedText", back_populates="sentences")


class LearnableObjectRow(Base):
    """Canonical lesson record, keyed by the plugin-generated deterministic ID.

    On re-parse the row is upserted: existing rows have their ``lesson_data``
    and ``confidence`` updated; ``created_at`` is only set on first insert.
    """
    __tablename__ = "learnable_objects"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    language: Mapped[str] = mapped_column(String(10))
    type: Mapped[str] = mapped_column(String(50))
    label: Mapped[str] = mapped_column(String)
    lesson_data: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ReviewStateRow(Base):
    """Persisted FSRS scheduling state for one learnable object.

    No FK constraint on ``object_id`` so that reviews can be submitted
    for objects that pre-date the current server session.
    """
    __tablename__ = "review_states"

    object_id: Mapped[str] = mapped_column(String, primary_key=True)
    state: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
