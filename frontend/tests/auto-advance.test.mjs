/**
 * auto-advance.test.mjs — structural tests for reading auto-advance on sentence completion.
 *
 * Run with: node frontend/tests/auto-advance.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT      = path.resolve(__dirname, '..')

const mainJs = readFileSync(path.join(ROOT, 'js', 'main.js'), 'utf8')
const css    = readFileSync(path.join(ROOT, 'css', 'components.css'), 'utf8')

// ── State variables ───────────────────────────────────────────────────────────

assert.ok(mainJs.includes('_currentSourceDocId'), 'main.js must declare _currentSourceDocId')
assert.ok(mainJs.includes('_currentSentenceIdx'), 'main.js must declare _currentSentenceIdx')
assert.ok(mainJs.includes('_sentenceRatedIds'),   'main.js must declare _sentenceRatedIds')
console.log('✓ main.js: auto-advance state variables declared')

// ── _loadSource resets state ──────────────────────────────────────────────────

const loadSourceIdx  = mainJs.indexOf('async function _loadSource(')
const loadSourceBody = mainJs.slice(loadSourceIdx, loadSourceIdx + 500)
assert.ok(
  loadSourceBody.includes('_currentSourceDocId = sourceId'),
  '_loadSource must assign _currentSourceDocId = sourceId'
)
assert.ok(
  loadSourceBody.includes('_sentenceRatedIds.clear()'),
  '_loadSource must clear _sentenceRatedIds'
)
console.log('✓ main.js: _loadSource captures sourceId and clears rated set')

// ── lesson-open captures sentence index ───────────────────────────────────────

const lessonOpenIdx  = mainJs.indexOf("results.addEventListener('lesson-open'")
const lessonOpenBody = mainJs.slice(lessonOpenIdx, lessonOpenIdx + 800)
assert.ok(
  lessonOpenBody.includes('_currentSentenceIdx'),
  "lesson-open handler must update _currentSentenceIdx"
)
assert.ok(
  lessonOpenBody.includes('sentenceIndex'),
  "lesson-open handler must read dataset.sentenceIndex"
)
console.log('✓ main.js: lesson-open handler captures sentence index')

// ── _trackSentenceRating function ────────────────────────────────────────────

assert.ok(mainJs.includes('function _trackSentenceRating('), 'main.js must define _trackSentenceRating')
const trackIdx  = mainJs.indexOf('function _trackSentenceRating(')
const trackBody = mainJs.slice(trackIdx, trackIdx + 600)
assert.ok(trackBody.includes('_sentenceRatedIds'), '_trackSentenceRating must use _sentenceRatedIds')
assert.ok(trackBody.includes('learnable_objects'), '_trackSentenceRating must check learnable_objects')
assert.ok(trackBody.includes('_autoAdvanceSentence'), '_trackSentenceRating must call _autoAdvanceSentence')
console.log('✓ main.js: _trackSentenceRating checks all items rated')

// ── _autoAdvanceSentence function ────────────────────────────────────────────

assert.ok(mainJs.includes('function _autoAdvanceSentence('), 'main.js must define _autoAdvanceSentence')
const advIdx  = mainJs.indexOf('function _autoAdvanceSentence(')
const advBody = mainJs.slice(advIdx, advIdx + 1000)
assert.ok(advBody.includes('scrollIntoView'), '_autoAdvanceSentence must scrollIntoView next card')
assert.ok(advBody.includes('sentence-card--done-flash'), '_autoAdvanceSentence must add done-flash class')
assert.ok(advBody.includes('/reading/'), '_autoAdvanceSentence must PATCH /reading/ endpoint')
assert.ok(advBody.includes('sentences_read'), '_autoAdvanceSentence must send sentences_read payload')
console.log('✓ main.js: _autoAdvanceSentence scrolls, flashes, and PATCHes reading progression')

// ── pane-practice-check calls _trackSentenceRating ────────────────────────────

const practiceCheckIdx  = mainJs.indexOf("addEventListener('pane-practice-check'")
const practiceCheckBody = mainJs.slice(practiceCheckIdx, practiceCheckIdx + 2500)
assert.ok(
  practiceCheckBody.includes('_trackSentenceRating'),
  'pane-practice-check handler must call _trackSentenceRating'
)
console.log('✓ main.js: pane-practice-check triggers _trackSentenceRating')

// ── PATCH is non-fatal (fire-and-forget) ─────────────────────────────────────

assert.ok(
  advBody.includes('.catch('),
  '_autoAdvanceSentence PATCH must have a .catch handler (non-fatal)'
)
console.log('✓ main.js: reading PATCH is fire-and-forget with .catch')

// ── CSS: animation ───────────────────────────────────────────────────────────

assert.ok(css.includes('sentence-done-flash'),       'CSS must define sentence-done-flash keyframes')
assert.ok(css.includes('.sentence-card--done-flash'), 'CSS must define .sentence-card--done-flash')
assert.ok(css.includes('prefers-reduced-motion'),     'CSS must respect prefers-reduced-motion')
assert.ok(css.includes('forced-colors'),              'CSS must include forced-colors support')
console.log('✓ CSS: sentence-card--done-flash animation with a11y variants')

console.log('\nAll auto-advance tests passed.')
