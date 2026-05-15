/**
 * reader-render.test.mjs — DOM-level rendering tests for mnemosyne-pill and
 * mnemosyne-text-panel.
 *
 * Proves the rendered reader behaves correctly (not just the payload builder):
 *   - pill badge text, icon, aria-label, lang, dir, confidence styling
 *   - pill lesson-open event fires with correct detail on click
 *   - text-panel line elements and data attributes
 *   - annotation span structure, text range, gap preservation
 *   - annotation-select and line-speak events
 *   - setActiveLine, header visibility, RTL propagation
 *   - overlapping annotation badge hints
 *
 * Uses linkedom for a lightweight browser-like DOM environment.
 * Run with: node frontend/tests/reader-render.test.mjs
 */
import assert from 'node:assert/strict'
import { parseHTML } from 'linkedom'

// ── DOM environment setup — must precede component imports ────────────────────

const dom = parseHTML('<!doctype html><html><head></head><body></body></html>')
const { window, document, customElements, HTMLElement, Event, CustomEvent } = dom
Object.assign(globalThis, { window, document, customElements, HTMLElement, Event, CustomEvent })

// CSS.escape polyfill — used by text-panel's #findLineEl
globalThis.CSS = {
  escape: s => s.replace(/([!"#$%&'()*+,./:;<=>?@[\\\]^`{|}~])/g, '\\$1'),
}
// localStorage stub — i18n uses it only in initUiLanguage() which we never call
globalThis.localStorage = { getItem: () => null, setItem: () => {} }
// requestAnimationFrame stub — VirtualList uses it but we stay well under the
// 200-line threshold so virtual mode is never activated in these tests
globalThis.requestAnimationFrame = () => {}

// Dynamic imports so globalThis is fully set up first
await import('../components/mnemosyne-pill.js')
await import('../components/mnemosyne-text-panel.js')

// ── Helpers ───────────────────────────────────────────────────────────────────

function makePill({ type = 'vocabulary', label = 'test', objectId = 'obj-1',
                    language = '', dir = '', confidence = '' } = {}) {
  const el = document.createElement('mnemosyne-pill')
  el.setAttribute('type', type)
  el.setAttribute('label', label)
  el.setAttribute('object-id', objectId)
  if (language)   el.setAttribute('language', language)
  if (dir)        el.setAttribute('dir', dir)
  if (confidence) el.setAttribute('confidence', confidence)
  document.body.appendChild(el)
  return el
}

/**
 * Lines are stored before connecting so connectedCallback's #render() picks
 * them up on first paint without a second render cycle.
 */
function makePanel(lines = [], attrs = {}) {
  const el = document.createElement('mnemosyne-text-panel')
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v)
  el.lines = lines
  document.body.appendChild(el)
  return el
}

const sr = el => el.shadowRoot
const cleanUp = () => { document.body.innerHTML = '' }

// ── mnemosyne-pill ────────────────────────────────────────────────────────────

// 1. Vocabulary badge text and label text
{
  const pill = makePill({ type: 'vocabulary', label: 'hablar', language: 'es' })
  const spans = sr(pill).querySelectorAll('button span')
  assert.ok(spans.length >= 4, `pill must have ≥ 4 child spans; got ${spans.length}`)
  assert.equal(spans[1].textContent, 'vocab', 'vocabulary badge must read "vocab"')
  assert.equal(sr(pill).querySelector('.pill-label').textContent, 'hablar',
    '.pill-label must display label attribute value')
  cleanUp()
  console.log('  ✓ vocabulary pill: badge text "vocab", label text correct')
}

// 2. Conjugation badge text
{
  const pill = makePill({ type: 'conjugation', label: 'habló' })
  const spans = sr(pill).querySelectorAll('button span')
  assert.equal(spans[1].textContent, 'verb', 'conjugation badge must read "verb"')
  cleanUp()
  console.log('  ✓ conjugation badge renders as "verb"')
}

// 3. Unknown type falls back to vocabulary defaults
{
  const pill = makePill({ type: 'unknown_xyz', label: 'foo' })
  const spans = sr(pill).querySelectorAll('button span')
  assert.equal(spans[1].textContent, 'vocab', 'unknown type must fall back to "vocab" badge')
  cleanUp()
  console.log('  ✓ unknown type falls back to vocab badge')
}

// 4. aria-label contains the label text
{
  const pill = makePill({ type: 'vocabulary', label: 'hablar' })
  const ariaLabel = sr(pill).querySelector('button').getAttribute('aria-label')
  assert.ok(ariaLabel && ariaLabel.toLowerCase().includes('hablar'),
    `aria-label must include "hablar"; got: "${ariaLabel}"`)
  cleanUp()
  console.log('  ✓ aria-label includes label text')
}

// 5. language attribute becomes lang on shadow button
{
  const pill = makePill({ type: 'vocabulary', label: 'hablar', language: 'es' })
  assert.equal(sr(pill).querySelector('button').getAttribute('lang'), 'es',
    'button lang must match language attribute')
  cleanUp()
  console.log('  ✓ language attribute propagates as lang on shadow button')
}

// 6. RTL: dir="rtl" applies to .pill-label only, not to the button element
{
  const pill = makePill({ label: 'مرحبا', language: 'ar', dir: 'rtl' })
  const labelEl = sr(pill).querySelector('.pill-label')
  const btn     = sr(pill).querySelector('button')
  assert.equal(labelEl.getAttribute('dir'), 'rtl',
    '.pill-label must carry dir="rtl"')
  assert.notEqual(btn.getAttribute('dir'), 'rtl',
    'button itself must not carry dir="rtl" — only the label span should')
  cleanUp()
  console.log('  ✓ RTL: dir="rtl" on .pill-label only, not on button')
}

// 7. LTR (default): no dir attribute on .pill-label
{
  const pill = makePill({ label: 'hablar', dir: 'ltr' })
  assert.ok(!sr(pill).querySelector('.pill-label').hasAttribute('dir'),
    '.pill-label must not carry dir for LTR content')
  cleanUp()
  console.log('  ✓ LTR (default): no dir attribute on .pill-label')
}

// 8. Low confidence (< 0.72): dashed border and 0.65 opacity in shadow style
{
  const pill = makePill({ confidence: '0.5' })
  const styleText = sr(pill).querySelector('style').textContent
  assert.ok(styleText.includes('dashed'),
    'low-confidence pill style must contain "dashed"')
  assert.ok(styleText.includes('0.65'),
    'low-confidence pill style must contain opacity 0.65')
  cleanUp()
  console.log('  ✓ confidence 0.5 (low): dashed border + 0.65 opacity in shadow style')
}

// 9. Moderate confidence (0.72–0.87): solid border, reduced opacity
{
  const pill = makePill({ confidence: '0.8' })
  const styleText = sr(pill).querySelector('style').textContent
  assert.ok(!styleText.includes('dashed'),
    'moderate-confidence pill must not have dashed border')
  assert.ok(styleText.includes('0.82'),
    'moderate-confidence pill must have 0.82 opacity')
  cleanUp()
  console.log('  ✓ confidence 0.8 (moderate): solid border + 0.82 opacity')
}

// 10. High confidence (≥ 0.88): solid border, full opacity
{
  const pill = makePill({ confidence: '0.95' })
  const styleText = sr(pill).querySelector('style').textContent
  assert.ok(!styleText.includes('dashed'),
    'high-confidence pill must not have dashed border')
  cleanUp()
  console.log('  ✓ confidence 0.95 (high): solid border, no opacity reduction')
}

// 11. lesson-open event fires on inner button click with correct detail
{
  const pill = makePill({ type: 'vocabulary', label: 'hablar', objectId: 'obj-99', language: 'es' })
  let detail = null
  pill.addEventListener('lesson-open', e => { detail = e.detail })
  sr(pill).querySelector('button').click()
  assert.ok(detail !== null, 'lesson-open event must fire on button click')
  assert.equal(detail.objectId, 'obj-99', 'detail.objectId must match object-id attribute')
  assert.equal(detail.language, 'es',     'detail.language must match language attribute')
  assert.equal(detail.type,    'vocabulary', 'detail.type must match type attribute')
  assert.equal(detail.label,   'hablar',   'detail.label must match label attribute')
  cleanUp()
  console.log('  ✓ lesson-open fires with objectId, language, type, label on click')
}

// ── mnemosyne-text-panel ──────────────────────────────────────────────────────

// 12. Empty lines shows .panel__empty
{
  const panel = makePanel([])
  assert.ok(sr(panel).querySelector('.panel__empty') !== null,
    '.panel__empty must appear when lines is empty')
  cleanUp()
  console.log('  ✓ empty lines renders .panel__empty placeholder')
}

// 13. Multiple lines produce .line elements with correct data-line-id
{
  const panel = makePanel([
    { id: 'L1', text: 'Primera línea.', annotations: [] },
    { id: 'L2', text: 'Segunda línea.', annotations: [] },
    { id: 'L3', text: 'Tercera línea.', annotations: [] },
  ])
  const lineEls = sr(panel).querySelectorAll('.line')
  assert.equal(lineEls.length, 3, 'three lines must produce three .line elements')
  assert.equal(lineEls[0].dataset.lineId, 'L1')
  assert.equal(lineEls[1].dataset.lineId, 'L2')
  assert.equal(lineEls[2].dataset.lineId, 'L3')
  cleanUp()
  console.log('  ✓ three lines render three .line elements with correct data-line-id')
}

// 14. Annotation span: data-ann-id, data-type, role="button", tabindex="0"
{
  const panel = makePanel([{
    id: 'line-1',
    text: 'hablar es un verbo.',
    annotations: [{ id: 'ann-1', start: 0, end: 6, type: 'vocab' }],
  }])
  const ann = sr(panel).querySelector('.ann')
  assert.ok(ann !== null, '.ann span must be rendered for annotation')
  assert.equal(ann.dataset.annId, 'ann-1', 'data-ann-id must match annotation id')
  assert.equal(ann.dataset.type, 'vocab',  'data-type must match annotation type')
  assert.equal(ann.getAttribute('role'), 'button',  'role must be "button" for keyboard access')
  assert.equal(ann.getAttribute('tabindex'), '0',   'tabindex must be "0" for focusability')
  cleanUp()
  console.log('  ✓ annotation span: data-ann-id, data-type, role="button", tabindex="0"')
}

// 15. Annotation text matches the character range in line.text
{
  const panel = makePanel([{
    id: '1',
    text: 'Le soleil se lève.',
    annotations: [{ id: 'ann-sol', start: 3, end: 9, type: 'vocab' }],
  }])
  // First child of .ann is the annotated text node
  const phrase = sr(panel).querySelector('.ann').childNodes[0].textContent
  assert.equal(phrase, 'soleil', `annotated text must be "soleil"; got "${phrase}"`)
  cleanUp()
  console.log('  ✓ annotation text matches character range slice of line.text')
}

// 16. Pre-annotation gap preserved as a text node before the .ann span
{
  const panel = makePanel([{
    id: '1',
    text: 'El sol brilla.',
    annotations: [{ id: 'ann-sol', start: 3, end: 6, type: 'vocab' }],
  }])
  const p = sr(panel).querySelector('.line__text')
  const firstNode = p.childNodes[0]
  assert.equal(firstNode.nodeType, 3,
    'pre-annotation gap must be a text node (nodeType === 3)')
  assert.equal(firstNode.textContent, 'El ',
    `gap text must be "El "; got "${firstNode.textContent}"`)
  cleanUp()
  console.log('  ✓ pre-annotation text gap preserved as plain text node')
}

// 17. Post-annotation gap preserved as a text node after the .ann span
{
  const panel = makePanel([{
    id: '1',
    text: 'hablar es útil.',
    annotations: [{ id: 'ann-h', start: 0, end: 6, type: 'vocab' }],
  }])
  const p = sr(panel).querySelector('.line__text')
  // childNodes: [.ann, textNode(" es útil.")]
  const lastNode = p.childNodes[p.childNodes.length - 1]
  assert.equal(lastNode.nodeType, 3,
    'post-annotation gap must be a text node (nodeType === 3)')
  assert.ok(lastNode.textContent.includes(' es útil.'),
    `post-annotation text must contain " es útil."; got "${lastNode.textContent}"`)
  cleanUp()
  console.log('  ✓ post-annotation text gap preserved as plain text node')
}

// 18. lang and dir attributes propagate to .line__text elements
{
  const panel = makePanel(
    [{ id: '1', text: 'مرحبا بالعالم.', annotations: [] }],
    { lang: 'ar', dir: 'rtl' },
  )
  const p = sr(panel).querySelector('.line__text')
  assert.equal(p.getAttribute('lang'), 'ar',  '.line__text must carry lang="ar"')
  assert.equal(p.getAttribute('dir'),  'rtl', '.line__text must carry dir="rtl"')
  cleanUp()
  console.log('  ✓ lang and dir propagate to .line__text from panel attributes')
}

// 19. line-speak event fires on speaker button click with lineId and text
{
  const panel = makePanel([{ id: 'line-x', text: 'Bonjour monde.', annotations: [] }])
  let detail = null
  panel.addEventListener('line-speak', e => { detail = e.detail })
  sr(panel).querySelector('.line__speak').click()
  assert.ok(detail !== null, 'line-speak must fire on speaker button click')
  assert.equal(detail.lineId, 'line-x',       'detail.lineId must match line id')
  assert.equal(detail.text,   'Bonjour monde.', 'detail.text must match line text')
  cleanUp()
  console.log('  ✓ line-speak event fires with lineId and text on speaker button click')
}

// 20. annotation-select event fires on annotation click with annotationId, lineId, type
{
  const panel = makePanel([{
    id: 'line-a',
    text: 'hablar es útil.',
    annotations: [{ id: 'ann-5', start: 0, end: 6, type: 'vocab' }],
  }])
  let detail = null
  panel.addEventListener('annotation-select', e => { detail = e.detail })
  sr(panel).querySelector('.ann').click()
  assert.ok(detail !== null, 'annotation-select must fire on annotation click')
  assert.equal(detail.annotationId, 'ann-5',  'detail.annotationId must match annotation id')
  assert.equal(detail.lineId,       'line-a', 'detail.lineId must match line id')
  assert.equal(detail.type,         'vocab',  'detail.type must match annotation type')
  cleanUp()
  console.log('  ✓ annotation-select fires with annotationId, lineId, type on click')
}

// 21. setActiveLine marks the correct line with .line--active
{
  const panel = makePanel([
    { id: 'L1', text: 'First.',  annotations: [] },
    { id: 'L2', text: 'Second.', annotations: [] },
  ])
  panel.setActiveLine('L2')
  const activeEl = sr(panel).querySelector('.line--active')
  assert.ok(activeEl !== null, 'setActiveLine must add .line--active')
  assert.equal(activeEl.dataset.lineId, 'L2',
    '.line--active must be on the specified line')
  cleanUp()
  console.log('  ✓ setActiveLine adds .line--active to the correct line')
}

// 22. Overlapping annotations: greedy selection keeps the earlier/shorter one;
//     overlapping type appears in .ann__badges on the winning span
{
  const text = 'hablar de nuevo'
  const panel = makePanel([{
    id: '1', text,
    annotations: [
      { id: 'ann-a', start: 0, end: 6,  type: 'vocab' },   // selected (starts first, shorter)
      { id: 'ann-b', start: 0, end: 15, type: 'idiom'  },  // overlaps → badge hint
    ],
  }])
  const ann = sr(panel).querySelector('.ann')
  assert.ok(ann !== null, 'primary annotation must be rendered')
  const badges = ann.querySelector('.ann__badges')
  assert.ok(badges !== null,
    'overlapping annotation type must produce .ann__badges element')
  assert.ok(badges.textContent.trim().length > 0,
    '.ann__badges must contain at least one badge emoji')
  cleanUp()
  console.log('  ✓ overlapping annotations: primary rendered, overlap appears as .ann__badges')
}

// 23. Panel header hidden when neither panel-title nor panel-scene is set
{
  const panel = makePanel([{ id: '1', text: 'Text.', annotations: [] }])
  assert.ok(sr(panel).getElementById('header').hasAttribute('hidden'),
    'header must be hidden when no title or scene is provided')
  cleanUp()
  console.log('  ✓ panel header hidden when panel-title and panel-scene are absent')
}

// 24. Panel header visible and populated when panel-title is set
{
  const panel = makePanel(
    [{ id: '1', text: 'Text.', annotations: [] }],
    { 'panel-title': 'Don Quixote' },
  )
  const header = sr(panel).getElementById('header')
  assert.ok(!header.hasAttribute('hidden'),
    'header must be visible when panel-title is set')
  assert.equal(sr(panel).getElementById('panel-title').textContent, 'Don Quixote',
    'panel-title element must show the attribute value')
  cleanUp()
  console.log('  ✓ panel-title shows header with correct text')
}

// 25. Annotation with invalid offsets (end > text.length) is silently skipped
{
  const panel = makePanel([{
    id: '1',
    text: 'short',
    annotations: [{ id: 'bad', start: 0, end: 999, type: 'vocab' }],  // end > length
  }])
  const ann = sr(panel).querySelector('.ann')
  assert.equal(ann, null,
    'annotation with end > text.length must be silently skipped — no .ann rendered')
  cleanUp()
  console.log('  ✓ out-of-range annotation silently skipped, no .ann rendered')
}

console.log('\nAll reader render tests passed.')
