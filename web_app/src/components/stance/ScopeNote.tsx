import { useState } from 'react'

interface Props {
  /** One short muted line: "Showing Alabama", then "Why?" for the reason. */
  short: string
  /** The full plain-words reason, behind "Why?". */
  full: string
  level: string
}

/**
 * Why the story shows a wider place than the one asked (#1285): a short line under the headline in the sticky bar, with
 * the full explanation behind a small "Why?" disclosure. It sits in the headline's column, never over it (#1337).
 */
export default function ScopeNote({ short, full, level }: Props) {
  const [open, setOpen] = useState(false)
  return (
    <div className="story-scope-note" role="note" data-testid="story-scope-note" data-scope-level={level}>
      <span className="story-scope-short" data-testid="story-scope-short">
        {short}
      </span>
      <span aria-hidden="true"> · </span>
      <button type="button" className="folio-link-btn story-scope-why" data-testid="story-scope-why" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        Why?
      </button>
      {open && <p className="story-scope-full" data-testid="story-scope-full">{full}</p>}
    </div>
  )
}
