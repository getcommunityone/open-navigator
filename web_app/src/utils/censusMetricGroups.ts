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
  /** Short header used as a sub-group label inside a theme (e.g. "Income"). */
  shortTitle?: string
  slugs: string[]
}

export const CENSUS_METRIC_GROUPS: CensusMetricGroup[] = [
  {
    id: 'income',
    title: 'Income & inequality',
    shortTitle: 'Income',
    slugs: ['median_household_income', 'per_capita_income', 'gini_income_inequality'],
  },
  {
    id: 'housing',
    title: 'Housing',
    shortTitle: 'Housing',
    slugs: ['median_home_value', 'median_gross_rent', 'median_gross_rent_pct_hhincome', 'housing_units'],
  },
  {
    id: 'people',
    title: 'Population & age',
    shortTitle: 'Population',
    slugs: ['total_population', 'median_age'],
  },
  {
    id: 'poverty_insurance',
    title: 'Poverty',
    shortTitle: 'Poverty',
    slugs: ['population_income_below_poverty_level', 'poverty_universe'],
  },
  {
    id: 'education',
    title: 'Education & enrollment',
    shortTitle: 'Education',
    slugs: ['school_enrollment_total', 'population_25_and_over_education_universe'],
  },
  {
    id: 'work',
    title: 'Work & commute',
    shortTitle: 'Jobs',
    slugs: ['travel_time_to_work_minutes', 'labor_force', 'employed_civilian', 'unemployed_civilian'],
  },
  {
    id: 'health',
    title: 'Health insurance',
    shortTitle: 'Insurance',
    slugs: ['health_insurance_civilian_noninstitutional_total', 'health_insurance_under19_table_total'],
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
  shortTitle?: string
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
    if (entries.length) groups.push({ id: g.id, title: g.title, shortTitle: g.shortTitle, metrics: entries })
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

// ── Themes ──────────────────────────────────────────────────────────────────
// A two-level grouping (theme → sub-groups → metrics) for the map's metric
// browser. Themes reference the flat groups above by id; an empty ``groupIds``
// renders an expandable "no metrics yet" placeholder (e.g. Crime/Government,
// which have no ACS metrics ingested). The scorecard keeps using the flat
// groups directly, so this layer is additive.

export interface CensusMetricTheme {
  id: string
  title: string
  groupIds: string[]
}

export const CENSUS_METRIC_THEMES: CensusMetricTheme[] = [
  { id: 'economy', title: 'Economy', groupIds: ['income', 'housing', 'work', 'poverty_insurance'] },
  { id: 'people', title: 'People', groupIds: ['people', 'education'] },
  { id: 'health', title: 'Health', groupIds: ['health'] },
  { id: 'crime', title: 'Crime', groupIds: [] },
  { id: 'government', title: 'Government', groupIds: [] },
]

export interface CensusMetricBrowserTheme {
  id: string
  title: string
  groups: CensusMetricBrowserGroup[]
}

/**
 * Project a flat metric list into the two-level theme structure. Reuses
 * ``groupMetricsForBrowser`` so the slug→group mapping (and the "Other" sweep)
 * stays in one place; any group not claimed by a theme — including "Other
 * measures" — is appended under a trailing "More measures" theme so the union
 * of all rendered metrics still equals the input set.
 */
export function groupMetricsByTheme(
  metrics: ReadonlyArray<{ slug: string; label: string }>,
): CensusMetricBrowserTheme[] {
  const browserGroups = groupMetricsForBrowser(metrics)
  const byId = new Map(browserGroups.map((g) => [g.id, g] as const))
  const used = new Set<string>()

  const themes: CensusMetricBrowserTheme[] = CENSUS_METRIC_THEMES.map((t) => {
    const groups: CensusMetricBrowserGroup[] = []
    for (const gid of t.groupIds) {
      const g = byId.get(gid)
      if (g) {
        groups.push(g)
        used.add(gid)
      }
    }
    return { id: t.id, title: t.title, groups }
  })

  const leftover = browserGroups.filter((g) => !used.has(g.id))
  if (leftover.length) {
    themes.push({ id: 'more', title: 'More measures', groups: leftover })
  }
  return themes
}

/** The theme id that owns ``slug`` (for auto-expanding the active theme). */
export function themeIdForMetric(slug: string): string {
  const gid = groupIdForMetric(slug)
  for (const t of CENSUS_METRIC_THEMES) {
    if (t.groupIds.includes(gid)) return t.id
  }
  return 'more'
}
