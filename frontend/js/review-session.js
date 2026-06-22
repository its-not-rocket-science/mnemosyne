/**
 * review-session.js — wires the #open-review-btn and mnemosyne-review-pane.
 *
 * Responsibilities:
 *   · Poll /review/sentence-items/stats on auth and every 5 min to update badge.
 *   · Show/hide #route-review (was #review-panel) on #/review navigation.
 *   · Pass the current language (if one is selected) to startSession().
 *   · Handle the session-end event to collapse the panel.
 *   · Confirm before leaving an active review session via browser back.
 */

import { API_BASE } from './config.js'
import { t, ti } from './i18n.js'
import { navigate, onRoute } from './router.js'

let _pollTimer = null

export function initReviewSession() {
  const openBtn = document.getElementById('open-review-btn')
  const reviewPanel = document.getElementById('route-review')
  const reviewBar = document.getElementById('review-bar')
  const reviewPane = document.getElementById('review-pane')
  const badge    = document.getElementById('review-due-badge')
  const navBadge = document.getElementById('nav-due-badge')
  const weaknessBar = document.getElementById('weakness-graph-bar')
  const weaknessGraph = document.getElementById('weakness-graph')
  const statsBar = document.getElementById('srs-stats-bar')
  const forecastBar   = document.getElementById('forecast-bar')
  const forecastChart = document.getElementById('forecast-chart')

  if (!openBtn || !reviewPanel || !reviewPane) return

  // Show the review bar once auth is confirmed
  reviewBar?.removeAttribute('hidden')

  // Show weakness graph bar and load profile for current language
  if (weaknessBar && weaknessGraph) {
    weaknessBar.removeAttribute('hidden')
    const langSel = document.getElementById('language')
    const lang = langSel?.value || null
    if (lang) weaknessGraph.load?.(lang)

    // Reload when language changes
    langSel?.addEventListener('change', () => {
      const newLang = langSel.value || null
      if (newLang) weaknessGraph.load?.(newLang)
    })
  }

  // ── Daily insight ─────────────────────────────────────────────────────────

  const insightBar = document.getElementById('daily-insight')

  function _buildInsightItems(metrics, profile) {
    const items = []

    // Weakest concept type — lowest accuracy with meaningful volume (≥5 reviews)
    if (profile?.concept_type_accuracy?.length) {
      const candidates = profile.concept_type_accuracy
        .filter(e => (e.correct_count + (e.total_reviews - e.correct_count)) >= 5)
      if (candidates.length) {
        const worst = candidates.reduce((a, b) => a.accuracy < b.accuracy ? a : b)
        if (worst.accuracy < 0.75) {
          const pct = Math.round(worst.accuracy * 100)
          const concept = worst.concept_type.replace(/_/g, ' ')
          items.push({ kind: 'weak', text: ti('insight_weak_concept', { concept, pct }) })
        }
      }
    }

    // Top confusion pair
    if (profile?.confusion_pairs?.length) {
      const top = profile.confusion_pairs[0]
      if (top.confusion_count >= 2) {
        items.push({ kind: 'confusion', text: ti('insight_confusion', { a: top.object_id, b: top.confused_with }) })
      }
    }

    // High-friction items from metrics.weakest (lapse_rate > 0.3)
    if (items.length < 2 && metrics?.weakest?.length) {
      const sticky = metrics.weakest.filter(w => w.lapse_rate > 0.3 && w.total_reviews >= 3)
      if (sticky.length >= 2) {
        items.push({ kind: 'friction', text: ti('insight_high_friction', { n: sticky.length }) })
      }
    }

    return items.slice(0, 2)
  }

  function _renderInsight(items) {
    if (!insightBar) return
    if (!items.length) {
      insightBar.setAttribute('hidden', '')
      return
    }
    const p = document.createElement('p')
    p.className = 'daily-insight'
    items.forEach(item => {
      const span = document.createElement('span')
      span.className = 'daily-insight__item'
      span.textContent = item.text
      if (item.kind === 'friction' || item.kind === 'confusion') span.classList.add('daily-insight__accent')
      p.appendChild(span)
    })
    insightBar.replaceChildren(p)
    insightBar.removeAttribute('hidden')
  }

  // ── SRS stats + insight ────────────────────────────────────────────────────

  // Fetch SRS stats and populate the stats bar tiles
  async function refreshStats() {
    try {
      const token = localStorage.getItem('mnemosyne_token')
      if (!token) return

      const langSel = document.getElementById('language')
      const lang = langSel?.value || null
      const params = new URLSearchParams()
      if (lang) params.set('language', lang)

      const [sentStats, metrics, profile] = await Promise.all([
        fetch(`${API_BASE}/review/sentence-items/stats?${params}`, {
          headers: { Authorization: `Bearer ${token}` },
        }).then(r => r.ok ? r.json() : null).catch(() => null),
        fetch(`${API_BASE}/metrics?${params}`, {
          headers: { Authorization: `Bearer ${token}` },
        }).then(r => r.ok ? r.json() : null).catch(() => null),
        lang
          ? fetch(`${API_BASE}/weakness/profile/${encodeURIComponent(lang)}`, {
              headers: { Authorization: `Bearer ${token}` },
            }).then(r => r.ok ? r.json() : null).catch(() => null)
          : Promise.resolve(null),
      ])

      const statDue      = document.getElementById('stat-due')
      const statStreak   = document.getElementById('stat-streak')
      const statMastered = document.getElementById('stat-mastered')
      const statToday    = document.getElementById('stat-today')

      if (statDue && sentStats != null)      statDue.textContent      = String(sentStats.due_now      ?? '—')
      if (statStreak && metrics != null)     statStreak.textContent   = String(metrics.streak_days    ?? '—')
      if (statMastered && metrics != null)   statMastered.textContent = String(metrics.total_mastered ?? '—')
      if (statToday && metrics != null)      statToday.textContent    = String(metrics.reviews_today  ?? '—')

      statsBar?.removeAttribute('hidden')

      // Daily insight — only meaningful when a language is selected
      if (lang && (metrics || profile)) {
        _renderInsight(_buildInsightItems(metrics, profile))
      }
    } catch {
      // Non-fatal — tiles stay at "—"
    }
  }

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

      const dueLabel = due > 99 ? '99+' : String(due)
      const ariaLabel = `${due} item${due !== 1 ? 's' : ''} due for review`
      for (const el of [badge, navBadge]) {
        if (!el) continue
        if (due > 0) {
          el.textContent = dueLabel
          el.removeAttribute('hidden')
          el.setAttribute('aria-label', ariaLabel)
        } else {
          el.textContent = ''
          el.setAttribute('hidden', '')
        }
      }
    } catch {
      // Non-fatal — badges stay hidden
    }
  }

  // ── #/review route ────────────────────────────────────────────────────────
  // Was a manual show/hide toggle on #review-panel; now driven by the router.
  // A session is "active" between startSession() and the session-end event,
  // so the back-navigation confirm (below) only fires when there's something to
  // lose.
  let _sessionActive = false
  // Set when we're programmatically leaving the route (confirmed back-nav or
  // session end) so the route handler doesn't re-prompt for the same exit.
  let _leavingProgrammatically = false

  async function _enterReviewRoute() {
    openBtn.setAttribute('aria-expanded', 'true')
    const langSel = document.getElementById('language')
    const lang = langSel?.value || null
    _sessionActive = true
    await reviewPane.startSession?.(lang)
  }

  function _exitReviewRoute() {
    openBtn.setAttribute('aria-expanded', 'false')
    reviewPane.endSession?.()
    _sessionActive = false
  }

  onRoute((route) => {
    const isReview = route.path === 'review'
    reviewPanel.hidden = !isReview
    if (isReview) {
      _enterReviewRoute()
    } else if (_sessionActive) {
      _exitReviewRoute()
    }
  })

  openBtn.addEventListener('click', () => {
    const isOpen = !reviewPanel.hidden
    navigate(isOpen ? '#/explore' : '#/review')
  })

  // Confirm before losing an in-progress review session via browser back.
  // hashchange has already happened by the time this fires, so we can't
  // truly "cancel" navigation — instead, if the user declines, we navigate
  // straight back to #/review to restore the session view (the underlying
  // review-pane state, e.g. current card, is preserved since endSession()
  // was not called).
  window.addEventListener('hashchange', () => {
    if (!_sessionActive || _leavingProgrammatically) return
    const stillReview = (window.location.hash || '').startsWith('#/review')
    if (stillReview) return
    const proceed = confirm('Leave your review session? Progress on the current card will be lost.')
    if (!proceed) {
      _leavingProgrammatically = true
      navigate('#/review')
      _leavingProgrammatically = false
    }
  })

  // Navigate off #/review once a session ends, if we're still on that route
  // (the user may have already navigated away, e.g. via back-nav above).
  function _leaveReviewRouteIfActive() {
    if (!(window.location.hash || '').startsWith('#/review')) return
    _leavingProgrammatically = true
    navigate('#/explore')
    _leavingProgrammatically = false
  }

  // Collapse panel when session ends
  reviewPane.addEventListener('review-session-end', () => {
    _sessionActive = false
    reviewPanel.setAttribute('hidden', '')
    openBtn.setAttribute('aria-expanded', 'false')
    openBtn.focus()
    refreshBadge()
    refreshStats()
    _leaveReviewRouteIfActive()
  })

  // Update badge and stats after each rated item
  reviewPane.addEventListener('review-item-rated', () => {
    refreshBadge()
    refreshStats()
  })

  // ── Retention / calibration panel ─────────────────────────────────────────

  const retentionPanel = document.getElementById('retention-panel')
  const retentionBody  = document.getElementById('retention-panel-body')

  function _agoLabel(isoDate) {
    if (!isoDate) return null
    const diffMs   = Date.now() - new Date(isoDate).getTime()
    const diffDays = Math.floor(diffMs / 86_400_000)
    if (diffDays < 1) return 'today'
    if (diffDays === 1) return '1 day ago'
    return `${diffDays} days ago`
  }

  function _renderRetentionBody(params) {
    if (!retentionBody) return
    const pct  = Math.round((params.desired_retention ?? 0.90) * 100)
    const ago  = _agoLabel(params.last_calibrated_at)

    let calibrationText
    if (ago) {
      calibrationText = ti('retention_calibrated', {
        ago,
        reviews: params.reviews_used ?? '?',
      })
      if (params.calibration_rmse != null) {
        calibrationText += ' · ' + ti('retention_rmse', { rmse: params.calibration_rmse.toFixed(3) })
      }
    } else {
      calibrationText = t('retention_not_calibrated') + ' — ' + t('retention_requires')
    }

    retentionBody.innerHTML = `
      <div class="retention-panel__row">
        <span class="retention-panel__value">${ti('retention_targeting', { pct })}</span>
      </div>
      <div class="retention-panel__row">
        <span class="retention-panel__muted">${calibrationText}</span>
      </div>
      <div class="retention-panel__actions">
        <button type="button" class="ghost-button retention-panel__recalibrate-btn"
                id="recalibrate-btn">${t('retention_recalibrate_btn')}</button>
        <span class="retention-panel__status" id="recalibrate-status" aria-live="polite"></span>
      </div>
    `

    document.getElementById('recalibrate-btn')?.addEventListener('click', async () => {
      const statusEl = document.getElementById('recalibrate-status')
      const btn      = document.getElementById('recalibrate-btn')
      if (!btn) return
      btn.disabled = true
      if (statusEl) statusEl.textContent = t('retention_calibrating')
      try {
        const token = localStorage.getItem('mnemosyne_token')
        const resp  = await fetch(`${API_BASE}/users/me/calibrate`, {
          method:  'POST',
          headers: { Authorization: `Bearer ${token}` },
        })
        if (resp.ok) {
          const updated = await resp.json()
          _renderRetentionBody(updated)
        } else if (resp.status === 422) {
          const data = await resp.json().catch(() => ({}))
          const needed = data?.detail?.min_reviews ?? 30
          if (statusEl) statusEl.textContent = ti('retention_requires', {}) || `Need ${needed} reviews`
          btn.disabled = false
        } else {
          if (statusEl) statusEl.textContent = '—'
          btn.disabled = false
        }
      } catch {
        if (statusEl) statusEl.textContent = '—'
        btn.disabled = false
      }
    })
  }

  async function refreshRetentionPanel() {
    if (!retentionPanel || !retentionBody) return
    try {
      const token = localStorage.getItem('mnemosyne_token')
      if (!token) return
      const resp = await fetch(`${API_BASE}/users/me/fsrs-params`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!resp.ok) return
      const params = await resp.json()
      _renderRetentionBody(params)
      retentionPanel.removeAttribute('hidden')
    } catch {
      // Non-fatal — panel stays hidden
    }
  }

  // ── 7-day review forecast ──────────────────────────────────────────────────

  async function refreshForecast() {
    if (!forecastChart) return
    try {
      const token = localStorage.getItem('mnemosyne_token')
      if (!token) return
      const langSel = document.getElementById('language')
      const lang = langSel?.value || null
      const params = new URLSearchParams({ days: '7' })
      if (lang) params.set('language', lang)
      const resp = await fetch(`${API_BASE}/metrics/forecast?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!resp.ok) return
      const data = await resp.json()
      _renderForecast(data.days)
      forecastBar?.removeAttribute('hidden')
    } catch {
      // Non-fatal — chart stays hidden
    }
  }

  function _renderForecast(days) {
    if (!forecastChart || !days?.length) return
    const max = Math.max(...days.map(d => d.total), 1)

    const ul = document.createElement('ul')
    ul.className  = 'forecast-chart'
    ul.setAttribute('role', 'list')

    days.forEach(day => {
      const frac = day.total / max
      const li = document.createElement('li')
      li.className = 'forecast-bar' + (day.is_today ? ' forecast-bar--today' : '')

      const fill = document.createElement('span')
      fill.className = 'forecast-bar__fill'
      fill.style.setProperty('--_h', String(frac.toFixed(3)))

      const count = document.createElement('span')
      count.className   = 'forecast-bar__count'
      count.textContent = day.total > 0 ? String(day.total) : ''
      count.setAttribute('aria-hidden', 'true')

      const label = document.createElement('span')
      label.className   = 'forecast-bar__label'
      label.textContent = day.is_today ? '·' : day.day_label

      li.setAttribute('aria-label', `${day.day_label}: ${day.total} items`)
      li.append(fill, count, label)
      ul.appendChild(li)
    })

    forecastChart.replaceChildren(ul)
  }

  // Language change: refresh badge, stats, forecast, retention
  document.getElementById('language')?.addEventListener('change', () => {
    refreshStats()
    refreshForecast()
    refreshRetentionPanel()
  })

  // Initial fetch + periodic refresh every 5 minutes
  refreshBadge()
  refreshStats()
  refreshForecast()
  refreshRetentionPanel()
  _pollTimer = setInterval(() => { refreshBadge(); refreshStats(); refreshForecast() }, 5 * 60 * 1000)

  // Refresh when the tab regains focus (user returns from another tab/app)
  window.addEventListener('focus', () => { refreshBadge(); refreshStats(); refreshForecast() })
}

export function teardownReviewSession() {
  if (_pollTimer) {
    clearInterval(_pollTimer)
    _pollTimer = null
  }
}
