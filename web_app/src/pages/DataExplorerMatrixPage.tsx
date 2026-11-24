import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQueries, useQuery } from '@tanstack/react-query'
import '@fontsource-variable/geist'
import '@fontsource-variable/geist-mono'
import '../styles/folio.css'
import { formatMetricValueDisplay } from '../utils/censusMapTransforms'
import { censusMetricRankDirection } from '../utils/censusDataDictionary'
import { fetchStaticJson } from '../utils/fetchStaticJson'
import { shadeT } from '../utils/matrixMapMath'
import { DATA_EXPLORER_MAP_BASE, mapPathUs } from '../utils/dataExplorerPaths'
import { DEFAULT_THEME_ID, FOLIO_THEMES, themeById } from '../utils/folioThemes'
import { usePrefersReducedMotion } from '../hooks/usePrefersReducedMotion'
import { geoNounFor, rowsFromPayload, statsOf } from '../components/matrix/data'
import Kpi from '../components/matrix/Kpi'
import SectionBand from '../components/matrix/SectionBand'
import BarsSection from '../components/matrix/BarsSection'
import ColumnsSection from '../components/matrix/ColumnsSection'
import CompareSection from '../components/matrix/CompareSection'
import DivergingSection from '../components/matrix/DivergingSection'
import DotsSection from '../components/matrix/DotsSection'
import HeatmapSection from '../components/matrix/HeatmapSection'
import PivotSection from '../components/matrix/PivotSection'
import ScatterSection from '../components/matrix/ScatterSection'
import ShareSection from '../components/matrix/ShareSection'
import TableSection from '../components/matrix/TableSection'
import TilesSection from '../components/matrix/TilesSection'
import TrendSection from '../components/matrix/TrendSection'
import { SECTIONS, type Manifest, type MatrixCtx, type Row, type SectionId, type StatePayload } from '../components/matrix/types'

const isSection = (v: string | null): v is SectionId => SECTIONS.some((s) => s.id === v)

/**
 * "Matrix map": one scrolling, sectioned report over the census bundle (tiles, share, pivot, compare, bars, trend, columns,
 * heatmap, diverging, scatter, dot map, table). The shared controls (metric, vintage, theme) sit under the heading; each
 * section has its own text, figure, controls and data table. All state that shapes the data lives in the URL.
 */
export default function DataExplorerMatrixPage() {
  const [sp, setSp] = useSearchParams()
  const reduced = usePrefersReducedMotion()

  // The router applies URL changes after a render, so two quick changes could each start from the same old URL. Keep the
  // newest params in a ref: every change builds on the previous one, then replaces the URL (never adds history).
  const latest = useRef(sp)
  latest.current = sp
  const commit = useCallback(
    (mutate: (next: URLSearchParams) => void) => {
      const next = new URLSearchParams(latest.current)
      mutate(next)
      latest.current = next
      setSp(next, { replace: true })
    },
    [setSp],
  )
  const setMany = useCallback(
    (entries: Record<string, string | null>) =>
      commit((next) => {
        for (const [k, v] of Object.entries(entries)) {
          if (v == null || v === '') next.delete(k)
          else next.set(k, v)
        }
      }),
    [commit],
  )
  const setQP = useCallback((k: string, v: string | null) => setMany({ [k]: v }), [setMany])
  /** Change one param from its latest value (so rapid clicks never act on a stale URL). */
  const updateQP = useCallback(
    (k: string, fn: (prev: string | null) => string | null) =>
      commit((next) => {
        const v = fn(next.get(k))
        if (v == null || v === '') next.delete(k)
        else next.set(k, v)
      }),
    [commit],
  )
  const setManyRef = useRef(setMany)
  setManyRef.current = setMany

  const { data: manifest, isLoading: mLoading } = useQuery({
    queryKey: ['census-map-manifest'],
    queryFn: () => fetchStaticJson<Manifest>('/data/census-map/manifest.json'),
    retry: false,
  })
  const vintage = sp.get('vintage') || manifest?.vintage || ''
  const vintages = useMemo(() => {
    const list = new Set([...(manifest?.vintages ?? []), ...(manifest?.vintage ? [manifest.vintage] : []), ...(vintage ? [vintage] : [])])
    return [...list].sort()
  }, [manifest, vintage])
  const vq = useQueries({
    queries: vintages.map((v) => ({
      queryKey: ['census-state-metrics', v],
      queryFn: async (): Promise<StatePayload | null> => {
        const r = await fetch(`/data/census-map/${v}/state_metrics.json`)
        if (!r.ok) return null
        return r.json()
      },
      enabled: !!manifest,
      retry: false,
    })),
  })
  const sig = vq.map((q) => `${q.status}:${q.dataUpdatedAt}`).join('|')
  const rowsByVintage = useMemo(() => {
    const out: Record<string, Row[] | null | undefined> = {}
    vintages.forEach((v, i) => {
      const q = vq[i]
      out[v] = !q || q.isPending ? undefined : q.data ? rowsFromPayload(q.data) : null
    })
    return out
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sig, vintages.join(',')])
  const rows = useMemo(() => rowsByVintage[vintage] ?? [], [rowsByVintage, vintage])
  const pLoading = rowsByVintage[vintage] === undefined && !!manifest && !!vintage

  const metrics = useMemo(() => manifest?.metrics ?? [], [manifest])
  const countMetrics = useMemo(() => metrics.filter((m) => m.format === 'count'), [metrics])
  // An unknown ?metric= falls back to the first published metric instead of drawing empty charts.
  const metricParam = sp.get('metric')
  const metricSlug = (metricParam && metrics.some((m) => m.slug === metricParam) ? metricParam : metrics[0]?.slug) || ''
  const theme = themeById(sp.get('theme'))

  const shade = useMemo(() => {
    const out: MatrixCtx['shade'] = {}
    for (const m of metrics) {
      const xs = rows.map((r) => r.vals[m.slug]).filter((x): x is number => x != null)
      if (!xs.length) continue
      const lo = Math.min(...xs)
      const hi = Math.max(...xs)
      const flip = censusMetricRankDirection(m.slug) === 'lower'
      out[m.slug] = (v) => shadeT(v, lo, hi, flip)
    }
    return out
  }, [rows, metrics])

  const sortRaw = sp.get('sort') ?? ''
  const sortKey = sortRaw === 'name' || metrics.some((m) => m.slug === sortRaw) ? sortRaw : ''
  const ctx: MatrixCtx = {
    sp,
    setQP,
    updateQP,
    setMany,
    reduced,
    theme,
    metrics,
    countMetrics,
    metricSlug,
    metricLabel: metrics.find((m) => m.slug === metricSlug)?.label ?? metricSlug,
    vintage,
    vintages,
    rows,
    rowsByVintage,
    fmt: (slug, v) => formatMetricValueDisplay(slug, v, metrics),
    labelOf: (slug) => metrics.find((m) => m.slug === slug)?.label ?? slug,
    shade,
    mapHref: mapPathUs(DATA_EXPLORER_MAP_BASE, vintage, metricSlug),
    minPct: Math.min(95, Math.max(0, Number(sp.get('min')) || 0)),
    sortKey,
    sortRaw,
    sortDir: sp.get('dir') === 'asc' ? 'asc' : 'desc',
    geoNoun: geoNounFor(rows.length),
  }

  // Section in view (band + `layout` param), and the deep link on load.
  const layoutQ = sp.get('layout')
  const [active, setActive] = useState<SectionId>(isSection(layoutQ) ? layoutQ : 'tiles')
  const activeRef = useRef(active)
  activeRef.current = active
  const jumping = useRef(false)
  const jumpTimer = useRef<number | undefined>(undefined)
  const sectionsRef = useRef<HTMLDivElement>(null)
  // Deep-link scrolling and section tracking wait until every vintage file has settled, because Compare, Trend and
  // Columns change height as they load and would otherwise push the target out from under the scroll position.
  const settled = vintages.every((v) => rowsByVintage[v] !== undefined)
  const ready = !!manifest && !pLoading && rows.length > 0 && metrics.length > 0 && settled
  const hold = (ms: number) => {
    jumping.current = true
    window.clearTimeout(jumpTimer.current)
    jumpTimer.current = window.setTimeout(() => (jumping.current = false), ms)
  }
  const jump = (id: SectionId, smooth: boolean) => {
    setActive(id)
    setManyRef.current({ layout: id === 'tiles' ? null : id })
    hold(smooth && !reduced ? 1100 : 400)
    document.getElementById(id)?.scrollIntoView({ behavior: smooth && !reduced ? 'smooth' : 'auto', block: 'start' })
  }
  const deepLinked = useRef(false)
  useEffect(() => {
    if (!ready || deepLinked.current) return
    if (!isSection(layoutQ) || layoutQ === 'tiles') return
    // Land on the section, and keep it there while web fonts and charts settle (heights above it still change for a moment),
    // until the reader scrolls or the settling window ends.
    const align = () => document.getElementById(layoutQ)?.scrollIntoView({ behavior: 'auto', block: 'start' })
    hold(1800)
    let live = true
    const ro = typeof ResizeObserver !== 'undefined' && sectionsRef.current ? new ResizeObserver(() => live && align()) : null
    ro?.observe(sectionsRef.current!)
    void document.fonts?.ready.then(() => live && align())
    requestAnimationFrame(align)
    const stop = () => {
      live = false
      ro?.disconnect()
    }
    const finish = () => {
      stop()
      deepLinked.current = true // done: later vintage changes must not pull the page back to the section
    }
    const timer = window.setTimeout(finish, 1600)
    for (const ev of ['wheel', 'touchstart', 'keydown', 'pointerdown'] as const) window.addEventListener(ev, finish, { once: true })
    return () => {
      stop()
      window.clearTimeout(timer)
      for (const ev of ['wheel', 'touchstart', 'keydown', 'pointerdown'] as const) window.removeEventListener(ev, finish)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready])
  useEffect(() => {
    if (!ready || typeof IntersectionObserver === 'undefined') return
    const hit = new Set<SectionId>()
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          const id = e.target.id as SectionId
          if (e.isIntersecting) hit.add(id)
          else hit.delete(id)
        }
        if (jumping.current || !hit.size) return
        const idx = Math.max(...[...hit].map((id) => SECTIONS.findIndex((s) => s.id === id)))
        const id = SECTIONS[idx]!.id
        if (id !== activeRef.current) {
          activeRef.current = id
          setActive(id)
          setManyRef.current({ layout: id === 'tiles' ? null : id })
        }
      },
      { rootMargin: '-35% 0px -60% 0px', threshold: 0 },
    )
    SECTIONS.forEach((s) => {
      const el = document.getElementById(s.id)
      if (el) io.observe(el)
    })
    return () => io.disconnect()
  }, [ready])

  if (mLoading || pLoading) {
    return (
      <div className="folio" style={theme.vars as CSSProperties}>
        <p className="folio-muted">Loading matrix…</p>
      </div>
    )
  }
  if (!manifest || rows.length === 0 || metrics.length === 0) {
    return (
      <div className="folio" style={theme.vars as CSSProperties}>
        <p className="folio-status" role="status">
          No data available. The census data files are not on this server (<code>/data/census-map/</code>). They are generated, not stored in the
          repository: run <code>python -m ingestion.census.export_census_map_static --all-years</code>, then reload.
        </p>
      </div>
    )
  }

  const st = statsOf(rows, metricSlug)
  const select = (label: string, value: string, onChange: (v: string) => void, options: Array<{ value: string; label: string }>) => (
    <label className="folio-field">
      {label}
      <select className="folio-select" value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  )

  return (
    <div className="folio" data-theme={theme.id} style={theme.vars as CSSProperties}>
      <SectionBand active={active} onJump={(id) => jump(id, true)} rootRef={sectionsRef} reduced={reduced} />
      <p className="folio-eyebrow folio-page-eyebrow">Matrix map</p>
      <h2 className="folio-heading">
        {ctx.geoNoun} · {vintage} ACS 5-year
      </h2>

      <dl className="folio-kpis" aria-label="Key figures for the metric in view">
        <Kpi label="Geographies with data" value={st.n} format={(v) => Math.round(v).toLocaleString('en-US')} sub={ctx.metricLabel} reduced={reduced} />
        <Kpi label="Median" value={st.median} format={(v) => ctx.fmt(metricSlug, v)} sub="the median state" reduced={reduced} />
        <Kpi label="Highest" value={st.high?.v ?? null} format={(v) => ctx.fmt(metricSlug, v)} sub={st.high?.r.name ?? 'No data available'} reduced={reduced} />
        <Kpi label="Lowest" value={st.low?.v ?? null} format={(v) => ctx.fmt(metricSlug, v)} sub={st.low?.r.name ?? 'No data available'} reduced={reduced} />
      </dl>

      <div className="folio-toolbar" role="group" aria-label="Controls for every section">
        {select('Metric', metricSlug, (v) => setQP('metric', v), metrics.map((m) => ({ value: m.slug, label: m.label })))}
        {select('Vintage', vintage, (v) => setQP('vintage', v === manifest.vintage ? null : v), vintages.map((v) => ({ value: v, label: v })))}
        {select('Theme', theme.id, (v) => setQP('theme', v === DEFAULT_THEME_ID ? null : v), FOLIO_THEMES.map((t) => ({ value: t.id, label: t.label })))}
        <p className="folio-note">Metric, vintage and theme apply to every section below. The medians and ranks are over the geographies in this bundle.</p>
      </div>

      <div ref={sectionsRef}>
        <TilesSection ctx={ctx} />
        <ShareSection ctx={ctx} />
        <PivotSection ctx={ctx} />
        <CompareSection ctx={ctx} />
        <BarsSection ctx={ctx} />
        <TrendSection ctx={ctx} />
        <ColumnsSection ctx={ctx} />
        <HeatmapSection ctx={ctx} />
        <DivergingSection ctx={ctx} />
        <ScatterSection ctx={ctx} />
        <DotsSection ctx={ctx} />
        <TableSection ctx={ctx} />
      </div>
    </div>
  )
}
