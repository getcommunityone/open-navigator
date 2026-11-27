import type { StoryData, StoryScope, StoryScreen, ScreenText, StoryStatus } from '../../utils/dataStory'
import { chartScopeLabel, contextSourceFor, positionsLoaded, statsScopeNote, storyScopeLabel, storyStats } from '../../utils/dataStory'
import type { AreaConcernsResponse, DataCenterMeetingMentionsResponse, DataCenterPositionsResponse, JobClaimsResponse } from '../../api/dataCenters'
import ChartPanel from './ChartPanel'
import PayrollJobsPanel from './PayrollJobsPanel'
import PositionsBlock from './PositionsBlock'
import StoryScreenFrame from './StoryScreenFrame'
import StatRow from './StatRow'
import StoryDotMap from './StoryDotMap'
import DumbbellChart from './DumbbellChart'
import ConcernsDumbbell from './ConcernsDumbbell'
import StoryCountyMap from './StoryCountyMap'
import MapDrill from './MapDrill'
import StoryStatement from './StoryStatement'
import type { ScreenStatement } from './useStoryStatements'
import { speakerCounts } from '../../utils/stanceGame'

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
}

/** One screen of the record: the short word, the headline, one line of context and the chart (or counts) beside it. */
export default function StoryScreenView(p: Props) {
  const { screen, text, scope } = p

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
  const jobsData = p.data['job-claims'] as JobClaimsResponse | null | undefined
  const noClaims = (jobsData?.totals?.construction ?? 0) + (jobsData?.totals?.operations ?? 0) === 0

  return (
    <StoryScreenFrame
      id={screen.id}
      index={p.index}
      active={p.active}
      eyebrow={screen.eyebrow}
      kicker={screen.kicker ? `${screen.kicker} · source: ${contextSourceFor(screen.chart)}` : undefined}
      headline={text.headline}
      context={text.context}
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
                stats.length > 0 ? (
                  <>
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
                        passages={mentions?.items}
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
                  </>
                ) : (
                  <p className="stance-nodata" role="status">
                    {text.failed ? 'The counts could not be loaded right now.' : 'No counts available for this place.'}
                  </p>
                )
              }
            </MapDrill>
          ) : screen.chart === 'concerns' ? (
            // The concerns dumbbell (#1209): the place's share of mentions against the nation's, or one dot each nationally.
            <ConcernsDumbbell
              data={p.data.concerns as AreaConcernsResponse | null | undefined}
              status={p.status.concerns ?? 'loading'}
              place={chartScopeLabel('concerns', scope) === 'National' ? null : chartScopeLabel('concerns', scope)}
              idBase={`story-${screen.id}`}
            />
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
      {(p.question || p.said) && (
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
