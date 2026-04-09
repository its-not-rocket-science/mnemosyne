"""SQLAlchemy 2.0 async ORM models for Mnemosyne.

Table overview
──────────────
  parsed_texts       One row per /parse call; stores raw input for audit.
  sentences          One row per sentence within a ParsedText, in order.
  canonical_objects  Deduplicated learnable objects keyed by a deterministic
                     UUID derived from (language, type, canonical_form).
                     The same word encountered in different texts always maps
                     to the same row.
  object_relations   Directed relationships between canonical objects
                     (e.g. conjugation → vocabulary lemma).
  sentence_objects   Join table linking sentences to the canonical objects
                     found in them, enabling cross-text reinforcement queries.
  user_knowledge     One row per (user_id, object_id) pair; stores the FSRS
                     scheduling state, mastery score, and review history.
                     No FK to canonical_objects so reviews can be submitted
                     even when the object row is absent (e.g. after a DB
                     outage during /parse).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
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
    sentence_objects: Mapped[list[SentenceObjectRow]] = relationship(
        "SentenceObjectRow", back_populates="sentence", cascade="all, delete-orphan"
    )


class CanonicalObjectRow(Base):
    """Deduplicated canonical learnable object.

    The primary key is a deterministic UUID-v5 derived from
    ``(language, type, canonical_form)`` via ``canonical_object_id()``.
    This means upserts are PK lookups — no SELECT by natural key needed.
    """
    __tablename__ = "canonical_objects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    language: Mapped[str] = mapped_column(String(10))
    type: Mapped[str] = mapped_column(String(50))
    canonical_form: Mapped[str] = mapped_column(String)
    display_label: Mapped[str] = mapped_column(String)
    lesson_data: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    __table_args__ = (
        UniqueConstraint("language", "type", "canonical_form", name="uq_canonical_object"),
    )


class ObjectRelationRow(Base):
    """Directed relationship between two canonical objects.

    Example: a conjugation object (source) relates to its lemma's vocabulary
    object (target) via ``relation_type = "conjugation_of"``.
    """
    __tablename__ = "object_relations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("canonical_objects.id"))
    target_id: Mapped[str] = mapped_column(String(36), ForeignKey("canonical_objects.id"))
    relation_type: Mapped[str] = mapped_column(String(50))

    __table_args__ = (
        UniqueConstraint("source_id", "target_id", "relation_type", name="uq_object_relation"),
    )


class SentenceObjectRow(Base):
    """Join table: which canonical objects appear in which sentence.

    Enables queries like "show me all sentences where this word appeared"
    for cross-text reinforcement.  ``position`` is the zero-based index of
    the object within the sentence's learnable_objects list.
    """
    __tablename__ = "sentence_objects"

    sentence_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sentences.id"), primary_key=True
    )
    object_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("canonical_objects.id"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer)

    sentence: Mapped[Sentence] = relationship("Sentence", back_populates="sentence_objects")


class UserKnowledgeRow(Base):
    """FSRS state and mastery metrics for one (user, canonical object) pair.

    No FK constraint on ``object_id`` so that reviews can be submitted for
    objects that pre-date the current server session or whose
    ``canonical_objects`` row was absent during a DB outage.

    ``user_id`` is ``"default"`` for all requests until authentication is
    implemented (Phase 1).

    ``due_at`` mirrors ``fsrs_state["due_at"]`` as a proper datetime column
    so that the daily review queue query is a single indexed comparison
    instead of a JSON extraction.
    """
    __tablename__ = "user_knowledge"

    user_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    object_id: Mapped[str] = mapped_column(String, primary_key=True)
    fsrs_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    mastery_score: Mapped[float] = mapped_column(Float, default=0.0)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    total_reviews: Mapped[int] = mapped_column(Integer, default=0)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
