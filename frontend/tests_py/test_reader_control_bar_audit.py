from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
READING = (ROOT / 'frontend/js/reading-experience.js').read_text(encoding='utf-8')
FLOW = (ROOT / 'frontend/js/flow-mode.js').read_text(encoding='utf-8')
ADAPTIVE = (ROOT / 'frontend/js/adaptive-reader.js').read_text(encoding='utf-8')
DIFFICULTY = (ROOT / 'frontend/js/difficulty-modulation.js').read_text(encoding='utf-8')
I18N = (ROOT / 'frontend/js/i18n.js').read_text(encoding='utf-8')


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


def test_adaptive_primary_button_opens_difficulty_dialog_only():
    assert "reader-adaptive-btn" in READING
    assert "window.mnemosyneDifficulty?.openDialog?.()" in READING


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


def test_adaptive_difficulty_events_exist_but_not_reader_control_button_path():
    assert "mnemosyne:difficulty-adjusted" in ADAPTIVE
    assert "flashDifficultyAdjustment(detail.mode)" in ADAPTIVE
    # The reader control bar adaptive button itself only opens dialog and does not
    # directly mutate adaptiveEnabled/reinforcementEnabled.
    adaptive_button_section = READING.split("const adaptiveBtn =", 1)[1].split("secondary.append", 1)[0]
    assert "adaptiveEnabled" not in adaptive_button_section
    assert "reinforcementEnabled" not in adaptive_button_section


def test_i18n_help_text_matches_expected_control_descriptions():
    assert "Subtle hides most annotations" in I18N
    assert "Learning shows key terms" in I18N
    assert "Deep reveals all" in I18N
    assert "Flow reads sentence-by-sentence" in I18N
    assert "Focus dims the page" in I18N
    assert "Adaptive tunes difficulty" in I18N


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
