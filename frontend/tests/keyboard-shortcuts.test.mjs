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
const mainJs    = readFileSync(path.join(ROOT, 'js', 'main.js'), 'utf8')
const filterBar = readFileSync(path.join(ROOT, 'components', 'mnemosyne-filter-bar.js'), 'utf8')

// ── FILTER_CYCLE state ────────────────────────────────────────────────────────

assert.ok(mainJs.includes('FILTER_CYCLE'), 'main.js must declare FILTER_CYCLE')
assert.ok(mainJs.includes("'vocab'"), 'FILTER_CYCLE must include vocab')
assert.ok(mainJs.includes("'grammar'"), 'FILTER_CYCLE must include grammar')
assert.ok(mainJs.includes('_filterCycleIdx'), 'main.js must declare _filterCycleIdx')
console.log('✓ main.js: FILTER_CYCLE and _filterCycleIdx declared')

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
assert.ok(keydownBody.includes('_openCorpusDrills'), 'D shortcut must call _openCorpusDrills')
console.log('✓ main.js: D shortcut opens corpus drills')

// ── F: cycle filter ───────────────────────────────────────────────────────────

assert.ok(
  keydownBody.includes("case 'f':") && keydownBody.includes("case 'F':"),
  'F key must be handled'
)
assert.ok(keydownBody.includes('_filterCycleIdx'), 'F shortcut must advance _filterCycleIdx')
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
