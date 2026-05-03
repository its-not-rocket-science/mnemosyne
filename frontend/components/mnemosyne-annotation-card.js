import { t } from '../js/i18n.js'

// Shared palette with mnemosyne-filter-bar and mnemosyne-text-panel
const TYPE_COLOR = {
  vocab:     'var(--accent-vocab)',
  grammar:   'var(--accent-grammar)',
  idiom:     'var(--accent-idiom)',
  literary:  'var(--accent-literary)',
  etymology: 'var(--accent-etymology)',
}

const TYPE_LABEL_KEY = {
  vocab:     'ann_type_vocab',
  grammar:   'ann_type_grammar',
  idiom:     'ann_type_idiom',
  literary:  'ann_type_literary',
  etymology: 'ann_type_etymology',
}

const RATINGS = [
  { id: 'correct',     icon: '\u2713', labelKey: 'ann_rating_correct',     descKey: 'ann_rating_correct_desc',     color: 'oklch(0.52 0.16 145)' },
  { id: 'misspelling', icon: '\u2248', labelKey: 'ann_rating_misspelling',  descKey: 'ann_rating_misspelling_desc', color: 'oklch(0.60 0.16 68)'  },
  { id: 'incorrect',   icon: '\u2717', labelKey: 'ann_rating_incorrect',    descKey: 'ann_rating_incorrect_desc',   color: 'oklch(0.52 0.20 25)'  },
]

class MnemosyneAnnotationCard extends HTMLElement {
  #shadow
  #data     = null
  #loading  = false

  static get observedAttributes() { return ['loading'] }

  constructor() {
    super()
    this.#shadow = this.attachShadow({ mode: 'open' })
  }

  connectedCallback() {
    this.#shadow.innerHTML = this.#html()
    this.#wire()
    this.#syncAll()
    document.addEventListener('mnemosyne:language-changed', this.#onLangChange)
  }

  disconnectedCallback() {
    document.removeEventListener('mnemosyne:language-changed', this.#onLangChange)
  }

  #onLangChange = () => {
    this.#shadow.innerHTML = this.#html()
    this.#wire()
    this.#syncAll()
  }

  attributeChangedCallback(name, oldVal, newVal) {
    if (name !== 'loading' || oldVal === newVal) return
    this.#loading = newVal !== null
    if (this.#shadow.firstChild) this.#syncAll()
  }

  // ── Public API ────────────────────────────────────────────────────────────────

  set data(val) {
    this.#data = val ?? null
    if (this.isConnected) this.#syncAll()
  }

  get data() { return this.#data }

  // ── Wiring ────────────────────────────────────────────────────────────────────

  #wire() {
    const shadow = this.#shadow
    const $ = id => shadow.getElementById(id)

    $('close-btn')?.addEventListener('click', () => {
      this.dispatchEvent(new CustomEvent('ann-close', { bubbles: true, composed: true }))
    })

    // Rating buttons — delegated from container
    $('ratings')?.addEventListener('click', e => {
      const btn = e.target.closest('.rating-btn[data-rating]')
      if (!btn || !this.#data) return
      const rating = btn.dataset.rating
      // Toggle: clicking active rating deselects
      const next = this.#data.rating === rating ? null : rating
      this.#data = { ...this.#data, rating: next }
      this.#syncRatings()
      if (next) {
        this.dispatchEvent(new CustomEvent('ann-rate', {
          bubbles: true, composed: true,
          detail:  { annotationId: this.#data.id, rating: next },
        }))
      }
    })

    $('add-note-btn')?.addEventListener('click', () => {
      if (!this.#data) return
      this.dispatchEvent(new CustomEvent('ann-add-note', {
        bubbles: true, composed: true,
        detail:  { annotationId: this.#data.id },
      }))
    })

    $('more-btn')?.addEventListener('click', () => {
      if (!this.#data) return
      this.dispatchEvent(new CustomEvent('ann-more', {
        bubbles: true, composed: true,
        detail:  { annotationId: this.#data.id },
      }))
    })
  }

  // ── Sync ──────────────────────────────────────────────────────────────────────

  #syncAll() {
    const card = this.#shadow.querySelector('.card')
    if (card) card.dataset.loading = String(this.#loading)

    if (this.#loading || !this.#data) {
      this.#showSkeleton()
      return
    }

    this.#showContent()
  }

  #showSkeleton() {
    const body = this.#shadow.getElementById('body')
    if (!body) return
    body.replaceChildren(this.#buildSkeleton())

    const header = this.#shadow.getElementById('header')
    if (header) {
      header.querySelector('.card__badge')?.removeAttribute('style')
      const phrase = header.querySelector('.card__phrase')
      const sub    = header.querySelector('.card__subtitle')
      if (phrase) phrase.textContent = ''
      if (sub)    sub.textContent    = ''
    }
  }

  #showContent() {
    const d      = this.#data
    const shadow = this.#shadow

    // Header
    const badge  = shadow.querySelector('.card__badge')
    const phrase = shadow.getElementById('phrase')
    const sub    = shadow.getElementById('subtitle')
    const color  = TYPE_COLOR[d.type] ?? TYPE_COLOR.vocab
    if (badge) {
      badge.textContent = t(TYPE_LABEL_KEY[d.type]) || d.type
      badge.style.setProperty('--_c', color)
    }
    if (phrase) phrase.textContent = d.phrase ?? ''
    if (sub)    sub.textContent    = d.subtitle ?? ''
    sub?.toggleAttribute('hidden', !d.subtitle)

    // Body
    const body = shadow.getElementById('body')
    if (body) body.replaceChildren(...this.#buildBodySections())

    this.#syncRatings()
  }

  #syncRatings() {
    this.#shadow.querySelectorAll('.rating-btn').forEach(btn => {
      const active = this.#data?.rating === btn.dataset.rating
      btn.setAttribute('aria-pressed', String(active))
      btn.classList.toggle('rating-btn--active', active)
    })
  }

  // ── Content builders ──────────────────────────────────────────────────────────

  #buildBodySections() {
    const d = this.#data
    const sections = []

    if (d.definition) {
      sections.push(this.#section(t('ann_section_definition'), el => {
        const p = document.createElement('p')
        p.className   = 'section__def'
        p.textContent = d.definition
        el.appendChild(p)
      }))
    }

    if (d.context?.text) {
      sections.push(this.#section(t('ann_section_context'), el => {
        el.appendChild(this.#buildContext(d.context))
      }))
    }

    if (d.examples?.length) {
      sections.push(this.#section(t('ann_section_examples'), el => {
        const list = document.createElement('ol')
        list.className = 'section__examples'
        for (const ex of d.examples) {
          const li = document.createElement('li')
          li.textContent = ex
          list.appendChild(li)
        }
        el.appendChild(list)
      }))
    }

    // Rating section always shown when data is present
    sections.push(this.#buildRatingSection())

    return sections
  }

  #section(title, fillFn) {
    const sec = document.createElement('section')
    sec.className = 'section'
    const h = document.createElement('h3')
    h.className   = 'section__title'
    h.textContent = title
    sec.appendChild(h)
    fillFn(sec)
    return sec
  }

  #buildContext({ text, start, end }) {
    const bq = document.createElement('blockquote')
    bq.className = 'section__context'

    const before = text.slice(0, start)
    const phrase = text.slice(start, end)
    const after  = text.slice(end)
    const color  = TYPE_COLOR[this.#data.type] ?? TYPE_COLOR.vocab

    if (before) bq.appendChild(document.createTextNode(before))

    const mark = document.createElement('mark')
    mark.className = 'context__mark'
    mark.style.setProperty('--_c', color)
    mark.textContent = phrase
    bq.appendChild(mark)

    if (after) bq.appendChild(document.createTextNode(after))

    return bq
  }

  #buildRatingSection() {
    const sec = document.createElement('section')
    sec.className = 'section section--rating'

    const prompt = document.createElement('p')
    prompt.className   = 'section__rating-prompt'
    prompt.textContent = t('ann_rating_prompt')
    sec.appendChild(prompt)

    const group = document.createElement('div')
    group.className = 'rating-group'
    group.id        = 'ratings'
    group.setAttribute('role', 'group')
    group.setAttribute('aria-label', 'Rate your recall')

    for (const r of RATINGS) {
      const btn = document.createElement('button')
      btn.type          = 'button'
      btn.className     = 'rating-btn'
      btn.dataset.rating = r.id
      btn.setAttribute('aria-pressed', String(this.#data?.rating === r.id))
      btn.style.setProperty('--_rc', r.color)
      if (this.#data?.rating === r.id) btn.classList.add('rating-btn--active')

      const icon = document.createElement('span')
      icon.className   = 'rating-btn__icon'
      icon.setAttribute('aria-hidden', 'true')
      icon.textContent = r.icon

      const label = document.createElement('span')
      label.className   = 'rating-btn__label'
      label.textContent = t(r.labelKey)

      const desc = document.createElement('span')
      desc.className   = 'rating-btn__desc'
      desc.textContent = t(r.descKey)

      btn.append(icon, label, desc)
      group.appendChild(btn)
    }

    sec.appendChild(group)
    return sec
  }

  #buildSkeleton() {
    const wrap = document.createElement('div')
    wrap.className = 'skeleton'
    for (const w of ['70%', '100%', '90%', '50%', '100%', '80%']) {
      const line = document.createElement('div')
      line.className = 'skeleton__line'
      line.style.width = w
      wrap.appendChild(line)
    }
    return wrap
  }

  // ── Template ──────────────────────────────────────────────────────────────────

  #html() {
    return /* html */`
<style>${this.#css()}</style>

<div class="card" part="card">

  <!-- Sticky header -->
  <div class="card__header" id="header" part="header">
    <div class="card__header-top">
      <span class="card__badge" style="--_c:${TYPE_COLOR.vocab}">Vocab</span>
      <button class="card__close" id="close-btn" type="button" aria-label="Close">&#x2715;</button>
    </div>
    <h2 class="card__phrase" id="phrase"></h2>
    <p class="card__subtitle" id="subtitle" hidden></p>
  </div>

  <!-- Scrollable body -->
  <div class="card__body" id="body" part="body"></div>

  <!-- Sticky footer -->
  <div class="card__footer" part="footer">
    <button class="card__add-note" id="add-note-btn" type="button">${t('ann_add_note')}</button>
    <button class="card__more"     id="more-btn"     type="button"
            aria-label="More options">&#x22EF;</button>
  </div>

</div>`
  }

  // ── Styles ────────────────────────────────────────────────────────────────────

  #css() {
    return /* css */`
:host {
  display: flex;
  flex-direction: column;
  block-size: 100%;
  overflow: hidden;
  font-family: inherit;
}

/* ── Shell ───────────────────────────────────────────────────────────────── */

.card {
  display: flex;
  flex-direction: column;
  block-size: 100%;
  overflow: hidden;
}

/* ── Sticky header ───────────────────────────────────────────────────────── */

.card__header {
  flex-shrink: 0;
  padding-block: 0.75rem 0.65rem;
  padding-inline: 1rem;
  border-block-end: 1px solid
    var(--border, color-mix(in srgb, CanvasText 15%, Canvas));
  background: var(--bg, Canvas);
}

.card__header-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-block-end: 0.5rem;
}

/* Type badge — filled pill, colour from --_c */
.card__badge {
  display: inline-block;
  padding-block: 0.15rem;
  padding-inline: 0.55rem;
  border-radius: 999px;
  background: var(--_c, #3557ff);
  color: #fff;
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}

.card__close {
  inline-size: 1.7rem;
  block-size: 1.7rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  border-radius: 0.35rem;
  cursor: pointer;
  font-size: 0.82rem;
  color: var(--muted, color-mix(in srgb, CanvasText 50%, Canvas));
  padding: 0;
  margin-inline-start: auto;
  transition: background 100ms, color 100ms;
}

.card__close:hover {
  background: var(--surface, color-mix(in srgb, CanvasText 9%, Canvas));
  color: CanvasText;
}

.card__close:focus-visible {
  outline: 2px solid var(--accent, #3557ff);
  outline-offset: 2px;
}

.card__phrase {
  margin: 0;
  font-size: 1.45rem;
  font-weight: 700;
  font-style: italic;
  line-height: 1.2;
  letter-spacing: -0.02em;
  word-break: break-word;
}

.card__subtitle {
  margin: 0;
  margin-block-start: 0.25rem;
  font-size: 0.78rem;
  color: var(--muted, color-mix(in srgb, CanvasText 55%, Canvas));
  font-style: normal;
}

.card__subtitle[hidden] { display: none; }

/* ── Scrollable body ─────────────────────────────────────────────────────── */

.card__body {
  flex: 1 1 auto;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding-block: 0.25rem 0.5rem;
}

/* ── Sections ────────────────────────────────────────────────────────────── */

.section {
  padding-block: 0.8rem;
  padding-inline: 1rem;
  border-block-end: 1px solid
    var(--border-faint, color-mix(in srgb, CanvasText 7%, Canvas));
}

.section:last-child { border-block-end: none; }

.section__title {
  margin: 0 0 0.4rem;
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  color: var(--muted, color-mix(in srgb, CanvasText 50%, Canvas));
}

.section__def {
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.6;
}

/* In-context blockquote */
.section__context {
  margin: 0;
  padding-inline-start: 0.75rem;
  border-inline-start: 3px solid
    var(--border, color-mix(in srgb, CanvasText 18%, Canvas));
  font-size: 0.88rem;
  line-height: 1.65;
  color: var(--muted, color-mix(in srgb, CanvasText 65%, Canvas));
  font-style: italic;
  word-break: break-word;
}

.context__mark {
  background: color-mix(in srgb, var(--_c) 18%, transparent);
  box-shadow: 0 2px 0 0 var(--_c);
  border-radius: 2px 2px 0 0;
  padding-block: 0.05em;
  color: CanvasText;
  font-style: normal;
  font-weight: 600;
}

/* Examples */
.section__examples {
  margin: 0;
  padding-inline-start: 1.1rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
}

.section__examples li {
  font-size: 0.86rem;
  line-height: 1.55;
}

/* ── Rating section ──────────────────────────────────────────────────────── */

.section--rating {
  padding-block-end: 1rem;
}

.section__rating-prompt {
  margin: 0 0 0.7rem;
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--muted, color-mix(in srgb, CanvasText 60%, Canvas));
}

.rating-group {
  display: flex;
  gap: 0.45rem;
}

.rating-btn {
  flex: 1 1 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.2rem;
  padding-block: 0.55rem 0.6rem;
  padding-inline: 0.3rem;
  border: 1.5px solid var(--_rc);
  border-radius: 0.6rem;
  background: transparent;
  color: var(--_rc);
  cursor: pointer;
  font-family: inherit;
  transition: background 130ms, color 130ms, transform 80ms;
}

.rating-btn:hover {
  background: color-mix(in srgb, var(--_rc) 10%, transparent);
}

.rating-btn:active {
  transform: scale(0.96);
}

.rating-btn:focus-visible {
  outline: 2px solid var(--_rc);
  outline-offset: 2px;
}

.rating-btn--active {
  background: var(--_rc);
  color: #fff;
}

.rating-btn--active:hover {
  background: color-mix(in srgb, var(--_rc) 88%, #000 12%);
}

.rating-btn__icon {
  font-size: 1rem;
  line-height: 1;
  font-weight: 700;
}

.rating-btn__label {
  font-size: 0.72rem;
  font-weight: 700;
}

.rating-btn__desc {
  font-size: 0.62rem;
  line-height: 1.3;
  text-align: center;
  opacity: 0.75;
}

.rating-btn--active .rating-btn__desc {
  opacity: 0.88;
}

/* ── Sticky footer ───────────────────────────────────────────────────────── */

.card__footer {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding-block: 0.65rem;
  padding-inline: 1rem;
  border-block-start: 1px solid
    var(--border, color-mix(in srgb, CanvasText 15%, Canvas));
  background: var(--bg, Canvas);
}

.card__add-note {
  flex: 1 1 auto;
  padding-block: 0.4rem;
  padding-inline: 0.9rem;
  border: 1.5px solid var(--border, color-mix(in srgb, CanvasText 25%, Canvas));
  border-radius: 0.5rem;
  background: transparent;
  color: inherit;
  font-size: 0.8rem;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: background 120ms, border-color 120ms;
}

.card__add-note:hover {
  background: var(--surface, color-mix(in srgb, CanvasText 6%, Canvas));
  border-color: var(--text, CanvasText);
}

.card__add-note:focus-visible {
  outline: 2px solid var(--accent, #3557ff);
  outline-offset: 2px;
}

.card__more {
  flex-shrink: 0;
  inline-size: 2.4rem;
  block-size: 2.4rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: 1.5px solid var(--border, color-mix(in srgb, CanvasText 22%, Canvas));
  border-radius: 0.5rem;
  font-size: 1.1rem;
  line-height: 1;
  letter-spacing: -0.05em;
  cursor: pointer;
  color: inherit;
  padding: 0;
  transition: background 120ms, border-color 120ms;
}

.card__more:hover {
  background: var(--surface, color-mix(in srgb, CanvasText 6%, Canvas));
  border-color: var(--text, CanvasText);
}

.card__more:focus-visible {
  outline: 2px solid var(--accent, #3557ff);
  outline-offset: 2px;
}

/* ── Skeleton loading ────────────────────────────────────────────────────── */

.skeleton {
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.skeleton__line {
  block-size: 0.85rem;
  border-radius: 0.3rem;
  background: var(--surface, color-mix(in srgb, CanvasText 8%, Canvas));
  background-image: linear-gradient(
    90deg,
    transparent 0%,
    color-mix(in srgb, CanvasText 4%, Canvas) 50%,
    transparent 100%
  );
  background-size: 200% 100%;
  animation: skeleton-sweep 1.5s ease-in-out infinite;
}

@keyframes skeleton-sweep {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* ── Loading state — dim header content ──────────────────────────────────── */

.card[data-loading="true"] .card__phrase,
.card[data-loading="true"] .card__subtitle {
  visibility: hidden;
}

/* ── Reduced motion ──────────────────────────────────────────────────────── */

@media (prefers-reduced-motion: reduce) {
  .rating-btn, .card__add-note, .card__more, .card__close { transition: none; }
  .skeleton__line { animation: none; }
}
`
  }
}

customElements.define('mnemosyne-annotation-card', MnemosyneAnnotationCard)
