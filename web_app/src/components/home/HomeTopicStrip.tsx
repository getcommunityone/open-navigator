import { useCallback, useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { Link } from 'react-router-dom'
import { Bike, Camera, ChevronLeft, ChevronRight, Crosshair, Droplets, HandHeart, House, MessagesSquare, Server, ShieldCheck, Volleyball, type LucideIcon } from 'lucide-react'
import { useQueries } from '@tanstack/react-query'
import TopicCompaniesPanel from './TopicCompaniesPanel'
import { fetchTopicCaptionFacts } from '../../api/topics'
import { useTopicStories } from '../../hooks/useTopicStories'
import { docsUrl } from '../../utils/docsLinks'
import { buildTiles } from '../../utils/homeTopicTiles'
import { STATE_CODE_TO_NAME } from '../../utils/stateMapping'
import { CAPTION_COPY, captionText, pickCaption } from '../../utils/storyCaption'
import { scrollLeftForPage, scrollPages, type ScrollPages } from '../../utils/scrollPages'

/** The story the home card shows (#1025, #1133): `data-centers` or any live topic story's slug. */
export type HomeStoryKey = string

/** Each known tile's look; any other live topic gets the plain one. */
const LOOK: Record<string, { Icon: LucideIcon; tint: string; ink: string }> = {
  dc: { Icon: Server, tint: '#ccfbf1', ink: '#0f766e' },
  str: { Icon: House, tint: '#dcfce7', ink: '#15803d' },
  lpr: { Icon: Camera, tint: '#dbeafe', ink: '#1d4ed8' },
  guns: { Icon: Crosshair, tint: '#fee2e2', ink: '#b91c1c' },
  pickleball: { Icon: Volleyball, tint: '#ecfccb', ink: '#4d7c0f' },
  bike: { Icon: Bike, tint: '#ffedd5', ink: '#c2410c' },
  fluoride: { Icon: Droplets, tint: '#e0f2fe', ink: '#0369a1' },
  nonprofit: { Icon: HandHeart, tint: '#fce7f3', ink: '#be185d' },
  insurance: { Icon: ShieldCheck, tint: '#e0f2fe', ink: '#0369a1' },
}
const PLAIN_LOOK = { Icon: MessagesSquare, tint: '#f5f5f4', ink: '#44403c' }

interface Props {
  /** The page's place (?state=&city=), carried by the "all stories" link. */
  query: string
  /** The story shown above the strip. */
  selected: HomeStoryKey
  onSelect: (story: HomeStoryKey) => void
  /** The page's scope, for the companies panel (CLAUDE.md scope-label rule). */
  stateCode?: string
  city?: string | null
  scopeLabel: string
}

/**
 * "Browse topics" under the home story (#1013, #1025, #1133): picks which story the card above shows (Data centers by
 * default). A tile is live when the topic catalog has a curated topic for it with meetings (utils/homeTopicTiles); guides
 * link to their page; the rest honestly say "Coming soon".
 */
export default function HomeTopicStrip({ query, selected, onSelect, stateCode, city = null, scopeLabel }: Props) {
  const { topics } = useTopicStories()
  const TOPICS = buildTiles(topics)
  // The card whose companies are shown (#1052): the live story's card, or a coming-soon card the reader picked.
  const storyCard = TOPICS.find((t) => t.story === selected)?.key ?? TOPICS[0]!.key
  const [picked, setPicked] = useState<string>(storyCard)
  useEffect(() => setPicked(storyCard), [storyCard])
  const shown = TOPICS.find((t) => t.key === picked && t.companies)

  // Each tile's caption (#1125): the strongest statement its record supports for the page's scope, else its blurb.
  const scope = { stateCode, stateName: stateCode ? (STATE_CODE_TO_NAME[stateCode] ?? stateCode) : null, city: stateCode ? city : null }
  // One query per distinct facts slug (#1170): guide tiles have no slug and several tiles can share one, and duplicate
  // keys in useQueries share observers and trigger TanStack's "Duplicate Queries" warning.
  // Only live tiles ask (#1191): a "coming soon" tile's topic isn't in the catalog, so the API answers 404 for it (it
  // showed its blurb anyway); guides have no meeting record behind them.
  const slugOf = (t: (typeof TOPICS)[number]): string | null => {
    if (t.status !== 'live') return null
    const copy = CAPTION_COPY[t.captionKey]
    return (copy ? copy.facts : t.captionKey) || null
  }
  const slugs = [...new Set(TOPICS.map(slugOf).filter((s): s is string => Boolean(s)))]
  const slugQ = useQueries({
    queries: slugs.map((slug) => ({
      queryKey: ['caption-facts', slug, stateCode ?? '', scope.city ?? ''],
      queryFn: () => fetchTopicCaptionFacts(slug, stateCode, scope.city),
      staleTime: 5 * 60_000,
      retry: 1,
    })),
  })
  const factsQ = TOPICS.map((t) => {
    const slug = slugOf(t)
    return slug ? slugQ[slugs.indexOf(slug)] : undefined
  })
  const captions = TOPICS.map((t, i) => {
    const c = pickCaption(t.captionKey, factsQ[i]?.data, scope)
    return c.kind === 'question' ? null : { text: captionText(c, CAPTION_COPY[t.captionKey]?.topic ?? t.title.toLowerCase()), ai: c.ai }
  })

  // The scroller (#1101): snap per card, previous/next arrows and one dot per page of visible cards.
  const listRef = useRef<HTMLUListElement>(null)
  const [pos, setPos] = useState<ScrollPages>({ pages: 1, current: 0, atStart: true, atEnd: true })
  const measure = useCallback(() => {
    const el = listRef.current
    if (!el) return
    const next = scrollPages(el.scrollLeft, el.clientWidth, el.scrollWidth)
    setPos((p) => (p.pages === next.pages && p.current === next.current && p.atStart === next.atStart && p.atEnd === next.atEnd ? p : next))
  }, [])
  useEffect(() => {
    const el = listRef.current
    if (!el) return
    let frame = 0
    const onScroll = () => {
      if (frame) return
      frame = requestAnimationFrame(() => {
        frame = 0
        measure()
      })
    }
    measure()
    el.addEventListener('scroll', onScroll, { passive: true })
    const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(measure) : null
    ro?.observe(el)
    return () => {
      el.removeEventListener('scroll', onScroll)
      ro?.disconnect()
      if (frame) cancelAnimationFrame(frame)
    }
  }, [measure])
  const behavior = (): ScrollBehavior =>
    typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'
  const page = (dir: 1 | -1) => {
    const el = listRef.current
    if (el) el.scrollBy({ left: dir * el.clientWidth, behavior: behavior() })
  }
  const goTo = (index: number) => {
    const el = listRef.current
    if (el) el.scrollTo({ left: scrollLeftForPage(index, el.clientWidth, el.scrollWidth), behavior: behavior() })
  }

  // Keyboard (#1146): one tab stop into the strip (roving tabindex); ←/→/Home/End move between tiles, Enter or Space picks one.
  const selectedIndex = Math.max(0, TOPICS.findIndex((t) => t.story != null && t.story === selected))
  const [focusIndex, setFocusIndex] = useState(selectedIndex)
  useEffect(() => setFocusIndex(selectedIndex), [selectedIndex])
  const tabStop = Math.min(focusIndex, TOPICS.length - 1)
  const tileAt = (i: number) => listRef.current?.querySelectorAll<HTMLElement>('[data-topic-tile]')[i] ?? null
  const onTileKey = (e: KeyboardEvent<HTMLUListElement>) => {
    const n = TOPICS.length
    const target = e.target as HTMLElement
    if (!target.hasAttribute('data-topic-tile')) return
    const next =
      e.key === 'ArrowRight' ? (focusIndex + 1) % n
      : e.key === 'ArrowLeft' ? (focusIndex - 1 + n) % n
      : e.key === 'Home' ? 0
      : e.key === 'End' ? n - 1
      : null
    if (next != null) {
      e.preventDefault()
      setFocusIndex(next)
      const el = tileAt(next)
      el?.focus({ preventScroll: true })
    } else if (e.key === ' ' && target.tagName === 'A') {
      // A guide tile is a link: Space follows it as Enter does, like the other tiles.
      e.preventDefault()
      target.click()
    }
  }
  return (
    <nav aria-labelledby="home-topics-h" className="home-topics">
      <div className="home-topics-head">
        <p id="home-topics-h" className="font-mono-x">
          Browse topics
        </p>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          {/* Every main topic, last year against this year, in one dumbbell (#1343), in the page's place. */}
          <Link to={`/browse-topics/all${query}`} style={{ fontSize: 13, fontWeight: 600, color: '#0f766e' }}>
            Compare all
          </Link>
          <Link to={`/stories${query}`} aria-label="All data stories" title="All data stories" className="home-topics-all">
            <ChevronRight size={18} aria-hidden="true" />
          </Link>
        </span>
      </div>
      <div className="home-topics-scroller">
        <button type="button" className="home-topics-arrow is-prev" aria-label="Previous topics" onClick={() => page(-1)} disabled={pos.atStart} hidden={pos.pages <= 1}>
          <ChevronLeft size={20} aria-hidden="true" />
        </button>
        <p id="home-topics-keys" className="sr-only">
          Use the left and right arrow keys to move between topics, Enter or Space to pick one.
        </p>
        <ul ref={listRef} className="home-topics-list" aria-labelledby="home-topics-h" aria-describedby="home-topics-keys" onKeyDown={onTileKey}>
          {TOPICS.map((t, i) => {
            const { key, title, blurb, story, status, companies, guide } = t
            const { Icon, tint, ink } = LOOK[key] ?? PLAIN_LOOK
            const cap = captions[i]
            const on = story != null && story === selected
            const companiesOn = status === 'soon' && key === picked
            // The roving tab stop: only one tile is in the tab order; focusing one makes it the stop.
            const rove = {
              'data-topic-tile': '',
              tabIndex: i === tabStop ? 0 : -1,
              onFocus: () => {
                setFocusIndex(i)
                tileAt(i)?.scrollIntoView({ behavior: behavior(), block: 'nearest', inline: 'nearest' })
              },
            }
            const body = (
              <>
                <span className="home-topic-icon" style={{ background: tint, color: ink, opacity: status === 'soon' ? 0.55 : 1 }} aria-hidden="true">
                  <Icon size={26} strokeWidth={1.8} />
                </span>
                <span className="home-topic-text">
                  <span className="home-topic-title">{title}</span>
                  {cap ? (
                    <span className="home-topic-blurb home-topic-caption">
                      {/* No "AI reading" label (owner, #1285); the story's method note names the classifier. */}
                      {cap.text}
                    </span>
                  ) : (
                    <span className="home-topic-blurb">{blurb}</span>
                  )}
                  {status === 'guide' ? (
                    <span className="home-topic-go">
                      Read the guide <span aria-hidden="true">→</span>
                    </span>
                  ) : status === 'soon' ? (
                    <span className="home-topic-soon">
                      Coming soon{companies ? (companiesOn ? ' · Companies below' : ' · See companies') : ''}
                    </span>
                  ) : on ? (
                    <span className="home-topic-on">Showing above</span>
                  ) : (
                    <span className="home-topic-go">
                      Show this story <span aria-hidden="true">→</span>
                    </span>
                  )}
                </span>
              </>
            )
            return (
              <li key={key}>
                {status === 'live' && story ? (
                  <button type="button" {...rove} className={'home-topic' + (on ? ' is-on' : '')} aria-pressed={on} onClick={() => { onSelect(story); setPicked(key) }}>
                    {body}
                  </button>
                ) : status === 'guide' && guide ? (
                  <a {...rove} className="home-topic" href={docsUrl(guide)}>
                    {body}
                  </a>
                ) : companies ? (
                  // Coming soon, but its companies are tracked: picking it shows them below (the story above stays).
                  <button type="button" {...rove} className={'home-topic is-soon' + (companiesOn ? ' is-picked' : '')} aria-pressed={companiesOn} onClick={() => setPicked(key)}>
                    {body}
                  </button>
                ) : (
                  // Coming soon with nothing to show: still reachable by the arrows, and announced as unavailable.
                  <div {...rove} role="button" className="home-topic is-soon" aria-disabled="true">
                    {body}
                  </div>
                )}
              </li>
            )
          })}
        </ul>
        <button type="button" className="home-topics-arrow is-next" aria-label="Next topics" onClick={() => page(1)} disabled={pos.atEnd} hidden={pos.pages <= 1}>
          <ChevronRight size={20} aria-hidden="true" />
        </button>
      </div>
      {pos.pages > 1 && (
        <div className="home-topics-dots">
          {Array.from({ length: pos.pages }, (_, i) => (
            <button
              key={i}
              type="button"
              className={'home-topics-dot' + (i === pos.current ? ' is-on' : '')}
              aria-label={`Topics page ${i + 1} of ${pos.pages}`}
              aria-current={i === pos.current ? 'true' : undefined}
              onClick={() => goTo(i)}
            />
          ))}
        </div>
      )}
      {shown?.companies && (
        <TopicCompaniesPanel queryId={shown.companies} title={shown.title} stateCode={stateCode} city={city} scopeLabel={scopeLabel} />
      )}
    </nav>
  )
}
