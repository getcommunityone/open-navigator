import type { GroupResult, StanceAnswer } from '../../api/stance'
import Odometer from './Odometer'
import { resultBars, type ResultBar } from '../../utils/stanceGame'

interface Props {
  /** Row title, e.g. "Nationally" or "Tuscaloosa, Alabama". */
  title: string
  group: GroupResult | null | undefined
  minSample: number | null
  yourAnswer: StanceAnswer | null
  /** Roll the numbers in (the round is in view). */
  play?: boolean
  /** Why there is no group at all (no state or community chosen). */
  missing?: string
}

const plural = (n: number, one: string, many: string) => `${n.toLocaleString('en-US')} ${n === 1 ? one : many}`

/** One group's split as a horizontal stacked bar. Counts and percentages are also written as text, never colour alone. */
export default function ResultBars({ title, group, minSample, yourAnswer, missing, play = true }: Props) {
  const bars: ResultBar[] | null = resultBars(group)
  return (
    <div className="stance-result">
      <p className="stance-result-title">
        <span>{title}</span>
        {group && <span className="stance-result-n"> · {plural(group.n, 'answer', 'answers')}</span>}
      </p>
      {missing && !group ? (
        <p className="stance-result-none">{missing}</p>
      ) : !bars ? (
        <p className="stance-result-none">
          Not enough answers yet ({group ? group.n.toLocaleString('en-US') : 0} so far, {minSample ?? '—'} needed)
        </p>
      ) : (
        <>
          <div className="stance-stack" role="img" aria-label={bars.map((b) => `${b.label} ${b.count} (${b.percent}%)`).join(', ')}>
            {bars.map((b, i) =>
              b.percent > 0 ? (
                <span
                  key={b.answer}
                  className={`stance-seg stance-seg-${b.answer}${yourAnswer === b.answer ? ' is-yours' : ''}`}
                  style={{ width: `${b.percent}%`, ['--i' as string]: i }}
                >
                  {b.percent >= 9 ? `${b.percent}%` : ''}
                </span>
              ) : null,
            )}
          </div>
          <ul className="stance-legend">
            {bars.map((b) => (
              <li key={b.answer} className={yourAnswer === b.answer ? 'is-yours' : undefined}>
                <span className={`stance-swatch stance-seg-${b.answer}`} aria-hidden="true" />
                {b.label}: <Odometer text={b.count.toLocaleString('en-US')} play={play} /> (<Odometer text={String(b.percent)} play={play} />%)
                {yourAnswer === b.answer ? ' — your answer' : ''}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
