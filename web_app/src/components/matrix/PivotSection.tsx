import { useEffect, useMemo, useRef } from 'react'
import { Link } from 'react-router-dom'
import { CENSUS_REGION_LABEL, type CensusRegionId } from '../../utils/censusRegions'
import { rowDelayMs } from '../../utils/folioMotion'
import { barFraction } from '../../utils/matrixTable'
import { useFlip, useIntro } from '../../hooks/useFlip'
import { cellStyle, sortByKey } from './data'
import { useSection } from './hooks'
import { Empty, GROUP_OPTIONS, InlineBar, ScaleLegend, Seg, SortTh } from './parts'
import SectionShell from './SectionShell'
import { delayVar, type MatrixCtx } from './types'

const MAX_COLS = 8
const INTRO_MS = 900 + 600 + 100

/** The chosen pivot columns from `?cols=`, else the first four metrics. */
export function pivotCols(ctx: Pick<MatrixCtx, 'sp' | 'metrics'>): string[] {
  const fromUrl = (ctx.sp.get('cols') ?? '').split(',').filter((s) => ctx.metrics.some((m) => m.slug === s))
  return (fromUrl.length ? fromUrl : ctx.metrics.slice(0, 4).map((m) => m.slug)).slice(0, MAX_COLS)
}

/** Header click: sort by that key; the same key again flips the direction. */
export function nextSort(ctx: MatrixCtx, active: string, key: string) {
  ctx.setMany({
    sort: key,
    dir: active === key && ctx.sortDir === 'desc' ? 'asc' : 'desc',
  })
}

export default function PivotSection({ ctx }: { ctx: MatrixCtx }) {
  const cols = pivotCols(ctx)
  const group = ctx.sp.get('group') === 'region' ? 'region' : 'none'
  const activeSort = ctx.sortKey || cols[0] || ''
  const sorted = useMemo(() => sortByKey(ctx.rows, activeSort, ctx.sortDir), [ctx.rows, activeSort, ctx.sortDir])
  const groups = useMemo(
    () =>
      group === 'none'
        ? [{ id: 'all', label: null as string | null, items: sorted }]
        : (Object.keys(CENSUS_REGION_LABEL) as CensusRegionId[])
            .map((id) => ({
              id: id as string,
              label: CENSUS_REGION_LABEL[id] as string | null,
              items: sorted.filter((r) => r.region === id),
            }))
            .filter((g) => g.items.length),
    [sorted, group],
  )
  const toggleCol = (slug: string) => {
    if (cols.length === 1 && cols[0] === slug) return
    const next = cols.includes(slug) ? cols.filter((c) => c !== slug) : [...cols, slug].slice(0, MAX_COLS)
    ctx.setQP('cols', next.join(','))
  }
  let lit = 0
  let total = 0
  for (const r of ctx.rows)
    for (const c of cols) {
      const t = ctx.shade[c]?.(r.vals[c] ?? null) ?? null
      if (r.vals[c] != null) total += 1
      if (t != null && t * 100 >= ctx.minPct) lit += 1
    }
  const noun = cols.length === 1 ? 'metric' : 'metrics'
  // The Share column belongs to the selected metric when it is a count; a rate has no total to take a share of.
  const shareSlug = ctx.countMetrics.some((m) => m.slug === ctx.metricSlug) ? ctx.metricSlug : null
  const isCount = (slug: string) => ctx.countMetrics.some((m) => m.slug === slug)
  const share = useMemo(() => {
    if (!shareSlug) return null
    const vals = ctx.rows.map((r) => r.vals[shareSlug]).filter((v): v is number => v != null)
    const total = vals.reduce((a, v) => a + v, 0)
    return vals.length && total > 0 ? { slug: shareSlug, total, maxPct: (Math.max(...vals) / total) * 100 } : null
  }, [ctx.rows, shareSlug])
  const showTotal = !!share || cols.some(isCount)
  return (
    <SectionShell
      ctx={ctx}
      id="pivot"
      headline={[`${cols.length} ${noun} by state,`, `${ctx.rows.length} rows,`, ctx.vintage]}
      text={
        <>
          <p>
            A sortable breakdown: one row per geography, one column per chosen metric, each column shaded on its own scale. Click a column header to sort by it
            (again to reverse); the rows glide to their new places. Sorting here also orders the Heatmap and Table.
          </p>
          <p>
            {share
              ? `The Share column is each row's part of the ${ctx.labelOf(share.slug)} total across all ${ctx.rows.length} rows. `
              : `Share needs a count metric; ${ctx.metricLabel} is not one, so there is no Share column. `}
            The Total row adds up count columns only; a rate has no total, so it reads “—”.
          </p>
          <p>
            Showing {cols.map((c) => ctx.labelOf(c)).join(', ')}. Sorted by {activeSort === 'name' ? 'name' : ctx.labelOf(activeSort)},{' '}
            {ctx.sortDir === 'asc' ? 'lowest' : 'highest'} first.
          </p>
        </>
      }
      controls={
        <>
          <Seg label="Group rows by" value={group} onChange={(v) => ctx.setQP('group', v === 'none' ? null : v)} options={GROUP_OPTIONS} />
          <details className="folio-field relative">
            <summary className="cursor-pointer select-none">
              Columns ({cols.length}/{MAX_COLS})
            </summary>
            <div className="folio-panel absolute z-10 mt-1 max-h-64 w-72 overflow-y-auto">
              {ctx.metrics.map((m) => (
                <label
                  key={m.slug}
                  className="flex items-center gap-1.5 py-0.5"
                  style={{
                    fontFamily: 'var(--font-sans)',
                    color: 'var(--ink)',
                  }}
                >
                  <input
                    type="checkbox"
                    checked={cols.includes(m.slug)}
                    disabled={cols.length === 1 && cols[0] === m.slug}
                    onChange={() => toggleCol(m.slug)}
                    style={{ accentColor: 'var(--violet-ink)' }}
                  />
                  {m.label}
                </label>
              ))}
            </div>
          </details>
        </>
      }
      caption={
        <>
          {cols.length} {noun} by state, each column shaded on its own scale; {ctx.vintage} ACS 5-year. Source: ACS 5-year, {ctx.vintage}.
        </>
      }
      table={() => ({
        columns: [
          { label: 'Geography' },
          ...cols.map((c) => ({ label: ctx.labelOf(c), numeric: true })),
          ...(share
            ? [
                {
                  label: `Share of ${ctx.labelOf(share.slug)} total`,
                  numeric: true,
                },
              ]
            : []),
        ],
        rows: groups.flatMap((g) =>
          g.items.map((r) => [
            r.name,
            ...cols.map((c) => ctx.fmt(c, r.vals[c] ?? null)),
            ...(share ? [sharePct(r.vals[share.slug] ?? null, share.total) ?? '—'] : []),
          ]),
        ),
      })}
    >
      {ctx.rows.length === 0 ? (
        <Empty>No data available for {ctx.vintage}.</Empty>
      ) : (
        <>
          <ScaleLegend ctx={ctx} note="each column has its own scale" lit={`${lit} of ${total} cells highlighted`} />
          <div className="folio-chart">
            {groups.map((g) => (
              <div key={g.id} className="mb-3">
                {g.label && (
                  <h3 className="folio-group-label">
                    {g.label} · {g.items.length}
                  </h3>
                )}
                <PivotTable ctx={ctx} items={g.items} cols={cols} activeSort={activeSort} share={share} showTotal={showTotal} isCount={isCount} />
              </div>
            ))}
          </div>
        </>
      )}
    </SectionShell>
  )
}

const sharePct = (v: number | null, total: number): string | null => (v == null ? null : `${((v / total) * 100).toFixed(1)} %`)

interface ShareModel {
  slug: string
  total: number
  maxPct: number
}

function PivotTable({
  ctx,
  items,
  cols,
  activeSort,
  share,
  showTotal,
  isCount,
}: {
  ctx: MatrixCtx
  items: MatrixCtx['rows']
  cols: string[]
  activeSort: string
  share: ShareModel | null
  showTotal: boolean
  isCount: (slug: string) => boolean
}) {
  const { seen } = useSection()
  const ref = useRef<HTMLTableSectionElement>(null)
  const intro = useIntro(INTRO_MS, ctx.reduced, seen)
  useFlip(ref, `${items.map((r) => r.fips).join(',')}|${cols.join(',')}`, !ctx.reduced && !intro)
  const { setHotFips } = ctx
  // A row that goes away while hovered must not leave Tiles dimmed.
  useEffect(() => () => setHotFips(null), [setHotFips])
  const sortFirst = (key: string) => nextSort(ctx, activeSort, key)
  const sum = (slug: string): number | null => {
    const xs = items.map((r) => r.vals[slug]).filter((v): v is number => v != null)
    return xs.length ? xs.reduce((a, v) => a + v, 0) : null
  }
  const totalShare = share ? sum(share.slug) : null
  return (
    <div className="folio-heat-scroll">
      <table className="folio-table folio-dtable">
        <thead>
          <tr>
            <SortTh label="State" active={activeSort === 'name'} dir={ctx.sortDir} onSort={() => sortFirst('name')} className="folio-sticky" />
            {cols.map((c) => (
              <SortTh key={c} label={ctx.labelOf(c)} numeric active={activeSort === c} dir={ctx.sortDir} onSort={() => sortFirst(c)} />
            ))}
            {share && (
              <SortTh
                label={`Share of ${ctx.labelOf(share.slug)}`}
                numeric
                active={activeSort === share.slug}
                dir={ctx.sortDir}
                onSort={() => sortFirst(share.slug)}
              />
            )}
          </tr>
        </thead>
        <tbody ref={ref}>
          {items.map((r, i) => {
            const sv = share ? (r.vals[share.slug] ?? null) : null
            const pct = share && sv != null ? (sv / share.total) * 100 : null
            return (
              <tr
                key={r.fips}
                data-flip={r.fips}
                className={intro ? 'folio-in' : undefined}
                style={intro ? delayVar(rowDelayMs(i, items.length, 30, 500)) : undefined}
                onPointerEnter={() => setHotFips(r.fips)}
                onPointerLeave={() => setHotFips(null)}
                onFocus={() => setHotFips(r.fips)}
                onBlur={() => setHotFips(null)}
              >
                <th scope="row" className="folio-sticky text-left">
                  <Link to={ctx.mapHref}>{r.name}</Link>
                </th>
                {cols.map((c) => {
                  const v = r.vals[c] ?? null
                  return (
                    <td key={c} className="text-right" style={cellStyle(ctx.theme, ctx.shade[c]?.(v) ?? null, ctx.minPct)}>
                      {ctx.fmt(c, v)}
                    </td>
                  )
                })}
                {share && (
                  <td className="text-right">
                    <InlineBar fraction={barFraction(pct, 0, share.maxPct)}>{pct == null ? '—' : `${pct.toFixed(1)} %`}</InlineBar>
                  </td>
                )}
              </tr>
            )
          })}
        </tbody>
        {showTotal && (
          <tfoot>
            <tr>
              <th scope="row" className="folio-sticky text-left">
                Total · {items.length}
              </th>
              {cols.map((c) => {
                const t = isCount(c) ? sum(c) : null
                return (
                  <td key={c} className="text-right">
                    {t == null ? '—' : ctx.fmt(c, t)}
                  </td>
                )
              })}
              {share && (
                <td className="text-right">
                  <span className="folio-ibar">
                    <span>{totalShare == null ? '—' : `${((totalShare / share.total) * 100).toFixed(1)} %`}</span>
                  </span>
                </td>
              )}
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  )
}
