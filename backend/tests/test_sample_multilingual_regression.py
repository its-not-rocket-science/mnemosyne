from __future__ import annotations

import json
import pathlib
import re


ROOT = pathlib.Path(__file__).parents[2]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding='utf-8')


def _sample_fixture() -> dict[str, str]:
    return json.loads(_read('backend/tests/fixtures/sample_regression_multilingual.json'))


def _sample_texts() -> dict[str, str]:
    # SAMPLE_TEXTS moved to js/modes/explorer.js when Session 1 of the
    # frontend refactor split the former monolithic js/main.js.
    js = _read('frontend/js/modes/explorer.js')
    block = re.search(r"const SAMPLE_TEXTS = \{([\s\S]*?)\n\}", js)
    assert block, 'SAMPLE_TEXTS constant missing'
    samples: dict[str, str] = {}
    for key, value in re.findall(r"\n\s{2}([a-z-]+): '((?:\\'|[^'])*)',", block.group(1)):
        samples[key] = value.replace("\\'", "'")
    return samples


def test_sample_fixtures_exist_for_english_spanish_french() -> None:
    fixture = _sample_fixture()
    assert set(fixture) == {'en', 'es', 'fr'}


def test_spanish_fixture_matches_bug_report_and_keeps_accents() -> None:
    fixture = _sample_fixture()['es']
    assert fixture == (
        'El sol brillaba sobre las montañas mientras los viajeros descansaban junto al río. '
        'El agua fría refrescaba sus pies cansados después de un largo día de camino.'
    )
    assert 'montañas' in fixture
    assert 'río' in fixture
    assert 'fría' in fixture
    assert 'sobre mientras . El de un de .' not in fixture


def test_french_fixture_stays_french_and_keeps_diacritics() -> None:
    fixture = _sample_fixture()['fr']
    assert 'aperçut' in fixture
    assert 'hésita' in fixture
    assert "s'approcher" in fixture
    assert 'montañas' not in fixture


def test_frontend_sample_texts_include_exact_regression_fixtures_without_leakage() -> None:
    fixture = _sample_fixture()
    samples = _sample_texts()

    for code, text in fixture.items():
        assert samples[code] == text

    assert 'aperçut' not in samples['es']
    assert 'montañas' not in samples['fr']
    assert 'montañas' not in samples['en']


def test_language_switch_and_stale_cleanup_guardrails_present() -> None:
    # This guardrail logic moved to js/modes/explorer.js when Session 1 of
    # the frontend refactor split the former monolithic js/main.js.
    js = _read('frontend/js/modes/explorer.js')
    assert 'pickerTextarea.value = sample' in js
    assert "languageSelect.value = selectedSampleLang" in js
    assert "languageSelect.dispatchEvent(new Event('change'))" in js
    assert "setPickerStatus('')" in js


def test_next_up_and_clickable_pill_wiring_is_language_aware() -> None:
    # rec_next_up lives in js/i18n/library.js since Session 5 of the frontend
    # refactor split the former monolithic js/i18n.js (now a thin re-export
    # shim) into js/i18n/{core,annotations,lesson,library,review}.js.
    i18n = _read('frontend/js/i18n/library.js')
    recommended = _read('frontend/js/recommended-reading.js')
    main_js = _read('frontend/js/main.js')

    for snippet in ['Next up', 'A continuación', 'À venir']:
        assert snippet in i18n

    assert "t('rec_next_up')" in recommended
    assert "import '../components/mnemosyne-pill.js'" in main_js
