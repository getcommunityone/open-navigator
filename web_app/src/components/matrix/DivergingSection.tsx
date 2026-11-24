import { useMemo } from 'react'
import { medianOf, quantileOf } from '../../utils/matrixMapMath'
import { signedChange } from './data'
import DivergingBars, { type BarRow } from './DivergingBars'
import { useSection, useSeries } from './hooks'
import Kpi from './Kpi'
import LegendChips from './LegendChips'
import { Empty, Seg } from './parts'
import SectionShell from './SectionShell'
import type { MatrixCtx } from './types'

const SIDES = ['below', 'above']

/** Diverging bars: each geography's distance from the median geography, sorted by value by default. */
function Bars({ ctx, rows, maxSide, hot, axisLabel }: { ctx: MatrixCtx; rows: BarRow[]; maxSide: number; hot: string | null; axisLabel: string }) {
  const { seen } = useSection()
  return <DivergingBars rows={rows} maxSide={maxSide} revealed={seen || ctx.reduced} hot={hot} axisLabel={axisLabel} />
}

export default function DivergingSection({ ctx }: { ctx: MatrixCtx }) {
  const slug = ctx.metricSlug
  const { theme } = ctx
  const alpha = ctx.sortRaw === 'name'
  const sv = useSeries(ctx, 'diverging', SIDES)
  const vals = ctx.rows.flatMap((r) => (r.vals[slug] != null ? [{ r, v: r.vals[slug] as number }] : []))
  const med = medianOf(vals.map((x) => x.v))
  const q1 = quantileOf(vals.map((x) => x.v), 0.25)
  const q3 = quantileOf(vals.map((x) => x.v), 0.75)
  const ok = med != null && q1 != null && q3 != null && vals.length >= 3
  const colors = {
    belowNear: theme.vars['--vermilion-tint']!,
    belowFar: theme.vars['--vermilion']!,
    aboveNear: theme.vars['--violet-tint']!,
    aboveFar: theme.vars['--violet']!,
  }
  const built = useMemo(() => {
    if (!ok) return { rows: [] as BarRow[], items: [] as Array<{ name: string; v: number; d: number }>, maxSide: 0 }
    const items = vals.map(({ r, v }) => ({ r, name: r.name, v, d: v - med! }))
    const sorted = [...items].sort((a, b) => {
      if (alpha) return a.name.localeCompare(b.name) * (ctx.sp.get('dir') === 'desc' ? -1 : 1)
      return (ctx.sortDir === 'asc' ? a.d - b.d : b.d - a.d) || a.name.localeCompare(b.name)
    })
    const shown = sorted.filter((i) => (i.d < 0 ? sv.on('below') : sv.on('above')))
    const nearAbove = q3! - med!
    const nearBelow = med! - q1!
    const maxSide = Math.max(0, ...shown.map((i) => Math.abs(i.d)))
    const rows: BarRow[] = shown.map((i) => {
      const dist = signedChange(slug, med, i.v, ctx.metrics, ctx.fmt)
      const segments =
        i.d >= 0
          ? [
              { key: 'near', value: Math.min(i.d, nearAbove), side: 'right' as const, color: colors.aboveNear },
              { key: 'far', value: Math.max(0, i.d - nearAbove), side: 'right' as const, color: colors.aboveFar },
            ]
          : [
              { key: 'near', value: Math.min(-i.d, nearBelow), side: 'left' as const, color: colors.belowNear },
              { key: 'far', value: Math.max(0, -i.d - nearBelow), side: 'left' as const, color: colors.belowFar },
            ]
      return {
        id: i.r.fips,
        label: `${i.name} · ${ctx.fmt(slug, i.v)}`,
        segments,
        endLeft: i.d < 0 ? dist : undefined,
        endRight: i.d >= 0 ? dist : undefined,
        info: { cat: i.name, val: ctx.fmt(slug, i.v), sub: `${dist} from the median (${ctx.fmt(slug, med)})` },
        ariaLabel: `${i.name}: ${ctx.fmt(slug, i.v)}, ${dist} from the median`,
      }
    })
    return { rows, items: shown, maxSide }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ok, ctx.rows, slug, alpha, ctx.sortDir, ctx.sp.get('dir'), sv.off, ctx.theme, ctx.fmt])
  const above = vals.filter((x) => med != null && x.v > med).length
  const high = vals.reduce<{ r: (typeof vals)[number]['r']; v: number } | null>((a, x) => (a == null || x.v > a.v ? x : a), null)
  const low = vals.reduce<{ r: (typeof vals)[number]['r']; v: number } | null>((a, x) => (a == null || x.v < a.v ? x : a), null)
  const shownNote = sv.off.size ? ` Only ${sv.on('below') ? 'below' : 'above'}-median rows are shown.` : ''
  return (
    <SectionShell
      ctx={ctx}
      id="diverging"
      headline={[ctx.metricLabel, `against the median,`, `${ctx.geoNoun}, ${ctx.vintage}`]}
      text={
        <>
          <p>
            Each bar is one geography's distance from the median geography{ok ? ` (${ctx.fmt(slug, med)})` : ''}. Bars grow left, in the vermilion family, below the
            median and right, in the violet family, above it. The lighter step covers the distance up to the nearest quartile (the middle half of
            geographies); the stronger step is the distance beyond it. The number at the end of each bar is the real distance in the metric's own unit.
          </p>
          <p>
            Sorted {alpha ? `by name, ${ctx.sp.get('dir') === 'desc' ? 'Z to A' : 'A to Z'}` : `by value, ${ctx.sortDir === 'asc' ? 'lowest' : 'highest'} first`}; use the toggle to switch. Hover or
            focus a legend chip to highlight one side; click it to hide that side.{shownNote}
          </p>
        </>
      }
      controls={
        <Seg
          label="Sort diverging rows"
          value={alpha ? 'name' : 'value'}
          onChange={(v) => ctx.setMany(v === 'name' ? { sort: 'name', dir: null } : { sort: null })}
          options={[
            { value: 'value', label: 'Sort by value' },
            { value: 'name', label: 'Alphabetical' },
          ]}
        />
      }
      caption={
        <>
          {ctx.metricLabel}: distance of each of {vals.length} geographies from the median, {ctx.vintage} ACS 5-year; lighter bars are within the middle half
          (Q1 to Q3), stronger bars beyond it. Source: ACS 5-year, {ctx.vintage}.
        </>
      }
      table={() =>
        ok
          ? {
              columns: [{ label: 'Geography' }, { label: ctx.metricLabel, numeric: true }, { label: 'Distance from median', numeric: true }],
              rows: built.items.map((i) => [i.name, ctx.fmt(slug, i.v), signedChange(slug, med, i.v, ctx.metrics, ctx.fmt)]),
            }
          : null
      }
    >
      {!ok ? (
        <Empty>No data available — at least 3 geographies with a value for {ctx.metricLabel} are needed.</Empty>
      ) : (
        <div className="folio-diverge">
          <div className="folio-diverge-chart">
            <LegendChips
              label="Sides of the median"
              items={[
                { key: 'below', label: 'Below the median', color: colors.belowFar },
                { key: 'above', label: 'Above the median', color: colors.aboveFar },
              ]}
              off={sv.off}
              onToggle={sv.toggle}
              onHot={sv.setHot}
            />
            <p className="folio-legend-inline">
              <span>
                <i className="folio-legend-swatch" style={{ background: colors.belowNear }} />
                <i className="folio-legend-swatch" style={{ background: colors.aboveNear }} /> within the middle half (Q1 to Q3)
              </span>
              <span>
                <i className="folio-legend-swatch" style={{ background: colors.belowFar }} />
                <i className="folio-legend-swatch" style={{ background: colors.aboveFar }} /> beyond it
              </span>
            </p>
            <Bars ctx={ctx} rows={built.rows} maxSide={built.maxSide} hot={sv.hot} axisLabel={`Median ${ctx.fmt(slug, med)}`} />
          </div>
          <dl className="folio-diverge-kpis" aria-label="Key figures for this chart">
            <Kpi label="Above the median" value={above} format={(v) => String(Math.round(v))} sub={`of ${vals.length} geographies`} reduced={ctx.reduced} />
            <Kpi label="Highest" value={high?.v ?? null} format={(v) => ctx.fmt(slug, v)} sub={high?.r.name ?? 'No data available'} reduced={ctx.reduced} />
            <Kpi label="Lowest" value={low?.v ?? null} format={(v) => ctx.fmt(slug, v)} sub={low?.r.name ?? 'No data available'} reduced={ctx.reduced} />
          </dl>
        </div>
      )}
    </SectionShell>
  )
}
