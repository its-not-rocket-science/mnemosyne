/**
 * mnemosyne-now-playing-bar.js — Persistent playback status bar.
 *
 * Sits at the bottom of .app-shell__left (flex-shrink: 0 sibling of <main>),
 * so it is always visible within the text-panel column and never overlaps
 * the detail panel on desktop.
 *
 * Desktop layout (always expanded):
 *   Strip:    [Now playing] [waveform] [track title] [≡ queue]  ···  [✕ dismiss]
 *   Expanded: [Sentence N of M]
 *             [Sentence text bold]
 *             [⏮][⏸][⏭]  ──────── progress ────────  00:06 / 00:08
 *
 * Mobile (<54rem) — single compact row, tapping expands to full:
 *   Compact:  [sentence text truncated ··· progress bar]  [⏸]
 *   Expanded: same as desktop
 *
 * Connects directly to playbackEngine singleton.
 * Attribute: track-title  — "Act II, Scene VII – The Merchant of Venice"
 *
 * Events (bubbles + composed):
 *   np-queue   — user opened the queue
 */

import { playbackEngine } from '../js/playback.js'

class MnemosyneNowPlayingBar extends HTMLElement {
  #shadow
  #expanded    = false  // mobile expand state
  #wallStart   = null
  #pauseOffset = 0
  #estDuration = 0
  #timerId     = null

  static get observedAttributes() { return ['track-title'] }

  constructor() {
    super()
    this.#shadow = this.attachShadow({ mode: 'open' })
  }

  connectedCallback() {
    this.#shadow.innerHTML = this.#html()
    this.#wire()
    playbackEngine.addEventListener('state-change', this.#onStateChange)
    // Sync with engine state that may already be running
    this.#syncFull({
      state:   playbackEngine.state,
      current: playbackEngine.current,
      index:   playbackEngine.index,
      total:   playbackEngine.total,
    })
  }

  disconnectedCallback() {
    playbackEngine.removeEventListener('state-change', this.#onStateChange)
    this.#stopTimer()
  }

  attributeChangedCallback(name, _old, val) {
    if (name === 'track-title') {
      const el = this.#shadow.getElementById('track-title')
      if (el) { el.textContent = val ?? ''; el.title = val ?? '' }
    }
  }

  // ── Playback state ────────────────────────────────────────────────────────────

  #onStateChange = ({ detail }) => this.#syncFull(detail)

  #syncFull({ state, current, index, total }) {
    this.hidden = state === 'idle'

    const shadow = this.#shadow
    const bar    = shadow.querySelector('.bar')
    if (bar) bar.dataset.state = state

    const playing = state === 'playing'
    const icon    = playing ? '\u23F8' : '\u25B6'  // ⏸ / ▶
    const label   = playing ? 'Pause'  : 'Resume'

    // Update both play buttons
    for (const id of ['play-toggle', 'compact-play']) {
      const b = shadow.getElementById(id)
      if (!b) continue
      b.textContent = icon
      b.setAttribute('aria-label', label)
    }

    // Sentence text / counter
    if (current) {
      const meta = `Sentence\u00A0${index + 1}\u00A0of\u00A0${total}`
      shadow.getElementById('sentence-meta')?.let(el => { el.textContent = meta })
      const textStr = current.text
      shadow.getElementById('sentence-text')?.let(el => { el.textContent = textStr })
      shadow.getElementById('compact-text')?.let(el => { el.textContent = textStr })

      // Manually set since .let() isn't real — use helper
      this.#setText('sentence-meta',  meta)
      this.#setText('sentence-text',  current.text)
      this.#setText('compact-text',   current.text)
    }

    // Timer management
    if (playing) {
      if (!this.#wallStart) {
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
      this.#setProgress(0, 0)
    }
  }

  #setText(id, value) {
    const el = this.#shadow.getElementById(id)
    if (el) el.textContent = value
  }

  // ── Timer ──────────────────────────────────────────────────────────────────────

  #startTimer() {
    this.#stopTimer()
    this.#timerId = setInterval(() => this.#tick(), 500)
  }

  #stopTimer() {
    if (this.#timerId !== null) { clearInterval(this.#timerId); this.#timerId = null }
  }

  #tick() {
    if (!this.#wallStart) return
    this.#setProgress((Date.now() - this.#wallStart) / 1000, this.#estDuration)
  }

  #setProgress(elapsed, total) {
    const pct   = total > 0 ? Math.min((elapsed / total) * 100, 100) : 0
    const label = `${this.#fmt(elapsed)}\u2009/\u2009${this.#fmt(total)}`
    const pctStr = `${pct.toFixed(1)}%`

    const fill  = this.#shadow.getElementById('progress-fill')
    const cFill = this.#shadow.getElementById('compact-fill')
    const ts    = this.#shadow.getElementById('timestamps')
    const track = this.#shadow.querySelector('.progress-track')

    if (fill)  fill.style.inlineSize  = pctStr
    if (cFill) cFill.style.inlineSize = pctStr
    if (ts)    ts.textContent = label
    if (track) track.setAttribute('aria-valuenow', String(Math.round(pct)))
  }

  #fmt(s) {
    const t = Math.max(0, Math.floor(s))
    return `${String(Math.floor(t / 60)).padStart(2, '0')}:${String(t % 60).padStart(2, '0')}`
  }

  // ── Wiring ────────────────────────────────────────────────────────────────────

  #wire() {
    const shadow = this.#shadow
    const $ = id => shadow.getElementById(id)

    $('prev-btn')?.addEventListener('click', () => playbackEngine.prev())
    $('next-btn')?.addEventListener('click', () => playbackEngine.next())
    $('play-toggle')?.addEventListener('click', () => playbackEngine.togglePause())

    $('compact-play')?.addEventListener('click', e => {
      e.stopPropagation()   // don't bubble to compact-expand
      playbackEngine.togglePause()
    })

    $('dismiss-btn')?.addEventListener('click', () => playbackEngine.stop())

    $('queue-btn')?.addEventListener('click', () => {
      this.dispatchEvent(new CustomEvent('np-queue', { bubbles: true, composed: true }))
    })

    // Mobile: tap compact area → expand
    $('compact-expand')?.addEventListener('click', () => {
      this.#expanded = !this.#expanded
      const bar = shadow.querySelector('.bar')
      if (bar) bar.dataset.expanded = String(this.#expanded)
      const btn = $('compact-expand')
      if (btn) btn.setAttribute('aria-expanded', String(this.#expanded))
    })
  }

  // ── Template ──────────────────────────────────────────────────────────────────

  #html() {
    const title = this.getAttribute('track-title') ?? ''
    return /* html */`
<style>${this.#css()}</style>

<div class="bar" part="bar" data-state="idle" data-expanded="false">

  <!-- ── Mobile compact row (hidden on desktop) ── -->
  <div class="compact">
    <button class="compact__expand" id="compact-expand" type="button"
            aria-label="Expand now playing" aria-expanded="false"
            aria-controls="expanded-section">
      <p class="compact__text" id="compact-text"></p>
      <div class="compact__prog-track" aria-hidden="true">
        <div class="compact__fill" id="compact-fill"></div>
      </div>
    </button>
    <button class="ctrl ctrl--circle" id="compact-play" type="button" aria-label="Pause">&#x23F8;</button>
  </div>

  <!-- ── Desktop strip + mobile expanded header ── -->
  <div class="strip" id="strip-section">

    <div class="strip__start">
      <span class="strip__label" aria-hidden="true">Now&nbsp;playing</span>
      <span class="strip__waveform" id="waveform" aria-hidden="true">
        <span class="wv"></span>
        <span class="wv"></span>
        <span class="wv"></span>
        <span class="wv"></span>
      </span>
      <span class="strip__title" id="track-title" title="${title}">${title}</span>
      <button class="icon-btn" id="queue-btn" type="button" aria-label="View queue">
        <svg viewBox="0 0 18 14" aria-hidden="true" focusable="false" fill="currentColor">
          <rect x="0" y="0"  width="18" height="2" rx="1"/>
          <rect x="0" y="6"  width="13" height="2" rx="1"/>
          <rect x="0" y="12" width="9"  height="2" rx="1"/>
        </svg>
      </button>
    </div>

    <div class="strip__end">
      <button class="icon-btn icon-btn--close" id="dismiss-btn" type="button"
              aria-label="Dismiss now playing">&#x2715;</button>
    </div>

  </div>

  <!-- ── Expanded section ── -->
  <div class="expanded" id="expanded-section">

    <div class="expanded__info">
      <span class="expanded__meta" id="sentence-meta" aria-live="polite"></span>
      <p class="expanded__text" id="sentence-text"></p>
    </div>

    <div class="expanded__controls">

      <div class="transport" role="group" aria-label="Playback controls">
        <button class="ctrl" id="prev-btn" type="button" aria-label="Previous sentence">&#x23EE;</button>
        <button class="ctrl ctrl--circle" id="play-toggle" type="button" aria-label="Pause">&#x23F8;</button>
        <button class="ctrl" id="next-btn" type="button" aria-label="Next sentence">&#x23ED;</button>
      </div>

      <div class="progress-area">
        <div class="progress-track"
             role="progressbar" aria-label="Playback progress"
             aria-valuemin="0" aria-valuemax="100" aria-valuenow="0">
          <div class="progress-fill" id="progress-fill"></div>
        </div>
        <span class="timestamps" id="timestamps" aria-live="off">00:00&thinsp;/&thinsp;00:00</span>
      </div>

    </div>

  </div>

</div>`
  }

  // ── Styles ────────────────────────────────────────────────────────────────────

  #css() {
    return /* css */`
:host {
  display: block;
  flex-shrink: 0;
}

:host([hidden]) { display: none; }

/* ── Bar shell ───────────────────────────────────────────────────────────── */

.bar {
  background: var(--bg, Canvas);
  border-block-start: 1px solid
    var(--border, color-mix(in srgb, CanvasText 15%, Canvas));
  box-shadow: 0 -3px 14px rgb(0 0 0 / 0.07);
}

/* ── Mobile compact row ──────────────────────────────────────────────────── */

.compact {
  display: none;  /* shown at ≤53.99rem */
  align-items: center;
  gap: 0.6rem;
  padding-block: 0.5rem;
  padding-inline: 0.9rem;
}

/* Expand button wraps text + mini progress — tapping it expands the bar */
.compact__expand {
  flex: 1 1 auto;
  min-inline-size: 0;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
  text-align: start;
}

.compact__text {
  margin: 0;
  font-size: 0.83rem;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: CanvasText;
}

.compact__prog-track {
  block-size: 2px;
  border-radius: 1px;
  background: var(--border, color-mix(in srgb, CanvasText 20%, Canvas));
  position: relative;
  overflow: hidden;
}

.compact__fill {
  position: absolute;
  inset-block: 0;
  inset-inline-start: 0;
  inline-size: 0%;
  background: var(--accent, #3557ff);
  border-radius: 1px;
  transition: inline-size 500ms linear;
}

/* ── Strip ───────────────────────────────────────────────────────────────── */

.strip {
  display: flex;
  align-items: center;
  padding-block: 0.45rem;
  padding-inline: 0.9rem;
  gap: 0.5rem;
}

.strip__start {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  flex: 1 1 auto;
  min-inline-size: 0;
}

.strip__end {
  flex-shrink: 0;
}

.strip__label {
  font-size: 0.6rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.09em;
  color: var(--accent, #3557ff);
  white-space: nowrap;
  flex-shrink: 0;
}

/* ── Animated waveform ───────────────────────────────────────────────────── */

.strip__waveform {
  display: inline-flex;
  align-items: flex-end;
  gap: 2px;
  block-size: 0.9rem;
  flex-shrink: 0;
}

.wv {
  inline-size: 3px;
  border-radius: 1.5px;
  background: var(--accent, #3557ff);
  animation: wv-beat 0.8s ease-in-out infinite alternate;
  transform-origin: bottom;
}

.wv:nth-child(1) { block-size: 8px;  animation-duration: 0.60s; animation-delay: 0.00s; }
.wv:nth-child(2) { block-size: 13px; animation-duration: 0.90s; animation-delay: 0.12s; }
.wv:nth-child(3) { block-size: 10px; animation-duration: 0.70s; animation-delay: 0.22s; }
.wv:nth-child(4) { block-size: 6px;  animation-duration: 0.82s; animation-delay: 0.35s; }

@keyframes wv-beat {
  from { transform: scaleY(0.22); }
  to   { transform: scaleY(1); }
}

.bar[data-state="paused"] .wv,
.bar[data-state="idle"]   .wv {
  animation-play-state: paused;
  transform: scaleY(0.35);
}

.strip__title {
  font-size: 0.8rem;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1 1 auto;
  min-inline-size: 0;
}

/* ── Expanded section ────────────────────────────────────────────────────── */

.expanded {
  padding-block: 0.1rem 0.7rem;
  padding-inline: 0.9rem;
}

.expanded__info {
  margin-block-end: 0.5rem;
}

.expanded__meta {
  display: block;
  font-size: 0.62rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--muted, color-mix(in srgb, CanvasText 50%, Canvas));
  margin-block-end: 0.18rem;
}

.expanded__text {
  margin: 0;
  font-size: 0.9rem;
  font-weight: 700;
  line-height: 1.4;
  /* Limit to 2 lines; full text is spoken, visual is a cue */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* ── Controls row ────────────────────────────────────────────────────────── */

.expanded__controls {
  display: flex;
  align-items: center;
  gap: 0.9rem;
  margin-block-start: 0.55rem;
}

.transport {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  flex-shrink: 0;
}

/* ── Buttons (shared) ────────────────────────────────────────────────────── */

.ctrl {
  inline-size: 2rem;
  block-size: 2rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  border-radius: 0.35rem;
  font-size: 0.9rem;
  font-family: inherit;
  color: CanvasText;
  cursor: pointer;
  padding: 0;
  flex-shrink: 0;
  transition: background 100ms;
}

.ctrl:hover:not(:disabled) {
  background: color-mix(in srgb, CanvasText 10%, transparent);
}

.ctrl:disabled { opacity: 0.35; cursor: default; }

.ctrl:focus-visible {
  outline: 2px solid var(--accent, #3557ff);
  outline-offset: 2px;
}

/* Primary circle play/pause button */
.ctrl--circle {
  border-radius: 50%;
  inline-size: 2.2rem;
  block-size: 2.2rem;
  background: var(--accent, #3557ff);
  color: #fff;
  font-size: 0.85rem;
}

.ctrl--circle:hover:not(:disabled) {
  background: color-mix(in srgb, var(--accent, #3557ff) 85%, #000 15%);
}

/* Small icon buttons (queue, dismiss) */
.icon-btn {
  inline-size: 1.8rem;
  block-size: 1.8rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  border-radius: 0.3rem;
  cursor: pointer;
  color: var(--muted, color-mix(in srgb, CanvasText 50%, Canvas));
  padding: 0;
  flex-shrink: 0;
  transition: color 100ms, background 100ms;
}

.icon-btn svg { inline-size: 0.9rem; block-size: auto; }

.icon-btn:hover {
  color: CanvasText;
  background: color-mix(in srgb, CanvasText 8%, transparent);
}

.icon-btn:focus-visible {
  outline: 2px solid var(--accent, #3557ff);
  outline-offset: 2px;
}

.icon-btn--close { font-size: 0.78rem; }

/* ── Progress + timestamps ───────────────────────────────────────────────── */

.progress-area {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  flex: 1 1 auto;
  min-inline-size: 0;
}

.progress-track {
  flex: 1 1 auto;
  block-size: 4px;
  border-radius: 2px;
  background: var(--border, color-mix(in srgb, CanvasText 18%, Canvas));
  position: relative;
  overflow: hidden;
  cursor: pointer;
}

.progress-track:hover { block-size: 6px; }

.progress-fill {
  position: absolute;
  inset-block: 0;
  inset-inline-start: 0;
  inline-size: 0%;
  background: var(--accent, #3557ff);
  border-radius: 2px;
  transition: inline-size 500ms linear;
}

.timestamps {
  font-size: 0.68rem;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  color: var(--muted, color-mix(in srgb, CanvasText 50%, Canvas));
  letter-spacing: 0.02em;
  flex-shrink: 0;
}

/* ── Mobile (<54rem) ─────────────────────────────────────────────────────── */

@media (max-width: 53.99rem) {
  /* Default collapsed: compact strip only */
  .compact        { display: flex; }
  .strip          { display: none; }
  .expanded       { display: none; }

  /* Expanded state: show full bar */
  .bar[data-expanded="true"] .compact  { display: none; }
  .bar[data-expanded="true"] .strip    { display: flex; }
  .bar[data-expanded="true"] .expanded { display: block; }
}

/* ── Reduced motion ──────────────────────────────────────────────────────── */

@media (prefers-reduced-motion: reduce) {
  .wv                   { animation: none; transform: scaleY(0.6); }
  .progress-fill,
  .compact__fill        { transition: none; }
  .ctrl, .icon-btn      { transition: none; }
  .progress-track:hover { block-size: 4px; }
}
`
  }
}

customElements.define('mnemosyne-now-playing-bar', MnemosyneNowPlayingBar)
