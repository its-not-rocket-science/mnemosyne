/*
  Adaptive reader memory layer.

  Status bands prioritize persisted review outcomes when available and use
  local recency/decay as a fallback. This keeps the Memory Map grounded in
  real learner interactions while still behaving sensibly offline.

  Server-backed when available, local-first when offline:
  - local memory gives immediate UI adaptation
  - /dashboard seeds memory from persisted FSRS UserKnowledge rows
  - explicit actions queue review events through the existing offline queue
  - reinforcement mode shows weak/fading memory and hides strong memory
*/

import { getAuthHeaders, getUser } from './auth.js'
import { queueReview } from './offline.js'
import { t } from './i18n.js'
import { makeHelpButton } from './help-popover.js'
import { API_BASE } from './config.js'
import { computeAdaptiveProfile } from './adaptive-policy.js'

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
    labelKey: 'adaptive_memory_weak',
    strength: 0.25,
    decayRate: 0.85,
    quality: 1,
    reviewState: 'again',
  },
  learning: {
    labelKey: 'adaptive_memory_learning',
    strength: 0.58,
    decayRate: 0.45,
    quality: 3,
    reviewState: 'hard',
  },
  known: {
    labelKey: 'adaptive_memory_known',
    strength: 0.92,
    decayRate: 0.18,
    quality: 5,
    reviewState: 'easy',
  },
}

let adaptiveEnabled = localStorage.getItem(SETTINGS_KEY) !== 'false'
let reinforcementEnabled = localStorage.getItem(REINFORCEMENT_KEY) === 'true'
let memory = readMemory()
let dashboardSyncedAt = null
const ADAPTIVE_OVERRIDE_KEY = 'mnemosyne.reader.adaptive.overrides.v1'

const ANNOTATION_CATEGORIES = [
  'vocabulary', 'grammar', 'translations', 'pronunciation',
  'cultural_notes', 'nuance', 'memory_map_status', 'difficulty_hints',
]

const MODE_DEFAULTS = {
  subtle:   { vocabulary:true, grammar:false, translations:false, pronunciation:false, cultural_notes:false, nuance:false, memory_map_status:false, difficulty_hints:false },
  learning: { vocabulary:true, grammar:true,  translations:true,  pronunciation:true,  cultural_notes:false, nuance:true,  memory_map_status:true,  difficulty_hints:true },
  deep:     { vocabulary:true, grammar:true,  translations:true,  pronunciation:true,  cultural_notes:true,  nuance:true,  memory_map_status:true,  difficulty_hints:true },
}

let adaptiveOverrides = readAdaptiveOverrides()
let adaptiveProfile = null

function readMemory() {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')
    if (parsed && typeof parsed === 'object' && Object.keys(parsed).length) return parsed
  } catch {}

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
        source: 'legacy-local',
      })
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(migrated))
    return migrated
  } catch {
    return {}
  }
}




function overrideStorageKey() {
  const userId = getUser()?.id || 'guest'
  return `${ADAPTIVE_OVERRIDE_KEY}.${userId}`
}

function readAdaptiveOverrides() {
  try {
    const parsed = JSON.parse(localStorage.getItem(overrideStorageKey()) || '{}')
    return parsed && typeof parsed === 'object' ? parsed : {}
  } catch {
    return {}
  }
}

function writeAdaptiveOverrides() {
  localStorage.setItem(overrideStorageKey(), JSON.stringify(adaptiveOverrides))
}

function selectedReaderLevel() {
  return localStorage.getItem('mnemosyne.cefr.level') || localStorage.getItem('mn-cefr-level') || ''
}

function computeAdaptiveState() {
  const stats = memoryStats()
  const reviewed = Object.values(memory).filter(hasReviewHistory)
  const totalReviews = reviewed.reduce((n, r) => n + Number(r.totalReviews || 0), 0)
  const successes = reviewed.reduce((n, r) => n + Number(r.successfulReviews || 0), 0)
  const accuracy = totalReviews > 0 ? successes / totalReviews : 0.5
  adaptiveProfile = computeAdaptiveProfile({
    level: selectedReaderLevel(),
    memory: stats,
    reviews: { total: totalReviews, accuracy },
    annotationUsage: reviewed.length,
  })
  return adaptiveProfile
}

function effectiveAdaptiveValue(key) {
  return adaptiveOverrides[key] || adaptiveProfile?.[key]
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
    annotation.dataset.object_id ||
    annotation.dataset.annotationId ||
    annotation.dataset.canonical ||
    `${annotation.dataset.type || 'annotation'}:${annotation.textContent?.trim() || ''}`
}

function annotationObjectId(annotation) {
  return annotation.dataset.objectId || annotation.dataset.object_id || annotation.dataset.annotationId || null
}

function buildMemoryRecord({ actionKey, label, type, objectId, action, source = 'local' }) {
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
    source,
    syncedAt: source === 'server' ? new Date(now).toISOString() : null,
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
    source: 'default',
    totalReviews: 0,
    successfulReviews: 0,
    failedReviews: 0,
    syncedAt: null,
  }
}

function currentStrength(record) {
  if (!record?.lastReviewed) return record?.strength ?? 0.5
  const elapsedDays = Math.max(0, (Date.now() - Date.parse(record.lastReviewed)) / DAY_MS)
  const rate = Number.isFinite(record.decayRate) ? record.decayRate : 0.5
  return Math.max(0, Math.min(1, (record.strength ?? 0.5) * Math.exp(-rate * elapsedDays)))
}

function nextReviewAt(fromMs, strength, decayRate) {
  const target = 0.62
  if (strength <= target) return fromMs
  const rate = Math.max(decayRate || 0.5, 0.01)
  const days = Math.log(strength / target) / rate
  return fromMs + Math.max(0, days) * DAY_MS
}

// UI banding uses inferred strength only; no direct correctness signal is read here.
function memoryBand(strength) {
  if (strength >= 0.82) return 'strong'
  if (strength >= 0.55) return 'fading'
  return 'weak'
}

function memoryFor(annotation) {
  const key = annotationKey(annotation)
  return memory[key] || defaultMemory(annotation)
}

// Maps dashboard status/mastery into local action buckets for UI adaptation.
// This consumes FSRS-derived probabilities, not explicit drill correctness events.
function actionFromDashboardStatus(status, score) {
  if (status === 'mastered' || score >= 0.82) return 'known'
  if (status === 'new' || status === 'forgotten' || score < 0.55) return 'weak'
  return 'learning'
}

function decayRateFromScore(score) {
  if (score >= 0.82) return 0.18
  if (score >= 0.55) return 0.45
  return 0.85
}

function maybeApplyServerRecord(obj) {
  const key = obj.object_id
  if (!key) return

  const score = Number.isFinite(obj.mastery_score) ? obj.mastery_score : 0.5
  const local = memory[key]
  const serverSeenMs = obj.last_seen ? Date.parse(obj.last_seen) : 0
  const localSeenMs = local?.lastReviewed ? Date.parse(local.lastReviewed) : 0

  // Do not overwrite fresher local user actions that have not yet synced.
  if (local && local.source !== 'server' && localSeenMs > serverSeenMs) return

  const actionKey = actionFromDashboardStatus(obj.status, score)
  memory[key] = {
    action: actionKey,
    strength: Math.max(0, Math.min(1, score)),
    lastReviewed: obj.last_seen || new Date().toISOString(),
    nextReview: obj.due_at || new Date().toISOString(),
    decayRate: decayRateFromScore(score),
    label: local?.label || '',
    type: local?.type || '',
    objectId: key,
    totalReviews: obj.total_reviews || 0,
    successfulReviews: obj.successful_reviews || 0,
    failedReviews: obj.failed_reviews || 0,
    source: 'server',
    syncedAt: new Date().toISOString(),
  }
}

function hasReviewHistory(record) {
  return Number(record?.totalReviews || 0) > 0
}

function isDue(record) {
  const dueAt = record?.nextReview ? Date.parse(record.nextReview) : NaN
  return Number.isFinite(dueAt) && dueAt <= Date.now()
}

function memoryBandFromRecord(record) {
  const strength = currentStrength(record)
  const successes = Number(record?.successfulReviews || 0)
  const failures = Number(record?.failedReviews || 0)
  const hasHistory = hasReviewHistory(record)
  const due = isDue(record)

  if (!hasHistory) {
    if (strength < 0.55) return 'weak'
    if (due || strength < 0.82) return 'fading'
    return 'strong'
  }

  if (successes < 2 || failures > successes) return 'weak'
  if (due || failures > 0 || strength < 0.82) return 'fading'
  return 'strong'
}

async function syncServerMemory() {
  try {
    const response = await fetch(`${API_BASE}/dashboard`, { headers: getAuthHeaders() })
    if (!response.ok) return
    const dashboard = await response.json()
    for (const bucket of ['known', 'weak', 'new', 'due_for_review']) {
      for (const obj of dashboard[bucket] || []) maybeApplyServerRecord(obj)
    }
    dashboardSyncedAt = new Date()
    writeMemory()
    enhanceAll()
  } catch {
    // Offline/local-only is expected during development and PWA use.
  }
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
  } catch {}
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
    source: 'local',
  })
  memory[key] = record
  writeMemory()
  applyAnnotationMemory(annotation)
  applyAdaptiveVisibility()
  renderMemoryMinimap()
  renderIntelligenceSummary()
  queueMemoryReview(annotation, actionKey, record)
  announce(`${record.label || 'Annotation'} marked ${t(action.labelKey).toLowerCase()}`)
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

function computeTier(annotation) {
  const band  = annotation.dataset.memoryBand  // set by applyAnnotationMemory
  if (band === 'strong') return 3
  if (band === 'weak')   return 1
  // fading or unknown: use type/level to split primary vs secondary
  const level = numericLevel(annotation)
  return level === 2 ? 2 : 1
}

function applyAnnotationMemory(annotation) {
  const record = memoryFor(annotation)
  const strength = currentStrength(record)
  const band = memoryBandFromRecord(record)

  annotation.dataset.memoryStrength = strength.toFixed(2)
  annotation.dataset.memoryBand = band
  annotation.dataset.memoryAction = record.action || 'learning'
  annotation.dataset.memorySource = record.source || 'default'

  annotation.classList.toggle('reader-annotation--memory-strong', band === 'strong')
  annotation.classList.toggle('reader-annotation--memory-fading', band === 'fading')
  annotation.classList.toggle('reader-annotation--memory-weak', band === 'weak')
  annotation.classList.toggle('reader-annotation--known', band === 'strong')
  annotation.classList.toggle('reader-annotation--weak', band === 'weak')
  annotation.classList.toggle('reader-annotation--learning', band === 'fading')

  if (band === 'strong') {
    annotation.dataset.adaptiveReason = 'known'
    annotation.title = t('adaptive_hidden_known')
  } else {
    delete annotation.dataset.adaptiveReason
    annotation.removeAttribute('title')
  }

  annotation.dataset.tier = String(computeTier(annotation))
}

function updateQuietBadge() {
  const quietCount = document.querySelectorAll('.reader-annotation[data-adaptive-reason="known"]').length
  let badge = document.querySelector('#reader-quiet-badge')

  if (quietCount === 0) {
    badge?.remove()
    return
  }

  const anchor = document.querySelector('#reader-control-bar') || document.querySelector('#reader-adaptive-toolbar')
  if (!anchor) return

  if (!badge) {
    badge = document.createElement('p')
    badge.id = 'reader-quiet-badge'
    badge.className = 'reader-quiet-badge'
    badge.setAttribute('aria-live', 'polite')

    const countEl = document.createElement('span')
    countEl.className = 'reader-quiet-badge__count'

    const revealBtn = document.createElement('button')
    revealBtn.type = 'button'
    revealBtn.className = 'reader-quiet-badge__reveal'
    revealBtn.setAttribute('aria-pressed', 'false')
    revealBtn.dataset.i18n = 'adaptive_quiet_reveal'
    revealBtn.textContent = t('adaptive_quiet_reveal')
    revealBtn.addEventListener('click', () => {
      const revealing = document.body.toggleAttribute('data-reveal-known')
      revealBtn.setAttribute('aria-pressed', String(revealing))
      const key = revealing ? 'adaptive_quiet_hide' : 'adaptive_quiet_reveal'
      revealBtn.dataset.i18n = key
      revealBtn.textContent = t(key)
    })

    badge.append(countEl, revealBtn)
    anchor.insertAdjacentElement('afterend', badge)
  }

  const countEl = badge.querySelector('.reader-quiet-badge__count')
  if (countEl) {
    countEl.textContent = t('adaptive_quiet_count').replace('{n}', quietCount)
    countEl.dataset.i18n = 'adaptive_quiet_count'
    countEl.dataset.i18nCount = String(quietCount)
  }
}

function readerMode() {
  return localStorage.getItem('mnemosyne.reader.annotationMode') || 'learning'
}

function normalizedType(annotation) {
  return String(annotation.dataset.type || '').toLowerCase()
}

function categoryEnabled(category) {
  const mode = readerMode()
  const defaults = MODE_DEFAULTS[mode] || MODE_DEFAULTS.learning
  return adaptiveOverrides[category] ?? defaults[category] ?? true
}

function isCategoryVisible(annotation, category) {
  const type = normalizedType(annotation)
  if (category === 'vocabulary') return ['vocabulary','vocab','word','word_form','lexical_item'].includes(type)
  if (category === 'grammar') return ['grammar','syntax','morphology','conjugation','agreement','grammar_point'].includes(type)
  if (category === 'translations') return ['translation','translations'].includes(type)
  if (category === 'pronunciation') return ['pronunciation','phonetics'].includes(type)
  if (category === 'cultural_notes') return ['cultural_note','culture','cultural'].includes(type)
  if (category === 'nuance') return ['nuance','nuance_or_style','phrase_family','idiom','literary_device'].includes(type)
  if (category === 'memory_map_status') return false
  if (category === 'difficulty_hints') return false
  return false
}

function flashDifficultyAdjustment(mode) {
  const existing = document.querySelector('.reader-difficulty-toast')
  existing?.remove()

  const key = { flow: 'diff_flow', fatigue: 'diff_fatigue', overload: 'diff_overload' }[mode]
  if (!key) return

  const toast = document.createElement('p')
  toast.className = 'reader-difficulty-toast'
  toast.setAttribute('role', 'status')
  toast.setAttribute('aria-live', 'polite')
  toast.textContent = t(key)
  document.body.appendChild(toast)
  announce(t(key))
  toast.addEventListener('animationend', () => toast.remove(), { once: true })
}

function applyAdaptiveVisibility() {
  computeAdaptiveState()
  document.body.classList.toggle('reader-adaptive-enabled', adaptiveEnabled)
  document.body.classList.toggle('reader-reinforcement-enabled', reinforcementEnabled)

  document.querySelectorAll('.reader-annotation').forEach(annotation => {
    applyAnnotationMemory(annotation)
    const record = memoryFor(annotation)
    const strength = currentStrength(record)
    const level = numericLevel(annotation)
    const band = memoryBandFromRecord(record)

    const density = effectiveAdaptiveValue('annotationDensity')
    const quietThreshold = density === 'guided' ? 0.92 : density === 'light' ? 0.7 : 0.82
    const shouldQuiet = adaptiveEnabled && strength >= quietThreshold && level <= 2
    const shouldHideForReinforcement = reinforcementEnabled && band === 'strong'
    const categoryHidden = ANNOTATION_CATEGORIES.some(cat => !categoryEnabled(cat) && isCategoryVisible(annotation, cat))

    annotation.toggleAttribute('data-adaptively-quiet', shouldQuiet)
    annotation.toggleAttribute('data-reinforcement-hidden', shouldHideForReinforcement)
    annotation.toggleAttribute('data-category-hidden', categoryHidden)
  })
  syncToolbar()
  updateQuietBadge()
}

function populateSystemBody(container) {
  // Memory group: adaptive toggle + reinforcement
  const memGroup = document.createElement('div')
  memGroup.className = 'reader-ctrl__system-group'

  const memLabel = document.createElement('span')
  memLabel.className = 'reader-ctrl__system-label'
  memLabel.dataset.i18n = 'adaptive_reader_label'
  memLabel.textContent = t('adaptive_reader_label')
  memLabel.setAttribute('aria-hidden', 'true')

  const toggle = document.createElement('button')
  toggle.id = 'reader-adaptive-toggle'
  toggle.type = 'button'
  toggle.className = 'reader-adaptive-toggle'
  toggle.addEventListener('click', () => {
    adaptiveEnabled = !adaptiveEnabled
    localStorage.setItem(SETTINGS_KEY, String(adaptiveEnabled))
    applyAdaptiveVisibility()
    renderMemoryMinimap()
    renderIntelligenceSummary()
    announce(adaptiveEnabled ? t('adaptive_reader_on') : t('adaptive_reader_off'))
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
    renderIntelligenceSummary()
    announce(reinforcementEnabled ? t('adaptive_reinforcement_on') : t('adaptive_reinforcement'))
  })

  memGroup.append(memLabel, toggle, reinforce)

  const categoryGroup = document.createElement('fieldset')
  categoryGroup.className = 'reader-ctrl__system-group reader-ctrl__system-group--categories'
  const legend = document.createElement('legend')
  legend.dataset.i18n = 'reader_adv_categories_title'
  legend.textContent = t('reader_adv_categories_title')
  categoryGroup.appendChild(legend)

  const modeHint = document.createElement('p')
  modeHint.className = 'reader-ctrl__hint'
  modeHint.dataset.i18n = 'reader_adv_mode_hint'
  modeHint.textContent = t('reader_adv_mode_hint')
  categoryGroup.appendChild(modeHint)

  for (const cat of ANNOTATION_CATEGORIES) {
    const label = document.createElement('label')
    const cb = document.createElement('input')
    cb.type = 'checkbox'
    cb.checked = categoryEnabled(cat)
    cb.addEventListener('change', () => { adaptiveOverrides[cat] = cb.checked; writeAdaptiveOverrides(); applyAdaptiveVisibility() })
    const text = document.createElement('span')
    text.dataset.i18n = `reader_adv_${cat}_label`
    text.textContent = t(`reader_adv_${cat}_label`)
    label.append(cb, text)
    categoryGroup.appendChild(label)
  }

  // Action group: sync + reset — pushed to end
  const actionGroup = document.createElement('div')
  actionGroup.className = 'reader-ctrl__system-group reader-ctrl__system-group--end'

  const sync = document.createElement('button')
  sync.type = 'button'
  sync.className = 'reader-adaptive-sync'
  sync.dataset.i18n = 'adaptive_sync'
  sync.textContent = t('adaptive_sync')
  sync.addEventListener('click', async () => {
    await syncServerMemory()
    announce(dashboardSyncedAt ? t('adaptive_synced') : t('adaptive_local_memory'))
  })

  const reset = document.createElement('button')
  reset.type = 'button'
  reset.className = 'reader-adaptive-reset'
  reset.dataset.i18n = 'adaptive_reset'
  reset.textContent = t('adaptive_reset')
  reset.addEventListener('click', () => {
    memory = {}
    writeMemory()
    document.querySelectorAll('.reader-annotation').forEach(applyAnnotationMemory)
    applyAdaptiveVisibility()
    renderMemoryMinimap()
    renderIntelligenceSummary()
    announce(t('adaptive_reset'))
  })

  const override = document.createElement('select')
  override.className = 'reader-adaptive-override'
  ;['', 'guided', 'balanced', 'light'].forEach(val => {
    const opt = document.createElement('option')
    opt.value = val
    opt.textContent = val ? t(`adaptive_path_${val}`) : t('adaptive_on')
    override.appendChild(opt)
  })
  override.value = adaptiveOverrides.annotationDensity || ''
  override.addEventListener('change', () => {
    if (override.value) adaptiveOverrides.annotationDensity = override.value
    else delete adaptiveOverrides.annotationDensity
    writeAdaptiveOverrides()
    applyAdaptiveVisibility()
    renderIntelligenceSummary()
  })
  const resetModeDefaults = document.createElement('button')
  resetModeDefaults.type = 'button'
  resetModeDefaults.dataset.i18n = 'reader_adv_reset_mode_defaults'
  resetModeDefaults.textContent = t('reader_adv_reset_mode_defaults')
  resetModeDefaults.addEventListener('click', () => {
    const mode = readerMode()
    const defaults = MODE_DEFAULTS[mode] || MODE_DEFAULTS.learning
    for (const cat of ANNOTATION_CATEGORIES) adaptiveOverrides[cat] = defaults[cat]
    writeAdaptiveOverrides()
    categoryGroup.querySelectorAll('input[type=checkbox]').forEach((cb, i) => { cb.checked = defaults[ANNOTATION_CATEGORIES[i]] })
    applyAdaptiveVisibility()
    announce(t('reader_adv_reset_mode_defaults'))
  })

  actionGroup.append(override, resetModeDefaults, sync, reset)
  container.append(memGroup, categoryGroup, actionGroup)
}

function ensureToolbar() {
  // Prefer the unified bar's system-body slot (created by reading-experience.js)
  const systemBody = document.querySelector('#reader-system-body')
  if (systemBody) {
    if (!systemBody.querySelector('#reader-adaptive-toggle')) populateSystemBody(systemBody)
    return systemBody
  }

  // Fallback: standalone toolbar when reading-experience.js is absent
  if (!resultsSection) return null
  let toolbar = document.querySelector('#reader-adaptive-toolbar')
  if (toolbar) return toolbar

  toolbar = document.createElement('section')
  toolbar.id = 'reader-adaptive-toolbar'
  toolbar.className = 'reader-adaptive-toolbar reader-ctrl__system-body'
  toolbar.setAttribute('aria-label', 'Adaptive learning controls')
  toolbar.setAttribute('role', 'group')
  populateSystemBody(toolbar)

  const controlBar = document.querySelector('#reader-control-bar')
  if (controlBar) controlBar.insertAdjacentElement('afterend', toolbar)
  else resultsSection.prepend(toolbar)
  return toolbar
}

function syncToolbar() {
  const toolbar = ensureToolbar()
  if (!toolbar) return

  const toggle = toolbar.querySelector('#reader-adaptive-toggle')
  if (toggle) {
    const key = adaptiveEnabled ? 'adaptive_reader_on' : 'adaptive_reader_off'
    toggle.dataset.i18n = key
    toggle.textContent = t(key)
    toggle.setAttribute('aria-pressed', String(adaptiveEnabled))
    toggle.classList.toggle('reader-adaptive-toggle--active', adaptiveEnabled)
  }

  const reinforce = toolbar.querySelector('#reader-reinforcement-toggle')
  if (reinforce) {
    const key = reinforcementEnabled ? 'adaptive_reinforcement_on' : 'adaptive_reinforcement'
    reinforce.dataset.i18n = key
    reinforce.textContent = t(key)
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
    btn.dataset.i18n = action.labelKey
    btn.textContent = t(action.labelKey)
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
    const source = record.source === 'server' ? t('adaptive_synced') : t('adaptive_local_memory')
    strengthEl.textContent = next
      ? t('adaptive_exposure_status_next').replace('{pct}', pct).replace('{date}', next.toLocaleDateString()).replace('{source}', source)
      : t('adaptive_exposure_status').replace('{pct}', pct).replace('{source}', source)
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

function memoryStats() {
  const annotations = Array.from(results?.querySelectorAll('.reader-annotation') || [])
  const stats = { strong: 0, fading: 0, weak: 0, total: annotations.length }
  for (const annotation of annotations) {
    const band = memoryBandFromRecord(memoryFor(annotation))
    stats[band] += 1
  }
  return stats
}

function renderIntelligenceSummary() {
  if (!resultsSection) return
  let summary = document.querySelector('#reader-intelligence-summary')
  if (!summary) {
    summary = document.createElement('aside')
    summary.id = 'reader-intelligence-summary'
    summary.className = 'reader-intelligence-summary'
    summary.setAttribute('aria-label', t('adaptive_summary_aria'))

    // Help button persists across re-renders; stats live in a child div.
    const helpBtn = makeHelpButton('help_intelligence_summary')
    helpBtn.className += ' reader-intelligence-summary__help'
    const statsDiv = document.createElement('div')
    statsDiv.className = 'reader-intelligence-summary__stats'

    const howWorks = document.createElement('details')
    howWorks.className = 'reader-intelligence-summary__how'
    const howWorksSummary = document.createElement('summary')
    howWorksSummary.className = 'reader-intelligence-summary__how-summary'
    howWorksSummary.dataset.i18n = 'adaptive_how_works_label'
    howWorksSummary.textContent = t('adaptive_how_works_label')

    const howWorksBody = document.createElement('div')
    howWorksBody.className = 'reader-intelligence-summary__how-body'
    howWorksBody.innerHTML = `
      <p data-i18n="adaptive_how_works_body">${t('adaptive_how_works_body')}</p>
      <ul>
        <li data-i18n="adaptive_how_works_tracked">${t('adaptive_how_works_tracked')}</li>
        <li data-i18n="adaptive_how_works_status">${t('adaptive_how_works_status')}</li>
        <li data-i18n="adaptive_how_works_progress">${t('adaptive_how_works_progress')}</li>
        <li data-i18n="adaptive_how_works_strengthen">${t('adaptive_how_works_strengthen')}</li>
      </ul>
    `
    howWorks.append(howWorksSummary, howWorksBody)

    summary.append(statsDiv, helpBtn, howWorks)

    const toolbar = document.querySelector('#reader-adaptive-toolbar')
    if (toolbar) toolbar.insertAdjacentElement('afterend', summary)
    else resultsSection.prepend(summary)
  }

  const stats = memoryStats()
  if (!stats.total) {
    summary.hidden = true
    return
  }

  summary.hidden = false
  const syncText = dashboardSyncedAt
    ? `${t('adaptive_synced')} ${dashboardSyncedAt.toLocaleTimeString()}`
    : t('adaptive_memory_fallback')
  const profile = computeAdaptiveState()
  const rawReasons = profile?.reasons || []
  const reasons = rawReasons.map(r => t(`adaptive_reason_${r}`) || r).join(', ')
  const densityVal = effectiveAdaptiveValue('annotationDensity')
  const densityLabel = densityVal ? t(`adaptive_path_${densityVal}`) || densityVal : t('adaptive_path_balanced')

  const statsDiv = summary.querySelector('.reader-intelligence-summary__stats')
  statsDiv.innerHTML = `
    <strong data-i18n="adaptive_memory_map">${t('adaptive_memory_map')}</strong>
    <span><b>${stats.weak}</b> <span data-i18n="adaptive_memory_weak_stat">${t('adaptive_memory_weak_stat')}</span></span>
    <span><b>${stats.fading}</b> <span data-i18n="adaptive_memory_fading_stat">${t('adaptive_memory_fading_stat')}</span></span>
    <span><b>${stats.strong}</b> <span data-i18n="adaptive_memory_strong_stat">${t('adaptive_memory_strong_stat')}</span></span>
    <small>${syncText}</small>
    <small>${t('adaptive_path_label')}: ${densityLabel}${reasons ? ` · ${reasons}` : ''}</small>
  `

  const howWorksSummary = summary.querySelector('.reader-intelligence-summary__how-summary')
  if (howWorksSummary) {
    howWorksSummary.textContent = t('adaptive_how_works_label')
  }

  const howWorksBody = summary.querySelector('.reader-intelligence-summary__how-body')
  if (howWorksBody) {
    howWorksBody.innerHTML = `
      <p data-i18n="adaptive_how_works_body">${t('adaptive_how_works_body')}</p>
      <ul>
        <li data-i18n="adaptive_how_works_tracked">${t('adaptive_how_works_tracked')}</li>
        <li data-i18n="adaptive_how_works_status">${t('adaptive_how_works_status')}</li>
        <li data-i18n="adaptive_how_works_progress">${t('adaptive_how_works_progress')}</li>
        <li data-i18n="adaptive_how_works_strengthen">${t('adaptive_how_works_strengthen')}</li>
      </ul>
    `
  }
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
    const strength = currentStrength(memoryFor(annotation))
    const band = memoryBandFromRecord(memoryFor(annotation))
    if (reinforcementEnabled && band === 'strong') return

    const tick = document.createElement('span')
    tick.className = `annotation-minimap__tick annotation-minimap__tick--memory-${band}`
    tick.style.top = `${(index / total) * 100}%`
    tick.title = t('adaptive_tick_title')
      .replace('{label}', annotation.textContent?.trim() || t('adaptive_annotation_label'))
      .replace('{pct}', Math.round(strength * 100))
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
  renderIntelligenceSummary()
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
    if (changed) {
      renderMemoryMinimap()
      renderIntelligenceSummary()
    }
  })
  observer.observe(results, { childList: true, subtree: true })
}

function init() {
  ensureToolbar()
  syncToolbar()
  enhanceAll()
  observe()
  syncServerMemory()
  document.addEventListener('mnemosyne:language-changed', () => {
    syncToolbar()
    renderIntelligenceSummary()
    updateQuietBadge()
  })
  document.addEventListener('mnemosyne:difficulty-adjusted', ({ detail }) => {
    flashDifficultyAdjustment(detail.mode)
  })
  setInterval(() => {
    applyAdaptiveVisibility()
    renderMemoryMinimap()
    renderIntelligenceSummary()
  }, 60_000)
  setInterval(syncServerMemory, 5 * 60_000)
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init, { once: true })
} else {
  init()
}
