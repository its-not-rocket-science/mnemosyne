/*
  Difficulty modulation layer

  Uses cognitive pacing state plus explicit user feedback to bias which
  /recommend result is chosen. It does not change backend scoring; it re-ranks
  candidates client-side.

  Modes:
  - flow: choose a slightly harder candidate
  - steady: choose closest to backend target centre
  - fatigue: choose a slightly easier candidate
  - overload/recovery: choose the safest candidate
*/

const STORAGE_KEY = 'mnemosyne.reader.difficultyModulation.enabled'
const BIAS_KEY = 'mnemosyne.reader.difficultyModulation.bias'

let enabled = localStorage.getItem(STORAGE_KEY) !== 'false'
let userBias = Number.parseFloat(localStorage.getItem(BIAS_KEY) || '0')
if (!Number.isFinite(userBias)) userBias = 0

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value))
}

function pacingMode() {
  return window.mnemosynePacing?.snapshot?.().mode || 'steady'
}

function targetForMode(mode, min, max) {
  const span = Math.max(max - min, 0.01)
  const center = (min + max) / 2

  if (window.mnemosynePacing?.isOverloaded?.()) return min

  let base
  switch (mode) {
    case 'flow': base = center + span * 0.35; break
    case 'fatigue': base = center - span * 0.35; break
    case 'overload': base = min; break
    case 'steady':
    default: base = center
  }

  return clamp(base + span * userBias, min, max)
}

function candidateDifficulty(item) {
  return Number.isFinite(item?.difficulty) ? item.difficulty : 0.5
}

function chooseRecommendation(data) {
  const sentences = Array.isArray(data?.sentences) ? data.sentences : []
  if (!enabled || sentences.length <= 1) return sentences[0] || null

  const mode = pacingMode()
  const min = Number(data.target_difficulty_min ?? 0.25)
  const max = Number(data.target_difficulty_max ?? 0.75)
  const target = targetForMode(mode, min, max)

  const sorted = [...sentences].sort((a, b) => {
    const da = Math.abs(candidateDifficulty(a) - target)
    const db = Math.abs(candidateDifficulty(b) - target)

    // Preserve continuation preference when close.
    if (Math.abs(da - db) < 0.04) {
      if (a.is_continuation && !b.is_continuation) return -1
      if (!a.is_continuation && b.is_continuation) return 1
    }
    return da - db
  })

  const chosen = sorted[0] || null
  if (chosen) {
    chosen.modulation_mode = mode
    chosen.modulation_target = target
    chosen.modulation_bias = userBias
  }
  return chosen
}

function describeModulation(item) {
  if (!enabled) return 'Difficulty modulation off'
  if (window.mnemosynePacing?.isOverloaded?.()) {
    return 'You seemed overloaded — adjusting to help you recover'
  }

  const mode = item?.modulation_mode || pacingMode()
  const biasNote = userBias > 0.05
    ? ' Your “too easy” feedback is nudging harder.'
    : userBias < -0.05
      ? ' Your “too hard” feedback is easing the path.'
      : ''

  switch (mode) {
    case 'flow': return `Flow detected: nudging slightly harder.${biasNote}`
    case 'fatigue': return `Fatigue detected: easing difficulty.${biasNote}`
    case 'overload': return `Overload detected: choosing the safest next step.${biasNote}`
    default: return `Steady pace: choosing the best level match.${biasNote}`
  }
}

function setEnabled(next) {
  enabled = Boolean(next)
  localStorage.setItem(STORAGE_KEY, String(enabled))
  document.dispatchEvent(new CustomEvent('mnemosyne:difficulty-modulation-changed', {
    detail: { enabled, userBias },
  }))
}

function setBias(nextBias) {
  userBias = clamp(nextBias, -0.3, 0.3)
  localStorage.setItem(BIAS_KEY, String(userBias))
  syncFeedback()
  document.dispatchEvent(new CustomEvent('mnemosyne:difficulty-modulation-changed', {
    detail: { enabled, userBias },
  }))
}

function adjustBias(delta) {
  setBias(userBias + delta)
}

function ensureToggle() {
  const toolbar = document.querySelector('#reader-adaptive-toolbar') ||
                  document.querySelector('#reader-experience-toolbar') ||
                  document.querySelector('#results-toolbar')
  if (!toolbar) return

  if (!document.querySelector('#difficulty-modulation-toggle')) {
    const btn = document.createElement('button')
    btn.id = 'difficulty-modulation-toggle'
    btn.type = 'button'
    btn.className = 'ghost-button ghost-button--small difficulty-modulation-toggle'
    btn.addEventListener('click', () => {
      setEnabled(!enabled)
      syncToggle()
    })
    toolbar.appendChild(btn)
  }

  ensureDifficultyFeedback(toolbar)
  syncToggle()
  syncFeedback()
}

function ensureDifficultyFeedback(toolbar) {
  if (document.querySelector('#difficulty-feedback')) return

  const wrap = document.createElement('div')
  wrap.id = 'difficulty-feedback'
  wrap.className = 'difficulty-feedback'
  wrap.setAttribute('role', 'group')
  wrap.setAttribute('aria-label', 'Adjust difficulty')

  const tooHard = document.createElement('button')
  tooHard.type = 'button'
  tooHard.className = 'ghost-button ghost-button--small difficulty-feedback__btn'
  tooHard.textContent = 'Too hard ↓'
  tooHard.addEventListener('click', () => adjustBias(-0.1))

  const tooEasy = document.createElement('button')
  tooEasy.type = 'button'
  tooEasy.className = 'ghost-button ghost-button--small difficulty-feedback__btn'
  tooEasy.textContent = 'Too easy ↑'
  tooEasy.addEventListener('click', () => adjustBias(0.1))

  const label = document.createElement('span')
  label.className = 'difficulty-feedback__bias'
  label.setAttribute('aria-live', 'polite')

  wrap.append(tooHard, tooEasy, label)
  toolbar.appendChild(wrap)
}

function syncToggle() {
  const btn = document.querySelector('#difficulty-modulation-toggle')
  if (!btn) return
  btn.textContent = enabled ? 'Difficulty: adaptive' : 'Difficulty: fixed'
  btn.setAttribute('aria-pressed', String(enabled))
}

function syncFeedback() {
  const label = document.querySelector('.difficulty-feedback__bias')
  if (!label) return
  if (Math.abs(userBias) < 0.01) label.textContent = 'balanced'
  else label.textContent = userBias > 0 ? `+${userBias.toFixed(1)}` : userBias.toFixed(1)
}

window.mnemosyneDifficulty = {
  chooseRecommendation,
  describeModulation,
  isEnabled: () => enabled,
  setEnabled,
  getBias: () => userBias,
  setBias,
  adjustBias,
}

function init() {
  ensureToggle()
  document.addEventListener('mnemosyne:pacing-updated', ensureToggle)
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init, { once: true })
} else {
  init()
}
