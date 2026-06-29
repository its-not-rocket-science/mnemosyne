/**
 * js/modes/lesson.js — Annotated reading surface and the detail pane it opens.
 *
 * Owns: Annotation type metadata, Annotation filters, Render sentence cards,
 * Inline annotation builder, Annotation density minimap, Lesson open,
 * Visual anchor (link annotation to detail pane), Sentence translation fetch,
 * Translation callback factory, Reading auto-advance state, Sentence
 * translation state, Playback controls, NowPlayingBar teleportation,
 * Text-to-speech.
 *
 * Also owns the annotation hover tooltip and the detail pane's pane-navigate
 * confusable-link handler — both operate directly on rendered annotation
 * marks, so they live alongside the code that creates those marks.
 */
import { API_BASE } from '../config.js'
import { getAuthHeaders } from '../auth.js'
import { t, ti, currentUiLang, TYPE_LABELS_LONG_I18N, loadBundle } from '../i18n.js'
import { playbackEngine } from '../playback.js'
import { openDetail, closeDetail } from '../layout.js'
import { validateLessonPipelinePayload } from '../lesson-pipeline.js'
import { announce, setStatus } from '../shared.js'
import { subcategoryLabel } from '../subcategory-labels.js'
import {
  currentDepth,
  languageCapabilities,
  isFollowAlongEnabled,
  activeFilterTypes,
  activeFilterCategories,
  activeLockedTypes,
  activeSearchTerm,
  setActiveSearchTerm,
  currentSentences,
  setCurrentSentences,
  currentTtsTag,
  setCurrentTtsTag,
  currentSentenceIndex,
  setCurrentSentenceIndex,
  ANNOTATION_DEPTH_MODEL,
  DEPTH_FALLBACK,
  currentDocumentTitle,
  currentDocumentEyebrow,
  currentSourceUrl,
  currentFilename,
} from '../reading-state.js'
import { getTermProgress, submitReview, submitLessonCheck, invalidateTermProgress } from './review.js'
import {
  setResultsHeading,
  updateScriptViewToolbar,
  applyScriptViewToResults,
  _clearResultsDifficultyBadge,
} from './explorer.js'
import { navigate, onRoute } from '../router.js'

// ── DOM references ────────────────────────────────────────────────────────────

const results           = document.querySelector('#results')
const modal             = document.querySelector('#lesson-modal')
const detailPane        = document.querySelector('#detail-pane')
const paneBackdrop      = document.querySelector('#pane-backdrop')
const resultsTransport  = document.querySelector('#results-transport')
const resultsPlayBtn    = document.querySelector('#results-play-btn')
const resultsScrubber   = document.querySelector('#results-scrubber')
const resultsTimeLabel  = document.querySelector('#results-time-label')
const filterBar         = document.querySelector('#filter-bar')
const appFilterBar      = document.querySelector('#app-filter-bar')
const nowPlayingBar     = document.querySelector('#now-playing-bar')
const readingProgress   = document.querySelector('#reading-progress')
const annotationMinimap = document.querySelector('#annotation-minimap')
const minimapLegend     = document.querySelector('#minimap-legend')
const annotationTooltip = document.querySelector('#annotation-tooltip')
const annotationSearch  = document.querySelector('#annotation-search')
const resultsSection    = document.querySelector('#results-section')
const siteHero          = document.querySelector('#site-hero')
// Was #parse-dialog — now the #/explore route's main section.
const parseDialog       = document.querySelector('#route-explore')
const changeLessonBtn   = document.querySelector('#change-lesson-btn')
const corpusDrillsBtn   = document.querySelector('#corpus-drills-btn')
const readerNowPlaying  = document.querySelector('#reader-nowplaying')
const rnpToggle         = document.querySelector('#rnp-toggle')
const rnpStop           = document.querySelector('#rnp-stop')
const rnpPrev           = document.querySelector('#rnp-prev')
const rnpNext           = document.querySelector('#rnp-next')
const rnpText           = document.querySelector('#reader-nowplaying .reader-nowplaying__text')
const rnpCounter        = document.querySelector('#reader-nowplaying .reader-nowplaying__counter')

const canSpeak = 'speechSynthesis' in window

// Transport timer state
let _transportTimerId   = null
let _transportWallStart = null
let _transportPauseOff  = 0
let _transportEstDur    = 0

function _transportFmt(s) {
  const tm = Math.max(0, Math.floor(s))
  return `${String(Math.floor(tm / 60)).padStart(2, '0')}:${String(tm % 60).padStart(2, '0')}`
}

function _transportTick() {
  if (!_transportWallStart) return
  const elapsed = (Date.now() - _transportWallStart) / 1000
  const pct = _transportEstDur > 0 ? Math.min((elapsed / _transportEstDur) * 100, 100) : 0
  if (resultsScrubber) resultsScrubber.value = String(pct)
  if (resultsTimeLabel) resultsTimeLabel.textContent =
    `${_transportFmt(elapsed)} / ${_transportFmt(_transportEstDur)}`
}

function _transportStart() {
  if (_transportTimerId) clearInterval(_transportTimerId)
  _transportEstDur    = Math.max(playbackEngine.totalChars / 14, 2)
  _transportWallStart = Date.now() - _transportPauseOff
  _transportTimerId   = setInterval(_transportTick, 500)
}

function _transportPause() {
  _transportPauseOff = Date.now() - (_transportWallStart ?? Date.now())
  if (_transportTimerId) { clearInterval(_transportTimerId); _transportTimerId = null }
}

function _transportReset() {
  if (_transportTimerId) { clearInterval(_transportTimerId); _transportTimerId = null }
  _transportWallStart = null
  _transportPauseOff  = 0
  _transportEstDur    = 0
  if (resultsScrubber)  resultsScrubber.value = '0'
  if (resultsTimeLabel) resultsTimeLabel.textContent = '--:--'
}

// ── Reading auto-advance state ─────────────────────────────────────────────────
let _currentSourceDocId   = null  // set by library.js's _loadSource; null for pasted/url texts
const _sentenceRatedIds   = new Map() // sentenceIdx → Set<objectId> of rated items

export function setCurrentSourceDocId(id) { _currentSourceDocId = id }
export function currentSourceDocId() { return _currentSourceDocId }
export function clearSentenceRatedIds() { _sentenceRatedIds.clear() }

// ── Sentence translation state ─────────────────────────────────────────────────
const _sentenceTranslations = new Map() // sentenceIdx → {text, attribution} | null

export function clearSentenceTranslations() { _sentenceTranslations.clear() }

// ── Annotation type metadata ───────────────────────────────────────────────────
// TYPE_LABEL_KEYS : tooltip text shown in the ::before pseudo-element.
// TYPE_LEVEL : 1=vocabulary, 2=grammar/script, 3=idiom/nuance/literary
const TYPE_LABEL_KEYS = {
  vocabulary: 'type_vocabulary_short',
  conjugation: 'type_conjugation_short',
  agreement: 'type_agreement_short',
  inflection: 'type_inflection_short',
  idiom: 'type_idiom_short',
  grammar: 'type_grammar_short',
  nuance: 'type_nuance_short',
  script: 'type_script_short',
  transliteration: 'type_script_short',
  phrase_family: 'type_phrase_family_short',
}

const TYPE_LEVEL = {
  vocabulary:      1,
  conjugation:     2,
  agreement:       2,
  inflection:      2,
  grammar:         2,
  script:          2,
  transliteration: 2,
  idiom:           3,
  nuance:          3,
  phrase_family:   3,
}

// ── Translation callback factory ─────────────────────────────────────────────

export function makeTranslateCallback(lesson) {
  return async (text, sourceLang, targetLang) => {
    if (!text || sourceLang === targetLang) return null
    try {
      // Only cache/retrieve by object_id when translating the lemma itself.
      // Sentence translations must not reuse the cached word translation.
      const lemma = lesson.lesson_data?.lemma || lesson.examples?.[0]
      const isLemma = lesson.type === 'vocabulary' && text === lemma
      const r = await fetch(`${API_BASE}/translate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({
          text,
          source_language: sourceLang,
          target_language: targetLang,
          object_id: isLemma ? lesson.id : undefined,
        }),
      })
      if (!r.ok) return null
      const d = await r.json()
      return d.translation ? { text: d.translation, attribution: d.attribution } : null
    } catch { return null }
  }
}

// ── Text-to-speech ────────────────────────────────────────────────────────────

export function speakText(text, langTag) {
  if (!text || !canSpeak) return
  playbackEngine.speak(text, langTag, 'phrase')
}

// ── Lesson open ───────────────────────────────────────────────────────────────

results.addEventListener('lesson-open', async (event) => {
  const { objectId, language, source } = event.detail
  const caps   = languageCapabilities.get(language)
  const ttsTag = caps?.tts_lang_tag ?? language
  const dir    = caps?.direction ?? 'ltr'

  // Resolve the originating annotation: prefer detail.source (set by the
  // inline preview CTA when dispatching on #results), then event.target's
  // own closest annotation, then event.target itself.
  const originEl = source
    ?? event.target?.closest?.('.reader-annotation')
    ?? event.target
  const sentenceCard = originEl?.closest?.('.sentence-card')
  const sentenceText = sentenceCard?.querySelector('.sentence-card__text')?.textContent ?? ''
  setCurrentSentenceIndex(parseInt(sentenceCard?.dataset.sentenceIndex ?? '-1', 10))

  const phrase = originEl?.getAttribute?.('aria-label') ?? objectId
  announce(ti('aria_loading_details', { phrase }))
  setStatus(t('loading_lesson'), 'busy')

  try {
    const url = `${API_BASE}/lesson/${encodeURIComponent(objectId)}?language=${encodeURIComponent(language)}&depth=${encodeURIComponent(currentDepth())}`
    const response = await fetch(url, { headers: getAuthHeaders() })

    if (!response.ok) {
      const body = await response.json().catch(() => null)
      throw new Error(body?.detail ?? `Lesson not available (${response.status})`)
    }

    const lesson = await response.json()
    const progressRows = await getTermProgress(language)
    const dueQueue = progressRows
      .filter((row) => row.review_bucket === 'due')
      .sort((a, b) => Date.parse(a.next_review_at || '') - Date.parse(b.next_review_at || ''))
      .slice(0, 8)

    // Open the detail pane as the primary view.
    // "Study drills" inside the pane delegates to the existing modal.
    if (detailPane) {
      const uiLang = currentUiLang()
      const termProgress = progressRows.find(row => row.source_lesson_ids?.includes(lesson.id)) ?? null

      // Open the shell column FIRST so the pane has non-zero width to animate
      // into. Mirrors the ordering used by other call sites (e.g. recommended
      // reading), where show() runs after openDetail().
      openDetail()

      detailPane.show({
        lesson,
        sentenceText,
        language,
        dir,
        ttsTag,
        caps,
        depth: currentDepth(),
        uiLang,
        onTranslate: makeTranslateCallback(lesson),
        reviewQueue: dueQueue,
        termProgress,
        onSpeak:  (text, lang) => speakText(text, lang ?? ttsTag),
        onStudy:  () => modal.open({
          lesson,
          objectId: lesson.id,
          caps,
          language,
          onRate:  submitReview,
          onSpeak: (text) => speakText(text, ttsTag),
          onCheckResult: (check) => { void submitLessonCheck(lesson, language, check) },
        }),
      })

      // ── Visual anchor: link annotation to detail pane ─────────────────────
      // Mark the source annotation so CSS can accent it and connect it to the
      // pane's left border.  Also compute the vertical clip origin so the pane
      // entry animation feels anchored to where the click happened.
      document.querySelector('[data-detail-source]')?.removeAttribute('data-detail-source')
      const sourceEl = originEl
      if (sourceEl?.classList?.contains('reader-annotation')) {
        sourceEl.dataset.detailSource = ''
      }

      const detailPanelEl = document.querySelector('#app-detail-panel')
      if (detailPanelEl) {
        const TYPE_ACCENT = {
          vocabulary: 'var(--ann-vocab)',
          grammar: 'var(--ann-grammar)', conjugation: 'var(--ann-grammar)', agreement: 'var(--ann-grammar)',
          idiom: 'var(--ann-idiom)',
          nuance: 'var(--ann-idiom)', phrase_family: 'var(--ann-idiom)',
          script: 'var(--ann-etymology)', transliteration: 'var(--ann-etymology)',
        }
        const type = sourceEl?.dataset?.type || lesson.type || ''
        detailPanelEl.style.setProperty('--detail-accent', TYPE_ACCENT[type] ?? 'var(--accent)')

      }

      // Force re-run of entry animation. Run in the same rAF as show()'s
      // data-open set so the backdrop only becomes pointer-active after the
      // pane already has pointer-events:auto (avoids a click-through window
      // on mobile where the backdrop would intercept and immediately close).
      detailPane.classList.remove('pane-entry-animate')
      requestAnimationFrame(() => {
        paneBackdrop?.classList.add('is-visible')
        detailPane.classList.add('pane-entry-animate')
      })
    } else {
      // Fallback: no detail pane in DOM — open modal directly.
      modal.open({
        lesson,
        objectId: lesson.id,
        caps,
        language,
        onRate:  submitReview,
        onSpeak: (text) => speakText(text, ttsTag),
        onCheckResult: (check) => { void submitLessonCheck(lesson, language, check) },
      })
    }

    setStatus(ti('lesson_open', { title: lesson.title }))
  } catch (error) {
    setStatus(error instanceof Error ? error.message : t('load_lesson_failed'), 'error')
  }
})

// Sync note badges on annotation marks when note is saved/cleared in the pane.
detailPane?.addEventListener('note-updated', ({ detail }) => {
  console.log('pane__note-note-updated', detail);
  results.querySelectorAll(`[data-object-id="${CSS.escape(detail.objectId)}"]`).forEach(mark => {
    mark.toggleAttribute('data-has-note', detail.hasNote)
  })
})

// Close handler: collapse the split-pane grid when the pane is dismissed.
detailPane?.addEventListener('pane-close', () => {
  closeDetail()
  paneBackdrop?.classList.remove('is-visible')
  document.querySelector('[data-detail-source]')?.removeAttribute('data-detail-source')
  document.querySelector('#app-detail-panel')?.style.removeProperty('--detail-accent')
  detailPane?.classList.remove('pane-entry-animate')
})

detailPane?.addEventListener('pane-practice-check', ({ detail }) => {
  if (!detail?.lesson || !detail?.language) return
  const objectId = detail.objectId ?? detail.lesson?.id
  if (!objectId) return
  const quality = detail.correct ? ((detail.attempts ?? 1) <= 1 ? 4 : 3) : 1
  const wrongAnswer = !detail.correct && detail.wrongAnswer ? detail.wrongAnswer : null
  void submitReview(objectId, quality, wrongAnswer).then((payload) => {
    if (!payload) return
    invalidateTermProgress(detail.language)

    // Update adaptive-reader memory + minimap immediately using FSRS-derived data.
    if (payload.mastery_score != null) {
      window.dispatchEvent(new CustomEvent('mnemosyne:practice-result', {
        detail: {
          objectId,
          masteryScore:   payload.mastery_score,
          nextReviewAt:   payload.next_review_at,
          reviewCount:    payload.review_count,
          correctCount:   payload.correct_count,
          incorrectCount: payload.incorrect_count,
          reviewBucket:   payload.review_bucket,
        },
      }))
    }

    detailPane.dispatchEvent(new CustomEvent('review-submitted', {
      detail: {
        objectId,
        quality,
        correct:           detail.correct,
        nextIntervalDays:  payload.next_interval_days,
        masteryBefore:     payload.mastery_score_before,
        masteryAfter:      payload.mastery_score,
        reviewBucket:      payload.review_bucket,
      },
    }))

    // Auto-advance when all items in the current sentence have been rated.
    _trackSentenceRating(objectId)
  })
})

function _trackSentenceRating(objectId) {
  const idx = currentSentenceIndex()
  if (idx < 0 || idx >= currentSentences().length) return
  let rated = _sentenceRatedIds.get(idx)
  if (!rated) { rated = new Set(); _sentenceRatedIds.set(idx, rated) }
  rated.add(objectId)
  const sentence  = currentSentences()[idx]
  const ratable   = sentence.learnable_objects.map(o => o.id).filter(Boolean)
  if (ratable.length > 0 && ratable.every(id => rated.has(id))) {
    _autoAdvanceSentence(idx)
  }
}

function _autoAdvanceSentence(doneIdx) {
  const nextIdx  = doneIdx + 1
  const nextCard = results?.querySelector(`[data-sentence-index="${nextIdx}"]`)
  if (nextCard) {
    nextCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    nextCard.classList.add('sentence-card--done')
    requestAnimationFrame(() => nextCard.classList.add('sentence-card--done-flash'))
    setTimeout(() => {
      nextCard.classList.remove('sentence-card--done', 'sentence-card--done-flash')
    }, 900)
  }
  if (_currentSourceDocId) {
    void fetch(`${API_BASE}/reading/${encodeURIComponent(_currentSourceDocId)}`, {
      method:  'PATCH',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body:    JSON.stringify({ sentences_read: 1 }),
    }).catch(() => { /* non-fatal: progression update best-effort */ })
  }
}

// ── Sentence translation fetch ────────────────────────────────────────────────

export async function fetchSentenceTranslation(sentenceIdx, text, sourceLang, el) {
  const cached = _sentenceTranslations.get(sentenceIdx)
  if (cached !== undefined) {
    _renderSentenceTranslation(el, cached)
    return
  }
  el.textContent = t('sentence_translating')
  try {
    const resp = await fetch(`${API_BASE}/translate`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body:    JSON.stringify({
        text,
        source_language: sourceLang,
        target_language: currentUiLang(),
      }),
    })
    if (!resp.ok) throw new Error(resp.status)
    const data = await resp.json()
    const result = data.translation
      ? { text: data.translation, attribution: data.attribution ?? null }
      : null
    _sentenceTranslations.set(sentenceIdx, result)
    _renderSentenceTranslation(el, result)
  } catch {
    _sentenceTranslations.set(sentenceIdx, null)
    _renderSentenceTranslation(el, null)
  }
}

function _renderSentenceTranslation(el, result) {
  if (!result) {
    el.textContent = t('sentence_translation_na')
    el.dataset.state = 'error'
    return
  }
  el.textContent = result.text
  el.removeAttribute('data-state')
  if (result.attribution) {
    const attr = document.createElement('span')
    attr.className   = 'reader-sentence__translation-attr'
    attr.textContent = result.attribution
    el.appendChild(attr)
  }
}

// ── Annotation hover tooltip ──────────────────────────────────────────────────
function _showAnnotationTooltip(mark) {
  if (!annotationTooltip || !mark) return
  annotationTooltip.removeAttribute('hidden')
  annotationTooltip.removeAttribute('aria-hidden')

  const typeLabel = mark.dataset.typeLabel || mark.dataset.type || ''
  const label = mark.dataset.label || mark.textContent || ''
  const gloss = mark.dataset.gloss || ''
  const cefrLevel = mark.dataset.cefrLevel || ''
  if (!typeLabel && !label && !gloss && !cefrLevel) return

  const rect = mark.getBoundingClientRect()
  annotationTooltip.innerHTML = ''

  const header = document.createElement('span')
  header.className = 'annotation-tooltip__header'

  if (typeLabel) {
    const chip = document.createElement('span')
    chip.className = 'annotation-tooltip__type'
    chip.textContent = typeLabel
    header.appendChild(chip)
  }

  if (cefrLevel) {
    const cefr = document.createElement('span')
    cefr.className = 'annotation-tooltip__cefr'
    cefr.dataset.cefr = cefrLevel
    cefr.textContent = cefrLevel
    header.appendChild(cefr)
  }

  const labelEl = document.createElement('span')
  labelEl.className = 'annotation-tooltip__label'
  labelEl.textContent = label
  const glossEl = document.createElement('span')
  glossEl.className = 'annotation-tooltip__gloss'
  glossEl.textContent = gloss

  annotationTooltip.append(header, labelEl, glossEl)

  requestAnimationFrame(() => {
    const tipW = annotationTooltip.offsetWidth
    const tipH = annotationTooltip.offsetHeight
    const viewW = window.innerWidth
    const left = Math.max(8, Math.min(rect.left + rect.width / 2 - tipW / 2, viewW - tipW - 8))
    const top = rect.top >= tipH + 10 ? rect.top - tipH - 6 : rect.bottom + 6
    annotationTooltip.style.left = `${left}px`
    annotationTooltip.style.top = `${top}px`
  })
}

function _hideAnnotationTooltip() {
  if (!annotationTooltip) return
  annotationTooltip.setAttribute('hidden', '')
  annotationTooltip.setAttribute('aria-hidden', 'true')
}

results.addEventListener('mouseover', e => {
  const mark = e.target?.closest?.('.reader-annotation')
  if (mark) _showAnnotationTooltip(mark)
  else _hideAnnotationTooltip()
})

results.addEventListener('mouseout', e => {
  if (!e.relatedTarget?.closest?.('.reader-annotation')) _hideAnnotationTooltip()
})

results.addEventListener('focusin', e => {
  const mark = e.target?.closest?.('.reader-annotation')
  if (mark) _showAnnotationTooltip(mark)
})

results.addEventListener('focusout', e => {
  if (!e.relatedTarget?.closest?.('.reader-annotation')) _hideAnnotationTooltip()
})

document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && !annotationTooltip?.hasAttribute('hidden')) _hideAnnotationTooltip()
})

paneBackdrop?.addEventListener('click', () => detailPane?.hide())

// Navigate from a confusable-family link inside the detail pane.
detailPane?.addEventListener('pane-navigate', async (event) => {
  const { objectId, language } = event.detail
  if (!objectId || !language) return
  const caps   = languageCapabilities.get(language)
  const ttsTag = caps?.tts_lang_tag ?? language
  const dir    = caps?.direction ?? 'ltr'
  try {
    const url = `${API_BASE}/lesson/${encodeURIComponent(objectId)}?language=${encodeURIComponent(language)}&depth=${encodeURIComponent(currentDepth())}`
    const response = await fetch(url, { headers: getAuthHeaders() })
    if (!response.ok) return
    const lesson = await response.json()
    const progressRows = await getTermProgress(language)
    const dueQueue = progressRows.filter((row) => row.review_bucket === 'due').slice(0, 8)
    if (!detailPane) return
    const uiLang = currentUiLang()
    const termProgress = progressRows.find(row => row.source_lesson_ids?.includes(lesson.id)) ?? null
    openDetail()
    paneBackdrop?.classList.add('is-visible')

    detailPane.show({
      lesson,
      sentenceText: '',
      language,
      dir,
      ttsTag,
      caps,
      depth: currentDepth(),
      uiLang,
      onTranslate: makeTranslateCallback(lesson),
      reviewQueue: dueQueue,
      termProgress,
      onSpeak:  (text, l) => speakText(text, l ?? ttsTag),
      onStudy:  () => modal.open({
        lesson,
        objectId: lesson.id,
        caps,
        language,
        onRate:  submitReview,
        onSpeak: (text) => speakText(text, ttsTag),
        onCheckResult: (check) => { void submitLessonCheck(lesson, language, check) },
      }),
    })
  } catch { /* ignore — confusable may not be in store yet */ }
})

// ── Render sentence cards ─────────────────────────────────────────────────────

export function renderResults(pipelinePayload, language) {
  _clearResultsDifficultyBadge()
  const payload = validateLessonPipelinePayload(pipelinePayload)
  const sentences = payload.sentences
  const fragment  = document.createDocumentFragment()
  const caps      = languageCapabilities.get(language)
  const dir       = caps?.direction         ?? 'ltr'
  const tokenMode = caps?.tokenization_mode ?? 'whitespace'
  const scriptFam = caps?.script_family     ?? 'latin'
  const ttsTag    = caps?.tts_lang_tag ?? language

  setCurrentSentences(sentences)
  setCurrentTtsTag(ttsTag)

  // Prose container — all sentences flow inline as one continuous paragraph.
  const prose = document.createElement('div')
  prose.className = 'reader-prose'
  prose.setAttribute('lang', language)
  prose.setAttribute('dir',  dir)

  for (const [sentenceIdx, sentence] of sentences.entries()) {
    if (sentenceIdx > 0) prose.appendChild(document.createTextNode(' '))

    const row = document.createElement('span')
    row.className = 'reader-sentence sentence-card'
    row.dataset.tokenization  = tokenMode
    row.dataset.sentenceIndex = sentenceIdx

    if (canSpeak) {
      const playBtn = document.createElement('button')
      playBtn.type      = 'button'
      playBtn.className = 'reader-gutter-btn sentence-card__play-btn'
      playBtn.setAttribute('aria-label',   ti('aria_play_sentence_n', { n: sentenceIdx + 1 }))
      playBtn.setAttribute('aria-pressed', 'false')
      const icon = document.createElement('span')
      icon.className   = 'play-icon'
      icon.setAttribute('aria-hidden', 'true')
      icon.textContent = '▶'
      playBtn.appendChild(icon)
      playBtn.addEventListener('click', () => {
        if (playbackEngine.state !== 'idle' && playbackEngine.current?.index === sentenceIdx) {
          playbackEngine.togglePause()
        } else {
          playbackEngine.speak(sentence.text, ttsTag, 'sentence', sentenceIdx)
        }
      })
      row.appendChild(playBtn)
    }

    const debugRanges = []
    row.appendChild(
      buildAnnotatedText(sentence.text, sentence.learnable_objects, language, dir, tokenMode, scriptFam, debugRanges)
    )
    row.dataset.debugRanges = JSON.stringify(debugRanges)
    if (debugRanges.some(r => r.status !== 'selected')) row.dataset.debugIssue = 'true'

    // Translate toggle — skip when reading language matches UI language
    if (language !== currentUiLang()) {
      const translateBtn = document.createElement('button')
      translateBtn.type      = 'button'
      translateBtn.className = 'reader-sentence__translate-btn'
      translateBtn.setAttribute('aria-expanded', 'false')
      translateBtn.setAttribute('aria-label', t('sentence_translate'))
      translateBtn.textContent = t('sentence_translate')

      const translationEl = document.createElement('span')
      translationEl.className = 'reader-sentence__translation'
      translationEl.hidden    = true

      translateBtn.addEventListener('click', () => {
        const expanded = translateBtn.getAttribute('aria-expanded') === 'true'
        if (expanded) {
          translateBtn.setAttribute('aria-expanded', 'false')
          translationEl.hidden = true
        } else {
          translateBtn.setAttribute('aria-expanded', 'true')
          translationEl.hidden = false
          fetchSentenceTranslation(sentenceIdx, sentence.text, language, translationEl)
        }
      })

      row.appendChild(translateBtn)
      row.appendChild(translationEl)
    }

    prose.appendChild(row)
  }

  fragment.appendChild(prose)

  results.replaceChildren(fragment)
  applyScriptViewToResults()
  updateScriptViewToolbar()
  requestAnimationFrame(buildMinimap)

  setResultsHeading(currentDocumentTitle(), currentDocumentEyebrow())
  if (resultsSection) resultsSection.hidden = false
  if (siteHero) siteHero.hidden = true
  if (parseDialog) parseDialog.hidden = true
  if (changeLessonBtn) changeLessonBtn.hidden = false

  // #/lesson/:id — was the parse-dialog's close() call. Falls back to a
  // generic id for ad-hoc pasted/fetched text that has no corpus document id
  // yet (only saved/loaded sources have one) — degrades gracefully rather
  // than overclaiming a specific identity for unsaved text.
  navigate(`#/lesson/${encodeURIComponent(_currentSourceDocId ?? 'current')}`)

  // Show "Practice confusables" button only when the text has nuance items
  if (corpusDrillsBtn) {
    const hasNuance = sentences.some(s =>
      s.learnable_objects.some(o => o.type === 'nuance')
    )
    corpusDrillsBtn.hidden = !hasNuance
  }

  if (filterBar) {
    const allObjects = sentences.flatMap(s => s.learnable_objects ?? [])
    const allTypes = [...new Set(allObjects.map(o => o.type).filter(Boolean))]
    const hasPoetic = allObjects.some(o => o.lesson_data?.is_poetic_citation)
    if (hasPoetic) allTypes.push('poetic_citation')
    filterBar.setAvailable(allTypes)
    filterBar.reset()
    filterBar.hidden = allTypes.length === 0
    if (appFilterBar) appFilterBar.hidden = allTypes.length === 0
    setActiveSearchTerm('')
    if (annotationSearch) annotationSearch.value = ''
  }

  if (nowPlayingBar) {
    let trackTitle = ''
    if (currentSourceUrl()) {
      try { trackTitle = new URL(currentSourceUrl()).hostname } catch { /* noop */ }
    } else if (currentFilename()) {
      trackTitle = currentFilename()
    }
    nowPlayingBar.setAttribute('track-title', trackTitle)
  }

  if (resultsTransport) {
    const show = canSpeak && sentences.length > 0
    resultsTransport.hidden = !show
    if (show && playbackEngine.state === 'idle') {
      const totalChars = sentences.reduce((s, r) => s + (r.text?.length ?? 0), 0)
      const estDur = Math.max(totalChars / 14, 2)
      if (resultsTimeLabel) resultsTimeLabel.textContent = `00:00 / ${_transportFmt(estDur)}`
      if (resultsScrubber) resultsScrubber.value = '0'
    }
  }

  _buildSubcategoryBar(sentences)
}

function _buildSubcategoryBar(sentences) {
  const bar = document.querySelector('#subcategory-bar')
  if (!bar) return
  const subcats = new Set(
    sentences.flatMap(s => s.learnable_objects ?? [])
      .map(o => o.lesson_data?.subcategory)
      .filter(Boolean)
  )
  if (subcats.size === 0) { bar.hidden = true; return }
  bar.replaceChildren()
  for (const sub of subcats) {
    const chip = document.createElement('span')
    chip.className = 'subcategory-bar__chip'
    chip.textContent = subcategoryLabel(sub)
    chip.dataset.subcategory = sub
    bar.appendChild(chip)
  }
  bar.hidden = false
}

// ── Inline annotation builder ─────────────────────────────────────────────────

function buildAnnotatedText(text, items, language, dir, tokenMode, scriptFam, debugRanges = []) {
  const p = document.createElement('span')
  p.className = 'sentence-card__text reader-sentence__text'
  p.setAttribute('lang', language)
  p.setAttribute('dir',  dir)
  p.dataset.tokenization = tokenMode
  p.dataset.scriptFamily = scriptFam
  p.dataset.layer        = 'native'

  if (!items.length) {
    p.textContent = text
    return p
  }

  const lower  = text.toLowerCase()
  const ranges = []

  for (const item of items) {
    if (!item.label) continue
    const needle = item.label.toLowerCase()
    let pos = 0
    while (pos < lower.length) {
      const idx = lower.indexOf(needle, pos)
      if (idx === -1) break
      ranges.push({ start: idx, end: idx + item.label.length, item })
      debugRanges.push({ label: item.label, type: item.type, start: idx, end: idx + item.label.length, status: 'candidate' })
      pos = idx + 1
    }
  }

  const typePriority = {
    conjugation: 6,
    inflection: 5,
    vocabulary: 5,
    nuance: 4,
    grammar: 4,
    idiom: 3,
    phrase_family: 3,
    agreement: 2,
    case_agreement: 2,
  }
  const priorityOf = (r) => typePriority[r?.item?.type] ?? 1

  // Sort by start, then pedagogical priority, then longer match.
  ranges.sort((a, b) => (
    a.start - b.start
    || priorityOf(b) - priorityOf(a)
    || (b.end - b.start) - (a.end - a.start)
  ))

  // Greedy non-overlapping selection with replacement if a higher-priority
  // span competes with the most-recent selected span.
  const selected = []
  for (const r of ranges) {
    const prev = selected[selected.length - 1]
    const overlapsPrev = Boolean(prev) && r.start < prev.end
    if (overlapsPrev) {
      const better = priorityOf(r) > priorityOf(prev)
      const samePriLonger = priorityOf(r) === priorityOf(prev)
        && (r.end - r.start) > (prev.end - prev.start)
      if (better || samePriLonger) {
        const prevMatch = debugRanges.find(x => x.start === prev.start && x.end === prev.end && x.label === prev.item.label)
        if (prevMatch) prevMatch.status = 'overlap_skipped'
        selected[selected.length - 1] = r
        const match = debugRanges.find(x => x.start === r.start && x.end === r.end && x.label === r.item.label)
        if (match) match.status = 'selected'
      } else {
        const match = debugRanges.find(x => x.start === r.start && x.end === r.end && x.label === r.item.label)
        if (match) match.status = 'overlap_skipped'
      }
      continue
    }

    selected.push(r)
    const match = debugRanges.find(x => x.start === r.start && x.end === r.end && x.label === r.item.label)
    if (match) match.status = 'selected'
  }

  let cursor = 0
  for (const { start, end, item } of selected) {
    if (cursor < start) p.appendChild(document.createTextNode(text.slice(cursor, start)))

    const mark = document.createElement('mark')
    mark.className    = 'reader-annotation'
    if (item.type) mark.classList.add('reader-annotation--' + item.type)
    mark.dataset.type      = item.type
    mark.dataset.objectId  = item.id
    mark.dataset.level     = String(TYPE_LEVEL[item.type] ?? 1)
    mark.dataset.typeLabel = t(TYPE_LABEL_KEYS[item.type] ?? 'type_unknown')
    mark.dataset.label     = item.label ?? ''
    const _gloss = item.lesson_data?.gloss || item.lesson_data?.translation || ''
    if (_gloss)                        mark.dataset.gloss     = _gloss
    if (item.lesson_data?.cefr_level)  mark.dataset.cefrLevel = item.lesson_data.cefr_level
    // Register (neutral/literary/formal/informal/archaic) — used by
    // applyAnnotationFilter() to route literary/archaic-register nuance and
    // phrase_family marks under the Literary pill instead of Idioms, even
    // though those types default to the Idioms category (see _TYPE_TO_CATEGORY).
    if (item.lesson_data?.register)          mark.dataset.register        = item.lesson_data.register
    if (item.lesson_data?.is_poetic_citation) mark.dataset.isPoeticCitation = '1'
    mark.setAttribute('role', 'button')
    mark.setAttribute('tabindex', '0')
    const typeLong  = TYPE_LABELS_LONG_I18N[currentUiLang()]?.[`type_${item.type}_long`]
               ?? TYPE_LABELS_LONG_I18N.en[`type_${item.type}_long`]
    mark.setAttribute('aria-label', typeLong)
    mark.textContent = text.slice(start, end)
    if (localStorage.getItem(`mn-note-${item.id}`)) mark.setAttribute('data-has-note', '')
    mark.addEventListener('click', () => {
      mark.dispatchEvent(new CustomEvent('lesson-open', {
        bubbles: true,
        detail:  { objectId: item.id, language },
      }))
    })
    mark.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); mark.click() }
    })
    mark.addEventListener('focus', () => announce(ti('aria_annotation_focus', { label: item.label })))
    p.appendChild(mark)
    cursor = end
  }

  if (cursor < text.length) p.appendChild(document.createTextNode(text.slice(cursor)))

  return p
}

// ── Annotation density minimap ────────────────────────────────────────────────

const _MINIMAP_COLORS = {
  // vocab
  vocabulary:          'var(--ann-vocab)',
  lexical_item:        'var(--ann-vocab)',
  word_form:           'var(--ann-vocab)',
  vocab:               'var(--ann-vocab)',
  word:                'var(--ann-vocab)',
  memory_map:          'var(--ann-vocab)',
  // grammar
  grammar:             'var(--ann-grammar)',
  grammatical_pattern: 'var(--ann-grammar)',
  morphology:          'var(--ann-grammar)',
  grammar_point:       'var(--ann-grammar)',
  syntax:              'var(--ann-grammar)',
  conjugation:         'var(--ann-grammar)',
  agreement:           'var(--ann-grammar)',
  inflection:          'var(--ann-grammar)',
  // idioms
  idiom:               'var(--ann-idiom)',
  expression:          'var(--ann-idiom)',
  phrase:              'var(--ann-idiom)',
  collocation:         'var(--ann-idiom)',
  proverb:             'var(--ann-idiom)',
  // idioms (nuance/phrase_family route to idioms, not literary — see _TYPE_TO_CATEGORY)
  nuance:              'var(--ann-idiom)',
  phrase_family:       'var(--ann-idiom)',
  // literary
  literary:            'var(--ann-literary)',
  literary_device:     'var(--ann-literary)',
  nuance_or_style:     'var(--ann-literary)',
  cultural_note:       'var(--ann-literary)',
  rhetoric:            'var(--ann-literary)',
  figure_of_speech:    'var(--ann-literary)',
  poetic:              'var(--ann-literary)',
  // etymology
  etymology:           'var(--ann-etymology)',
  derivation:          'var(--ann-etymology)',
  cognate:             'var(--ann-etymology)',
  root:                'var(--ann-etymology)',
  script:              'var(--ann-etymology)',
  transliteration:     'var(--ann-etymology)',
}

const _TYPE_TO_CATEGORY = {
  vocabulary: 'vocab', lexical_item: 'vocab', word_form: 'vocab',
  vocab: 'vocab', word: 'vocab', memory_map: 'vocab',
  grammar: 'grammar', grammatical_pattern: 'grammar', morphology: 'grammar',
  grammar_point: 'grammar', syntax: 'grammar', conjugation: 'grammar',
  agreement: 'grammar', inflection: 'grammar',
  idiom: 'idioms', expression: 'idioms', phrase: 'idioms',
  collocation: 'idioms', proverb: 'idioms',
  nuance: 'idioms', phrase_family: 'idioms', literary: 'literary',
  literary_device: 'literary', nuance_or_style: 'literary', cultural_note: 'literary',
  rhetoric: 'literary', figure_of_speech: 'literary', poetic: 'literary',
  etymology: 'etymology', derivation: 'etymology', cognate: 'etymology',
  root: 'etymology', script: 'etymology', transliteration: 'etymology',
}

function buildMinimap() {
  if (!annotationMinimap) return
  annotationMinimap.replaceChildren()

  const marks = Array.from(results.querySelectorAll('.reader-annotation:not([data-filtered])'))
  if (!marks.length) {
    annotationMinimap.hidden = true
    if (minimapLegend) minimapLegend.hidden = true
    return
  }

  const region = annotationMinimap.parentElement
  const regionRect = region.getBoundingClientRect()
  const regionTop  = regionRect.top + window.scrollY
  const totalH     = region.offsetHeight
  if (!totalH) return

  const presentCats = new Set()
  const frag = document.createDocumentFragment()
  marks.forEach(mark => {
    const markRect = mark.getBoundingClientRect()
    const markTop  = markRect.top + window.scrollY
    const pct      = Math.max(0, Math.min(99, (markTop - regionTop) / totalH * 100))
    const tick     = document.createElement('button')
    tick.type      = 'button'
    tick.className = 'annotation-minimap__tick'
    tick.style.top        = `${pct.toFixed(2)}%`
    tick.style.background = _MINIMAP_COLORS[mark.dataset.type] ?? 'var(--accent)'
    // Same register override as applyAnnotationFilter() — keep the minimap
    // legend's category dots consistent with what the filter pills actually do.
    let cat = _TYPE_TO_CATEGORY[mark.dataset.type]
    if (mark.dataset.type === 'nuance' || mark.dataset.type === 'phrase_family') {
      const register = mark.dataset.register ?? ''
      cat = (register === 'literary' || register === 'archaic') ? 'literary' : 'idioms'
    }
    if (cat) { tick.dataset.category = cat; presentCats.add(cat) }
    const label = (mark.dataset.type ?? '') + (mark.textContent.trim() ? ': ' + mark.textContent.trim().slice(0, 40) : '')
    tick.setAttribute('aria-label', label)
    tick.addEventListener('click', () => {
      mark.scrollIntoView({ behavior: 'smooth', block: 'center' })
      mark.classList.add('reader-annotation--jump-flash')
      setTimeout(() => mark.classList.remove('reader-annotation--jump-flash'), 700)
    })
    frag.appendChild(tick)
  })
  annotationMinimap.appendChild(frag)
  annotationMinimap.hidden = false

  _updateMinimapLegend(presentCats)
}

function _updateMinimapLegend(presentCats) {
  if (!minimapLegend) return
  minimapLegend.querySelectorAll('.minimap-legend__dot').forEach(dot => {
    const cat = dot.dataset.cat
    const isPresent = presentCats.has(cat)
    const isActive  = !activeFilterCategories() || activeFilterCategories().has(cat)
    dot.classList.toggle('minimap-legend__dot--present', isPresent && !isActive)
    dot.classList.toggle('minimap-legend__dot--active',  isPresent && isActive)
  })
  minimapLegend.hidden = false
}

// ── Annotation filters ────────────────────────────────────────────────────────

export function applyAnnotationFilter() {
  const depthTypes = ANNOTATION_DEPTH_MODEL[currentDepth()] ?? ANNOTATION_DEPTH_MODEL[DEPTH_FALLBACK]
  results?.querySelectorAll('.reader-annotation').forEach(mark => {
    const type = mark.dataset.type

    // Session filter (pill click): show exactly those types, overriding global depth.
    // No session filter: depth model applies, but locked categories are always shown.
    let typeAllowed
    if (activeFilterTypes() !== null) {
      typeAllowed = activeFilterTypes().has(type)
    } else {
      typeAllowed = depthTypes.has(type) || activeLockedTypes().has(type)
    }

    // Verse filter: show only is_poetic_citation annotations.
    if (activeFilterCategories()?.has('verse')) {
      typeAllowed = mark.dataset.isPoeticCitation === '1'
    } else if ((type === 'nuance' || type === 'phrase_family') && activeFilterCategories()) {
      // Register override: nuance/phrase_family default to the Idioms category
      // (_TYPE_TO_CATEGORY / filter-bar CATEGORIES), but a literary- or
      // archaic-register instance belongs under Literary instead.
      const register = mark.dataset.register ?? ''
      const effectiveCategory = (register === 'literary' || register === 'archaic') ? 'literary' : 'idioms'
      typeAllowed = activeFilterCategories().has(effectiveCategory)
    }

    const term = activeSearchTerm()
    const searchAllowed = !term
      || mark.textContent.toLowerCase().includes(term)
      || (mark.dataset.label ?? '').toLowerCase().includes(term)
    mark.toggleAttribute('data-filtered', !(typeAllowed && searchAllowed))

  })
  requestAnimationFrame(buildMinimap)
}

if (annotationSearch) {
  let _searchDebounce = null
  annotationSearch.addEventListener('input', () => {
    clearTimeout(_searchDebounce)
    _searchDebounce = setTimeout(() => {
      setActiveSearchTerm(annotationSearch.value.trim().toLowerCase())
      applyAnnotationFilter()
    }, 180)
  })
  annotationSearch.addEventListener('search', () => {
    setActiveSearchTerm(annotationSearch.value.trim().toLowerCase())
    applyAnnotationFilter()
  })
}

// ── Playback controls ─────────────────────────────────────────────────────────

rnpPrev?.addEventListener('click',   () => playbackEngine.prev())
rnpToggle?.addEventListener('click', () => playbackEngine.togglePause())
rnpStop?.addEventListener('click',   () => playbackEngine.stop())
rnpNext?.addEventListener('click',   () => playbackEngine.next())

resultsPlayBtn?.addEventListener('click', () => {
  if (playbackEngine.state === 'idle') {
    playbackEngine.playAll(
      currentSentences().map(s => ({ text: s.text, langTag: currentTtsTag() }))
    )
  } else {
    playbackEngine.stop()
  }
})

playbackEngine.addEventListener('state-change', ({ detail: { state, current, index, total } }) => {
  // Reading progress bar — show during multi-item playback
  if (readingProgress) {
    if (state === 'idle' || total <= 1) {
      readingProgress.hidden = true
      readingProgress.style.removeProperty('--progress')
    } else {
      const progress = (index + 1) / total
      readingProgress.style.setProperty('--progress', String(progress))
      readingProgress.hidden = false
      readingProgress.setAttribute('aria-valuenow', String(Math.round(progress * 100)))
    }
  }

  // Active sentence highlight + per-card button icons
  results?.querySelectorAll('.sentence-card').forEach((card) => {
    const cardIdx = parseInt(card.dataset.sentenceIndex ?? '-1', 10)
    const isActive = state !== 'idle' && current?.index === cardIdx
    card.classList.toggle('sentence-card--playing', isActive)

    const btn  = card.querySelector('.sentence-card__play-btn')
    const icon = btn?.querySelector('.play-icon')
    if (!btn || !icon) return
    const isPlaying = isActive && state === 'playing'
    icon.textContent = isPlaying ? '⏸' : '▶'
    btn.setAttribute('aria-label',   isPlaying ? t('aria_pause') : t('aria_play_sentence'))
    btn.setAttribute('aria-pressed', String(isActive))
  })

  // Results transport sync
  if (resultsPlayBtn) {
    const idle = state === 'idle'
    resultsPlayBtn.innerHTML        = idle ? `&#x25B6;&thinsp;${t('aria_play_all_sentences')}` : `&#x23F9;&thinsp;${t('aria_stop')}`
    resultsPlayBtn.setAttribute('aria-label', idle ? t('aria_play_all_sentences') : t('aria_stop'))
  }
  if (state === 'playing' && !_transportWallStart) {
    _transportStart()
  } else if (state === 'paused') {
    _transportPause()
  } else if (state === 'idle') {
    _transportReset()
  } else if (state === 'playing' && _transportWallStart && _transportTimerId === null) {
    _transportStart()
  }

  // Follow-along: scroll active sentence into view
  if (isFollowAlongEnabled() && state === 'playing' && current) {
    const activeCard = results?.querySelector(`[data-sentence-index="${current.index}"]`)
    activeCard?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }

  // Reader now-playing card
  if (readerNowPlaying) {
    const idle = state === 'idle'
    readerNowPlaying.hidden = idle
    if (!idle && current) {
      if (rnpText)    rnpText.textContent    = current.text
      if (rnpCounter) rnpCounter.textContent = `${index + 1} / ${total}`
    }
    if (rnpToggle) {
      const isPaused = state === 'paused'
      rnpToggle.textContent = isPaused ? '▶' : '⏸'
      rnpToggle.setAttribute('aria-label', isPaused ? t('aria_resume') : t('aria_pause'))
    }
  }
})

// ── NowPlayingBar teleportation ───────────────────────────────────────────────
// Mobile: move bar into detail pane's now-playing slot so it appears at the
// bottom of the bottom sheet. Desktop: return it to .app-shell__left.

const _leftCol = document.querySelector('.app-shell__left')
const _npMq    = window.matchMedia('(max-width: 53.99rem)')

function _relocateNowPlayingBar(mobile) {
  if (!nowPlayingBar) return
  if (mobile) {
    nowPlayingBar.setAttribute('slot', 'now-playing')
    detailPane?.appendChild(nowPlayingBar)
  } else {
    nowPlayingBar.removeAttribute('slot')
    _leftCol?.appendChild(nowPlayingBar)
  }
}

_npMq.addEventListener('change', e => _relocateNowPlayingBar(e.matches))

// ── Route handling ────────────────────────────────────────────────────────────
// #/lesson/:id shows the results section (and the #/explore entry form stays
// hidden); any other route hides results so it doesn't bleed into #/library,
// #/review, etc. Results content itself is populated by renderResults(),
// called from explorer.js/library.js — this handler only owns visibility.

function _applyLessonRoute(route) {
  if (!resultsSection) return
  if (route.path === 'lesson') {
    // Only reveal if a lesson has actually been rendered (results section
    // has content); otherwise leave the explore form as the visible surface.
    if (results?.children.length) resultsSection.hidden = false
  } else {
    resultsSection.hidden = true
  }
}

/**
 * initLesson() — runs the NowPlayingBar's initial placement based on the
 * current viewport, registers the #/lesson route handler, and kicks off the
 * 'lesson' and 'annotations' i18n bundles (fire-and-forget — not awaited,
 * since a user needs several seconds at minimum to type/paste text and
 * trigger a parse, which is ample time for these to resolve before
 * renderResults() or the detail pane ever reads from them; t()/ti() degrade
 * gracefully to the raw key in the rare case a bundle hasn't landed yet).
 * Both load together here, not just 'annotations' on first detail-pane
 * open as the lazy-load trigger points might suggest in isolation, because
 * TYPE_LABELS_LONG_I18N (in the 'annotations' bundle) is read during
 * sentence/annotation rendering — i.e. at parse-render time, not only when
 * the pane opens. Everything else in this module wires itself at import
 * time (event listeners on #results/#detail-pane/#annotation-search),
 * which matches how main.js originally ran this code unconditionally on load.
 */
export function initLesson() {
  _relocateNowPlayingBar(_npMq.matches)
  onRoute(_applyLessonRoute)
  loadBundle('lesson')
  loadBundle('annotations')
}
