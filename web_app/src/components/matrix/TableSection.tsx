import { useMemo, useRef } from 'react'
import { censusMetricRankDirection } from '../../utils/censusDataDictionary'
import { CENSUS_REGION_LABEL } from '../../utils/censusRegions'
import { rowDelayMs } from '../../utils/folioMotion'
import { barFraction, changeTone, filterRows, signedChange, sparklinePath, sparklinePoints, toCsv, type CsvColumn } from '../../utils/matrixTable'
import { useFlip } from '../../hooks/useFlip'
import { metricOf, sortByKey } from './data'
import { useSection } from './hooks'
import { Empty, InlineBar, SortTh } from './parts'
import SectionShell from './SectionShell'
import type { MatrixCtx, Row } from './types'

interface TRow {
  r: Row
  region: string
  /** The selected metric at every vintage in the bundle, oldest first (null = no reading). */
  series: Array<number | null>
  /** Selected vintage minus the earliest vintage; null when either reading is missing. */
  change: number | null
}

const SPARK_W = 96
const SPARK_H = 24

/** Sparkline of one geography's readings across the bundle: breaks at a missing vintage, ends in a dot at the selected vintage. */
function Sparkline({ ctx, row, vIdx }: { ctx: MatrixCtx; row: TRow; vIdx: number }) {
  const slug = ctx.metricSlug
  const present = row.series.filter((x) => x != null).length
  if (present < 2) {
    return (
      <>
        <span aria-hidden="true">—</span>
        <span className="folio-sr-only">Trend: fewer than two readings</span>
      </>
    )
  }
  const { d } = sparklinePath(row.series, SPARK_W, SPARK_H)
  const pts = sparklinePoints(row.series, SPARK_W, SPARK_H)
  const dot = pts[vIdx] ?? null
  // A reading with a gap on both sides has no line to carry it, so it gets its own small dot.
  const lone = pts.flatMap((p, i) => (p && !pts[i - 1] && !pts[i + 1] && i !== vIdx ? [p] : []))
  const spoken = ctx.vintages.map((v, i) => `${v}: ${row.series[i] == null ? 'no data' : ctx.fmt(slug, row.series[i]!)}`).join(', ')
  return (
    <>
      <svg width={SPARK_W} height={SPARK_H} viewBox={`0 0 ${SPARK_W} ${SPARK_H}`} aria-hidden="true" focusable="false" style={{ display: 'block' }}>
        <path
          d={d}
          className="folio-spark-line"
          fill="none"
          stroke="var(--violet-ink)"
          strokeWidth={1.5}
          strokeLinejoin="round"
          strokeLinecap="round"
          pathLength={1}
        />
        {lone.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r={1.5} fill="var(--violet-ink)" />
        ))}
        {dot && <circle cx={dot.x} cy={dot.y} r={2.5} fill="var(--violet-ink)" className="folio-spark-dot" />}
      </svg>
      <span className="folio-sr-only">{spoken}</span>
    </>
  )
}

/** All geographies in scope with all metrics: search (`?q=`), sortable columns, bars, change and trend, and a CSV of the rows as filtered and sorted. */
export default function TableSection({ ctx }: { ctx: MatrixCtx }) {
  const q = ctx.sp.get('q') ?? ''
  const { vintage, vintages, metricSlug: slug } = ctx
  const base = vintages[0] ?? ''
  const hasPair = !!base && base !== vintage
  const vIdx = vintages.indexOf(vintage)
  const lowerBetter = censusMetricRankDirection(slug) === 'lower'
  const unit = metricOf(ctx.metrics, slug)?.format === 'percent' ? 'pp' : 'number'
  const active = ctx.sortRaw === 'change' || ctx.sortRaw === 'region' ? ctx.sortRaw : ctx.sortKey || slug
  const { seen } = useSection()
  const body = useRef<HTMLTableSectionElement>(null)

  const rows: TRow[] = useMemo(() => {
    const byVintage = vintages.map((v) => new Map((ctx.rowsByVintage[v] ?? []).map((r) => [r.fips, r.vals[slug] ?? null])))
    const flat: TRow[] = ctx.rows.map((r) => {
      const series = vintages.map((v, i) => (v === vintage ? (r.vals[slug] ?? null) : (byVintage[i]!.get(r.fips) ?? null)))
      const a = hasPair ? series[0] : null
      const c = r.vals[slug] ?? null
      return { r, region: r.region ? CENSUS_REGION_LABEL[r.region] : '', series, change: a != null && c != null ? c - a : null }
    })
    const dir = ctx.sortDir === 'asc' ? 1 : -1
    const byName = (a: TRow, b: TRow) => a.r.name.localeCompare(b.r.name)
    let sorted: TRow[]
    if (active === 'change' || active === 'region') {
      sorted = [...flat].sort((a, b) => {
        if (active === 'region') return a.region.localeCompare(b.region) * dir || byName(a, b)
        if (a.change == null && b.change == null) return byName(a, b)
        if (a.change == null) return 1
        if (b.change == null) return -1
        return (a.change - b.change) * dir || byName(a, b)
      })
    } else {
      const order = new Map(sortByKey(ctx.rows, active, ctx.sortDir).map((r, i) => [r.fips, i]))
      sorted = [...flat].sort((a, b) => order.get(a.r.fips)! - order.get(b.r.fips)!)
    }
    const searchable = sorted.map((x) => ({ x, name: x.r.name, code: x.r.code, regionLabel: x.region }))
    return filterRows(searchable, q, ['name', 'code', 'regionLabel']).map((f) => f.x)
  }, [ctx.rows, ctx.rowsByVintage, vintages, vintage, slug, hasPair, active, ctx.sortDir, q])

  // Each metric's bars run from its lowest to its highest value among the rows shown.
  const ranges = useMemo(() => {
    const out: Record<string, { min: number; max: number } | null> = {}
    for (const m of ctx.metrics) {
      const xs = rows.map((x) => x.r.vals[m.slug]).filter((v): v is number => v != null)
      out[m.slug] = xs.length ? { min: Math.min(...xs), max: Math.max(...xs) } : null
    }
    return out
  }, [rows, ctx.metrics])

  useFlip(body, rows.map((x) => x.r.fips).join(','), !ctx.reduced && seen)

  const sortBy = (key: string, firstDir: 'asc' | 'desc') =>
    ctx.setMany({ sort: key, dir: active === key ? (ctx.sortDir === 'desc' ? 'asc' : 'desc') : firstDir })
  const fileName = `matrix-map-${slug}-${vintage}.csv`
  const changeText = (x: TRow): string | null => signedChange(x.r.vals[slug] ?? null, hasPair ? (x.series[0] ?? null) : null, unit, (a) => ctx.fmt(slug, a))
  const changeLabel = hasPair ? `${base} to ${vintage}` : 'needs two vintages'

  const download = () => {
    const columns: CsvColumn[] = [
      { key: 'state', label: 'State' },
      { key: 'state_code', label: 'State code' },
      { key: 'fips', label: 'FIPS' },
      { key: 'region', label: 'Region' },
      { key: 'vintage', label: 'Vintage' },
      ...ctx.metrics.map((m) => ({ key: m.slug, label: m.label })),
      { key: 'change', label: 'Change' },
      ...vintages.map((v) => ({ key: `v${v}`, label: v })), // the header is the year, as a string
    ]
    const data = rows.map((x) => ({
      state: x.r.name,
      state_code: x.r.code,
      fips: x.r.fips,
      region: x.region,
      vintage: String(vintage), // a bare year is a string in anything exported
      ...Object.fromEntries(ctx.metrics.map((m) => [m.slug, x.r.vals[m.slug] ?? null])),
      // Values only: the difference of two readings in the metric's own unit, or empty when either is missing.
      change: x.change == null ? null : Math.round(x.change * 1e6) / 1e6,
      ...Object.fromEntries(vintages.map((v, i) => [`v${v}`, x.series[i] ?? null])),
    }))
    const blob = new Blob([toCsv(columns, data)], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = fileName
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  }

  return (
    <SectionShell
      ctx={ctx}
      id="table"
      wide
      headline={[`${ctx.rows.length} geographies,`, `${ctx.metrics.length} metrics,`, vintage]}
      text={
        <>
          <p>
            Every geography with every metric for {vintage}. A thin bar beside each number shows where it sits between the lowest and highest value among the
            rows shown. Change is {ctx.metricLabel} {hasPair ? `from ${base} to ${vintage}` : 'between two vintages (only one is selectable here)'}, and the
            trend line follows it through every vintage in the bundle; it breaks where a vintage has no reading.
          </p>
          <p>
            {rows.length} of {ctx.rows.length} geographies match{q ? ` “${q}”` : ''}. Search by name, state code or region, click a column header to sort, and
            download exactly the rows you see as a CSV (missing values are empty cells). The file is named {fileName}.
          </p>
        </>
      }
      caption={
        <>
          {rows.length} of {ctx.rows.length} geographies{q ? ` matching “${q}”` : ''}, sorted by{' '}
          {active === 'name' ? 'name' : active === 'region' ? 'region' : active === 'change' ? `change in ${ctx.metricLabel}` : ctx.labelOf(active)}; {vintage}{' '}
          ACS 5-year. Change in {ctx.metricLabel}: {changeLabel}. Source: ACS 5-year, {vintage}
          {hasPair ? ` and ${base}` : ''}.
        </>
      }
      table={() => ({
        columns: [
          { label: 'Geography' },
          { label: 'Region' },
          ...ctx.metrics.map((m) => ({ label: m.label, numeric: true })),
          { label: `Change in ${ctx.metricLabel}, ${changeLabel}`, numeric: true },
        ],
        rows: rows.map((x) => [x.r.name, x.region || '—', ...ctx.metrics.map((m) => ctx.fmt(m.slug, x.r.vals[m.slug] ?? null)), changeText(x) ?? '—']),
      })}
    >
      <div className="folio-controls">
        <label className="folio-field">
          Search
          <input type="search" className="folio-select" value={q} placeholder="Name, code or region" onChange={(e) => ctx.setQP('q', e.target.value)} />
        </label>
        <button type="button" className="folio-btn" onClick={download} disabled={!rows.length}>
          Download CSV
        </button>
      </div>
      {!ctx.rows.length ? (
        <Empty>No data available for {vintage}.</Empty>
      ) : !rows.length ? (
        <Empty>No geography matches “{q}”.</Empty>
      ) : (
        <div className="folio-mtable-scroll" tabIndex={0} role="region" aria-label={`All geographies and metrics, ${vintage}`}>
          <table className="folio-table folio-dtable folio-mtable">
            <caption className="folio-sr-only">
              All geographies and metrics, {vintage}; change in {ctx.metricLabel} {changeLabel}
            </caption>
            <thead>
              <tr>
                <SortTh label="State" active={active === 'name'} dir={ctx.sortDir} onSort={() => sortBy('name', 'asc')} className="folio-sticky" />
                <SortTh label="Region" active={active === 'region'} dir={ctx.sortDir} onSort={() => sortBy('region', 'asc')} />
                {ctx.metrics.map((m) => (
                  <SortTh key={m.slug} label={m.label} numeric active={active === m.slug} dir={ctx.sortDir} onSort={() => sortBy(m.slug, 'desc')} />
                ))}
                <SortTh label={`Change · ${changeLabel}`} numeric active={active === 'change'} dir={ctx.sortDir} onSort={() => sortBy('change', 'desc')} />
                <th scope="col" className="text-left">
                  Trend · {ctx.metricLabel}
                </th>
              </tr>
            </thead>
            <tbody ref={body}>
              {rows.map((x, i) => {
                const delay = ctx.reduced ? 0 : rowDelayMs(i, rows.length, 12, 400)
                const ct = changeText(x)
                const tone = x.change != null && x.change !== 0 ? changeTone(x.change, lowerBetter) : null
                return (
                  <tr key={x.r.fips} data-flip={x.r.fips}>
                    <th scope="row" className="folio-sticky text-left">
                      {x.r.name}
                    </th>
                    <td className="folio-muted-cell">{x.region || '—'}</td>
                    {ctx.metrics.map((m) => {
                      const v = x.r.vals[m.slug] ?? null
                      const rg = ranges[m.slug]
                      return (
                        <td key={m.slug} className="text-right">
                          <InlineBar fraction={rg ? barFraction(v, rg.min, rg.max) : null} delayMs={delay}>
                            {ctx.fmt(m.slug, v)}
                          </InlineBar>
                        </td>
                      )
                    })}
                    <td
                      className="text-right"
                      style={{
                        color: tone == null ? 'var(--ink-2)' : tone === 'good' ? 'var(--violet-ink)' : 'var(--vermilion-ink)',
                        fontWeight: tone ? 500 : undefined,
                      }}
                    >
                      {ct ?? '—'}
                    </td>
                    <td>
                      <Sparkline ctx={ctx} row={x} vIdx={vIdx} />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </SectionShell>
  )
}
