/**
 * js/modes/create.js — Saving the current parsed text as a persisted lesson.
 *
 * Owns: #/create/:id route (was #save-lesson-dialog), and the inline
 * save-unsupported notice (was #save-unsupported-dialog) — the save
 * lifecycle, distinct from the library display in library.js, which owns
 * the load/browse surfaces once sources exist.
 */
import { API_BASE } from '../config.js'
import { getAuthHeaders, getUser, ownerEmail } from '../auth.js'
import { t } from '../i18n.js'
import { refreshLoadLessonBtn } from './library.js'
// currentText/currentSourceUrl belong to explorer.js's picker-intake flow;
// read here through the DOM-free getters explorer.js exports for this
// purpose rather than duplicating that state.
import { committedTextValue, committedSourceUrlValue } from './explorer.js'
import { currentSourceDocId } from './lesson.js'
import { navigate, onRoute } from '../router.js'

// ── DOM references ────────────────────────────────────────────────────────────

const languageSelect = document.querySelector('#language')
const saveLessonBtn  = document.querySelector('#save-lesson-btn')

// Was #save-lesson-dialog — now the #/create/:id route's section.
const saveLessonDialog     = document.querySelector('#route-create')
const saveTitleInput       = document.querySelector('#save-title')
const saveLessonStatus     = document.querySelector('#save-lesson-status')
const saveLessonCloseBtn   = document.querySelector('#save-lesson-close-btn')
const saveLessonConfirmBtn = document.querySelector('#save-lesson-confirm-btn')

// Was #save-unsupported-dialog — now an inline notice within #route-create.
const saveUnsupportedDialog   = document.querySelector('#save-unsupported-inline')
const saveUnsupportedOkBtn    = document.querySelector('#save-unsupported-ok-btn')

// ── #/create/:id route (was the save-lesson dialog) ───────────────────────────

function _navigateToCreate() {
  navigate(`#/create/${encodeURIComponent(currentSourceDocId() ?? 'current')}`)
}

saveLessonBtn?.addEventListener('click', () => {
  const owner = ownerEmail()
  if (owner && getUser()?.email !== owner) {
    _navigateToCreate()
    if (saveUnsupportedDialog) saveUnsupportedDialog.hidden = false
    return
  }
  _navigateToCreate()
  if (saveUnsupportedDialog) saveUnsupportedDialog.hidden = true
  saveTitleInput?.focus()
})

saveLessonCloseBtn?.addEventListener('click', () => navigate('#/explore'))

saveLessonConfirmBtn?.addEventListener('click', async () => {
  const title = saveTitleInput?.value.trim() ?? ''
  if (!title) {
    if (saveLessonStatus) {
      saveLessonStatus.textContent = t('text_empty_error')
      saveLessonStatus.dataset.state = 'error'
    }
    saveTitleInput?.focus()
    return
  }
  const language = languageSelect?.value
  const currentText = committedTextValue()
  if (!currentText || !language) { navigate('#/explore'); return }
  try {
    const resp = await fetch(`${API_BASE}/ingest`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body:    JSON.stringify({ text: currentText, language, title, source_url: committedSourceUrlValue() || null }),
    })
    if (!resp.ok) throw new Error(resp.status)
    const ingestData = await resp.json()
    navigate('#/explore')
    refreshLoadLessonBtn()
    window.mnemosyneRecommended?.reload(ingestData.source_document_id ?? null)
  } catch {
    if (saveLessonStatus) {
      saveLessonStatus.textContent = t('parse_error_generic')
      saveLessonStatus.dataset.state = 'error'
    }
  }
})

// ── Save-unsupported inline notice ────────────────────────────────────────────

saveUnsupportedOkBtn?.addEventListener('click', () => navigate('#/explore'))

// ── Route handling ────────────────────────────────────────────────────────────

function _applyCreateRoute(route) {
  if (saveLessonDialog) saveLessonDialog.hidden = route.path !== 'create'
}

/**
 * initCreate() — registers the #/create/:id route handler. All other
 * create.js event listeners wire themselves at import time, matching how
 * this code ran unconditionally in the original main.js.
 */
export function initCreate() {
  onRoute(_applyCreateRoute)
}
