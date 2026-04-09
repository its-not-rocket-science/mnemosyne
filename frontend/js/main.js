import '../components/mnemosyne-pill.js'
import '../components/mnemosyne-modal.js'

const API_BASE = 'http://localhost:8000'

// ── DOM references ────────────────────────────────────────────────────────────

const form           = document.querySelector('#parse-form')
const languageSelect = document.querySelector('#language')
const sourceUrlInput = document.querySelector('#source-url')
const textarea       = document.querySelector('#source-text')
const submitButton   = document.querySelector('#parse-submit')
const results        = document.querySelector('#results')
const resultsEmpty   = document.querySelector('.results-empty')
const status         = document.querySelector('#status')
const modal          = document.querySelector('#lesson-modal')

// Carries FSRS state across multiple ratings of the same object in one session.
const reviewStateByObject = new Map()


// ── Status helper ─────────────────────────────────────────────────────────────
// Writes to the role="status" live region.  The clear-then-set pattern ensures
// screen readers announce the new message even when the text is unchanged.

function setStatus(message, state = 'idle') {
  status.textContent = ''
  queueMicrotask(() => {
    status.textContent = message
    status.dataset.state = state  // 'idle' | 'busy' | 'error'
  })
}


// ── Results empty state ───────────────────────────────────────────────────────
// resultsEmpty is always an orphaned node that is moved in/out of #results
// by the helpers below.  It is never cloned, so one reference suffices.

function showResultsMessage(message) {
  resultsEmpty.textContent = message
  // replaceChildren re-parents the node if it was detached; no-op if already there.
  results.replaceChildren(resultsEmpty)
}

function hideResultsMessage() {
  // Remove from DOM without destroying the reference.
  resultsEmpty.remove()
}


// ── Parse form ────────────────────────────────────────────────────────────────

form.addEventListener('submit', async (event) => {
  event.preventDefault()

  const text = textarea.value.trim()
  if (!text) {
    setStatus('Please enter some text to parse.', 'error')
    textarea.focus()
    return
  }

  // Reset previous session.
  reviewStateByObject.clear()
  showResultsMessage('Loading…')
  setStatus('Parsing text…', 'busy')

  submitButton.disabled = true
  submitButton.setAttribute('aria-busy', 'true')
  const originalLabel = submitButton.textContent.trim()
  submitButton.textContent = 'Parsing…'

  try {
    const payload = {
      language:   languageSelect.value,
      text,
      source_url: sourceUrlInput?.value.trim() || null,
    }

    const response = await fetch(`${API_BASE}/parse`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    })

    if (!response.ok) {
      const body = await response.json().catch(() => null)
      throw new Error(body?.detail ?? `Parse failed (${response.status})`)
    }

    const data = await response.json()

    if (data.sentences.length === 0) {
      showResultsMessage('No learnable items found — try pasting a longer passage.')
      setStatus('No sentences found.')
      return
    }

    renderResults(data.sentences, payload.language)
    const n = data.sentences.length
    setStatus(`${n} sentence${n !== 1 ? 's' : ''} parsed. Use Tab to navigate the items.`)
  } catch (error) {
    showResultsMessage('An error occurred. Please try again.')
    setStatus(error instanceof Error ? error.message : 'Parsing failed.', 'error')
  } finally {
    submitButton.disabled = false
    submitButton.removeAttribute('aria-busy')
    submitButton.textContent = originalLabel
  }
})


// ── Lesson open ───────────────────────────────────────────────────────────────
// Delegated to #results so it catches events from all pill descendants.
// lesson-open is dispatched with composed:true so it crosses the shadow-DOM
// boundary and reaches the light DOM.

results.addEventListener('lesson-open', async (event) => {
  const { objectId, language } = event.detail

  setStatus('Loading lesson…', 'busy')

  try {
    const url = `${API_BASE}/lesson/${encodeURIComponent(objectId)}?language=${encodeURIComponent(language)}`
    const response = await fetch(url)

    if (!response.ok) {
      const body = await response.json().catch(() => null)
      throw new Error(body?.detail ?? `Lesson not available (${response.status})`)
    }

    const lesson = await response.json()

    modal.open({
      title:       lesson.title,
      html:        markdownToHtml(lesson.content_markdown),
      objectId:    lesson.id,
      exampleText: lesson.example_text,
      onRate:      submitReview,
      onSpeak:     (text) => speakText(text, language),
    })

    // Announce after the modal opens; the modal itself announces its title
    // via role="dialog" + aria-labelledby, so keep this brief.
    setStatus(`Lesson open: ${lesson.title}.`)
  } catch (error) {
    setStatus(error instanceof Error ? error.message : 'Failed to load lesson.', 'error')
  }
})


// ── Render sentence cards ─────────────────────────────────────────────────────

function renderResults(sentences, language) {
  const fragment = document.createDocumentFragment()

  for (const sentence of sentences) {
    const article = document.createElement('article')
    article.className = 'sentence-card'

    const textEl = document.createElement('p')
    textEl.className = 'sentence-card__text'
    textEl.textContent = sentence.text  // textContent — never innerHTML

    // Use <ul>/<li> for semantic list semantics; AT announces item count.
    const list = document.createElement('ul')
    list.className = 'sentence-card__pills'

    for (const item of sentence.learnable_objects) {
      const li = document.createElement('li')
      const pill = document.createElement('mnemosyne-pill')
      pill.setAttribute('type',      item.type)
      pill.setAttribute('label',     item.label)
      pill.setAttribute('object-id', item.id)
      pill.setAttribute('language',  language)
      li.appendChild(pill)
      list.appendChild(li)
    }

    article.append(textEl, list)
    fragment.appendChild(article)
  }

  // Replace everything in #results (detaches resultsEmpty if present).
  results.replaceChildren(fragment)
}


// ── Review submission ─────────────────────────────────────────────────────────

async function submitReview(objectId, quality) {
  const response = await fetch(`${API_BASE}/review`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({
      object_id:    objectId,
      quality,
      review_state: reviewStateByObject.get(objectId) ?? null,
    }),
  })

  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(body?.detail ?? `Review failed (${response.status})`)
  }

  const payload = await response.json()
  reviewStateByObject.set(objectId, payload.review_state)
  return payload
}


// ── Text-to-speech ────────────────────────────────────────────────────────────

function speakText(text, language) {
  if (!text || !('speechSynthesis' in window)) return
  const utterance = new SpeechSynthesisUtterance(text)
  if (language) utterance.lang = language
  window.speechSynthesis.cancel()  // stop any ongoing speech first
  window.speechSynthesis.speak(utterance)
}


// ── Markdown → safe HTML ──────────────────────────────────────────────────────
// Minimal subset: ##/### headings, - list items, **bold**, plain paragraphs.
//
// Maps ## → <h3> and ### → <h4> so lesson content headings sit below the
// modal's own <h2> title and maintain a valid document outline.
//
// All text is HTML-escaped before insertion; bold markers are applied after
// escaping so special characters in the text cannot break the <strong> tag.

function markdownToHtml(markdown) {
  const lines = markdown.split('\n')
  let html = '<div class="markdown">'
  let inList = false

  for (const line of lines) {
    if (line.startsWith('### ')) {
      if (inList) { html += '</ul>'; inList = false }
      html += `<h4>${escapeHtml(line.slice(4))}</h4>`
    } else if (line.startsWith('## ')) {
      if (inList) { html += '</ul>'; inList = false }
      html += `<h3>${escapeHtml(line.slice(3))}</h3>`
    } else if (line.startsWith('- ')) {
      if (!inList) { html += '<ul>'; inList = true }
      html += `<li>${inlineMarkdown(line.slice(2))}</li>`
    } else if (line.trim() === '') {
      if (inList) { html += '</ul>'; inList = false }
    } else {
      if (inList) { html += '</ul>'; inList = false }
      html += `<p>${inlineMarkdown(line)}</p>`
    }
  }

  if (inList) html += '</ul>'
  html += '</div>'
  return html
}

function inlineMarkdown(text) {
  return escapeHtml(text).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
}

function escapeHtml(value) {
  return value
    .replaceAll('&',  '&amp;')
    .replaceAll('<',  '&lt;')
    .replaceAll('>',  '&gt;')
    .replaceAll('"',  '&quot;')
    .replaceAll("'", '&#39;')
}
