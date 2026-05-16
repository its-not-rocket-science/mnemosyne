/**
 * recommended-reading-render.test.mjs — structural and behavioural tests for
 * the Next Up recommendation panel (recommended-reading.js).
 *
 * Pure functions (escapeHtml, normalizeMojibake, passageText, reasonFor) are
 * extracted via vm and tested against concrete inputs.  Panel HTML structure,
 * scroll thresholds, autonomous countdown, and the public API are verified via
 * source inspection — the same pattern as recommended-reading-language-guard.
 *
 * Run with: node frontend/tests/recommended-reading-render.test.mjs
 */
import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'

const source = fs.readFileSync(
  new URL('../js/recommended-reading.js', import.meta.url), 'utf8',
)

// ── Extract pure functions via vm ─────────────────────────────────────────────

const escapeMatch  = source.match(/function escapeHtml\(value\) \{[\s\S]*?\n\}/)
const mojiMatch    = source.match(/function normalizeMojibake\(text\) \{[\s\S]*?\n\}/)
const passageMatch = source.match(/function passageText\(item\) \{[\s\S]*?\n\}/)
const reasonMatch  = source.match(/function reasonFor\(item\) \{[\s\S]*?\n\}/)

if (!escapeMatch)   throw new Error('escapeHtml not found in source')
if (!mojiMatch)     throw new Error('normalizeMojibake not found in source')
if (!passageMatch)  throw new Error('passageText not found in source')
if (!reasonMatch)   throw new Error('reasonFor not found in source')

const ctx = {
  t: key => key,
  window: { mnemosyneDifficulty: null },
  result: {},
}
vm.createContext(ctx)
vm.runInContext(
  `${escapeMatch[0]}
   ${mojiMatch[0]}
   ${passageMatch[0]}
   ${reasonMatch[0]}
   result.escape  = escapeHtml
   result.moji    = normalizeMojibake
   result.passage = passageText
   result.reason  = reasonFor`,
  ctx,
)
const { escape: escapeHtml, moji: normalizeMojibake, passage: passageText, reason: reasonFor } = ctx.result

// ── escapeHtml ────────────────────────────────────────────────────────────────

// 1. All XSS-dangerous characters escaped correctly
assert.equal(escapeHtml('a & b'),    'a &amp; b',       '& → &amp;')
assert.equal(escapeHtml('<script>'), '&lt;script&gt;',  '< > → &lt; &gt;')
assert.equal(escapeHtml('"hello"'),  '&quot;hello&quot;', '" → &quot;')
assert.equal(escapeHtml("it's"),     "it&#039;s",       "' → &#039;")
console.log("  ✓ escapeHtml: & < > \" ' all escaped correctly")

// 2. Null/undefined → empty string (no TypeError thrown)
assert.equal(escapeHtml(null),      '', 'null → empty string')
assert.equal(escapeHtml(undefined), '', 'undefined → empty string')
console.log('  ✓ escapeHtml: null/undefined → empty string')

// ── normalizeMojibake ─────────────────────────────────────────────────────────

// 3. Curly quote sequences fixed
assert.ok(normalizeMojibake('“').includes('“'),
  'opening curly quote must pass through unchanged (sanity check)')
assert.ok(normalizeMojibake('‚Äú').includes('“'), '‚Äú → opening curly double-quote “')
assert.ok(normalizeMojibake('‚Äù').includes('”'), '‚Äù → closing curly double-quote ”')
assert.ok(normalizeMojibake('‚Äô').includes('’'), '‚Äô → curly apostrophe ’')
console.log('  ✓ normalizeMojibake: curly quote sequences corrected')

// 4. Em-dash and en-dash sequences fixed
assert.ok(normalizeMojibake('‚Äî').includes('—'), '‚Äî → em-dash —')
assert.ok(normalizeMojibake('‚Äì').includes('–'), '‚Äì → en-dash –')
console.log('  ✓ normalizeMojibake: em-dash and en-dash sequences corrected')

// 5. Clean text passes through unchanged
assert.equal(normalizeMojibake('Hola, mundo!'), 'Hola, mundo!')
assert.equal(normalizeMojibake(''), '')
console.log('  ✓ normalizeMojibake: clean text passes through unchanged')

// ── passageText ───────────────────────────────────────────────────────────────

// 6. Extracts from item.text (simple case)
assert.equal(passageText({ text: 'Hola mundo.' }), 'Hola mundo.')
console.log('  ✓ passageText: extracts text from item.text')

// 7. Joins passage[] array with space when item.passage exists
{
  const result = passageText({ passage: [{ text: 'First.' }, { text: 'Second.' }] })
  assert.ok(
    result.includes('First.') && result.includes('Second.'),
    `passageText must join passage[] array; got "${result}"`,
  )
}
console.log('  ✓ passageText: joins passage[] array with space')

// 8. Handles missing / null text without throwing
assert.equal(passageText({ text: null }), '')
assert.equal(passageText({}),             '')
console.log('  ✓ passageText: handles missing/null text gracefully')

// ── reasonFor ─────────────────────────────────────────────────────────────────

// 9. Default (no discriminating signals) → rec_near_level rationale key
{
  const r = reasonFor({ text: 'test' })
  assert.ok(r.includes('rec_near_level'),
    `default reason must include rec_near_level key; got "${r}"`)
}
console.log('  ✓ reasonFor: default rationale is rec_near_level')

// 10. Continuation items add rec_continues to rationale
{
  const r = reasonFor({ is_continuation: true })
  assert.ok(r.includes('rec_continues'),
    `continuation item must include rec_continues key; got "${r}"`)
}
console.log('  ✓ reasonFor: is_continuation → includes rec_continues')

// ── Panel HTML structure (source inspection) ──────────────────────────────────

// 11. Eyebrow references rec_next_up i18n key
assert.ok(source.includes("t('rec_next_up')"),
  "eyebrow element must use t('rec_next_up') for the 'Next up' label")
console.log("  ✓ eyebrow references t('rec_next_up')")

// 12. Featured card uses --chosen modifier to distinguish it from alternatives
assert.ok(source.includes('recommended-reading-card--chosen'),
  'featured card must carry recommended-reading-card--chosen class modifier')
console.log('  ✓ featured card has recommended-reading-card--chosen class')

// 13. Continue and Show-alternatives action buttons present in template
assert.ok(source.includes('rec-panel__continue'),   'continue button must be in panel template')
assert.ok(source.includes('rec-panel__toggle-alt'), 'show-alternatives button must be in panel template')
console.log('  ✓ continue and show-alternatives buttons present in template')

// 14. Alternatives list starts hidden with role="list" for screen readers
assert.ok(source.includes('hidden role="list"'),
  'alternatives list must start hidden and carry role="list"')
console.log('  ✓ alternatives list starts hidden with role="list"')

// 15. altExpanded toggle drives alternatives list show/hide
assert.ok(source.includes('altExpanded = !altExpanded'),
  'altExpanded must be toggled on expand/collapse click')
assert.ok(source.includes('altList.hidden = !altExpanded'),
  'altList.hidden must be derived from altExpanded state')
console.log('  ✓ altExpanded toggle drives alternatives list visibility')

// 16. dismiss() hides the panel by setting panel.hidden = true
assert.ok(source.includes('panel.hidden = true'),
  'dismiss() must set panel.hidden = true to hide the panel')
console.log('  ✓ dismiss() hides panel via panel.hidden = true')

// 17. Scroll thresholds: prefetch at 50 %, trigger at 70 %
assert.ok(source.includes('TRIGGER_PROGRESS = 0.7'),
  'scroll trigger threshold must be 0.7 (70 %)')
assert.ok(source.includes('PREFETCH_PROGRESS = 0.5'),
  'prefetch threshold must be 0.5 (50 %)')
console.log('  ✓ scroll trigger at 70 %, prefetch at 50 %')

// 18. Autonomous countdown: 4 s, conditional on autonomousEnabled, has pause control
assert.ok(source.includes('COUNTDOWN_MS = 4000'),
  'countdown duration must be 4000 ms')
assert.ok(source.includes('rec-panel__countdown'),
  'countdown element must be in panel template')
assert.ok(source.includes('autonomousEnabled ?'),
  'countdown section must be conditional on autonomousEnabled flag')
assert.ok(source.includes('rec-panel__pause'),
  'pause button must be present inside countdown section')
console.log('  ✓ autonomous countdown: 4 s, conditional on autonomousEnabled, has pause control')

// 19. Public API exposes window.mnemosyneRecommended.show()
assert.ok(source.includes('window.mnemosyneRecommended'),
  'public API object must be attached to window.mnemosyneRecommended')
assert.ok(source.includes('show()'),
  'public API must expose a show() method')
console.log('  ✓ public API window.mnemosyneRecommended.show() exposed')

// 20. Panel aria-labelledby points to eyebrow for screen-reader labelling
assert.ok(
  source.includes("setAttribute('aria-labelledby', 'rec-panel-eyebrow')"),
  'panel must call setAttribute aria-labelledby → rec-panel-eyebrow for accessible labelling',
)
console.log('  ✓ panel aria-labelledby points to rec-panel-eyebrow')

console.log('\nAll Next Up panel render tests passed.')
