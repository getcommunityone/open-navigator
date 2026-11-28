import { useEffect, useRef, useState, type FocusEvent, type KeyboardEvent, type MouseEvent } from 'react'
import { Link } from 'react-router-dom'
import { tabKeyTarget } from '../../utils/homeTopic'
import { pillBadgeText, type HotPill } from '../../utils/hotTopics'
import '../../styles/home-topic-bar.css'

/** The story a topic chip links to, with the place kept: `/stories/<slug>?state=...` (#1430). */
export function topicChipHref(slug: string, query: string): string {
  const q = query.replace(/^\?/, '')
  return `/stories/${encodeURIComponent(slug)}${q ? `?${q}` : ''}`
}

/** A pill's crawlable link: its story when it has one, else its meetings in Browse topics, the place kept. */
export function pillHref(p: Pick<HotPill, 'id' | 'live' | 'topicId'>, query: string): string {
  if (p.live || p.topicId == null) return topicChipHref(p.id, query)
  const q = new URLSearchParams(query.replace(/^\?/, ''))
  q.set('topic_id', String(p.topicId))
  return `/browse-topics?${q.toString()}`
}

interface Props {
  /** Hot and trending topics for the place (#1416): live stories plus rising and heated topics, already ordered. */
  pills: HotPill[]
  /** The topic the hero shows. */
  selected: string
  /** A topic picked and loading: its pill reads as active at once while its data is fetched for the box flight. */
  pendingId?: string | null
  onSelect: (slug: string) => void
  /** Hover, focus or pointerdown on a pill: the caller prefetches that topic's hero data. */
  onPrefetch?: (slug: string) => void
  /** "?state=AL&city=..." (or empty): carried to Compare all (`/browse-topics/all`) so the place travels. */
  query: string
  /** The hero it controls. */
  panelId: string
  /** The place the pills were computed for (the scope label), for the accessible name. */
  scopeLabel?: string
}

/**
 * The home topic switcher (#1350, #1416): one pill per hot or trending topic for the place, directly above the headline.
 * A tablist (one tab stop; arrows, Home and End move and pick), the active pill filled teal. A live story carries a dot, a
 * rising topic a ▲, a heated one a flame (each with its numbers in the tooltip and the screen-reader name). On a phone the
 * row scrolls sideways with a fade at the edge; on a desktop it wraps to at most two rows with **More** to open the rest.
 * **Compare all** (the YoY page, #1371) stays last, outside the tablist.
 */
export default function HomeTopicBar({ pills, selected, pendingId = null, onSelect, onPrefetch, query, panelId, scopeLabel }: Props) {
  const listRef = useRef<HTMLDivElement>(null)
  const scrollerRef = useRef<HTMLDivElement>(null)
  const [atEnd, setAtEnd] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [overflow, setOverflow] = useState(false)
  const active = pendingId ?? selected
  const idx = Math.max(0, pills.findIndex((t) => t.id === active))

  // Keep the active pill in view inside the row (never scrolls the page).
  useEffect(() => {
    const sc = scrollerRef.current
    const list = listRef.current
    const el = list?.querySelectorAll<HTMLElement>('[role="tab"]')[idx]
    if (!sc || !list || !el) return
    const left = el.offsetLeft - sc.offsetLeft
    if (left < sc.scrollLeft || left + el.offsetWidth > sc.scrollLeft + sc.clientWidth) sc.scrollLeft = Math.max(0, left - 16)
  }, [idx, pills.length])
  useEffect(() => {
    const sc = scrollerRef.current
    const list = listRef.current
    if (!sc || !list) return
    const measure = () => {
      setAtEnd(sc.scrollLeft + sc.clientWidth >= sc.scrollWidth - 4)
      // Desktop wraps: rows beyond the second are clipped, and More opens them.
      setOverflow(expanded || list.scrollHeight > list.clientHeight + 1)
    }
    measure()
    sc.addEventListener('scroll', measure, { passive: true })
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(measure) : null
    ro?.observe(sc)
    return () => {
      sc.removeEventListener('scroll', measure)
      ro?.disconnect()
    }
  }, [pills.length, expanded])

  // A pill in the clipped rows that takes focus (keyboard) opens the rest, so focus is never lost out of sight.
  const onFocusIn = (e: FocusEvent<HTMLDivElement>) => {
    const list = listRef.current
    const el = e.target as HTMLElement
    if (!expanded && list && el.getAttribute('role') === 'tab' && el.getBoundingClientRect().bottom > list.getBoundingClientRect().bottom + 1) setExpanded(true)
  }
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const next = tabKeyTarget(e.key, idx, pills.length)
    if (next == null) return
    e.preventDefault()
    const t = pills[next]
    if (!t) return
    onSelect(t.id)
    listRef.current?.querySelectorAll<HTMLElement>('[role="tab"]')[next]?.focus({ preventScroll: true })
  }

  return (
    <nav
      className="home-tbar"
      aria-label={scopeLabel ? `Hot and trending topics, ${scopeLabel}` : 'Hot and trending topics'}
      data-at-end={atEnd || undefined}
      data-expanded={expanded || undefined}
      data-scope={scopeLabel}
    >
      <div className="home-tbar-scroll" ref={scrollerRef}>
        <div ref={listRef} role="tablist" aria-label="Topic of the data story" className="home-tbar-list" onKeyDown={onKey} onFocus={onFocusIn}>
          {pills.map((t, i) => {
            const on = t.id === active
            const badge = pillBadgeText(t)
            return (
              // A tab that is also a real link (#1430): crawlers follow the href; a plain click switches the hero in place.
              <a
                key={t.id}
                href={pillHref(t, query)}
                role="tab"
                id={`home-tab-${t.id}`}
                data-topic={t.id}
                data-live={t.live || undefined}
                aria-selected={on}
                aria-controls={panelId}
                aria-busy={pendingId === t.id || undefined}
                tabIndex={i === idx ? 0 : -1}
                title={[t.live ? 'Has a data story' : null, badge || null].filter(Boolean).join('; ') || undefined}
                className={'home-tbar-chip' + (on ? ' is-on' : '') + (pendingId === t.id ? ' is-pending' : '')}
                onClick={(e: MouseEvent<HTMLAnchorElement>) => {
                  if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return
                  e.preventDefault()
                  onSelect(t.id)
                }}
                onPointerEnter={() => onPrefetch?.(t.id)}
                onPointerDown={() => onPrefetch?.(t.id)}
                onFocus={() => onPrefetch?.(t.id)}
              >
                {t.live && <span className="home-tbar-dot" aria-hidden="true" />}
                {t.title}
                {(t.rise != null || t.heat != null) && (
                  <span className="home-tbar-badges" aria-hidden="true">
                    {t.rise != null && <span data-badge="rising">{'\u25B2'}</span>}
                    {t.heat != null && <span data-badge="heated">{'\u{1F525}'}</span>}
                  </span>
                )}
                {(t.live || badge) && <span className="sr-only">{[t.live ? ', data story' : '', badge ? `, ${badge}` : ''].join('')}</span>}
              </a>
            )
          })}
        </div>
        <div className="home-tbar-tail">
          {overflow && (
            <button type="button" className="home-tbar-chip is-more" aria-expanded={expanded} onClick={() => setExpanded((v) => !v)}>
              {expanded ? 'Fewer' : 'More'}
            </button>
          )}
          <Link to={`/browse-topics/all${query}`} className="home-tbar-chip is-all">
            Compare all <span aria-hidden="true">→</span>
          </Link>
        </div>
      </div>
    </nav>
  )
}
