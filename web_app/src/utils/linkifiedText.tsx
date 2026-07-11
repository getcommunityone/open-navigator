/** Render plain text with http(s) URLs as clickable links. */

// Removed single quote from the exclusion class to support Legistar query parameters
export const URL_RE = /https?:\/\/[^\s<>"]+/g

export function cleanUrl(raw: string): string {
  let url = raw
  while (url.length > 0) {
    const lastChar = url[url.length - 1]

    if (/[!.,;:]/.test(lastChar)) {
      url = url.slice(0, -1)
      continue
    }

    if (lastChar === ')') {
      const openCount = (url.match(/\(/g) || []).length
      const closeCount = (url.match(/\)/g) || []).length
      if (closeCount > openCount) {
        url = url.slice(0, -1)
        continue
      }
    }

    if (lastChar === "'") {
      const quoteCount = (url.match(/'/g) || []).length
      if (quoteCount % 2 !== 0) {
        url = url.slice(0, -1)
        continue
      }
    }

    break
  }
  return url
}

export function parseLinkifiedParts(text: string) {
  const parts: { key: number; type: 'text' | 'url'; value: string }[] = []
  if (!text) return parts

  let last = 0
  let key = 0

  function pushText(val: string) {
    if (!val) return
    const lastPart = parts[parts.length - 1]
    if (lastPart && lastPart.type === 'text') {
      lastPart.value += val
    } else {
      parts.push({ key: key++, type: 'text', value: val })
    }
  }

  for (const match of text.matchAll(URL_RE)) {
    const idx = match.index ?? 0
    if (idx > last) {
      pushText(text.slice(last, idx))
    }
    
    const rawUrl = match[0]
    const cleaned = cleanUrl(rawUrl)
    const trailing = rawUrl.slice(cleaned.length)

    parts.push({ key: key++, type: 'url', value: cleaned })
    if (trailing) {
      pushText(trailing)
    }
    
    last = idx + rawUrl.length
  }
  
  if (last < text.length) {
    pushText(text.slice(last))
  }
  
  return parts
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
  const parts = parseLinkifiedParts(text)
  
  if (parts.length === 0 || parts.every(p => p.type === 'text')) {
    return <span className={className}>{text}</span>
  }

  return (
    <span className={className}>
      {parts.map((part) =>
        part.type === 'url' ? (
          <a
            key={part.key}
            href={part.value}
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
