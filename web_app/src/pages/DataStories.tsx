import { useCallback, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import '@fontsource-variable/geist'
import '@fontsource-variable/geist-mono'
import '../styles/folio.css'
import '../styles/stance.css'
import PlaceControl from '../components/stance/PlaceControl'
import SentenceHeading from '../components/stance/SentenceHeading'
import StatRow from '../components/stance/StatRow'
import { useStoryData } from '../components/stance/useStoryData'
import { STATE_CODES } from '../lib/usStates'
import { challengePath, scopeQuery, statsScopeNote, storyPlaceDisplay, storyScopeLabel, storyStats } from '../utils/dataStory'
import { HOUSE_STYLE } from '../utils/houseTheme'
import { STATE_CODE_TO_NAME } from '../utils/stateMapping'
import type { ChartKey } from '../utils/stanceGame'

// Only topics built from meeting recordings or transcripts are listed here (figure-only data such as census measures is under Explore).
/** The datasets behind the hub's counts. */
const HUB_CHARTS: ChartKey[] = ['meeting-mentions', 'agenda-items', 'sites', 'job-claims', 'projects']

/** `/stories`: one card per topic, each with the story and the challenge, and real counts for the place in scope. */
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

  const states = HUB_CHARTS.map((k) => status[k] ?? 'loading')
  const loading = states.some((s) => s === 'loading')
  const allFailed = states.every((s) => s === 'error')
  const stats = storyStats(data, scope)
  const q = scopeQuery(scope)

  return (
    <div className="folio stories-hub" style={HOUSE_STYLE}>
      <header className="stories-head">
        <p className="folio-eyebrow">Data stories</p>
        <SentenceHeading
          className="stories-title"
          template={['What did ', { blank: 'place' }, ' say about ', { blank: 'topic' }, '?']}
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
        <p className="stance-cover-lead">
          Public records told one scrolling screen at a time. Each story is built from meeting recordings, transcripts and agendas, and every
          dot in its charts is a record you can open. Records from other sources are marked "For context".
        </p>
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
            <p className="folio-eyebrow">Topic</p>
            <h2 className="stories-card-title" id="story-card-data-centers">
              Data centers
            </h2>
            <p className="stance-lede">
              Where they are, what is proposed, what is promised, what comes up in meetings and when. Read it as a story, or take the challenge
              and say where you stand.
            </p>
            {loading ? (
              <p className="folio-muted" role="status">
                Loading counts…
              </p>
            ) : allFailed ? (
              <div className="stance-nodata" role="status">
                <p>The counts could not be loaded right now.</p>
                <button type="button" className="folio-btn" onClick={() => HUB_CHARTS.forEach((k) => refetch(k))}>
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
              <Link className="folio-btn stance-next" to={`/stories/${encodeURIComponent(topic)}${q}`}>
                Read the story
              </Link>
              <Link className="folio-btn" to={challengePath('data-centers', scope)}>
                Take the challenge
              </Link>
            </div>
          </article>
        </li>
      </ul>
    </div>
  )
}
