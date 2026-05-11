const MIME_TYPES = {
  txt: ['text/plain'],
  markdown: ['text/markdown', 'text/x-markdown'],
  html: ['text/html', 'application/xhtml+xml'],
  xml: ['text/xml', 'application/xml'],
  rtf: ['application/rtf', 'text/rtf'],
  pdf: ['application/pdf'],
  docx: ['application/vnd.openxmlformats-officedocument.wordprocessingml.document'],
}

const EXTENSION_MAP = {
  txt: 'txt', md: 'markdown', markdown: 'markdown',
  html: 'html', htm: 'html', xhtml: 'html',
  xml: 'xml', svg: 'xml',
  rtf: 'rtf', pdf: 'pdf', docx: 'docx',
}

export const ACCEPT_ATTRIBUTE = '.txt,.md,.markdown,.pdf,.docx,.rtf,.html,.htm,.xhtml,.xml,.svg,text/plain,text/markdown,text/html,application/xhtml+xml,text/xml,application/xml,application/rtf,text/rtf,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document'

export function detectFormat(file) {
  const ext = (file.name.split('.').pop() || '').toLowerCase()
  const byExt = EXTENSION_MAP[ext]
  if (byExt) return byExt
  for (const [format, mimes] of Object.entries(MIME_TYPES)) {
    if (mimes.includes(file.type)) return format
  }
  return null
}

function normalizeParagraphs(text) {
  return text.replace(/\r\n?/g, '\n').replace(/\n{3,}/g, '\n\n').trim()
}

function stripMarkup(text) {
  const doc = new DOMParser().parseFromString(text, 'text/html')
  return normalizeParagraphs(doc.body?.textContent || '')
}

function stripRtf(rtf) {
  const plain = rtf
    .replace(/\\par[d]?\s?/g, '\n\n')
    .replace(/\\'[0-9a-fA-F]{2}/g, '')
    .replace(/\\[a-z]+-?\d*\s?/g, '')
    .replace(/[{}]/g, '')
  return normalizeParagraphs(plain)
}

async function extractPdfText(file) {
  const text = await file.text()
  if (/\/Encrypt\b/.test(text)) throw new Error('encrypted_pdf')
  const parts = [...text.matchAll(/\(([^\)]{1,500})\)\s*Tj/g)].map(m => m[1])
  return normalizeParagraphs(parts.join('\n'))
}

async function unzipFirstDocXml(buffer) {
  const bytes = new Uint8Array(buffer)
  let offset = 0
  while (offset + 30 < bytes.length) {
    const sig = bytes[offset] | (bytes[offset + 1] << 8) | (bytes[offset + 2] << 16) | (bytes[offset + 3] << 24)
    if (sig !== 0x04034b50) break
    const method = bytes[offset + 8] | (bytes[offset + 9] << 8)
    const compSize = bytes[offset + 18] | (bytes[offset + 19] << 8) | (bytes[offset + 20] << 16) | (bytes[offset + 21] << 24)
    const nameLen = bytes[offset + 26] | (bytes[offset + 27] << 8)
    const extraLen = bytes[offset + 28] | (bytes[offset + 29] << 8)
    const nameStart = offset + 30
    const name = new TextDecoder().decode(bytes.slice(nameStart, nameStart + nameLen))
    const dataStart = nameStart + nameLen + extraLen
    const data = bytes.slice(dataStart, dataStart + compSize)
    if (name === 'word/document.xml') {
      if (method === 0) return new TextDecoder().decode(data)
      if (method !== 8) throw new Error('corrupt_file')
      const ds = new DecompressionStream('deflate-raw')
      const stream = new Blob([data]).stream().pipeThrough(ds)
      const inflated = await new Response(stream).arrayBuffer()
      return new TextDecoder().decode(inflated)
    }
    offset = dataStart + compSize
  }
  throw new Error('corrupt_file')
}

async function extractDocxText(file) {
  const xml = await unzipFirstDocXml(await file.arrayBuffer())
  const text = xml.replace(/<w:p[^>]*>/g, '\n\n').replace(/<[^>]+>/g, '')
  return normalizeParagraphs(text)
}

export async function extractTextFromFile(file) {
  const format = detectFormat(file)
  if (!format) throw new Error('unsupported_file_type')
  let text = ''
  if (format === 'txt' || format === 'markdown') text = normalizeParagraphs(await file.text())
  else if (format === 'html' || format === 'xml') text = stripMarkup(await file.text())
  else if (format === 'rtf') text = stripRtf(await file.text())
  else if (format === 'pdf') text = await extractPdfText(file)
  else if (format === 'docx') text = await extractDocxText(file)
  if (!text) throw new Error('no_extractable_text')
  return text
}
