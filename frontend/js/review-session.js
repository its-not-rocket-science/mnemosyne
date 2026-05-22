/**
 * review-session.js — wires the #open-review-btn and mnemosyne-review-pane.
 *
 * Responsibilities:
 *   · Poll /review/sentence-items/stats on auth and every 5 min to update badge.
 *   · Show/hide #review-panel when the trigger button is clicked.
 *   · Pass the current language (if one is selected) to startSession().
 *   · Handle review-session-end to collapse the panel.
 */

import { API_BASE } from './config.js'

let _pollTimer = null

export function initReviewSession() {
  const openBtn = document.getElementById('open-review-btn')
  const reviewPanel = document.getElementById('review-panel')
  const reviewBar = document.getElementById('review-bar')
  const reviewPane = document.getElementById('review-pane')
  const badge = document.getElementById('review-due-badge')

  if (!openBtn || !reviewPanel || !reviewPane) return

  // Show the review bar once auth is confirmed
  reviewBar?.removeAttribute('hidden')

  // Fetch stats and update badge
  async function refreshBadge() {
    try {
      const token = localStorage.getItem('mnemosyne_token')
      if (!token) return

      // Detect current language from the language selector if present.
      const langSel = document.getElementById('language')
      const lang = langSel?.value || null
      const params = new URLSearchParams()
      if (lang) params.set('language', lang)

      const resp = await fetch(`${API_BASE}/review/sentence-items/stats?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!resp.ok) return
      const stats = await resp.json()
      const due = stats.due_now || 0

      if (badge) {
        if (due > 0) {
          badge.textContent = String(due > 99 ? '99+' : due)
          badge.removeAttribute('hidden')
          badge.setAttribute('aria-label', `${due} item${due !== 1 ? 's' : ''} due for review`)
        } else {
          badge.textContent = ''
          badge.setAttribute('hidden', '')
        }
      }
    } catch {
      // Non-fatal — badge just stays hidden
    }
  }

  // Open / close toggle
  openBtn.addEventListener('click', async () => {
    const isOpen = reviewPanel.hasAttribute('hidden') === false &&
                   !reviewPanel.hidden

    if (isOpen) {
      reviewPanel.setAttribute('hidden', '')
      openBtn.setAttribute('aria-expanded', 'false')
      reviewPane.endSession?.()
    } else {
      reviewPanel.removeAttribute('hidden')
      openBtn.setAttribute('aria-expanded', 'true')

      // Pass current language if selected
      const langSel = document.getElementById('language')
      const lang = langSel?.value || null
      await reviewPane.startSession?.(lang)
    }
  })

  // Collapse panel when session ends
  reviewPane.addEventListener('review-session-end', () => {
    reviewPanel.setAttribute('hidden', '')
    openBtn.setAttribute('aria-expanded', 'false')
    openBtn.focus()
    refreshBadge()
  })

  // Update badge after each rated item
  reviewPane.addEventListener('review-item-rated', refreshBadge)

  // Initial badge fetch + periodic refresh every 5 minutes
  refreshBadge()
  _pollTimer = setInterval(refreshBadge, 5 * 60 * 1000)
}

export function teardownReviewSession() {
  if (_pollTimer) {
    clearInterval(_pollTimer)
    _pollTimer = null
  }
}
