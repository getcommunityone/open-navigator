import { useMemo, useRef } from 'react'
import { CENSUS_REGION_LABEL, type CensusRegionId } from '../../utils/censusRegions'
import { rowDelayMs } from '../../utils/folioMotion'
import { useFlip } from '../../hooks/useFlip'
import { barsStory } from '../../utils/matrixStory'
import { itemsOf, sortByMetric, statsOf, statsSentence } from './data'
import { Empty } from './parts'
import SectionShell from './SectionShell'
import { delayVar, type MatrixCtx } from './types'

const REGIONS = Object.keys(CENSUS_REGION_LABEL) as CensusRegionId[]

/** One horizontal bar per geography for the chosen metric; region chips filter the rows (`?region=`). */
export default function BarsSection({ ctx }: { ctx: MatrixCtx }) {
  const q = ctx.sp.get('region')
  const region: CensusRegionId | null = REGIONS.includes(q as CensusRegionId) ? (q as CensusRegionId) : null
  const slug = ctx.metricSlug
  const scoped = useMemo(() => (region ? ctx.rows.filter((r) => r.region === region) : ctx.rows), [ctx.rows, region])
  const rows = useMemo(() => sortByMetric(scoped, slug, ctx.sortDir), [scoped, slug, ctx.sortDir])
  const ref = useRef<HTMLUListElement>(null)
  useFlip(ref, `${region ?? 'all'}|${slug}|${ctx.sortDir}|${rows.map((r) => r.fips).join(',')}`, !ctx.reduced)
  const vals = rows.flatMap((r) => (r.vals[slug] != null ? [r.vals[slug] as number] : []))
  const lo = Math.min(0, ...vals)
  const hi = Math.max(0, ...vals)
  const span = hi - lo || 1
  const st = statsOf(scoped, slug)
  const scope = region ? `${CENSUS_REGION_LABEL[region]} states` : ctx.geoNoun
  const story = barsStory({ metricLabel: ctx.metricLabel, vintage: ctx.vintage, scopeLabel: scope, items: itemsOf(scoped, slug), fmt: (v) => ctx.fmt(slug, v) })
  return (
    <SectionShell
      ctx={ctx}
      id="bars"
      headline={story.headline}
      lead={story.lead}
      text={
        <>
          <p>
            One horizontal bar per geography, ordered by {ctx.metricLabel.toLowerCase()} ({ctx.sortDir === 'asc' ? 'lowest' : 'highest'}{' '}
            first). Pick a region and the bars re-order and grow again; change the metric above and they animate to the new values.
          </p>
          <p>{statsSentence(st, slug, ctx.fmt)}</p>
        </>
      }
      controls={
        <div className="folio-seg" role="group" aria-label="Region filter">
          <button type="button" aria-pressed={!region} onClick={() => ctx.setQP('region', null)}>
            All regions
          </button>
          {REGIONS.map((id) => (
            <button key={id} type="button" aria-pressed={region === id} onClick={() => ctx.setQP('region', id)}>
              {CENSUS_REGION_LABEL[id]}
            </button>
          ))}
        </div>
      }
      caption={
        <>
          {ctx.metricLabel}, {scope}, {ctx.vintage}; {rows.length} {rows.length === 1 ? 'row' : 'rows'}. Source: ACS 5-year, {ctx.vintage}.
        </>
      }
      table={() => ({
        columns: [{ label: 'Geography' }, { label: 'Region' }, { label: ctx.metricLabel, numeric: true }],
        rows: rows.map((r) => [r.name, r.region ? CENSUS_REGION_LABEL[r.region] : '—', ctx.fmt(slug, r.vals[slug] ?? null)]),
      })}
    >
      {!rows.length || !vals.length ? (
        <Empty>No data available for {ctx.metricLabel} in {scope}, {ctx.vintage}.</Empty>
      ) : (
        <ul className="folio-rows" ref={ref} aria-label={`${ctx.metricLabel} by geography`}>
          {rows.map((r, i) => {
            const v = r.vals[slug] ?? null
            const left = ((Math.min(0, v ?? 0) - lo) / span) * 100
            const width = v == null ? 0 : (Math.abs(v) / span) * 100
            return (
              <li key={r.fips} data-flip={r.fips} className="folio-row" style={{ gridTemplateColumns: '7rem 1fr 5.5rem' }}>
                <span className="folio-row-name">{r.name}</span>
                <span className="folio-track">
                  <span
                    className="folio-bar folio-grow"
                    style={{ ...delayVar(rowDelayMs(i, rows.length, 20, 500)), left: `${left}%`, width: `${width}%` }}
                  />
                </span>
                <span className="folio-row-val">{ctx.fmt(slug, v)}</span>
              </li>
            )
          })}
        </ul>
      )}
    </SectionShell>
  )
}
