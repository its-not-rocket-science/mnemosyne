/**
 * detail-pane.test.mjs — DOM-level rendering tests for mnemosyne-detail-pane.
 *
 * Proves the detail pane Web Component renders correctly end-to-end:
 *   - type badge icon and label
 *   - title from canonical_form
 *   - explanation text
 *   - tab set for each depth level (subtle / learning / deep)
 *   - origins and related tabs when data is present
 *   - context panel with sentence text and highlighted phrase
 *   - hide() fires pane-close and sets inert
 *   - close button and study button events
 *   - match badge for non-canonical match types
 *   - tab click switches aria-selected state
 *
 * Uses linkedom for a lightweight browser-like DOM environment.
 * Run with: node frontend/tests/detail-pane.test.mjs
 */
import assert from 'node:assert/strict'
import { parseHTML } from 'linkedom'

// ── DOM environment setup — must precede component imports ────────────────────

const dom = parseHTML('<!doctype html><html><head></head><body></body></html>')
const { window, document, customElements, HTMLElement, Event, CustomEvent } = dom
Object.assign(globalThis, { window, document, customElements, HTMLElement, Event, CustomEvent })

// CSS.escape polyfill — used by text-panel internally; needed for i18n import chain
globalThis.CSS = {
  escape: s => s.replace(/([!"#$%&'()*+,./:;<=>?@[\\\]^`{|}~])/g, '\\$1'),
}
// localStorage stub — i18n uses it only in initUiLanguage() which tests never call;
// detail pane reads note keys from it in _wireEvents()
globalThis.localStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} }
// requestAnimationFrame stub — show() defers data-open and focus to the next frame;
// not executing the callback keeps tests synchronous without losing coverage
globalThis.requestAnimationFrame = () => {}
// Minimal navigator/location stubs — used only in the share-button click path
globalThis.navigator = {}
globalThis.location = { href: 'http://localhost/' }

await import('../components/mnemosyne-detail-pane.js')

// ── Fixtures ──────────────────────────────────────────────────────────────────

const VOCAB_LESSON = {
  id: 'ann-1',
  type: 'vocabulary',
  title: 'hablar',
  explanation: 'To speak.',
  examples: ['hablar'],
  fields: [{ label: 'definition', value: 'to speak' }],
  lesson_data: {
    canonical_form: 'hablar',
    matched_variant: 'hablar',
    match_type: 'exact',
  },
}

const IDIOM_LESSON = {
  id: 'ann-2',
  type: 'idiom',
  title: 'a la vez',
  explanation: 'At the same time.',
  examples: ['a la vez'],
  fields: [],
  lesson_data: {
    canonical_form: 'a la vez',
    matched_variant: 'a la vez',
    match_type: 'exact',
    origin: 'From Spanish idiom tradition.',
  },
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function makePane() {
  const el = document.createElement('mnemosyne-detail-pane')
  document.body.appendChild(el)
  return el
}

const sr = el => el.shadowRoot
const cleanUp = () => { document.body.innerHTML = '' }

// ── mnemosyne-detail-pane ─────────────────────────────────────────────────────

// 1. Type badge shows vocabulary icon (📗)
{
  const pane = makePane()
  pane.show({ lesson: VOCAB_LESSON, sentenceText: 'Me gusta hablar.', language: 'es', depth: 'deep' })
  const badge = sr(pane).querySelector('.pane__badge')
  assert.ok(badge !== null, '.pane__badge must be rendered')
  assert.ok(badge.textContent.includes('📗'),
    `.pane__badge must include 📗 for vocabulary type; got "${badge.textContent}"`)
  cleanUp()
  console.log('  ✓ vocabulary badge shows 📗 icon')
}

// 2. Title rendered from canonical_form
{
  const pane = makePane()
  pane.show({ lesson: VOCAB_LESSON, sentenceText: '', language: 'es', depth: 'deep' })
  const title = sr(pane).querySelector('.pane__title')
  assert.ok(title !== null, '.pane__title must be rendered')
  assert.equal(title.textContent, 'hablar', '.pane__title must show canonical_form')
  cleanUp()
  console.log('  ✓ title shows canonical_form')
}

// 3. Explanation text rendered from lesson.explanation
{
  const pane = makePane()
  pane.show({ lesson: VOCAB_LESSON, sentenceText: '', language: 'es', depth: 'deep' })
  const expl = sr(pane).querySelector('.pane__explanation')
  assert.ok(expl !== null, '.pane__explanation must be rendered')
  assert.equal(expl.textContent, 'To speak.', '.pane__explanation must show lesson.explanation verbatim')
  cleanUp()
  console.log('  ✓ explanation text rendered from lesson.explanation')
}

// 4. depth='subtle' → explanation tab only (1 tab total)
{
  const pane = makePane()
  pane.show({ lesson: VOCAB_LESSON, sentenceText: '', language: 'es', depth: 'subtle' })
  const tabs = sr(pane).querySelectorAll('[role="tab"]')
  assert.equal(tabs.length, 1, `subtle depth must render exactly 1 tab; got ${tabs.length}`)
  assert.equal(tabs[0].id, 'dp-tab-explanation', 'sole tab must be the explanation tab')
  cleanUp()
  console.log('  ✓ depth="subtle" renders only the explanation tab')
}

// 5. depth='learning' → explanation + context + practice (no origins without origin data)
{
  const pane = makePane()
  pane.show({ lesson: VOCAB_LESSON, sentenceText: 'hablar es fácil.', language: 'es', depth: 'learning' })
  const tabIds = Array.from(sr(pane).querySelectorAll('[role="tab"]')).map(t => t.id)
  assert.ok(tabIds.includes('dp-tab-explanation'), 'must have explanation tab at depth="learning"')
  assert.ok(tabIds.includes('dp-tab-context'),     'must have context tab at depth="learning"')
  assert.ok(tabIds.includes('dp-tab-practice'),    'must have practice tab at depth="learning"')
  assert.ok(!tabIds.includes('dp-tab-origins'),    'origins tab must not appear without origin data')
  cleanUp()
  console.log('  ✓ depth="learning" renders explanation, context, practice — no origins')
}

// 6. depth='deep' with lesson_data.origin → origins tab included
{
  const pane = makePane()
  pane.show({ lesson: IDIOM_LESSON, sentenceText: 'lo hace a la vez.', language: 'es', depth: 'deep' })
  const tabIds = Array.from(sr(pane).querySelectorAll('[role="tab"]')).map(t => t.id)
  assert.ok(tabIds.includes('dp-tab-origins'),
    'origins tab must appear when lesson_data.origin is set')
  cleanUp()
  console.log('  ✓ depth="deep" + origin data → origins tab rendered')
}

// 7. depth='deep' with variants (length > 1) → related tab included
{
  const withVariants = {
    ...VOCAB_LESSON,
    lesson_data: { ...VOCAB_LESSON.lesson_data, variants: ['hablar', 'hable'] },
  }
  const pane = makePane()
  pane.show({ lesson: withVariants, sentenceText: '', language: 'es', depth: 'deep' })
  const tabIds = Array.from(sr(pane).querySelectorAll('[role="tab"]')).map(t => t.id)
  assert.ok(tabIds.includes('dp-tab-related'),
    'related tab must appear when variants.length > 1')
  cleanUp()
  console.log('  ✓ depth="deep" + variants → related tab rendered')
}

// 8. Context panel rendered at depth='learning' with sentence text
{
  const pane = makePane()
  pane.show({
    lesson: VOCAB_LESSON,
    sentenceText: 'Me gusta hablar español.',
    language: 'es',
    depth: 'learning',
  })
  const ctx = sr(pane).querySelector('.pane__context-sentence')
  assert.ok(ctx !== null, '.pane__context-sentence must be rendered at depth="learning"')
  assert.ok(ctx.textContent.includes('hablar'),
    '.pane__context-sentence must contain sentence text')
  cleanUp()
  console.log('  ✓ context panel renders sentence text at depth="learning"')
}

// 9. Context panel highlights matched phrase with <mark class="context-highlight">
{
  const pane = makePane()
  pane.show({
    lesson: VOCAB_LESSON,
    sentenceText: 'Me gusta hablar español.',
    language: 'es',
    depth: 'learning',
  })
  const mark = sr(pane).querySelector('.pane__context-sentence .context-highlight')
  assert.ok(mark !== null,
    '<mark class="context-highlight"> must wrap matched phrase in context panel')
  assert.equal(mark.textContent.toLowerCase(), 'hablar',
    'highlighted text must match the canonical matched phrase')
  cleanUp()
  console.log('  ✓ context panel highlights matched phrase with <mark class="context-highlight">')
}

// 10. hide() fires pane-close event
{
  const pane = makePane()
  pane.show({ lesson: VOCAB_LESSON, sentenceText: '', language: 'es', depth: 'deep' })
  let fired = false
  pane.addEventListener('pane-close', () => { fired = true })
  pane.hide()
  assert.ok(fired, 'pane-close event must fire on hide()')
  cleanUp()
  console.log('  ✓ hide() fires pane-close event')
}

// 11. hide() sets inert attribute; show() removes it
{
  const pane = makePane()
  pane.show({ lesson: VOCAB_LESSON, sentenceText: '', language: 'es', depth: 'deep' })
  assert.ok(!pane.hasAttribute('inert'), 'inert must not be present after show()')
  pane.hide()
  assert.ok(pane.hasAttribute('inert'), 'inert must be set after hide()')
  cleanUp()
  console.log('  ✓ hide() sets inert; show() clears it')
}

// 12. Explanation panel has note textarea for user annotations
{
  const pane = makePane()
  pane.show({ lesson: VOCAB_LESSON, sentenceText: '', language: 'es', depth: 'deep' })
  const textarea = sr(pane).querySelector('.pane__note-input')
  assert.ok(textarea !== null, '.pane__note-input textarea must be rendered in explanation panel')
  cleanUp()
  console.log('  ✓ explanation panel has .pane__note-input textarea')
}

// 13. Footer study button rendered at all depths (including subtle)
{
  const pane = makePane()
  pane.show({ lesson: VOCAB_LESSON, sentenceText: '', language: 'es', depth: 'subtle' })
  const studyBtn = sr(pane).querySelector('footer .pane__study-btn')
  assert.ok(studyBtn !== null, 'footer .pane__study-btn must be rendered even at depth="subtle"')
  cleanUp()
  console.log('  ✓ footer study button rendered at depth="subtle"')
}

// 14. Close button click fires pane-close event (via shadow-root delegation)
{
  const pane = makePane()
  pane.show({ lesson: VOCAB_LESSON, sentenceText: '', language: 'es', depth: 'deep' })
  let fired = false
  pane.addEventListener('pane-close', () => { fired = true })
  sr(pane).querySelector('.pane__close').click()
  assert.ok(fired, 'pane-close must fire when close button is clicked')
  cleanUp()
  console.log('  ✓ close button click fires pane-close event')
}

// 15. Match badge shown for orthographic_variant with "variant" class modifier
{
  const nonCanon = {
    ...VOCAB_LESSON,
    lesson_data: {
      ...VOCAB_LESSON.lesson_data,
      match_type: 'orthographic_variant',
      match_type_note: 'Spelling variant.',
    },
  }
  const pane = makePane()
  pane.show({ lesson: nonCanon, sentenceText: '', language: 'es', depth: 'deep' })
  const badge = sr(pane).querySelector('.pane__match-badge')
  assert.ok(badge !== null, '.pane__match-badge must appear for orthographic_variant match type')
  assert.ok(badge.className.includes('variant'),
    `.pane__match-badge must carry "variant" class modifier; got "${badge.className}"`)
  cleanUp()
  console.log('  ✓ orthographic_variant renders .pane__match-badge--variant')
}

// 16. Tab click switches aria-selected state
{
  const pane = makePane()
  pane.show({ lesson: VOCAB_LESSON, sentenceText: 'hablar es fácil.', language: 'es', depth: 'learning' })
  const tabs = Array.from(sr(pane).querySelectorAll('[role="tab"]'))
  assert.ok(tabs.length >= 2, `need ≥2 tabs for switch test; got ${tabs.length}`)
  assert.equal(tabs[0].getAttribute('aria-selected'), 'true',  'first tab selected initially')
  assert.equal(tabs[1].getAttribute('aria-selected'), 'false', 'second tab unselected initially')
  tabs[1].click()
  assert.equal(tabs[0].getAttribute('aria-selected'), 'false', 'first tab deselected after click')
  assert.equal(tabs[1].getAttribute('aria-selected'), 'true',  'second tab selected after click')
  cleanUp()
  console.log('  ✓ tab click switches aria-selected between tabs')
}

// 17. Study button click fires pane-study event
{
  const pane = makePane()
  pane.show({ lesson: VOCAB_LESSON, sentenceText: '', language: 'es', depth: 'deep' })
  let fired = false
  pane.addEventListener('pane-study', () => { fired = true })
  sr(pane).querySelector('.pane__study-btn').click()
  assert.ok(fired, 'pane-study event must fire when study button is clicked')
  cleanUp()
  console.log('  ✓ study button fires pane-study event')
}

console.log('\nAll detail pane render tests passed.')
