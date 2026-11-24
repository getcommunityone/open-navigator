import { useEffect, useMemo, useRef, useState } from 'react'
import { medianOf, niceScale } from '../../utils/matrixMapMath'
import { sortByMetric } from './data'
import { useElementWidth, useSection, useSeries } from './hooks'
import LegendChips from './LegendChips'
import { Empty } from './parts'
import SectionShell from './SectionShell'
import { Tooltip, useTooltip } from './Tooltip'
import type { MatrixCtx, Row } from './types'

const MAX_GEO = 8
const LINE_COLORS = ['var(--violet)', 'var(--vermilion)', 'var(--magenta)', 'var(--ink-3)']

/** The geographies in `?geo=` (state FIPS, max 8); by default the four highest in the vintage in view. */
export function trendGeos(ctx: MatrixCtx): string[] {
  const valid = new Set(ctx.rows.map((r) => r.fips))
  const fromUrl = (ctx.sp.get('geo') ?? '')
    .split(',')
    .map((s) => s.trim().padStart(2, '0'))
    .filter((s, i, a) => s !== '00' && valid.has(s) && a.indexOf(s) === i)
  if (fromUrl.length) return fromUrl.slice(0, MAX_GEO)
  return sortByMetric(ctx.rows, ctx.metricSlug, 'desc')
    .filter((r) => r.vals[ctx.metricSlug] != null)
    .slice(0, 4)
    .map((r) => r.fips)
}

interface Series {
  key: string
  label: string
  color: string
  dash?: string
  width: number
  values: Array<number | null>
}

function valueIn(rows: Row[] | null | undefined, fips: string, slug: string): number | null {
  return rows?.find((r) => r.fips === fips)?.vals[slug] ?? null
}

/** Scroll-scrubbed draw progress 0..1 (the reference: starts at 80% of the viewport, done at 40%). Full when motion is reduced. */
function useDrawProgress(el: HTMLElement | null, reduced: boolean): number {
  const [p, setP] = useState(reduced ? 1 : 0)
  useEffect(() => {
    if (reduced) {
      setP(1)
      return
    }
    if (!el) return
    let raf = 0
    const update = () => {
      raf = 0
      const vh = window.innerHeight || 800
      const top = el.getBoundingClientRect().top
      const next = Math.max(0, Math.min(1, (vh * 0.8 - top) / (vh * 0.8 - vh * 0.4)))
      setP((cur) => (Math.abs(next - cur) > 0.004 ? next : cur))
    }
    const on = () => {
      if (!raf) raf = requestAnimationFrame(update)
    }
    update()
    window.addEventListener('scroll', on, { passive: true })
    window.addEventListener('resize', on)
    return () => {
      window.removeEventListener('scroll', on)
      window.removeEventListener('resize', on)
      if (raf) cancelAnimationFrame(raf)
    }
  }, [el, reduced])
  return p
}

export default function TrendSection({ ctx }: { ctx: MatrixCtx }) {
  const slug = ctx.metricSlug
  const geos = trendGeos(ctx)
  const pending = ctx.vintages.some((v) => ctx.rowsByVintage[v] === undefined)
  const series: Series[] = useMemo(() => {
    const geoSeries = geos.map((f, i) => ({
      key: f,
      label: ctx.rows.find((r) => r.fips === f)?.name ?? f,
      color: LINE_COLORS[i % 4]!,
      dash: i >= 4 ? '6 4' : undefined,
      width: 2,
      values: ctx.vintages.map((v) => valueIn(ctx.rowsByVintage[v], f, slug)),
    }))
    const median: Series = {
      key: 'median',
      label: 'Median across states',
      color: 'var(--ink)',
      dash: '2 4',
      width: 2.5,
      values: ctx.vintages.map((v) => medianOf((ctx.rowsByVintage[v] ?? []).map((r) => r.vals[slug] ?? null))),
    }
    return [...geoSeries, median]
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [geos.join(','), ctx.vintages, ctx.rowsByVintage, ctx.rows, slug])
  const keys = useMemo(() => series.map((s) => s.key), [series])
  const sv = useSeries(ctx, 'trend', keys)
  const shown = series.filter((s) => sv.on(s.key))
  const toggleGeo = (f: string) => {
    const next = geos.includes(f) ? geos.filter((g) => g !== f) : [...geos, f].slice(0, MAX_GEO)
    if (!next.length) return
    ctx.setQP('geo', next.join(','))
  }
  const nV = ctx.vintages.length
  const usable = nV >= 2 && !pending
  const first = ctx.vintages[0]
  const last = ctx.vintages[nV - 1]

  return (
    <SectionShell
      ctx={ctx}
      id="trend"
      headline={[ctx.metricLabel, `across ${nV} ${nV === 1 ? 'vintage' : 'vintages'},`, nV > 1 ? `${first} to ${last}` : `${first ?? ''}`]}
      text={
        <>
          <p>
            One line per selected geography, plus the median across all states, for each published vintage. The lines draw in as you scroll to
            this section. Click a legend chip to hide a line; hover or focus one to highlight it.
          </p>
          <p>
            Showing {geos.length} {geos.length === 1 ? 'geography' : 'geographies'} (up to {MAX_GEO}) and the median. Vintages without a file or
            without a value for a geography leave a gap in its line; nothing is filled in.
          </p>
        </>
      }
      controls={
        <details className="folio-field relative">
          <summary className="cursor-pointer select-none">
            Geographies ({geos.length}/{MAX_GEO})
          </summary>
          <div className="folio-panel absolute z-10 mt-1 max-h-64 w-64 overflow-y-auto">
            {[...ctx.rows].sort((a, b) => a.name.localeCompare(b.name)).map((r) => (
              <label key={r.fips} className="flex items-center gap-1.5 py-0.5" style={{ fontFamily: 'var(--font-sans)', color: 'var(--ink)' }}>
                <input
                  type="checkbox"
                  checked={geos.includes(r.fips)}
                  disabled={(geos.length === 1 && geos[0] === r.fips) || (!geos.includes(r.fips) && geos.length >= MAX_GEO)}
                  onChange={() => toggleGeo(r.fips)}
                  style={{ accentColor: 'var(--violet-ink)' }}
                />
                {r.name}
              </label>
            ))}
          </div>
        </details>
      }
      caption={
        <>
          {ctx.metricLabel} across {nV} vintages{nV > 1 ? `, ${first} to ${last}` : ''}: {shown.length} of {series.length} lines shown. Source: ACS 5-year.
        </>
      }
      table={() =>
        usable
          ? {
              columns: [{ label: 'Vintage' }, ...shown.map((s) => ({ label: s.label, numeric: true }))],
              rows: ctx.vintages.map((v, i) => [v, ...shown.map((s) => ctx.fmt(slug, s.values[i] ?? null))]),
            }
          : null
      }
    >
      {pending ? (
        <Empty>Loading vintages…</Empty>
      ) : nV < 2 ? (
        <Empty>No data available — only one vintage is published, so there is no trend to draw.</Empty>
      ) : (
        <TrendChart ctx={ctx} series={series} sv={sv} />
      )}
    </SectionShell>
  )
}

function TrendChart({ ctx, series, sv }: { ctx: MatrixCtx; series: Series[]; sv: ReturnType<typeof useSeries> }) {
  const { el } = useSection()
  const p = useDrawProgress(el, ctx.reduced)
  const host = useRef<HTMLDivElement>(null)
  const w = useElementWidth(host)
  const tt = useTooltip()
  const slug = ctx.metricSlug
  const vs = ctx.vintages
  const shown = series.filter((s) => sv.on(s.key))
  const padL = 62
  const padR = w < 460 ? 40 : 64
  const padT = 20
  const padB = 30
  const h = 300
  const nums = shown.flatMap((s) => s.values).filter((v): v is number => v != null)
  if (!nums.length) return <Empty>No data available for {ctx.metricLabel} in the lines shown.</Empty>
  const sc = niceScale(Math.min(...nums), Math.max(...nums), 4)
  const x = (i: number) => padL + (vs.length === 1 ? 0.5 : i / (vs.length - 1)) * (w - padL - padR)
  const y = (v: number) => h - padB - ((v - sc.min) / (sc.max - sc.min || 1)) * (h - padT - padB)
  const path = (vals: Array<number | null>) => {
    let d = ''
    let pen = false
    vals.forEach((v, i) => {
      if (v == null) {
        pen = false
        return
      }
      d += `${pen ? 'L' : 'M'} ${x(i).toFixed(1)} ${y(v).toFixed(1)} `
      pen = true
    })
    return d.trim()
  }
  // End labels, nudged apart so they never overlap.
  const ends = shown
    .map((s) => {
      const i = s.values.reduce<number>((a, v, k) => (v != null ? k : a), -1)
      return i < 0 ? null : { s, i, y: y(s.values[i]!) }
    })
    .filter((e): e is { s: Series; i: number; y: number } => !!e)
    .sort((a, b) => a.y - b.y)
  for (let k = 1; k < ends.length; k += 1) if (ends[k]!.y - ends[k - 1]!.y < 12) ends[k]!.y = ends[k - 1]!.y + 12
  const codeOf = (s: Series) => (s.key === 'median' ? 'Median' : ctx.rows.find((r) => r.fips === s.key)?.code ?? s.label)
  const hot = sv.hot
  const clipId = `trend-clip-${slug}`
  return (
    <div ref={host}>
      <LegendChips
        label="Lines"
        items={series.map((s) => ({ key: s.key, label: s.label, color: s.color }))}
        off={sv.off}
        onToggle={sv.toggle}
        onHot={sv.setHot}
      />
      <p className="folio-chart-title">
        {ctx.metricLabel} by vintage, {vs[0]} to {vs[vs.length - 1]}
      </p>
      <svg viewBox={`0 0 ${w} ${h}`} width={w} height={h} role="group" aria-label={`${ctx.metricLabel} trend, ${vs[0]} to ${vs[vs.length - 1]}`} style={{ display: 'block', overflow: 'visible' }} onPointerLeave={tt.hide}>
        <defs>
          <clipPath id={clipId}>
            <rect x={0} y={0} width={Math.max(0, padL + (w - padL) * p)} height={h} />
          </clipPath>
        </defs>
        {sc.ticks.map((t) => (
          <g key={t}>
            <line x1={padL} x2={w - padR} y1={y(t)} y2={y(t)} stroke={t === sc.min ? 'var(--ink)' : 'var(--rule)'} strokeWidth={t === sc.min ? 1.5 : 1} />
            <text x={padL - 8} y={y(t) + 4} textAnchor="end" className="folio-svg-micro">
              {ctx.fmt(slug, t)}
            </text>
          </g>
        ))}
        {vs.map((v, i) => (
          <text key={v} x={x(i)} y={h - 8} textAnchor="middle" className="folio-svg-micro">
            {v}
          </text>
        ))}
        {series.map((s) => {
          const on = sv.on(s.key)
          return (
            <g key={s.key} style={{ opacity: on ? (hot && hot !== s.key ? 0.2 : 1) : 0, transition: 'opacity var(--d-3) var(--ease-std)', pointerEvents: 'none' }}>
              <path d={path(s.values)} fill="none" stroke={s.color} strokeWidth={s.width} strokeDasharray={s.dash} clipPath={`url(#${clipId})`} />
              {s.values.map((v, i) =>
                v == null ? null : (
                  <rect
                    key={i}
                    x={x(i) - 3}
                    y={y(v) - 3}
                    width={6}
                    height={6}
                    fill={s.color}
                    style={{ opacity: p >= (vs.length === 1 ? 0 : i / (vs.length - 1)) - 0.03 ? 1 : 0, transition: 'opacity 180ms var(--ease-out)' }}
                  />
                ),
              )}
            </g>
          )
        })}
        {ends.map((e) => (
          <text
            key={e.s.key}
            x={x(e.i) + 10}
            y={e.y + 4}
            style={{
              fontSize: 11,
              fontWeight: 500,
              fill: 'var(--ink)',
              opacity: (hot && hot !== e.s.key ? 0.2 : 1) * (p >= e.i / Math.max(1, vs.length - 1) - 0.03 ? 1 : 0),
              transition: 'opacity 200ms var(--ease-std)',
            }}
          >
            {codeOf(e.s)}
          </text>
        ))}
        {vs.map((v, i) => {
          const slot = (w - padL - padR) / Math.max(1, vs.length - 1)
          const lines = shown.map((s) => `${s.label}: ${ctx.fmt(slug, s.values[i] ?? null)}`)
          return (
            <rect
              key={v}
              x={x(i) - slot / 2}
              y={padT}
              width={slot}
              height={h - padT - padB}
              fill="transparent"
              tabIndex={0}
              role="img"
              aria-label={`${v}: ${lines.join('; ')}`}
              {...tt.bind({ cat: ctx.metricLabel, val: v, sub: lines.join(' | ') })}
            />
          )
        })}
      </svg>
      <Tooltip tip={tt.tip} />
    </div>
  )
}
