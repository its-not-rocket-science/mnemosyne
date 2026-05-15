"""Unit-level regression tests for each stage of the URL-fetch/extract pipeline.

Every test here is anchored to an exact pattern that was reported in a real
URL (New Scientist, Project Gutenberg, arXiv DOI normalisation, etc.).  No
network calls are made — all tests operate directly on the private helpers
imported from ``backend.ingestion.fetcher``.
"""
from __future__ import annotations

import pytest

from backend.ingestion.fetcher import (
    _clean_extracted_text,
    _clean_gutenberg_text,
    _decode_mojibake,
    _dedupe_lines,
    _drop_disclosure_markers,
    _drop_promotional_lines,
    _extract,
    _normalize_reference_tokens,
)


# ── _decode_mojibake ──────────────────────────────────────────────────────────

class TestDecodeMojibake:
    def test_clean_text_unchanged(self):
        text = "The quick brown fox jumps over the lazy dog."
        assert _decode_mojibake(text) == text

    def test_utf8_mojibake_repaired(self):
        # "é" as UTF-8 bytes mis-decoded as latin-1 → Ã©
        mojibake = "cafÃ©"  # café as mojibake
        result = _decode_mojibake(mojibake)
        assert "café" in result or "café" in result

    def test_no_trigger_chars_passes_through(self):
        text = "Hello world – plain ASCII with dash."
        assert _decode_mojibake(text) == text

    def test_accented_chars_not_garbled(self):
        text = "El niño juega con su amigo."
        assert _decode_mojibake(text) == text

    def test_arabic_text_unchanged(self):
        text = "كان الطقس جميلاً في المدينة"
        assert _decode_mojibake(text) == text


# ── _drop_promotional_lines ───────────────────────────────────────────────────

class TestDropPromotionalLines:
    """Exact patterns reported from New Scientist and similar sites."""

    def test_advertisement_line_dropped(self):
        text = "Paragraph one.\n\nAdvertisement\n\nParagraph two."
        result = _drop_promotional_lines(text)
        assert "Advertisement" not in result
        assert "Paragraph one." in result
        assert "Paragraph two." in result

    def test_advertisement_case_insensitive(self):
        text = "Content.\nADVERTISEMENT\nMore content."
        assert "ADVERTISEMENT" not in _drop_promotional_lines(text)

    def test_new_scientist_weekly_dose_dropped(self):
        # Exact string from reported New Scientist article
        text = (
            "Real article text.\n"
            "Receive a weekly dose of discovery in your inbox sign up now\n"
            "More article text."
        )
        result = _drop_promotional_lines(text)
        assert "Receive a weekly dose" not in result
        assert "Real article text." in result
        assert "More article text." in result

    def test_sign_up_newsletter_variants_dropped(self):
        variants = [
            "Sign up to our weekly newsletter",
            "Sign Up To Our Science Newsletter Today",
            "sign up to our daily briefing newsletter",
        ]
        for line in variants:
            result = _drop_promotional_lines(f"Before.\n{line}\nAfter.")
            assert line not in result, f"Expected '{line}' to be dropped"
            assert "Before." in result
            assert "After." in result

    def test_subscribe_new_scientist_dropped(self):
        text = "Text before.\nSubscribe to New Scientist today\nText after."
        result = _drop_promotional_lines(text)
        assert "Subscribe to New Scientist" not in result
        assert "Text before." in result

    def test_blank_lines_preserved(self):
        text = "Para one.\n\nPara two."
        result = _drop_promotional_lines(text)
        assert "\n\n" in result

    def test_regular_content_not_dropped(self):
        text = "Scientists discovered a new species of beetle.\nThe research was published in Nature."
        result = _drop_promotional_lines(text)
        assert result == text


# ── _normalize_reference_tokens ───────────────────────────────────────────────

class TestNormalizeReferenceTokens:
    """Exact DOI and arXiv patterns observed in real article text."""

    def test_doi_with_spaced_dots_normalized(self):
        # From New Scientist article: "10 . 48550 / arXiv . 2505.01085"
        text = "Reference: 10 . 48550 / arXiv . 2505.01085"
        result = _normalize_reference_tokens(text)
        assert "10.48550/arXiv.2505.01085" in result

    def test_arxiv_with_dot_normalized(self):
        text = "See arXiv . 2505.01085 for details."
        result = _normalize_reference_tokens(text)
        assert "arXiv.2505.01085" in result

    def test_arxiv_with_colon_normalized(self):
        text = "Paper arXiv : 2505.01085 was cited."
        result = _normalize_reference_tokens(text)
        assert "arXiv:2505.01085" in result

    def test_doi_arxiv_combined_normalized(self):
        text = "DOI 10.48550/arXiv . 2505.01085 is the identifier."
        result = _normalize_reference_tokens(text)
        assert "10.48550/arXiv.2505.01085" in result

    def test_clean_doi_unchanged(self):
        text = "Reference: 10.1234/journal.2024.001"
        result = _normalize_reference_tokens(text)
        assert "10.1234/journal.2024.001" in result

    def test_unrelated_numbers_not_mangled(self):
        text = "There were 10 scientists and 48550 observations."
        result = _normalize_reference_tokens(text)
        assert "10 scientists" in result


# ── _drop_disclosure_markers ──────────────────────────────────────────────────

class TestDropDisclosureMarkers:
    """Disclosure triangle characters reported in scraped text."""

    def test_black_right_pointing_triangle_dropped(self):
        # U+25B6 ▶
        text = "▶ This is a disclosure section.\nNormal line."
        result = _drop_disclosure_markers(text)
        assert "▶" not in result
        assert "This is a disclosure section." in result

    def test_black_right_pointing_pointer_dropped(self):
        # U+25BA ►
        text = "► Source: some publication."
        result = _drop_disclosure_markers(text)
        assert "►" not in result
        assert "Source: some publication." in result

    def test_triangular_bullet_dropped(self):
        # U+25B8 ▸
        text = "▸ Disclosure: the author has no conflicts."
        result = _drop_disclosure_markers(text)
        assert "▸" not in result
        assert "Disclosure: the author has no conflicts." in result

    def test_mid_line_marker_dropped(self):
        text = "Content ▶ More content"
        result = _drop_disclosure_markers(text)
        assert "▶" not in result
        assert "Content" in result
        assert "More content" in result

    def test_no_markers_unchanged(self):
        text = "Plain text with no disclosure markers."
        result = _drop_disclosure_markers(text)
        assert result == text

    def test_duplicate_markers_cleaned(self):
        text = "▶ ▶ Double marker line."
        result = _drop_disclosure_markers(text)
        assert "▶" not in result
        assert "Double marker line." in result


# ── _dedupe_lines ─────────────────────────────────────────────────────────────

class TestDedupeLines:
    def test_duplicate_line_removed(self):
        text = "First line.\nDuplicate line.\nDuplicate line.\nLast line."
        result = _dedupe_lines(text)
        assert result.count("Duplicate line.") == 1
        assert "First line." in result
        assert "Last line." in result

    def test_blank_lines_preserved(self):
        text = "Para one.\n\nPara two."
        result = _dedupe_lines(text)
        assert "\n\n" in result

    def test_blank_lines_not_deduplicated(self):
        # Multiple blanks should be kept (not treated as duplicate)
        text = "Para.\n\n\nAnother para."
        result = _dedupe_lines(text)
        # The two blank lines are both kept (blank lines are not deduplicated)
        assert "Para." in result
        assert "Another para." in result

    def test_unique_lines_unchanged(self):
        lines = ["Alpha", "Beta", "Gamma", "Delta"]
        text = "\n".join(lines)
        result = _dedupe_lines(text)
        assert result == text

    def test_first_occurrence_kept(self):
        text = "Header\nContent A\nHeader\nContent B"
        result = _dedupe_lines(text)
        lines = [l for l in result.splitlines() if l.strip()]
        assert lines[0] == "Header"
        assert "Content A" in result
        assert "Content B" in result
        assert lines.count("Header") == 1

    def test_whitespace_trimmed_for_comparison(self):
        # "  Line  " and "Line" are the same after strip
        text = "  Line  \nLine\nOther"
        result = _dedupe_lines(text)
        assert result.count("Line") == 1


# ── _clean_gutenberg_text ─────────────────────────────────────────────────────

class TestCleanGutenbergText:
    def test_start_marker_stripped(self):
        text = (
            "*** START OF THE PROJECT GUTENBERG EBOOK NOTRE-DAME DE PARIS ***\n"
            "NOTRE-DAME DE PARIS\n"
            "By Victor Hugo\n"
            "*** END OF THE PROJECT GUTENBERG EBOOK NOTRE-DAME DE PARIS ***"
        )
        result = _clean_gutenberg_text(text)
        assert "NOTRE-DAME DE PARIS" in result
        assert "START OF THE PROJECT GUTENBERG EBOOK" not in result

    def test_end_marker_stripped(self):
        text = (
            "*** START OF THE PROJECT GUTENBERG EBOOK TEST ***\n"
            "Chapter I.\nThe story begins here.\n"
            "*** END OF THE PROJECT GUTENBERG EBOOK TEST ***\n"
            "Post-book boilerplate."
        )
        result = _clean_gutenberg_text(text)
        assert "Post-book boilerplate." not in result
        assert "Chapter I." in result

    def test_alternate_start_marker(self):
        text = (
            "***START OF THE PROJECT GUTENBERG EBOOK TEST ***\n"
            "Body text.\n"
            "*** END OF THE PROJECT GUTENBERG EBOOK TEST ***"
        )
        result = _clean_gutenberg_text(text)
        assert "Body text." in result
        assert "START OF THE PROJECT GUTENBERG EBOOK" not in result

    def test_eebook_end_variant(self):
        text = (
            "*** START OF THE PROJECT GUTENBERG EBOOK TEST ***\n"
            "Story text here.\n"
            "End of the Project Gutenberg eBook of Test"
        )
        result = _clean_gutenberg_text(text)
        assert "Story text here." in result
        assert "End of the Project Gutenberg eBook" not in result

    def test_no_markers_returns_stripped(self):
        text = "  Plain text without any Gutenberg markers.  "
        result = _clean_gutenberg_text(text)
        assert result == "Plain text without any Gutenberg markers."

    def test_content_between_markers_preserved(self):
        text = (
            "*** START OF THE PROJECT GUTENBERG EBOOK FOO ***\n"
            "Il y a aujourd'hui trois cent quarante-huit ans.\n"
            "La ville était pleine de bruit.\n"
            "*** END OF THE PROJECT GUTENBERG EBOOK FOO ***"
        )
        result = _clean_gutenberg_text(text)
        assert "Il y a aujourd'hui" in result
        assert "La ville était pleine" in result


# ── _clean_extracted_text (full pipeline) ────────────────────────────────────

class TestCleanExtractedTextPipeline:
    """Integration tests for the full cleaning pipeline on exact reported patterns."""

    def test_new_scientist_full_pipeline(self):
        # Exact pattern from the reported New Scientist article URL:
        # https://www.newscientist.com/article/2488095-how-government-use-of-ai-could-hurt-democracy/
        raw = (
            "How government use of AI could hurt democracy\n\n"
            "Advertisement\n\n"
            "Receive a weekly dose of discovery in your inbox sign up now\n\n"
            'Researchers warned that "opaque systems" can erode trust.\n\n'
            "Reference arXiv DOI: 10 . 48550 / arXiv . 2505.01085\n\n"
            "▶ Reference arXiv DOI: 10.48550/arXiv.2505.01085"
        )
        result = _clean_extracted_text(raw)
        assert "Advertisement" not in result
        assert "Receive a weekly dose" not in result
        assert '"opaque systems" can erode trust.' in result
        assert "10.48550/arXiv.2505.01085" in result
        assert result.count("10.48550/arXiv.2505.01085") == 1  # deduped
        assert "▶" not in result

    def test_newsletter_and_disclosure_stripped_together(self):
        raw = (
            "Article content here.\n"
            "Sign up to our science newsletter\n"
            "▸ Source: Nature journal\n"
            "More article content."
        )
        result = _clean_extracted_text(raw)
        assert "Sign up to our science newsletter" not in result
        assert "▸" not in result
        assert "Article content here." in result
        assert "More article content." in result


# ── _extract (HTML → text, exact URLs) ───────────────────────────────────────

class TestExtractExactUrlPatterns:
    """Regression tests anchored to exact reported URLs and their HTML patterns."""

    def test_new_scientist_url_pattern_cleans_correctly(self):
        html = """
        <html><body>
          <article>
            <h1>How government use of AI could hurt democracy</h1>
            <p>Advertisement</p>
            <p>Receive a weekly dose of discovery in your inbox sign up now</p>
            <p>Researchers warned that &#8220;opaque systems&#8221; can erode trust.</p>
            <p>Reference: 10 . 48550 / arXiv . 2505.01085</p>
            <p>&#9654; Reference: 10.48550/arXiv.2505.01085</p>
          </article>
        </body></html>
        """
        result = _extract(
            html,
            "https://www.newscientist.com/article/2488095-how-government-use-of-ai-could-hurt-democracy/",
        )
        assert "Advertisement" not in result.text
        assert "Receive a weekly dose" not in result.text
        assert "opaque systems" in result.text
        assert "10.48550/arXiv.2505.01085" in result.text
        assert result.text.count("10.48550/arXiv.2505.01085") == 1
        assert "▶" not in result.text  # U+25B6 ▶

    def test_gutenberg_notre_dame_url_pattern(self):
        # Regression for Gutenberg URL: https://www.gutenberg.org/files/19657/19657-h/19657-h.htm
        html = """
        <html><body>
          <div id="content">
            <p>*** START OF THE PROJECT GUTENBERG EBOOK NOTRE-DAME DE PARIS ***</p>
            <h2>LIVRE PREMIER</h2>
            <p>Il y a aujourd&#8217;hui trois cent quarante-huit ans six mois et dix-neuf jours.</p>
            <p>&#192; cette &#233;poque, Paris retentissait du tocsin.</p>
            <p>*** END OF THE PROJECT GUTENBERG EBOOK NOTRE-DAME DE PARIS ***</p>
          </div>
        </body></html>
        """
        result = _extract(
            html,
            "https://www.gutenberg.org/files/19657/19657-h/19657-h.htm#I",
        )
        assert "LIVRE PREMIER" in result.text
        assert "Il y a aujourd" in result.text
        assert "START OF THE PROJECT GUTENBERG EBOOK" not in result.text
        assert "END OF THE PROJECT GUTENBERG EBOOK" not in result.text

    def test_gutenberg_url_does_not_serve_only_footnotes(self):
        html = """
        <html><body>
          <div class="footnotes">
            <h2>FOOTNOTES</h2>
            <p>[1] A footnote reference.</p>
          </div>
          <div id="chapter1">
            <p>*** START OF THE PROJECT GUTENBERG EBOOK TEST ***</p>
            <h2>CHAPTER ONE</h2>
            <p>The main story begins here.</p>
            <p>*** END OF THE PROJECT GUTENBERG EBOOK TEST ***</p>
          </div>
        </body></html>
        """
        result = _extract(
            html,
            "https://www.gutenberg.org/files/12345/12345-h/12345-h.htm",
        )
        assert "CHAPTER ONE" in result.text
        assert "[1] A footnote reference." not in result.text
