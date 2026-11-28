import { useState, type ReactNode } from 'react'
import { useMediaQuery } from '../../hooks/useMediaQuery'
import { summaryStats } from '../../utils/storySummary'
import { useQuery } from '@tanstack/react-query'
import type { StoryData, StoryScope, StoryScreen, ScreenText, StoryStatus } from '../../utils/dataStory'
import { chartScopeLabel, contextSourceFor, positionsLoaded, statsScopeNote, storyScopeLabel, storyStats } from '../../utils/dataStory'
import type { DataCenterMeetingMentionsResponse, DataCenterPositionsResponse, DataCenterProjectsResponse, JobClaimsResponse } from '../../api/dataCenters'
import { fetchDataCenterMeetingMentions } from '../../api/dataCenters'
import ChartPanel from './ChartPanel'
import PayrollJobsPanel from './PayrollJobsPanel'
import PositionsBlock from './PositionsBlock'
import StoryScreenFrame from './StoryScreenFrame'
import StatRow from './StatRow'
import StoryDotMap from './StoryDotMap'
import DumbbellChart from './DumbbellChart'
import StoryCountyMap from './StoryCountyMap'
import MapSkeleton, { NATIONAL_MAP_ASPECT, useStateAspect } from './MapSkeleton'
import { COUNTIES_ALBERS_TOPO, STATES_ALBERS_TOPO, fetchTopo } from '../../lib/dotMatrix'
import MapDrill from './MapDrill'
import StoryStatement from './StoryStatement'
import type { ScreenStatement } from './useStoryStatements'
import { speakerCounts, statusLabel, tally } from '../../utils/stanceGame'
import ScreenBoxes from './ScreenBoxes'
import { useChartData } from './ChartPanel'
import { chartSpec } from '../../utils/stanceGame'
import { specDisplay } from '../../utils/displayFit'
import { GROUP_COLORS } from '../../utils/houseTheme'
import { jobClaimsBoxes, positionsBoxes, statusBoxes, type BoxesSpec } from '../../utils/screenBoxes'

interface Props {
  screen: StoryScreen
  index: number
  text: ScreenText
  data: StoryData
  status: StoryStatus
  scope: StoryScope
  active: boolean
  nextLabel: string | null
  onPrev?: () => void
  onNext: () => void
  /** Broaden the place: to the state (null when none is chosen) or to the whole country. */
  onBroaden: (stateCode: string | null, city: string | null) => void
  onRetry: () => void
  /** The statement this screen asks (#981): Agree / Disagree / Not sure, then where the reader sits. */
  stance?: ScreenStatement
  /** Overview only (#1134): the story's question worded for the place, and the reader's answer before reading, which the
   * retired Where screen used to show. */
  question?: string | null
  said?: string | null
  /** Overview only (#1282): the opening's subhead, basis and points, under the headline in the left column. */
  lead?: ReactNode
}

/**
 * The box strip of a chart screen whose own figure is a list or a sentence (a few records, #1289): the same cached dataset, one
 * box per record by its group. Screens that already draw boxes (the unit matrix, the box waffle) get none, so there is one visual.
 */
function ChartScreenBoxes({ chartKey, scope }: { chartKey: string; scope: StoryScope }) {
  const q = useChartData(chartKey, true, scope.stateCode, scope.city)
  const spec = q.data ? chartSpec(chartKey, q.data, scope.stateName, undefined) : null
  if (!spec) return null
  const kind = specDisplay(spec).display.kind
  const small = specDisplay(spec).rows.reduce((n, r) => n + r.count, 0) < 20
  if (kind !== 'list' && kind !== 'sentence' && kind !== 'line' && !((kind === 'bars' || kind === 'top-bars') && small)) return null
  const place = storyScopeLabel(scope)
  const groups = spec.groups.map((g, i) => ({ key: g.key, label: g.label, count: g.total ?? g.shown, color: GROUP_COLORS[i % GROUP_COLORS.length]! }))
  const total = groups.reduce((n, g) => n + g.count, 0)
  return (
    <ScreenBoxes
      spec={{ title: total > 0 ? `${place}: ${total.toLocaleString('en-US')} ${total === 1 ? spec.unit : `${spec.unit}s`} on record` : `No ${spec.unit}s on record in ${place}`, unit: `${spec.unit}s`, groups }}
    />
  )
}

/** One screen of the record: the short word, the headline, one line of context and the chart (or counts) beside it. */
export default function StoryScreenView(p: Props) {
  const { screen, text, scope } = p
  const phone = useMediaQuery('(max-width: 767px)')
  const [mapOpen, setMapOpen] = useState(false)

  const broaden = (
    <div className="stance-broaden">
      {text.failed && (
        <button type="button" className="folio-btn" onClick={p.onRetry}>
          Try again
        </button>
      )}
      {text.empty && scope.city && scope.stateName && (
        <button type="button" className="folio-btn" onClick={() => p.onBroaden(scope.stateCode ?? null, null)}>
          Show all of {scope.stateName}
        </button>
      )}
      {text.empty && scope.stateName && (
        <button type="button" className="folio-btn" onClick={() => p.onBroaden(null, null)}>
          Show national data
        </button>
      )}
    </div>
  )

  const stats = screen.kind === 'overview' ? storyStats(p.data, scope) : []
  // The Overview map (#970) needs the per-state counts; an older API without them keeps the dot chart.
  const mentions = p.data['meeting-mentions'] as DataCenterMeetingMentionsResponse | null | undefined
  const byState = mentions?.counts?.by_state
  const byPlace = mentions?.counts?.by_place
  // The national map's hover quote (#1230): each state's map-quote meeting (real public meetings only, meetings where the
  // public mostly opposed first, then newest), not the newest passage, which can be a briefing or a keyword-only mention.
  // The same query as the home map, so it is cached. A failure falls back to the scope's passages.
  const overviewNational = screen.kind === 'overview' && !scope.stateCode
  const mapQuotes = useQuery({
    queryKey: ['home', 'story-map', 'meeting-mentions', 'quotes-per-state', 3],
    queryFn: () => fetchDataCenterMeetingMentions({ quotesPerState: 3 }),
    enabled: overviewNational,
    staleTime: 5 * 60_000,
    retry: 1,
  })
  const nationalPassages = mapQuotes.data?.items ?? mentions?.items
  // The Overview's map and the counts beside it wait for this scope's place counts (#1328): until then one quiet box of
  // the map's size, so no other scope's map, no stray stats, and nothing jumps when the map arrives.
  const stateAspect = useStateAspect(screen.kind === 'overview' ? scope.stateCode : null)
  const mentionsState = p.status['meeting-mentions'] ?? 'loading'
  // The map's shapes too (the same cached queries the maps use), so the counts below never show before the map does.
  const isOverview = screen.kind === 'overview'
  const shapes = useQuery({
    queryKey: scope.stateCode ? ['us-atlas-counties-albers'] : ['us-atlas-states-albers'],
    queryFn: () => fetchTopo(scope.stateCode ? COUNTIES_ALBERS_TOPO : STATES_ALBERS_TOPO),
    enabled: isOverview,
    staleTime: 1000 * 60 * 60,
  })
  const overviewMapLoading =
    mentionsState === 'loading' ||
    (mentionsState === 'ready' && (scope.stateCode ? byPlace == null : byState == null)) ||
    (isOverview && shapes.isPending)
  const jobsData = p.data['job-claims'] as JobClaimsResponse | null | undefined
  // Phones (#1337): the Overview opens as a one-glance summary (real facts, a map thumbnail); the full map is one tap on.
  const summary = phone && screen.kind === 'overview' && !text.empty && !text.failed && stats.length > 0 && !mapOpen
  const facts = summary ? summaryStats(stats, p.data.positions as DataCenterPositionsResponse | null | undefined, scope) : []
  const noClaims = (jobsData?.totals?.construction ?? 0) + (jobsData?.totals?.operations ?? 0) === 0

  // The screen's own box strip (#1415), from the data its chart already loaded; the other chart screens draw theirs in the chart.
  const place = storyScopeLabel(scope)
  let boxSpec: BoxesSpec | null = null
  if (screen.chart === 'positions') {
    const pos = p.data.positions as DataCenterPositionsResponse | null | undefined
    boxSpec = pos?.available ? positionsBoxes(pos.totals, place) : null
  } else if (screen.chart === 'projects') {
    const pr = p.data.projects as DataCenterProjectsResponse | null | undefined
    boxSpec = pr ? statusBoxes(tally(pr.items ?? [], (x) => statusLabel(x.status)), 'projects', place) : null
  } else if (screen.chart === 'job-claims') {
    boxSpec = jobClaimsBoxes(jobsData?.totals, place)
  }

  return (
    <StoryScreenFrame
      boxes={boxSpec ? <ScreenBoxes spec={boxSpec} /> : screen.kind === 'chart' && screen.chart && !['positions', 'projects', 'job-claims'].includes(screen.chart) ? <ChartScreenBoxes chartKey={String(screen.chart)} scope={scope} /> : null}
      id={screen.id}
      index={p.index}
      active={p.active}
      eyebrow={screen.eyebrow}
      kicker={screen.kicker ? `${screen.kicker} · source: ${contextSourceFor(screen.chart)}` : undefined}
      headline={text.headline}
      context={summary ? '' : text.context}
      glance={summary}
      nextLabel={p.nextLabel}
      onNext={p.onNext}
      onPrev={p.onPrev}
      right={
        <>
          {screen.chart === 'positions' ? (
            // While the table is not loaded the screen's own line says so; the figure is left out, not repeated.
            (p.status.positions ?? 'loading') !== 'loading' && !positionsLoaded(p.data.positions as DataCenterPositionsResponse | null | undefined) ? null : (
            <PositionsBlock
              data={p.data.positions as DataCenterPositionsResponse | null | undefined}
              status={p.status.positions ?? 'loading'}
              scope={scope}
              labelledBy={`story-h-${screen.id}`}
              quotes
            />
            )
          ) : screen.kind === 'overview' ? (
            // Narrowing to a state, its boxes re-form into the county map; broadening plays it back (#1195). The wrapper stays
            // mounted while the new scope's counts load, so the transition can wait for the county map.
            <div
              className={summary ? 'story-summary-thumb' : undefined}
              data-testid={summary ? 'story-summary-map' : undefined}
              onClick={summary ? (e) => { if ((e.target as HTMLElement).closest('.stance-map-title')) setMapOpen(true) } : undefined}
            >
            {phone && mapOpen && (
              <button type="button" className="folio-link-btn story-summary-back" onClick={() => setMapOpen(false)}>
                ← Summary
              </button>
            )}
            <div className={summary ? 'story-summary-thumb-map' : undefined}>
            <MapDrill
              stateCode={scope.stateCode ?? null}
              byState={byState}
              county={
                !scope.stateCode || p.status['meeting-mentions'] === 'error'
                  ? 'none'
                  : byPlace == null
                    ? 'loading'
                    : byPlace.length > 0
                      ? 'ready'
                      : 'none'
              }
            >
              {(beforePick) =>
                overviewMapLoading ? (
                  <MapSkeleton aspect={scope.stateCode ? stateAspect : NATIONAL_MAP_ASPECT} label={`Loading the map of ${storyScopeLabel(scope)}`} />
                ) : stats.length > 0 ? (
                  // The map, its caption and the counts arrive together, in one short fade (#1328).
                  <div className="map-fade-in">
                    {stats.some((s) => s.key === 'meetings') && scope.stateCode && byPlace && byPlace.length > 0 ? (
                      // At state scope, the state's counties (#1039), like the Census map's state drill-down.
                      <StoryCountyMap
                        stateCode={scope.stateCode}
                        scopeCity={scope.city ?? null}
                        scopeLabel={storyScopeLabel(scope)}
                        byPlace={byPlace}
                        onPickState={(code) => {
                          beforePick(code)
                          p.onBroaden(code, null)
                        }}
                        labelledBy={`story-h-${screen.id}`}
                        passages={mentions?.items}
                      />
                    ) : stats.some((s) => s.key === 'meetings') && byState ? (
                      <StoryDotMap
                        byState={byState}
                        scopeStateCode={scope.stateCode ?? null}
                        scopeCity={scope.city ?? null}
                        scopeLabel={storyScopeLabel(scope)}
                        onPickState={(code) => {
                          beforePick(code)
                          p.onBroaden(code, null)
                        }}
                        labelledBy={`story-h-${screen.id}`}
                        passages={nationalPassages}
                      />
                    ) : stats.some((s) => s.key === 'meetings') && (
                      <ChartPanel
                        chartKey="meeting-mentions"
                        view="meetings"
                        round={p.index}
                        enabled
                        stateCode={scope.stateCode}
                        stateName={scope.stateName}
                        city={scope.city}
                        scopeLabel={storyScopeLabel(scope)}
                      />
                    )}
                    {!summary && (<>
                    {/* The period dumbbell (#1192, owner: "earlier in every story"): last year against this year, by state, or
                        by town at state scope, right under the map. It compares places, so at city scope it says where to see it. */}
                    {scope.city ? (
                      <p className="stance-note">
                        The year-over-year comparison is drawn by state, or by town within a state; choose All of {scope.stateName} to see it.
                      </p>
                    ) : (
                      <DumbbellChart topic="data-centers" stateCode={scope.stateCode} scopeLabel={storyScopeLabel(scope)} subject="data centers" idBase={`story-${screen.id}`} />
                    )}
                    <StatRow stats={stats} label={`What the records cover: ${storyScopeLabel(scope)}`} roll={p.active} />
                    <p className="stance-note">{statsScopeNote(stats, scope)}</p>
                    </>)}
                  </div>
                ) : (
                  <p className="stance-nodata" role="status">
                    {text.failed ? 'The counts could not be loaded right now.' : 'No counts available for this place.'}
                  </p>
                )
              }
            </MapDrill>
            </div>
            </div>
          ) : screen.chart === 'job-claims' && jobsData && noClaims ? (
            // No claims on record: the screen shows actual payroll jobs and where jobs are tracked instead (#1019).
            <PayrollJobsPanel data={jobsData} />
          ) : (
            <>
              <ChartPanel
                chartKey={String(screen.chart)}
                round={p.index}
                enabled
                stateCode={scope.stateCode}
                stateName={scope.stateName}
                city={scope.city}
                scopeLabel={chartScopeLabel(String(screen.chart), scope)}
              />
              {screen.chart === 'job-claims' && jobsData && <PayrollJobsPanel data={jobsData} />}
            </>
          )}
        </>
      }
    >
      {summary && facts.length > 0 && (
        <ul className="story-summary" data-testid="story-summary" aria-label={`At a glance: ${storyScopeLabel(scope)}`}>
          {facts.map((f) => (
            <li key={f.label}>
              <b>{f.value}</b>
              <span>{f.label}</span>
            </li>
          ))}
        </ul>
      )}
      {!summary && p.lead}
      {!summary && (p.question || p.said) && (
        <div className="stance-qblock">
          {p.question && (
            <p className="stance-statement" data-testid="scope-question">
              {p.question}
            </p>
          )}
          {p.said && (
            <p className="stance-yours">
              You said <b>{p.said}</b>.
            </p>
          )}
        </div>
      )}
      {(text.empty || text.failed) && broaden}
      {/* Asked only when the screen has a record to react to: no statement under "No data available". */}
      {p.stance && !text.empty && !text.failed && (
        <StoryStatement
          s={p.stance}
          scope={scope}
          speakers={speakerCounts(p.data.positions as DataCenterPositionsResponse | null | undefined)}
          id={`story-q-${screen.id}`}
        />
      )}
    </StoryScreenFrame>
  )
}
