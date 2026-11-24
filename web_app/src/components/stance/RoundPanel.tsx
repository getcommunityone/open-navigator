import { useEffect, useRef } from 'react'
import type { StanceAnswer, StanceStatement, StatementResults } from '../../api/stance'
import { chartScopeLabel, contextSourceFor, landConcernNote } from '../../utils/dataStory'
import type { AreaConcernsResponse } from '../../api/dataCenters'
import { ANSWER_LABEL, chartTitle, findingFor, placeLabel, roundHeadline } from '../../utils/stanceGame'
import ChartPanel, { useChartData } from './ChartPanel'
import ResultBars from './ResultBars'
import ScreenNav from './ScreenNav'

export interface RoundScope {
  stateCode: string | undefined
  stateName: string | null
  city: string | null
}

interface Props {
  statement: StanceStatement
  /** 0-based position. */
  index: number
  total: number
  /** The panel is the one in view. */
  active: boolean
  /** A neighbour of the one in view: its chart data loads. */
  near: boolean
  scope: RoundScope
  results: StatementResults | undefined
  resultsLoading: boolean
  resultsFailed: boolean
  minSample: number | null
  /** The answer the API has confirmed for this player, or null. */
  answer: StanceAnswer | null
  posting: boolean
  error: string | null
  changing: boolean
  onAnswer: (a: StanceAnswer) => void
  onRetry: () => void
  onChange: () => void
  /** The category of the screen after this one, in words ("Concerns"). */
  nextLabel: string
  /** Absent on the first round. */
  onPrev?: () => void
  onNext: () => void
}

const ORDER: StanceAnswer[] = ['agree', 'disagree', 'unsure']
const KEY: Record<StanceAnswer, string> = { agree: 'A', disagree: 'D', unsure: 'N' }

/** One round: category card and big round word, the finding, the statement and answers, then the reveal; chart on the right. */
export default function RoundPanel(p: Props) {
  const { statement, index, scope } = p
  const round = index + 1
  const chart = useChartData(String(statement.chart), p.near, scope.stateCode, scope.city)
  // The place the chart really shows: the city where the source can narrow to one, otherwise the state, otherwise national.
  const chartScope = chartScopeLabel(String(statement.chart), { stateName: scope.stateName, city: scope.city })
  const finding = findingFor(String(statement.chart), chart.data, chartScope === 'National' ? null : chartScope)
  // The round about homes and land use also notes how often land and property concerns appear (only when the data has them).
  const landNote =
    statement.statement_id === 'near-homes-ok' && String(statement.chart) === 'concerns'
      ? landConcernNote(chart.data as AreaConcernsResponse | undefined, chartScope === 'National' ? null : chartScope)
      : null
  const headline = roundHeadline(String(statement.chart), finding)
  const nextRef = useRef<HTMLButtonElement>(null)
  const leftRef = useRef<HTMLDivElement>(null)
  const rightRef = useRef<HTMLDivElement>(null)

  // A column that is taller than its frame scrolls on its own: tell Lenis to leave wheel and touch over it alone,
  // but only while it really overflows (otherwise the wheel must drive the page).
  const markOverflow = useRef<() => void>(() => {})
  // Content can shrink without the column's box changing, so re-check after every render as well.
  useEffect(() => markOverflow.current())
  useEffect(() => {
    const els = [leftRef.current, rightRef.current].filter((e): e is HTMLDivElement => e != null)
    const mark = () => els.forEach((e) => e.toggleAttribute('data-lenis-prevent', e.scrollHeight > e.clientHeight + 1))
    markOverflow.current = mark
    mark()
    if (typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(mark)
    els.forEach((e) => ro.observe(e))
    return () => ro.disconnect()
  }, [])
  const revealed = p.answer != null && !p.changing
  const showButtons = p.answer == null || p.changing

  // After a confirmed answer, move focus to "Continue" so Enter carries on (only for the round in view).
  const was = useRef<StanceAnswer | null>(p.answer)
  useEffect(() => {
    if (p.active && was.current == null && p.answer != null) nextRef.current?.focus({ preventScroll: true })
    was.current = p.answer
  }, [p.answer, p.active])

  const label = placeLabel(scope.stateName, scope.city)

  return (
    <section
      className="stance-panel stance-act"
      data-panel={index}
      aria-labelledby={`stance-q-${round}`}
      aria-roledescription="round"
    >
      <span className="stance-word" aria-hidden="true">
        {statement.category}
      </span>
      <div className="stance-grid">
        <div className="stance-left" ref={leftRef}>
          <div className="stance-card">
            <p className="stance-card-title">{statement.category}</p>
          </div>
          <div className="stance-head">
            <h2 className="stance-headline" id={`stance-q-${round}`}>
              {headline.text}
            </h2>
            {headline.isFinding && (
              <p className="stance-context">
                {chartTitle(String(statement.chart))} · {chartScope}
                {landNote ? ` · ${landNote}` : ''}
              </p>
            )}
          </div>
          <div className="stance-qblock">
          <p className="stance-ask">Agree or disagree?</p>
          <p className="stance-statement">{statement.statement}</p>

          {showButtons && (
            <div className="stance-answers" role="group" aria-label={`Your answer: ${statement.category}`}>
              {ORDER.map((a) => (
                <button
                  key={a}
                  type="button"
                  className={`stance-answer stance-answer-${a}`}
                  disabled={p.posting}
                  aria-pressed={p.changing ? p.answer === a : undefined}
                  onClick={() => p.onAnswer(a)}
                >
                  <span>{ANSWER_LABEL[a]}</span>
                  {p.active && <kbd aria-hidden="true">{KEY[a]}</kbd>}
                </button>
              ))}
            </div>
          )}
          {p.posting && (
            <p className="folio-muted" role="status">
              Saving your answer…
            </p>
          )}
          {p.error && (
            <div className="stance-error" role="alert">
              <span>{p.error}</span>
              <button type="button" className="folio-btn" onClick={p.onRetry} disabled={p.posting}>
                Retry
              </button>
            </div>
          )}

          </div>

          <div className="stance-reveal" aria-live="polite" aria-atomic="false">
            {!revealed && p.answer == null && (
              <p className="stance-note">Answer above to see how people who played answered.</p>
            )}
            {revealed && (
              <>
                <p className="stance-yours">
                  Your answer: <b>{ANSWER_LABEL[p.answer!]}</b>{' '}
                  <button type="button" className="folio-link-btn" onClick={p.onChange}>
                    Change my answer
                  </button>
                </p>
                {p.results ? (
                  <div className="stance-reveal-body">
                    <p className="stance-reveal-head">How people who played answered · showing {label}</p>
                    <ResultBars title="Nationally" group={p.results.national} minSample={p.minSample} yourAnswer={p.answer} play={p.active} />
                    <ResultBars
                      title={scope.stateName ? `In ${scope.stateName}` : 'In your state'}
                      group={p.results.state}
                      minSample={p.minSample}
                      yourAnswer={p.answer}
                      play={p.active}
                      missing="Choose your state to see this group."
                    />
                    <ResultBars
                      title={scope.city && scope.stateName ? `In ${scope.city}, ${scope.stateName}` : 'In your community'}
                      group={p.results.place}
                      minSample={p.minSample}
                      yourAnswer={p.answer}
                      play={p.active}
                      missing={scope.stateName ? 'Add your community to see this group.' : 'Choose your state and community to see this group.'}
                    />
                    <p className="stance-note">This is how people who played answered. It is not a poll.</p>
                  </div>
                ) : (
                  <p className="folio-muted" role="status">
                    {p.resultsFailed ? 'Results could not be loaded right now.' : p.resultsLoading ? `Loading how people answered for ${label}…` : ''}
                  </p>
                )}
              </>
            )}
          </div>

          <ScreenNav ref={nextRef} nextLabel={p.nextLabel} onNext={p.onNext} onPrev={p.onPrev} />
        </div>
        <div className="stance-right" ref={rightRef}>
          {contextSourceFor(String(statement.chart)) && (
            <p className="stance-kicker">For context · source: {contextSourceFor(String(statement.chart))} (not from meeting recordings)</p>
          )}
          <ChartPanel
            chartKey={String(statement.chart)}
            round={round}
            enabled={p.near}
            stateCode={scope.stateCode}
            stateName={scope.stateName}
            city={scope.city}
            scopeLabel={chartScope}
          />
        </div>
      </div>
    </section>
  )
}
