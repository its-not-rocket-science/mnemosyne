/**
 * mnemosyne-weakness-graph — learner weakness profile visualisation.
 *
 * Usage
 * ─────
 *   <mnemosyne-weakness-graph language="es"></mnemosyne-weakness-graph>
 *
 * Public API
 * ──────────
 *   el.load(language?)  — fetch and render the weakness profile for language
 *   el.reset()          — clear and return to idle state
 *
 * Attributes
 * ──────────
 *   language  — BCP-47 language code (e.g. "es", "ja")
 *
 * Design intent
 * ─────────────
 * Scholarly, exploratory tone.  No streaks, no confetti.
 * Shows conceptual growth: stage distribution, concept-type accuracy,
 * confusion pairs, and high-friction constructions.
 *
 * Accessibility
 * ─────────────
 *   · All data presented in accessible text (no colour-only signalling).
 *   · ARIA live region announces load completion.
 *   · Keyboard accessible; no mouse-only interactions.
 */

import { API_BASE } from '../js/config.js'

const STAGE_LABELS = {
  recognition:               'Recognition',
  guided_recall:             'Guided recall',
  partial_production:        'Partial production',
  transformation:            'Transformation',
  free_production:           'Free production',
  contextual_interpretation: 'Contextual interpretation',
}

const STAGE_ORDER = Object.keys(STAGE_LABELS)

function _esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

export class MnemosyneWeaknessGraph extends HTMLElement {
  #language = null
  #loading = false

  static get observedAttributes() { return ['language'] }

  constructor() {
    super()
    this.attachShadow({ mode: 'open' })
  }

  connectedCallback() {
    this._renderIdle()
    const lang = this.getAttribute('language')
    if (lang) this.load(lang)
  }

  attributeChangedCallback(name, _old, val) {
    if (name === 'language' && val && val !== this.#language) {
      this.load(val)
    }
  }

  // ── Public API ─────────────────────────────────────────────────────────────

  async load(language) {
    if (this.#loading) return
    this.#language = language
    this.#loading = true
    this._renderLoading()
    try {
      const token = localStorage.getItem('mnemosyne_token')
      const resp = await fetch(
        `${API_BASE}/weakness/profile/${encodeURIComponent(language)}`,
        { headers: token ? { Authorization: `Bearer ${token}` } : {} }
      )
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const profile = await resp.json()
      this._renderProfile(profile)
    } catch (err) {
      this._renderError(err.message)
    } finally {
      this.#loading = false
    }
  }

  reset() {
    this.#language = null
    this._renderIdle()
  }

  // ── Rendering ──────────────────────────────────────────────────────────────

  _renderIdle() {
    this.shadowRoot.innerHTML = `
      ${this._styles()}
      <div class="graph" aria-live="polite"></div>
    `
  }

  _renderLoading() {
    this.shadowRoot.innerHTML = `
      ${this._styles()}
      <div class="graph" aria-live="polite" aria-busy="true">
        <p class="muted">Loading acquisition profile…</p>
      </div>
    `
  }

  _renderError(msg) {
    this.shadowRoot.innerHTML = `
      ${this._styles()}
      <div class="graph" role="alert">
        <p class="muted">Profile unavailable: ${_esc(msg)}</p>
      </div>
    `
  }

  _renderProfile(profile) {
    const { stage_distribution, concept_type_accuracy, confusion_pairs, high_friction_items, total_items } = profile

    // ── Stage distribution ──────────────────────────────────────────────────
    const stageRows = STAGE_ORDER.map(stage => {
      const count = stage_distribution?.[stage] ?? 0
      const pct = total_items > 0 ? Math.round((count / total_items) * 100) : 0
      const label = STAGE_LABELS[stage] || stage
      return /* html */`
        <li class="stage-row" aria-label="${_esc(label)}: ${count} item${count !== 1 ? 's' : ''}, ${pct}%">
          <span class="stage-label">${_esc(label)}</span>
          <div class="stage-bar-wrap" aria-hidden="true">
            <div class="stage-bar" style="inline-size:${pct}%" data-stage="${_esc(stage)}"></div>
          </div>
          <span class="stage-count">${count}</span>
        </li>
      `
    }).join('')

    // ── Concept type accuracy ───────────────────────────────────────────────
    const accuracyRows = (concept_type_accuracy || []).slice(0, 8).map(entry => {
      const pct = Math.round(entry.accuracy * 100)
      const label = entry.concept_type.replace(/_/g, ' ')
      return /* html */`
        <li class="accuracy-row" aria-label="${_esc(label)}: ${pct}% accuracy, ${entry.total_reviews} review${entry.total_reviews !== 1 ? 's' : ''}">
          <span class="accuracy-label">${_esc(label)}</span>
          <div class="stage-bar-wrap" aria-hidden="true">
            <div class="accuracy-bar" style="inline-size:${pct}%" data-pct="${pct}"></div>
          </div>
          <span class="accuracy-pct">${pct}%</span>
        </li>
      `
    }).join('')

    // ── Confusion pairs ─────────────────────────────────────────────────────
    const confusionRows = (confusion_pairs || []).slice(0, 6).map(pair => /* html */`
      <li class="confusion-row">
        <span class="confusion-form">${_esc(pair.confused_with)}</span>
        <span class="confusion-count" aria-label="${pair.confusion_count} time${pair.confusion_count !== 1 ? 's' : ''}">${pair.confusion_count}×</span>
      </li>
    `).join('')

    this.shadowRoot.innerHTML = `
      ${this._styles()}
      <div class="graph" aria-live="polite" aria-label="Acquisition profile for ${_esc(profile.language)}">

        <section class="section" aria-labelledby="wg-stage-h">
          <h3 class="section-heading" id="wg-stage-h">Acquisition stages</h3>
          <p class="muted">${total_items} item${total_items !== 1 ? 's' : ''} tracked</p>
          ${total_items > 0 ? `<ul class="stage-list">${stageRows}</ul>` : `<p class="muted">No items reviewed yet.</p>`}
        </section>

        ${accuracyRows ? /* html */`
        <section class="section" aria-labelledby="wg-accuracy-h">
          <h3 class="section-heading" id="wg-accuracy-h">Accuracy by concept type</h3>
          <ul class="stage-list">${accuracyRows}</ul>
        </section>
        ` : ''}

        ${confusionRows ? /* html */`
        <section class="section" aria-labelledby="wg-confusion-h">
          <h3 class="section-heading" id="wg-confusion-h">Recurring confusions</h3>
          <p class="muted">Items most frequently confused with others. Contrast drills are scheduled automatically.</p>
          <ul class="confusion-list">${confusionRows}</ul>
        </section>
        ` : ''}

        ${high_friction_items?.length ? /* html */`
        <section class="section" aria-labelledby="wg-friction-h">
          <h3 class="section-heading" id="wg-friction-h">High-friction constructions</h3>
          <p class="muted">Items reviewed several times with low mastery — they benefit most from context recycling.</p>
          <ul class="friction-list">
            ${high_friction_items.map(id => `<li class="friction-item"><code class="friction-id">${_esc(id.slice(0, 8))}…</code></li>`).join('')}
          </ul>
        </section>
        ` : ''}

      </div>
    `
  }

  // ── Styles ─────────────────────────────────────────────────────────────────

  _styles() {
    return `<style>
      :host {
        display: block;
        color-scheme: light dark;
        font-family: inherit;
      }
      :host([hidden]) { display: none; }

      .graph {
        color: CanvasText;
        font-size: 0.875rem;
      }

      .section {
        margin-block-end: 1.5rem;
      }

      .section-heading {
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        color: GrayText;
        margin: 0 0 0.5rem;
      }

      .muted {
        color: GrayText;
        margin: 0 0 0.5rem;
        font-size: 0.8rem;
        line-height: 1.5;
      }

      /* ── Stage / accuracy bars ── */
      .stage-list, .confusion-list, .friction-list {
        list-style: none;
        padding: 0;
        margin: 0;
        display: flex;
        flex-direction: column;
        gap: 0.35rem;
      }

      .stage-row, .accuracy-row {
        display: grid;
        grid-template-columns: 10rem 1fr 2.5rem;
        align-items: center;
        gap: 0.5rem;
        font-size: 0.8rem;
      }

      .stage-label, .accuracy-label {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .stage-bar-wrap {
        background: color-mix(in srgb, CanvasText 10%, Canvas);
        border-radius: 999px;
        block-size: 6px;
        overflow: hidden;
      }

      .stage-bar {
        block-size: 100%;
        border-radius: 999px;
        background: oklch(0.55 0.18 240);
        min-inline-size: 0;
        transition: inline-size 0.5s ease;
      }

      .stage-bar[data-stage="recognition"]               { background: oklch(0.65 0.12 240); }
      .stage-bar[data-stage="guided_recall"]             { background: oklch(0.62 0.14 200); }
      .stage-bar[data-stage="partial_production"]        { background: oklch(0.60 0.15 160); }
      .stage-bar[data-stage="transformation"]            { background: oklch(0.57 0.16 130); }
      .stage-bar[data-stage="free_production"]           { background: oklch(0.55 0.17 100); }
      .stage-bar[data-stage="contextual_interpretation"] { background: oklch(0.52 0.18 145); }

      .accuracy-bar {
        block-size: 100%;
        border-radius: 999px;
        background: oklch(0.55 0.15 145);
        min-inline-size: 0;
        transition: inline-size 0.5s ease;
      }

      .accuracy-bar[data-pct] { }

      .stage-count, .accuracy-pct {
        text-align: end;
        font-variant-numeric: tabular-nums;
        color: GrayText;
        font-size: 0.75rem;
      }

      /* ── Confusion pairs ── */
      .confusion-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.3rem 0.5rem;
        border-radius: 0.35rem;
        background: color-mix(in srgb, oklch(0.55 0.20 29) 6%, Canvas);
        border: 1px solid color-mix(in srgb, oklch(0.55 0.20 29) 16%, Canvas);
        font-size: 0.8rem;
      }

      .confusion-form { font-weight: 500; }

      .confusion-count {
        color: GrayText;
        font-size: 0.75rem;
        font-variant-numeric: tabular-nums;
      }

      /* ── Friction list ── */
      .friction-item {
        font-size: 0.8rem;
        color: GrayText;
      }

      .friction-id {
        font-family: monospace;
        font-size: 0.75rem;
        background: color-mix(in srgb, CanvasText 6%, Canvas);
        padding: 0.1em 0.3em;
        border-radius: 0.2rem;
      }

      @media (prefers-reduced-motion: reduce) {
        .stage-bar, .accuracy-bar { transition: none; }
      }

      @media (forced-colors: active) {
        .confusion-row { border: 1px solid ButtonText; }
        .stage-bar, .accuracy-bar { forced-color-adjust: none; background: Highlight; }
      }

      @media (max-width: 30rem) {
        .stage-row, .accuracy-row {
          grid-template-columns: 7rem 1fr 2rem;
        }
      }
    </style>`
  }
}

customElements.define('mnemosyne-weakness-graph', MnemosyneWeaknessGraph)
