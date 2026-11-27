import { useQuery } from '@tanstack/react-query'
import { fetchTopicPositions, type TopicPositionsResponse } from '../../api/topicPolicy'
import { pct, positionFill, positionStyle } from '../../utils/topicPolicy'
import './storyCharts.css'

interface Props {
  topic: string
  stateCode?: string
  scopeLabel: string
  subject: string
}

const fmt = (n: number) => n.toLocaleString('en-US')

/**
 * The positions the public took in meetings (#1274): one bar per position, the count of meetings where the AI reading
 * (Jev) put the public who spoke closest to it, out of the meetings where the public spoke on the topic. Support on the
 * violet side, opposition on the vermilion side, no opinion in grey. Counts of meetings, never of speakers. Meetings
 * where the public didn't speak are said in the note, not drawn.
 */
export default function PositionBreakdown({ topic, stateCode, scopeLabel, subject }: Props) {
  const q = useQuery<TopicPositionsResponse>({
    queryKey: ['topic-positions', topic, stateCode ?? 'national'],
    queryFn: () => fetchTopicPositions(topic, stateCode),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  const title = (
    <p className="sc-h">
      What the public said in meetings on {subject} · {scopeLabel}
    </p>
  )
  if (q.isLoading) {
    return (
      <div className="sc-block">
        {title}
        <p className="sc-note" role="status">Loading positions…</p>
      </div>
    )
  }
  if (q.isError || !q.data) {
    return (
      <div className="sc-block">
        {title}
        <p className="sc-note">Positions could not be loaded right now.</p>
      </div>
    )
  }
  const d = q.data
  if (!d.available || d.read_meetings === 0) {
    return (
      <div className="sc-block">
        {title}
        <p className="sc-note">No meeting on {subject} has an AI reading{scopeLabel === 'National' ? '' : ` in ${scopeLabel}`} yet.</p>
      </div>
    )
  }
  const max = Math.max(1, ...d.options.map((o) => o.meetings))
  return (
    <div className="sc-block pb">
      {title}
      {d.spoke_meetings === 0 ? (
        <p className="sc-note">
          The public didn&apos;t speak on {subject} in any of the {fmt(d.read_meetings)} meetings read
          {scopeLabel === 'National' ? '' : ` in ${scopeLabel}`}.
        </p>
      ) : (
        <ul className="pb-rows" aria-label={`Meetings by the public's position, ${scopeLabel}`}>
          {d.options.map((o) => {
            const st = positionStyle(o.key)
            const share = pct(o.meetings, d.spoke_meetings)
            return (
              <li key={o.key} className="pb-row" title={`${st.label}: ${fmt(o.meetings)} meeting${o.meetings === 1 ? '' : 's'}`}>
                <span className="pb-label">{st.label}</span>
                <span className="pb-track" aria-hidden="true">
                  <span
                    className="pb-bar"
                    style={{ width: `${(o.meetings / max) * 100}%`, background: positionFill(st), minWidth: o.meetings > 0 ? 3 : 0 }}
                  />
                </span>
                <span className="pb-value">
                  {fmt(o.meetings)}
                  {share != null && <span className="pb-share"> · {share}%</span>}
                </span>
              </li>
            )
          })}
        </ul>
      )}
      <p className="sc-note">
        An AI reading (Jev) of each meeting transcript: the position closest to most of the members of the public who spoke.
        Out of <b>{fmt(d.spoke_meetings)}</b> meeting{d.spoke_meetings === 1 ? '' : 's'} where the public spoke on it
        {d.states > 0 && !stateCode ? ` in ${d.states} state${d.states === 1 ? '' : 's'}` : ''}; in <b>{fmt(d.did_not_speak)}</b> more
        read meeting{d.did_not_speak === 1 ? '' : 's'} the public didn&apos;t speak on it. Counts meetings, not people.
      </p>
    </div>
  )
}
