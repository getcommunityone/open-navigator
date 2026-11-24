import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { staggerDelayMs } from '../../utils/folioMotion'
import { largestRemainder } from '../../utils/matrixMapMath'
import { useSeries } from './hooks'
import LegendChips from './LegendChips'
import { Empty, Seg } from './parts'
import SectionShell from './SectionShell'
import { Tooltip, useTooltip } from './Tooltip'
import { delayVar, type MatrixCtx } from './types'

interface Part {
  id: string
  name: string
  value: number
}
const TOP = 8

/** Part-of-whole: states of the U.S. total, or counties of one state. Additive (count) metrics only. */
export default function ShareSection({ ctx }: { ctx: MatrixCtx }) {
  const { sp, theme, countMetrics, fmt } = ctx
  const scope: 'state' | 'county' = sp.get('part') === 'county' ? 'county' : 'state'
  const stateFips = sp.get('st') || '01'
  // Part-of-whole only makes sense for additive (count) metrics: a non-count metric falls back to the first count metric.
  const slug = countMetrics.some((m) => m.slug === ctx.metricSlug) ? ctx.metricSlug : countMetrics[0]?.slug ?? ''
  const label = ctx.labelOf(slug)
  const fellBack = !!slug && slug !== ctx.metricSlug
  const stateName = ctx.rows.find((r) => r.fips === stateFips)?.name ?? stateFips
  const { data: counties, isLoading } = useQuery({
    queryKey: ['census-county-metrics', ctx.vintage],
    queryFn: async (): Promise<{ values: Record<string, Record<string, number | string | null | undefined>> } | null> => {
      const r = await fetch(`/data/census-map/${ctx.vintage}/county_metrics.json`)
      return r.ok ? r.json() : null
    },
    enabled: scope === 'county' && !!ctx.vintage,
    retry: false,
    staleTime: 1000 * 60 * 60,
  })
  const tt = useTooltip()

  const model = useMemo(() => {
    let parts: Part[] = []
    let missing = ''
    if (!slug) missing = 'No additive (count) metrics are published.'
    else if (scope === 'state') {
      // ACS "United States" excludes Puerto Rico, so it is left out of the whole.
      parts = ctx.rows.filter((r) => r.fips !== '72' && r.vals[slug] != null).map((r) => ({ id: r.fips, name: r.name, value: r.vals[slug] as number }))
    } else if (counties) {
      parts = Object.entries(counties.values)
        .filter(([gid, v]) => gid.startsWith(stateFips.padStart(2, '0')) && typeof v[slug] === 'number')
        .map(([gid, v]) => ({ id: gid, name: typeof v.NAME === 'string' ? v.NAME.replace(/,.*$/, '') : gid, value: v[slug] as number }))
    } else if (!isLoading) missing = 'county_metrics.json for this vintage is not published.'
    parts = parts.filter((p) => p.value > 0).sort((a, b) => b.value - a.value)
    const rest = parts.slice(TOP).reduce((a, p) => a + p.value, 0)
    const head = parts.slice(0, TOP)
    const segs = rest > 0 ? [...head, { id: 'rest', name: `All others (${parts.length - TOP})`, value: rest }] : head
    return { parts, segs, missing }
  }, [ctx.rows, slug, scope, counties, stateFips, isLoading])

  const keys = useMemo(() => model.segs.map((s) => s.id), [model.segs])
  const series = useSeries(ctx, 'share', keys)
  const visible = model.segs.filter((s) => series.on(s.id))
  const total = visible.reduce((a, s) => a + s.value, 0)
  const colorOf = (id: string) => theme.seg[Math.max(0, keys.indexOf(id))] ?? theme.neutral
  const pct = (v: number) => `${((v / total) * 100).toFixed(1)}%`
  const cells = largestRemainder(visible.map((s) => s.value))
  const waffle = cells.flatMap((n, i) => Array<number>(n).fill(i))
  const whole = scope === 'state' ? 'U.S. total (50 states + DC)' : `${stateName} counties`
  const unit = scope === 'state' ? 'states' : 'counties'
  const segOfPart = (p: Part) => {
    const i = model.parts.indexOf(p)
    return i < TOP ? p.id : 'rest'
  }
  const shownParts = model.parts.filter((p) => series.on(segOfPart(p)))
  const hot = series.hot

  return (
    <SectionShell
      ctx={ctx}
      id="share"
      headline={[`${label}, as a share`, `of ${whole}`, ctx.vintage]}
      text={
        <>
          <p>
            One 100% stacked bar and a waffle of 100 squares show how the whole divides among the largest {unit}; the rest are grouped as
            “All others”. Click a legend chip to take a segment out: the others re-share the remaining total.
          </p>
          {fellBack && (
            <p>
              Part-of-whole needs a count. {ctx.metricLabel} is not a count, so this section shows {label}.
            </p>
          )}
          {total > 0 && (
            <p>
              Whole shown: {fmt(slug, total)} across {shownParts.length} {unit} with data.
            </p>
          )}
        </>
      }
      controls={
        <>
          <Seg
            label="Whole"
            value={scope}
            onChange={(v) => ctx.setMany({ part: v === 'county' ? 'county' : null })}
            options={[
              { value: 'state', label: 'States of U.S.' },
              { value: 'county', label: 'Counties of a state' },
            ]}
          />
          {scope === 'county' && (
            <select aria-label="State" className="folio-select" value={stateFips} onChange={(e) => ctx.setQP('st', e.target.value)}>
              {[...ctx.rows].sort((a, b) => a.name.localeCompare(b.name)).map((r) => (
                <option key={r.fips} value={r.fips}>
                  {r.name}
                </option>
              ))}
            </select>
          )}
        </>
      }
      caption={
        <>
          {label} as a share of {whole}, {ctx.vintage}; {visible.length} of {model.segs.length} segments shown. Source: ACS 5-year, {ctx.vintage}.
        </>
      }
      table={() => ({
        columns: [{ label: scope === 'state' ? 'State' : 'County' }, { label, numeric: true }, { label: 'Share of shown total', numeric: true }],
        rows: shownParts.map((p) => [p.name, fmt(slug, p.value), pct(p.value)]),
      })}
    >
      {model.missing ? (
        <Empty>No data available — {model.missing}</Empty>
      ) : !model.segs.length ? (
        <Empty>{isLoading ? 'Loading counties…' : `No data available for ${label}.`}</Empty>
      ) : (
        <div>
          <LegendChips
            label="Segments"
            items={model.segs.map((s) => ({ key: s.id, label: s.name, color: colorOf(s.id) }))}
            off={series.off}
            onToggle={series.toggle}
            onHot={series.setHot}
          />
          <div className="folio-stackbar" role="img" aria-label={`Share of ${whole}`} onPointerLeave={tt.hide}>
            {model.segs.map((s, i) => {
              const on = series.on(s.id)
              return (
                <div
                  key={s.id}
                  className="folio-stackseg"
                  style={{
                    ...delayVar(i * 60),
                    width: on && total > 0 ? `${(s.value / total) * 100}%` : '0%',
                    background: colorOf(s.id),
                    opacity: hot && hot !== s.id ? 0.3 : 1,
                  }}
                  {...(on ? tt.bind({ cat: s.name, val: pct(s.value), sub: `${fmt(slug, s.value)} of ${fmt(slug, total)}` }) : {})}
                />
              )
            })}
          </div>
          <div className="mt-3 flex flex-wrap gap-4">
            <div className="folio-waffle" role="img" aria-label="Waffle: each square is 1% of the whole shown">
              {waffle.map((si, k) => (
                <span
                  key={k}
                  className="folio-pop"
                  style={{
                    ...delayVar(staggerDelayMs(k % 10, Math.floor(k / 10), 18, 700)),
                    background: colorOf(visible[si]!.id),
                    opacity: hot && hot !== visible[si]!.id ? 0.3 : 1,
                  }}
                />
              ))}
            </div>
            <ul className="folio-share-list">
              {visible.map((s) => (
                <li key={s.id}>
                  <span className="folio-legend-swatch" style={{ background: colorOf(s.id) }} /> {s.name}
                  <span className="folio-row-val"> {fmt(slug, s.value)} · {pct(s.value)}</span>
                </li>
              ))}
            </ul>
          </div>
          <Tooltip tip={tt.tip} />
        </div>
      )}
    </SectionShell>
  )
}
