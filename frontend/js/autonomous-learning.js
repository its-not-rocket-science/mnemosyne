/*
  Autonomous Learning Mode

  Now integrates:
  - difficulty modulation (what to load)
  - cognitive pacing (when to load)
*/

import { getAuthHeaders } from './auth.js'

const API = 'http://localhost:8000'

let enabled = false
let loading = false

const languageSelect = document.querySelector('#language')
const pickerTextarea = document.querySelector('#picker-text')
const pickerUseBtn = document.querySelector('#picker-use-btn')
const resultsSection = document.querySelector('#results-section')

function createToggle() {
  const btn = document.createElement('button')
  btn.className = 'ghost-button'
  btn.textContent = 'Autonomous mode'
  btn.setAttribute('aria-pressed', 'false')

  btn.addEventListener('click', () => {
    enabled = !enabled
    btn.setAttribute('aria-pressed', String(enabled))
    btn.textContent = enabled ? 'Autonomous: on' : 'Autonomous mode'

    if (enabled) preloadNext()
  })

  const toolbar = document.querySelector('#results-toolbar')
  if (toolbar) toolbar.appendChild(btn)
}

async function fetchNext() {
  const lang = languageSelect?.value
  if (!lang) return null

  const res = await fetch(`${API}/recommend?language=${lang}&limit=12`, {
    headers: getAuthHeaders(),
  })

  if (!res.ok) return null
  const data = await res.json()

  return window.mnemosyneDifficulty?.chooseRecommendation?.(data) || data.sentences?.[0] || null
}

function passageText(item) {
  if (!item) return ''
  if (Array.isArray(item.passage)) {
    return item.passage.map(s => s.text).join(' ')
  }
  return item.text
}

async function loadNext() {
  if (!enabled || loading) return
  loading = true

  const next = await fetchNext()
  if (!next) {
    loading = false
    return
  }

  const text = passageText(next)
  if (!text) {
    loading = false
    return
  }

  document.body.classList.add('mnemosyne-transitioning-passage')

  pickerTextarea.value = text
  pickerTextarea.dispatchEvent(new Event('input', { bubbles: true }))
  pickerUseBtn.click()

  if (next.source_document_id) {
    fetch(`${API}/reading/${next.source_document_id}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify({ sentences_read: 1 }),
    }).catch(() => {})
  }

  setTimeout(() => {
    document.body.classList.remove('mnemosyne-transitioning-passage')
  }, 900)

  loading = false
}

function observeEnd() {
  const sentinel = document.createElement('div')
  sentinel.style.height = '1px'

  resultsSection?.appendChild(sentinel)

  const observer = new IntersectionObserver(entries => {
    if (entries[0].isIntersecting && enabled) {
      const delay = window.mnemosynePacing?.getNextDelayMs?.() || 1800
      setTimeout(loadNext, delay)
    }
  }, { threshold: 1 })

  observer.observe(sentinel)
}

function preloadNext() {
  fetchNext().catch(() => {})
}

function init() {
  createToggle()
  observeEnd()
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init, { once: true })
} else {
  init()
}
