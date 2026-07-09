"""Perseus Digital Library URL helpers for classical Latin and Greek entries.

Provides:
  perseus_morph_url(lemma, lang)   — morphological analysis page on Perseus Hopper
  scaife_citation_url(abbreviated, ref) — Scaife reader URL for a resolved citation

No network requests are made. All functions are synchronous and pure.
"""
from __future__ import annotations

import urllib.parse

SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"la", "grc"})

_LANG_CODE: dict[str, str] = {"la": "lat", "grc": "greek"}

_PERSEUS_MORPH_BASE = "https://www.perseus.tufts.edu/hopper/morph"
_SCAIFE_READER_BASE = "https://scaife.perseus.org/reader"

# Maps L&S/LSJ author abbreviation → CTS work URN.
# Only single-work authors or authors with one overwhelmingly dominant work are
# listed; multi-work authors where the citation alone cannot identify the work
# (Cic., Plat., Arist., Plut., etc.) are intentionally omitted so we never
# produce a link that points to the wrong passage.
_ABBR_URN: dict[str, str] = {
    # ── Latin prose ──────────────────────────────────────────────────────────
    "Caes.":  "urn:cts:latinLit:phi0448.phi001.perseus-lat2",  # de Bello Gallico
    "Lucr.":  "urn:cts:latinLit:phi0550.phi001.perseus-lat2",  # De Rerum Natura
    "Sal.":   "urn:cts:latinLit:phi0631.phi001.perseus-lat2",  # Bellum Catilinae
    "Liv.":   "urn:cts:latinLit:phi0914.phi001.perseus-lat2",  # Ab Urbe Condita
    "Tac.":   "urn:cts:latinLit:phi1351.phi005.perseus-lat2",  # Annales
    "Quint.": "urn:cts:latinLit:phi1002.phi001.perseus-lat2",  # Institutio Oratoria
    "Gell.":  "urn:cts:latinLit:phi1254.phi001.perseus-lat2",  # Noctes Atticae
    "Apul.":  "urn:cts:latinLit:phi1212.phi001.perseus-lat2",  # Metamorphoses
    # ── Latin poetry ─────────────────────────────────────────────────────────
    "Verg.":  "urn:cts:latinLit:phi0690.phi003.perseus-lat2",  # Aeneid (most cited)
    "Cat.":   "urn:cts:latinLit:phi0472.phi001.perseus-lat2",  # Carmina
    "Ov.":    "urn:cts:latinLit:phi0959.phi006.perseus-lat2",  # Metamorphoses
    "Hor.":   "urn:cts:latinLit:phi0893.phi001.perseus-lat2",  # Odes (most cited)
    "Juv.":   "urn:cts:latinLit:phi1276.phi001.perseus-lat2",  # Saturae
    "Mart.":  "urn:cts:latinLit:phi1294.phi002.perseus-lat2",  # Epigrammata
    "Prop.":  "urn:cts:latinLit:phi0620.phi001.perseus-lat2",  # Elegiae
    "Tib.":   "urn:cts:latinLit:phi0660.phi001.perseus-lat2",  # Elegiae
    # Cic., Hor., Plin., Sen., Luc. (conflicts w/ Lucian), Stat., Sil.,
    # Val., Ter., Plaut., Varr., Nep., Suet., Aug., Hier., Ambr., etc. omitted
    # ── Greek ────────────────────────────────────────────────────────────────
    "Hom.":   "urn:cts:greekLit:tlg0012.tlg001.perseus-grc2",  # Iliad (default)
    "Hdt.":   "urn:cts:greekLit:tlg0016.tlg001.perseus-grc2",  # Historiae
    "Thuc.":  "urn:cts:greekLit:tlg0003.tlg001.perseus-grc2",  # Historiae
    "Pind.":  "urn:cts:greekLit:tlg0033.tlg001.perseus-grc2",  # Olympian Odes
    "Polyb.": "urn:cts:greekLit:tlg0543.tlg001.perseus-grc2",  # Historiae
    # Xen., Soph., Eur., Aesch., Dem., Plat., Arist., Plut., Diod., Arr.,
    # Strab., D.C., Luc. (Lucian) omitted — multi-work or uncertain work ids
}


def perseus_morph_url(lemma: str, lang: str) -> str | None:
    """Return Perseus morphological analysis URL, or None for unsupported langs."""
    code = _LANG_CODE.get(lang)
    if not code:
        return None
    q = urllib.parse.quote(lemma, safe="")
    return f"{_PERSEUS_MORPH_BASE}?l={q}&la={code}"


def scaife_citation_url(abbreviated: str, ref: str) -> str | None:
    """Return a Scaife reader URL for a citation dict entry, or None.

    Parameters
    ----------
    abbreviated : str
        Full citation string, e.g. ``"Verg. 2.766"`` or ``"Hom. 1.1"``.
    ref : str
        Raw reference from L&S/LSJ, e.g. ``"2.766"``.
    """
    ref = ref.strip().rstrip(",. ")
    if not ref:
        return None
    for abbr, urn in _ABBR_URN.items():
        if abbreviated.startswith(abbr):
            return f"{_SCAIFE_READER_BASE}/{urn}:{ref}/"
    return None
