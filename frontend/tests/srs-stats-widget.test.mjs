/**
 * srs-stats-widget.test.mjs — structural tests for the dashboard SRS stats bar.
 *
 * Run with: node frontend/tests/srs-stats-widget.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT      = path.resolve(__dirname, '..')

const html        = readFileSync(path.join(ROOT, 'index.html'), 'utf8')
const reviewJs    = readFileSync(path.join(ROOT, 'js', 'review-session.js'), 'utf8')
const reviewCss   = readFileSync(path.join(ROOT, 'css', 'review.css'), 'utf8')
const i18n        = readFileSync(path.join(ROOT, 'js', 'i18n.js'), 'utf8')

// ── HTML structure ────────────────────────────────────────────────────────────

assert.ok(html.includes('id="srs-stats-bar"'),  'index.html must have #srs-stats-bar')
assert.ok(html.includes('id="stat-due"'),        'index.html must have #stat-due')
assert.ok(html.includes('id="stat-streak"'),     'index.html must have #stat-streak')
assert.ok(html.includes('id="stat-mastered"'),   'index.html must have #stat-mastered')
assert.ok(html.includes('id="stat-today"'),      'index.html must have #stat-today')
console.log('✓ HTML: all stat tile elements present')

// srs-stats-bar is initially hidden
const barStart = html.indexOf('id="srs-stats-bar"')
const barEl    = html.slice(barStart - 60, html.indexOf('>', barStart) + 1)
assert.ok(barEl.includes('hidden'), '#srs-stats-bar must start hidden')
console.log('✓ HTML: #srs-stats-bar starts hidden')

// Uses <dl> for semantic term/description pairing
assert.ok(html.includes('<dl class="srs-stats">'), 'stats must use <dl> for semantics')
assert.ok(html.includes('<dt class="srs-stat__label"'), 'labels must use <dt>')
assert.ok(html.includes('<dd class="srs-stat__value"'), 'values must use <dd>')
console.log('✓ HTML: semantic <dl>/<dt>/<dd> structure')

// i18n attributes
assert.ok(html.includes('data-i18n="stats_due"'),      'Due label must use data-i18n')
assert.ok(html.includes('data-i18n="stats_streak"'),   'Streak label must use data-i18n')
assert.ok(html.includes('data-i18n="stats_mastered"'), 'Mastered label must use data-i18n')
assert.ok(html.includes('data-i18n="stats_today"'),    'Today label must use data-i18n')
console.log('✓ HTML: i18n attributes on all stat labels')

// ── i18n keys in all 11 languages ────────────────────────────────────────────

const statsKeys = ['stats_due', 'stats_streak', 'stats_mastered', 'stats_today']
for (const key of statsKeys) {
  const count = (i18n.match(new RegExp(key, 'g')) || []).length
  assert.ok(count >= 11, `i18n.js must define ${key} in all 11 language blocks (found ${count})`)
}
console.log('✓ i18n: stats keys present in all 11 language blocks')

// ── review-session.js wiring ──────────────────────────────────────────────────

assert.ok(reviewJs.includes('refreshStats'),        'review-session.js must define refreshStats')
assert.ok(reviewJs.includes('stat-due'),            'refreshStats must reference stat-due element')
assert.ok(reviewJs.includes('stat-streak'),         'refreshStats must reference stat-streak element')
assert.ok(reviewJs.includes('stat-mastered'),       'refreshStats must reference stat-mastered element')
assert.ok(reviewJs.includes('stat-today'),          'refreshStats must reference stat-today element')
assert.ok(
  reviewJs.includes('/review/sentence-items/stats') && reviewJs.includes('/metrics'),
  'refreshStats must fetch both sentence-items/stats and /metrics'
)
assert.ok(reviewJs.includes('Promise.all'), 'refreshStats must use Promise.all for parallel fetches')
console.log('✓ review-session.js: refreshStats wired with parallel fetches')

// Called initially and on key events
assert.ok(reviewJs.includes('refreshStats()'), 'refreshStats must be called on init')
assert.ok(
  reviewJs.includes("'review-session-end'") && reviewJs.match(/review-session-end[\s\S]{1,300}refreshStats/),
  'refreshStats must be called on review-session-end'
)
assert.ok(
  reviewJs.includes("'review-item-rated'") && reviewJs.match(/review-item-rated[\s\S]{1,300}refreshStats/),
  'refreshStats must be called on review-item-rated'
)
console.log('✓ review-session.js: refreshStats called on init, session-end, item-rated')

// srs-stats-bar shown after fetch
assert.ok(reviewJs.includes("statsBar?.removeAttribute('hidden')"), 'statsBar must be shown after successful fetch')
console.log('✓ review-session.js: stats bar revealed after fetch')

// ── CSS ───────────────────────────────────────────────────────────────────────

assert.ok(reviewCss.includes('.srs-stats-bar'),    'review.css must define .srs-stats-bar')
assert.ok(reviewCss.includes('.srs-stats'),        'review.css must define .srs-stats')
assert.ok(reviewCss.includes('.srs-stat'),         'review.css must define .srs-stat')
assert.ok(reviewCss.includes('.srs-stat__label'),  'review.css must define .srs-stat__label')
assert.ok(reviewCss.includes('.srs-stat__value'),  'review.css must define .srs-stat__value')
console.log('✓ CSS: all .srs-stat* classes defined')

// Forced-colors support
assert.ok(
  reviewCss.includes('forced-colors') && reviewCss.includes('.srs-stat'),
  'review.css must include forced-colors support for srs-stat'
)
console.log('✓ CSS: forced-colors support present')

console.log('\nAll srs-stats-widget tests passed.')
