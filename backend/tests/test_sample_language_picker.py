from __future__ import annotations

import pathlib
import re


def _read(rel: str) -> str:
    return (pathlib.Path(__file__).parents[2] / rel).read_text(encoding='utf-8')


def test_sample_picker_has_language_selector_ui() -> None:
    html = _read('frontend/index.html')
    assert 'id="picker-sample-language"' in html
    assert 'data-i18n="sample_language_label"' in html


def test_sample_picker_excludes_fake_locales_and_has_fallback() -> None:
    js = _read('frontend/js/main.js')
    assert "'x-cjk-test'" in js and "'x-rtl-test'" in js
    assert "SAMPLE_TEXTS[selectedSampleLang] ?? SAMPLE_TEXTS[fallbackLang] ?? SAMPLE_TEXTS.es" in js


def test_sample_picker_localization_keys_exist_in_all_ui_locales() -> None:
    i18n = _read('frontend/js/i18n.js')
    locale_blocks = re.findall(r"\n\s{2}([a-z]{2}):\s*\{", i18n)
    for code in locale_blocks:
        block_match = re.search(rf"\n\s{{2}}{code}:\s*\{{(.*?)\n\s{{2}}\}},", i18n, re.S)
        assert block_match, f'missing block for {code}'
        block = block_match.group(1)
        assert 'sample_language_label' in block, f'missing sample_language_label in {code}'
        assert 'sample_missing_fallback' in block, f'missing sample_missing_fallback in {code}'
