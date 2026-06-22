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

// Auto-advance state and _trackSentenceRating/_autoAdvanceSentence/lesson-open
// live in js/modes/lesson.js after the main.js split (Session 1 of the
// frontend refactor); _loadSource (which seeds _currentSourceDocId via the
// setCurrentSourceDocId() export and clears _sentenceRatedIds via
// clearSentenceRatedIds()) lives in js/modes/library.js. Concatenate both so
// assertions against either file's content keep working.
const lessonJs  = readFileSync(path.join(ROOT, 'js', 'modes', 'lesson.js'), 'utf8')
const libraryJs = readFileSync(path.join(ROOT, 'js', 'modes', 'library.js'), 'utf8')
const mainJs = lessonJs + libraryJs
const css    = readFileSync(path.join(ROOT, 'css', 'components.css'), 'utf8')

// ── State variables ───────────────────────────────────────────────────────────

assert.ok(lessonJs.includes('_currentSourceDocId'), 'lesson.js must declare _currentSourceDocId')
assert.ok(lessonJs.includes('currentSentenceIndex'), 'lesson.js must use the currentSentenceIndex accessor')
assert.ok(lessonJs.includes('_sentenceRatedIds'),   'lesson.js must declare _sentenceRatedIds')
console.log('✓ lesson.js: auto-advance state variables declared')

// ── _loadSource resets state ──────────────────────────────────────────────────

const loadSourceIdx  = libraryJs.indexOf('async function _loadSource(')
const loadSourceBody = libraryJs.slice(loadSourceIdx, loadSourceIdx + 500)
assert.ok(
  loadSourceBody.includes('setCurrentSourceDocId(sourceId)'),
  '_loadSource must call setCurrentSourceDocId(sourceId)'
)
assert.ok(
  loadSourceBody.includes('clearSentenceRatedIds()'),
  '_loadSource must call clearSentenceRatedIds()'
)
console.log('✓ library.js: _loadSource captures sourceId and clears rated set')

// ── lesson-open captures sentence index ───────────────────────────────────────

const lessonOpenIdx  = lessonJs.indexOf("results.addEventListener('lesson-open'")
const lessonOpenBody = lessonJs.slice(lessonOpenIdx, lessonOpenIdx + 800)
assert.ok(
  lessonOpenBody.includes('setCurrentSentenceIndex'),
  "lesson-open handler must call setCurrentSentenceIndex"
)
assert.ok(
  lessonOpenBody.includes('sentenceIndex'),
  "lesson-open handler must read dataset.sentenceIndex"
)
console.log('✓ lesson.js: lesson-open handler captures sentence index')

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
