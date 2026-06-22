/**
 * analytics-insight.test.mjs
 *
 * DOM-aware tests for the daily learning insight bar and retention panel.
 * Covers: DOM structure, i18n key presence, CSS classes, JS wiring.
 */
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { loadDocument, readSource } from './lib/dom.mjs'
import { assertLocaleKeys } from './lib/i18n.mjs'

const document = loadDocument()
const mainJs   = readSource('js/review-session.js')
const i18n     = readSource('js/i18n.js')
const css      = readSource('css/components.css')

// ── DOM structure — daily insight ─────────────────────────────────────────────

describe('analytics insight — DOM structure', () => {
  it('#daily-insight exists in authenticated shell', () => {
    assert.ok(document.querySelector('#daily-insight'), '#daily-insight must exist')
  })

  it('#daily-insight is inside #main-content', () => {
    const mainContent = document.querySelector('#main-content')
    assert.ok(mainContent?.querySelector('#daily-insight'), '#daily-insight must be inside #main-content')
  })

  it('#daily-insight is hidden by default', () => {
    const el = document.querySelector('#daily-insight')
    assert.ok(el?.hasAttribute('hidden'), '#daily-insight must start hidden')
  })

  it('#daily-insight has aria-live="polite"', () => {
    const el = document.querySelector('#daily-insight')
    assert.equal(el?.getAttribute('aria-live'), 'polite')
  })

  it('#daily-insight appears before #forecast-bar', () => {
    const insight  = document.querySelector('#daily-insight')
    const forecast = document.querySelector('#forecast-bar')
    assert.ok(insight && forecast)
    // compareDocumentPosition: 4 = following (forecast follows insight)
    assert.ok(
      insight.compareDocumentPosition(forecast) & 4,
      '#daily-insight must precede #forecast-bar in DOM order'
    )
  })
})

// ── DOM structure — retention panel ───────────────────────────────────────────

describe('analytics insight — retention panel DOM', () => {
  it('#retention-panel exists', () => {
    assert.ok(document.querySelector('#retention-panel'), '#retention-panel must exist')
  })

  it('#retention-panel is hidden by default', () => {
    const el = document.querySelector('#retention-panel')
    assert.ok(el?.hasAttribute('hidden'), '#retention-panel must start hidden')
  })

  it('#retention-details is a <details> element', () => {
    const el = document.querySelector('#retention-details')
    assert.equal(el?.tagName?.toLowerCase(), 'details')
  })

  it('#retention-details has a <summary> child', () => {
    const summary = document.querySelector('#retention-details > summary')
    assert.ok(summary, 'retention-details must have a summary child')
  })

  it('summary has data-i18n="retention_panel_heading"', () => {
    const summary = document.querySelector('#retention-details > summary')
    assert.equal(summary?.getAttribute('data-i18n'), 'retention_panel_heading')
  })

  it('#retention-panel-body exists', () => {
    assert.ok(document.querySelector('#retention-panel-body'))
  })

  it('#retention-panel-body has aria-live="polite"', () => {
    const el = document.querySelector('#retention-panel-body')
    assert.equal(el?.getAttribute('aria-live'), 'polite')
  })

  it('#retention-panel appears after #weakness-graph-bar', () => {
    const weakness  = document.querySelector('#weakness-graph-bar')
    const retention = document.querySelector('#retention-panel')
    assert.ok(weakness && retention)
    // compareDocumentPosition: 4 = following (retention follows weakness)
    assert.ok(
      weakness.compareDocumentPosition(retention) & 4,
      '#retention-panel must follow #weakness-graph-bar in DOM order'
    )
  })
})

// ── CSS ───────────────────────────────────────────────────────────────────────

describe('analytics insight — CSS', () => {
  it('defines .daily-insight', () => {
    assert.ok(css.includes('.daily-insight'))
  })

  it('defines .daily-insight__item', () => {
    assert.ok(css.includes('.daily-insight__item'))
  })

  it('defines .retention-disclosure', () => {
    assert.ok(css.includes('.retention-disclosure'))
  })

  it('defines .retention-panel__body', () => {
    assert.ok(css.includes('.retention-panel__body'))
  })

  it('defines .retention-panel__row', () => {
    assert.ok(css.includes('.retention-panel__row'))
  })

  it('forced-colors coverage for retention panel', () => {
    assert.ok(
      css.includes('forced-colors') && css.includes('.retention-disclosure__summary'),
      'forced-colors block must cover .retention-disclosure__summary'
    )
  })
})

// ── JS wiring ─────────────────────────────────────────────────────────────────

describe('analytics insight — review-session.js wiring', () => {
  it('imports t and ti from i18n.js', () => {
    assert.ok(mainJs.includes("from './i18n.js'") && mainJs.includes('ti'))
  })

  it('defines _buildInsightItems', () => {
    assert.ok(mainJs.includes('_buildInsightItems'))
  })

  it('defines _renderInsight', () => {
    assert.ok(mainJs.includes('_renderInsight'))
  })

  it('defines refreshRetentionPanel', () => {
    assert.ok(mainJs.includes('refreshRetentionPanel'))
  })

  it('calls refreshRetentionPanel on init', () => {
    // After initial refreshBadge/refreshStats/refreshForecast calls
    const idx = mainJs.indexOf('refreshRetentionPanel()')
    assert.ok(idx > -1, 'refreshRetentionPanel() must be called on init')
  })

  it('fetches /users/me/fsrs-params', () => {
    assert.ok(mainJs.includes('/users/me/fsrs-params'))
  })

  it('calls POST /users/me/calibrate for recalibrate button', () => {
    assert.ok(mainJs.includes('/users/me/calibrate'))
  })

  it('uses ti() with insight_weak_concept', () => {
    assert.ok(mainJs.includes('insight_weak_concept'))
  })

  it('uses ti() with insight_confusion', () => {
    assert.ok(mainJs.includes('insight_confusion'))
  })

  it('uses ti() with insight_high_friction', () => {
    assert.ok(mainJs.includes('insight_high_friction'))
  })

  it('uses ti() with retention_calibrated', () => {
    assert.ok(mainJs.includes('retention_calibrated'))
  })

  it('uses t() with retention_not_calibrated', () => {
    assert.ok(mainJs.includes('retention_not_calibrated'))
  })

  it('uses t() with retention_recalibrate_btn', () => {
    assert.ok(mainJs.includes('retention_recalibrate_btn'))
  })

  it('uses t() with retention_calibrating', () => {
    assert.ok(mainJs.includes('retention_calibrating'))
  })

  it('weakness/profile fetch in refreshStats', () => {
    assert.ok(mainJs.includes('/weakness/profile/'))
  })
})

// ── i18n coverage ─────────────────────────────────────────────────────────────

describe('analytics insight — i18n (all 11 locales)', () => {
  it('insight keys present in every locale', () => {
    assertLocaleKeys(i18n, [
      'insight_weak_concept',
      'insight_confusion',
      'insight_high_friction',
    ])
  })

  it('retention panel keys present in every locale', () => {
    assertLocaleKeys(i18n, [
      'retention_panel_heading',
      'retention_targeting',
      'retention_calibrated',
      'retention_not_calibrated',
      'retention_requires',
      'retention_rmse',
      'retention_recalibrate_btn',
      'retention_calibrating',
    ])
  })
})
