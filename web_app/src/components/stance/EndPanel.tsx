import { Link } from 'react-router-dom'
import type { PackSummary, StanceAnswer, StatementResults } from '../../api/stance'
import { placeLabel, tallySided } from '../../utils/stanceGame'

interface Props {
  index: number
  rounds: Array<{ statementId: string; answer: StanceAnswer | null; results: StatementResults | undefined }>
  stateName: string | null
  city: string | null
  otherPacks: PackSummary[]
  /** Query string that carries the place into the next pack ("?state=AL&city=…" or ""). */
  placeQuery: string
  onJump: (roundIndex: number) => void
  onBack: () => void
  /** The data story, with the scope in it. */
  storyLink: string
  onChangePlace: () => void
}

/** The end screen. Counts only rounds the player answered, and only groups that were available. */
export default function EndPanel({ index, rounds, stateName, city, otherPacks, placeQuery, onJump, onBack, storyLink, onChangePlace }: Props) {
  const answered = rounds.filter((r) => r.answer != null)
  const unsure = answered.filter((r) => r.answer === 'unsure').length
  const nat = tallySided(answered.map((r) => ({ answer: r.answer, group: r.results?.national })))
  const st = tallySided(answered.map((r) => ({ answer: r.answer, group: r.results?.state })))
  const firstOpen = rounds.findIndex((r) => r.answer == null)

  return (
    <section className="stance-panel stance-act stance-end" data-panel={index} aria-labelledby="stance-end-h" aria-roledescription="round">
      <span className="stance-word" aria-hidden="true">
        Results
      </span>
      <div className="stance-end-body">
        <div className="stance-card">
          <p className="stance-card-eyebrow">Your results</p>
          <p className="stance-card-title" id="stance-end-h">
            Where you stood
          </p>
        </div>
        <p className="stance-finding">
          You answered {answered.length} of {rounds.length} rounds.
          {firstOpen >= 0 && (
            <>
              {' '}
              <button type="button" className="folio-link-btn" onClick={() => onJump(firstOpen)}>
                Go to the first round you have not answered
              </button>
              .
            </>
          )}
        </p>
        <ul className="stance-end-list">
          <li>
            Nationally, you were with the larger group of people who played in{' '}
            <b>
              {nat.withLarger} of {nat.compared}
            </b>{' '}
            rounds with a national split to compare.
          </li>
          <li>
            {stateName ? (
              <>
                In {stateName}, you were with the larger group of people who played in{' '}
                <b>
                  {st.withLarger} of {st.compared}
                </b>{' '}
                rounds with a state split to compare.
              </>
            ) : (
              'Choose your state to compare your answers with people who played there.'
            )}
          </li>
          <li>
            You answered “Not sure” in <b>{unsure}</b> {unsure === 1 ? 'round' : 'rounds'}.
          </li>
        </ul>
        <p className="stance-note">
          Rounds with not enough answers, or a tie for the larger group, are left out of those counts. Showing {placeLabel(stateName, city)}.
          This is how people who played answered. It is not a poll.
        </p>
        <div className="stance-nav">
          <button type="button" className="folio-btn stance-next" onClick={() => onJump(0)}>
            Play again
          </button>
          <Link className="folio-btn" to={storyLink}>
            Read the story
          </Link>
          <button type="button" className="folio-btn" onClick={onChangePlace}>
            Change my place
          </button>
          <button type="button" className="folio-btn stance-back" onClick={onBack}>
            <span aria-hidden="true">←</span> Back
          </button>
        </div>
        {otherPacks.length > 0 && (
          <div className="stance-others">
            <p className="stance-card-eyebrow">More topics</p>
            <ul>
              {otherPacks.map((p) => (
                <li key={p.pack_id}>
                  <Link to={`/challenge/${encodeURIComponent(p.pack_id)}${placeQuery}`}>
                    {p.title} ({p.statement_count} statements)
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </section>
  )
}
