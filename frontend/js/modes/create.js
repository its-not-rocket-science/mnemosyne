/**
 * js/modes/create.js — Saving the current parsed text as a persisted lesson.
 *
 * Owns: Save-lesson dialog, Save-unsupported dialog (the save lifecycle,
 * distinct from the library display in library.js, which owns the
 * load/browse dialogs once sources exist).
 */
import { API_BASE, OWNER_EMAIL } from '../config.js'
import { getAuthHeaders, getUser } from '../auth.js'
import { t } from '../i18n.js'
import { refreshLoadLessonBtn } from './library.js'
// currentText/currentSourceUrl belong to explorer.js's picker-intake flow;
// read here through the DOM-free getters explorer.js exports for this
// purpose rather than duplicating that state.
import { committedTextValue, committedSourceUrlValue } from './explorer.js'

// ── DOM references ────────────────────────────────────────────────────────────

const languageSelect = document.querySelector('#language')
const saveLessonBtn  = document.querySelector('#save-lesson-btn')

const saveLessonDialog     = document.querySelector('#save-lesson-dialog')
const saveTitleInput       = document.querySelector('#save-title')
const saveLessonStatus     = document.querySelector('#save-lesson-status')
const saveLessonCloseBtn   = document.querySelector('#save-lesson-close-btn')
const saveLessonConfirmBtn = document.querySelector('#save-lesson-confirm-btn')

const saveUnsupportedDialog   = document.querySelector('#save-unsupported-dialog')
const saveUnsupportedCloseBtn = document.querySelector('#save-unsupported-close-btn')
const saveUnsupportedOkBtn    = document.querySelector('#save-unsupported-ok-btn')

// ── Save-lesson dialog ────────────────────────────────────────────────────────

saveLessonBtn?.addEventListener('click', () => {
  if (getUser()?.email !== OWNER_EMAIL) {
    saveUnsupportedDialog?.showModal()
    return
  }
  saveLessonDialog?.showModal()
  saveTitleInput?.focus()
})

saveLessonCloseBtn?.addEventListener('click', () => saveLessonDialog?.close())

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
  if (!currentText || !language) { saveLessonDialog?.close(); return }
  try {
    const resp = await fetch(`${API_BASE}/ingest`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body:    JSON.stringify({ text: currentText, language, title, source_url: committedSourceUrlValue() || null }),
    })
    if (!resp.ok) throw new Error(resp.status)
    const ingestData = await resp.json()
    saveLessonDialog?.close()
    refreshLoadLessonBtn()
    window.mnemosyneRecommended?.reload(ingestData.source_document_id ?? null)
  } catch {
    if (saveLessonStatus) {
      saveLessonStatus.textContent = t('parse_error_generic')
      saveLessonStatus.dataset.state = 'error'
    }
  }
})

// ── Save-unsupported dialog ───────────────────────────────────────────────────

saveUnsupportedCloseBtn?.addEventListener('click', () => saveUnsupportedDialog?.close())
saveUnsupportedOkBtn?.addEventListener('click',    () => saveUnsupportedDialog?.close())

/**
 * initCreate() — no-op at present. All create.js event listeners wire
 * themselves at import time, matching how this code ran unconditionally in
 * the original main.js.
 */
export function initCreate() {
  // Intentionally empty — see comment above.
}
