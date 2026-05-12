/**
 * Human-readable titles and “how to read” copy for the census explorer map and charts.
 *
 * Copy is built deterministically from metric, geography, year, viz, and value mode so it stays
 * correct when data or controls change. For optional AI-assisted wording later, POST a payload
 * shaped like {@link censusNarrativeContextPayload} to a narrative service and replace the
 * string fields in the UI while keeping the same structure.
 */
import type { CensusValueMode } from './censusMapValueMode'
import {
  nationalBaseline,
  prevVintageInList,
  trendCell,
  type NationalRefEntry,
} from './censusMapValueMode'
import { censusMetricRankDirection, type CensusMetricRankDirection } from './censusDataDictionary'

export const CENSUS_NARRATIVE_CONTEXT_VERSION = 1 as const

export type CensusNarrativeGeoLevel = 'us_states' | 'counties' | 'places'

export type CensusNarrativeContextPayload = {
  version: typeof CENSUS_NARRATIVE_CONTEXT_VERSION
  geoLevel: CensusNarrativeGeoLevel
  regionDisplayName: string
  metricSlug: string
  metricLabel: string
  displayVintage: string
  viz: 'filled' | 'bubble'
  valueMode: CensusValueMode
}

export function censusNarrativeContextPayload(input: Omit<CensusNarrativeContextPayload, 'version'>): CensusNarrativeContextPayload {
  return { version: CENSUS_NARRATIVE_CONTEXT_VERSION, ...input }
}

type NationalRefMap = Record<string, Record<string, NationalRefEntry>> | undefined

/** Short, conversational noun phrase for titles (lowercase for mid-sentence use). */
function everydayTopicForMetric(slug: string, metricLabel: string): string {
  const bySlug: Record<string, string> = {
    median_home_value: 'home values',
    median_household_income: 'household income',
    per_capita_income: 'income per person',
    median_gross_rent: 'typical rent',
    median_gross_rent_pct_hhincome: 'rent as a share of income',
    travel_time_to_work_minutes: 'commute time',
    total_population: 'population',
    median_age: 'median age',
    gini_income_inequality: 'income inequality',
    housing_units: 'housing stock',
    poverty_universe: 'population in poverty-rate statistics',
    labor_force: 'labor-force size',
  }
  const t = bySlug[slug]
  if (t) return t
  const s = metricLabel.trim()
  if (!s) return 'this measure'
  return s.charAt(0).toLowerCase() + s.slice(1)
}

function valueModeClause(mode: CensusValueMode): string {
  if (mode === 'raw') return 'Colors reflect the published survey estimate (adjusted on the map so differences are easier to see).'
  if (mode === 'yoy') return 'Colors show percent change versus the previous year on the year slider.'
  return 'Colors show how far above or below a national benchmark each area is (when that reference exists).'
}

function vizClause(viz: 'filled' | 'bubble'): string {
  return viz === 'filled'
    ? 'Each area is shaded from light to dark using the scale in the sidebar.'
    : 'Each area has a bubble at its center—bigger means a higher value on this measure; color matches the same scale.'
}

function nationalBenchmarkStory(
  metricSlug: string,
  metricLabel: string,
  nationalRef: NationalRefMap,
  vintages: string[] | undefined,
  displayVintage: string,
  rank: CensusMetricRankDirection,
): string | null {
  if (!nationalRef || !vintages?.length) return null
  const topic = everydayTopicForMetric(metricSlug, metricLabel)
  const vNow = nationalBaseline(nationalRef, displayVintage, metricSlug)
  if (vNow == null) return null

  const firstY = vintages[0]!
  const vFirst = nationalBaseline(nationalRef, firstY, metricSlug)
  if (vFirst != null && vFirst !== 0 && firstY !== displayVintage) {
    const pct = ((vNow - vFirst) / vFirst) * 100
    if (Math.abs(pct) < 0.85) {
      return `Nationwide, the benchmark for ${topic} was roughly flat between ${firstY} and ${displayVintage}.`
    }
    const mag = Math.abs(pct).toFixed(0)
    const rose = pct > 0
    if (rank === 'lower') {
      if (rose) {
        return `Nationwide, the benchmark for ${topic} rose about ${mag}% from ${firstY} to ${displayVintage} (for this measure, lower is usually better).`
      }
      return `Nationwide, the benchmark for ${topic} fell about ${mag}% from ${firstY} to ${displayVintage}.`
    }
    if (rank === 'higher') {
      if (rose) {
        return `Nationwide, the benchmark for ${topic} rose about ${mag}% from ${firstY} to ${displayVintage}.`
      }
      return `Nationwide, the benchmark for ${topic} fell about ${mag}% from ${firstY} to ${displayVintage}.`
    }
    return `Nationwide, the benchmark for ${topic} moved about ${pct > 0 ? '+' : ''}${pct.toFixed(0)}% from ${firstY} to ${displayVintage}.`
  }

  const prevY = prevVintageInList(vintages, displayVintage)
  if (!prevY) return null
  const vPrev = nationalBaseline(nationalRef, prevY, metricSlug)
  if (vPrev == null || vPrev === 0) return null
  const pct = ((vNow - vPrev) / vPrev) * 100
  if (Math.abs(pct) < 0.35) return null
  const mag = Math.abs(pct).toFixed(0)
  const rose = pct > 0
  if (rank === 'lower') {
    if (rose) return `Versus ${prevY}, the national benchmark for ${topic} ticked up about ${mag}% (lower is usually better for this measure).`
    return `Versus ${prevY}, the national benchmark for ${topic} eased down about ${mag}%.`
  }
  if (rank === 'higher') {
    if (rose) return `Versus ${prevY}, the national benchmark for ${topic} is up about ${mag}%.`
    return `Versus ${prevY}, the national benchmark for ${topic} is down about ${mag}%.`
  }
  return `Versus ${prevY}, the national benchmark for ${topic} shifted about ${pct > 0 ? '+' : ''}${pct.toFixed(0)}%.`
}

function buildFocusStateMapInsight(params: {
  stateName: string
  metricSlug: string
  metricLabel: string
  displayVintage: string
  vintages: string[]
  nationalRef: NationalRefMap
  stateMetricSeries: Record<string, unknown> | undefined
}): string | null {
  const { stateName, metricSlug, metricLabel, displayVintage, vintages, nationalRef, stateMetricSeries } = params
  const topic = everydayTopicForMetric(metricSlug, metricLabel)

  const rawNow = stateMetricSeries ? trendCell(stateMetricSeries, displayVintage) : null
  const prevY = prevVintageInList(vintages, displayVintage)
  const rawPrev = prevY && stateMetricSeries ? trendCell(stateMetricSeries, prevY) : null
  const nat = nationalBaseline(nationalRef, displayVintage, metricSlug)

  const chunks: string[] = []

  if (rawNow != null && rawPrev != null && rawPrev !== 0 && prevY) {
    const pct = ((rawNow - rawPrev) / rawPrev) * 100
    const mag = Math.abs(pct)
    if (mag < 0.65) {
      chunks.push(
        `${stateName}: statewide ${topic} was about flat from the ${prevY} to the ${displayVintage} ACS 5-year periods.`,
      )
    } else {
      const m = mag >= 10 ? mag.toFixed(0) : mag.toFixed(1)
      const up = pct > 0
      const phrase = up ? `rose about ${m}%` : `fell about ${m}%`
      chunks.push(
        `${stateName}: statewide ${topic} ${phrase} between the ${prevY} and ${displayVintage} survey end-years.`,
      )
    }
  }

  if (rawNow != null && nat != null && nat !== 0) {
    const rel = ((rawNow / nat) - 1) * 100
    const mag = Math.abs(rel)
    if (mag < 0.9) {
      chunks.push(`For ${displayVintage}, ${stateName} lines up with the national benchmark for this metric.`)
    } else {
      const m = mag >= 10 ? mag.toFixed(0) : mag.toFixed(1)
      if (rel > 0) {
        chunks.push(`For ${displayVintage}, ${stateName} is about ${m}% above the national benchmark on this measure.`)
      } else {
        chunks.push(`For ${displayVintage}, ${stateName} is about ${m}% below the national benchmark on this measure.`)
      }
    }
  }

  if (!chunks.length) return null
  return chunks.join(' ')
}

/**
 * Insight-first map titles: “where / how” + everyday topic + trend phrase + geography,
 * updated whenever metric, year (vintage), value mode, or drill level changes.
 */
function buildMapTitle(
  geoLevel: CensusNarrativeGeoLevel,
  regionDisplayName: string,
  topic: string,
  valueMode: CensusValueMode,
  rank: CensusMetricRankDirection,
  displayVintage: string,
): string {
  if (geoLevel === 'us_states') {
    if (valueMode === 'yoy')
      return `% change in ${topic} by state (${displayVintage} vs prior year)`
    if (valueMode === 'vs_natl')
      return `% vs national ${topic} by state (${displayVintage})`
    if (rank === 'higher') return `Highest ${topic} by state (${displayVintage})`
    if (rank === 'lower') return `Lowest ${topic} by state (${displayVintage})`
    return `${topic} by state (${displayVintage})`
  }
  const place = regionDisplayName
  if (geoLevel === 'counties') {
    if (valueMode === 'yoy')
      return `% change in ${topic} by county in ${place} (${displayVintage})`
    if (valueMode === 'vs_natl')
      return `% vs national ${topic} by county in ${place} (${displayVintage})`
    if (rank === 'higher') return `Highest ${topic} by county in ${place} (${displayVintage})`
    if (rank === 'lower') return `Lowest ${topic} by county in ${place} (${displayVintage})`
    return `${topic} by county in ${place} (${displayVintage})`
  }
  if (valueMode === 'yoy') return `% change in ${topic} by place in ${place} (${displayVintage})`
  if (valueMode === 'vs_natl')
    return `% vs national ${topic} by place in ${place} (${displayVintage})`
  if (rank === 'higher') return `Highest ${topic} by place in ${place} (${displayVintage})`
  if (rank === 'lower') return `Lowest ${topic} by place in ${place} (${displayVintage})`
  return `${topic} by place in ${place} (${displayVintage})`
}

function buildLeaderboardTitle(
  geoLevel: CensusNarrativeGeoLevel,
  regionDisplayName: string,
  topic: string,
  valueMode: CensusValueMode,
  rank: CensusMetricRankDirection,
  displayVintage: string,
): string {
  // Match the map heading strip: “Highest … by state”, “Lowest … by county in Alabama”, etc.
  // (Previously this panel used shorter “Top states: …” copy, which felt like a step back vs the map title.)
  return buildMapTitle(geoLevel, regionDisplayName, topic, valueMode, rank, displayVintage)
}

export type CensusNarrativePack = {
  mapTitle: string
  /** Shown under the map title when viewing a selected state (counties/places): trend vs prior period + vs national. */
  mapTitleInsight: string | null
  mapSubtitle: string
  mapCallouts: string[]
  leaderboardSectionTitle: string
  barChartCallouts: string[]
  trendChartSubtitle: string
  trendChartCallouts: string[]
}

/** Hover trend chart: “How … shifted between A and B” using non-null years in the series. */
export function buildCensusTrendChartTitle(
  areaDisplayName: string,
  metricSlug: string,
  metricLabel: string,
  points: { year: string; value: number | null }[],
): string {
  const topic = everydayTopicForMetric(metricSlug, metricLabel)
  const years = points
    .filter((p) => p.value != null)
    .map((p) => p.year)
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))
  if (years.length === 0) return `How ${topic} is trending in ${areaDisplayName}`
  if (years.length === 1) return `How ${topic} looks in ${areaDisplayName} (${years[0]})`
  const yStart = years[0]!
  const yEnd = years[years.length - 1]!
  if (yStart === yEnd) return `How ${topic} looks in ${areaDisplayName} (${yEnd})`
  return `How ${topic} shifted between ${yStart} and ${yEnd} in ${areaDisplayName}`
}

/** Trend panel copy when a specific place (hover or pinned row) is driving the chart. */
export function buildPlaceTrendNarrative(
  placeName: string,
  stateName: string,
  baseTrendCallouts: string[],
): { subtitle: string; readingLines: string[] } {
  const st = stateName.trim() || 'this state'
  return {
    subtitle: `Each year’s dot is ${placeName} in ${st} — same metric and map value mode as the map (5-year average ending in that survey year).`,
    readingLines: [
      `This line tracks ${placeName} only; the place map still compares all places in ${st}.`,
      ...baseTrendCallouts,
    ],
  }
}

export function buildCensusNarrativePack(input: {
  geoLevel: CensusNarrativeGeoLevel
  regionDisplayName: string
  metricLabel: string
  metricSlug: string
  displayVintage: string
  viz: 'filled' | 'bubble'
  valueMode: CensusValueMode
  nationalRef?: NationalRefMap
  vintages?: string[]
  /** When drilling into a state, drive location-specific insight from state trend series + national ref. */
  focusState?: {
    stateName: string
    stateFips: string
    stateMetricSeries: Record<string, unknown> | undefined
  } | null
  /** Pinned place row (place map): personalize leaderboard + bar “how to read” copy. */
  focusPlaceName?: string | null
  /** Pinned state row on the U.S. map: lead the map title with that state. */
  focusPinnedState?: { geoid: string; name: string } | null
  /** Pinned county row on the state county map: lead the map title with that county. */
  focusPinnedCounty?: { geoid: string; name: string } | null
}): CensusNarrativePack {
  const {
    geoLevel,
    regionDisplayName,
    metricLabel,
    metricSlug,
    displayVintage,
    viz,
    valueMode,
    nationalRef,
    vintages,
    focusState,
    focusPlaceName,
    focusPinnedState,
    focusPinnedCounty,
  } = input
  const rank = censusMetricRankDirection(metricSlug)
  const topic = everydayTopicForMetric(metricSlug, metricLabel)
  const natStory = nationalBenchmarkStory(metricSlug, metricLabel, nationalRef, vintages, displayVintage, rank)

  const rankHint =
    rank === 'higher'
      ? 'Darker or larger usually means a higher value on this measure (often “better,” but use your own judgment).'
      : rank === 'lower'
        ? 'Darker or larger still means a higher number here—but for this measure, lower is usually better (e.g., shorter commutes).'
        : 'There’s no built-in “higher is always better” rule for this measure—use the (i) tooltip for what the number means.'

  const geoNoun =
    geoLevel === 'us_states' ? 'states' : geoLevel === 'counties' ? 'counties' : 'places'

  const mapTitle = buildMapTitle(geoLevel, regionDisplayName, topic, valueMode, rank, displayVintage)

  const pinStateName = focusPinnedState?.name?.trim()
  const pinCountyName = focusPinnedCounty?.name?.trim()
  const pinPlaceName = focusPlaceName?.trim()

  let mapTitleResolved = mapTitle
  if (geoLevel === 'us_states' && pinStateName) {
    mapTitleResolved = `${pinStateName} — ${mapTitle}`
  } else if (geoLevel === 'counties' && pinCountyName) {
    mapTitleResolved = `${pinCountyName} — ${mapTitle}`
  } else if (geoLevel === 'places' && pinPlaceName) {
    mapTitleResolved = `${pinPlaceName} — ${mapTitle}`
  }

  let mapTitleInsight =
    geoLevel !== 'us_states' && focusState
      ? buildFocusStateMapInsight({
          stateName: focusState.stateName,
          metricSlug,
          metricLabel,
          displayVintage,
          vintages: vintages ?? [],
          nationalRef,
          stateMetricSeries: focusState.stateMetricSeries,
        })
      : null

  if (geoLevel === 'us_states' && pinStateName) {
    mapTitleInsight = `${pinStateName} is highlighted on the map and in the state list below; click the bar again to clear.`
  } else if (geoLevel === 'counties' && pinCountyName) {
    const line = `${pinCountyName} is outlined on the map and highlighted in the county list; click the bar again to clear.`
    mapTitleInsight = mapTitleInsight ? `${mapTitleInsight} ${line}` : line
  } else if (geoLevel === 'places' && pinPlaceName) {
    const line = `${pinPlaceName} is outlined on the map and highlighted in the place list; click the bar again to clear.`
    mapTitleInsight = mapTitleInsight ? `${mapTitleInsight} ${line}` : line
  }

  const surveyLine = `Source: U.S. Census Bureau American Community Survey (5-year results ending in ${displayVintage}) for ${geoNoun}.`
  const mapSubtitleParts = [surveyLine, vizClause(viz), valueModeClause(valueMode)]
  if (natStory) mapSubtitleParts.push(natStory)
  const mapSubtitle = mapSubtitleParts.join(' ')

  const mapCallouts: string[] = [
    rankHint,
    geoLevel === 'us_states'
      ? 'Hover a state for its value; click to open county-level maps where data exists.'
      : geoLevel === 'counties'
        ? 'Click a county to focus; zoom stays near that state so you don’t lose context.'
        : 'Hover a place for its value; the map stays zoomed near this state’s places.',
    viz === 'filled'
      ? 'Match colors to the legend ticks on the right to read values at a glance.'
      : 'Compare bubble sizes to the reference circles in the bubble legend on the right.',
  ]

  let leaderboardSectionTitle = buildLeaderboardTitle(
    geoLevel,
    regionDisplayName,
    topic,
    valueMode,
    rank,
    displayVintage,
  )
  if (geoLevel === 'us_states' && pinStateName) {
    leaderboardSectionTitle = `${leaderboardSectionTitle} — ${pinStateName} highlighted`
  }
  if (geoLevel === 'counties' && pinCountyName) {
    leaderboardSectionTitle = `${leaderboardSectionTitle} — ${pinCountyName} highlighted`
  }
  if (geoLevel === 'places' && pinPlaceName) {
    leaderboardSectionTitle = `${leaderboardSectionTitle} — ${pinPlaceName} highlighted`
  }

  const orderHint =
    rank === 'higher'
      ? 'The strip lists the strongest values first (what we treat as “leading” for this measure).'
      : rank === 'lower'
        ? 'The strip lists the smallest values first (what we treat as “best” when lower is better).'
        : 'The strip lists the largest values first; check the metric tooltip if “bigger” is good or bad.'

  const rowNoun =
    geoLevel === 'us_states' ? 'state' : geoLevel === 'counties' ? 'county' : 'place'
  const mapLinkLine = `Same numbers as the map for ${displayVintage} and the map value mode you picked.`
  const barChartCallouts = [
    mapLinkLine,
    ...(geoLevel === 'us_states' && pinStateName
      ? [
          `“${pinStateName}” is the highlighted row; the map outline matches it until you click that bar again to clear.`,
        ]
      : []),
    ...(geoLevel === 'counties' && pinCountyName
      ? [
          `“${pinCountyName}” is the highlighted row; the map outline matches it until you click that bar again to clear.`,
        ]
      : []),
    ...(geoLevel === 'places' && pinPlaceName
      ? [
          `“${pinPlaceName}” is the highlighted row; the map outline matches it until you click that bar again to clear.`,
        ]
      : []),
    orderHint,
    `Each row is one ${rowNoun}; bar length lines up with the horizontal number scale.`,
    'The right column repeats the value in a compact form so you can scan quickly.',
  ]

  const trendChartSubtitle = `Same measure as the map for one area, across every survey year loaded here (each point is still a 5-year average ending in that year).`

  const trendChartCallouts = [
    'Each dot is the Census estimate for that 5-year window ending in the year on the axis—not a single calendar year.',
    'Use the line to see whether things have been trending up, down, or holding steady before comparing peers on the map.',
    'Number formatting matches map tooltips for the underlying published values.',
  ]

  return {
    mapTitle: mapTitleResolved,
    mapTitleInsight,
    mapSubtitle,
    mapCallouts,
    leaderboardSectionTitle,
    barChartCallouts,
    trendChartSubtitle,
    trendChartCallouts,
  }
}
