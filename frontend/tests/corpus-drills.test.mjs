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
// Corpus drills moved to js/modes/review.js (the button handler,
// _openCorpusDrills renamed to exported openCorpusDrills) after the main.js
// split (Session 1 of the frontend refactor); the renderResults
// show/hide-on-nuance gating stays with js/modes/lesson.js.
const reviewJs = readFileSync(path.join(ROOT, 'js', 'modes', 'review.js'), 'utf8')
const lessonJs = readFileSync(path.join(ROOT, 'js', 'modes', 'lesson.js'), 'utf8')
const mainJs = reviewJs + lessonJs
const i18n   = ['core','annotations','lesson','library','review'].map(f => readFileSync(path.join(ROOT, 'js', 'i18n', `${f}.js`), 'utf8')).join('\n')

// ── HTML ──────────────────────────────────────────────────────────────────────

assert.ok(html.includes('id="corpus-drills-btn"'), 'index.html must include #corpus-drills-btn')
assert.ok(
  html.includes('data-i18n="corpus_drills_btn"'),
  '#corpus-drills-btn must carry data-i18n="corpus_drills_btn"'
)
console.log('✓ HTML: #corpus-drills-btn present with i18n attr')

// ── main.js: DOM ref ──────────────────────────────────────────────────────────

assert.ok(mainJs.includes('corpusDrillsBtn'), 'review.js/lesson.js must declare corpusDrillsBtn')
assert.ok(
  mainJs.includes("querySelector('#corpus-drills-btn')"),
  'review.js/lesson.js must query #corpus-drills-btn'
)
console.log('✓ review.js/lesson.js: corpusDrillsBtn DOM ref declared')

// ── renderResults: shows/hides button based on nuance items ──────────────────

const renderIdx  = lessonJs.indexOf('function renderResults(')
const renderBody = lessonJs.slice(renderIdx, lessonJs.indexOf('\nfunction ', renderIdx + 10))
assert.ok(
  renderBody.includes('corpusDrillsBtn'),
  'renderResults must update corpusDrillsBtn visibility'
)
assert.ok(
  renderBody.includes("type === 'nuance'"),
  'renderResults must check for nuance items'
)
console.log('✓ lesson.js: renderResults gates button on nuance items')

// ── openCorpusDrills function ─────────────────────────────────────────────────

assert.ok(reviewJs.includes('async function openCorpusDrills('), 'review.js must define openCorpusDrills')
const drillsIdx  = reviewJs.indexOf('async function openCorpusDrills(')
// Window widened slightly past the original 1400 chars — Session 5 of the
// frontend refactor added an i18n loadBundle('review') call + explanatory
// comment at the top of this function (corpus drills can be reached via
// the D shortcut without ever visiting #/review, so the bundle holding its
// modal_* strings needs an explicit load here too).
const drillsBody = reviewJs.slice(drillsIdx, drillsIdx + 1700)
assert.ok(drillsBody.includes('nuance_types'),        'openCorpusDrills must collect nuance_types')
assert.ok(drillsBody.includes('nuance_type'),         'openCorpusDrills must read lesson_data.nuance_type')
assert.ok(drillsBody.includes('/nuance-drills'),      'openCorpusDrills must call /nuance-drills endpoint')
assert.ok(drillsBody.includes('syntheticLesson'),     'openCorpusDrills must build synthetic lesson')
assert.ok(drillsBody.includes('modal.open('),         'openCorpusDrills must open modal')
assert.ok(drillsBody.includes("'nuance'"),             'synthetic lesson must have type nuance')
console.log('✓ review.js: openCorpusDrills collects types, fetches, builds synthetic lesson, opens modal')

// ── button wired to handler ───────────────────────────────────────────────────

assert.ok(
  reviewJs.includes("corpusDrillsBtn?.addEventListener('click', openCorpusDrills)"),
  'corpusDrillsBtn must be wired to openCorpusDrills'
)
console.log('✓ review.js: corpusDrillsBtn click → openCorpusDrills')

// ── i18n ──────────────────────────────────────────────────────────────────────

assert.ok(i18n.includes('corpus_drills_btn'), 'i18n.js must define corpus_drills_btn')
assert.ok(
  (i18n.match(/corpus_drills_btn/g) ?? []).length >= 11,
  'corpus_drills_btn must appear in all 11 language blocks'
)
console.log('✓ i18n: corpus_drills_btn defined in all 11 language blocks')

console.log('\nAll corpus-drills tests passed.')
