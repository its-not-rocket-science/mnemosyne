/*
  Progressive reading experience behaviour.

  This module is intentionally additive. It does not replace main.js rendering;
  it observes the existing reader DOM and adds:
  - annotation reveal density: subtle / learning / deep
  - focus mode: dims app chrome around the reading surface
  - inline preview cards below clicked inline annotations
  - keyboard support for inline previews
*/

const results = document.querySelector('#results')
const resultsSection = document.querySelector('#results-section')
const a11yLive = document.querySelector('#a11y-live')

const STORAGE_MODE_KEY = 'mnemosyne.reader.annotationMode'
const STORAGE_FOCUS_KEY = 'mnemosyne.reader.focusMode'

const MODES = [
  { value: 'subtle', label: 'Subtle', hint: 'Faint cues only' },
  { value: 'learning', label: 'Learning', hint: 'Labels on hover' },
  { value: 'deep', label: 'Deep', hint: 'Maximum scaffolding' },
]

let currentMode = localStorage.getItem(STORAGE_MODE_KEY) || 'learning'
let focusMode = localStorage.getItem(STORAGE_FOCUS_KEY) === 'true'

function announce(message) {
  if (!a11yLive) return
  a11yLive.textContent = ''
  queueMicrotask(() => { a11yLive.textContent = message })
}

function makeButton({ text, className, pressed, ariaLabel }) {
  const btn = document.createElement('button')
  btn.type = 'button'
  btn.className = className
  btn.textContent = text
  btn.setAttribute('aria-pressed', String(Boolean(pressed)))
  if (ariaLabel) btn.setAttribute('aria-label', ariaLabel)
  return btn
}

function ensureToolbar() {
  if (!resultsSection) return null
  let toolbar = document.querySelector('#reader-experience-toolbar')
  if (toolbar) return toolbar

  toolbar = document.createElement('section')
  toolbar.id = 'reader-experience-toolbar'
  toolbar.className = 'reader-experience-toolbar'
  toolbar.setAttribute('aria-label', 'Reading experience controls')

  const density = document.createElement('div')
  density.className = 'reader-experience-toolbar__group'
  density.setAttribute('role', 'group')
  density.setAttribute('aria-label', 'Annotation reveal density')

  const label = document.createElement('span')
  label.className = 'reader-experience-toolbar__label'
  label.textContent = 'Reveal'
  label.setAttribute('aria-hidden', 'true')
  density.appendChild(label)

  for (const mode of MODES) {
    const btn = makeButton({
      text: mode.label,
      className: 'reader-mode-btn',
      pressed: mode.value === currentMode,
      ariaLabel: `${mode.label} annotation reveal: ${mode.hint}`,
    })
    btn.dataset.mode = mode.value
    btn.title = mode.hint
    btn.addEventListener('click', () => setMode(mode.value))
    density.appendChild(btn)
  }

  const focusBtn = makeButton({
    text: 'Focus mode',
    className: 'reader-focus-btn',
    pressed: focusMode,
    ariaLabel: 'Toggle focus mode',
  })
  focusBtn.id = 'reader-focus-mode-btn'
  focusBtn.addEventListener('click', () => setFocusMode(!focusMode))

  toolbar.append(density, focusBtn)
  resultsSection.prepend(toolbar)
  return toolbar
}

function syncToolbar() {
  const toolbar = ensureToolbar()
  if (!toolbar) return
  toolbar.querySelectorAll('.reader-mode-btn').forEach(btn => {
    const active = btn.dataset.mode === currentMode
    btn.setAttribute('aria-pressed', String(active))
    btn.classList.toggle('reader-mode-btn--active', active)
  })
  const focusBtn = toolbar.querySelector('#reader-focus-mode-btn')
  if (focusBtn) {
    focusBtn.setAttribute('aria-pressed', String(focusMode))
    focusBtn.classList.toggle('reader-focus-btn--active', focusMode)
  }
}

function setMode(mode) {
  if (!MODES.some(m => m.value === mode)) mode = 'learning'
  currentMode = mode
  localStorage.setItem(STORAGE_MODE_KEY, currentMode)
  applyMode()
  syncToolbar()
  announce(`Annotation reveal set to ${mode}`)
}

function setFocusMode(next) {
  focusMode = Boolean(next)
  localStorage.setItem(STORAGE_FOCUS_KEY, String(focusMode))
  document.body.classList.toggle('reader-focus-mode', focusMode)
  syncToolbar()
  announce(focusMode ? 'Focus mode on' : 'Focus mode off')
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
    ? 'Open the detail pane for the full explanation.'
    : 'Use the detail pane for explanation, context, origin and related forms.'
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
  detailBtn.textContent = 'Open full lesson'
  detailBtn.addEventListener('click', () => {
    annotation.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }))
  })

  const closeBtn = document.createElement('button')
  closeBtn.type = 'button'
  closeBtn.className = 'ghost-button ghost-button--small reader-inline-preview__close'
  closeBtn.textContent = 'Close'
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
  document.addEventListener('click', event => {
    const annotation = event.target.closest?.('.reader-annotation')
    if (annotation) {
      openInlinePreview(annotation)
      return
    }

    if (!event.target.closest?.('.reader-inline-preview')) {
      closeExistingPreviews()
    }
  })

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
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init, { once: true })
} else {
  init()
}
