/**
 * results-difficulty-badge.test.mjs — structural tests for the CEFR difficulty
 * badge shown in the results heading after a text is parsed.
 *
 * Run with: node frontend/tests/results-difficulty-badge.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT      = path.resolve(__dirname, '..')

// Results heading difficulty badge lives in js/modes/explorer.js after the
// main.js split (Session 1 of the frontend refactor); renderResults itself
// (which clears the badge on each render) lives in js/modes/lesson.js and
// imports _clearResultsDifficultyBadge from explorer.js.
const mainJs    = readFileSync(path.join(ROOT, 'js', 'modes', 'explorer.js'), 'utf8')
const lessonJs  = readFileSync(path.join(ROOT, 'js', 'modes', 'lesson.js'), 'utf8')
const html      = readFileSync(path.join(ROOT, 'index.html'), 'utf8')
const globalCss = readFileSync(path.join(ROOT, 'css', 'components.css'), 'utf8')

// ── index.html: #results-difficulty element ───────────────────────────────────

assert.ok(html.includes('id="results-difficulty"'), 'index.html must have #results-difficulty element')
assert.ok(html.includes('class="results-difficulty"'), '#results-difficulty must have results-difficulty class')
assert.ok(html.includes('aria-live="polite"'), '#results-difficulty must have aria-live=polite')
assert.ok(
  (function () {
    const idx = html.indexOf('id="results-difficulty"')
    return html.slice(idx, idx + 300).includes('hidden')
  })(),
  '#results-difficulty must start hidden'
)

const titleRowIdx = html.indexOf('class="results-title-row"')
assert.ok(titleRowIdx !== -1, 'index.html must have .results-title-row wrapper')
const titleRowBody = html.slice(titleRowIdx, titleRowIdx + 300)
assert.ok(titleRowBody.includes('results-heading'), '.results-title-row must contain #results-heading')
assert.ok(titleRowBody.includes('results-difficulty'), '.results-title-row must contain #results-difficulty')
console.log('✓ index.html: #results-difficulty in .results-title-row, starts hidden, has aria-live')

// ── main.js: refs and state ───────────────────────────────────────────────────

assert.ok(mainJs.includes('resultsDifficulty'), 'main.js must declare resultsDifficulty')
assert.ok(
  mainJs.includes("querySelector('#results-difficulty')"),
  "main.js must query '#results-difficulty'"
)
assert.ok(mainJs.includes('currentDocumentDifficulty'), 'main.js must declare currentDocumentDifficulty')
console.log('✓ main.js: resultsDifficulty ref and currentDocumentDifficulty state declared')

// ── badge helper functions ────────────────────────────────────────────────────

assert.ok(mainJs.includes('function _clearResultsDifficultyBadge()'), 'main.js must define _clearResultsDifficultyBadge')
assert.ok(mainJs.includes('function _setResultsDifficultyBadge(cefr, confident)'), 'main.js must define _setResultsDifficultyBadge')
assert.ok(mainJs.includes('async function _fetchResultsDifficulty(text, language)'), 'main.js must define _fetchResultsDifficulty')

const clearFnIdx  = mainJs.indexOf('function _clearResultsDifficultyBadge()')
const clearFnBody = mainJs.slice(clearFnIdx, clearFnIdx + 250)
assert.ok(clearFnBody.includes('resultsDifficulty.hidden = true'), '_clearResultsDifficultyBadge must hide element')
assert.ok(clearFnBody.includes('currentDocumentDifficulty = null'), '_clearResultsDifficultyBadge must reset state')

const setFnIdx  = mainJs.indexOf('function _setResultsDifficultyBadge(cefr, confident)')
const setFnBody = mainJs.slice(setFnIdx, setFnIdx + 450)
assert.ok(setFnBody.includes('dataset.cefr'), '_setResultsDifficultyBadge must set dataset.cefr')
assert.ok(setFnBody.includes('resultsDifficulty.hidden = false'), '_setResultsDifficultyBadge must show element')

console.log('✓ main.js: _clearResultsDifficultyBadge, _setResultsDifficultyBadge, _fetchResultsDifficulty defined')

// ── fetch wired after parse and load ─────────────────────────────────────────

assert.ok(
  mainJs.includes('_fetchResultsDifficulty(normalizedText, language)'),
  'doParseText must call _fetchResultsDifficulty after parse'
)
// _loadSource lives in js/modes/library.js, which imports _fetchResultsDifficulty
// from explorer.js (cross-coordinator function import, not DOM passing).
const libraryJs = readFileSync(path.join(ROOT, 'js', 'modes', 'library.js'), 'utf8')
assert.ok(
  libraryJs.includes('_fetchResultsDifficulty(sourceText, data.language)'),
  '_loadSource must call _fetchResultsDifficulty after load'
)
console.log('✓ main.js: _fetchResultsDifficulty called in doParseText and _loadSource')

// ── renderResults clears badge ────────────────────────────────────────────────

const renderIdx  = lessonJs.indexOf('function renderResults(pipelinePayload, language) {')
const renderHead = lessonJs.slice(renderIdx, renderIdx + 150)
assert.ok(
  renderHead.includes('_clearResultsDifficultyBadge()'),
  'renderResults must call _clearResultsDifficultyBadge at start'
)
console.log('✓ main.js: renderResults clears badge on each new render')

// ── CSS: .results-difficulty with CEFR color variants ────────────────────────

assert.ok(globalCss.includes('.results-difficulty {'), 'global.css must define .results-difficulty')
assert.ok(globalCss.includes('.results-difficulty[hidden]'), 'global.css must hide .results-difficulty[hidden]')
assert.ok(globalCss.includes('[data-cefr="A1"]'), 'global.css must define A1 color variant')
assert.ok(globalCss.includes('[data-cefr="B1"]'), 'global.css must define B1 color variant')
assert.ok(globalCss.includes('[data-cefr="C1"]'), 'global.css must define C1 color variant')
assert.ok(globalCss.includes('.results-title-row {'), 'global.css must define .results-title-row')
console.log('✓ CSS: .results-difficulty with A/B/C color variants, .results-title-row layout')

console.log('\nAll results-difficulty-badge tests passed.')
