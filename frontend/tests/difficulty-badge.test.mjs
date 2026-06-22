/**
 * difficulty-badge.test.mjs — structural tests for the CEFR difficulty badge
 * that appears in the text-picker dialog after POST /estimate-difficulty.
 *
 * Run with: node frontend/tests/difficulty-badge.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT      = path.resolve(__dirname, '..')

const html     = readFileSync(path.join(ROOT, 'index.html'), 'utf8')
// Text-picker dialog + difficulty estimator live in js/modes/explorer.js
// after the main.js split (Session 1 of the frontend refactor).
const mainJs   = readFileSync(path.join(ROOT, 'js', 'modes', 'explorer.js'), 'utf8')
const i18n     = readFileSync(path.join(ROOT, 'js', 'i18n.js'), 'utf8')
const globalCss = readFileSync(path.join(ROOT, 'css', 'components.css'), 'utf8')

// ── HTML element ──────────────────────────────────────────────────────────────

assert.ok(
  html.includes('id="picker-difficulty"'),
  '#picker-difficulty element must be present in index.html'
)
assert.ok(
  html.includes('class="picker-difficulty"'),
  '#picker-difficulty must have class picker-difficulty'
)
assert.ok(
  html.includes('role="status"') && html.includes('aria-live="polite"'),
  '#picker-difficulty must have role=status and aria-live=polite'
)
const difficultyElStart = html.indexOf('id="picker-difficulty"')
const difficultyElEnd   = html.indexOf('</p>', difficultyElStart)
const difficultyEl      = html.slice(difficultyElStart, difficultyElEnd)
assert.ok(
  difficultyEl.includes('hidden'),
  '#picker-difficulty must start hidden'
)
console.log('✓ HTML: #picker-difficulty element present with correct attributes')

// ── CSS classes ───────────────────────────────────────────────────────────────

assert.ok(
  globalCss.includes('.picker-difficulty {'),
  'global.css must define .picker-difficulty'
)
assert.ok(
  globalCss.includes('.picker-difficulty__badge {'),
  'global.css must define .picker-difficulty__badge'
)
assert.ok(
  globalCss.includes('.picker-difficulty__note {'),
  'global.css must define .picker-difficulty__note'
)
assert.ok(
  globalCss.includes('.picker-difficulty__cap {'),
  'global.css must define .picker-difficulty__cap'
)
console.log('✓ CSS: .picker-difficulty, __badge, __note, __cap defined')

// ── i18n keys ─────────────────────────────────────────────────────────────────

assert.ok(
  i18n.includes('difficulty_label'),
  'i18n.js must define difficulty_label key'
)
assert.ok(
  i18n.includes('difficulty_indicative'),
  'i18n.js must define difficulty_indicative key'
)
console.log('✓ i18n: difficulty_label and difficulty_indicative keys present')

// ── main.js wiring ────────────────────────────────────────────────────────────

assert.ok(
  mainJs.includes('pickerDifficulty'),
  'main.js must reference pickerDifficulty DOM element'
)
assert.ok(
  mainJs.includes('scheduleDifficultyEstimate'),
  'main.js must define scheduleDifficultyEstimate'
)
assert.ok(
  mainJs.includes('_runDifficultyEstimate'),
  'main.js must define _runDifficultyEstimate'
)
assert.ok(
  mainJs.includes('estimate-difficulty'),
  'main.js must call /estimate-difficulty endpoint'
)
assert.ok(
  mainJs.includes('_clearDifficultyBadge'),
  'main.js must define _clearDifficultyBadge'
)
console.log('✓ main.js: difficulty estimator functions wired')

// ── Debounce constants ────────────────────────────────────────────────────────

assert.ok(
  mainJs.includes('_DIFF_DEBOUNCE_MS'),
  'main.js must define _DIFF_DEBOUNCE_MS debounce constant'
)
assert.ok(
  mainJs.includes('_DIFF_MIN_CHARS'),
  'main.js must define _DIFF_MIN_CHARS minimum character threshold'
)
console.log('✓ main.js: debounce and min-chars constants defined')

// ── Trigger sites ─────────────────────────────────────────────────────────────

// textarea input
const textareaListenerBlock = mainJs.slice(
  mainJs.indexOf("// Textarea edits inside picker"),
  mainJs.indexOf("// Textarea edits inside picker") + 500,
)
assert.ok(
  textareaListenerBlock.includes('scheduleDifficultyEstimate'),
  'textarea input listener must call scheduleDifficultyEstimate'
)
console.log('✓ main.js: textarea input triggers difficulty estimate')

// language change
const langChangeBlock = mainJs.slice(
  mainJs.indexOf("languageSelect.addEventListener('change'"),
  mainJs.indexOf("languageSelect.addEventListener('change'") + 300,
)
assert.ok(
  langChangeBlock.includes('scheduleDifficultyEstimate'),
  'language change listener must call scheduleDifficultyEstimate'
)
console.log('✓ main.js: language change triggers difficulty estimate')

// openPicker resets badge
const openPickerBlock = mainJs.slice(
  mainJs.indexOf('function openPicker()'),
  mainJs.indexOf('function openPicker()') + 400,
)
assert.ok(
  openPickerBlock.includes('_clearDifficultyBadge'),
  'openPicker must call _clearDifficultyBadge'
)
assert.ok(
  openPickerBlock.includes('scheduleDifficultyEstimate'),
  'openPicker must call scheduleDifficultyEstimate'
)
console.log('✓ main.js: openPicker resets and re-schedules difficulty estimate')

// ── Badge structure ───────────────────────────────────────────────────────────

// Verify badge uses correct class names
assert.ok(
  mainJs.includes("'picker-difficulty__badge'"),
  "main.js must create element with class 'picker-difficulty__badge'"
)
assert.ok(
  mainJs.includes("'picker-difficulty__note'"),
  "main.js must create element with class 'picker-difficulty__note'"
)
console.log('✓ main.js: badge and note elements use correct CSS class names')

// Verify confident flag gates note
const estimateBlock = mainJs.slice(
  mainJs.indexOf('async function _runDifficultyEstimate'),
  mainJs.indexOf('async function _runDifficultyEstimate') + 2000,
)
assert.ok(
  estimateBlock.includes('data.confident'),
  '_runDifficultyEstimate must check data.confident before showing indicative note'
)
assert.ok(
  estimateBlock.includes('data.estimated_cefr'),
  '_runDifficultyEstimate must check data.estimated_cefr before rendering badge'
)
console.log('✓ main.js: confidence check gates indicative note; null CEFR clears badge')

// ── Capability chip ───────────────────────────────────────────────────────────

assert.ok(
  mainJs.includes('CAPABILITY_LABELS_I18N'),
  'main.js must import CAPABILITY_LABELS_I18N'
)
assert.ok(
  mainJs.includes("'picker-difficulty__cap'"),
  "main.js must create element with class 'picker-difficulty__cap'"
)
assert.ok(
  mainJs.includes('_CAP_KEY_MAP'),
  'main.js must define _CAP_KEY_MAP to map analysis_depth to i18n key'
)
assert.ok(
  mainJs.includes('cap_label_full') && mainJs.includes('cap_label_morphology_light') &&
  mainJs.includes('cap_label_dictionary') && mainJs.includes('cap_label_segmentation_only'),
  '_CAP_KEY_MAP must cover all four analysis_depth values'
)
assert.ok(
  mainJs.includes('analysis_depth_label'),
  'main.js must reference analysis_depth_label as fallback'
)
console.log('✓ main.js: capability chip uses CAPABILITY_LABELS_I18N with analysis_depth mapping')

// Verify CAPABILITY_LABELS_I18N exported from i18n.js
assert.ok(
  i18n.includes('export const CAPABILITY_LABELS_I18N'),
  'i18n.js must export CAPABILITY_LABELS_I18N'
)
assert.ok(
  i18n.includes('cap_label_full') && i18n.includes('cap_label_morphology_light') &&
  i18n.includes('cap_label_dictionary') && i18n.includes('cap_label_segmentation_only'),
  'CAPABILITY_LABELS_I18N must define all four cap_label keys'
)
console.log('✓ i18n.js: CAPABILITY_LABELS_I18N exported with all four cap keys')

console.log('\nAll difficulty-badge tests passed.')
