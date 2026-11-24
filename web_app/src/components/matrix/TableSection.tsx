import { useMemo } from 'react'
import { CENSUS_REGION_LABEL } from '../../utils/censusRegions'
import { filterRows, toCsv, type CsvColumn } from '../../utils/matrixTable'
import { sortByKey } from './data'
import { Empty } from './parts'
import { nextSort } from './PivotSection'
import SectionShell from './SectionShell'
import type { MatrixCtx } from './types'

/** All geographies in scope with all metrics: search (`?q=`), sortable columns and a CSV of the rows as filtered and sorted. */
export default function TableSection({ ctx }: { ctx: MatrixCtx }) {
  const q = ctx.sp.get('q') ?? ''
  const active = ctx.sortKey || ctx.metricSlug
  const rows = useMemo(() => {
    const sorted = sortByKey(ctx.rows, active, ctx.sortDir)
    const flat = sorted.map((r) => ({ r, name: r.name, code: r.code, regionLabel: r.region ? CENSUS_REGION_LABEL[r.region] : '' }))
    return filterRows(flat, q, ['name', 'code', 'regionLabel']).map((x) => x.r)
  }, [ctx.rows, active, ctx.sortDir, q])
  const aria = (k: string) => (active === k ? (ctx.sortDir === 'asc' ? 'ascending' : 'descending') : 'none')
  const mark = (k: string) => (active === k ? (ctx.sortDir === 'asc' ? ' ▲' : ' ▼') : '')
  const fileName = `matrix-map-${ctx.metricSlug}-${ctx.vintage}.csv`

  const download = () => {
    const columns: CsvColumn[] = [
      { key: 'state', label: 'State' },
      { key: 'state_code', label: 'State code' },
      { key: 'fips', label: 'FIPS' },
      { key: 'region', label: 'Region' },
      { key: 'vintage', label: 'Vintage' },
      ...ctx.metrics.map((m) => ({ key: m.slug, label: m.label })),
    ]
    const data = rows.map((r) => ({
      state: r.name,
      state_code: r.code,
      fips: r.fips,
      region: r.region ? CENSUS_REGION_LABEL[r.region] : '',
      vintage: String(ctx.vintage), // a bare year is a string in anything exported
      ...Object.fromEntries(ctx.metrics.map((m) => [m.slug, r.vals[m.slug] ?? null])),
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
      headline={[`${ctx.rows.length} geographies,`, `${ctx.metrics.length} metrics,`, ctx.vintage]}
      text={
        <>
          <p>
            Every geography with every metric for {ctx.vintage}. Search by name, state code or region, click a column header to sort, and download exactly the
            rows you see as a CSV. Missing values read “—” here and are empty cells in the file.
          </p>
          <p>
            {rows.length} of {ctx.rows.length} geographies match{q ? ` “${q}”` : ''}. The file is named {fileName}.
          </p>
        </>
      }
      caption={
        <>
          {rows.length} of {ctx.rows.length} geographies{q ? ` matching “${q}”` : ''}, sorted by {active === 'name' ? 'name' : ctx.labelOf(active)}; {ctx.vintage} ACS
          5-year. Source: ACS 5-year, {ctx.vintage}.
        </>
      }
      table={() => ({
        columns: [{ label: 'Geography' }, { label: 'Region' }, ...ctx.metrics.map((m) => ({ label: m.label, numeric: true }))],
        rows: rows.map((r) => [r.name, r.region ? CENSUS_REGION_LABEL[r.region] : '—', ...ctx.metrics.map((m) => ctx.fmt(m.slug, r.vals[m.slug] ?? null))]),
      })}
    >
      <div className="folio-controls">
        <label className="folio-field">
          Search
          <input
            type="search"
            className="folio-select"
            value={q}
            placeholder="Name, code or region"
            onChange={(e) => ctx.setQP('q', e.target.value)}
          />
        </label>
        <button type="button" className="folio-btn" onClick={download} disabled={!rows.length}>
          Download CSV
        </button>
      </div>
      {!ctx.rows.length ? (
        <Empty>No data available for {ctx.vintage}.</Empty>
      ) : !rows.length ? (
        <Empty>No geography matches “{q}”.</Empty>
      ) : (
        <div className="folio-heat-scroll">
          <table className="folio-table folio-heat folio-full">
            <caption className="folio-sr-only">All geographies and metrics, {ctx.vintage}</caption>
            <thead>
              <tr>
                <th scope="col" className="folio-sticky text-left" aria-sort={aria('name')}>
                  <button type="button" onClick={() => nextSort(ctx, active, 'name')}>
                    State{mark('name')}
                  </button>
                </th>
                <th scope="col" className="text-left">Region</th>
                {ctx.metrics.map((m) => (
                  <th key={m.slug} scope="col" className="text-right align-bottom" aria-sort={aria(m.slug)}>
                    <button type="button" onClick={() => nextSort(ctx, active, m.slug)}>
                      {m.label}
                      {mark(m.slug)}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.fips}>
                  <th scope="row" className="folio-sticky text-left">
                    {r.name}
                  </th>
                  <td>{r.region ? CENSUS_REGION_LABEL[r.region] : '—'}</td>
                  {ctx.metrics.map((m) => (
                    <td key={m.slug} className="text-right">
                      {ctx.fmt(m.slug, r.vals[m.slug] ?? null)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SectionShell>
  )
}
