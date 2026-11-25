import { useEffect, useRef, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { ChoiceMoment, ChoiceResults, ChoiceScopes, StanceQuestion } from '../../api/stance'
import { PAUSE_NOTE, storyScopeLabel, type ScreenText, type StoryScope, type StoryScreen } from '../../utils/dataStory'
import { answerChange, optionLabel, optionTone, questionText } from '../../utils/storyQuestion'
import { cap, roundWord } from '../../utils/stanceGame'
import ChoiceBars from './ChoiceBars'
import KineticText from './KineticText'
import ScreenNav from './ScreenNav'

/** What the three vote screens share: the question, the reader's answers and how an answer is stored. */
export interface VoteState {
  question: StanceQuestion | null
  /** The pack is still loading (no question yet). */
  loading: boolean
  /** The pack could not be loaded. */
  failed: boolean
  onRetryLoad: () => void
  /** The reader's stored answers (option ids), or null. */
  before: string | null
  after: string | null
  /** The answer being stored right now. */
  pending: { moment: ChoiceMoment; choice: string } | null
  /** The last answer that could not be stored. */
  error: { moment: ChoiceMoment; choice: string; message: string } | null
  onAnswer: (moment: ChoiceMoment, choice: string) => void
}

interface ScreenProps {
  screen: StoryScreen
  index: number
  text: ScreenText
  scope: StoryScope
  vote: VoteState
  /** The screen is the one in view. */
  active: boolean
  nextLabel: string | null
  onPrev?: () => void
  onNext: () => void
}

/** A column taller than its frame scrolls on its own: Lenis must leave wheel and touch over it alone, but only then. */
function useOwnScroll() {
  const ref = useRef<HTMLDivElement>(null)
  const ref2 = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const els = [ref.current, ref2.current].filter((e): e is HTMLDivElement => e != null)
    const mark = () => els.forEach((e) => e.toggleAttribute('data-lenis-prevent', e.scrollHeight > e.clientHeight + 1))
    mark()
    if (typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(mark)
    els.forEach((e) => ro.observe(e))
    return () => ro.disconnect()
  })
  return [ref, ref2] as const
}

/** The answers to the story's question. An answer that is stored stays pressed, and another can still be picked. */
function Answers({ vote, moment, label, primary }: { vote: VoteState; moment: ChoiceMoment; label: string; primary: boolean }) {
  const q = vote.question
  if (!q) return null
  const stored = moment === 'before' ? vote.before : vote.after
  const pending = vote.pending?.moment === moment ? vote.pending.choice : null
  const busy = vote.pending != null
  const error = vote.error?.moment === moment ? vote.error : null
  return (
    <>
      <div className="stance-answers stance-choices" role="group" aria-label={label} data-primary={primary ? '' : undefined}>
        {q.options.map((o, i) => (
          <button
            key={o.id}
            type="button"
            style={{ ['--i' as string]: i }}
            className={`stance-answer stance-answer-${optionTone(i)}${pending === o.id ? ' is-locked' : pending ? ' is-dim' : ''}`}
            disabled={busy}
            aria-pressed={(pending ?? stored) === o.id}
            data-choice={o.id}
            onClick={() => vote.onAnswer(moment, o.id)}
          >
            <span>{o.label}</span>
          </button>
        ))}
      </div>
      <p className="stance-note">{PAUSE_NOTE}</p>
      {pending && (
        <p className="folio-muted" role="status">
          Saving your answer…
        </p>
      )}
      {error && (
        <div className="stance-error" role="alert">
          <span>{error.message}</span>
          <button type="button" className="folio-btn" onClick={() => vote.onAnswer(moment, error.choice)} disabled={busy}>
            Retry
          </button>
        </div>
      )}
    </>
  )
}

/** Shown in place of the answers while the question is loading, or when it could not be loaded. The story can still be read. */
function QuestionUnavailable({ vote }: { vote: VoteState }) {
  if (vote.loading) {
    return (
      <p className="folio-muted" role="status">
        Loading…
      </p>
    )
  }
  return (
    <div className="stance-error" role="alert">
      <span>The question could not be loaded right now. You can still read on.</span>
      <button type="button" className="folio-btn" onClick={vote.onRetryLoad}>
        Try again
      </button>
    </div>
  )
}

function Frame(p: { screen: StoryScreen; index: number; active: boolean; single: boolean; className?: string; children: ReactNode }) {
  return (
    <section
      className={`stance-panel stance-act stance-vote${p.className ? ` ${p.className}` : ''}`}
      data-panel={p.index}
      data-screen={p.screen.id}
      data-live={p.active ? '' : undefined}
      aria-labelledby={`story-h-${p.screen.id}`}
      aria-roledescription="screen"
      tabIndex={-1}
    >
      <span className="stance-word" aria-hidden="true">
        {p.screen.eyebrow}
      </span>
      <div className={`stance-grid${p.single ? ' is-single' : ''}`}>{p.children}</div>
    </section>
  )
}

/** The story's first screen: the question, large, with its answers. Nothing is explained first, and the reader may skip. */
export function QuestionScreen(p: ScreenProps) {
  const { vote } = p
  const [leftRef] = useOwnScroll()
  const said = optionLabel(vote.question, vote.before)
  return (
    <Frame screen={p.screen} index={p.index} active={p.active} single className="stance-vote-question">
      <div className="stance-left" ref={leftRef}>
        <div className="stance-card">
          <p className="stance-card-eyebrow">Before you read</p>
        </div>
        <div className="stance-head">
          <h2 className="stance-headline stance-bigq" id={`story-h-${p.screen.id}`}>
            <KineticText text={p.text.headline} />
          </h2>
        </div>
        <div className="stance-qblock">
          {vote.question ? <Answers vote={vote} moment="before" label="Your answer before reading" primary={!said} /> : <QuestionUnavailable vote={vote} />}
          {said && !vote.pending && (
            <p className="stance-yours" role="status">
              You said <b>{said}</b>. Pick another to change it.
            </p>
          )}
        </div>
        <div className="stance-nav stance-nav-split">
          {said || !vote.question ? (
            <button
              type="button"
              className="folio-btn stance-next stance-next-end"
              onClick={p.onNext}
              aria-label={`Next: ${p.nextLabel}`}
              title={`Next: ${p.nextLabel}`}
              data-primary
            >
              Next <span aria-hidden="true">→</span>
            </button>
          ) : (
            <button type="button" className="folio-link-btn stance-skip" onClick={p.onNext}>
              Skip, I'd rather read first
            </button>
          )}
        </div>
      </div>
    </Frame>
  )
}

/** The second screen: where. The place picker sits in the sentence, and the question is worded for the place it shows. */
export function ScopeScreen(p: ScreenProps & { place: ReactNode }) {
  const { vote } = p
  const [leftRef] = useOwnScroll()
  const said = optionLabel(vote.question, vote.before)
  return (
    <Frame screen={p.screen} index={p.index} active={p.active} single className="stance-vote-scope">
      <div className="stance-left" ref={leftRef}>
        <div className="stance-head">
          <h2 className="stance-headline stance-bigq" id={`story-h-${p.screen.id}`}>
            <KineticText text={p.text.headline} />
          </h2>
          <p className="stance-lede">{p.text.context}</p>
        </div>
        <div className="stance-qblock">
          <div className="stance-where">
            <span>Show me</span> {p.place}
          </div>
          {vote.question && (
            <p className="stance-statement" data-testid="scope-question">
              {questionText(vote.question, p.scope)}
            </p>
          )}
          {said && (
            <p className="stance-yours">
              You said <b>{said}</b>.
            </p>
          )}
        </div>
        <ScreenNav nextLabel={p.nextLabel} onNext={p.onNext} onPrev={p.onPrev} />
      </div>
    </Frame>
  )
}

interface VerdictProps extends ScreenProps {
  results: ChoiceResults | undefined
  resultsFailed: boolean
  /** The answer after reading was given on this visit: the results land one after another. */
  fresh: boolean
  links: { challenge: string; dataCenters: string; decisions: string }
  /** How many statements the challenge has (from the pack), or null while it is unknown. */
  statementCount: number | null
}

/**
 * The last screen: the same question again. Once the reader answers, it says whether their answer changed and shows how
 * readers answered before and after, for the country, the state and the place, each withheld below the minimum sample.
 */
export function VerdictScreen(p: VerdictProps) {
  const { vote, scope } = p
  const [leftRef, rightRef] = useOwnScroll()
  const q = vote.question
  const answered = q != null && optionLabel(q, vote.after) != null
  const change = q ? answerChange(q, vote.before, vote.after) : null
  const label = storyScopeLabel(scope)
  const rows: Array<{ key: keyof ChoiceScopes; title: string; missing: string }> = [
    { key: 'national', title: 'Across the country', missing: '' },
    { key: 'state', title: scope.stateName ? `In ${scope.stateName}` : 'In your state', missing: 'Pick a place to see your state.' },
    {
      key: 'place',
      title: scope.city && scope.stateName ? `In ${scope.city}, ${scope.stateName}` : 'In your community',
      missing: scope.stateName ? 'Pick a city or county to see your community.' : 'Pick a place to see your community.',
    },
  ]

  return (
    <Frame screen={p.screen} index={p.index} active={p.active} single={!answered} className="stance-vote-verdict">
      <div className="stance-left" ref={leftRef}>
        <div className="stance-card">
          <p className="stance-card-eyebrow">After you read</p>
        </div>
        <div className="stance-head">
          <h2 className="stance-headline" id={`story-h-${p.screen.id}`}>
            <KineticText text={p.text.headline} />
          </h2>
        </div>
        <div className="stance-qblock">
          {q ? (
            <>
              <p className="stance-statement" data-testid="verdict-question">
                {questionText(q, scope)}
              </p>
              <Answers vote={vote} moment="after" label="Your answer after reading" primary={!answered} />
            </>
          ) : (
            <QuestionUnavailable vote={vote} />
          )}
          {answered && change?.sentence && !vote.pending && (
            <p className="stance-yours stance-change" role="status" data-testid="verdict-change">
              {change.sentence}
            </p>
          )}
        </div>
        <div className="stance-nav">
          {answered || !q ? (
            <Link className="folio-btn stance-next" to={p.links.challenge} data-primary>
              Take the Data Center Challenge <span aria-hidden="true">→</span>
            </Link>
          ) : (
            <Link className="folio-link-btn stance-skip" to={p.links.challenge}>
              Skip to the Data Center Challenge
            </Link>
          )}
          {p.onPrev && (
            <button type="button" className="folio-btn stance-back" onClick={p.onPrev}>
              <span aria-hidden="true">←</span> Back
            </button>
          )}
        </div>
        {answered && (
          <p className="stance-note stance-after-links">
            {p.statementCount ? `${cap(roundWord(p.statementCount))} statements people argued over in local meetings. ` : ''}
            Or see <Link to={p.links.dataCenters}>every data center record</Link> or <Link to={p.links.decisions}>local decisions</Link> for{' '}
            {label === 'National' ? 'the country' : label}.
          </p>
        )}
      </div>
      {answered && q && (
        <div className={`stance-right stance-reveal${p.fresh ? ' is-fresh' : ''}`} ref={rightRef} aria-live="polite" aria-atomic="false">
          {p.results ? (
            <div className="stance-reveal-body" data-testid="verdict-results">
              <p className="stance-reveal-head">How readers answered · showing {label}</p>
              {rows.map((r, k) => {
                const b = p.results!.before[r.key]
                const a = p.results!.after[r.key]
                return (
                  <div className="stance-scopeblock" key={r.key} data-scope={r.key}>
                    <p className="stance-scopeblock-title">{r.title}</p>
                    {b == null && a == null ? (
                      <p className="stance-result-none">{r.missing}</p>
                    ) : (
                      <>
                        <ChoiceBars title="Before reading" group={b} options={q.options} minSample={p.results!.min_sample} yours={vote.before} landIndex={k * 2} />
                        <ChoiceBars title="After reading" group={a} options={q.options} minSample={p.results!.min_sample} yours={vote.after} landIndex={k * 2 + 1} />
                      </>
                    )}
                  </div>
                )
              })}
              <p className="stance-note">This is how readers of this story answered. It is not a poll.</p>
            </div>
          ) : (
            <p className="folio-muted" role="status">
              {p.resultsFailed ? 'The answers could not be loaded right now.' : 'Loading how readers answered…'}
            </p>
          )}
        </div>
      )}
    </Frame>
  )
}
