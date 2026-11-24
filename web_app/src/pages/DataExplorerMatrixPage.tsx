import { Fragment, useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
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
import { CHAPTERS, chapterDomId, chapterLead, isChapterId } from '../utils/matrixStory'
import { geoNounFor, rowsFromPayload, statsOf } from '../components/matrix/data'
import Kpi from '../components/matrix/Kpi'
import ChapterCard from '../components/matrix/ChapterCard'
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

const SECTION_VIEW: Record<SectionId, (p: { ctx: MatrixCtx }) => JSX.Element> = {
  tiles: TilesSection,
  dots: DotsSection,
  share: ShareSection,
  dumbbell: CompareSection,
  diverging: DivergingSection,
  bars: BarsSection,
  scatter: ScatterSection,
  heatmap: HeatmapSection,
  trend: TrendSection,
  columns: ColumnsSection,
  pivot: PivotSection,
  table: TableSection,
}
/** Every element the band follows, in reading order: each chapter card, then its sections. */
const FOLLOW: readonly string[] = CHAPTERS.flatMap((c) => [chapterDomId(c.id), ...c.sections])

/**
 * "Matrix map": one scrolling report over the census bundle, told as a public meeting in five chapters (call to order, the
 * motion, public comment, the vote and the work, new business), each opened by a chapter card and holding two or three
 * sections (twelve in all). The shared controls (metric, vintage, theme) sit under the heading; each section has its own story
 * sentence, text, figure, controls and data table. All state that shapes the data lives in the URL.
 */
export default function DataExplorerMatrixPage() {
  const [sp, setSp] = useSearchParams()
  const reduced = usePrefersReducedMotion()
  const [hotFips, setHotFips] = useState<string | null>(null)

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

  // The one state in scope, if any: the dot map drilled into a state, or the county share of a state.
  const stateFips = sp.get('dot') || (sp.get('part') === 'county' ? sp.get('st') || '01' : null)
  const stateScope = useMemo(() => {
    const r = stateFips ? rows.find((x) => x.fips === stateFips.padStart(2, '0')) : undefined
    return r ? { fips: r.fips, code: r.code, name: r.name } : null
  }, [rows, stateFips])

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
    hotFips,
    setHotFips,
    stateScope,
  }

  // Where the reader is (band + `layout` / `chapter` params), and the deep link on load. `pos` is a DOM id: a chapter card
  // (`chapter-<id>`) or a section. A section in view writes `layout=<id>`; a chapter card writes `chapter=<id>`.
  const layoutQ = sp.get('layout')
  const chapterQ = sp.get('chapter')
  const target = isSection(layoutQ) ? layoutQ : isChapterId(chapterQ) ? chapterDomId(chapterQ) : null
  const [pos, setPos] = useState<string>(target ?? chapterDomId('problem'))
  const posRef = useRef(pos)
  posRef.current = pos
  const jumping = useRef(false)
  const jumpTimer = useRef<number | undefined>(undefined)
  const sectionsRef = useRef<HTMLDivElement>(null)
  const urlFor = (domId: string): Record<string, string | null> =>
    isSection(domId) ? { layout: domId, chapter: null } : { chapter: domId.replace(/^chapter-/, ''), layout: null }
  // Deep-link scrolling and position tracking wait until every vintage file has settled, because Compare, Trend and
  // Columns change height as they load and would otherwise push the target out from under the scroll position.
  const settled = vintages.every((v) => rowsByVintage[v] !== undefined)
  const ready = !!manifest && !pLoading && rows.length > 0 && metrics.length > 0 && settled
  const hold = (ms: number) => {
    jumping.current = true
    window.clearTimeout(jumpTimer.current)
    jumpTimer.current = window.setTimeout(() => (jumping.current = false), ms)
  }
  const jump = (domId: string, smooth: boolean) => {
    setPos(domId)
    setManyRef.current(urlFor(domId))
    hold(smooth && !reduced ? 1100 : 400)
    document.getElementById(domId)?.scrollIntoView({ behavior: smooth && !reduced ? 'smooth' : 'auto', block: 'start' })
  }
  const deepLinked = useRef(false)
  useEffect(() => {
    if (!ready || deepLinked.current || !target) return
    // Land on the target, and keep it there while web fonts and charts settle (heights above it still change for a moment),
    // until the reader scrolls or the settling window ends.
    const align = () => document.getElementById(target)?.scrollIntoView({ behavior: 'auto', block: 'start' })
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
      deepLinked.current = true // done: later vintage changes must not pull the page back to the target
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
  // The element in view is the last one in reading order whose top has passed the 40% line of the viewport. Reading it from
  // the scroll position (not from intersection events) keeps the band right after a long jump and at the end of the page.
  useEffect(() => {
    if (!ready) return
    let raf = 0
    const update = () => {
      raf = 0
      if (jumping.current) return
      const line = window.innerHeight * 0.4
      let id: string | null = null
      for (const x of FOLLOW) {
        const el = document.getElementById(x)
        if (el && el.getBoundingClientRect().top <= line) id = x
      }
      if (id && id !== posRef.current) {
        posRef.current = id
        setPos(id)
        setManyRef.current(urlFor(id))
      }
    }
    const on = () => {
      if (!raf) raf = requestAnimationFrame(update)
    }
    window.addEventListener('scroll', on, { passive: true })
    window.addEventListener('resize', on)
    on()
    return () => {
      window.removeEventListener('scroll', on)
      window.removeEventListener('resize', on)
      if (raf) cancelAnimationFrame(raf)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
  const scatterY = sp.get('y') && metrics.some((m) => m.slug === sp.get('y')) ? sp.get('y')! : metrics.find((m) => m.slug !== metricSlug)?.slug
  const chapterData = {
    metricLabel: ctx.metricLabel,
    vintage,
    vintages,
    geoNoun: rows.length ? ctx.geoNoun : null,
    yLabel: scatterY ? ctx.labelOf(scatterY) : null,
    stateName: stateScope?.name ?? null,
  }
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
      <SectionBand pos={pos} onJump={(id) => jump(id, true)} rootRef={sectionsRef} reduced={reduced} />
      <p className="folio-eyebrow folio-page-eyebrow">Matrix map</p>
      <h2 className="folio-heading">
        {ctx.geoNoun} · {vintage} ACS 5-year
      </h2>
      <p className="folio-note">
        <Link to="/play/data-centers">Play: Where Do You Stand?</Link>
      </p>

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
        {CHAPTERS.map((c, i) => {
          return (
            <Fragment key={c.id}>
              <ChapterCard chapter={c} index={i} total={CHAPTERS.length} lead={chapterLead(c.id, chapterData)} />
              {c.sections.map((id) => {
                const Section = SECTION_VIEW[id]
                return <Section key={id} ctx={ctx} />
              })}
            </Fragment>
          )
        })}
      </div>
    </div>
  )
}
