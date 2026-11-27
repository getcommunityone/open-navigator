import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { createPortal } from 'react-dom'
import { useQuery } from '@tanstack/react-query'
import { pickDisplay } from '../../utils/displayFit'
import { fetchTopicTimeline, type TimelineMilestone, type TopicTimelineResponse } from '../../api/topicTimeline'
import {
  buildSeries,
  dateToYearPos,
  defaultMarker,
  defaultSeriesMode,
  gapYears,
  isHollow,
  milestoneLanes,
  MILESTONE_LABELS,
  niceMax,
  splitRun,
  stepMarker,
  thinNote,
  thinYears,
  timelinePads,
  MIN_RECORDED_FOR_ZERO,
  type SeriesMode,
} from '../../utils/storyTimeline'
import { HOUSE_STYLE } from '../../utils/houseTheme'
import { DataTable } from '../matrix/SectionShell'
import { Tooltip, useTooltip } from '../matrix/Tooltip'
import { useChartReveal } from './useChartReveal'
import { useChartWidth } from './useChartWidth'
import { pickYearTicks } from '../../utils/axisTicks'
import './storyCharts.css'

const fmt = (n: number) => n.toLocaleString('en-US')
const COVERAGE_NOTE =
  'Meetings in our record by year; recording coverage grew sharply in 2025–26, so the rise partly reflects coverage.'
/** Below this width the milestone track becomes a tap list (the reference's compact breakpoint). */
const COMPACT_W = 560
const TAP_LIST_FIRST = 12
/** The line's draw-in, matching `--d-4` in storyCharts.css: points and milestones are timed against it. */
const DRAW_MS = 900
/** Delays for `.sc-pt` / `.sc-ms-pop` (opacity, transform, fill): the entrance waits, a selection's colour change never does. */
const popDelay = (ms: number) => `${ms}ms, ${ms}ms, 0ms`

interface Props {
  topic: string
  stateCode?: string
  city?: string | null
  scopeLabel: string
  /** Lower-case subject for sentences ("data centers"). */
  subject: string
  idBase: string
}

export function useTopicTimeline(topic: string, stateCode?: string, city?: string | null, enabled = true) {
  const c = stateCode && city ? city : ''
  return useQuery<TopicTimelineResponse>({
    queryKey: ['topic-timeline', topic, stateCode ?? 'national', c],
    queryFn: () => fetchTopicTimeline(topic, stateCode, c || undefined),
    enabled,
    staleTime: 5 * 60_000,
    retry: 1,
  })
}

function prettyDate(iso: string): string {
  const d = new Date(`${iso.slice(0, 10)}T12:00:00Z`)
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric', timeZone: 'UTC' })
}

function MilestoneCard({ m }: { m: TimelineMilestone }) {
  const what = MILESTONE_LABELS[m.kind]
  const place = [m.place, m.state_code && m.place !== m.state_code ? m.state_code : null].filter(Boolean).join(', ')
  return (
    <div className="sc-detail" aria-live="polite">
      <div className="sc-detail-date">{prettyDate(m.date)}</div>
      <h3 className="sc-detail-title">
        {what}
        {place ? ` · ${place}` : ''}
        <span className="sc-tag">{m.source === 'ai_reading' ? 'AI reading' : 'Official record'}</span>
      </h3>
      {m.title && <p className="sc-detail-body">{m.title}</p>}
      <p className="sc-detail-body">
        {m.source === 'ai_reading'
          ? `What officials did with the item, as an AI (Jev) read the meeting transcript; not an official record.`
          : 'The bill as recorded by the state legislature (Open States).'}{' '}
        {m.url && (
          <a href={m.url} target="_blank" rel="noopener noreferrer">
            {m.kind === 'bill_enacted' ? 'Open the bill' : 'Watch the meeting'} ↗
          </a>
        )}
      </p>
    </div>
  )
}

/**
 * The Meetings screen's trend line (#1140, the reference's §4.5): meetings per year for the topic and scope, or the
 * topic's share of all recorded meetings, with an aligned milestone track underneath. A click or the arrow keys pick a
 * marker and the card below shows it; under 560px the markers become a tap list. A year with no data is a gap.
 */
export default function TimelineChart({ topic, stateCode, city, scopeLabel, subject, idBase }: Props) {
  const q = useTopicTimeline(topic, stateCode, city)
  const { ref, width } = useChartWidth<HTMLDivElement>()
  const { bind, tip } = useTooltip()
  // null until the reader picks: the chart opens on the share when a year's count isn't comparable (#1207).
  const [mode, setMode] = useState<SeriesMode | null>(null)
  const [sel, setSel] = useState(-1)
  const [tableOpen, setTableOpen] = useState(false)
  const [showAll, setShowAll] = useState(false)
  const trackRef = useRef<SVGSVGElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  const data = q.data
  const years = useMemo(() => data?.years ?? [], [data])
  const ms = useMemo(() => data?.milestones ?? [], [data])
  const shareOk = Boolean(data?.coverage_available) && years.some((y) => y.share != null)
  const thin = useMemo(() => thinYears(years), [years])
  const openOn = useMemo(() => defaultSeriesMode(years, Boolean(data?.coverage_available)), [years, data])
  const activeMode: SeriesMode = (mode ?? openOn) === 'share' && shareOk ? 'share' : 'meetings'
  const runs = useMemo(() => buildSeries(years, activeMode), [years, activeMode])
  // Dashed pieces only on the count line: the share stays comparable in a thin year.
  const pieces = useMemo(() => runs.map((run) => splitRun(run, activeMode === 'meetings' ? thin : new Set<number>())), [runs, activeMode, thin])
  const gaps = useMemo(() => gapYears(years, activeMode), [years, activeMode])
  const lanes = useMemo(() => milestoneLanes(ms), [ms])

  useEffect(() => setSel(defaultMarker(ms)), [ms])
  // The reference's §4.5 entrance (#1228): when the chart scrolls into view the line draws left to right, the year points
  // pop in as it passes them and the milestone squares follow along the track. A new series (scope or mode) replays it.
  const { ref: revealRef, revealed, reduced } = useChartReveal<SVGSVGElement>(runs)

  if (q.isLoading) return <p className="folio-muted" role="status">Loading the timeline…</p>
  if (q.isError) return <p className="stance-nodata" role="status">The timeline could not be loaded right now.</p>
  const pts = runs.flat()
  if (!data || pts.length === 0) return null
  // A line only with 6 or more points (#1289, utils/displayFit): fewer years read as the numbers in a sentence.
  const counts = buildSeries(years, 'meetings').flat()
  const fit = pickDisplay({ items: counts.reduce((a, p) => a + p.value, 0), seriesPoints: pts.length })
  if (fit.kind !== 'line') {
    return (
      <div className="sc-block" data-display={fit.kind}>
        <p className="sc-h">
          Meetings that discussed {subject}, by year · {scopeLabel}
        </p>
        <p className="stance-fit-lead">
          {counts.length === 1
            ? `All in ${counts[0]!.year}: ${fmt(counts[0]!.value)} ${counts[0]!.value === 1 ? 'meeting' : 'meetings'}.`
            : `${counts.map((p) => `${p.year}: ${fmt(p.value)}`).join('; ')}.`}{' '}
          Too few years on record for a trend line.
        </p>
      </div>
    )
  }

  const w = Math.max(280, width)
  const h = 240
  const { padL, padR } = timelinePads(w, ms.length > 0)
  const padT = 20
  const padB = 28
  const allYears = pts.map((p) => p.year)
  const msPos = ms.map((m) => dateToYearPos(m.date)).filter((v): v is number => v != null)
  const x0 = Math.min(...allYears, ...msPos.map(Math.floor))
  const x1 = Math.max(...allYears, ...msPos.map(Math.floor))
  const span = Math.max(1, x1 - x0 + 1)
  // A year's point sits at the middle of its year, so a milestone dated in that year lands under or near it.
  const xs = (pos: number) => padL + ((pos - x0) / span) * (w - padL - padR)
  const xYear = (y: number) => xs(y + 0.5)
  // How far along the plot an x is (0 at the left edge, 1 at the right), and when the drawing line reaches it.
  const alongFrac = (x: number) => Math.min(1, Math.max(0, (x - padL) / Math.max(1, w - padL - padR)))
  const alongMs = (x: number) => Math.round(alongFrac(x) * (DRAW_MS - 150))
  const vmax = niceMax(Math.max(...pts.map((p) => p.value)))
  const ys = (v: number) => h - padB - (v / vmax) * (h - padT - padB)
  const ticks = [0, vmax / 2, vmax]
  // Year labels chosen by the room they have, so they never run together on a phone.
  const yearTicks = pickYearTicks(Array.from({ length: span }, (_, i) => x0 + i), w - padL - padR)
  const valueText = (v: number) => (activeMode === 'share' ? `${v < 10 ? v.toFixed(1) : Math.round(v)}%` : fmt(v))
  const last = pts[pts.length - 1]!
  const compact = w < COMPACT_W
  const drawnYears = new Set(allYears)
  const thinDrawn = new Set([...thin].filter((y) => drawnYears.has(y)))
  const thinText = thinNote(years, thinDrawn)
  const hollowShare = activeMode === 'share' && pts.some((p) => isHollow(p, 'share', thin))

  const pick = (i: number, focus = false) => {
    setSel(i)
    if (focus) {
      const host = compact ? listRef.current : trackRef.current
      requestAnimationFrame(() => host?.querySelector<HTMLElement | SVGElement>(`[data-ms="${i}"]`)?.focus())
    }
  }
  const onMsKey = (e: KeyboardEvent) => {
    const to = stepMarker(sel, e.key, ms.length)
    if (to == null) return
    e.preventDefault()
    e.stopPropagation()
    if (compact && !showAll && to >= TAP_LIST_FIRST) setShowAll(true)
    pick(to, true)
  }
  const laneH = 26
  const trackH = 16 + lanes.length * laneH
  // Newest first in the tap list.
  const tapOrder = ms.map((_, i) => i).reverse()
  const tapShown = showAll ? tapOrder : tapOrder.slice(0, TAP_LIST_FIRST)

  return (
    <div className="sc-block">
      <p className="sc-h">
        {activeMode === 'share' ? `Share of recorded meetings that discussed ${subject}, by year` : `Meetings that discussed ${subject}, by year`} · {scopeLabel}
      </p>
      {shareOk && (
        <div className="sc-controls">
          <div className="folio-seg" role="group" aria-label="Series">
            <button type="button" aria-pressed={activeMode === 'meetings'} onClick={() => setMode('meetings')}>
              Meetings
            </button>
            <button type="button" aria-pressed={activeMode === 'share'} onClick={() => setMode('share')}>
              Share of recorded meetings
            </button>
          </div>
        </div>
      )}
      <div ref={ref}>
        <svg ref={revealRef} className={`sc-svg sc-trend${revealed ? ' is-revealed' : ''}`} viewBox={`0 0 ${w} ${h}`} role="group" aria-label={`Trend line, ${scopeLabel}`}>
          {ticks.map((t) => (
            <g key={t}>
              <line x1={padL} x2={w - padR} y1={ys(t)} y2={ys(t)} stroke={t === 0 ? 'var(--ink)' : 'var(--rule)'} strokeWidth={t === 0 ? 1.5 : 1} />
              <text className="sc-micro" x={padL - 8} y={ys(t) + 4} textAnchor="end">
                {valueText(t)}
              </text>
            </g>
          ))}
          {yearTicks.map((y) => (
            <text key={y} className="sc-micro" x={xYear(y)} y={h - 8} textAnchor="middle">
              {y}
            </text>
          ))}
          {pieces.flat().map((piece) => {
            const d = piece.points.map((p, i) => `${i ? 'L' : 'M'} ${xYear(p.year).toFixed(1)} ${ys(p.value).toFixed(1)}`).join(' ')
            return piece.dashed ? (
              <path key={`${activeMode}-thin-${piece.points[0]!.year}`} className="sc-line sc-line--thin" d={d} />
            ) : (
              <path
                key={`${activeMode}-${piece.points[0]!.year}`}
                className={`sc-line${revealed && !reduced ? ' is-drawing' : ''}`}
                pathLength={1}
                d={d}
              />
            )
          })}
          {pts.map((p) => {
            const y = p.src
            const sub = [
              y.passages != null ? `${fmt(y.passages)} passages` : null,
              y.all_recorded_meetings != null ? `of ${fmt(y.all_recorded_meetings)} recorded meetings` : null,
              y.share != null ? `${(y.share * 100).toFixed(1)}%` : null,
            ]
              .filter(Boolean)
              .join(' · ')
            const hollow = isHollow(p, activeMode, thin)
            const caveat = hollow
              ? activeMode === 'meetings'
                ? ' (few meetings were recorded that year: the count is not comparable)'
                : ` (fewer than ${MIN_RECORDED_FOR_ZERO} meetings recorded)`
              : ''
            const label = `${y.year}: ${fmt(y.meetings)} meetings${sub ? `, ${sub}` : ''}${caveat}`
            return (
              <rect
                key={`${activeMode}-${p.year}`}
                className={`sc-pt sc-focusable${hollow ? ' is-hollow' : ''}`}
                style={reduced ? undefined : { transitionDelay: popDelay(alongMs(xYear(p.year))) }}
                x={xYear(p.year) - 3.5}
                y={ys(p.value) - 3.5}
                width={7}
                height={7}
                tabIndex={0}
                role="img"
                aria-label={label}
                {...bind({ cat: y.year, val: activeMode === 'share' ? valueText(p.value) : `${fmt(y.meetings)} meetings`, sub: (sub + caveat).trim() || undefined })}
              />
            )
          })}
          <text className="sc-end" style={reduced ? undefined : { transitionDelay: `${DRAW_MS}ms` }} x={xYear(last.year) + 9} y={ys(last.value) + 7}>
            {valueText(last.value)}
          </text>
        </svg>

        {ms.length > 0 && !compact && (
          <svg
            ref={trackRef}
            className={`sc-svg sc-track${revealed ? ' is-revealed' : ''}`}
            viewBox={`0 0 ${w} ${trackH}`}
            role="group"
            aria-label={`Milestones, ${scopeLabel}: ${ms.length} dated events. Use the arrow keys to move between them.`}
            onKeyDown={onMsKey}
            data-keys-own
          >
            {lanes.map((k, li) => {
              const y = 10 + li * laneH + laneH / 2
              const n = ms.filter((m) => m.kind === k).length
              return (
                <g key={k}>
                  <line x1={padL} x2={w - padR} y1={y} y2={y} stroke="var(--rule)" strokeWidth={1} />
                  <text className="sc-micro" x={w - padR + 6} y={y + 4}>
                    {k === 'bill_enacted' ? 'Bills' : MILESTONE_LABELS[k].split(' ')[0]} · {n}
                  </text>
                </g>
              )
            })}
            {ms.map((m, i) => {
              const pos = dateToYearPos(m.date)
              if (pos == null) return null
              const li = lanes.indexOf(m.kind)
              const cx = xs(pos)
              const cy = 10 + li * laneH + laneH / 2
              const on = i === sel
              const size = on ? 12 : 8
              return (
                <g
                  key={`${m.date}-${m.kind}-${i}`}
                  className="sc-ms"
                  data-ms={i}
                  role="button"
                  tabIndex={on || (sel < 0 && i === ms.length - 1) ? 0 : -1}
                  aria-pressed={on}
                  aria-label={`${prettyDate(m.date)}: ${MILESTONE_LABELS[m.kind]}${m.place ? `, ${m.place}` : ''}${m.source === 'ai_reading' ? ' (AI reading)' : ''}`}
                  onClick={() => pick(i)}
                  onFocus={() => setSel(i)}
                >
                  <rect x={cx - 8} y={cy - 10} width={16} height={20} fill="transparent" />
                  <rect className="sc-ms-sq sc-ms-pop" style={reduced ? undefined : { transitionDelay: popDelay(DRAW_MS - 200 + Math.round(alongFrac(cx) * 500)) }} x={cx - size / 2} y={cy - size / 2} width={size} height={size} />
                </g>
              )
            })}
          </svg>
        )}
        {ms.length > 0 && compact && (
          <div ref={listRef} className="sc-taplist" role="group" aria-label={`Milestones, ${scopeLabel}, newest first`} onKeyDown={onMsKey} data-keys-own>
            {tapShown.map((i) => {
              const m = ms[i]!
              return (
                <button key={`${m.date}-${i}`} type="button" className="sc-tapbtn" data-ms={i} aria-pressed={i === sel} onClick={() => pick(i)}>
                  <span className="sc-tapsq" aria-hidden="true" />
                  <span className="sc-tapdate">{prettyDate(m.date)}</span>
                  <span>
                    {MILESTONE_LABELS[m.kind]}
                    {m.place ? ` · ${m.place}` : ''}
                  </span>
                </button>
              )
            })}
            {!showAll && tapOrder.length > TAP_LIST_FIRST && (
              <button type="button" className="folio-btn" onClick={() => setShowAll(true)}>
                Show all {fmt(ms.length)} milestones
              </button>
            )}
          </div>
        )}
        {sel >= 0 && ms[sel] && <MilestoneCard m={ms[sel]!} />}
      </div>

      <p className="sc-note">
        {COVERAGE_NOTE}
        {activeMode === 'share' && ' The share divides by every recorded meeting in the same place and year.'}
        {thinText &&
          (activeMode === 'meetings'
            ? ` ${thinText} ${thinDrawn.size === 1 ? 'It is drawn as a hollow point' : 'They are drawn as hollow points'} on a dashed line.`
            : ` ${thinText} The share of recorded meetings still compares, so the chart opens on it; Meetings shows the counts.`)}
        {hollowShare && ` A hollow point is a share of fewer than ${MIN_RECORDED_FOR_ZERO} recorded meetings.`}
        {gaps.length > 0 && ` No line is drawn for ${gaps.join(', ')}: too few recorded meetings to say.`}
        {data.undated_meetings > 0 && ` ${fmt(data.undated_meetings)} ${data.undated_meetings === 1 ? 'meeting has' : 'meetings have'} no date and ${data.undated_meetings === 1 ? 'is' : 'are'} not on the line.`}
        {ms.length > 0 &&
          ' Milestones are meetings where officials approved, denied, tabled or paused the item, as an AI read the transcript'}
        {ms.length > 0 && (data.bills_available ? ', and state bills enacted.' : '.')}
      </p>
      {ms.length > 0 && !compact && <p className="stance-note stance-hint-keys">Select a square on the track, then use the arrow keys to move between milestones.</p>}
      <button type="button" className="folio-btn" aria-expanded={tableOpen} aria-controls={`${idBase}-tl-table`} onClick={() => setTableOpen((o) => !o)}>
        {tableOpen ? 'Hide data table' : 'Show data table'} {tableOpen ? '↑' : '↓'}
      </button>
      {tableOpen && (
        <DataTable
          id={`${idBase}-tl-table`}
          caption={`Data table: meetings that discussed ${subject} by year, ${scopeLabel}`}
          spec={{
            columns: [
              { label: 'Year' },
              { label: 'Meetings', numeric: true },
              { label: 'Passages', numeric: true },
              { label: 'Recorded meetings', numeric: true },
              { label: 'Share', numeric: true },
            ],
            rows: years.map((y) => [
              y.year,
              fmt(y.meetings),
              y.passages != null ? fmt(y.passages) : '—',
              y.all_recorded_meetings != null ? fmt(y.all_recorded_meetings) : '—',
              y.share != null ? `${(y.share * 100).toFixed(1)}%` : '—',
            ]),
          }}
        />
      )}
      {typeof document !== 'undefined' && createPortal(<div className="folio" style={HOUSE_STYLE}><Tooltip tip={tip} /></div>, document.body)}
    </div>
  )
}
