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
  /** One word per screen: with `onJump`, the bar reads "3 of 11 · Sites" and opens a list to jump to any screen (#1337). */
  labels?: string[]
  onJump?: (index: number) => void
  /** The next screen's word, for the button's accessible name. */
  nextLabel: string | null
  onNext: () => void
  /** Where Next goes from the last screen. */
  storyHref: string
  storyLabel: string
  /** True when the last screen leads to another story (not the list of stories). */
  storyIsNext: boolean
  /** The previous screen's word (#1222), for Back's accessible name; null on the first screen (no Back). */
  prevLabel?: string | null
  /** Back one screen (#1222): the phone bar's Back, the same move as a swipe right. */
  onPrev?: () => void
  /** False: the bar shows no Next (the story's fixed `StoryNextButton` is the way forward, #1234). */
  withNext?: boolean
  /** True while the story's cover is in view (#1192): its Start button is the way forward there, so the bar shows progress only. */
  hideNext?: boolean
}

/**
 * Phones (< 768px): a bar fixed to the bottom of the window with compact progress dots and one prominent Next. It is the
 * phone's only progress indicator (#1192: the top bar shows none there), and on the cover it drops Next for Start. Next moves to
 * the next screen; on the last screen it becomes the way to the next story. The page leaves room for it (stance.css), so it
 * never covers the story's own controls.
 */
export function StoryBottomBar({ active, count, labels, onJump, nextLabel, onNext, prevLabel = null, onPrev, storyHref, storyLabel, storyIsNext, hideNext = false, withNext = true }: BarProps) {
  const last = isLastScreen(active, count)
  const [listOpen, setListOpen] = useState(false)
  // Back (#1222, owner: "On phone back button is missing"): from the second screen on, never on the cover.
  const showBack = !hideNext && active > 0 && Boolean(onPrev) && Boolean(prevLabel)
  return (
    <div className="story-bottombar" data-testid="story-bottombar">
      {showBack && (
        <button type="button" className="folio-btn story-bottombar-back" onClick={onPrev} aria-label={`Back: ${prevLabel}`}>
          <span aria-hidden="true">←</span>
        </button>
      )}
      {onJump && labels ? (
        <span className="story-bottombar-progress story-pager" data-testid="story-pager-wrap">
          <button
            type="button"
            className="story-pager-btn"
            data-testid="story-pager"
            aria-haspopup="listbox"
            aria-expanded={listOpen}
            onClick={() => setListOpen((o) => !o)}
          >
            {active + 1} of {count} · {labels[active] ?? ''} <span aria-hidden="true">▴</span>
          </button>
          {listOpen && (
            <ol className="story-pager-list" role="listbox" aria-label="Story screens" data-testid="story-pager-list">
              {labels.map((name, i) => (
                <li key={i} role="option" aria-selected={i === active}>
                  <button
                    type="button"
                    className="story-pager-item"
                    aria-current={i === active ? 'step' : undefined}
                    onClick={() => {
                      setListOpen(false)
                      onJump(i)
                    }}
                  >
                    <span className="story-pager-n">{i + 1}</span> {name}
                  </button>
                </li>
              ))}
            </ol>
          )}
        </span>
      ) : (
        <span className="story-bottombar-progress">
          <span className="story-bottombar-dots" aria-hidden="true">
            {Array.from({ length: count }, (_, i) => (
              <span key={i} className={`story-bottombar-dot is-${dotState(i, active, count)}`} />
            ))}
          </span>
          <span className="story-bottombar-left">{toGoLabel(count - 1 - active)}</span>
        </span>
      )}
      {hideNext || !withNext ? (
        // Room for the fixed Next at the bar's right end (#1234).
        withNext ? null : <span className="story-bottombar-nextspace" aria-hidden="true" />
      ) : last ? (
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
