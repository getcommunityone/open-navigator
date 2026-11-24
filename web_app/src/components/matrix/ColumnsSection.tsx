import { useMemo, useRef, useState } from 'react'
import { CENSUS_REGION_LABEL, type CensusRegionId } from '../../utils/censusRegions'
import { niceScale } from '../../utils/matrixMapMath'
import { stackByRegion } from '../../utils/matrixTable'
import { useElementWidth, useSection, useSeries } from './hooks'
import LegendChips from './LegendChips'
import { Empty, Seg } from './parts'
import SectionShell from './SectionShell'
import { Tooltip, useTooltip } from './Tooltip'
import type { MatrixCtx } from './types'

const REGIONS = Object.keys(CENSUS_REGION_LABEL) as CensusRegionId[]
type Mode = 'abs' | 'share'

/** Stacked columns: one per vintage, stacked by Census region. Only for metrics that can be summed (counts). */
export default function ColumnsSection({ ctx }: { ctx: MatrixCtx }) {
  const { metricSlug: slug, metrics, vintages } = ctx
  const isCount = metrics.find((m) => m.slug === slug)?.format === 'count'
  const [mode, setMode] = useState<Mode>('abs')
  const sv = useSeries(ctx, 'columns', REGIONS)
  const pending = vintages.some((v) => ctx.rowsByVintage[v] === undefined)
  const data = useMemo(
    () =>
      stackByRegion(
        vintages.map((v) => ({
          vintage: v,
          items: (ctx.rowsByVintage[v] ?? []).map((r) => ({ region: r.region, value: r.vals[slug] ?? null })),
        })),
        REGIONS,
      ),
    [vintages, ctx.rowsByVintage, slug],
  )
  const have = new Set(vintages.filter((v) => ctx.rowsByVintage[v]))
  const shown = REGIONS.filter((id) => sv.on(id))
  /** Per vintage: the value drawn for each shown region (a count, or its share of the shown regions' total). */
  const cols = data.map((d) => {
    const sum = shown.reduce((a, id) => a + (d.byRegion[id] ?? 0), 0)
    const any = shown.some((id) => d.byRegion[id] != null)
    return {
      d,
      sum: any ? sum : null,
      draw: Object.fromEntries(
        shown.map((id) => {
          const v = d.byRegion[id]
          return [id, v == null ? null : mode === 'share' ? (sum > 0 ? (v / sum) * 100 : null) : v]
        }),
      ) as Record<string, number | null>,
    }
  })
  const fmtShare = (v: number | null) => (v == null ? '—' : `${v.toFixed(1)}%`)
  const first = vintages[0]
  const last = vintages[vintages.length - 1]
  const firstCol = cols.find((c) => c.sum != null)
  const lastCol = [...cols].reverse().find((c) => c.sum != null)

  let body: React.ReactNode
  if (!isCount) {
    const alt = ctx.countMetrics[0]
    body = (
      <div className="folio-status" role="status">
        <p>
          <strong>This metric can't be stacked.</strong> {ctx.metricLabel} is a {metrics.find((m) => m.slug === slug)?.format ?? 'non-count'} measure, so
          adding it up across states would not mean anything. Columns are shown only for counts.
        </p>
        {alt && (
          <p className="mt-2">
            <button type="button" className="folio-link-btn" onClick={() => ctx.setQP('metric', alt.slug)}>
              Switch to {alt.label}
            </button>
          </p>
        )}
      </div>
    )
  } else if (pending) body = <Empty>Loading vintages…</Empty>
  else if (!cols.some((c) => c.sum != null)) body = <Empty>No data available for {ctx.metricLabel} in any vintage.</Empty>
  else body = <ColumnChart ctx={ctx} cols={cols} shown={shown} mode={mode} sv={sv} have={have} fmtShare={fmtShare} />

  return (
    <SectionShell
      ctx={ctx}
      id="columns"
      headline={[ctx.metricLabel, `by Census region,`, vintages.length > 1 ? `${first} to ${last}` : `${first ?? ''}`]}
      text={
        <>
          <p>
            One column per published vintage, stacked by Census region. Each segment is the sum of the states with a value; a region with no value
            in a vintage is left out of that column, never counted as zero. “Share of total” rescales every column to 100%.
          </p>
          {isCount && firstCol && lastCol && (
            <p>
              Total of the regions shown: {ctx.fmt(slug, firstCol.sum)} in {firstCol.d.vintage}
              {lastCol !== firstCol ? ` and ${ctx.fmt(slug, lastCol.sum)} in ${lastCol.d.vintage}` : ''}. The state count per region can differ between
              vintages; hover a column for it.
            </p>
          )}
        </>
      }
      controls={
        isCount ? (
          <Seg
            label="Column values"
            value={mode}
            onChange={(v) => setMode(v as Mode)}
            options={[
              { value: 'abs', label: 'Absolute' },
              { value: 'share', label: 'Share of total' },
            ]}
          />
        ) : undefined
      }
      caption={
        isCount ? (
          <>
            {ctx.metricLabel} summed by Census region, one column per vintage; {shown.length} of {REGIONS.length} regions shown,{' '}
            {mode === 'abs' ? 'absolute' : 'share of the shown total'}. Source: ACS 5-year.
          </>
        ) : (
          <>Nothing is drawn: {ctx.metricLabel} is not a count and cannot be summed across states.</>
        )
      }
      table={() =>
        isCount && !pending
          ? {
              columns: [{ label: 'Vintage' }, ...shown.map((id) => ({ label: CENSUS_REGION_LABEL[id], numeric: true })), { label: mode === 'abs' ? 'Total' : 'Total (share)', numeric: true }],
              rows: cols.map((c) => [
                c.d.vintage,
                ...shown.map((id) => (mode === 'abs' ? ctx.fmt(slug, c.d.byRegion[id] ?? null) : fmtShare(c.draw[id] ?? null))),
                mode === 'abs' ? ctx.fmt(slug, c.sum) : c.sum == null ? '—' : '100.0%',
              ]),
            }
          : null
      }
    >
      {body}
    </SectionShell>
  )
}

function ColumnChart({
  ctx,
  cols,
  shown,
  mode,
  sv,
  have,
  fmtShare,
}: {
  ctx: MatrixCtx
  cols: Array<{ d: ReturnType<typeof stackByRegion>[number]; sum: number | null; draw: Record<string, number | null> }>
  shown: CensusRegionId[]
  mode: Mode
  sv: ReturnType<typeof useSeries>
  have: Set<string>
  fmtShare: (v: number | null) => string
}) {
  const { seen } = useSection()
  const revealed = seen || ctx.reduced
  const host = useRef<HTMLDivElement>(null)
  const w = useElementWidth(host)
  const tt = useTooltip()
  const [cross, setCross] = useState<number | null>(null)
  const refs = useRef<Array<SVGRectElement | null>>([])
  const slug = ctx.metricSlug
  const padL = 56
  const padR = 12
  const padT = 34
  const padB = 44
  const h = 360
  const plotW = w - padL - padR
  const plotH = h - padT - padB
  const maxSum = Math.max(0, ...cols.map((c) => c.sum ?? 0))
  const sc = mode === 'share' ? { min: 0, max: 100, ticks: [0, 25, 50, 75, 100] } : niceScale(0, maxSum, 4, true)
  const yOf = (v: number) => padT + plotH - ((v - sc.min) / (sc.max - sc.min || 1)) * plotH
  const slot = plotW / cols.length
  const barW = Math.max(18, Math.min(48, slot * 0.68))
  const compact = slot < 36
  const hot = sv.hot
  return (
    <div ref={host}>
      <LegendChips
        label="Regions"
        items={REGIONS.map((id, i) => ({ key: id, label: CENSUS_REGION_LABEL[id], color: ctx.theme.series[i]! }))}
        off={sv.off}
        onToggle={sv.toggle}
        onHot={sv.setHot}
      />
      <p className="folio-chart-title">
        {ctx.metricLabel} by Census region, {mode === 'abs' ? 'absolute' : 'share of total'}
      </p>
      <svg viewBox={`0 0 ${w} ${h}`} width={w} height={h} role="group" aria-label={`${ctx.metricLabel} stacked by Census region`} style={{ display: 'block', overflow: 'visible' }} onPointerLeave={() => { tt.hide(); setCross(null) }}>
        {sc.ticks.map((t) => (
          <g key={t}>
            <line x1={padL} x2={w - padR} y1={yOf(t)} y2={yOf(t)} stroke={t === 0 ? 'var(--ink)' : 'var(--rule)'} strokeWidth={t === 0 ? 1.5 : 1} />
            <text x={padL - 8} y={yOf(t) + 4} textAnchor="end" className="folio-svg-micro">
              {mode === 'share' ? `${t}%` : ctx.fmt(slug, t)}
            </text>
          </g>
        ))}
        {cols.map((c, idx) => {
          const cx = padL + slot * idx + slot / 2
          const x0 = cx - barW / 2
          let acc = 0
          const delay = ctx.reduced ? 0 : idx * 45
          const total = c.sum
          return (
            <g key={c.d.vintage}>
              <g
                style={{
                  transformOrigin: `${cx}px ${padT + plotH}px`,
                  transform: `scaleY(${revealed ? 1 : 0})`,
                  transition: 'transform var(--d-3) var(--ease-out)',
                  transitionDelay: `${delay}ms`,
                }}
              >
                {REGIONS.map((id, ri) => {
                  const on = shown.includes(id)
                  const val = on ? c.draw[id] ?? null : null
                  const y1 = yOf(acc + (val ?? 0))
                  const y0 = yOf(acc)
                  if (val != null) acc += val
                  const hh = val != null ? Math.max(0, y0 - y1) : 0
                  return (
                    <rect
                      key={id}
                      x={x0}
                      width={barW}
                      fill={ctx.theme.series[ri]}
                      stroke="var(--paper)"
                      strokeWidth={val != null ? 1 : 0}
                      style={{
                        y: val != null ? y1 : y0,
                        height: hh,
                        opacity: hot && hot !== id ? 0.25 : 1,
                        transition: 'y var(--d-3) var(--ease-out), height var(--d-3) var(--ease-out), opacity var(--d-2) var(--ease-std)',
                      }}
                    />
                  )
                })}
              </g>
              <text
                x={cx}
                y={(total != null ? yOf(mode === 'share' ? 100 : total) : padT + plotH) - 7}
                textAnchor="middle"
                className="folio-svg-label"
                style={{ fontSize: compact ? 10 : 12, opacity: revealed ? 1 : 0, transition: 'opacity var(--d-2) var(--ease-out), y var(--d-3) var(--ease-out)', transitionDelay: `${delay + 300}ms` }}
              >
                {total == null ? '—' : mode === 'share' ? '100%' : ctx.fmt(slug, total)}
              </text>
              <text x={cx} y={padT + plotH + 18} textAnchor="middle" className="folio-svg-micro" style={compact ? { fontSize: 10 } : undefined}>
                {compact ? `’${c.d.vintage.slice(2)}` : c.d.vintage}
              </text>
              {!have.has(c.d.vintage) && (
                <text x={cx} y={padT + plotH + 32} textAnchor="middle" className="folio-svg-micro">
                  no file
                </text>
              )}
            </g>
          )
        })}
        {cross != null && <line x1={cross} x2={cross} y1={padT} y2={padT + plotH} stroke="var(--ink)" strokeDasharray="3 3" style={{ pointerEvents: 'none' }} />}
        {cols.map((c, idx) => {
          const cx = padL + slot * idx + slot / 2
          const lines = shown.map((id) => `${CENSUS_REGION_LABEL[id]}: ${mode === 'abs' ? ctx.fmt(slug, c.d.byRegion[id] ?? null) : fmtShare(c.draw[id] ?? null)}${c.d.byRegion[id] != null ? ` (${c.d.counts[id]} states)` : ''}`)
          const info = { cat: `${ctx.metricLabel} · ${c.d.vintage}`, val: c.sum == null ? '—' : ctx.fmt(slug, c.sum), sub: lines.join(' | ') }
          return (
            <rect
              key={c.d.vintage}
              ref={(n) => {
                refs.current[idx] = n
              }}
              x={padL + slot * idx}
              y={padT}
              width={slot}
              height={plotH}
              fill="transparent"
              tabIndex={0}
              role="img"
              aria-label={`${c.d.vintage}: total ${c.sum == null ? 'no data' : ctx.fmt(slug, c.sum)}. ${lines.join('; ')}`}
              onPointerEnter={(e) => { setCross(cx); tt.show(info, e) }}
              onPointerMove={(e) => tt.show(info, e)}
              onPointerLeave={() => { setCross(null); tt.hide() }}
              onFocus={(e) => { setCross(cx); tt.show(info, e.currentTarget) }}
              onBlur={() => { setCross(null); tt.hide() }}
              onKeyDown={(e) => {
                const n = refs.current.length
                if (e.key === 'ArrowRight') { e.preventDefault(); refs.current[(idx + 1) % n]?.focus() }
                else if (e.key === 'ArrowLeft') { e.preventDefault(); refs.current[(idx - 1 + n) % n]?.focus() }
              }}
            />
          )
        })}
      </svg>
      <Tooltip tip={tt.tip} />
    </div>
  )
}
