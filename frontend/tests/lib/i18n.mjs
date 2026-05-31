/**
 * i18n key-coverage helpers.
 * The count-based approach (key appears ≥N times in the source) is robust:
 * it doesn't depend on file structure, only on key presence across all blocks.
 */

/** Return how many times a literal key appears in source. */
export function keyCount(source, key) {
  const escaped = key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return (source.match(new RegExp(escaped, 'g')) ?? []).length
}

/**
 * Assert each key appears at least `minLocales` times in source.
 * Throws with a descriptive message listing all failing keys.
 */
export function assertLocaleKeys(source, keys, minLocales = 11) {
  const failing = keys
    .map(k => ({ key: k, n: keyCount(source, k) }))
    .filter(({ n }) => n < minLocales)
  if (failing.length) {
    const detail = failing.map(({ key, n }) => `${key} (${n})`).join(', ')
    throw new Error(`Keys missing from ≥${minLocales} locales: ${detail}`)
  }
}
