"""Paragraph-aware text chunking with accurate char_start / char_end tracking.

Splits a document into ``Chunk`` objects suitable for passing to the NLP
pipeline one at a time.  The chunking algorithm:

  1. Split on paragraph boundaries (two or more newlines).
  2. For paragraphs exceeding ``max_chars``, sub-split on sentence-ending
     punctuation (CJK-aware) then on hard character limits as a last resort.
  3. Greedily pack consecutive paragraphs up to ``max_chars`` into one chunk
     to avoid tiny single-sentence chunks.

Each ``Chunk`` records ``char_start`` and ``char_end`` as byte-accurate
offsets into the original full document text so they can be stored in
``SourceChunkRow`` without ambiguity.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

DEFAULT_MAX_CHUNK_CHARS: int = 2_000

# CJK languages whose sentences don't end with ". " patterns.
_CJK_LANGUAGES: frozenset[str] = frozenset({"zh", "ja", "ko", "grc", "grc-"})

_CJK_SENT_END = re.compile(r"[。！？!?…]")
_LATIN_SENT_END = re.compile(r"(?<=[.!?])\s+")
_PARA_SPLIT = re.compile(r"\n{2,}")


@dataclass(frozen=True)
class Chunk:
    text: str
    chunk_index: int
    char_start: int
    char_end: int


def _is_cjk_language(language: str | None) -> bool:
    if language is None:
        return False
    lang = language.lower()
    return any(lang.startswith(prefix) for prefix in _CJK_LANGUAGES)


def _split_into_sentences(text: str, language: str | None) -> list[str]:
    """Split *text* into sentences, CJK-aware."""
    if _is_cjk_language(language):
        # Split after sentence-ending punctuation, keeping the punctuation.
        parts = _CJK_SENT_END.split(text)
        endings = _CJK_SENT_END.findall(text)
        sentences = []
        for part, end in zip(parts, endings):
            s = (part + end).strip()
            if s:
                sentences.append(s)
        if parts and parts[-1].strip():
            sentences.append(parts[-1].strip())
        return sentences or [text]
    else:
        return [s.strip() for s in _LATIN_SENT_END.split(text) if s.strip()] or [text]


def _split_paragraph(para: str, para_offset: int, max_chars: int, language: str | None) -> list[tuple[str, int, int]]:
    """Split a single over-sized paragraph into sub-chunks."""
    if len(para) <= max_chars:
        return [(para, para_offset, para_offset + len(para))]

    sentences = _split_into_sentences(para, language)
    sub_chunks: list[tuple[str, int, int]] = []
    current_parts: list[str] = []
    current_len = 0
    local_offset = 0  # offset within para

    for sent in sentences:
        # Find this sentence's position in the paragraph.
        sent_pos = para.find(sent, local_offset)
        if sent_pos == -1:
            sent_pos = local_offset  # fallback

        if current_parts and current_len + len(sent) + 1 > max_chars:
            chunk_text = " ".join(current_parts)
            chunk_start = para_offset + para.find(current_parts[0], 0)
            sub_chunks.append((chunk_text, chunk_start, chunk_start + len(chunk_text)))
            current_parts = []
            current_len = 0

        if len(sent) > max_chars:
            # Hard-split a single sentence too long for one chunk.
            for i in range(0, len(sent), max_chars):
                part = sent[i: i + max_chars]
                abs_start = para_offset + sent_pos + i
                sub_chunks.append((part, abs_start, abs_start + len(part)))
        else:
            current_parts.append(sent)
            current_len += len(sent) + 1  # +1 for joining space
            local_offset = sent_pos + len(sent)

    if current_parts:
        chunk_text = " ".join(current_parts)
        chunk_start = para_offset + para.find(current_parts[0], 0)
        sub_chunks.append((chunk_text, chunk_start, chunk_start + len(chunk_text)))

    return sub_chunks


def chunk_text(
    text: str,
    max_chars: int = DEFAULT_MAX_CHUNK_CHARS,
    language: str | None = None,
) -> list[Chunk]:
    """Split *text* into ``Chunk`` objects with accurate char offsets.

    Args:
        text:       The full document text (already normalised).
        max_chars:  Soft upper bound on chunk character count.
        language:   BCP-47 language code; influences sentence-split strategy.

    Returns:
        List of ``Chunk`` objects in document order.  Returns a single chunk
        for texts shorter than *max_chars*.
    """
    if not text:
        return []

    if len(text) <= max_chars:
        return [Chunk(text=text, chunk_index=0, char_start=0, char_end=len(text))]

    # Build a list of (paragraph_text, abs_start, abs_end) from the full text.
    para_spans: list[tuple[str, int, int]] = []
    pos = 0
    for m in _PARA_SPLIT.finditer(text):
        para = text[pos: m.start()].strip()
        if para:
            actual_start = text.find(para, pos)
            para_spans.append((para, actual_start, actual_start + len(para)))
        pos = m.end()
    tail = text[pos:].strip()
    if tail:
        actual_start = text.find(tail, pos)
        para_spans.append((tail, actual_start, actual_start + len(tail)))

    # Expand over-sized paragraphs and then greedily bin-pack the rest.
    expanded: list[tuple[str, int, int]] = []
    for para, p_start, p_end in para_spans:
        if len(para) > max_chars:
            expanded.extend(_split_paragraph(para, p_start, max_chars, language))
        else:
            expanded.append((para, p_start, p_end))

    # Greedy packing: accumulate units until the next one would exceed max_chars.
    chunks: list[Chunk] = []
    current_units: list[tuple[str, int, int]] = []
    current_len = 0

    for unit_text, u_start, u_end in expanded:
        separator = "\n\n" if current_units else ""
        needed = len(separator) + len(unit_text)
        if current_units and current_len + needed > max_chars:
            joined = "\n\n".join(u[0] for u in current_units)
            chunks.append(Chunk(
                text=joined,
                chunk_index=len(chunks),
                char_start=current_units[0][1],
                char_end=current_units[-1][2],
            ))
            current_units = []
            current_len = 0
        current_units.append((unit_text, u_start, u_end))
        current_len += len(unit_text) + (2 if current_units else 0)

    if current_units:
        joined = "\n\n".join(u[0] for u in current_units)
        chunks.append(Chunk(
            text=joined,
            chunk_index=len(chunks),
            char_start=current_units[0][1],
            char_end=current_units[-1][2],
        ))

    return chunks
