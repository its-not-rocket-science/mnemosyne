/**
 * mnemosyne-player.js
 *
 * Fixed mini-player bar shown during TTS playback.
 * Displays current sentence text, position, and transport controls.
 * Automatically hidden while the playback engine is idle.
 *
 * Integration: import this module (or include as a <script type="module">).
 * It connects to the singleton playbackEngine exported from ../js/playback.js.
 */

import { playbackEngine } from '../js/playback.js'

class MnemosynePlayer extends HTMLElement {
  #stateHandler = null

  constructor() {
    super()
    this.attachShadow({ mode: 'open' })
  }

  connectedCallback() {
    this._render()
    this.#stateHandler = (e) => this._onStateChange(e.detail)
    playbackEngine.addEventListener('state-change', this.#stateHandler)
  }

  disconnectedCallback() {
    if (this.#stateHandler) {
      playbackEngine.removeEventListener('state-change', this.#stateHandler)
      this.#stateHandler = null
    }
  }

  _onStateChange({ state, current, index, total }) {
    if (state === 'idle') {
      this.hidden = true
      document.body.classList.remove('player-active')
      return
    }

    this.hidden = false
    document.body.classList.add('player-active')

    const sr = this.shadowRoot

    const posEl = sr.querySelector('.player__position')
    if (posEl) {
      posEl.textContent = total > 1 ? `${index + 1} / ${total}` : ''
    }

    const textEl = sr.querySelector('.player__text')
    if (textEl) textEl.textContent = current?.text ?? ''

    const playBtn = sr.querySelector('.player__play-pause')
    if (playBtn) {
      const isPlaying = state === 'playing'
      playBtn.innerHTML = isPlaying
        ? '<span aria-hidden="true">&#x23F8;</span>'
        : '<span aria-hidden="true">&#x25B6;</span>'
      playBtn.setAttribute('aria-label', isPlaying ? 'Pause' : 'Resume')
    }

    const prevBtn = sr.querySelector('.player__prev')
    const nextBtn = sr.querySelector('.player__next')
    if (prevBtn) prevBtn.disabled = total <= 1
    if (nextBtn) nextBtn.disabled = total <= 1 || index >= total - 1
  }

  _render() {
    this.shadowRoot.innerHTML = /* html */`
      <style>${this._styles()}</style>
      <div class="player" role="region" aria-label="Playback controls">

        <div class="player__info">
          <span class="player__position" aria-live="polite" aria-atomic="true"></span>
          <p class="player__text"></p>
        </div>

        <div class="player__controls" role="group" aria-label="Transport">
          <button class="player__btn player__prev" type="button"
                  aria-label="Previous sentence" disabled>
            <span aria-hidden="true">&#x23EE;</span>
          </button>
          <button class="player__btn player__play-pause" type="button" aria-label="Pause">
            <span aria-hidden="true">&#x23F8;</span>
          </button>
          <button class="player__btn player__next" type="button"
                  aria-label="Next sentence" disabled>
            <span aria-hidden="true">&#x23ED;</span>
          </button>
          <button class="player__btn player__stop" type="button"
                  aria-label="Stop playback">
            <span aria-hidden="true">&#x23F9;</span>
          </button>
        </div>

      </div>
    `

    const sr = this.shadowRoot
    sr.querySelector('.player__play-pause').addEventListener('click', () => playbackEngine.togglePause())
    sr.querySelector('.player__prev').addEventListener('click', () => playbackEngine.prev())
    sr.querySelector('.player__next').addEventListener('click', () => playbackEngine.next())
    sr.querySelector('.player__stop').addEventListener('click', () => playbackEngine.stop())
  }

  _styles() {
    return /* css */`
      :host {
        position: fixed;
        inset-block-end: 0;
        inset-inline: 0;
        z-index: 150;
        display: block;
      }
      :host([hidden]) { display: none; }

      .player {
        background: var(--surface);
        border-block-start: 1px solid var(--border);
        box-shadow: 0 -0.25rem 1rem rgb(0 0 0 / 0.1);
        display: flex;
        align-items: center;
        gap: var(--space-2);
        /* Align inner content with the page's .wrap container */
        padding-inline: max(var(--space-3), calc(50% - 36rem));
        padding-block: 0.5rem;
        min-block-size: 3.5rem;
      }

      /* ── Sentence info ──────────────────────────────────────────────────── */

      .player__info {
        flex: 1 1 0;
        min-inline-size: 0;
        display: flex;
        align-items: baseline;
        gap: var(--space-1);
        overflow: hidden;
      }

      .player__position {
        font-size: 0.6875rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        color: var(--muted);
        white-space: nowrap;
        flex-shrink: 0;
      }

      .player__text {
        font-size: 0.875rem;
        color: var(--text);
        margin: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        min-inline-size: 0;
      }

      /* ── Transport controls ─────────────────────────────────────────────── */

      .player__controls {
        display: flex;
        align-items: center;
        gap: 0.25rem;
        flex-shrink: 0;
      }

      .player__btn {
        background: transparent;
        border: 1px solid var(--border-input);
        border-radius: 999px;
        font: inherit;
        font-size: 0.875rem;
        line-height: 1;
        color: var(--text);
        cursor: pointer;
        min-block-size: 2.75rem;
        min-inline-size: 2.75rem;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0;
        transition: background 0.1s ease, color 0.1s ease;
      }

      .player__btn:hover:not(:disabled) {
        background: var(--border);
      }

      .player__btn:disabled {
        opacity: 0.35;
        cursor: default;
      }

      .player__btn:focus-visible {
        outline: 3px solid var(--accent);
        outline-offset: 2px;
      }

      /* Play/pause is the primary action — accent filled */
      .player__play-pause {
        background: var(--accent);
        color: white;
        border-color: var(--accent);
      }

      .player__play-pause:hover:not(:disabled) {
        background: color-mix(in srgb, var(--accent) 85%, black);
      }

      /* Stop is a quiet secondary action */
      .player__stop {
        border-color: transparent;
        color: var(--muted);
      }

      .player__stop:hover:not(:disabled) {
        color: var(--text);
        border-color: var(--border-input);
        background: var(--border);
      }

      @media (prefers-reduced-motion: reduce) {
        .player__btn { transition: none; }
      }

      /* On very narrow screens, collapse the text so controls remain usable */
      @media (max-width: 25rem) {
        .player__info { display: none; }
      }
    `
  }
}

customElements.define('mnemosyne-player', MnemosynePlayer)
