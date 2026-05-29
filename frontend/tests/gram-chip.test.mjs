/**
 * gram-chip.test.mjs — structural tests for clickable grammar tag chips
 * in the detail pane explanation tab.
 *
 * Run with: node frontend/tests/gram-chip.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT      = path.resolve(__dirname, '..')

const pane = readFileSync(path.join(ROOT, 'components', 'mnemosyne-detail-pane.js'), 'utf8')

// ── Chip HTML builder ─────────────────────────────────────────────────────────

assert.ok(
  pane.includes('gramChipsHtml'),
  '_htmlExplanationPanel must build gramChipsHtml from morphology_axes'
)
assert.ok(
  pane.includes('pane__gram-chip'),
  'gram chips must use class pane__gram-chip'
)
assert.ok(
  pane.includes('value_concept_id || ax.axis_concept_id'),
  'chips must use value_concept_id with fallback to axis_concept_id'
)
console.log('✓ _htmlExplanationPanel: gramChipsHtml built from morphology_axes')

// ── Chips rendered in explanation panel ──────────────────────────────────────

assert.ok(
  pane.includes('pane__gram-chips'),
  'explanation panel must include a .pane__gram-chips container'
)

// Verify chips container is placed inside the explanation panel HTML
const explIdx  = pane.indexOf('_htmlExplanationPanel(lesson, ld, matchedVariant, depthIdx = 2)')
const explBody = pane.slice(explIdx, explIdx + 5000)
assert.ok(
  explBody.includes('pane__gram-chips'),
  'pane__gram-chips container must be inside _htmlExplanationPanel output'
)
console.log('✓ _htmlExplanationPanel: .pane__gram-chips container rendered')

// ── Chips reuse concept-help click delegation ─────────────────────────────────

assert.ok(
  pane.includes('"pane__concept-help pane__gram-chip"'),
  'gram chips must carry pane__concept-help class to reuse existing click delegation'
)
console.log('✓ gram chips reuse .pane__concept-help click delegation')

// ── CSS defined in _styles() ──────────────────────────────────────────────────

assert.ok(
  pane.includes('.pane__gram-chip {'),
  '_styles must define .pane__gram-chip'
)
assert.ok(
  pane.includes('.pane__gram-chips {'),
  '_styles must define .pane__gram-chips container'
)
assert.ok(
  pane.includes('flex-wrap: wrap'),
  '.pane__gram-chips must use flex-wrap: wrap'
)
assert.ok(
  pane.includes('.pane__gram-chip:hover'),
  '_styles must define hover state for .pane__gram-chip'
)
console.log('✓ _styles: .pane__gram-chips and .pane__gram-chip CSS defined')

// ── Forced-colors support ─────────────────────────────────────────────────────

assert.ok(
  pane.includes('forced-colors') && pane.includes('.pane__gram-chip'),
  '_styles must include a forced-colors rule for .pane__gram-chip'
)
console.log('✓ _styles: forced-colors support for .pane__gram-chip')

// ── Axis concept fallback ─────────────────────────────────────────────────────

assert.ok(
  pane.includes('ax.axis_concept_id'),
  'chips must reference ax.axis_concept_id as fallback'
)
assert.ok(
  pane.includes('ax.label || ax.value || ax.axis'),
  'chip label must use ax.label with fallbacks to ax.value and ax.axis'
)
console.log('✓ gram chip label uses ax.label → ax.value → ax.axis fallback chain')

console.log('\nAll gram-chip tests passed.')
