/*
  Passage transition card

  Fires when the reader reaches the bottom of the current passage.
  Shows a pacing-contextualised reason line plus two actions:
    [Continue reading]  — loads next passage immediately
    [Show alternatives] — expands the recommendations panel

  If Autonomous Mode is enabled, adds a 4-second countdown with a [Pause]
  button. Countdown drives the CSS progress-fill animation; JS updates
  the remaining-seconds label every second.
*/

import { t } from './i18n.js'

const COUNTDOWN_MS = 4000
const resultsSection = document.querySelector('#results-section')
const a11yLive = document.querySelector('#a11y-live')

let card = null
let countdownTimer = null

function announce(msg) {
  if (!a11yLive) return
  a11yLive.textContent = ''
  queueMicrotask(() => { a11yLive.textContent = msg })
}

function escapeHtml(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

function pacingReason() {
  const mode = window.mnemosynePacing?.snapshot?.().mode || 'steady'
  return t(`passage_end_${mode}`) || t('passage_end_steady')
}

function stopCountdown() {
  clearInterval(countdownTimer)
  countdownTimer = null
}

function dismiss() {
  stopCountdown()
  card?.remove()
  card = null
}

function loadNextNow() {
  dismiss()
  window.mnemosyneAutonomous?.loadNext()
}

function showAlternatives() {
  dismiss()
  if (window.mnemosyneRecommended) {
    window.mnemosyneRecommended.show()
    queueMicrotask(() => {
      document.querySelector('#recommended-reading-panel')
        ?.scrollIntoView({ behavior: 'smooth', block: 'start', inline: 'nearest' })
    })
    return
  }
  const panel = document.querySelector('#recommended-reading-panel')
  if (!panel) return
  panel.hidden = false
  panel.scrollIntoView({ behavior: 'smooth', block: 'start', inline: 'nearest' })
}

function buildCard(autonomousEnabled) {
  const el = document.createElement('aside')
  el.className = 'passage-transition-card'
  el.setAttribute('role', 'status')
  el.setAttribute('aria-label', t('passage_end_heading'))

  el.innerHTML = `
    <p class="passage-transition__reason">${escapeHtml(pacingReason())}</p>
    <div class="passage-transition__actions">
      <button type="button" class="button-primary passage-transition__continue">
        ${escapeHtml(t('passage_end_continue'))}
      </button>
      <button type="button" class="ghost-button passage-transition__alternatives">
        ${escapeHtml(t('passage_end_alternatives'))}
      </button>
    </div>
    ${autonomousEnabled ? `
    <div class="passage-transition__auto">
      <span class="passage-transition__countdown" aria-live="polite" aria-atomic="true"></span>
      <div class="passage-transition__progress" aria-hidden="true">
        <span class="passage-transition__progress-fill"></span>
      </div>
      <button type="button" class="ghost-button ghost-button--small passage-transition__pause">
        ${escapeHtml(t('passage_end_pause'))}
      </button>
    </div>
    ` : ''}
  `

  el.querySelector('.passage-transition__continue').addEventListener('click', loadNextNow)
  el.querySelector('.passage-transition__alternatives').addEventListener('click', showAlternatives)

  if (autonomousEnabled) {
    const countdownEl = el.querySelector('.passage-transition__countdown')
    const fillEl = el.querySelector('.passage-transition__progress-fill')
    const pauseBtn = el.querySelector('.passage-transition__pause')
    let paused = false
    let remaining = COUNTDOWN_MS

    function tick() {
      remaining -= 1000
      const secs = Math.max(0, Math.ceil(remaining / 1000))
      countdownEl.textContent = t('passage_end_loading').replace('{n}', secs)
      if (remaining <= 0) { stopCountdown(); loadNextNow() }
    }

    function beginCountdown() {
      remaining = COUNTDOWN_MS
      countdownEl.textContent = t('passage_end_loading').replace('{n}', COUNTDOWN_MS / 1000)
      fillEl?.classList.remove('passage-transition__progress-fill--running')
      // Trigger reflow so the animation restarts.
      void fillEl?.offsetWidth
      fillEl?.classList.add('passage-transition__progress-fill--running')
      countdownTimer = setInterval(tick, 1000)
      announce(countdownEl.textContent)
    }

    pauseBtn.addEventListener('click', () => {
      paused = !paused
      if (paused) {
        stopCountdown()
        fillEl?.classList.add('passage-transition__progress-fill--paused')
        pauseBtn.textContent = t('passage_end_resume')
        announce(t('passage_end_paused'))
      } else {
        fillEl?.classList.remove('passage-transition__progress-fill--paused')
        beginCountdown()
        pauseBtn.textContent = t('passage_end_pause')
      }
    })

    beginCountdown()
  }

  return el
}

function showTransitionCard({ autonomousEnabled }) {
  // Suppress if the recommended panel is already visible with content
  const recPanel = document.querySelector('#recommended-reading-panel')
  if (recPanel && !recPanel.hidden) return
  dismiss()
  card = buildCard(autonomousEnabled)
  if (resultsSection) {
    resultsSection.insertAdjacentElement('afterend', card)
  } else {
    document.body.appendChild(card)
  }
}

function observeNewPassage() {
  const results = document.querySelector('#results')
  if (!results) return
  new MutationObserver(mutations => {
    if (card && mutations.some(m => m.addedNodes.length)) dismiss()
  }).observe(results, { childList: true })
}

function init() {
  document.addEventListener('mnemosyne:passage-end', ({ detail }) => {
    showTransitionCard({ autonomousEnabled: Boolean(detail?.autonomousEnabled) })
  })
  document.addEventListener('mnemosyne:language-changed', () => {
    if (!card) return
    const autonomousEnabled = card.querySelector('.passage-transition__auto') !== null
    dismiss()
    card = buildCard(autonomousEnabled)
    if (resultsSection) {
      resultsSection.insertAdjacentElement('afterend', card)
    } else {
      document.body.appendChild(card)
    }
  })
  observeNewPassage()
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init, { once: true })
} else {
  init()
}
