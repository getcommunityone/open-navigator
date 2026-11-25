import { useEffect, useRef } from 'react'
import type { StoryData, StoryScope, StoryScreen, ScreenText, StoryStatus } from '../../utils/dataStory'
import { chartScopeLabel, contextSourceFor, positionsLoaded, statsScopeNote, storyScopeLabel, storyStats } from '../../utils/dataStory'
import type { DataCenterMeetingMentionsResponse, DataCenterPositionsResponse } from '../../api/dataCenters'
import ChartPanel from './ChartPanel'
import PositionsBlock from './PositionsBlock'
import KineticText from './KineticText'
import ScreenNav from './ScreenNav'
import StatRow from './StatRow'
import StoryDotMap from './StoryDotMap'
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
}

/** One screen of the record: the short word, the headline, one line of context and the chart (or counts) beside it. */
export default function StoryScreenView(p: Props) {
  const { screen, text, scope } = p
  const leftRef = useRef<HTMLDivElement>(null)
  const rightRef = useRef<HTMLDivElement>(null)
  const nextRef = useRef<HTMLButtonElement>(null)

  // A column taller than its frame scrolls on its own: Lenis must leave wheel and touch over it alone, but only then.
  useEffect(() => {
    const els = [leftRef.current, rightRef.current].filter((e): e is HTMLDivElement => e != null)
    const mark = () => els.forEach((e) => e.toggleAttribute('data-lenis-prevent', e.scrollHeight > e.clientHeight + 1))
    mark()
    if (typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(mark)
    els.forEach((e) => ro.observe(e))
    return () => ro.disconnect()
  })

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

  return (
    <section
      className="stance-panel stance-act"
      data-panel={p.index}
      data-screen={screen.id}
      data-live={p.active ? '' : undefined}
      aria-labelledby={`story-h-${screen.id}`}
      aria-roledescription="screen"
      tabIndex={-1}
    >
      <span className="stance-word" aria-hidden="true">
        {screen.eyebrow}
      </span>
      <div className="stance-grid">
        <div className="stance-left" ref={leftRef}>
          <div className="stance-card">
            {screen.kicker && (
              <p className="stance-card-eyebrow">
                {screen.kicker} · source: {contextSourceFor(screen.chart)}
              </p>
            )}
            <p className="stance-card-title">{screen.eyebrow}</p>
          </div>
          <div className="stance-head">
            <h2 className="stance-headline" id={`story-h-${screen.id}`}>
              <KineticText text={text.headline} />
            </h2>
            <p className="stance-lede">
              {text.context}
            </p>
          </div>
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
          <ScreenNav ref={nextRef} nextLabel={p.nextLabel} onNext={p.onNext} onPrev={p.onPrev} />
        </div>
        <div className="stance-right" ref={rightRef}>
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
            stats.length > 0 ? (
              <>
                {stats.some((s) => s.key === 'meetings') && byState ? (
                  <StoryDotMap
                    byState={byState}
                    scopeStateCode={scope.stateCode ?? null}
                    scopeCity={scope.city ?? null}
                    scopeLabel={storyScopeLabel(scope)}
                    onPickState={(code) => p.onBroaden(code, null)}
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
                <StatRow stats={stats} label={`What the records cover: ${storyScopeLabel(scope)}`} roll={p.active} />
                <p className="stance-note">{statsScopeNote(stats, scope)}</p>
              </>
            ) : (
              <p className="stance-nodata" role="status">
                {text.failed ? 'The counts could not be loaded right now.' : 'No counts available for this place.'}
              </p>
            )
          ) : (
            <ChartPanel
              chartKey={String(screen.chart)}
              round={p.index}
              enabled
              stateCode={scope.stateCode}
              stateName={scope.stateName}
              city={scope.city}
              scopeLabel={chartScopeLabel(String(screen.chart), scope)}
            />
          )}
        </div>
      </div>
    </section>
  )
}
