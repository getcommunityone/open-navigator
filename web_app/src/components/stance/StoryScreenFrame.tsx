import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useScreenFit } from './useScreenFit'
import KineticText from './KineticText'
import ScreenNav from './ScreenNav'

interface Props {
  /** The screen's id (`data-screen`, the heading's id, `?screen=`). */
  id: string
  /** 0-based position (`data-panel`, what the scroller counts). */
  index: number
  active: boolean
  /** The screen's short word ("Overview", "Who spoke"). */
  eyebrow: string
  /** The line above the word ("For context · source: …"), when the screen has one. */
  kicker?: ReactNode
  headline: string
  context: ReactNode
  /** Under the headline and context, before the nav (a question, a broaden button, a statement). */
  children?: ReactNode
  nextLabel: string | null
  onNext: () => void
  onPrev?: () => void
  /** The screen's own primary action in Next's spot (see ScreenNav). */
  navPrimary?: ReactNode
  /** The figure column. */
  right: ReactNode
  /** Phones (#1380): the Overview drops its boxed word and fills the screen with the map; the headline stays for screen readers. */
  glance?: boolean
}

/**
 * One screen of a data story (#1224): the big word, the card, the headline and its line of context, the inline Back/Next and
 * the figure beside them. The markup and hooks (`.stance-panel`, `.stance-word`, `.stance-card`, `.stance-head`,
 * `.stance-right`, `.stance-nav`) are the ones `useActs` and stance.css animate, so every story's screens move alike. Shared
 * by the Data Center Story (StoryScreenView) and the topic stories.
 */
export default function StoryScreenFrame(p: Props) {
  const leftRef = useRef<HTMLDivElement>(null)
  const rightRef = useRef<HTMLDivElement>(null)
  const nextRef = useRef<HTMLButtonElement>(null)
  const sectionRef = useRef<HTMLElement>(null)
  // On a phone the screen fits above the bottom bar (#1290): what doesn't fit waits behind "More".
  const [more, setMore] = useState(false)
  const hasMore = useScreenFit(sectionRef, rightRef, p.active, more || !!p.glance)
  useEffect(() => {
    if (!p.active) setMore(false)
  }, [p.active])

  // A column taller than its frame scrolls on its own: Lenis must leave wheel and touch over it alone, but only then.
  useEffect(() => {
    const els = [leftRef.current, rightRef.current].filter((e): e is HTMLDivElement => e != null)
    const mark = () => els.forEach((e) => e.toggleAttribute('data-lenis-prevent', e.scrollHeight > e.clientHeight + 1))
    mark()
    if (typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(mark)
    els.forEach((e) => ro.observe(e))
    return () => ro.disconnect()
  })

  return (
    <section
      ref={sectionRef}
      data-fit-more={more ? '' : undefined}
      className={`stance-panel stance-act${p.glance ? ' stance-panel--glance' : ''}`}
      data-panel={p.index}
      data-screen={p.id}
      data-live={p.active ? '' : undefined}
      aria-labelledby={`story-h-${p.id}`}
      aria-roledescription="screen"
      tabIndex={-1}
    >
      <span className="stance-word" aria-hidden="true">
        {p.eyebrow}
      </span>
      <div className="stance-grid">
        <div className="stance-left" ref={leftRef}>
          <div className="stance-card">
            {p.kicker && <p className="stance-card-eyebrow">{p.kicker}</p>}
            <p className="stance-card-title">{p.eyebrow}</p>
          </div>
          <div className="stance-head">
            <h2 className="stance-headline" id={`story-h-${p.id}`}>
              <KineticText text={p.headline} />
            </h2>
            <p className="stance-lede">{p.context}</p>
          </div>
          {p.children}
          <ScreenNav ref={nextRef} nextLabel={p.nextLabel} onNext={p.onNext} onPrev={p.onPrev} primary={p.navPrimary} />
        </div>
        <div className="stance-right" ref={rightRef}>
          {p.right}
          {(hasMore || more) && (
            <button type="button" className="folio-link-btn stance-screen-more" aria-expanded={more} onClick={() => setMore((m) => !m)}>
              {more ? 'Less' : 'More on this screen'} {more ? '↑' : '↓'}
            </button>
          )}
        </div>
      </div>
    </section>
  )
}
