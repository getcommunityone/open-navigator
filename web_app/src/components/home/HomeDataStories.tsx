import { Link, useSearchParams } from 'react-router-dom'
import { STATE_CODES } from '../../lib/usStates'
import { useStoryData } from '../stance/useStoryData'
import { challengePath, scopeQuery, storyScopeLabel, storyStats } from '../../utils/dataStory'
import { STATE_CODE_TO_NAME } from '../../utils/stateMapping'
import type { ChartKey } from '../../utils/stanceGame'

/** The counts the section shows: the same datasets (and `storyStats`) as the Data Stories hub. */
const COUNT_CHARTS: ChartKey[] = ['meeting-mentions', 'agenda-items', 'sites']

interface Props {
  /** The home page's place, so this section's label, counts and links match it (CLAUDE.md, scope label rule). */
  stateCode?: string
  city?: string | null
}

const fmt = (n: number) => n.toLocaleString('en-US')

/**
 * Home `#data-stories` (#975): the header's Data Stories tab scrolls here; the story, the challenge and the full hub open
 * from its actions. Counts are real (the hub's own endpoints); while they load, or when none load, it says so.
 */
export default function HomeDataStories({ stateCode: homeState, city: homeCity = null }: Props) {
  // A place carried in the address (from a tab on a scoped page) wins over the home page's own place.
  const [sp] = useSearchParams()
  const urlState = (sp.get('state') ?? '').trim().toUpperCase()
  const fromUrl = STATE_CODES.includes(urlState)
  const stateCode = fromUrl ? urlState : homeState
  const city = fromUrl ? (sp.get('city') ?? '').trim() || null : homeCity
  const stateName = stateCode ? (STATE_CODE_TO_NAME[stateCode] ?? stateCode) : null
  const scope = { stateCode, stateName, city: stateCode ? city : null }
  const label = storyScopeLabel(scope)
  const { data, status, refetch } = useStoryData(stateCode, scope.city, COUNT_CHARTS)
  const states = COUNT_CHARTS.map((k) => status[k] ?? 'loading')
  const loading = states.some((s) => s === 'loading')
  const failed = states.every((s) => s === 'error')
  const stats = storyStats(data, scope)
  const q = scopeQuery(scope)

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
            Walk through what local meetings put on the record, one screen at a time, then say where you stand.
          </p>
        </div>

        <article
          aria-labelledby="home-story-dc"
          style={{ border: '1px solid #e7e5e4', borderRadius: 16, background: '#fafaf9', padding: '22px 24px', maxWidth: 980, margin: '0 auto' }}
        >
          <p className="font-mono-x" style={{ margin: 0, fontSize: 11.5, letterSpacing: '0.12em', textTransform: 'uppercase', color: '#0f766e', fontWeight: 600 }}>
            Data centers · {label}
          </p>
          <h3 id="home-story-dc" className="font-display" style={{ fontSize: 'clamp(22px, 2.6vw, 28px)', fontWeight: 700, margin: '6px 0 6px', color: '#1c1917' }}>
            Power, water, and land bring people to the microphone
          </h3>
          <p style={{ margin: 0, fontSize: 15.5, color: '#44403c', lineHeight: 1.5, maxWidth: 720 }}>
            Neighbors show up when a data center hits the agenda. See who spoke, what was promised, and what was decided.
          </p>

          {loading ? (
            <p role="status" style={{ margin: '16px 0 0', fontSize: 14, color: '#78716c' }}>
              Loading counts…
            </p>
          ) : failed ? (
            <p role="status" style={{ margin: '16px 0 0', fontSize: 14, color: '#78716c' }}>
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
              style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: 14, margin: '18px 0 0' }}
            >
              {stats.map((s) => (
                <div key={s.key} style={{ borderTop: '1px solid #d6d3d1', paddingTop: 8, display: 'flex', flexDirection: 'column-reverse', justifyContent: 'flex-end' }}>
                  <dt className="font-mono-x" style={{ fontSize: 11, letterSpacing: '0.06em', textTransform: 'uppercase', color: '#57534e', marginTop: 4 }}>
                    {s.label}
                  </dt>
                  <dd className="font-display" style={{ margin: 0, fontSize: 30, fontWeight: 800, color: '#1c1917', lineHeight: 1.1 }}>
                    {fmt(s.value)}
                  </dd>
                </div>
              ))}
            </dl>
          ) : (
            <p role="status" style={{ margin: '16px 0 0', fontSize: 14, color: '#78716c' }}>
              No data available for {label}.
            </p>
          )}

          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '10px 18px', marginTop: 20 }}>
            <Link
              to={`/stories/data-centers${q}`}
              style={{ background: '#0f766e', color: '#fff', borderRadius: 999, padding: '11px 22px', fontSize: 15, fontWeight: 700, textDecoration: 'none' }}
            >
              Start the story <span aria-hidden="true">→</span>
            </Link>
            <Link to={challengePath('data-centers', scope)} style={{ color: '#0f766e', fontWeight: 600, fontSize: 15 }}>
              Take the challenge
            </Link>
            <Link to={`/stories${q}`} style={{ color: '#0f766e', fontWeight: 600, fontSize: 15 }}>
              All data stories
            </Link>
          </div>
        </article>
      </div>
    </section>
  )
}
