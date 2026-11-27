import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchTopicLocalActions, type ActionGroup, type TopicLocalActionsResponse } from '../../api/topicPolicy'
import { STATE_CODE_TO_NAME } from '../../utils/stateMapping'
import { ACTION_FILL, ACTION_ORDER, actionLabels, actionTotal } from '../../utils/topicPolicy'
import { useChartWidth } from './useChartWidth'
import './storyCharts.css'

interface Props {
  topic: string
  stateCode?: string
  scopeLabel: string
  subject: string
}

const fmt = (n: number) => n.toLocaleString('en-US')
const fmtDate = (iso: string | null) =>
  iso ? new Date(`${iso}T00:00:00`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : 'Date not recorded'
/** Meetings listed before "Show all". */
const FIRST_MEETINGS = 12

/**
 * Where local bodies acted (#1274): meetings where a council or board voted to move the topic forward, voted to stop or
 * limit it, or tabled or put it off, as read by the AI (Jev) from the transcript (public.topic_meeting_lean.outcome_group).
 * A stacked column per year, the states with most actions, and the meetings themselves, each linked to its recording.
 */
export default function LocalActionsTracker({ topic, stateCode, scopeLabel, subject }: Props) {
  const q = useQuery<TopicLocalActionsResponse>({
    queryKey: ['topic-local-actions', topic, stateCode ?? 'national'],
    queryFn: () => fetchTopicLocalActions(topic, stateCode),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  const labels = actionLabels(topic)
  const [only, setOnly] = useState<ActionGroup | null>(null)
  const [showAll, setShowAll] = useState(false)
  const [hoverYear, setHoverYear] = useState<string | null>(null)
  const { ref: figRef, width: figWidth } = useChartWidth<HTMLElement>(640)
  const meetings = useMemo(() => (q.data?.meetings ?? []).filter((m) => !only || m.outcome_group === only), [q.data, only])

  const title = (
    <p className="sc-h">
      Where local bodies acted on {subject} · {scopeLabel}
    </p>
  )
  if (q.isLoading) {
    return (
      <div className="sc-block">
        {title}
        <p className="sc-note" role="status">Loading local actions…</p>
      </div>
    )
  }
  if (q.isError || !q.data) {
    return (
      <div className="sc-block">
        {title}
        <p className="sc-note">Local actions could not be loaded right now.</p>
      </div>
    )
  }
  const d = q.data
  if (!d.available || d.total === 0) {
    return (
      <div className="sc-block">
        {title}
        <p className="sc-note">
          No meeting{scopeLabel === 'National' ? '' : ` in ${scopeLabel}`} has an AI reading of a vote or a delay on {subject} yet.
        </p>
      </div>
    )
  }

  // Stacked columns, one per year with an action.
  // Drawn at the host's real width so labels stay legible on a phone.
  const W = Math.max(280, figWidth)
  const H = W < 480 ? 160 : 180
  const padL = 28
  const padB = 22
  // Every year from the first to the last action, so an empty year is a gap on the axis, not skipped.
  const years = (() => {
    if (!d.by_year.length) return d.by_year
    const have = new Map(d.by_year.map((y) => [y.year, y.counts]))
    const lo = Number(d.by_year[0]!.year)
    const hi = Number(d.by_year[d.by_year.length - 1]!.year)
    const out = []
    for (let y = lo; y <= hi; y++) out.push({ year: String(y), counts: have.get(String(y)) ?? { advanced: 0, blocked: 0, tabled_or_deferred: 0 } })
    return out
  })()
  const shown = (c: (typeof years)[number]['counts']) => (only ? c[only] : actionTotal(c))
  const maxY = Math.max(1, ...years.map((y) => shown(y.counts)))
  const colW = years.length ? (W - padL) / years.length : 0
  const barW = Math.max(4, Math.min(28, colW - 4))
  const yScale = (n: number) => (n / maxY) * (H - padB - 8)
  const hover = hoverYear ? years.find((y) => y.year === hoverYear) : undefined
  const labelEvery = Math.ceil(years.length / Math.max(3, Math.floor(W / 80)))

  return (
    <div className="sc-block la">
      {title}
      <ul className="la-totals" aria-label="Totals">
        {ACTION_ORDER.map((g) => (
          <li key={g}>
            <button type="button" className="la-total" aria-pressed={only === g} onClick={() => setOnly(only === g ? null : g)}>
              <span className="lm-swatch" style={{ background: ACTION_FILL[g] }} aria-hidden="true" />
              <span className="la-num">{fmt(d.totals[g])}</span>
              <span className="la-word">{labels[g]}</span>
            </button>
          </li>
        ))}
      </ul>

      {years.length > 0 && (
        <figure className="la-fig" ref={figRef}>
          <svg viewBox={`0 0 ${W} ${H}`} className="sc-svg" role="img" aria-label={`Meetings with an action on ${subject}, by year`}>
            <line x1={padL} x2={W} y1={H - padB} y2={H - padB} stroke="var(--rule)" />
            <text x={padL - 6} y={H - padB - yScale(maxY) + 4} textAnchor="end" className="sc-micro">
              {maxY}
            </text>
            {years.map((y, i) => {
              const x = padL + i * colW + (colW - barW) / 2
              let base = H - padB
              return (
                <g
                  key={y.year}
                  onMouseEnter={() => setHoverYear(y.year)}
                  onMouseLeave={() => setHoverYear(null)}
                  onClick={() => setHoverYear((h) => (h === y.year ? null : y.year))}
                  opacity={hoverYear && hoverYear !== y.year ? 0.45 : 1}
                >
                  <rect x={padL + i * colW} y={0} width={colW} height={H - padB} fill="transparent" />
                  {ACTION_ORDER.map((g) => {
                    const n = only && only !== g ? 0 : y.counts[g]
                    if (!n) return null
                    const h = yScale(n)
                    base -= h
                    return <rect key={g} x={x} y={base + 1} width={barW} height={Math.max(1, h - 2)} rx={2} fill={ACTION_FILL[g]} />
                  })}
                  {((i % labelEvery === 0 && (labelEvery === 1 || years.length - 1 - i >= labelEvery)) || i === years.length - 1) && (
                    <text
                      x={i === years.length - 1 ? Math.min(W, x + barW) : i === 0 ? Math.max(padL, x) : x + barW / 2}
                      y={H - 6}
                      textAnchor={i === years.length - 1 ? 'end' : i === 0 ? 'start' : 'middle'}
                      className="sc-micro"
                    >
                      {y.year}
                    </text>
                  )}
                </g>
              )
            })}
          </svg>
          <figcaption className="lm-readout" aria-live="polite">
            {hover
              ? `${hover.year}: ${ACTION_ORDER.map((g) => `${hover.counts[g]} ${labels[g].toLowerCase()}`).join(', ')}`
              : `Meetings per year${d.undated ? `; ${d.undated} more have no recorded date` : ''}. Hover or tap a year for its counts.`}
          </figcaption>
        </figure>
      )}

      {!stateCode && d.by_state.length > 0 && (
        <div className="la-states">
          <p className="la-sub">By state ({d.by_state.length})</p>
          <ul className="la-statelist">
            {d.by_state.slice(0, 12).map((s) => {
              const n = actionTotal(s.counts)
              return (
                <li key={s.state_code} title={ACTION_ORDER.map((g) => `${s.counts[g]} ${labels[g].toLowerCase()}`).join(', ')}>
                  <span className="la-state">{s.state ?? STATE_CODE_TO_NAME[s.state_code] ?? s.state_code}</span>
                  <span className="la-strip" aria-hidden="true">
                    {ACTION_ORDER.map((g) =>
                      s.counts[g] ? <span key={g} style={{ flex: s.counts[g], background: ACTION_FILL[g] }} /> : null,
                    )}
                  </span>
                  <span className="la-n">{n}</span>
                </li>
              )
            })}
          </ul>
        </div>
      )}

      <p className="la-sub">
        Meetings{only ? `: ${labels[only].toLowerCase()}` : ''} ({fmt(meetings.length)})
      </p>
      <ul className="la-meetings">
        {(showAll ? meetings : meetings.slice(0, FIRST_MEETINGS)).map((m) => (
          <li key={`${m.video_id}-${m.outcome_group}`}>
            <span className="lm-swatch" style={{ background: ACTION_FILL[m.outcome_group] }} aria-hidden="true" />
            <span className="la-when">{fmtDate(m.meeting_date)}</span>
            <span className="la-where">
              {m.url ? (
                <a href={m.url} target="_blank" rel="noopener noreferrer">
                  {m.jurisdiction_name ?? 'Meeting'}
                  {m.state_code ? `, ${m.state_code}` : ''}
                </a>
              ) : (
                <>
                  {m.jurisdiction_name ?? 'Meeting'}
                  {m.state_code ? `, ${m.state_code}` : ''}
                </>
              )}
            </span>
            <span className="la-what">
              {labels[m.outcome_group]}
              {m.outcome_p != null && <span className="lm-meta"> · AI reading, {Math.round(m.outcome_p * 100)}% sure</span>}
            </span>
          </li>
        ))}
      </ul>
      {meetings.length > FIRST_MEETINGS && (
        <button type="button" className="lm-chip" onClick={() => setShowAll((v) => !v)}>
          {showAll ? 'Show fewer' : `Show all ${fmt(meetings.length)}`}
        </button>
      )}
      <p className="sc-note">
        What the body did, as an AI (Jev) read it from the meeting transcript, not from official minutes; the percent is how
        sure the reading was. A council, board or commission&apos;s action only, never a person&apos;s.
      </p>
    </div>
  )
}
