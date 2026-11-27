import { useCallback, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useQueries } from '@tanstack/react-query'
import '../styles/folio.css'
import '../styles/stance.css'
import { fetchTopicCaptionFacts } from '../api/topics'
import type { DataCenterPositionsResponse } from '../api/dataCenters'
import PlaceControl from '../components/stance/PlaceControl'
import PositionsBlock from '../components/stance/PositionsBlock'
import StatRow from '../components/stance/StatRow'
import { useStoryData } from '../components/stance/useStoryData'
import { useTopicStories } from '../hooks/useTopicStories'
import { STATE_CODES } from '../lib/usStates'
import {
  positionFigures,
  positionsLoaded,
  scopeQuery,
  statsScopeNote,
  storyPlaceDisplay,
  storyScopeLabel,
  storyStats,
  type StoryScope,
} from '../utils/dataStory'
import { HOUSE_STYLE } from '../utils/houseTheme'
import { storyStartLabel } from '../utils/storyCaption'
import { storyCardMeetings, storyCardTitle, storyFactsSlug, storyIndexCards } from '../utils/storyIndex'
import { STATE_CODE_TO_NAME } from '../utils/stateMapping'
import type { ChartKey } from '../utils/stanceGame'

/** The datasets behind the data-center counts row. */
const COUNT_CHARTS: ChartKey[] = ['meeting-mentions', 'agenda-items', 'sites', 'job-claims', 'projects']
/** Everything the data-center detail reads: who spoke up leads, the volume counts follow. */
const DC_CHARTS: ChartKey[] = ['positions', ...COUNT_CHARTS]

const fmt = (n: number) => n.toLocaleString('en-US')

/**
 * `/stories` (#1203): every data story, one card each, in the home Browse topics strip's order (Data centers first). A live
 * card shows the story's title from the shared caption picker for the page's place, its meetings on record there and Start;
 * a topic with no meetings yet reads "Coming soon". The place is the URL's `?state=&city=`, named in the header and carried
 * by every link.
 */
export default function DataStories() {
  const [sp, setSp] = useSearchParams()
  const rawState = (sp.get('state') ?? '').trim().toUpperCase()
  const stateCode = STATE_CODES.includes(rawState) ? rawState : undefined
  const stateName = stateCode ? (STATE_CODE_TO_NAME[stateCode] ?? stateCode) : null
  const city = stateCode ? (sp.get('city') ?? '').trim() || null : null
  const scope: StoryScope = { stateCode, stateName, city }
  const label = storyScopeLabel(scope)
  const q = scopeQuery(scope)
  const [placeOpen, setPlaceOpen] = useState(false)

  const applyPlace = useCallback(
    (code: string | null, community: string | null) => {
      setSp(
        (prev) => {
          const next = new URLSearchParams(prev)
          if (code) next.set('state', code)
          else next.delete('state')
          if (code && community) next.set('city', community)
          else next.delete('city')
          return next
        },
        { replace: true },
      )
    },
    [setSp],
  )

  const { topics, pending: catalogPending, failed: catalogFailed } = useTopicStories()
  // Until the catalog answers (or when it fails) whether a topic is live is unknown: list only the stories known to be live
  // (data centers) rather than calling every other topic "coming soon".
  const cards = storyIndexCards(topics).filter((c) => topics || c.status === 'live')
  const live = cards.filter((c) => c.status === 'live')
  // One caption-facts query per live card's slug, keyed like the home strip's so the two share the cache.
  const slugs = [...new Set(live.map(storyFactsSlug).filter((s): s is string => Boolean(s)))]
  const factsQ = useQueries({
    queries: slugs.map((slug) => ({
      queryKey: ['caption-facts', slug, stateCode ?? '', city ?? ''],
      queryFn: () => fetchTopicCaptionFacts(slug, stateCode, city),
      staleTime: 5 * 60_000,
      retry: 1,
    })),
  })
  const factsFor = (slug: string | null) => (slug ? factsQ[slugs.indexOf(slug)] : undefined)

  return (
    <div className="folio stories-hub" style={HOUSE_STYLE}>
      <header className="stories-head">
        <p className="folio-eyebrow">Data stories</p>
        {/* The scope label (CLAUDE.md): the place every card below is read for. */}
        <h1 className="stories-title" data-testid="stories-scope-title">
          All data stories · {label}
        </h1>
        <div className="stories-scope">
          <p className="stance-scope" data-testid="stance-scope">
            Showing: <b>{label}</b>
            {city && stateName && (
              <button type="button" className="folio-link-btn" onClick={() => applyPlace(stateCode ?? null, null)}>
                All of {stateName}
              </button>
            )}
            {stateName && (
              <button type="button" className="folio-link-btn" onClick={() => applyPlace(null, null)}>
                National
              </button>
            )}
          </p>
          <PlaceControl
            display={storyPlaceDisplay(scope)}
            stateCode={stateCode}
            city={city}
            open={placeOpen}
            onOpenChange={setPlaceOpen}
            onApply={applyPlace}
          />
        </div>
        {catalogFailed && (
          <p className="stance-note" role="status">
            The list of topic stories could not be loaded right now, so only the data center story is shown.
          </p>
        )}
        {catalogPending && (
          <p className="folio-muted" role="status">
            Loading the topic stories…
          </p>
        )}
      </header>

      <ul className="stories-list" data-testid="stories-index">
        {cards.map((card) => {
          const headingId = `story-card-${card.key}`
          if (card.status !== 'live' || !card.story) {
            return (
              <li key={card.key} data-story-card={card.key} data-status="soon">
                <article className="stories-card is-soon" aria-labelledby={headingId}>
                  <h2 className="stories-card-title" id={headingId}>
                    {card.title}
                  </h2>
                  <p className="stance-lede">{card.blurb}</p>
                  <p className="stance-note">Coming soon</p>
                </article>
              </li>
            )
          }
          const fq = factsFor(storyFactsSlug(card))
          const pending = fq?.isPending ?? false
          const title = storyCardTitle(card, fq?.data, scope)
          const meetings = storyCardMeetings(fq?.data, scope)
          return (
            <li key={card.key} data-story-card={card.key} data-status="live">
              <article className="stories-card" aria-labelledby={headingId}>
                <p className="folio-eyebrow">{card.title}</p>
                {/* While the record loads the title's place is held (invisible), so the question doesn't flash first. */}
                <h2 className="stories-card-title" id={headingId} aria-busy={pending || undefined} style={pending ? { visibility: 'hidden' } : undefined}>
                  {title}
                </h2>
                {meetings != null ? (
                  <p className="stance-note" data-testid="story-card-meetings">
                    {fmt(meetings)} {meetings === 1 ? 'meeting' : 'meetings'} on record{label === 'National' ? ' nationally' : ` in ${label}`}
                  </p>
                ) : !pending ? (
                  <p className="stance-note">{card.blurb}</p>
                ) : null}
                <div className="stories-actions">
                  <Link className="folio-btn stance-next stories-start" to={`/stories/${encodeURIComponent(card.story)}${q}`}>
                    {storyStartLabel(card.captionKey, label, card.title)} <span aria-hidden="true">→</span>
                  </Link>
                </div>
                {card.story === 'data-centers' && <DataCenterDetail scope={scope} label={label} />}
              </article>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

/**
 * The data center story's record at a glance (the former hub's counts row and Who spoke for and against), kept as the Data
 * centers card's detail. Loaded only when opened, so the index stays light.
 */
function DataCenterDetail({ scope, label }: { scope: StoryScope; label: string }) {
  const [open, setOpen] = useState(false)
  return (
    <details className="stories-detail" onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}>
      <summary>What the data center records cover</summary>
      {open && <DataCenterRecord scope={scope} label={label} />}
    </details>
  )
}

function DataCenterRecord({ scope, label }: { scope: StoryScope; label: string }) {
  const { data, status, refetch } = useStoryData(scope.stateCode, scope.city, DC_CHARTS)
  const states = COUNT_CHARTS.map((k) => status[k] ?? 'loading')
  const loading = states.some((s) => s === 'loading')
  const allFailed = states.every((s) => s === 'error')
  const stats = storyStats(data, scope)
  const positions = data.positions as DataCenterPositionsResponse | null | undefined
  // Only when real figures are in, never the empty "not loaded yet" filler (#962).
  const showVoices =
    (status.positions ?? 'loading') === 'ready' && Boolean(positionFigures(positions) && positionsLoaded(positions))
  const countsLabel = scope.stateName ? `What the data center records cover: ${label}` : 'What the data center records cover'
  return (
    <div className="stories-detail-body">
      {loading ? (
        <p className="folio-muted" role="status">
          Loading counts…
        </p>
      ) : allFailed ? (
        <div className="stance-nodata" role="status">
          <p>The counts could not be loaded right now.</p>
          <button type="button" className="folio-btn" onClick={() => COUNT_CHARTS.forEach((k) => refetch(k))}>
            Try again
          </button>
        </div>
      ) : stats.length > 0 ? (
        <>
          <StatRow stats={stats} label={countsLabel} />
          {scope.stateName ? <p className="stance-note">{statsScopeNote(stats, scope)}</p> : null}
        </>
      ) : (
        <p className="stance-nodata" role="status">
          No data available for this place.
        </p>
      )}
      {showVoices && (
        <section className="stories-voices" aria-labelledby="story-voices-h">
          <h3 className="stories-voices-title" id="story-voices-h">
            Who spoke for and against
          </h3>
          <PositionsBlock data={positions} status={status.positions ?? 'ready'} scope={scope} labelledBy="story-voices-h" />
        </section>
      )}
    </div>
  )
}
