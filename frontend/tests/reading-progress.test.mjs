/**
 * reading-progress.test.mjs — structural tests for reading progress in the
 * load-lesson dialog (progress bar, resume/start/re-read action labels).
 *
 * Run with: node frontend/tests/reading-progress.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT      = path.resolve(__dirname, '..')

// Load-lesson dialog / source list item builder lives in js/modes/library.js
// after the main.js split (Session 1 of the frontend refactor).
const mainJs    = readFileSync(path.join(ROOT, 'js', 'modes', 'library.js'), 'utf8')
const i18n      = readFileSync(path.join(ROOT, 'js', 'i18n.js'), 'utf8')
const css       = readFileSync(path.join(ROOT, 'css', 'components.css'), 'utf8')

// ── i18n keys ─────────────────────────────────────────────────────────────────

const REQUIRED_KEYS = [
  'source_action_start',
  'source_action_resume',
  'source_action_reread',
  'source_progress_text',
  'source_complete',
]
for (const key of REQUIRED_KEYS) {
  assert.ok(i18n.includes(key), `i18n.js must define ${key}`)
}
console.log('✓ i18n: source action/progress keys present')

// ── CSS classes ───────────────────────────────────────────────────────────────

assert.ok(css.includes('.load-lesson-list__title'),        'CSS must define __title')
assert.ok(css.includes('.load-lesson-list__action'),       'CSS must define __action')
assert.ok(css.includes('.load-lesson-list__progress-row'), 'CSS must define __progress-row')
assert.ok(css.includes('.load-lesson-list__progress-bar'), 'CSS must define __progress-bar')
assert.ok(css.includes('.load-lesson-list__progress-fill'),'CSS must define __progress-fill')
assert.ok(css.includes('.load-lesson-list__progress-text'),'CSS must define __progress-text')
console.log('✓ CSS: all load-lesson-list progress classes defined')

// ── main.js: _buildSourceItem ─────────────────────────────────────────────────

assert.ok(mainJs.includes('_buildSourceItem'), 'main.js must define _buildSourceItem')
assert.ok(mainJs.includes('completion_fraction'), '_buildSourceItem must use completion_fraction')
assert.ok(mainJs.includes('sentences_total'), '_buildSourceItem must use sentences_total')
assert.ok(mainJs.includes('next_position'), '_buildSourceItem must use next_position')
assert.ok(mainJs.includes('is_complete'), '_buildSourceItem must check is_complete')
console.log('✓ main.js: _buildSourceItem uses all progress fields')

// Three action states wired
const buildFn = mainJs.slice(
  mainJs.indexOf('function _buildSourceItem'),
  mainJs.indexOf('function _buildSourceItem') + 2500,
)
assert.ok(buildFn.includes('source_action_start'),  '_buildSourceItem must produce start action')
assert.ok(buildFn.includes('source_action_resume'),  '_buildSourceItem must produce resume action')
assert.ok(buildFn.includes('source_action_reread'),  '_buildSourceItem must produce re-read action')
console.log('✓ main.js: start / resume / re-read action keys used')

// Progress bar fill uses percentage
assert.ok(buildFn.includes('inlineSize'), '_buildSourceItem must set inlineSize on fill')
assert.ok(buildFn.includes('pct'), '_buildSourceItem must compute pct percentage')
console.log('✓ main.js: progress fill bar width computed from completion_fraction')

// Accessible aria-label
assert.ok(buildFn.includes('aria-label'), '_buildSourceItem must set aria-label on button')
console.log('✓ main.js: button has aria-label for screen readers')

// ── Logical property usage ────────────────────────────────────────────────────

// Ensure progress bar uses logical CSS (inline-size not width)
const progressBarBlock = css.slice(
  css.indexOf('.load-lesson-list__progress-fill'),
  css.indexOf('.load-lesson-list__progress-fill') + 200,
)
assert.ok(
  progressBarBlock.includes('inline-size') || progressBarBlock.includes('inlineSize'),
  'progress fill must use inline-size (logical property)'
)
console.log('✓ CSS: progress fill uses inline-size (logical property)')

console.log('\nAll reading-progress tests passed.')
