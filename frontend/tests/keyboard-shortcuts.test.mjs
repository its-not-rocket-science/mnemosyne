/**
 * keyboard-shortcuts.test.mjs — structural tests for reader keyboard shortcuts.
 *
 * Run with: node frontend/tests/keyboard-shortcuts.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT      = path.resolve(__dirname, '..')

const html      = readFileSync(path.join(ROOT, 'index.html'), 'utf8')
// Global keyboard shortcuts live in js/shared.js after the main.js split
// (Session 1 of the frontend refactor); FILTER_CYCLE is a shared constant
// re-exported from js/reading-state.js, and the former bare _filterCycleIdx
// module variable is now the filterCycleIndex()/setFilterCycleIndex()
// accessor pair (ES module bindings can't be reassigned by importers).
const mainJs    = readFileSync(path.join(ROOT, 'js', 'shared.js'), 'utf8')
const filterBar = readFileSync(path.join(ROOT, 'components', 'mnemosyne-filter-bar.js'), 'utf8')

// ── FILTER_CYCLE state ────────────────────────────────────────────────────────

assert.ok(mainJs.includes('FILTER_CYCLE'), 'shared.js must reference FILTER_CYCLE')
const readingState = readFileSync(path.join(ROOT, 'js', 'reading-state.js'), 'utf8')
assert.ok(readingState.includes("'vocab'"), 'FILTER_CYCLE must include vocab')
assert.ok(readingState.includes("'grammar'"), 'FILTER_CYCLE must include grammar')
assert.ok(mainJs.includes('filterCycleIndex'), 'shared.js must use filterCycleIndex accessor')
assert.ok(mainJs.includes('setFilterCycleIndex'), 'shared.js must use setFilterCycleIndex accessor')
console.log('✓ shared.js: FILTER_CYCLE and filterCycleIndex/setFilterCycleIndex used')

// ── mnemosyne-filter-bar: activateCategory ────────────────────────────────────

assert.ok(filterBar.includes('activateCategory('), 'filter-bar must define activateCategory method')
const activateIdx  = filterBar.indexOf('activateCategory(')
const activateBody = filterBar.slice(activateIdx, activateIdx + 300)
assert.ok(activateBody.includes('this.#active.clear()'), 'activateCategory must clear active set')
assert.ok(activateBody.includes('#dispatch'), 'activateCategory must dispatch filter-change')
console.log('✓ mnemosyne-filter-bar: activateCategory method defined')

// ── follow-along remapped to L ────────────────────────────────────────────────

const keydownIdx  = mainJs.lastIndexOf("document.addEventListener('keydown'")
const keydownBody = mainJs.slice(keydownIdx, keydownIdx + 4000)

assert.ok(
  keydownBody.includes("case 'l':") && keydownBody.includes("case 'L':"),
  'follow-along must be on l/L key'
)
assert.ok(keydownBody.includes('isFollowAlongEnabled'), 'l/L must toggle isFollowAlongEnabled')
console.log('✓ main.js: follow-along remapped to L')

// ── T: translate focused sentence ────────────────────────────────────────────

assert.ok(
  keydownBody.includes("case 't':") && keydownBody.includes("case 'T':"),
  'T key must be handled'
)
assert.ok(keydownBody.includes('translate-btn'), 'T shortcut must click translate-btn')
assert.ok(keydownBody.includes('sentence-card'), 'T shortcut must find sentence-card')
console.log('✓ main.js: T shortcut triggers translate on focused sentence')

// ── D: corpus drills ─────────────────────────────────────────────────────────

assert.ok(
  keydownBody.includes("case 'd':") && keydownBody.includes("case 'D':"),
  'D key must be handled'
)
// D shortcut clicks the corpus-drills button rather than calling the drill
// opener directly — the opener (openCorpusDrills) is wired to that button's
// click listener in js/modes/review.js, which owns corpus confusable drills.
assert.ok(keydownBody.includes('corpusDrillsBtn.click()'), 'D shortcut must click corpusDrillsBtn')
const reviewJs = readFileSync(path.join(ROOT, 'js', 'modes', 'review.js'), 'utf8')
assert.ok(
  reviewJs.includes("corpusDrillsBtn?.addEventListener('click', openCorpusDrills)"),
  'review.js must wire corpusDrillsBtn click to openCorpusDrills'
)
console.log('✓ shared.js: D shortcut clicks corpusDrillsBtn, wired to openCorpusDrills in review.js')

// ── F: cycle filter ───────────────────────────────────────────────────────────

assert.ok(
  keydownBody.includes("case 'f':") && keydownBody.includes("case 'F':"),
  'F key must be handled'
)
assert.ok(keydownBody.includes('filterCycleIndex'), 'F shortcut must advance filterCycleIndex')
assert.ok(keydownBody.includes('activateCategory'), 'F shortcut must call activateCategory')
console.log('✓ main.js: F shortcut cycles annotation filter')

// ── S: focus annotation search ────────────────────────────────────────────────

assert.ok(
  keydownBody.includes("case 's':") && keydownBody.includes("case 'S':"),
  'S key must be handled'
)
assert.ok(keydownBody.includes('annotationSearch.focus()'), 'S shortcut must focus annotationSearch')
assert.ok(keydownBody.includes('annotationSearch.select()'), 'S shortcut must select annotationSearch text')
console.log('✓ main.js: S shortcut focuses annotation search input')

// ── Shortcuts dialog updated ──────────────────────────────────────────────────

assert.ok(html.includes('<kbd>T</kbd>'), 'shortcuts dialog must show T key')
assert.ok(html.includes('<kbd>D</kbd>'), 'shortcuts dialog must show D key')
assert.ok(html.includes('<kbd>F</kbd>'), 'shortcuts dialog must show F key')
assert.ok(html.includes('<kbd>S</kbd>'), 'shortcuts dialog must show S key')
assert.ok(html.includes('<kbd>L</kbd>'), 'shortcuts dialog must show L key (follow-along)')
assert.ok(!html.includes('<kbd>F</kbd>\n            </dt>\n            <dd>Toggle follow-along'), 'F must not map to follow-along anymore')
console.log('✓ HTML: shortcuts dialog lists T, D, F, S, L')

console.log('\nAll keyboard-shortcuts tests passed.')
