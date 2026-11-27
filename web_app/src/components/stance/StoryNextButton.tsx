import { Link } from 'react-router-dom'
import { dotState } from '../../utils/storyNav'
import { toGoLabel } from '../../utils/floatingNext'

interface Props {
  /** The screen in view (0-based); ignored on the cover. */
  active: number
  count: number
  /** The story's cover is in view: Next starts the story. */
  onCover: boolean
  /** "Start the pickleball story" (the cover Next's accessible name). */
  startLabel: string
  onStart: () => void
  /** The next screen's word, for Next's accessible name; null on the last screen. */
  nextLabel: string | null
  onNext: () => void
  /** The previous screen's word, for the phone Back's accessible name; null on the first screen. */
  prevLabel: string | null
  onPrev: () => void
  /** Where the last screen's quiet Done goes (home, keeping the scope). */
  doneHref: string
  /** Phones: the bar with Back and the progress dots around Next. */
  phone: boolean
}

/**
 * The one way forward in a story (#1224, owner 2026-11-27: "a right Next green button at bottom right always visible. The
 * two buttons is confusing."): a single green Next fixed at the bottom right of every screen. On the cover it starts the
 * story, on a screen it goes to the next one, and on the last screen it is a quiet Done that closes the story (no Next story
 * button: readers pick the next story on home, owner 2026-11-27). It never moves, so
 * the reader always finds it in the same place. On a phone it sits in a bottom bar with Back at the left (from the second
 * screen on) and the progress dots; on a wide screen Back stays inline in each screen and the segments are in the top bar.
 */
export default function StoryNextButton(p: Props) {
  const last = !p.onCover && p.active >= p.count - 1
  const next = last ? (
    <Link to={p.doneHref} className="folio-btn story-next-fixed is-done" data-testid="story-next" aria-label="Done: close the story">
      Done
    </Link>
  ) : (
    <button
      type="button"
      className="folio-btn story-next-fixed"
      data-testid="story-next"
      onClick={p.onCover ? p.onStart : p.onNext}
      aria-label={p.onCover ? p.startLabel : p.nextLabel ? `Next: ${p.nextLabel}` : 'Next'}
    >
      Next <span aria-hidden="true">→</span>
    </button>
  )
  if (!p.phone) return <div className="story-nextdock is-wide">{next}</div>
  const showBack = !p.onCover && p.active > 0 && p.prevLabel != null
  return (
    <div className="story-nextdock is-phone" data-testid="story-nextdock">
      {showBack ? (
        <button type="button" className="folio-btn story-nextdock-back" onClick={p.onPrev} aria-label={`Back: ${p.prevLabel}`} data-testid="story-back">
          <span aria-hidden="true">←</span> Back
        </button>
      ) : null}
      <span className="story-nextdock-progress">
        <span className="story-bottombar-dots" aria-hidden="true">
          {Array.from({ length: p.count }, (_, i) => (
            <span key={i} className={`story-bottombar-dot is-${p.onCover ? 'ahead' : dotState(i, p.active, p.count)}`} />
          ))}
        </span>
        <span className="story-bottombar-left">{p.onCover ? `${p.count} screens` : toGoLabel(p.count - 1 - p.active)}</span>
      </span>
      {next}
    </div>
  )
}
