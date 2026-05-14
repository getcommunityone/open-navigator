import type { CensusValueMode } from './censusMapValueMode'

/**
 * Short ACS-style descriptions for census map UI tooltips (aligned with common subject-table wording).
 * Keys are metric slugs from ``manifest.json``; fallback copy is provided for unknown slugs.
 */

/** Plain-English entry points for the census map metric picker (non-technical framing). */
export const CENSUS_METRIC_EXPLORE_QUESTIONS: Record<string, string> = {
  median_household_income: 'How much do households earn?',
  median_home_value: 'What are typical home values?',
  median_gross_rent: 'What do renters pay?',
  per_capita_income: 'How much income per person?',
  total_population: 'Where do more people live?',
  median_age: 'How old is the population?',
  gini_income_inequality: 'How unequal is income?',
  median_gross_rent_pct_hhincome: 'How heavy is rent compared to income?',
  travel_time_to_work_minutes: 'How long are commutes?',
  housing_units: 'Where are there more housing units?',
  poverty_universe: 'What population is used for poverty stats?',
  labor_force: 'How large is the labor force?',
  sex_by_age_table_total: 'How large is the sex-by-age table total?',
  race_table_total: 'How large is the race table total?',
  hispanic_latino_by_race_total: 'How large is the Hispanic/Latino-by-race table total?',
  population_income_below_poverty_level: 'How many people are below the poverty line?',
  employed_civilian: 'How many people are employed (civilian 16+)?',
  unemployed_civilian: 'How many people are unemployed (civilian 16+)?',
  health_insurance_civilian_noninstitutional_total: 'How large is the health insurance coverage universe?',
  health_insurance_under19_table_total: 'How large is the under-19 health insurance table total?',
  population_25_and_over_education_universe: 'How many adults 25+ are in the education table?',
  school_enrollment_total: 'How many people are enrolled in school?',
}

/**
 * Table-total rows that duplicate population or universe counts — omitted from map metric pickers
 * (still present in ``manifest.json`` and payloads for compatibility).
 */
export const CENSUS_EXPLORER_HIDDEN_METRIC_SLUGS: ReadonlySet<string> = new Set([
  'sex_by_age_table_total',
  'race_table_total',
  'hispanic_latino_by_race_total',
])

export function censusMetricExploreQuestion(slug: string, label: string): string {
  const q = CENSUS_METRIC_EXPLORE_QUESTIONS[slug]
  if (q) return q
  const trimmed = label.trim()
  if (trimmed) return `How does ${trimmed} compare across places?`
  return 'What do you want to explore on the map?'
}

export type CensusChoroLegendSemantics = {
  /** Left side of the ramp (conceptual “low” end). */
  lowEnd: string
  /** Right side of the ramp (conceptual “high” end). */
  highEnd: string
  /** One short sentence tying color intensity to the metric. */
  gradientHint: string
}

/** Human-readable legend copy so users map color intensity to meaning (depends on value mode). */
export function censusChoroLegendSemantics(
  slug: string,
  valueMode: CensusValueMode,
  metricLabel: string,
): CensusChoroLegendSemantics {
  const ml = metricLabel.trim() || slug.replace(/_/g, ' ')
  if (valueMode === 'yoy') {
    return {
      lowEnd: 'Larger decrease',
      highEnd: 'Larger increase',
      gradientHint: 'Darker colors = larger increase vs the prior year in the year list (lighter = larger decrease).',
    }
  }
  if (valueMode === 'vs_natl') {
    return {
      lowEnd: 'Further below U.S.',
      highEnd: 'Further above U.S.',
      gradientHint: 'Darker colors = further above the national benchmark for this metric (when available).',
    }
  }
  if (slug === 'median_household_income') {
    return {
      lowEnd: 'Lower income',
      highEnd: 'Higher income',
      gradientHint: 'Darker colors = higher median household income on this scale.',
    }
  }
  if (slug === 'median_home_value' || slug === 'median_gross_rent' || slug === 'per_capita_income') {
    return {
      lowEnd: `Lower ${ml.toLowerCase()}`,
      highEnd: `Higher ${ml.toLowerCase()}`,
      gradientHint: `Darker colors = higher ${ml.toLowerCase()} on this scale.`,
    }
  }
  if (slug === 'median_gross_rent_pct_hhincome' && valueMode === 'raw') {
    return {
      lowEnd: 'Rent takes a smaller bite of income',
      highEnd: 'Rent takes a larger bite of income',
      gradientHint:
        'Each area is shaded by the published median rent-to-income ratio for renter households paying cash rent (ACS table B25071). Those medians are almost always under 100%. Huge “%” values mean the map bundle was built with the wrong table column—re-export census static data.',
    }
  }
  if (slug === 'gini_income_inequality') {
    if (valueMode === 'raw') {
      return {
        lowEnd: 'More equal (lower Gini)',
        highEnd: 'Less equal (higher Gini)',
        gradientHint:
          'Darker colors = higher inequality on this scale. The A–F row below ties the same 0–1 Gini index to those letters (lower is better).',
      }
    }
    return {
      lowEnd: `Lower ${ml.toLowerCase()}`,
      highEnd: `Higher ${ml.toLowerCase()}`,
      gradientHint: `Darker colors = higher ${ml.toLowerCase()} (not always “better”—read the metric notes).`,
    }
  }
  if (slug === 'travel_time_to_work_minutes') {
    return {
      lowEnd: `Lower ${ml.toLowerCase()}`,
      highEnd: `Higher ${ml.toLowerCase()}`,
      gradientHint: `Darker colors = higher ${ml.toLowerCase()} (not always “better”—read the metric notes).`,
    }
  }
  return {
    lowEnd: 'Lower values',
    highEnd: 'Higher values',
    gradientHint: `Darker colors = higher ${ml.toLowerCase()} along the mapped range.`,
  }
}

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
    'Median gross rent as a percent of household income for renter households paying cash rent (ACS table B25071). It is one median percentage for the area, not a sum across people. Typical state medians are often roughly 25–55%.',
  travel_time_to_work_minutes:
    'Mean travel time to work in minutes for workers 16+ who did not work from home (ACS subject table S0801). One-way usual commute.',
  housing_units:
    'Housing units — separate living quarters where people live or could live; includes occupied and vacant units.',
  poverty_universe:
    'Population for whom poverty status is determined — used as the denominator for poverty rate calculations in detailed tables.',
  labor_force:
    'Civilian labor force — people 16+ who are employed or unemployed and actively looked for work in the past four weeks.',
  sex_by_age_table_total:
    'Total row of ACS table B01001 (sex by age). Often close to total population; use B01003 for official population total.',
  race_table_total: 'Total row of ACS table B02001 (race).',
  hispanic_latino_by_race_total: 'Total row of ACS table B03002 (Hispanic or Latino origin by race).',
  population_income_below_poverty_level:
    'Count of people for whom poverty status is determined and whose income in the past 12 months was below the poverty threshold (B17001).',
  employed_civilian: 'Civilian employed population age 16+ (B23025).',
  unemployed_civilian: 'Civilian unemployed population age 16+ (B23025).',
  health_insurance_civilian_noninstitutional_total:
    'Civilian noninstitutionalized population — universe for detailed health insurance coverage (B27001).',
  health_insurance_under19_table_total:
    'Total row for ACS table B27010 (insurance coverage by age for children / under 19; exact universe follows Census labels for your vintage).',
  population_25_and_over_education_universe:
    'Population 25 years and over — universe for detailed educational attainment (B15003).',
  school_enrollment_total: 'Population enrolled in school — total from school enrollment by age (B14001).',
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
  sex_by_age_table_total: 'neutral',
  race_table_total: 'neutral',
  hispanic_latino_by_race_total: 'neutral',
  population_income_below_poverty_level: 'lower',
  employed_civilian: 'higher',
  unemployed_civilian: 'lower',
  health_insurance_civilian_noninstitutional_total: 'neutral',
  health_insurance_under19_table_total: 'neutral',
  population_25_and_over_education_universe: 'neutral',
  school_enrollment_total: 'neutral',
}

export function censusMetricRankDirection(slug: string): CensusMetricRankDirection {
  return CENSUS_METRIC_RANK_DIRECTION[slug] ?? 'neutral'
}

/**
 * Detects obviously wrong **raw** bundles (e.g. wrong ACS column in older exports) so we can warn instead of
 * letting users interpret garbage numbers.
 */
export function censusMetricStaleDataNote(
  slug: string,
  valueMode: CensusValueMode,
  rawValues: (number | null | undefined)[],
): string | null {
  if (valueMode !== 'raw') return null
  const nums = rawValues.filter((x): x is number => typeof x === 'number' && Number.isFinite(x))
  if (nums.length < 8) return null
  if (slug === 'median_gross_rent_pct_hhincome') {
    const hi = Math.max(...nums)
    if (hi > 100) {
      return 'Rent-to-income values above 100% usually mean this bundle was built from the wrong Census column (B25070 “total renters” instead of B25071 “median rent % of income”). From the repo root, re-download B25071 parquets and run .venv/bin/python scripts/datasources/census/export_census_map_static.py for your year(s), then hard-refresh the app.'
    }
  }
  if (slug === 'travel_time_to_work_minutes') {
    const hi = Math.max(...nums)
    if (hi > 240) {
      return 'Commute “times” in the hundreds of hours usually mean worker counts were mistaken for minutes (wrong S0801 column in an older export). Re-download S0801 and re-run export_census_map_static.py with the current script, then hard-refresh.'
    }
  }
  return null
}

/** Sort comparator so “better” values sort first (top of bar list). */
export function compareRankedMetricValues(a: number, b: number, slug: string): number {
  return censusMetricRankDirection(slug) === 'lower' ? a - b : b - a
}

/** One-line explanation under the winner callout (keep short — sits under “#1 for this metric”). */
export function censusMetricWinnerCaption(slug: string): string {
  const d = censusMetricRankDirection(slug)
  if (d === 'higher') return 'Higher values rank first.'
  if (d === 'lower') return 'Lower values rank first.'
  return 'Ordered by largest value first.'
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

/** Slugs where we omit the “Census label:” line under the map picker (universe / table totals; redundant with the dropdown). */
const CENSUS_MAP_SLUGS_HIDE_OFFICIAL_LABEL = new Set([
  'population_25_and_over_education_universe',
  'health_insurance_under19_table_total',
  'health_insurance_civilian_noninstitutional_total',
  'poverty_universe',
])

export function censusMapShowOfficialCensusLabel(slug: string): boolean {
  return !CENSUS_MAP_SLUGS_HIDE_OFFICIAL_LABEL.has(slug)
}

export const CENSUS_MAP_UI_HELP = {
  year: `The selected year is the end year of the ACS 5-year period. Each estimate pools five consecutive years of responses, so it is labeled by the latest year in that window (not a single calendar year snapshot).`,
  metric:
    'Pick the question you want to answer on the map. Each topic uses published Census ACS tables — open the (i) next to the picker for definitions.',
  vizFilled: 'Choropleth colors each region by the mapped value using the selected color transform.',
  vizBubble: 'Bubble map shows the same value as circle area at each region’s centroid; color also reflects magnitude.',
  scale: 'Nonlinear scales spread or compress the numeric range before mapping to color or bubble size (useful for skewed metrics).',
  mapValue:
    'Raw uses the published estimate. % change vs prior year compares to the previous year in the year slider order. % vs national compares to a U.S. or population-weighted benchmark when exported.',
  play: 'Plays once through each year (oldest to newest) using the same metric and view, then stops.',
  allGeographiesTable:
    'Sortable list for the selected year and map value mode; numbers match the map. Click a row where supported to drill down.',
} as const
