import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { Link } from 'react-router-dom'
import { tabKeyTarget } from '../../utils/homeTopic'
import '../../styles/home-topic-bar.css'

export interface TopicChip {
  id: string
  title: string
}

interface Props {
  /** Every live topic story, from the topic catalog (`useTopicStories().live`); nothing is hard-coded. */
  topics: TopicChip[]
  /** The story the hero shows. */
  selected: string
  onSelect: (slug: string) => void
  /** "?state=AL&city=…" (or empty): carried to Compare all (`/browse-topics/all`) so the place travels. */
  query: string
  /** The hero it controls. */
  panelId: string
}

/**
 * The home topic switcher (#1350): one chip per live topic story, directly above the headline so a reader sees how to
 * change topic without scrolling. A tablist (one tab stop; arrows, Home and End move and pick), the active chip filled
 * teal. It scrolls sideways with a fade at the edge; **Compare all** opens the YoY compare page (#1371), kept out of the
 * tablist (replaces the old "All topics" link and the large Browse topics strip).
 */
export default function HomeTopicBar({ topics, selected, onSelect, query, panelId }: Props) {
  const listRef = useRef<HTMLDivElement>(null)
  const scrollerRef = useRef<HTMLDivElement>(null)
  const [atEnd, setAtEnd] = useState(false)
  const idx = Math.max(0, topics.findIndex((t) => t.id === selected))

  // Keep the active chip in view inside the row (never scrolls the page).
  useEffect(() => {
    const sc = scrollerRef.current
    const el = listRef.current?.querySelectorAll<HTMLElement>('[role="tab"]')[idx]
    if (!sc || !el) return
    const left = el.offsetLeft - sc.offsetLeft
    if (left < sc.scrollLeft || left + el.offsetWidth > sc.scrollLeft + sc.clientWidth) sc.scrollLeft = Math.max(0, left - 16)
  }, [idx, topics.length])
  useEffect(() => {
    const sc = scrollerRef.current
    if (!sc) return
    const measure = () => setAtEnd(sc.scrollLeft + sc.clientWidth >= sc.scrollWidth - 4)
    measure()
    sc.addEventListener('scroll', measure, { passive: true })
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(measure) : null
    ro?.observe(sc)
    return () => {
      sc.removeEventListener('scroll', measure)
      ro?.disconnect()
    }
  }, [topics.length])

  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const next = tabKeyTarget(e.key, idx, topics.length)
    if (next == null) return
    e.preventDefault()
    const t = topics[next]
    if (!t) return
    onSelect(t.id)
    listRef.current?.querySelectorAll<HTMLElement>('[role="tab"]')[next]?.focus({ preventScroll: true })
  }

  return (
    <nav className="home-tbar" aria-label="Topics" data-at-end={atEnd || undefined}>
      <div className="home-tbar-scroll" ref={scrollerRef}>
        <div ref={listRef} role="tablist" aria-label="Topic of the data story" className="home-tbar-list" onKeyDown={onKey}>
          {topics.map((t, i) => {
            const on = t.id === selected
            return (
              <button
                key={t.id}
                type="button"
                role="tab"
                id={`home-tab-${t.id}`}
                aria-selected={on}
                aria-controls={panelId}
                tabIndex={i === idx ? 0 : -1}
                className={'home-tbar-chip' + (on ? ' is-on' : '')}
                onClick={() => onSelect(t.id)}
              >
                {t.title}
              </button>
            )
          })}
        </div>
        <Link to={`/browse-topics/all${query}`} className="home-tbar-chip is-all">
          Compare all <span aria-hidden="true">→</span>
        </Link>
      </div>
    </nav>
  )
}
