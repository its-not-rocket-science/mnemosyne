/**
 * corpus-drills.test.mjs — structural tests for confusable pair drill from corpus.
 *
 * Run with: node frontend/tests/corpus-drills.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT      = path.resolve(__dirname, '..')

const html   = readFileSync(path.join(ROOT, 'index.html'), 'utf8')
const mainJs = readFileSync(path.join(ROOT, 'js', 'main.js'), 'utf8')
const i18n   = readFileSync(path.join(ROOT, 'js', 'i18n.js'), 'utf8')

// ── HTML ──────────────────────────────────────────────────────────────────────

assert.ok(html.includes('id="corpus-drills-btn"'), 'index.html must include #corpus-drills-btn')
assert.ok(
  html.includes('data-i18n="corpus_drills_btn"'),
  '#corpus-drills-btn must carry data-i18n="corpus_drills_btn"'
)
console.log('✓ HTML: #corpus-drills-btn present with i18n attr')

// ── main.js: DOM ref ──────────────────────────────────────────────────────────

assert.ok(mainJs.includes('corpusDrillsBtn'), 'main.js must declare corpusDrillsBtn')
assert.ok(
  mainJs.includes("querySelector('#corpus-drills-btn')"),
  'main.js must query #corpus-drills-btn'
)
console.log('✓ main.js: corpusDrillsBtn DOM ref declared')

// ── renderResults: shows/hides button based on nuance items ──────────────────

const renderIdx  = mainJs.indexOf('function renderResults(')
const renderBody = mainJs.slice(renderIdx, mainJs.indexOf('\nfunction ', renderIdx + 10))
assert.ok(
  renderBody.includes('corpusDrillsBtn'),
  'renderResults must update corpusDrillsBtn visibility'
)
assert.ok(
  renderBody.includes("type === 'nuance'"),
  'renderResults must check for nuance items'
)
console.log('✓ main.js: renderResults gates button on nuance items')

// ── _openCorpusDrills function ────────────────────────────────────────────────

assert.ok(mainJs.includes('async function _openCorpusDrills('), 'main.js must define _openCorpusDrills')
const drillsIdx  = mainJs.indexOf('async function _openCorpusDrills(')
const drillsBody = mainJs.slice(drillsIdx, drillsIdx + 1400)
assert.ok(drillsBody.includes('nuance_types'),        '_openCorpusDrills must collect nuance_types')
assert.ok(drillsBody.includes('nuance_type'),         '_openCorpusDrills must read lesson_data.nuance_type')
assert.ok(drillsBody.includes('/nuance-drills'),      '_openCorpusDrills must call /nuance-drills endpoint')
assert.ok(drillsBody.includes('syntheticLesson'),     '_openCorpusDrills must build synthetic lesson')
assert.ok(drillsBody.includes('modal.open('),         '_openCorpusDrills must open modal')
assert.ok(drillsBody.includes("'nuance'"),             'synthetic lesson must have type nuance')
console.log('✓ main.js: _openCorpusDrills collects types, fetches, builds synthetic lesson, opens modal')

// ── button wired to handler ───────────────────────────────────────────────────

assert.ok(
  mainJs.includes("corpusDrillsBtn?.addEventListener('click', _openCorpusDrills)"),
  'corpusDrillsBtn must be wired to _openCorpusDrills'
)
console.log('✓ main.js: corpusDrillsBtn click → _openCorpusDrills')

// ── i18n ──────────────────────────────────────────────────────────────────────

assert.ok(i18n.includes('corpus_drills_btn'), 'i18n.js must define corpus_drills_btn')
assert.ok(
  (i18n.match(/corpus_drills_btn/g) ?? []).length >= 11,
  'corpus_drills_btn must appear in all 11 language blocks'
)
console.log('✓ i18n: corpus_drills_btn defined in all 11 language blocks')

console.log('\nAll corpus-drills tests passed.')
