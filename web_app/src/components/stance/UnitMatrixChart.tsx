import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent, type MouseEvent } from 'react'
import { createPortal } from 'react-dom'
import type { DotsSpec } from '../../utils/stanceGame'
import { GROUP_COLORS, HOUSE_STYLE } from '../../utils/houseTheme'
import { STATE_CODE_TO_NAME } from '../../utils/stateMapping'
import { availableGroupings, groupRecords, layoutMatrix, sideLabelsFor, type GroupingKey, type MatrixRecord } from '../../utils/unitMatrix'
import { DataTable } from '../matrix/SectionShell'
import { Tooltip, useTooltip } from '../matrix/Tooltip'
import { youtubeThumbnail } from '../../lib/youtubeThumbnail'
import usePrefersReducedMotion from '../../hooks/usePrefersReducedMotion'
import MeetingVideoModal, { type MeetingVideo } from './MeetingVideoModal'
import { useChartWidth } from './useChartWidth'
import './storyCharts.css'
import { topicPositions } from '../../utils/topicPositions'

/** What a chart's own grouping is called on its toggle. */
const NATIVE_NAMES: Record<string, string> = {
  'job-claims': 'By phase',
  'agenda-items': 'Upcoming or past',
  decisions: 'Debated or not',
  sites: 'By status',
  projects: 'By status',
  'community-events': 'By kind',
}

const fmt = (n: number) => n.toLocaleString('en-US')

interface Props {
  spec: DotsSpec
  chartKey: string
  /** National scope groups places by state; a state scope groups them by town. */
  placeGrain: 'state' | 'town'
  /** Used for ids (data table). */
  idBase: string
  scopeLabel: string
}

/**
 * Unit matrix (#1140, the reference's §4.1): one square per real record, regrouped by a toggle into labelled blocks
 * "Name · N (x%)". Squares keep their identity across groupings and slide to their new place (no motion with
 * prefers-reduced-motion). Arrow keys move between squares; a meeting square plays its recording, any other opens its source.
 */
const DC_SIDE_LABELS = sideLabelsFor(topicPositions('data-centers'))

export default function UnitMatrixChart({ spec, chartKey, placeGrain, idBase, scopeLabel }: Props) {
  const reduced = usePrefersReducedMotion()
  const { ref, width } = useChartWidth<HTMLDivElement>()
  const svgRef = useRef<SVGSVGElement>(null)
  const { bind, tip, hide } = useTooltip()
  const [rove, setRove] = useState(0)
  const [revealed, setRevealed] = useState(reduced)
  const [tableOpen, setTableOpen] = useState(false)
  const [playing, setPlaying] = useState<MeetingVideo | null>(null)
  const playingFrom = useRef<number | null>(null)

  const records = useMemo(
    () => spec.groups.flatMap((g) => g.dots.map((d) => ({ d, nativeKey: g.key, group: g.label, facets: d.facets }))),
    [spec],
  )
  // A narrower scope can leave fewer squares than the roving index: keep one square tabbable.
  useEffect(() => setRove((r) => Math.min(r, Math.max(0, records.length - 1))), [records.length])
  const native = useMemo(() => spec.groups.map((g) => ({ key: g.key, label: g.label })), [spec])
  const nativeName = NATIVE_NAMES[chartKey]
  const options = useMemo(
    () => availableGroupings(records as MatrixRecord[], Boolean(nativeName) && spec.groups.length > 1, placeGrain),
    [records, nativeName, spec.groups.length, placeGrain],
  )
  const [grouping, setGrouping] = useState<GroupingKey>(() => (options.includes('native') ? 'native' : options.includes('year') ? 'year' : 'all'))
  const active = options.includes(grouping) ? grouping : 'all'

  const groups = useMemo(
    () =>
      groupRecords(records as MatrixRecord[], active, {
        placeGrain,
        native,
        placeLabel: placeGrain === 'state' ? (k) => STATE_CODE_TO_NAME[k] ?? k : undefined,
        // The matrix is the data center story's (#1140): its sides in that topic's words (#1200).
        sideLabels: DC_SIDE_LABELS,
      }),
    [records, active, placeGrain, native],
  )
  const layout = useMemo(() => layoutMatrix(records.length, groups, width, active), [records.length, groups, width, active])
  const groupOf = useMemo(() => {
    const m = new Array<number>(records.length)
    groups.forEach((g, gi) => g.members.forEach((i) => (m[i] = gi)))
    return m
  }, [groups, records.length])

  // Squares fade in once the chart is on screen.
  useEffect(() => {
    if (reduced) return setRevealed(true)
    const el = svgRef.current
    if (!el || typeof IntersectionObserver === 'undefined') return setRevealed(true)
    const io = new IntersectionObserver((es) => es.some((e) => e.isIntersecting) && setRevealed(true), { threshold: 0.15 })
    io.observe(el)
    return () => io.disconnect()
  }, [reduced])

  const closeVideo = useCallback(() => {
    const from = playingFrom.current
    playingFrom.current = null
    setPlaying(null)
    if (from != null) requestAnimationFrame(() => svgRef.current?.querySelector<SVGElement>(`[data-sq="${from}"]`)?.focus())
  }, [])

  // Arrow keys walk the squares in the current grouping's reading order.
  const order = useMemo(() => groups.flatMap((g) => g.members), [groups])
  const onKey = (e: KeyboardEvent) => {
    const pos = order.indexOf(rove)
    const step = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0
    const to = e.key === 'Home' ? 0 : e.key === 'End' ? order.length - 1 : step ? Math.min(order.length - 1, Math.max(0, pos + step)) : null
    if (to == null || to < 0) return
    e.preventDefault()
    e.stopPropagation()
    const idx = order[to]!
    setRove(idx)
    svgRef.current?.querySelector<SVGElement>(`[data-sq="${idx}"]`)?.focus()
  }

  // Years and places are told apart by their block labels, so one colour; the chart's own groups keep the house palette.
  const colour = (gi: number, tone?: string) =>
    tone ? undefined : active === 'all' ? 'var(--ink-3)' : active === 'native' ? GROUP_COLORS[gi % GROUP_COLORS.length] : 'var(--violet)'
  const groupingName = (k: GroupingKey) =>
    k === 'all' ? 'All' : k === 'native' ? nativeName : k === 'year' ? 'By year' : k === 'place' ? (placeGrain === 'town' ? 'By town' : 'By state') : k === 'outcome' ? 'By outcome (AI reading)' : 'By who spoke (AI reading)'
  const aiGrouping = active === 'outcome' || active === 'side'
  const capped = spec.grandTotal != null ? spec.drawn < spec.grandTotal : /Showing/.test(spec.note ?? '')
  const hasVideo = records.some((r) => r.d.video)

  return (
    <div className="sc-block">
      {options.length > 1 && (
        <div className="sc-controls">
          <div className="folio-seg" role="group" aria-label="Group the squares">
            {options.map((k) => (
              <button key={k} type="button" aria-pressed={k === active} onClick={() => setGrouping(k)}>
                {groupingName(k)}
              </button>
            ))}
          </div>
        </div>
      )}
      <div ref={ref} data-keys-own onKeyDown={onKey}>
        <svg
          ref={svgRef}
          className={`sc-svg sc-matrix${revealed ? ' is-revealed' : ''}`}
          viewBox={`0 0 ${layout.width} ${layout.height}`}
          role="group"
          aria-label={`${spec.title}, ${scopeLabel}: one square per ${spec.unit}, ${groupingName(active)}`}
        >
          {layout.labels.map((l) => (
            <text key={l.key} className="sc-label" x={l.x} y={l.y}>
              {l.text}
            </text>
          ))}
          {records.map((r, i) => {
            const s = layout.squares[i]!
            const gi = groupOf[i] ?? 0
            const g = groups[gi]
            const sub = [r.d.place, r.d.date].filter(Boolean).join(' · ') || undefined
            const b = bind({
              cat: g ? g.label : r.group,
              val: r.d.title,
              sub,
              thumb: r.d.video ? youtubeThumbnail(r.d.video.videoId, 'mqdefault') ?? undefined : undefined,
            })
            const label = `${r.d.title}${sub ? `, ${sub}` : ''}${g && active !== 'all' ? `, ${g.label}` : ''}${r.d.video ? ' (plays the recording)' : r.d.url ? ' (opens the source)' : ''}`
            const open = (e: MouseEvent | KeyboardEvent) => {
              if (r.d.video) {
                if ('metaKey' in e && (e.metaKey || e.ctrlKey)) return
                e.preventDefault()
                hide()
                playingFrom.current = i
                setPlaying({ ...r.d.video, title: r.d.title, sub, url: r.d.url, quote: r.d.quote ?? null, place: r.d.place, date: r.d.date })
              } else if (r.d.url) {
                window.open(r.d.url, '_blank', 'noopener,noreferrer')
              }
            }
            const delay = reduced ? 0 : Math.min(500, Math.round((i / Math.max(1, records.length)) * 480))
            return (
              <rect
                key={r.d.id + i}
                data-sq={i}
                className={`sc-sq${g?.tone ? ` sc-tone-${g.tone}` : g?.key === 'none' && active !== 'all' ? ' sc-tone-none' : ''}`}
                width={s.size}
                height={s.size}
                style={{ transform: `translate(${s.x}px, ${s.y}px)`, transitionDelay: `${delay}ms`, fill: g?.key === 'none' && active !== 'all' ? undefined : colour(gi, g?.tone) }}
                tabIndex={i === rove ? 0 : -1}
                role="img"
                aria-label={label}
                {...b}
                onFocus={(e) => {
                  setRove(i)
                  b.onFocus(e)
                }}
                onClick={open}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') open(e)
                }}
              />
            )
          })}
        </svg>
      </div>
      {active !== 'all' && (
      <p className="sc-note">
        {`Percentages are of the ${fmt(records.length)} ${capped ? 'shown' : 'on record in this scope'}. `}
        {aiGrouping &&
          (chartKey === 'decisions'
            ? 'Outcome as written in the meeting analysis, an AI reading of the transcript, not an official record.'
            : 'An AI reading (Jev) of each meeting transcript, not an official record; "Not screened" means the meeting has no reading.')}
      </p>
      )}
      <p className="stance-note stance-hint-keys">Use the arrow keys to move between squares.</p>
      {records.some((r) => r.d.url) && <p className="stance-note stance-hint-touch">{hasVideo ? 'Tap a square to play the meeting.' : 'Tap a square to open it.'}</p>}
      <button type="button" className="folio-btn" aria-expanded={tableOpen} aria-controls={`${idBase}-matrix-table`} onClick={() => setTableOpen((o) => !o)}>
        {tableOpen ? 'Hide data table' : 'Show data table'} {tableOpen ? '↑' : '↓'}
      </button>
      {tableOpen && (
        <DataTable
          id={`${idBase}-matrix-table`}
          caption={`Data table: ${spec.title}, ${scopeLabel}, ${groupingName(active)}`}
          spec={{
            columns: [{ label: 'Group' }, { label: 'Squares', numeric: true }, { label: 'Share', numeric: true }],
            rows: groups.map((g) => [g.label, fmt(g.count), `${g.pct.toFixed(1)}%`]),
          }}
        />
      )}
      {typeof document !== 'undefined' && createPortal(<div className="folio" style={HOUSE_STYLE}><Tooltip tip={tip} /></div>, document.body)}
      <MeetingVideoModal video={playing} onClose={closeVideo} />
    </div>
  )
}
