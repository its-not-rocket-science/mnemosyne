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

// 18. Field with both concept_id and value_concept_id renders two separate help buttons
{
  const withConcept = {
    ...VOCAB_LESSON,
    fields: [
      { label: 'Part of speech', value: 'Noun', concept_id: 'axis.part_of_speech', value_concept_id: 'pos.noun' },
      { label: 'definition', value: 'to speak' },
    ],
  }
  const pane = makePane()
  pane.show({ lesson: withConcept, sentenceText: '', language: 'es', depth: 'deep' })
  const helpBtns = sr(pane).querySelectorAll('.pane__concept-help')
  assert.equal(helpBtns.length, 2,
    'two .pane__concept-help buttons must appear when both concept_id and value_concept_id present')
  const labelBtn = sr(pane).querySelector('dt .pane__concept-help')
  const valueBtn = sr(pane).querySelector('dd .pane__concept-help')
  assert.ok(labelBtn !== null, 'label help button must be inside <dt>')
  assert.ok(valueBtn !== null, 'value help button must be inside <dd>')
  assert.equal(labelBtn.dataset.conceptId, 'axis.part_of_speech',
    'label help button must use concept_id (axis concept)')
  assert.equal(valueBtn.dataset.conceptId, 'pos.noun',
    'value help button must use value_concept_id (value concept)')
  cleanUp()
  console.log('  ✓ field with both concept IDs renders separate label and value help buttons')
}

// 19. Field with only concept_id renders one label help button, no value button
{
  const labelOnly = {
    ...VOCAB_LESSON,
    fields: [{ label: 'Lemma', value: 'hablar', concept_id: 'axis.lemma' }],
  }
  const pane = makePane()
  pane.show({ lesson: labelOnly, sentenceText: '', language: 'es', depth: 'deep' })
  const labelBtn = sr(pane).querySelector('dt .pane__concept-help')
  const valueBtn = sr(pane).querySelector('dd .pane__concept-help')
  assert.ok(labelBtn !== null, 'label help button must render when concept_id set')
  assert.equal(valueBtn, null, 'no value help button when value_concept_id absent')
  assert.equal(labelBtn.dataset.conceptId, 'axis.lemma')
  cleanUp()
  console.log('  ✓ field with only concept_id renders label help button, no value button')
}

// 20. Field without concept IDs renders no help buttons
{
  const noConcept = {
    ...VOCAB_LESSON,
    fields: [{ label: 'definition', value: 'to speak' }],
  }
  const pane = makePane()
  pane.show({ lesson: noConcept, sentenceText: '', language: 'es', depth: 'deep' })
  const helpBtns = sr(pane).querySelectorAll('.pane__concept-help')
  assert.equal(helpBtns.length, 0,
    'no .pane__concept-help buttons must appear when no concept IDs are set')
  cleanUp()
  console.log('  ✓ field without concept IDs renders no help buttons')
}

// 21. Morphology axis renders separate axis and value help buttons
{
  const withAxes = {
    ...VOCAB_LESSON,
    morphology_axes: [
      { axis: 'Tense', value: 'imperfect', axis_concept_id: 'axis.tense', value_concept_id: 'tense.imperfect' },
      { axis: 'Person', value: '3', axis_concept_id: 'axis.person' },
    ],
  }
  const pane = makePane()
  pane.show({ lesson: withAxes, sentenceText: '', language: 'es', depth: 'deep' })
  const dtBtns = sr(pane).querySelectorAll('.pane__axis-label .pane__concept-help')
  const ddBtns = sr(pane).querySelectorAll('.pane__axis-value .pane__concept-help')
  assert.equal(dtBtns.length, 2, 'both axis label buttons rendered (axis_concept_id on each dt)')
  assert.equal(ddBtns.length, 1, 'one axis value button (only first axis has value_concept_id)')
  assert.equal(dtBtns[0].dataset.conceptId, 'axis.tense')
  assert.equal(ddBtns[0].dataset.conceptId, 'tense.imperfect')
  assert.equal(dtBtns[1].dataset.conceptId, 'axis.person')
  cleanUp()
  console.log('  ✓ morphology axes render separate axis and value concept help buttons')
}

// 21. Concept dialog is present but hidden initially
{
  const pane = makePane()
  pane.show({ lesson: VOCAB_LESSON, sentenceText: '', language: 'es', depth: 'deep' })
  const dialog = sr(pane).querySelector('#dp-concept-dialog')
  assert.ok(dialog !== null, '#dp-concept-dialog must be rendered')
  assert.ok(dialog.hidden, '#dp-concept-dialog must be hidden initially')
  assert.equal(dialog.getAttribute('role'), 'dialog', 'concept dialog must have role="dialog"')
  assert.equal(dialog.getAttribute('aria-modal'), 'true', 'concept dialog must have aria-modal="true"')
  assert.equal(dialog.getAttribute('aria-labelledby'), 'dp-concept-title', 'dialog must be labelled by title element')
  assert.equal(dialog.getAttribute('aria-describedby'), 'dp-concept-body', 'dialog must have aria-describedby pointing to body')
  const body = sr(pane).querySelector('#dp-concept-body')
  assert.ok(body !== null, '#dp-concept-body element must exist')
  assert.equal(body.getAttribute('aria-live'), 'polite', 'concept body must have aria-live=polite for loading announcements')
  cleanUp()
  console.log('  ✓ concept dialog is rendered hidden with correct ARIA attributes')
}

// Test 23: concept help buttons have distinct aria-labels when label/value text available
{
  const MORPH_LESSON = {
    ...VOCAB_LESSON,
    fields: [
      { label: 'Tense', value: 'imperfect', concept_id: 'tense', value_concept_id: 'tense.imperfect' }
    ]
  }
  const pane = makePane()
  pane.show({ lesson: MORPH_LESSON, sentenceText: '', language: 'es', depth: 'learning' })
  const buttons = sr(pane).querySelectorAll('.pane__concept-help')
  assert.ok(buttons.length >= 2, 'need at least 2 help buttons for this test')
  const labels = Array.from(buttons).map(b => b.getAttribute('aria-label'))
  assert.notEqual(labels[0], labels[1], 'label-help and value-help buttons must have distinct aria-labels')
  assert.ok(labels[0].includes('Tense') || labels[0].includes('imperfect') || labels[0].length > 1, 'label button aria-label must include some context')
  cleanUp()
  console.log('  ✓ label and value concept help buttons have distinct aria-labels')
}

// 24. Loading state shown synchronously in body aria-live region
{
  const withConcept = {
    ...VOCAB_LESSON,
    fields: [{ label: 'Tense', value: 'present', concept_id: 'axis.tense' }],
  }
  const pane = makePane()
  pane.show({ lesson: withConcept, sentenceText: '', language: 'es', depth: 'deep' })
  const origFetch = globalThis.fetch
  globalThis.fetch = () => new Promise(() => {}) // never resolves — freeze to observe loading state
  const helpBtn = sr(pane).querySelector('.pane__concept-help')
  helpBtn.click()
  const body = sr(pane).querySelector('#dp-concept-body')
  assert.ok(body.textContent.trim().length > 0,
    'body must show loading message synchronously while fetch is pending')
  globalThis.fetch = origFetch
  cleanUp()
  console.log('  ✓ concept dialog body shows loading message synchronously')
}

// 25. Error state shown in body after fetch rejects
await (async () => {
  const withConcept = {
    ...VOCAB_LESSON,
    fields: [{ label: 'Tense', value: 'present', concept_id: 'axis.tense' }],
  }
  const pane = makePane()
  pane.show({ lesson: withConcept, sentenceText: '', language: 'es', depth: 'deep' })
  globalThis.fetch = () => Promise.reject(new Error('no server'))
  sr(pane).querySelector('.pane__concept-help').click()
  await new Promise(r => setTimeout(r, 0))
  const body = sr(pane).querySelector('#dp-concept-body')
  assert.ok(body.textContent.trim().length > 0,
    'body must show error message after fetch failure')
  const errorEl = sr(pane).querySelector('.pane__concept-error')
  assert.ok(errorEl !== null, '.pane__concept-error element must be rendered in body')
  globalThis.fetch = undefined
  cleanUp()
  console.log('  ✓ concept dialog body shows error message after fetch failure')
})()

// 26. Practice CTA rendered when concept has practice_tags
await (async () => {
  const CONCEPT_WITH_PRACTICE = {
    concept_id: 'axis.tense', title: 'Tense',
    short_definition: 'When an action occurs.',
    learner_explanation: 'Tense marks time.',
    examples: [], related_concepts: [],
    practice_tags: ['tense_recognition'],
  }
  const withConcept = {
    ...VOCAB_LESSON,
    fields: [{ label: 'Tense', value: 'present', concept_id: 'axis.tense' }],
  }
  const pane = makePane()
  pane.show({ lesson: withConcept, sentenceText: '', language: 'es', depth: 'learning' })
  globalThis.fetch = () => Promise.resolve({ ok: true, json: () => Promise.resolve(CONCEPT_WITH_PRACTICE) })
  sr(pane).querySelector('.pane__concept-help').click()
  await new Promise(r => setTimeout(r, 0))
  const cta = sr(pane).querySelector('.pane__concept-practice-cta')
  assert.ok(cta !== null, 'practice CTA must render when concept has practice_tags')
  globalThis.fetch = undefined
  cleanUp()
  console.log('  ✓ concept dialog renders practice CTA when concept has practice_tags')
})()

// 27. Practice CTA click closes concept dialog
await (async () => {
  const CONCEPT_WITH_PRACTICE = {
    concept_id: 'axis.tense', title: 'Tense',
    short_definition: 'When an action occurs.',
    learner_explanation: 'Tense marks time.',
    examples: [], related_concepts: [],
    practice_tags: ['tense_recognition'],
  }
  const withConcept = {
    ...VOCAB_LESSON,
    fields: [{ label: 'Tense', value: 'present', concept_id: 'axis.tense' }],
  }
  const pane = makePane()
  pane.show({ lesson: withConcept, sentenceText: 'hablar es fácil.', language: 'es', depth: 'learning' })
  globalThis.fetch = () => Promise.resolve({ ok: true, json: () => Promise.resolve(CONCEPT_WITH_PRACTICE) })
  sr(pane).querySelector('.pane__concept-help').click()
  await new Promise(r => setTimeout(r, 0))
  const dialog = sr(pane).querySelector('#dp-concept-dialog')
  assert.ok(!dialog.hidden, 'dialog must be open before CTA click')
  sr(pane).querySelector('.pane__concept-practice-cta').click()
  assert.ok(dialog.hidden, 'dialog must close when practice CTA is clicked')
  globalThis.fetch = undefined
  cleanUp()
  console.log('  ✓ practice CTA click closes concept dialog')
})()

// 28. Loading state has aria-busy="true" for AT announcement suppression
{
  const withConcept = {
    ...VOCAB_LESSON,
    fields: [{ label: 'Tense', value: 'present', concept_id: 'axis.tense' }],
  }
  const pane = makePane()
  pane.show({ lesson: withConcept, sentenceText: '', language: 'es', depth: 'deep' })
  globalThis.fetch = () => new Promise(() => {})
  sr(pane).querySelector('.pane__concept-help').click()
  const loadingEl = sr(pane).querySelector('.pane__concept-loading')
  assert.ok(loadingEl !== null, '.pane__concept-loading element must be present during fetch')
  assert.equal(loadingEl.getAttribute('aria-busy'), 'true',
    'loading element must have aria-busy="true" to signal AT that content is pending')
  globalThis.fetch = undefined
  cleanUp()
  console.log('  ✓ concept dialog loading state has aria-busy="true"')
}

// 29. Escape key closes concept dialog without closing the pane
await (async () => {
  const withConcept = {
    ...VOCAB_LESSON,
    fields: [{ label: 'Tense', value: 'present', concept_id: 'axis.tense' }],
  }
  const pane = makePane()
  pane.show({ lesson: withConcept, sentenceText: '', language: 'es', depth: 'deep' })
  globalThis.fetch = () => Promise.resolve({ ok: true, json: () => Promise.resolve({
    concept_id: 'axis.tense', title: 'Tense', explanation: 'When.', related_concepts: [], practice_tags: [],
  }) })
  sr(pane).querySelector('.pane__concept-help').click()
  await new Promise(r => setTimeout(r, 0))
  const dialog = sr(pane).querySelector('#dp-concept-dialog')
  assert.ok(!dialog.hidden, 'dialog must be open before Escape')
  // linkedom doesn't expose KeyboardEvent — use Event + key property, which is all the handler inspects
  sr(pane).dispatchEvent(Object.assign(new Event('keydown', { bubbles: true, cancelable: true }), { key: 'Escape' }))
  assert.ok(dialog.hidden, 'concept dialog must close on Escape')
  assert.ok(document.body.contains(pane), 'pane must remain in DOM — Escape must not close the pane when dialog was open')
  globalThis.fetch = undefined
  cleanUp()
  console.log('  ✓ Escape closes concept dialog only, pane stays open')
})()

// 30. Error state paragraph has role="alert" for assertive AT announcement
await (async () => {
  const withConcept = {
    ...VOCAB_LESSON,
    fields: [{ label: 'Tense', value: 'present', concept_id: 'axis.tense' }],
  }
  const pane = makePane()
  pane.show({ lesson: withConcept, sentenceText: '', language: 'es', depth: 'deep' })
  globalThis.fetch = () => Promise.reject(new Error('offline'))
  sr(pane).querySelector('.pane__concept-help').click()
  await new Promise(r => setTimeout(r, 0))
  const errorEl = sr(pane).querySelector('.pane__concept-error')
  assert.ok(errorEl !== null, '.pane__concept-error must be rendered')
  assert.equal(errorEl.getAttribute('role'), 'alert',
    'error paragraph must have role="alert" so AT announces it assertively')
  globalThis.fetch = undefined
  cleanUp()
  console.log('  ✓ concept dialog error state has role="alert"')
})()

console.log('\nAll detail pane render tests passed.')
