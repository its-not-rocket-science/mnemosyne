/**
 * detail-pane.test.mjs — DOM-level rendering tests for mnemosyne-detail-pane.
 *
 * Proves the detail pane Web Component renders correctly end-to-end as a
 * 3-level progressive disclosure panel (no tab bar — level 1 is always
 * visible, level 2 "More about this" and level 3 "Full detail" are
 * collapsible <div aria-expanded> sections expanded via ghost buttons):
 *   - type badge icon and label
 *   - title from canonical_form
 *   - explanation text (level 1, always rendered)
 *   - level 2 / level 3 disclosure section presence per depth (subtle / learning / deep)
 *   - origins and related content reachable inside level 2 when data is present
 *   - context panel with sentence text and highlighted phrase (inside level 2)
 *   - hide() fires pane-close and sets inert
 *   - close button and study button events
 *   - match badge for non-canonical match types
 *   - "More about this" / "Full detail" toggle clicks expand their section and update aria-expanded
 *   - no [role="tab"] / [role="tablist"] anywhere in the pane
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

// A morphology axis guarantees level 2 ("More about this") has content —
// origins/context/related now live in level 3, so level 2's presence
// depends on form/paradigm/equivalents/nuance/memory/extra-fields/
// why-it-matters data, independent of depth (which separately still gates
// origins/context/related/practice/review availability).
const VOCAB_LESSON_WITH_FORM = {
  ...VOCAB_LESSON,
  morphology_axes: [{ axis: 'tense', value: 'present' }],
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

const PHRASE_FAMILY_LESSON = {
  id: 'ann-3',
  type: 'phrase_family',
  title: 'bite the bullet',
  explanation: 'To face a difficult situation with courage.',
  examples: ['bite the bullet'],
  fields: [],
  lesson_data: {
    canonical_form: 'bite the bullet',
    matched_variant: 'bite the bullet',
    match_type: 'exact',
    why_it_matters: 'Soldiers literally bit on a bullet to endure pain before anesthesia existed.',
    register: 'informal',
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

// 4. depth='subtle' → no level 2 disclosure (no origins/context/etc at this depth)
{
  const pane = makePane()
  pane.show({ lesson: VOCAB_LESSON, sentenceText: '', language: 'es', depth: 'subtle' })
  const l2Toggle = sr(pane).querySelector('.pane__level2-toggle')
  const l3Toggle = sr(pane).querySelector('.pane__level3-toggle')
  assert.equal(l2Toggle, null, 'depth="subtle" must not render a "More about this" toggle')
  assert.equal(l3Toggle, null, 'depth="subtle" must not render a "Full detail" toggle')
  assert.ok(sr(pane).querySelector('#dp-panel-explanation'),
    'explanation (level 1) content must always be present')
  cleanUp()
  console.log('  ✓ depth="subtle" renders level 1 only — no level 2/3 disclosure triggers')
}

// 5. depth='learning' → level 3 (context + practice) present; no level 2 without
//    form/paradigm/equivalents/nuance/memory/extra-field/why-it-matters data;
//    no origins without origin data
{
  const pane = makePane()
  pane.show({ lesson: VOCAB_LESSON, sentenceText: 'hablar es fácil.', language: 'es', depth: 'learning' })
  const sr_ = sr(pane)
  assert.equal(sr_.querySelector('.pane__level2-toggle'), null,
    'must not have "More about this" toggle when there is no level 2 content')
  assert.ok(sr_.querySelector('.pane__level3-toggle'), 'must have "Full detail" toggle at depth="learning"')
  assert.ok(sr_.querySelector('#dp-panel-context'),  'context content must exist at depth="learning"')
  assert.ok(sr_.querySelector('#dp-panel-practice'), 'practice content must exist at depth="learning"')
  assert.equal(sr_.querySelector('#dp-panel-origins'), null,
    'origins content must not appear without origin data')
  cleanUp()
  console.log('  ✓ depth="learning" renders context + practice in level 3 — no origins without data, no empty level 2')
}

// 6. depth='deep' with lesson_data.origin → origins content included in level 3
{
  const pane = makePane()
  pane.show({ lesson: IDIOM_LESSON, sentenceText: 'lo hace a la vez.', language: 'es', depth: 'deep' })
  const origins = sr(pane).querySelector('#dp-panel-origins')
  assert.ok(origins !== null, 'origins content must appear when lesson_data.origin is set')
  assert.ok(sr(pane).querySelector('#dp-level3').contains(origins),
    'origins content must live inside the level 3 ("Full detail") section')
  cleanUp()
  console.log('  ✓ depth="deep" + origin data → origins content rendered inside level 3')
}

// 7. depth='deep' with variants (length > 1) → related content included in level 3
{
  const withVariants = {
    ...VOCAB_LESSON,
    lesson_data: { ...VOCAB_LESSON.lesson_data, variants: ['hablar', 'hable'] },
  }
  const pane = makePane()
  pane.show({ lesson: withVariants, sentenceText: '', language: 'es', depth: 'deep' })
  const related = sr(pane).querySelector('#dp-panel-related')
  assert.ok(related !== null, 'related content must appear when variants.length > 1')
  assert.ok(sr(pane).querySelector('#dp-level3').contains(related),
    'related content must live inside the level 3 ("Full detail") section')
  cleanUp()
  console.log('  ✓ depth="deep" + variants → related content rendered inside level 3')
}

// 8. Context panel rendered at depth='learning' with sentence text (inside level 3)
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
  assert.ok(sr(pane).querySelector('#dp-level3').contains(ctx),
    'context sentence must live inside the level 3 section')
  cleanUp()
  console.log('  ✓ context panel renders sentence text at depth="learning", inside level 3')
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

// 16a. "More about this" toggle click expands level 2 and flips aria-expanded
{
  const pane = makePane()
  pane.show({ lesson: VOCAB_LESSON_WITH_FORM, sentenceText: 'hablar es fácil.', language: 'es', depth: 'learning' })
  const sr_ = sr(pane)
  const l2Toggle  = sr_.querySelector('.pane__level2-toggle')
  const l2Section = sr_.querySelector('#dp-level2')
  assert.ok(l2Toggle !== null, '"More about this" toggle must be rendered at depth="learning"')
  assert.equal(l2Toggle.getAttribute('aria-expanded'), 'false', 'level 2 collapsed initially')
  assert.equal(l2Toggle.getAttribute('aria-controls'), 'dp-level2', 'toggle must point at the level 2 section id')
  assert.ok(l2Section.hidden, 'level 2 section must be hidden before expansion')
  l2Toggle.click()
  assert.equal(l2Toggle.getAttribute('aria-expanded'), 'true', 'level 2 expanded after click')
  assert.ok(!l2Section.hidden, 'level 2 section must be visible after expansion')
  cleanUp()
  console.log('  ✓ "More about this" toggle expands level 2 and updates aria-expanded')
}

// 16b. "Full detail" toggle click expands level 3 and flips aria-expanded
{
  const pane = makePane()
  pane.show({ lesson: VOCAB_LESSON, sentenceText: 'hablar es fácil.', language: 'es', depth: 'learning' })
  const sr_ = sr(pane)
  const l3Toggle  = sr_.querySelector('.pane__level3-toggle')
  const l3Section = sr_.querySelector('#dp-level3')
  assert.ok(l3Toggle !== null, '"Full detail" toggle must be rendered at depth="learning"')
  assert.equal(l3Toggle.getAttribute('aria-expanded'), 'false', 'level 3 collapsed initially')
  assert.equal(l3Toggle.getAttribute('aria-controls'), 'dp-level3', 'toggle must point at the level 3 section id')
  assert.ok(l3Section.hidden, 'level 3 section must be hidden before expansion')
  l3Toggle.click()
  assert.equal(l3Toggle.getAttribute('aria-expanded'), 'true', 'level 3 expanded after click')
  assert.ok(!l3Section.hidden, 'level 3 section must be visible after expansion')
  cleanUp()
  console.log('  ✓ "Full detail" toggle expands level 3 and updates aria-expanded')
}

// 16c. Disclosure state persists across re-render while pane stays open, resets on hide()
{
  const pane = makePane()
  pane.show({ lesson: VOCAB_LESSON_WITH_FORM, sentenceText: 'hablar es fácil.', language: 'es', depth: 'learning' })
  sr(pane).querySelector('.pane__level2-toggle').click()
  assert.equal(sr(pane).querySelector('.pane__level2-toggle').getAttribute('aria-expanded'), 'true')
  // Re-show with the same lesson (simulates a re-render path, e.g. language change) —
  // level 2/3 state must persist while the pane stays open.
  pane.show({ lesson: VOCAB_LESSON_WITH_FORM, sentenceText: 'hablar es fácil.', language: 'es', depth: 'learning' })
  assert.equal(sr(pane).querySelector('.pane__level2-toggle').getAttribute('aria-expanded'), 'true',
    'level 2 expansion must persist across re-render while pane stays open')
  pane.hide()
  pane.show({ lesson: VOCAB_LESSON_WITH_FORM, sentenceText: 'hablar es fácil.', language: 'es', depth: 'learning' })
  assert.equal(sr(pane).querySelector('.pane__level2-toggle').getAttribute('aria-expanded'), 'false',
    'level 2 must reset to collapsed after hide() + show()')
  cleanUp()
  console.log('  ✓ disclosure state persists across re-render, resets on hide()')
}

// 16d. No [role="tab"] / [role="tablist"] anywhere in the pane
{
  const pane = makePane()
  pane.show({ lesson: VOCAB_LESSON, sentenceText: 'hablar es fácil.', language: 'es', depth: 'deep' })
  assert.equal(sr(pane).querySelectorAll('[role="tab"]').length, 0, 'no [role="tab"] must be present')
  assert.equal(sr(pane).querySelectorAll('[role="tablist"]').length, 0, 'no [role="tablist"] must be present')
  cleanUp()
  console.log('  ✓ no [role="tab"] or [role="tablist"] anywhere in the pane')
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

// 31. why_it_matters visible at "learning"/Standard depth (cultural-catalogue
// visibility fix — was gated to depthIdx >= 2/"deep" only)
{
  const pane = makePane()
  pane.show({ lesson: PHRASE_FAMILY_LESSON, sentenceText: '', language: 'en', depth: 'learning' })
  const why = sr(pane).querySelector('.pane__why-it-matters-text')
  assert.ok(why !== null, '.pane__why-it-matters-text must render at depth="learning"')
  assert.ok(why.textContent.includes('Soldiers'), 'why-it-matters text must match lesson_data.why_it_matters')
  cleanUp()
  console.log('  ✓ why_it_matters visible at depth="learning" (Standard)')
}

// 32. why_it_matters hidden at "subtle"/Words-only depth
{
  const pane = makePane()
  pane.show({ lesson: PHRASE_FAMILY_LESSON, sentenceText: '', language: 'en', depth: 'subtle' })
  const why = sr(pane).querySelector('.pane__why-it-matters-text')
  assert.equal(why, null, '.pane__why-it-matters-text must not render at depth="subtle"')
  cleanUp()
  console.log('  ✓ why_it_matters hidden at depth="subtle" (Words only)')
}

// 33. Register badge renders for non-neutral register, absent for neutral
{
  const pane = makePane()
  pane.show({ lesson: PHRASE_FAMILY_LESSON, sentenceText: '', language: 'en', depth: 'deep' })
  const badge = sr(pane).querySelector('.pane__register-badge')
  assert.ok(badge !== null, '.pane__register-badge must render for register="informal"')
  assert.ok(badge.classList.contains('pane__register-badge--informal'),
    'badge must carry the register-specific modifier class')
  cleanUp()

  const neutralLesson = { ...PHRASE_FAMILY_LESSON, lesson_data: { ...PHRASE_FAMILY_LESSON.lesson_data, register: 'neutral' } }
  const pane2 = makePane()
  pane2.show({ lesson: neutralLesson, sentenceText: '', language: 'en', depth: 'deep' })
  assert.equal(sr(pane2).querySelector('.pane__register-badge'), null,
    'no register badge for register="neutral"')
  cleanUp()
  console.log('  ✓ register badge shown for non-neutral register, hidden for neutral')
}

console.log('\nAll detail pane render tests passed.')
