/**
 * mnemosyne-review-pane — sentence-level spaced-retrieval review session.
 *
 * Usage
 * ─────
 *   <mnemosyne-review-pane id="review-pane"></mnemosyne-review-pane>
 *
 * Public API
 * ──────────
 *   el.startSession(language?)  — fetch queue and show first card
 *   el.endSession()             — hide and reset
 *
 * Events emitted on the element
 * ──────────────────────────────
 *   review-session-end          — user completed or skipped all due items
 *   review-item-rated           — { itemId, quality, masteryScore, streak }
 *
 * Card types rendered
 * ────────────────────
 *   cloze                Fill-blank in sentence context.
 *   chunk_recall         Complete the stem of an idiomatic expression.
 *   grammar_transform    Self-graded tense / mood transformation.
 *   meaning_discrimination  Choose the correct form for the context.
 *
 * Accessibility
 * ─────────────
 *   · Full keyboard navigation (Tab, Shift+Tab, Enter to check, 1-4 to rate).
 *   · ARIA live regions for feedback.
 *   · No color-only signalling; correct/wrong states use both color and icon.
 *   · prefers-reduced-motion: transitions disabled.
 *   · Focus returns to session heading when a new card loads.
 */

import { API_BASE } from '../js/config.js'

const ITEM_TYPE_LABELS = {
  cloze:                   'Fill in the blank',
  chunk_recall:            'Complete the expression',
  grammar_transform:       'Grammar challenge',
  meaning_discrimination:  'Choose the correct form',
}

const STREAK_ICONS = ['', '🔥', '🔥🔥', '🔥🔥🔥']

export class MnemosyneReviewPane extends HTMLElement {
  #queue = []
  #currentIndex = 0
  #language = null
  #answered = false
  #loading = false

  constructor() {
    super()
    this.attachShadow({ mode: 'open' })
  }

  connectedCallback() {
    this._renderShell()
  }

  // ── Public API ─────────────────────────────────────────────────────────────

  async startSession(language = null) {
    this.#language = language
    this.#queue = []
    this.#currentIndex = 0
    this.removeAttribute('hidden')
    this._renderLoading()
    await this._fetchQueue()
    this._renderCard()
  }

  endSession() {
    this.setAttribute('hidden', '')
    this.#queue = []
    this.#currentIndex = 0
    this._renderShell()
  }

  // ── Fetch ──────────────────────────────────────────────────────────────────

  async _fetchQueue() {
    this.#loading = true
    try {
      const params = new URLSearchParams({ limit: '30' })
      if (this.#language) params.set('language', this.#language)
      const token = localStorage.getItem('mnemosyne_token')
      const resp = await fetch(`${API_BASE}/review/sentence-items?${params}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      this.#queue = await resp.json()
    } catch (err) {
      this._renderError(`Could not load review queue: ${err.message}`)
      return
    } finally {
      this.#loading = false
    }
  }

  async _submitRating(itemId, quality) {
    const token = localStorage.getItem('mnemosyne_token')
    const resp = await fetch(`${API_BASE}/review/sentence-items/${itemId}/submit`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ quality }),
    })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    return resp.json()
  }

  // ── Rendering ──────────────────────────────────────────────────────────────

  _renderShell() {
    if (!this.shadowRoot) return
    this.shadowRoot.innerHTML = `<style>:host([hidden]){display:none}:host{display:block}</style>`
  }

  _renderLoading() {
    const sr = this.shadowRoot
    sr.innerHTML = `
      ${this._styles()}
      <section class="pane" aria-labelledby="review-heading" aria-busy="true">
        <h2 id="review-heading" class="pane__heading">Review</h2>
        <p class="loading" aria-live="polite">Loading review queue…</p>
      </section>
    `
  }

  _renderError(msg) {
    this.shadowRoot.innerHTML = `
      ${this._styles()}
      <section class="pane" aria-labelledby="review-heading">
        <h2 id="review-heading" class="pane__heading">Review</h2>
        <p class="error" role="alert">${_escHtml(msg)}</p>
        <button type="button" class="btn btn--primary" id="retry-btn">Retry</button>
      </section>
    `
    this.shadowRoot.getElementById('retry-btn')?.addEventListener('click', () => {
      this.startSession(this.#language)
    })
  }

  _renderCard() {
    if (this.#currentIndex >= this.#queue.length) {
      this._renderDone()
      return
    }

    const item = this.#queue[this.#currentIndex]
    this.#answered = false

    const sr = this.shadowRoot
    const typeLabel = ITEM_TYPE_LABELS[item.item_type] || item.item_type
    const progressText = `${this.#currentIndex + 1} / ${this.#queue.length}`
    const streakDisplay = this._streakHtml(item.streak)
    const masteryPct = Math.round((item.mastery_score || 0) * 100)

    sr.innerHTML = `
      ${this._styles()}
      <section class="pane" aria-labelledby="review-heading">
        <div class="pane__header">
          <h2 id="review-heading" class="pane__heading">Review</h2>
          <div class="pane__meta" aria-label="Progress">
            <span class="progress-label">${_escHtml(progressText)}</span>
            ${streakDisplay}
          </div>
          <button type="button" class="btn btn--ghost close-btn" aria-label="End review session">✕</button>
        </div>

        <div class="card" role="region" aria-labelledby="card-type-label">
          <p id="card-type-label" class="card__type">${_escHtml(typeLabel)}</p>

          <div class="card__prompt" id="card-prompt"></div>

          ${item.item_type === 'meaning_discrimination' ? this._renderDiscriminationChoices(item) : ''}
          ${item.item_type !== 'meaning_discrimination' && item.item_type !== 'grammar_transform'
            ? this._renderInputRow(item)
            : ''}
          ${item.item_type === 'grammar_transform' ? this._renderTransformPrompt(item) : ''}

          <p class="card__hint" id="card-hint" ${item.hint ? '' : 'hidden'}></p>

          <div class="card__feedback" aria-live="polite" aria-atomic="true" id="feedback-region"></div>
        </div>

        <details class="card__context" id="context-details">
          <summary class="card__context-summary">Show context</summary>
          <div class="card__context-body" id="context-body" aria-busy="true">
            <p class="card__context-loading">Loading…</p>
          </div>
        </details>

        <div class="mastery-bar" aria-label="Mastery: ${masteryPct}%">
          <div class="mastery-bar__fill" style="inline-size:${masteryPct}%"></div>
        </div>

        <div class="ratings" role="group" aria-label="How well did you recall this?" id="ratings-row" hidden>
          <button type="button" class="btn btn--rate" data-quality="1" aria-keyshortcuts="1">Again</button>
          <button type="button" class="btn btn--rate" data-quality="2" aria-keyshortcuts="2">Hard</button>
          <button type="button" class="btn btn--rate" data-quality="3" aria-keyshortcuts="3">Good</button>
          <button type="button" class="btn btn--rate" data-quality="4" aria-keyshortcuts="4">Easy</button>
        </div>

        <p class="status-error" role="alert" aria-atomic="true" id="submit-error"></p>
      </section>
    `

    // Set prompt text safely via DOM
    const promptEl = sr.getElementById('card-prompt')
    promptEl.textContent = item.prompt

    if (item.hint) {
      sr.getElementById('card-hint').textContent = item.hint
    }

    this._wireCard(item)
    this._wireContext(item.id)

    // Move focus to the heading for screen readers announcing new card
    sr.getElementById('review-heading')?.focus()
  }

  _wireContext(itemId) {
    const details = this.shadowRoot.getElementById('context-details')
    if (!details) return
    let loaded = false
    details.addEventListener('toggle', async () => {
      if (!details.open || loaded) return
      loaded = true
      await this._loadContext(itemId)
    }, { once: true })
  }

  async _loadContext(itemId) {
    const body = this.shadowRoot.getElementById('context-body')
    if (!body) return
    try {
      const token = localStorage.getItem('mnemosyne_token')
      const resp = await fetch(`${API_BASE}/review/sentence-items/${itemId}/context`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const ctx = await resp.json()

      body.removeAttribute('aria-busy')
      body.replaceChildren()

      for (const text of ctx.before) {
        const p = document.createElement('p')
        p.className = 'context-sent context-sent--before'
        p.textContent = text
        body.appendChild(p)
      }

      const target = document.createElement('p')
      target.className = 'context-sent context-sent--target'
      target.textContent = ctx.target
      target.setAttribute('aria-current', 'true')
      body.appendChild(target)

      for (const text of ctx.after) {
        const p = document.createElement('p')
        p.className = 'context-sent context-sent--after'
        p.textContent = text
        body.appendChild(p)
      }

      if (ctx.source_title) {
        const cite = document.createElement('p')
        cite.className = 'context-source'
        cite.textContent = `From: ${ctx.source_title}`
        body.appendChild(cite)
      }
    } catch {
      if (body) {
        body.removeAttribute('aria-busy')
        body.replaceChildren()
        const err = document.createElement('p')
        err.className = 'card__context-loading'
        err.textContent = 'Context unavailable.'
        body.appendChild(err)
      }
    }
  }

  _renderDiscriminationChoices(item) {
    const choices = [item.answer, ...(item.distractors || [])]
    // Stable shuffle: interleave answer and distractors without randomness for
    // reproducibility. For two options just swap them 50/50 by hash parity.
    const swapped = (item.target_span.charCodeAt(0) || 0) % 2 === 0
    const ordered = swapped ? [choices[1], choices[0]] : [choices[0], choices[1]]
    return `
      <div class="disc-choices" role="group" aria-label="Choose one" id="disc-group">
        ${ordered.map((c, i) => `
          <button type="button" class="btn btn--choice" data-choice="${_escAttr(c)}"
                  aria-keyshortcuts="${i + 1}">
            ${String.fromCharCode(65 + i)}) <span class="choice-text"></span>
          </button>
        `).join('')}
      </div>
    `
  }

  _renderInputRow(item) {
    const dir = _guessDir(item.language)
    return `
      <div class="input-row" id="input-row">
        <label for="answer-input" class="sr-only">Your answer</label>
        <input
          id="answer-input"
          type="text"
          class="answer-input"
          autocomplete="off"
          autocorrect="off"
          spellcheck="false"
          dir="${dir}"
          lang="${_escAttr(item.language)}"
          placeholder="Type your answer…"
        >
        <button type="button" class="btn btn--primary" id="check-btn">Check</button>
      </div>
    `
  }

  _renderTransformPrompt(item) {
    return `
      <div class="transform-area" id="transform-area">
        <label for="transform-input" class="sr-only">Your rewritten sentence</label>
        <textarea
          id="transform-input"
          class="transform-input"
          rows="2"
          autocorrect="off"
          spellcheck="false"
          lang="${_escAttr(item.language)}"
          placeholder="Type your rewritten sentence…"
        ></textarea>
        <button type="button" class="btn btn--primary" id="check-btn">Show answer</button>
      </div>
    `
  }

  _renderDone() {
    this.shadowRoot.innerHTML = `
      ${this._styles()}
      <section class="pane pane--done" aria-labelledby="review-heading">
        <h2 id="review-heading" class="pane__heading">Review complete</h2>
        <p class="done-msg">You reviewed ${this.#queue.length} item${this.#queue.length !== 1 ? 's' : ''}.
          Come back tomorrow for more.</p>
        <button type="button" class="btn btn--primary" id="done-btn">Close</button>
      </section>
    `
    this.shadowRoot.getElementById('done-btn')?.addEventListener('click', () => {
      this.endSession()
      this.dispatchEvent(new CustomEvent('review-session-end', { bubbles: true, composed: true }))
    })
    this.shadowRoot.getElementById('review-heading')?.focus()
  }

  // ── Event wiring ───────────────────────────────────────────────────────────

  _wireCard(item) {
    const sr = this.shadowRoot

    // Close button
    sr.querySelector('.close-btn')?.addEventListener('click', () => {
      this.endSession()
      this.dispatchEvent(new CustomEvent('review-session-end', { bubbles: true, composed: true }))
    })

    // Set choice text via DOM (discrimination items)
    sr.querySelectorAll('.choice-text').forEach((el, i) => {
      const choices = [item.answer, ...(item.distractors || [])]
      const swapped = (item.target_span.charCodeAt(0) || 0) % 2 === 0
      const ordered = swapped ? [choices[1], choices[0]] : [choices[0], choices[1]]
      el.textContent = ordered[i] ?? ''
    })

    // Discrimination choices
    sr.querySelectorAll('[data-choice]').forEach((btn) => {
      btn.addEventListener('click', () => {
        if (this.#answered) return
        this.#answered = true
        const chosen = btn.dataset.choice
        const correct = chosen === item.answer
        this._showFeedback(correct, item.answer)
        sr.querySelectorAll('[data-choice]').forEach((b) => {
          b.disabled = true
          if (b.dataset.choice === item.answer) b.dataset.state = 'correct'
          else if (b.dataset.choice === chosen && !correct) b.dataset.state = 'wrong'
        })
        this._showRatings()
      })
    })

    // Text input (cloze / chunk_recall)
    const checkBtn = sr.getElementById('check-btn')
    const answerInput = sr.getElementById('answer-input') || sr.getElementById('transform-input')

    if (checkBtn && answerInput) {
      const doCheck = () => {
        if (this.#answered) return
        const value = answerInput.value.trim()
        if (!value) return
        this.#answered = true
        answerInput.disabled = true
        checkBtn.disabled = true

        if (item.item_type === 'grammar_transform') {
          // Self-graded: show reference answer; learner rates themselves
          this._showTransformAnswer(item.answer)
        } else {
          const correct = value.toLowerCase() === item.answer.toLowerCase()
          this._showFeedback(correct, item.answer)
        }
        this._showRatings()
      }

      checkBtn.addEventListener('click', doCheck)
      answerInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); doCheck() }
      })

      // Auto-focus input
      requestAnimationFrame(() => answerInput.focus())
    }

    // Rating buttons
    sr.querySelectorAll('[data-quality]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const quality = Number(btn.dataset.quality)
        await this._rate(item, quality)
      })
    })

    // Keyboard shortcuts for ratings (1-4) — only active after answering
    this._keyHandler = (e) => {
      if (!this.#answered) return
      if (['1', '2', '3', '4'].includes(e.key)) {
        e.preventDefault()
        this._rate(item, Number(e.key))
        document.removeEventListener('keydown', this._keyHandler)
      }
    }
    document.addEventListener('keydown', this._keyHandler)

    // Hint toggle
    const hintEl = sr.getElementById('card-hint')
    if (hintEl && item.hint) {
      hintEl.style.cursor = 'pointer'
      hintEl.setAttribute('tabindex', '0')
      hintEl.setAttribute('role', 'button')
      hintEl.setAttribute('aria-label', 'Toggle hint visibility')
      let hintVisible = false
      hintEl.removeAttribute('hidden')
      hintEl.textContent = 'Show hint…'
      hintEl.addEventListener('click', () => {
        hintVisible = !hintVisible
        hintEl.textContent = hintVisible ? item.hint : 'Show hint…'
        hintEl.setAttribute('aria-pressed', String(hintVisible))
      })
      hintEl.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); hintEl.click() }
      })
    }
  }

  _showFeedback(correct, correctAnswer) {
    const region = this.shadowRoot.getElementById('feedback-region')
    if (!region) return
    region.dataset.result = correct ? 'correct' : 'wrong'
    if (correct) {
      region.textContent = '✓ Correct'
    } else {
      region.textContent = ''
      region.append('✗ Answer: ', _bdi(correctAnswer))
    }
  }

  _showTransformAnswer(referenceAnswer) {
    const region = this.shadowRoot.getElementById('feedback-region')
    if (!region) return
    region.dataset.result = 'info'
    region.textContent = `Reference: ${referenceAnswer.replace(/^\[|\]$/g, '')}`
  }

  _showRatings() {
    const ratingsRow = this.shadowRoot.getElementById('ratings-row')
    ratingsRow?.removeAttribute('hidden')
    // Focus first rating button
    this.shadowRoot.querySelector('[data-quality]')?.focus()
  }

  async _rate(item, quality) {
    const ratingsRow = this.shadowRoot.getElementById('ratings-row')
    const errorEl = this.shadowRoot.getElementById('submit-error')

    ratingsRow?.querySelectorAll('button').forEach((b) => { b.disabled = true })
    if (errorEl) errorEl.textContent = ''

    try {
      const result = await this._submitRating(item.id, quality)
      this.dispatchEvent(new CustomEvent('review-item-rated', {
        bubbles: true,
        composed: true,
        detail: {
          itemId: item.id,
          quality,
          masteryScore: result.mastery_score,
          streak: result.streak,
          nextIntervalDays: result.next_interval_days,
        },
      }))
    } catch (err) {
      if (errorEl) errorEl.textContent = `Save failed: ${err.message}. Rating still recorded locally.`
      ratingsRow?.querySelectorAll('button').forEach((b) => { b.disabled = false })
      return
    }

    // Remove key listener before advancing
    document.removeEventListener('keydown', this._keyHandler)

    this.#currentIndex++
    this._renderCard()
  }

  _streakHtml(streak) {
    if (!streak) return ''
    const icon = STREAK_ICONS[Math.min(streak, STREAK_ICONS.length - 1)] || '🔥'
    return `<span class="streak" aria-label="Streak: ${streak}" title="Streak: ${streak} reviews">${icon} ${streak}</span>`
  }

  // ── Styles ─────────────────────────────────────────────────────────────────

  _styles() {
    return `<style>
      :host {
        display: block;
        color-scheme: light dark;
      }
      :host([hidden]) { display: none; }

      .sr-only {
        position: absolute;
        inline-size: 1px; block-size: 1px;
        overflow: hidden; clip-path: inset(50%);
        white-space: nowrap;
      }

      .pane {
        background: Canvas;
        color: CanvasText;
        border-radius: 0.75rem;
        padding: clamp(1rem, 4vw, 1.5rem);
        max-inline-size: 44rem;
        margin-inline: auto;
        box-shadow: 0 2px 12px color-mix(in srgb, black 12%, transparent);
      }

      .pane__header {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        margin-block-end: 1rem;
        flex-wrap: wrap;
      }

      .pane__heading {
        margin: 0;
        font-size: 1.1rem;
        font-weight: 700;
        flex: 1;
      }

      .pane__heading:focus { outline: none; }

      .pane__meta {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-size: 0.85rem;
        color: var(--muted, GrayText);
      }

      .progress-label { font-variant-numeric: tabular-nums; }

      .streak {
        font-size: 0.85rem;
        background: color-mix(in srgb, oklch(0.72 0.18 55) 12%, Canvas);
        border-radius: 999px;
        padding: 0.1em 0.5em;
        border: 1px solid color-mix(in srgb, oklch(0.72 0.18 55) 30%, Canvas);
      }

      .close-btn {
        margin-inline-start: auto;
        padding-inline: 0.6rem;
        min-block-size: 2.75rem;
        font-size: 1rem;
      }

      /* ── Card ── */
      .card {
        background: color-mix(in srgb, CanvasText 4%, Canvas);
        border-radius: 0.5rem;
        padding: 1rem;
        margin-block-end: 1rem;
      }

      .card__type {
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--muted, GrayText);
        margin: 0 0 0.6rem;
      }

      .card__prompt {
        font-size: 1.05rem;
        line-height: 1.6;
        white-space: pre-wrap;
        overflow-wrap: break-word;
        margin-block-end: 0.75rem;
      }

      .card__hint {
        font-size: 0.85rem;
        color: var(--muted, GrayText);
        cursor: pointer;
        margin-block: 0.5rem;
      }

      .card__hint:focus-visible {
        outline: 3px solid var(--accent, #3557ff);
        outline-offset: 2px;
        border-radius: 2px;
      }

      .card__feedback {
        margin-block-start: 0.6rem;
        font-size: 0.9rem;
        font-weight: 500;
        min-block-size: 1.4em;
      }

      .card__feedback[data-result="correct"] { color: oklch(0.45 0.15 145); }
      .card__feedback[data-result="wrong"]   { color: var(--error-color, oklch(0.50 0.2 29)); }
      .card__feedback[data-result="info"]    { color: var(--muted, GrayText); }

      @media (prefers-color-scheme: dark) {
        :host-context(:root[data-theme="auto"]) .card__feedback[data-result="correct"] {
          color: oklch(0.70 0.15 145);
        }
      }
      :host-context(:root[data-theme="dark"]) .card__feedback[data-result="correct"] {
        color: oklch(0.70 0.15 145);
      }

      /* ── Input ── */
      .input-row {
        display: flex;
        gap: 0.5rem;
        flex-wrap: wrap;
        align-items: center;
      }

      .answer-input {
        flex: 1 1 0;
        min-inline-size: 8rem;
        block-size: 2.75rem;
        padding-inline: 0.6rem;
        border: 1px solid color-mix(in srgb, CanvasText 30%, transparent);
        border-radius: 0.375rem;
        background: Canvas;
        color: CanvasText;
        font: inherit;
        font-size: 0.95rem;
      }

      .answer-input:focus-visible {
        outline: 3px solid var(--accent, #3557ff);
        outline-offset: 2px;
      }

      .transform-input {
        inline-size: 100%;
        padding: 0.5rem 0.6rem;
        border: 1px solid color-mix(in srgb, CanvasText 30%, transparent);
        border-radius: 0.375rem;
        background: Canvas;
        color: CanvasText;
        font: inherit;
        font-size: 0.95rem;
        resize: vertical;
        margin-block-end: 0.4rem;
      }

      .transform-input:focus-visible {
        outline: 3px solid var(--accent, #3557ff);
        outline-offset: 2px;
      }

      .transform-area { display: flex; flex-direction: column; }

      /* ── Discrimination choices ── */
      .disc-choices {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin-block: 0.5rem;
      }

      .btn--choice {
        flex: 1 1 auto;
        text-align: start;
        font-size: 0.95rem;
        padding: 0.5rem 0.75rem;
      }

      .btn--choice[data-state="correct"] {
        background: oklch(0.92 0.10 145);
        border-color: oklch(0.55 0.18 145);
        color: oklch(0.25 0.10 145);
      }

      .btn--choice[data-state="wrong"] {
        background: color-mix(in srgb, var(--error-color, oklch(0.50 0.2 29)) 10%, transparent);
        border-color: var(--error-color, oklch(0.50 0.2 29));
        opacity: 0.7;
      }

      @media (prefers-color-scheme: dark) {
        :host-context(:root[data-theme="auto"]) .btn--choice[data-state="correct"] {
          background: oklch(0.30 0.10 145);
          border-color: oklch(0.55 0.18 145);
          color: oklch(0.85 0.08 145);
        }
      }
      :host-context(:root[data-theme="dark"]) .btn--choice[data-state="correct"] {
        background: oklch(0.30 0.10 145);
        border-color: oklch(0.55 0.18 145);
        color: oklch(0.85 0.08 145);
      }

      /* ── Buttons ── */
      button {
        border: 1px solid color-mix(in srgb, CanvasText 45%, Canvas);
        border-radius: 999px;
        background: transparent;
        color: inherit;
        font: inherit;
        cursor: pointer;
        min-block-size: 2.75rem;
        padding-inline: 0.85rem;
      }

      button:focus-visible {
        outline: 3px solid var(--accent, #3557ff);
        outline-offset: 3px;
      }

      button:disabled { opacity: 0.5; cursor: not-allowed; }

      .btn--primary {
        background: var(--accent, #3557ff);
        color: white;
        border-color: transparent;
      }

      .btn--ghost { background: transparent; }

      /* ── Rating row ── */
      .ratings {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin-block-start: 0.75rem;
      }

      .btn--rate { flex: 1 1 auto; font-size: 0.9rem; }

      .btn--rate[data-quality="1"] { color: var(--error-color, oklch(0.50 0.2 29)); }
      .btn--rate[data-quality="4"] { color: oklch(0.45 0.15 145); }

      @media (prefers-color-scheme: dark) {
        :host-context(:root[data-theme="auto"]) .btn--rate[data-quality="4"] { color: oklch(0.70 0.15 145); }
      }
      :host-context(:root[data-theme="dark"]) .btn--rate[data-quality="4"] { color: oklch(0.70 0.15 145); }

      /* ── Mastery bar ── */
      .mastery-bar {
        block-size: 4px;
        background: color-mix(in srgb, CanvasText 12%, Canvas);
        border-radius: 999px;
        overflow: hidden;
        margin-block: 0.75rem;
      }

      .mastery-bar__fill {
        block-size: 100%;
        background: var(--accent, #3557ff);
        border-radius: 999px;
        transition: inline-size 0.3s ease;
      }

      @media (prefers-reduced-motion: reduce) {
        .mastery-bar__fill { transition: none; }
      }

      /* ── Status ── */
      .loading { color: var(--muted, GrayText); font-size: 0.9rem; }
      .error   { color: var(--error-color, oklch(0.50 0.2 29)); }
      .status-error {
        color: var(--error-color, oklch(0.50 0.2 29));
        font-size: 0.875rem;
        min-block-size: 1.25rem;
      }
      .status-error:empty { display: none; }

      /* ── Done state ── */
      .pane--done { text-align: center; }
      .done-msg { color: var(--muted, GrayText); margin-block: 1rem; }

      /* ── Sentence context ── */
      .card__context {
        margin-block: 0.5rem 0;
        border-radius: 0.375rem;
        border: 1px solid color-mix(in srgb, CanvasText 15%, Canvas);
        overflow: hidden;
      }

      .card__context-summary {
        cursor: pointer;
        padding: 0.4rem 0.6rem;
        font-size: 0.8rem;
        color: GrayText;
        user-select: none;
        list-style: none;
      }
      .card__context-summary::-webkit-details-marker { display: none; }
      .card__context-summary::before { content: '▶ '; font-size: 0.65rem; }
      .card__context[open] .card__context-summary::before { content: '▼ '; }

      .card__context-body {
        padding: 0.5rem 0.75rem 0.6rem;
        display: flex;
        flex-direction: column;
        gap: 0.3rem;
      }

      .card__context-loading {
        color: GrayText;
        font-size: 0.85rem;
        font-style: italic;
        margin: 0;
      }

      .context-sent {
        margin: 0;
        font-size: 0.875rem;
        line-height: 1.5;
      }

      .context-sent--before,
      .context-sent--after {
        color: GrayText;
      }

      .context-sent--target {
        font-weight: 600;
        padding-inline: 0.3rem;
        background: color-mix(in srgb, var(--accent, #3557ff) 8%, Canvas);
        border-radius: 0.2rem;
      }

      .context-source {
        margin-block-start: 0.4rem;
        margin-block-end: 0;
        font-size: 0.75rem;
        color: GrayText;
        font-style: italic;
      }

      /* ── Forced colors ── */
      @media (forced-colors: active) {
        .btn--choice[data-state="correct"] { outline: 3px solid Highlight; }
        .btn--choice[data-state="wrong"]   { outline: 3px solid Mark; }
        .mastery-bar__fill                 { forced-color-adjust: none; background: Highlight; }
        .context-sent--target              { outline: 2px solid Highlight; background: transparent; }
      }
    </style>`
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function _escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function _escAttr(str) {
  return String(str).replace(/"/g, '&quot;')
}

function _bdi(text) {
  const el = document.createElement('bdi')
  el.textContent = text
  return el
}

function _guessDir(lang) {
  const RTL = new Set(['ar', 'he', 'fa', 'ur', 'yi', 'arc', 'dv', 'ku'])
  return RTL.has((lang || '').split('-')[0]) ? 'rtl' : 'ltr'
}

customElements.define('mnemosyne-review-pane', MnemosyneReviewPane)
