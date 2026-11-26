import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bike, Camera, ChevronLeft, ChevronRight, Crosshair, HandHeart, House, ScanLine, Server, ShieldCheck, Volleyball, type LucideIcon } from 'lucide-react'
import { useQueries } from '@tanstack/react-query'
import TopicCompaniesPanel from './TopicCompaniesPanel'
import { fetchTopicCaptionFacts } from '../../api/topics'
import { STATE_CODE_TO_NAME } from '../../utils/stateMapping'
import { CAPTION_COPY, captionText, pickCaption } from '../../utils/storyCaption'
import { scrollLeftForPage, scrollPages, type ScrollPages } from '../../utils/scrollPages'

/** The live home stories the strip can select (#1025). */
export type HomeStoryKey = 'data-centers' | 'short-term-rentals'

interface Topic {
  key: string
  title: string
  blurb: string
  Icon: LucideIcon
  tint: string
  ink: string
  /** The home story it selects; absent while the story is coming soon. */
  story?: HomeStoryKey
  /** The curated topic whose companies it shows (#1052); absent when none are tracked. */
  topic?: string
  /** Its caption (#1125): a `CAPTION_COPY` key, read for the page's scope. */
  caption: string
}

// Browse topics (#1013, #1025), in the owner's order: Data centers (the default story above), Short-term rentals, then
// the stories still to come. A live card selects the story shown above it; the rest say "Coming soon" and do nothing.
const TOPICS: Topic[] = [
  { key: 'dc', title: 'Data centers', blurb: 'Who spoke up, the sites and projects, and what was decided.', Icon: Server, tint: '#ccfbf1', ink: '#0f766e', story: 'data-centers', topic: 'data-centers', caption: 'data-centers' },
  { key: 'str', title: 'Short-term rentals', blurb: 'Airbnb, VRBO and vacation rentals, in the words said at meetings.', Icon: House, tint: '#dcfce7', ink: '#15803d', story: 'short-term-rentals', topic: 'short-term-rentals', caption: 'short-term-rentals' },
  { key: 'flock', title: 'Flock', blurb: 'Flock Safety cameras and the contracts behind them.', Icon: Camera, tint: '#dbeafe', ink: '#1d4ed8', topic: 'license-plate-readers', caption: 'flock' },
  { key: 'guns', title: 'Guns', blurb: 'Firearm rules, gun shows and ranges, and gunshot detection, as councils weigh them.', Icon: Crosshair, tint: '#fee2e2', ink: '#b91c1c', topic: 'guns', caption: 'guns' },
  { key: 'lpr', title: 'License plate readers', blurb: 'Automated plate readers: who uses them and for what.', Icon: ScanLine, tint: '#ede9fe', ink: '#6d28d9', topic: 'license-plate-readers', caption: 'license-plate-readers' },
  { key: 'pickleball', title: 'Pickleball', blurb: 'Courts, noise and new venues, as councils and parks boards weigh them.', Icon: Volleyball, tint: '#ecfccb', ink: '#4d7c0f', topic: 'pickleball', caption: 'pickleball' },
  { key: 'bike', title: 'Bike lanes', blurb: 'Bike lanes and paths, as councils weigh them.', Icon: Bike, tint: '#ffedd5', ink: '#c2410c', caption: 'bike-lanes' },
  // Guides, not meeting stories (#1078, #1079): coming soon, with no companies or counts until real data backs them.
  { key: 'nonprofit', title: 'Starting a nonprofit', blurb: 'Every step, filing and fee to start one, state by state.', Icon: HandHeart, tint: '#fce7f3', ink: '#be185d', caption: 'starting-a-nonprofit' },
  { key: 'insurance', title: 'Insurance shopping', blurb: 'Are you paying too much? What regulators publish, made simple.', Icon: ShieldCheck, tint: '#e0f2fe', ink: '#0369a1', caption: 'insurance' },
]

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

/** "Browse topics" under the home story: picks which story the card above shows (Data centers by default). */
export default function HomeTopicStrip({ query, selected, onSelect, stateCode, city = null, scopeLabel }: Props) {
  // The card whose companies are shown (#1052): the live story's card, or a coming-soon card the reader picked.
  const storyCard = TOPICS.find((t) => t.story === selected)?.key ?? TOPICS[0]!.key
  const [picked, setPicked] = useState<string>(storyCard)
  useEffect(() => setPicked(storyCard), [storyCard])
  const shown = TOPICS.find((t) => t.key === picked && t.topic)

  // Each tile's caption (#1125): the strongest statement its record supports for the page's scope, else its blurb.
  const scope = { stateCode, stateName: stateCode ? (STATE_CODE_TO_NAME[stateCode] ?? stateCode) : null, city: stateCode ? city : null }
  const factsQ = useQueries({
    queries: TOPICS.map((t) => {
      const slug = CAPTION_COPY[t.caption]?.facts ?? null
      return {
        queryKey: ['caption-facts', slug, stateCode ?? '', scope.city ?? ''],
        queryFn: () => fetchTopicCaptionFacts(slug!, stateCode, scope.city),
        enabled: Boolean(slug),
        staleTime: 5 * 60_000,
        retry: 1,
      }
    }),
  })
  const captions = TOPICS.map((t, i) => {
    const c = pickCaption(t.caption, factsQ[i]?.data, scope)
    return c.kind === 'question' ? null : { text: captionText(c, CAPTION_COPY[t.caption]?.topic ?? t.title), ai: c.ai }
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
  return (
    <nav aria-labelledby="home-topics-h" className="home-topics">
      <div className="home-topics-head">
        <p id="home-topics-h" className="font-mono-x">
          Browse topics
        </p>
        <Link to={`/stories${query}`} aria-label="All data stories" className="home-topics-all">
          <ChevronRight size={18} aria-hidden="true" />
        </Link>
      </div>
      <div className="home-topics-scroller">
        <button type="button" className="home-topics-arrow is-prev" aria-label="Previous topics" onClick={() => page(-1)} disabled={pos.atStart} hidden={pos.pages <= 1}>
          <ChevronLeft size={20} aria-hidden="true" />
        </button>
        <ul ref={listRef} className="home-topics-list">
          {TOPICS.map(({ key, title, blurb, Icon, tint, ink, story, topic }, i) => {
            const cap = captions[i]
            const on = story != null && story === selected
            const companiesOn = !story && key === picked
            const body = (
              <>
                <span className="home-topic-icon" style={{ background: tint, color: ink, opacity: story ? 1 : 0.55 }} aria-hidden="true">
                  <Icon size={26} strokeWidth={1.8} />
                </span>
                <span className="home-topic-text">
                  <span className="home-topic-title">{title}</span>
                  {cap ? (
                    <span className="home-topic-blurb home-topic-caption">
                      {cap.ai && <span className="home-topic-ai">AI reading · </span>}
                      {cap.text}
                    </span>
                  ) : (
                    <span className="home-topic-blurb">{blurb}</span>
                  )}
                  {!story ? (
                    <span className="home-topic-soon">
                      Coming soon{topic ? (companiesOn ? ' · Companies below' : ' · See companies') : ''}
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
                {story ? (
                  <button type="button" className={'home-topic' + (on ? ' is-on' : '')} aria-pressed={on} onClick={() => { onSelect(story); setPicked(key) }}>
                    {body}
                  </button>
                ) : topic ? (
                  // Coming soon, but its companies are tracked: picking it shows them below (the story above stays).
                  <button type="button" className={'home-topic is-soon' + (companiesOn ? ' is-picked' : '')} aria-pressed={companiesOn} onClick={() => setPicked(key)}>
                    {body}
                  </button>
                ) : (
                  <div className="home-topic is-soon" aria-disabled="true">
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
      {shown?.topic && (
        <TopicCompaniesPanel queryId={shown.topic} title={shown.title} stateCode={stateCode} city={city} scopeLabel={scopeLabel} />
      )}
    </nav>
  )
}
