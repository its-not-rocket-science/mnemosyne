/**
 * minimap-jump.test.mjs — structural tests for minimap click-to-jump.
 *
 * Run with: node frontend/tests/minimap-jump.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT      = path.resolve(__dirname, '..')

// Annotation density minimap lives in js/modes/lesson.js after the main.js
// split (Session 1 of the frontend refactor).
const mainJs = readFileSync(path.join(ROOT, 'js', 'modes', 'lesson.js'), 'utf8')
const css    = readFileSync(path.join(ROOT, 'css', 'components.css'), 'utf8')

// ── buildMinimap creates button elements ──────────────────────────────────────

const minimapIdx  = mainJs.indexOf('function buildMinimap(')
const minimapBody = mainJs.slice(minimapIdx, minimapIdx + 1600)

assert.ok(minimapBody.includes("createElement('button')"), 'buildMinimap must create button elements')
assert.ok(minimapBody.includes("tick.type      = 'button'"), 'tick must have type=button')
console.log('✓ buildMinimap: creates <button type="button"> ticks')

// ── aria-label set on each tick ───────────────────────────────────────────────

assert.ok(minimapBody.includes('aria-label'), 'tick must have aria-label')
assert.ok(minimapBody.includes('setAttribute'), 'aria-label set via setAttribute')
console.log('✓ buildMinimap: aria-label set on each tick')

// ── click handler scrolls and flashes ────────────────────────────────────────

assert.ok(minimapBody.includes('scrollIntoView'), 'click handler must call scrollIntoView')
assert.ok(minimapBody.includes("behavior: 'smooth'"), 'scrollIntoView must use smooth behavior')
assert.ok(minimapBody.includes('reader-annotation--jump-flash'), 'click handler must add jump-flash class')
assert.ok(minimapBody.includes('setTimeout'), 'jump-flash must be removed via setTimeout')
console.log('✓ buildMinimap: click scrolls to mark and adds/removes jump-flash class')

// ── CSS: minimap is interactive ───────────────────────────────────────────────

assert.ok(css.includes('pointer-events: auto'), '.annotation-minimap must have pointer-events: auto')
assert.ok(css.includes('annotation-minimap__tick'), '.annotation-minimap__tick defined in CSS')
assert.ok(css.includes('cursor: pointer'), 'tick must have cursor: pointer')
console.log('✓ CSS: minimap pointer-events auto, tick cursor pointer')

// ── CSS: jump-flash animation defined ────────────────────────────────────────

assert.ok(css.includes('annotation-jump-flash'), '@keyframes annotation-jump-flash defined')
assert.ok(css.includes('reader-annotation--jump-flash'), '.reader-annotation--jump-flash class defined')
console.log('✓ CSS: jump-flash animation defined')

console.log('\nAll minimap-jump tests passed.')
