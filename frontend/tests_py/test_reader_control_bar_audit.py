from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
READING = (ROOT / 'frontend/js/reading-experience.js').read_text(encoding='utf-8')
FLOW = (ROOT / 'frontend/js/flow-mode.js').read_text(encoding='utf-8')
ADAPTIVE = (ROOT / 'frontend/js/adaptive-reader.js').read_text(encoding='utf-8')
DIFFICULTY = (ROOT / 'frontend/js/difficulty-modulation.js').read_text(encoding='utf-8')
I18N = (ROOT / 'frontend/js/i18n.js').read_text(encoding='utf-8')
READING_CSS = (ROOT / 'frontend/css/reading-progressive.css').read_text(encoding='utf-8')


def test_subtle_learning_deep_modes_are_wired_and_persisted():
    for mode in ("subtle", "learning", "deep"):
        assert f"value: '{mode}'" in READING
    assert "btn.addEventListener('click', () => setMode(mode.value))" in READING
    assert "STORAGE_MODE_KEY = 'mnemosyne.reader.annotationMode'" in READING
    assert "document.documentElement.dataset.annotationReveal = currentMode" in READING
    assert "results.dataset.annotationReveal = currentMode" in READING


def test_flow_mode_is_wired_to_state_ui_and_persistence():
    assert "mnemosyne.reader.flowMode" in FLOW
    assert "document.body.classList.toggle('reader-flow-mode', flowMode)" in FLOW
    assert "localStorage.setItem(STORAGE_KEY, String(flowMode))" in FLOW
    assert "new CustomEvent('mnemosyne:flow-mode-changed'" in FLOW
    assert "#reader-flow-mode-btn" in FLOW
    assert "export function stepFlowSentence" in FLOW
    assert "syncAnnotationsForActiveSentence" in FLOW
    assert "mark.toggleAttribute('data-flow-hidden', shouldHide)" in FLOW


def test_focus_mode_is_wired_to_state_ui_and_persistence():
    assert "STORAGE_FOCUS_KEY = 'mnemosyne.reader.focusMode'" in READING
    assert "document.body.classList.toggle('reader-focus-mode', focusMode)" in READING
    assert "localStorage.setItem(STORAGE_FOCUS_KEY, String(focusMode))" in READING
    assert "#reader-focus-mode-btn" in READING


def test_adaptive_primary_button_is_real_toggle():
    assert "reader-adaptive-btn" in READING
    assert "mnemosyne:toggle-adaptive-reader" in READING
    assert "window.mnemosyneAdaptive?.isEnabled?.()" in READING
    assert "mnemosyne:adaptive-reader-changed" in READING


def test_adaptive_system_toggles_are_wired_and_persisted():
    assert "SETTINGS_KEY = 'mnemosyne.reader.adaptive.enabled'" in ADAPTIVE
    assert "REINFORCEMENT_KEY = 'mnemosyne.reader.reinforcement.enabled'" in ADAPTIVE
    assert "id = 'reader-adaptive-toggle'" in ADAPTIVE
    assert "id = 'reader-reinforcement-toggle'" in ADAPTIVE
    assert "document.body.classList.toggle('reader-adaptive-enabled', adaptiveEnabled)" in ADAPTIVE
    assert "document.body.classList.toggle('reader-reinforcement-enabled', reinforcementEnabled)" in ADAPTIVE


def test_settings_button_only_discloses_system_body():
    assert "id = 'reader-settings-toggle'" in READING
    assert "body.hidden = !opening" in READING
    assert "aria-controls', 'reader-system-body'" in READING
    assert "reader-ctrl__settings-btn--open" in READING


def test_adaptive_difficulty_events_exist_and_reader_button_wires_to_toggle():
    assert "mnemosyne:difficulty-adjusted" in ADAPTIVE
    assert "flashDifficultyAdjustment(detail.mode)" in ADAPTIVE
    # Adaptive button dispatches toggle event; state mutation lives in adaptive-reader.js.
    adaptive_button_section = READING.split("const adaptiveBtn =", 1)[1].split("secondary.append", 1)[0]
    assert "mnemosyne:toggle-adaptive-reader" in adaptive_button_section
    assert "adaptiveEnabled" not in adaptive_button_section
    assert "reinforcementEnabled" not in adaptive_button_section


def test_i18n_help_text_matches_expected_control_descriptions():
    assert "Subtle hides most annotations" in I18N
    assert "Learning shows key terms" in I18N
    assert "Deep reveals all" in I18N
    assert "Flow reads sentence-by-sentence" in I18N
    assert "Focus dims the page" in I18N
    assert "Adaptive shows or hides terms you already know" in I18N


def test_flow_navigation_controls_and_shortcuts_are_wired():
    assert "reader-flow-prev-btn" in READING
    assert "reader-flow-next-btn" in READING
    assert "reader_flow_shortcuts" in READING
    assert "event.key === 'ArrowRight' || event.key === 'n' || event.key === 'N'" in READING
    assert "event.key === 'ArrowLeft' || event.key === 'p' || event.key === 'P'" in READING


def test_flow_i18n_keys_exist():
    assert "reader_flow_prev" in I18N
    assert "reader_flow_next" in I18N
    assert "reader_flow_shortcuts" in I18N


def test_focus_mode_styles_cover_flow_and_viewport_blocks():
    assert 'body.reader-focus-mode .sentence-card[data-focus-block="true"]' in READING_CSS
    assert 'body.reader-focus-mode.reader-flow-mode .sentence-card[data-flow-active]' in READING_CSS
    assert 'body.reader-focus-mode #results-section::before' in READING_CSS
    assert 'forced-colors: active' in READING_CSS


def test_focus_mode_keyboard_and_viewport_tracking_are_wired():
    assert "document.addEventListener('focusin'" in READING
    assert "document.addEventListener('scroll', scheduleViewportFocusBlock" in READING
    assert "if (event.key.toLowerCase() === 'f'" in READING


def test_flow_plus_focus_combination_stays_predictable():
    assert "if (isFlowMode()) return" in READING
    assert "document.addEventListener('mnemosyne:flow-mode-changed'" in READING
    assert "if (isFlowMode() && getActiveSentenceIndex() < 0) stepFlowSentence(1)" in READING
    assert "body.reader-focus-mode.reader-flow-mode .sentence-card[data-flow-active]" in READING_CSS


def test_adaptive_and_advanced_overrides_are_composed_and_persisted():
    assert "const ADAPTIVE_OVERRIDE_KEY = 'mnemosyne.reader.adaptive.overrides.v1'" in ADAPTIVE
    assert "function overrideStorageKey()" in ADAPTIVE
    assert "const userId = getUser()?.id || 'guest'" in ADAPTIVE
    assert "function effectiveAdaptiveValue(key)" in ADAPTIVE
    assert "return adaptiveOverrides[key] || adaptiveProfile?.[key]" in ADAPTIVE
    assert "adaptiveOverrides[cat] = cb.checked; writeAdaptiveOverrides(); applyAdaptiveVisibility()" in ADAPTIVE
    assert "const categoryHidden = ANNOTATION_CATEGORIES.some(cat => !categoryEnabled(cat) && isCategoryVisible(annotation, cat))" in ADAPTIVE


def test_subtle_learning_deep_modes_drive_annotation_filtering_categories():
    assert "const MODE_DEFAULTS = {" in ADAPTIVE
    for mode in ("subtle", "learning", "deep"):
        assert f"{mode}:" in ADAPTIVE
    assert "function readerMode()" in ADAPTIVE
    assert "const defaults = MODE_DEFAULTS[mode] || MODE_DEFAULTS.learning" in ADAPTIVE
    assert "return adaptiveOverrides[category] ?? defaults[category] ?? true" in ADAPTIVE
    assert "annotation.toggleAttribute('data-category-hidden', categoryHidden)" in ADAPTIVE


def test_reader_control_modes_and_adaptive_settings_persist_across_session_reload():
    assert "let currentMode = localStorage.getItem(STORAGE_MODE_KEY) || 'learning'" in READING
    assert "let focusMode = localStorage.getItem(STORAGE_FOCUS_KEY) === 'true'" in READING
    assert "let adaptiveEnabled = localStorage.getItem(SETTINGS_KEY) !== 'false'" in ADAPTIVE
    assert "let reinforcementEnabled = localStorage.getItem(REINFORCEMENT_KEY) === 'true'" in ADAPTIVE
    assert "let adaptiveOverrides = readAdaptiveOverrides()" in ADAPTIVE


def test_localized_reader_control_labels_exist_in_all_locale_blocks():
    import re

    localized_keys = [
        "reader_mode_subtle", "reader_mode_learning", "reader_mode_deep",
        "reader_flow_mode", "reader_focus_mode", "adaptive_btn", "reader_flow_shortcuts",
    ]
    for key in localized_keys:
        occurrences = len(re.findall(rf"\b{key}\s*:\s*", I18N))
        assert occurrences >= 10, f"Missing or sparse translations for {key}: {occurrences}"

    # These labels are currently shared fallback strings; ensure they still exist
    # so untranslated locales fail loudly at lookup-time tests.
    assert "reader_settings_aria" in I18N
    assert "reader_adv_mode_hint" in I18N


def test_difficulty_bar_is_inline_not_dialog():
    assert "resultsSection.appendChild(bar)" in DIFFICULTY
    assert "document.createElement('dialog')" not in DIFFICULTY
    assert "showModal()" not in DIFFICULTY
    assert "#results-adaptive-bar" in DIFFICULTY
    assert "results-adaptive-bar" in READING_CSS
    assert "adaptive-settings-dialog" not in READING_CSS


def test_keyboard_navigation_and_aria_states_are_explicitly_wired():
    assert "flowPrevBtn.addEventListener('click', () => stepFlowSentence(-1))" in READING
    assert "flowNextBtn.addEventListener('click', () => stepFlowSentence(1))" in READING
    assert "btn.setAttribute('aria-pressed', String(active))" in READING
    assert "focusBtn.setAttribute('aria-pressed', String(focusMode))" in READING
    assert "btn.setAttribute('aria-disabled', String(!flowEnabled))" in READING
    assert "settingsBtn.setAttribute('aria-expanded', String(opening))" in READING
    assert "explainerToggle.setAttribute('aria-expanded', String(opening))" in READING
    assert "toggle.setAttribute('aria-pressed', String(adaptiveEnabled))" in ADAPTIVE
    assert "reinforce.setAttribute('aria-pressed', String(reinforcementEnabled))" in ADAPTIVE
