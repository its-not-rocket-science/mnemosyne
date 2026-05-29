/**
 * annotation-tooltip.test.mjs — structural tests for annotation hover tooltip.
 *
 * Run with: node frontend/tests/annotation-tooltip.test.mjs
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

// ── HTML ──────────────────────────────────────────────────────────────────────

assert.ok(html.includes('id="annotation-tooltip"'), 'index.html must include #annotation-tooltip')
assert.ok(html.includes('role="tooltip"'), '#annotation-tooltip must have role=tooltip')
console.log('✓ HTML: #annotation-tooltip present with role=tooltip')

// ── main.js: DOM ref ──────────────────────────────────────────────────────────

assert.ok(mainJs.includes('annotationTooltip'), 'main.js must declare annotationTooltip')
assert.ok(
  mainJs.includes("querySelector('#annotation-tooltip')"),
  'main.js must query #annotation-tooltip'
)
console.log('✓ main.js: annotationTooltip DOM ref declared')

// ── mark creation stores data-label ──────────────────────────────────────────

assert.ok(
  mainJs.includes("mark.dataset.label     = item.label ?? ''"),
  'mark creation must store item.label as data-label'
)
console.log('✓ main.js: mark creation stores data-label')

// ── _showAnnotationTooltip function ──────────────────────────────────────────

assert.ok(mainJs.includes('function _showAnnotationTooltip('), 'main.js must define _showAnnotationTooltip')
const showIdx  = mainJs.indexOf('function _showAnnotationTooltip(')
const showBody = mainJs.slice(showIdx, showIdx + 1200)
assert.ok(showBody.includes('typeLabel'), '_showAnnotationTooltip must use typeLabel')
assert.ok(showBody.includes('dataset.label'), '_showAnnotationTooltip must read dataset.label')
assert.ok(showBody.includes('annotation-tooltip__type'), '_showAnnotationTooltip must create type chip')
assert.ok(showBody.includes('annotation-tooltip__label'), '_showAnnotationTooltip must create label element')
assert.ok(showBody.includes('removeAttribute'), '_showAnnotationTooltip must show the tooltip')
assert.ok(showBody.includes('getBoundingClientRect'), '_showAnnotationTooltip must position via getBoundingClientRect')
console.log('✓ main.js: _showAnnotationTooltip populates and positions tooltip')

// ── _hideAnnotationTooltip function ──────────────────────────────────────────

assert.ok(mainJs.includes('function _hideAnnotationTooltip('), 'main.js must define _hideAnnotationTooltip')
const hideIdx  = mainJs.indexOf('function _hideAnnotationTooltip(')
const hideBody = mainJs.slice(hideIdx, hideIdx + 200)
assert.ok(hideBody.includes("setAttribute('hidden'"), '_hideAnnotationTooltip must set hidden attr')
console.log('✓ main.js: _hideAnnotationTooltip hides tooltip')

// ── event delegation ─────────────────────────────────────────────────────────

assert.ok(mainJs.includes("results.addEventListener('mouseover'"), 'results must listen for mouseover')
assert.ok(mainJs.includes("results.addEventListener('mouseout'"), 'results must listen for mouseout')
assert.ok(mainJs.includes("results.addEventListener('focusin'"), 'results must listen for focusin')
assert.ok(mainJs.includes("results.addEventListener('focusout'"), 'results must listen for focusout')
console.log('✓ main.js: mouseover/mouseout/focusin/focusout delegation on results')

// ── Escape key dismissal ──────────────────────────────────────────────────────

assert.ok(
  mainJs.includes("e.key === 'Escape'") && mainJs.includes('_hideAnnotationTooltip'),
  'Escape key must dismiss tooltip'
)
console.log('✓ main.js: Escape key dismisses tooltip')

// ── CSS ───────────────────────────────────────────────────────────────────────

assert.ok(css.includes('#annotation-tooltip'), 'components.css must style #annotation-tooltip')
assert.ok(css.includes('.annotation-tooltip__type'), 'components.css must style .annotation-tooltip__type')
assert.ok(css.includes('.annotation-tooltip__label'), 'components.css must style .annotation-tooltip__label')
assert.ok(css.includes('#annotation-tooltip[hidden]'), 'components.css must hide tooltip when [hidden]')
console.log('✓ CSS: annotation tooltip styles defined')

// ── ::before suppressed ───────────────────────────────────────────────────────

const hoverBeforeIdx  = css.indexOf('.reader-annotation:hover::before')
const hoverBeforeBody = css.slice(hoverBeforeIdx, hoverBeforeIdx + 120)
assert.ok(hoverBeforeBody.includes('opacity: 0'), '::before hover opacity must be 0 (superseded by JS tooltip)')
console.log('✓ CSS: ::before hover opacity suppressed, JS tooltip is sole popover')

console.log('\nAll annotation-tooltip tests passed.')
