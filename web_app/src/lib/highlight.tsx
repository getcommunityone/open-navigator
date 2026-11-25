import type { ReactNode } from 'react'

/**
 * Render a server-side `ts_headline` snippet (whose matched terms are wrapped in
 * literal `<mark>…</mark>` markers) as highlighted React nodes WITHOUT
 * dangerouslySetInnerHTML: split on the markers and wrap the odd segments in
 * <mark>, so every text segment is React-escaped and the raw transcript/decision
 * body can never inject markup.
 *
 * This is the canonical match-evidence renderer shared by every filtered surface
 * (search tiles, decision/cause cards, policy-question meetings). The backend
 * produces the `<mark>` snippet; callers pass it straight through.
 */
export function highlightSnippet(text: string): ReactNode {
  return text.split(/<\/?mark>/).map((seg, i) =>
    i % 2 === 1 ? (
      <mark key={i} className="bg-yellow-200 text-gray-900 rounded px-0.5">
        {seg}
      </mark>
    ) : (
      <span key={i}>{seg}</span>
    ),
  )
}

/** About `max` visible characters of the passage around its first match, cut at word edges, with ellipses where cut. */
export function excerptAroundMark(text: string, max = 190): string {
  const plain = text.replace(/\s+/g, ' ').trim()
  if (plain.replace(/<\/?mark>/g, '').length <= max) return plain
  const at = Math.max(0, plain.indexOf('<mark>'))
  let start = Math.max(0, at - Math.round(max * 0.35))
  let end = Math.min(plain.length, start + max + 26)
  if (start > 0) start = plain.indexOf(' ', start) + 1
  if (end < plain.length) end = Math.max(start, plain.lastIndexOf(' ', end))
  let cut = plain.slice(start, end)
  // never leave half a tag, or a <mark> without its end, at either edge
  cut = cut.replace(/<\/?m?a?r?k?$/, '')
  if (/^[^<]*<\/mark>/.test(cut)) cut = cut.replace('</mark>', '')
  if ((cut.match(/<mark>/g)?.length ?? 0) > (cut.match(/<\/mark>/g)?.length ?? 0)) cut += '</mark>'
  return `${start > 0 ? '… ' : ''}${cut}${end < plain.length ? ' …' : ''}`
}
