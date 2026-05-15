import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'

const source = fs.readFileSync(new URL('../js/recommended-reading.js', import.meta.url), 'utf8')
const canUseMatch = source.match(/function canUseRecommendationItem\(item, language\) \{[\s\S]*?\n\}/)
const normalizeMojibakeMatch = source.match(/function normalizeMojibake\(text\) \{[\s\S]*?\n\}/)
const passageTextMatch = source.match(/function passageText\(item\) \{[\s\S]*?\n\}/)
if (!canUseMatch) throw new Error('canUseRecommendationItem not found')
if (!normalizeMojibakeMatch) throw new Error('normalizeMojibake not found')
if (!passageTextMatch) throw new Error('passageText not found')

const ctx = { result: null }
vm.createContext(ctx)
vm.runInContext(
  `${normalizeMojibakeMatch[0]}\n${passageTextMatch[0]}\n${canUseMatch[0]}\nresult = canUseRecommendationItem`,
  ctx,
)
const canUseRecommendationItem = ctx.result

// ── Explicit language tag takes precedence ─────────────────────────────────────
// Items with a language tag are accepted only when it matches the session language.

// French text with language='fr' → accepted for French session.
assert.equal(canUseRecommendationItem({ text: 'Presque tout a disparu.', language: 'fr' }, 'fr'), true)

// Spanish text with language='es' → rejected for French session.
assert.equal(canUseRecommendationItem({ text: 'Casi todo ha desaparecido.', language: 'es' }, 'fr'), false)

// French text with language='fr' → rejected for English session.
assert.equal(canUseRecommendationItem({ text: 'Presque tout a disparu.', language: 'fr' }, 'en'), false)

// English text with language='en' → accepted for English session.
assert.equal(canUseRecommendationItem({ text: 'The quick brown fox.', language: 'en' }, 'en'), true)

// German text with language='de' → rejected for Spanish session.
assert.equal(canUseRecommendationItem({ text: 'Das ist gut.', language: 'de' }, 'es'), false)

// Russian text with language='ru' → rejected for French session.
assert.equal(canUseRecommendationItem({ text: 'Привет мир.', language: 'ru' }, 'fr'), false)

// ── Existing Spanish heuristic (no language tag) ──────────────────────────────

// French text with no language tag rejected for Spanish (no Spanish markers).
assert.equal(canUseRecommendationItem({ text: 'Presque tout a disparu.', language: 'fr' }, 'es'), false)
assert.equal(canUseRecommendationItem({ text: 'Casi todo ha desaparecido.', language: 'es' }, 'es'), true)
assert.equal(canUseRecommendationItem({ text: 'Casi todo ha desaparecido.' }, 'es'), true)
assert.equal(canUseRecommendationItem({ text: 'Presque tout a disparu.' }, 'es'), false)

// Spanish markers trigger acceptance: accented characters.
assert.equal(canUseRecommendationItem({ text: 'La niña está en casa.' }, 'es'), true)
// Spanish markers: common Spanish function words.
assert.equal(canUseRecommendationItem({ text: 'Hola mundo como estas.' }, 'es'), true)

// ── Mojibake normalisation ─────────────────────────────────────────────────────

// Mojibake Spanish text is normalised and accepted.
assert.equal(canUseRecommendationItem({ text: '‚ÄúHola, mundo‚Äù' }, 'es'), true)

// ── Edge cases ────────────────────────────────────────────────────────────────

// Null/undefined item rejected.
assert.equal(canUseRecommendationItem(null, 'es'), false)
assert.equal(canUseRecommendationItem(undefined, 'es'), false)

// Non-object item rejected.
assert.equal(canUseRecommendationItem('text', 'es'), false)

// Empty text rejected.
assert.equal(canUseRecommendationItem({ text: '' }, 'es'), false)
assert.equal(canUseRecommendationItem({ text: '   ' }, 'es'), false)

// ── passage array items ───────────────────────────────────────────────────────
// Items may carry text via item.passage[].text array instead of item.text.

// Spanish passage array accepted for Spanish session.
assert.equal(
  canUseRecommendationItem(
    { passage: [{ text: 'Hola mundo.' }, { text: 'Buenos días.' }], language: 'es' },
    'es',
  ),
  true,
)

// French passage array rejected for Spanish session (explicit language tag).
assert.equal(
  canUseRecommendationItem(
    { passage: [{ text: 'Bonjour.' }, { text: 'Comment ça va?' }], language: 'fr' },
    'es',
  ),
  false,
)

// ── Next Up language isolation ────────────────────────────────────────────────
// suggestedNextPassage from a different language session must not be surfaced.
// Simulate: recommendation data contains items for multiple languages.

const mixedItems = [
  { text: 'Presque tout a disparu.', language: 'fr' },
  { text: 'Casi todo ha desaparecido.', language: 'es' },
  { text: 'The quick brown fox.', language: 'en' },
  { text: 'Das ist gut.', language: 'de' },
]

const forSpanish = mixedItems.filter(item => canUseRecommendationItem(item, 'es'))
assert.deepEqual(forSpanish.map(i => i.language), ['es'])

const forFrench = mixedItems.filter(item => canUseRecommendationItem(item, 'fr'))
assert.deepEqual(forFrench.map(i => i.language), ['fr'])

const forEnglish = mixedItems.filter(item => canUseRecommendationItem(item, 'en'))
assert.deepEqual(forEnglish.map(i => i.language), ['en'])

// After language switch, previous language's Next Up items must not leak.
const afterSwitchToFr = mixedItems.filter(item => canUseRecommendationItem(item, 'fr'))
assert.ok(!afterSwitchToFr.some(i => i.language === 'es'))
assert.ok(!afterSwitchToFr.some(i => i.language === 'en'))

console.log('recommended-reading language guard tests passed')
