/**
 * Dot-matrix map geometry, shared by the Census dot map (DotMatrixMap) and the Data Story
 * Overview map (StoryDotMap, #970): US Albers shapes from us-atlas, and a square grid of dots
 * clipped to them. Each dot knows which area (state or county FIPS) it sits in.
 */
import { geoPath } from 'd3-geo'
import { feature } from 'topojson-client'

export const STATES_ALBERS_TOPO = 'https://cdn.jsdelivr.net/npm/us-atlas@3/states-albers-10m.json'
export const COUNTIES_ALBERS_TOPO = 'https://cdn.jsdelivr.net/npm/us-atlas@3/counties-albers-10m.json'

export type Ring = number[][]
export interface Feat {
  id: string
  name: string
  polys: Ring[][] // polygon -> rings
  bbox: [number, number, number, number]
}
export interface Dot {
  x: number
  y: number
  id: string
}

const inRing = (x: number, y: number, ring: Ring): boolean => {
  let inside = false
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i]!
    const [xj, yj] = ring[j]!
    if (yi > y !== yj > y && x < ((xj! - xi!) * (y - yi!)) / (yj! - yi!) + xi!) inside = !inside
  }
  return inside
}
const inFeat = (x: number, y: number, f: Feat): boolean => {
  const [x0, y0, x1, y1] = f.bbox
  if (x < x0 || x > x1 || y < y0 || y > y1) return false
  return f.polys.some((rings) => rings.reduce((n, r) => n + (inRing(x, y, r) ? 1 : 0), 0) % 2 === 1)
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function toFeats(topo: any, objName: string): Feat[] {
  const fc = feature(topo, topo.objects[objName]) as unknown as {
    features: { id?: string | number; properties?: { name?: string }; geometry: { type: string; coordinates: unknown } | null }[]
  }
  const path = geoPath()
  return fc.features
    .filter((f) => f.geometry)
    .map((f) => {
      const g = f.geometry!
      const polys = (g.type === 'Polygon' ? [g.coordinates] : g.coordinates) as Ring[][]
      const b = path.bounds(f as never)
      return { id: String(f.id ?? '').padStart(objName === 'states' ? 2 : 5, '0'), name: f.properties?.name ?? '', polys, bbox: [b[0]![0], b[0]![1], b[1]![0], b[1]![1]] as [number, number, number, number] }
    })
}

export function dotsFor(feats: Feat[], bbox: [number, number, number, number], cols: number): { dots: Dot[]; step: number } {
  const step = (bbox[2] - bbox[0]) / cols
  const dots: Dot[] = []
  for (let y = bbox[1] + step / 2; y < bbox[3]; y += step) {
    for (let x = bbox[0] + step / 2; x < bbox[2]; x += step) {
      const hit = feats.find((f) => inFeat(x, y, f))
      if (hit) dots.push({ x, y, id: hit.id })
    }
  }
  return { dots, step }
}


/** The national grid in the states-albers viewBox (975 × 610), without Puerto Rico. */
export const NATIONAL_BBOX: [number, number, number, number] = [0, 0, 975, 610]

/** Fetch a us-atlas topology; throws on an HTTP error so callers can show an unavailable state. */
export async function fetchTopo(url: string): Promise<unknown> {
  const r = await fetch(url)
  if (!r.ok) throw new Error(`map shapes ${r.status}`)
  return r.json()
}

/**
 * An area's dot colour (the Overview map, #970): the empty colour for none (or no data), else one of `ramp`'s steps on a log scale of its count against the
 * largest, so the few states with most meetings don't leave the rest looking empty. Never shades a state it has no count for.
 */
export function meetingColor(n: number | null | undefined, max: number, ramp: readonly string[], empty: string): string {
  if (!n || n <= 0 || max <= 0 || ramp.length === 0) return empty
  const t = max === 1 ? 1 : Math.log1p(n) / Math.log1p(max)
  return ramp[Math.min(ramp.length - 1, Math.max(0, Math.ceil(t * ramp.length) - 1))]!
}
