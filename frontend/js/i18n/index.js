/**
 * js/i18n/index.js — public i18n API. The ONLY i18n file other modules
 * should import from directly (js/i18n.js is a thin backward-compat shim
 * over this file, kept so the app's 24+ existing "from './i18n.js'"-style
 * imports don't need to change — see js/i18n.js).
 *
 * Re-exports core.js synchronously (initUiLanguage, t, ti, currentUiLang,
 * UI_LANGUAGES, CAPABILITY_LABELS_I18N — all needed before/during initial
 * render) and exposes loadBundle()/bundleReady() for the four lazy domain
 * bundles (annotations, lesson, library, review).
 *
 * ANNOTATION_ARIA_I18N, TYPE_LABELS_LONG_I18N, and RECOMMEND_UI_I18N are
 * re-exported as LIVE mutable object references from core.js (_annotationAria,
 * _typeLabelsLong, _recommendUi) — they start empty and loadBundle() merges
 * each map's real content into them in place once the owning bundle resolves.
 * This deliberately avoids a static "export {...} from './annotations.js'"
 * here, which would defeat lazy-loading entirely by eagerly pulling in the
 * largest bundle (~2500 lines) the moment index.js itself is imported. Since
 * the object identity never changes, existing call sites (e.g.
 * js/modes/lesson.js's TYPE_LABELS_LONG_I18N[lang]?.[key] lookup) need no
 * changes — they just see an empty object until the bundle loads.
 *
 * Part of Session 5 of the frontend refactor (split of the former
 * 9181-line js/i18n.js).
 */

export {
  initUiLanguage, applyUiLanguage, t, ti, currentUiLang, UI_LANGUAGES,
  CAPABILITY_LABELS_I18N,
  _table, _annotationAria as ANNOTATION_ARIA_I18N,
  _typeLabelsLong as TYPE_LABELS_LONG_I18N, _recommendUi as RECOMMEND_UI_I18N,
} from './core.js'

import { _table, _annotationAria, _typeLabelsLong, _recommendUi, UI_LANGUAGES } from './core.js'

const _loaded = new Set()
const _loaders = {
  annotations: () => import('./annotations.js'),
  lesson:      () => import('./lesson.js'),
  library:     () => import('./library.js'),
  review:      () => import('./review.js'),
}

/**
 * Dynamically import the named bundle ('annotations'|'lesson'|'library'|
 * 'review') and merge its strings into the shared, mutable lookup table(s)
 * from core.js. Safe to call more than once for the same bundle —
 * subsequent calls are no-ops once loaded.
 */
export async function loadBundle(name) {
  if (_loaded.has(name)) return
  const loader = _loaders[name]
  if (!loader) throw new Error(`i18n: unknown bundle "${name}"`)
  const mod = await loader()
  const langs = UI_LANGUAGES.map(l => l.code)
  for (const lang of langs) Object.assign(_table[lang], mod.STRINGS[lang])
  if (name === 'annotations') {
    for (const lang of langs) {
      Object.assign(_annotationAria[lang], mod.ANNOTATION_ARIA_I18N[lang])
      Object.assign(_typeLabelsLong[lang], mod.TYPE_LABELS_LONG_I18N[lang])
    }
  }
  if (name === 'library') {
    for (const lang of langs) Object.assign(_recommendUi[lang], mod.RECOMMEND_UI_I18N[lang])
  }
  _loaded.add(name)
}

/** True if loadBundle(name) has already resolved for this bundle. */
export function bundleReady(name) {
  return _loaded.has(name)
}
