/*
  Adaptive reader mastery layer.

  Adds a lightweight local mastery model on top of the progressive reader:
  - known annotations become visually quiet
  - weak annotations stay prominent
  - learning annotations keep normal scaffolding
  - adaptive mode automatically suppresses lower-level known material

  This is local-first by design. It can be connected to the review API later,
  but it is useful immediately and does not change parser contracts.
*/

const results = document.querySelector('#results')
const resultsSection = document.querySelector('#results-section')
const a11yLive = document.querySelector('#a11y-live')

const STORAGE_KEY = 'mnemosyne.reader.mastery.v1'
const SETTINGS_KEY = 'mnemosyne.reader.adaptive.enabled'

const STATES = {
  weak: 'weak',
  learning: 'learning',
  known: 'known',
}

let adaptiveEnabled = localStorage.getItem(SETTINGS_KEY) !== 'false'
let mastery = readMastery()

function readMastery() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

function writeMastery() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(mastery))
}

function announce(message) {
  if (!a11yLive) return
  a11yLive.textContent = ''
  queueMicrotask(() => { a11yLive.textContent = message })
}

function annotationKey(annotation) {
  return annotation.dataset.objectId ||
    annotation.dataset.annotationId ||
    annotation.dataset.canonical ||
    `${annotation.dataset.type || 'annotation'}:${annotation.textContent?.trim() || ''}`
}

function getState(annotation) {
  return mastery[annotationKey(annotation)]?.state || STATES.learning
}

function setState(annotation, state) {
  const key = annotationKey(annotation)
  mastery[key] = {
    state,
    label: annotation.textContent?.trim() || '',
    type: annotation.dataset.type || annotation.dataset.typeLabel || '',
    updatedAt: new Date().toISOString(),
  }
  writeMastery()
  applyAnnotationState(annotation)
  applyAdaptiveVisibility()
  announce(`${mastery[key].label || 'Annotation'} marked ${state}`)
}

function applyAnnotationState(annotation) {
  const state = getState(annotation)
  annotation.dataset.mastery = state
  annotation.classList.toggle('reader-annotation--known', state === STATES.known)
  annotation.classList.toggle('reader-annotation--weak', state === STATES.weak)
  annotation.classList.toggle('reader-annotation--learning', state === STATES.learning)
}

function numericLevel(annotation) {
  const raw = annotation.dataset.level || annotation.dataset.annotationLevel
  const parsed = Number.parseInt(raw, 10)
  if (Number.isFinite(parsed)) return parsed
  const type = annotation.dataset.type || ''
  if (type === 'vocabulary') return 1
  if (['idiom', 'nuance', 'phrase_family'].includes(type)) return 3
  return 2
}

function applyAdaptiveVisibility() {
  document.body.classList.toggle('reader-adaptive-enabled', adaptiveEnabled)
  document.querySelectorAll('.reader-annotation').forEach(annotation => {
    const state = getState(annotation)
    const level = numericLevel(annotation)
    const shouldQuiet = adaptiveEnabled && state === STATES.known && level <= 2
    annotation.toggleAttribute('data-adaptively-quiet', shouldQuiet)
  })
  syncToolbar()
}

function ensureToolbar() {
  if (!resultsSection) return null
  let toolbar = document.querySelector('#reader-adaptive-toolbar')
  if (toolbar) return toolbar

  toolbar = document.createElement('section')
  toolbar.id = 'reader-adaptive-toolbar'
  toolbar.className = 'reader-adaptive-toolbar'
  toolbar.setAttribute('aria-label', 'Adaptive learning controls')

  const label = document.createElement('span')
  label.className = 'reader-adaptive-toolbar__label'
  label.textContent = 'Adaptive'

  const toggle = document.createElement('button')
  toggle.id = 'reader-adaptive-toggle'
  toggle.type = 'button'
  toggle.className = 'reader-adaptive-toggle'
  toggle.addEventListener('click', () => {
    adaptiveEnabled = !adaptiveEnabled
    localStorage.setItem(SETTINGS_KEY, String(adaptiveEnabled))
    applyAdaptiveVisibility()
    announce(adaptiveEnabled ? 'Adaptive reader on' : 'Adaptive reader off')
  })

  const reset = document.createElement('button')
  reset.type = 'button'
  reset.className = 'reader-adaptive-reset'
  reset.textContent = 'Reset local mastery'
  reset.addEventListener('click', () => {
    mastery = {}
    writeMastery()
    document.querySelectorAll('.reader-annotation').forEach(applyAnnotationState)
    applyAdaptiveVisibility()
    announce('Local annotation mastery reset')
  })

  toolbar.append(label, toggle, reset)

  const experienceToolbar = document.querySelector('#reader-experience-toolbar')
  if (experienceToolbar) {
    experienceToolbar.insertAdjacentElement('afterend', toolbar)
  } else {
    resultsSection.prepend(toolbar)
  }
  return toolbar
}

function syncToolbar() {
  const toolbar = ensureToolbar()
  if (!toolbar) return
  const toggle = toolbar.querySelector('#reader-adaptive-toggle')
  if (toggle) {
    toggle.textContent = adaptiveEnabled ? 'On' : 'Off'
    toggle.setAttribute('aria-pressed', String(adaptiveEnabled))
    toggle.classList.toggle('reader-adaptive-toggle--active', adaptiveEnabled)
  }
}

function buildMasteryControls(annotation) {
  const controls = document.createElement('div')
  controls.className = 'reader-mastery-controls'
  controls.setAttribute('role', 'group')
  controls.setAttribute('aria-label', 'Annotation mastery')

  const configs = [
    ['Weak', STATES.weak],
    ['Learning', STATES.learning],
    ['Known', STATES.known],
  ]

  for (const [label, state] of configs) {
    const btn = document.createElement('button')
    btn.type = 'button'
    btn.className = 'reader-mastery-btn'
    btn.textContent = label
    btn.dataset.masteryState = state
    btn.setAttribute('aria-pressed', String(getState(annotation) === state))
    btn.addEventListener('click', event => {
      event.stopPropagation()
      setState(annotation, state)
      syncPreviewControls(annotation)
    })
    controls.appendChild(btn)
  }

  return controls
}

function syncPreviewControls(annotation) {
  const sentence = annotation.closest('.reader-sentence, .sentence-card')
  const controls = sentence?.querySelector('.reader-mastery-controls')
  if (!controls) return
  const state = getState(annotation)
  controls.querySelectorAll('.reader-mastery-btn').forEach(btn => {
    btn.setAttribute('aria-pressed', String(btn.dataset.masteryState === state))
    btn.classList.toggle('reader-mastery-btn--active', btn.dataset.masteryState === state)
  })
}

function injectControlsIntoPreview(preview, annotation) {
  if (!preview || preview.querySelector('.reader-mastery-controls')) return
  const controls = buildMasteryControls(annotation)
  const actions = preview.querySelector('.reader-inline-preview__actions')
  if (actions) actions.insertAdjacentElement('beforebegin', controls)
  else preview.appendChild(controls)
}

function enhanceAnnotation(annotation) {
  if (annotation.dataset.adaptiveEnhanced === 'true') return
  annotation.dataset.adaptiveEnhanced = 'true'
  applyAnnotationState(annotation)
  annotation.addEventListener('click', () => {
    requestAnimationFrame(() => {
      const sentence = annotation.closest('.reader-sentence, .sentence-card')
      const preview = sentence?.querySelector('.reader-inline-preview')
      injectControlsIntoPreview(preview, annotation)
      syncPreviewControls(annotation)
    })
  })
}

function enhanceAll(root = document) {
  root.querySelectorAll('.reader-annotation').forEach(enhanceAnnotation)
  applyAdaptiveVisibility()
}

function observe() {
  if (!results) return
  const observer = new MutationObserver(mutations => {
    for (const mutation of mutations) {
      mutation.addedNodes.forEach(node => {
        if (node.nodeType === Node.ELEMENT_NODE) enhanceAll(node)
      })
    }
  })
  observer.observe(results, { childList: true, subtree: true })
}

function init() {
  ensureToolbar()
  syncToolbar()
  enhanceAll()
  observe()
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init, { once: true })
} else {
  init()
}
