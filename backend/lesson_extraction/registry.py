from __future__ import annotations

from .adapters.arabic import ArabicAdapter
from .adapters.base import LessonExtractionAdapter
from .adapters.chinese import ChineseAdapter
from .adapters.japanese import JapaneseAdapter
from .adapters.russian import RussianAdapter

_REGISTRY: dict[str, LessonExtractionAdapter] = {
    "ar": ArabicAdapter(),
    "zh": ChineseAdapter(),
    "ja": JapaneseAdapter(),
    "ru": RussianAdapter(),
}


def get_adapter(language: str) -> LessonExtractionAdapter:
    return _REGISTRY.get(language, LessonExtractionAdapter())
