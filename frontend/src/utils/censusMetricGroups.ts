/**
 * Topic taxonomy for the Census ACS metrics shown across the data explorer
 * (the scorecard's grouped rows and the map's metric browser sidebar both read
 * from this single source so the two stay in lockstep).
 *
 * The map exporter's ``manifest.json`` can publish metrics that aren't slotted
 * into a group yet; ``groupMetricsForBrowser`` funnels those into a trailing
 * "Other measures" bucket so a newly-added metric is never silently dropped
 * from the picker.
 */

export interface CensusMetricGroup {
  id: string
  title: string
  slugs: string[]
}

export const CENSUS_METRIC_GROUPS: CensusMetricGroup[] = [
  {
    id: 'income',
    title: 'Income & inequality',
    slugs: ['median_household_income', 'per_capita_income', 'gini_income_inequality'],
  },
  {
    id: 'housing',
    title: 'Housing',
    slugs: ['median_home_value', 'median_gross_rent', 'median_gross_rent_pct_hhincome', 'housing_units'],
  },
  {
    id: 'people',
    title: 'Population & age',
    slugs: ['total_population', 'median_age'],
  },
  {
    id: 'poverty_insurance',
    title: 'Poverty',
    slugs: ['population_income_below_poverty_level'],
  },
  {
    id: 'education',
    title: 'Education & enrollment',
    slugs: ['school_enrollment_total'],
  },
  {
    id: 'work',
    title: 'Work & commute',
    slugs: ['travel_time_to_work_minutes', 'labor_force', 'employed_civilian', 'unemployed_civilian'],
  },
]

const OTHER_GROUP_ID = 'other'
const OTHER_GROUP_TITLE = 'Other measures'

/** A metric paired with its display label, as resolved against the manifest. */
export interface CensusMetricGroupEntry {
  slug: string
  label: string
}

export interface CensusMetricBrowserGroup {
  id: string
  title: string
  metrics: CensusMetricGroupEntry[]
}

/**
 * Project a flat metric list (slug + label) into the ordered topic groups,
 * dropping empty groups and sweeping any ungrouped slug into "Other measures"
 * so the union of all rendered groups always equals the input set.
 */
export function groupMetricsForBrowser(
  metrics: ReadonlyArray<{ slug: string; label: string }>,
): CensusMetricBrowserGroup[] {
  const labelBySlug = new Map(metrics.map((m) => [m.slug, m.label] as const))
  const claimed = new Set<string>()

  const groups: CensusMetricBrowserGroup[] = []
  for (const g of CENSUS_METRIC_GROUPS) {
    const entries: CensusMetricGroupEntry[] = []
    for (const slug of g.slugs) {
      const label = labelBySlug.get(slug)
      if (label === undefined) continue
      claimed.add(slug)
      entries.push({ slug, label })
    }
    if (entries.length) groups.push({ id: g.id, title: g.title, metrics: entries })
  }

  const leftovers = metrics.filter((m) => !claimed.has(m.slug))
  if (leftovers.length) {
    groups.push({
      id: OTHER_GROUP_ID,
      title: OTHER_GROUP_TITLE,
      metrics: leftovers.map((m) => ({ slug: m.slug, label: m.label })),
    })
  }
  return groups
}

/** The group id that owns ``slug`` (for auto-expanding the active category). */
export function groupIdForMetric(slug: string): string {
  for (const g of CENSUS_METRIC_GROUPS) {
    if (g.slugs.includes(slug)) return g.id
  }
  return OTHER_GROUP_ID
}
