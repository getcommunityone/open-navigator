import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { colorFromT, formatMetricValueDisplay, type CensusMetricFormatRow } from '../utils/censusMapTransforms'
import { censusMetricRankDirection } from '../utils/censusDataDictionary'
import { CENSUS_REGION_LABEL, censusRegionForStateFips, type CensusRegionId } from '../utils/censusRegions'
import { STATE_CODE_TO_NAME } from '../utils/stateMapping'
import { STATE_FIPS_TO_CODE } from '../utils/stateFips'
import { DATA_EXPLORER_MAP_BASE, mapPathUs } from '../utils/dataExplorerPaths'

type Metric = CensusMetricFormatRow & { label: string }
type Manifest = { vintage?: string; vintages?: string[]; metrics?: Metric[] }
type StatePayload = { values: Record<string, Record<string, number | null | undefined>> }

type Layout = 'tiles' | 'pivot' | 'dumbbell' | 'scatter' | 'diverging' | 'share'
type GroupBy = 'none' | 'region'

const MAX_COLS = 8
/** Discrete 6-step shade (like a printed heatmap legend) so cells compare at a glance. */
const BIN_EDGES = [0.1, 0.25, 0.45, 0.65, 0.8] // same bins as the Folio reference heatmap
const stepOf = (t: number | null): number | null => (t == null ? null : BIN_EDGES.filter((e) => t >= e).length)
const stepColor = (t: number | null): string => {
  const k = stepOf(t)
  return colorFromT(k == null ? null : [0.05, 0.175, 0.35, 0.55, 0.725, 0.9][k]!)
}
const stepText = (t: number | null): string => ((stepOf(t) ?? 0) >= 3 ? '#fff' : '#0f172a')

interface Row {
  fips: string
  code: string
  name: string
  region: CensusRegionId | null
  vals: Record<string, number | null>
}

const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null)

/** "Matrix map": every state as a box. Tiles = one metric shaded; Pivot = states × chosen metrics. */
export default function DataExplorerMatrixPage() {
  const [sp, setSp] = useSearchParams()
  const layoutQ = sp.get('layout')
  const layout: Layout = layoutQ === 'pivot' || layoutQ === 'dumbbell' || layoutQ === 'scatter' || layoutQ === 'diverging' || layoutQ === 'share' ? layoutQ : 'tiles'
  const groupBy: GroupBy = sp.get('group') === 'region' ? 'region' : 'none'
  const sortKey = sp.get('sort') ?? ''
  const minPct = Math.min(95, Math.max(0, Number(sp.get('min')) || 0))
  const sortDir = sp.get('dir') === 'asc' ? 'asc' : 'desc'

  const setQP = (k: string, v: string | null) => {
    const next = new URLSearchParams(sp)
    if (v == null || v === '') next.delete(k)
    else next.set(k, v)
    setSp(next, { replace: true })
  }

  const { data: manifest, isLoading: mLoading } = useQuery({
    queryKey: ['census-map-manifest'],
    queryFn: async (): Promise<Manifest> => {
      const r = await fetch('/data/census-map/manifest.json')
      if (!r.ok) throw new Error('manifest')
      return r.json()
    },
    retry: false,
  })
  const vintage = sp.get('vintage') || manifest?.vintage || ''
  const { data: payload, isLoading: pLoading } = useQuery({
    queryKey: ['census-state-metrics', vintage || manifest?.vintage],
    queryFn: async (): Promise<StatePayload | null> => {
      const r = await fetch(`/data/census-map/${vintage}/state_metrics.json`)
      if (!r.ok) return null
      return r.json()
    },
    enabled: !!manifest && !!vintage,
    retry: false,
  })

  const vintageList = manifest?.vintages ?? []
  const baseVintage = vintageList.length > 1 ? vintageList[0]! : ''
  const { data: basePayload } = useQuery({
    queryKey: ['census-state-metrics', baseVintage],
    queryFn: async (): Promise<StatePayload | null> => {
      const r = await fetch(`/data/census-map/${baseVintage}/state_metrics.json`)
      return r.ok ? r.json() : null
    },
    enabled: layout === 'dumbbell' && !!baseVintage,
    retry: false,
  })

  const metrics = manifest?.metrics ?? []
  const countMetrics = metrics.filter((m) => m.format === 'count')
  const metricQ = sp.get('metric') || metrics[0]?.slug || ''
  // Part-of-whole only makes sense for additive (count) metrics.
  const metricSlug = layout === 'share' && !countMetrics.some((m) => m.slug === metricQ) ? countMetrics[0]?.slug ?? metricQ : metricQ
  const partScope: 'state' | 'county' = sp.get('part') === 'county' ? 'county' : 'state'
  const partState = sp.get('st') || '01'
  const { data: countyPayload } = useQuery({
    queryKey: ['census-county-metrics', vintage],
    queryFn: async (): Promise<{ values: Record<string, Record<string, number | string | null | undefined>> } | null> => {
      const r = await fetch(`/data/census-map/${vintage}/county_metrics.json`)
      return r.ok ? r.json() : null
    },
    enabled: layout === 'share' && partScope === 'county' && !!vintage,
    retry: false,
    staleTime: 1000 * 60 * 60,
  })
  const cols = useMemo(() => {
    const fromUrl = (sp.get('cols') ?? '').split(',').filter((s) => metrics.some((m) => m.slug === s))
    return (fromUrl.length ? fromUrl : metrics.slice(0, 4).map((m) => m.slug)).slice(0, MAX_COLS)
  }, [sp, metrics])

  const rows: Row[] = useMemo(() => {
    const values = payload?.values ?? {}
    return Object.entries(values)
      .map(([fips, v]) => {
        const code = STATE_FIPS_TO_CODE[fips.padStart(2, '0')] ?? ''
        return {
          fips,
          code,
          name: STATE_CODE_TO_NAME[code] ?? code ?? fips,
          region: censusRegionForStateFips(fips),
          vals: Object.fromEntries(Object.entries(v ?? {}).map(([k, x]) => [k, num(x)])),
        }
      })
      .filter((r) => r.code)
  }, [payload])

  /** Per-metric min/max → shade 0..1 (flipped when lower is better so darker always means "better"). */
  const shade = useMemo(() => {
    const out: Record<string, (v: number | null) => number | null> = {}
    for (const m of metrics) {
      const xs = rows.map((r) => r.vals[m.slug]).filter((x): x is number => x != null)
      if (!xs.length) continue
      const lo = Math.min(...xs)
      const hi = Math.max(...xs)
      const flip = censusMetricRankDirection(m.slug) === 'lower'
      out[m.slug] = (v) => (v == null || hi === lo ? null : flip ? 1 - (v - lo) / (hi - lo) : (v - lo) / (hi - lo))
    }
    return out
  }, [rows, metrics])

  const activeSort = layout === 'tiles' ? metricSlug : sortKey || cols[0] || ''
  const sorted = useMemo(() => {
    const dir = sortDir === 'asc' ? 1 : -1
    return [...rows].sort((a, b) => {
      if (activeSort === 'name') return a.name.localeCompare(b.name) * dir
      const av = a.vals[activeSort]
      const bv = b.vals[activeSort]
      if (av == null && bv == null) return a.name.localeCompare(b.name)
      if (av == null) return 1
      if (bv == null) return -1
      return (av - bv) * dir
    })
  }, [rows, activeSort, sortDir])

  const groups = useMemo(() => {
    if (groupBy === 'none' || layout === 'share') return [{ label: null as string | null, items: sorted }]
    return (Object.keys(CENSUS_REGION_LABEL) as CensusRegionId[]).map((id) => ({
      label: CENSUS_REGION_LABEL[id],
      items: sorted.filter((r) => r.region === id),
    }))
  }, [sorted, groupBy, layout])

  const dim = (t: number | null) => (minPct > 0 && (t == null || t * 100 < minPct) ? 0.25 : 1)
  const fmt = (slug: string, v: number | null) => formatMetricValueDisplay(slug, v, metrics)
  const metricLabel = (slug: string) => metrics.find((m) => m.slug === slug)?.label ?? slug
  const mapHref = (_r: Row) => mapPathUs(DATA_EXPLORER_MAP_BASE, vintage, layout === "tiles" ? metricSlug : cols[0] ?? metricSlug)

  const toggleCol = (slug: string) => {
    const next = cols.includes(slug) ? cols.filter((c) => c !== slug) : [...cols, slug].slice(0, MAX_COLS)
    setQP('cols', next.join(','))
  }
  const clickHeader = (key: string) => {
    const next = new URLSearchParams(sp)
    next.set('sort', key)
    next.set('dir', activeSort === key && sortDir === 'desc' ? 'asc' : 'desc')
    setSp(next, { replace: true })
  }

  const btn = (on: boolean) =>
    `px-2.5 py-1 text-xs font-medium ${on ? 'bg-[#354F52] text-white' : 'bg-white text-slate-700 hover:bg-slate-50'}`

  if (mLoading || pLoading) return <p className="p-4 text-sm text-slate-600">Loading matrix…</p>
  if (!manifest || !payload || rows.length === 0 || metrics.length === 0) {
    return (
      <p className="rounded-lg bg-white p-4 text-sm text-slate-700" role="status">
        No data available — the ACS state bundle for this vintage hasn’t been published yet.
      </p>
    )
  }

  const cellMetrics = layout === 'tiles' ? [metricSlug] : cols
  let litCount = 0
  let totalCells = 0
  for (const r of rows) {
    for (const c of cellMetrics) {
      const t = shade[c]?.(r.vals[c] ?? null) ?? null
      if (r.vals[c] != null) totalCells += 1
      if (t != null && t * 100 >= minPct) litCount += 1
    }
  }
  const scopeLabel = `All states · ${vintage} ACS 5-year`

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-slate-300 bg-white px-3 py-2">
        <h2 className="text-sm font-semibold text-slate-900">
          Matrix map <span className="font-normal text-slate-600">· {scopeLabel}</span>
        </h2>
        <div className="inline-flex overflow-hidden rounded-md border border-slate-300" role="group" aria-label="Layout">
          <button type="button" className={btn(layout === 'tiles')} onClick={() => setQP('layout', null)}>
            ▦ Tiles
          </button>
          <button type="button" className={btn(layout === 'pivot')} onClick={() => setQP('layout', 'pivot')}>
            ▤ Pivot
          </button>
          <button type="button" className={btn(layout === 'dumbbell')} onClick={() => setQP('layout', 'dumbbell')}>
            ◐ Compare
          </button>
          <button type="button" className={btn(layout === 'scatter')} onClick={() => setQP('layout', 'scatter')}>
            ⁘ Scatter
          </button>
          <button type="button" className={btn(layout === 'diverging')} onClick={() => setQP('layout', 'diverging')}>
            ⇋ Diverging
          </button>
          <button type="button" className={btn(layout === 'share')} onClick={() => setQP('layout', 'share')}>
            ◔ Share
          </button>
        </div>
        <div className="inline-flex overflow-hidden rounded-md border border-slate-300" role="group" aria-label="Group by">
          <button type="button" className={btn(groupBy === 'none')} onClick={() => setQP('group', null)}>
            Flat
          </button>
          <button type="button" className={btn(groupBy === 'region')} onClick={() => setQP('group', 'region')}>
            By region
          </button>
        </div>
        {layout !== 'pivot' ? (
          <label className="text-xs text-slate-700">
            Metric{' '}
            <select
              className="rounded border border-slate-300 px-1.5 py-1 text-xs"
              value={metricSlug}
              onChange={(e) => setQP('metric', e.target.value)}
            >
              {(layout === 'share' ? countMetrics : metrics).map((m) => (
                <option key={m.slug} value={m.slug}>
                  {m.label}
                </option>
              ))}
            </select>
          </label>
        ) : (
          <details className="text-xs text-slate-700">
            <summary className="cursor-pointer select-none">
              Columns ({cols.length}/{MAX_COLS})
            </summary>
            <div className="absolute z-10 mt-1 max-h-64 w-72 overflow-y-auto rounded-md border border-slate-300 bg-white p-2 shadow-lg">
              {metrics.map((m) => (
                <label key={m.slug} className="flex items-center gap-1.5 py-0.5">
                  <input type="checkbox" checked={cols.includes(m.slug)} onChange={() => toggleCol(m.slug)} />
                  {m.label}
                </label>
              ))}
            </div>
          </details>
        )}
        {layout === 'share' && (
          <>
            <div className="inline-flex overflow-hidden rounded-md border border-slate-300" role="group" aria-label="Whole">
              <button type="button" className={btn(partScope === 'state')} onClick={() => setQP('part', null)}>
                States of U.S.
              </button>
              <button type="button" className={btn(partScope === 'county')} onClick={() => setQP('part', 'county')}>
                Counties of a state
              </button>
            </div>
            {partScope === 'county' && (
              <select
                aria-label="State"
                className="rounded border border-slate-300 px-1.5 py-1 text-xs"
                value={partState}
                onChange={(e) => setQP('st', e.target.value)}
              >
                {[...rows].sort((a, b) => a.name.localeCompare(b.name)).map((r) => (
                  <option key={r.fips} value={r.fips}>
                    {r.name}
                  </option>
                ))}
              </select>
            )}
          </>
        )}
        {layout === 'scatter' && (
          <label className="text-xs text-slate-700">
            vs{' '}
            <select
              className="rounded border border-slate-300 px-1.5 py-1 text-xs"
              value={sp.get('y') || metrics.find((m) => m.slug !== metricSlug)?.slug || ''}
              onChange={(e) => setQP('y', e.target.value)}
            >
              {metrics.map((m) => (
                <option key={m.slug} value={m.slug}>
                  {m.label}
                </option>
              ))}
            </select>
          </label>
        )}
        <p className="text-[11px] text-slate-500">Darker = better rank for the metric (neutral metrics: larger).</p>
      </div>

      {(layout === 'tiles' || layout === 'pivot') && (
        <div className="flex flex-wrap items-center gap-1.5 px-1 text-[11px] text-slate-600" aria-label="Scale">
          <span className="font-semibold uppercase tracking-wide">Scale</span>
          {['Lowest', '', '', '', '', 'Highest'].map((l, i) => (
            <span key={i} className="inline-flex items-center gap-1">
              <span className="inline-block h-3 w-5 rounded-sm border border-slate-300" style={{ background: stepColor([0.05, 0.175, 0.35, 0.55, 0.725, 0.9][i]!) }} />
              {l}
            </span>
          ))}
          <span>(per column · darker = better rank)</span>
          <label className="ml-2 inline-flex items-center gap-1">
            Highlight ≥ {minPct}% of range
            <input type="range" min={0} max={95} step={5} value={minPct} onChange={(e) => setQP('min', e.target.value === '0' ? null : e.target.value)} />
          </label>
          {minPct > 0 && <span aria-live="polite">{litCount} of {totalCells} cells highlighted</span>}
        </div>
      )}
      <div className="overflow-auto rounded-lg border border-slate-300 bg-white p-2">
        {groups.map((g) => (
          <section key={g.label ?? 'all'} className="mb-3">
            {g.label && <h3 className="mb-1 text-xs font-semibold text-slate-700">{g.label}</h3>}
            {layout === 'share' ? (
              <Share
                slug={metricSlug}
                label={metricLabel(metricSlug)}
                fmt={fmt}
                scope={partScope}
                states={rows}
                stateName={rows.find((r) => r.fips === partState)?.name ?? partState}
                stateFips={partState}
                counties={countyPayload?.values}
                countsAvailable={countMetrics.length > 0}
              />
            ) : layout === 'scatter' ? (
              <Scatter
                items={g.items}
                xSlug={metricSlug}
                ySlug={sp.get('y') || metrics.find((m) => m.slug !== metricSlug)?.slug || ''}
                label={metricLabel}
                fmt={fmt}
                href={mapHref}
              />
            ) : layout === 'diverging' ? (
              <Diverging allItems={rows} items={g.items} slug={metricSlug} fmt={fmt} />
            ) : layout === 'dumbbell' ? (
              <Dumbbell
                items={g.items}
                slug={metricSlug}
                base={basePayload?.values}
                baseLabel={baseVintage}
                curLabel={vintage}
                fmt={fmt}
              />
            ) : layout === 'tiles' ? (
              <ul className="grid grid-cols-[repeat(auto-fill,minmax(5.5rem,1fr))] gap-1.5">
                {g.items.map((r) => {
                  const v = r.vals[metricSlug] ?? null
                  const t = shade[metricSlug]?.(v) ?? null
                  return (
                    <li key={r.fips}>
                      <Link
                        to={mapHref(r)}
                        title={`${r.name}: ${fmt(metricSlug, v)} — ${metricLabel(metricSlug)}`}
                        className="flex h-16 flex-col justify-between rounded-md border border-slate-300 p-1.5 text-[11px] leading-tight hover:ring-2 hover:ring-teal-600"
                        style={{ background: stepColor(t), color: stepText(t), opacity: dim(t) }}
                      >
                        <span className="font-semibold">{r.code}</span>
                        <span className="tabular-nums">{fmt(metricSlug, v)}</span>
                      </Link>
                    </li>
                  )
                })}
              </ul>
            ) : (
              <table className="w-full border-collapse text-xs">
                <thead>
                  <tr>
                    <th className="sticky left-0 bg-white p-1 text-left">
                      <button type="button" onClick={() => clickHeader('name')}>
                        State{activeSort === 'name' ? (sortDir === 'asc' ? ' ▲' : ' ▼') : ''}
                      </button>
                    </th>
                    {cols.map((c) => (
                      <th key={c} className="p-1 text-right align-bottom">
                        <button type="button" onClick={() => clickHeader(c)}>
                          {metricLabel(c)}
                          {activeSort === c ? (sortDir === 'asc' ? ' ▲' : ' ▼') : ''}
                        </button>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {g.items.map((r) => (
                    <tr key={r.fips} className="border-t border-slate-200">
                      <td className="sticky left-0 bg-white p-1 font-medium">
                        <Link className="text-teal-800 hover:underline" to={mapHref(r)}>
                          {r.name}
                        </Link>
                      </td>
                      {cols.map((c) => {
                        const v = r.vals[c] ?? null
                        const t = shade[c]?.(v) ?? null
                        return (
                          <td
                            key={c}
                            className="p-1 text-right tabular-nums"
                            style={{ background: stepColor(t), color: stepText(t), opacity: dim(t) }}
                          >
                            {fmt(c, v)}
                          </td>
                        )
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        ))}
      </div>
    </div>
  )
}

/** Dumbbell: earliest vs latest published vintage per state; sorted by the page sort (value) order. */
function Dumbbell({
  items,
  slug,
  base,
  baseLabel,
  curLabel,
  fmt,
}: {
  items: Row[]
  slug: string
  base: Record<string, Record<string, number | null | undefined>> | undefined
  baseLabel: string
  curLabel: string
  fmt: (slug: string, v: number | null) => string
}) {
  if (!base || !baseLabel) {
    return <p className="p-2 text-xs text-slate-600">No data available — only one vintage is published, so there is nothing to compare.</p>
  }
  const pts = items.map((r) => {
    const b = base[r.fips]?.[slug]
    return { r, a: typeof b === 'number' && Number.isFinite(b) ? b : null, c: r.vals[slug] ?? null }
  })
  const all = pts.flatMap((p) => [p.a, p.c]).filter((x): x is number => x != null)
  if (!all.length) return <p className="p-2 text-xs text-slate-600">No data available for this metric.</p>
  const lo = Math.min(...all)
  const hi = Math.max(...all)
  const x = (v: number) => (hi === lo ? 50 : ((v - lo) / (hi - lo)) * 100)
  return (
    <div>
      <p className="mb-1 text-[11px] text-slate-600">
        <span className="inline-block h-2 w-2 rounded-full bg-slate-400" /> {baseLabel}{' '}
        <span className="ml-2 inline-block h-2 w-2 rounded-full bg-teal-700" /> {curLabel}
      </p>
      <ul className="space-y-0.5">
        {pts.map(({ r, a, c }) => (
          <li key={r.fips} className="grid grid-cols-[7rem_1fr_9rem] items-center gap-2 text-[11px]">
            <span className="truncate font-medium">{r.name}</span>
            <span className="relative h-4">
              <span className="absolute inset-x-0 top-1/2 h-px bg-slate-200" />
              {a != null && c != null && (
                <span className="absolute top-1/2 h-0.5 bg-slate-400" style={{ left: `${Math.min(x(a), x(c))}%`, width: `${Math.abs(x(c) - x(a))}%` }} />
              )}
              {a != null && <span className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-slate-400" style={{ left: `${x(a)}%` }} />}
              {c != null && <span className="absolute top-1/2 h-2.5 w-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full bg-teal-700" style={{ left: `${x(c)}%` }} />}
            </span>
            <span className="tabular-nums text-slate-700">
              {fmt(slug, a)} → {fmt(slug, c)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

const REGION_COLOR: Record<string, string> = { NE: '#354F52', MW: '#b45309', S: '#be123c', W: '#4338ca' }

/** Scatter of two metrics across states, coloured by Census region, with a live OLS line, slope and r². */
function Scatter({
  items,
  xSlug,
  ySlug,
  label,
  fmt,
  href,
}: {
  items: Row[]
  xSlug: string
  ySlug: string
  label: (slug: string) => string
  fmt: (slug: string, v: number | null) => string
  href: (r: Row) => string
}) {
  const [hidden, setHidden] = useState<Set<string>>(new Set())
  const [trend, setTrend] = useState(true)
  const pts = items
    .map((r) => ({ r, x: r.vals[xSlug] ?? null, y: r.vals[ySlug] ?? null }))
    .filter((p): p is { r: Row; x: number; y: number } => p.x != null && p.y != null)
  if (!ySlug || pts.length < 3) return <p className="p-2 text-xs text-slate-600">No data available — need at least 3 states with both metrics.</p>
  const vis = pts.filter((p) => !hidden.has(p.r.region ?? ''))
  const W = 640
  const H = 360
  const pad = { l: 56, r: 12, t: 12, b: 40 }
  const xs = pts.map((p) => p.x)
  const ys = pts.map((p) => p.y)
  const [x0, x1] = [Math.min(...xs), Math.max(...xs)]
  const [y0, y1] = [Math.min(...ys), Math.max(...ys)]
  const sx = (v: number) => pad.l + (x1 === x0 ? 0.5 : (v - x0) / (x1 - x0)) * (W - pad.l - pad.r)
  const sy = (v: number) => H - pad.b - (y1 === y0 ? 0.5 : (v - y0) / (y1 - y0)) * (H - pad.t - pad.b)
  let slope = 0
  let icpt = 0
  let r2 = 0
  if (vis.length >= 3) {
    const n = vis.length
    const mx = vis.reduce((a, p) => a + p.x, 0) / n
    const my = vis.reduce((a, p) => a + p.y, 0) / n
    const sxx = vis.reduce((a, p) => a + (p.x - mx) ** 2, 0)
    const sxy = vis.reduce((a, p) => a + (p.x - mx) * (p.y - my), 0)
    const syy = vis.reduce((a, p) => a + (p.y - my) ** 2, 0)
    slope = sxx ? sxy / sxx : 0
    icpt = my - slope * mx
    r2 = sxx && syy ? (sxy * sxy) / (sxx * syy) : 0
  }
  return (
    <div>
      <div className="mb-1 flex flex-wrap items-center gap-2 text-[11px]">
        {(Object.keys(CENSUS_REGION_LABEL) as CensusRegionId[]).map((id) => (
          <button
            key={id}
            type="button"
            aria-pressed={!hidden.has(id)}
            className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 ${hidden.has(id) ? 'opacity-40' : ''}`}
            onClick={() => {
              const n = new Set(hidden)
              if (n.has(id)) n.delete(id)
              else n.add(id)
              setHidden(n)
            }}
          >
            <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: REGION_COLOR[id] }} />
            {CENSUS_REGION_LABEL[id]}
          </button>
        ))}
        <label className="inline-flex items-center gap-1">
          <input type="checkbox" checked={trend} onChange={(e) => setTrend(e.target.checked)} /> Trend line
        </label>
        {trend && vis.length >= 3 && (
          <span className="text-slate-600">
            slope {slope.toPrecision(3)} · r² {r2.toFixed(2)} · n={vis.length}
          </span>
        )}
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label={`${label(ySlug)} versus ${label(xSlug)} by state`}>
        <line x1={pad.l} x2={W - pad.r} y1={H - pad.b} y2={H - pad.b} stroke="#94a3b8" />
        <line x1={pad.l} x2={pad.l} y1={pad.t} y2={H - pad.b} stroke="#94a3b8" />
        <text x={(W + pad.l) / 2} y={H - 6} textAnchor="middle" fontSize="11" fill="#475569">
          {label(xSlug)} ({fmt(xSlug, x0)} – {fmt(xSlug, x1)})
        </text>
        <text transform={`translate(12 ${(H - pad.b) / 2}) rotate(-90)`} textAnchor="middle" fontSize="11" fill="#475569">
          {label(ySlug)} ({fmt(ySlug, y0)} – {fmt(ySlug, y1)})
        </text>
        {trend && vis.length >= 3 && (
          <line x1={sx(x0)} x2={sx(x1)} y1={sy(slope * x0 + icpt)} y2={sy(slope * x1 + icpt)} stroke="#0f172a" strokeDasharray="5 4" strokeWidth="1.5" />
        )}
        {vis.map((p) => (
          <a key={p.r.fips} href={href(p.r)}>
            <circle cx={sx(p.x)} cy={sy(p.y)} r="5" fill={REGION_COLOR[p.r.region ?? ''] ?? '#64748b'} fillOpacity="0.8">
              <title>{`${p.r.name}: ${fmt(xSlug, p.x)} / ${fmt(ySlug, p.y)}`}</title>
            </circle>
          </a>
        ))}
      </svg>
    </div>
  )
}

/** Diverging bars: each state's distance from the median state for one metric (computed from the same bundle). */
function Diverging({
  allItems,
  items,
  slug,
  fmt,
}: {
  allItems: Row[]
  items: Row[]
  slug: string
  fmt: (slug: string, v: number | null) => string
}) {
  const vals = allItems.map((r) => r.vals[slug]).filter((x): x is number => x != null).sort((a, b) => a - b)
  if (vals.length < 3) return <p className="p-2 text-xs text-slate-600">No data available for this metric.</p>
  const med = vals[Math.floor(vals.length / 2)]!
  const dev = items.map((r) => ({ r, d: r.vals[slug] != null ? r.vals[slug]! - med : null }))
  const maxAbs = Math.max(...dev.map((x) => Math.abs(x.d ?? 0))) || 1
  return (
    <div>
      <p className="mb-1 text-[11px] text-slate-600">Difference from the median state ({fmt(slug, med)}). Right = above median, left = below.</p>
      <ul className="space-y-0.5">
        {dev.map(({ r, d }) => (
          <li key={r.fips} className="grid grid-cols-[7rem_1fr_6rem] items-center gap-2 text-[11px]">
            <span className="truncate font-medium">{r.name}</span>
            <span className="relative h-3.5 border-x border-slate-200">
              <span className="absolute inset-y-0 left-1/2 w-px bg-slate-400" />
              {d != null && (
                <span
                  className="absolute inset-y-0.5"
                  style={{
                    background: d >= 0 ? '#354F52' : '#be123c',
                    left: d >= 0 ? '50%' : `${50 - (Math.abs(d) / maxAbs) * 50}%`,
                    width: `${(Math.abs(d) / maxAbs) * 50}%`,
                  }}
                />
              )}
            </span>
            <span className="tabular-nums text-slate-700">{fmt(slug, r.vals[slug] ?? null)}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}

const SEG_COLORS = ['#354F52', '#4338ca', '#b45309', '#be123c', '#0f766e', '#7c3aed', '#a16207', '#0369a1', '#94a3b8']

interface Part {
  id: string
  name: string
  value: number
}

/** Part-of-whole: states of the U.S. total, or counties of one state. Additive (count) metrics only. */
function Share({
  slug,
  label,
  fmt,
  scope,
  states,
  stateName,
  stateFips,
  counties,
  countsAvailable,
}: {
  slug: string
  label: string
  fmt: (slug: string, v: number | null) => string
  scope: 'state' | 'county'
  states: Row[]
  stateName: string
  stateFips: string
  counties: Record<string, Record<string, number | string | null | undefined>> | undefined
  countsAvailable: boolean
}) {
  if (!countsAvailable) return <p className="p-2 text-xs text-slate-600">No data available — no additive (count) metrics are published.</p>
  let parts: Part[] = []
  if (scope === 'state') {
    // ACS "United States" excludes Puerto Rico, so it is left out of the whole.
    parts = states
      .filter((r) => r.fips.padStart(2, '0') !== '72' && r.vals[slug] != null)
      .map((r) => ({ id: r.fips, name: r.name, value: r.vals[slug] as number }))
  } else if (counties) {
    const pre = stateFips.padStart(2, '0')
    parts = Object.entries(counties)
      .filter(([gid, v]) => gid.startsWith(pre) && typeof v[slug] === 'number')
      .map(([gid, v]) => ({ id: gid, name: typeof v.NAME === 'string' ? v.NAME.replace(/,.*$/, '') : gid, value: v[slug] as number }))
  } else {
    return <p className="p-2 text-xs text-slate-600" role="status">No data available — county_metrics.json for this vintage is not published.</p>
  }
  parts = parts.filter((p) => p.value > 0).sort((a, b) => b.value - a.value)
  const total = parts.reduce((a, p) => a + p.value, 0)
  if (!parts.length || total <= 0) return <p className="p-2 text-xs text-slate-600">No data available for this metric.</p>
  const whole = scope === 'state' ? 'U.S. total (50 states + DC)' : stateName
  const TOP = 8
  const head = parts.slice(0, TOP)
  const restVal = parts.slice(TOP).reduce((a, p) => a + p.value, 0)
  const segs = restVal > 0 ? [...head, { id: 'rest', name: `All others (${parts.length - TOP})`, value: restVal }] : head
  // Waffle: largest-remainder allocation of 100 cells.
  const raw = segs.map((g) => (g.value / total) * 100)
  const cells = raw.map(Math.floor)
  let left = 100 - cells.reduce((a, c) => a + c, 0)
  raw
    .map((r, i) => ({ i, f: r - Math.floor(r) }))
    .sort((a, b) => b.f - a.f)
    .forEach(({ i }) => {
      if (left > 0) {
        cells[i]! += 1
        left -= 1
      }
    })
  const waffle = cells.flatMap((n, i) => Array<number>(n).fill(i))
  const pct = (v: number) => `${((v / total) * 100).toFixed(1)}%`
  return (
    <div>
      <p className="mb-1 text-xs text-slate-700">
        <strong>{label}</strong> · share of {whole} · whole = {fmt(slug, total)} ({parts.length} {scope === 'state' ? 'states' : 'counties'} with data)
      </p>
      <div className="flex h-7 w-full overflow-hidden rounded border border-slate-300" role="img" aria-label={`Share of ${whole}`}>
        {segs.map((g, i) => (
          <div key={g.id} style={{ width: `${(g.value / total) * 100}%`, background: SEG_COLORS[i] }} title={`${g.name}: ${pct(g.value)}`} />
        ))}
      </div>
      <div className="mt-3 flex flex-wrap gap-4">
        <div className="grid grid-cols-10 gap-0.5" role="img" aria-label="Waffle: each square is 1% of the whole" style={{ width: '9rem' }}>
          {waffle.map((si, k) => (
            <span key={k} className="aspect-square rounded-[2px]" style={{ background: SEG_COLORS[si] }} />
          ))}
        </div>
        <table className="min-w-[16rem] flex-1 border-collapse text-xs">
          <thead>
            <tr className="text-left text-slate-600">
              <th className="p-1">{scope === 'state' ? 'State' : 'County'}</th>
              <th className="p-1 text-right">{label}</th>
              <th className="p-1 text-right">Share</th>
            </tr>
          </thead>
          <tbody>
            {parts.map((p) => {
              const si = segs.findIndex((g) => g.id === p.id)
              return (
                <tr key={p.id} className="border-t border-slate-200">
                  <td className="p-1 font-medium">
                    <span className="mr-1.5 inline-block h-2.5 w-2.5 rounded-sm align-middle" style={{ background: SEG_COLORS[si >= 0 ? si : SEG_COLORS.length - 1] }} />
                    {p.name}
                  </td>
                  <td className="p-1 text-right tabular-nums">{fmt(slug, p.value)}</td>
                  <td className="p-1 text-right tabular-nums">{pct(p.value)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
