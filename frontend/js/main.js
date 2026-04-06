import '../components/mnemosyne-pill.js'
import '../components/mnemosyne-modal.js'

const API_BASE = 'http://localhost:8000'
const form = document.querySelector('#parse-form')
const languageSelect = document.querySelector('#language')
const textarea = document.querySelector('#source-text')
const results = document.querySelector('#results')
const status = document.querySelector('#status')
const modal = document.querySelector('#lesson-modal')

const reviewStateByObject = new Map()

form.addEventListener('submit', async (event) => {
  event.preventDefault()
  status.textContent = 'Parsing text…'
  results.innerHTML = ''

  try {
    const payload = {
      language: languageSelect.value,
      text: textarea.value.trim(),
    }

    const response = await fetch(`${API_BASE}/parse`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })

    if (!response.ok) {
      throw new Error(`Parse failed with status ${response.status}`)
    }

    const data = await response.json()
    renderResults(data.sentences, payload.language)
    status.textContent = `${data.sentences.length} sentence(s) parsed.`
  } catch (error) {
    status.textContent = error instanceof Error ? error.message : 'Parsing failed.'
  }
})

results.addEventListener('lesson-open', async (event) => {
  const { objectId, language } = event.detail
  try {
    status.textContent = 'Loading lesson…'
    const response = await fetch(`${API_BASE}/lesson/${encodeURIComponent(objectId)}?language=${encodeURIComponent(language)}`)
    if (!response.ok) {
      throw new Error(`Lesson failed with status ${response.status}`)
    }
    const lesson = await response.json()
    modal.open({
      title: lesson.title,
      html: markdownToHtml(lesson.content_markdown),
      objectId: lesson.id,
      exampleText: lesson.example_text,
      onRate: submitReview,
      onSpeak: speakText,
    })
    status.textContent = 'Lesson opened.'
  } catch (error) {
    status.textContent = error instanceof Error ? error.message : 'Failed to load lesson.'
  }
})

function renderResults(sentences, language) {
  const fragment = document.createDocumentFragment()

  for (const sentence of sentences) {
    const article = document.createElement('article')
    article.className = 'sentence-card'

    const text = document.createElement('p')
    text.className = 'sentence-card__text'
    text.textContent = sentence.text

    const pills = document.createElement('div')
    pills.className = 'sentence-card__pills'

    for (const item of sentence.learnable_objects) {
      const pill = document.createElement('mnemosyne-pill')
      pill.setAttribute('type', item.type)
      pill.setAttribute('label', item.label)
      pill.setAttribute('object-id', item.id)
      pill.setAttribute('language', language)
      pills.appendChild(pill)
    }

    article.append(text, pills)
    fragment.appendChild(article)
  }

  results.appendChild(fragment)
}

async function submitReview(objectId, quality) {
  const response = await fetch(`${API_BASE}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      object_id: objectId,
      quality,
      review_state: reviewStateByObject.get(objectId) || null,
    }),
  })

  if (!response.ok) {
    throw new Error(`Review failed with status ${response.status}`)
  }

  const payload = await response.json()
  reviewStateByObject.set(objectId, payload.review_state)
  return payload
}

function speakText(text) {
  if (!text || !('speechSynthesis' in window)) return
  const utterance = new SpeechSynthesisUtterance(text)
  window.speechSynthesis.cancel()
  window.speechSynthesis.speak(utterance)
}

function markdownToHtml(markdown) {
  const lines = markdown.split('\n')
  let html = '<div class="markdown">'
  let inList = false

  for (const line of lines) {
    if (line.startsWith('## ')) {
      if (inList) {
        html += '</ul>'
        inList = false
      }
      html += `<h2>${escapeHtml(line.slice(3))}</h2>`
    } else if (line.startsWith('### ')) {
      if (inList) {
        html += '</ul>'
        inList = false
      }
      html += `<h3>${escapeHtml(line.slice(4))}</h3>`
    } else if (line.startsWith('- ')) {
      if (!inList) {
        html += '<ul>'
        inList = true
      }
      html += `<li>${inlineMarkdown(line.slice(2))}</li>`
    } else if (line.trim() === '') {
      if (inList) {
        html += '</ul>'
        inList = false
      }
    } else {
      if (inList) {
        html += '</ul>'
        inList = false
      }
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
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}
