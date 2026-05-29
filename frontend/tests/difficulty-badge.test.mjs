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
const mainJs   = readFileSync(path.join(ROOT, 'js', 'main.js'), 'utf8')
const i18n     = readFileSync(path.join(ROOT, 'js', 'i18n.js'), 'utf8')
const globalCss = readFileSync(path.join(ROOT, 'css', 'global.css'), 'utf8')

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
console.log('✓ CSS: .picker-difficulty, __badge, __note defined')

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
  mainJs.indexOf('async function _runDifficultyEstimate') + 1200,
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

console.log('\nAll difficulty-badge tests passed.')
