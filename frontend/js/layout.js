/**
 * layout.js — App Shell layout regions and state API.
 *
 * Import these named references instead of calling document.querySelector()
 * in each module.  Layout state (detail open/closed) is centralised here.
 */

let _shell = /** @type {HTMLElement|null} */ (document.querySelector('#app-shell'))

function getShell() {
  if (!_shell || !_shell.isConnected) {
    _shell = /** @type {HTMLElement|null} */ (document.querySelector('#app-shell'))
  }
  return _shell
}

// ── Named regions ─────────────────────────────────────────────────────────────

/** Sticky top navigation bar. */
export const TopNav = /** @type {HTMLElement|null} */ (
  document.querySelector('#app-top-nav')
)

/**
 * Annotation-type filter chip strip.
 * Sticky below TopNav; contains #results-toolbar and #reader-filters.
 */
export const FilterBar = /** @type {HTMLElement|null} */ (
  document.querySelector('#app-filter-bar')
)

/** Scrollable text reading panel (left column on desktop). */
export const TextPanel = /** @type {HTMLElement|null} */ (
  document.querySelector('#main')
)

/**
 * Phrase-detail panel.
 * Desktop: slides in from inline-end via flex-basis transition (300ms).
 * Mobile:  mnemosyne-detail-pane manages its own bottom-sheet at <54rem;
 *          this element is a zero-height passthrough on that breakpoint.
 */
export const DetailPanel = /** @type {HTMLElement|null} */ (
  document.querySelector('#app-detail-panel')
)

/**
 * Now-playing bar region.
 * The mnemosyne-player component inside is position:fixed and manages
 * its own visibility via the [hidden] attribute.
 */
export const NowPlayingBar = /** @type {HTMLElement|null} */ (
  document.querySelector('#app-now-playing')
)

// ── TopNav height tracking ────────────────────────────────────────────────────
// Writes --app-top-nav-h on <html> so FilterBar and DetailPanel can offset
// their sticky inset-block-start precisely, regardless of content changes.

if (TopNav) {
  const _updateNavH = () => {
    document.documentElement.style.setProperty(
      '--app-top-nav-h',
      `${TopNav.offsetHeight}px`
    )
  }
  new ResizeObserver(_updateNavH).observe(TopNav)
  _updateNavH()
}

// ── Layout state API ──────────────────────────────────────────────────────────

/**
 * Open the detail panel.
 *
 * Desktop: adds app-shell--detail-open to the shell root, triggering the
 *          flex-basis 0→45% transition that slides the panel in.
 * Mobile:  class is still set (for any CSS consumers) but visual behaviour
 *          is driven by the component's own data-open attribute + transform.
 */
export function openDetail() {
  getShell()?.classList.add('app-shell--detail-open')
}

/** Close the detail panel (reverses the flex-basis transition on desktop). */
export function closeDetail() {
  getShell()?.classList.remove('app-shell--detail-open')
}

/** @returns {boolean} Whether the detail panel is currently open. */
export function isDetailOpen() {
  return getShell()?.classList.contains('app-shell--detail-open') ?? false
}
