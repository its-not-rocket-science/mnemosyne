/**
 * mnemosyne-filter-bar.js — Horizontally-scrollable category filter pill bar.
 *
 * Fixed categories: Vocab · Grammar · Idioms · Literary · Etymology
 * Plus a "Custom ▾" pill that opens a popover for user-defined filter terms.
 * Multiple pills active simultaneously; none active = show all.
 *
 * Dispatches (bubbles + composed):
 *   filter-change — { active: string[], customTerms: string[], types: string[] }
 *     active      — category IDs toggled on
 *     customTerms — user-added annotation type strings
 *     types       — flat union of annotation types covered by active filters
 *                   (empty = no filter active = show all)
 *
 * Public methods:
 *   setAvailable(types: string[])  — dims pills with no matching data in current text
 *   reset()                        — clear all active state and re-dispatch
 */

const CATEGORIES = [
  {
    id:    'vocab',
    label: 'Vocab',
    color: 'oklch(0.55 0.18 240)',
    types: ['vocabulary', 'lexical_item', 'word_form', 'vocab', 'word'],
  },
  {
    id:    'grammar',
    label: 'Grammar',
    color: 'oklch(0.50 0.20 265)',
    types: ['grammar', 'grammatical_pattern', 'morphology', 'grammar_point', 'syntax'],
  },
  {
    id:    'idioms',
    label: 'Idioms',
    color: 'oklch(0.62 0.18 55)',
    types: ['idiom', 'expression', 'phrase', 'collocation', 'proverb'],
  },
  {
    id:    'literary',
    label: 'Literary',
    color: 'oklch(0.50 0.22 305)',
    types: ['literary_device', 'rhetoric', 'figure_of_speech', 'literary', 'poetic'],
  },
  {
    id:    'etymology',
    label: 'Etymology',
    color: 'oklch(0.52 0.15 195)',
    types: ['etymology', 'derivation', 'cognate', 'root'],
  },
]

const CUSTOM_COLOR = 'oklch(0.50 0.12 140)'

class MnemosyneFilterBar extends HTMLElement {
  #shadow
  #active    = new Set()  // active category IDs
  #custom    = []         // user-added annotation type terms
  #available = null       // Set<string> | null — types present in current text
  #popOpen   = false

  constructor() {
    super()
    this.#shadow = this.attachShadow({ mode: 'open' })
  }

  connectedCallback() {
    this.#shadow.innerHTML = this.#html()
    this.#wire()
  }

  disconnectedCallback() {
    document.removeEventListener('pointerdown', this.#handleOutsideClick)
  }

  // ── Public API ────────────────────────────────────────────────────────────────

  setAvailable(types) {
    this.#available = types.length ? new Set(types) : null
    this.#syncEmptyState()
  }

  reset() {
    this.#active.clear()
    this.#custom = []
    this.#syncAllPills()
    this.#renderCustomList()
    this.#dispatch()
  }

  // ── Template ──────────────────────────────────────────────────────────────────

  #html() {
    const pills = CATEGORIES.map(({ id, label, color }) => /* html */`
      <button class="pill" data-id="${id}" type="button"
              aria-pressed="false" style="--_c:${color}">${label}</button>
    `).join('')

    return /* html */`
<style>${this.#css()}</style>

<div class="bar" part="bar">
  <div class="bar__pills" id="pills"
       role="group" aria-label="Annotation filters">
    ${pills}
    <button class="pill pill--custom" id="custom-btn" type="button"
            aria-pressed="false" aria-haspopup="dialog" aria-expanded="false"
            style="--_c:${CUSTOM_COLOR}">
      <span id="custom-label">Custom</span>
      <span class="pill__caret" aria-hidden="true">▾</span>
    </button>
  </div>
</div>

<div class="pop" id="pop" hidden role="dialog"
     aria-label="Custom filters" aria-modal="false">
  <div class="pop__header">
    <span class="pop__title">Custom filters</span>
    <button class="pop__close" id="pop-close" type="button" aria-label="Close">&#x2715;</button>
  </div>
  <p class="pop__hint">Enter an annotation type string to add a custom filter.</p>
  <div class="pop__add">
    <input class="pop__input" id="pop-input" type="text"
           placeholder="e.g. subjunctive" autocomplete="off"
           aria-label="New filter term">
    <button class="pop__add-btn" id="pop-add-btn" type="button">Add</button>
  </div>
  <ul class="pop__list" id="pop-list" role="list"></ul>
</div>`
  }

  // ── Wiring ────────────────────────────────────────────────────────────────────

  #wire() {
    const $ = id => this.#shadow.getElementById(id)

    $('pills').addEventListener('click', e => {
      const btn = e.target.closest('.pill[data-id]')
      if (!btn || btn.hasAttribute('data-empty')) return
      const id = btn.dataset.id
      if (this.#active.has(id)) this.#active.delete(id)
      else this.#active.add(id)
      this.#syncPill(btn)
      this.#dispatch()
    })

    $('custom-btn').addEventListener('click', e => {
      e.stopPropagation()
      this.#togglePop()
    })

    $('pop-close').addEventListener('click', () => this.#closePop())

    const doAdd = () => {
      const input = $('pop-input')
      const term  = input.value.trim().toLowerCase()
      if (!term || this.#custom.includes(term)) { input.select(); return }
      this.#custom.push(term)
      this.#renderCustomList()
      this.#syncCustomBtn()
      this.#dispatch()
      input.value = ''
      input.focus()
    }
    $('pop-add-btn').addEventListener('click', doAdd)
    $('pop-input').addEventListener('keydown', e => {
      if (e.key === 'Enter')  { e.preventDefault(); doAdd() }
      if (e.key === 'Escape') this.#closePop()
    })
  }

  // ── Popover ───────────────────────────────────────────────────────────────────

  #handleOutsideClick = e => {
    if (!e.composedPath().includes(this)) this.#closePop()
  }

  #togglePop() { this.#popOpen ? this.#closePop() : this.#openPop() }

  #openPop() {
    this.#popOpen = true
    const pop = this.#shadow.getElementById('pop')
    const btn = this.#shadow.getElementById('custom-btn')
    pop.hidden = false
    btn.setAttribute('aria-expanded', 'true')
    this.#shadow.getElementById('pop-input').focus()
    document.addEventListener('pointerdown', this.#handleOutsideClick)
  }

  #closePop() {
    if (!this.#popOpen) return
    this.#popOpen = false
    const pop = this.#shadow.getElementById('pop')
    const btn = this.#shadow.getElementById('custom-btn')
    if (pop) pop.hidden = true
    if (btn) btn.setAttribute('aria-expanded', 'false')
    document.removeEventListener('pointerdown', this.#handleOutsideClick)
  }

  // ── Custom list ───────────────────────────────────────────────────────────────

  #renderCustomList() {
    const list = this.#shadow.getElementById('pop-list')
    if (!list) return
    list.replaceChildren()
    for (const term of this.#custom) {
      const li    = document.createElement('li')
      li.className = 'pop__item'

      const label = document.createElement('span')
      label.className   = 'pop__item-label'
      label.textContent = term

      const rm = document.createElement('button')
      rm.type      = 'button'
      rm.className = 'pop__remove'
      rm.setAttribute('aria-label', `Remove ${term}`)
      rm.textContent = '×'
      rm.addEventListener('click', () => {
        this.#custom = this.#custom.filter(t => t !== term)
        this.#renderCustomList()
        this.#syncCustomBtn()
        this.#dispatch()
      })

      li.append(label, rm)
      list.appendChild(li)
    }
  }

  // ── State sync ────────────────────────────────────────────────────────────────

  #syncPill(btn) {
    const active = this.#active.has(btn.dataset.id)
    btn.setAttribute('aria-pressed', String(active))
    btn.classList.toggle('pill--active', active)
  }

  #syncAllPills() {
    this.#shadow.querySelectorAll('.pill[data-id]').forEach(btn => this.#syncPill(btn))
    this.#syncCustomBtn()
  }

  #syncCustomBtn() {
    const btn = this.#shadow.getElementById('custom-btn')
    const lbl = this.#shadow.getElementById('custom-label')
    if (!btn) return
    const active = this.#custom.length > 0
    btn.setAttribute('aria-pressed', String(active))
    btn.classList.toggle('pill--active', active)
    if (lbl) lbl.textContent = active ? `Custom\u2009(${this.#custom.length})` : 'Custom'
  }

  #syncEmptyState() {
    this.#shadow.querySelectorAll('.pill[data-id]').forEach(btn => {
      const cat   = CATEGORIES.find(c => c.id === btn.dataset.id)
      const empty = !!(cat && this.#available && !cat.types.some(t => this.#available.has(t)))
      btn.toggleAttribute('data-empty', empty)
    })
  }

  // ── Dispatch ──────────────────────────────────────────────────────────────────

  #dispatch() {
    const active = [...this.#active]
    const types  = [
      ...new Set([
        ...active.flatMap(id => CATEGORIES.find(c => c.id === id)?.types ?? []),
        ...this.#custom,
      ]),
    ]
    this.dispatchEvent(new CustomEvent('filter-change', {
      bubbles:  true,
      composed: true,
      detail:   { active, customTerms: [...this.#custom], types },
    }))
  }

  // ── Styles ────────────────────────────────────────────────────────────────────

  #css() {
    return /* css */`
:host {
  display: block;
  position: relative;
  --_grad-dir: to right;
}

:host(:dir(rtl)) { --_grad-dir: to left; }

/* ── Bar + scroll ────────────────────────────────────────────────────────── */

.bar {
  position: relative;
  overflow: hidden; /* clips fade ::after */
}

/* Right-edge overflow hint */
.bar::after {
  content: '';
  position: absolute;
  inset-block: 0;
  inset-inline-end: 0;
  inline-size: 2.5rem;
  background: linear-gradient(var(--_grad-dir), transparent, var(--bg, Canvas) 85%);
  pointer-events: none;
  z-index: 1;
}

.bar__pills {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  padding-block: 0.5rem;
  padding-inline-start: 0.75rem;
  padding-inline-end: 3rem; /* room for last pill past fade */
  overflow-x: auto;
  scrollbar-width: none;
  -webkit-overflow-scrolling: touch;
}

.bar__pills::-webkit-scrollbar { display: none; }

/* ── Pills ───────────────────────────────────────────────────────────────── */

.pill {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding-block: 0.25rem;
  padding-inline: 0.72rem;
  border-radius: 999px;
  border: 1.5px solid var(--_c);
  background: transparent;
  color: var(--_c);
  font-size: 0.75rem;
  font-weight: 600;
  font-family: inherit;
  white-space: nowrap;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 140ms, color 140ms, opacity 140ms, transform 80ms;
}

.pill:hover:not([data-empty]) {
  background: color-mix(in srgb, var(--_c) 12%, transparent);
}

.pill:active:not([data-empty]) {
  transform: scale(0.95);
}

.pill:focus-visible {
  outline: 2px solid var(--_c);
  outline-offset: 2px;
}

.pill--active {
  background: var(--_c);
  color: #fff;
}

.pill--active:hover:not([data-empty]) {
  background: color-mix(in srgb, var(--_c) 85%, #000 15%);
}

/* Dims pills whose category has no annotations in the current text */
.pill[data-empty] {
  opacity: 0.32;
  cursor: default;
  pointer-events: none;
}

/* Caret rotates when popover open */
.pill__caret {
  font-size: 0.6rem;
  line-height: 1;
  transition: transform 180ms cubic-bezier(0.4, 0, 0.2, 1);
}

#custom-btn[aria-expanded="true"] .pill__caret {
  transform: rotate(180deg);
}

/* ── Custom filter popover ───────────────────────────────────────────────── */

.pop {
  position: absolute;
  inset-block-start: calc(100% - 0.25rem);
  inset-inline-end: 0;
  z-index: 200;
  min-inline-size: 16rem;
  max-inline-size: min(22rem, calc(100vw - 1.5rem));
  background: var(--bg, Canvas);
  border: 1px solid var(--border, color-mix(in srgb, CanvasText 20%, Canvas));
  border-radius: 0.75rem;
  padding: 0.9rem;
  box-shadow:
    0 8px 28px rgb(0 0 0 / 0.13),
    0 2px 6px rgb(0 0 0 / 0.07);
}

.pop[hidden] { display: none; }

.pop__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-block-end: 0.2rem;
}

.pop__title {
  font-size: 0.78rem;
  font-weight: 700;
}

.pop__close {
  inline-size: 1.6rem;
  block-size: 1.6rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  border-radius: 0.35rem;
  cursor: pointer;
  font-size: 0.82rem;
  color: inherit;
  padding: 0;
  transition: background 100ms;
}

.pop__close:hover {
  background: var(--surface, color-mix(in srgb, CanvasText 8%, Canvas));
}

.pop__hint {
  font-size: 0.72rem;
  color: var(--muted, color-mix(in srgb, CanvasText 55%, Canvas));
  margin-block: 0 0.6rem;
}

.pop__add {
  display: flex;
  gap: 0.4rem;
}

.pop__input {
  flex: 1 1 auto;
  min-inline-size: 0;
  padding-block: 0.3rem;
  padding-inline: 0.55rem;
  border: 1px solid var(--border, color-mix(in srgb, CanvasText 25%, Canvas));
  border-radius: 0.4rem;
  background: var(--bg, Canvas);
  color: inherit;
  font-size: 0.78rem;
  font-family: inherit;
}

.pop__input:focus-visible {
  outline: 2px solid var(--accent, #3557ff);
  outline-offset: 0;
  border-color: transparent;
}

.pop__add-btn {
  padding-block: 0.3rem;
  padding-inline: 0.7rem;
  background: var(--accent, #3557ff);
  color: #fff;
  border: none;
  border-radius: 0.4rem;
  font-size: 0.78rem;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  transition: opacity 120ms;
}

.pop__add-btn:hover { opacity: 0.85; }

.pop__list {
  list-style: none;
  padding: 0;
  margin: 0;
  margin-block-start: 0.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  max-block-size: 9rem;
  overflow-y: auto;
}

.pop__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.4rem;
  padding-block: 0.22rem;
  padding-inline: 0.45rem;
  background: var(--surface, color-mix(in srgb, CanvasText 5%, Canvas));
  border-radius: 0.35rem;
  font-size: 0.77rem;
}

.pop__item-label {
  flex: 1 1 auto;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: ui-monospace, 'Cascadia Code', 'Fira Code', monospace;
}

.pop__remove {
  inline-size: 1.3rem;
  block-size: 1.3rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  border-radius: 0.25rem;
  cursor: pointer;
  font-size: 0.9rem;
  color: var(--muted, color-mix(in srgb, CanvasText 50%, Canvas));
  padding: 0;
  flex-shrink: 0;
  transition: color 100ms, background 100ms;
}

.pop__remove:hover {
  color: CanvasText;
  background: color-mix(in srgb, CanvasText 12%, Canvas);
}

/* ── Reduced motion ──────────────────────────────────────────────────────── */

@media (prefers-reduced-motion: reduce) {
  .pill, .pill__caret, .pop__close, .pop__add-btn, .pop__remove {
    transition: none;
  }
}
`
  }
}

customElements.define('mnemosyne-filter-bar', MnemosyneFilterBar)
