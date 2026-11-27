import { Link } from 'react-router-dom'

interface Props {
  /** The visible words: "Next", or "Next story: Pickleball" on the last screen. */
  label: string
  /** The accessible name and tooltip when it says more than the label ("Next: Who spoke up", "Start the data center story"). */
  ariaLabel?: string
  /** A move inside the story (start, next screen). */
  onClick?: () => void
  /** A link out of the story (the next story, keeping the place). Wins over `onClick`. */
  href?: string
  /** The last screen (#1234): a quiet outlined "Done" in the same place, the story ends there. */
  quiet?: boolean
}

/**
 * The story's one way forward (#1234, owner 2026-11-27: "a right Next green button at bottom right always visible. The two
 * buttons is confusing."): a green pill fixed at the bottom right of the window on every screen, desktop and phone, inside
 * the safe-area insets and at least 44px tall. On the cover it starts the story, on a screen it goes to the next screen; on
 * the last screen it is a quiet "Done" that closes the story (the home page is where readers pick the next one). The page leaves room under its last content for it (stance.css), so it never
 * covers anything. Shared by the Data Center Story and the topic stories.
 */
export default function StoryNextButton({ label, ariaLabel, onClick, href, quiet = false }: Props) {
  const body = (
    <>
      {label}
      {!quiet && <span aria-hidden="true">→</span>}
    </>
  )
  const common = {
    className: `folio-btn story-next-fixed${quiet ? ' is-quiet' : ''}`,
    'aria-label': ariaLabel ?? label,
    title: ariaLabel ?? label,
    'data-testid': 'story-next',
  }
  return href ? (
    <Link to={href} {...common}>
      {body}
    </Link>
  ) : (
    <button type="button" onClick={onClick} {...common}>
      {body}
    </button>
  )
}
