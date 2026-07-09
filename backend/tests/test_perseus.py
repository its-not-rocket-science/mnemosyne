"""Tests for backend.dictionary.perseus URL helpers."""
import pytest

from backend.dictionary.perseus import (
    SUPPORTED_LANGUAGES,
    perseus_morph_url,
    scaife_citation_url,
)


def test_supported_languages():
    assert "la" in SUPPORTED_LANGUAGES
    assert "grc" in SUPPORTED_LANGUAGES
    assert "fr" not in SUPPORTED_LANGUAGES


# ── perseus_morph_url ────────────────────────────────────────────────────────

def test_morph_url_latin():
    url = perseus_morph_url("amor", "la")
    assert url == "https://www.perseus.tufts.edu/hopper/morph?l=amor&la=lat"


def test_morph_url_greek():
    url = perseus_morph_url("λόγος", "grc")
    assert url is not None
    assert "la=greek" in url
    assert url.startswith("https://www.perseus.tufts.edu/hopper/morph")


def test_morph_url_unsupported_lang():
    assert perseus_morph_url("amour", "fr") is None


def test_morph_url_lemma_encoded():
    url = perseus_morph_url("sum esse", "la")
    assert " " not in url
    assert "sum%20esse" in url


# ── scaife_citation_url ──────────────────────────────────────────────────────

def test_scaife_url_virgil():
    url = scaife_citation_url("Verg. 2.766", "2.766")
    assert url is not None
    assert "phi0690" in url
    assert "phi003" in url
    assert url.endswith(":2.766/")


def test_scaife_url_homer():
    url = scaife_citation_url("Hom. 1.1", "1.1")
    assert url is not None
    assert "tlg0012" in url
    assert "tlg001" in url
    assert url.endswith(":1.1/")


def test_scaife_url_caesar():
    url = scaife_citation_url("Caes. 1.1.1", "1.1.1")
    assert url is not None
    assert "phi0448" in url


def test_scaife_url_thucydides():
    url = scaife_citation_url("Thuc. 2.34", "2.34")
    assert url is not None
    assert "tlg0003" in url
    assert url.endswith(":2.34/")


def test_scaife_url_herodotus():
    url = scaife_citation_url("Hdt. 1.5", "1.5")
    assert url is not None
    assert "tlg0016" in url


def test_scaife_url_catullus():
    url = scaife_citation_url("Cat. 64.1", "64.1")
    assert url is not None
    assert "phi0472" in url


def test_scaife_url_no_match():
    # Cicero is multi-work, not in map
    assert scaife_citation_url("Cic. 1.1", "1.1") is None


def test_scaife_url_plato_omitted():
    assert scaife_citation_url("Plat. 300a", "300a") is None


def test_scaife_url_empty_ref():
    assert scaife_citation_url("Verg. ", "") is None


def test_scaife_url_ref_whitespace_stripped():
    url = scaife_citation_url("Lucr. 2.100", "  2.100  ")
    assert url is not None
    assert url.endswith(":2.100/")


def test_scaife_url_ref_trailing_comma_stripped():
    url = scaife_citation_url("Liv. 1.1", "1.1,")
    assert url is not None
    assert url.endswith(":1.1/")


def test_scaife_url_scaife_base():
    url = scaife_citation_url("Hom. 1.1", "1.1")
    assert url.startswith("https://scaife.perseus.org/reader/")
