/**
 * srs-forecast.test.mjs — structural tests for the 7-day review forecast chart.
 *
 * Run with: node frontend/tests/srs-forecast.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT      = path.resolve(__dirname, '..')

const html      = readFileSync(path.join(ROOT, 'index.html'), 'utf8')
const reviewJs  = readFileSync(path.join(ROOT, 'js', 'review-session.js'), 'utf8')
const reviewCss = readFileSync(path.join(ROOT, 'css', 'components.css'), 'utf8')

// ── HTML structure ────────────────────────────────────────────────────────────

assert.ok(html.includes('id="forecast-bar"'),    'index.html must have #forecast-bar')
assert.ok(html.includes('id="forecast-chart"'),  'index.html must have #forecast-chart')
assert.ok(html.includes('forecast-disclosure'),  'index.html must use forecast-disclosure <details>')
assert.ok(html.includes('forecast-disclosure__summary'), 'index.html must have forecast summary element')
console.log('✓ HTML: forecast disclosure structure present')

// #forecast-bar starts hidden
const barStart = html.indexOf('id="forecast-bar"')
const barEl    = html.slice(barStart - 60, html.indexOf('>', barStart) + 1)
assert.ok(barEl.includes('hidden'), '#forecast-bar must start hidden')
console.log('✓ HTML: #forecast-bar starts hidden')

// Uses <details>/<summary> disclosure pattern
assert.ok(html.includes('<details'), 'forecast must use <details> for collapsible section')
assert.ok(html.includes('<summary'), 'forecast must use <summary> for toggle label')
console.log('✓ HTML: <details>/<summary> disclosure pattern used')

// ── review-session.js wiring ──────────────────────────────────────────────────

assert.ok(reviewJs.includes('refreshForecast'),      'review-session.js must define refreshForecast')
assert.ok(reviewJs.includes('_renderForecast'),      'review-session.js must define _renderForecast')
assert.ok(reviewJs.includes('/metrics/forecast'),    'refreshForecast must fetch /metrics/forecast')
assert.ok(reviewJs.includes("'forecast-chart'"),     'review-session.js must reference forecast-chart element')
console.log('✓ review-session.js: refreshForecast and _renderForecast defined')

// _renderForecast uses CSS custom property for bar height
const renderIdx  = reviewJs.indexOf('_renderForecast')
const renderBody = reviewJs.slice(renderIdx, renderIdx + 1200)
assert.ok(renderBody.includes('--_h'),               '_renderForecast must set --_h CSS custom property')
assert.ok(renderBody.includes('forecast-bar__fill'), '_renderForecast must create forecast-bar__fill spans')
assert.ok(renderBody.includes('forecast-bar--today'),'_renderForecast must mark today bar with forecast-bar--today')
console.log('✓ review-session.js: _renderForecast renders bars with --_h and today class')

// Called on init, interval, focus, and language change
assert.ok(reviewJs.includes('refreshForecast()'), 'refreshForecast must be called on init')
assert.ok(
  reviewJs.match(/setInterval[\s\S]{1,100}refreshForecast/),
  'refreshForecast must be in setInterval polling'
)
assert.ok(
  reviewJs.match(/window\.addEventListener\(['"]focus['"][\s\S]{1,200}refreshForecast/),
  'refreshForecast must be called on window focus'
)
assert.ok(
  reviewJs.match(/language[\s\S]{1,200}change[\s\S]{1,200}refreshForecast/),
  'refreshForecast must be called on language change'
)
console.log('✓ review-session.js: refreshForecast wired to init, interval, focus, language change')

// forecastBar revealed after successful fetch
assert.ok(
  reviewJs.includes("forecastBar?.removeAttribute('hidden')"),
  'forecastBar must be shown after successful fetch'
)
console.log('✓ review-session.js: forecast bar revealed after fetch')

// ── CSS ───────────────────────────────────────────────────────────────────────

assert.ok(reviewCss.includes('.forecast-disclosure'),          'review.css must define .forecast-disclosure')
assert.ok(reviewCss.includes('.forecast-disclosure__summary'), 'review.css must define .forecast-disclosure__summary')
assert.ok(reviewCss.includes('.forecast-chart'),               'review.css must define .forecast-chart')
assert.ok(reviewCss.includes('.forecast-bar'),                 'review.css must define .forecast-bar')
assert.ok(reviewCss.includes('.forecast-bar__fill'),           'review.css must define .forecast-bar__fill')
assert.ok(reviewCss.includes('.forecast-bar--today'),          'review.css must define .forecast-bar--today')
assert.ok(reviewCss.includes('.forecast-bar__count'),          'review.css must define .forecast-bar__count')
assert.ok(reviewCss.includes('.forecast-bar__label'),          'review.css must define .forecast-bar__label')
console.log('✓ CSS: all .forecast-* classes defined')

// CSS custom property drives bar height
assert.ok(reviewCss.includes('var(--_h'), 'forecast-bar__fill must use --_h custom property for height')
console.log('✓ CSS: --_h custom property used for bar height')

// Reduced motion and forced colors
assert.ok(
  reviewCss.includes('prefers-reduced-motion') && reviewCss.includes('forecast-bar__fill'),
  'review.css must include reduced-motion support for forecast bars'
)
assert.ok(
  reviewCss.includes('forced-colors') && reviewCss.includes('forecast'),
  'review.css must include forced-colors support for forecast'
)
console.log('✓ CSS: reduced-motion and forced-colors support present')

console.log('\nAll srs-forecast tests passed.')
