import { useLayoutEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { CENSUS_REGION_LABEL, type CensusRegionId } from '../../utils/censusRegions'
import { staggerDelayMs } from '../../utils/folioMotion'
import { largestRemainder } from '../../utils/matrixMapMath'
import { useFlip, useIntro } from '../../hooks/useFlip'
import { cellStyle, labelFor, sortByMetric, statsOf, statsSentence } from './data'
import { useSection } from './hooks'
import { Empty, ScaleLegend, Seg } from './parts'
import SectionShell from './SectionShell'
import { delayVar, type MatrixCtx, type Row } from './types'

type Mode = 'none' | 'region' | 'quartile'
interface Group {
  key: string
  label: string | null
  color: string | null
  items: Row[]
}

const QUARTILES = ['Highest quarter', 'Upper-middle quarter', 'Lower-middle quarter', 'Lowest quarter']

/** Groups for the chosen regroup mode. Every group name carries its real count and its share of the tiles shown. */
export function tileGroups(ctx: MatrixCtx, sorted: Row[], mode: Mode): Group[] {
  if (mode === 'none') return [{ key: 'all', label: null, color: null, items: sorted }]
  const { theme, metricSlug } = ctx
  let raw: Array<{ key: string; name: string; color: string; items: Row[] }>
  if (mode === 'region') {
    raw = (Object.keys(CENSUS_REGION_LABEL) as CensusRegionId[]).map((id, i) => ({
      key: id,
      name: CENSUS_REGION_LABEL[id],
      color: theme.series[i]!,
      items: sorted.filter((r) => r.region === id),
    }))
  } else {
    const withVal = sorted.filter((r) => r.vals[metricSlug] != null)
    const missing = sorted.filter((r) => r.vals[metricSlug] == null)
    const q = (i: number) => withVal.filter((_, k) => Math.min(3, Math.floor((k * 4) / withVal.length)) === i)
    // Quarters follow the on-screen order (descending by default); "highest" is the first quarter of a descending sort.
    const ordered = ctx.sortDir === 'asc' ? [...QUARTILES].reverse() : QUARTILES
    raw = [0, 1, 2, 3].map((i) => ({ key: `q${i}`, name: ordered[i]!, color: theme.series[i]!, items: q(i) }))
    if (missing.length) raw.push({ key: 'none', name: 'No data', color: theme.neutral, items: missing })
  }
  const nonEmpty = raw.filter((g) => g.items.length)
  const shares = largestRemainder(nonEmpty.map((g) => g.items.length), 100)
  return nonEmpty.map((g, i) => ({
    key: g.key,
    label: `${g.name} · ${g.items.length} (${shares[i] ?? 0}%)`,
    color: g.color,
    items: g.items,
  }))
}

const INTRO_MS = 900 + 600 + 100

function TileGrid({ ctx, groups }: { ctx: MatrixCtx; groups: Group[] }) {
  const { seen } = useSection()
  const ref = useRef<HTMLUListElement>(null)
  const intro = useIntro(INTRO_MS, ctx.reduced, seen)
  const [nCols, setNCols] = useState(1)
  const ids = groups.map((g) => `${g.key}:${g.items.map((r) => r.fips).join(',')}`).join('|')
  useFlip(ref, ids, !ctx.reduced && !intro)
  useLayoutEffect(() => {
    const el = ref.current
    if (!el) return
    setNCols(Math.max(1, getComputedStyle(el).gridTemplateColumns.split(' ').filter(Boolean).length))
  }, [])
  const total = groups.reduce((a, g) => a + g.items.length, 0)
  const maxDiag = nCols - 1 + Math.max(0, Math.ceil(total / nCols) - 1)
  let i = 0
  const { metricSlug: slug, fmt, theme, metricLabel } = ctx
  return (
    <ul ref={ref} className="folio-tiles">
      {groups.flatMap((g) => [
        ...(g.label ? [<li key={`g:${g.key}`} className="folio-group-label">{g.label}</li>] : []),
        ...g.items.map((r) => {
          const idx = i++
          const v = r.vals[slug] ?? null
          const t = ctx.shade[slug]?.(v) ?? null
          const style = g.color ? { background: g.color, color: labelFor(theme, g.color) } : cellStyle(theme, t, ctx.minPct)
          return (
            <li
              key={r.fips}
              data-flip={r.fips}
              className={intro ? 'folio-in' : undefined}
              style={intro ? delayVar(staggerDelayMs(idx % nCols, Math.floor(idx / nCols), maxDiag, 900)) : undefined}
            >
              <Link to={ctx.mapHref} title={`${r.name}: ${fmt(slug, v)} — ${metricLabel}`} className="folio-tile" style={style}>
                <b>{r.code}</b>
                <span>{fmt(slug, v)}</span>
              </Link>
            </li>
          )
        }),
      ])}
    </ul>
  )
}

export default function TilesSection({ ctx }: { ctx: MatrixCtx }) {
  const mode: Mode = ctx.sp.get('group') === 'region' ? 'region' : ctx.sp.get('group') === 'quartile' ? 'quartile' : 'none'
  const sorted = useMemo(() => sortByMetric(ctx.rows, ctx.metricSlug, ctx.sortDir), [ctx.rows, ctx.metricSlug, ctx.sortDir])
  const groups = tileGroups(ctx, sorted, mode)
  const st = statsOf(ctx.rows, ctx.metricSlug)
  let lit = 0
  let withData = 0
  for (const r of ctx.rows) {
    const v = r.vals[ctx.metricSlug]
    if (v != null) withData += 1
    const t = ctx.shade[ctx.metricSlug]?.(v ?? null) ?? null
    if (t != null && t * 100 >= ctx.minPct) lit += 1
  }
  const scope = `${ctx.geoNoun}, ${ctx.vintage}`
  const modeText = mode === 'region' ? 'grouped by Census region' : mode === 'quartile' ? 'grouped by quarter of the ranking' : 'in one flat grid'
  return (
    <SectionShell
      ctx={ctx}
      id="tiles"
      headline={[`${ctx.metricLabel}`, `across ${ctx.geoNoun},`, ctx.vintage]}
      text={
        <>
          <p>
            Each box is one geography, shaded by where its {ctx.metricLabel.toLowerCase()} ranks among the {ctx.rows.length} shown. Choose a
            grouping and the boxes glide into labelled groups; each group name carries its count and its share of the boxes shown.
          </p>
          <p>{statsSentence(st, ctx.metricSlug, ctx.fmt)}</p>
        </>
      }
      controls={
        <>
          <Seg
            label="Group tiles by"
            value={mode}
            onChange={(v) => ctx.setQP('group', v === 'none' ? null : v)}
            options={[
              { value: 'none', label: 'Flat' },
              { value: 'region', label: 'By region' },
              { value: 'quartile', label: 'By quarter' },
            ]}
          />
          <p className="folio-note">{mode === 'none' ? 'Darker = better rank for the metric (neutral metrics: larger).' : 'One colour per group; the value is printed on each box.'}</p>
        </>
      }
      caption={
        <>
          {ctx.metricLabel} by state, {modeText}; {scope} ACS 5-year. {withData} of {ctx.rows.length} have a value. Source: ACS 5-year, {ctx.vintage}.
        </>
      }
      table={() => ({
        columns: [{ label: 'Geography' }, { label: 'Code' }, { label: ctx.metricLabel, numeric: true }, ...(mode === 'none' ? [] : [{ label: 'Group' }])],
        rows: groups.flatMap((g) =>
          g.items.map((r) => [r.name, r.code, ctx.fmt(ctx.metricSlug, r.vals[ctx.metricSlug] ?? null), ...(mode === 'none' ? [] : [g.label ?? ''])]),
        ),
      })}
    >
      {withData === 0 ? (
        <Empty>No data available for {ctx.metricLabel} in {ctx.vintage}.</Empty>
      ) : (
        <>
          {mode === 'none' && <ScaleLegend ctx={ctx} note="scaled across states" lit={`${lit} of ${withData} cells highlighted`} />}
          <div className="folio-chart">
            <TileGrid ctx={ctx} groups={groups} />
          </div>
        </>
      )}
    </SectionShell>
  )
}
