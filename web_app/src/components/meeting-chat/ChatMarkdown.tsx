import { Fragment, type ReactNode } from 'react'
import { Link } from 'react-router-dom'

/**
 * A small, safe markdown renderer for Ask meetings answers (#1011): paragraphs, "- " / "* " / "1. " lists, **bold**,
 * [text](url) links and bare /meetings/<id> paths. React elements only (never innerHTML). A link becomes clickable only
 * when it is a same-site path ("/...") or an http(s) URL; anything else stays text.
 */

const INLINE = /(\*\*[^*]+\*\*)|(\[[^\]]+\]\(([^)\s]+)\))|(\/meetings\/\d+)/g

function safeHref(href: string): string | null {
  if (href.startsWith('/') && !href.startsWith('//')) return href
  if (/^https?:\/\//i.test(href)) return href
  return null
}

function LinkTo({ href, children }: { href: string; children: ReactNode }) {
  const cls = 'font-medium text-primary-700 underline underline-offset-2 hover:text-primary-800'
  return href.startsWith('/') ? (
    <Link to={href} className={cls}>
      {children}
    </Link>
  ) : (
    <a href={href} target="_blank" rel="noopener noreferrer" className={cls}>
      {children}
    </a>
  )
}

export function renderInline(text: string, keyBase = 'i'): ReactNode[] {
  const out: ReactNode[] = []
  let last = 0
  let n = 0
  for (const m of text.matchAll(INLINE)) {
    const at = m.index ?? 0
    if (at > last) out.push(text.slice(last, at))
    const key = `${keyBase}-${n++}`
    if (m[1]) {
      out.push(<strong key={key}>{renderInline(m[1].slice(2, -2), key)}</strong>)
    } else if (m[2]) {
      const label = m[2].slice(1, m[2].indexOf(']('))
      const href = safeHref(m[3]!)
      out.push(href ? <LinkTo key={key} href={href}>{label}</LinkTo> : <Fragment key={key}>{label}</Fragment>)
    } else if (m[4]) {
      out.push(
        <LinkTo key={key} href={m[4]}>
          meeting
        </LinkTo>,
      )
    }
    last = at + m[0].length
  }
  if (last < text.length) out.push(text.slice(last))
  return out
}

type Block = { kind: 'p'; lines: string[] } | { kind: 'ul' | 'ol'; items: string[] }

function blocks(text: string): Block[] {
  const out: Block[] = []
  for (const raw of text.replace(/\r\n/g, '\n').split('\n')) {
    const line = raw.trimEnd()
    const bullet = /^\s*[-*•]\s+(.*)$/.exec(line)
    const num = /^\s*\d+[.)]\s+(.*)$/.exec(line)
    const prev = out[out.length - 1]
    if (bullet || num) {
      const kind = bullet ? 'ul' : 'ol'
      const item = (bullet ?? num)![1]!
      if (prev && prev.kind === kind) prev.items.push(item)
      else out.push({ kind, items: [item] })
    } else if (!line.trim()) {
      out.push({ kind: 'p', lines: [] })
    } else if (prev && prev.kind === 'p' && prev.lines.length) {
      prev.lines.push(line)
    } else {
      out.push({ kind: 'p', lines: [line.replace(/^#{1,6}\s+/, '')] })
    }
  }
  return out.filter((b) => (b.kind === 'p' ? b.lines.length > 0 : b.items.length > 0))
}

export default function ChatMarkdown({ text }: { text: string }) {
  return (
    <div className="space-y-2">
      {blocks(text).map((b, i) => {
        if (b.kind === 'p') return <p key={i}>{renderInline(b.lines.join(' '), `p${i}`)}</p>
        const Tag = b.kind
        return (
          <Tag key={i} className={`${Tag === 'ul' ? 'list-disc' : 'list-decimal'} space-y-1.5 pl-5`}>
            {b.items.map((it, j) => (
              <li key={j}>{renderInline(it, `l${i}-${j}`)}</li>
            ))}
          </Tag>
        )
      })}
    </div>
  )
}
