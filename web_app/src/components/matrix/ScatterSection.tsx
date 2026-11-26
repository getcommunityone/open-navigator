import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { CENSUS_REGION_LABEL, type CensusRegionId } from '../../utils/censusRegions'
import { rowDelayMs } from '../../utils/folioMotion'
import { scatterStory } from '../../utils/matrixStory'
import { niceScale, olsFit } from '../../utils/matrixMapMath'
import { useElementWidth, useFitHeight, useSeries } from './hooks'
import LegendChips from './LegendChips'
import { Empty } from './parts'
import SectionShell from './SectionShell'
import { Tooltip, useTooltip } from './Tooltip'
import { delayVar, type MatrixCtx } from './types'

const REGIONS = Object.keys(CENSUS_REGION_LABEL) as CensusRegionId[]

/** Two metrics across states, coloured by Census region, with a live OLS line, slope and r². Legend chips toggle regions. */
export default function ScatterSection({ ctx }: { ctx: MatrixCtx }) {
  const xSlug = ctx.metricSlug
  const ySlug = ctx.sp.get('y') && ctx.metrics.some((m) => m.slug === ctx.sp.get('y')) ? ctx.sp.get('y')! : ctx.metrics.find((m) => m.slug !== xSlug)?.slug ?? ''
  const sv = useSeries(ctx, 'scatter', REGIONS)
  const [trend, setTrend] = useState(true)
  const host = useRef<HTMLDivElement>(null)
  const w = useElementWidth(host)
  const tt = useTooltip()
  const pts = ctx.rows
    .map((r) => ({ r, x: r.vals[xSlug] ?? null, y: r.vals[ySlug] ?? null }))
    .filter((p): p is { r: MatrixCtx['rows'][number]; x: number; y: number } => p.x != null && p.y != null)
  const vis = pts.filter((p) => sv.on(p.r.region ?? ''))
  const fit = olsFit(vis)
  const xl = ctx.labelOf(xSlug)
  const yl = ctx.labelOf(ySlug)
  const usable = !!ySlug && pts.length >= 3
  const story = scatterStory({ xLabel: xl, yLabel: yl, n: fit?.n ?? vis.length, total: ctx.rows.length, fit: fit ? { slope: fit.slope, r2: fit.r2 } : null })

  const H = useFitHeight(360, 505)
  const pad = { l: 64, r: 14, t: 12, b: 46 }
  const hot = sv.hot
  const xs = pts.map((p) => p.x)
  const ys = pts.map((p) => p.y)
  const sx = usable ? niceScale(Math.min(...xs), Math.max(...xs), 4) : null
  const sy = usable ? niceScale(Math.min(...ys), Math.max(...ys), 4) : null
  const X = (v: number) => pad.l + ((v - sx!.min) / (sx!.max - sx!.min || 1)) * (w - pad.l - pad.r)
  const Y = (v: number) => H - pad.b - ((v - sy!.min) / (sy!.max - sy!.min || 1)) * (H - pad.t - pad.b)
  const order = new Map(pts.map((p, i) => [p.r.fips, i]))

  return (
    <SectionShell
      ctx={ctx}
      id="scatter"
      headline={story.headline}
      lead={story.lead}
      text={
        <>
          <p>
            Each dot is one geography, placed by {xl.toLowerCase()} (across) and {yl.toLowerCase()} (up) and coloured by Census region. The dashed line is a
            least-squares fit through the dots shown; it updates as you hide regions with the legend chips.
          </p>
          {fit && (
            <p>
              Slope {fit.slope.toPrecision(3)}, r² {fit.r2.toFixed(2)}, n={fit.n}. A relationship in these data is not evidence that one metric causes the other.
            </p>
          )}
        </>
      }
      controls={
        <label className="folio-field">
          vs
          <select className="folio-select" value={ySlug} onChange={(e) => ctx.setQP('y', e.target.value)}>
            {ctx.metrics.map((m) => (
              <option key={m.slug} value={m.slug}>
                {m.label}
              </option>
            ))}
          </select>
        </label>
      }
      caption={
        <>
          {yl} against {xl}, one point per geography, coloured by Census region; {vis.length} points shown, {ctx.vintage} ACS 5-year. Source: ACS 5-year, {ctx.vintage}.
        </>
      }
      table={() =>
        usable
          ? {
              columns: [{ label: 'Geography' }, { label: 'Region' }, { label: xl, numeric: true }, { label: yl, numeric: true }],
              rows: vis.map((p) => [p.r.name, p.r.region ? CENSUS_REGION_LABEL[p.r.region] : '—', ctx.fmt(xSlug, p.x), ctx.fmt(ySlug, p.y)]),
            }
          : null
      }
    >
      {!usable ? (
        <Empty>No data available — need at least 3 geographies with both metrics.</Empty>
      ) : (
        <div ref={host}>
          <LegendChips
            label="Regions"
            items={REGIONS.map((id, i) => ({ key: id, label: CENSUS_REGION_LABEL[id], color: ctx.theme.series[i]! }))}
            off={sv.off}
            onToggle={sv.toggle}
            onHot={sv.setHot}
          />
          <label className="inline-flex items-center gap-1 folio-note">
            <input type="checkbox" checked={trend} style={{ accentColor: 'var(--violet-ink)' }} onChange={(e) => setTrend(e.target.checked)} /> Trend line
          </label>
          <svg viewBox={`0 0 ${w} ${H}`} width={w} height={H} role="img" aria-label={`${yl} versus ${xl} by state`} style={{ display: 'block', overflow: 'visible' }} onPointerLeave={tt.hide}>
            {sy!.ticks.map((t) => (
              <g key={`y${t}`}>
                <line x1={pad.l} x2={w - pad.r} y1={Y(t)} y2={Y(t)} stroke="var(--rule)" />
                <text x={pad.l - 8} y={Y(t) + 4} textAnchor="end" className="folio-svg-micro">
                  {ctx.fmt(ySlug, t)}
                </text>
              </g>
            ))}
            {sx!.ticks.map((t) => (
              <text key={`x${t}`} x={X(t)} y={H - pad.b + 16} textAnchor="middle" className="folio-svg-micro">
                {ctx.fmt(xSlug, t)}
              </text>
            ))}
            <line x1={pad.l} x2={w - pad.r} y1={H - pad.b} y2={H - pad.b} stroke="var(--ink)" />
            <line x1={pad.l} x2={pad.l} y1={pad.t} y2={H - pad.b} stroke="var(--ink)" />
            <text x={(w + pad.l) / 2} y={H - 6} textAnchor="middle" className="folio-svg-micro">
              {xl}
            </text>
            <text transform={`translate(12 ${(H - pad.b) / 2}) rotate(-90)`} textAnchor="middle" className="folio-svg-micro">
              {yl}
            </text>
            {fit && (
              <line
                x1={X(Math.min(...vis.map((p) => p.x)))}
                x2={X(Math.max(...vis.map((p) => p.x)))}
                y1={Y(fit.slope * Math.min(...vis.map((p) => p.x)) + fit.intercept)}
                y2={Y(fit.slope * Math.max(...vis.map((p) => p.x)) + fit.intercept)}
                stroke="var(--ink)"
                strokeWidth={1.5}
                strokeDasharray="5 4"
                style={{ opacity: trend ? 1 : 0, transition: 'opacity 180ms var(--ease-std)', pointerEvents: 'none' }}
              />
            )}
            {pts.map((p) => {
              const ri = REGIONS.indexOf((p.r.region ?? '') as CensusRegionId)
              const on = sv.on(p.r.region ?? '')
              const info = { cat: p.r.name, val: `${ctx.fmt(xSlug, p.x)} / ${ctx.fmt(ySlug, p.y)}`, sub: `${xl} / ${yl}${p.r.region ? ` · ${CENSUS_REGION_LABEL[p.r.region]}` : ''}` }
              return (
                <Link key={p.r.fips} to={ctx.mapHref} tabIndex={on ? 0 : -1} aria-hidden={!on} aria-label={`${p.r.name}: ${info.val}`} style={{ pointerEvents: on ? 'auto' : 'none' }}>
                  <circle
                    className="folio-pop"
                    cx={X(p.x)}
                    cy={Y(p.y)}
                    r={5}
                    fill={ri >= 0 ? ctx.theme.series[ri] : 'var(--ink-3)'}
                    stroke="var(--ink)"
                    strokeWidth={0.75}
                    style={{
                      ...delayVar(rowDelayMs(order.get(p.r.fips) ?? 0, pts.length, 12, 500)),
                      opacity: on ? (hot && hot !== p.r.region ? 0.2 : 0.9) : 0,
                      transition: 'opacity var(--d-3) var(--ease-std)',
                    }}
                    {...tt.bind(info)}
                  />
                </Link>
              )
            })}
          </svg>
          <Tooltip tip={tt.tip} />
        </div>
      )}
    </SectionShell>
  )
}
