/**
 * reading-history.test.mjs — structural tests for reading history / resume.
 *
 * Run with: node frontend/tests/reading-history.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT      = path.resolve(__dirname, '..')

const html   = readFileSync(path.join(ROOT, 'index.html'), 'utf8')
const mainJs = readFileSync(path.join(ROOT, 'js', 'main.js'), 'utf8')
const css    = readFileSync(path.join(ROOT, 'css', 'components.css'), 'utf8')
const i18n   = readFileSync(path.join(ROOT, 'js', 'i18n.js'), 'utf8')

// ── HTML ──────────────────────────────────────────────────────────────────────

assert.ok(html.includes('id="reading-history"'), 'index.html must include #reading-history section')
assert.ok(html.includes('id="reading-history-list"'), 'index.html must include #reading-history-list')
assert.ok(html.includes('data-i18n="rec_continue_reading"'), '#reading-history heading must use rec_continue_reading i18n')
console.log('✓ HTML: #reading-history section present with list and i18n heading')

// ── main.js: DOM refs ─────────────────────────────────────────────────────────

assert.ok(mainJs.includes('readingHistoryEl'), 'main.js must declare readingHistoryEl')
assert.ok(mainJs.includes('readingHistoryList'), 'main.js must declare readingHistoryList')
assert.ok(
  mainJs.includes("querySelector('#reading-history')"),
  'main.js must query #reading-history'
)
console.log('✓ main.js: readingHistoryEl and readingHistoryList refs declared')

// ── _loadSource accepts resumeAt ──────────────────────────────────────────────

assert.ok(
  mainJs.includes('async function _loadSource(sourceId, language, resumeAt = 0)'),
  '_loadSource must accept resumeAt param with default 0'
)
const loadIdx  = mainJs.indexOf('async function _loadSource(sourceId, language, resumeAt = 0)')
const loadBody = mainJs.slice(loadIdx, loadIdx + 1800)
assert.ok(loadBody.includes('scrollIntoView'), '_loadSource must scroll to resumeAt sentence on resume')
console.log('✓ main.js: _loadSource accepts resumeAt and scrolls to position')

// ── _fetchReadingHistory function ─────────────────────────────────────────────

assert.ok(mainJs.includes('async function _fetchReadingHistory('), 'main.js must define _fetchReadingHistory')
const fetchIdx  = mainJs.indexOf('async function _fetchReadingHistory(')
const fetchBody = mainJs.slice(fetchIdx, fetchIdx + 400)
assert.ok(fetchBody.includes('/reading?limit=3'), '_fetchReadingHistory must call /reading?limit=3')
assert.ok(fetchBody.includes('_renderReadingHistory'), '_fetchReadingHistory must call _renderReadingHistory on success')
console.log('✓ main.js: _fetchReadingHistory fetches /reading and renders on success')

// ── _renderReadingHistory function ────────────────────────────────────────────

assert.ok(mainJs.includes('function _renderReadingHistory('), 'main.js must define _renderReadingHistory')
const renderIdx  = mainJs.indexOf('function _renderReadingHistory(')
const renderBody = mainJs.slice(renderIdx, renderIdx + 3000)
assert.ok(renderBody.includes('completion_fraction'), '_renderReadingHistory must use completion_fraction')
assert.ok(renderBody.includes('reading-history__bar'), '_renderReadingHistory must create bar element')
assert.ok(renderBody.includes('reading_resume_btn'), '_renderReadingHistory must use reading_resume_btn i18n key')
assert.ok(renderBody.includes('_loadSource'), '_renderReadingHistory resume button must call _loadSource')
assert.ok(renderBody.includes('next_position'), '_renderReadingHistory must pass next_position to _loadSource')
console.log('✓ main.js: _renderReadingHistory builds cards with progress bar and resume button')

// ── _relativeTime function ────────────────────────────────────────────────────

assert.ok(mainJs.includes('function _relativeTime('), 'main.js must define _relativeTime')
assert.ok(mainJs.includes('RelativeTimeFormat'), '_relativeTime must use Intl.RelativeTimeFormat')
console.log('✓ main.js: _relativeTime uses Intl.RelativeTimeFormat')

// ── wired on changeLessonBtn and startup ──────────────────────────────────────

assert.ok(
  mainJs.includes("changeLessonBtn?.addEventListener('click', _fetchReadingHistory)"),
  'changeLessonBtn must trigger _fetchReadingHistory'
)
assert.ok(
  mainJs.includes('_fetchReadingHistory()'),
  '_fetchReadingHistory called on startup'
)
console.log('✓ main.js: _fetchReadingHistory wired on changeLessonBtn and startup')

// ── CSS ───────────────────────────────────────────────────────────────────────

assert.ok(css.includes('.reading-history__item'), 'components.css must style .reading-history__item')
assert.ok(css.includes('.reading-history__bar'), 'components.css must style .reading-history__bar')
assert.ok(css.includes('.reading-history__bar-wrap'), 'components.css must style .reading-history__bar-wrap')
assert.ok(css.includes('.reading-history__footer'), 'components.css must style .reading-history__footer')
assert.ok(css.includes('.reading-history[hidden]'), 'reading-history must be hidden when [hidden] attr set')
console.log('✓ CSS: reading history styles defined')

// ── i18n ──────────────────────────────────────────────────────────────────────

assert.ok(i18n.includes('reading_resume_btn'), 'i18n must define reading_resume_btn')
assert.ok(
  (i18n.match(/reading_resume_btn/g) ?? []).length >= 11,
  'reading_resume_btn must appear in all 11 language blocks'
)
console.log('✓ i18n: reading_resume_btn in all 11 language blocks')

console.log('\nAll reading-history tests passed.')
