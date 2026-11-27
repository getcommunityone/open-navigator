import { BOX_COLORS } from '../home/storyColors'
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
  const unread = counts.meetings != null ? Math.max(0, counts.meetings - counts.read) : null
  return (
    <figure className="topic-positions" aria-labelledby={labelledBy}>
      <ul className="topic-positions-rows">
        {rows.map((r) => (
          <li key={r.key} className="topic-positions-row">
            <span className="topic-positions-label">{r.label}</span>
            <span className="topic-positions-bar" aria-hidden="true">
              <span style={{ width: `${pct(r.n, counts.read)}%`, background: r.color }} />
            </span>
            <span className="topic-positions-n">
              {fmt(r.n)} <span className="topic-positions-pct">({pct(r.n, counts.read)}%)</span>
            </span>
          </li>
        ))}
      </ul>
      <figcaption className="stance-note">
        {scopeLabel}: {fmt(counts.read)} {counts.read === 1 ? 'meeting' : 'meetings'} read by an AI (each meeting's transcript, never a count of
        speakers){unread ? `; ${fmt(unread)} more on record aren't shown here (not read yet, or read in a label this page can't show)` : ''}. {words.forMeans ? `${words.forMeans}. ` : ''}
        {SPLIT_NOTE}
      </figcaption>
    </figure>
  )
}
