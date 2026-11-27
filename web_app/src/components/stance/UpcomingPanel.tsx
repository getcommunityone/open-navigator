import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTopicUpcoming } from '../../hooks/useTopicUpcoming'
import { highlightSnippet } from '../../lib/highlight'
import {
  broaderHref,
  nothingUpcoming,
  upcomingBasisNote,
  upcomingDate,
  upcomingKindLabel,
  upcomingPlace,
} from '../../utils/topicUpcoming'
import './storyCharts.css'
import './UpcomingPanel.css'

interface Props {
  topic: string
  stateCode?: string | null
  city?: string | null
  /** The scope label in effect ("National", "Georgia", "Tuscaloosa"). */
  scopeLabel: string
  /** The topic in words ("data centers"). */
  subject: string
  /** The page the "look wider" link opens (the story's own path), keeping the screen. */
  basePath: string
}

const fmt = (n: number) => n.toLocaleString('en-US')
/** Items listed before "Show all". */
const FIRST_ITEMS = 5

/**
 * What is coming up on a topic (#1302): scheduled meetings and public hearings, soonest first, each saying what, when,
 * where and how to take part (the agenda, meeting page, livestream or official notice), with the quoted evidence that
 * ties it to the topic; then the state bills still open, dated by their last action. Only items with a real date from
 * today on. An empty scope says so and offers the next level up.
 */
export default function UpcomingPanel({ topic, stateCode, city, scopeLabel, subject, basePath }: Props) {
  const q = useTopicUpcoming(topic, stateCode, city)
  const [showAll, setShowAll] = useState(false)
  const title = (
    <p className="sc-h">
      Coming up on {subject} · {scopeLabel}
    </p>
  )
  if (q.isLoading) {
    return (
      <div className="sc-block">
        {title}
        <p className="sc-note" role="status">Loading what&apos;s coming up…</p>
      </div>
    )
  }
  if (q.isError || !q.data) {
    return (
      <div className="sc-block">
        {title}
        <p className="sc-note">What&apos;s coming up could not be loaded right now.</p>
      </div>
    )
  }
  const d = q.data
  const items = showAll ? d.items : d.items.slice(0, FIRST_ITEMS)
  const wider = broaderHref(basePath, d.broader, 'screen=upcoming')
  const bills = d.pending_bills
  const billsWhere = stateCode ? (d.state ?? stateCode) : 'any state'

  return (
    <div className="sc-block up">
      {title}
      {d.total === 0 ? (
        <div className="up-empty" role="status">
          <p className="up-empty-line">{nothingUpcoming(scopeLabel)}</p>
          {wider && d.broader && (
            <p className="sc-note">
              {d.broader.total > 0 ? (
                <Link to={wider}>
                  See {fmt(d.broader.total)} coming up {d.broader.label === 'National' ? 'nationally' : `in ${d.broader.label}`} →
                </Link>
              ) : (
                <>Nothing {d.broader.label === 'National' ? 'nationally' : `in ${d.broader.label}`} either.</>
              )}
            </p>
          )}
        </div>
      ) : (
        <>
          <ol className="up-list">
            {items.map((i) => (
              <li key={i.upcoming_id} className="up-item">
                <div className="up-when">
                  <span className="up-date">{upcomingDate(i.date)}</span>
                  {i.time && <span className="up-time">{i.time}</span>}
                </div>
                <div className="up-body">
                  <p className="up-kind">
                    <span className={`up-tag up-tag--${i.kind}`}>{upcomingKindLabel(i)}</span>
                    <span className="up-place">{upcomingPlace(i)}</span>
                  </p>
                  <p className="up-title">{i.title ?? i.body_name ?? 'Meeting'}</p>
                  {i.location && <p className="up-meta">{i.location}</p>}
                  <p className="up-basis">{upcomingBasisNote(i, subject)}</p>
                  <blockquote className="up-quote">
                    “{highlightSnippet(i.matched_text)}”
                    {i.match_basis === 'place_discussed_before' && i.prior_url && (
                      <a className="up-prior" href={i.prior_url} target="_blank" rel="noopener noreferrer">
                        Watch that meeting
                      </a>
                    )}
                  </blockquote>
                  <a className="up-go" href={i.source_url} target="_blank" rel="noopener noreferrer">
                    {i.source_label === 'Livestream' ? 'Watch or attend: livestream' : `Take part: ${i.source_label.toLowerCase()}`} →
                  </a>
                </div>
              </li>
            ))}
          </ol>
          {d.items.length > FIRST_ITEMS && (
            <button type="button" className="lm-chip" onClick={() => setShowAll((v) => !v)}>
              {showAll ? 'Show fewer' : `Show all ${fmt(d.items.length)}`}
            </button>
          )}
          {d.total > d.items.length && <p className="sc-note">Showing the first {fmt(d.items.length)} of {fmt(d.total)}.</p>}
        </>
      )}

      <div className="up-bills">
        <p className="la-sub">State bills still open{stateCode ? ` in ${billsWhere}` : ''} ({fmt(bills.total)})</p>
        {bills.total === 0 ? (
          <p className="sc-note">No open state bill on {subject} in {billsWhere} in our copy of OpenStates.</p>
        ) : (
          <ul className="up-billlist">
            {bills.items.map((b) => (
              <li key={b.bill_id}>
                <span className="up-bill-id">
                  {b.url ? (
                    <a href={b.url} target="_blank" rel="noopener noreferrer">
                      {b.state_code} {b.identifier ?? 'Bill'}
                    </a>
                  ) : (
                    `${b.state_code} ${b.identifier ?? 'Bill'}`
                  )}
                </span>
                <span className="up-bill-title">{b.title}</span>
                <span className="up-meta">
                  {b.status === 'passed_chamber' ? 'Passed one chamber' : 'Not yet passed or failed'}
                  {b.last_action_date ? ` · last action ${upcomingDate(b.last_action_date)}` : ''}
                  {b.last_action ? `: ${b.last_action}` : ''}
                </span>
              </li>
            ))}
          </ul>
        )}
        {bills.total > bills.items.length && (
          <p className="sc-note">The {fmt(bills.items.length)} furthest along are listed; the State bills screen has them all.</p>
        )}
      </div>

      <p className="sc-note">
        Only items with a real date from {upcomingDate(d.as_of)} on. A meeting is listed when its posted agenda names the
        topic, an official notice lists a hearing, or the same government discussed it in a recorded meeting in the last two
        years (its agenda isn&apos;t posted yet). Bills show their last recorded action
        {bills.latest_action_seen ? `; the newest action in our copy is from ${upcomingDate(bills.latest_action_seen)}` : ''}.
        {d.last_updated ? ` Calendars last checked ${upcomingDate(d.last_updated.slice(0, 10))}.` : ''}
      </p>
    </div>
  )
}
