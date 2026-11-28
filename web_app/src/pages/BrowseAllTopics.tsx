import { useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchTopicsYoy, type YoyResponse } from '../api/topicsYoy'
import { fetchRankingTopics, type RankingTopicSummary } from '../api/rankings'
import DumbbellRows, { type DumbbellRow } from '../components/stance/DumbbellRows'
import { DataTable } from '../components/matrix/SectionShell'
import { pctLabel } from '../utils/storyTimeline'
import { STATE_CODE_TO_NAME } from '../utils/stateMapping'
import {
  changeLabel,
  filterTopics,
  parseTopicFilter,
  parseYoySort,
  heatColumnLabel,
  scopeQuery,
  splitTopics,
  topicDestination,
  yearBLabel,
  type YoyMetric,
  type YoySort,
  type YoyTopicFilter,
} from '../utils/topicsYoy'
import { useDocumentTitle } from '../utils/useDocumentTitle'
import { HOUSE_STYLE } from '../utils/houseTheme'
import '../styles/folio.css'
import '../components/stance/storyCharts.css'

const fmt = (n: number) => n.toLocaleString('en-US')
const countLabel = (v: number) => fmt(Math.round(v))

const FILTER_LABEL: Record<YoyTopicFilter, string> = {
  all: 'All major topics',
  candidates: 'Not yet a story',
  stories: 'Live stories',
}

/**
 * Browse all topics (#1343, #1361): one animated dumbbell across all major meeting topics (both curated stories and
 * CivicSearch meeting topics), last full year (hollow dot) against this year to date (filled dot). Supports filtering
 * to topics that do not have a story yet (`?show=candidates`) and sorting by biggest rise or most discussed
 * (`?sort=latest`) so you can spot which meeting topics to add next.
 */
export default function BrowseAllTopics() {
  useDocumentTitle('Browse all topics')
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const stateParam = (searchParams.get('state') || '').trim().toUpperCase() || undefined
  const cityParam = stateParam ? (searchParams.get('city') || '').trim() || undefined : undefined
  const filter = parseTopicFilter(searchParams.get('show'))
  const sort = parseYoySort(searchParams.get('sort'))
  const [metric, setMetric] = useState<YoyMetric>('share')
  const [tableOpen, setTableOpen] = useState(false)

  const q = useQuery<YoyResponse>({
    queryKey: ['topics-yoy', stateParam ?? '', cityParam ?? ''],
    queryFn: () => fetchTopicsYoy(stateParam, cityParam),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  const d = q.data

  // #1438: one-line "Where towns stand" summary per topic with ranked places. A failed fetch renders nothing.
  const rankQ = useQuery<RankingTopicSummary[]>({ queryKey: ['rankings-topics'], queryFn: fetchRankingTopics, staleTime: 5 * 60_000, retry: 0 })
  const rankedTopics = (rankQ.data ?? []).filter((t) => t.places_ranked > 0)
  const rankedTopicsShown = rankedTopics.filter((t) => (d?.topics ?? []).some((y) => y.topic_id === t.topic_id || y.slug === t.slug))

  // The label names the scope the data is actually filtered to: the API's normalised scope once loaded, else the URL's.
  const stateCode = d ? d.scope.state_code : (stateParam ?? null)
  const city = d ? d.scope.city : (cityParam ?? null)
  const stateName = stateCode ? (STATE_CODE_TO_NAME[stateCode] ?? stateCode) : null
  const scopeLabel = city ? `${city}, ${stateCode}` : (stateName ?? 'National')
  const here = scopeQuery(stateCode, city)
  const inPlace = city ? `in ${city}` : stateName ? `in ${stateName}` : 'nationally'

  const updateParam = (key: 'show' | 'sort', value: string, def: string) => {
    const next = new URLSearchParams(searchParams)
    if (value === def) next.delete(key)
    else next.set(key, value)
    setSearchParams(next, { replace: true })
  }

  const keepViewQuery = (targetState?: string | null, targetCity?: string | null) => {
    const p = new URLSearchParams(scopeQuery(targetState, targetCity))
    if (filter !== 'all') p.set('show', filter)
    if (sort !== 'change') p.set('sort', sort)
    const s = p.toString()
    return s ? `?${s}` : ''
  }

  const shown = useMemo(() => filterTopics(d?.topics ?? [], filter), [d, filter])
  const { rows, tooFew } = useMemo(() => splitTopics(shown, metric, sort), [shown, metric, sort])
  // Topics with no tagged meeting in either year share one line; the rest show their two counts.
  const untagged = tooFew.filter((t) => t.meetings_a === 0 && t.meetings_b === 0)
  const thin = tooFew.filter((t) => t.meetings_a > 0 || t.meetings_b > 0)
  const yA = d?.year_a ?? ''
  const yB = d ? yearBLabel(d) : ''
  const format = metric === 'share' ? pctLabel : countLabel

  const drawn: DumbbellRow[] = rows.map(({ topic: t, a, b, change }) => {
    const ch = changeLabel(change)
    const heat = heatColumnLabel(t)
    const heatAria = t.heat_mean != null ? `classifier heat ${t.heat_mean.toFixed(1)} of 5 from ${fmt(t.heat_rated ?? 0)} rated speakers` : 'too few speakers rated for heat'

    const counts = `${fmt(t.meetings_a)} of ${fmt(t.recorded_a)} meetings in ${yA}; ${fmt(t.meetings_b)} of ${fmt(t.recorded_b)} in ${yB}`
    const status = t.has_story ? 'Live story' : 'Not a story yet — opens Browse Topics'
    return {
      key: t.slug,
      label: t.name,
      a,
      b,
      right: sort === 'heat' ? heat : ch,
      negative: b < a,
      ariaLabel: `${t.name} (${t.has_story ? 'live story' : 'not a story yet'}): ${yA} ${format(a)}, ${yB} ${format(b)}, ${ch.replace('−', 'minus ')} change; ${heatAria}. ${counts}. ${t.has_story ? 'Opens the story.' : 'Opens meetings in Browse Topics.'}`,
      tip: {
        cat: t.name,
        val: sort === 'heat' ? `${heat} (${fmt(t.heat_rated ?? 0)} rated speakers)` : `${format(a)} → ${format(b)} (${ch})`,
        sub: `${counts} · ${status}`,
      },
    }
  })

  const open = (slug: string) => {
    const hit = shown.find((t) => t.slug === slug)
    if (hit) navigate(topicDestination(hit, stateCode, city))
  }
  const rising = rows.filter((r) => r.b > r.a).length
  const falling = rows.filter((r) => r.b < r.a).length
  const candidateRows = rows.filter((r) => !r.topic.has_story).length

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-6 sm:px-6">
      <div className="mb-3 text-sm">
        <Link to={`/browse-topics${here}`} className="font-medium text-primary-700 hover:underline">
          ← Browse topics
        </Link>
        {' · '}
        <Link to={`/where-towns-stand${stateParam ? `?state=${encodeURIComponent(stateParam)}` : ''}`} className="font-medium text-primary-700 hover:underline">
          Where towns stand
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
            <Link to={`/browse-topics/all${keepViewQuery(stateCode, null)}`}>All of {stateCode}</Link>
          )}
          {stateCode && <Link to={`/browse-topics/all${keepViewQuery(null, null)}`}>National</Link>}
        </div>

        <div className="sc-block" style={{ marginTop: 16 }}>
          <div className="sc-controls" style={{ flexWrap: 'wrap' }}>
            <div className="folio-seg sc-chips" role="group" aria-label="Which topics to include">
              {(['all', 'candidates', 'stories'] as const).map((k) => (
                <button
                  key={k}
                  type="button"
                  aria-pressed={filter === k}
                  onClick={() => updateParam('show', k, 'all')}
                >
                  {FILTER_LABEL[k]}
                </button>
              ))}
            </div>
            <div className="folio-seg sc-chips" role="group" aria-label="What the dots measure">
              <button type="button" aria-pressed={metric === 'share'} onClick={() => setMetric('share')}>
                Share of meetings
              </button>
              <button type="button" aria-pressed={metric === 'count'} onClick={() => setMetric('count')}>
                Meeting count
              </button>
            </div>
            <div className="folio-seg sc-chips" role="group" aria-label="Sort order">
              {(
                [
                  ['change', 'Biggest rise'],
                  ['latest', 'Most discussed'],
                  ['heat', 'Most heated'],
                ] as [YoySort, string][]
              ).map(([k, label]) => (
                <button
                  key={k}
                  type="button"
                  aria-pressed={sort === k}
                  onClick={() => updateParam('sort', k, 'change')}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          <p className="sc-h">
            {FILTER_LABEL[filter]} ·{' '}
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
              No {filter === 'candidates' ? 'candidate topics without a story' : filter === 'stories' ? 'live story topics' : 'topics'} can be compared for {scopeLabel} yet: each needs at least {d.min_meetings} meetings on the topic in both{' '}
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
                <b>{rising}</b> {rising === 1 ? 'topic is' : 'topics are'} up and <b>{falling}</b> down
                {filter === 'all' && candidateRows > 0 ? ` (${candidateRows} without a story yet)` : ''}. Hollow dot = {yA}, filled dot ={' '}
                {yB}; teal rises, ochre falls. Tap a row to open its story or meetings.
                {sort === 'heat' &&
                  ` Most heated: the mean heat (1-5) a classifier rated from public speakers' own words on the topic, all years, shown with at least ${d.min_heat_rated ?? 20} rated speakers; fewer says "too few rated".`}
              </p>
              <DumbbellRows
                title={`${rising} of ${rising + falling} topics compared rose from ${yA} to ${yB} · ${scopeLabel}`}
                rows={drawn}
                aName={yA}
                bName={yB}
                ariaLabel={`Dumbbell chart of ${FILTER_LABEL[filter].toLowerCase()}, ${yA} against ${yB}, ${scopeLabel}`}
                firstRows={60}
                unitPlural="topics"
                replayKey={`${stateCode ?? ''}|${city ?? ''}|${filter}`}
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
              Curated topics match hand-picked phrases (data centers from mentioned passages); major meeting topics match two or more distinct multi-word phrases in transcripts. A topic needs at least {d.min_meetings} meetings in each year to be compared.
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

          {rankedTopicsShown.length > 0 && (
            <div className="sc-note" data-testid="where-towns-stand-summary" style={{ maxWidth: 'none' }}>
              {/* The rankings are national (each ranked place against similar-sized places), whatever this page's scope. */}
              <p className="sc-h">Where towns stand · National</p>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                {rankedTopicsShown.map((t) => {
                  const lean =
                    t.places_leaning_against > t.places_leaning_for
                      ? `${t.places_leaning_against} of ${t.places_ranked} ranked places leaned against`
                      : t.places_leaning_for > t.places_leaning_against
                        ? `${t.places_leaning_for} of ${t.places_ranked} ranked places leaned for`
                        : `${t.places_ranked} ranked places were split`
                  return (
                    <li key={t.slug} style={{ padding: '2px 0' }}>
                      <Link to={`/where-towns-stand?${new URLSearchParams({ topic: t.slug, ...(stateParam ? { state: stateParam } : {}) })}`}>
                        {t.name}: {lean}
                      </Link>
                    </li>
                  )
                })}
              </ul>
            </div>
          )}

          {d && tooFew.length > 0 && (
            <div style={{ marginTop: 14 }}>
              <p className="sc-h">Too few meetings to compare</p>
              <ul className="sc-note" style={{ listStyle: 'none', padding: 0, maxWidth: 'none' }}>
                {thin.map((t) => (
                  <li key={t.slug} style={{ padding: '2px 0' }}>
                    <Link to={topicDestination(t, stateCode, city)}>{t.name}</Link> — {fmt(t.meetings_a)} in {yA},{' '}
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
                      <Link to={topicDestination(t, stateCode, city)}>{t.name}</Link>
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
                  caption={`Data table: ${FILTER_LABEL[filter].toLowerCase()}, ${yA} and ${yB}, ${scopeLabel}`}
                  spec={{
                    columns: [
                      { label: 'Topic' },
                      { label: 'Status' },
                      { label: `${yA} share`, numeric: true },
                      { label: `${yB} share`, numeric: true },
                      { label: `Meetings ${yA} / ${yB}`, numeric: true },
                      { label: metric === 'share' ? 'Share change' : 'Count change', numeric: true },
                    ],
                    rows: rows.map((r) => [
                      r.topic.name,
                      r.topic.has_story ? 'Live story' : 'Not a story yet',
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
