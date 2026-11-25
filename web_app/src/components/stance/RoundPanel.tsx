import { useEffect, useRef, useState } from 'react'
import type { StanceAnswer, StanceStatement, StatementResults } from '../../api/stance'
import { chartScopeLabel, contextSourceFor, landConcernNote } from '../../utils/dataStory'
import type { AreaConcernsResponse } from '../../api/dataCenters'
import {
  ANSWER_LABEL,
  BAR_FIRST_MS,
  BAR_GAP_MS,
  LOCK_HOLD_MS,
  askAfterMs,
  chartTitle,
  findingFor,
  placeLabel,
  resultBars,
  roundBeat,
  roundHeadline,
} from '../../utils/stanceGame'
import type { RoundStop } from '../../utils/stanceGame'
import type { Cue } from '../../utils/stanceSound'
import { usePrefersReducedMotion } from '../../hooks/usePrefersReducedMotion'
import ChartPanel, { useChartData } from './ChartPanel'
import KineticText from './KineticText'
import ResultBars from './ResultBars'
import ScreenNav from './ScreenNav'
import SidesBlock, { type Sides } from './SidesBlock'
import { useAskTimer } from './useAskTimer'

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
  /** The round is really on screen (it is the active one, the cover has gone and the stored answers are known): its beats run. */
  playing: boolean
  /** A neighbour of the one in view: its chart data loads. */
  near: boolean
  scope: RoundScope
  results: StatementResults | undefined
  resultsLoading: boolean
  resultsFailed: boolean
  minSample: number | null
  /** The answer the API has confirmed for this player, or null. */
  answer: StanceAnswer | null
  /** The answer being saved right now (it shows locked), or null. */
  pendingAnswer: StanceAnswer | null
  posting: boolean
  error: string | null
  changing: boolean
  /** The player has asked for the question on this visit (the "Ask me" button, Space, or the pause running out). */
  asked: boolean
  onAsk: () => void
  /** Pause the automatic question (a popover is open). */
  paused?: boolean
  /** Make a sound cue; a no-op when sound is off. */
  onCue: (cue: Cue, step?: number) => void
  /** Verbatim quotes from public meetings, when a source supplies them. Nothing is shown without both sides. */
  sides?: Sides
  onAnswer: (a: StanceAnswer) => void
  onRetry: () => void
  onChange: () => void
  /** The category of the screen after this one, in words ("Concerns"). */
  nextLabel: string
  /** Absent on the first round. */
  onPrev?: () => void
  onNext: () => void
  /** Page-level scroll to a stop (e.g. pinned holds); optional until Challenge wires acts.goToStop. */
  onNeedPageScroll?: (stop: RoundStop) => void
}

const ORDER: StanceAnswer[] = ['agree', 'disagree', 'unsure']
const KEY: Record<StanceAnswer, string> = { agree: 'A', disagree: 'D', unsure: 'N' }

function scrollToStop(root: HTMLElement | null, stop: RoundStop, smooth: boolean) {
  const el = root?.querySelector<HTMLElement>(`[data-stop="${stop}"]`)
  el?.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto', block: 'start' })
}

/**
 * One round, in three scroll stops: (1) the category and the finding with the chart; (2) the statement and stacked answers
 * below the fold; (3) the chosen answer and how people who played answered. Answers live only on the question stop.
 */
export default function RoundPanel(p: Props) {
  const { statement, index, scope } = p
  const round = index + 1
  const reduced = usePrefersReducedMotion()
  const panelRef = useRef<HTMLElement>(null)
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
  const rightRef = useRef<HTMLDivElement>(null)
  const barRef = useRef<HTMLSpanElement>(null)

  // --- the beat ---------------------------------------------------------------------------------------------------------
  const rawBeat = roundBeat({ answered: p.answer != null, asked: p.asked, changing: p.changing })
  // A fresh answer shows locked for a moment before the results land. A round that is already answered when it is shown goes straight to results.
  const [holdLock, setHoldLock] = useState(false)
  const [fresh, setFresh] = useState(false)
  // Derived while rendering (not in an effect) so the results never show for a frame before the lock.
  const [prevRaw, setPrevRaw] = useState(rawBeat)
  if (prevRaw !== rawBeat) {
    setPrevRaw(rawBeat)
    if (prevRaw === 'question' && rawBeat === 'results') {
      setFresh(true)
      setHoldLock(true)
    } else if (rawBeat !== 'results') {
      setFresh(false)
    }
  }
  useEffect(() => {
    if (!holdLock) return
    const t = window.setTimeout(() => setHoldLock(false), reduced ? 300 : LOCK_HOLD_MS)
    return () => window.clearTimeout(t)
  }, [holdLock, reduced])
  const beat = holdLock ? 'question' : rawBeat
  const chosen: StanceAnswer | null = p.pendingAnswer ?? (holdLock ? p.answer : null)
  const showButtons = beat === 'question'
  const revealed = beat === 'results'

  const showQuestionStop = beat !== 'finding' || p.asked || p.answer != null
  const showRevealStop = beat === 'results' || (p.answer != null && !p.changing)

  // The chart draws once, the first time the round plays and is still at the finding.
  const [drawn, setDrawn] = useState(false)
  useEffect(() => {
    if (p.playing && rawBeat === 'finding') setDrawn(true)
  }, [p.playing, rawBeat])
  const chartMode = drawn ? 'is-played' : p.answer != null || p.asked ? 'is-still' : ''

  // Cues with a visible counterpart: the finding rising in (open), the question arriving (question).
  const beatRef = useRef(rawBeat)
  beatRef.current = rawBeat
  useEffect(() => {
    if (p.playing && beatRef.current === 'finding') p.onCue('open')
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.playing])
  const prevShown = useRef(beat)
  useEffect(() => {
    if (p.playing && beat === 'question' && prevShown.current !== 'question') p.onCue('question')
    prevShown.current = beat
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [beat])

  const prevAsked = useRef(p.asked)
  useEffect(() => {
    if (!p.playing || !p.active) return
    if (p.asked && !prevAsked.current) {
      scrollToStop(panelRef.current, 'question', !reduced)
      p.onNeedPageScroll?.('question')
    }
    prevAsked.current = p.asked
  }, [p.asked, p.playing, p.active, reduced, p])

  const prevHold = useRef(holdLock)
  useEffect(() => {
    if (!p.playing || !p.active) return
    if (prevHold.current && !holdLock && revealed) {
      scrollToStop(panelRef.current, 'reveal', !reduced)
      p.onNeedPageScroll?.('reveal')
    }
    prevHold.current = holdLock
  }, [holdLock, revealed, p.playing, p.active, reduced, p])

  // The question arrives by itself once the chart is ready, drawn and the pause is over: never while the player is on the chart or its table.
  const [hovering, setHovering] = useState(false)
  const [tableOpen, setTableOpen] = useState(false)
  useEffect(() => {
    const el = rightRef.current
    if (!el) return
    const check = () => setTableOpen(el.querySelector('[aria-expanded="true"]') != null)
    const mo = new MutationObserver(check)
    mo.observe(el, { subtree: true, attributes: true, attributeFilter: ['aria-expanded'] })
    return () => mo.disconnect()
  }, [])
  const chartReady = !(p.near && chart.isLoading)
  useAskTimer({
    running: p.playing && rawBeat === 'finding' && chartReady && !hovering && !tableOpen && !p.paused,
    totalMs: askAfterMs(reduced),
    resetKey: `${statement.statement_id}|${p.playing}|${chartReady}`,
    barRef,
    onDone: p.onAsk,
  })

  // --- the results land one scope at a time -------------------------------------------------------------------------------
  const [landed, setLanded] = useState(false)
  const groups = [p.results?.national, p.results?.state, p.results?.place]
  const hasResults = p.results != null
  useEffect(() => {
    if (!revealed || holdLock) {
      setLanded(false)
      return
    }
    if (!fresh) {
      setLanded(true)
      return
    }
    if (!hasResults) return
    const timers: number[] = []
    let last = 0
    groups.forEach((g, k) => {
      const at = reduced ? k * 250 : BAR_FIRST_MS + k * BAR_GAP_MS
      last = Math.max(last, at)
      // A split that is withheld lands without a sound: nothing implies a result that is not there.
      if (resultBars(g)) timers.push(window.setTimeout(() => p.onCue('bar', k), at))
    })
    timers.push(window.setTimeout(() => setLanded(true), last + (reduced ? 150 : 450)))
    return () => timers.forEach((t) => window.clearTimeout(t))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [revealed, holdLock, fresh, hasResults, reduced])

  // Once the results have landed, move focus to "Continue" so Enter carries on (only for the round in view, and only for a fresh answer).
  useEffect(() => {
    if (p.active && fresh && landed) nextRef.current?.focus({ preventScroll: true })
  }, [p.active, fresh, landed])

  const label = placeLabel(scope.stateName, scope.city)
  const live = p.playing
    ? beat === 'finding'
      ? `${headline.text}${headline.isFinding ? ` ${chartTitle(String(statement.chart))}, ${chartScope}.` : ''}`
      : beat === 'question'
        ? `Where do you stand? ${statement.statement}`
        : p.answer
          ? `You chose ${ANSWER_LABEL[p.answer]}.`
          : ''
  : ''

  const chartColumn = (
    <div
      className="stance-right"
      ref={rightRef}
      onPointerEnter={() => setHovering(true)}
      onPointerLeave={() => setHovering(false)}
      onFocus={() => setHovering(true)}
      onBlur={() => setHovering(false)}
    >
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
  )

  return (
    <section
      ref={panelRef}
      className={`stance-panel stance-act ${chartMode}`}
      data-panel={index}
      data-beat={beat}
      data-live={p.active ? '' : undefined}
      aria-labelledby={`stance-q-${round}`}
      aria-roledescription="round"
    >
      <span className="stance-word" aria-hidden="true">
        {statement.category}
      </span>
      <p className="folio-sr-only" role="status" aria-live="polite">
        {live}
      </p>

      <div className="stance-stop" data-stop="finding">
        <div className="stance-grid">
          <div className="stance-left">
            <div className="stance-card">
              <p className="stance-card-title">{statement.category}</p>
            </div>
            <div className="stance-head">
              <p className="stance-ask">What the record shows</p>
              <h2 className="stance-headline" id={`stance-q-${round}`}>
                <KineticText text={headline.text} />
              </h2>
              {headline.isFinding && (
                <p className="stance-context">
                  {chartTitle(String(statement.chart))} · {chartScope}
                  {landNote ? ` · ${landNote}` : ''}
                </p>
              )}
            </div>
            {beat === 'finding' && (
              <>
                <SidesBlock sides={p.sides} />
                <div className="stance-askrow">
                  <button type="button" className="folio-btn stance-ask-btn" onClick={p.onAsk} data-primary>
                    Ask me <span aria-hidden="true">→</span>
                    <kbd aria-hidden="true">Space</kbd>
                  </button>
                  <button type="button" className="folio-link-btn stance-skip" onClick={p.onNext}>
                    Skip this one
                  </button>
                  <span className="stance-countdown" aria-hidden="true">
                    <span ref={barRef} />
                  </span>
                </div>
              </>
            )}
          </div>
          {chartColumn}
        </div>
      </div>

      {showQuestionStop && (
        <div className="stance-stop" data-stop="question">
          <div className="stance-qblock">
            <div className="stance-card">
              <p className="stance-card-title">{statement.category}</p>
            </div>
            <p className="stance-ask">Where do you stand?</p>
            <p className="stance-statement">
              <KineticText text={statement.statement} />
            </p>

            <div
              className="stance-answers stance-answers-stack"
              role="group"
              aria-label={`Your answer: ${statement.category}`}
              data-primary={showButtons ? '' : undefined}
            >
              {ORDER.map((a) => (
                <button
                  key={a}
                  type="button"
                  className={`folio-btn stance-answer stance-answer-${a}${chosen === a ? ' is-locked' : chosen ? ' is-dim' : ''}`}
                  disabled={!showButtons || p.posting || holdLock}
                  aria-pressed={chosen ? chosen === a : p.changing ? p.answer === a : undefined}
                  onClick={() => p.onAnswer(a)}
                >
                  <span>{ANSWER_LABEL[a]}</span>
                  {p.active && showButtons && <kbd aria-hidden="true">{KEY[a]}</kbd>}
                </button>
              ))}
            </div>
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
            {beat === 'question' && (
              <div className="stance-nav">
                {p.answer != null && (
                  <button type="button" className="folio-link-btn" onClick={p.onChange}>
                    Change my answer
                  </button>
                )}
                <button type="button" className="folio-link-btn stance-skip" onClick={p.onNext}>
                  Skip this one
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {showRevealStop && (
        <div className={`stance-stop stance-reveal${fresh ? ' is-fresh' : ''}`} data-stop="reveal" aria-live="polite" aria-atomic="false">
          {revealed && p.answer != null && (
            <>
              <p className="stance-yours">
                You chose {ANSWER_LABEL[p.answer]}.{' '}
                <button type="button" className="folio-link-btn" onClick={p.onChange}>
                  Change my answer
                </button>
              </p>
              {p.results ? (
                <div className="stance-reveal-body">
                  <p className="stance-reveal-head">How people who played answered · showing {label}</p>
                  <ResultBars title="Nationally" group={p.results.national} minSample={p.minSample} yourAnswer={p.answer} play={p.active} landIndex={0} />
                  <ResultBars
                    title={scope.stateName ? `In ${scope.stateName}` : 'In your state'}
                    group={p.results.state}
                    minSample={p.minSample}
                    yourAnswer={p.answer}
                    play={p.active}
                    landIndex={1}
                    missing="Choose your state to see this group."
                  />
                  <ResultBars
                    title={scope.city && scope.stateName ? `In ${scope.city}, ${scope.stateName}` : 'In your community'}
                    group={p.results.place}
                    minSample={p.minSample}
                    yourAnswer={p.answer}
                    play={p.active}
                    landIndex={2}
                    missing={scope.stateName ? 'Add your community to see this group.' : 'Choose your state and community to see this group.'}
                  />
                  <p className="stance-note">This is how people who played answered. It is not a poll.</p>
                </div>
              ) : (
                <p className="folio-muted" role="status">
                  {p.resultsFailed ? 'Results could not be loaded right now.' : p.resultsLoading ? `Loading how people answered for ${label}…` : ''}
                </p>
              )}
              <ScreenNav ref={nextRef} nextLabel={landed || !fresh ? p.nextLabel : null} onNext={p.onNext} onPrev={p.onPrev} />
            </>
          )}
        </div>
      )}
    </section>
  )
}