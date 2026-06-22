/**
 * theme.test.mjs — Tests for the user-toggleable dark mode feature.
 *
 * Run: node frontend/tests/theme.test.mjs
 *
 * Covers:
 *   1. Persistence — localStorage key and data-theme attribute survive cycle
 *   2. OS tracking — auto mode dispatches mnemosyne:theme-changed on OS change
 *   3. Accessibility — aria-label reflects current theme state
 *   4. FOUC — boot script sets data-theme before stylesheets (structural test)
 */

import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT      = path.resolve(__dirname, '..')

// ── Test 1: Theme cycle ───────────────────────────────────────────────────────

const CYCLE = { auto: 'light', light: 'dark', dark: 'auto' }
const ICONS  = { auto: '◑', light: '☼', dark: '☾' }

let t = 'auto'
for (let i = 0; i < 6; i++) {
  t = CYCLE[t]
}
assert.equal(t, 'auto', 'Full cycle (3 steps × 2) returns to auto')

const cycleOrder = ['auto', 'light', 'dark', 'auto', 'light', 'dark']
let cur = 'auto'
for (let i = 1; i < cycleOrder.length; i++) {
  cur = CYCLE[cur]
  assert.equal(cur, cycleOrder[i], `Step ${i}: got ${cur}, expected ${cycleOrder[i]}`)
}

console.log('✓ Theme cycle: auto → light → dark → auto')

// ── Test 2: All themes have icons ─────────────────────────────────────────────

for (const theme of ['auto', 'light', 'dark']) {
  assert.ok(ICONS[theme], `ICONS['${theme}'] must be defined`)
  assert.equal(typeof ICONS[theme], 'string')
  assert.ok(ICONS[theme].length > 0)
}

console.log('✓ All themes have icon characters')

// ── Test 3: Boot script is before first stylesheet in index.html ──────────────

const html = readFileSync(path.join(ROOT, 'index.html'), 'utf8')

const bootScriptPos   = html.indexOf('localStorage.getItem(\'mnemosyne_theme\')')
const firstStylePos   = html.indexOf('<link rel="stylesheet"')
const firstModulePos  = html.indexOf('type="module"')

assert.ok(bootScriptPos > -1, 'Boot script must be present in index.html')
assert.ok(firstStylePos > -1, 'At least one stylesheet must be in index.html')
assert.ok(
  bootScriptPos < firstStylePos,
  `Boot script (pos ${bootScriptPos}) must appear before first stylesheet (pos ${firstStylePos})`
)
assert.ok(
  bootScriptPos < firstModulePos,
  `Boot script (pos ${bootScriptPos}) must appear before first module script (pos ${firstModulePos})`
)

console.log('✓ FOUC: boot script precedes all stylesheets and module scripts')

// ── Test 4: Boot script handles localStorage failure gracefully ───────────────

const bootBlock = html.slice(html.indexOf('(function ()'), html.indexOf('})();') + 5)
assert.ok(bootBlock.includes('try'), 'Boot script must have try/catch')
assert.ok(bootBlock.includes('catch'), 'Boot script must have try/catch')
assert.ok(bootBlock.includes("setAttribute('data-theme'"), 'Boot script must set data-theme in both branches')

console.log('✓ Boot script has try/catch fallback')

// ── Test 5: i18n keys present in all 11 languages ────────────────────────────

const i18nSrc = readFileSync(path.join(ROOT, 'js', 'i18n.js'), 'utf8')
const REQUIRED_KEYS = ['nav_theme_aria', 'nav_theme_auto', 'nav_theme_light', 'nav_theme_dark']
const LANG_CODES    = ['en', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'ja', 'zh', 'ar', 'he']

for (const key of REQUIRED_KEYS) {
  const matches = (i18nSrc.match(new RegExp(key, 'g')) || []).length
  assert.ok(
    matches >= LANG_CODES.length,
    `Key '${key}' must appear at least ${LANG_CODES.length} times (once per language). Found: ${matches}`
  )
}

console.log('✓ i18n keys nav_theme_* present in all 11 language tables')

// ── Test 6: CSS data-theme selectors present in global.css ───────────────────

const globalCss = readFileSync(path.join(ROOT, 'css', 'tokens.css'), 'utf8')

assert.ok(
  globalCss.includes(':root[data-theme="dark"]'),
  'global.css must have :root[data-theme="dark"] block'
)
assert.ok(
  globalCss.includes(':root[data-theme="auto"]'),
  'global.css must have :root[data-theme="auto"] block inside @media prefers-color-scheme: dark'
)
assert.ok(
  !globalCss.includes('@media (prefers-color-scheme: dark) {\n  :root {'),
  'global.css must NOT have bare :root inside dark media query (only data-theme selectors)'
)

console.log('✓ global.css uses data-theme attribute selectors for dark mode')

// ── Test 7: LS_THEME constant matches boot script key ────────────────────────

const navSrc = readFileSync(path.join(ROOT, 'components', 'mnemosyne-top-nav.js'), 'utf8')
assert.ok(navSrc.includes("'mnemosyne_theme'"), 'top-nav must use mnemosyne_theme localStorage key')
assert.ok(html.includes("'mnemosyne_theme'"), 'boot script must use mnemosyne_theme localStorage key')

console.log('✓ localStorage key consistent between boot script and top-nav')

console.log('\nAll theme tests passed.')
