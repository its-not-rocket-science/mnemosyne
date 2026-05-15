/**
 * mnemosyne-text-panel.js — Annotated literary text reader.
 *
 * Accepts lines with explicit character-offset annotations and renders them
 * with colour-coded inline highlights, icon badges, per-line TTS controls,
 * and a sticky title/scene sub-header.
 *
 * Virtualises the list when line count exceeds VIRT_THRESHOLD.
 *
 * Attributes (reflected, observed):
 *   panel-title   — work title shown in sticky sub-header
 *   panel-scene   — act / scene / chapter label
 *   lang          — BCP-47 tag applied to text (default 'en')
 *   dir           — text direction (default 'ltr')
 *
 * Property (set after connectedCallback):
 *   lines  ←  Array<{
 *     id:          string | number,
 *     text:        string,
 *     annotations: Array<{ start: number, end: number, type: string, id: string | number }>
 *   }>
 *
 * Methods:
 *   setActiveLine(lineId)  — highlight the line (e.g. currently playing)
 *   scrollToLine(lineId)   — scroll line into view
 *
 * Events (bubbles + composed):
 *   annotation-select  — { annotationId, lineId, type }
 *   line-speak         — { lineId, text }
 */

import { t } from '../js/i18n.js'

const VIRT_THRESHOLD = 200

// Matches mnemosyne-filter-bar palette exactly
const TYPE_COLOR = {
  vocab:     'oklch(0.55 0.18 240)',
  grammar:   'oklch(0.50 0.20 265)',
  idiom:     'oklch(0.62 0.18 55)',
  literary:  'oklch(0.50 0.22 305)',
  etymology: 'oklch(0.52 0.15 195)',
}

const TYPE_BADGE = {
  vocab:     '\u{1F4D6}',  // 📖 open book
  etymology: '\u{1F512}',  // 🔒 lock
  literary:  '\u{1F5C2}',  // 🗂 card index dividers
  grammar:   '\u{1F524}',  // 🔤 input latin letters
  idiom:     '\u{1F4AC}',  // 💬 speech bubble
}

const TYPE_LABEL = {
  vocab:     'vocabulary',
  grammar:   'grammar',
  idiom:     'idiom',
  literary:  'literary',
  etymology: 'etymology',
}

// Priority for badge ordering (most informative first)
const BADGE_PRIORITY = ['vocab', 'etymology', 'literary', 'grammar', 'idiom']

const SPEAKER_SVG = /* html */`
<svg viewBox="0 0 20 20" aria-hidden="true" focusable="false" fill="currentColor">
  <path d="M3 7.5v5h3.5L11 16.5V3.5L6.5 7.5H3z"/>
  <path d="M13.5 7a4.5 4.5 0 0 1 0 6"
        fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
</svg>`

// ── VirtualList ───────────────────────────────────────────────────────────────
//
// Simple window-based virtual scroller for variable-height items.
// Items are position:absolute within a position:relative scroll container.
// A phantom in-flow spacer div sets the total scroll height.

class VirtualList {
  #el       // scroll container — must be position:relative; overflow-y:auto
  #spacer   // in-flow element whose height sets scroll range
  #items  = []
  #heights = []   // per-item height estimates (updated after render)
  #offsets = []   // per-item inset-block-start values
  #pool    = new Map()   // index → rendered element
  #buf     = 10   // extra items rendered above/below viewport
  #estH    = 64   // px — initial height estimate per line

  /** @param {(item, index) => HTMLElement} renderFn */
  renderFn = null

  constructor(el, spacer) {
    this.#el     = el
    this.#spacer = spacer
    el.addEventListener('scroll', () => this.update(), { passive: true })
  }

  load(items) {
    this.#items   = items
    this.#heights = new Array(items.length).fill(this.#estH)
    this.#recomputeFrom(0)
    this.#spacer.style.height = `${this.#total()}px`
    this.#clearPool()
    this.update()
  }

  update() {
    const { start, end } = this.#range()
    for (const [i, el] of this.#pool) {
      if (i < start || i >= end) { el.remove(); this.#pool.delete(i) }
    }
    for (let i = start; i < end; i++) {
      if (this.#pool.has(i)) continue
      const el = this.renderFn(this.#items[i], i)
      el.style.cssText = `position:absolute;inset-block-start:${this.#offsets[i]}px;inset-inline:0`
      this.#el.appendChild(el)
      this.#pool.set(i, el)
      // Refine height estimate after browser paints the item
      requestAnimationFrame(() => this.#measureItem(i, el))
    }
  }

  /** Returns the estimated inset-block-start for item at index. */
  offsetOf(index) { return this.#offsets[index] ?? 0 }

  /** Returns the rendered element for index, or null if not in pool. */
  elementOf(index) { return this.#pool.get(index) ?? null }

  /** Finds the pool element for a line by matching data-line-id. */
  elementByLineId(lineId) {
    const key = String(lineId)
    for (const [, el] of this.#pool) {
      if (el.dataset.lineId === key) return el
    }
    return null
  }

  #measureItem(i, el) {
    const h = el.getBoundingClientRect().height
    if (h > 0 && Math.abs(h - this.#heights[i]) > 2) {
      this.#heights[i] = h
      this.#recomputeFrom(i + 1)
      this.#spacer.style.height = `${this.#total()}px`
      for (const [j, elj] of this.#pool) {
        if (j > i) elj.style.insetBlockStart = `${this.#offsets[j]}px`
      }
    }
  }

  #range() {
    const top    = this.#el.scrollTop
    const bottom = top + this.#el.clientHeight
    // Binary search for first visible item
    let lo = 0, hi = this.#offsets.length - 1
    while (lo < hi) {
      const mid = (lo + hi) >>> 1
      this.#offsets[mid] + this.#heights[mid] < top ? (lo = mid + 1) : (hi = mid)
    }
    const start = Math.max(0, lo - this.#buf)
    let end = lo
    while (end < this.#items.length && this.#offsets[end] < bottom) end++
    return { start, end: Math.min(this.#items.length, end + this.#buf) }
  }

  #recomputeFrom(startIdx) {
    for (let j = startIdx; j < this.#heights.length; j++) {
      this.#offsets[j] = j === 0 ? 0 : this.#offsets[j - 1] + this.#heights[j - 1]
    }
  }

  #total() {
    const n = this.#items.length
    return n ? this.#offsets[n - 1] + this.#heights[n - 1] : 0
  }

  #clearPool() {
    for (const [, el] of this.#pool) el.remove()
    this.#pool.clear()
  }
}

// ── Component ─────────────────────────────────────────────────────────────────

class MnemosyneTextPanel extends HTMLElement {
  #shadow
  #lines    = []
  #virt     = null    // VirtualList instance when > VIRT_THRESHOLD lines
  #activeId = null    // currently highlighted line ID

  static get observedAttributes() {
    return ['panel-title', 'panel-scene', 'lang', 'dir']
  }

  constructor() {
    super()
    this.#shadow = this.attachShadow({ mode: 'open' })
  }

  connectedCallback() {
    this.#shadow.innerHTML = this.#html()
    this.#render()
  }

  attributeChangedCallback(name, oldVal, newVal) {
    if (oldVal === newVal || !this.#shadow.firstChild) return
    const shadow = this.#shadow
    if (name === 'panel-title') {
      const el = shadow.getElementById('panel-title')
      if (el) el.textContent = newVal ?? ''
      this.#updateHeaderVisibility()
    } else if (name === 'panel-scene') {
      const el = shadow.getElementById('panel-scene')
      if (el) el.textContent = newVal ?? ''
      this.#updateHeaderVisibility()
    } else if (name === 'lang' || name === 'dir') {
      shadow.querySelectorAll('.line__text').forEach(p => {
        p.setAttribute(name, newVal ?? '')
      })
    }
  }

  // ── Public property ───────────────────────────────────────────────────────────

  set lines(data) {
    this.#lines = Array.isArray(data) ? data : []
    if (this.isConnected) this.#render()
  }

  get lines() { return this.#lines }

  // ── Public methods ────────────────────────────────────────────────────────────

  setActiveLine(lineId) {
    this.#shadow.querySelector('.line--active')?.classList.remove('line--active')
    this.#activeId = lineId ?? null
    if (lineId == null) return
    const el = this.#findLineEl(lineId)
    el?.classList.add('line--active')
  }

  scrollToLine(lineId) {
    const el = this.#findLineEl(lineId)
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
      return
    }
    // Virtual scroll: jump to estimated position before the item is rendered
    if (this.#virt) {
      const idx = this.#lines.findIndex(l => String(l.id) === String(lineId))
      if (idx >= 0) {
        const body = this.#shadow.getElementById('body')
        body.scrollTop = this.#virt.offsetOf(idx)
      }
    }
  }

  // ── Render orchestration ──────────────────────────────────────────────────────

  #render() {
    const body = this.#shadow.getElementById('body')
    if (!body) return

    this.#updateHeaderVisibility()
    body.replaceChildren()
    body.classList.remove('panel__body--virtual')
    this.#virt = null

    if (!this.#lines.length) {
      const empty = document.createElement('p')
      empty.className = 'panel__empty'
      empty.textContent = t('text_panel_empty')
      body.appendChild(empty)
      return
    }

    if (this.#lines.length > VIRT_THRESHOLD) {
      this.#setupVirtual(body)
    } else {
      this.#renderAll(body)
    }
  }

  #renderAll(body) {
    const lang = this.#lang()
    const dir  = this.#dir()
    const frag = document.createDocumentFragment()
    for (const line of this.#lines) frag.appendChild(this.#buildLine(line, lang, dir))
    body.appendChild(frag)
  }

  #setupVirtual(body) {
    body.classList.add('panel__body--virtual')

    // In-flow spacer establishes scroll height; items sit atop it.
    const spacer = document.createElement('div')
    spacer.className = 'virt-spacer'
    body.appendChild(spacer)

    const vl = new VirtualList(body, spacer)
    const lang = this.#lang()
    const dir  = this.#dir()
    vl.renderFn = (line) => this.#buildLine(line, lang, dir)
    vl.load(this.#lines)
    this.#virt = vl
  }

  // ── Line builder ──────────────────────────────────────────────────────────────

  #buildLine(line, lang, dir) {
    const div = document.createElement('div')
    div.className = 'line'
    if (String(line.id) === String(this.#activeId)) div.classList.add('line--active')
    div.dataset.lineId = String(line.id)

    // Speaker button
    const btn = document.createElement('button')
    btn.type      = 'button'
    btn.className = 'line__speak'
    btn.setAttribute('aria-label', t('text_panel_play_line'))
    btn.innerHTML = SPEAKER_SVG
    btn.addEventListener('click', e => {
      e.stopPropagation()
      this.dispatchEvent(new CustomEvent('line-speak', {
        bubbles: true, composed: true,
        detail:  { lineId: line.id, text: line.text },
      }))
    })

    div.appendChild(btn)
    div.appendChild(this.#buildAnnotatedP(line, lang, dir))
    return div
  }

  #buildAnnotatedP(line, lang, dir) {
    const { text, annotations = [] } = line
    const p = document.createElement('p')
    p.className = 'line__text'
    p.setAttribute('lang', lang)
    p.setAttribute('dir',  dir)

    if (!annotations.length) {
      p.textContent = text
      return p
    }

    // Validate, then sort by start ASC, length DESC (greedy longest-first)
    const valid = annotations
      .filter(a =>
        Number.isInteger(a.start) && Number.isInteger(a.end) &&
        a.start >= 0 && a.end <= text.length && a.start < a.end
      )
      .sort((a, b) => a.start - b.start || (b.end - b.start) - (a.end - a.start))

    // Greedy non-overlapping selection
    const selected = []
    let lastEnd = 0
    for (const ann of valid) {
      if (ann.start < lastEnd) continue
      // Collect overlapping annotations that didn't get selected — they become badge hints
      const overlaps = valid.filter(a =>
        a !== ann && a.start < ann.end && a.end > ann.start
      )
      selected.push({ ann, overlapTypes: overlaps.map(a => a.type) })
      lastEnd = ann.end
    }

    // Build text + annotated spans
    let cursor = 0
    for (const { ann, overlapTypes } of selected) {
      if (cursor < ann.start) {
        p.appendChild(document.createTextNode(text.slice(cursor, ann.start)))
      }
      p.appendChild(this.#buildAnnSpan(ann, text.slice(ann.start, ann.end), line.id, overlapTypes))
      cursor = ann.end
    }
    if (cursor < text.length) {
      p.appendChild(document.createTextNode(text.slice(cursor)))
    }

    return p
  }

  #buildAnnSpan(ann, phrase, lineId, overlapTypes) {
    const span = document.createElement('span')
    span.className = 'ann'
    span.dataset.annId = String(ann.id)
    span.dataset.type  = ann.type
    const typeLabel = TYPE_LABEL[ann.type] ?? ann.type
    span.setAttribute('role', 'button')
    span.setAttribute('tabindex', '0')
    span.setAttribute('aria-label', `${phrase} — ${typeLabel} annotation`)
    span.style.setProperty('--_c', TYPE_COLOR[ann.type] ?? TYPE_COLOR.vocab)

    span.appendChild(document.createTextNode(phrase))

    // Badges: collect unique types in priority order, max 3
    const allTypes = [ann.type, ...overlapTypes]
    const badgeTypes = BADGE_PRIORITY
      .filter(t => allTypes.includes(t) && TYPE_BADGE[t])
      .slice(0, 3)

    if (badgeTypes.length) {
      const badges = document.createElement('span')
      badges.className = 'ann__badges'
      badges.setAttribute('aria-hidden', 'true')
      badges.setAttribute('title', badgeTypes.join(' · '))
      badges.textContent = badgeTypes.map(t => TYPE_BADGE[t]).join('')
      span.appendChild(badges)
    }

    span.addEventListener('click', () => {
      this.dispatchEvent(new CustomEvent('annotation-select', {
        bubbles: true, composed: true,
        detail:  { annotationId: ann.id, lineId, type: ann.type },
      }))
    })
    span.addEventListener('keydown', e => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); span.click() }
    })

    return span
  }

  // ── Helpers ───────────────────────────────────────────────────────────────────

  #lang() { return this.getAttribute('lang') || 'en' }
  #dir()  { return this.getAttribute('dir')  || 'ltr' }

  #findLineEl(lineId) {
    const key = CSS.escape(String(lineId))
    return this.#shadow.querySelector(`.line[data-line-id="${key}"]`)
  }

  #updateHeaderVisibility() {
    const header = this.#shadow.getElementById('header')
    if (!header) return
    const hasTitle = !!(this.getAttribute('panel-title') || this.getAttribute('panel-scene'))
    header.hidden = !hasTitle
  }

  // ── Template ──────────────────────────────────────────────────────────────────

  #html() {
    const title = this.getAttribute('panel-title') ?? ''
    const scene = this.getAttribute('panel-scene') ?? ''
    const hasHeader = !!(title || scene)
    return /* html */`
<style>${this.#css()}</style>

<div class="panel" part="panel">
  <div class="panel__header" id="header" part="header"${hasHeader ? '' : ' hidden'}>
    <span class="panel__title" id="panel-title">${title}</span>
    <span class="panel__scene" id="panel-scene">${scene}</span>
  </div>
  <div class="panel__body" id="body" part="body"></div>
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

.panel {
  display: flex;
  flex-direction: column;
  block-size: 100%;
  overflow: hidden;
}

/* ── Sticky sub-header ───────────────────────────────────────────────────── */

.panel__header {
  flex-shrink: 0;
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 0.1rem 0.7rem;
  padding-block: 0.45rem;
  padding-inline: 0.9rem;
  border-block-end: 1px solid var(--border, color-mix(in srgb, CanvasText 15%, Canvas));
  background: var(--bg, Canvas);
}

.panel__header[hidden] { display: none; }

.panel__title {
  font-size: 0.88rem;
  font-weight: 700;
  font-style: italic;
}

.panel__scene {
  font-size: 0.76rem;
  color: var(--muted, color-mix(in srgb, CanvasText 55%, Canvas));
  font-variant-numeric: oldstyle-nums;
}

/* ── Body (scroll container) ─────────────────────────────────────────────── */

.panel__body {
  flex: 1 1 auto;
  overflow-y: auto;
  overscroll-behavior: contain;
}

/* Virtual mode: becomes a positioned ancestor for absolutely-placed items */
.panel__body--virtual {
  position: relative;
}

.panel__empty {
  padding: 1.5rem 1rem;
  color: var(--muted, color-mix(in srgb, CanvasText 55%, Canvas));
  font-size: 0.85rem;
}

/* In-flow spacer: establishes virtual scroll height without visual presence */
.virt-spacer {
  inline-size: 100%;
  pointer-events: none;
  visibility: hidden;
  user-select: none;
  /* height set by JS */
}

/* ── Lines ───────────────────────────────────────────────────────────────── */

.line {
  display: flex;
  align-items: flex-start;
  gap: 0.55rem;
  padding-block: 0.45rem;
  padding-inline: 0.9rem;
  border-block-end: 1px solid
    var(--border-faint, color-mix(in srgb, CanvasText 7%, Canvas));
  /* content-visibility skips expensive off-screen rendering in non-virtual mode */
  content-visibility: auto;
  contain-intrinsic-block-size: auto 2.75rem;
  transition: background 160ms;
}

/* Virtual-mode items are absolutely placed — content-visibility conflicts */
.panel__body--virtual .line {
  content-visibility: visible;
  contain: none;
  border-block-end: 1px solid
    var(--border-faint, color-mix(in srgb, CanvasText 7%, Canvas));
}

.line:last-child { border-block-end: none; }

.line--active {
  background: var(--surface, color-mix(in srgb, CanvasText 5%, Canvas));
}

/* ── Speaker button ──────────────────────────────────────────────────────── */

.line__speak {
  flex-shrink: 0;
  inline-size: 2.75rem;
  block-size: 2.75rem;
  margin-block-start: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  border-radius: 0.3rem;
  color: var(--muted, color-mix(in srgb, CanvasText 40%, Canvas));
  cursor: pointer;
  padding: 0;
  transition: color 120ms, background 120ms;
}

.line__speak svg {
  inline-size: 0.85rem;
  block-size: 0.85rem;
}

.line__speak:hover {
  color: var(--text, CanvasText);
  background: var(--surface, color-mix(in srgb, CanvasText 9%, Canvas));
}

.line__speak:focus-visible {
  outline: 2px solid var(--accent, #3557ff);
  outline-offset: 2px;
}

/* ── Line text ───────────────────────────────────────────────────────────── */

.line__text {
  flex: 1 1 auto;
  margin: 0;
  line-height: 1.8;
  font-size: 0.96rem;
  word-break: break-word;
  overflow-wrap: break-word;
  hanging-punctuation: first last;
}

/* ── Annotated span ──────────────────────────────────────────────────────── */

.ann {
  cursor: pointer;
  border-radius: 2px 2px 0 0;
  background: color-mix(in srgb, var(--_c) 13%, transparent);
  /* box-shadow underline doesn't affect line-height or text flow */
  box-shadow: 0 2px 0 0 var(--_c);
  padding-block: 0.06em;
  padding-inline: 0.06em;
  transition: background 130ms;
}

.ann:hover {
  background: color-mix(in srgb, var(--_c) 27%, transparent);
}

.ann:focus-visible {
  outline: 2px solid var(--_c);
  outline-offset: 2px;
  border-radius: 3px;
  box-shadow: none;
}

/* ── Badge strip ─────────────────────────────────────────────────────────── */

.ann__badges {
  display: inline;
  margin-inline-start: 0.06em;
  font-size: 0.58em;
  line-height: 1;
  vertical-align: super;
  letter-spacing: -0.12em;
  pointer-events: none;
  user-select: none;
}

/* ── Reduced motion ──────────────────────────────────────────────────────── */

@media (prefers-reduced-motion: reduce) {
  .line, .line__speak, .ann { transition: none; }
}
`
  }
}

customElements.define('mnemosyne-text-panel', MnemosyneTextPanel)
