/**
 * js/modes/review.js — Review concerns: submission, offline queue, and
 * corpus confusable drills. Also re-exports initReviewSession from
 * js/review-session.js so this module is the single entry point for all
 * review concerns.
 *
 * Owns: Review submission, Offline review queue, Corpus confusable drills.
 */
import { API_BASE } from '../config.js'
import { getAuthHeaders } from '../auth.js'
import { t, ti, loadBundle } from '../i18n.js'
import {
  queueReview,
  getPendingReviews,
  deleteReview,
  countPendingReviews,
} from '../offline.js'
import { initReviewSession } from '../review-session.js'
import { setStatus } from '../shared.js'
import { currentSentences, languageCapabilities } from '../reading-state.js'
import { speakText } from './lesson.js'

export { initReviewSession }

const reviewStateByObject    = new Map()
const termProgressByLanguage = new Map()

// ── Review submission ─────────────────────────────────────────────────────────

export async function submitReview(objectId, quality, wrongAnswer = null) {
  const body = {
    object_id:    objectId,
    quality,
    review_state: reviewStateByObject.get(objectId) ?? null,
    ...(wrongAnswer ? { wrong_answer: wrongAnswer } : {}),
  }

  let response
  try {
    response = await fetch(`${API_BASE}/review`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body:    JSON.stringify(body),
    })
  } catch {
    await queueReview({ ...body, queued_at: Date.now() })
    updateOfflineBadge()
    return null
  }

  if (!response.ok) {
    const detail = await response.json().catch(() => null)
    throw new Error(detail?.detail ?? `Review failed (${response.status})`)
  }

  const payload = await response.json()
  reviewStateByObject.set(objectId, payload.review_state)
  return payload
}

export async function submitLessonCheck(lesson, language, check) {
  const term = check?.term || lesson?.lesson_data?.lemma || lesson?.examples?.[0] || lesson?.title
  if (!term || !language || !check) return
  const response = await fetch(`${API_BASE}/term-progress`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify({
      term,
      lemma: lesson?.lesson_data?.lemma || term,
      language,
      seen: true,
      reviewed: true,
      correct: Boolean(check.correct),
      mastery_delta: check.correct ? 0.08 : -0.1,
      source_lesson_id: lesson.id,
    }),
  })
  termProgressByLanguage.delete(language)
  if (response.ok && lesson?.id) {
    try {
      const tp = await response.json()
      window.dispatchEvent(new CustomEvent('mnemosyne:practice-result', {
        detail: {
          objectId:      lesson.id,
          masteryScore:  tp.mastery_score,
          nextReviewAt:  tp.next_review_at,
          reviewCount:   tp.review_count,
          correctCount:  tp.correct_count,
          incorrectCount: tp.incorrect_count,
          reviewBucket:  tp.review_bucket,
        },
      }))
    } catch {}
  }
}

export async function getTermProgress(language) {
  if (!language) return []
  if (termProgressByLanguage.has(language)) return termProgressByLanguage.get(language) || []
  try {
    const response = await fetch(`${API_BASE}/term-progress/${encodeURIComponent(language)}?limit=300`, {
      headers: { ...getAuthHeaders() },
    })
    if (!response.ok) return []
    const rows = await response.json()
    termProgressByLanguage.set(language, rows)
    return rows
  } catch {
    return []
  }
}

export function invalidateTermProgress(language) {
  termProgressByLanguage.delete(language)
}

// ── Corpus confusable drills ──────────────────────────────────────────────────

const languageSelect  = document.querySelector('#language')
const corpusDrillsBtn = document.querySelector('#corpus-drills-btn')
const modal           = document.querySelector('#lesson-modal')

export async function openCorpusDrills() {
  // Corpus drills can be reached via the D keyboard shortcut from the
  // reading view, without ever visiting #/review — so the 'review' bundle
  // (which holds the modal_* drill strings) needs an explicit load here too,
  // not just on route entry.
  await loadBundle('review')
  const language = languageSelect?.value
  if (!language) return

  const nuanceTypes = [
    ...new Set(
      currentSentences().flatMap(s =>
        s.learnable_objects
          .filter(o => o.type === 'nuance' && o.lesson_data?.nuance_type)
          .map(o => o.lesson_data.nuance_type)
      )
    ),
  ]
  if (!nuanceTypes.length) return

  setStatus(t('loading'), 'busy')
  try {
    const params = new URLSearchParams({ language, nuance_types: nuanceTypes.join(','), limit: '8' })
    const resp = await fetch(`${API_BASE}/nuance-drills?${params}`, { headers: getAuthHeaders() })
    if (!resp.ok) throw new Error(resp.status)
    const data = await resp.json()
    if (!data.drills?.length) { setStatus(''); return }

    const caps   = languageCapabilities.get(language)
    const ttsTag = caps?.tts_lang_tag ?? language
    const syntheticLesson = {
      id:          `corpus-drills-${language}`,
      title:       t('corpus_drills_btn'),
      type:        'nuance',
      label:       t('corpus_drills_btn'),
      drills:      data.drills,
      nuance_sets: [],
      examples:    [],
      lesson_data: {},
    }
    setStatus('')
    modal.open({
      lesson:        syntheticLesson,
      objectId:      null,
      caps,
      language,
      onRate:        submitReview,
      onSpeak:       (text) => speakText(text, ttsTag),
      onCheckResult: (check) => { void submitLessonCheck(syntheticLesson, language, check) },
    })
  } catch {
    setStatus(t('load_lesson_failed'), 'error')
  }
}

// ── Offline review queue ──────────────────────────────────────────────────────

let _offlineJwtExpired = false

export async function updateOfflineBadge() {
  const badge = document.querySelector('#offline-queue-badge')
  if (!badge) return
  const n = await countPendingReviews()
  if (n === 0) {
    badge.hidden = true
    badge.dataset.state = ''
    _offlineJwtExpired = false
    return
  }
  badge.hidden = false
  if (_offlineJwtExpired) {
    badge.textContent = ti('offline_jwt_expired', { n })
    badge.dataset.state = 'expired'
  } else if (!navigator.onLine) {
    badge.textContent = ti('offline_queued', { n })
    badge.dataset.state = 'offline'
  } else {
    badge.textContent = ti('offline_pending', { n })
    badge.dataset.state = 'pending'
  }
}

async function drainReviewQueue() {
  const pending = await getPendingReviews()
  if (!pending.length) return

  const badge = document.querySelector('#offline-queue-badge')
  if (badge && !badge.hidden) {
    badge.dataset.state = 'syncing'
    badge.textContent = t('offline_syncing')
  }

  let synced = 0
  for (const { key, value } of pending) {
    try {
      const response = await fetch(`${API_BASE}/review`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body:    JSON.stringify({
          object_id:    value.object_id,
          quality:      value.quality,
          review_state: value.review_state ?? null,
        }),
      })
      if (response.ok) {
        await deleteReview(key)
        synced++
      } else if (response.status === 401) {
        _offlineJwtExpired = true
        setStatus(t('session_expired_queue'), 'error')
        await updateOfflineBadge()
        break
      } else {
        await updateOfflineBadge()
        break
      }
    } catch {
      await updateOfflineBadge()
      break
    }
  }

  if (synced > 0) {
    if (badge) {
      badge.hidden = false
      badge.dataset.state = 'synced'
      badge.textContent = ti('offline_synced', { n: synced })
    }
    setTimeout(updateOfflineBadge, 3000)
  } else {
    await updateOfflineBadge()
  }
}

/**
 * initReview() — wires the corpus-drills button, the offline review queue
 * (online/offline listeners, initial badge update) and the offline-queue
 * explain dialog. Call once during app startup.
 */
export function initReview() {
  corpusDrillsBtn?.addEventListener('click', openCorpusDrills)

  window.addEventListener('online', drainReviewQueue)
  window.addEventListener('offline', updateOfflineBadge)
  setTimeout(updateOfflineBadge, 200)

  document.querySelector('#offline-queue-badge')?.addEventListener('click', async () => {
    const n = await countPendingReviews()
    const dialog = document.querySelector('#offline-explain-dialog')
    const body   = document.querySelector('#offline-explain-body')
    if (!dialog || !body) return
    if (_offlineJwtExpired) {
      body.textContent = ti('offline_explain_expired', { n })
    } else if (!navigator.onLine) {
      body.textContent = ti('offline_explain_offline', { n })
    } else {
      body.textContent = ti('offline_explain_pending', { n })
    }
    dialog.showModal()
  })

  document.querySelector('#offline-explain-close')?.addEventListener('click', () => {
    document.querySelector('#offline-explain-dialog')?.close()
  })
}
