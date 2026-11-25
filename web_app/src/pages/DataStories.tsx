import { useCallback, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import '@fontsource-variable/geist'
import '@fontsource-variable/geist-mono'
import '../styles/folio.css'
import '../styles/stance.css'
import type { DataCenterPositionsResponse } from '../api/dataCenters'
import FloatingNext from '../components/stance/FloatingNext'
import PlaceControl from '../components/stance/PlaceControl'
import PositionsBlock from '../components/stance/PositionsBlock'
import SentenceHeading from '../components/stance/SentenceHeading'
import StatRow from '../components/stance/StatRow'
import { useStoryData } from '../components/stance/useStoryData'
import { useIdleNudge } from '../hooks/useIdleNudge'
import { STATE_CODES } from '../lib/usStates'
import { challengePath, scopeQuery, statsScopeNote, storyPlaceDisplay, storyScopeLabel, storyStats } from '../utils/dataStory'
import { HOUSE_STYLE } from '../utils/houseTheme'
import { STATE_CODE_TO_NAME } from '../utils/stateMapping'
import type { ChartKey } from '../utils/stanceGame'

// Only topics built from meeting recordings or transcripts are listed here (figure-only data such as census measures is under Explore).
/** The datasets behind the hub's volume counts. */
const COUNT_CHARTS: ChartKey[] = ['meeting-mentions', 'agenda-items', 'sites', 'job-claims', 'projects']
/** Everything the hub reads: who spoke up leads, the volume counts follow. */
const HUB_CHARTS: ChartKey[] = ['positions', ...COUNT_CHARTS]

/**
 * `/stories`: one card per topic. The page sentence names place and topic (two lines max); the card leads with a
 * care-first hook and a prompt to Start — not a second topic title (#950 / #954). The agree/disagree question lives in
 * the story's closing screen and in the Challenge.
 */
export default function DataStories() {
  const [sp, setSp] = useSearchParams()
  const rawState = (sp.get('state') ?? '').trim().toUpperCase()
  const stateCode = STATE_CODES.includes(rawState) ? rawState : undefined
  const stateName = stateCode ? (STATE_CODE_TO_NAME[stateCode] ?? stateCode) : null
  const city = stateCode ? (sp.get('city') ?? '').trim() || null : null
  const scope = { stateCode, stateName, city }
  const label = storyScopeLabel(scope)
  const [placeOpen, setPlaceOpen] = useState(false)
  const [topic, setTopic] = useState('data-centers')
  const { data, status, refetch } = useStoryData(stateCode, city, HUB_CHARTS)
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

  return (
    <div className="folio stories-hub" style={HOUSE_STYLE} ref={rootRef}>
      <header className="stories-head">
        <p className="folio-eyebrow">Data stories</p>
        <SentenceHeading
          className="stories-title"
          template={['What did local meetings in ', { blank: 'place' }, ' say about ', { blank: 'topic' }, '?']}
          blanks={[
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
            { id: 'topic', label: 'Topic', value: topic, display: 'data centers', options: [{ value: 'data-centers', label: 'data centers' }], onChange: setTopic },
          ]}
        />
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
                National only
              </button>
            )}
          </p>
        </div>
      </header>

      <ul className="stories-list">
        <li>
          <article className="stories-card" aria-labelledby="story-card-data-centers">
            <h2 className="stories-card-title" id="story-card-data-centers">
              Power, water, and land bring people to the microphone
            </h2>
            <p className="stance-lede">
              In {label === 'National' ? 'the United States' : label}, neighbors show up when a project hits the agenda. See
              who spoke for and against — then Start the story to walk through what the meetings put on the record.
            </p>
            <section className="stories-voices" aria-labelledby="story-voices-h">
              <h3 className="stories-voices-title" id="story-voices-h">
                Who spoke up
              </h3>
              <PositionsBlock
                data={data.positions as DataCenterPositionsResponse | null | undefined}
                status={status.positions ?? 'loading'}
                scope={scope}
                labelledBy="story-voices-h"
              />
            </section>
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
                <StatRow stats={stats} label={`What the data center records cover: ${label}`} />
                <p className="stance-note">{statsScopeNote(stats, scope)}</p>
              </>
            ) : (
              <p className="stance-nodata" role="status">
                No data available for this place.
              </p>
            )}
            <div className="stories-actions">
              <Link
                className="folio-btn stance-next stories-start stories-start-pulse"
                to={`/stories/${encodeURIComponent(topic)}${q}`}
                data-primary
              >
                Start the story <span aria-hidden="true">→</span>
              </Link>
              <Link className="folio-link-btn stories-second" to={challengePath('data-centers', scope)}>
                Take the challenge
              </Link>
            </div>
          </article>
        </li>
      </ul>
      <FloatingNext rootRef={rootRef} />
    </div>
  )
}
