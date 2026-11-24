import { Fragment, useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
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
import { themeById } from '../utils/folioThemes'
import { usePrefersReducedMotion } from '../hooks/usePrefersReducedMotion'
import { lc } from '../utils/matrixStory'
import { CENSUS_REGION_LABEL, type CensusRegionId } from '../utils/censusRegions'
import { olsFit } from '../utils/matrixMapMath'
import { CHAPTERS, SCREENS, adjacentScreens, chapterDomId, chapterTitle, isChapterId, screenIndexOf, type ChapterInput, type RegionRead } from '../utils/matrixStory'
import { geoNounFor, itemsOf, rowsFromPayload, signedChange, statsOf } from '../components/matrix/data'
import Kpi from '../components/matrix/Kpi'
import ChapterCard from '../components/matrix/ChapterCard'
import QuestionHeading from '../components/matrix/QuestionHeading'
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
/** Every element the story bar follows, in reading order: one per screen (a chapter opener stands for its first section). */
const FOLLOW: readonly string[] = SCREENS.map((s) => s.domId)

/** True when a key press belongs to the control or scrolling region it is aimed at, so it must not page the story. */
function keepsKey(t: EventTarget | null): boolean {
  if (!(t instanceof HTMLElement)) return false
  if (t.isContentEditable) return true
  if (t.closest('input, select, textarea, button, a[href], summary, table, [role="slider"], [role="region"], [role="listbox"], [role="menu"]')) return true
  if (t.closest('[tabindex]:not([tabindex="-1"])')) return true
  for (let el: HTMLElement | null = t; el && el !== document.body; el = el.parentElement) {
    const oy = getComputedStyle(el).overflowY
    if ((oy === 'auto' || oy === 'scroll') && el.scrollHeight > el.clientHeight + 1) return true
  }
  return false
}

/**
 * "How states compare" (route `/data-explorer/matrix`): one scrolling report over the census bundle, told in five chapters (where things stand, what changed, what
 * goes with it, over time, your move). Each chapter opens with its finding as a sentence and holds two or three sections
 * (twelve in all, then the closing action block); every one is a screen that fits the viewport. The shared controls (metric,
 * vintage, theme) sit under the heading; each section has its own headline, text, figure, controls and data table. The reader
 * pages with Continue / Back, PageDown / PageUp, Space, the arrow keys, Home and End, or just scrolls. All state that shapes
 * the data lives in the URL.
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

  const scatterY = sp.get('y') && metrics.some((m) => m.slug === sp.get('y')) ? sp.get('y')! : metrics.find((m) => m.slug !== metricSlug)?.slug
  const metricLabel = metrics.find((m) => m.slug === metricSlug)?.label ?? metricSlug
  const labelOf = (slug: string) => metrics.find((m) => m.slug === slug)?.label ?? slug
  // The earliest vintage, when it is earlier than the selected one (the same pair Compare draws).
  const base = vintages[0] && vintages[0] !== vintage ? vintages[0] : null
  const goToRef = useRef<(domId: string) => void>(() => undefined)

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
    metricLabel,
    vintage,
    vintages,
    rows,
    rowsByVintage,
    fmt: (slug, v) => formatMetricValueDisplay(slug, v, metrics),
    labelOf,
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
    labelInput: { metricLabel, base, yLabel: scatterY ? labelOf(scatterY) : null, stateName: stateScope?.name ?? null },
    goTo: (domId) => goToRef.current(domId),
  }

  // Where the reader is (band + `layout` / `chapter` params), and the deep link on load. `pos` is a DOM id: a chapter card
  // (`chapter-<id>`) or a section. A section in view writes `layout=<id>`; a chapter card writes `chapter=<id>`.
  const layoutQ = sp.get('layout')
  const chapterQ = sp.get('chapter')
  // A section deep link lands on its screen: a chapter's first section on the chapter opener above it.
  const screenOf = (id: string): string => SCREENS[screenIndexOf(id)]?.domId ?? id
  const target = isSection(layoutQ) || layoutQ === 'action' ? screenOf(layoutQ) : isChapterId(chapterQ) ? chapterDomId(chapterQ) : null
  const [pos, setPos] = useState<string>(target ?? chapterDomId('problem'))
  const posRef = useRef(pos)
  posRef.current = pos
  const jumping = useRef(false)
  const jumpTimer = useRef<number | undefined>(undefined)
  const sectionsRef = useRef<HTMLDivElement>(null)
  const urlFor = (domId: string): Record<string, string | null> =>
    domId.startsWith('chapter-') ? { chapter: domId.replace(/^chapter-/, ''), layout: null } : { layout: domId, chapter: null }
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
    // Keyboard and screen-reader users arrive at the heading of the screen, without a second scroll.
    const heading = SCREENS.find((x) => x.domId === domId)?.headingId
    if (heading) document.getElementById(heading)?.focus({ preventScroll: true })
  }
  goToRef.current = (domId) => {
    if (domId === 'top') {
      hold(reduced ? 400 : 1100)
      window.scrollTo({ top: 0, behavior: reduced ? 'auto' : 'smooth' })
      setPos(SCREENS[0]!.domId)
      setManyRef.current({ chapter: null, layout: null })
      document.getElementById('matrix-top')?.focus({ preventScroll: true })
      return
    }
    jump(domId, true)
  }
  /** Back to the very top of the page and the main menu: scroll up, forget the screen in the address, focus the site header. */
  const toTop = () => {
    hold(reduced ? 400 : 1100)
    window.scrollTo({ top: 0, behavior: reduced ? 'auto' : 'smooth' })
    setPos(SCREENS[0]!.domId)
    setManyRef.current({ chapter: null, layout: null })
    document.querySelector<HTMLElement>('header.site-header a, header.site-header button')?.focus({ preventScroll: true })
  }
  /** Back to the sentence heading so the reader can change the measure. */
  const changeSelection = () => {
    hold(reduced ? 400 : 1100)
    document.getElementById('matrix-top')?.scrollIntoView({ behavior: reduced ? 'auto' : 'smooth', block: 'start' })
    document.querySelector<HTMLElement>('button[aria-label^="Measure:"]')?.focus({ preventScroll: true })
  }
  const lastHome = useRef(0)
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

  // Page the story from the keyboard: PageDown / Space / Down arrow go to the next screen, PageUp / Shift+Space / Up arrow to the
  // previous one (or to the top of the current one when it is scrolled), Home and End to the first and last. Never while the
  // reader is typing, using a control or scrolling inside a figure, and never with a modifier key; a screen taller than the
  // window (a long open data table) scrolls natively until its end is in view. The wheel and touch are left alone.
  useEffect(() => {
    if (!ready) return
    const topLine = () => (document.querySelector('.folio-band')?.getBoundingClientRect().bottom ?? 0) + 4
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.ctrlKey || e.metaKey || e.altKey) return
      const k = e.key
      const forward = k === 'PageDown' || k === 'ArrowDown' || (k === ' ' && !e.shiftKey)
      const backward = k === 'PageUp' || k === 'ArrowUp' || (k === ' ' && e.shiftKey)
      if (!forward && !backward && k !== 'Home' && k !== 'End') return
      if (e.shiftKey && k !== ' ') return
      if (keepsKey(e.target)) return
      const go = (i: number) => {
        e.preventDefault()
        goToRef.current(SCREENS[i]!.domId)
      }
      if (k === 'Home') {
        // Home goes to the first screen; pressed again (or already there) it goes to the very top of the page.
        const now = Date.now()
        const again = now - lastHome.current < 1500
        lastHome.current = now
        const onFirst = Math.abs((document.getElementById(FOLLOW[0]!)?.getBoundingClientRect().top ?? 1e6) - topLine()) < 40
        if (again || onFirst) {
          e.preventDefault()
          return toTop()
        }
        return go(0)
      }
      if (k === 'End') return go(SCREENS.length - 1)
      const line = window.innerHeight * 0.4
      let cur = -1
      FOLLOW.forEach((id, i) => {
        const el = document.getElementById(id)
        if (el && el.getBoundingClientRect().top <= line) cur = i
      })
      const top = (i: number) => document.getElementById(FOLLOW[i]!)?.getBoundingClientRect().top ?? 0
      const tl = topLine()
      const curTop = cur >= 0 ? top(cur) : Infinity
      const nextTop = cur + 1 < FOLLOW.length ? top(cur + 1) : cur >= 0 ? (document.getElementById(FOLLOW[cur]!)?.getBoundingClientRect().bottom ?? 0) : 0
      const tall = cur >= 0 && nextTop - curTop > window.innerHeight - tl + 40
      if (forward) {
        if (cur + 1 >= FOLLOW.length) return
        if (tall && nextTop > window.innerHeight + 24) return
        return go(cur + 1)
      }
      if (cur < 0) return
      if (curTop < tl - 24) {
        if (tall) return
        return go(cur)
      }
      if (cur > 0) go(cur - 1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [ready])

  // Gentle snapping (proximity, never forced) once each screen fits the window; folio.css turns it off on phones and under reduced motion.
  useEffect(() => {
    document.documentElement.classList.add('folio-snap')
    return () => document.documentElement.classList.remove('folio-snap')
  }, [])

  // The first-screen hint goes away at the first move.
  const [moved, setMoved] = useState(false)
  useEffect(() => {
    if (!ready || moved) return
    const done = () => setMoved(true)
    const onScroll = () => window.scrollY > 40 && done()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('keydown', done, { once: true })
    window.addEventListener('wheel', done, { once: true, passive: true })
    window.addEventListener('touchstart', done, { once: true, passive: true })
    return () => {
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('keydown', done)
      window.removeEventListener('wheel', done)
      window.removeEventListener('touchstart', done)
    }
  }, [ready, moved])

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
  const fmtV = (v: number) => ctx.fmt(metricSlug, v)
  const baseRows = base ? rowsByVintage[base] : null
  const xyPts = rows.flatMap((r) => {
    const x = scatterY ? r.vals[metricSlug] : null
    const y = scatterY ? r.vals[scatterY] : null
    return x != null && y != null ? [{ x, y }] : []
  })
  const fit = olsFit(xyPts)
  const isCount = metrics.find((m) => m.slug === metricSlug)?.format === 'count'
  const regionRead = (v: string | undefined): RegionRead | null => {
    const rs = v ? rowsByVintage[v] : null
    if (!v || !rs) return null
    const shares = (Object.keys(CENSUS_REGION_LABEL) as CensusRegionId[]).flatMap((id) => {
      const xs = rs.filter((r) => r.region === id && r.vals[metricSlug] != null)
      return xs.length ? [{ label: `The ${CENSUS_REGION_LABEL[id]}`, value: xs.reduce((a, r) => a + (r.vals[metricSlug] as number), 0) }] : []
    })
    return { vintage: v, shares }
  }
  const chapterData: ChapterInput = {
    metricLabel,
    vintage,
    vintages,
    fmt: fmtV,
    fmtDiff: (hi, lo) => {
      const t = signedChange(metricSlug, lo, hi, metrics, ctx.fmt)
      return t === '—' ? null : t.replace(/^\+/, '')
    },
    fmtChange: (from, to) => signedChange(metricSlug, from, to, metrics, ctx.fmt),
    items: itemsOf(rows, metricSlug),
    baseItems: base && baseRows ? itemsOf(baseRows, metricSlug) : null,
    base: base && baseRows ? base : null,
    stateName: stateScope?.name ?? null,
    yLabel: scatterY ? labelOf(scatterY) : null,
    fit: fit ? { slope: fit.slope, r2: fit.r2, n: fit.n } : null,
    medians: { first: statsOf(rowsByVintage[vintages[0] ?? ''] ?? [], metricSlug).median, last: statsOf(rowsByVintage[vintages[vintages.length - 1] ?? ''] ?? [], metricSlug).median },
    regions: isCount ? { first: regionRead(vintages[0]), last: regionRead(vintages[vintages.length - 1]) } : null,
  }
  const first = adjacentScreens(null).next!
  return (
    <div className="folio" data-theme={theme.id} style={theme.vars as CSSProperties}>
      <SectionBand
        pos={pos}
        onJump={(id) => jump(id, true)}
        rootRef={sectionsRef}
        reduced={reduced}
        labels={ctx.labelInput}
        selection={{ measure: lc(metricLabel), place: 'United States' }}
        onTop={toTop}
        onChange={changeSelection}
      />
      <QuestionHeading
        metrics={metrics}
        metricSlug={metricSlug}
        hasData={(slug) => rows.some((r) => r.vals[slug] != null)}
        hintOf={(slug) => {
          const med = statsOf(rows, slug).median
          return med == null ? undefined : `Median ${ctx.fmt(slug, med)} across the states`
        }}
        onMetric={(v) => setQP('metric', v)}
      >
        <p className="folio-orient">
          Census Bureau figures for {rows.length.toLocaleString('en-US')} {rows.length === 1 ? 'state or territory' : 'states and territories'},{' '}
          {vintages.length > 1 ? (
            <label className="folio-year">
              <span className="folio-sr-only">Year</span>
              <select className="folio-year-select" value={vintage} onChange={(e) => setQP('vintage', e.target.value === manifest.vintage ? null : e.target.value)}>
                {vintages.map((v) => (
                  <option key={v} value={v}>
                    {v}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            vintage
          )}
          .
        </p>
      </QuestionHeading>
      <dl className="folio-kpis" aria-label="Key figures for the metric in view">
        <Kpi label="Geographies with data" value={st.n} format={(v) => Math.round(v).toLocaleString('en-US')} sub={ctx.metricLabel} reduced={reduced} />
        <Kpi label="Median" value={st.median} format={(v) => ctx.fmt(metricSlug, v)} sub="the median state" reduced={reduced} />
        <Kpi label="Highest" value={st.high?.v ?? null} format={(v) => ctx.fmt(metricSlug, v)} sub={st.high?.r.name ?? 'No data available'} reduced={reduced} />
        <Kpi label="Lowest" value={st.low?.v ?? null} format={(v) => ctx.fmt(metricSlug, v)} sub={st.low?.r.name ?? 'No data available'} reduced={reduced} />
      </dl>

      <div ref={sectionsRef}>
        {CHAPTERS.map((c) => {
          return (
            <Fragment key={c.id}>
              <ChapterCard chapter={c} title={chapterTitle(c.id, chapterData)} />
              {c.sections.map((id) => {
                const Section = SECTION_VIEW[id]
                return <Section key={id} ctx={ctx} />
              })}
            </Fragment>
          )
        })}
      </div>
      {!moved && ready && (
        <button type="button" className="folio-hint" onClick={() => jump(first.domId, true)}>
          Scroll or press <span aria-hidden="true">↓</span>
          <span className="folio-sr-only">the down arrow key</span> to continue
        </button>
      )}
    </div>
  )
}
