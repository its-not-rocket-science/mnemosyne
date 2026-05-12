"""Registry of per-language NuanceExtractor instances."""
from __future__ import annotations

from backend.nuance.interface import NuanceExtractor

_REGISTRY: dict[str, NuanceExtractor] | None = None


def _build() -> dict[str, NuanceExtractor]:
    from backend.nuance import ar, de, en, es, fr, grc, he, it, ja, ko, la, pt, ru, zh
    return {
        "ar":  ar.ArabicNuanceExtractor(),
        "de":  de.GermanNuanceExtractor(),
        "en":  en.EnglishNuanceExtractor(),
        "es":  es.SpanishNuanceExtractor(),
        "fr":  fr.FrenchNuanceExtractor(),
        "grc": grc.AncientGreekNuanceExtractor(),
        "he":  he.HebrewNuanceExtractor(),
        "it":  it.ItalianNuanceExtractor(),
        "ja":  ja.JapaneseNuanceExtractor(),
        "ko":  ko.KoreanNuanceExtractor(),
        "la":  la.LatinNuanceExtractor(),
        "pt":  pt.PortugueseNuanceExtractor(),
        "ru":  ru.RussianNuanceExtractor(),
        "zh":  zh.ChineseNuanceExtractor(),
    }


def get_extractor(language: str) -> NuanceExtractor | None:
    """Return the extractor for *language*, or None if not supported."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _build()
    return _REGISTRY.get(language)
