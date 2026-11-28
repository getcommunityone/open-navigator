import { useState } from 'react'
import { hasQuoteText } from '../../lib/highlight'

/** One verbatim passage from a recorded public meeting. */
export interface Passage {
  quote: string
  /** "Audra T." (#1036): first name + last initial, or first name only; null when no name was heard. */
  speakerName?: string | null
  speakerRole?: string | null
  jurisdictionName: string
  meetingDate?: string | null
  videoUrl?: string | null
  startSeconds?: number | null
  /** The item the words were about (a decision's headline), shown when the quote alone does not say. */
  about?: string | null
}

export interface Sides {
  for: Passage[]
  against: Passage[]
}

const SHOWN = 2

/** The recording at the moment of the quote: a `t=` parameter, or none when the start time is not known. */
export function passageLink(p: Passage): string | null {
  if (!p.videoUrl) return null
  if (p.startSeconds == null || !Number.isFinite(p.startSeconds)) return p.videoUrl
  try {
    const u = new URL(p.videoUrl)
    u.searchParams.set('t', `${Math.max(0, Math.floor(p.startSeconds))}s`)
    return u.toString()
  } catch {
    return p.videoUrl
  }
}

/** One side's quotes: each with who said it, where, when, and a link to the moment in the recording. */
export function SideColumn({ title, items }: { title: string; items: Passage[] }) {
  const [all, setAll] = useState(false)
  const shown = all ? items : items.slice(0, SHOWN)
  return (
    <div className="stance-side">
      <p className="stance-side-title">{title}</p>
      <ul className="stance-side-list">
        {shown.map((p, i) => {
          const href = passageLink(p)
          const who = [p.speakerName, p.speakerRole, p.jurisdictionName, p.meetingDate].filter(Boolean).join(' · ')
          return (
            <li key={`${p.jurisdictionName}-${p.meetingDate ?? ''}-${i}`}>
              {hasQuoteText(p.quote) && <blockquote>“{p.quote}”</blockquote>}
              <p className="stance-side-who">
                {p.about && <span className="stance-side-about">On: {p.about} · </span>}
                {who}
                {href && (
                  <>
                    {' · '}
                    <a href={href} target="_blank" rel="noopener noreferrer">
                      Watch this moment
                    </a>
                  </>
                )}
              </p>
            </li>
          )
        })}
      </ul>
      {items.length > SHOWN && (
        <button type="button" className="folio-link-btn" aria-expanded={all} onClick={() => setAll((a) => !a)}>
          {all ? 'Show fewer' : `Show ${items.length - SHOWN} more`}
        </button>
      )}
    </div>
  )
}

/**
 * What was said for and against, as verbatim quotes from public meetings. Renders nothing unless both sides have at least one
 * real passage: there is no placeholder text.
 */
export default function SidesBlock({ sides }: { sides: Sides | undefined }) {
  if (!sides || sides.for.length === 0 || sides.against.length === 0) return null
  return (
    <div className="stance-sides" data-testid="stance-sides" data-lenis-prevent>
      <SideColumn title="What was said for" items={sides.for} />
      <SideColumn title="What was said against" items={sides.against} />
    </div>
  )
}
