/**
 * review-summary.test.mjs — structural tests for review session summary screen.
 *
 * Run with: node frontend/tests/review-summary.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT      = path.resolve(__dirname, '..')

const pane = readFileSync(path.join(ROOT, 'components', 'mnemosyne-review-pane.js'), 'utf8')

// ── Session stats tracking ────────────────────────────────────────────────────

assert.ok(pane.includes('#sessionStats'), 'component must declare #sessionStats private field')
assert.ok(
  pane.includes('count: 0') && pane.includes('qualitySum: 0') &&
  pane.includes('masteryDeltaSum: 0') && pane.includes('nextDueAt: null'),
  '#sessionStats must initialise all four counters'
)
console.log('✓ #sessionStats: field declared with correct initial shape')

assert.ok(
  pane.includes('#sessionStats = { count: 0') || pane.includes("'count': 0"),
  'startSession must reset #sessionStats'
)
const startIdx = pane.indexOf('async startSession')
assert.ok(startIdx !== -1, 'startSession must be defined')
const startBody = pane.slice(startIdx, startIdx + 500)
assert.ok(startBody.includes('#sessionStats'), 'startSession must reset #sessionStats')
console.log('✓ startSession: resets #sessionStats')

// ── Stats accumulated in _rate ────────────────────────────────────────────────

const rateIdx = pane.indexOf('async _rate(')
assert.ok(rateIdx !== -1, '_rate method must exist')
const rateBody = pane.slice(rateIdx, rateIdx + 1500)
assert.ok(rateBody.includes('#sessionStats.count++'), '_rate must increment count')
assert.ok(rateBody.includes('#sessionStats.qualitySum += quality'), '_rate must accumulate quality')
assert.ok(
  rateBody.includes('masteryDeltaSum') && rateBody.includes('mastery_score_before'),
  '_rate must accumulate mastery delta using mastery_score_before'
)
assert.ok(rateBody.includes('#sessionStats.nextDueAt'), '_rate must track earliest next_review_at')
console.log('✓ _rate: accumulates all four session stats')

// ── _renderDone summary HTML ──────────────────────────────────────────────────

assert.ok(pane.includes('pane--summary'), '_renderDone must use pane--summary class')
assert.ok(pane.includes('summary-stats'), '_renderDone must render .summary-stats')
assert.ok(pane.includes('summary-stat__label'), '_renderDone must use .summary-stat__label')
assert.ok(pane.includes('summary-stat__value'), '_renderDone must use .summary-stat__value')
assert.ok(pane.includes('<dl class="summary-stats">'), 'stats must use <dl> for semantics')
assert.ok(pane.includes('<dt class="summary-stat__label">'), 'labels must use <dt>')
assert.ok(pane.includes('<dd class="summary-stat__value"'), 'values must use <dd>')
console.log('✓ _renderDone: summary screen with semantic <dl>/<dt>/<dd>')

// ── Four stat tiles ───────────────────────────────────────────────────────────

assert.ok(pane.includes('Reviewed'), 'summary must show Reviewed tile')
assert.ok(pane.includes('Avg quality'), 'summary must show Avg quality tile')
assert.ok(pane.includes('Mastery'), 'summary must show Mastery tile')
assert.ok(pane.includes('Next review'), 'summary must show Next review tile')
console.log('✓ _renderDone: four stat tiles present')

// ── "Nothing due" empty state ─────────────────────────────────────────────────

assert.ok(pane.includes('Nothing due'), '_renderDone must show "Nothing due" when queue was empty')
assert.ok(pane.includes('summary-empty'), 'empty state must use .summary-empty class')
console.log('✓ _renderDone: nothing-due empty state present')

// ── Mastery delta sign and color ──────────────────────────────────────────────

assert.ok(pane.includes('data-positive='), 'mastery delta must use data-positive attribute for coloring')
assert.ok(
  pane.includes('summary-stat__value--delta'),
  '_renderDone must apply --delta modifier class for color'
)
console.log('✓ _renderDone: mastery delta colored via data-positive attribute')

// ── _relativeTime helper ──────────────────────────────────────────────────────

assert.ok(pane.includes('function _relativeTime'), '_relativeTime helper must be defined')
assert.ok(pane.includes('soon'), '_relativeTime must handle < 1 min')
assert.ok(pane.includes('${mins}m'), '_relativeTime must format minutes')
assert.ok(pane.includes('${hours}h'), '_relativeTime must format hours')
assert.ok(pane.includes('${days}d'), '_relativeTime must format days')
console.log('✓ _relativeTime: helper defined with soon/m/h/d branches')

// ── CSS ───────────────────────────────────────────────────────────────────────

const CSS_CLASSES = [
  '.pane--summary',
  '.summary-stats',
  '.summary-stat',
  '.summary-stat__label',
  '.summary-stat__value',
  '.summary-stat__value--delta',
  '.summary-empty',
]
for (const cls of CSS_CLASSES) {
  assert.ok(pane.includes(cls), `CSS must define ${cls}`)
}
console.log('✓ CSS: all .summary-* classes defined in component styles')

// Forced-colors support
assert.ok(
  pane.includes('forced-colors') && pane.includes('.summary-stat'),
  'CSS must include forced-colors rules for summary stats'
)
console.log('✓ CSS: forced-colors support present for summary stats')

console.log('\nAll review-summary tests passed.')
