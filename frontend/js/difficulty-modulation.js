/*
  Difficulty modulation layer

  Uses cognitive pacing state to bias which /recommend result is chosen.
  It does not change backend scoring; it re-ranks the returned candidates client-side.

  Modes:
  - flow: choose a slightly harder candidate
  - steady: choose closest to backend target centre
  - fatigue: choose a slightly easier candidate
  - overload: choose the easiest safe candidate
*/

const STORAGE_KEY = 'mnemosyne.reader.difficultyModulation.enabled'

let enabled = localStorage.getItem(STORAGE_KEY) !== 'false'

function pacingMode() {
  return window.mnemosynePacing?.snapshot?.().mode || 'steady'
}

function targetForMode(mode, min, max) {
  const span = Math.max(max - min, 0.01)
  const center = (min + max) / 2

  switch (mode) {
    case 'flow': return center + span * 0.35
    case 'fatigue': return center - span * 0.35
    case 'overload': return min
    case 'steady':
    default: return center
  }
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

    // preserve continuation preference when close
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
  }
  return chosen
}

function describeModulation(item) {
  if (!enabled) return 'Difficulty modulation off'
  const mode = item?.modulation_mode || pacingMode()
  switch (mode) {
    case 'flow': return 'Flow detected: nudging slightly harder'
    case 'fatigue': return 'Fatigue detected: easing difficulty'
    case 'overload': return 'Overload detected: choosing the safest next step'
    default: return 'Steady pace: choosing the best level match'
  }
}

function setEnabled(next) {
  enabled = Boolean(next)
  localStorage.setItem(STORAGE_KEY, String(enabled))
  document.dispatchEvent(new CustomEvent('mnemosyne:difficulty-modulation-changed', {
    detail: { enabled },
  }))
}

function ensureToggle() {
  const toolbar = document.querySelector('#reader-adaptive-toolbar') ||
                  document.querySelector('#reader-experience-toolbar') ||
                  document.querySelector('#results-toolbar')
  if (!toolbar || document.querySelector('#difficulty-modulation-toggle')) return

  const btn = document.createElement('button')
  btn.id = 'difficulty-modulation-toggle'
  btn.type = 'button'
  btn.className = 'ghost-button ghost-button--small difficulty-modulation-toggle'
  btn.addEventListener('click', () => {
    setEnabled(!enabled)
    syncToggle()
  })
  toolbar.appendChild(btn)
  syncToggle()
}

function syncToggle() {
  const btn = document.querySelector('#difficulty-modulation-toggle')
  if (!btn) return
  btn.textContent = enabled ? 'Difficulty: adaptive' : 'Difficulty: fixed'
  btn.setAttribute('aria-pressed', String(enabled))
}

window.mnemosyneDifficulty = {
  chooseRecommendation,
  describeModulation,
  isEnabled: () => enabled,
  setEnabled,
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
