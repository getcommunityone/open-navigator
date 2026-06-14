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
