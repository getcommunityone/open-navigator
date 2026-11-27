import { useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchTopicsYoy, type YoyResponse } from '../api/topicsYoy'
import DumbbellRows, { type DumbbellRow } from '../components/stance/DumbbellRows'
import { DataTable } from '../components/matrix/SectionShell'
import { pctLabel } from '../utils/storyTimeline'
import { STATE_CODE_TO_NAME } from '../utils/stateMapping'
import { changeLabel, scopeQuery, splitTopics, yearBLabel, type YoyMetric } from '../utils/topicsYoy'
import { useDocumentTitle } from '../utils/useDocumentTitle'
import { HOUSE_STYLE } from '../utils/houseTheme'
import '../styles/folio.css'
import '../components/stance/storyCharts.css'

const fmt = (n: number) => n.toLocaleString('en-US')
const countLabel = (v: number) => fmt(Math.round(v))

/**
 * Browse all topics (#1343): one animated dumbbell, a row per main (curated) topic, last full year (hollow dot) against
 * this year to date (filled dot), sorted by change. The default metric is the share of recorded meetings that discussed
 * the topic, so a growing recordings base can't fake growth; a toggle shows raw meeting counts. Rising rows are teal,
 * falling rows ochre, and every change is also written out with its sign. Each row opens that topic's story in the same
 * place. A topic with too few meetings in either year is listed under "Too few meetings to compare", never drawn.
 *
 * Its own route rather than the top of Browse Topics: that page opens on decision cards (owner's call), and the chart
 * needs the full width and a deep link (`/browse-topics/all?state=GA`).
 */
export default function BrowseAllTopics() {
  useDocumentTitle('Browse all topics')
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const stateParam = (searchParams.get('state') || '').trim().toUpperCase() || undefined
  const cityParam = stateParam ? (searchParams.get('city') || '').trim() || undefined : undefined
  const [metric, setMetric] = useState<YoyMetric>('share')
  const [tableOpen, setTableOpen] = useState(false)

  const q = useQuery<YoyResponse>({
    queryKey: ['topics-yoy', stateParam ?? '', cityParam ?? ''],
    queryFn: () => fetchTopicsYoy(stateParam, cityParam),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  const d = q.data

  // The label names the scope the data is actually filtered to: the API's normalised scope once loaded, else the URL's.
  const stateCode = d ? d.scope.state_code : (stateParam ?? null)
  const city = d ? d.scope.city : (cityParam ?? null)
  const stateName = stateCode ? (STATE_CODE_TO_NAME[stateCode] ?? stateCode) : null
  const scopeLabel = city ? `${city}, ${stateCode}` : (stateName ?? 'National')
  const here = scopeQuery(stateCode, city)
  const inPlace = city ? `in ${city}` : stateName ? `in ${stateName}` : 'nationally'

  const { rows, tooFew } = useMemo(() => splitTopics(d?.topics ?? [], metric), [d, metric])
  // Topics with no tagged meeting in either year share one line; the rest show their two counts.
  const untagged = tooFew.filter((t) => t.meetings_a === 0 && t.meetings_b === 0)
  const thin = tooFew.filter((t) => t.meetings_a > 0 || t.meetings_b > 0)
  const yA = d?.year_a ?? ''
  const yB = d ? yearBLabel(d) : ''
  const format = metric === 'share' ? pctLabel : countLabel

  const drawn: DumbbellRow[] = rows.map(({ topic: t, a, b, change }) => {
    const ch = changeLabel(change)
    const counts = `${fmt(t.meetings_a)} of ${fmt(t.recorded_a)} meetings in ${yA}; ${fmt(t.meetings_b)} of ${fmt(t.recorded_b)} in ${yB}`
    return {
      key: t.slug,
      label: t.name,
      a,
      b,
      right: ch,
      negative: b < a,
      ariaLabel: `${t.name}: ${yA} ${format(a)}, ${yB} ${format(b)}, ${ch.replace('−', 'minus ')} change. ${counts}. Opens the story.`,
      tip: { cat: t.name, val: `${format(a)} → ${format(b)} (${ch})`, sub: counts },
    }
  })

  const open = (slug: string) => navigate(`/stories/${encodeURIComponent(slug)}${here}`)
  const rising = rows.filter((r) => r.b > r.a).length
  const falling = rows.filter((r) => r.b < r.a).length

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6">
      <div className="mb-3 text-sm">
        <Link to={`/browse-topics${here}`} className="font-medium text-primary-700 hover:underline">
          ← Browse topics
        </Link>
      </div>
      <section className="folio" style={HOUSE_STYLE} aria-labelledby="all-topics-title">
        <p className="folio-eyebrow">Browse all topics · {scopeLabel}</p>
        <h1 id="all-topics-title" className="folio-heading">
          Which topics are meetings talking about more{yA ? `, ${yA} against ${yB}` : ''}?
        </h1>

        <div className="mt-3 flex flex-wrap items-center gap-2 text-sm" aria-label="Place">
          <span className="rounded-full border border-current px-3 py-1 font-medium" aria-current="true">
            📍 {scopeLabel}
          </span>
          {city && stateCode && (
            <Link to={`/browse-topics/all${scopeQuery(stateCode, null)}`}>All of {stateCode}</Link>
          )}
          {stateCode && <Link to="/browse-topics/all">National</Link>}
        </div>

        <div className="sc-block" style={{ marginTop: 16 }}>
          <div className="sc-controls">
            <div className="folio-seg sc-chips" role="group" aria-label="What the dots measure">
              <button type="button" aria-pressed={metric === 'share'} onClick={() => setMetric('share')}>
                Share of meetings
              </button>
              <button type="button" aria-pressed={metric === 'count'} onClick={() => setMetric('count')}>
                Meeting count
              </button>
            </div>
          </div>
          <p className="sc-h">
            {metric === 'share' ? 'Share of recorded meetings that discussed each topic' : 'Meetings that discussed each topic'}
            {yA ? `, ${yA} and ${yB}` : ''} · {scopeLabel}
          </p>

          {q.isLoading && (
            <p className="sc-note" role="status">
              Loading the comparison…
            </p>
          )}
          {q.isError && <p className="sc-note">The topic comparison could not be loaded right now.</p>}

          {d && rows.length === 0 && (
            <p className="sc-note">
              No topic can be compared for {scopeLabel} yet: each needs at least {d.min_meetings} meetings on the topic in both{' '}
              {yA} and {yB}
              {d.recorded_a < d.min_recorded_meetings || d.recorded_b < d.min_recorded_meetings
                ? `, and the place needs at least ${d.min_recorded_meetings} recorded meetings in each year (${fmt(d.recorded_a)} and ${fmt(d.recorded_b)} are on record)`
                : ''}
              .{stateCode ? ' Try a wider place above.' : ''}
            </p>
          )}

          {d && rows.length > 0 && (
            <>
              <p className="sc-note" aria-live="polite">
                <b>{rising}</b> {rising === 1 ? 'topic is' : 'topics are'} up and <b>{falling}</b> down. Hollow dot = {yA}, filled dot ={' '}
                {yB}; teal rises, ochre falls. Tap a topic for its story.
              </p>
              <DumbbellRows
                rows={drawn}
                aName={yA}
                bName={yB}
                ariaLabel={`Dumbbell chart of every compared topic, ${yA} against ${yB}, ${scopeLabel}`}
                firstRows={30}
                unitPlural="topics"
                replayKey={`${stateCode ?? ''}|${city ?? ''}`}
                format={format}
                valuesOverDots
                toneDots
                onSelect={open}
              />
            </>
          )}

          {d && (
            <p className="sc-note">
              {metric === 'share' ? (
                <>
                  Each dot divides meetings whose transcript discussed the topic by every recorded meeting {inPlace} that
                  year ({fmt(d.recorded_a)} in {yA}, {fmt(d.recorded_b)} in {yB}), so more recordings don’t read as more interest.
                </>
              ) : (
                <>
                  Raw counts of meetings that discussed each topic. {yB} is not a full year, and {fmt(d.recorded_b)} meetings are
                  recorded for it against {fmt(d.recorded_a)} in {yA}, so counts mix interest with how much was recorded; the share
                  view corrects for that.
                </>
              )}{' '}
              {d.year_b_partial && `${d.year_b} runs through the latest meeting on record${d.year_b_through ? ` (${d.year_b_through})` : ''}.`}{' '}
              A topic needs at least {d.min_meetings} meetings in each year to be compared.
              {d.thin_year && (
                <>
                  {' '}
                  <b>
                    Few meetings are recorded {inPlace} in {d.thin_year === d.year_b ? yB : yA}
                  </b>
                  , so read that year with care.
                </>
              )}
            </p>
          )}

          {d && tooFew.length > 0 && (
            <div style={{ marginTop: 14 }}>
              <p className="sc-h">Too few meetings to compare</p>
              <ul className="sc-note" style={{ listStyle: 'none', padding: 0, maxWidth: 'none' }}>
                {thin.map((t) => (
                  <li key={t.slug} style={{ padding: '2px 0' }}>
                    <Link to={`/stories/${encodeURIComponent(t.slug)}${here}`}>{t.name}</Link> — {fmt(t.meetings_a)} in {yA},{' '}
                    {fmt(t.meetings_b)} in {yB}
                  </li>
                ))}
              </ul>
              {untagged.length > 0 && (
                <p className="sc-note">
                  No meetings tagged {inPlace} in {yA} or {yB}:{' '}
                  {untagged.map((t, i) => (
                    <span key={t.slug}>
                      {i > 0 && ', '}
                      <Link to={`/stories/${encodeURIComponent(t.slug)}${here}`}>{t.name}</Link>
                    </span>
                  ))}
                  .
                </p>
              )}
            </div>
          )}

          {d && rows.length > 0 && (
            <>
              <button
                type="button"
                className="folio-btn"
                aria-expanded={tableOpen}
                aria-controls="all-topics-table"
                onClick={() => setTableOpen((o) => !o)}
              >
                {tableOpen ? 'Hide data table ↑' : 'Show data table ↓'}
              </button>
              {tableOpen && (
                <DataTable
                  id="all-topics-table"
                  caption={`Data table: every compared topic, ${yA} and ${yB}, ${scopeLabel}`}
                  spec={{
                    columns: [
                      { label: 'Topic' },
                      { label: `${yA} share`, numeric: true },
                      { label: `${yB} share`, numeric: true },
                      { label: `Meetings ${yA} / ${yB}`, numeric: true },
                      { label: 'Change', numeric: true },
                    ],
                    rows: rows.map((r) => [
                      r.topic.name,
                      pctLabel(r.topic.share_a ?? 0),
                      pctLabel(r.topic.share_b ?? 0),
                      `${fmt(r.topic.meetings_a)} / ${fmt(r.topic.meetings_b)}`,
                      changeLabel(r.change),
                    ]),
                  }}
                />
              )}
            </>
          )}
        </div>
      </section>
    </div>
  )
}
