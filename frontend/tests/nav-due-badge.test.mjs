/**
 * nav-due-badge.test.mjs — structural tests for the nav due-review badge.
 *
 * Run with: node frontend/tests/nav-due-badge.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT      = path.resolve(__dirname, '..')

const html          = readFileSync(path.join(ROOT, 'index.html'), 'utf8')
const reviewSession = readFileSync(path.join(ROOT, 'js', 'review-session.js'), 'utf8')
const css           = readFileSync(path.join(ROOT, 'css', 'components.css'), 'utf8')

// ── HTML: badge in top nav ────────────────────────────────────────────────────

assert.ok(html.includes('id="nav-due-badge"'), 'index.html must include #nav-due-badge')
assert.ok(
  html.includes('class="nav-due-badge"'),
  '#nav-due-badge must carry .nav-due-badge class'
)

// Must appear inside mnemosyne-top-nav (slotted into nav__end)
const navStart = html.indexOf('<mnemosyne-top-nav')
const navEnd   = html.indexOf('</mnemosyne-top-nav>', navStart)
const navBlock = html.slice(navStart, navEnd)
assert.ok(navBlock.includes('id="nav-due-badge"'), '#nav-due-badge must be inside mnemosyne-top-nav')

assert.ok(html.includes('aria-live="polite"') && navBlock.includes('aria-live="polite"'),
  '#nav-due-badge must have aria-live="polite"')
console.log('✓ HTML: #nav-due-badge slotted inside mnemosyne-top-nav with aria-live')

// ── review-session.js: populates nav badge ────────────────────────────────────

assert.ok(
  reviewSession.includes("getElementById('nav-due-badge')"),
  'review-session.js must fetch #nav-due-badge'
)
assert.ok(
  reviewSession.includes('navBadge'),
  'review-session.js must declare navBadge variable'
)
console.log('✓ review-session.js: nav-due-badge acquired')

// Both badges updated together
const refreshBadgeIdx  = reviewSession.indexOf('async function refreshBadge(')
const refreshBadgeBody = reviewSession.slice(refreshBadgeIdx, refreshBadgeIdx + 1200)
assert.ok(
  refreshBadgeBody.includes('navBadge'),
  'refreshBadge must update navBadge'
)
assert.ok(
  refreshBadgeBody.includes('badge') && refreshBadgeBody.includes('navBadge'),
  'refreshBadge must update both review-bar badge and nav badge'
)
console.log('✓ review-session.js: refreshBadge updates both badges')

// ── window focus refresh ──────────────────────────────────────────────────────

assert.ok(
  reviewSession.includes("window.addEventListener('focus'"),
  "review-session.js must refresh on window 'focus' event"
)
assert.ok(
  reviewSession.includes("refreshBadge") &&
  reviewSession.slice(
    reviewSession.indexOf("window.addEventListener('focus'"),
    reviewSession.indexOf("window.addEventListener('focus'") + 80
  ).includes('refreshBadge'),
  'window focus handler must call refreshBadge'
)
console.log('✓ review-session.js: refreshes on window focus')

// ── CSS ───────────────────────────────────────────────────────────────────────

assert.ok(css.includes('.nav-due-badge'),          'CSS must define .nav-due-badge')
assert.ok(css.includes('.nav-due-badge[hidden]'),  'CSS must hide .nav-due-badge[hidden]')
assert.ok(css.includes('forced-colors'),           'CSS must include forced-colors support for nav badge')
console.log('✓ CSS: .nav-due-badge defined with forced-colors support')

console.log('\nAll nav-due-badge tests passed.')
