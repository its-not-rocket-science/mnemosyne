import '../components/mnemosyne-pill.js'
import '../components/mnemosyne-modal.js'

const API_BASE = 'http://localhost:8000'

// ── DOM references ───────────────────────────────────────────────────────────
const form          = document.querySelector('#parse-form')
const languageSelect = document.querySelector('#language')
const sourceUrlInput = document.querySelector('#source-url')
const textarea      = document.querySelector('#source-text')
const submitButton  = form.querySelector('[type="submit"]')
const results       = document.querySelector('#results')
const status        = document.querySelector('#status')
const modal         = document.querySelector('#lesson-modal')

// Persists the latest review state for each learnable object so that
// subsequent reviews carry forward the scheduler's updated memory state.
const reviewStateByObject = new Map()


// ── Status helper ────────────────────────────────────────────────────────────
// Writes to the aria-live region and sets a data-state attribute so that
// CSS can style errors differently without JS managing individual classes.

function setStatus(message, state = 'idle') {
  // Clear first so screen readers announce the new message even if text
  // is identical to the previous value.
  status.textContent = ''
  // Microtask delay gives the live-region observer a chance to notice the
  // empty state before the new text arrives.
  queueMicrotask(() => {
    status.textContent = message
    status.dataset.state = state   // 'idle' | 'busy' | 'error'
  })
}


// ── Parse form ───────────────────────────────────────────────────────────────

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
  results.replaceChildren()
  setStatus('Parsing text…', 'busy')

  submitButton.disabled = true
  submitButton.setAttribute('aria-busy', 'true')
  const originalLabel = submitButton.textContent
  submitButton.textContent = 'Parsing…'

  try {
    const payload = {
      language: languageSelect.value,
      text,
      // source_url is for attribution; the server stores it but does not
      // fetch it.  Null when the field is empty.
      source_url: sourceUrlInput?.value.trim() || null,
    }

    const response = await fetch(`${API_BASE}/parse`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })

    if (!response.ok) {
      const body = await response.json().catch(() => null)
      throw new Error(body?.detail ?? `Parse failed (${response.status})`)
    }

    const data = await response.json()

    if (data.sentences.length === 0) {
      setStatus('No sentences found. Try pasting a longer passage.')
      return
    }

    renderResults(data.sentences, payload.language)
    const n = data.sentences.length
    setStatus(`${n} sentence${n !== 1 ? 's' : ''} parsed.`)
  } catch (error) {
    setStatus(error instanceof Error ? error.message : 'Parsing failed.', 'error')
  } finally {
    submitButton.disabled = false
    submitButton.removeAttribute('aria-busy')
    submitButton.textContent = originalLabel
  }
})


// ── Lesson open ──────────────────────────────────────────────────────────────
// Delegated to #results so it catches events from all pill descendants.
// The lesson-open CustomEvent is dispatched with composed:true so it
// crosses the pill's shadow-DOM boundary and reaches the light DOM.

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
      // Bind language so the TTS utterance uses the correct voice.
      onSpeak:     (text) => speakText(text, language),
    })

    setStatus('Lesson opened.')
  } catch (error) {
    setStatus(error instanceof Error ? error.message : 'Failed to load lesson.', 'error')
  }
})


// ── Render sentence cards ────────────────────────────────────────────────────

function renderResults(sentences, language) {
  const fragment = document.createDocumentFragment()

  for (const sentence of sentences) {
    const article = document.createElement('article')
    article.className = 'sentence-card'

    const textEl = document.createElement('p')
    textEl.className = 'sentence-card__text'
    textEl.textContent = sentence.text   // textContent — never innerHTML

    const pills = document.createElement('div')
    pills.className = 'sentence-card__pills'

    for (const item of sentence.learnable_objects) {
      const pill = document.createElement('mnemosyne-pill')
      pill.setAttribute('type',      item.type)
      pill.setAttribute('label',     item.label)
      pill.setAttribute('object-id', item.id)
      pill.setAttribute('language',  language)
      pills.appendChild(pill)
    }

    article.append(textEl, pills)
    fragment.appendChild(article)
  }

  results.appendChild(fragment)
}


// ── Review submission ────────────────────────────────────────────────────────

async function submitReview(objectId, quality) {
  const response = await fetch(`${API_BASE}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      object_id:    objectId,
      quality,
      // Pass the accumulated review state so FSRS can grow stability
      // across multiple ratings of the same object in one session.
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


// ── Text-to-speech ───────────────────────────────────────────────────────────
// language is a BCP-47 tag (e.g. "es", "en") used to select a matching
// voice.  SpeechSynthesis does not guarantee a matching voice exists;
// passing the hint is best-effort.

function speakText(text, language) {
  if (!text || !('speechSynthesis' in window)) return
  const utterance = new SpeechSynthesisUtterance(text)
  if (language) utterance.lang = language
  window.speechSynthesis.cancel()   // stop any ongoing speech first
  window.speechSynthesis.speak(utterance)
}


// ── Markdown → safe HTML ─────────────────────────────────────────────────────
// Minimal subset: ##/### headings, - list items, **bold**, plain paragraphs.
// All text is HTML-escaped before insertion; bold markers are re-applied
// after escaping so special characters in the text cannot escape the tag.

function markdownToHtml(markdown) {
  const lines = markdown.split('\n')
  let html = '<div class="markdown">'
  let inList = false

  for (const line of lines) {
    if (line.startsWith('## ')) {
      if (inList) { html += '</ul>'; inList = false }
      html += `<h2>${escapeHtml(line.slice(3))}</h2>`
    } else if (line.startsWith('### ')) {
      if (inList) { html += '</ul>'; inList = false }
      html += `<h3>${escapeHtml(line.slice(4))}</h3>`
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
  // Escape HTML first, then apply bold so **…** is never mis-parsed as tags.
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
