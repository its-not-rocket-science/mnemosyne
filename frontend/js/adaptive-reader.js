/*
  Adaptive reader memory layer.

  This replaces static known/learning/weak mastery with a decaying memory model:
  - strength: 0..1 estimated recall strength now
  - lastReviewed: timestamp of last user signal
  - nextReview: predicted timestamp for reinforcement
  - decayRate: exponential decay rate per day

  It remains local-first, but every explicit memory action is also queued through
  the existing offline review queue contract when an object_id is available.
*/

import { queueReview } from './offline.js'

const results = document.querySelector('#results')
const resultsSection = document.querySelector('#results-section')
const annotationMinimap = document.querySelector('#annotation-minimap')
const a11yLive = document.querySelector('#a11y-live')

const STORAGE_KEY = 'mnemosyne.reader.memory.v1'
const LEGACY_STORAGE_KEY = 'mnemosyne.reader.mastery.v1'
const SETTINGS_KEY = 'mnemosyne.reader.adaptive.enabled'
const REINFORCEMENT_KEY = 'mnemosyne.reader.reinforcement.enabled'

const DAY_MS = 86_400_000

const MEMORY_ACTIONS = {
  weak: {
    label: 'Weak',
    strength: 0.25,
    decayRate: 0.85,
    quality: 1,
    reviewState: 'again',
  },
  learning: {
    label: 'Learning',
    strength: 0.58,
    decayRate: 0.45,
    quality: 3,
    reviewState: 'hard',
  },
  known: {
    label: 'Known',
    strength: 0.92,
    decayRate: 0.18,
    quality: 5,
    reviewState: 'easy',
  },
}

let adaptiveEnabled = localStorage.getItem(SETTINGS_KEY) !== 'false'
let reinforcementEnabled = localStorage.getItem(REINFORCEMENT_KEY) === 'true'
let memory = readMemory()

function readMemory() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')
    if (parsed && typeof parsed === 'object' && Object.keys(parsed).length) return parsed
  } catch {}

  // One-time migration from the earlier static mastery model.
  try {
    const legacy = JSON.parse(localStorage.getItem(LEGACY_STORAGE_KEY) || '{}')
    if (!legacy || typeof legacy !== 'object') return {}
    const migrated = {}
    for (const [key, value] of Object.entries(legacy)) {
      const action = MEMORY_ACTIONS[value?.state] || MEMORY_ACTIONS.learning
      migrated[key] = buildMemoryRecord({
        actionKey: value?.state || 'learning',
        label: value?.label || '',
        type: value?.type || '',
        objectId: value?.objectId || null,
        action,
      })
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(migrated))
    return migrated
  } catch {
    return {}
  }
}

function writeMemory() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(memory))
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

function annotationObjectId(annotation) {
  return annotation.dataset.objectId || annotation.dataset.object_id || annotation.dataset.annotationId || null
}

function buildMemoryRecord({ actionKey, label, type, objectId, action }) {
  const now = Date.now()
  const nextReview = nextReviewAt(now, action.strength, action.decayRate)
  return {
    action: actionKey,
    strength: action.strength,
    lastReviewed: new Date(now).toISOString(),
    nextReview: new Date(nextReview).toISOString(),
    decayRate: action.decayRate,
    label,
    type,
    objectId,
  }
}

function defaultMemory(annotation) {
  return {
    action: 'learning',
    strength: 0.5,
    lastReviewed: null,
    nextReview: new Date(Date.now()).toISOString(),
    decayRate: 0.5,
    label: annotation.textContent?.trim() || '',
    type: annotation.dataset.type || annotation.dataset.typeLabel || '',
    objectId: annotationObjectId(annotation),
  }
}

function currentStrength(record) {
  if (!record?.lastReviewed) return record?.strength ?? 0.5
  const elapsedDays = Math.max(0, (Date.now() - Date.parse(record.lastReviewed)) / DAY_MS)
  const rate = Number.isFinite(record.decayRate) ? record.decayRate : 0.5
  return Math.max(0, Math.min(1, (record.strength ?? 0.5) * Math.exp(-rate * elapsedDays)))
}

function nextReviewAt(fromMs, strength, decayRate) {
  // Predict when memory falls below the fading threshold.
  const target = 0.62
  if (strength <= target) return fromMs
  const rate = Math.max(decayRate || 0.5, 0.01)
  const days = Math.log(strength / target) / rate
  return fromMs + Math.max(0, days) * DAY_MS
}

function memoryBand(strength) {
  if (strength >= 0.82) return 'strong'
  if (strength >= 0.55) return 'fading'
  return 'weak'
}

function memoryFor(annotation) {
  const key = annotationKey(annotation)
  return memory[key] || defaultMemory(annotation)
}

async function queueMemoryReview(annotation, actionKey, record) {
  const objectId = annotationObjectId(annotation)
  if (!objectId) return
  const action = MEMORY_ACTIONS[actionKey]
  try {
    await queueReview({
      object_id: objectId,
      quality: action.quality,
      review_state: action.reviewState,
      queued_at: new Date().toISOString(),
      source: 'adaptive_reader',
      memory_strength: record.strength,
      memory_next_review: record.nextReview,
    })
  } catch {
    // Local memory still succeeds; queue failure should not block the reader.
  }
}

function setMemory(annotation, actionKey) {
  const action = MEMORY_ACTIONS[actionKey] || MEMORY_ACTIONS.learning
  const key = annotationKey(annotation)
  const record = buildMemoryRecord({
    actionKey,
    label: annotation.textContent?.trim() || '',
    type: annotation.dataset.type || annotation.dataset.typeLabel || '',
    objectId: annotationObjectId(annotation),
    action,
  })
  memory[key] = record
  writeMemory()
  applyAnnotationMemory(annotation)
  applyAdaptiveVisibility()
  renderMemoryMinimap()
  queueMemoryReview(annotation, actionKey, record)
  announce(`${record.label || 'Annotation'} marked ${action.label.toLowerCase()}`)
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

function applyAnnotationMemory(annotation) {
  const record = memoryFor(annotation)
  const strength = currentStrength(record)
  const band = memoryBand(strength)

  annotation.dataset.memoryStrength = strength.toFixed(2)
  annotation.dataset.memoryBand = band
  annotation.dataset.memoryAction = record.action || 'learning'

  annotation.classList.toggle('reader-annotation--memory-strong', band === 'strong')
  annotation.classList.toggle('reader-annotation--memory-fading', band === 'fading')
  annotation.classList.toggle('reader-annotation--memory-weak', band === 'weak')

  // Backward-compatible class names for earlier CSS.
  annotation.classList.toggle('reader-annotation--known', band === 'strong')
  annotation.classList.toggle('reader-annotation--weak', band === 'weak')
  annotation.classList.toggle('reader-annotation--learning', band === 'fading')
}

function applyAdaptiveVisibility() {
  document.body.classList.toggle('reader-adaptive-enabled', adaptiveEnabled)
  document.body.classList.toggle('reader-reinforcement-enabled', reinforcementEnabled)

  document.querySelectorAll('.reader-annotation').forEach(annotation => {
    applyAnnotationMemory(annotation)
    const record = memoryFor(annotation)
    const strength = currentStrength(record)
    const level = numericLevel(annotation)
    const band = memoryBand(strength)

    const shouldQuiet = adaptiveEnabled && strength >= 0.82 && level <= 2
    const shouldHideForReinforcement = reinforcementEnabled && band === 'strong'

    annotation.toggleAttribute('data-adaptively-quiet', shouldQuiet)
    annotation.toggleAttribute('data-reinforcement-hidden', shouldHideForReinforcement)
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
    renderMemoryMinimap()
    announce(adaptiveEnabled ? 'Adaptive reader on' : 'Adaptive reader off')
  })

  const reinforce = document.createElement('button')
  reinforce.id = 'reader-reinforcement-toggle'
  reinforce.type = 'button'
  reinforce.className = 'reader-reinforcement-toggle'
  reinforce.addEventListener('click', () => {
    reinforcementEnabled = !reinforcementEnabled
    localStorage.setItem(REINFORCEMENT_KEY, String(reinforcementEnabled))
    applyAdaptiveVisibility()
    renderMemoryMinimap()
    announce(reinforcementEnabled ? 'Reinforcement mode on' : 'Reinforcement mode off')
  })

  const reset = document.createElement('button')
  reset.type = 'button'
  reset.className = 'reader-adaptive-reset'
  reset.textContent = 'Reset memory'
  reset.addEventListener('click', () => {
    memory = {}
    writeMemory()
    document.querySelectorAll('.reader-annotation').forEach(applyAnnotationMemory)
    applyAdaptiveVisibility()
    renderMemoryMinimap()
    announce('Local memory reset')
  })

  toolbar.append(label, toggle, reinforce, reset)

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
    toggle.textContent = adaptiveEnabled ? 'Adaptive on' : 'Adaptive off'
    toggle.setAttribute('aria-pressed', String(adaptiveEnabled))
    toggle.classList.toggle('reader-adaptive-toggle--active', adaptiveEnabled)
  }

  const reinforce = toolbar.querySelector('#reader-reinforcement-toggle')
  if (reinforce) {
    reinforce.textContent = reinforcementEnabled ? 'Reinforcement on' : 'Reinforcement'
    reinforce.setAttribute('aria-pressed', String(reinforcementEnabled))
    reinforce.classList.toggle('reader-reinforcement-toggle--active', reinforcementEnabled)
  }
}

function buildMemoryControls(annotation) {
  const controls = document.createElement('div')
  controls.className = 'reader-mastery-controls reader-memory-controls'
  controls.setAttribute('role', 'group')
  controls.setAttribute('aria-label', 'Annotation memory')

  for (const [actionKey, action] of Object.entries(MEMORY_ACTIONS)) {
    const btn = document.createElement('button')
    btn.type = 'button'
    btn.className = 'reader-mastery-btn reader-memory-btn'
    btn.textContent = action.label
    btn.dataset.memoryAction = actionKey
    btn.setAttribute('aria-pressed', String(memoryFor(annotation).action === actionKey))
    btn.addEventListener('click', event => {
      event.stopPropagation()
      setMemory(annotation, actionKey)
      syncPreviewControls(annotation)
    })
    controls.appendChild(btn)
  }

  const strength = document.createElement('span')
  strength.className = 'reader-memory-strength'
  controls.appendChild(strength)

  return controls
}

function syncPreviewControls(annotation) {
  const sentence = annotation.closest('.reader-sentence, .sentence-card')
  const controls = sentence?.querySelector('.reader-memory-controls')
  if (!controls) return

  const record = memoryFor(annotation)
  const strength = currentStrength(record)
  controls.querySelectorAll('.reader-memory-btn').forEach(btn => {
    const active = btn.dataset.memoryAction === record.action
    btn.setAttribute('aria-pressed', String(active))
    btn.classList.toggle('reader-mastery-btn--active', active)
  })

  const strengthEl = controls.querySelector('.reader-memory-strength')
  if (strengthEl) {
    const pct = Math.round(strength * 100)
    const next = record.nextReview ? new Date(record.nextReview) : null
    strengthEl.textContent = next
      ? `Memory ${pct}% · next ${next.toLocaleDateString()}`
      : `Memory ${pct}%`
  }
}

function injectControlsIntoPreview(preview, annotation) {
  if (!preview || preview.querySelector('.reader-memory-controls')) return
  const controls = buildMemoryControls(annotation)
  const actions = preview.querySelector('.reader-inline-preview__actions')
  if (actions) actions.insertAdjacentElement('beforebegin', controls)
  else preview.appendChild(controls)
  syncPreviewControls(annotation)
}

function renderMemoryMinimap() {
  if (!annotationMinimap || !results) return
  const annotations = Array.from(results.querySelectorAll('.reader-annotation'))
  if (!annotations.length) {
    annotationMinimap.hidden = true
    annotationMinimap.replaceChildren()
    return
  }

  const cards = Array.from(results.querySelectorAll('.reader-sentence, .sentence-card'))
  const total = Math.max(cards.length - 1, 1)
  const frag = document.createDocumentFragment()

  annotations.forEach(annotation => {
    const card = annotation.closest('.reader-sentence, .sentence-card')
    const index = Math.max(0, cards.indexOf(card))
    const record = memoryFor(annotation)
    const strength = currentStrength(record)
    const band = memoryBand(strength)

    const tick = document.createElement('span')
    tick.className = `annotation-minimap__tick annotation-minimap__tick--memory-${band}`
    tick.style.top = `${(index / total) * 100}%`
    tick.title = `${annotation.textContent?.trim() || 'Annotation'} · ${Math.round(strength * 100)}% memory`
    frag.appendChild(tick)
  })

  annotationMinimap.replaceChildren(frag)
  annotationMinimap.hidden = false
}

function enhanceAnnotation(annotation) {
  if (annotation.dataset.adaptiveEnhanced === 'true') return
  annotation.dataset.adaptiveEnhanced = 'true'
  applyAnnotationMemory(annotation)
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
  renderMemoryMinimap()
}

function observe() {
  if (!results) return
  const observer = new MutationObserver(mutations => {
    let changed = false
    for (const mutation of mutations) {
      mutation.addedNodes.forEach(node => {
        if (node.nodeType === Node.ELEMENT_NODE) {
          enhanceAll(node)
          changed = true
        }
      })
    }
    if (changed) renderMemoryMinimap()
  })
  observer.observe(results, { childList: true, subtree: true })
}

function init() {
  ensureToolbar()
  syncToolbar()
  enhanceAll()
  observe()
  // Decay is time-dependent; refresh periodically during long reading sessions.
  setInterval(() => {
    applyAdaptiveVisibility()
    renderMemoryMinimap()
  }, 60_000)
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init, { once: true })
} else {
  init()
}
