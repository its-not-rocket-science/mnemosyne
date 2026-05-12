import assert from 'node:assert/strict'
import { computeAdaptiveProfile } from '../js/adaptive-policy.js'

const beginner = computeAdaptiveProfile({ level: 'A2', memory: { weak: 6, fading: 2, strong: 1, total: 9 }, reviews: { total: 12, accuracy: 0.55 } })
assert.equal(beginner.annotationDensity, 'guided')

const intermediate = computeAdaptiveProfile({ level: 'B1', memory: { weak: 1, fading: 5, strong: 3, total: 9 }, reviews: { total: 14, accuracy: 0.72 } })
assert.equal(intermediate.exampleDifficulty, 'intermediate')

const advanced = computeAdaptiveProfile({ level: 'C1', memory: { weak: 0, fading: 2, strong: 8, total: 10 }, reviews: { total: 20, accuracy: 0.9 } })
assert.equal(advanced.annotationDensity, 'light')

const noHistory = computeAdaptiveProfile({ level: '', memory: { weak: 0, fading: 0, strong: 0, total: 0 }, reviews: { total: 0, accuracy: 0.5 } })
assert.equal(noHistory.defaulting, true)
assert.ok(noHistory.reasons.includes('no_history_default'))

console.log('adaptive-policy tests passed')
