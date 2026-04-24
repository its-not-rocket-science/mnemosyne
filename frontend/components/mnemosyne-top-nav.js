/**
 * mnemosyne-top-nav.js — Persistent navigation + playback control bar.
 *
 * Regions (left → right):
 *   Logo | Play btn | Transport (pause/stop/scrubber) | Voice | Speed |
 *   Follow toggle | Depth | Settings | <slot> (auth elements)
 *
 * Mobile (<54rem): Transport, Voice, Depth and Settings collapse into an
 *   expandable row; Speed and Follow stay visible in the header bar.
 *
 * Dispatches (bubbles + composed):
 *   play-text-request  — user hit Play with engine idle
 *   follow-change      — detail: { enabled: boolean }
 *   depth-change       — detail: { depth: string }
 *   settings-open      — user hit ⚙
 */

import { playbackEngine } from '../js/playback.js'

// ── SVG assets ────────────────────────────────────────────────────────────────

const TREE = /* html */`
<svg viewBox="0 0 20 24" aria-hidden="true" focusable="false" fill="currentColor">
  <ellipse cx="10" cy="12" rx="8"   ry="6"/>
  <ellipse cx="10" cy="7.5" rx="6"  ry="5"/>
  <ellipse cx="10" cy="3.5" rx="3.5" ry="3"/>
  <rect x="8.5" y="16.5" width="3" height="7" rx="1.5"/>
</svg>`

const chevron = up => /* html */`
<svg viewBox="0 0 10 6" aria-hidden="true" focusable="false"
     fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
  <path d="${up ? 'M1 5l4-4 4 4' : 'M1 1l4 4 4-4'}"/>
</svg>`

// URL-encoded SVG chevron for <select> background (neutral gray, works in both themes)
const SELECT_ARROW = `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 10 6' fill='none' stroke='%23888' stroke-width='1.6' stroke-linecap='round'%3E%3Cpath d='M1 1l4 4 4-4'/%3E%3C/svg%3E")`

// ── Component ─────────────────────────────────────────────────────────────────

class MnemosyneTopNav extends HTMLElement {
  #shadow
  #expanded      = false
  #followAlong   = false
  #depth         = 'scholar'
  #speed         = 1.0

  // Wall-clock time tracking (Web Speech API has no position; we estimate)
  #wallStart     = null   // Date.now() when current play session began
  #pauseOffset   = 0      // ms accumulated before last pause
  #estDuration   = 0      // estimated total seconds for current queue
  #timerId       = null

  constructor() {
    super()
    this.#shadow = this.attachShadow({ mode: 'open' })
  }

  connectedCallback() {
    this.#shadow.innerHTML = this.#html()
    this.#wire()
    this.#populateVoices()
    if (window.speechSynthesis) {
      window.speechSynthesis.addEventListener(
        'voiceschanged', () => this.#populateVoices(), { once: true }
      )
    }
    playbackEngine.addEventListener('state-change', this.#onStateChange)
  }

  disconnectedCallback() {
    playbackEngine.removeEventListener('state-change', this.#onStateChange)
    this.#stopTimer()
  }

  // ── Public getters ──────────────────────────────────────────────────────────

  get followAlong() { return this.#followAlong }
  get depth()       { return this.#depth }
  get speed()       { return this.#speed }

  // ── Template ────────────────────────────────────────────────────────────────

  #html() {
    return /* html */`
<style>${this.#css()}</style>

<nav class="nav" part="nav">

  <div class="nav__start">
    <a class="nav__logo" href="/" aria-label="Mnemosyne home">
      ${TREE}
      <span class="nav__wordmark">Mnemosyne</span>
    </a>
  </div>

  <div class="nav__mid">

    <button class="nav__play-btn" id="play-btn" type="button">
      <span id="play-icon" aria-hidden="true">&#x25B6;</span>
      <span id="play-label">Play text</span>
    </button>

    <div class="nav__transport" id="transport">
      <button class="nav__ctrl" id="pause-btn" type="button" aria-label="Pause" disabled>&#x23F8;</button>
      <button class="nav__ctrl" id="stop-btn"  type="button" aria-label="Stop"  disabled>&#x23F9;</button>
      <div class="nav__scrubber">
        <span class="nav__time" id="time-label" aria-live="off">00:00 / 00:00</span>
        <input class="nav__progress" id="progress" type="range"
               min="0" max="100" value="0" aria-label="Playback position">
      </div>
    </div>

    <select class="nav__pill" id="voice-select" aria-label="Voice"></select>

    <select class="nav__pill" id="speed-select" aria-label="Playback speed">
      <option value="0.5">0.5×</option>
      <option value="0.75">0.75×</option>
      <option value="1.0" selected>1.0×</option>
      <option value="1.25">1.25×</option>
      <option value="1.5">1.5×</option>
      <option value="2.0">2.0×</option>
    </select>

    <label class="nav__follow" for="follow-cb">
      <span class="nav__follow-txt">Follow along</span>
      <input class="nav__sr-only" id="follow-cb" type="checkbox"
             role="switch" aria-checked="false">
      <span class="nav__switch" aria-hidden="true"></span>
    </label>

    <select class="nav__pill" id="depth-select" aria-label="Lesson depth">
      <option value="quick">Quick</option>
      <option value="learner">Learner</option>
      <option value="scholar" selected>Scholar</option>
    </select>

    <button class="nav__ctrl nav__settings" id="settings-btn"
            type="button" aria-label="Settings">&#x2699;&#xFE0E;</button>

  </div><!-- /.nav__mid -->

  <div class="nav__end">
    <slot></slot>
    <button class="nav__expand" id="expand-btn" type="button"
            aria-label="Show playback controls"
            aria-expanded="false" aria-controls="xrow">
      ${chevron(false)}
    </button>
  </div>

</nav><!-- /.nav -->

<!-- Expanded row: transport + voice + depth + settings (mobile only) -->
<div class="nav__xrow" id="xrow" hidden>
  <button class="nav__ctrl" id="xpause" type="button" aria-label="Pause" disabled>&#x23F8;</button>
  <button class="nav__ctrl" id="xstop"  type="button" aria-label="Stop"  disabled>&#x23F9;</button>
  <div class="nav__scrubber">
    <span class="nav__time" id="xtime" aria-live="off">00:00 / 00:00</span>
    <input class="nav__progress" id="xprogress" type="range"
           min="0" max="100" value="0" aria-label="Playback position">
  </div>
  <select class="nav__pill" id="xvoice" aria-label="Voice"></select>
  <select class="nav__pill" id="xdepth" aria-label="Lesson depth">
    <option value="quick">Quick</option>
    <option value="learner">Learner</option>
    <option value="scholar" selected>Scholar</option>
  </select>
  <button class="nav__ctrl nav__settings" id="xsettings"
          type="button" aria-label="Settings">&#x2699;&#xFE0E;</button>
</div>`
  }

  // ── Wire events ─────────────────────────────────────────────────────────────

  #wire() {
    const $ = id => this.#shadow.getElementById(id)

    // Play / stop toggle
    $('play-btn').addEventListener('click', () => {
      if (playbackEngine.state !== 'idle') {
        playbackEngine.stop()
      } else {
        this.dispatchEvent(new CustomEvent('play-text-request', { bubbles: true, composed: true }))
      }
    })

    // Desktop transport
    $('pause-btn').addEventListener('click', () => playbackEngine.togglePause())
    $('stop-btn').addEventListener('click',  () => playbackEngine.stop())

    // Mobile transport (xrow)
    $('xpause').addEventListener('click', () => playbackEngine.togglePause())
    $('xstop').addEventListener('click',  () => playbackEngine.stop())

    // Voice
    for (const id of ['voice-select', 'xvoice']) {
      $(id).addEventListener('change', e => {
        this.#syncSelect('voice-select', 'xvoice', e.target.id, e.target.value)
        this.#applyVoice(e.target.value)
      })
    }

    // Speed (desktop only — mobile uses same element via CSS show/hide)
    $('speed-select').addEventListener('change', e => {
      this.#speed = Number(e.target.value)
      playbackEngine.rate = this.#speed
    })

    // Follow along
    $('follow-cb').addEventListener('change', e => {
      this.#followAlong = e.target.checked
      e.target.setAttribute('aria-checked', String(this.#followAlong))
      this.dispatchEvent(new CustomEvent('follow-change', {
        bubbles: true, composed: true,
        detail: { enabled: this.#followAlong },
      }))
    })

    // Depth
    for (const id of ['depth-select', 'xdepth']) {
      $(id).addEventListener('change', e => {
        this.#syncSelect('depth-select', 'xdepth', e.target.id, e.target.value)
        this.#depth = e.target.value
        this.dispatchEvent(new CustomEvent('depth-change', {
          bubbles: true, composed: true,
          detail: { depth: this.#depth },
        }))
      })
    }

    // Settings
    const openSettings = () =>
      this.dispatchEvent(new CustomEvent('settings-open', { bubbles: true, composed: true }))
    $('settings-btn').addEventListener('click', openSettings)
    $('xsettings').addEventListener('click', openSettings)

    // Expand / collapse
    $('expand-btn').addEventListener('click', () => this.#toggleExpand())
  }

  // Keep paired selects in sync when one changes
  #syncSelect(idA, idB, changedId, value) {
    const other = this.#shadow.getElementById(changedId === idA ? idB : idA)
    if (other) other.value = value
  }

  // ── Voices ──────────────────────────────────────────────────────────────────

  #populateVoices() {
    if (!window.speechSynthesis) return
    const voices = window.speechSynthesis.getVoices()

    for (const id of ['voice-select', 'xvoice']) {
      const sel = this.#shadow.getElementById(id)
      if (!sel) continue
      const prev = sel.value
      sel.replaceChildren()

      const auto = document.createElement('option')
      auto.value = ''
      auto.textContent = '— auto —'
      sel.appendChild(auto)

      for (const v of voices) {
        const opt = document.createElement('option')
        opt.value = v.name
        // Show name + short lang tag; trim Microsoft/Google prefix noise
        const shortName = v.name
          .replace(/^Microsoft\s+/i, '')
          .replace(/^Google\s+/i, '')
        opt.textContent = `${shortName} (${v.lang})`
        sel.appendChild(opt)
      }

      if (prev) sel.value = prev
    }
  }

  #applyVoice(name) {
    const voice = name
      ? (window.speechSynthesis?.getVoices().find(v => v.name === name) ?? null)
      : null
    playbackEngine.setPreferredVoice(voice)
  }

  // ── Playback state ───────────────────────────────────────────────────────────

  // Arrow function — preserves `this` when bound to EventTarget.
  #onStateChange = ({ detail: { state, current, total } }) => {
    const $ = id => this.#shadow.getElementById(id)
    const active  = state !== 'idle'
    const playing = state === 'playing'

    // Play button
    $('play-icon').textContent  = active ? '\u23F9' : '\u25B6'
    $('play-label').textContent = active ? 'Stop'    : 'Play text'
    $('play-btn').classList.toggle('nav__play-btn--stop', active)

    // Pause/stop buttons in both rows
    for (const id of ['pause-btn', 'xpause']) {
      const b = $(id)
      if (!b) continue
      b.disabled     = !active
      b.textContent  = playing ? '\u23F8' : '\u25B6'
      b.setAttribute('aria-label', playing ? 'Pause' : 'Resume')
    }
    for (const id of ['stop-btn', 'xstop']) {
      const b = $(id); if (b) b.disabled = !active
    }

    // Timer
    if (playing) {
      if (!this.#wallStart) {
        // Estimate duration: assume ~80 chars/sentence at ~14 chars/sec
        this.#estDuration = Math.max((total * 80) / 14, 2)
        this.#wallStart   = Date.now() - this.#pauseOffset
      }
      this.#startTimer()
    } else if (state === 'paused') {
      this.#pauseOffset = Date.now() - (this.#wallStart ?? Date.now())
      this.#stopTimer()
    } else {
      this.#wallStart   = null
      this.#pauseOffset = 0
      this.#estDuration = 0
      this.#stopTimer()
      this.#setTime(0, 0)
    }
  }

  #startTimer() {
    this.#stopTimer()
    this.#timerId = setInterval(() => this.#tick(), 500)
  }

  #stopTimer() {
    if (this.#timerId !== null) { clearInterval(this.#timerId); this.#timerId = null }
  }

  #tick() {
    if (!this.#wallStart) return
    this.#setTime((Date.now() - this.#wallStart) / 1000, this.#estDuration)
  }

  #setTime(elapsedSec, totalSec) {
    const pct   = totalSec > 0 ? Math.min((elapsedSec / totalSec) * 100, 100) : 0
    const label = `${this.#fmt(elapsedSec)} / ${this.#fmt(totalSec)}`
    for (const id of ['time-label', 'xtime']) {
      const el = this.#shadow.getElementById(id); if (el) el.textContent = label
    }
    for (const id of ['progress', 'xprogress']) {
      const el = this.#shadow.getElementById(id); if (el) el.value = String(pct)
    }
  }

  #fmt(s) {
    const t = Math.max(0, Math.floor(s))
    return `${String(Math.floor(t / 60)).padStart(2, '0')}:${String(t % 60).padStart(2, '0')}`
  }

  // ── Mobile expand ────────────────────────────────────────────────────────────

  #toggleExpand() {
    this.#expanded = !this.#expanded
    const row = this.#shadow.getElementById('xrow')
    const btn = this.#shadow.getElementById('expand-btn')
    row.hidden = !this.#expanded
    btn.setAttribute('aria-expanded', String(this.#expanded))
    btn.setAttribute('aria-label',
      this.#expanded ? 'Hide playback controls' : 'Show playback controls')
    btn.innerHTML = chevron(this.#expanded)
  }

  // ── Styles ──────────────────────────────────────────────────────────────────

  #css() {
    return /* css */`
/* Inherit document custom properties (they cross shadow boundary). */
:host {
  display: block;
  --_play: oklch(0.46 0.25 293); /* ≈ #7C3AED brand purple */
}

/* ── Nav bar ──────────────────────────────────────────────────────────────── */

.nav {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding-block: 0.45rem;
  padding-inline: 1rem;
  min-block-size: 3.25rem;
  border-block-end: 1px solid var(--border);
  background: var(--bg);
}

/* ── Logo ─────────────────────────────────────────────────────────────────── */

.nav__start { flex: 0 0 auto; }

.nav__logo {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  text-decoration: none;
  color: inherit;
}

.nav__logo svg {
  inline-size: 1.1rem;
  block-size: 1.3rem;
  color: var(--_play);
  flex-shrink: 0;
}

.nav__wordmark {
  font-family: Georgia, 'Palatino Linotype', 'Book Antiqua', Palatino, serif;
  font-size: 1.05rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  white-space: nowrap;
}

/* ── Middle controls strip ────────────────────────────────────────────────── */

.nav__mid {
  flex: 1 1 auto;
  min-inline-size: 0;
  display: flex;
  align-items: center;
  gap: 0.3rem;
  overflow: hidden;
}

/* ── Play button ──────────────────────────────────────────────────────────── */

.nav__play-btn {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  background: var(--_play);
  color: #fff;
  border: none;
  border-radius: 999px;
  padding: 0.3rem 0.85rem;
  font-size: 0.78rem;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  transition: opacity 120ms, transform 80ms;
}

.nav__play-btn:hover  { opacity: 0.85; }
.nav__play-btn:active { opacity: 0.7; transform: scale(0.97); }

/* Mild desaturate when showing "Stop" */
.nav__play-btn--stop {
  background: color-mix(in srgb, var(--_play) 60%, CanvasText 40%);
}

/* ── Transport ────────────────────────────────────────────────────────────── */

.nav__transport {
  display: flex;
  align-items: center;
  gap: 0.2rem;
  flex-shrink: 0;
}

.nav__ctrl {
  inline-size: 1.7rem;
  block-size: 1.7rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: 1px solid transparent;
  border-radius: 0.35rem;
  font-size: 0.8rem;
  font-family: inherit;
  color: var(--text, CanvasText);
  cursor: pointer;
  padding: 0;
  transition: background 100ms, border-color 100ms;
  flex-shrink: 0;
}

.nav__ctrl:hover:not(:disabled) {
  background: var(--surface);
  border-color: var(--border);
}

.nav__ctrl:disabled { opacity: 0.35; cursor: default; }

.nav__settings { font-size: 0.95rem; }

/* ── Scrubber ─────────────────────────────────────────────────────────────── */

.nav__scrubber {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-shrink: 1;
  min-inline-size: 0;
}

.nav__time {
  font-size: 0.7rem;
  font-variant-numeric: tabular-nums;
  color: var(--muted, color-mix(in srgb, CanvasText 60%, Canvas));
  white-space: nowrap;
  letter-spacing: 0.02em;
}

.nav__progress {
  -webkit-appearance: none;
  appearance: none;
  inline-size: clamp(4rem, 8vw, 8rem);
  block-size: 3px;
  border-radius: 999px;
  background: var(--border);
  outline: none;
  cursor: pointer;
  flex-shrink: 1;
}

.nav__progress::-webkit-slider-thumb {
  -webkit-appearance: none;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--accent, #3557ff);
  cursor: pointer;
  box-shadow: 0 0 0 2px var(--bg, Canvas);
}

.nav__progress::-moz-range-thumb {
  width: 10px;
  height: 10px;
  border: none;
  border-radius: 50%;
  background: var(--accent, #3557ff);
  cursor: pointer;
}

/* ── Pill selects ─────────────────────────────────────────────────────────── */

.nav__pill {
  -webkit-appearance: none;
  appearance: none;
  background-color: var(--surface);
  background-image: ${SELECT_ARROW};
  background-repeat: no-repeat;
  background-position: right 0.4rem center;
  background-size: 0.55rem 0.38rem;
  border: 1px solid var(--border);
  border-radius: 999px;
  padding-block: 0.2rem;
  padding-inline: 0.6rem 1.3rem;
  font-size: 0.76rem;
  font-family: inherit;
  color: inherit;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  max-inline-size: 9rem;
}

.nav__pill:focus-visible {
  outline: 2px solid var(--accent, #3557ff);
  outline-offset: 1px;
}

/* ── Follow-along toggle ──────────────────────────────────────────────────── */

.nav__follow {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  cursor: pointer;
  flex-shrink: 0;
  white-space: nowrap;
}

.nav__follow-txt {
  font-size: 0.76rem;
  user-select: none;
}

/* Visually-hidden checkbox (accessible but invisible) */
.nav__sr-only {
  position: absolute;
  inline-size: 1px;
  block-size: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

/* Toggle track */
.nav__switch {
  display: inline-block;
  inline-size: 2rem;
  block-size: 1.1rem;
  border-radius: 999px;
  background: var(--border-input, color-mix(in srgb, CanvasText 45%, Canvas));
  position: relative;
  flex-shrink: 0;
  transition: background 180ms;
}

/* Toggle thumb */
.nav__switch::after {
  content: '';
  position: absolute;
  inline-size: 0.8rem;
  block-size: 0.8rem;
  border-radius: 50%;
  background: white;
  inset-block-start: 0.15rem;
  inset-inline-start: 0.15rem;
  box-shadow: 0 1px 3px rgb(0 0 0 / 0.25);
  transition: translate 180ms cubic-bezier(0.4, 0, 0.2, 1);
}

.nav__sr-only:checked + .nav__switch {
  background: var(--_play);
}

.nav__sr-only:checked + .nav__switch::after {
  translate: 0.9rem 0;
}

/* Focus ring on the visible switch */
.nav__sr-only:focus-visible + .nav__switch {
  outline: 2px solid var(--accent, #3557ff);
  outline-offset: 2px;
}

/* ── End slot + expand button ─────────────────────────────────────────────── */

.nav__end {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin-inline-start: 0.25rem;
}

.nav__expand {
  display: none; /* shown on mobile below */
  inline-size: 1.7rem;
  block-size: 1.7rem;
  align-items: center;
  justify-content: center;
  background: none;
  border: 1px solid var(--border);
  border-radius: 0.35rem;
  cursor: pointer;
  color: inherit;
  padding: 0;
  flex-shrink: 0;
}

.nav__expand svg { inline-size: 0.7rem; block-size: 0.7rem; }

/* ── Expanded row (mobile) ────────────────────────────────────────────────── */

.nav__xrow {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
  padding-block: 0.5rem;
  padding-inline: 1rem;
  border-block-end: 1px solid var(--border);
  background: var(--surface);
}

.nav__xrow[hidden] { display: none; }

/* ── Mobile (<54rem / 864px) ──────────────────────────────────────────────── */

@media (max-width: 53.99rem) {
  .nav__expand { display: inline-flex; }

  /* Hide: desktop-only transport + voice + depth + settings in main bar */
  #transport,
  #voice-select,
  #depth-select,
  #settings-btn { display: none; }
}

/* ── Reduced motion ───────────────────────────────────────────────────────── */

@media (prefers-reduced-motion: reduce) {
  .nav__play-btn,
  .nav__switch,
  .nav__switch::after { transition: none; }
}
`
  }
}

customElements.define('mnemosyne-top-nav', MnemosyneTopNav)
