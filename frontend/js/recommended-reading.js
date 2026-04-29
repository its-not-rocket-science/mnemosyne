/*
  Adaptive recommended reading panel.

  Uses the existing /recommend endpoint to surface i+1 passages from the user's
  saved/parsed corpus. The panel is intentionally frontend-only: it does not
  alter recommendation logic, and it degrades silently when the user has no
  saved texts or the backend is unavailable.
*/

import { getAuthHeaders } from './auth.js'

const API_BASE = 'http://localhost:8000'

const languageSelect = document.querySelector('#language')
const resultsSection = document.querySelector('#results-section')
const pickerTextarea = document.querySelector('#picker-text')
const pickerUseBtn = document.querySelector('#picker-use-btn')
const a11yLive = document.querySelector('#a11y-live')

let currentRecommendations = []

function announce(message) {
  if (!a11yLive) return
  a11yLive.textContent = ''
  queueMicrotask(() => { a11yLive.textContent = message })
}

function ensurePanel() {
  if (!resultsSection) return null
  let panel = document.querySelector('#recommended-reading-panel')
  if (panel) return panel

  panel = document.createElement('aside')
  panel.id = 'recommended-reading-panel'
  panel.className = 'recommended-reading-panel'
  panel.setAttribute('aria-labelledby', 'recommended-reading-heading')
  panel.hidden = true

  panel.innerHTML = `
    <div class="recommended-reading-panel__header">
      <div>
        <p class="recommended-reading-panel__eyebrow">Adaptive path</p>
        <h3 id="recommended-reading-heading">Recommended next reads</h3>
      </div>
      <button type="button" class="ghost-button ghost-button--small" id="recommended-reading-refresh">
        Refresh
      </button>
    </div>
    <p class="recommended-reading-panel__summary"></p>
    <div class="recommended-reading-list" role="list"></div>
  `

  const adaptiveToolbar = document.querySelector('#reader-adaptive-toolbar')
  const experienceToolbar = document.querySelector('#reader-experience-toolbar')
  const anchor = adaptiveToolbar || experienceToolbar
  if (anchor) anchor.insertAdjacentElement('afterend', panel)
  else resultsSection.prepend(panel)

  panel.querySelector('#recommended-reading-refresh')?.addEventListener('click', loadRecommendations)
  return panel
}

function passageText(item) {
  if (Array.isArray(item.passage) && item.passage.length) {
    return item.passage.map(s => s.text).join(' ')
  }
  return item.text || ''
}

function reasonFor(item) {
  const unknownPct = Math.round((item.unknown_ratio || 0) * 100)
  const parts = []
  if (item.is_continuation) parts.push('continues a text you already started')
  if (unknownPct > 0) parts.push(`${unknownPct}% unfamiliar material`)
  if ((item.grammar_score || 0) > 0.35) parts.push('useful grammar density')
  if (!parts.length) parts.push('close to your current level')
  return parts.join(' · ')
}

function renderRecommendations(data) {
  const panel = ensurePanel()
  if (!panel) return

  const list = panel.querySelector('.recommended-reading-list')
  const summary = panel.querySelector('.recommended-reading-panel__summary')
  currentRecommendations = data?.sentences || []

  if (!currentRecommendations.length) {
    panel.hidden = true
    return
  }

  panel.hidden = false
  summary.textContent = `${data.user_level || 'Current level'} · target difficulty ${Number(data.target_difficulty_min || 0).toFixed(2)}–${Number(data.target_difficulty_max || 0).toFixed(2)} · ${data.total_mastered || 0} mastered`

  const frag = document.createDocumentFragment()
  currentRecommendations.slice(0, 5).forEach((item, index) => {
    const card = document.createElement('article')
    card.className = 'recommended-reading-card'
    card.setAttribute('role', 'listitem')

    const title = item.source_title || (item.is_continuation ? 'Continue reading' : 'Suggested passage')
    const text = passageText(item)
    const focusSentence = item.text || text

    card.innerHTML = `
      <div class="recommended-reading-card__meta">
        <span>${item.is_continuation ? 'Continue' : 'i+1'}</span>
        <span>${item.difficulty_label || 'matched'}</span>
      </div>
      <h4>${escapeHtml(title)}</h4>
      <p class="recommended-reading-card__text">${escapeHtml(focusSentence)}</p>
      <p class="recommended-reading-card__reason">${escapeHtml(reasonFor(item))}</p>
      <div class="recommended-reading-card__actions">
        <button type="button" class="button-primary recommended-reading-card__study" data-index="${index}">
          Study this passage
        </button>
      </div>
    `

    frag.appendChild(card)
  })

  list.replaceChildren(frag)
  list.querySelectorAll('.recommended-reading-card__study').forEach(button => {
    button.addEventListener('click', () => {
      const item = currentRecommendations[Number(button.dataset.index)]
      studyRecommendation(item)
    })
  })
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

function studyRecommendation(item) {
  const text = passageText(item)
  if (!text || !pickerTextarea || !pickerUseBtn) return
  pickerTextarea.value = text
  pickerTextarea.dispatchEvent(new Event('input', { bubbles: true }))
  pickerUseBtn.click()
  announce('Recommended passage loaded')
}

async function loadRecommendations() {
  const language = languageSelect?.value
  const panel = ensurePanel()
  if (!language || !panel) return

  try {
    const response = await fetch(`${API_BASE}/recommend?language=${encodeURIComponent(language)}&limit=8`, {
      headers: getAuthHeaders(),
    })
    if (!response.ok) {
      panel.hidden = true
      return
    }
    const data = await response.json()
    renderRecommendations(data)
  } catch {
    panel.hidden = true
  }
}

function init() {
  ensurePanel()
  languageSelect?.addEventListener('change', loadRecommendations)
  document.addEventListener('mnemosyne:memory-updated', loadRecommendations)
  loadRecommendations()
  setInterval(loadRecommendations, 5 * 60_000)
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init, { once: true })
} else {
  init()
}
