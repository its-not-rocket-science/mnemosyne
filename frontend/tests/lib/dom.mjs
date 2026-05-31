/**
 * Shared DOM parsing utilities for frontend tests.
 * Uses linkedom — already in devDependencies.
 */
import { parseHTML } from 'linkedom'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
export const ROOT = path.resolve(__dirname, '..', '..')

/** Parse index.html and return a linkedom document. */
export function loadDocument() {
  const html = readFileSync(path.join(ROOT, 'index.html'), 'utf8')
  return parseHTML(html).document
}

/** Read any file relative to the frontend root. */
export function readSource(relPath) {
  return readFileSync(path.join(ROOT, relPath), 'utf8')
}
