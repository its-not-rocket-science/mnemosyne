/**
 * mnemosyne-top-nav.js — Persistent navigation bar.
 *
 * Regions (left → right):
 *   Logo | Depth | Settings | <slot> (auth elements)
 *
 * Mobile (<54rem): Depth and Settings collapse into an expandable row.
 *
 * Dispatches (bubbles + composed):
 *   depth-change       — detail: { depth: string }
 *   settings-open      — user hit ⚙
 */

import { t } from '../js/i18n.js'

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

// Light chevron for dark nav background
const SELECT_ARROW = `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 10 6' fill='none' stroke='%23c4c2d4' stroke-width='1.6' stroke-linecap='round'%3E%3Cpath d='M1 1l4 4 4-4'/%3E%3C/svg%3E")`

// ── Component ─────────────────────────────────────────────────────────────────

class MnemosyneTopNav extends HTMLElement {
  #shadow
  #expanded = false
  #depth    = 'learning'

  constructor() {
    super()
    this.#shadow = this.attachShadow({ mode: 'open' })
  }

  #langHandler = null

  connectedCallback() {
    this.#shadow.innerHTML = this.#html()
    this.#wire()
    this.#langHandler = () => {
      this.#shadow.innerHTML = this.#html()
      this.#wire()
    }
    document.addEventListener('mnemosyne:language-changed', this.#langHandler)
  }

  disconnectedCallback() {
    if (this.#langHandler) {
      document.removeEventListener('mnemosyne:language-changed', this.#langHandler)
      this.#langHandler = null
    }
  }

  // ── Public getters ──────────────────────────────────────────────────────────

  get depth() { return this.#depth }
  set depth(value) {
    if (!['subtle', 'learning', 'deep'].includes(value)) return
    this.#depth = value
    if (!this.#shadow) return
    for (const id of ['depth-select', 'xdepth']) {
      const el = this.#shadow.getElementById(id)
      if (el) el.value = value
    }
    this.#updateModeIndicator()
  }

  // ── Template ────────────────────────────────────────────────────────────────

  #html() {
    return /* html */`
<style>${this.#css()}</style>

<nav class="nav" part="nav">

  <div class="nav__start">
    <a class="nav__logo" href="/" aria-label="${t('nav_home_aria')}">
      <img src="./mnemosyneThumbnail.png" alt="Mnemosyne logo" width="60" height="60">
      <span class="nav__wordmark">Mnemosyne</span>
    </a>
  </div>

  <div class="nav__mid">

    <select class="nav__pill" id="depth-select" aria-label="${t('nav_depth_aria')}">
      <option value="subtle">${t('nav_depth_subtle')}</option>
      <option value="learning">${t('nav_depth_learning')}</option>
      <option value="deep">${t('nav_depth_deep')}</option>
    </select>
    <span class="nav__mode-indicator" id="mode-indicator" aria-live="polite">${t('nav_mode_label')}: ${t('nav_depth_learning')}</span>

    <button class="nav__ctrl nav__settings" id="settings-btn"
            type="button" aria-label="${t('nav_settings_aria')}">&#x2699;&#xFE0E;</button>

  </div><!-- /.nav__mid -->

  <div class="nav__end">
    <slot></slot>
    <button class="nav__expand" id="expand-btn" type="button"
            aria-label="${t('nav_expand_show')}"
            aria-expanded="false" aria-controls="xrow">
      ${chevron(false)}
    </button>
  </div>

</nav><!-- /.nav -->

<!-- Expanded row: depth + settings (mobile only) -->
<div class="nav__xrow" id="xrow" hidden>
  <select class="nav__pill" id="xdepth" aria-label="${t('nav_depth_aria')}">
    <option value="subtle">${t('nav_depth_subtle')}</option>
    <option value="learning">${t('nav_depth_learning')}</option>
    <option value="deep">${t('nav_depth_deep')}</option>
  </select>
  <button class="nav__ctrl nav__settings" id="xsettings"
          type="button" aria-label="${t('nav_settings_aria')}">&#x2699;&#xFE0E;</button>
</div>`
  }

  // ── Wire events ─────────────────────────────────────────────────────────────

  #wire() {
    const $ = id => this.#shadow.getElementById(id)

    // Depth
    for (const id of ['depth-select', 'xdepth']) {
      $(id)?.addEventListener('change', e => {
        this.#syncSelect('depth-select', 'xdepth', e.target.id, e.target.value)
        this.#depth = e.target.value
        this.dispatchEvent(new CustomEvent('depth-change', {
          bubbles: true, composed: true,
          detail: { depth: this.#depth },
        }))
        this.#updateModeIndicator()
      })
    }

    // Settings
    const openSettings = () =>
      this.dispatchEvent(new CustomEvent('settings-open', { bubbles: true, composed: true }))
    $('settings-btn').addEventListener('click', openSettings)
    $('xsettings').addEventListener('click', openSettings)

    for (const id of ['depth-select', 'xdepth']) {
      const el = $(id); if (el) el.value = this.#depth
    }
    this.#updateModeIndicator()

    // Expand / collapse
    $('expand-btn').addEventListener('click', () => this.#toggleExpand())
  }

  // Keep paired selects in sync when one changes
  #syncSelect(idA, idB, changedId, value) {
    const other = this.#shadow.getElementById(changedId === idA ? idB : idA)
    if (other) other.value = value
  }

  #updateModeIndicator() {
    const label = t(`nav_depth_${this.#depth}`)
    const indicator = this.#shadow.getElementById('mode-indicator')
    if (indicator) indicator.textContent = `${t('nav_mode_label')}: ${label}`
  }

  // ── Mobile expand ────────────────────────────────────────────────────────────

  #toggleExpand() {
    this.#expanded = !this.#expanded
    const row = this.#shadow.getElementById('xrow')
    const btn = this.#shadow.getElementById('expand-btn')
    row.hidden = !this.#expanded
    btn.setAttribute('aria-expanded', String(this.#expanded))
    btn.setAttribute('aria-label',
      this.#expanded ? t('nav_expand_hide') : t('nav_expand_show'))
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

/* Slotted light-DOM elements (user-info, sign-out, etc.) on dark nav */
::slotted(*) {
  color: oklch(0.92 0.02 280);
}

::slotted(.ghost-button) {
  border-color: rgb(255 255 255 / 0.25);
  color: oklch(0.88 0.02 280);
}

/* ── Nav bar ──────────────────────────────────────────────────────────────── */

.nav {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding-block: 0.45rem;
  padding-inline: 1rem;
  min-block-size: 3.25rem;
  border-block-end: 1px solid rgb(255 255 255 / 0.08);
  background: oklch(0.22 0.06 280);
  color: oklch(0.92 0.02 280);
}

/* ── Logo ─────────────────────────────────────────────────────────────────── */

.nav__start { flex: 0 0 auto; }

.nav__logo {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  text-decoration: none;
  color: oklch(0.96 0.01 280);
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

/* ── Settings button ─────────────────────────────────────────────────────── */

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
  color: oklch(0.88 0.02 280);
  cursor: pointer;
  padding: 0;
  transition: background 100ms, border-color 100ms;
  flex-shrink: 0;
}

.nav__ctrl:hover:not(:disabled) {
  background: rgb(255 255 255 / 0.12);
  border-color: rgb(255 255 255 / 0.2);
}

.nav__settings { font-size: 0.95rem; }

.nav__mode-indicator {
  font-size: 0.74rem;
  color: oklch(0.86 0.02 280);
  border: 1px solid rgb(255 255 255 / 0.2);
  border-radius: 999px;
  padding: 0.1rem 0.45rem;
  white-space: nowrap;
}

/* ── Pill selects ─────────────────────────────────────────────────────────── */

.nav__pill {
  -webkit-appearance: none;
  appearance: none;
  background-color: rgb(255 255 255 / 0.1);
  background-image: ${SELECT_ARROW};
  background-repeat: no-repeat;
  background-position: right 0.4rem center;
  background-size: 0.55rem 0.38rem;
  border: 1px solid rgb(255 255 255 / 0.18);
  border-radius: 999px;
  padding-block: 0.2rem;
  padding-inline: 0.6rem 1.3rem;
  font-size: 0.76rem;
  font-family: inherit;
  color: oklch(0.92 0.02 280);
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  max-inline-size: 9rem;
}

.nav__pill:focus-visible {
  outline: 2px solid var(--accent, #3557ff);
  outline-offset: 1px;
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
  border: 1px solid rgb(255 255 255 / 0.2);
  border-radius: 0.35rem;
  cursor: pointer;
  color: oklch(0.88 0.02 280);
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
  border-block-end: 1px solid rgb(255 255 255 / 0.08);
  background: oklch(0.26 0.05 280);
}

.nav__xrow[hidden] { display: none; }

/* ── Mobile (<54rem / 864px) ──────────────────────────────────────────────── */

@media (max-width: 53.99rem) {
  .nav__expand { display: inline-flex; }

  /* Hide desktop-only depth + settings in main bar; show in xrow instead */
  #depth-select,
  #settings-btn { display: none; }
}
`
  }
}

customElements.define('mnemosyne-top-nav', MnemosyneTopNav)
