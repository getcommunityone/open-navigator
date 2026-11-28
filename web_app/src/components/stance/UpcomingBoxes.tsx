import { useMemo } from 'react'
import type { TopicUpcomingResponse } from '../../api/topicUpcoming'
import { UPCOMING_KIND_LABEL, upcomingKindColor, upcomingStrip } from '../../utils/screenBoxes'
import { upcomingDate } from '../../utils/topicUpcoming'
import ScreenBoxes from './ScreenBoxes'
import './storyCharts.css'

const fmt = (n: number) => n.toLocaleString('en-US')
const NOUN: Record<string, [string, string]> = {
  meeting: ['meeting', 'meetings'],
  hearing: ['hearing', 'hearings'],
  event: ['event', 'events'],
  bill_action: ['bill action', 'bill actions'],
  deadline: ['deadline', 'deadlines'],
}

interface Props {
  data: TopicUpcomingResponse | null | undefined
  scopeLabel: string
}

/**
 * The Coming up screen's box strip (#1415): one box per upcoming item on a date strip (the next 30, 60 or 90 days, whichever
 * holds them), a column per week, coloured by kind (scheduled meeting, hearing, bill action, nonprofit event), with a legend and
 * a takeaway title ("6 meetings ahead in Georgia; the next is Dec 1"). Only dated items the API returned; none are added.
 */
export default function UpcomingBoxes({ data, scopeLabel }: Props) {
  const strip = useMemo(() => (data ? upcomingStrip(data) : null), [data])
  if (!data || !strip) return null
  if (data.items.length === 0) {
    return <ScreenBoxes spec={{ title: `Nothing is scheduled ahead in ${scopeLabel}`, unit: 'items', groups: [] }} />
  }
  const kinds = [...new Set(data.items.map((i) => i.kind))]
  const n = data.total
  const noun = kinds.length === 1 ? NOUN[kinds[0]!]![n === 1 ? 0 : 1] : n === 1 ? 'item' : 'items'
  const where = scopeLabel === 'National' ? 'across America' : `in ${scopeLabel}`
  const title = `${fmt(n)} ${noun} ahead ${where}; the next is ${upcomingDate(strip.next, false) ?? 'soon'}`
  const counts = kinds.map((k) => ({ k, n: data.items.filter((i) => i.kind === k).length }))
  const tallest = Math.max(1, ...strip.weeks.map((w) => w.items.length))
  return (
    <figure className="sb sb-strip" data-screen-boxes="" aria-label={title}>
      <figcaption className="sb-title" data-chart-title="">
        {title}
      </figcaption>
      <div className="sb-weeks" role="img" aria-label={`Upcoming items by week, the next ${strip.days} days`} style={{ ['--sb-weeks' as string]: strip.weeks.length, ['--sb-rows' as string]: Math.min(tallest, 6) }}>
        {strip.weeks.map((w) => (
          <div key={w.start} className="sb-week" title={`Week of ${upcomingDate(w.start, false)}`}>
            {w.items.map((i, n) => (
              <span key={i.id} className="sb-box" data-box="" data-group={i.kind} style={{ background: upcomingKindColor(i.kind), ['--i' as string]: n + strip.weeks.indexOf(w) }} title={`${upcomingDate(i.date, false)}: ${i.title}`} />
            ))}
          </div>
        ))}
      </div>
      <div className="sb-axis" aria-hidden="true">
        <span>{upcomingDate(data.as_of, false)}</span>
        <span>{`+${strip.days} days`}</span>
      </div>
      <ul className="sb-legend" data-chart-legend="">
        {counts.map(({ k, n: c }) => (
          <li key={k}>
            <span className="sb-swatch" style={{ background: upcomingKindColor(k) }} aria-hidden="true" />
            {UPCOMING_KIND_LABEL[k]} <b>{fmt(c)}</b>
          </li>
        ))}
      </ul>
      {(strip.later > 0 || data.total > data.items.length) && (
        <p className="sb-note">
          {strip.later > 0 ? `${fmt(strip.later)} more fall after ${strip.days} days. ` : ''}
          {data.total > data.items.length ? `Showing ${fmt(data.items.length)} of ${fmt(data.total)}.` : ''}
        </p>
      )}
    </figure>
  )
}
