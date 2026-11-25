import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { useStoryData } from '../stance/useStoryData'
import { fetchDataCenterMeetingMentions } from '../../api/dataCenters'
import { STORIES, scopeQuery, storyScopeLabel, storyStats } from '../../utils/dataStory'
import { STATE_CODE_TO_NAME } from '../../utils/stateMapping'
import type { ChartKey } from '../../utils/stanceGame'
import StoryStatesMap from './StoryStatesMap'

/** The counts the box shows: the same datasets (and `storyStats`) as the Data Stories hub. */
const COUNT_CHARTS: ChartKey[] = ['meeting-mentions', 'agenda-items', 'sites']

interface Props {
  /** The home page's place, so this section's label, counts and links match it (CLAUDE.md, scope label rule). */
  stateCode?: string
  city?: string | null
}

const fmt = (n: number) => n.toLocaleString('en-US')
const STORY = STORIES['data-centers']!

/**
 * Home `#data-stories` (#975, #985): the header's Data Stories tab scrolls here. The box names the story (The Data
 * Center Story), shows a US map whose markers open the story for each state (real meeting counts), the counts for the
 * home page's place, and lists every story there is. Counts are real (the hub's own endpoints); while they load, or when
 * none load, it says so.
 */
export default function HomeDataStories({ stateCode, city = null }: Props) {
  const stateName = stateCode ? (STATE_CODE_TO_NAME[stateCode] ?? stateCode) : null
  const scope = { stateCode, stateName, city: stateCode ? city : null }
  const label = storyScopeLabel(scope)
  const { data, status, refetch } = useStoryData(stateCode, scope.city, COUNT_CHARTS)
  const states = COUNT_CHARTS.map((k) => status[k] ?? 'loading')
  const loading = states.some((s) => s === 'loading')
  const failed = states.every((s) => s === 'error')
  const stats = storyStats(data, scope)
  const q = scopeQuery(scope)
  // The map is national (every state's own count); the page's state is highlighted.
  const national = useQuery({
    queryKey: ['home', 'story-map', 'meeting-mentions-by-state'],
    queryFn: () => fetchDataCenterMeetingMentions({ limit: 1 }),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  const placeIn = label === 'National' ? 'across the country' : `in ${label}`
  const otherStories = Object.entries(STORIES)

  return (
    <section
      id="data-stories"
      className="v9-section-full"
      aria-labelledby="home-data-stories-h"
      style={{ background: '#fff', borderTop: '1px solid #e7e5e4', padding: '40px 24px', scrollMarginTop: 72 }}
    >
      <div style={{ maxWidth: 1180, margin: '0 auto' }}>
        <div style={{ textAlign: 'center', maxWidth: 720, margin: '0 auto 22px' }}>
          <h2 id="home-data-stories-h" className="font-display" style={{ fontSize: 'clamp(26px, 3.6vw, 34px)', fontWeight: 800, margin: 0, color: '#1c1917' }}>
            Data stories
          </h2>
          <p style={{ fontSize: 15, color: '#57534e', lineHeight: 1.45, marginTop: 8 }}>
            Walk through what local meetings put on the record, one screen at a time, and say where you stand along the way.
          </p>
        </div>

        <article
          aria-labelledby="home-story-dc"
          className="home-story-card"
          style={{ border: '1px solid #e7e5e4', borderRadius: 16, background: '#fafaf9', padding: '24px', maxWidth: 1080, margin: '0 auto' }}
        >
          <div className="home-story-text">
            <p className="font-mono-x" style={{ margin: 0, fontSize: 11.5, letterSpacing: '0.12em', textTransform: 'uppercase', color: '#0f766e', fontWeight: 600 }}>
              Data story · Data centers
            </p>
            <h3 id="home-story-dc" className="font-display" style={{ fontSize: 'clamp(26px, 3vw, 34px)', fontWeight: 800, margin: '6px 0 4px', color: '#1c1917' }}>
              {STORY.title}
            </h3>
            <p className="font-display" style={{ margin: '0 0 8px', fontSize: 'clamp(17px, 1.8vw, 20px)', fontWeight: 600, color: '#0f766e' }}>
              {STORY.question}
            </p>
            <p style={{ margin: 0, fontSize: 15.5, color: '#44403c', lineHeight: 1.5 }}>
              Power, water and land bring neighbors to the microphone. See who spoke, what was promised and what was decided,
              and say whether you agree.
            </p>

            <p className="font-mono-x" style={{ margin: '18px 0 0', fontSize: 11, letterSpacing: '0.08em', textTransform: 'uppercase', color: '#57534e' }}>
              On the record {placeIn}
            </p>
            {loading ? (
              <p role="status" style={{ margin: '8px 0 0', fontSize: 14, color: '#78716c' }}>
                Loading counts…
              </p>
            ) : failed ? (
              <p role="status" style={{ margin: '8px 0 0', fontSize: 14, color: '#78716c' }}>
                The counts could not be loaded right now.{' '}
                <button
                  type="button"
                  onClick={() => COUNT_CHARTS.forEach((k) => refetch(k))}
                  style={{ background: 'none', border: 'none', padding: 0, color: '#0f766e', fontWeight: 600, cursor: 'pointer', textDecoration: 'underline', fontFamily: 'inherit' }}
                >
                  Try again
                </button>
              </p>
            ) : stats.length > 0 ? (
              <dl
                aria-label={`What the data center records cover: ${label}`}
                style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 12, margin: '8px 0 0' }}
              >
                {stats.map((s) => (
                  <div key={s.key} style={{ borderTop: '1px solid #d6d3d1', paddingTop: 6, display: 'flex', flexDirection: 'column-reverse', justifyContent: 'flex-end' }}>
                    <dt style={{ fontSize: 13, color: '#57534e', marginTop: 2, lineHeight: 1.3 }}>{s.label}</dt>
                    <dd className="font-display" style={{ margin: 0, fontSize: 28, fontWeight: 800, color: '#1c1917', lineHeight: 1.1 }}>
                      {fmt(s.value)}
                    </dd>
                  </div>
                ))}
              </dl>
            ) : (
              <p role="status" style={{ margin: '8px 0 0', fontSize: 14, color: '#78716c' }}>
                No data available for {label}.
              </p>
            )}

            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px 18px', marginTop: 20 }}>
              <Link
                to={`/stories/data-centers${q}`}
                style={{ background: '#0f766e', color: '#fff', borderRadius: 999, padding: '11px 22px', fontSize: 15, fontWeight: 700, textDecoration: 'none' }}
              >
                Start the story {label === 'National' ? '' : `for ${label} `}
                <span aria-hidden="true">→</span>
              </Link>
            </div>
          </div>

          <div className="home-story-map">
            <p style={{ margin: '0 0 6px', fontSize: 14, fontWeight: 600, color: '#1c1917' }}>Pick a state to read its story</p>
            {national.isError ? (
              <p className="text-sm text-stone-500">The map could not be loaded right now.</p>
            ) : (
              <StoryStatesMap
                byState={national.data?.counts?.by_state}
                highlight={stateCode ?? null}
                href={(code) => `/stories/data-centers?state=${encodeURIComponent(code)}`}
              />
            )}
          </div>
        </article>

        <nav aria-labelledby="home-all-stories-h" style={{ maxWidth: 1080, margin: '18px auto 0' }}>
          <p id="home-all-stories-h" className="font-mono-x" style={{ margin: '0 0 8px', fontSize: 11, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#57534e' }}>
            All data stories
          </p>
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexWrap: 'wrap', gap: 10 }}>
            {otherStories.map(([id, s]) => (
              <li key={id}>
                <Link
                  to={`/stories/${id}${q}`}
                  style={{ display: 'inline-block', border: '1px solid #d6d3d1', borderRadius: 999, padding: '7px 14px', fontSize: 14, fontWeight: 600, color: '#0f766e', textDecoration: 'none', background: '#fff' }}
                >
                  {s.title}
                </Link>
              </li>
            ))}
          </ul>
          <p style={{ margin: '8px 0 0', fontSize: 13, color: '#78716c' }}>
            {otherStories.length === 1 ? 'This is the first story; more topics are being written.' : `${otherStories.length} stories.`}{' '}
            <Link to={`/stories${q}`} style={{ color: '#0f766e', fontWeight: 600 }}>
              See the stories page
            </Link>
          </p>
        </nav>
      </div>
    </section>
  )
}
