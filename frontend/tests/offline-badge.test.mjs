/**
 * offline-badge.test.mjs
 *
 * DOM-aware tests for the offline queue status badge and explain dialog.
 * Covers: DOM structure, JS wiring, JWT-expiry queue state, reconnect drain
 * logic references, and i18n coverage across all 11 locales.
 */
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { loadDocument, readSource } from './lib/dom.mjs'
import { assertLocaleKeys } from './lib/i18n.mjs'

const document = loadDocument()
// Offline review queue lives in js/modes/review.js after the main.js split
// (Session 1 of the frontend refactor).
const mainJs   = readSource('js/modes/review.js')
const i18n     = readSource('js/i18n.js')
const css      = readSource('css/components.css')

// ── DOM structure ─────────────────────────────────────────────────────────────

describe('offline badge — DOM structure', () => {
  it('#offline-queue-badge exists in the top-nav slot', () => {
    const badge = document.querySelector('#offline-queue-badge')
    assert.ok(badge, '#offline-queue-badge must exist')
  })

  it('#offline-queue-badge is a button (keyboard accessible)', () => {
    const badge = document.querySelector('#offline-queue-badge')
    assert.equal(badge?.tagName?.toLowerCase(), 'button')
  })

  it('#offline-queue-badge is hidden by default', () => {
    const badge = document.querySelector('#offline-queue-badge')
    assert.ok(badge?.hasAttribute('hidden'), 'badge must start hidden')
  })

  it('#offline-queue-badge has aria-haspopup="dialog"', () => {
    const badge = document.querySelector('#offline-queue-badge')
    assert.equal(badge?.getAttribute('aria-haspopup'), 'dialog')
  })

  it('#offline-queue-badge is inside <mnemosyne-top-nav>', () => {
    const nav = document.querySelector('mnemosyne-top-nav')
    assert.ok(nav?.querySelector('#offline-queue-badge'), 'badge must be slotted into top-nav')
  })
})

// ── Explain dialog ────────────────────────────────────────────────────────────

describe('offline badge — explain dialog', () => {
  it('#offline-explain-dialog exists', () => {
    assert.ok(document.querySelector('#offline-explain-dialog'), '#offline-explain-dialog must exist')
  })

  it('dialog has aria-labelledby="offline-explain-heading"', () => {
    const d = document.querySelector('#offline-explain-dialog')
    assert.equal(d?.getAttribute('aria-labelledby'), 'offline-explain-heading')
  })

  it('#offline-explain-heading exists', () => {
    assert.ok(document.querySelector('#offline-explain-heading'))
  })

  it('#offline-explain-body exists', () => {
    assert.ok(document.querySelector('#offline-explain-body'))
  })

  it('#offline-explain-close button exists', () => {
    assert.ok(document.querySelector('#offline-explain-close'))
  })
})

// ── CSS ───────────────────────────────────────────────────────────────────────

describe('offline badge — CSS', () => {
  it('review.css defines .offline-queue-badge', () => {
    assert.ok(css.includes('.offline-queue-badge'))
  })

  it('defines offline state', () => {
    assert.ok(css.includes('[data-state="offline"]'))
  })

  it('defines pending state', () => {
    assert.ok(css.includes('[data-state="pending"]'))
  })

  it('defines syncing state with animation', () => {
    assert.ok(css.includes('[data-state="syncing"]'))
    assert.ok(css.includes('_offline-pulse') || css.includes('animation'))
  })

  it('defines synced state', () => {
    assert.ok(css.includes('[data-state="synced"]'))
  })

  it('defines expired state', () => {
    assert.ok(css.includes('[data-state="expired"]'))
  })

  it('forced-colors support for offline badge', () => {
    assert.ok(
      css.includes('forced-colors') && css.includes('.offline-queue-badge'),
      'forced-colors block must cover .offline-queue-badge'
    )
  })
})

// ── JS wiring ─────────────────────────────────────────────────────────────────

describe('offline badge — main.js wiring', () => {
  it('defines updateOfflineBadge', () => {
    assert.ok(mainJs.includes('updateOfflineBadge'))
  })

  it('updateOfflineBadge called after queueReview in submitReview', () => {
    assert.ok(mainJs.includes('queueReview') && mainJs.includes('updateOfflineBadge()'))
  })

  it('drainReviewQueue sets syncing state on badge', () => {
    assert.ok(mainJs.includes("'syncing'"))
  })

  it('drainReviewQueue shows synced count after successful drain', () => {
    assert.ok(mainJs.includes("'synced'") && mainJs.includes('offline_synced'))
  })

  it('drainReviewQueue calls updateOfflineBadge after 401 (JWT expired)', () => {
    assert.ok(mainJs.includes('_offlineJwtExpired = true'))
    assert.ok(mainJs.includes('updateOfflineBadge()'))
  })

  it('_offlineJwtExpired flag tracked', () => {
    assert.ok(mainJs.includes('_offlineJwtExpired'))
  })

  it('listens to window online event for drain', () => {
    assert.ok(mainJs.includes("addEventListener('online', drainReviewQueue)"))
  })

  it('listens to window offline event to update badge', () => {
    assert.ok(mainJs.includes("addEventListener('offline', updateOfflineBadge)"))
  })

  it('calls updateOfflineBadge on startup (setTimeout)', () => {
    assert.ok(mainJs.includes('setTimeout(updateOfflineBadge'))
  })

  it('badge click handler opens explain dialog', () => {
    assert.ok(mainJs.includes('#offline-queue-badge') && mainJs.includes('showModal'))
  })

  it('explain close button wired', () => {
    assert.ok(mainJs.includes('#offline-explain-close') && mainJs.includes('.close()'))
  })

  it('uses offline_explain_expired for JWT-expired state', () => {
    assert.ok(mainJs.includes('offline_explain_expired'))
  })

  it('uses offline_explain_offline for offline state', () => {
    assert.ok(mainJs.includes('offline_explain_offline'))
  })

  it('uses offline_explain_pending for online+pending state', () => {
    assert.ok(mainJs.includes('offline_explain_pending'))
  })
})

// ── i18n coverage ─────────────────────────────────────────────────────────────

describe('offline badge — i18n (all 11 locales)', () => {
  it('badge label keys present in every locale', () => {
    assertLocaleKeys(i18n, [
      'offline_queued',
      'offline_pending',
      'offline_syncing',
      'offline_synced',
      'offline_jwt_expired',
    ])
  })

  it('explain dialog keys present in every locale', () => {
    assertLocaleKeys(i18n, [
      'offline_explain_heading',
      'offline_explain_offline',
      'offline_explain_pending',
      'offline_explain_expired',
    ])
  })
})
