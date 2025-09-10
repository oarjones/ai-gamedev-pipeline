import DOMPurify from 'dompurify'
import { marked } from 'marked'

marked.setOptions({ mangle: false, headerIds: false, breaks: true })

export function renderMarkdown(md: string): string {
  const raw = marked.parse(md ?? '') as string
  const safe = DOMPurify.sanitize(raw, { USE_PROFILES: { html: true } })
  return safe
}

