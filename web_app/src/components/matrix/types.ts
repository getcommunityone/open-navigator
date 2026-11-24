import type { CSSProperties } from 'react'
import type { CensusMetricFormatRow } from '../../utils/censusMapTransforms'
import type { CensusRegionId } from '../../utils/censusRegions'
import type { FolioTheme } from '../../utils/folioThemes'

export type Metric = CensusMetricFormatRow & { label: string }
export type Manifest = { vintage?: string; vintages?: string[]; metrics?: Metric[] }
export type StatePayload = { values: Record<string, Record<string, number | null | undefined>> }

export interface Row {
  fips: string
  code: string
  name: string
  region: CensusRegionId | null
  vals: Record<string, number | null>
}

export type SectionId =
  | 'tiles'
  | 'share'
  | 'pivot'
  | 'dumbbell'
  | 'bars'
  | 'trend'
  | 'columns'
  | 'heatmap'
  | 'diverging'
  | 'scatter'
  | 'dots'
  | 'table'

export const SECTIONS: ReadonlyArray<{ id: SectionId; name: string }> = [
  { id: 'tiles', name: 'Tiles' },
  { id: 'share', name: 'Share' },
  { id: 'pivot', name: 'Pivot' },
  { id: 'dumbbell', name: 'Compare' },
  { id: 'bars', name: 'Bars' },
  { id: 'trend', name: 'Trend' },
  { id: 'columns', name: 'Columns' },
  { id: 'heatmap', name: 'Heatmap' },
  { id: 'diverging', name: 'Diverging' },
  { id: 'scatter', name: 'Scatter' },
  { id: 'dots', name: 'Dot map' },
  { id: 'table', name: 'Table' },
]

/** What every section needs from the page: the loaded data in scope, the shared controls and the URL. */
export interface MatrixCtx {
  sp: URLSearchParams
  setQP: (k: string, v: string | null) => void
  /** Change one param from its latest value. */
  updateQP: (k: string, fn: (prev: string | null) => string | null) => void
  /** Set several params in one navigation. */
  setMany: (entries: Record<string, string | null>) => void
  reduced: boolean
  theme: FolioTheme
  metrics: Metric[]
  countMetrics: Metric[]
  metricSlug: string
  metricLabel: string
  vintage: string
  /** Every vintage in the bundle, oldest first. */
  vintages: string[]
  rows: Row[]
  /** Rows per vintage as loaded; null = the file is missing, undefined = still loading. */
  rowsByVintage: Record<string, Row[] | null | undefined>
  fmt: (slug: string, v: number | null) => string
  labelOf: (slug: string) => string
  /** 0..1 rank shade for a metric's value across the current states (flipped when lower is better). */
  shade: Record<string, (v: number | null) => number | null>
  /** Link to the Map view for the metric in view. */
  mapHref: string
  minPct: number
  /** `?sort=` when it names "name" or a metric (what Pivot, Heatmap and Table order by); else "". */
  sortKey: string
  /** `?sort=` exactly as written (Compare also reads "change" and "base"). */
  sortRaw: string
  sortDir: 'asc' | 'desc'
  /** Count of geographies, as "N states and territories". */
  geoNoun: string
  /** The geography (FIPS) a Pivot row is hovered or focused on; Tiles highlights the matching tile. Null when none. */
  hotFips: string | null
  setHotFips: (fips: string | null) => void
}

export const delayVar = (ms: number): CSSProperties => ({ '--delay': `${Math.round(ms)}ms` }) as CSSProperties

export interface TableSpec {
  columns: Array<{ label: string; numeric?: boolean }>
  rows: string[][]
}
