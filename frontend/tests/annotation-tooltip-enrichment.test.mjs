/**
 * annotation-tooltip-enrichment.test.mjs — structural tests for gloss and
 * CEFR enrichment of the annotation hover tooltip.
 *
 * Run with: node frontend/tests/annotation-tooltip-enrichment.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT      = path.resolve(__dirname, '..')

const mainJs = readFileSync(path.join(ROOT, 'js', 'main.js'), 'utf8')
const css    = readFileSync(path.join(ROOT, 'css', 'components.css'), 'utf8')

// ── buildAnnotatedText stores gloss and cefrLevel in dataset ──────────────────
// Search the full file (code is deep inside the function body).

assert.ok(
  mainJs.includes('lesson_data?.gloss') || mainJs.includes("lesson_data?.['gloss']"),
  'main.js must read lesson_data.gloss for tooltip enrichment'
)
assert.ok(
  mainJs.includes('lesson_data?.translation') || mainJs.includes("lesson_data?.['translation']"),
  'main.js must check lesson_data.translation as gloss fallback'
)
assert.ok(
  mainJs.includes('mark.dataset.gloss'),
  'main.js must store gloss in mark.dataset.gloss'
)
assert.ok(
  mainJs.includes('lesson_data?.cefr_level') || mainJs.includes("lesson_data?.['cefr_level']"),
  'main.js must read lesson_data.cefr_level'
)
assert.ok(
  mainJs.includes('mark.dataset.cefrLevel'),
  'main.js must store cefr level in mark.dataset.cefrLevel'
)

// Verify these appear inside buildAnnotatedText (not elsewhere)
const buildIdx  = mainJs.indexOf('function buildAnnotatedText(')
const buildEnd  = mainJs.indexOf('\nfunction ', buildIdx + 1)
const buildBody = mainJs.slice(buildIdx, buildEnd)
assert.ok(buildBody.includes('mark.dataset.gloss'),     'gloss dataset assignment must be inside buildAnnotatedText')
assert.ok(buildBody.includes('mark.dataset.cefrLevel'), 'cefrLevel dataset assignment must be inside buildAnnotatedText')
console.log('✓ buildAnnotatedText: stores gloss (with translation fallback) and cefrLevel in dataset')

// ── _showAnnotationTooltip reads new fields ───────────────────────────────────

const tooltipFnIdx  = mainJs.indexOf('function _showAnnotationTooltip(mark)')
const tooltipFnBody = mainJs.slice(tooltipFnIdx, tooltipFnIdx + 1300)

assert.ok(
  tooltipFnBody.includes("mark.dataset.gloss"),
  '_showAnnotationTooltip must read mark.dataset.gloss'
)
assert.ok(
  tooltipFnBody.includes("mark.dataset.cefrLevel"),
  '_showAnnotationTooltip must read mark.dataset.cefrLevel'
)
assert.ok(
  tooltipFnBody.includes("annotation-tooltip__gloss"),
  '_showAnnotationTooltip must create .annotation-tooltip__gloss element'
)
assert.ok(
  tooltipFnBody.includes("annotation-tooltip__cefr"),
  '_showAnnotationTooltip must create .annotation-tooltip__cefr element'
)
assert.ok(
  tooltipFnBody.includes('dataset.cefr') || tooltipFnBody.includes("['cefr']"),
  '_showAnnotationTooltip must set data-cefr on the CEFR badge for color-coding'
)
console.log('✓ _showAnnotationTooltip: reads gloss + cefrLevel, creates enriched elements')

// ── CSS: new tooltip element styles defined ───────────────────────────────────

assert.ok(css.includes('.annotation-tooltip__gloss'), 'components.css must define .annotation-tooltip__gloss')
assert.ok(css.includes('.annotation-tooltip__cefr'),  'components.css must define .annotation-tooltip__cefr')
assert.ok(css.includes('.annotation-tooltip__header'), 'components.css must define .annotation-tooltip__header')
assert.ok(css.includes('[data-cefr="A1"]'), 'components.css must define A1 color variant for cefr badge')
assert.ok(css.includes('[data-cefr="B1"]'), 'components.css must define B1 color variant for cefr badge')
assert.ok(css.includes('[data-cefr="C1"]'), 'components.css must define C1 color variant for cefr badge')
console.log('✓ CSS: .annotation-tooltip__gloss, __cefr, __header defined with CEFR color variants')

console.log('\nAll annotation-tooltip-enrichment tests passed.')
