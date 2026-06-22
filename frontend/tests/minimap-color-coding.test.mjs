/**
 * minimap-color-coding.test.mjs — structural tests for minimap tick coloring
 * and legend display.
 *
 * Run with: node frontend/tests/minimap-color-coding.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT      = path.resolve(__dirname, '..')

// Annotation density minimap lives in js/modes/lesson.js after the main.js
// split (Session 1 of the frontend refactor).
const mainJs = readFileSync(path.join(ROOT, 'js', 'modes', 'lesson.js'), 'utf8')
const html   = readFileSync(path.join(ROOT, 'index.html'), 'utf8')
const css    = readFileSync(path.join(ROOT, 'css', 'components.css'), 'utf8')

// ── main.js: _MINIMAP_COLORS covers all 5 CSS vars ───────────────────────────

const colorsIdx  = mainJs.indexOf('const _MINIMAP_COLORS = {')
const colorsBody = mainJs.slice(colorsIdx, colorsIdx + 1600)

assert.ok(colorsBody.includes('var(--ann-vocab)'),     '_MINIMAP_COLORS must map vocab types')
assert.ok(colorsBody.includes('var(--ann-grammar)'),   '_MINIMAP_COLORS must map grammar types')
assert.ok(colorsBody.includes('var(--ann-idiom)'),     '_MINIMAP_COLORS must map idiom types')
assert.ok(colorsBody.includes('var(--ann-literary)'),  '_MINIMAP_COLORS must map literary types')
assert.ok(colorsBody.includes('var(--ann-etymology)'), '_MINIMAP_COLORS must map etymology types')
console.log('✓ _MINIMAP_COLORS: all 5 CSS variable categories present')

// ── _TYPE_TO_CATEGORY maps all 5 category IDs ────────────────────────────────

assert.ok(mainJs.includes('const _TYPE_TO_CATEGORY = {'), 'main.js must declare _TYPE_TO_CATEGORY')

const catIdx  = mainJs.indexOf('const _TYPE_TO_CATEGORY = {')
const catBody = mainJs.slice(catIdx, catIdx + 900)

assert.ok(catBody.includes("'vocab'"),     '_TYPE_TO_CATEGORY must use vocab category')
assert.ok(catBody.includes("'grammar'"),   '_TYPE_TO_CATEGORY must use grammar category')
assert.ok(catBody.includes("'idioms'"),    '_TYPE_TO_CATEGORY must use idioms category')
assert.ok(catBody.includes("'literary'"),  '_TYPE_TO_CATEGORY must use literary category')
assert.ok(catBody.includes("'etymology'"), '_TYPE_TO_CATEGORY must use etymology category')
console.log('✓ _TYPE_TO_CATEGORY: all 5 category IDs present')

// ── minimapLegend ref declared ────────────────────────────────────────────────

assert.ok(mainJs.includes('minimapLegend'), 'main.js must declare minimapLegend')
assert.ok(
  mainJs.includes("querySelector('#minimap-legend')"),
  'main.js must query #minimap-legend'
)
console.log('✓ main.js: minimapLegend ref declared')

// ── buildMinimap sets tick.dataset.category and collects presentCats ──────────

const buildIdx  = mainJs.indexOf('function buildMinimap() {')
const buildBody = mainJs.slice(buildIdx, buildIdx + 2100)

assert.ok(buildBody.includes('_MINIMAP_COLORS['), 'buildMinimap must look up _MINIMAP_COLORS')
assert.ok(buildBody.includes('tick.style.background'), 'buildMinimap must set tick background')
assert.ok(buildBody.includes('tick.dataset.category'), 'buildMinimap must set tick.dataset.category')
assert.ok(buildBody.includes('presentCats'), 'buildMinimap must track presentCats Set')
assert.ok(buildBody.includes('_updateMinimapLegend(presentCats)'), 'buildMinimap must call _updateMinimapLegend')
console.log('✓ buildMinimap: colors ticks, sets dataset.category, calls _updateMinimapLegend')

// ── _updateMinimapLegend uses activeFilterCategories ─────────────────────────

const legendFnIdx  = mainJs.indexOf('function _updateMinimapLegend(presentCats) {')
const legendFnBody = mainJs.slice(legendFnIdx, legendFnIdx + 650)

assert.ok(legendFnBody.includes('minimapLegend'), '_updateMinimapLegend must reference minimapLegend')
assert.ok(legendFnBody.includes('.minimap-legend__dot'), '_updateMinimapLegend must query .minimap-legend__dot')
assert.ok(legendFnBody.includes('activeFilterCategories'), '_updateMinimapLegend must use activeFilterCategories')
assert.ok(legendFnBody.includes('minimap-legend__dot--present'), '_updateMinimapLegend must toggle --present class')
assert.ok(legendFnBody.includes('minimap-legend__dot--active'),  '_updateMinimapLegend must toggle --active class')
console.log('✓ _updateMinimapLegend: queries dots, uses activeFilterCategories, toggles state classes')

// ── index.html: #minimap-legend with 5 data-cat dots ─────────────────────────

assert.ok(html.includes('id="minimap-legend"'), 'index.html must have #minimap-legend element')
assert.ok(html.includes('class="minimap-legend"'), '#minimap-legend must have minimap-legend class')

const legendHtmlIdx  = html.indexOf('id="minimap-legend"')
const legendHtmlBody = html.slice(legendHtmlIdx, legendHtmlIdx + 750)

assert.ok(legendHtmlBody.includes('data-cat="vocab"'),     '#minimap-legend must include vocab dot')
assert.ok(legendHtmlBody.includes('data-cat="grammar"'),   '#minimap-legend must include grammar dot')
assert.ok(legendHtmlBody.includes('data-cat="idioms"'),    '#minimap-legend must include idioms dot')
assert.ok(legendHtmlBody.includes('data-cat="literary"'),  '#minimap-legend must include literary dot')
assert.ok(legendHtmlBody.includes('data-cat="etymology"'), '#minimap-legend must include etymology dot')

const dotCount = (legendHtmlBody.match(/minimap-legend__dot/g) ?? []).length
assert.ok(dotCount >= 5, `#minimap-legend must contain 5 dots (found ${dotCount})`)
console.log('✓ index.html: #minimap-legend with 5 category dots')

// ── CSS: .minimap-legend and state classes defined ────────────────────────────

assert.ok(css.includes('.minimap-legend {'),            'components.css must define .minimap-legend')
assert.ok(css.includes('.minimap-legend[hidden]'),      'components.css must hide .minimap-legend[hidden]')
assert.ok(css.includes('.minimap-legend__dot {'),       'components.css must define .minimap-legend__dot')
assert.ok(css.includes('.minimap-legend__dot--present'), 'components.css must define --present state')
assert.ok(css.includes('.minimap-legend__dot--active'),  'components.css must define --active state')
console.log('✓ CSS: minimap legend and all state classes defined')

console.log('\nAll minimap-color-coding tests passed.')
