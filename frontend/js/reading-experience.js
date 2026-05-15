/*
  Progressive reading experience behaviour.

  This module is intentionally additive. It does not replace main.js rendering;
  it observes the existing reader DOM and adds:
  - annotation reveal density: subtle / learning / deep
  - focus mode: dims app chrome around the reading surface
  - inline preview cards below clicked inline annotations
  - keyboard support for inline previews
*/

import { t } from './i18n.js'
import { toggleFlowMode, isFlowMode, syncFlowBtn, stepFlowSentence, getActiveSentenceIndex } from './flow-mode.js'
import { makeHelpButton } from './help-popover.js'

const results = document.querySelector('#results')
const resultsSection = document.querySelector('#results-section')
const a11yLive = document.querySelector('#a11y-live')

const STORAGE_MODE_KEY = 'mnemosyne.reader.annotationMode'
const STORAGE_FOCUS_KEY = 'mnemosyne.reader.focusMode'

const MODES = [
  { value: 'subtle',   labelKey: 'reader_mode_subtle',   hintKey: 'reader_mode_subtle_hint' },
  { value: 'learning', labelKey: 'reader_mode_learning', hintKey: 'reader_mode_learning_hint' },
  { value: 'deep',     labelKey: 'reader_mode_deep',     hintKey: 'reader_mode_deep_hint' },
]

let currentMode = localStorage.getItem(STORAGE_MODE_KEY) || 'learning'
let focusMode = localStorage.getItem(STORAGE_FOCUS_KEY) === 'true'

let focusTicking = false

function annotationObjectId(annotation) {
  return annotation?.dataset?.objectId
    || annotation?.dataset?.object_id
    || annotation?.dataset?.annotationId
    || null
}

function clearFocusBlock() {
  results?.querySelectorAll('[data-focus-block]').forEach(el => {
    el.removeAttribute('data-focus-block')
    el.removeAttribute('aria-current')
  })
}

function setFocusBlock(target) {
  if (!(target instanceof HTMLElement)) return
  const card = target.closest('.sentence-card')
  if (!(card instanceof HTMLElement)) return
  clearFocusBlock()
  card.setAttribute('data-focus-block', 'true')
  card.setAttribute('aria-current', 'true')
}

function updateViewportFocusBlock() {
  if (!focusMode || !results) return
  if (isFlowMode()) return
  const cards = [...results.querySelectorAll('.sentence-card')]
  if (!cards.length) return
  const center = window.innerHeight * 0.42
  let best = cards[0]
  let bestDist = Number.POSITIVE_INFINITY
  for (const card of cards) {
    const rect = card.getBoundingClientRect()
    if (rect.bottom < 0 || rect.top > window.innerHeight) continue
    const dist = Math.abs(((rect.top + rect.bottom) / 2) - center)
    if (dist < bestDist) { bestDist = dist; best = card }
  }
  setFocusBlock(best)
}

function scheduleViewportFocusBlock() {
  if (focusTicking) return
  focusTicking = true
  requestAnimationFrame(() => {
    focusTicking = false
    updateViewportFocusBlock()
  })
}

function announce(message) {
  if (!a11yLive) return
  a11yLive.textContent = ''
  queueMicrotask(() => { a11yLive.textContent = message })
}

function makeButton({ text, i18nKey, className, pressed, ariaLabel }) {
  const btn = document.createElement('button')
  btn.type = 'button'
  btn.className = className
  btn.textContent = text
  if (i18nKey) btn.dataset.i18n = i18nKey
  btn.setAttribute('aria-pressed', String(Boolean(pressed)))
  if (ariaLabel) btn.setAttribute('aria-label', ariaLabel)
  return btn
}

function ensureToolbar() {
  if (!resultsSection) return null
  let bar = document.querySelector('#reader-control-bar')
  if (bar) return bar

  bar = document.createElement('section')
  bar.id = 'reader-control-bar'
  bar.className = 'reader-ctrl-bar'
  bar.setAttribute('aria-label', 'Reading controls')

  // ── Primary row ───────────────────────────────────────────────────────────
  const row = document.createElement('div')
  row.className = 'reader-ctrl__row'

  // Segmented mode selector
  const modeGroup = document.createElement('div')
  modeGroup.className = 'reader-ctrl__primary'
  modeGroup.setAttribute('role', 'group')
  modeGroup.setAttribute('aria-label', t('reader_reveal_label'))

  for (const mode of MODES) {
    const btn = makeButton({
      text: t(mode.labelKey),
      i18nKey: mode.labelKey,
      className: 'reader-mode-btn',
      pressed: mode.value === currentMode,
    })
    btn.dataset.mode = mode.value
    btn.title = t(mode.hintKey)
    btn.addEventListener('click', () => setMode(mode.value))
    modeGroup.appendChild(btn)
  }

  // Secondary: flow + focus + settings disclosure
  const secondary = document.createElement('div')
  secondary.className = 'reader-ctrl__secondary'

  const flowBtn = makeButton({
    text: t('reader_flow_mode'),
    i18nKey: 'reader_flow_mode',
    className: 'reader-focus-btn',
    pressed: isFlowMode(),
  })
  flowBtn.id = 'reader-flow-mode-btn'
  flowBtn.addEventListener('click', () => { toggleFlowMode(); syncFlowBtn() })

  const focusBtn = makeButton({
    text: t('reader_focus_mode'),
    i18nKey: 'reader_focus_mode',
    className: 'reader-focus-btn',
    pressed: focusMode,
  })
  focusBtn.id = 'reader-focus-mode-btn'
  focusBtn.addEventListener('click', () => setFocusMode(!focusMode))

  const settingsBtn = document.createElement('button')
  settingsBtn.type = 'button'
  settingsBtn.id = 'reader-settings-toggle'
  settingsBtn.className = 'reader-ctrl__settings-btn'
  settingsBtn.setAttribute('aria-label', t('reader_settings_aria'))
  settingsBtn.setAttribute('aria-expanded', 'false')
  settingsBtn.setAttribute('aria-controls', 'reader-system-body')
  settingsBtn.innerHTML = '<span aria-hidden="true">⚙</span>'
  settingsBtn.addEventListener('click', () => {
    const body = document.querySelector('#reader-system-body')
    if (!body) return
    const opening = body.hidden
    body.hidden = !opening
    settingsBtn.setAttribute('aria-expanded', String(opening))
    settingsBtn.classList.toggle('reader-ctrl__settings-btn--open', opening)
  })

  const adaptiveBtn = document.createElement('button')
  adaptiveBtn.type = 'button'
  adaptiveBtn.id = 'reader-adaptive-btn'
  adaptiveBtn.className = 'reader-focus-btn'
  adaptiveBtn.dataset.i18n = 'adaptive_btn'
  adaptiveBtn.textContent = t('adaptive_btn')
  adaptiveBtn.setAttribute('aria-pressed', String(window.mnemosyneAdaptive?.isEnabled?.() ?? true))
  adaptiveBtn.addEventListener('click', () => {
    document.dispatchEvent(new CustomEvent('mnemosyne:toggle-adaptive-reader'))
  })

  const ctrlHelpBtn = makeHelpButton('help_control_bar_tooltip')
  const flowPrevBtn = makeButton({
    text: t('reader_flow_prev'),
    i18nKey: 'reader_flow_prev',
    className: 'reader-focus-btn',
  })
  flowPrevBtn.id = 'reader-flow-prev-btn'
  flowPrevBtn.addEventListener('click', () => stepFlowSentence(-1))

  const flowNextBtn = makeButton({
    text: t('reader_flow_next'),
    i18nKey: 'reader_flow_next',
    className: 'reader-focus-btn',
  })
  flowNextBtn.id = 'reader-flow-next-btn'
  flowNextBtn.addEventListener('click', () => stepFlowSentence(1))

  const flowShortcut = document.createElement('span')
  flowShortcut.id = 'reader-flow-shortcuts'
  flowShortcut.dataset.i18n = 'reader_flow_shortcuts'
  flowShortcut.textContent = t('reader_flow_shortcuts')
  flowShortcut.className = 'reader-ctrl__hint'

  secondary.append(flowBtn, flowPrevBtn, flowNextBtn, flowShortcut, focusBtn, adaptiveBtn, settingsBtn, ctrlHelpBtn)
  row.append(modeGroup, secondary)

  const explainerWrap = document.createElement('div')
  explainerWrap.className = 'reader-ctrl__explainer'

  const explainerToggle = document.createElement('button')
  explainerToggle.type = 'button'
  explainerToggle.id = 'reader-modes-help-toggle'
  explainerToggle.className = 'reader-ctrl__explainer-toggle'
  explainerToggle.dataset.i18n = 'reader_modes_help_title'
  explainerToggle.textContent = t('reader_modes_help_title')
  explainerToggle.setAttribute('aria-expanded', 'false')
  explainerToggle.setAttribute('aria-controls', 'reader-modes-help-panel')
  explainerToggle.setAttribute('aria-label', t('reader_modes_help_aria'))

  const explainerPanel = document.createElement('div')
  explainerPanel.id = 'reader-modes-help-panel'
  explainerPanel.className = 'reader-ctrl__explainer-panel'
  explainerPanel.hidden = true
  explainerPanel.setAttribute('role', 'region')
  explainerPanel.setAttribute('aria-label', t('reader_modes_help_title'))
  explainerPanel.dataset.i18n = 'reader_modes_help_body'
  explainerPanel.textContent = t('reader_modes_help_body')

  explainerToggle.addEventListener('click', () => {
    const opening = explainerPanel.hidden
    explainerPanel.hidden = !opening
    explainerToggle.setAttribute('aria-expanded', String(opening))
  })
  explainerWrap.append(explainerToggle, explainerPanel)

  // ── System body — populated by adaptive-reader.js ─────────────────────────
  const systemBody = document.createElement('div')
  systemBody.id = 'reader-system-body'
  systemBody.className = 'reader-ctrl__system-body'
  systemBody.setAttribute('role', 'group')
  systemBody.setAttribute('aria-label', t('reader_settings_aria'))
  systemBody.hidden = true

  bar.append(row, explainerWrap, systemBody)
  resultsSection.prepend(bar)
  return bar
}

function syncToolbar() {
  const bar = document.querySelector('#reader-control-bar')
  if (!bar) return

  bar.querySelectorAll('.reader-mode-btn').forEach(btn => {
    const active = btn.dataset.mode === currentMode
    btn.setAttribute('aria-pressed', String(active))
    btn.classList.toggle('reader-mode-btn--active', active)
    const mode = MODES.find(m => m.value === btn.dataset.mode)
    if (mode) btn.title = t(mode.hintKey)
  })

  const focusBtn = bar.querySelector('#reader-focus-mode-btn')
  if (focusBtn) {
    const key = focusMode ? 'reader_focus_on' : 'reader_focus_mode'
    focusBtn.dataset.i18n = key
    focusBtn.textContent = t(key)
    focusBtn.setAttribute('aria-pressed', String(focusMode))
    focusBtn.classList.toggle('reader-focus-btn--active', focusMode)
  }

  const settingsBtn = bar.querySelector('#reader-settings-toggle')
  if (settingsBtn) settingsBtn.setAttribute('aria-label', t('reader_settings_aria'))

  const adaptiveBtn = bar.querySelector('#reader-adaptive-btn')
  if (adaptiveBtn) {
    adaptiveBtn.textContent = t('adaptive_btn')
    const enabled = window.mnemosyneAdaptive?.isEnabled?.() ?? true
    adaptiveBtn.setAttribute('aria-pressed', String(enabled))
    adaptiveBtn.classList.toggle('reader-focus-btn--active', enabled)
  }
  const flowHint = bar.querySelector('#reader-flow-shortcuts')
  if (flowHint) flowHint.textContent = t('reader_flow_shortcuts')

  const explainerToggle = bar.querySelector('#reader-modes-help-toggle')
  if (explainerToggle) {
    explainerToggle.textContent = t('reader_modes_help_title')
    explainerToggle.setAttribute('aria-label', t('reader_modes_help_aria'))
  }
  const explainerPanel = bar.querySelector('#reader-modes-help-panel')
  if (explainerPanel) {
    explainerPanel.setAttribute('aria-label', t('reader_modes_help_title'))
    explainerPanel.textContent = t('reader_modes_help_body')
  }

  syncFlowBtn()

  const flowEnabled = isFlowMode()
  for (const id of ['#reader-flow-prev-btn', '#reader-flow-next-btn']) {
    const btn = bar.querySelector(id)
    if (!btn) continue
    btn.toggleAttribute('disabled', !flowEnabled)
    btn.setAttribute('aria-disabled', String(!flowEnabled))
  }
}

document.addEventListener('keydown', (event) => {
  if (!isFlowMode()) return
  const inInput = event.target instanceof HTMLElement && event.target.closest('input, textarea, [contenteditable="true"]')
  if (inInput || event.altKey || event.metaKey || event.ctrlKey) return
  if (event.key === 'ArrowRight' || event.key === 'n' || event.key === 'N') {
    event.preventDefault()
    stepFlowSentence(1)
    announce(t('reader_flow_next'))
  } else if (event.key === 'ArrowLeft' || event.key === 'p' || event.key === 'P') {
    event.preventDefault()
    stepFlowSentence(-1)
    announce(t('reader_flow_prev'))
  }
})

document.addEventListener('mnemosyne:flow-mode-changed', () => {
  syncToolbar()
  if (isFlowMode() && getActiveSentenceIndex() < 0) stepFlowSentence(1)
  scheduleViewportFocusBlock()
})

document.addEventListener('scroll', scheduleViewportFocusBlock, { passive: true })
document.addEventListener('focusin', (event) => {
  if (!focusMode) return
  if (isFlowMode()) return
  setFocusBlock(event.target)
})
document.addEventListener('mnemosyne:render-complete', scheduleViewportFocusBlock)

function setMode(mode) {
  if (!MODES.some(m => m.value === mode)) mode = 'learning'
  currentMode = mode
  localStorage.setItem(STORAGE_MODE_KEY, currentMode)
  applyMode()
  syncToolbar()
  announce(t(`reader_mode_${mode}`) || mode)
}

function setFocusMode(next) {
  focusMode = Boolean(next)
  localStorage.setItem(STORAGE_FOCUS_KEY, String(focusMode))
  document.body.classList.toggle('reader-focus-mode', focusMode)
  if (!focusMode) clearFocusBlock()
  else scheduleViewportFocusBlock()
  syncToolbar()
  announce(focusMode ? t('reader_focus_on') : t('reader_focus_off'))
}

function applyMode() {
  document.documentElement.dataset.annotationReveal = currentMode
  if (results) results.dataset.annotationReveal = currentMode
}

function annotationTitle(el) {
  const type = el.dataset.typeLabel || el.dataset.type || 'Lesson'
  const text = el.textContent?.trim() || 'this passage'
  return `${type}: ${text}`
}

function annotationSummary(el) {
  const level = el.dataset.level
  const type = el.dataset.typeLabel || el.dataset.type || 'lesson'
  const visibleHint = currentMode === 'subtle'
    ? t('reader_preview_hint_subtle')
    : t('reader_preview_hint_default')
  return `${type}${level ? ` · level ${level}` : ''}. ${visibleHint}`
}

function closeInlinePreview(preview, restoreFocusTo) {
  preview?.remove()
  if (restoreFocusTo?.isConnected) restoreFocusTo.focus({ preventScroll: true })
}

function closeExistingPreviews() {
  document.querySelectorAll('.reader-inline-preview').forEach(el => el.remove())
}

function positionPreview(preview, anchor) {
  const GAP = 8
  const MARGIN = 8
  const rect = anchor.getBoundingClientRect()

  // Initial position: below the annotation, left-aligned to it
  let top = rect.bottom + GAP
  let left = rect.left

  preview.style.top = `${top}px`
  preview.style.left = `${left}px`

  // After first paint the preview has real dimensions — correct any overflow
  requestAnimationFrame(() => {
    const pr = preview.getBoundingClientRect()
    const vpW = window.innerWidth
    const vpH = window.innerHeight

    if (left + pr.width > vpW - MARGIN) left = vpW - pr.width - MARGIN
    if (left < MARGIN) left = MARGIN

    // Flip above if it would overflow bottom
    if (top + pr.height > vpH - MARGIN) top = rect.top - pr.height - GAP
    if (top < MARGIN) top = MARGIN

    preview.style.top = `${top}px`
    preview.style.left = `${left}px`
  })
}

function openInlinePreview(annotation) {
  if (!annotation || annotation.hasAttribute('data-filtered')) return

  // Toggle: clicking the same annotation again closes the preview
  const existing = document.querySelector('.reader-inline-preview')
  if (existing) {
    const wasSame = existing._annotationSource === annotation
    existing.remove()
    if (wasSame) return
  }

  const preview = document.createElement('aside')
  preview._annotationSource = annotation
  preview.className = 'reader-inline-preview'
  preview.setAttribute('aria-label', 'Inline lesson preview')

  const title = document.createElement('h3')
  title.className = 'reader-inline-preview__title'
  title.textContent = annotationTitle(annotation)

  const body = document.createElement('p')
  body.className = 'reader-inline-preview__body'
  body.textContent = annotationSummary(annotation)

  const actions = document.createElement('div')
  actions.className = 'reader-inline-preview__actions'

  const detailBtn = document.createElement('button')
  detailBtn.type = 'button'
  detailBtn.className = 'ghost-button ghost-button--small reader-inline-preview__detail'
  detailBtn.dataset.i18n = 'reader_open_full_lesson'
  detailBtn.textContent = t('reader_open_full_lesson')
  detailBtn.addEventListener('click', () => {
    const language = annotation.closest('[lang]')?.getAttribute('lang')
      || document.querySelector('#language')?.value
    const objectId = annotationObjectId(annotation)
    if (!objectId || !language) return

    closeInlinePreview(preview, annotation)
    // Dispatch on #results directly so the lesson-open listener fires
    // regardless of the annotation's bubble path. Pass the source annotation
    // in detail so the listener can still resolve the visual anchor.
    const target = results ?? annotation
    target.dispatchEvent(new CustomEvent('lesson-open', {
      bubbles: true,
      detail: { objectId, language, source: annotation },
    }))
  })

  const closeBtn = document.createElement('button')
  closeBtn.type = 'button'
  closeBtn.className = 'ghost-button ghost-button--small reader-inline-preview__close'
  closeBtn.dataset.i18n = 'close_btn_aria'
  closeBtn.textContent = t('close_btn_aria')
  closeBtn.addEventListener('click', () => closeInlinePreview(preview, annotation))

  actions.append(detailBtn, closeBtn)
  preview.append(title, body, actions)

  document.body.appendChild(preview)
  positionPreview(preview, annotation)
  announce(`Preview opened for ${annotation.textContent?.trim() || 'annotation'}`)
}

function enhanceAnnotations(root = document) {
  root.querySelectorAll('.reader-annotation').forEach(annotation => {
    if (annotation.dataset.experienceEnhanced === 'true') return
    annotation.dataset.experienceEnhanced = 'true'

    if (!annotation.hasAttribute('tabindex')) annotation.tabIndex = 0
    if (!annotation.hasAttribute('role')) annotation.setAttribute('role', 'button')
    if (!annotation.hasAttribute('aria-label')) {
      annotation.setAttribute('aria-label', `Preview ${annotationTitle(annotation)}`)
    }

    annotation.addEventListener('keydown', event => {
      if (event.key !== 'Enter' && event.key !== ' ') return
      event.preventDefault()
      openInlinePreview(annotation)
    })
  })
}

function installGlobalHandlers() {
  // Capture phase so we intercept before the pill web component's bubble-phase
  // handler dispatches lesson-open. Annotation clicks show the inline preview
  // and stop propagation — the full lesson pane only opens via "Open full lesson".
  document.addEventListener('click', event => {
    const annotation = event.target.closest?.('.reader-annotation')
    if (annotation) {
      event.stopPropagation()
      openInlinePreview(annotation)
      return
    }

    if (!event.target.closest?.('.reader-inline-preview')) {
      closeExistingPreviews()
    }
  }, { capture: true })

  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') closeExistingPreviews()
    if (event.key.toLowerCase() === 'f' && !event.altKey && !event.ctrlKey && !event.metaKey) {
      const tag = document.activeElement?.tagName?.toLowerCase()
      if (tag === 'input' || tag === 'textarea' || tag === 'select') return
      setFocusMode(!focusMode)
    }
  })
}

function observeResults() {
  if (!results) return
  const observer = new MutationObserver(mutations => {
    for (const mutation of mutations) {
      mutation.addedNodes.forEach(node => {
        if (node.nodeType === Node.ELEMENT_NODE) enhanceAnnotations(node)
      })
    }
    ensureToolbar()
    scheduleViewportFocusBlock()
  })
  observer.observe(results, { childList: true, subtree: true })
  enhanceAnnotations(results)
}

function init() {
  applyMode()
  setFocusMode(focusMode)
  ensureToolbar()
  syncToolbar()
  observeResults()
  installGlobalHandlers()
  document.addEventListener('mnemosyne:language-changed', syncToolbar)
  document.addEventListener('mnemosyne:adaptive-reader-changed', syncToolbar)
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init, { once: true })
} else {
  init()
}
