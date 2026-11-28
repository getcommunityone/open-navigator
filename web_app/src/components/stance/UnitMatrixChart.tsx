import ChartFrame, { type LegendItem } from '../chart/ChartFrame'
import { TONE_COLOR } from '../chart/toneColors'
import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent, type MouseEvent } from 'react'
import { createPortal } from 'react-dom'
import type { DotsSpec } from '../../utils/stanceGame'
import { GROUP_COLORS, HOUSE_STYLE } from '../../utils/houseTheme'
import { STATE_CODE_TO_NAME } from '../../utils/stateMapping'
import { availableGroupings, groupRecords, layoutMatrix, sideLabelsFor, type GroupingKey, type MatrixRecord } from '../../utils/unitMatrix'
import { DataTable } from '../matrix/SectionShell'
import { Tooltip, useTooltip } from '../matrix/Tooltip'
import { youtubeThumbnail } from '../../lib/youtubeThumbnail'
import { staggerDelayMs } from '../../utils/folioMotion'
import { useChartReveal } from './useChartReveal'
import MeetingVideoModal, { type MeetingVideo } from './MeetingVideoModal'
import { useChartWidth } from './useChartWidth'
import './storyCharts.css'
import { topicPositions } from '../../utils/topicPositions'

/** What a chart's own grouping is called on its toggle. */
const NATIVE_NAMES: Record<string, string> = {
  'job-claims': 'By phase',
  'agenda-items': 'Upcoming or past',
  decisions: 'On a data center or not',
  sites: 'By status',
  projects: 'By status',
  'community-events': 'By kind',
  positions: 'By stance',
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
  const { ref, width } = useChartWidth<HTMLDivElement>()
  const svgRef = useRef<SVGSVGElement | null>(null)
  const { bind, tip, hide } = useTooltip()
  const [rove, setRove] = useState(0)
  // Squares fade in on a diagonal wave once the chart scrolls into view (#1228, the reference's §4.1); a new scope replays it.
  const { ref: revealRef, revealed, reduced } = useChartReveal<SVGSVGElement>(`${chartKey}|${scopeLabel}`)
  const [tableOpen, setTableOpen] = useState(false)
  const [playing, setPlaying] = useState<MeetingVideo | null>(null)
  const [hoveredGroup, setHoveredGroup] = useState<string | null>(null)
  const [pinnedGroup, setPinnedGroup] = useState<string | null>(null)
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

  const svgRefs = useCallback(
    (node: SVGSVGElement | null) => {
      svgRef.current = node
      revealRef(node)
    },
    [revealRef],
  )

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
  const spotlightRaw = hoveredGroup ?? pinnedGroup
  const spotlight = spotlightRaw && groups.some((g) => g.key === spotlightRaw) ? spotlightRaw : null
  const capped = spec.grandTotal != null ? spec.drawn < spec.grandTotal : /Showing/.test(spec.note ?? '')
  const hasVideo = records.some((r) => r.d.video)

  // Title and key (#1409): the largest group as the takeaway when it is clear, every group's colour in the key.
  const top = [...groups].sort((a, b) => b.count - a.count)[0]
  const unitWord = `${spec.unit}${records.length === 1 ? '' : 's'}`
  const frameTitle =
    active !== 'all' && top && records.length >= 5 && top.pct >= 40 && groups.length > 1
      ? `${spec.title}: ${top.label} is the largest group, ${Math.round(top.pct)}% of ${fmt(records.length)} ${unitWord}`
      : `${spec.title}: ${fmt(records.length)} ${unitWord}, ${scopeLabel}`
  const legend: LegendItem[] =
    active === 'all'
      ? [{ key: 'all', label: `One square per ${spec.unit}`, color: 'var(--ink-3)' }]
      : groups.map((g, gi) => ({
          key: g.key,
          label: `${g.label} (${fmt(g.count)})`,
          color: g.tone ? TONE_COLOR[g.tone] : g.key === 'none' ? 'var(--paper-raised)' : colour(gi, g.tone),
        }))

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
      <ChartFrame title={frameTitle} legend={legend} caption={`One square per ${spec.unit}, grouped ${groupingName(active).toLowerCase()}.`}>
      <div ref={ref} data-keys-own onKeyDown={onKey}>
        <svg
          ref={svgRefs}
          className={`sc-svg sc-matrix${revealed ? ' is-revealed' : ''}`}
          viewBox={`0 0 ${layout.width} ${layout.height}`}
          role="group"
          aria-label={`${spec.title}, ${scopeLabel}: one square per ${spec.unit}, ${groupingName(active)}`}
        >
          {layout.labels.map((l) => (
            <text
              key={l.key}
              className="sc-label sc-label-btn"
              x={l.x}
              y={l.y}
              role="button"
              tabIndex={0}
              aria-pressed={pinnedGroup === l.key}
              style={spotlight && spotlight !== l.key ? { opacity: 0.45 } : undefined}
              onMouseEnter={() => setHoveredGroup(l.key)}
              onMouseLeave={() => setHoveredGroup((c) => (c === l.key ? null : c))}
              onFocus={() => setHoveredGroup(l.key)}
              onBlur={() => setHoveredGroup((c) => (c === l.key ? null : c))}
              onClick={() => setPinnedGroup((c) => (c === l.key ? null : l.key))}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  setPinnedGroup((c) => (c === l.key ? null : l.key))
                }
              }}
            >
              {l.text}
            </text>
          ))}
          {records.map((r, i) => {
            const s = layout.squares[i]!
            const gi = groupOf[i] ?? 0
            const g = groups[gi]
            const dimmed = Boolean(spotlight && g?.key !== spotlight)
            const sub = [r.d.place, r.d.date].filter(Boolean).join(' · ') || undefined
            const b = bind({
              cat: g ? g.label : r.group,
              val: r.d.title,
              // Who supported and opposed a decision, and its vote (#1320), after where and when.
              sub: [sub, ...(r.d.detail ?? [])].filter(Boolean).join(' · ') || undefined,
              thumb: r.d.video ? youtubeThumbnail(r.d.video.videoId, 'mqdefault') ?? undefined : undefined,
            })
            const label = `${r.d.title}${sub ? `, ${sub}` : ''}${g && active !== 'all' ? `, ${g.label}` : ''}${r.d.video ? ' (plays the recording)' : r.d.url ? ' (opens the source)' : ''}`
            const open = (e: MouseEvent | KeyboardEvent) => {
              if (r.d.video) {
                if ('metaKey' in e && (e.metaKey || e.ctrlKey)) return
                e.preventDefault()
                hide()
                playingFrom.current = i
                setPlaying({ ...r.d.video, title: r.d.title, sub, url: r.d.url, quote: r.d.quote ?? null, place: r.d.place, date: r.d.date, speakerName: r.d.speakerName ?? null, role: r.d.role ?? null, stanceNote: r.d.stanceNote ?? null })
              } else if (r.d.url) {
                window.open(r.d.url, '_blank', 'noopener,noreferrer')
              }
            }
            // .sc-sq transitions transform, fill, opacity. A regrouping flies the squares in reading order (up to ~0.5 s);
            // the entrance fades them in on the diagonal wave, top-left first, like the reference's first draw.
            const fly = reduced ? 0 : Math.min(500, Math.round((i / Math.max(1, records.length)) * 480))
            const wave = reduced ? 0 : Math.round(staggerDelayMs(s.x, s.y, layout.width + layout.height))
            return (
              <rect
                key={r.d.id + i}
                data-box=""
                data-group={g?.key ?? ''}
                data-sq={i}
                className={`sc-sq${g?.tone ? ` sc-tone-${g.tone}` : g?.key === 'none' && active !== 'all' ? ' sc-tone-none' : ''}`}
                width={s.size}
                height={s.size}
                style={{
                  transform: `translate(${s.x}px, ${s.y}px)`,
                  transitionDelay: `${fly}ms, ${fly}ms, ${wave}ms`,
                  fill: dimmed ? 'var(--neutral-data)' : g?.key === 'none' && active !== 'all' ? undefined : g?.tone ? TONE_COLOR[g.tone] : colour(gi, g?.tone),
                  opacity: dimmed ? 0.3 : undefined,
                }}
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
      </ChartFrame>
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
