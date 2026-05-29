/**
 * review-context.test.mjs — structural tests for sentence review source context.
 *
 * Run with: node frontend/tests/review-context.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT      = path.resolve(__dirname, '..')

const reviewPane = readFileSync(path.join(ROOT, 'components', 'mnemosyne-review-pane.js'), 'utf8')

// ── <details> context block in card HTML ──────────────────────────────────────

assert.ok(
  reviewPane.includes('class="card__context"'),
  'card HTML must include card__context details element'
)
assert.ok(
  reviewPane.includes('id="context-details"'),
  'card HTML must include context-details id'
)
assert.ok(
  reviewPane.includes('class="card__context-summary"'),
  'details must have card__context-summary summary element'
)
assert.ok(
  reviewPane.includes('id="context-body"'),
  'details must have context-body div'
)
assert.ok(
  reviewPane.includes('aria-busy="true"'),
  'context-body must start with aria-busy=true'
)
console.log('✓ HTML: context <details> block present with correct structure')

// ── _wireContext method ────────────────────────────────────────────────────────

assert.ok(reviewPane.includes('_wireContext'), '_wireContext method must be defined')
assert.ok(
  reviewPane.includes("getElementById('context-details')"),
  '_wireContext must look up context-details element'
)
assert.ok(
  reviewPane.includes("'toggle'"),
  '_wireContext must listen for toggle event'
)
assert.ok(
  reviewPane.includes('once: true'),
  '_wireContext must use { once: true } to avoid duplicate loads'
)
console.log('✓ _wireContext: toggle listener registered once')

// ── _loadContext method ───────────────────────────────────────────────────────

assert.ok(reviewPane.includes('_loadContext'), '_loadContext method must be defined')
assert.ok(
  reviewPane.includes('/review/sentence-items/'),
  '_loadContext must fetch context endpoint'
)
assert.ok(
  reviewPane.includes('/context'),
  '_loadContext endpoint path must include /context'
)
assert.ok(
  reviewPane.includes('ctx.before'),
  '_loadContext must render before sentences'
)
assert.ok(
  reviewPane.includes('ctx.after'),
  '_loadContext must render after sentences'
)
assert.ok(
  reviewPane.includes('ctx.target'),
  '_loadContext must render target sentence'
)
assert.ok(
  reviewPane.includes('ctx.source_title'),
  '_loadContext must conditionally render source_title'
)
console.log('✓ _loadContext: fetches context and renders before/target/after/source_title')

// ── Context CSS classes ───────────────────────────────────────────────────────

const CSS_CLASSES = [
  'context-sent--before',
  'context-sent--after',
  'context-sent--target',
  'context-source',
  'card__context-loading',
]

for (const cls of CSS_CLASSES) {
  assert.ok(reviewPane.includes(cls), `mnemosyne-review-pane.js must reference CSS class ${cls}`)
}
console.log('✓ CSS: context sentence classes referenced')

// ── aria-current on target sentence ──────────────────────────────────────────

assert.ok(
  reviewPane.includes("setAttribute('aria-current', 'true')"),
  'target sentence must have aria-current=true'
)
console.log('✓ Accessibility: target sentence has aria-current=true')

// ── Error state ───────────────────────────────────────────────────────────────

assert.ok(
  reviewPane.includes('Context unavailable.'),
  '_loadContext must show error message when fetch fails'
)
console.log('✓ Error state: context unavailable message shown on failure')

// ── _wireContext called from _renderCard ──────────────────────────────────────

assert.ok(
  reviewPane.includes('_wireContext(item.id)'),
  '_renderCard must call _wireContext(item.id) to wire up the context panel'
)
console.log('✓ _renderCard: calls _wireContext for each card')

console.log('\nAll review-context tests passed.')
