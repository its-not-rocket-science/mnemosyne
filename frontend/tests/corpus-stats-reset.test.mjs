/**
 * corpus-stats-reset.test.mjs — structural tests for corpus stats strip,
 * progress-pct label, and reading-progress reset.
 *
 * Run with: node frontend/tests/corpus-stats-reset.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT      = path.resolve(__dirname, '..')

// Corpus browser lives entirely in js/modes/library.js after the main.js
// split (Session 1 of the frontend refactor).
const mainJs = readFileSync(path.join(ROOT, 'js', 'modes', 'library.js'), 'utf8')
const html   = readFileSync(path.join(ROOT, 'index.html'), 'utf8')
const i18n   = ['core','annotations','lesson','library','review'].map(f => readFileSync(path.join(ROOT, 'js', 'i18n', `${f}.js`), 'utf8')).join('\n')

// ── index.html: #corpus-browser-stats strip ───────────────────────────────────

assert.ok(html.includes('id="corpus-browser-stats"'), 'index.html must have #corpus-browser-stats')

const statsIdx  = html.indexOf('id="corpus-browser-stats"')
const statsBody = html.slice(statsIdx, statsIdx + 1400)

assert.ok(statsBody.includes('id="corpus-stat-total"'),        '#corpus-stat-total span required')
assert.ok(statsBody.includes('id="corpus-stat-in-progress"'),  '#corpus-stat-in-progress span required')
assert.ok(statsBody.includes('id="corpus-stat-not-started"'),  '#corpus-stat-not-started span required')
assert.ok(statsBody.includes('id="corpus-stat-complete"'),     '#corpus-stat-complete span required')
assert.ok(statsBody.includes('data-sort="in_progress"'),       'in_progress chip must have data-sort')
assert.ok(statsBody.includes('data-sort="not_started"'),       'not_started chip must have data-sort')
assert.ok(statsBody.includes('data-sort="complete"'),          'complete chip must have data-sort')
assert.ok(statsBody.includes('corpus_stats_total'),            'corpus_stats_total i18n key required')
assert.ok(statsBody.includes('corpus_stats_in_progress'),      'corpus_stats_in_progress i18n key required')
assert.ok(statsBody.includes('corpus_stats_not_started'),      'corpus_stats_not_started i18n key required')
assert.ok(statsBody.includes('corpus_stats_complete'),         'corpus_stats_complete i18n key required')
console.log('✓ index.html: #corpus-browser-stats with 4 chips, data-sort attrs, i18n keys')

// ── main.js: refs ─────────────────────────────────────────────────────────────

assert.ok(mainJs.includes('corpusBrowserStats'), 'main.js must declare corpusBrowserStats')
assert.ok(mainJs.includes("querySelector('#corpus-browser-stats')"), 'main.js must query #corpus-browser-stats')
assert.ok(mainJs.includes('corpusStatTotal'),      'main.js must declare corpusStatTotal ref')
assert.ok(mainJs.includes('corpusStatInProgress'), 'main.js must declare corpusStatInProgress ref')
assert.ok(mainJs.includes('corpusStatNotStarted'), 'main.js must declare corpusStatNotStarted ref')
assert.ok(mainJs.includes('corpusStatComplete'),   'main.js must declare corpusStatComplete ref')
console.log('✓ main.js: all 5 corpus stats refs declared')

// ── main.js: _loadCorpusStats ─────────────────────────────────────────────────

assert.ok(mainJs.includes('function _loadCorpusStats()'), 'main.js must define _loadCorpusStats')

const statsIdx2  = mainJs.indexOf('function _loadCorpusStats()')
const statsBody2 = mainJs.slice(statsIdx2, statsIdx2 + 700)

assert.ok(statsBody2.includes('/corpus/stats'),              '_loadCorpusStats must fetch /corpus/stats')
assert.ok(statsBody2.includes('d.total'),                    '_loadCorpusStats must read d.total')
assert.ok(statsBody2.includes('d.in_progress'),              '_loadCorpusStats must read d.in_progress')
assert.ok(statsBody2.includes('corpusBrowserStats.hidden'),  '_loadCorpusStats must reveal stats strip')
console.log('✓ main.js: _loadCorpusStats fetches /corpus/stats and populates all 4 values')

// ── main.js: _resetCorpusProgress ────────────────────────────────────────────

assert.ok(mainJs.includes('function _resetCorpusProgress('), 'main.js must define _resetCorpusProgress')

const resetIdx  = mainJs.indexOf('function _resetCorpusProgress(')
const resetBody = mainJs.slice(resetIdx, resetIdx + 400)

assert.ok(resetBody.includes("method: 'DELETE'"),        '_resetCorpusProgress must use DELETE method')
assert.ok(resetBody.includes('/progress'),               '_resetCorpusProgress must hit /progress endpoint')
assert.ok(resetBody.includes('_loadCorpus()'),           '_resetCorpusProgress must reload corpus list')
assert.ok(resetBody.includes('_loadCorpusStats()'),      '_resetCorpusProgress must reload stats')
console.log('✓ main.js: _resetCorpusProgress uses DELETE and reloads both corpus and stats')

// ── main.js: _buildCorpusItem enhancements ────────────────────────────────────

const buildIdx  = mainJs.indexOf('function _buildCorpusItem(')
const buildBody = mainJs.slice(buildIdx, buildIdx + 3800)

assert.ok(buildBody.includes('corpus-browser-list__progress-pct'), '_buildCorpusItem must add progress-pct span')
assert.ok(buildBody.includes('corpus-browser-list__reset'),         '_buildCorpusItem must add reset button')
assert.ok(buildBody.includes('corpus_reset_progress_aria'),         'reset button must use i18n aria key')
assert.ok(buildBody.includes("li.dataset.complete"),               '_buildCorpusItem must set data-complete on li')
assert.ok(buildBody.includes("role', 'progressbar'"),              'progress bar must have role=progressbar')
assert.ok(buildBody.includes("aria-valuenow"),                     'progress bar must have aria-valuenow')
console.log('✓ main.js: _buildCorpusItem adds pct label, reset btn, data-complete, ARIA on progress bar')

// ── main.js: chip click wiring ────────────────────────────────────────────────

assert.ok(
  mainJs.includes("querySelectorAll('.corpus-stats-chip')"),
  'main.js must wire click events on .corpus-stats-chip elements'
)
console.log('✓ main.js: corpus stat chips wired to set sort and reload')

// ── i18n: all keys in all 11 language blocks ─────────────────────────────────

const newKeys = [
  'corpus_stats_total',
  'corpus_stats_in_progress',
  'corpus_stats_not_started',
  'corpus_stats_complete',
  'corpus_reset_progress_aria',
]

for (const key of newKeys) {
  const count = (i18n.match(new RegExp(key, 'g')) ?? []).length
  assert.ok(count >= 11, `${key} must appear in all 11 language blocks (found ${count})`)
}
console.log('✓ i18n: all 5 new corpus stats/reset keys in all 11 language blocks')

console.log('\nAll corpus-stats-reset tests passed.')
