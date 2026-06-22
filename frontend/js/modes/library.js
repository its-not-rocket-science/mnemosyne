/**
 * js/modes/library.js — Browsing and resuming previously-imported texts.
 *
 * Owns: Corpus browser, Collections, Bulk mode, Import history, Continue
 * reading strip, Source list item builder, Reading history, Load-lesson
 * dialog, Vocabulary browser.
 */
import { API_BASE } from '../config.js'
import { getAuthHeaders, getUser } from '../auth.js'
import { t, ti, currentUiLang, loadBundle } from '../i18n.js'
import { buildLessonPipelinePayload } from '../lesson-pipeline.js'
import { setStatus } from '../shared.js'
import {
  languageCapabilities,
  setCurrentDocumentTitle,
  setCurrentDocumentEyebrow,
} from '../reading-state.js'
import { renderResults, setCurrentSourceDocId, clearSentenceRatedIds, clearSentenceTranslations } from './lesson.js'
import { _fetchResultsDifficulty } from './explorer.js'
import { navigate, onRoute } from '../router.js'

// ── DOM references ────────────────────────────────────────────────────────────

const languageSelect = document.querySelector('#language')
const loadLessonBtn  = document.querySelector('#load-lesson-btn')
const saveLessonBtn  = document.querySelector('#save-lesson-btn')
const results        = document.querySelector('#results')

// Was #load-lesson-dialog — its list is now absorbed inline into #route-library.
const loadLessonSection  = document.querySelector('#load-lesson-section')
const loadLessonList     = document.querySelector('#load-lesson-list')

// Was #parse-dialog — now the #/explore route's main section.
const parseDialog       = document.querySelector('#route-explore')
const changeLessonBtn   = document.querySelector('#change-lesson-btn')
const readingHistoryEl   = document.querySelector('#reading-history')
const readingHistoryList = document.querySelector('#reading-history-list')

// Was #vocab-browser-dialog / #corpus-browser-dialog.
const vocabBrowserRouteSection  = document.querySelector('#route-library-vocab')
const corpusBrowserRouteSection = document.querySelector('#route-library')

// ── Vocabulary browser ────────────────────────────────────────────────────────
// Was #vocab-browser-dialog — now the #/library/vocab route's section.

const vocabBrowserDialog    = vocabBrowserRouteSection
const vocabBrowserCloseBtn  = document.querySelector('#vocab-browser-close-btn')
const openVocabBrowserBtn   = document.querySelector('#open-vocab-browser-btn')
const vocabBrowserSearch    = document.querySelector('#vocab-browser-search')
const vocabBrowserLevel     = document.querySelector('#vocab-browser-level')
const vocabBrowserSort      = document.querySelector('#vocab-browser-sort')
const vocabBrowserList      = document.querySelector('#vocab-browser-list')
const vocabBrowserStatus    = document.querySelector('#vocab-browser-status')
const vocabBrowserCount     = document.querySelector('#vocab-browser-count')
const vocabBrowserMoreBtn   = document.querySelector('#vocab-browser-more-btn')
const vocabExportCsvBtn     = document.querySelector('#vocab-export-csv-btn')
const vocabExportAnkiBtn    = document.querySelector('#vocab-export-anki-btn')

const _VOCAB_PAGE_SIZE = 50
let _vocabOffset = 0
let _vocabTotal  = 0
let _vocabSearchTimer = null

function _vocabParams() {
  const p = new URLSearchParams()
  const q = vocabBrowserSearch?.value.trim()
  const lv = vocabBrowserLevel?.value
  const sort = vocabBrowserSort?.value || 'mastery'
  const lang = languageSelect?.value
  if (lang)  p.set('language', lang)
  if (q)     p.set('q', q)
  if (lv)    p.set('level', lv)
  p.set('sort', sort)
  p.set('limit', String(_VOCAB_PAGE_SIZE))
  p.set('offset', String(_vocabOffset))
  return p
}

async function _loadVocab(append = false) {
  if (!vocabBrowserList) return
  if (!append) {
    _vocabOffset = 0
    vocabBrowserList.replaceChildren()
  }
  if (vocabBrowserStatus) vocabBrowserStatus.textContent = t('vocab_loading')
  if (vocabBrowserMoreBtn) vocabBrowserMoreBtn.hidden = true

  try {
    const resp = await fetch(`${API_BASE}/users/me/vocabulary?${_vocabParams()}`, {
      headers: getAuthHeaders(),
    })
    if (!resp.ok) throw new Error(`${resp.status}`)
    const data = await resp.json()
    _vocabTotal = data.total

    if (vocabBrowserStatus) vocabBrowserStatus.textContent = ''

    if (data.items.length === 0 && !append) {
      const li = document.createElement('li')
      li.className = 'vocab-browser-item'
      li.textContent = t('vocab_empty')
      vocabBrowserList.appendChild(li)
    } else {
      for (const item of data.items) {
        const li = document.createElement('li')
        li.className = 'vocab-browser-item'

        const wordSpan = document.createElement('span')
        wordSpan.className = 'vocab-browser-item__word'
        wordSpan.textContent = item.display_label || item.canonical_form

        const meta = document.createElement('span')
        meta.className = 'vocab-browser-item__meta'

        if (item.cefr_level) {
          const cefr = document.createElement('span')
          cefr.className = 'vocab-browser-item__cefr'
          cefr.textContent = item.cefr_level
          meta.appendChild(cefr)
        }

        const mastery = document.createElement('span')
        mastery.className = 'vocab-browser-item__mastery'
        mastery.textContent = `${Math.round(item.mastery_score * 100)}%`
        meta.appendChild(mastery)

        li.appendChild(wordSpan)
        li.appendChild(meta)

        if (item.gloss) {
          const gloss = document.createElement('span')
          gloss.className = 'vocab-browser-item__gloss'
          gloss.textContent = item.gloss
          li.appendChild(gloss)
        }

        vocabBrowserList.appendChild(li)
      }
      _vocabOffset += data.items.length
    }

    const shown = Math.min(_vocabOffset, _vocabTotal)
    if (vocabBrowserCount) {
      vocabBrowserCount.textContent = ti('vocab_count', { shown, total: _vocabTotal })
    }
    if (vocabBrowserMoreBtn) {
      vocabBrowserMoreBtn.hidden = _vocabOffset >= _vocabTotal
    }
  } catch (err) {
    if (vocabBrowserStatus) vocabBrowserStatus.textContent = t('parse_error_generic')
  }
}

function _scheduleVocabSearch() {
  clearTimeout(_vocabSearchTimer)
  _vocabSearchTimer = setTimeout(() => _loadVocab(false), 350)
}

// The #/library/vocab route handler (_applyLibraryRoute) calls _loadVocab()
// once the route activates — calling it here too would double-fetch.
openVocabBrowserBtn?.addEventListener('click', () => navigate('#/library/vocab'))

vocabBrowserCloseBtn?.addEventListener('click', () => navigate('#/library'))

vocabBrowserSearch?.addEventListener('input', _scheduleVocabSearch)
vocabBrowserLevel?.addEventListener('change', () => _loadVocab(false))
vocabBrowserSort?.addEventListener('change', () => _loadVocab(false))
vocabBrowserMoreBtn?.addEventListener('click', () => _loadVocab(true))

async function _downloadVocabExport(format) {
  const btn = format === 'csv' ? vocabExportCsvBtn : vocabExportAnkiBtn
  if (!btn) return
  const orig = btn.textContent
  btn.disabled = true
  btn.textContent = t('vocab_export_busy')

  try {
    const p = new URLSearchParams({ format })
    const lang = languageSelect?.value
    const lv   = vocabBrowserLevel?.value
    const q    = vocabBrowserSearch?.value.trim()
    if (lang) p.set('language', lang)
    if (lv)   p.set('level', lv)
    if (q)    p.set('q', q)

    const resp = await fetch(`${API_BASE}/users/me/vocabulary/export?${p}`, {
      headers: getAuthHeaders(),
    })
    if (!resp.ok) throw new Error(resp.status)

    const blob = await resp.blob()
    const cd   = resp.headers.get('content-disposition') ?? ''
    const fnMatch = cd.match(/filename="([^"]+)"/)
    const filename = fnMatch ? fnMatch[1] : `mnemosyne_vocabulary.${format === 'anki' ? 'txt' : 'csv'}`

    const url = URL.createObjectURL(blob)
    const a   = document.createElement('a')
    a.href     = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  } catch {
    // Download failure is silent — user sees no response; no state to roll back.
  } finally {
    btn.disabled = false
    btn.textContent = orig
  }
}

vocabExportCsvBtn?.addEventListener('click', () => _downloadVocabExport('csv'))
vocabExportAnkiBtn?.addEventListener('click', () => _downloadVocabExport('anki'))

// ── Source list item builder ──────────────────────────────────────────────────

function _buildSourceItem(src) {
  const pct       = Math.round((src.completion_fraction ?? 0) * 100)
  const pos       = src.next_position ?? 0
  const total     = src.sentences_total ?? 0
  const started   = pos > 0
  const complete  = src.is_complete ?? false

  const actionKey = complete ? 'source_action_reread'
    : started ? 'source_action_resume'
    : 'source_action_start'

  const li = document.createElement('li')
  li.className = 'load-lesson-list__item'

  const btn = document.createElement('button')
  btn.type = 'button'
  btn.className = 'load-lesson-list__btn'
  btn.dataset.sourceId   = src.id
  btn.dataset.sourceLang = src.language
  btn.addEventListener('click', () => _loadSource(src.id, src.language))

  const titleSpan = document.createElement('span')
  titleSpan.className = 'load-lesson-list__title'
  titleSpan.textContent = src.title || src.language

  const actionSpan = document.createElement('span')
  actionSpan.className = 'load-lesson-list__action'
  actionSpan.textContent = t(actionKey)
  actionSpan.setAttribute('aria-hidden', 'true')

  btn.appendChild(titleSpan)
  btn.appendChild(actionSpan)

  if (total > 0) {
    const progressRow = document.createElement('span')
    progressRow.className = 'load-lesson-list__progress-row'

    const barWrap = document.createElement('span')
    barWrap.className = 'load-lesson-list__progress-bar'
    barWrap.setAttribute('role', 'presentation')

    const fill = document.createElement('span')
    fill.className = 'load-lesson-list__progress-fill'
    fill.style.inlineSize = `${pct}%`
    barWrap.appendChild(fill)

    const label = document.createElement('span')
    label.className = 'load-lesson-list__progress-text'
    label.textContent = complete
      ? t('source_complete')
      : ti('source_progress_text', { pos, total })

    progressRow.appendChild(barWrap)
    progressRow.appendChild(label)
    btn.appendChild(progressRow)
  }

  li.appendChild(btn)

  // Accessible label includes action + title + progress context
  const ariaLabel = `${t(actionKey)}: ${src.title || src.language}`
    + (total > 0 ? ` — ${complete ? t('source_complete') : ti('source_progress_text', { pos, total })}` : '')
  btn.setAttribute('aria-label', ariaLabel)

  return li
}

// ── Load-lesson list — was #load-lesson-dialog, absorbed into #/library ───────

loadLessonBtn?.addEventListener('click', async () => {
  const language = languageSelect?.value || null
  loadLessonList && (loadLessonList.innerHTML = '')
  navigate('#/library')
  if (loadLessonSection) loadLessonSection.hidden = false
  try {
    const url = `${API_BASE}/sources` + (language ? `?language=${language}` : '')
    const resp = await fetch(url, { headers: getAuthHeaders() })
    if (!resp.ok) throw new Error(resp.status)
    const { sources } = await resp.json()
    if (!sources.length) {
      const li = document.createElement('li')
      li.className = 'load-lesson-list__empty'
      li.textContent = t(language ? 'load_lesson_empty' : 'load_lesson_all_empty')
      loadLessonList?.appendChild(li)
      return
    }
    for (const src of sources) {
      loadLessonList?.appendChild(_buildSourceItem(src))
    }
  } catch {
    const li = document.createElement('li')
    li.className = 'load-lesson-list__empty'
    li.textContent = t('parse_error_generic')
    loadLessonList?.appendChild(li)
  }
})

// ── Reading history ───────────────────────────────────────────────────────────

function _relativeTime(iso) {
  if (!iso) return ''
  try {
    const diff = Date.now() - new Date(iso).getTime()
    const rtf  = new Intl.RelativeTimeFormat(currentUiLang(), { numeric: 'auto' })
    const min  = Math.floor(diff / 60000)
    if (min < 60) return rtf.format(-Math.max(min, 1), 'minute')
    const hr = Math.floor(min / 60)
    if (hr < 24) return rtf.format(-hr, 'hour')
    return rtf.format(-Math.floor(hr / 24), 'day')
  } catch {
    return ''
  }
}

function _renderReadingHistory(items) {
  if (!readingHistoryList) return
  readingHistoryList.replaceChildren()
  items.forEach(item => {
    const li    = document.createElement('li')
    li.className = 'reading-history__item'
    const pct   = Math.round((item.completion_fraction ?? 0) * 100)
    const rawTitle = item.title ?? item.source_document_id
    const title = rawTitle.length > 55 ? rawTitle.slice(0, 52) + '…' : rawTitle

    const meta = document.createElement('div')
    meta.className = 'reading-history__meta'

    const lang = document.createElement('span')
    lang.className   = 'reading-history__lang'
    lang.textContent = item.language

    const titleEl = document.createElement('span')
    titleEl.className   = 'reading-history__title'
    titleEl.textContent = title
    titleEl.title       = rawTitle

    meta.append(lang, titleEl)

    const barWrap = document.createElement('div')
    barWrap.className     = 'reading-history__bar-wrap'
    barWrap.setAttribute('role', 'progressbar')
    barWrap.setAttribute('aria-valuenow', String(pct))
    barWrap.setAttribute('aria-valuemin', '0')
    barWrap.setAttribute('aria-valuemax', '100')

    const bar = document.createElement('div')
    bar.className = 'reading-history__bar'
    bar.style.setProperty('--_prog', String(item.completion_fraction ?? 0))
    barWrap.appendChild(bar)

    const footer = document.createElement('div')
    footer.className = 'reading-history__footer'

    const pctEl = document.createElement('span')
    pctEl.className   = 'reading-history__pct'
    pctEl.textContent = `${pct}%`

    const dateEl = document.createElement('span')
    dateEl.className   = 'reading-history__date'
    dateEl.textContent = _relativeTime(item.last_read_at)

    const btn = document.createElement('button')
    btn.type      = 'button'
    btn.className = 'ghost-button ghost-button--small reading-history__btn'
    btn.setAttribute('data-i18n', 'reading_resume_btn')
    btn.textContent = t('reading_resume_btn')
    btn.addEventListener('click', () => {
      parseDialog?.close()
      _loadSource(item.source_document_id, item.language, item.next_position)
    })

    footer.append(pctEl, dateEl, btn)
    li.append(meta, barWrap, footer)
    readingHistoryList.appendChild(li)
  })
}

export async function _fetchReadingHistory() {
  if (!readingHistoryEl) return
  // The "Continue reading" strip can render outside the #/library route
  // (main.js calls this unconditionally on startup) — its rec_* heading
  // and reading-history card strings live in the 'library' bundle, so load
  // it here too rather than relying solely on the #/library route trigger.
  loadBundle('library')
  try {
    const resp = await fetch(`${API_BASE}/reading?limit=3`, { headers: getAuthHeaders() })
    if (!resp.ok) { readingHistoryEl.hidden = true; return }
    const data = await resp.json()
    if (!data.items?.length) { readingHistoryEl.hidden = true; return }
    _renderReadingHistory(data.items)
    readingHistoryEl.hidden = false
  } catch {
    readingHistoryEl.hidden = true
  }
}

changeLessonBtn?.addEventListener('click', _fetchReadingHistory)

async function _loadSource(sourceId, language, resumeAt = 0) {
  if (loadLessonSection) loadLessonSection.hidden = true
  setCurrentSourceDocId(sourceId)
  clearSentenceRatedIds()
  clearSentenceTranslations()
  setStatus(t('loading'))
  try {
    const resp = await fetch(`${API_BASE}/sources/${sourceId}`, { headers: getAuthHeaders() })
    if (!resp.ok) throw new Error(resp.status)
    const data = await resp.json()
    // Set language selector to match
    if (languageSelect && data.language) {
      languageSelect.value = data.language
      languageSelect.dispatchEvent(new Event('change'))
    }
    setCurrentDocumentTitle(data.title || null)
    setCurrentDocumentEyebrow(null)
    const sourceText = data.sentences.map(s => s.text).join(" ")
    renderResults(buildLessonPipelinePayload({
      sourceText,
      normalizedText: sourceText,
      parseData: data,
      suggestedNextPassage: null,
    }), data.language)
    _fetchResultsDifficulty(sourceText, data.language)
    setStatus(ti('sentences_parsed', { n: data.sentences.length }))
    if (saveLessonBtn) saveLessonBtn.hidden = false
    if (resumeAt > 0) {
      requestAnimationFrame(() => {
        const card = results?.querySelector(`[data-sentence-index="${resumeAt}"]`)
        card?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      })
    }
  } catch {
    setStatus(t('load_lesson_failed'), 'error')
  }
}

export async function refreshLoadLessonBtn() {
  if (!loadLessonBtn) return
  const user = getUser()
  if (!user) { loadLessonBtn.hidden = true; return }
  try {
    const language = languageSelect?.value || null
    const url = `${API_BASE}/sources` + (language ? `?language=${language}` : '')
    const resp = await fetch(url, { headers: getAuthHeaders() })
    if (!resp.ok) throw new Error()
    const { sources } = await resp.json()
    loadLessonBtn.hidden = sources.length === 0
  } catch {
    loadLessonBtn.hidden = true
  }
}

// ── Corpus confusable drills button + reading history wiring ──────────────────
// (corpusDrillsBtn click is wired in review.js; nothing further needed here.)

// ── Corpus browser ────────────────────────────────────────────────────────────
// Was #corpus-browser-dialog — now the #/library route's main section.

const corpusBrowserDialog   = corpusBrowserRouteSection
const corpusBrowserCloseBtn = document.querySelector('#corpus-browser-close-btn')
const openCorpusBrowserBtn  = document.querySelector('#open-corpus-browser-btn')
const corpusBrowserSearch   = document.querySelector('#corpus-browser-search')
const corpusBrowserLang       = document.querySelector('#corpus-browser-lang')
const corpusBrowserType       = document.querySelector('#corpus-browser-type')
const corpusBrowserSort       = document.querySelector('#corpus-browser-sort')
const corpusBrowserTag        = document.querySelector('#corpus-browser-tag')
const corpusBrowserCollection = document.querySelector('#corpus-browser-collection')
const corpusBrowserList       = document.querySelector('#corpus-browser-list')
const corpusBrowserStatus    = document.querySelector('#corpus-browser-status')
const corpusBrowserCount     = document.querySelector('#corpus-browser-count')
const corpusBrowserMoreBtn   = document.querySelector('#corpus-browser-more-btn')
const corpusBrowserStats     = document.querySelector('#corpus-browser-stats')
const corpusImportToggle     = document.querySelector('#corpus-import-url-toggle')
const corpusImportForm       = document.querySelector('#corpus-import-url-form')
const corpusImportInput      = document.querySelector('#corpus-import-url-input')
const corpusImportLang       = document.querySelector('#corpus-import-url-lang')
const corpusImportSubmit     = document.querySelector('#corpus-import-url-submit')
const corpusImportStatus     = document.querySelector('#corpus-import-url-status')
const corpusStatTotal        = document.querySelector('#corpus-stat-total')
const corpusStatInProgress   = document.querySelector('#corpus-stat-in-progress')
const corpusStatNotStarted   = document.querySelector('#corpus-stat-not-started')
const corpusStatComplete     = document.querySelector('#corpus-stat-complete')

const _CORPUS_PAGE_SIZE = 20
let _corpusOffset = 0
let _corpusTotal  = 0
let _corpusSearchTimer = null
let _bulkMode = false
let _selectedDocIds = new Set()
let _collectionsCache = []

function _corpusParams() {
  const p = new URLSearchParams()
  const sort = corpusBrowserSort?.value || 'recent'
  p.set('sort', sort)

  const lang = corpusBrowserLang?.value
  if (lang) p.set('language', lang)

  const type = corpusBrowserType?.value
  if (type) p.set('content_type', type)

  const tag = corpusBrowserTag?.value
  if (tag) p.set('tag', tag)

  const col = corpusBrowserCollection?.value
  if (col) p.set('collection_id', col)

  const query = corpusBrowserSearch?.value?.trim()
  if (query) p.set('q', query)

  p.set('limit', String(_CORPUS_PAGE_SIZE))
  p.set('offset', String(_corpusOffset))
  return p
}

function _applyQueryHighlight(span, text, query) {
  span.textContent = ''
  if (!query) { span.textContent = text; return }
  const idx = text.toLowerCase().indexOf(query.toLowerCase())
  if (idx === -1) { span.textContent = text; return }
  span.append(text.slice(0, idx))
  const mark = document.createElement('mark')
  mark.className = 'corpus-browser-list__match'
  mark.textContent = text.slice(idx, idx + query.length)
  span.appendChild(mark)
  span.append(text.slice(idx + query.length))
}

function _buildCorpusItem(item) {
  const pct = Math.round((item.completion_fraction ?? 0) * 100)
  const progressText = item.is_complete
    ? t('source_complete')
    : item.started
      ? ti('source_progress_text', { pos: item.next_position, total: item.sentences_total })
      : ''
  const actionLabel = (item.started && !item.is_complete) ? t('corpus_continue_btn') : t('corpus_open_btn')

  const li = document.createElement('li')
  li.className = 'corpus-browser-list__item'
  if (item.is_complete) li.dataset.complete = ''

  const btn = document.createElement('button')
  btn.type = 'button'
  btn.className = 'corpus-browser-list__btn'
  btn.setAttribute('aria-label',
    `${actionLabel}: ${item.title || item.language}${progressText ? ` — ${progressText}` : ''}`)

  const titleSpan = document.createElement('span')
  titleSpan.className = 'corpus-browser-list__title'
  _applyQueryHighlight(titleSpan, item.title || item.language, corpusBrowserSearch?.value.trim() || '')

  const meta = document.createElement('span')
  meta.className = 'corpus-browser-list__meta'

  const langTag = document.createElement('span')
  langTag.className = 'corpus-browser-list__tag'
  langTag.textContent = item.language.toUpperCase()
  meta.appendChild(langTag)

  if (item.char_count) {
    const chars = document.createElement('span')
    chars.className = 'corpus-browser-list__chars'
    chars.textContent = ti('corpus_char_count', { n: item.char_count.toLocaleString() })
    meta.appendChild(chars)
  }

  if (item.started) {
    const pctSpan = document.createElement('span')
    pctSpan.className = 'corpus-browser-list__progress-pct'
    pctSpan.textContent = item.is_complete ? t('source_complete') : `${pct}%`
    meta.appendChild(pctSpan)

    const resetBtn = document.createElement('button')
    resetBtn.type = 'button'
    resetBtn.className = 'corpus-browser-list__reset'
    resetBtn.setAttribute('aria-label', `${t('corpus_reset_progress_aria')}: ${item.title || item.language}`)
    resetBtn.textContent = '↺'
    resetBtn.addEventListener('click', (e) => {
      e.stopPropagation()
      _resetCorpusProgress(item.id)
    })
    meta.appendChild(resetBtn)
  }

  const resumeAt = (item.started && !item.is_complete) ? item.next_position : 0

  const openBtn = document.createElement('button')
  openBtn.type = 'button'
  openBtn.className = 'corpus-browser-list__open'
  openBtn.textContent = (item.started && !item.is_complete)
    ? t('corpus_continue_btn')
    : t('corpus_open_btn')
  openBtn.addEventListener('click', (e) => {
    e.stopPropagation()
    _loadSource(item.id, item.language, resumeAt)
  })

  btn.appendChild(titleSpan)
  btn.appendChild(meta)
  btn.appendChild(openBtn)
  btn.addEventListener('click', () => _loadSource(item.id, item.language, resumeAt))

  // Progress bar at top of card; ARIA role for screen readers
  if (item.started && item.sentences_total > 0) {
    const prog = document.createElement('div')
    prog.className = 'corpus-browser-list__progress'
    prog.setAttribute('role', 'progressbar')
    prog.setAttribute('aria-valuemin', '0')
    prog.setAttribute('aria-valuemax', '100')
    prog.setAttribute('aria-valuenow', String(pct))
    prog.setAttribute('aria-label', progressText)
    const fill = document.createElement('span')
    fill.className = 'corpus-browser-list__progress-fill'
    fill.style.inlineSize = `${pct}%`
    prog.appendChild(fill)
    li.appendChild(prog)
  }

  li.appendChild(btn)

  // Tags + study row
  const tagsRow = document.createElement('div')
  tagsRow.className = 'corpus-browser-list__tags'

  for (const tag of (item.tags ?? [])) {
    const chip = document.createElement('span')
    chip.className = 'corpus-browser-list__tag-chip'

    const chipLabel = document.createElement('button')
    chipLabel.type = 'button'
    chipLabel.className = 'corpus-browser-list__tag-chip-label'
    chipLabel.textContent = tag
    chipLabel.addEventListener('click', (e) => {
      e.stopPropagation()
      if (corpusBrowserTag) { corpusBrowserTag.value = tag; _loadCorpus() }
    })

    const removeBtn = document.createElement('button')
    removeBtn.type = 'button'
    removeBtn.className = 'corpus-browser-list__tag-remove'
    removeBtn.setAttribute('aria-label', `${t('corpus_tag_remove_aria')}: ${tag}`)
    removeBtn.textContent = '×'
    removeBtn.addEventListener('click', (e) => {
      e.stopPropagation()
      _removeCorpusTag(item.id, tag)
    })

    chip.appendChild(chipLabel)
    chip.appendChild(removeBtn)
    tagsRow.appendChild(chip)
  }

  const addTagBtn = document.createElement('button')
  addTagBtn.type = 'button'
  addTagBtn.className = 'corpus-browser-list__tag-add'
  addTagBtn.setAttribute('aria-label', t('corpus_tag_add_aria'))
  addTagBtn.textContent = '+'

  const tagInput = document.createElement('input')
  tagInput.type = 'text'
  tagInput.className = 'corpus-browser-list__tag-input'
  tagInput.placeholder = t('corpus_tag_add_placeholder')
  tagInput.hidden = true
  tagInput.maxLength = 50

  addTagBtn.addEventListener('click', (e) => {
    e.stopPropagation()
    tagInput.hidden = !tagInput.hidden
    if (!tagInput.hidden) tagInput.focus()
  })

  tagInput.addEventListener('keydown', async (e) => {
    if (e.key === 'Enter') {
      const val = tagInput.value.trim()
      if (val) { await _addCorpusTag(item.id, val); tagInput.value = ''; tagInput.hidden = true }
    } else if (e.key === 'Escape') {
      tagInput.value = ''; tagInput.hidden = true
    }
  })

  tagInput.addEventListener('blur', () => {
    setTimeout(() => { tagInput.hidden = true; tagInput.value = '' }, 150)
  })

  const studyBtn = document.createElement('button')
  studyBtn.type = 'button'
  studyBtn.className = 'corpus-browser-list__study'
  studyBtn.textContent = t('corpus_study_btn')
  studyBtn.setAttribute('aria-label', `${t('corpus_study_aria')}: ${item.title || item.language}`)
  studyBtn.addEventListener('click', (e) => {
    e.stopPropagation()
    _studyCorpusDocument(item.id, studyBtn)
  })

  tagsRow.appendChild(addTagBtn)
  tagsRow.appendChild(tagInput)
  tagsRow.appendChild(studyBtn)
  li.appendChild(tagsRow)

  // Vocab density indicator
  const density = item.vocab_density || 0
  if (density > 0) {
    const level = density >= 0.7 ? 'high' : density >= 0.35 ? 'mid' : 'low'
    li.dataset.vocabLevel = level
    const densityDot = document.createElement('span')
    densityDot.className = `corpus-browser-list__density corpus-browser-list__density--${level}`
    densityDot.setAttribute('aria-label', `${t('corpus_vocab_density_label')}: ${Math.round(density * 100)}%`)
    densityDot.setAttribute('role', 'img')
    btn.appendChild(densityDot)
  }

  // Note row
  const noteToggle = document.createElement('button')
  noteToggle.type = 'button'
  noteToggle.className = 'corpus-browser-list__note-toggle'
  const notePreview = item.note ? item.note.slice(0, 80) + (item.note.length > 80 ? '…' : '') : ''
  noteToggle.textContent = notePreview || t('corpus_note_add')
  if (!item.note) noteToggle.classList.add('corpus-browser-list__note-toggle--empty')
  noteToggle.addEventListener('click', (e) => {
    e.stopPropagation()
    noteArea.hidden = !noteArea.hidden
    if (!noteArea.hidden) noteTextarea.focus()
  })

  const noteArea = document.createElement('div')
  noteArea.className = 'corpus-browser-list__note-area'
  noteArea.hidden = true

  const noteTextarea = document.createElement('textarea')
  noteTextarea.className = 'corpus-browser-list__note-textarea'
  noteTextarea.rows = 3
  noteTextarea.maxLength = 2000
  noteTextarea.value = item.note || ''
  noteTextarea.placeholder = t('corpus_note_placeholder')
  noteTextarea.addEventListener('click', e => e.stopPropagation())
  noteTextarea.addEventListener('blur', async () => {
    const text = noteTextarea.value.trim()
    if (text !== (item.note || '').trim()) {
      if (text) {
        await _saveCorpusNote(item.id, text)
        item.note = text
        noteToggle.textContent = text.slice(0, 80) + (text.length > 80 ? '…' : '')
        noteToggle.classList.remove('corpus-browser-list__note-toggle--empty')
      } else {
        await _deleteCorpusNote(item.id)
        item.note = null
        noteToggle.textContent = t('corpus_note_add')
        noteToggle.classList.add('corpus-browser-list__note-toggle--empty')
      }
    }
  })

  noteArea.appendChild(noteTextarea)
  li.appendChild(noteToggle)
  li.appendChild(noteArea)

  // Provenance row: author, source link, content-type badge
  if (item.author || item.source_url || item.content_type) {
    const prov = document.createElement('div')
    prov.className = 'corpus-browser-list__provenance'
    if (item.author) {
      const byline = document.createElement('span')
      byline.className = 'corpus-browser-list__author'
      byline.textContent = `by ${item.author}`
      prov.appendChild(byline)
    }
    if (item.source_url) {
      const link = document.createElement('a')
      link.className = 'corpus-browser-list__source-link'
      link.href = item.source_url
      link.target = '_blank'
      link.rel = 'noopener noreferrer'
      link.textContent = '↗ Source'
      link.addEventListener('click', e => e.stopPropagation())
      prov.appendChild(link)
    }
    const typeBadge = document.createElement('span')
    typeBadge.className = `corpus-browser-list__type-badge corpus-browser-list__type-badge--${item.content_type}`
    typeBadge.textContent = item.content_type.replace('_', ' ')
    prov.appendChild(typeBadge)
    li.appendChild(prov)
  }

  // Add-to-shelf button (shown when collections exist)
  if (_collectionsCache.length) {
    const shelfSel = document.createElement('select')
    shelfSel.className = 'corpus-browser-list__shelf-select ghost-select ghost-select--small'
    shelfSel.setAttribute('aria-label', t('corpus_collection_add'))
    const placeholder = document.createElement('option')
    placeholder.value = ''
    placeholder.textContent = t('corpus_collection_add')
    placeholder.disabled = true
    placeholder.selected = true
    shelfSel.appendChild(placeholder)
    for (const col of _collectionsCache) {
      const opt = document.createElement('option')
      opt.value = col.id
      opt.textContent = col.name
      shelfSel.appendChild(opt)
    }
    shelfSel.addEventListener('change', async (e) => {
      e.stopPropagation()
      const colId = shelfSel.value
      if (!colId) return
      await _addToCollection(item.id, colId)
      shelfSel.value = ''
    })
    li.appendChild(shelfSel)
  }

  // Bulk-mode checkbox (always present, shown only in bulk mode)
  const checkbox = document.createElement('input')
  checkbox.type = 'checkbox'
  checkbox.className = 'corpus-browser-list__checkbox'
  checkbox.setAttribute('aria-label', item.title || item.language)
  checkbox.hidden = !_bulkMode
  checkbox.addEventListener('change', () => {
    if (checkbox.checked) {
      _selectedDocIds.add(item.id)
    } else {
      _selectedDocIds.delete(item.id)
    }
    _updateBulkCount()
  })
  li.insertBefore(checkbox, li.firstChild)

  return li
}

async function _loadCorpus(append = false) {
  if (!corpusBrowserList) return
  if (!append) {
    _corpusOffset = 0
    corpusBrowserList.replaceChildren()
  }
  if (corpusBrowserStatus) corpusBrowserStatus.textContent = t('vocab_loading')
  if (corpusBrowserMoreBtn) corpusBrowserMoreBtn.hidden = true

  try {
    const resp = await fetch(`${API_BASE}/corpus?${_corpusParams()}`, {
      headers: getAuthHeaders(),
    })
    if (!resp.ok) throw new Error(`${resp.status}`)
    const data = await resp.json()
    _corpusTotal = data.total

    if (corpusBrowserStatus) corpusBrowserStatus.textContent = ''

    if (data.items.length === 0 && !append) {
      const li = document.createElement('li')
      li.className = 'corpus-browser-list__empty'
      li.textContent = t('corpus_empty')
      corpusBrowserList.appendChild(li)
    } else {
      for (const item of data.items) {
        corpusBrowserList.appendChild(_buildCorpusItem(item))
      }
      _corpusOffset += data.items.length
    }

    if (corpusBrowserCount) {
      corpusBrowserCount.textContent = ti('corpus_count', { n: _corpusTotal })
    }
    if (corpusBrowserMoreBtn) {
      corpusBrowserMoreBtn.hidden = _corpusOffset >= _corpusTotal
    }
  } catch {
    if (corpusBrowserStatus) corpusBrowserStatus.textContent = t('load_lesson_failed')
  }
}

function _makeAllLangsOption() {
  const o = document.createElement('option')
  o.value = ''
  o.textContent = t('corpus_lang_all')
  return o
}

function _langOptLabel(code) {
  const label = t('lesson_lang_' + code)
  return (label && label !== 'lesson_lang_' + code)
    ? label
    : (languageCapabilities.get(code)?.name || code)
}

async function _populateCorpusLangSelect() {
  if (!corpusBrowserLang) return
  // Pre-select current app language so first load is filtered correctly.
  const preselect = languageSelect?.value || ''
  try {
    const resp = await fetch(`${API_BASE}/corpus/languages`, { headers: getAuthHeaders() })
    if (resp.ok) {
      const data = await resp.json()
      const options = data.languages.map(({ language, count }) => {
        const opt = document.createElement('option')
        opt.value = language
        opt.textContent = `${_langOptLabel(language)} (${count})`
        return opt
      })
      corpusBrowserLang.replaceChildren(_makeAllLangsOption(), ...options)
      const hasPreselect = data.languages.some(l => l.language === preselect)
      corpusBrowserLang.value = hasPreselect ? preselect : ''
      return
    }
  } catch { /* fall through to static */ }
  // Fallback: show all supported languages without counts
  const staticOpts = [...languageCapabilities.entries()]
    .filter(([code]) => !['x-cjk-test', 'x-rtl-test'].includes(code))
    .map(([code]) => {
      const opt = document.createElement('option')
      opt.value = code
      opt.textContent = _langOptLabel(code)
      return opt
    })
  corpusBrowserLang.replaceChildren(_makeAllLangsOption(), ...staticOpts)
  corpusBrowserLang.value = preselect
}

async function _loadCorpusStats() {
  try {
    const resp = await fetch(`${API_BASE}/corpus/stats`, { headers: getAuthHeaders() })
    if (!resp.ok) return
    const d = await resp.json()
    if (corpusStatTotal)      corpusStatTotal.textContent      = d.total
    if (corpusStatInProgress) corpusStatInProgress.textContent = d.in_progress
    if (corpusStatNotStarted) corpusStatNotStarted.textContent = d.not_started
    if (corpusStatComplete)   corpusStatComplete.textContent   = d.complete
    if (corpusBrowserStats)   corpusBrowserStats.hidden = false
  } catch { /* ignore */ }
}

async function _resetCorpusProgress(docId) {
  try {
    const resp = await fetch(`${API_BASE}/corpus/${encodeURIComponent(docId)}/progress`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    })
    if (resp.ok || resp.status === 204) {
      await Promise.all([_loadCorpus(), _loadCorpusStats()])
    }
  } catch { /* ignore */ }
}

async function _addCorpusTag(docId, tag) {
  try {
    const resp = await fetch(`${API_BASE}/corpus/${encodeURIComponent(docId)}/tags`, {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ tag }),
    })
    if (resp.ok) await Promise.all([_loadCorpus(), _populateTagFilter()])
  } catch { /* ignore */ }
}

async function _removeCorpusTag(docId, tag) {
  try {
    const resp = await fetch(
      `${API_BASE}/corpus/${encodeURIComponent(docId)}/tags/${encodeURIComponent(tag)}`,
      { method: 'DELETE', headers: getAuthHeaders() }
    )
    if (resp.ok || resp.status === 204) await Promise.all([_loadCorpus(), _populateTagFilter()])
  } catch { /* ignore */ }
}

async function _studyCorpusDocument(docId, btn) {
  const orig = btn.textContent
  btn.disabled = true
  btn.textContent = '…'
  try {
    const resp = await fetch(`${API_BASE}/corpus/${encodeURIComponent(docId)}/study`, {
      method: 'POST',
      headers: getAuthHeaders(),
    })
    if (resp.ok) {
      const d = await resp.json()
      btn.textContent = ti('corpus_study_mined', { n: d.mined })
    } else {
      btn.textContent = orig
    }
  } catch {
    btn.textContent = orig
  } finally {
    btn.disabled = false
  }
}

async function _populateTagFilter() {
  if (!corpusBrowserTag) return
  try {
    const resp = await fetch(`${API_BASE}/corpus/all-tags`, { headers: getAuthHeaders() })
    if (!resp.ok) return
    const d = await resp.json()
    const current = corpusBrowserTag.value
    const allOpt = document.createElement('option')
    allOpt.value = ''
    allOpt.textContent = t('corpus_tag_all')
    const opts = d.tags.map(tag => {
      const o = document.createElement('option')
      o.value = tag
      o.textContent = tag
      return o
    })
    corpusBrowserTag.replaceChildren(allOpt, ...opts)
    if (d.tags.includes(current)) corpusBrowserTag.value = current
  } catch { /* ignore */ }
}

async function _saveCorpusNote(docId, text) {
  try {
    await fetch(`${API_BASE}/corpus/${encodeURIComponent(docId)}/note`, {
      method: 'PUT',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    })
  } catch { /* ignore */ }
}

async function _deleteCorpusNote(docId) {
  try {
    await fetch(`${API_BASE}/corpus/${encodeURIComponent(docId)}/note`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    })
  } catch { /* ignore */ }
}

// ── Collections ───────────────────────────────────────────────────────────────

async function _loadCollections() {
  try {
    const resp = await fetch(`${API_BASE}/collections`, { headers: getAuthHeaders() })
    if (!resp.ok) return
    const data = await resp.json()
    _collectionsCache = data.collections || []
    _populateCorpusCollectionSelect()
  } catch { /* ignore */ }
}

function _populateCorpusCollectionSelect() {
  if (!corpusBrowserCollection) return
  const current = corpusBrowserCollection.value
  // Keep first option ("All shelves"), rebuild the rest
  while (corpusBrowserCollection.options.length > 1) corpusBrowserCollection.remove(1)
  for (const col of _collectionsCache) {
    const opt = document.createElement('option')
    opt.value = col.id
    opt.textContent = `${col.name} (${col.item_count})`
    corpusBrowserCollection.appendChild(opt)
  }
  // Append "New shelf…" option
  const newOpt = document.createElement('option')
  newOpt.value = '__new__'
  newOpt.textContent = t('corpus_collection_new')
  corpusBrowserCollection.appendChild(newOpt)
  if ([...corpusBrowserCollection.options].some(o => o.value === current)) {
    corpusBrowserCollection.value = current
  }
}

async function _addToCollection(docId, colId) {
  try {
    await fetch(`${API_BASE}/collections/${encodeURIComponent(colId)}/items/${encodeURIComponent(docId)}`, {
      method: 'POST',
      headers: getAuthHeaders(),
    })
    await _loadCollections()
  } catch { /* ignore */ }
}

async function _createCollection(name) {
  try {
    const resp = await fetch(`${API_BASE}/collections`, {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    })
    if (resp.ok) {
      await _loadCollections()
      return await resp.json()
    }
  } catch { /* ignore */ }
  return null
}

// ── Bulk mode ─────────────────────────────────────────────────────────────────

function _updateBulkCount() {
  const countEl = document.querySelector('#corpus-bulk-count')
  if (countEl) countEl.textContent = `${_selectedDocIds.size} selected`
}

function _enterBulkMode() {
  _bulkMode = true
  _selectedDocIds.clear()
  document.querySelector('#corpus-bulk-select-btn')?.setAttribute('aria-pressed', 'true')
  document.querySelector('#corpus-bulk-bar')?.removeAttribute('hidden')
  corpusBrowserList?.querySelectorAll('.corpus-browser-list__checkbox').forEach(cb => {
    cb.hidden = false
    cb.checked = false
  })
  _updateBulkCount()
}

function _exitBulkMode() {
  _bulkMode = false
  _selectedDocIds.clear()
  document.querySelector('#corpus-bulk-select-btn')?.setAttribute('aria-pressed', 'false')
  const bulkBar = document.querySelector('#corpus-bulk-bar')
  if (bulkBar) bulkBar.hidden = true
  corpusBrowserList?.querySelectorAll('.corpus-browser-list__checkbox').forEach(cb => {
    cb.hidden = true
    cb.checked = false
  })
}

async function _executeBulkTag(action) {
  const tag = document.querySelector('#corpus-bulk-tag-input')?.value.trim()
  if (!tag || _selectedDocIds.size === 0) return
  try {
    await fetch(`${API_BASE}/corpus/bulk/tags`, {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ doc_ids: [..._selectedDocIds], tag, action }),
    })
  } catch { /* ignore */ }
  _exitBulkMode()
  await Promise.all([_loadCorpus(), _populateTagFilter()])
}

// ── Import history ────────────────────────────────────────────────────────────

async function _loadImportLog() {
  const list = document.querySelector('#corpus-import-log-list')
  if (!list) return
  try {
    const resp = await fetch(`${API_BASE}/corpus/import-log?limit=20`, { headers: getAuthHeaders() })
    if (!resp.ok) return
    const data = await resp.json()
    list.innerHTML = ''
    if (!data.entries.length) {
      const li = document.createElement('li')
      li.className = 'corpus-import-log__empty'
      li.textContent = t('corpus_import_log_empty')
      list.appendChild(li)
      return
    }
    for (const e of data.entries) {
      const li = document.createElement('li')
      li.className = `corpus-import-log__item corpus-import-log__item--${e.status}`
      const statusSpan = document.createElement('span')
      statusSpan.className = 'corpus-import-log__status'
      const statusKey = { success: 'corpus_import_log_ok', failed: 'corpus_import_log_fail', duplicate: 'corpus_import_log_dup' }[e.status] || 'corpus_import_log_fail'
      statusSpan.textContent = t(statusKey)
      const titleSpan = document.createElement('span')
      titleSpan.className = 'corpus-import-log__title'
      try { titleSpan.textContent = e.title || new URL(e.url).hostname } catch { titleSpan.textContent = e.url }
      li.appendChild(statusSpan)
      li.appendChild(titleSpan)
      if (e.error_detail) {
        const err = document.createElement('span')
        err.className = 'corpus-import-log__error'
        err.textContent = e.error_detail
        li.appendChild(err)
      }
      list.appendChild(li)
    }
  } catch { /* ignore */ }
}

// ── Continue reading strip ────────────────────────────────────────────────────

async function _loadInProgress() {
  const section = document.querySelector('#corpus-in-progress')
  const list    = document.querySelector('#corpus-in-progress-list')
  if (!section || !list) return
  try {
    const resp = await fetch(`${API_BASE}/corpus/in-progress?limit=10`, { headers: getAuthHeaders() })
    if (!resp.ok) return
    const data = await resp.json()
    if (!data.items.length) { section.hidden = true; return }
    list.innerHTML = ''
    for (const item of data.items) list.appendChild(_buildInProgressCard(item))
    section.hidden = false
  } catch { section.hidden = true }
}

function _buildInProgressCard(item) {
  const li  = document.createElement('li')
  li.className = 'corpus-in-progress__card'
  const pct = Math.round((item.completion_fraction || 0) * 100)

  const lang = document.createElement('span')
  lang.className = 'corpus-in-progress__lang'
  lang.textContent = item.language.toUpperCase()

  const title = document.createElement('span')
  title.className = 'corpus-in-progress__title'
  title.textContent = item.title || item.language

  const bar = document.createElement('div')
  bar.className = 'corpus-in-progress__bar'
  bar.setAttribute('role', 'progressbar')
  bar.setAttribute('aria-valuemin', '0')
  bar.setAttribute('aria-valuemax', '100')
  bar.setAttribute('aria-valuenow', String(pct))
  const fill = document.createElement('div')
  fill.className = 'corpus-in-progress__fill'
  fill.style.inlineSize = `${pct}%`
  bar.appendChild(fill)

  const pctSpan = document.createElement('span')
  pctSpan.className = 'corpus-in-progress__pct'
  pctSpan.textContent = `${pct}%`

  const resumeBtn = document.createElement('button')
  resumeBtn.type = 'button'
  resumeBtn.className = 'ghost-button ghost-button--small corpus-in-progress__resume'
  resumeBtn.textContent = t('corpus_continue_btn')
  resumeBtn.addEventListener('click', () => _loadSource(item.source_document_id, item.language, item.next_position))

  li.append(lang, title, bar, pctSpan, resumeBtn)
  return li
}

async function _populateImportLangSelect() {
  if (!corpusImportLang) return
  try {
    const resp = await fetch(`${API_BASE}/languages`, { headers: getAuthHeaders() })
    if (!resp.ok) return
    const langs = await resp.json()
    const opts = langs.map(l => {
      const o = document.createElement('option')
      o.value = l.language
      o.textContent = l.language
      return o
    })
    corpusImportLang.replaceChildren(...opts)
  } catch { /* ignore */ }
}

async function _importCorpusUrl() {
  const url  = corpusImportInput?.value.trim()
  const lang = corpusImportLang?.value
  if (!url || !lang) return
  if (corpusImportSubmit) corpusImportSubmit.disabled = true
  if (corpusImportStatus) corpusImportStatus.textContent = '…'
  try {
    const resp = await fetch(`${API_BASE}/corpus/import-url`, {
      method: 'POST',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, language: lang }),
    })
    if (resp.ok) {
      const d = await resp.json()
      const label = d.title || url
      if (corpusImportStatus) corpusImportStatus.textContent = ti('corpus_import_url_success', { title: label })
      if (corpusImportInput) corpusImportInput.value = ''
      if (corpusImportForm) corpusImportForm.hidden = true
      if (corpusImportToggle) corpusImportToggle.setAttribute('aria-expanded', 'false')
      await Promise.all([_loadCorpus(), _loadCorpusStats()])
    } else if (resp.status === 409) {
      const err = await resp.json().catch(() => ({}))
      const detail = err.detail || {}
      const existingTitle = detail.title || detail.source_document_id || url
      if (corpusImportStatus) corpusImportStatus.textContent = ti('corpus_import_url_duplicate', { title: existingTitle })
    } else {
      const err = await resp.json().catch(() => ({}))
      if (corpusImportStatus) corpusImportStatus.textContent = (typeof err.detail === 'string' ? err.detail : null) || t('corpus_import_url_error')
    }
  } catch {
    if (corpusImportStatus) corpusImportStatus.textContent = t('corpus_import_url_error')
  } finally {
    if (corpusImportSubmit) corpusImportSubmit.disabled = false
  }
}

// Loads/populates the corpus browser's data. Called by the #/library route
// handler whenever that route becomes active — it must NOT call navigate()
// itself, since navigate() to an already-current hash dispatches
// synchronously and this function is itself invoked from that dispatch
// (calling navigate('#/library') here would recurse infinitely).
async function _openCorpusBrowser() {
  await _populateCorpusLangSelect()
  await _loadCorpus()
  await Promise.all([
    _loadCorpusStats(),
    _populateTagFilter(),
    _populateImportLangSelect(),
    _loadCollections(),
    _loadInProgress(),
  ])
}

openCorpusBrowserBtn?.addEventListener('click', () => navigate('#/library'))

corpusBrowserCloseBtn?.addEventListener('click', () => navigate('#/explore'))

corpusBrowserSearch?.addEventListener('input', () => {
  clearTimeout(_corpusSearchTimer)
  _corpusSearchTimer = setTimeout(() => _loadCorpus(), 300)
})

corpusBrowserLang?.addEventListener('change', () => _loadCorpus())
corpusBrowserType?.addEventListener('change', () => _loadCorpus())
corpusBrowserSort?.addEventListener('change', () => _loadCorpus())
corpusBrowserTag?.addEventListener('change',  () => _loadCorpus())
corpusBrowserCollection?.addEventListener('change', async () => {
  if (corpusBrowserCollection.value === '__new__') {
    const name = prompt(t('corpus_collection_new'))?.trim()
    corpusBrowserCollection.value = ''
    if (name) {
      const col = await _createCollection(name)
      if (col) corpusBrowserCollection.value = col.id
    }
  }
  _loadCorpus()
})

document.querySelector('#corpus-bulk-select-btn')?.addEventListener('click', () => {
  if (_bulkMode) _exitBulkMode(); else _enterBulkMode()
})
document.querySelector('#corpus-bulk-tag-add-btn')?.addEventListener('click', () => _executeBulkTag('add'))
document.querySelector('#corpus-bulk-tag-remove-btn')?.addEventListener('click', () => _executeBulkTag('remove'))
document.querySelector('#corpus-bulk-done-btn')?.addEventListener('click', _exitBulkMode)

document.querySelector('#corpus-import-log-toggle')?.addEventListener('click', () => {
  const toggle = document.querySelector('#corpus-import-log-toggle')
  const list   = document.querySelector('#corpus-import-log-list')
  const open   = list?.hidden
  if (list) list.hidden = !open
  toggle?.setAttribute('aria-expanded', String(!!open))
  if (open) _loadImportLog()
})

corpusBrowserStats?.querySelectorAll('.corpus-stats-chip').forEach(chip => {
  chip.addEventListener('click', () => {
    if (corpusBrowserSort) {
      corpusBrowserSort.value = chip.dataset.sort || 'recent'
      _loadCorpus()
    }
  })
})

corpusBrowserMoreBtn?.addEventListener('click', () => _loadCorpus(true))

corpusImportToggle?.addEventListener('click', () => {
  const open = corpusImportForm?.hidden
  if (corpusImportForm) corpusImportForm.hidden = !open
  corpusImportToggle.setAttribute('aria-expanded', String(!!open))
  if (open) corpusImportInput?.focus()
})

corpusImportSubmit?.addEventListener('click', _importCorpusUrl)

corpusImportInput?.addEventListener('keydown', e => {
  if (e.key === 'Enter') _importCorpusUrl()
})

// ── Route handling ────────────────────────────────────────────────────────────
// #/library shows the corpus browser section; #/library/vocab shows the
// vocabulary browser. Each route hides the other, and both hide the
// load-lesson list (which only opens explicitly via #load-lesson-btn).

function _applyLibraryRoute(route) {
  if (corpusBrowserRouteSection) corpusBrowserRouteSection.hidden = route.path !== 'library'
  if (vocabBrowserRouteSection)  vocabBrowserRouteSection.hidden  = route.path !== 'library-vocab'
  if (route.path !== 'library' && loadLessonSection) loadLessonSection.hidden = true

  if (route.path === 'library' || route.path === 'library-vocab') loadBundle('library')
  if (route.path === 'library') _openCorpusBrowser()
  if (route.path === 'library-vocab') _loadVocab(false)
}

/**
 * initLibrary() — registers the #/library and #/library/vocab route
 * handlers. All other library.js event listeners wire themselves at import
 * time (matching how this code ran unconditionally in the original main.js);
 * refreshLoadLessonBtn() is called by explorer.js's loadLanguages() once the
 * language list is ready, not here.
 */
export function initLibrary() {
  onRoute(_applyLibraryRoute)
}
