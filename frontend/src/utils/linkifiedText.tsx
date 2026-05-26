/** Render plain text with http(s) URLs as clickable links. */

const URL_RE = /https?:\/\/[^\s<>"']+/g

function cleanUrl(raw: string): string {
  return raw.replace(/[!.,;:)]+$/g, '')
}

export function LinkifiedText({
  text,
  className,
  linkClassName = 'text-teal-700 underline decoration-teal-400/60 hover:text-teal-900 break-all',
}: {
  text: string
  className?: string
  linkClassName?: string
}) {
  if (!text) return null

  const parts: { key: number; type: 'text' | 'url'; value: string }[] = []
  let last = 0
  let key = 0
  for (const match of text.matchAll(URL_RE)) {
    const idx = match.index ?? 0
    if (idx > last) {
      parts.push({ key: key++, type: 'text', value: text.slice(last, idx) })
    }
    parts.push({ key: key++, type: 'url', value: match[0] })
    last = idx + match[0].length
  }
  if (last < text.length) {
    parts.push({ key: key++, type: 'text', value: text.slice(last) })
  }

  if (parts.length === 0) {
    return <span className={className}>{text}</span>
  }

  return (
    <span className={className}>
      {parts.map((part) =>
        part.type === 'url' ? (
          <a
            key={part.key}
            href={cleanUrl(part.value)}
            target="_blank"
            rel="noopener noreferrer"
            className={linkClassName}
          >
            {part.value}
          </a>
        ) : (
          <span key={part.key}>{part.value}</span>
        ),
      )}
    </span>
  )
}
