/** Base path for the choropleth map under Data explorer (ACS 5-year static bundle). */
export const DATA_EXPLORER_MAP_BASE = '/data-explorer/map'

/** Scorecard tab (trends + benchmarks). */
export const DATA_EXPLORER_SCORECARD = '/data-explorer/scorecard'

/** Prefer new prefix; support legacy `/census-map` URLs until removed. */
export function censusMapPathPrefix(pathname: string): string {
  if (pathname.includes(`${DATA_EXPLORER_MAP_BASE}/`) || pathname === DATA_EXPLORER_MAP_BASE) {
    return DATA_EXPLORER_MAP_BASE
  }
  if (pathname.includes('/census-map/') || pathname === '/census-map') {
    return '/census-map'
  }
  return DATA_EXPLORER_MAP_BASE
}

export function mapPathUs(prefix: string, vintage: string, metric: string, search?: string) {
  const q = search && search.length > 0 ? (search.startsWith('?') ? search : `?${search}`) : ''
  return `${prefix}/us/${vintage}/${metric}${q}`
}

export function mapPathState(prefix: string, stateFips: string, vintage: string, metric: string, search?: string) {
  const q = search && search.length > 0 ? (search.startsWith('?') ? search : `?${search}`) : ''
  return `${prefix}/state/${stateFips}/${vintage}/${metric}${q}`
}

export function mapPathPlace(prefix: string, stateFips: string, vintage: string, metric: string, search?: string) {
  const q = search && search.length > 0 ? (search.startsWith('?') ? search : `?${search}`) : ''
  return `${prefix}/place/${stateFips}/${vintage}/${metric}${q}`
}
