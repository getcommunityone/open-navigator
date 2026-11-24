import DotMatrixMap from '../DotMatrixMap'
import { dotsStory } from '../../utils/matrixStory'
import { itemsOf, stepColor, statsOf, statsSentence } from './data'
import { Empty, ScaleLegend } from './parts'
import SectionShell from './SectionShell'
import type { MatrixCtx } from './types'

/** The country (or one state's counties) as a dot-matrix map; click a state to drill into its counties (`?dot=`). */
export default function DotsSection({ ctx }: { ctx: MatrixCtx }) {
  const drill = ctx.sp.get('dot')
  const drillName = drill ? ctx.rows.find((r) => r.fips === drill)?.name ?? drill : null
  const slug = ctx.metricSlug
  const st = statsOf(ctx.rows, slug)
  const where = drillName ? `${drillName} counties` : 'the United States'
  const story = dotsStory({ metricLabel: ctx.metricLabel, vintage: ctx.vintage, drillName, items: itemsOf(ctx.rows, slug), fmt: (v) => ctx.fmt(slug, v) })
  return (
    <SectionShell
      ctx={ctx}
      id="dots"
      headline={story.headline}
      lead={story.lead}
      text={
        <>
          <p>
            The map is drawn as a grid of dots clipped to the outline; each dot takes the shade of the area it sits in, so it is a real choropleth of{' '}
            {ctx.metricLabel.toLowerCase()}. Click a state to open its counties, scaled within that state, and use the breadcrumb to come back out.
          </p>
          {!drillName && <p>{statsSentence(st, slug, ctx.fmt)}</p>}
        </>
      }
      caption={
        <>
          {ctx.metricLabel} as a dot-matrix map of {where}, {drillName ? 'scaled within the state' : 'scaled across states'}; {ctx.vintage} ACS 5-year. Source: ACS 5-year,{' '}
          {ctx.vintage}.
        </>
      }
      table={() =>
        drill
          ? null // the county values live in the map component, not the state bundle; go back to the nation for the table
          : {
              columns: [{ label: 'Geography' }, { label: ctx.metricLabel, numeric: true }],
              rows: ctx.rows.map((r) => [r.name, ctx.fmt(slug, r.vals[slug] ?? null)]),
            }
      }
    >
      {!ctx.rows.length ? (
        <Empty>No data available for {ctx.vintage}.</Empty>
      ) : (
        <>
          <ScaleLegend ctx={ctx} slider={false} note={drillName ? 'scaled within this state' : 'scaled across states'} />
          <div className="folio-chart">
            <DotMatrixMap
              slug={slug}
              vintage={ctx.vintage}
              stateValue={(f) => ctx.rows.find((r) => r.fips === f)?.vals[slug] ?? null}
              stateName={(f) => ctx.rows.find((r) => r.fips === f)?.name ?? f}
              stateT={(f) => ctx.shade[slug]?.(ctx.rows.find((r) => r.fips === f)?.vals[slug] ?? null) ?? null}
              color={(t) => stepColor(ctx.theme, t)}
              fmt={ctx.fmt}
              drill={drill}
              onDrill={(f) => ctx.setQP('dot', f)}
            />
          </div>
        </>
      )}
    </SectionShell>
  )
}
