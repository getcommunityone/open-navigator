import { useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { useQuery } from '@tanstack/react-query'
import { fetchChartData } from '../../api/stance'
import { chartSpec, type BarsSpec, type DotsSpec } from '../../utils/stanceGame'
import { docsUrl } from '../../utils/docsLinks'
import { GROUP_COLORS, HOUSE_STYLE } from '../../utils/houseTheme'
import { DataTable } from '../matrix/SectionShell'
import { Tooltip, useTooltip } from '../matrix/Tooltip'

interface Props {
  chartKey: string
  round: number
  /** Only the round in view and its neighbours load their data. */
  enabled: boolean
  stateCode: string | undefined
  /** Full state name when a state is chosen, otherwise null (national). */
  stateName: string | null
  /** A city, for the data stories (the challenge never narrows its charts below a state). */
  city?: string | null
  /** What the caption says the figure shows; defaults to the state name or "National". */
  scopeLabel?: string
  /** Shown under "No data available" (for example buttons that broaden the place). */
  emptyExtra?: ReactNode
}

const fmt = (n: number) => n.toLocaleString('en-US')

/** The dataset behind one round's chart, shared by the chart and the headline through the query cache. */
export function useChartData(chartKey: string, enabled: boolean, stateCode: string | undefined, city?: string | null) {
  const c = stateCode && city ? city : ''
  return useQuery({
    queryKey: ['stance', 'chart', chartKey, stateCode ?? 'national', c],
    queryFn: () => fetchChartData(chartKey, stateCode, c || undefined),
    enabled,
    staleTime: 5 * 60_000,
    retry: 1,
  })
}

function Bars({ spec }: { spec: BarsSpec }) {
  const max = Math.max(...spec.rows.map((r) => r.value), 1)
  return (
    <ul className="stance-hbars" role="list">
      {spec.rows.slice(0, 10).map((r) => (
        <li key={r.label}>
          <span className="stance-hbar-label">{r.label}</span>
          <span className="stance-hbar-track">
            <span className="stance-hbar-fill" style={{ width: `${(r.value / max) * 100}%` }} />
          </span>
          <span className="stance-hbar-value">
            {fmt(r.value)} · {r.percent}%
          </span>
        </li>
      ))}
    </ul>
  )
}

/** One mark per real record, grouped under "Group · N records · P%". Roving focus: arrow keys move between the dots. */
function Dots({ spec }: { spec: DotsSpec }) {
  const { bind, tip } = useTooltip()
  const [rove, setRove] = useState(0)
  const root = useRef<HTMLDivElement>(null)
  const flat = useMemo(() => spec.groups.flatMap((g, gi) => g.dots.map((d) => ({ d, gi, label: g.label }))), [spec])
  const onKey = (e: KeyboardEvent) => {
    const step = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1 : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0
    const to = e.key === 'Home' ? 0 : e.key === 'End' ? flat.length - 1 : step ? Math.min(flat.length - 1, Math.max(0, rove + step)) : null
    if (to == null) return
    e.preventDefault()
    e.stopPropagation()
    setRove(to)
    root.current?.querySelector<HTMLElement>(`[data-dot="${to}"]`)?.focus()
  }
  let n = -1
  const total = flat.length
  return (
    <div className="stance-dots" ref={root} data-keys-own onKeyDown={onKey}>
      {spec.groups.map((g, gi) => (
        <div className="stance-dotgroup" key={g.key}>
          <p className="stance-dotgroup-head">
            <span className="stance-swatch" style={{ background: GROUP_COLORS[gi % GROUP_COLORS.length] }} aria-hidden="true" />
            {g.heading}
          </p>
          <div className="stance-dotrow" role="list" aria-label={g.heading}>
            {g.dots.map((d) => {
              n += 1
              const i = n
              const info = { cat: g.label, val: d.title, sub: [d.place, d.date].filter(Boolean).join(' · ') || undefined }
              const label = `${d.title}${d.place ? `, ${d.place}` : ''}${d.date ? `, ${d.date}` : ''}${d.url ? ' (opens the source)' : ''}`
              const b = bind(info)
              const common = {
                className: 'stance-dot',
                'data-dot': i,
                'aria-label': label,
                tabIndex: i === rove ? 0 : -1,
                style: { background: GROUP_COLORS[gi % GROUP_COLORS.length], ['--f' as string]: total > 1 ? i / total : 0 },
                ...b,
                onFocus: (e: { currentTarget: Element }) => {
                  setRove(i)
                  b.onFocus(e)
                },
              }
              return d.url ? (
                <a key={d.id + i} role="listitem" href={d.url} target="_blank" rel="noopener noreferrer" {...common} />
              ) : (
                <span key={d.id + i} role="listitem" {...common} />
              )
            })}
          </div>
        </div>
      ))}
      {typeof document !== 'undefined' && createPortal(<div className="folio" style={HOUSE_STYLE}><Tooltip tip={tip} /></div>, document.body)}
      <p className="stance-note stance-hint-keys">Use the arrow keys to move between dots.</p>
      {flat.some((x) => x.d.url) && <p className="stance-note stance-hint-touch">Tap a dot to open it.</p>}
    </div>
  )
}

/** The chart for one round: one simple figure from the dataset the statement names, its FIG. caption and data table. */
export default function ChartPanel({ chartKey, round, enabled, stateCode, stateName, city, scopeLabel, emptyExtra }: Props) {
  const q = useChartData(chartKey, enabled, stateCode, city)
  const spec = useMemo(() => chartSpec(chartKey, q.data, stateName), [chartKey, q.data, stateName])
  const [open, setOpen] = useState(false)
  const fig = String(round).padStart(2, '0')
  const scope = scopeLabel ?? stateName ?? 'National'
  const hasLinks = spec?.kind === 'dots' && spec.groups.some((g) => g.dots.some((d) => d.url))

  return (
    <figure className="stance-figure" aria-label={spec?.title ?? 'Chart'}>
      {q.isLoading && enabled ? (
        <p className="folio-muted" role="status">
          Loading chart…
        </p>
      ) : !spec ? (
        <div className="stance-nodata" role="status">
          <p>{q.isError ? 'This chart could not be loaded right now.' : 'No data available for this chart'}</p>
          {emptyExtra}
        </div>
      ) : spec.kind === 'bars' ? (
        <Bars spec={spec} />
      ) : (
        <Dots spec={spec} />
      )}
      <figcaption className="folio-fig">
        <b>FIG. {fig}</b> — {spec ? `${spec.title}, ${scope}.` : `${scope}.`}
        {spec?.kind === 'dots' && ` Every dot is one ${spec.unit}. ${hasLinks ? 'Select a dot to open it.' : 'Hover or focus a dot for details.'}`}
        {spec && ` Source: ${spec.source}.`}
        {spec?.note && ` ${spec.note}`}
        {spec && chartKey === 'sites' && city && ' Sites are listed by state only: the source has no city.'}
        {spec && stateName == null && ' National figures, because no state is chosen.'}{' '}
        <a href={docsUrl('/guides/data-center-challenge#sources-and-limits')} target="_blank" rel="noopener noreferrer">
          About this data
        </a>
      </figcaption>
      {spec && (
        <>
          <button
            type="button"
            className="folio-btn"
            aria-expanded={open}
            aria-controls={`stance-data-${round}`}
            onClick={() => setOpen((o) => !o)}
          >
            {open ? 'Hide data table' : 'Show data table'} {open ? '↑' : '↓'}
          </button>
          {open && (
            <DataTable
              id={`stance-data-${round}`}
              caption={`Data table: ${spec.title}, ${scope}`}
              spec={
                spec.kind === 'bars'
                  ? {
                      columns: [{ label: 'Group' }, { label: 'Count', numeric: true }, { label: 'Share', numeric: true }],
                      rows: spec.rows.map((r) => [r.label, fmt(r.value), `${r.percent}%`]),
                    }
                  : {
                      columns: [
                        { label: 'Group' },
                        { label: spec.grandTotal != null ? 'Records' : 'Records shown', numeric: true },
                        { label: spec.grandTotal != null ? 'Share' : 'Share (not known)', numeric: true },
                        { label: 'Dots drawn', numeric: true },
                      ],
                      rows: spec.groups.map((g) => [g.label, fmt(g.total ?? g.shown), g.share != null ? `${g.share}%` : '—', fmt(g.shown)]),
                    }
              }
            />
          )}
        </>
      )}
    </figure>
  )
}
