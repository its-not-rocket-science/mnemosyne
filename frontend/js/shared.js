/**
 * shared.js — Helpers used by more than one mode coordinator.
 *
 * Owns: the status helper, HTML escaping, screen-reader announcements,
 * OS theme tracking (auto mode), defocus-on-pointer-interaction,
 * the keyboard shortcut legend, global keyboard shortcuts, and TopNav
 * event wiring. These all touch DOM nodes that exist outside any single
 * mode's surface (global chrome), so they live here rather than inside
 * a coordinator.
 */
import { playbackEngine } from './playback.js'
import { t } from './i18n.js'
import {
  isFollowAlongEnabled,
  setFollowAlongEnabled,
  currentSentenceIndex,
  FILTER_CYCLE,
  filterCycleIndex,
  setFilterCycleIndex,
  currentDepth,
  setCurrentDepth,
  ANNOTATION_DEPTH_KEY,
  setActiveFilterTypes,
  setActiveFilterCategories,
  activeLockedCatIds,
  setActiveLockedCatIds,
  setActiveLockedTypes,
} from './reading-state.js'
import { applyAnnotationFilter } from './modes/lesson.js'

// ── Status helper ─────────────────────────────────────────────────────────────

const status = document.querySelector('#status')

export function setStatus(message, state = 'idle') {
  if (!status) return
  status.textContent = ''
  queueMicrotask(() => {
    status.textContent = message
    status.dataset.state = state
  })
}

// ── HTML escaping ─────────────────────────────────────────────────────────────

export function escapeHtml(value) {
  return String(value)
    .replaceAll('&',  '&amp;')
    .replaceAll('<',  '&lt;')
    .replaceAll('>',  '&gt;')
    .replaceAll('"',  '&quot;')
    .replaceAll("'", '&#39;')
}

// ── Screen-reader announcements ───────────────────────────────────────────────

const a11yLive = document.querySelector('#a11y-live')

export function announce(msg) {
  if (!a11yLive) return
  // Clear first so the same message re-announces if repeated.
  a11yLive.textContent = ''
  requestAnimationFrame(() => { a11yLive.textContent = msg })
}

// ── OS theme tracking (auto mode) ─────────────────────────────────────────────
// When the user has chosen 'auto', mirror OS preference changes in real time.
;(function () {
  const mq = window.matchMedia('(prefers-color-scheme: dark)')
  mq.addEventListener('change', () => {
    if ((document.documentElement.getAttribute('data-theme') || 'auto') === 'auto') {
      document.dispatchEvent(new CustomEvent('mnemosyne:theme-changed', {
        detail: { theme: 'auto' }, bubbles: false,
      }))
    }
  })
})()

// ── Defocus on pointer interaction ────────────────────────────────────────────
// Blurs buttons/links after mouse/touch click so focus rings don't linger.
// pointerup never fires for keyboard events, so keyboard nav is unaffected.
document.addEventListener('pointerup', () => {
  setTimeout(() => {
    const el  = document.activeElement
    if (!el || el === document.body) return
    const tag = el.tagName.toLowerCase()
    if (tag === 'button' || tag === 'a') el.blur()
  }, 0)
}, { passive: true })

// Blur select after pointer-driven option selection.
// change fires on every arrow-key press too, so we only blur when the
// interaction was initiated by a pointer (tracked via pointerdown).
const _selectsWithPointerDown = new WeakSet()
document.addEventListener('pointerdown', e => {
  if (e.target.tagName.toLowerCase() === 'select') _selectsWithPointerDown.add(e.target)
}, { passive: true })
document.addEventListener('change', e => {
  const el = e.target
  if (el.tagName.toLowerCase() === 'select' && _selectsWithPointerDown.has(el)) {
    _selectsWithPointerDown.delete(el)
    el.blur()
  }
})

// ── Keyboard shortcut legend ──────────────────────────────────────────────────

const shortcutsDialog   = document.querySelector('#shortcuts-dialog')
const shortcutsCloseBtn = document.querySelector('#shortcuts-close-btn')
const topNav            = document.querySelector('mnemosyne-top-nav')

shortcutsCloseBtn?.addEventListener('click', () => shortcutsDialog?.close())

export function openShortcuts() {
  shortcutsDialog?.showModal()
  shortcutsCloseBtn?.focus()
}

topNav?.addEventListener('settings-open', openShortcuts)

// ── Global keyboard shortcuts ─────────────────────────────────────────────────
// Uses e.composedPath()[0] so the innermost shadow-DOM element is checked,
// avoiding false positives when focus is inside a Web Component.
//
// Reading-mode state (follow-along, filter cycling, current sentence, corpus
// drills) is owned by js/modes/lesson.js and js/modes/review.js but tracked
// here via reading-state.js's live bindings, so the shortcuts stay in sync
// without this module owning that state itself.

const resultsSection   = document.querySelector('#results-section')
const appFilterBar     = document.querySelector('#app-filter-bar')
const filterBar        = document.querySelector('#filter-bar')
const annotationSearch = document.querySelector('#annotation-search')
const corpusDrillsBtn  = document.querySelector('#corpus-drills-btn')
const results          = document.querySelector('#results')

document.addEventListener('keydown', e => {
  // Never intercept when a modal/dialog is open (it handles its own keys).
  if (shortcutsDialog?.open) return

  // Innermost focused element — pierces Shadow DOM.
  const target = /** @type {HTMLElement|null} */ (e.composedPath()[0])
  const tag = target?.tagName?.toLowerCase() ?? ''
  const inText   = tag === 'input' || tag === 'textarea'
  const inSelect = tag === 'select'
  const inButton = tag === 'button' || tag === 'a'

  // Never steal keys from text-entry controls.
  if (inText || inSelect) return

  // Whether results are currently rendered.
  const hasResults = resultsSection && !resultsSection.hidden

  switch (e.key) {
    case '?':
      if (!inButton) { e.preventDefault(); openShortcuts() }
      break

    case ' ':
      // Space activates the focused button natively; only intercept in dead space.
      if (!inButton && playbackEngine.state !== 'idle') {
        e.preventDefault()
        playbackEngine.togglePause()
        announce(playbackEngine.state === 'playing' ? t('aria_paused') : t('aria_resumed'))
      }
      break

    case 'ArrowLeft':
      if (!inButton && playbackEngine.state !== 'idle') {
        e.preventDefault()
        playbackEngine.prev()
        announce(t('aria_prev_sentence'))
      }
      break

    case 'ArrowRight':
      if (!inButton && playbackEngine.state !== 'idle') {
        e.preventDefault()
        playbackEngine.next()
        announce(t('aria_next_sentence'))
      }
      break

    case 'l':
    case 'L':
      if (!inButton && !e.ctrlKey && !e.metaKey) {
        e.preventDefault()
        setFollowAlongEnabled(!isFollowAlongEnabled())
        announce(isFollowAlongEnabled() ? t('aria_follow_along_on') : t('aria_follow_along_off'))
      }
      break

    case 't':
    case 'T':
      if (inButton || e.ctrlKey || e.metaKey || !hasResults) break
      e.preventDefault()
      {
        const focused = /** @type {HTMLElement} */ (e.composedPath()[0])
        const card = focused?.closest?.('.sentence-card')
          ?? results?.querySelector(`[data-sentence-index="${currentSentenceIndex()}"]`)
          ?? results?.querySelector('.sentence-card')
        const translateBtn = card?.querySelector('.reader-sentence__translate-btn')
        if (translateBtn) translateBtn.click()
      }
      break

    case 'd':
    case 'D':
      if (inButton || e.ctrlKey || e.metaKey || !hasResults) break
      if (corpusDrillsBtn?.hidden !== false) break
      e.preventDefault()
      corpusDrillsBtn.click()
      break

    case 'f':
    case 'F':
      if (inButton || e.ctrlKey || e.metaKey) break
      if (!appFilterBar || appFilterBar.hidden) break
      e.preventDefault()
      setFilterCycleIndex((filterCycleIndex() + 1) % FILTER_CYCLE.length)
      filterBar?.activateCategory?.(FILTER_CYCLE[filterCycleIndex()])
      break

    case 's':
    case 'S':
      if (inButton || e.ctrlKey || e.metaKey || !hasResults) break
      if (!annotationSearch || appFilterBar?.hidden) break
      e.preventDefault()
      annotationSearch.focus()
      annotationSearch.select()
      break
  }
})

// ── TopNav event wiring ───────────────────────────────────────────────────────

const detailPane = document.querySelector('#detail-pane')

if (topNav && currentDepth()) topNav.depth = currentDepth()

topNav?.addEventListener('depth-change', ({ detail }) => {
  setCurrentDepth(detail.depth)
  localStorage.setItem(ANNOTATION_DEPTH_KEY, detail.depth)
  detailPane?.updateDepth(detail.depth)
  applyAnnotationFilter()
})

document.addEventListener('mnemosyne:mode-changed', ({ detail }) => {
  setCurrentDepth(detail.mode)
  applyAnnotationFilter()
})

filterBar?.addEventListener('filter-change', ({ detail }) => {
  setActiveFilterTypes(detail.types.length   ? new Set(detail.types)  : null)
  setActiveFilterCategories(detail.active.length  ? new Set(detail.active) : null)

  // Persist per-category depth locks when they change
  if (detail.locked !== undefined) {
    setActiveLockedCatIds(detail.locked)
    setActiveLockedTypes(new Set(detail.lockedTypes || []))
    localStorage.setItem('mn-cat-locks',       JSON.stringify(activeLockedCatIds()))
    localStorage.setItem('mn-cat-lock-types',  JSON.stringify([...detail.lockedTypes || []]))
  }

  if (!detail.active.length) {
    setFilterCycleIndex(0)
  } else {
    const idx = FILTER_CYCLE.indexOf(detail.active[0])
    if (idx >= 0) setFilterCycleIndex(idx)
  }
  applyAnnotationFilter()
})

// Restore persisted per-category depth locks (fires filter-change → applyAnnotationFilter)
if (activeLockedCatIds().length) filterBar?.setLocks?.(activeLockedCatIds())

function applyFilterBarLabels() {
  filterBar?.setLabels?.({
    vocab:        t('filter_vocab'),
    grammar:      t('filter_grammar'),
    idioms:       t('filter_idioms'),
    literary:     t('filter_literary'),
    etymology:    t('filter_etymology'),
    verse:        t('filter_verse'),
    custom:       t('filter_custom'),
    custom_title: t('filter_custom_title'),
    custom_hint:  t('filter_custom_hint'),
    add_btn:      t('filter_add_btn'),
    placeholder:  t('filter_placeholder'),
  })
}

document.addEventListener('mnemosyne:language-changed', applyFilterBarLabels)
// Apply labels now (initUiLanguage ran before filterBar was defined).
applyFilterBarLabels()

// ── About dialog ─────────────────────────────────────────────────────────────
// Global app-chrome dialogs (not owned by any single reading/library/review
// mode), so they live here alongside the other cross-cutting chrome wiring.

const aboutDialog   = document.querySelector('#about-dialog')
const aboutCloseBtn = document.querySelector('#about-close-btn')
const aboutBtn      = document.querySelector('#about-btn')

aboutBtn?.addEventListener('click', () => aboutDialog?.showModal())
aboutCloseBtn?.addEventListener('click', () => aboutDialog?.close())

const aboutTabs   = document.querySelectorAll('.about-dialog__tab')
const aboutPanels = document.querySelectorAll('#about-dialog [role="tabpanel"]')
aboutTabs.forEach(tab => {
  tab.addEventListener('click', () => {
    aboutTabs.forEach(tb => {
      tb.setAttribute('aria-selected', 'false')
      tb.tabIndex = -1
    })
    aboutPanels.forEach(p => { p.hidden = true })
    tab.setAttribute('aria-selected', 'true')
    tab.tabIndex = 0
    const panel = document.getElementById(tab.getAttribute('aria-controls'))
    if (panel) panel.hidden = false
  })
})

// Arrow-key navigation inside the about-dialog tablist (APG tab pattern).
document.querySelector('.about-dialog__tabs')?.addEventListener('keydown', (e) => {
  const tabs = [...aboutTabs]
  const idx  = tabs.indexOf(document.activeElement)
  if (idx === -1) return
  if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
    e.preventDefault()
    const next = tabs[(idx + (e.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length]
    next.focus()
    next.click()
  }
})

// ── GDPR dialog ───────────────────────────────────────────────────────────────

const gdprDialog   = document.querySelector('#gdpr-dialog')
const gdprCloseBtn = document.querySelector('#gdpr-close-btn')
const gdprOkBtn    = document.querySelector('#gdpr-ok-btn')
const privacyLink  = document.querySelector('#privacy-link')

privacyLink?.addEventListener('click', e => {
  e.preventDefault()
  gdprDialog?.showModal()
})
gdprCloseBtn?.addEventListener('click', () => gdprDialog?.close())
gdprOkBtn?.addEventListener('click',    () => gdprDialog?.close())
