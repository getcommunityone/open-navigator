import { useEffect, useRef } from 'react'
import type { StanceAnswer } from '../../api/stance'
import type { StoryScope } from '../../utils/dataStory'
import { storyScopeLabel } from '../../utils/dataStory'
import { readersRow, speakersRow, type ContinuumRow, type SpeakerCounts } from '../../utils/stanceContinuum'
import { ANSWER_LABEL } from '../../utils/stanceGame'
import type { ScreenStatement } from './useStoryStatements'

const ORDER: StanceAnswer[] = ['agree', 'disagree', 'unsure']

interface Props {
  s: ScreenStatement
  scope: StoryScope
  /** Real speaker counts for the scope (positions), or null when not recorded. */
  speakers: SpeakerCounts | null
  /** Ids the block's heading and the screen headline share. */
  id: string
}

/**
 * The statement this screen's record is about, with Agree / Disagree / Not sure (#981), in the story itself rather than a
 * separate challenge. After an answer, "Where you sit": the reader on the line of readers' answers for the place, and,
 * when the statement leans to one side, on the line of people who spoke at the meetings. Every bar is real counts; a group
 * below the minimum sample says how many have answered instead of showing a split.
 */
export default function StoryStatement({ s, scope, speakers, id }: Props) {
  const answered = s.answer != null && !s.changing
  // Keep keyboard focus in the block: a saved answer replaces the buttons (focus would fall to the page and the next
  // Space or arrow would jump screens), so it moves to "Change"; after "Change", to the answer that was chosen.
  const changeRef = useRef<HTMLButtonElement>(null)
  const answersRef = useRef<HTMLDivElement>(null)
  const was = useRef(answered)
  useEffect(() => {
    const block = answersRef.current?.closest('.story-statement')
    const focusInside = block?.contains(document.activeElement) || document.activeElement === document.body
    if (answered && !was.current && focusInside) changeRef.current?.focus()
    if (!answered && was.current && focusInside) {
      answersRef.current?.querySelector<HTMLButtonElement>('[aria-pressed="true"]')?.focus() ??
        answersRef.current?.querySelector<HTMLButtonElement>('button')?.focus()
    }
    was.current = answered
  }, [answered])
  const placePhrase = scope.stateName ? `in ${storyScopeLabel(scope)}` : 'across the country'
  const readers = answered ? readersRow(s.results, s.minSample, s.answer, { stateName: scope.stateName, city: scope.city }) : null
  const talk = answered ? speakersRow(speakers, s.statement.speaker_lean, s.answer, placePhrase) : null

  return (
    <section className="stance-qblock story-statement" aria-labelledby={`${id}-ask`}>
      <p className="stance-ask" id={`${id}-ask`}>
        Where do you stand?
      </p>
      <p className="stance-statement story-statement-text">{s.statement.statement}</p>
      {!answered ? (
        <div ref={answersRef} className="stance-answers story-answers" role="group" aria-label={`Your answer: ${s.statement.statement}`}>
          {ORDER.map((a) => (
            <button
              key={a}
              type="button"
              className={`folio-btn stance-answer stance-answer-${a}${s.answer === a ? ' is-locked' : ''}`}
              disabled={s.posting}
              aria-pressed={s.changing ? s.answer === a : undefined}
              onClick={() => s.onAnswer(a)}
            >
              {ANSWER_LABEL[a]}
            </button>
          ))}
        </div>
      ) : (
        <p className="stance-yours story-yours" role="status">
          Your answer: <strong>{ANSWER_LABEL[s.answer!]}</strong>{' '}
          <button ref={changeRef} type="button" className="folio-link-btn" onClick={s.onChange}>
            Change
          </button>
        </p>
      )}
      {s.posting && (
        <p className="folio-muted" role="status">
          Saving your answer…
        </p>
      )}
      {s.error && (
        <p className="stance-error" role="alert">
          {s.error}
        </p>
      )}
      {answered && (
        <div className="story-sit" role="group" aria-labelledby={`${id}-sit`}>
          <p className="story-sit-title" id={`${id}-sit`}>
            Where you sit
          </p>
          {readers && 'row' in readers ? (
            <Continuum row={readers.row} />
          ) : readers && 'pending' in readers ? (
            <p className="stance-note">
              {readers.pending.title}: {readers.pending.n.toLocaleString('en-US')} so far.{' '}
              {readers.pending.minSample > 0
                ? `The split shows once ${readers.pending.minSample.toLocaleString('en-US')} have answered.`
                : 'The split shows once enough readers have answered.'}
            </p>
          ) : (
            <p className="stance-note">Readers&apos; answers couldn&apos;t be loaded right now.</p>
          )}
          {talk && <Continuum row={talk} />}
        </div>
      )}
    </section>
  )
}

function Continuum({ row }: { row: ContinuumRow }) {
  return (
    <figure className="story-continuum">
      <figcaption className="story-continuum-title">{row.title}</figcaption>
      <div
        className="story-continuum-bar"
        role="img"
        aria-label={`${row.segments.map((g) => `${g.label} ${g.percent}%`).join(', ')}. ${row.sentence}`}
      >
        {row.segments.map((g) =>
          g.percent > 0 ? (
            <span key={g.key} className={`story-continuum-seg story-continuum-seg--${g.key}`} style={{ width: `${g.percent}%` }} />
          ) : null,
        )}
        <span
          className={`story-continuum-you${row.marker < 8 ? ' is-start' : row.marker > 92 ? ' is-end' : ''}`}
          style={{ left: `${row.marker}%` }}
          aria-hidden="true"
        >
          <span>You</span>
        </span>
      </div>
      <div className="story-continuum-ends" aria-hidden="true">
        <span>{row.segments[0]!.label}</span>
        <span>{row.segments[row.segments.length - 1]!.label}</span>
      </div>
      <p className="story-continuum-sentence">{row.sentence}</p>
    </figure>
  )
}
