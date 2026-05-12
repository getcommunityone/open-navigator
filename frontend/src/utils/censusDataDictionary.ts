/**
 * Short ACS-style descriptions for census map UI tooltips (aligned with common subject-table wording).
 * Keys are metric slugs from ``manifest.json``; fallback copy is provided for unknown slugs.
 */

export const CENSUS_FIELD_HELP: Record<string, string> = {
  median_household_income:
    'Median household income in the past 12 months (inflation-adjusted dollars). Half of households earn more and half earn less; not comparable to per capita income.',
  median_home_value:
    'Median value of owner-occupied housing units. Based on respondents’ estimate of what the property would sell for, not tax assessment.',
  median_gross_rent:
    'Median gross rent including utilities (if paid) for renter-occupied units paying cash rent. Contract rent plus estimated average monthly cost of utilities and fuels.',
  per_capita_income:
    'Mean income computed for every man, woman, and child in the area. It is derived by dividing the total income of all people 15+ by the total population in that scope.',
  total_population:
    'Total population — count of all people living in the geography at the time of the ACS sample, including group quarters.',
  median_age:
    'Median age of all people in the geography. Half the population is older and half is younger.',
  gini_income_inequality:
    'Gini index of income inequality for households. 0 indicates perfect equality (everyone has the same income); 1 indicates maximum inequality.',
  median_gross_rent_pct_hhincome:
    'Median gross rent as a percent of household income — the rent-to-income ratio for the typical renter household paying cash rent.',
  travel_time_to_work_minutes:
    'Mean travel time to work in minutes for workers 16+ who did not work from home (ACS subject table S0801). One-way usual commute.',
  housing_units:
    'Housing units — separate living quarters where people live or could live; includes occupied and vacant units.',
  poverty_universe:
    'Population for whom poverty status is determined — used as the denominator for poverty rate calculations in detailed tables.',
  labor_force:
    'Civilian labor force — people 16+ who are employed or unemployed and actively looked for work in the past four weeks.',
}

export function censusMetricHelpText(slug: string, label: string): string {
  return CENSUS_FIELD_HELP[slug] ?? `${label}: ACS 5-year estimate for this geography. See Census Data API / subject definitions for the underlying table.`
}

/** How “top” / winner rows rank this metric (drives default sort and bar order). */
export type CensusMetricRankDirection = 'higher' | 'lower' | 'neutral'

export const CENSUS_METRIC_RANK_DIRECTION: Record<string, CensusMetricRankDirection> = {
  median_household_income: 'higher',
  median_home_value: 'higher',
  median_gross_rent: 'neutral',
  per_capita_income: 'higher',
  total_population: 'neutral',
  median_age: 'neutral',
  gini_income_inequality: 'lower',
  median_gross_rent_pct_hhincome: 'lower',
  travel_time_to_work_minutes: 'lower',
  housing_units: 'neutral',
  poverty_universe: 'neutral',
  labor_force: 'higher',
}

export function censusMetricRankDirection(slug: string): CensusMetricRankDirection {
  return CENSUS_METRIC_RANK_DIRECTION[slug] ?? 'neutral'
}

/** Sort comparator so “better” values sort first (top of bar list). */
export function compareRankedMetricValues(a: number, b: number, slug: string): number {
  return censusMetricRankDirection(slug) === 'lower' ? a - b : b - a
}

/** One-line explanation under the winner callout. */
export function censusMetricWinnerCaption(slug: string, label: string): string {
  const d = censusMetricRankDirection(slug)
  if (d === 'higher') return `Highest ${label} ranks first (larger is better).`
  if (d === 'lower') return `Lowest ${label} ranks first (smaller is better).`
  return `Largest value ranks first (no default better/worse direction for this metric).`
}

/** Tooltip / aria text: data dictionary + table + how rankings interpret the metric. */
export function censusMetricFullHelp(
  slug: string,
  meta: { label: string; table?: string } | undefined,
): string {
  const label = meta?.label ?? slug
  const base = censusMetricHelpText(slug, label)
  const tbl = meta?.table ? `\n\nACS summary table: ${meta.table}.` : ''
  const d = censusMetricRankDirection(slug)
  const rank =
    d === 'higher'
      ? '\n\nRanking: higher values are treated as more favorable. The top bar list and winner use that order (largest first).'
      : d === 'lower'
        ? '\n\nRanking: lower values are treated as more favorable. The top bar list and winner use that order (smallest first).'
        : '\n\nRanking: the leaderboard orders by largest displayed value first. This metric has no built-in “higher or lower is always better” rule—use context when comparing places.'
  return `${base}${tbl}${rank}`
}

export const CENSUS_MAP_UI_HELP = {
  year: `The selected year is the end year of the ACS 5-year period. Each estimate pools five consecutive years of responses, so it is labeled by the latest year in that window (not a single calendar year snapshot).`,
  metric: 'Choose which ACS estimate to map. Values come from published Census tables (see each metric’s description).',
  vizFilled: 'Choropleth colors each region by the mapped value using the selected color transform.',
  vizBubble: 'Bubble map shows the same value as circle area at each region’s centroid; color also reflects magnitude.',
  scale: 'Nonlinear scales spread or compress the numeric range before mapping to color or bubble size (useful for skewed metrics).',
  mapValue:
    'Raw uses the published estimate. % change vs prior year compares to the previous year in the year slider order. % vs national compares to a U.S. or population-weighted benchmark when exported.',
  play: 'Animates through each year in the slider using the same metric and view settings.',
  allGeographiesTable:
    'Sortable list for the selected year and map value mode; numbers match the map. Click a row where supported to drill down.',
} as const
