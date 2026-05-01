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

  // Secondary: focus + settings disclosure
  const secondary = document.createElement('div')
  secondary.className = 'reader-ctrl__secondary'

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

  secondary.append(focusBtn, settingsBtn)
  row.append(modeGroup, secondary)

  // ── System body — populated by adaptive-reader.js ─────────────────────────
  const systemBody = document.createElement('div')
  systemBody.id = 'reader-system-body'
  systemBody.className = 'reader-ctrl__system-body'
  systemBody.setAttribute('role', 'group')
  systemBody.setAttribute('aria-label', t('reader_settings_aria'))
  systemBody.hidden = true

  bar.append(row, systemBody)
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
}

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

function openInlinePreview(annotation) {
  if (!annotation || annotation.hasAttribute('data-filtered') || annotation.hasAttribute('data-level-filtered')) return

  const sentence = annotation.closest('.reader-sentence, .sentence-card')
  if (!sentence) return

  const existing = sentence.querySelector('.reader-inline-preview')
  if (existing) {
    existing.remove()
    return
  }

  closeExistingPreviews()

  const preview = document.createElement('aside')
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
    // Mark the annotation so the capture handler lets this click through to lesson-open.
    annotation.dataset.openFullLesson = 'true'
    closeInlinePreview(preview, annotation)
    annotation.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }))
  })

  const closeBtn = document.createElement('button')
  closeBtn.type = 'button'
  closeBtn.className = 'ghost-button ghost-button--small reader-inline-preview__close'
  closeBtn.dataset.i18n = 'close_btn_aria'
  closeBtn.textContent = t('close_btn_aria')
  closeBtn.addEventListener('click', () => closeInlinePreview(preview, annotation))

  actions.append(detailBtn, closeBtn)
  preview.append(title, body, actions)
  sentence.appendChild(preview)

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
      if (annotation.dataset.openFullLesson) {
        // "Open full lesson" button set this flag — let click through to lesson-open.
        delete annotation.dataset.openFullLesson
        return
      }
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
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init, { once: true })
} else {
  init()
}
