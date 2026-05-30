/**
 * review-mastery-animation.test.mjs — structural tests for mastery bar animation
 * and next-interval hint display after rating.
 *
 * Run with: node frontend/tests/review-mastery-animation.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT      = path.resolve(__dirname, '..')

const pane = readFileSync(path.join(ROOT, 'components', 'mnemosyne-review-pane.js'), 'utf8')

// ── HTML structure ────────────────────────────────────────────────────────────

assert.ok(pane.includes('id="mastery-bar"'), 'mastery-bar div must have id="mastery-bar"')
assert.ok(pane.includes('id="next-interval"'), 'next-interval element must have id="next-interval"')
assert.ok(
  pane.includes('class="next-interval"') && pane.includes('aria-live="polite"'),
  'next-interval must have class and aria-live="polite"'
)

// next-interval starts hidden
const niIdx = pane.indexOf('id="next-interval"')
const niEl  = pane.slice(niIdx - 40, niIdx + 80)
assert.ok(niEl.includes('hidden'), 'next-interval must start hidden')
console.log('✓ HTML: mastery-bar id, next-interval element present and hidden by default')

// ── _rate() updates mastery bar ───────────────────────────────────────────────

const rateIdx  = pane.indexOf('async _rate(')
const rateBody = pane.slice(rateIdx, rateIdx + 2200)

assert.ok(rateBody.includes("getElementById('mastery-bar')"), '_rate must look up mastery-bar by id')
assert.ok(rateBody.includes('.mastery-bar__fill'), '_rate must target mastery-bar__fill')
assert.ok(rateBody.includes("'inline-size'"), '_rate must set inline-size on mastery fill')
assert.ok(rateBody.includes('mastery_score'), '_rate must use result.mastery_score for new percentage')
console.log('✓ _rate: mastery bar animated to new mastery score')

// ── _rate() shows next-interval hint ─────────────────────────────────────────

assert.ok(rateBody.includes("getElementById('next-interval')"), '_rate must look up next-interval element')
assert.ok(rateBody.includes('next_interval_days'), '_rate must use result.next_interval_days')
assert.ok(rateBody.includes('_fmtDays'), '_rate must call _fmtDays to format the interval')
assert.ok(
  rateBody.includes("removeAttribute('hidden')"),
  '_rate must unhide next-interval element after rating'
)
console.log('✓ _rate: next-interval hint shown with formatted days')

// ── _animationPause() ────────────────────────────────────────────────────────

assert.ok(pane.includes('function _animationPause'), '_animationPause helper must be defined')
assert.ok(pane.includes('prefers-reduced-motion'), '_animationPause must check prefers-reduced-motion')
assert.ok(pane.includes('_animationPause()'), '_rate must await _animationPause()')

// Short delay for reduced-motion
const pauseIdx  = pane.indexOf('function _animationPause')
const pauseBody = pane.slice(pauseIdx, pauseIdx + 200)
assert.ok(
  pauseBody.match(/\b(80|100|120)\b/),
  '_animationPause must use a short delay (≤120ms) for reduced-motion users'
)
console.log('✓ _animationPause: defined, checks reduced-motion, used in _rate')

// ── _fmtDays() ───────────────────────────────────────────────────────────────

assert.ok(pane.includes('function _fmtDays'), '_fmtDays helper must be defined')

const fmtIdx  = pane.indexOf('function _fmtDays')
const fmtBody = pane.slice(fmtIdx, fmtIdx + 200)
assert.ok(fmtBody.includes("'d'") || fmtBody.includes('`${days}d`'), '_fmtDays must format days')
assert.ok(fmtBody.includes("'w'") || fmtBody.includes('`${w}w`'), '_fmtDays must format weeks')
console.log('✓ _fmtDays: defined, formats days and weeks')

// ── CSS ───────────────────────────────────────────────────────────────────────

assert.ok(pane.includes('.next-interval {'), 'CSS must define .next-interval')
assert.ok(pane.includes('.next-interval[hidden]'), 'CSS must define .next-interval[hidden]')
assert.ok(
  pane.match(/\.next-interval[\s\S]{1,200}transition/),
  '.next-interval must have a transition (fade)'
)
assert.ok(
  pane.match(/prefers-reduced-motion[\s\S]{1,200}next-interval/),
  'CSS must disable .next-interval transition under reduced-motion'
)
console.log('✓ CSS: .next-interval styles defined with transition and reduced-motion support')

console.log('\nAll review-mastery-animation tests passed.')
