import { useMemo } from 'react'
import { censusMetricRankDirection } from '../../utils/censusDataDictionary'
import { heatmapStory } from '../../utils/matrixStory'
import { cellStyle, rankShade, sortByKey } from './data'
import { Empty, ScaleLegend } from './parts'
import { nextSort } from './PivotSection'
import SectionShell from './SectionShell'
import type { MatrixCtx } from './types'

/** Geographies as rows, metrics as columns; each cell is shaded by that metric's rank. Click a column header to sort by it. */
export default function HeatmapSection({ ctx }: { ctx: MatrixCtx }) {
  const { metrics } = ctx
  const active = ctx.sortKey || ctx.metricSlug
  const sorted = useMemo(() => sortByKey(ctx.rows, active, ctx.sortDir), [ctx.rows, active, ctx.sortDir])
  const ranks = useMemo(
    () => Object.fromEntries(metrics.map((m) => [m.slug, rankShade(ctx.rows, m.slug, censusMetricRankDirection(m.slug) === 'lower')])),
    [ctx.rows, metrics],
  )
  const aria = (k: string) => (active === k ? (ctx.sortDir === 'asc' ? 'ascending' : 'descending') : 'none')
  const mark = (k: string) => (active === k ? (ctx.sortDir === 'asc' ? ' ▲' : ' ▼') : '')
  let lit = 0
  let withData = 0
  for (const r of ctx.rows)
    for (const m of metrics) {
      const t = ranks[m.slug]?.get(r.fips) ?? null
      if (r.vals[m.slug] != null) withData += 1
      if (t != null && t * 100 >= ctx.minPct) lit += 1
    }
  const story = heatmapStory({
    vintage: ctx.vintage,
    metricCount: metrics.length,
    geoCount: ctx.rows.length,
    leaders: metrics.map((m) => ctx.rows.filter((r) => ranks[m.slug]?.get(r.fips) === 1).map((r) => r.name)),
  })
  return (
    <SectionShell
      ctx={ctx}
      id="heatmap"
      wide
      headline={story.headline}
      lead={story.lead}
      text={
        <>
          <p>
            Every geography against every metric at once. Each cell is shaded by where that geography ranks on that metric among the {ctx.rows.length} shown,
            and each column is ranked on its own: darker is the better rank (the higher value, except where lower is better).
          </p>
          <p>Click a column header to sort the rows by it; click it again to reverse. Cells with no value are neutral and read “—”.</p>
        </>
      }
      caption={
        <>
          Rank shading of {metrics.length} metrics for {ctx.rows.length} geographies, sorted by {active === 'name' ? 'name' : ctx.labelOf(active)}; {ctx.vintage} ACS
          5-year. Source: ACS 5-year, {ctx.vintage}.
        </>
      }
      table={() => ({
        columns: [{ label: 'Geography' }, ...metrics.map((m) => ({ label: m.label, numeric: true }))],
        rows: sorted.map((r) => [r.name, ...metrics.map((m) => ctx.fmt(m.slug, r.vals[m.slug] ?? null))]),
      })}
    >
      {!ctx.rows.length || !metrics.length ? (
        <Empty>No data available for {ctx.vintage}.</Empty>
      ) : (
        <>
          <ScaleLegend ctx={ctx} note="each column ranked on its own" lit={`${lit} of ${withData} cells highlighted`} />
          <div className="folio-heat-scroll">
            <table className="folio-table folio-heat">
              <thead>
                <tr>
                  <th scope="col" className="folio-sticky text-left" aria-sort={aria('name')}>
                    <button type="button" onClick={() => nextSort(ctx, active, 'name')}>
                      State{mark('name')}
                    </button>
                  </th>
                  {metrics.map((m) => (
                    <th key={m.slug} scope="col" className="align-bottom" aria-sort={aria(m.slug)}>
                      <button type="button" onClick={() => nextSort(ctx, active, m.slug)}>
                        {m.label}
                        {mark(m.slug)}
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sorted.map((r) => (
                  <tr key={r.fips}>
                    <th scope="row" className="folio-sticky text-left">
                      {r.name}
                    </th>
                    {metrics.map((m) => (
                      <td key={m.slug} className="text-center" style={cellStyle(ctx.theme, ranks[m.slug]?.get(r.fips) ?? null, ctx.minPct)} title={`${r.name} · ${m.label}: ${ctx.fmt(m.slug, r.vals[m.slug] ?? null)}`}>
                        {ctx.fmt(m.slug, r.vals[m.slug] ?? null)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </SectionShell>
  )
}
