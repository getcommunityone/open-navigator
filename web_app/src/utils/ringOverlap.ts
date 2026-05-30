/**
 * 2D polygon-ring helpers used to decide which Census "places" (cities/towns)
 * belong to a drilled-in county. A pure centroid-in-county test misses the
 * common case of a city straddling a county line (Atlanta spans Fulton +
 * DeKalb + Clayton + Cobb): centroid lives in one county, polygon overlaps
 * several. These helpers operate on raw ring arrays so callers can use them
 * in either lng/lat or projected SVG coords — the math is coordinate-system
 * agnostic.
 */

// Matches GeoJSON Position (number[] with optional elevation) — we only read
// [0] and [1], so we don't need a strict tuple type.
export type Ring = ReadonlyArray<ArrayLike<number>>
export type Rings = ReadonlyArray<Ring>
export type Bbox = readonly [number, number, number, number] // [minX, minY, maxX, maxY]

/** Extract every linear ring from a Polygon or MultiPolygon. */
export function ringsOfGeom(geom: GeoJSON.Geometry | null | undefined): Rings {
  if (!geom) return []
  if (geom.type === 'Polygon') return geom.coordinates as unknown as Rings
  if (geom.type === 'MultiPolygon') return (geom.coordinates as number[][][][]).flat() as unknown as Rings
  return []
}

export function bboxOfRings(rings: Rings): Bbox | null {
  let minX = Infinity
  let maxX = -Infinity
  let minY = Infinity
  let maxY = -Infinity
  let n = 0
  for (const r of rings) {
    for (const p of r) {
      if (p[0] < minX) minX = p[0]
      if (p[0] > maxX) maxX = p[0]
      if (p[1] < minY) minY = p[1]
      if (p[1] > maxY) maxY = p[1]
      n++
    }
  }
  return n ? [minX, minY, maxX, maxY] : null
}

export function bboxesOverlap(a: Bbox, b: Bbox): boolean {
  return a[0] <= b[2] && b[0] <= a[2] && a[1] <= b[3] && b[1] <= a[3]
}

/** Even-odd point-in-polygon over a flat ring list. Matches SVG fill rule. */
export function pointInRings(rings: Rings, x: number, y: number): boolean {
  let inside = false
  for (const ring of rings) {
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const xi = ring[i]![0]
      const yi = ring[i]![1]
      const xj = ring[j]![0]
      const yj = ring[j]![1]
      const denom = yj - yi
      if (denom === 0) continue
      const intersect = yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / denom + xi
      if (intersect) inside = !inside
    }
  }
  return inside
}

/**
 * Cheap-and-good-enough polygon overlap: returns true if any vertex of A is
 * inside B, or any vertex of B is inside A. Misses the rare "edges cross but
 * neither has a vertex inside the other" case (two narrow strips crossing
 * orthogonally with no vertices nested). For city/county pairs the polygons
 * are vertex-dense and the only realistic miss would be a sliver — acceptable.
 *
 * Uses a bbox prefilter so the O(|A_verts|·|B|) work only fires on candidates
 * whose bboxes overlap.
 */
export function ringsOverlap(a: Rings, b: Rings): boolean {
  const ab = bboxOfRings(a)
  const bb = bboxOfRings(b)
  if (!ab || !bb || !bboxesOverlap(ab, bb)) return false
  for (const r of a) for (const p of r) if (pointInRings(b, p[0], p[1])) return true
  for (const r of b) for (const p of r) if (pointInRings(a, p[0], p[1])) return true
  return false
}
