import type { ChoiceGroup, StanceQuestion } from '../../api/stance'
import { choiceBars, optionTone } from '../../utils/storyQuestion'

interface Props {
  /** Row title: "Before reading" or "After reading". */
  title: string
  group: ChoiceGroup | null | undefined
  options: StanceQuestion['options']
  minSample: number | null
  /** The reader's own answer at this moment (an option id), or null. */
  yours: string | null
  /** Order in which the row lands (see `.is-fresh` in stance.css). */
  landIndex?: number
}

const answers = (n: number) => `${n.toLocaleString('en-US')} ${n === 1 ? 'answer' : 'answers'}`

/**
 * How one group answered the story's question at one moment, as a stacked bar with one segment per option (#915). The same
 * rules as the challenge's bars: counts and percentages are written out, colour is never the only signal, the reader's own
 * answer is marked, and a group below the minimum sample shows how many answers there are and nothing else.
 */
export default function ChoiceBars({ title, group, options, minSample, yours, landIndex = 0 }: Props) {
  const bars = choiceBars(group, options)
  return (
    <div className="stance-result stance-choice" style={{ ['--k' as string]: landIndex }}>
      <p className="stance-result-title">
        <span>{title}</span>
        {group && <span className="stance-result-n"> · {answers(group.n)}</span>}
      </p>
      {!bars ? (
        <p className="stance-result-none">
          Not enough answers yet ({group ? group.n.toLocaleString('en-US') : 0} so far, {minSample ?? '—'} needed)
        </p>
      ) : (
        <>
          <div className="stance-stack" role="img" aria-label={bars.map((b) => `${b.label} ${b.count} (${b.percent}%)`).join(', ')}>
            {bars.map((b, i) =>
              b.percent > 0 ? (
                <span
                  key={b.id}
                  className={`stance-seg stance-seg-${optionTone(i)}${yours === b.id ? ' is-yours' : ''}`}
                  style={{ width: `${b.percent}%`, ['--i' as string]: i }}
                >
                  {b.percent >= 12 ? `${b.percent}%` : ''}
                </span>
              ) : null,
            )}
          </div>
          <ul className="stance-legend">
            {bars.map((b, i) => (
              <li key={b.id} className={yours === b.id ? 'is-yours' : undefined}>
                <span className={`stance-swatch stance-seg-${optionTone(i)}`} aria-hidden="true" />
                {b.label}: {b.count.toLocaleString('en-US')} ({b.percent}%){yours === b.id ? ' · your answer' : ''}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
