/**
 * js/i18n.js — backward-compat re-export shim.
 *
 * Session 5 of the frontend refactor split the former 9181-line i18n.js
 * into js/i18n/{core,annotations,lesson,library,review,index}.js (domain
 * bundles, four of them lazy-loaded). This file forwards everything to
 * js/i18n/index.js so the app's 24+ existing `from './i18n.js'` /
 * `from '../i18n.js'` / `from '../../i18n.js'` imports keep working
 * unchanged — new code should import from js/i18n/index.js directly.
 */
export * from './i18n/index.js'
