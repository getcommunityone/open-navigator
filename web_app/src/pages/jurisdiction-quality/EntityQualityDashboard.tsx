/**
 * Entity-first jurisdiction mapping quality dashboard (layout inspired by internal mock:
 * entity tiles (incl. State) → Overview / By population / By income tabs directly under the selected tile.
 * Uses live JSON from export_jurisdiction_mapping_quality_json.py including entity_state_rollup.
 * Styling stays on the light `.jmq-quality-page` tokens — do not switch the page to a dark/black background.
 */
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import {
  ArrowLeftIcon,
  ChevronDownIcon,
  InformationCircleIcon,
} from '@heroicons/react/24/outline'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useQuery } from '@tanstack/react-query'
import {
  fetchUnmappedJurisdictions,
  type UnmappedDrillParams,
} from '../../api/jurisdictionMappingUnmapped'
import {
  fetchMissingYoutubeChannels,
  type MissingYoutubeDrillParams,
} from '../../api/jurisdictionMappingMissingYoutube'
import { DATA_EXPLORER_MAP_BASE } from '../../utils/dataExplorerPaths'
import {
  fetchYoutubeChannelCoverage,
  fetchYoutubeStateRollup,
} from '../../api/jurisdictionMappingYoutubeDiagnostics'
import { formatCompactNumber, formatFullNumber } from '../../utils/formatCompact'
import CountyYoutubeDiagnosticsSection from './CountyYoutubeDiagnosticsSection'
import StateYoutubeCategorySection from './StateYoutubeCategorySection'

const US_STATE_NAMES: Record<string, string> = {
  AL: 'Alabama',
  AK: 'Alaska',
  AZ: 'Arizona',
  AR: 'Arkansas',
  CA: 'California',
  CO: 'Colorado',
  CT: 'Connecticut',
  DE: 'Delaware',
  FL: 'Florida',
  GA: 'Georgia',
  HI: 'Hawaii',
  ID: 'Idaho',
  IL: 'Illinois',
  IN: 'Indiana',
  IA: 'Iowa',
  KS: 'Kansas',
  KY: 'Kentucky',
  LA: 'Louisiana',
  ME: 'Maine',
  MD: 'Maryland',
  MA: 'Massachusetts',
  MI: 'Michigan',
  MN: 'Minnesota',
  MS: 'Mississippi',
  MO: 'Missouri',
  MT: 'Montana',
  NE: 'Nebraska',
  NV: 'Nevada',
  NH: 'New Hampshire',
  NJ: 'New Jersey',
  NM: 'New Mexico',
  NY: 'New York',
  NC: 'North Carolina',
  ND: 'North Dakota',
  OH: 'Ohio',
  OK: 'Oklahoma',
  OR: 'Oregon',
  PA: 'Pennsylvania',
  RI: 'Rhode Island',
  SC: 'South Carolina',
  SD: 'South Dakota',
  TN: 'Tennessee',
  TX: 'Texas',
  UT: 'Utah',
  VT: 'Vermont',
  VA: 'Virginia',
  WA: 'Washington',
  WV: 'West Virginia',
  WI: 'Wisconsin',
  WY: 'Wyoming',
}

type SummaryRow = {
  jurisdiction_type: string
  total_jurisdictions: number
  with_primary_website: number
  pct_with_primary_website: number | null
  with_primary_url_syntax_ok?: number
  with_primary_url_likely_wrong_host?: number
  jurisdictions_touching_naco: number
  jurisdictions_touching_uscm: number
  jurisdictions_touching_nces: number
  jurisdictions_touching_gsa: number
  jurisdictions_touching_league: number
  jurisdictions_touching_wikidata: number
  jurisdictions_touching_override: number
  primary_from_naco?: number
  primary_from_uscm?: number
  primary_from_nces_directory?: number
  primary_from_gsa?: number
  primary_from_league?: number
  primary_from_wikidata?: number
  primary_from_override?: number
  with_youtube_channel?: number
  pct_with_youtube_channel?: number | null
}

type MunicipalityPlaceSummaryRow = {
  municipality_place_kind: string
  total_jurisdictions: number
  with_primary_website: number
  pct_with_primary_website: number | null
  with_primary_url_syntax_ok?: number
  jurisdictions_touching_naco: number
  jurisdictions_touching_uscm: number
  jurisdictions_touching_nces: number
  jurisdictions_touching_gsa: number
  jurisdictions_touching_league: number
  jurisdictions_touching_wikidata: number
  jurisdictions_touching_override: number
  primary_from_naco?: number
  primary_from_uscm?: number
  primary_from_nces_directory?: number
  primary_from_gsa?: number
  primary_from_league?: number
  primary_from_wikidata?: number
  primary_from_override?: number
  with_youtube_channel?: number
  pct_with_youtube_channel?: number | null
}

type YoutubeStateRollupRow = {
  state_code: string
  total_jurisdictions: number
  with_youtube_channel: number
  pct_with_youtube_channel: number | null
}

type SourceRow = { website_source: string; distinct_jurisdictions: number }

type StateRollupRow = {
  state_code: string
  total_jurisdictions: number
  with_primary_website: number
  pct_with_primary_website: number | null
}

/** One row per state: ACS tiers + whether the state-government row has a primary portal URL. */
export type StateQualityRow = {
  state_code: string
  state_fips: string
  state_name: string
  acs_population: number | null
  acs_median_household_income: number | null
  state_population_tier: string | null
  state_income_level: string | null
  /** Always 1 — one state government per row. */
  total_jurisdictions: number
  /** 0 or 1 — primary URL on ``jurisdiction_type = 'state'``. */
  with_primary_website: number
  pct_with_primary_website: number | null
  has_state_portal?: boolean
  primary_website_url?: string | null
  primary_website_source?: string | null
  n_website_candidate_rows?: number
  has_gsa_source?: boolean
  has_override_source?: boolean
  website_candidates?: { source: string; url: string }[]
}

type StateBucketSummaryRow = {
  state_population_tier?: string
  state_income_level?: string
  state_count: number
  total_jurisdictions: number
  with_primary_website: number
  pct_with_primary_website: number | null
}

const STATE_POPULATION_TIER_ORDER = [
  'Very Large',
  'Large',
  'Major Mid-Sized',
  'Mid-Sized',
  'Small',
] as const

const STATE_INCOME_TIER_ORDER = ['High Earner', 'Middle Class', 'Lower Middle', 'Low Income'] as const

type UnmappedDrillRow = {
  jurisdiction_id: string
  name: string
  state_code: string
  jurisdiction_type: string
  geoid?: string | null
  municipality_place_kind?: string | null
  n_website_candidate_rows?: number | null
  has_naco_source?: boolean | null
  has_uscm_source?: boolean | null
  has_nces_directory_source?: boolean | null
  has_gsa_source?: boolean | null
  has_league_source?: boolean | null
  has_wikidata_source?: boolean | null
  has_override_source?: boolean | null
  acs_population_tier?: string | null
  acs_income_level?: string | null
}

type MappedUrlIssueDrillRow = UnmappedDrillRow & {
  primary_website_url: string | null
  primary_website_source: string | null
  primary_url_syntax_ok: boolean | null
  primary_url_likely_wrong_host: boolean | null
  primary_url_passes_basic_checks: boolean | null
}

type DrilldownPayload = {
  unmapped: UnmappedDrillRow[]
  mapped_url_issues: MappedUrlIssueDrillRow[]
}

export type QualityPayload = {
  generated_at: string | null
  database_host?: string | null
  summary_by_type: SummaryRow[]
  summary_municipality_by_place_kind?: MunicipalityPlaceSummaryRow[]
  summary_by_acs_population_tier?: {
    jurisdiction_type: string
    acs_population_tier: string
    total_jurisdictions: number
    with_primary_website: number
    pct_with_primary_website: number | null
  }[]
  summary_by_acs_income_level?: {
    jurisdiction_type: string
    acs_income_level: string
    total_jurisdictions: number
    with_primary_website: number
    pct_with_primary_website: number | null
  }[]
  candidates_by_source: SourceRow[]
  n_source_detail_rows?: number
  sources_explained?: Record<string, string>
  drilldown?: DrilldownPayload
  entity_state_rollup?: {
    county: StateRollupRow[]
    municipality_incorporated_city: StateRollupRow[]
    municipality_towns_and_cdp: StateRollupRow[]
    school_district: StateRollupRow[]
  }
  youtube_entity_state_rollup?: {
    county: YoutubeStateRollupRow[]
    municipality_incorporated_city: YoutubeStateRollupRow[]
    municipality_towns_and_cdp: YoutubeStateRollupRow[]
  }
  state_youtube_category_rollup?: {
    categories: string[]
    by_category: Record<
      string,
      {
        state_code: string
        state_name: string
        category: string
        mapped: boolean
        youtube_channel_url?: string | null
        channel_id?: string | null
        channel_title?: string | null
        channel_type?: string | null
        discovery_method?: string | null
        match_score?: number | null
        confidence_score?: number | null
      }[]
    >
    summary?: Record<
      string,
      {
        total_states: number
        mapped: number
        missing: number
        pct_mapped: number | null
      }
    >
    explained?: {
      source_table?: string | null
      categories?: Record<string, string>
      classification?: string
    }
  }
  acs_vintage_year?: string | null
  acs_source?: string | null
  states?: StateQualityRow[]
  summary_by_state_population_tier?: StateBucketSummaryRow[]
  summary_by_state_income_level?: StateBucketSummaryRow[]
  state_population_tiers_explained?: Record<string, string>
  state_income_levels_explained?: Record<string, string>
  /** ACS bucket rollups scoped to each entity slice (cities = incorporated cities only, etc.). */
  entity_acs_by_slice?: Partial<
    Record<
      Exclude<EntityKey, 'state'>,
      {
        by_population_tier: {
          bucket: string
          total_jurisdictions: number
          with_primary_website: number
          pct_with_primary_website: number | null
          primary_from_naco?: number
          primary_from_uscm?: number
          primary_from_nces_directory?: number
          primary_from_gsa?: number
          primary_from_league?: number
          primary_from_wikidata?: number
          primary_from_override?: number
        }[]
        by_income_level: {
          bucket: string
          total_jurisdictions: number
          with_primary_website: number
          pct_with_primary_website: number | null
          primary_from_naco?: number
          primary_from_uscm?: number
          primary_from_nces_directory?: number
          primary_from_gsa?: number
          primary_from_league?: number
          primary_from_wikidata?: number
          primary_from_override?: number
        }[]
      }
    >
  >
  /** Per-bucket unmapped rows (Postgres); aligns with population/income table missing counts. */
  entity_acs_unmapped_drill?: Partial<
    Record<
      Exclude<EntityKey, 'state'>,
      {
        by_population_tier: Record<string, UnmappedDrillRow[]>
        by_income_level: Record<string, UnmappedDrillRow[]>
      }
    >
  >
  entity_acs_bucket_drill_cap?: number
}

export type EntityKey = 'cities' | 'towns' | 'counties' | 'schools' | 'state'

const ENTITY_ROLLUP_KEY: Record<Exclude<EntityKey, 'state'>, keyof NonNullable<QualityPayload['entity_state_rollup']>> = {
  cities: 'municipality_incorporated_city',
  towns: 'municipality_towns_and_cdp',
  counties: 'county',
  schools: 'school_district',
}

const ENTITY_YOUTUBE_ROLLUP_KEY: Record<
  Exclude<EntityKey, 'state' | 'schools'>,
  keyof NonNullable<QualityPayload['youtube_entity_state_rollup']>
> = {
  cities: 'municipality_incorporated_city',
  towns: 'municipality_towns_and_cdp',
  counties: 'county',
}

const YOUTUBE_ENTITY_KEYS = new Set<EntityKey>(['cities', 'towns', 'counties'])

function stateRowsToRollup(states: StateQualityRow[]): StateRollupRow[] {
  return states.map((s) => ({
    state_code: s.state_code,
    total_jurisdictions: s.total_jurisdictions,
    with_primary_website: s.with_primary_website,
    pct_with_primary_website: s.pct_with_primary_website,
  }))
}

function stateBucketChartRows(
  summaries: StateBucketSummaryRow[] | undefined,
  tierKey: 'state_population_tier' | 'state_income_level',
  order: readonly string[],
): { bucket: string; n: number; withUrl: number; pct: number; missing: number; stateCount: number }[] {
  if (!summaries?.length) return []
  const byTier = new Map(summaries.map((r) => [String(r[tierKey] ?? ''), r]))
  return order
    .map((tier) => {
      const r = byTier.get(tier)
      if (!r) return null
      const n = Number(r.total_jurisdictions)
      const withUrl = Number(r.with_primary_website)
      const pct = r.pct_with_primary_website != null ? Number(r.pct_with_primary_website) : n > 0 ? (100 * withUrl) / n : 0
      return {
        bucket: tier,
        n,
        withUrl,
        pct,
        missing: Math.max(0, n - withUrl),
        stateCount: Number(r.state_count),
      }
    })
    .filter((x): x is NonNullable<typeof x> => x != null && x.n > 0)
}

function stateBucketTableRows(
  summaries: StateBucketSummaryRow[] | undefined,
  tierKey: 'state_population_tier' | 'state_income_level',
  order: readonly string[],
): { bucket: string; tierValue: string; n: number; withUrl: number; pct: number; missing: number }[] {
  return stateBucketChartRows(summaries, tierKey, order).map((r) => ({
    bucket: `${r.bucket} (${r.stateCount} states)`,
    tierValue: r.bucket,
    n: r.n,
    withUrl: r.withUrl,
    pct: r.pct,
    missing: r.missing,
  }))
}

function fmtPop(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return '—'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${Math.round(n / 1_000)}k`
  return fmt(n)
}

const ENTITY_META: Record<
  EntityKey,
  { label: string; icon: string; accentVar: string; sourceKeys: string[] }
> = {
  state: {
    label: 'State',
    icon: '📍',
    accentVar: '--jmq-teal',
    sourceKeys: ['gsa', 'override'],
  },
  cities: {
    label: 'Cities',
    icon: '🏙',
    accentVar: '--jmq-amber',
    sourceKeys: ['uscm', 'league', 'gsa', 'wikidata', 'override'],
  },
  towns: {
    label: 'Towns & Villages',
    icon: '🏘',
    accentVar: '--jmq-red',
    sourceKeys: ['gsa', 'wikidata', 'override'],
  },
  counties: {
    label: 'Counties',
    icon: '🗺',
    accentVar: '--jmq-teal',
    sourceKeys: ['naco', 'gsa', 'wikidata', 'override'],
  },
  schools: {
    label: 'School Districts',
    icon: '🏫',
    accentVar: '--jmq-blue',
    sourceKeys: ['nces_directory', 'gsa', 'override'],
  },
}

function fmt(n: number): string {
  return Number(n).toLocaleString()
}

function fmtCompact(n: number): string {
  return formatCompactNumber(n)
}

function exportHasYoutubeChannelMetrics(data: QualityPayload): boolean {
  const county = data.summary_by_type?.find((x) => x.jurisdiction_type === 'county')
  return county != null && county.with_youtube_channel != null
}

function youtubeDiagnosticsEntity(entity: EntityKey): 'counties' | 'cities' | 'towns' | null {
  if (entity === 'counties' || entity === 'cities' || entity === 'towns') return entity
  return null
}

/** Shared Y-axis title for bar charts that plot share with a primary website URL. */
const AXIS_LABEL_PCT_WITH_PRIMARY_URL = '% with primary URL'

function barColor(p: number): string {
  if (p >= 80) return '#117a72'
  if (p >= 50) return '#0969da'
  if (p >= 25) return '#9a6700'
  return '#a40e26'
}

function aggregateMuniKinds(
  rows: MunicipalityPlaceSummaryRow[] | undefined,
  kinds: string[],
): {
  total: number
  withUrl: number
  pct: number
  syntaxOk: number
  touch: Pick<
    MunicipalityPlaceSummaryRow,
    | 'jurisdictions_touching_naco'
    | 'jurisdictions_touching_uscm'
    | 'jurisdictions_touching_nces'
    | 'jurisdictions_touching_gsa'
    | 'jurisdictions_touching_league'
    | 'jurisdictions_touching_wikidata'
    | 'jurisdictions_touching_override'
  >
} {
  let total = 0
  let withUrl = 0
  let syntaxOk = 0
  const touch = { naco: 0, uscm: 0, nces: 0, gsa: 0, league: 0, wikidata: 0, override: 0 }
  for (const r of rows ?? []) {
    if (!kinds.includes(r.municipality_place_kind)) continue
    total += Number(r.total_jurisdictions)
    withUrl += Number(r.with_primary_website)
    syntaxOk += Number(r.with_primary_url_syntax_ok ?? 0)
    touch.naco += Number(r.jurisdictions_touching_naco)
    touch.uscm += Number(r.jurisdictions_touching_uscm)
    touch.nces += Number(r.jurisdictions_touching_nces)
    touch.gsa += Number(r.jurisdictions_touching_gsa)
    touch.league += Number(r.jurisdictions_touching_league)
    touch.wikidata += Number(r.jurisdictions_touching_wikidata ?? 0)
    touch.override += Number(r.jurisdictions_touching_override)
  }
  const pct = total > 0 ? (100 * withUrl) / total : 0
  return {
    total,
    withUrl,
    pct,
    syntaxOk,
    touch: {
      jurisdictions_touching_naco: touch.naco,
      jurisdictions_touching_uscm: touch.uscm,
      jurisdictions_touching_nces: touch.nces,
      jurisdictions_touching_gsa: touch.gsa,
      jurisdictions_touching_league: touch.league,
      jurisdictions_touching_wikidata: touch.wikidata,
      jurisdictions_touching_override: touch.override,
    },
  }
}

function aggregateMuniPrimaryFrom(
  rows: MunicipalityPlaceSummaryRow[] | undefined,
  kinds: string[],
): PrimarySourceRow | null {
  let total = 0
  const sums = {
    primary_from_naco: 0,
    primary_from_uscm: 0,
    primary_from_nces_directory: 0,
    primary_from_gsa: 0,
    primary_from_league: 0,
    primary_from_wikidata: 0,
    primary_from_override: 0,
  }
  for (const r of rows ?? []) {
    if (!kinds.includes(r.municipality_place_kind)) continue
    total += Number(r.total_jurisdictions)
    sums.primary_from_naco += Number(r.primary_from_naco ?? 0)
    sums.primary_from_uscm += Number(r.primary_from_uscm ?? 0)
    sums.primary_from_nces_directory += Number(r.primary_from_nces_directory ?? 0)
    sums.primary_from_gsa += Number(r.primary_from_gsa ?? 0)
    sums.primary_from_league += Number(r.primary_from_league ?? 0)
    sums.primary_from_wikidata += Number(r.primary_from_wikidata ?? 0)
    sums.primary_from_override += Number(r.primary_from_override ?? 0)
  }
  if (total === 0) return null
  return {
    jurisdiction_type: 'municipality',
    total_jurisdictions: total,
    with_primary_website: Object.values(sums).reduce((a, b) => a + b, 0),
    pct_with_primary_website: null,
    jurisdictions_touching_naco: 0,
    jurisdictions_touching_uscm: 0,
    jurisdictions_touching_nces: 0,
    jurisdictions_touching_gsa: 0,
    jurisdictions_touching_league: 0,
    jurisdictions_touching_wikidata: 0,
    jurisdictions_touching_override: 0,
    ...sums,
  }
}

/** State tile: count of state governments with a mapped primary portal (not local jurisdictions). */
function stateGovMetrics(states: StateQualityRow[]): {
  total: number
  withUrl: number
  pct: number
  syntaxErr: number
  touch: SummaryRow | null
} {
  const total = states.length
  const withUrl = states.filter((s) => Number(s.with_primary_website) > 0).length
  const pct = total > 0 ? (100 * withUrl) / total : 0
  return { total, withUrl, pct, syntaxErr: 0, touch: null }
}

function metricsFromRollupRow(row: StateRollupRow): {
  total: number
  withUrl: number
  pct: number
  syntaxErr: number
  touch: SummaryRow | null
} {
  const total = Number(row.total_jurisdictions)
  const withUrl = Number(row.with_primary_website)
  const pct =
    row.pct_with_primary_website != null ? Number(row.pct_with_primary_website) : total > 0 ? (100 * withUrl) / total : 0
  return { total, withUrl, pct, syntaxErr: 0, touch: null }
}

function entityMetrics(
  entity: EntityKey,
  summaryByType: SummaryRow[],
  muniRows: MunicipalityPlaceSummaryRow[] | undefined,
): {
  total: number
  withUrl: number
  pct: number
  syntaxErr: number
  touch: MunicipalityPlaceSummaryRow | SummaryRow | null
} {
  if (entity === 'counties') {
    const r = summaryByType.find((x) => x.jurisdiction_type === 'county')
    if (!r) return { total: 0, withUrl: 0, pct: 0, syntaxErr: 0, touch: null }
    const w = Number(r.with_primary_website)
    const syn = Number(r.with_primary_url_syntax_ok ?? 0)
    return {
      total: Number(r.total_jurisdictions),
      withUrl: w,
      pct: Number(r.pct_with_primary_website ?? 0),
      syntaxErr: Math.max(0, w - syn),
      touch: r,
    }
  }
  if (entity === 'schools') {
    const r = summaryByType.find((x) => x.jurisdiction_type === 'school_district')
    if (!r) return { total: 0, withUrl: 0, pct: 0, syntaxErr: 0, touch: null }
    const w = Number(r.with_primary_website)
    const syn = Number(r.with_primary_url_syntax_ok ?? 0)
    return {
      total: Number(r.total_jurisdictions),
      withUrl: w,
      pct: Number(r.pct_with_primary_website ?? 0),
      syntaxErr: Math.max(0, w - syn),
      touch: r,
    }
  }
  if (entity === 'cities') {
    const row = muniRows?.find((x) => x.municipality_place_kind === 'incorporated_city')
    if (!row) return { total: 0, withUrl: 0, pct: 0, syntaxErr: 0, touch: null }
    const w = Number(row.with_primary_website)
    const syn = Number(row.with_primary_url_syntax_ok ?? 0)
    return {
      total: Number(row.total_jurisdictions),
      withUrl: w,
      pct: Number(row.pct_with_primary_website ?? 0),
      syntaxErr: Math.max(0, w - syn),
      touch: row,
    }
  }
  const agg = aggregateMuniKinds(muniRows, ['incorporated_other', 'unknown', 'census_designated_place'])
  const syntaxErr = Math.max(0, agg.withUrl - agg.syntaxOk)
  return { total: agg.total, withUrl: agg.withUrl, pct: agg.pct, syntaxErr, touch: null }
}

function youtubeEntityMetrics(
  entity: EntityKey,
  summaryByType: SummaryRow[],
  muniRows: MunicipalityPlaceSummaryRow[] | undefined,
): { total: number; withChannel: number; pct: number } {
  if (!YOUTUBE_ENTITY_KEYS.has(entity)) return { total: 0, withChannel: 0, pct: 0 }
  if (entity === 'counties') {
    const r = summaryByType.find((x) => x.jurisdiction_type === 'county')
    if (!r) return { total: 0, withChannel: 0, pct: 0 }
    const withChannel = Number(r.with_youtube_channel ?? 0)
    return {
      total: Number(r.total_jurisdictions),
      withChannel,
      pct: Number(r.pct_with_youtube_channel ?? 0),
    }
  }
  if (entity === 'cities') {
    const row = muniRows?.find((x) => x.municipality_place_kind === 'incorporated_city')
    if (!row) return { total: 0, withChannel: 0, pct: 0 }
    const withChannel = Number(row.with_youtube_channel ?? 0)
    return {
      total: Number(row.total_jurisdictions),
      withChannel,
      pct: Number(row.pct_with_youtube_channel ?? 0),
    }
  }
  let total = 0
  let withChannel = 0
  for (const r of muniRows ?? []) {
    if (!['incorporated_other', 'unknown', 'census_designated_place'].includes(r.municipality_place_kind)) continue
    total += Number(r.total_jurisdictions)
    withChannel += Number(r.with_youtube_channel ?? 0)
  }
  const pct = total > 0 ? (100 * withChannel) / total : 0
  return { total, withChannel, pct }
}

function metricsFromYoutubeRollupRow(row: YoutubeStateRollupRow): {
  total: number
  withChannel: number
  pct: number
} {
  const total = Number(row.total_jurisdictions)
  const withChannel = Number(row.with_youtube_channel)
  const pct =
    row.pct_with_youtube_channel != null
      ? Number(row.pct_with_youtube_channel)
      : total > 0
        ? (100 * withChannel) / total
        : 0
  return { total, withChannel, pct }
}

type PrimarySourceRow = SummaryRow | MunicipalityPlaceSummaryRow

const PRIMARY_SOURCE_DEFS: {
  sourceKey: string
  field: keyof Pick<
    SummaryRow,
    | 'primary_from_naco'
    | 'primary_from_uscm'
    | 'primary_from_nces_directory'
    | 'primary_from_gsa'
    | 'primary_from_league'
    | 'primary_from_wikidata'
    | 'primary_from_override'
  >
  label: string
  fill: string
}[] = [
  { sourceKey: 'naco', field: 'primary_from_naco', label: 'NACo', fill: '#6e40c9' },
  { sourceKey: 'uscm', field: 'primary_from_uscm', label: 'USCM', fill: '#0969da' },
  { sourceKey: 'nces_directory', field: 'primary_from_nces_directory', label: 'NCES', fill: '#117a72' },
  { sourceKey: 'gsa', field: 'primary_from_gsa', label: 'GSA', fill: '#9a6700' },
  { sourceKey: 'league', field: 'primary_from_league', label: 'League', fill: '#8250df' },
  { sourceKey: 'wikidata', field: 'primary_from_wikidata', label: 'Wikidata', fill: '#990055' },
  { sourceKey: 'override', field: 'primary_from_override', label: 'Override', fill: '#116329' },
]

function sourceMappingRateRows(
  row: PrimarySourceRow | null,
  total: number,
  withUrl: number,
  entity: EntityKey,
  opts?: { includeZero?: boolean },
): { sourceKey: string; label: string; mapped: number; pctTotal: number; pctMapped: number; fill: string }[] {
  if (!row || total <= 0) return []
  const allowed = new Set(ENTITY_META[entity].sourceKeys)
  const rows = PRIMARY_SOURCE_DEFS.filter((d) => allowed.has(d.sourceKey)).map((d) => {
    const mapped = Number(row[d.field] ?? 0)
    return {
      sourceKey: d.sourceKey,
      label: d.label,
      mapped,
      pctTotal: total > 0 ? (100 * mapped) / total : 0,
      pctMapped: withUrl > 0 ? (100 * mapped) / withUrl : 0,
      fill: d.fill,
    }
  })
  return opts?.includeZero ? rows : rows.filter((r) => r.mapped > 0)
}

function TypicalStatePortalSourcesCard({
  row,
  total,
  withUrl,
}: {
  row: PrimarySourceRow | null
  total: number
  withUrl: number
}) {
  const rates = sourceMappingRateRows(row, total, withUrl, 'state', { includeZero: true })
  const hasPrimaryCols = row != null && PRIMARY_SOURCE_DEFS.some((d) => d.field in row)

  return (
    <div className="jmq-card !py-3">
      <div className="mb-2 font-mono text-[10px] font-semibold uppercase text-[var(--jmq-text-muted)]">
        Typical state-portal sources
      </div>
      {!row ? (
        <p className="text-xs text-[var(--jmq-text-muted)]">No state summary row.</p>
      ) : !hasPrimaryCols ? (
        <p className="text-xs text-[#4d2d00]">
          Re-run dbt + <code className="text-[10px]">export_jurisdiction_mapping_quality_json.py</code> for{' '}
          <code className="text-[10px]">primary_from_*</code>.
        </p>
      ) : (
        <div className="space-y-2">
          {rates.map((r) => (
            <div key={r.sourceKey}>
              <div className="flex items-center justify-between gap-2">
                <span className={sourceBadgeClass(r.sourceKey)}>{r.label}</span>
                <span className="font-mono text-xs font-semibold tabular-nums" style={{ color: r.fill }}>
                  {r.pctTotal.toFixed(1)}%
                </span>
              </div>
              <div className="mt-0.5 font-mono text-[10px] text-[var(--jmq-text-muted)]">
                {fmt(r.mapped)} of {fmt(total)} state governments
              </div>
            </div>
          ))}
          <div className="flex items-center justify-between border-t border-[var(--jmq-border)] pt-2 font-mono text-[10px]">
            <span className="text-[var(--jmq-text-muted)]">Missing portal</span>
            <span className="font-semibold text-[var(--jmq-red)]">
              {total > 0 ? ((100 * Math.max(0, total - withUrl)) / total).toFixed(1) : '0'}%
            </span>
          </div>
        </div>
      )}
    </div>
  )
}

function sourceMappingChartCopy(entity: EntityKey): { title: string; sub: string } {
  const labels = ENTITY_META[entity].sourceKeys.map((k) => PRIMARY_SOURCE_DEFS.find((d) => d.sourceKey === k)?.label ?? k)
  const title = `Mapped by source (${labels.join(' · ')})`
  const sub =
    entity === 'state'
      ? 'Share of state governments whose winning primary URL came from each directory (52 rows).'
      : `${ENTITY_META[entity].label}: share of jurisdictions whose winning primary URL came from each directory.`
  return { title, sub }
}

function SourceMappingBarChart({
  row,
  total,
  withUrl,
  entity,
}: {
  row: PrimarySourceRow | null
  total: number
  withUrl: number
  entity: EntityKey
}) {
  const rows = sourceMappingRateRows(row, total, withUrl, entity, { includeZero: entity === 'state' })
  const hasPrimaryCols = row != null && PRIMARY_SOURCE_DEFS.some((d) => d.field in row)
  if (!row) {
    return <p className="text-xs text-[var(--jmq-text-muted)]">No summary row for this entity.</p>
  }
  if (!hasPrimaryCols && withUrl > 0) {
    return (
      <p className="text-xs text-[#4d2d00]">
        Re-run dbt quality marts and <code className="text-[10px]">export_jurisdiction_mapping_quality_json.py</code> for{' '}
        <code className="text-[10px]">primary_from_*</code> columns.
      </p>
    )
  }
  if (rows.length === 0) {
    return <p className="text-xs text-[var(--jmq-text-muted)]">No mapped jurisdictions from any directory yet.</p>
  }
  const chartHeight = Math.max(120, rows.length * 36 + 24)
  return (
    <div style={{ height: chartHeight }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart layout="vertical" data={rows} margin={{ top: 4, right: 12, bottom: 4, left: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--jmq-border)" horizontal={false} />
          <XAxis
            type="number"
            domain={[0, 100]}
            tickFormatter={(v) => `${v}%`}
            tick={{ fontSize: 10, fill: 'var(--jmq-text-muted)' }}
          />
          <YAxis
            type="category"
            dataKey="label"
            width={64}
            tick={{ fontSize: 10, fill: 'var(--jmq-text-muted)' }}
          />
          <Tooltip
            formatter={(v: number, _name, item) => {
              const mapped = (item?.payload as { mapped?: number })?.mapped ?? 0
              return [`${Number(v).toFixed(1)}% (${fmt(mapped)} mapped)`, '% of all jurisdictions']
            }}
            contentStyle={{ background: 'var(--jmq-surface2)', border: '1px solid var(--jmq-border)', fontSize: 12 }}
          />
          <Bar dataKey="pctTotal" name="% mapped" radius={[0, 4, 4, 0]}>
            {rows.map((d, i) => (
              <Cell key={i} fill={d.fill} fillOpacity={0.85} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

function SourceMappingRatesCard({
  row,
  total,
  withUrl,
  entity,
  compact = false,
}: {
  row: PrimarySourceRow | null
  total: number
  withUrl: number
  entity: EntityKey
  compact?: boolean
}) {
  const rates = sourceMappingRateRows(row, total, withUrl, entity, { includeZero: entity === 'state' })
  const hasPrimaryCols = row != null && PRIMARY_SOURCE_DEFS.some((d) => d.field in row)
  const title = entity === 'state' ? 'Map rate · state portal sources' : 'Primary URL by source'
  const sub =
    entity === 'state'
      ? 'Share of state governments whose winning primary URL came from GSA or a curated override (52 rows).'
      : 'Winning primary URL by directory. Sources with zero mapped are hidden; rows sum to mapped coverage.'

  if (!row) {
    return (
      <div className="jmq-card !py-3">
        <div className="jmq-card-title text-sm">{title}</div>
        <p className="mt-1 text-xs text-[var(--jmq-text-muted)]">No summary row for this entity.</p>
      </div>
    )
  }

  if (!hasPrimaryCols && withUrl > 0) {
    return (
      <div className="jmq-card !py-3">
        <div className="jmq-card-title text-sm">{title}</div>
        <p className="mt-1 text-xs text-[#4d2d00]">
          Re-run dbt quality marts and <code className="text-[10px]">export_jurisdiction_mapping_quality_json.py</code> for{' '}
          <code className="text-[10px]">primary_from_*</code> columns.
        </p>
      </div>
    )
  }

  return (
    <div className={`jmq-card ${compact ? '!py-3' : ''}`}>
      <div className="jmq-card-title text-sm">{title}</div>
      <p className="jmq-card-sub !mb-2">{sub}</p>
      <table className="jmq-dt w-full text-[11px]">
        <thead>
          <tr>
            {['Source', 'Mapped', '% of all', '% of mapped'].map((h) => (
              <th key={h}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rates.map((r) => (
            <tr key={r.sourceKey}>
              <td>
                <span className={sourceBadgeClass(r.sourceKey)}>{r.label}</span>
              </td>
              <td className="font-mono">{fmt(r.mapped)}</td>
              <td className="font-mono">{r.pctTotal.toFixed(1)}%</td>
              <td className="font-mono font-semibold" style={{ color: r.fill }}>
                {r.pctMapped.toFixed(1)}%
              </td>
            </tr>
          ))}
          <tr className="border-t border-[var(--jmq-border)] font-semibold">
            <td>Missing URL</td>
            <td className="font-mono">{fmt(Math.max(0, total - withUrl))}</td>
            <td className="font-mono">{total > 0 ? ((100 * Math.max(0, total - withUrl)) / total).toFixed(1) : '0'}%</td>
            <td className="font-mono text-[var(--jmq-text-muted)]">—</td>
          </tr>
        </tbody>
      </table>
    </div>
  )
}

type EntityAcsBucketRow = {
  bucket: string
  total_jurisdictions: number
  with_primary_website: number
  pct_with_primary_website: number | null
  primary_from_naco?: number
  primary_from_uscm?: number
  primary_from_nces_directory?: number
  primary_from_gsa?: number
  primary_from_league?: number
  primary_from_wikidata?: number
  primary_from_override?: number
}

function entityAcsBucketTableRows(
  slice: { by_population_tier?: EntityAcsBucketRow[]; by_income_level?: EntityAcsBucketRow[] } | undefined,
  tierKey: 'by_population_tier' | 'by_income_level',
): { bucket: string; tierValue: string; n: number; withUrl: number; pct: number; missing: number }[] {
  return (slice?.[tierKey] ?? []).map((r) => {
    const n = Number(r.total_jurisdictions)
    const w = Number(r.with_primary_website)
    const pct = r.pct_with_primary_website != null ? Number(r.pct_with_primary_website) : n > 0 ? (100 * w) / n : 0
    return {
      bucket: r.bucket,
      tierValue: r.bucket,
      n,
      withUrl: w,
      pct,
      missing: Math.max(0, n - w),
    }
  })
}

function StateTierDrillPanel({
  tierLabel,
  tierField,
  tierValue,
  states,
  onClose,
  onDrillState,
}: {
  tierLabel: string
  tierField: 'state_population_tier' | 'state_income_level'
  tierValue: string
  states: StateQualityRow[]
  onClose: () => void
  onDrillState: (s: StateQualityRow) => void
}) {
  const inTier = states
    .filter((s) => s[tierField] === tierValue)
    .map((s) => {
      const total = Number(s.total_jurisdictions)
      const withUrl = Number(s.with_primary_website)
      const pct = s.pct_with_primary_website != null ? Number(s.pct_with_primary_website) : total > 0 ? (100 * withUrl) / total : 0
      return { ...s, missing: Math.max(0, total - withUrl), pct }
    })
    .sort((a, b) => b.missing - a.missing)

  const modal = (
    <div
      className="jmq-modal-portal-root jmq-modal-scrim fixed inset-0 z-[300] flex items-start justify-end p-4"
      role="dialog"
      aria-modal
      onClick={(ev) => {
        if (ev.target === ev.currentTarget) onClose()
      }}
    >
      <div
        className="flex max-h-[92vh] w-full max-w-2xl flex-col overflow-hidden rounded-xl border border-[var(--jmq-border)] bg-[var(--jmq-surface)] shadow-2xl"
        onClick={(ev) => ev.stopPropagation()}
      >
        <div className="flex items-center gap-3 border-b border-[var(--jmq-border)] px-4 py-3">
          <div className="h-7 w-1 shrink-0 rounded bg-[var(--jmq-teal)]" />
          <div className="min-w-0 flex-1">
            <div className="text-[15px] font-bold text-[var(--jmq-text)]">States in tier</div>
            <div className="mt-0.5 font-mono text-xs text-[var(--jmq-text-muted)]">
              State · {tierValue} ({tierLabel})
            </div>
          </div>
          <button type="button" onClick={onClose} className="shrink-0 rounded-md border border-[var(--jmq-border)] bg-[var(--jmq-surface2)] px-3 py-1 text-xs">
            ✕ Close
          </button>
        </div>
        <div className="border-b border-[var(--jmq-border)] bg-[var(--jmq-amber-dim)] px-4 py-2 text-[11px] text-[#4d2d00]">
          States in this ACS tier. Drill a state missing a portal to see its state-government row. For cities, counties, or districts in a state, use those tiles with the state filter.
        </div>
        <div className="flex-1 overflow-y-auto p-2">
          {inTier.length === 0 ? (
            <p className="p-8 text-center text-sm text-[var(--jmq-text-muted)]">No states in this tier (load state ACS in export).</p>
          ) : (
            <table className="jmq-dt w-full text-xs">
              <thead>
                <tr>
                  {['State', 'ACS pop', 'Portal', 'Status', 'Drill'].map((h) => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {inTier.map((s) => (
                  <tr key={s.state_code}>
                    <td className="font-mono font-semibold">{s.state_code}</td>
                    <td className="font-mono text-[10px]">{fmtPop(s.acs_population)}</td>
                    <td className="font-mono text-[10px]">{s.missing > 0 ? '—' : '✓ mapped'}</td>
                    <td>
                      <CovBarLite pct={s.pct} width={72} />
                    </td>
                    <td>
                      {s.missing > 0 ? (
                        <button
                          type="button"
                          className="rounded border border-[var(--jmq-red)] bg-[var(--jmq-red-dim)] px-2 py-0.5 font-mono text-[10px]"
                          onClick={() => onDrillState(s)}
                        >
                          ↗
                        </button>
                      ) : (
                        <span className="text-[var(--jmq-green)] text-[10px]">✓</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
  if (typeof document === 'undefined') return null
  return createPortal(modal, document.body)
}

function statePortalDetailLines(s: StateQualityRow): string[] {
  const lines: string[] = []
  if (s.primary_website_url) {
    lines.push(`Primary URL (${s.primary_website_source ?? 'unknown'}): ${s.primary_website_url}`)
  } else {
    lines.push('Primary URL: none in warehouse')
  }
  const candidates = s.website_candidates ?? []
  if (candidates.length > 0) {
    lines.push(
      `Candidate rows (${candidates.length}): ${candidates.map((c) => `${c.source} → ${c.url}`).join(' · ')}`,
    )
  } else {
    lines.push(`Candidate rows in warehouse: ${s.n_website_candidate_rows ?? 0}`)
  }
  if (!s.primary_website_url && (s.n_website_candidate_rows ?? 0) === 0) {
    lines.push(
      'GSA may list portal.ct.gov / dc.gov, but automated matching often skips CT/DC until jurisdiction_website_url_overrides is seeded and dbt is re-run.',
    )
  }
  return lines
}

function StatePortalUrlCell({ s }: { s: StateQualityRow }) {
  if (s.primary_website_url) {
    return (
      <div className="max-w-[220px]">
        <a
          href={s.primary_website_url}
          target="_blank"
          rel="noreferrer"
          className="block truncate font-mono text-[10px] text-[var(--jmq-teal)] hover:underline"
          title={s.primary_website_url}
        >
          {s.primary_website_url.replace(/^https?:\/\//, '')}
        </a>
        {s.primary_website_source ? (
          <span className={`mt-0.5 inline-block ${sourceBadgeClass(s.primary_website_source)}`}>
            {s.primary_website_source}
          </span>
        ) : null}
      </div>
    )
  }
  const candidates = s.website_candidates ?? []
  if (candidates.length > 0) {
    return (
      <div className="max-w-[220px] space-y-0.5">
        {candidates.slice(0, 3).map((c) => (
          <div key={`${c.source}-${c.url}`} className="truncate font-mono text-[10px] text-[var(--jmq-text-muted)]" title={c.url}>
            <span className={sourceBadgeClass(c.source)}>{c.source}</span>{' '}
            <a href={c.url} target="_blank" rel="noreferrer" className="text-[var(--jmq-teal)] hover:underline">
              {c.url.replace(/^https?:\/\//, '')}
            </a>
          </div>
        ))}
        {candidates.length > 3 ? (
          <span className="font-mono text-[10px] text-[var(--jmq-text-muted)]">+{candidates.length - 3} more</span>
        ) : null}
      </div>
    )
  }
  if (s.has_state_portal || Number(s.with_primary_website) > 0) {
    return (
      <span className="font-mono text-[10px] text-[#4d2d00]" title="Portal is mapped in summary counts but URL fields are missing from the JSON snapshot.">
        Mapped · re-export JSON
      </span>
    )
  }
  return <span className="font-mono text-[10px] text-[var(--jmq-red)]">None in warehouse</span>
}

function sourceBadgeClass(src: string): string {
  const base = 'jmq-src-badge !m-0'
  const m: Record<string, string> = {
    naco: 'jmq-src-badge--naco',
    uscm: 'jmq-src-badge--uscm',
    nces_directory: 'jmq-src-badge--nces_directory',
    gsa: 'jmq-src-badge--gsa',
    league: 'jmq-src-badge--league',
    wikidata: 'jmq-src-badge--wikidata',
    override: 'jmq-src-badge--override',
  }
  return `${base} ${m[src] ?? ''}`.trim()
}

function CovBarLite({ pct, width = 100 }: { pct: number; width?: number }) {
  const c = barColor(pct)
  const w = Math.min(100, Math.max(0, pct))
  return (
    <div className="flex items-center gap-2">
      <div
        className="h-1.5 shrink-0 overflow-hidden rounded bg-[var(--jmq-surface2)]"
        style={{ width }}
      >
        <div className="h-full rounded" style={{ width: `${w}%`, background: c }} />
      </div>
      <span className="w-10 shrink-0 text-right font-mono text-[11px]" style={{ color: c }}>
        {pct.toFixed(0)}%
      </span>
    </div>
  )
}

function DrillPanel({
  query,
  title,
  subtitle,
  onClose,
  bannerExtra,
  expectedMissing,
  variant = 'primary',
}: {
  query: UnmappedDrillParams | MissingYoutubeDrillParams
  title: string
  subtitle: string
  onClose: () => void
  /** Optional second line in the amber banner. */
  bannerExtra?: string | null
  /** Rollup missing count from JSON summary (for mismatch hint). */
  expectedMissing?: number
  variant?: 'primary' | 'youtube'
}) {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ['jurisdiction-mapping-drill', variant, query],
    queryFn: ({ signal }) =>
      variant === 'youtube'
        ? fetchMissingYoutubeChannels({ ...(query as MissingYoutubeDrillParams), limit: 50_000, offset: 0 }, signal)
        : fetchUnmappedJurisdictions({ ...(query as UnmappedDrillParams), limit: 50_000, offset: 0 }, signal),
    staleTime: 60_000,
  })
  const rows = data?.rows ?? []
  const total = data?.total ?? 0

  let loadBanner = bannerExtra ?? null
  if (!isPending && !isError && data) {
    loadBanner = [
      loadBanner,
      `Showing ${fmt(rows.length)} of ${fmt(total)} ${variant === 'youtube' ? 'missing YouTube channel' : 'unmapped'} jurisdictions (live API).`,
      expectedMissing != null && expectedMissing > 0 && total !== expectedMissing
        ? `Summary rollup reports ${fmt(expectedMissing)} missing in this slice — counts can differ if the snapshot JSON is stale.`
        : null,
    ]
      .filter(Boolean)
      .join(' ')
  }

  const apiPath =
    variant === 'youtube'
      ? 'GET /api/jurisdiction-mapping/missing-youtube-channel'
      : 'GET /api/jurisdiction-mapping/unmapped'

  const modal = (
    <div
      className="jmq-modal-portal-root jmq-modal-scrim fixed inset-0 z-[300] flex items-start justify-end p-4"
      role="dialog"
      aria-modal
      aria-labelledby="jmq-drill-title"
      onClick={(ev) => {
        if (ev.target === ev.currentTarget) onClose()
      }}
    >
      <div
        className="flex max-h-[92vh] w-full max-w-2xl flex-col overflow-hidden rounded-xl border border-[var(--jmq-border)] bg-[var(--jmq-surface)] shadow-2xl"
        onClick={(ev) => ev.stopPropagation()}
      >
        <div className="flex items-center gap-3 border-b border-[var(--jmq-border)] px-4 py-3">
          <div className="h-7 w-1 shrink-0 rounded bg-[var(--jmq-teal)]" />
          <div className="min-w-0 flex-1">
            <div id="jmq-drill-title" className="text-[15px] font-bold text-[var(--jmq-text)]">
              {title}
            </div>
            <div className="mt-0.5 font-mono text-xs text-[var(--jmq-text-muted)]">{subtitle}</div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="shrink-0 rounded-md border border-[var(--jmq-border)] bg-[var(--jmq-surface2)] px-3 py-1 text-xs text-[var(--jmq-text-muted)] hover:bg-[#e6eaef]"
          >
            ✕ Close
          </button>
        </div>
        <div className="border-b border-[var(--jmq-border)] bg-[var(--jmq-amber-dim)] px-4 py-2 text-[11px] text-[#4d2d00]">
          <div>
            Loaded from <code className="text-[10px]">{apiPath}</code>
          </div>
          {loadBanner ? <div className="mt-1 font-medium">{loadBanner}</div> : null}
        </div>
        <div className="flex-1 overflow-y-auto">
          {isPending ? (
            <div className="p-10 text-center text-sm text-[var(--jmq-text-muted)]">
              Loading {variant === 'youtube' ? 'missing YouTube channel' : 'unmapped'} list…
            </div>
          ) : isError ? (
            <div className="p-10 text-center text-sm text-[var(--jmq-red)]">
              Could not load drill-down: {(error as Error)?.message ?? 'unknown error'}. Is the API running on port 8000?
            </div>
          ) : rows.length === 0 ? (
            <div className="p-10 text-center text-sm text-[var(--jmq-green)]">No matching rows in the warehouse.</div>
          ) : (
            <table className="w-full border-collapse text-xs">
              <thead className="sticky top-0 bg-[var(--jmq-surface2)]">
                <tr>
                  {(variant === 'youtube'
                    ? ['Jurisdiction', 'State', 'GEOID', 'Primary URL', 'ACS pop', 'ACS income']
                    : ['Jurisdiction', 'State', 'GEOID', 'ACS pop', 'ACS income', 'Directories']
                  ).map((h) => (
                    <th
                      key={h}
                      className="border-b border-[var(--jmq-border)] px-3 py-2 text-left font-mono text-[10px] font-semibold uppercase tracking-wide text-[var(--jmq-text-muted)]"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.jurisdiction_id} className="border-b border-[var(--jmq-border)]/60 hover:bg-[var(--jmq-surface2)]">
                    <td className="px-3 py-2 font-medium text-[var(--jmq-text)]">{r.name}</td>
                    <td className="px-3 py-2 font-mono text-[var(--jmq-text-muted)]">{r.state_code}</td>
                    <td className="px-3 py-2 font-mono text-[10px] text-[var(--jmq-text-muted)]">{r.geoid ?? '—'}</td>
                    {variant === 'youtube' ? (
                      <td className="max-w-[14rem] break-all px-3 py-2 font-mono text-[10px] text-[var(--jmq-text-muted)]">
                        {(r as { primary_website_url?: string | null }).primary_website_url || '—'}
                      </td>
                    ) : null}
                    <td className="px-3 py-2 font-mono text-[10px]">{r.acs_population_tier ?? '—'}</td>
                    <td className="px-3 py-2 font-mono text-[10px]">{r.acs_income_level ?? '—'}</td>
                    {variant === 'primary' ? (
                      <td className="px-3 py-2 font-mono text-[10px] text-[var(--jmq-text-muted)]">
                        {[
                          'has_naco_source' in r && r.has_naco_source && 'NACo',
                          'has_uscm_source' in r && r.has_uscm_source && 'USCM',
                          'has_nces_directory_source' in r && r.has_nces_directory_source && 'NCES',
                          'has_gsa_source' in r && r.has_gsa_source && 'GSA',
                          'has_league_source' in r && r.has_league_source && 'League',
                          'has_wikidata_source' in r && r.has_wikidata_source && 'WD',
                          'has_override_source' in r && r.has_override_source && 'ovr',
                        ]
                          .filter(Boolean)
                          .join(', ') || '—'}
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
  if (typeof document === 'undefined') return null
  return createPortal(modal, document.body)
}

type EnrichedStateRollup = StateRollupRow & {
  name: string
  missing: number
  pct: number
  state_population_tier?: string | null
  acs_population?: number | null
  state_income_level?: string | null
}

function enrichStateRollup(
  rollup: StateRollupRow[],
  stateQuality?: StateQualityRow[],
): EnrichedStateRollup[] {
  const qualityByCode = new Map<string, StateQualityRow>()
  for (const s of stateQuality ?? []) qualityByCode.set(s.state_code, s)
  return rollup.map((r) => {
    const total = Number(r.total_jurisdictions)
    const withUrl = Number(r.with_primary_website)
    const pct = r.pct_with_primary_website != null ? Number(r.pct_with_primary_website) : total > 0 ? (100 * withUrl) / total : 0
    const q = qualityByCode.get(r.state_code)
    return {
      ...r,
      name: q?.state_name ?? US_STATE_NAMES[r.state_code] ?? r.state_code,
      missing: Math.max(0, total - withUrl),
      pct,
      state_population_tier: q?.state_population_tier ?? null,
      acs_population: q?.acs_population ?? null,
      state_income_level: q?.state_income_level ?? null,
    }
  })
}

type EnrichedYoutubeStateRollup = YoutubeStateRollupRow & {
  name: string
  missing: number
  pct: number
}

function enrichYoutubeStateRollup(
  rollup: YoutubeStateRollupRow[],
  stateQuality?: StateQualityRow[],
): EnrichedYoutubeStateRollup[] {
  const qualityByCode = new Map<string, StateQualityRow>()
  for (const s of stateQuality ?? []) qualityByCode.set(s.state_code, s)
  return rollup.map((r) => {
    const total = Number(r.total_jurisdictions)
    const withChannel = Number(r.with_youtube_channel)
    const pct =
      r.pct_with_youtube_channel != null
        ? Number(r.pct_with_youtube_channel)
        : total > 0
          ? (100 * withChannel) / total
          : 0
    const q = qualityByCode.get(r.state_code)
    return {
      ...r,
      name: q?.state_name ?? US_STATE_NAMES[r.state_code] ?? r.state_code,
      missing: Math.max(0, total - withChannel),
      pct,
    }
  })
}

/** State-by-state coverage + missing-primary-URL drill for cities, towns, counties, schools. */
function EntityStateRollupSection({
  entity,
  rollup,
  stateQuality,
  variant = 'primary',
}: {
  entity: Exclude<EntityKey, 'state'>
  rollup: StateRollupRow[] | YoutubeStateRollupRow[]
  stateQuality?: StateQualityRow[]
  variant?: 'primary' | 'youtube'
}) {
  const label = ENTITY_META[entity].label
  const isYoutube = variant === 'youtube'
  const [view, setView] = useState<'worst' | 'best' | 'all'>('worst')
  const [search, setSearch] = useState('')
  const [sortCol, setSortCol] = useState<'pct' | 'missing' | 'total_jurisdictions' | 'state_code'>('missing')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [drill, setDrill] = useState<(EnrichedStateRollup | EnrichedYoutubeStateRollup) | null>(null)

  const enriched = useMemo(() => {
    if (isYoutube) {
      return enrichYoutubeStateRollup(rollup as YoutubeStateRollupRow[], stateQuality)
    }
    return enrichStateRollup(rollup as StateRollupRow[], stateQuality)
  }, [isYoutube, rollup, stateQuality])

  const filtered = useMemo(() => {
    let rows = [...enriched]
    const q = search.trim().toLowerCase()
    if (q) rows = rows.filter((r) => r.name.toLowerCase().includes(q) || r.state_code.toLowerCase().includes(q))
    rows.sort((a, b) => {
      let c = 0
      if (sortCol === 'state_code') c = a.state_code.localeCompare(b.state_code)
      else if (sortCol === 'total_jurisdictions')
        c = Number(a.total_jurisdictions) - Number(b.total_jurisdictions)
      else c = Number(a[sortCol]) - Number(b[sortCol])
      return sortDir === 'asc' ? c : -c
    })
    if (!q && view === 'worst') return rows.filter((r) => r.missing > 0).slice(0, 15)
    if (!q && view === 'best') return [...enriched].sort((a, b) => b.pct - a.pct).slice(0, 15)
    return rows
  }, [enriched, search, sortCol, sortDir, view])

  const chartData = useMemo(() => {
    const withGaps = [...enriched].filter((r) => r.missing > 0).sort((a, b) => b.missing - a.missing)
    if (view === 'best') return [...enriched].sort((a, b) => b.pct - a.pct).slice(0, 20)
    return withGaps.slice(0, 20)
  }, [enriched, view])

  const totalMissing = useMemo(() => enriched.reduce((s, r) => s + r.missing, 0), [enriched])

  const setDrillFromBar = (barData: unknown) => {
    const p = (barData as { payload?: EnrichedStateRollup | EnrichedYoutubeStateRollup } | null)?.payload
    if (p?.state_code && p.missing > 0) setDrill(p)
  }

  const toggleSort = (col: 'pct' | 'missing' | 'total_jurisdictions' | 'state_code') => {
    if (sortCol === col) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    else {
      setSortCol(col)
      setSortDir(col === 'missing' ? 'desc' : 'asc')
    }
  }

  return (
    <div id={isYoutube ? 'jmq-missing-youtube-by-state' : 'jmq-missing-by-state'} className="scroll-mt-24">
      {drill ? (
        <DrillPanel
          query={{ entity: entity as MissingYoutubeDrillParams['entity'] & UnmappedDrillParams['entity'], state_code: drill.state_code }}
          expectedMissing={drill.missing}
          title={isYoutube ? 'Missing YouTube channel URL' : 'Missing primary URL'}
          subtitle={`${drill.name} (${drill.state_code}) · ${label}`}
          onClose={() => setDrill(null)}
          variant={variant}
        />
      ) : null}

      <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[
          { label: 'States in view', val: fmt(enriched.length) },
          { label: 'With any gap', val: fmt(enriched.filter((s) => s.missing > 0).length) },
          {
            label: isYoutube ? 'Missing channels (sum)' : 'Missing URLs (sum)',
            val: fmt(totalMissing),
          },
          {
            label: 'National coverage',
            val: `${(
              (enriched.reduce(
                (s, r) =>
                  s +
                  Number(
                    isYoutube
                      ? (r as EnrichedYoutubeStateRollup).with_youtube_channel
                      : (r as EnrichedStateRollup).with_primary_website,
                  ),
                0,
              ) /
                Math.max(1, enriched.reduce((s, r) => s + Number(r.total_jurisdictions), 0))) *
              100
            ).toFixed(1)}%`,
          },
        ].map((k) => (
          <div key={k.label} className="rounded-lg border border-[var(--jmq-border)] bg-[var(--jmq-surface2)] px-3 py-2">
            <div className="font-mono text-[10px] font-semibold uppercase tracking-wide text-[var(--jmq-text-muted)]">
              {k.label}
            </div>
            <div className="mt-1 font-mono text-sm font-bold text-[var(--jmq-text)]">{k.val}</div>
          </div>
        ))}
      </div>

      <div className="jmq-pill-row mb-3">
        {(
          [
            ['worst', '15 Most gaps'],
            ['best', '15 Best coverage'],
            ['all', 'All states'],
          ] as const
        ).map(([id, lbl]) => (
          <button
            key={id}
            type="button"
            className={`jmq-pill text-xs ${view === id && !search ? 'jmq-pill--active' : ''}`}
            onClick={() => {
              setView(id)
              setSearch('')
              setSortCol(id === 'best' ? 'pct' : 'missing')
              setSortDir(id === 'best' ? 'desc' : 'desc')
            }}
          >
            {lbl}
          </button>
        ))}
        <input
          type="search"
          placeholder="Search state…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setView('all')
          }}
          className="ml-auto w-44 rounded-md border border-[var(--jmq-border)] bg-[var(--jmq-surface)] px-2 py-1.5 text-xs text-[var(--jmq-text)]"
        />
      </div>

      <div className="jmq-card mb-4">
        <div className="jmq-card-title">
          {isYoutube ? 'Missing YouTube channel URLs by state (click a bar)' : 'Missing primary URLs by state (click a bar)'}
        </div>
        <p className="jmq-card-sub">
          {isYoutube
            ? `Count of ${label.toLowerCase()} without a golden youtube_channel_url in intermediate.int_events_channels. Bars with zero are omitted.`
            : `Count of ${label.toLowerCase()} without a mapped primary website in each state. Bars with zero are omitted in this chart.`}
        </p>
        <div className="h-56 w-full sm:h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 8, right: 12, bottom: 48, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--jmq-border)" />
              <XAxis dataKey="state_code" tick={{ fontSize: 10, fill: 'var(--jmq-text-muted)' }} interval={0} angle={-40} textAnchor="end" height={50} />
              <YAxis
                tickFormatter={(v) => fmt(v)}
                tick={{ fontSize: 10, fill: 'var(--jmq-text-muted)' }}
                width={48}
                label={{
                  value: isYoutube ? 'Missing YouTube channel (count)' : 'Missing primary URL (count)',
                  angle: -90,
                  position: 'insideLeft',
                  offset: 4,
                  fill: 'var(--jmq-text-muted)',
                  fontSize: 11,
                  fontWeight: 600,
                }}
              />
              <Tooltip contentStyle={{ background: 'var(--jmq-surface2)', border: '1px solid var(--jmq-border)' }} />
              <Bar dataKey="missing" name="Missing" radius={[3, 3, 0, 0]} cursor="pointer" onClick={setDrillFromBar}>
                {chartData.map((d, i) => (
                  <Cell key={i} fill={barColor(d.pct)} fillOpacity={0.85} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="jmq-card">
        <div className="jmq-card-title">
          {search ? `Search: “${search}”` : view === 'worst' ? 'States with the most missing URLs' : view === 'best' ? 'Highest coverage by state' : 'All states'}
        </div>
        <p className="jmq-card-sub">
          Per-state rollup for {label.toLowerCase()}. Use <strong>↗ Missing</strong> to load the full unmapped list for that state (API).
        </p>
        <div className="jmq-tbl-wrap mt-2">
          <table className="jmq-dt text-xs">
            <thead>
              <tr>
                {(
                  [
                    { k: null, l: '#' },
                    { k: 'state_code', l: 'St' },
                    { k: null, l: 'Name' },
                    { k: 'total_jurisdictions', l: 'Total' },
                    { k: 'pct', l: 'Coverage' },
                    { k: 'missing', l: 'Missing' },
                    { k: null, l: 'Drill' },
                  ] as { k: 'pct' | 'missing' | 'total_jurisdictions' | 'state_code' | null; l: string }[]
                ).map(({ k, l }) => (
                  <th
                    key={l}
                    className={`${k ? 'cursor-pointer select-none' : ''} ${sortCol === k ? 'text-[var(--jmq-teal)]' : ''}`}
                    onClick={k ? () => toggleSort(k) : undefined}
                  >
                    {l}
                    {k ? <span className="ml-1 opacity-60">{sortCol === k ? (sortDir === 'asc' ? '↑' : '↓') : '↕'}</span> : null}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-[var(--jmq-text-muted)]">
                    No states match this filter.
                  </td>
                </tr>
              ) : (
                filtered.map((r, i) => {
                  const rank = !search && view !== 'all' ? i + 1 : null
                  return (
                    <tr key={r.state_code}>
                      <td className="font-mono text-[10px] text-[var(--jmq-text-muted)]">{rank ? `#${rank}` : ''}</td>
                      <td className="font-mono font-semibold">{r.state_code}</td>
                      <td>{r.name}</td>
                      <td className="font-mono tabular-nums">{fmt(Number(r.total_jurisdictions))}</td>
                      <td>
                        <CovBarLite pct={r.pct} width={72} />
                      </td>
                      <td className="font-mono text-[10px] text-[var(--jmq-red)]">{r.missing > 0 ? fmt(r.missing) : '—'}</td>
                      <td>
                        {r.missing > 0 ? (
                          <button
                            type="button"
                            className="rounded border border-[var(--jmq-red)] bg-[var(--jmq-red-dim)] px-2 py-0.5 font-mono text-[10px] text-[var(--jmq-red)] hover:opacity-90"
                            onClick={() => setDrill(r)}
                          >
                            ↗ Missing
                          </button>
                        ) : (
                          <span className="text-[var(--jmq-green)] font-mono text-[10px]">✓</span>
                        )}
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function StateAnalysisSection({
  rollup,
  stateQuality,
}: {
  rollup: StateRollupRow[]
  stateQuality?: StateQualityRow[]
}) {
  const qualityByCode = useMemo(() => {
    const m = new Map<string, StateQualityRow>()
    for (const s of stateQuality ?? []) m.set(s.state_code, s)
    return m
  }, [stateQuality])
  const [view, setView] = useState<'worst' | 'best' | 'all'>('worst')
  const [search, setSearch] = useState('')
  const [sortCol, setSortCol] = useState<'pct' | 'missing' | 'total_jurisdictions' | 'state_code'>('pct')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')
  type EnrichedState = StateRollupRow & {
    name: string
    missing: number
    pct: number
    state_population_tier?: string | null
    acs_population?: number | null
    state_income_level?: string | null
    portal?: StateQualityRow
  }
  const [drill, setDrill] = useState<EnrichedState | null>(null)

  const enriched = useMemo(
    () =>
      rollup.map((r) => {
        const total = Number(r.total_jurisdictions)
        const withUrl = Number(r.with_primary_website)
        const pct = r.pct_with_primary_website != null ? Number(r.pct_with_primary_website) : total > 0 ? (100 * withUrl) / total : 0
        const q = qualityByCode.get(r.state_code)
        return {
          ...r,
          name: q?.state_name ?? US_STATE_NAMES[r.state_code] ?? r.state_code,
          missing: Math.max(0, total - withUrl),
          pct,
          state_population_tier: q?.state_population_tier ?? null,
          acs_population: q?.acs_population ?? null,
          state_income_level: q?.state_income_level ?? null,
          portal: q,
        }
      }),
    [rollup, qualityByCode],
  )

  const filtered = useMemo(() => {
    let rows = [...enriched]
    const q = search.trim().toLowerCase()
    if (q) rows = rows.filter((r) => r.name.toLowerCase().includes(q) || r.state_code.toLowerCase().includes(q))
    rows.sort((a, b) => {
      let c = 0
      if (sortCol === 'state_code') c = a.state_code.localeCompare(b.state_code)
      else if (sortCol === 'total_jurisdictions')
        c = Number(a.total_jurisdictions) - Number(b.total_jurisdictions)
      else c = Number(a[sortCol]) - Number(b[sortCol])
      return sortDir === 'asc' ? c : -c
    })
    if (!q && view === 'worst') return rows.slice(0, 15)
    if (!q && view === 'best') return [...enriched].sort((a, b) => b.pct - a.pct).slice(0, 15)
    return rows
  }, [enriched, search, sortCol, sortDir, view])

  const chartData = useMemo(() => {
    const base = [...enriched].sort((a, b) => a.pct - b.pct)
    if (view === 'best') return base.slice(-20).reverse()
    return base.slice(0, 20)
  }, [enriched, view])

  const setDrillFromBar = (barData: unknown) => {
    const p = (barData as { payload?: EnrichedState } | null)?.payload
    if (p?.state_code) setDrill(p)
  }

  const toggleSort = (col: 'pct' | 'missing' | 'total_jurisdictions' | 'state_code') => {
    if (sortCol === col) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    else {
      setSortCol(col)
      setSortDir(col === 'missing' ? 'desc' : 'asc')
    }
  }

  return (
    <div>
      {drill ? (
        <DrillPanel
          query={{ entity: 'state', state_code: drill.state_code }}
          expectedMissing={drill.missing}
          title="State without portal"
          subtitle={`${drill.name} (${drill.state_code}) · state government row`}
          bannerExtra={drill?.portal ? statePortalDetailLines(drill.portal).join(' · ') : null}
          onClose={() => setDrill(null)}
        />
      ) : null}

      <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[
          { label: 'State governments', val: fmt(enriched.length) },
          { label: 'With portal', val: fmt(enriched.filter((s) => s.pct >= 100).length) },
          { label: 'Missing portal', val: fmt(enriched.filter((s) => s.missing > 0).length) },
          { label: 'Mapped share', val: `${((enriched.filter((s) => s.pct >= 100).length / Math.max(1, enriched.length)) * 100).toFixed(1)}%` },
        ].map((k) => (
          <div key={k.label} className="rounded-lg border border-[var(--jmq-border)] bg-[var(--jmq-surface2)] px-3 py-2">
            <div className="font-mono text-[10px] font-semibold uppercase tracking-wide text-[var(--jmq-text-muted)]">
              {k.label}
            </div>
            <div className="mt-1 font-mono text-sm font-bold text-[var(--jmq-text)]">{k.val}</div>
          </div>
        ))}
      </div>

      <div className="jmq-pill-row mb-3">
        {(
          [
            ['worst', '15 Worst states'],
            ['best', '15 Best states'],
            ['all', 'All states'],
          ] as const
        ).map(([id, lbl]) => (
          <button
            key={id}
            type="button"
            className={`jmq-pill text-xs ${view === id && !search ? 'jmq-pill--active' : ''}`}
            onClick={() => {
              setView(id)
              setSearch('')
              setSortCol('pct')
              setSortDir(id === 'best' ? 'desc' : 'asc')
            }}
          >
            {lbl}
          </button>
        ))}
        <input
          type="search"
          placeholder="Search state…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setView('all')
          }}
          className="ml-auto w-44 rounded-md border border-[var(--jmq-border)] bg-[var(--jmq-surface)] px-2 py-1.5 text-xs text-[var(--jmq-text)]"
        />
      </div>

      <div className="jmq-card mb-4">
        <div className="jmq-card-title">State portal mapped (click a bar)</div>
        <p className="jmq-card-sub">Each bar is one state government — 100% = primary URL in warehouse, 0% = missing.</p>
        <div className="h-56 w-full sm:h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={chartData}
              layout="horizontal"
              margin={{ top: 8, right: 12, bottom: 48, left: 8 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="var(--jmq-border)" />
              <XAxis dataKey="state_code" tick={{ fontSize: 10, fill: 'var(--jmq-text-muted)' }} interval={0} angle={-40} textAnchor="end" height={50} />
              <YAxis
                domain={[0, 100]}
                tickFormatter={(v) => `${v}%`}
                tick={{ fontSize: 10, fill: 'var(--jmq-text-muted)' }}
                width={44}
                label={{
                  value: AXIS_LABEL_PCT_WITH_PRIMARY_URL,
                  angle: -90,
                  position: 'insideLeft',
                  offset: 4,
                  fill: 'var(--jmq-text-muted)',
                  fontSize: 11,
                  fontWeight: 600,
                }}
              />
              <Tooltip
                formatter={(v: number) => [`${Number(v).toFixed(1)}%`, AXIS_LABEL_PCT_WITH_PRIMARY_URL]}
                contentStyle={{ background: 'var(--jmq-surface2)', border: '1px solid var(--jmq-border)', fontSize: 12 }}
              />
              <Bar dataKey="pct" name={AXIS_LABEL_PCT_WITH_PRIMARY_URL} radius={[3, 3, 0, 0]} cursor="pointer" onClick={setDrillFromBar}>
                {chartData.map((d, i) => (
                  <Cell key={i} fill={barColor(d.pct)} fillOpacity={0.85} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="jmq-card mb-4">
        <div className="jmq-card-title">States without a portal</div>
        <p className="jmq-card-sub">State governments missing a primary URL (click a bar to drill).</p>
        <div className="h-48 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              layout="vertical"
              data={[...enriched].sort((a, b) => b.missing - a.missing).slice(0, 15)}
              margin={{ top: 8, right: 12, bottom: 36, left: 8 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="var(--jmq-border)" />
              <XAxis
                type="number"
                tickFormatter={(v) => fmt(v)}
                tick={{ fontSize: 10, fill: 'var(--jmq-text-muted)' }}
                label={{
                  value: 'Without primary URL (count)',
                  position: 'insideBottom',
                  offset: -2,
                  fill: 'var(--jmq-text-muted)',
                  fontSize: 11,
                  fontWeight: 600,
                }}
              />
              <YAxis
                type="category"
                dataKey="state_code"
                width={40}
                tick={{ fontSize: 10, fill: 'var(--jmq-text-muted)' }}
                label={{
                  value: 'State',
                  angle: 0,
                  position: 'insideLeft',
                  offset: 6,
                  fill: 'var(--jmq-text-muted)',
                  fontSize: 11,
                  fontWeight: 600,
                }}
              />
              <Tooltip contentStyle={{ background: 'var(--jmq-surface2)', border: '1px solid var(--jmq-border)' }} />
              <Bar dataKey="missing" name="Missing" radius={[0, 4, 4, 0]} cursor="pointer" onClick={setDrillFromBar}>
                {[...enriched]
                  .sort((a, b) => b.missing - a.missing)
                  .slice(0, 15)
                  .map((d, i) => (
                    <Cell key={i} fill={barColor(d.pct)} fillOpacity={0.85} />
                  ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="jmq-card">
        <div className="jmq-card-title">
          {search ? `Search: “${search}”` : view === 'worst' ? '15 lowest coverage' : view === 'best' ? '15 highest coverage' : 'All states'}
        </div>
        <p className="jmq-card-sub">
          One row per state government (official state portal in the warehouse). ACS tiers are Census state estimates.
        </p>
        <div className="jmq-tbl-wrap mt-2">
          <table className="jmq-dt text-xs">
            <thead>
              <tr>
                {(
                  [
                    { k: null, l: '#' },
                    { k: 'state_code', l: 'St' },
                    { k: null, l: 'Name' },
                    { k: null, l: 'Pop tier' },
                    { k: null, l: 'ACS pop' },
                    { k: null, l: 'Primary URL' },
                    { k: 'pct', l: 'Portal' },
                    { k: 'missing', l: 'Gap' },
                    { k: null, l: 'Drill' },
                  ] as { k: 'pct' | 'missing' | 'total_jurisdictions' | 'state_code' | null; l: string }[]
                ).map(({ k, l }) => (
                  <th
                    key={l}
                    className={`${k ? 'cursor-pointer select-none' : ''} ${sortCol === k ? 'text-[var(--jmq-teal)]' : ''}`}
                    onClick={k ? () => toggleSort(k) : undefined}
                  >
                    {l}
                    {k ? <span className="ml-1 opacity-60">{sortCol === k ? (sortDir === 'asc' ? '↑' : '↓') : '↕'}</span> : null}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map((r, i) => {
                const rank = !search && view !== 'all' ? i + 1 : null
                return (
                  <tr key={r.state_code}>
                    <td className="font-mono text-[10px] text-[var(--jmq-text-muted)]">{rank ? `#${rank}` : ''}</td>
                    <td className="font-mono font-semibold">{r.state_code}</td>
                    <td>{r.name}</td>
                    <td className="font-mono text-[10px] text-[var(--jmq-text-muted)]">{r.state_population_tier ?? '—'}</td>
                    <td className="font-mono text-[10px] tabular-nums">{fmtPop(r.acs_population)}</td>
                    <td className="min-w-[12rem] max-w-[280px]">
                      {r.portal ? <StatePortalUrlCell s={r.portal} /> : <span className="text-[var(--jmq-text-muted)]">—</span>}
                    </td>
                    <td>
                      <CovBarLite pct={r.pct} width={72} />
                    </td>
                    <td className="font-mono text-[10px]">{r.missing > 0 ? 'No portal' : '—'}</td>
                    <td>
                      {r.missing > 0 ? (
                        <button
                          type="button"
                          className="rounded border border-[var(--jmq-red)] bg-[var(--jmq-red-dim)] px-2 py-0.5 font-mono text-[10px] text-[var(--jmq-red)] hover:opacity-90"
                          onClick={() => setDrill(r)}
                        >
                          ↗ Drill
                        </button>
                      ) : (
                        <span className="text-[var(--jmq-green)] font-mono text-[10px]">✓</span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

function SectionTable({
  rows,
  onDrillMissing,
  variant = 'default',
}: {
  rows: { bucket: string; tierValue?: string; n: number; withUrl: number; pct: number; missing: number }[]
  onDrillMissing: (row: { bucket: string; tierValue?: string; missing: number }) => void
  variant?: 'default' | 'state_portal'
}) {
  const data = rows.filter((r) => r.n > 0)
  const headers =
    variant === 'state_portal'
      ? ['Tier', 'States', 'With portal', 'Coverage', 'Missing portals', 'Drill']
      : ['Bucket', 'In bucket', 'With URL', 'Coverage', 'Missing', 'Drill']
  return (
    <table className="jmq-dt w-full text-xs">
      <thead>
        <tr>
          {headers.map((h) => (
            <th key={h}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {data.length === 0 ? (
          <tr>
            <td colSpan={6} className="px-3 py-8 text-center text-sm text-[var(--jmq-text-muted)]">
              No bucket rows in this export. Re-export after state ACS is loaded (see Refresh panel).
            </td>
          </tr>
        ) : null}
        {data.map((r) => (
          <tr key={r.bucket}>
            <td className="font-semibold text-[var(--jmq-text)]">{r.bucket}</td>
            <td className="font-mono text-[var(--jmq-text-muted)]">{fmt(r.n)}</td>
            <td className="font-mono" style={{ color: barColor(r.pct) }}>
              {fmt(r.withUrl)}
            </td>
            <td>
              <CovBarLite pct={r.pct} width={90} />
            </td>
            <td className="font-mono text-[var(--jmq-red)]">{fmt(r.missing)}</td>
            <td>
              {r.missing > 0 ? (
                <button
                  type="button"
                  className="rounded border border-[var(--jmq-red)] bg-[var(--jmq-red-dim)] px-2 py-0.5 font-mono text-[10px]"
                  onClick={() => onDrillMissing({ bucket: r.bucket, tierValue: r.tierValue, missing: r.missing })}
                >
                  ↗
                </button>
              ) : (
                <span className="text-[var(--jmq-green)] text-[10px]">✓</span>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default function EntityQualityDashboard({
  data,
  refreshOpen,
  setRefreshOpen,
}: {
  data: QualityPayload
  refreshOpen: boolean
  setRefreshOpen: (v: boolean | ((b: boolean) => boolean)) => void
}) {
  const [entity, setEntity] = useState<EntityKey>('cities')
  const [section, setSection] = useState<'overview' | 'population' | 'income'>('overview')
  type BucketDrill =
    | {
        mode: 'state_tier'
        field: 'state_population_tier' | 'state_income_level'
        value: string
      }
    | {
        mode: 'entity_acs'
        entityKey: Exclude<EntityKey, 'state'>
        field: 'acs_population_tier' | 'acs_income_level'
        value: string
        expectedMissing: number
      }
  const [bucketDrill, setBucketDrill] = useState<BucketDrill | null>(null)
  const [stateJurisDrill, setStateJurisDrill] = useState<StateQualityRow | null>(null)
  const [stateFilter, setStateFilter] = useState('')
  const [mappedIssuesOpen, setMappedIssuesOpen] = useState(false)

  const location = useLocation()
  const navigate = useNavigate()
  const prevEntityRef = useRef(entity)

  useEffect(() => {
    if (location.hash === '#state') setEntity('state')
  }, [location.hash])

  useEffect(() => {
    if (prevEntityRef.current === 'state' && entity !== 'state' && location.hash === '#state') {
      navigate({ pathname: location.pathname, search: location.search, hash: '' }, { replace: true })
    }
    prevEntityRef.current = entity
  }, [entity, location.hash, location.pathname, location.search, navigate])

  useEffect(() => {
    setStateFilter('')
  }, [entity])

  const summaryByType = data.summary_by_type ?? []
  const muniRows = data.summary_municipality_by_place_kind ?? []
  const popRowsAll = data.summary_by_acs_population_tier ?? []
  const incRowsAll = data.summary_by_acs_income_level ?? []
  const drill = data.drilldown
  const mappedIssues = drill?.mapped_url_issues ?? []

  const stateQualityRows = data.states ?? []

  const filteredRollupRow = useMemo(() => {
    if (entity === 'state' || !stateFilter) return null
    const roll = data.entity_state_rollup
    if (!roll) return null
    return roll[ENTITY_ROLLUP_KEY[entity]]?.find((r) => r.state_code === stateFilter) ?? null
  }, [data.entity_state_rollup, entity, stateFilter])

  const filteredYoutubeRollupRow = useMemo(() => {
    if (!YOUTUBE_ENTITY_KEYS.has(entity) || !stateFilter) return null
    const roll = data.youtube_entity_state_rollup
    if (!roll) return null
    return roll[ENTITY_YOUTUBE_ROLLUP_KEY[entity as Exclude<EntityKey, 'state' | 'schools'>]]?.find(
      (r) => r.state_code === stateFilter,
    ) ?? null
  }, [data.youtube_entity_state_rollup, entity, stateFilter])

  const youtubeDiagEntity = youtubeDiagnosticsEntity(entity)
  const needsLiveYoutubeCoverage =
    YOUTUBE_ENTITY_KEYS.has(entity) &&
    !exportHasYoutubeChannelMetrics(data) &&
    (filteredYoutubeRollupRow == null || filteredYoutubeRollupRow.with_youtube_channel == null)

  const { data: liveYoutubeCoverage } = useQuery({
    queryKey: ['youtube-channel-coverage', youtubeDiagEntity, stateFilter || 'national'],
    queryFn: ({ signal }) =>
      fetchYoutubeChannelCoverage(
        {
          entity: youtubeDiagEntity!,
          state_code: stateFilter.trim() || undefined,
        },
        signal,
      ),
    enabled: needsLiveYoutubeCoverage && youtubeDiagEntity != null,
    staleTime: 60_000,
  })

  // Per-state YouTube rollup falls back to FastAPI when the static JSON section is
  // missing or empty (the JSON goes stale whenever int_events_channels is reloaded).
  // We always fetch when the entity supports YouTube — selection logic in the
  // youtubeRollup memo below prefers JSON when present and uses the API otherwise.
  const { data: liveYoutubeStateRollup } = useQuery({
    queryKey: ['youtube-state-rollup', youtubeDiagEntity],
    queryFn: ({ signal }) => fetchYoutubeStateRollup(youtubeDiagEntity!, signal),
    enabled: youtubeDiagEntity != null,
    staleTime: 60_000,
  })

  const metrics = useMemo(() => {
    if (entity === 'state') return stateGovMetrics(stateQualityRows)
    if (filteredRollupRow) return metricsFromRollupRow(filteredRollupRow)
    return entityMetrics(entity, summaryByType, muniRows)
  }, [entity, filteredRollupRow, stateQualityRows, summaryByType, muniRows])

  const youtubeMetrics = useMemo(() => {
    if (!YOUTUBE_ENTITY_KEYS.has(entity)) return { total: 0, withChannel: 0, pct: 0 }
    if (filteredYoutubeRollupRow?.with_youtube_channel != null) {
      return metricsFromYoutubeRollupRow(filteredYoutubeRollupRow)
    }
    if (liveYoutubeCoverage) {
      return {
        total: liveYoutubeCoverage.total,
        withChannel: liveYoutubeCoverage.with_youtube_channel,
        pct: liveYoutubeCoverage.pct_with_youtube_channel,
      }
    }
    return youtubeEntityMetrics(entity, summaryByType, muniRows)
  }, [entity, filteredYoutubeRollupRow, liveYoutubeCoverage, summaryByType, muniRows])

  const sourceRateRow = useMemo((): PrimarySourceRow | null => {
    if (filteredRollupRow) return null
    if (entity === 'state') return summaryByType.find((x) => x.jurisdiction_type === 'state') ?? null
    if (entity === 'cities') return muniRows?.find((x) => x.municipality_place_kind === 'incorporated_city') ?? null
    if (entity === 'towns')
      return aggregateMuniPrimaryFrom(muniRows, ['incorporated_other', 'unknown', 'census_designated_place'])
    if (entity === 'counties') return summaryByType.find((x) => x.jurisdiction_type === 'county') ?? null
    if (entity === 'schools') return summaryByType.find((x) => x.jurisdiction_type === 'school_district') ?? null
    return null
  }, [entity, filteredRollupRow, muniRows, summaryByType])

  const entityAcsSlice =
    entity !== 'state' ? data.entity_acs_by_slice?.[entity as Exclude<EntityKey, 'state'>] : undefined

  const popTableRows = useMemo(() => {
    if (entity === 'state') {
      return stateBucketTableRows(data.summary_by_state_population_tier, 'state_population_tier', STATE_POPULATION_TIER_ORDER)
    }
    if (entityAcsSlice?.by_population_tier?.length) {
      return entityAcsBucketTableRows(entityAcsSlice, 'by_population_tier')
    }
    const acsJurisdictionFilter = entity === 'counties' ? 'county' : entity === 'schools' ? 'school_district' : 'municipality'
    return popRowsAll
      .filter((r) => r.jurisdiction_type === acsJurisdictionFilter)
      .map((r) => {
        const n = Number(r.total_jurisdictions)
        const w = Number(r.with_primary_website)
        const pct = r.pct_with_primary_website != null ? Number(r.pct_with_primary_website) : n > 0 ? (100 * w) / n : 0
        return { bucket: r.acs_population_tier, tierValue: r.acs_population_tier, n, withUrl: w, pct, missing: Math.max(0, n - w) }
      })
  }, [entity, entityAcsSlice, popRowsAll, data.summary_by_state_population_tier])

  const incTableRows = useMemo(() => {
    if (entity === 'state') {
      return stateBucketTableRows(data.summary_by_state_income_level, 'state_income_level', STATE_INCOME_TIER_ORDER)
    }
    if (entityAcsSlice?.by_income_level?.length) {
      return entityAcsBucketTableRows(entityAcsSlice, 'by_income_level')
    }
    const acsJurisdictionFilter = entity === 'counties' ? 'county' : entity === 'schools' ? 'school_district' : 'municipality'
    return incRowsAll
      .filter((r) => r.jurisdiction_type === acsJurisdictionFilter)
      .map((r) => {
        const n = Number(r.total_jurisdictions)
        const w = Number(r.with_primary_website)
        const pct = r.pct_with_primary_website != null ? Number(r.pct_with_primary_website) : n > 0 ? (100 * w) / n : 0
        return { bucket: r.acs_income_level, tierValue: r.acs_income_level, n, withUrl: w, pct, missing: Math.max(0, n - w) }
      })
  }, [entity, entityAcsSlice, incRowsAll, data.summary_by_state_income_level])

  const popChartData = popTableRows.filter((r) => r.n > 0)
  const incChartData = incTableRows.filter((r) => r.n > 0)

  const rollup = useMemo(() => {
    if (entity === 'state') return stateRowsToRollup(stateQualityRows)
    const roll = data.entity_state_rollup
    if (!roll) return []
    const rows = roll[ENTITY_ROLLUP_KEY[entity]] ?? []
    if (!stateFilter) return rows
    return rows.filter((r) => r.state_code === stateFilter)
  }, [data.entity_state_rollup, entity, stateFilter, stateQualityRows])

  const youtubeRollup = useMemo(() => {
    if (!YOUTUBE_ENTITY_KEYS.has(entity)) return []
    const roll = data.youtube_entity_state_rollup
    const jsonRows = roll
      ? roll[ENTITY_YOUTUBE_ROLLUP_KEY[entity as Exclude<EntityKey, 'state' | 'schools'>]] ?? []
      : []
    // Prefer the live FastAPI rollup when the static JSON section is empty (its
    // export depends on int_events_channels being populated when dbt last ran).
    const rows: YoutubeStateRollupRow[] =
      jsonRows.length > 0 ? jsonRows : liveYoutubeStateRollup?.rows ?? []
    if (!stateFilter) return rows
    return rows.filter((r) => r.state_code === stateFilter)
  }, [data.youtube_entity_state_rollup, entity, stateFilter, liveYoutubeStateRollup])

  const insight = useMemo(() => {
    const { total, withUrl, pct } = metrics
    const miss = total - withUrl
    const fromWikidata = Number(sourceRateRow?.primary_from_wikidata ?? 0)
    const fromGsa = Number(sourceRateRow?.primary_from_gsa ?? 0)
    const fromLeague = Number(sourceRateRow?.primary_from_league ?? 0)
    const fromUscm = Number(sourceRateRow?.primary_from_uscm ?? 0)
    if (entity === 'towns')
      return `${fmt(miss)} incorporated towns/CDPs/unknown-LSAD rows still lack a primary URL (${(100 - pct).toFixed(1)}% gap). GSA and Wikidata (P856) cover part of the long tail; gaps are usually no official website in any source.`
    if (entity === 'cities')
      return `Incorporated cities sit near ${pct.toFixed(1)}% coverage (${fmt(withUrl)} of ${fmt(total)}). Primaries come from GSA (${fmt(fromGsa)}), Wikidata official sites (${fmt(fromWikidata)}), League (${fmt(fromLeague)}), and USCM (${fmt(fromUscm)}). ${fmt(miss)} cities still have no URL — often no Wikidata P856 and no directory match (Wikipedia articles are not used).`
    if (entity === 'counties')
      return `Counties are the best-covered class in most snapshots (~${pct.toFixed(1)}%). NACO, GSA, and Wikidata (P856) supply most primaries; remaining ${fmt(miss)} gaps skew rural / no official website.`
    if (entity === 'state') {
      const yt = data.state_youtube_category_rollup?.summary
      const overallPct = yt?.overall?.pct_mapped
      const ytNote =
        overallPct != null
          ? ` YouTube registry mapping: ${overallPct.toFixed(1)}% of states have an overall government channel; use category pills below for public health, education, and transportation.`
          : ''
      return `${fmt(withUrl)} of ${fmt(total)} state governments have a primary portal URL in the warehouse (${pct.toFixed(1)}%). ${fmt(miss)} states lack one.${ytNote} Population / income tabs group states by ACS tiers.`
    }
    const stateNote = stateFilter ? ` · ${US_STATE_NAMES[stateFilter] ?? stateFilter} (${stateFilter})` : ''
    return `${ENTITY_META[entity].label}${stateNote}: ~${pct.toFixed(1)}% with a primary URL; ${fmt(miss)} still missing. Use the state filter to scope drills to one state.`
  }, [entity, metrics, stateFilter, sourceRateRow, data.state_youtube_category_rollup])

  const acsBucketDrillQuery = useMemo((): UnmappedDrillParams | null => {
    if (!bucketDrill || bucketDrill.mode !== 'entity_acs') return null
    return {
      entity: bucketDrill.entityKey,
      ...(stateFilter ? { state_code: stateFilter } : {}),
      ...(bucketDrill.field === 'acs_population_tier'
        ? { acs_population_tier: bucketDrill.value }
        : { acs_income_level: bucketDrill.value }),
    }
  }, [bucketDrill, stateFilter])

  const syntaxIssueRows = useMemo(() => {
    if (entity !== 'schools') return []
    return mappedIssues.filter((r) => r.jurisdiction_type === 'school_district').slice(0, 40)
  }, [mappedIssues, entity])

  const hasAcs = popRowsAll.length > 0 || incRowsAll.length > 0
  const hasStateAcs = stateQualityRows.some((s) => s.acs_population != null)

  const statePopChartData = useMemo(
    () => stateBucketChartRows(data.summary_by_state_population_tier, 'state_population_tier', STATE_POPULATION_TIER_ORDER),
    [data.summary_by_state_population_tier],
  )
  const stateIncChartData = useMemo(
    () => stateBucketChartRows(data.summary_by_state_income_level, 'state_income_level', STATE_INCOME_TIER_ORDER),
    [data.summary_by_state_income_level],
  )
  const statePopTableRows = useMemo(
    () => stateBucketTableRows(data.summary_by_state_population_tier, 'state_population_tier', STATE_POPULATION_TIER_ORDER),
    [data.summary_by_state_population_tier],
  )
  const stateIncTableRows = useMemo(
    () => stateBucketTableRows(data.summary_by_state_income_level, 'state_income_level', STATE_INCOME_TIER_ORDER),
    [data.summary_by_state_income_level],
  )

  return (
    <div className="jmq-main pb-16">
      {/* top-16 + z-40: align with Layout main pt-16; stay below global fixed header (z-50) when scrolling */}
      <header className="sticky top-16 z-40 mb-6 border-b border-[var(--jmq-border)] bg-[var(--jmq-surface)] py-4 shadow-md [isolation:isolate]">
        <div className="jmq-header !border-b-0 !px-0 !py-0">
          <Link
            to={`${DATA_EXPLORER_MAP_BASE}/us/2024/median_household_income`}
            className="order-last inline-flex shrink-0 items-center gap-1.5 font-mono text-xs font-semibold text-[var(--jmq-teal)] hover:opacity-90 sm:order-none"
          >
            <ArrowLeftIcon className="h-3.5 w-3.5" />
            Map
          </Link>
          <div className="jmq-logo">C1</div>
          <div className="min-w-0">
            <div className="jmq-hdr-title">Open Navigator — Data Quality</div>
            <div className="font-mono text-[11px] text-[var(--jmq-text-muted)]">
              jurisdiction_mapping_quality.json · NACo / USCM / NCES / GSA / Wikidata · YouTube (int_events_channels)
            </div>
          </div>
          <div className="jmq-hdr-sub hidden flex-wrap justify-end gap-2 lg:flex">
            <span className="rounded border border-[var(--jmq-border)] bg-[var(--jmq-surface2)] px-2 py-0.5 font-mono text-[10px]">
              {entity === 'state'
                ? hasStateAcs
                  ? `State ACS ${data.acs_vintage_year ?? ''}`.trim()
                  : 'State ACS missing'
                : hasAcs
                  ? 'ACS in JSON'
                  : 'ACS empty'}
            </span>
            <span className="rounded border border-[var(--jmq-border)] px-2 py-0.5 font-mono text-[10px] text-[var(--jmq-text-muted)]">
              Snapshot
            </span>
          </div>
        </div>
      </header>

      {bucketDrill?.mode === 'state_tier' ? (
        <StateTierDrillPanel
          tierLabel={bucketDrill.field === 'state_population_tier' ? 'state population' : 'state income'}
          tierField={bucketDrill.field}
          tierValue={bucketDrill.value}
          states={stateQualityRows}
          onClose={() => setBucketDrill(null)}
          onDrillState={(s) => {
            setBucketDrill(null)
            setStateJurisDrill(s)
          }}
        />
      ) : null}
      {stateJurisDrill ? (
        <DrillPanel
          query={{ entity: 'state', state_code: stateJurisDrill.state_code }}
          expectedMissing={1}
          title="State without portal"
          subtitle={`${stateJurisDrill.state_name} (${stateJurisDrill.state_code}) · state government`}
          bannerExtra={statePortalDetailLines(stateJurisDrill).join(' · ')}
          onClose={() => setStateJurisDrill(null)}
        />
      ) : null}
      {acsBucketDrillQuery && bucketDrill?.mode === 'entity_acs' ? (
        <DrillPanel
          query={acsBucketDrillQuery}
          expectedMissing={bucketDrill.expectedMissing}
          title="Missing primary URL"
          subtitle={`${ENTITY_META[bucketDrill.entityKey].label} · ${bucketDrill.value}`}
          onClose={() => setBucketDrill(null)}
        />
      ) : null}

      {mappedIssuesOpen ? (
        <div
          className="fixed inset-0 z-[200] flex items-start justify-end bg-black/40 p-4"
          role="dialog"
          aria-modal
        >
          <div className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-xl border border-[var(--jmq-border)] bg-[var(--jmq-surface)] shadow-2xl">
            <div className="flex items-center justify-between border-b border-[var(--jmq-border)] px-4 py-3">
              <div className="text-sm font-bold text-[var(--jmq-text)]">Mapped URL static-check sample (school districts)</div>
              <button
                type="button"
                className="rounded-md border border-[var(--jmq-border)] bg-[var(--jmq-surface2)] px-2 py-1 text-xs"
                onClick={() => setMappedIssuesOpen(false)}
              >
                ✕ Close
              </button>
            </div>
            <div className="overflow-auto p-2">
              {syntaxIssueRows.length === 0 ? (
                <p className="p-6 text-center text-sm text-[var(--jmq-text-muted)]">No school-district rows in mapped_url_issues sample.</p>
              ) : (
                <table className="jmq-dt w-full text-[11px]">
                  <thead>
                    <tr>
                      {['State', 'Name', 'Source', 'URL', 'Flags'].map((h) => (
                        <th key={h}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {syntaxIssueRows.map((r) => (
                      <tr key={r.jurisdiction_id}>
                        <td className="font-mono">{r.state_code}</td>
                        <td>{r.name}</td>
                        <td className="font-mono">{r.primary_website_source ?? '—'}</td>
                        <td className="max-w-[14rem] break-all font-mono text-[10px]">{r.primary_website_url ?? '—'}</td>
                        <td className="font-mono text-[10px] text-[var(--jmq-red)]">
                          {[
                            r.primary_url_syntax_ok === false && 'syntax',
                            r.primary_url_likely_wrong_host && 'host',
                            r.primary_url_passes_basic_checks === false && 'basic',
                          ]
                            .filter(Boolean)
                            .join(' · ') || '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      ) : null}

      <div className="mb-6 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
        {(Object.keys(ENTITY_META) as EntityKey[]).map((ek) => {
          const m = ek === 'state' ? stateGovMetrics(stateQualityRows) : entityMetrics(ek, summaryByType, muniRows)
          const active = entity === ek
          return (
            <button
              key={ek}
              type="button"
              onClick={() => {
                setEntity(ek)
                setSection('overview')
                if (ek === 'state') {
                  navigate({ pathname: location.pathname, search: location.search, hash: 'state' }, { replace: true })
                  return
                }
                if (location.hash === '#state') {
                  navigate({ pathname: location.pathname, search: location.search, hash: '' }, { replace: true })
                }
              }}
              className={`rounded-[10px] border p-3 text-left transition-colors ${
                active ? 'border-[var(--jmq-teal)] bg-[var(--jmq-surface)] shadow-sm' : 'border-[var(--jmq-border)] bg-[var(--jmq-surface2)] hover:bg-[#e6eaef]'
              }`}
            >
              <div className="mb-2 flex items-center gap-2">
                <span className="text-lg">{ENTITY_META[ek].icon}</span>
                <span className={`text-[13px] font-bold ${active ? 'text-[var(--jmq-teal)]' : 'text-[var(--jmq-text-muted)]'}`}>
                  {ENTITY_META[ek].label}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <div className="h-1 flex-1 overflow-hidden rounded bg-[var(--jmq-border)]">
                  <div className="h-full rounded" style={{ width: `${Math.min(100, m.pct)}%`, background: barColor(m.pct) }} />
                </div>
                <span className="font-mono text-xs font-bold" style={{ color: barColor(m.pct) }}>
                  {m.pct.toFixed(1)}%
                </span>
              </div>
              <div className="mt-1 font-mono text-[10px] text-[var(--jmq-text-muted)]">
                {ek === 'state' ? 'portals' : 'coverage'} · {fmt(m.withUrl)} / {fmt(m.total)}
              </div>
            </button>
          )
        })}
      </div>

      <nav
        className="mb-5 flex flex-wrap items-center gap-1 border-b border-[var(--jmq-border)]"
        aria-label={`${ENTITY_META[entity].label} sections`}
      >
        {(
          [
            ['overview', 'Overview'],
            ['population', 'By population'],
            ['income', 'By income'],
          ] as const
        ).map(([id, lbl]) => (
          <button
            key={id}
            type="button"
            onClick={() => setSection(id)}
            className={`rounded-t-md border border-b-0 px-3 py-2 text-xs font-medium ${
              section === id
                ? 'border-[var(--jmq-border)] bg-[var(--jmq-surface)] text-[var(--jmq-teal)]'
                : 'border-transparent text-[var(--jmq-text-muted)] hover:text-[var(--jmq-text)]'
            }`}
          >
            {lbl}
          </button>
        ))}
        {entity === 'schools' && mappedIssues.length > 0 ? (
          <button
            type="button"
            className="ml-auto self-center rounded border border-[var(--jmq-amber)] bg-[var(--jmq-amber-dim)] px-2 py-1 font-mono text-[11px] text-[#4d2d00]"
            onClick={() => setMappedIssuesOpen(true)}
          >
            URL shape sample ({syntaxIssueRows.length})
          </button>
        ) : null}
      </nav>

      {entity !== 'state' ? (
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <label htmlFor="jmq-state-filter" className="font-mono text-[10px] font-semibold uppercase text-[var(--jmq-text-muted)]">
            State filter
          </label>
          <select
            id="jmq-state-filter"
            value={stateFilter}
            onChange={(e) => setStateFilter(e.target.value)}
            className="min-w-[12rem] rounded-md border border-[var(--jmq-border)] bg-[var(--jmq-surface)] px-2 py-1.5 text-xs text-[var(--jmq-text)]"
          >
            <option value="">All states (national)</option>
            {Object.keys(US_STATE_NAMES)
              .sort()
              .map((sc) => (
                <option key={sc} value={sc}>
                  {sc} — {US_STATE_NAMES[sc]}
                </option>
              ))}
          </select>
          {stateFilter ? (
            <span className="font-mono text-[10px] text-[var(--jmq-text-muted)]">
              Scoping KPIs, insight, and drills to {US_STATE_NAMES[stateFilter] ?? stateFilter}
            </span>
          ) : null}
        </div>
      ) : null}

      <div className="mb-5 grid grid-cols-2 gap-2 sm:grid-cols-5">
        {[
          { label: 'Total', val: fmt(metrics.total), c: 'var(--jmq-text-muted)' },
          { label: 'With URL', val: fmt(metrics.withUrl), c: 'var(--jmq-teal)' },
          { label: 'Coverage', val: `${metrics.pct.toFixed(1)}%`, c: barColor(metrics.pct) },
          { label: 'Missing', val: fmt(Math.max(0, metrics.total - metrics.withUrl)), c: metrics.total - metrics.withUrl > 5000 ? '#a40e26' : '#9a6700' },
          { label: 'Syntax gaps†', val: fmt(metrics.syntaxErr), c: metrics.syntaxErr > 0 ? '#9a6700' : 'var(--jmq-green)' },
        ].map((k) => (
          <div key={k.label} className="jmq-kpi jmq-kpi--info relative overflow-hidden rounded-lg border border-[var(--jmq-border)] bg-[var(--jmq-surface)] p-3">
            <div className="absolute left-0 right-0 top-0 h-0.5" style={{ background: k.c }} />
            <div className="jmq-kpi-label !mb-1">{k.label}</div>
            <div className="font-mono text-xl font-extrabold leading-tight" style={{ color: k.c }}>
              {k.val}
            </div>
          </div>
        ))}
      </div>
      <p className="mb-4 font-mono text-[10px] text-[var(--jmq-text-muted)]">
        † Among rows with a primary URL: jurisdictions failing static syntax vs counted “syntax OK” in summary tables.
      </p>

      {YOUTUBE_ENTITY_KEYS.has(entity) ? (
        <>
          <div className="mb-2 font-mono text-[10px] font-semibold uppercase tracking-wide text-[var(--jmq-text-muted)]">
            YouTube channel URL match · intermediate.int_events_channels
          </div>
          <div className="mb-5 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {(
              [
                {
                  label: 'Total',
                  display: fmtCompact(youtubeMetrics.total),
                  title: formatFullNumber(youtubeMetrics.total),
                  c: 'var(--jmq-text-muted)',
                  href: undefined as string | undefined,
                },
                {
                  label: 'With channel',
                  display: fmtCompact(youtubeMetrics.withChannel),
                  title: formatFullNumber(youtubeMetrics.withChannel),
                  c: 'var(--jmq-blue)',
                  href: undefined as string | undefined,
                },
                {
                  label: 'Match rate',
                  display: `${youtubeMetrics.pct.toFixed(1)}%`,
                  title: undefined,
                  c: barColor(youtubeMetrics.pct),
                  href: undefined as string | undefined,
                },
                {
                  label: 'Missing',
                  display: fmtCompact(Math.max(0, youtubeMetrics.total - youtubeMetrics.withChannel)),
                  title: formatFullNumber(Math.max(0, youtubeMetrics.total - youtubeMetrics.withChannel)),
                  c: youtubeMetrics.total - youtubeMetrics.withChannel > 500 ? '#a40e26' : '#9a6700',
                  // Drill into the jurisdictions with no golden channel (per-state, then individual).
                  href: '#jmq-missing-youtube-by-state' as string | undefined,
                },
              ] as const
            ).map((k) => {
              const inner = (
                <>
                  <div className="absolute left-0 right-0 top-0 h-0.5" style={{ background: k.c }} />
                  <div className="jmq-kpi-label !mb-1">
                    {k.label}
                    {k.href ? <span className="ml-1 text-[var(--jmq-text-muted)]">↓</span> : null}
                  </div>
                  <div
                    className="font-mono text-xl font-extrabold leading-tight"
                    style={{ color: k.c }}
                    title={k.title}
                  >
                    {k.display}
                  </div>
                </>
              )
              const cls =
                'jmq-kpi jmq-kpi--info relative overflow-hidden rounded-lg border border-[var(--jmq-border)] bg-[var(--jmq-surface)] p-3'
              return k.href ? (
                <a
                  key={k.label}
                  href={k.href}
                  className={`${cls} block transition-colors hover:border-[var(--jmq-teal)] hover:bg-[var(--jmq-teal-dim)]`}
                  title="Drill into jurisdictions with no golden YouTube channel"
                >
                  {inner}
                </a>
              ) : (
                <div key={k.label} className={cls}>
                  {inner}
                </div>
              )
            })}
          </div>
          {needsLiveYoutubeCoverage && liveYoutubeCoverage ? (
            <p className="mb-4 font-mono text-[10px] text-[var(--jmq-text-muted)]">
              YouTube KPIs from live <code>int_events_channels</code> join (export JSON lacks{' '}
              <code>with_youtube_channel</code> — re-run dbt + export for offline snapshot).
            </p>
          ) : null}
        </>
      ) : null}

      {entity === 'state' && section === 'overview' ? (
        <div className="space-y-4">
          <div className="grid gap-3 lg:grid-cols-[1fr_200px]">
            <div className="rounded-lg border border-[var(--jmq-teal)]/30 bg-[var(--jmq-teal-dim)] px-4 py-3 text-sm leading-relaxed text-[var(--jmq-text)]">
              <span className="font-bold text-[var(--jmq-teal)]">Insight · </span>
              {insight}
              {data.state_youtube_category_rollup ? (
                <p className="mt-2 font-mono text-[11px]">
                  <a
                    href="#jmq-state-youtube-by-category"
                    className="font-semibold text-[var(--jmq-teal)] underline-offset-2 hover:underline"
                  >
                    ↓ YouTube URL mapping by policy category
                  </a>
                </p>
              ) : null}
            </div>
            <TypicalStatePortalSourcesCard row={sourceRateRow} total={metrics.total} withUrl={metrics.withUrl} />
          </div>
          {!hasStateAcs ? (
            <div className="rounded-lg border border-[var(--jmq-amber)]/40 bg-[var(--jmq-amber-dim)] px-4 py-3 text-sm text-[#4d2d00]">
              State ACS parquets missing. Run{' '}
              <code className="text-[11px]">download_census_acs_data.py --geography state --state &apos;*&apos;</code> then
              re-export mapping quality JSON.
            </div>
          ) : null}
          <div className="grid gap-3 lg:grid-cols-3">
            <div className="jmq-card">
              <div className="jmq-card-title">By state population (ACS)</div>
              <p className="jmq-card-sub">State B01003 tiers · % of state governments with a primary portal.</p>
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={statePopChartData} margin={{ top: 8, right: 8, bottom: 28, left: 12 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--jmq-border)" />
                    <XAxis dataKey="bucket" tick={{ fontSize: 8, fill: 'var(--jmq-text-muted)' }} angle={-20} textAnchor="end" interval={0} height={48} />
                    <YAxis domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={{ fontSize: 9, fill: 'var(--jmq-text-muted)' }} width={44} />
                    <Tooltip formatter={(v: number) => [`${v.toFixed(1)}%`, AXIS_LABEL_PCT_WITH_PRIMARY_URL]} />
                    <Bar dataKey="pct" radius={[3, 3, 0, 0]}>
                      {statePopChartData.map((d, i) => (
                        <Cell key={i} fill={barColor(d.pct)} fillOpacity={0.85} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
            <div className="jmq-card">
              <div className="jmq-card-title">By state income (ACS)</div>
              <p className="jmq-card-sub">State B19013 median household income tiers.</p>
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={stateIncChartData} margin={{ top: 8, right: 8, bottom: 8, left: 12 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--jmq-border)" />
                    <XAxis dataKey="bucket" tick={{ fontSize: 9, fill: 'var(--jmq-text-muted)' }} />
                    <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 9, fill: 'var(--jmq-text-muted)' }} width={44} />
                    <Tooltip formatter={(v: number) => [`${v.toFixed(1)}%`, AXIS_LABEL_PCT_WITH_PRIMARY_URL]} />
                    <Bar dataKey="pct" radius={[3, 3, 0, 0]}>
                      {stateIncChartData.map((d, i) => (
                        <Cell key={i} fill={barColor(d.pct)} fillOpacity={0.85} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
            <div className="jmq-card">
              <div className="jmq-card-title">{sourceMappingChartCopy(entity).title}</div>
              <p className="jmq-card-sub">{sourceMappingChartCopy(entity).sub}</p>
              <SourceMappingBarChart row={sourceRateRow} total={metrics.total} withUrl={metrics.withUrl} entity={entity} />
            </div>
          </div>
          <SourceMappingRatesCard row={sourceRateRow} total={metrics.total} withUrl={metrics.withUrl} entity={entity} />
          {rollup.length === 0 ? (
            <div className="jmq-placeholder">
              <strong>No state rollup in JSON</strong>
              Re-run <code>export_jurisdiction_mapping_quality_json.py</code> after updating the repo.
            </div>
          ) : (
            <StateAnalysisSection rollup={rollup} stateQuality={stateQualityRows} />
          )}
          {data.state_youtube_category_rollup ? (
            <StateYoutubeCategorySection rollup={data.state_youtube_category_rollup} />
          ) : null}
        </div>
      ) : null}
      {entity === 'state' && section === 'population' ? (
        <div className="space-y-4">
          <SourceMappingRatesCard row={sourceRateRow} total={metrics.total} withUrl={metrics.withUrl} entity={entity} compact />
        <div className="jmq-card">
          <div className="jmq-card-title">State population buckets</div>
          <p className="jmq-card-sub">
            ACS state population tiers. Counts are state governments with a primary portal — not cities or counties in those states.
          </p>
          {!hasStateAcs ? (
            <div className="mb-3 rounded-lg border border-[var(--jmq-amber)]/40 bg-[var(--jmq-amber-dim)] px-3 py-2 text-sm text-[#4d2d00]">
              State ACS is missing from <code>jurisdiction_mapping_quality.json</code>. Re-run the export (it can
              fetch Census state B01003/B19013 automatically) or download parquets first — steps under Refresh.
            </div>
          ) : null}
          <SectionTable
            variant="state_portal"
            rows={statePopTableRows}
            onDrillMissing={({ tierValue }) =>
              setBucketDrill({
                mode: 'state_tier',
                field: 'state_population_tier',
                value: tierValue ?? '',
              })
            }
          />
        </div>
        </div>
      ) : null}
      {entity === 'state' && section === 'income' ? (
        <div className="space-y-4">
          <SourceMappingRatesCard row={sourceRateRow} total={metrics.total} withUrl={metrics.withUrl} entity={entity} compact />
        <div className="jmq-card">
          <div className="jmq-card-title">State income buckets</div>
          <p className="jmq-card-sub">ACS state median income tiers. Counts are state governments with a mapped portal.</p>
          {!hasStateAcs ? (
            <div className="mb-3 rounded-lg border border-[var(--jmq-amber)]/40 bg-[var(--jmq-amber-dim)] px-3 py-2 text-sm text-[#4d2d00]">
              State ACS is missing from the export. Re-run{' '}
              <code className="text-[11px]">export_jurisdiction_mapping_quality_json.py</code> (see Refresh).
            </div>
          ) : null}
          <SectionTable
            variant="state_portal"
            rows={stateIncTableRows}
            onDrillMissing={({ tierValue }) =>
              setBucketDrill({
                mode: 'state_tier',
                field: 'state_income_level',
                value: tierValue ?? '',
              })
            }
          />
        </div>
        </div>
      ) : null}
      {entity !== 'state' ? (
        <>
      {section === 'overview' && (
        <div className="space-y-4">
          <div className="grid gap-3 lg:grid-cols-[1fr_200px]">
            <div className="rounded-lg border border-[var(--jmq-teal)]/30 bg-[var(--jmq-teal-dim)] px-4 py-3 text-sm leading-relaxed text-[var(--jmq-text)]">
              <span className="font-bold text-[var(--jmq-teal)]">Insight · </span>
              {insight}
              {rollup.length > 0 ? (
                <p className="mt-2 font-mono text-[11px]">
                  <a href="#jmq-missing-by-state" className="font-semibold text-[var(--jmq-teal)] underline-offset-2 hover:underline">
                    ↓ Drill missing URLs by state
                  </a>
                </p>
              ) : null}
            </div>
            <div className="jmq-card !py-3">
              <div className="mb-2 font-mono text-[10px] font-semibold uppercase text-[var(--jmq-text-muted)]">Sources touched</div>
              <div className="flex flex-col gap-1">
                {ENTITY_META[entity].sourceKeys.map((s) => (
                  <span key={s} className={sourceBadgeClass(s)}>
                    {s}
                  </span>
                ))}
              </div>
            </div>
          </div>
          <div className="grid gap-3 lg:grid-cols-3">
            <div className="jmq-card">
              <div className="jmq-card-title">By population (ACS)</div>
              <p className="jmq-card-sub">
                {entityAcsSlice
                  ? `${ENTITY_META[entity].label} only.`
                  : entity === 'cities' || entity === 'towns'
                    ? 'All municipalities in ACS mart — use Cities / Towns for place-kind splits.'
                    : ''}
              </p>
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={popChartData} margin={{ top: 8, right: 8, bottom: 28, left: 12 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--jmq-border)" />
                    <XAxis dataKey="bucket" tick={{ fontSize: 8, fill: 'var(--jmq-text-muted)' }} angle={-20} textAnchor="end" interval={0} height={48} />
                    <YAxis
                      domain={[0, 100]}
                      tickFormatter={(v) => `${v}%`}
                      tick={{ fontSize: 9, fill: 'var(--jmq-text-muted)' }}
                      width={44}
                      label={{
                        value: AXIS_LABEL_PCT_WITH_PRIMARY_URL,
                        angle: -90,
                        position: 'insideLeft',
                        offset: 2,
                        fill: 'var(--jmq-text-muted)',
                        fontSize: 11,
                        fontWeight: 600,
                      }}
                    />
                    <Tooltip formatter={(v: number) => [`${v.toFixed(1)}%`, AXIS_LABEL_PCT_WITH_PRIMARY_URL]} />
                    <Bar dataKey="pct" name={AXIS_LABEL_PCT_WITH_PRIMARY_URL} radius={[3, 3, 0, 0]}>
                      {popChartData.map((d, i) => (
                        <Cell key={i} fill={barColor(d.pct)} fillOpacity={0.85} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
            <div className="jmq-card">
              <div className="jmq-card-title">By income (ACS)</div>
              <p className="jmq-card-sub"> </p>
              <div className="h-48">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={incChartData} margin={{ top: 8, right: 8, bottom: 8, left: 12 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--jmq-border)" />
                    <XAxis dataKey="bucket" tick={{ fontSize: 9, fill: 'var(--jmq-text-muted)' }} />
                    <YAxis
                      tickFormatter={(v) => `${v}%`}
                      tick={{ fontSize: 9, fill: 'var(--jmq-text-muted)' }}
                      width={44}
                      label={{
                        value: AXIS_LABEL_PCT_WITH_PRIMARY_URL,
                        angle: -90,
                        position: 'insideLeft',
                        offset: 2,
                        fill: 'var(--jmq-text-muted)',
                        fontSize: 11,
                        fontWeight: 600,
                      }}
                    />
                    <Tooltip formatter={(v: number) => [`${v.toFixed(1)}%`, AXIS_LABEL_PCT_WITH_PRIMARY_URL]} />
                    <Bar dataKey="pct" radius={[3, 3, 0, 0]}>
                      {incChartData.map((d, i) => (
                        <Cell key={i} fill={barColor(d.pct)} fillOpacity={0.85} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
            <div className="jmq-card">
              <div className="jmq-card-title">{sourceMappingChartCopy(entity).title}</div>
              <p className="jmq-card-sub">{sourceMappingChartCopy(entity).sub}</p>
              <SourceMappingBarChart row={sourceRateRow} total={metrics.total} withUrl={metrics.withUrl} entity={entity} />
            </div>
          </div>
          <SourceMappingRatesCard row={sourceRateRow} total={metrics.total} withUrl={metrics.withUrl} entity={entity} />
          {rollup.length === 0 ? (
            <div className="jmq-placeholder">
              <strong>No per-state rollup in JSON</strong>
              Re-run <code>export_jurisdiction_mapping_quality_json.py</code> so <code>entity_state_rollup</code> is populated.
            </div>
          ) : (
            <EntityStateRollupSection
              entity={entity}
              rollup={rollup}
              stateQuality={stateQualityRows}
            />
          )}
              {YOUTUBE_ENTITY_KEYS.has(entity) ? (
            youtubeRollup.length === 0 ? (
              <div className="jmq-placeholder">
                <strong>No YouTube state rollup available</strong>
                Live FastAPI rollup returned no rows for this entity. Check{' '}
                <code>intermediate.int_events_channels</code> has data, then refresh.
              </div>
            ) : (
              <EntityStateRollupSection
                entity={entity}
                rollup={youtubeRollup}
                stateQuality={stateQualityRows}
                variant="youtube"
              />
            )
          ) : null}
          {YOUTUBE_ENTITY_KEYS.has(entity) ? (
            <>
              <p className="font-mono text-[11px]">
                <a
                  href="#jmq-youtube-channel-diagnostics"
                  className="font-semibold text-[var(--jmq-teal)] underline-offset-2 hover:underline"
                >
                  ↓ YouTube channel diagnostics (int_events_channels vs bronze videos)
                </a>
              </p>
              <CountyYoutubeDiagnosticsSection
                entity={entity}
                stateFilter={stateFilter}
                onPickState={setStateFilter}
              />
            </>
          ) : null}
        </div>
      )}

      {section === 'population' && (
        <div className="space-y-4">
          <SourceMappingRatesCard row={sourceRateRow} total={metrics.total} withUrl={metrics.withUrl} entity={entity} compact />
        <div className="jmq-card">
          <div className="jmq-card-title">Population buckets</div>
          <p className="jmq-card-sub">
            {entity === 'cities'
              ? 'Incorporated cities only — each city’s ACS population size.'
              : entity === 'towns'
                ? 'Towns, villages, and CDPs only.'
                : entity === 'counties'
                  ? 'Counties only.'
                  : 'School districts only.'}{' '}
            State tiers (Very Large, Large, …) are on the <strong>State</strong> tile.
          </p>
          <SectionTable
            rows={popTableRows}
            onDrillMissing={({ tierValue, missing }) =>
              setBucketDrill({
                mode: 'entity_acs',
                entityKey: entity,
                field: 'acs_population_tier',
                value: tierValue ?? '',
                expectedMissing: missing,
              })
            }
          />
        </div>
        </div>
      )}

      {section === 'income' && (
        <div className="space-y-4">
          <SourceMappingRatesCard row={sourceRateRow} total={metrics.total} withUrl={metrics.withUrl} entity={entity} compact />
        <div className="jmq-card">
          <div className="jmq-card-title">Income buckets</div>
          <p className="jmq-card-sub">
            {entity === 'cities'
              ? 'Incorporated cities only.'
              : entity === 'towns'
                ? 'Towns, villages, and CDPs only.'
                : entity === 'counties'
                  ? 'Counties only.'
                  : 'School districts only.'}{' '}
            State income tiers are on the <strong>State</strong> tile.
          </p>
          <SectionTable
            rows={incTableRows}
            onDrillMissing={({ tierValue, missing }) =>
              setBucketDrill({
                mode: 'entity_acs',
                entityKey: entity,
                field: 'acs_income_level',
                value: tierValue ?? '',
                expectedMissing: missing,
              })
            }
          />
        </div>
        </div>
      )}

        </>
      ) : null}

      <div className="jmq-refresh mt-10">
        <button
          type="button"
          className="jmq-refresh-toggle"
          onClick={() => setRefreshOpen((o) => !o)}
          aria-expanded={refreshOpen}
        >
          <span>Refresh this dashboard</span>
          <ChevronDownIcon className={`h-5 w-5 shrink-0 transition-transform ${refreshOpen ? 'rotate-180' : ''}`} />
        </button>
        {refreshOpen ? (
          <div className="jmq-refresh-panel">
            <div className="jmq-alert jmq-alert--warn">
              <InformationCircleIcon className="jmq-alert-icon h-5 w-5 shrink-0" />
              <ol className="list-inside list-decimal space-y-2 text-sm">
                <li>
                  Build marts:{' '}
                  <code className="text-[11px]">./scripts/dbt.sh run --select jurisdiction_mapping_analysis+</code>
                </li>
                <li>
                  State ACS (needs <code className="text-[11px]">CENSUS_API_KEY</code> in .env):{' '}
                  <code className="text-[11px]">
                    .venv/bin/python scripts/datasources/census/download_census_acs_data.py --geography state --state
                    &apos;*&apos; --year 2022
                  </code>
                  — or re-export below (auto-fetches B01003/B19013 when parquets are absent).
                </li>
                <li>
                  Export:{' '}
                  <code className="text-[11px]">
                    .venv/bin/python scripts/datasources/jurisdictions/export_jurisdiction_mapping_quality_json.py
                  </code>
                </li>
                <li>Hard-refresh this page.</li>
              </ol>
              {data.generated_at ? (
                <p className="mt-2 font-mono text-[11px] text-[var(--jmq-text-muted)]">
                  Generated {data.generated_at}
                  {data.database_host ? ` · ${data.database_host}` : ''}
                </p>
              ) : null}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}
