/**
 * annotation-tooltip.test.mjs
 *
 * DOM-aware tests for the annotation hover tooltip.
 * Checks structure (via linkedom), CSS presence, and high-level JS wiring.
 * Does NOT inspect function body internals.
 */
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { loadDocument, readSource } from './lib/dom.mjs'

const document = loadDocument()
const mainJs   = readSource('js/main.js')
const css      = readSource('css/components.css')

// ── DOM structure ─────────────────────────────────────────────────────────────

describe('annotation tooltip — DOM', () => {
  it('#annotation-tooltip element exists', () => {
    const el = document.querySelector('#annotation-tooltip')
    assert.ok(el, '#annotation-tooltip must be in index.html')
  })

  it('#annotation-tooltip has role="tooltip"', () => {
    const el = document.querySelector('#annotation-tooltip')
    assert.equal(el?.getAttribute('role'), 'tooltip')
  })

  it('#annotation-tooltip is hidden by default', () => {
    const el = document.querySelector('#annotation-tooltip')
    assert.ok(
      el?.hasAttribute('hidden') || el?.getAttribute('aria-hidden') === 'true',
      'tooltip must be hidden by default'
    )
  })
})

// ── CSS ───────────────────────────────────────────────────────────────────────

describe('annotation tooltip — CSS', () => {
  it('components.css defines .annotation-tooltip', () => {
    assert.ok(css.includes('.annotation-tooltip'), '.annotation-tooltip block must exist in CSS')
  })

  it('tooltip uses absolute or fixed positioning', () => {
    assert.ok(
      css.includes('position: absolute') || css.includes('position: fixed'),
      'tooltip must use absolute or fixed positioning'
    )
  })
})

// ── JS wiring (existence only — no body inspection) ──────────────────────────

describe('annotation tooltip — main.js', () => {
  it('defines _showAnnotationTooltip', () => {
    assert.ok(mainJs.includes('_showAnnotationTooltip'))
  })

  it('defines _hideAnnotationTooltip', () => {
    assert.ok(mainJs.includes('_hideAnnotationTooltip'))
  })

  it('annotated marks store dataset.label for tooltip access', () => {
    assert.ok(mainJs.includes('dataset.label'), 'marks must write dataset.label')
  })
})
