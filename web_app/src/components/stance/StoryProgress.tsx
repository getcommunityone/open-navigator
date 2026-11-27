import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { dotState, isLastScreen } from '../../utils/storyNav'
import { toGoLabel } from '../../utils/floatingNext'

// Progress through a data story and the way on to the next one (#1102). Every control here moves with the story's own
// screen navigation (`goTo`, the same function as Next and the keys), so the landing and scroll logic stays in one place.
// Wide screens show progress in the top bar's segments (ProgressPips with onJump, #1192); phones in the bottom bar here.

interface CardProps {
  href: string
  /** "Next story: Short-term rentals" or "All data stories". */
  label: string
  /** True when the link is the next story (not the list of stories). */
  isStory: boolean
  /** Told when the card comes into view or leaves it. */
  onInView?: (inView: boolean) => void
}

/**
 * The end of the story (#1102): after the last screen, a full-width card fades in (opacity and a short rise; opacity only
 * under reduced motion, see stance.css) and leads to the next live story, keeping the place in the address.
 */
export function NextStoryCard({ href, label, isStory, onInView }: CardProps) {
  const ref = useRef<HTMLDivElement>(null)
  const [shown, setShown] = useState(false)
  const told = useRef(onInView)
  told.current = onInView
  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (typeof IntersectionObserver === 'undefined') {
      setShown(true)
      return
    }
    // Once shown it stays shown; whether it is in view is reported every time it changes.
    const io = new IntersectionObserver(
      (entries) => {
        const e = entries[entries.length - 1]
        if (!e) return
        if (e.isIntersecting) setShown(true)
        told.current?.(e.isIntersecting)
      },
      { threshold: 0.15 },
    )
    io.observe(el)
    return () => {
      io.disconnect()
      told.current?.(false)
    }
  }, [])
  return (
    <div className={`story-next-card${shown ? ' is-shown' : ''}`} ref={ref} data-testid="next-story-card">
      <Link to={href} className="story-next-link">
        <span className="story-next-eyebrow">{isStory ? 'Up next' : 'That was the last story'}</span>
        <span className="story-next-title">
          {label} <span aria-hidden="true">→</span>
        </span>
      </Link>
    </div>
  )
}

interface BarProps {
  active: number
  count: number
  /** The next screen's word, for the button's accessible name. */
  nextLabel: string | null
  onNext: () => void
  /** Where Next goes from the last screen. */
  storyHref: string
  storyLabel: string
  /** True when the last screen leads to another story (not the list of stories). */
  storyIsNext: boolean
  /** True while the story's cover is in view (#1192): its Start button is the way forward there, so the bar shows progress only. */
  hideNext?: boolean
}

/**
 * Phones (< 768px): a bar fixed to the bottom of the window with compact progress dots and one prominent Next. It is the
 * phone's only progress indicator (#1192: the top bar shows none there), and on the cover it drops Next for Start. Next moves to
 * the next screen; on the last screen it becomes the way to the next story. The page leaves room for it (stance.css), so it
 * never covers the story's own controls.
 */
export function StoryBottomBar({ active, count, nextLabel, onNext, storyHref, storyLabel, storyIsNext, hideNext = false }: BarProps) {
  const last = isLastScreen(active, count)
  return (
    <div className="story-bottombar" data-testid="story-bottombar">
      <span className="story-bottombar-progress">
        <span className="story-bottombar-dots" aria-hidden="true">
          {Array.from({ length: count }, (_, i) => (
            <span key={i} className={`story-bottombar-dot is-${dotState(i, active, count)}`} />
          ))}
        </span>
        <span className="story-bottombar-left">{toGoLabel(count - 1 - active)}</span>
      </span>
      {hideNext ? null : last ? (
        <Link to={storyHref} className="folio-btn story-bottombar-next" aria-label={storyLabel}>
          {storyIsNext ? 'Next story' : 'All stories'} <span aria-hidden="true">→</span>
        </Link>
      ) : (
        <button
          type="button"
          className="folio-btn story-bottombar-next"
          onClick={onNext}
          aria-label={nextLabel ? `Next: ${nextLabel}` : 'Next'}
        >
          Next <span aria-hidden="true">→</span>
        </button>
      )}
    </div>
  )
}
