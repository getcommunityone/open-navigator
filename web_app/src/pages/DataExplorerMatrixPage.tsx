import { useMemo } from 'react'
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

type Layout = 'tiles' | 'pivot'
type GroupBy = 'none' | 'region'

const MAX_COLS = 8

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
  const layout: Layout = sp.get('layout') === 'pivot' ? 'pivot' : 'tiles'
  const groupBy: GroupBy = sp.get('group') === 'region' ? 'region' : 'none'
  const sortKey = sp.get('sort') ?? ''
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

  const metrics = manifest?.metrics ?? []
  const metricSlug = sp.get('metric') || metrics[0]?.slug || ''
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
    if (groupBy === 'none') return [{ label: null as string | null, items: sorted }]
    return (Object.keys(CENSUS_REGION_LABEL) as CensusRegionId[]).map((id) => ({
      label: CENSUS_REGION_LABEL[id],
      items: sorted.filter((r) => r.region === id),
    }))
  }, [sorted, groupBy])

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
        </div>
        <div className="inline-flex overflow-hidden rounded-md border border-slate-300" role="group" aria-label="Group by">
          <button type="button" className={btn(groupBy === 'none')} onClick={() => setQP('group', null)}>
            Flat
          </button>
          <button type="button" className={btn(groupBy === 'region')} onClick={() => setQP('group', 'region')}>
            By region
          </button>
        </div>
        {layout === 'tiles' ? (
          <label className="text-xs text-slate-700">
            Metric{' '}
            <select
              className="rounded border border-slate-300 px-1.5 py-1 text-xs"
              value={metricSlug}
              onChange={(e) => setQP('metric', e.target.value)}
            >
              {metrics.map((m) => (
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
        <p className="text-[11px] text-slate-500">Darker = better rank for the metric (neutral metrics: larger).</p>
      </div>

      <div className="overflow-auto rounded-lg border border-slate-300 bg-white p-2">
        {groups.map((g) => (
          <section key={g.label ?? 'all'} className="mb-3">
            {g.label && <h3 className="mb-1 text-xs font-semibold text-slate-700">{g.label}</h3>}
            {layout === 'tiles' ? (
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
                        style={{ background: colorFromT(t), color: t != null && t > 0.55 ? '#fff' : '#0f172a' }}
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
                            style={{ background: colorFromT(t), color: t != null && t > 0.55 ? '#fff' : '#0f172a' }}
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
