/**
 * review-quality-ui.test.mjs — structural tests for FSRS quality rating buttons.
 *
 * Run with: node frontend/tests/review-quality-ui.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT      = path.resolve(__dirname, '..')

const pane = readFileSync(path.join(ROOT, 'components', 'mnemosyne-review-pane.js'), 'utf8')

// ── Rating button structure ───────────────────────────────────────────────────

assert.ok(pane.includes('data-quality="1"'), 'rating button quality 1 (Again) must exist')
assert.ok(pane.includes('data-quality="2"'), 'rating button quality 2 (Hard) must exist')
assert.ok(pane.includes('data-quality="3"'), 'rating button quality 3 (Good) must exist')
assert.ok(pane.includes('data-quality="4"'), 'rating button quality 4 (Easy) must exist')
console.log('✓ rating buttons: all 4 qualities present')

// Each button has label + interval sublabel spans
assert.ok(pane.includes('class="rate__label"'),    'buttons must have .rate__label span')
assert.ok(pane.includes('class="rate__interval"'), 'buttons must have .rate__interval span')
assert.ok(
  (pane.match(/rate__interval/g) || []).length >= 4,
  'all 4 buttons must have .rate__interval span'
)
console.log('✓ rating buttons: .rate__label and .rate__interval spans in each button')

// Interval spans have aria-hidden (decorative)
const firstInterval = pane.indexOf('class="rate__interval"')
const surrounding   = pane.slice(firstInterval - 50, firstInterval + 80)
assert.ok(surrounding.includes('aria-hidden="true"'), '.rate__interval must be aria-hidden')
console.log('✓ rating buttons: interval sublabels are aria-hidden')

// ── 4-grade color system ──────────────────────────────────────────────────────

// Each quality has a distinct CSS rule
assert.ok(pane.includes('.btn--rate[data-quality="1"]'), 'CSS must define quality-1 color')
assert.ok(pane.includes('.btn--rate[data-quality="2"]'), 'CSS must define quality-2 color (amber)')
assert.ok(pane.includes('.btn--rate[data-quality="3"]'), 'CSS must define quality-3 color (green)')
assert.ok(pane.includes('.btn--rate[data-quality="4"]'), 'CSS must define quality-4 color (teal)')
console.log('✓ CSS: all 4 grade colors defined')

// Dark-theme overrides for grades 2, 3, 4
assert.ok(
  pane.includes('.btn--rate[data-quality="2"]') &&
  pane.match(/data-theme="dark"[\s\S]{1,200}data-quality="2"/),
  'CSS must have dark-theme override for quality 2'
)
assert.ok(
  pane.match(/data-theme="dark"[\s\S]{1,200}data-quality="3"/),
  'CSS must have dark-theme override for quality 3'
)
assert.ok(
  pane.match(/data-theme="dark"[\s\S]{1,200}data-quality="4"/),
  'CSS must have dark-theme override for quality 4'
)
console.log('✓ CSS: dark-theme overrides for grades 2–4')

// ── Schedule preview fetch ────────────────────────────────────────────────────

assert.ok(pane.includes('_fetchSchedulePreview'),    'must define _fetchSchedulePreview method')
assert.ok(pane.includes('schedule-preview'),         '_fetchSchedulePreview must call schedule-preview endpoint')
assert.ok(pane.includes('rate__interval'),           '_fetchSchedulePreview must update .rate__interval elements')
assert.ok(pane.includes('data.previews'),            '_fetchSchedulePreview must iterate data.previews')
console.log('✓ _fetchSchedulePreview: defined, fetches endpoint, updates sublabels')

// Called from _showRatings
const showRatingsDefIdx  = pane.indexOf('_showRatings() {')
const showRatingsBody    = pane.slice(showRatingsDefIdx, showRatingsDefIdx + 300)
assert.ok(
  showRatingsBody.includes('_fetchSchedulePreview'),
  '_showRatings must call _fetchSchedulePreview'
)
console.log('✓ _showRatings: calls _fetchSchedulePreview after revealing buttons')

// ── Keyboard shortcuts still wired ───────────────────────────────────────────

assert.ok(pane.includes("['1', '2', '3', '4']"), '1–4 keyboard shortcuts must still be wired')
assert.ok(pane.includes('aria-keyshortcuts="1"'),  'aria-keyshortcuts must be on quality-1 button')
assert.ok(pane.includes('aria-keyshortcuts="4"'),  'aria-keyshortcuts must be on quality-4 button')
console.log('✓ keyboard shortcuts: 1–4 still wired with aria-keyshortcuts')

// ── Forced-colors support ─────────────────────────────────────────────────────

assert.ok(
  pane.includes('forced-colors: active') && pane.includes('btn--rate[data-quality]'),
  'CSS must include forced-colors support for rating buttons'
)
console.log('✓ CSS: forced-colors support for rating buttons')

console.log('\nAll review-quality-ui tests passed.')
