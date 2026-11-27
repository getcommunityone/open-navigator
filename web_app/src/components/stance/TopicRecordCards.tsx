import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import type { TopicDecision, TopicMeeting } from '../../api/topics'
import { highlightSnippet } from '../../lib/highlight'
import { commentersLine, positionChips, speakerLine } from '../../utils/saidCards'
import { pickDisplay } from '../../utils/displayFit'

const fmtDate = (d?: string | null) => {
  if (!d) return null
  const t = new Date(`${d.slice(0, 10)}T12:00:00`)
  return Number.isNaN(t.getTime()) ? null : t.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

/** An in-app path opens in place; a recording opens in a new tab. */
function AnyLink({ href, className, children, label }: { href: string; className?: string; children: ReactNode; label?: string }) {
  return href.startsWith('/') ? (
    <Link to={href} className={className} aria-label={label}>
      {children}
    </Link>
  ) : (
    <a href={href} target="_blank" rel="noopener noreferrer" className={className} aria-label={label}>
      {children}
    </a>
  )
}

/**
 * One "What was said" card (#1293): the meeting (its name and date are the link, and the whole card is the tap target, to the
 * recording or else the meeting page), the verbatim passage with the matched words marked, who said it as served (or
 * "Speaker not identified"), the named commenters on the topic, and the position chips from the meeting's AI reading.
 */
export function SaidQuoteCard({ m, slug }: { m: TopicMeeting; slug: string }) {
  const date = fmtDate(m.date)
  const linkText = [m.title ?? 'Meeting', date].filter(Boolean).join(' · ')
  const primary = m.video_url ?? m.meeting_url ?? null
  const chips = positionChips(slug, m)
  const who = speakerLine(m)
  const others = commentersLine(m, who ? 'Also spoke on it' : 'Spoke on it at this meeting')
  return (
    <li className={`topic-story-item topic-story-card${primary ? ' is-linked' : ''}`} data-testid="said-card">
      {primary ? (
        <AnyLink href={primary} className="topic-story-item-title topic-story-card-link" label={`${linkText}${m.video_url ? ' (plays the recording)' : ' (opens the meeting)'}`}>
          {linkText}
        </AnyLink>
      ) : (
        <p className="topic-story-item-title">{linkText}</p>
      )}
      <p className="topic-story-item-meta">{[m.jurisdiction_name ?? m.city, m.state].filter(Boolean).join(', ')}</p>
      {m.excerpt && <blockquote className="topic-story-quote">“{highlightSnippet(m.excerpt)}”</blockquote>}
      <p className={`topic-story-speaker${who ? '' : ' is-unknown'}`} data-testid="said-speaker">
        {who ? `Said by ${who}` : 'Speaker not identified'}
      </p>
      {others && <p className="topic-story-item-meta">{others}</p>}
      {chips.length > 0 && (
        <ul className="topic-story-chips" aria-label="Positions on record">
          {chips.map((c) => (
            <li key={c.source} className={`topic-story-chip is-${c.side}`} data-source={c.source}>
              {c.label}
            </li>
          ))}
        </ul>
      )}
      <p className="topic-story-card-links">
        {m.video_url && (
          <a href={m.video_url} target="_blank" rel="noopener noreferrer">
            Watch the meeting ↗
          </a>
        )}
        {m.meeting_url && <Link to={m.meeting_url}>Meeting page</Link>}
      </p>
    </li>
  )
}

/**
 * One decision card (#1293): its title links the decision's page; the meeting's name and date link the recording (decisions
 * carry no timestamp, so it opens at the start) or else the meeting page. The whole card opens the decision on a phone.
 */
export function TopicDecisionCard({ d }: { d: TopicDecision }) {
  const date = fmtDate(d.meeting_date)
  const meetingText = [d.meeting_name ?? 'Meeting', date].filter(Boolean).join(' · ')
  const meetingHref = d.video_url ?? d.meeting_url ?? null
  return (
    <li className="topic-story-item topic-story-card is-linked" data-testid="decision-card" data-relevance={d.relevance}>
      <Link to={d.decision_url} className="topic-story-item-title topic-story-card-link">
        {d.title}
      </Link>
      <p className="topic-story-item-meta">
        {[d.jurisdiction_name, d.state_code].filter(Boolean).join(', ')}
        {d.outcome ? ` · ${d.outcome}` : ''}
      </p>
      {d.excerpt && <p className="topic-story-item-body">{highlightSnippet(d.excerpt)}</p>}
      <p className="topic-story-card-links">
        {meetingHref ? (
          <AnyLink href={meetingHref} label={`${meetingText}${d.video_url ? ' (plays the recording)' : ' (opens the meeting)'}`}>
            {meetingText}
            {d.video_url ? ' ↗' : ''}
          </AnyLink>
        ) : (
          <span>{meetingText}</span>
        )}
        {d.video_url && d.meeting_url && <Link to={d.meeting_url}>Meeting page</Link>}
        <Link to={d.decision_url}>Decision details</Link>
      </p>
    </li>
  )
}

/**
 * One Decisions panel ("Decisions on <topic>" or "Mentioned in passing", #1293) in the form the shared display rule picks
 * from its whole-scope count (utils/displayFit `pickDisplay`, #1289): nothing for 0, the cards for a handful, and otherwise
 * a sentence with the listed cards under a fold. The cards keep their matched passage (CLAUDE.md, match evidence), so a
 * unit chart, which would drop it, is not drawn here; its count sentence stands in.
 */
export function DecisionPanel({
  heading,
  total,
  items,
  testId,
  lead,
}: {
  heading: string
  total: number
  items: TopicDecision[]
  testId: string
  /** The count sentence for the folded form ("6 decisions only mention it in passing."). */
  lead: string
}) {
  const display = pickDisplay({ items: total })
  if (display.kind === 'empty' || items.length === 0) return null
  const cards = (
    <ul className="topic-story-list" data-testid={testId}>
      {items.map((x) => (
        <TopicDecisionCard key={x.event_decision_id} d={x} />
      ))}
    </ul>
  )
  return (
    <section className="topic-story-panel" data-display={display.kind}>
      <h3 className="topic-story-subhead">{heading}</h3>
      {display.kind === 'list' ? (
        cards
      ) : (
        <>
          <p className="stance-fit-lead">{lead}</p>
          <details className="stance-fit-more">
            <summary>
              Show the {items.length < total ? `newest ${items.length.toLocaleString('en-US')}` : items.length.toLocaleString('en-US')}
            </summary>
            {cards}
          </details>
        </>
      )}
    </section>
  )
}
