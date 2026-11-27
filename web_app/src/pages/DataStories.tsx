import { useCallback, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import '../styles/folio.css'
import '../styles/stance.css'
import type { DataCenterPositionsResponse } from '../api/dataCenters'
import FloatingNext from '../components/stance/FloatingNext'
import PlaceControl from '../components/stance/PlaceControl'
import PositionsBlock from '../components/stance/PositionsBlock'
import SentenceHeading from '../components/stance/SentenceHeading'
import StatRow from '../components/stance/StatRow'
import { useStoryData } from '../components/stance/useStoryData'
import { useStoryConclusionState } from '../components/stance/useStoryConclusion'
import { useIdleNudge } from '../hooks/useIdleNudge'
import { STATE_CODES } from '../lib/usStates'
import {
  positionFigures,
  positionsLoaded,
  scopeQuery,
  statsScopeNote,
  storyPlaceDisplay,
  storyScopeLabel,
  storyStats,
} from '../utils/dataStory'
import { HOUSE_STYLE } from '../utils/houseTheme'
import { storyStartLabel } from '../utils/storyCaption'
import { STATE_CODE_TO_NAME } from '../utils/stateMapping'
import type { ChartKey } from '../utils/stanceGame'
import { useDocumentTitle } from '../utils/useDocumentTitle'

// Only topics built from meeting recordings or transcripts are listed here (figure-only data such as census measures is under Explore).
/** The datasets behind the hub's volume counts. */
const COUNT_CHARTS: ChartKey[] = ['meeting-mentions', 'agenda-items', 'sites', 'job-claims', 'projects']
/** Everything the hub reads: who spoke up leads, the volume counts follow. */
const HUB_CHARTS: ChartKey[] = ['positions', ...COUNT_CHARTS]

/**
 * `/stories`: one card per topic. Short sentence about what people are saying in local data-center meetings; the card
 * leads with a care-first hook and compact counts so Start fits the first viewport (#950 / #954 / #962). Empty "Who spoke
 * up" is omitted on the hub until positions data is loaded. The agree/disagree question lives in the story's closing
 * screen and in the Challenge.
 */
export default function DataStories() {
  const [sp, setSp] = useSearchParams()
  const rawState = (sp.get('state') ?? '').trim().toUpperCase()
  const stateCode = STATE_CODES.includes(rawState) ? rawState : undefined
  const stateName = stateCode ? (STATE_CODE_TO_NAME[stateCode] ?? stateCode) : null
  const city = stateCode ? (sp.get('city') ?? '').trim() || null : null
  const scope = { stateCode, stateName, city }
  const label = storyScopeLabel(scope)
  useDocumentTitle(stateCode ? `Data stories · ${city ? `${city}, ${stateCode}` : stateName}` : 'Data stories')
  const [placeOpen, setPlaceOpen] = useState(false)
  const [topic, setTopic] = useState('data-centers')
  const { data, status, refetch } = useStoryData(stateCode, city, HUB_CHARTS)
  const { conclusion, pending } = useStoryConclusionState('data-centers')
  const rootRef = useRef<HTMLDivElement>(null)
  // A reader who has stopped gets a calm cue on Start (or on the floating bar when Start has scrolled away).
  useIdleNudge({ rootRef })

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

  const states = COUNT_CHARTS.map((k) => status[k] ?? 'loading')
  const loading = states.some((s) => s === 'loading')
  const allFailed = states.every((s) => s === 'error')
  const stats = storyStats(data, scope)
  const q = scopeQuery(scope)
  const positions = data.positions as DataCenterPositionsResponse | null | undefined
  // Hub: only show Who spoke up when real figures are in — never the empty "not loaded yet" filler (#962).
  const showVoices =
    (status.positions ?? 'loading') === 'ready' && Boolean(positionFigures(positions) && positionsLoaded(positions))
  const placeInLede = label === 'National' ? 'the United States' : label
  const countsLabel = stateName
    ? `What the data center records cover: ${label}`
    : 'What the data center records cover'

  return (
    <div className="folio stories-hub" style={HOUSE_STYLE} ref={rootRef}>
      <header className="stories-head">
        <p className="folio-eyebrow">Data stories</p>
        <SentenceHeading
          className="stories-title"
          template={['What people are saying about ', { blank: 'topic' }, ' in ', { blank: 'place' }]}
          blanks={[
            {
              id: 'topic',
              label: 'Topic',
              value: topic,
              display: 'data centers',
              options: [{ value: 'data-centers', label: 'data centers' }],
              onChange: setTopic,
            },
            {
              id: 'place',
              label: 'Place',
              value: stateCode ?? '',
              display: storyPlaceDisplay(scope),
              options: [],
              onChange: () => {},
              control: (
                <PlaceControl
                  variant="blank"
                  display={storyPlaceDisplay(scope)}
                  stateCode={stateCode}
                  city={city}
                  open={placeOpen}
                  onOpenChange={setPlaceOpen}
                  onApply={applyPlace}
                />
              ),
            },
          ]}
        />
        {/* National is already "the United States" in the sentence — don't repeat Showing: National (#959). */}
        {stateName && (
          <div className="stories-scope">
            <p className="stance-scope" data-testid="stance-scope">
              Showing: <b>{label}</b>
              {city && (
                <button type="button" className="folio-link-btn" onClick={() => applyPlace(stateCode ?? null, null)}>
                  All of {stateName}
                </button>
              )}
              <button type="button" className="folio-link-btn" onClick={() => applyPlace(null, null)}>
                National only
              </button>
            </p>
          </div>
        )}
      </header>

      <ul className="stories-list">
        <li>
          <article className="stories-card" aria-labelledby="story-card-data-centers">
            {/* #989: the story's conclusion leads, while the national record backs it; else the neutral hook. */}
            <h2 className="stories-card-title" id="story-card-data-centers" aria-busy={pending || undefined} style={pending ? { visibility: 'hidden' } : undefined}>
              {conclusion ? conclusion.headline : 'Power, water, and land bring people to the microphone'}
            </h2>
            {conclusion ? (
              <>
                <p className="stance-lede">{conclusion.subhead}</p>
                <p className="stance-note stories-basis">{conclusion.basis}</p>
              </>
            ) : (
              <p className="stance-lede">
                In {placeInLede}, neighbors show up when a data center hits the agenda. Start the data center story to walk through what
                the meetings put on the record.
              </p>
            )}
            {/* Start right under the headline, so it is in view on a laptop and a phone (#989). */}
            <div className="stories-actions">
              <Link
                className="folio-btn stance-next stories-start stories-start-pulse"
                to={`/stories/${encodeURIComponent(topic)}${q}`}
                data-primary
              >
                {storyStartLabel(topic, label)} <span aria-hidden="true">→</span>
              </Link>
            </div>
            {showVoices && (
              <section className="stories-voices" aria-labelledby="story-voices-h">
                <h3 className="stories-voices-title" id="story-voices-h">
                  Who spoke for and against
                </h3>
                <PositionsBlock
                  data={positions}
                  status={status.positions ?? 'ready'}
                  scope={scope}
                  labelledBy="story-voices-h"
                />
              </section>
            )}
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
                {stateName ? <p className="stance-note">{statsScopeNote(stats, scope)}</p> : null}
              </>
            ) : (
              <p className="stance-nodata" role="status">
                No data available for this place.
              </p>
            )}
          </article>
        </li>
      </ul>
      <FloatingNext rootRef={rootRef} />
    </div>
  )
}
