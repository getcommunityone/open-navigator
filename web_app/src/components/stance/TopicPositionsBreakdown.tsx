import { BOX_COLORS } from '../home/storyColors'
import { countsSentence, pickDisplay } from '../../utils/displayFit'
import { SPLIT_NOTE, type PositionCounts, type TopicPositions } from '../../utils/topicPositions'

const fmt = (n: number) => n.toLocaleString('en-US')
const pct = (n: number, of: number) => (of > 0 ? Math.round((n / of) * 100) : 0)

interface Props {
  counts: PositionCounts
  words: TopicPositions
  /** Exactly the scope the counts are for ("National", "California"). */
  scopeLabel: string
  labelledBy?: string
}

/**
 * "Who spoke" on a topic story (#1224): the public's position in the meetings the AI read, in the topic's own words
 * (utils/topicPositions, #1200). One bar per position, sized by its share of the meetings read; every count is a meeting
 * the AI (Jev) read, never a counted speaker. Meetings on record outside the four (not read yet, or a label outside the question, #1201) are said in a line, not drawn.
 */
export default function TopicPositionsBreakdown({ counts, words, scopeLabel, labelledBy }: Props) {
  const rows = [
    { key: 'against', label: words.against, n: counts.against, color: BOX_COLORS.against },
    { key: 'for', label: words.for, n: counts.for, color: BOX_COLORS.for },
    { key: 'split', label: words.split, n: counts.split, color: BOX_COLORS.neutral },
    { key: 'silent', label: words.silent, n: counts.silent, color: BOX_COLORS.meetings },
  ]
  // The shared display rule (#1289, applied here by #1290): no zero rows and no percentages; a few meetings read are a
  // sentence, 20 or more sorted count bars.
  const display = pickDisplay({ items: counts.read, categories: rows.map((r) => r.n) })
  const kept = rows.filter((r) => r.n > 0)
  const shown = [...kept].sort((a, b) => b.n - a.n)
  const max = Math.max(1, ...shown.map((r) => r.n))
  const asSentence = display.kind === 'list' || display.kind === 'sentence'
  const unread = counts.meetings != null ? Math.max(0, counts.meetings - counts.read) : null
  return (
    <figure className="topic-positions" aria-labelledby={labelledBy}>
      {asSentence ? (
        <p className="stance-fit-lead" data-display="sentence">
          {fmt(counts.read)} {counts.read === 1 ? 'meeting' : 'meetings'} read. {countsSentence(kept.map((r) => ({ label: r.label, count: r.n })))}
        </p>
      ) : (
      <ul className="topic-positions-rows" data-display={display.kind}>
        {shown.map((r) => (
          <li key={r.key} className="topic-positions-row">
            <span className="topic-positions-label">{r.label}</span>
            <span className="topic-positions-bar" aria-hidden="true">
              <span style={{ width: `${pct(r.n, max)}%`, background: r.color }} />
            </span>
            <span className="topic-positions-n">
              {fmt(r.n)}
            </span>
          </li>
        ))}
      </ul>
      )}
      <figcaption className="stance-note">
        {scopeLabel}: {fmt(counts.read)} {counts.read === 1 ? 'meeting' : 'meetings'} read by an AI (each meeting's transcript, never a count of
        speakers){unread ? `; ${fmt(unread)} more on record aren't shown here (not read yet, or read in a label this page can't show)` : ''}. {words.forMeans ? `${words.forMeans}. ` : ''}
        {SPLIT_NOTE}
      </figcaption>
    </figure>
  )
}
