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

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON

JsonType = JSONB().with_variant(JSON(), "sqlite")


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    """Registered user account for authentication.

    ``id`` is a random UUID-v4 and becomes the ``user_id`` used throughout
    the system once JWT auth is active.  ``email`` is the unique login
    credential; ``hashed_password`` stores a bcrypt hash (never plain text).

    Keeping auth in a separate table from the rest of the knowledge schema
    means the auth layer can be swapped (e.g. SSO) without touching any
    knowledge-state tables.

    ``analytics_opt_out`` — when True, no LearningEventRow rows are written
    for this user.  Defaults False (opted-in) because events are aggregate,
    non-identifiable session counts.  Users can toggle at any time; past
    events are retained until explicit deletion or account deletion.
    """
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    analytics_opt_out: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ParsedText(Base):
    __tablename__ = "parsed_texts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    language: Mapped[str] = mapped_column(String(10))
    source_text: Mapped[str] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    user_id: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
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
    surface_forms: Mapped[list] = mapped_column(JSON, default=list)
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


class SourceDocumentRow(Base):
    """A source document: one ingested piece of text with attribution metadata.

    Represents a logical unit of text as the user thinks of it — an article,
    a book chapter, a subtitle file, or a paste session.  One document maps to
    one or more ``SourceChunkRow`` entries; each chunk links to one
    ``ParsedText`` row.

    For the common case (pasted text, short file upload) there is exactly one
    chunk.  For long-form text (ebooks, corpora) the chunker will split the
    document at paragraph boundaries, creating multiple sequential chunks each
    with its own ``ParsedText`` parse.

    ``content_type`` mirrors ``ContentType`` in ``backend.schemas.ingest``.
    Stored as a plain string so the DB does not need an ALTER when new
    content types are added.

    ``script_hint`` is the dominant Unicode script family detected at
    ingestion time (e.g. "latin", "arabic", "cjk").  Stored for display
    and future recommendation heuristics.
    """
    __tablename__ = "source_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    language: Mapped[str] = mapped_column(String(10))
    content_type: Mapped[str] = mapped_column(String(50))
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    author: Mapped[str | None] = mapped_column(String(256), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String, nullable=True)
    filename: Mapped[str | None] = mapped_column(String(256), nullable=True)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    script_hint: Mapped[str | None] = mapped_column(String(32), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    chunks: Mapped[list["SourceChunkRow"]] = relationship(
        "SourceChunkRow", back_populates="source_document", cascade="all, delete-orphan"
    )


class SourceChunkRow(Base):
    """One parsed segment of a ``SourceDocument``.

    Links a ``SourceDocument`` to the ``ParsedText`` row that holds the raw
    text and NLP results for that segment.  ``char_start`` / ``char_end`` are
    character offsets within the original document so chunks can be
    reassembled in order and sentence context can be reconstructed.

    For single-chunk documents (pasted text, short file uploads):
        chunk_index = 0, char_start = 0, char_end = len(text).

    For multi-chunk long-form documents the chunker assigns sequential
    ``chunk_index`` values and tracks where each chunk begins in the original
    text so that sentence highlights can be mapped back to the source.
    """
    __tablename__ = "source_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("source_documents.id"), nullable=False
    )
    parsed_text_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("parsed_texts.id"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    char_start: Mapped[int] = mapped_column(Integer, default=0)
    char_end: Mapped[int] = mapped_column(Integer, default=0)

    source_document: Mapped[SourceDocumentRow] = relationship(
        "SourceDocumentRow", back_populates="chunks"
    )


class SourceProgressionRow(Base):
    """Text-level reading progression for one (user, source_document) pair.

    Complements the object-level FSRS tracking in ``UserKnowledgeRow`` with
    a document-level view of learning progress.  Where FSRS tracks whether a
    learner *knows* a word, this tracks how far they have *read* through a
    source text — enabling the i+1 recommendation engine to prefer continuing
    an in-progress document over jumping to an unrelated sentence.

    Design rationale
    ────────────────
    Authentic reading requires context.  Recommending isolated sentences from
    different documents produces the flashcard anti-pattern: learners never
    encounter the same vocabulary in a coherent narrative.  SourceProgressionRow
    allows the recommendation engine to:

      1. Prefer the next unread passage from a document the user has already
         started, preserving narrative context.
      2. Track comprehension at the document level (avg_comprehension is the
         rolling mean of object mastery scores for all objects in the document).
      3. Record reading velocity (sentences_seen / sessions) for curriculum
         pacing — not yet implemented but the data is preserved.
      4. Mark documents as completed (next_position >= sentences_total).

    next_position
        Zero-based sentence index of the sentence the user should read next.
        Incremented by the frontend after the user finishes reading a passage.
        Persisted here so progress survives across sessions.

    sentences_total
        Total sentence count for the associated source document.  Set at
        ingestion time from the ParsedText sentence count.  Needed to
        determine document completion without a COUNT(*) query.

    avg_comprehension
        Rolling mean of ``mastery_score`` values for every canonical object
        encountered in this document.  Updated asynchronously as review
        events arrive.  Ranges from 0.0 (nothing mastered) to 1.0 (all
        objects mastered).  Used for document-level progress display and to
        weigh recommendation preference toward documents where the learner
        has enough vocabulary to benefit from continued reading.

    completion_fraction
        Derived from ``next_position / sentences_total``; stored as a
        convenience column to avoid a division on every sort.  Updated
        whenever ``next_position`` changes.  Ranges from 0.0 to 1.0.
    """
    __tablename__ = "source_progression"

    user_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    source_document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("source_documents.id"), primary_key=True
    )

    next_position: Mapped[int] = mapped_column(Integer, default=0)
    sentences_total: Mapped[int] = mapped_column(Integer, default=0)
    avg_comprehension: Mapped[float] = mapped_column(Float, default=0.0)
    completion_fraction: Mapped[float] = mapped_column(Float, default=0.0)

    last_read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CorpusDocumentTagRow(Base):
    """User-defined label on a corpus document.

    Composite primary key (user_id, source_document_id, tag) makes add
    idempotent via INSERT OR IGNORE and keeps the table compact.  No FK on
    user_id — consistent with the FK-free design used elsewhere.
    """

    __tablename__ = "corpus_document_tags"

    user_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    source_document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("source_documents.id", ondelete="CASCADE"), primary_key=True
    )
    tag: Mapped[str] = mapped_column(String(50), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CorpusDocumentNoteRow(Base):
    """Freetext note a user has attached to a corpus document."""

    __tablename__ = "corpus_document_notes"

    user_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    source_document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("source_documents.id", ondelete="CASCADE"), primary_key=True
    )
    note: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CorpusCollectionRow(Base):
    """Named shelf for organizing corpus documents."""

    __tablename__ = "corpus_collections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(50), index=True)
    name: Mapped[str] = mapped_column(String(100))
    position: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CorpusCollectionItemRow(Base):
    """Membership record mapping one document into one collection."""

    __tablename__ = "corpus_collection_items"

    collection_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("corpus_collections.id", ondelete="CASCADE"), primary_key=True
    )
    source_document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("source_documents.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(String(50))
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class CorpusImportLogRow(Base):
    """Audit log of corpus import attempts (success, failed, or duplicate)."""

    __tablename__ = "corpus_import_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(50), index=True)
    url: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20))  # success / failed / duplicate
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_document_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


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

    ``progression_stage`` tracks the learner's current acquisition stage for
    this item: recognition → guided_recall → partial_production →
    transformation → free_production → contextual_interpretation.
    Advances when mastery score meets the stage threshold; never regresses.
    """
    __tablename__ = "user_knowledge"

    user_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    object_id: Mapped[str] = mapped_column(String, primary_key=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    fsrs_state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    mastery_score: Mapped[float] = mapped_column(Float, default=0.0)
    first_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    total_reviews: Mapped[int] = mapped_column(Integer, default=0)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    progression_stage: Mapped[str] = mapped_column(
        String(30), default="recognition", server_default="recognition"
    )


class ReviewEventRow(Base):
    """One recorded review interaction.

    Written by ``POST /review`` immediately after the FSRS scheduler updates
    the card state.  Never updated — rows are append-only.

    ``mastery_score_before`` and ``mastery_score_after`` are the FSRS
    retrievability R(t, S) computed just before and just after the review so
    that retention curves can be reconstructed without re-running the scheduler.

    ``wrong_answer`` is the label/form the learner chose when quality < 3.
    Used to mine confusion pairs for targeted contrast drilling.

    ``concept_type`` mirrors ``CanonicalObjectRow.type`` so that accuracy
    can be analysed per linguistic concept category without joins.

    No FK constraints on ``user_id`` or ``object_id`` — consistent with
    ``UserKnowledgeRow`` so reviews can be logged even when canonical_objects
    or users rows are temporarily absent.
    """
    __tablename__ = "review_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    object_id: Mapped[str] = mapped_column(String, nullable=False)
    quality: Mapped[int] = mapped_column(Integer, nullable=False)
    mastery_score_before: Mapped[float] = mapped_column(Float, nullable=False)
    mastery_score_after: Mapped[float] = mapped_column(Float, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False, index=True
    )
    wrong_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    concept_type: Mapped[str | None] = mapped_column(String(30), nullable=True)


class UserFsrsParamsRow(Base):
    """Per-user FSRS scheduling parameters.

    Created on demand when a user first calibrates or manually sets their
    desired retention.  A missing row means "use global defaults".

    ``desired_retention`` ∈ [0.70, 0.97] controls the target recall probability
    at the scheduled review date.  Lower values → longer intervals (user has
    stronger memory or prefers more spacing); higher values → shorter intervals.

    ``last_calibrated_at`` and ``calibration_rmse`` are populated only by the
    auto-calibration endpoint; they are ``None`` when the user set the parameter
    manually.
    """
    __tablename__ = "user_fsrs_params"

    user_id: Mapped[str] = mapped_column(String(50), primary_key=True)

    #: Target recall probability at scheduled review; default 0.90.
    desired_retention: Mapped[float] = mapped_column(Float, default=0.90)

    #: Set to the timestamp of the last auto-calibration run, else None.
    last_calibrated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    #: Number of review events used in the last calibration.
    reviews_used: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: RMSE of predicted vs actual recall across bins (lower = better).
    calibration_rmse: Mapped[float | None] = mapped_column(Float, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class TermProgressRow(Base):
    """Per-user, per-language progress for highlighted terms.

    This model is independent from canonical object IDs so the UI can track
    literal highlighted terms and their normalized lemmas directly.
    """
    __tablename__ = "term_progress"

    user_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    language: Mapped[str] = mapped_column(String(10), primary_key=True)
    term: Mapped[str] = mapped_column(String, primary_key=True)

    lemma: Mapped[str | None] = mapped_column(String, nullable=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    exposure_count: Mapped[int] = mapped_column(Integer, default=0)
    review_count: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    incorrect_count: Mapped[int] = mapped_column(Integer, default=0)
    mastery_score: Mapped[float] = mapped_column(Float, default=0.0)
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_lesson_ids: Mapped[list] = mapped_column(JSON, default=list)


class UserLanguagePreferenceRow(Base):
    """Per-user, per-language study preferences.

    Stores presentation and pathway overrides for a specific (user, language)
    pair.  Orthogonal to FSRS state — describes *how* to present content,
    not *what* the user knows.

    Design notes
    ────────────
    Rows are sparse by intent: only languages where the user has changed a
    default need a row.  A missing row means "apply all defaults".

    show_transliteration
        Toggle romanisation for scripts the user cannot yet read natively.
        Relevant for CJK (pinyin), Arabic, Hebrew, Japanese (romaji), etc.

    script_preference
        Variant when a language has multiple orthographies:
          "simplified" / "traditional"  for Mandarin Chinese
          "modern"     / "classical"    for Arabic
        None → use the plugin default.

    lesson_mode_override
        Force a lesson mode for this language, overriding the plugin's
        richest-available mode.  Useful for reading-only languages where the
        user wants dictionary mode without grammar drills.
        None → use the plugin's richest available mode.

    Upgrade path
    ────────────
    Future per-language settings (study goals, notification schedules, custom
    vocabulary lists) extend this table rather than adding new preference tables.
    """
    __tablename__ = "user_language_preferences"

    user_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    language_code: Mapped[str] = mapped_column(String(10), primary_key=True)

    show_transliteration: Mapped[bool] = mapped_column(Boolean, default=True)
    script_preference: Mapped[str | None] = mapped_column(String(50), nullable=True)
    lesson_mode_override: Mapped[str | None] = mapped_column(String(30), nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class VocabularyEntry(Base):
    """CEFR-graded vocabulary harvested from open corpora.

    Uniqueness key: (language, lemma, pos).  The same lemma may appear at
    different CEFR levels when it has multiple parts of speech.
    """
    __tablename__ = "vocabulary_entries"
    __table_args__ = (UniqueConstraint("language", "lemma", "pos", name="uq_vocab_lang_lemma_pos"),)

    id:             Mapped[int]          = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    language:       Mapped[str]          = mapped_column(String(10), nullable=False, index=True)
    lemma:          Mapped[str]          = mapped_column(Text, nullable=False)
    pos:            Mapped[str | None]   = mapped_column(String(20), nullable=True)
    cefr_level:     Mapped[str]          = mapped_column(String(2), nullable=False)
    definition:     Mapped[str | None]   = mapped_column(Text, nullable=True)
    frequency_rank: Mapped[int | None]   = mapped_column(Integer, nullable=True)
    source:         Mapped[str]          = mapped_column(String(80), nullable=False)
    created_at:     Mapped[datetime]     = mapped_column(DateTime(timezone=True), default=_now)


class ContentGapSignalRow(Base):
    """Append-only log of /recommend calls that returned zero results.

    Used to identify which languages need more ingested source texts.
    Query: SELECT language, COUNT(*) FROM content_gap_signal GROUP BY language ORDER BY 2 DESC
    """
    __tablename__ = "content_gap_signal"

    id:               Mapped[str]      = mapped_column(String(36), primary_key=True, default=_uuid)
    language:         Mapped[str]      = mapped_column(String(20), nullable=False, index=True)
    user_id:          Mapped[str]      = mapped_column(String(50), nullable=False)
    has_parsed_texts: Mapped[bool]     = mapped_column(Boolean, nullable=False)
    requested_at:     Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class GrammarRule(Base):
    """CEFR-graded grammar rules per language.

    Each rule belongs to a named category (e.g. 'verb_tenses', 'articles',
    'cases') and carries a description plus JSON array of examples
    ({sentence, translation, note}).
    """
    __tablename__ = "grammar_rules"
    __table_args__ = (UniqueConstraint("language", "cefr_level", "name", name="uq_grammar_lang_level_name"),)

    id:          Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    language:    Mapped[str]      = mapped_column(String(10), nullable=False, index=True)
    cefr_level:  Mapped[str]      = mapped_column(String(2),  nullable=False)
    category:    Mapped[str]      = mapped_column(String(80), nullable=False)
    name:        Mapped[str]      = mapped_column(Text, nullable=False)
    description: Mapped[str]      = mapped_column(Text, nullable=False)
    examples:    Mapped[list]     = mapped_column(JsonType, nullable=False, default=list)
    source:      Mapped[str]      = mapped_column(String(80), nullable=False)
    created_at:  Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SentenceReviewItemRow(Base):
    """One mined review item anchored to a specific sentence.

    The uniqueness constraint (sentence_id, item_type, target_span) makes
    mining idempotent — re-mining the same sentence produces no duplicates.

    ``target_object_ids`` is a JSON list of canonical-object UUIDs involved in
    this item (usually one, occasionally two for discrimination items).  No FK
    constraint so items survive object-row deletions without breaking reviews.
    """
    __tablename__ = "sentence_review_items"
    __table_args__ = (
        UniqueConstraint("sentence_id", "item_type", "target_span", name="uq_sentence_review_item"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    sentence_id: Mapped[str] = mapped_column(String(36), ForeignKey("sentences.id"), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(10), nullable=False, index=True)

    #: "cloze" | "chunk_recall" | "grammar_transform" | "meaning_discrimination"
    item_type: Mapped[str] = mapped_column(String(30), nullable=False)

    #: Human-readable prompt displayed to the learner.
    prompt: Mapped[str] = mapped_column(Text, nullable=False)

    #: The word/phrase targeted by this item (used as idempotency key with sentence+type).
    target_span: Mapped[str] = mapped_column(String(500), nullable=False)

    #: Expected answer (compared case-insensitively for cloze/chunk items).
    answer: Mapped[str] = mapped_column(Text, nullable=False)

    #: Optional distractor strings for meaning-discrimination items.
    distractors: Mapped[list] = mapped_column(JsonType, default=list)

    #: Optional learner hint (e.g. lemma, grammar note).
    hint: Mapped[str | None] = mapped_column(Text, nullable=True)

    #: Grammar concept tag for transform/discrimination items (e.g. "preterite_imperfect").
    grammar_concept: Mapped[str | None] = mapped_column(String(100), nullable=True)

    #: CEFR level of the target vocabulary/structure (e.g. "B1").
    cefr_level: Mapped[str | None] = mapped_column(String(2), nullable=True)

    #: Difficulty ∈ [0, 1]; higher = harder.  Derived from object confidence.
    difficulty_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    #: JSON list of canonical-object UUIDs involved in this item.
    target_object_ids: Mapped[list] = mapped_column(JsonType, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class UserSentenceReviewRow(Base):
    """FSRS scheduling state for one (user, sentence review item) pair.

    Parallel to ``UserKnowledgeRow`` but scoped to sentence-level items.
    No FK on ``item_id`` — consistent with the FK-free design in
    ``UserKnowledgeRow`` for resilience during outages.

    ``streak`` counts consecutive successful reviews (quality ≥ 3) without
    an "Again" (quality 1) — used by the frontend mastery visualisation.
    """
    __tablename__ = "user_sentence_review"

    user_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    fsrs_state: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    mastery_score: Mapped[float] = mapped_column(Float, default=0.0)
    total_reviews: Mapped[int] = mapped_column(Integer, default=0)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    streak: Mapped[int] = mapped_column(Integer, default=0)


class CorpusIngestionRow(Base):
    """Persistent record of every corpus ingestion attempt.

    Enables idempotent re-runs: if a source_identity + raw_content_hash pair
    already exists with status='ok', the build pipeline skips re-ingestion.
    When content changes (different raw_content_hash) the pipeline re-ingests
    and updates this record.
    """
    __tablename__ = "corpus_ingestions"

    id:                    Mapped[str]           = mapped_column(String(36), primary_key=True, default=_uuid)
    source_identity:       Mapped[str]           = mapped_column(String(64), nullable=False, index=True)
    """sha256(language + framework + level + normalized_url + normalized_title + author)[:64]"""
    manifest_entry_hash:   Mapped[str]           = mapped_column(String(64), nullable=False)
    """sha256 of the full manifest entry YAML (for detecting metadata-only changes)."""
    raw_content_hash:      Mapped[str | None]    = mapped_column(String(64), nullable=True)
    normalized_content_hash: Mapped[str | None]  = mapped_column(String(64), nullable=True)
    language:              Mapped[str]           = mapped_column(String(20), nullable=False)
    framework:             Mapped[str]           = mapped_column(String(30), nullable=False)
    level:                 Mapped[str]           = mapped_column(String(20), nullable=False)
    cefr_equivalent:       Mapped[str | None]    = mapped_column(String(2),  nullable=True)
    source_document_id:    Mapped[str | None]    = mapped_column(String(36), nullable=True)
    pipeline_version:      Mapped[str]           = mapped_column(String(20), nullable=False, default="1.0")
    acquired_at:           Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    normalized_at:         Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at:           Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status:                Mapped[str]           = mapped_column(String(20), nullable=False, default="pending")
    """pending | ok | failed | skipped | metadata_only"""
    error_message:         Mapped[str | None]    = mapped_column(Text, nullable=True)


class ConfusionPairRow(Base):
    """Records which items a learner confuses with each other.

    Written when a review is submitted with quality < 3 and a ``wrong_answer``
    is included in the payload.  The PK (user_id, object_id, confused_with)
    makes upserts safe and idempotent.

    ``confused_with`` is the display label of the wrong answer chosen, not an
    object_id, because wrong answers may come from arbitrary distractors that
    do not map to canonical objects.

    ``next_contrast_at`` is set to 2 days after each confusion event; the
    weakness endpoint surfaces items where this is in the past so the UI can
    prompt targeted contrast drilling.
    """
    __tablename__ = "confusion_pairs"

    user_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    object_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    confused_with: Mapped[str] = mapped_column(Text, primary_key=True)
    confusion_count: Mapped[int] = mapped_column(Integer, default=1)
    last_confused_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    next_contrast_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WeaknessClusterRow(Base):
    """Aggregated learner confusion patterns grouped by linguistic category.

    Populated by the weakness profile endpoint.  Stores pre-computed cluster
    analysis so the profile endpoint can return fast without scanning all
    review events on each request.

    ``cluster_type`` is one of: morphology_errors, tense_confusion,
    aspect_confusion, register_confusion, particle_confusion, article_case.

    ``labels`` is a JSON list of canonical_form strings (or display labels)
    belonging to this cluster.

    ``strength`` ∈ [0, 1]: how strong/persistent the confusion cluster is.
    Decays toward 0 as the learner masters the distinctions.
    """
    __tablename__ = "weakness_clusters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(10), nullable=False)
    cluster_type: Mapped[str] = mapped_column(String(50), nullable=False)
    labels: Mapped[list] = mapped_column(JSON, default=list)
    strength: Mapped[float] = mapped_column(Float, default=0.0)
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class LearningEventRow(Base):
    """Privacy-conscious aggregate learning event.

    Stores non-identifiable session-level counts (not raw answers, not
    text snippets) to power aggregate progress analytics and detect
    feature engagement without personal-data exposure.

    ``event_type`` enum (enforced by application layer):
      review_session   — user completed a review session (count of items)
      text_ingested    — user ingested a text for parsing
      recommend_served — recommendation engine returned results
      practice_drill   — user completed a drill (count of correct answers)

    GDPR compliance:
      - No FK to users table; ``user_id`` is an opaque identifier.
      - On account deletion, application MUST delete rows WHERE user_id = ?
        (cascade in application code, not DB FK, for resilience).
      - When analytics_opt_out=True on UserRow, no events are written.
      - Rows older than 365 days may be purged by a maintenance job without
        user notification (aggregate retention policy).

    ``metadata_json`` holds non-identifiable context (e.g. language, count).
    It MUST NOT contain: text snippets, canonical_form values, or
    anything that could identify a specific review item.
    """
    __tablename__ = "learning_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    count: Mapped[int] = mapped_column(Integer, default=1)
    metadata_json: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, index=True
    )
