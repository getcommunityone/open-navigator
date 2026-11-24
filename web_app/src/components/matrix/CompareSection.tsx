import { useMemo, useRef } from 'react'
import { censusMetricRankDirection } from '../../utils/censusDataDictionary'
import { niceScale } from '../../utils/matrixMapMath'
import { changeTone } from '../../utils/matrixTable'
import { compareStory } from '../../utils/matrixStory'
import { signedChange } from './data'
import { useElementWidth, useSection } from './hooks'
import { Empty, Seg } from './parts'
import SectionShell from './SectionShell'
import { Tooltip, useTooltip } from './Tooltip'
import type { MatrixCtx, Row } from './types'

type SortBy = 'latest' | 'change' | 'base'
interface Pt {
  r: Row
  a: number | null
  c: number | null
  d: number | null
}

/** Compare (dumbbell): the earliest published vintage against the selected one, per geography. */
export default function CompareSection({ ctx }: { ctx: MatrixCtx }) {
  const { vintage, vintages, metricSlug: slug, fmt } = ctx
  const base = vintages[0] ?? ''
  const hasPair = !!base && base !== vintage
  const baseRows = hasPair ? ctx.rowsByVintage[base] : undefined
  const sortBy: SortBy = ctx.sortRaw === 'change' ? 'change' : ctx.sortRaw === 'base' ? 'base' : 'latest'
  const lowerBetter = censusMetricRankDirection(slug) === 'lower'
  const pts: Pt[] = useMemo(() => {
    if (!baseRows) return []
    const byFips = new Map(baseRows.map((r) => [r.fips, r]))
    const list = ctx.rows.map((r) => {
      const a = byFips.get(r.fips)?.vals[slug] ?? null
      const c = r.vals[slug] ?? null
      return { r, a, c, d: a != null && c != null ? c - a : null }
    })
    const dir = ctx.sortDir === 'asc' ? 1 : -1
    const key = (p: Pt) => (sortBy === 'change' ? p.d : sortBy === 'base' ? p.a : p.c)
    return list.sort((x, y) => {
      const kx = key(x)
      const ky = key(y)
      if (kx == null && ky == null) return x.r.name.localeCompare(y.r.name)
      if (kx == null) return 1
      if (ky == null) return -1
      return (kx - ky) * dir || x.r.name.localeCompare(y.r.name)
    })
  }, [baseRows, ctx.rows, slug, sortBy, ctx.sortDir])

  const set = (v: SortBy) => ctx.setMany({ sort: v === 'latest' ? null : v })
  const withBoth = pts.filter((p) => p.d != null)
  const ups = withBoth.filter((p) => p.d! > 0).length
  const downs = withBoth.filter((p) => p.d! < 0).length
  const name = `${ctx.metricLabel}, ${base} to ${vintage}`
  const story =
    hasPair && baseRows === undefined
      ? { headline: `${ctx.metricLabel}, ${base} against ${vintage}.`, lead: null }
      : compareStory({
          metricLabel: ctx.metricLabel,
          base: hasPair ? base : null,
          vintage,
          pairs: pts.map((p) => ({ name: p.r.name, from: p.a, to: p.c })),
          fmt: (v) => fmt(slug, v),
          fmtChange: (a, b) => signedChange(slug, a, b, ctx.metrics, fmt),
        })

  let body: React.ReactNode
  if (!hasPair) {
    body = (
      <Empty>
        No data available — this needs two vintages. {vintages.length < 2 ? 'Only one vintage is published, so there is nothing to compare.' : `Choose a vintage later than ${base} to compare with it.`}
      </Empty>
    )
  } else if (baseRows === undefined) body = <Empty>Loading {base}…</Empty>
  else if (baseRows === null) body = <Empty>No data available — the {base} state file could not be loaded, so there is nothing to compare with.</Empty>
  else if (!pts.some((p) => p.a != null || p.c != null)) body = <Empty>No data available for {ctx.metricLabel}.</Empty>
  else body = <Dumbbell ctx={ctx} pts={pts} base={base} lowerBetter={lowerBetter} title={name} />

  return (
    <SectionShell
      ctx={ctx}
      id="dumbbell"
      headline={story.headline}
      lead={story.lead}
      text={
        <>
          <p>
            Each row is one geography: a hollow dot for {base} and a filled dot for {vintage}, joined by a line that grows from the first to
            the second. The right-hand column is the change, in the metric's own unit; it reads “—” when either vintage is missing.
          </p>
          {hasPair && baseRows && (
            <p>
              {withBoth.length} geographies have both readings: {ups} {lowerBetter ? 'rose' : 'higher'}, {downs} {lowerBetter ? 'fell' : 'lower'}.
              Sort by {vintage}, by change or by {base}; again to reverse.
            </p>
          )}
        </>
      }
      controls={
        hasPair ? (
          <Seg
            label="Sort compare rows"
            value={sortBy}
            onChange={(v) => set(v as SortBy)}
            options={[
              { value: 'latest', label: `By ${vintage}` },
              { value: 'change', label: 'By change' },
              { value: 'base', label: `By ${base}` },
            ]}
          />
        ) : undefined
      }
      caption={
        <>
          {name}, one row per geography. Source: ACS 5-year, {base} and {vintage}.
        </>
      }
      table={() =>
        hasPair && baseRows
          ? {
              columns: [{ label: 'Geography' }, { label: base, numeric: true }, { label: vintage, numeric: true }, { label: 'Change', numeric: true }],
              rows: pts.map((p) => [p.r.name, fmt(slug, p.a), fmt(slug, p.c), signedChange(slug, p.a, p.c, ctx.metrics, fmt)]),
            }
          : null
      }
    >
      {body}
    </SectionShell>
  )
}

const ROW_H = 26
const TOP = 34

function Dumbbell({ ctx, pts, base, lowerBetter, title }: { ctx: MatrixCtx; pts: Pt[]; base: string; lowerBetter: boolean; title: string }) {
  const { seen } = useSection()
  const host = useRef<HTMLDivElement>(null)
  const w = useElementWidth(host)
  const tt = useTooltip()
  const slug = ctx.metricSlug
  const revealed = seen || ctx.reduced
  const compact = w < 460
  const labelW = compact ? 0 : Math.min(120, Math.round(w * 0.24))
  const deltaW = compact ? 0 : 74
  const plotL = compact ? 10 : labelW
  const plotR = compact ? w - 14 : w - deltaW
  const rH = compact ? 44 : ROW_H
  const all = pts.flatMap((p) => [p.a, p.c]).filter((x): x is number => x != null)
  const sc = niceScale(Math.min(...all), Math.max(...all), compact ? 3 : 5)
  const x = (v: number) => plotL + ((v - sc.min) / (sc.max - sc.min || 1)) * (plotR - plotL)
  const h = TOP + pts.length * rH + 30
  const good = 'var(--violet)'
  const bad = 'var(--bad)'
  const dirColor = (d: number) => (changeTone(d, lowerBetter) === 'good' ? good : bad)
  const dirInk = (d: number) => (changeTone(d, lowerBetter) === 'good' ? 'var(--violet-ink)' : 'var(--bad-ink)')
  return (
    <div ref={host}>
      <p className="folio-chart-title">{title}</p>
      <div className="folio-legend-inline" aria-label="Legend">
        <span>
          <i className="folio-legend-swatch" style={{ border: '2px solid var(--ink)', borderRadius: 999 }} /> {base} (base)
        </span>
        <span>
          <i className="folio-legend-swatch" style={{ background: 'var(--violet)', borderRadius: 999 }} /> {ctx.vintage} (latest)
        </span>
        <span>
          <i className="folio-legend-swatch" style={{ background: good }} />
          {lowerBetter ? ' better (lower is better for this metric)' : ' higher'}
        </span>
        <span>
          <i className="folio-legend-swatch" style={{ background: bad }} />
          {lowerBetter ? ' worse' : ' lower'}
        </span>
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} width={w} height={h} role="group" aria-label={title} style={{ display: 'block', overflow: 'visible' }}>
        {sc.ticks.map((t) => (
          <g key={t}>
            <line x1={x(t)} x2={x(t)} y1={TOP - 14} y2={h - 24} stroke={sc.min === t && t === 0 ? 'var(--ink)' : 'var(--rule)'} strokeWidth={t === 0 ? 1.5 : 1} />
            <text x={x(t)} y={h - 8} textAnchor="middle" className="folio-svg-micro">
              {ctx.fmt(slug, t)}
            </text>
          </g>
        ))}
        {pts.map((p, idx) => {
          const y = TOP + idx * rH
          const trackY = compact ? 30 : rH / 2
          const xa = p.a != null ? x(p.a) : null
          const xc = p.c != null ? x(p.c) : null
          const delay = ctx.reduced ? 0 : idx * 60
          const info = { cat: p.r.name, val: `${ctx.fmt(slug, p.a)} → ${ctx.fmt(slug, p.c)}`, sub: `Change: ${signedChange(slug, p.a, p.c, ctx.metrics, ctx.fmt)} (${base} to ${ctx.vintage})` }
          return (
            <g
              key={p.r.fips}
              tabIndex={0}
              role="img"
              aria-label={`${p.r.name}: ${base} ${ctx.fmt(slug, p.a)}, ${ctx.vintage} ${ctx.fmt(slug, p.c)}, change ${signedChange(slug, p.a, p.c, ctx.metrics, ctx.fmt)}`}
              className="folio-glide"
              style={{ transform: `translate3d(0, ${y}px, 0)`, cursor: 'pointer' }}
              {...tt.bind(info)}
            >
              <rect x={0} y={0} width={w} height={rH} fill="transparent" />
              <text x={0} y={compact ? 12 : rH / 2 + 4} className="folio-svg-label">
                {p.r.name}
              </text>
              {xa != null && xc != null && (
                <line
                  x1={xa}
                  x2={xc}
                  y1={trackY}
                  y2={trackY}
                  stroke={dirColor(p.d ?? 0)}
                  strokeWidth={2}
                  style={{
                    transformOrigin: `${xa}px ${trackY}px`,
                    transform: revealed ? 'scaleX(1)' : 'scaleX(0)',
                    transition: 'transform var(--d-3) var(--ease-out)',
                    transitionDelay: `${delay + 120}ms`,
                  }}
                />
              )}
              {xa != null && (
                <circle
                  cx={xa}
                  cy={trackY}
                  r={5}
                  fill="var(--paper)"
                  stroke="var(--ink)"
                  strokeWidth={2}
                  style={{ opacity: revealed ? 1 : 0, transition: 'opacity var(--d-2) var(--ease-out)', transitionDelay: `${delay}ms` }}
                />
              )}
              {xc != null && (
                <circle
                  cx={xc}
                  cy={trackY}
                  r={6}
                  fill="var(--violet)"
                  style={{ opacity: revealed ? 1 : 0, transition: 'opacity var(--d-2) var(--ease-out)', transitionDelay: `${delay + 360}ms` }}
                />
              )}
              <text
                x={w}
                y={compact ? 12 : rH / 2 + 4}
                textAnchor="end"
                style={{ fontSize: 12, fontWeight: 500, fill: p.d == null ? 'var(--ink-2)' : dirInk(p.d) }}
              >
                {signedChange(slug, p.a, p.c, ctx.metrics, ctx.fmt)}
              </text>
            </g>
          )
        })}
      </svg>
      <Tooltip tip={tt.tip} />
    </div>
  )
}
