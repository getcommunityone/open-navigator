import { useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import type { StoryData, StoryScope, StoryScreen, ScreenText, StoryStatus } from '../../utils/dataStory'
import { chartScopeLabel, contextSourceFor, statsScopeNote, storyScopeLabel, storyStats } from '../../utils/dataStory'
import ChartPanel from './ChartPanel'
import ScreenNav from './ScreenNav'
import StatRow from './StatRow'

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
  /** Closing screen links, with the scope already in them. */
  links: { challenge: string; dataCenters: string; decisions: string }
}

/** One screen of a story: the short word, the headline, one line of context and the chart (or counts, or links) beside it. */
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
  const closing = screen.kind === 'closing'

  return (
    <section
      className="stance-panel stance-act"
      data-panel={p.index}
      data-screen={screen.id}
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
              {text.headline}
            </h2>
            <p className="stance-lede">
              {text.context}
            </p>
          </div>
          {(text.empty || text.failed) && broaden}
          <ScreenNav ref={nextRef} nextLabel={p.nextLabel} onNext={p.onNext} onPrev={p.onPrev} />
        </div>
        <div className="stance-right" ref={rightRef}>
          {screen.kind === 'overview' ? (
            stats.length > 0 ? (
              <>
                <StatRow stats={stats} label={`What the records cover: ${storyScopeLabel(scope)}`} roll={p.active} />
                <p className="stance-note">{statsScopeNote(stats, scope)}</p>
              </>
            ) : (
              <p className="stance-nodata" role="status">
                {text.failed ? 'The counts could not be loaded right now.' : 'No counts available for this place.'}
              </p>
            )
          ) : closing ? (
            <ul className="stance-links">
              <li>
                <Link className="stance-link-card is-primary" to={p.links.challenge}>
                  <b>Take the Data Center Challenge</b>
                  <span>Agree, disagree or not sure, then see how people who played answered.</span>
                </Link>
              </li>
              <li>
                <Link className="stance-link-card" to={p.links.dataCenters}>
                  <b>Open the Data centers page</b>
                  <span>Every site, claim and meeting passage behind this story, for {storyScopeLabel(scope)}.</span>
                </Link>
              </li>
              <li>
                <Link className="stance-link-card" to={p.links.decisions}>
                  <b>See decisions {scope.stateName ? `in ${storyScopeLabel(scope)}` : 'nationwide'}</b>
                  <span>Decisions local governments made, filtered to the same place.</span>
                </Link>
              </li>
            </ul>
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
