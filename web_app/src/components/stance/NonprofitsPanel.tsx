import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useTopicOrganizations } from '../../hooks/useTopicOrganizations'
import { highlightSnippet } from '../../lib/highlight'
import { countsSentence, pickDisplay } from '../../utils/displayFit'
import {
  methodCounts,
  noNonprofits,
  oneLine,
  placeOf,
  revenueLine,
  sentenceCase,
  sideLabel,
  whyListed,
} from '../../utils/topicOrganizations'
import { broaderHref } from '../../utils/topicUpcoming'
import { CountBars } from './FitDisplay'
import './storyCharts.css'
import './UpcomingPanel.css'
import './NonprofitsPanel.css'

interface Props {
  topic: string
  stateCode?: string | null
  city?: string | null
  /** The scope label in effect ("National", "Georgia"). */
  scopeLabel: string
  /** The topic in words ("water fluoridation"). */
  subject: string
  /** The page the "look wider" link opens (the story's own path), keeping the screen. */
  basePath: string
}

const fmt = (n: number) => n.toLocaleString('en-US')
/** Listed before "Show all": three fit a phone screen above the bottom bar. */
const FIRST_ITEMS = 3

/**
 * Who's working on this (#1345): the nonprofits tied to the topic in the scope, strongest evidence first (named in one of
 * the topic's meetings, then a 990 mission that names it, then a name that does, then an IRS category in the field). Each
 * says why it is listed, with the quoted evidence, and links to its page and website. A side shows only when the
 * organization's own name or mission states it. The summary figure follows the shared display rule (pickDisplay).
 */
export default function NonprofitsPanel({ topic, stateCode, city, scopeLabel, subject, basePath }: Props) {
  const q = useTopicOrganizations(topic, stateCode, city)
  const [showAll, setShowAll] = useState(false)
  const title = (
    <p className="sc-h">
      Nonprofits working on {subject} · {scopeLabel}
    </p>
  )
  if (q.isLoading) {
    return (
      <div className="sc-block">
        {title}
        <p className="sc-note" role="status">Loading nonprofits…</p>
      </div>
    )
  }
  if (q.isError || !q.data) {
    return (
      <div className="sc-block">
        {title}
        <p className="sc-note">The nonprofits could not be loaded right now.</p>
      </div>
    )
  }
  const d = q.data
  const rows = methodCounts(d)
  const display = pickDisplay({ items: d.total, categories: rows.map((r) => r.count) })
  const wider = broaderHref(basePath, d.broader, 'screen=nonprofits')
  const items = showAll ? d.items : d.items.slice(0, FIRST_ITEMS)

  if (display.kind === 'empty') {
    return (
      <div className="sc-block np">
        {title}
        <div className="up-empty" role="status">
          <p className="up-empty-line">{noNonprofits(scopeLabel)}</p>
          {wider && d.broader && (
            <p className="sc-note">
              {d.broader.total > 0 ? (
                <Link to={wider}>
                  See {fmt(d.broader.total)} {d.broader.label === 'National' ? 'nationally' : `in ${d.broader.label}`} →
                </Link>
              ) : (
                <>None {d.broader.label === 'National' ? 'nationally' : `in ${d.broader.label}`} either.</>
              )}
            </p>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="sc-block np">
      {title}
      <ol className="np-list">
        {items.map((o) => {
          const mission = oneLine(sentenceCase(o.mission))
          const money = revenueLine(o)
          const side = sideLabel(o.side)
          const quote = o.match_method === 'named_in_meeting' || o.match_method === 'keyword_in_mission' ? o.match_text : null
          return (
            <li key={o.master_org_id} className="np-item">
              <p className="np-name">
                <Link to={`/organizations/${encodeURIComponent(o.master_org_id)}`}>{o.org_name}</Link>
                {side && <span className="np-side">{side}</span>}
              </p>
              <p className="up-meta">{[placeOf(o), money].filter(Boolean).join(' · ')}</p>
              {mission && o.match_method !== 'keyword_in_mission' && <p className="np-mission">{mission}</p>}
              <p className="up-basis">{whyListed(o, subject)}</p>
              {quote && (
                <blockquote className="up-quote">
                  “{highlightSnippet(o.match_method === 'keyword_in_mission' ? (sentenceCase(quote) ?? quote) : quote)}”
                  {o.match_source_url && (
                    <a className="up-prior" href={o.match_source_url} target="_blank" rel="noopener noreferrer">
                      Watch that meeting
                    </a>
                  )}
                </blockquote>
              )}
              {o.website_url && (
                <a className="up-go" href={o.website_url} target="_blank" rel="noopener noreferrer">
                  Website →
                </a>
              )}
            </li>
          )
        })}
      </ol>
      {d.items.length > FIRST_ITEMS && (
        <button type="button" className="lm-chip" onClick={() => setShowAll((v) => !v)}>
          {showAll ? 'Show fewer' : `Show all ${fmt(d.items.length)}`}
        </button>
      )}
      {/* The counts by evidence after the list: on a phone the list is what fits first (useScreenFit). */}
      {display.kind === 'bars' || display.kind === 'top-bars' ? (
        <CountBars rows={rows} label={`Nonprofits by how they are tied to ${subject}`} />
      ) : display.kind !== 'list' ? (
        <p className="np-counts">{countsSentence(rows)}</p>
      ) : null}
      {d.total > d.items.length && <p className="sc-note">Showing the {fmt(d.items.length)} with the strongest evidence of {fmt(d.total)}.</p>}
      <p className="sc-note">
        From IRS and Form 990 records. A nonprofit is listed when it is named in a recorded meeting on {subject} in its state,
        its 990 mission or its name names the topic, or its IRS category is the topic&apos;s field. A side is shown only when the
        organization&apos;s own name or mission states it. Revenue is the latest figure it reported, with the tax year.
      </p>
    </div>
  )
}
