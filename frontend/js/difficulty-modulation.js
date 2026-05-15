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
    if (mode !== 'steady') {
      document.dispatchEvent(new CustomEvent('mnemosyne:difficulty-adjusted', {
        detail: { mode, target, bias: userBias },
      }))
    }
  }
  return chosen
}

function describeModulation(item) {
  if (!enabled) return t('adaptive_fixed')
  if (window.mnemosynePacing?.isOverloaded?.()) {
    return t('diff_overloaded')
  }

  const mode = item?.modulation_mode || pacingMode()

  switch (mode) {
    case 'flow': return t('diff_flow')
    case 'fatigue': return t('diff_fatigue')
    case 'overload': return t('diff_overload')
    default: return t('diff_steady')
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

import { t } from './i18n.js'

function ensureBar() {
  if (document.querySelector('#results-adaptive-bar')) return

  const resultsSection = document.querySelector('#results-section')
  if (!resultsSection) return

  const bar = document.createElement('div')
  bar.id = 'results-adaptive-bar'
  bar.className = 'results-adaptive-bar'
  bar.setAttribute('role', 'group')
  bar.setAttribute('aria-label', t('adaptive_heading'))

  bar.innerHTML = `
    <div class="results-adaptive-bar__header">
      <span class="results-adaptive-bar__heading" data-i18n="adaptive_heading"></span>
      <div class="results-adaptive-bar__controls">
        <div class="difficulty-feedback" role="group" aria-label="${t('adaptive_heading')}">
          <button type="button" id="difficulty-too-hard"
                  class="ghost-button ghost-button--small difficulty-feedback__btn"
                  aria-label="${t('adaptive_too_hard')}">
            <span aria-hidden="true">↓</span>
            <span data-i18n="adaptive_too_hard"></span>
          </button>
          <span class="difficulty-feedback__bias" aria-live="polite"></span>
          <button type="button" id="difficulty-too-easy"
                  class="ghost-button ghost-button--small difficulty-feedback__btn"
                  aria-label="${t('adaptive_too_easy')}">
            <span data-i18n="adaptive_too_easy"></span>
            <span aria-hidden="true">↑</span>
          </button>
        </div>
        <button type="button" id="difficulty-modulation-toggle"
                class="ghost-button ghost-button--small difficulty-modulation-toggle"
                aria-pressed="true"></button>
      </div>
    </div>
    <p class="results-adaptive-bar__hint" data-i18n="adaptive_hint"></p>
  `

  resultsSection.appendChild(bar)

  bar.querySelector('#difficulty-too-hard')?.addEventListener('click', () => adjustBias(-0.1))
  bar.querySelector('#difficulty-too-easy')?.addEventListener('click', () => adjustBias(0.1))
  bar.querySelector('#difficulty-modulation-toggle')?.addEventListener('click', () => {
    setEnabled(!enabled)
    syncToggle()
  })

  retranslateBar()
  syncToggle()
  syncFeedback()
}

function retranslateBar() {
  const bar = document.querySelector('#results-adaptive-bar')
  if (!bar) return
  bar.setAttribute('aria-label', t('adaptive_heading'))
  bar.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = t(el.dataset.i18n) })
}

// openDialog retained for API compat — scrolls to the inline bar instead of opening a modal.
function openDialog() {
  ensureBar()
  document.querySelector('#results-adaptive-bar')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  document.dispatchEvent(new CustomEvent('mnemosyne:adaptive-dialog-opened'))
}

function syncToggle() {
  const btn = document.querySelector('#difficulty-modulation-toggle')
  if (!btn) return
  const key = enabled ? 'adaptive_on' : 'adaptive_fixed'
  btn.setAttribute('data-i18n', key)
  btn.textContent = t(key)
  btn.setAttribute('aria-pressed', String(enabled))
}

function syncFeedback() {
  const label = document.querySelector('.difficulty-feedback__bias')
  if (!label) return
  if (Math.abs(userBias) < 0.01) {
    label.setAttribute('data-i18n', 'adaptive_balanced')
    label.textContent = t('adaptive_balanced')
  } else {
    label.removeAttribute('data-i18n')
    label.textContent = userBias > 0 ? `+${userBias.toFixed(1)}` : userBias.toFixed(1)
  }
}

window.mnemosyneDifficulty = {
  chooseRecommendation,
  describeModulation,
  isEnabled: () => enabled,
  setEnabled,
  getBias: () => userBias,
  setBias,
  adjustBias,
  ensureBar,
  openDialog,
}

function init() {
  // Bar is created eagerly when results appear so autonomous-learning.js
  // can find #results-adaptive-bar via MutationObserver.
  const resultsSection = document.querySelector('#results-section')
  if (resultsSection && !resultsSection.hidden) {
    ensureBar()
  }

  const observer = new MutationObserver(() => {
    const rs = document.querySelector('#results-section')
    if (rs && !rs.hidden) {
      ensureBar()
      observer.disconnect()
    }
  })
  observer.observe(document.body, { attributes: true, subtree: true, attributeFilter: ['hidden'] })

  document.addEventListener('mnemosyne:pacing-updated', syncFeedback)
  document.addEventListener('mnemosyne:language-changed', retranslateBar)
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init, { once: true })
} else {
  init()
}
