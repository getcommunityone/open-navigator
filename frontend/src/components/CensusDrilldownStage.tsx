// @ts-nocheck — d3 + topojson types are loose; we use idiomatic d3 patterns.
import { useEffect, useMemo, useRef, useState } from 'react'
import { select } from 'd3-selection'
import { zoom as d3zoom, zoomIdentity, type ZoomTransform } from 'd3-zoom'
import 'd3-transition'
import { geoAlbersUsa, geoPath } from 'd3-geo'
import { feature, mesh } from 'topojson-client'
import {
  CENSUS_CHORO_FILL_TRANSITION,
  bubbleFillFromT,
  bubbleRadiusPx,
  colorFromT,
  metricToDisplayT,
  type CensusScaleId,
} from '../utils/censusMapTransforms'

const W = 975
const H = 610

const ALBERS = geoAlbersUsa().scale(1300).translate([W / 2, H / 2])
const path = geoPath() // for pre-projected topojson
const projectedPath = geoPath().projection(ALBERS) // for raw lng/lat geometries

export type DrilldownView = 'nation' | 'state' | 'county' | 'place' | 'zip'

interface Topo {
  type: 'Topology'
  objects: Record<string, unknown>
}

interface StageProps {
  view: DrilldownView
  statesTopo: Topo | null
  countiesTopo: Topo | null
  /** Per-state ZCTA topology, loaded lazily when the user drills to ZIP. */
  zctaTopo?: Topo | null
  /**
   * Per-state Census "places" (cities, towns, CDPs) as a raw lng/lat
   * FeatureCollection — output of `export_census_map_static.py --place-states`.
   * Lazy-loaded when the user drills to the place tier.
   */
  placesGeoJson?: GeoJSON.FeatureCollection | null
  selectedStateFips: string | null
  selectedCountyGeoid: string | null
  /** Selected 7-digit place GEOID (when view === 'place' and one is pinned). */
  selectedPlaceGeoid?: string | null
  /** Selected 5-digit ZCTA (when view === 'zip' and one is pinned). */
  selectedZcta?: string | null
  /** Display value (raw / yoy / vs_natl) keyed by 2-digit state FIPS. */
  stateDisplayById: Record<string, number | null>
  /** Display value keyed by 5-digit county GEOID. */
  countyDisplayByGeoid: Record<string, number | null>
  /** Display value keyed by 5-digit ZCTA. Empty when metrics not yet ingested — layer falls back to neutral fill. */
  zctaDisplayByZcta?: Record<string, number | null>
  /** Display value keyed by 7-digit place GEOID. */
  placeDisplayByGeoid?: Record<string, number | null>
  /** GEOIDs of places whose polygon overlaps the drilled-from county. The
   *  parent computes this with polygon-intersect (not just centroid) so
   *  multi-county cities (Atlanta) appear when any of their counties is
   *  pinned. When provided, the stage uses it as the rendering filter
   *  instead of the legacy centroid containment fallback. */
  placeIdsInCounty?: Set<string> | null
  /** Extents for the choropleth ramp (already percentile-clipped). */
  stateChoroExtent: { min: number; max: number }
  countyChoroExtent: { min: number; max: number }
  zctaChoroExtent?: { min: number; max: number }
  placeChoroExtent?: { min: number; max: number }
  /** Extents for the bubble size scale. */
  stateBubbleExtent: { min: number; max: number }
  countyBubbleExtent: { min: number; max: number }
  zctaBubbleExtent?: { min: number; max: number }
  placeBubbleExtent?: { min: number; max: number }
  scale: CensusScaleId
  viz: 'filled' | 'bubble'
  onPickState: (fips: string) => void
  /**
   * County click no longer auto-drills — instead it surfaces a click-locked
   * info card via this callback. The parent owns the card UI and decides
   * whether/how to drill into deeper tiers.
   */
  onPickCounty: (info: {
    geoid: string
    name: string
    value: number | null
    rank: { rank: number; total: number } | null
    lngLat: { lng: number; lat: number } | null
    feature: GeoJSON.Feature
  }) => void
  /** ZIP click — same click-lock pattern as county. */
  onPickZcta?: (info: {
    zcta: string
    value: number | null
    rank: { rank: number; total: number } | null
    lngLat: { lng: number; lat: number } | null
    feature: GeoJSON.Feature
  }) => void
  /** Place click — same click-lock pattern as county. */
  onPickPlace?: (info: {
    geoid: string
    name: string
    value: number | null
    rank: { rank: number; total: number } | null
    lngLat: { lng: number; lat: number } | null
    feature: GeoJSON.Feature
  }) => void
  /** Click on empty SVG background — reset to nation. */
  onResetToNation: () => void
  /** Optional pinned address (lng/lat). Renders an SVG circle. */
  pinnedLngLat?: { lng: number; lat: number } | null
  /** Highlight the pinned county polygon (when the click-locked card is open). */
  pinnedCountyGeoid?: string | null
  /** Highlight the pinned ZCTA polygon. */
  pinnedZcta?: string | null
  /** Highlight the pinned place polygon. */
  pinnedPlaceGeoid?: string | null
  /** ZIP view only: draw the drilled-from county's boundary over the ZCTAs. */
  showCountyOutline?: boolean
  /** Place view: overlay the ZCTA outlines on top of the city polygons so the
   *  user can see which ZIPs each city covers. */
  showZipOutlineInPlace?: boolean
  /** Optional state rank by FIPS — passed through to onHoverInfo for the aside card. */
  stateRankById?: Record<string, { rank: number; total: number } | null>
  /** Optional county rank by GEOID — passed through to onHoverInfo for the aside card. */
  countyRankByGeoid?: Record<string, { rank: number; total: number } | null>
  /** Optional ZCTA rank by ZCTA5. */
  zctaRankByZcta?: Record<string, { rank: number; total: number } | null>
  /** Optional place rank by 7-digit GEOID. */
  placeRankByGeoid?: Record<string, { rank: number; total: number } | null>
  /** Called when the cursor enters/leaves a polygon. The parent renders the
   * hover readout in its own panel (no floating tooltip — keeps the map clean). */
  onHoverInfo?: (
    info: {
      kind: 'state' | 'county' | 'zip' | 'place'
      id: string
      name: string
      value: number | null
      rank: { rank: number; total: number } | null
    } | null,
  ) => void
}

function fips2(id: string | number | undefined): string {
  if (id == null) return ''
  return String(id).padStart(2, '0')
}

function geoid5(id: string | number | undefined): string {
  if (id == null) return ''
  return String(id).padStart(5, '0')
}

/** Flatten a (Multi)Polygon geometry into a flat list of coordinate rings. */
function ringsOf(geom: GeoJSON.Geometry | null | undefined): number[][][] {
  if (!geom) return []
  if (geom.type === 'Polygon') return geom.coordinates as number[][][]
  if (geom.type === 'MultiPolygon') return (geom.coordinates as number[][][][]).flat()
  return []
}

/**
 * Even-odd point-in-polygon (ray casting) over a flat ring list. Exterior +
 * hole rings together give correct containment for polygons-with-holes and
 * non-overlapping multipolygons — matches the SVG fill rule geoPath uses.
 */
function pointInRings(rings: number[][][], x: number, y: number): boolean {
  let inside = false
  for (const ring of rings) {
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const xi = ring[i][0]
      const yi = ring[i][1]
      const xj = ring[j][0]
      const yj = ring[j][1]
      const intersect = yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi
      if (intersect) inside = !inside
    }
  }
  return inside
}

export default function CensusDrilldownStage({
  view,
  statesTopo,
  countiesTopo,
  zctaTopo = null,
  placesGeoJson = null,
  selectedStateFips,
  selectedCountyGeoid,
  selectedPlaceGeoid = null,
  selectedZcta = null,
  stateDisplayById,
  countyDisplayByGeoid,
  zctaDisplayByZcta = {},
  placeDisplayByGeoid = {},
  placeIdsInCounty = null,
  stateChoroExtent,
  countyChoroExtent,
  zctaChoroExtent = { min: 0, max: 1 },
  placeChoroExtent = { min: 0, max: 1 },
  stateBubbleExtent,
  countyBubbleExtent,
  zctaBubbleExtent = { min: 0, max: 1 },
  placeBubbleExtent = { min: 0, max: 1 },
  scale,
  viz,
  onPickState,
  onPickCounty,
  onPickZcta,
  onPickPlace,
  onResetToNation,
  pinnedLngLat = null,
  pinnedCountyGeoid = null,
  pinnedZcta = null,
  pinnedPlaceGeoid = null,
  showCountyOutline = false,
  showZipOutlineInPlace = false,
  stateRankById,
  countyRankByGeoid,
  zctaRankByZcta,
  placeRankByGeoid,
  onHoverInfo,
}: StageProps) {
  const svgRef = useRef<SVGSVGElement | null>(null)
  /**
   * Local-only — tracks the polygon under the cursor so we can render a clear
   * hover stroke. We don't bubble this up to the page (the page already has
   * `onHoverInfo` for the readout) because every cursor move would re-render
   * the whole page if we did.
   */
  const [hoveredId, setHoveredId] = useState<string | null>(null)
  /**
   * Current zoom scale. Always-on ZIP labels live inside the zoomed <g>, so we
   * counter-scale their font by 1/k to keep them a constant on-screen size.
   * Updated only when k actually changes (pure pans don't trigger a re-render).
   */
  const [zoomK, setZoomK] = useState(1)
  const gRef = useRef<SVGGElement | null>(null)
  const zoomBehaviorRef = useRef<ReturnType<typeof d3zoom> | null>(null)

  /** Cached states GeoJSON + interior mesh. */
  const states = useMemo(() => {
    if (!statesTopo) return null
    try {
      const obj = (statesTopo.objects as Record<string, unknown>).states
      return feature(statesTopo as never, obj as never).features as GeoJSON.Feature[]
    } catch {
      return null
    }
  }, [statesTopo])

  const stateInteriorMesh = useMemo(() => {
    if (!statesTopo) return null
    try {
      const obj = (statesTopo.objects as Record<string, unknown>).states
      return mesh(statesTopo as never, obj as never, (a, b) => a !== b) as GeoJSON.MultiLineString
    } catch {
      return null
    }
  }, [statesTopo])

  /** Counties filtered to the selected state. */
  const countiesInState = useMemo(() => {
    if (!countiesTopo || !selectedStateFips) return null
    try {
      const obj = (countiesTopo.objects as Record<string, unknown>).counties
      const all = feature(countiesTopo as never, obj as never).features as GeoJSON.Feature[]
      const prefix = fips2(selectedStateFips)
      return all.filter((f) => geoid5(f.id as string | number).startsWith(prefix))
    } catch {
      return null
    }
  }, [countiesTopo, selectedStateFips])

  /**
   * ZCTAs from the lazy-loaded per-state topology. Output of
   * scripts/frontend/prep_zcta_tiles.sh writes `objects.zctas` with id=GEOID20.
   */
  const zctasInState = useMemo(() => {
    if (!zctaTopo) return null
    try {
      const obj = (zctaTopo.objects as Record<string, unknown>).zctas
      if (!obj) return null
      return feature(zctaTopo as never, obj as never).features as GeoJSON.Feature[]
    } catch {
      return null
    }
  }, [zctaTopo])

  /** The county the user drilled from (pre-projected geometry). */
  const selectedCountyFeature = useMemo(() => {
    if (!selectedCountyGeoid || !countiesInState) return null
    return countiesInState.find((f) => geoid5(f.id as string | number) === selectedCountyGeoid) ?? null
  }, [selectedCountyGeoid, countiesInState])

  /**
   * ZCTAs whose centroid falls inside the selected county. The state tile holds
   * ~650 ZCTAs but a county only touches a few dozen — filtering here cuts the
   * rendered DOM nodes (and hover/zoom work) by ~10-20x. Centroid containment
   * matches the prep script's state-assignment heuristic; ZCTAs that straddle a
   * county line are assigned to whichever county holds their centroid. Falls
   * back to the full state set if no county is selected.
   */
  const zctasInCounty = useMemo(() => {
    if (!zctasInState) return null
    if (!selectedCountyFeature) return zctasInState
    const rings = ringsOf(selectedCountyFeature.geometry)
    if (!rings.length) return zctasInState
    return zctasInState.filter((f) => {
      const c = projectedPath.centroid(f as never)
      if (!c || !Number.isFinite(c[0]) || !Number.isFinite(c[1])) return false
      return pointInRings(rings, c[0], c[1])
    })
  }, [zctasInState, selectedCountyFeature])

  /** All places (lng/lat features) for the selected state. */
  const placesInState = useMemo<GeoJSON.Feature[] | null>(() => {
    if (!placesGeoJson) return null
    return (placesGeoJson.features ?? []) as GeoJSON.Feature[]
  }, [placesGeoJson])

  /**
   * Places to render in the place tier. Prefers the parent-supplied GEOID
   * set (which uses polygon-intersect — handles multi-county cities like
   * Atlanta). Falls back to centroid containment in projected coords when
   * the parent doesn't pass the set, and to the full statewide list when
   * no county is drilled in.
   */
  const placesInCounty = useMemo<GeoJSON.Feature[] | null>(() => {
    if (!placesInState) return null
    if (!selectedCountyFeature) return placesInState
    if (placeIdsInCounty) {
      const filtered = placesInState.filter((f) => {
        const gid = String(f.id ?? (f.properties as { GEOID?: string })?.GEOID ?? '').padStart(7, '0')
        return placeIdsInCounty.has(gid)
      })
      return filtered.length ? filtered : placesInState
    }
    const rings = ringsOf(selectedCountyFeature.geometry)
    if (!rings.length) return placesInState
    return placesInState.filter((f) => {
      const c = projectedPath.centroid(f as never)
      if (!c || !Number.isFinite(c[0]) || !Number.isFinite(c[1])) return false
      return pointInRings(rings, c[0], c[1])
    })
  }, [placesInState, selectedCountyFeature, placeIdsInCounty])

  /** Selected place feature (for camera framing). */
  const selectedPlaceFeature = useMemo<GeoJSON.Feature | null>(() => {
    if (!selectedPlaceGeoid || !placesInState) return null
    const want = String(selectedPlaceGeoid).padStart(7, '0')
    return (
      placesInState.find((f) => String(f.id ?? '').padStart(7, '0') === want) ??
      null
    )
  }, [selectedPlaceGeoid, placesInState])

  /** Install d3-zoom on mount. */
  useEffect(() => {
    const svgEl = svgRef.current
    const gEl = gRef.current
    if (!svgEl || !gEl) return
    const z = d3zoom()
      .scaleExtent([1, 200])
      // clickDistance=10 keeps clicks reliable when the mouse jiggles 1-2px
      // between mousedown/mouseup (default 0 turns those into drags, eating
      // the click — that's the "click to zoom not sticky" symptom).
      .clickDistance(10)
      .on('zoom', (event) => {
        select(gEl).attr('transform', event.transform.toString())
        const k = event.transform.k
        setZoomK((prev) => (Math.abs(prev - k) > 1e-3 ? k : prev))
      })
    zoomBehaviorRef.current = z
    select(svgEl).call(z).on('dblclick.zoom', null)
    return () => {
      select(svgEl).on('.zoom', null)
    }
  }, [])

  /** Drive zoom transform from view + selection (Bostock zoom-to-bbox). */
  useEffect(() => {
    const svgEl = svgRef.current
    const z = zoomBehaviorRef.current
    if (!svgEl || !z) return
    let targetFeature: GeoJSON.Feature | null = null
    // ZCTA tiles are raw lng/lat (need ALBERS); state/county tiles are
    // pre-projected. Track which so we measure the bbox with the right path.
    let targetIsLngLat = false
    if (view === 'state' && selectedStateFips && states) {
      targetFeature = states.find((f) => fips2(f.id as string | number) === selectedStateFips) ?? null
    } else if (view === 'county' && selectedCountyGeoid && countiesInState) {
      targetFeature =
        countiesInState.find((f) => geoid5(f.id as string | number) === selectedCountyGeoid) ?? null
    } else if (view === 'zip') {
      // ZIP view: stay framed on the selected ZCTA if one is pinned, else fall
      // back to the county the user drilled from (keeps the camera anchored).
      if (selectedZcta && zctasInCounty) {
        targetFeature = zctasInCounty.find((f) => String(f.id) === selectedZcta) ?? null
        if (targetFeature) targetIsLngLat = true
      }
      if (!targetFeature && selectedCountyGeoid && countiesInState) {
        targetFeature =
          countiesInState.find((f) => geoid5(f.id as string | number) === selectedCountyGeoid) ?? null
      }
    } else if (view === 'place') {
      // Place view: frame the pinned city/town if one is selected, else the
      // drilled-from county. Mirrors the ZIP tier camera logic.
      if (selectedPlaceFeature) {
        targetFeature = selectedPlaceFeature
        targetIsLngLat = true
      }
      if (!targetFeature && selectedCountyGeoid && countiesInState) {
        targetFeature =
          countiesInState.find((f) => geoid5(f.id as string | number) === selectedCountyGeoid) ?? null
      }
    }
    if (!targetFeature) {
      // Nation reset.
      select(svgEl).transition().duration(750).call(z.transform as never, zoomIdentity)
      return
    }
    const boundsPath = targetIsLngLat ? projectedPath : path
    const [[x0, y0], [x1, y1]] = boundsPath.bounds(targetFeature as never) as [[number, number], [number, number]]
    // Pad the county bbox slightly so the ZIP boundaries don't kiss the SVG
    // edge when we land — gives the postal grid a little breathing room.
    const pad =
      (view === 'zip' && !selectedZcta) || (view === 'place' && !selectedPlaceFeature)
        ? 0.82
        : 0.9
    const k = Math.min(150, pad / Math.max((x1 - x0) / W, (y1 - y0) / H))
    const tx = W / 2 - k * ((x0 + x1) / 2)
    const ty = H / 2 - k * ((y0 + y1) / 2)
    const next = zoomIdentity.translate(tx, ty).scale(k) as ZoomTransform
    // d3-zoom interpolates transforms with interpolateZoom (van Wijk) by
    // default — the long duration when first entering the ZIP tier makes the
    // county-bbox flight read as cinematic; a pinned ZCTA gets a snappier hop.
    const duration =
      view === 'zip'
        ? selectedZcta
          ? 800
          : 1250
        : view === 'place'
          ? selectedPlaceFeature
            ? 800
            : 1250
          : 900
    select(svgEl).transition().duration(duration).call(z.transform as never, next)
  }, [
    view,
    selectedStateFips,
    selectedCountyGeoid,
    selectedZcta,
    selectedPlaceFeature,
    states,
    countiesInState,
    zctasInCounty,
  ])

  // --- fill / bubble helpers (depend on viz + scale + extents) ---
  const stateFill = (sid: string): string => {
    // Sub-state tiers (ZIP / place): the state polygon sits beneath the
    // ZCTAs/places and would otherwise show its statewide choropleth color
    // through every gap, washing out the per-feature fills. Force white so
    // the layer above reads with maximum contrast.
    if (view === 'zip' || view === 'place') return '#ffffff'
    if (viz === 'bubble') return 'rgba(248,250,252,0.94)'
    const v = stateDisplayById[sid]
    const t = metricToDisplayT(v, stateChoroExtent.min, stateChoroExtent.max, scale)
    return colorFromT(t)
  }
  const countyFill = (gid: string): string => {
    if (viz === 'bubble') return 'rgba(248,250,252,0.94)'
    const v = countyDisplayByGeoid[gid]
    const t = metricToDisplayT(v, countyChoroExtent.min, countyChoroExtent.max, scale)
    return colorFromT(t)
  }
  const zctaFill = (z: string): string => {
    if (viz === 'bubble') return 'rgba(248,250,252,0.94)'
    const v = zctaDisplayByZcta[z]
    // Neutral fill when per-ZCTA metric data hasn't been ingested yet — the
    // outline drilldown still works without it.
    if (v == null) return 'rgba(248,250,252,0.40)'
    const t = metricToDisplayT(v, zctaChoroExtent.min, zctaChoroExtent.max, scale)
    return colorFromT(t)
  }
  const placeFill = (g: string): string => {
    if (viz === 'bubble') return 'rgba(248,250,252,0.94)'
    const v = placeDisplayByGeoid[g]
    if (v == null) return 'rgba(248,250,252,0.40)'
    const t = metricToDisplayT(v, placeChoroExtent.min, placeChoroExtent.max, scale)
    return colorFromT(t)
  }

  return (
    <div
      className="relative w-full"
      onMouseLeave={() => onHoverInfo?.(null)}
    >
    <svg
      ref={svgRef}
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="xMidYMid meet"
      className="block h-auto w-full select-none"
      role="img"
      aria-label="Census drill-down map"
      onClick={(e) => {
        // Background click resets to nation. Children stopPropagation.
        if (e.target === e.currentTarget || e.target === svgRef.current) {
          if (view !== 'nation') onResetToNation()
        }
      }}
    >
      <g ref={gRef}>
        {!states ? (
          <text x={W / 2} y={H / 2} textAnchor="middle" fill="#94a3b8" fontSize="14">
            Loading map topology…
          </text>
        ) : null}
        {/* state layer */}
        {states ? (
        <g className="states-layer">
          {states.map((f) => {
            const sid = fips2(f.id as string | number)
            const isSelected = sid === selectedStateFips
            const d = path(f as never) ?? ''
            return (
              <path
                key={sid || (f as { rsmKey?: string }).rsmKey || (f.properties as { name?: string })?.name}
                data-fips={sid}
                d={d}
                onClick={(e) => {
                  e.stopPropagation()
                  onPickState(sid)
                }}
                onMouseEnter={() => {
                  setHoveredId(sid)
                  onHoverInfo?.({
                    kind: 'state',
                    id: sid,
                    name: (f.properties as { name?: string })?.name ?? sid,
                    value: stateDisplayById[sid] ?? null,
                    rank: stateRankById?.[sid] ?? null,
                  })
                }}
                onMouseLeave={() => {
                  setHoveredId((prev) => (prev === sid ? null : prev))
                  onHoverInfo?.(null)
                }}
                style={(() => {
                  const isHovered = hoveredId === sid
                  return {
                    fill: stateFill(sid),
                    stroke: isSelected ? '#b45309' : isHovered ? '#0f172a' : '#6b6661',
                    strokeWidth: isSelected ? 1.5 : isHovered ? 2 : 0.75,
                    cursor: 'pointer',
                    vectorEffect: 'non-scaling-stroke',
                    transition: CENSUS_CHORO_FILL_TRANSITION,
                  }
                })()}
              />

            )
          })}
        </g>
        ) : null}

        {/* interior state mesh — crisp single-stroke borders */}
        {stateInteriorMesh ? (
          <path
            d={path(stateInteriorMesh as never) ?? ''}
            style={{
              fill: 'none',
              stroke: '#3d3a36',
              strokeWidth: 0.6,
              strokeLinejoin: 'round',
              pointerEvents: 'none',
              vectorEffect: 'non-scaling-stroke',
            }}
          />
        ) : null}

        {/* county layer — only when zoomed into a state */}
        {(view === 'state' || view === 'county') && countiesInState ? (
          <g className="counties-layer">
            {countiesInState.map((f) => {
              const gid = geoid5(f.id as string | number)
              const name = (f.properties as { name?: string })?.name ?? gid
              const isPinned = gid === pinnedCountyGeoid
              const d = path(f as never) ?? ''
              const rank = countyRankByGeoid?.[gid] ?? null
              const value = countyDisplayByGeoid[gid] ?? null
              return (
                <path
                  key={gid}
                  data-geoid={gid}
                  d={d}
                  onClick={(e) => {
                    e.stopPropagation()
                    let lngLat: { lng: number; lat: number } | null = null
                    try {
                      const c = path.centroid(f as never)
                      if (c && Number.isFinite(c[0]) && Number.isFinite(c[1])) {
                        const inv = ALBERS.invert?.([c[0], c[1]])
                        if (inv && Number.isFinite(inv[0]) && Number.isFinite(inv[1])) {
                          lngLat = { lng: inv[0], lat: inv[1] }
                        }
                      }
                    } catch {
                      // fall through: caller handles null
                    }
                    onPickCounty({ geoid: gid, name, value, rank, lngLat, feature: f })
                  }}
                  onMouseEnter={() => {
                    setHoveredId(gid)
                    onHoverInfo?.({ kind: 'county', id: gid, name, value, rank })
                  }}
                  onMouseLeave={() => {
                    setHoveredId((prev) => (prev === gid ? null : prev))
                    onHoverInfo?.(null)
                  }}
                  style={(() => {
                    const isHovered = hoveredId === gid
                    return {
                      fill: countyFill(gid),
                      // amber for pinned, near-black for hover, neutral otherwise
                      stroke: isPinned ? '#b45309' : isHovered ? '#0f172a' : '#9a9690',
                      strokeWidth: isPinned ? 1.4 : isHovered ? 1.6 : 0.4,
                      cursor: 'pointer',
                      vectorEffect: 'non-scaling-stroke',
                      transition: CENSUS_CHORO_FILL_TRANSITION,
                    }
                  })()}
                />
              )
            })}
          </g>
        ) : null}

        {/* ZIP layer — only when view === 'zip' and the per-state ZCTA topology
            has been lazy-loaded by the page. Renders under the hover overlay so
            its strokes don't shadow neighbor edges. */}
        {view === 'zip' && zctasInCounty ? (
          <g className="zctas-layer">
            {zctasInCounty.map((f) => {
              const zid = String(f.id ?? (f.properties as { GEOID20?: string; ZCTA5CE20?: string })?.GEOID20 ?? '')
              if (!zid) return null
              const isPinned = zid === pinnedZcta
              // ZCTA geometries are raw lng/lat — project through ALBERS.
              const d = projectedPath(f as never) ?? ''
              const rank = zctaRankByZcta?.[zid] ?? null
              const value = zctaDisplayByZcta[zid] ?? null
              return (
                <path
                  key={zid}
                  d={d}
                  onClick={(e) => {
                    e.stopPropagation()
                    if (!onPickZcta) return
                    let lngLat: { lng: number; lat: number } | null = null
                    try {
                      const c = projectedPath.centroid(f as never)
                      if (c && Number.isFinite(c[0]) && Number.isFinite(c[1])) {
                        const inv = ALBERS.invert?.([c[0], c[1]])
                        if (inv && Number.isFinite(inv[0]) && Number.isFinite(inv[1])) {
                          lngLat = { lng: inv[0], lat: inv[1] }
                        }
                      }
                    } catch {
                      // fall through: caller handles null
                    }
                    onPickZcta({ zcta: zid, value, rank, lngLat, feature: f })
                  }}
                  onMouseEnter={() => {
                    setHoveredId(zid)
                    onHoverInfo?.({ kind: 'zip', id: zid, name: zid, value, rank })
                  }}
                  onMouseLeave={() => {
                    setHoveredId((prev) => (prev === zid ? null : prev))
                    onHoverInfo?.(null)
                  }}
                  style={(() => {
                    const isHovered = hoveredId === zid
                    return {
                      fill: zctaFill(zid),
                      stroke: isPinned ? '#b45309' : isHovered ? '#0f172a' : '#94a3b8',
                      strokeWidth: isPinned ? 1.2 : isHovered ? 1.4 : 0.3,
                      cursor: 'pointer',
                      vectorEffect: 'non-scaling-stroke',
                      transition: CENSUS_CHORO_FILL_TRANSITION,
                    }
                  })()}
                />
              )
            })}
          </g>
        ) : null}

        {/* place layer — cities, towns, CDPs filtered to the drilled-from
            county by centroid containment. Raw lng/lat → projectedPath. */}
        {view === 'place' && placesInCounty ? (
          <g className="places-layer">
            {placesInCounty.map((f) => {
              const gid = String(f.id ?? (f.properties as { GEOID?: string })?.GEOID ?? '').padStart(7, '0')
              if (!gid || gid === '0000000') return null
              const name = (f.properties as { NAME?: string })?.NAME ?? gid
              const isPinned = gid === pinnedPlaceGeoid
              const d = projectedPath(f as never) ?? ''
              const rank = placeRankByGeoid?.[gid] ?? null
              const value = placeDisplayByGeoid[gid] ?? null
              return (
                <path
                  key={gid}
                  d={d}
                  onClick={(e) => {
                    e.stopPropagation()
                    if (!onPickPlace) return
                    let lngLat: { lng: number; lat: number } | null = null
                    try {
                      const c = projectedPath.centroid(f as never)
                      if (c && Number.isFinite(c[0]) && Number.isFinite(c[1])) {
                        const inv = ALBERS.invert?.([c[0], c[1]])
                        if (inv && Number.isFinite(inv[0]) && Number.isFinite(inv[1])) {
                          lngLat = { lng: inv[0], lat: inv[1] }
                        }
                      }
                    } catch {
                      // fall through: caller handles null
                    }
                    onPickPlace({ geoid: gid, name, value, rank, lngLat, feature: f })
                  }}
                  onMouseEnter={() => {
                    setHoveredId(gid)
                    onHoverInfo?.({ kind: 'place', id: gid, name, value, rank })
                  }}
                  onMouseLeave={() => {
                    setHoveredId((prev) => (prev === gid ? null : prev))
                    onHoverInfo?.(null)
                  }}
                  style={(() => {
                    const isHovered = hoveredId === gid
                    return {
                      fill: placeFill(gid),
                      stroke: isPinned ? '#b45309' : isHovered ? '#0f172a' : '#94a3b8',
                      strokeWidth: isPinned ? 1.2 : isHovered ? 1.4 : 0.4,
                      cursor: 'pointer',
                      vectorEffect: 'non-scaling-stroke',
                      transition: CENSUS_CHORO_FILL_TRANSITION,
                    }
                  })()}
                />
              )
            })}
          </g>
        ) : null}

        {/* county outline for the place tier — same opt-in toggle as ZIP. */}
        {view === 'place' && showCountyOutline && selectedCountyFeature ? (
          <path
            d={path(selectedCountyFeature as never) ?? ''}
            pointerEvents="none"
            style={{
              fill: 'none',
              stroke: '#b45309',
              strokeWidth: 1.6,
              strokeLinejoin: 'round',
              strokeDasharray: '4 3',
              vectorEffect: 'non-scaling-stroke',
            }}
          />
        ) : null}

        {/* ZIP outline overlay for the place tier — opt-in. Renders the same
            county-scoped ZCTA set as the ZIP view, but stroke-only so the
            place fills underneath stay visible. ZCTA labels follow so the
            user can read the ZIP code, not just the boundary. */}
        {view === 'place' && showZipOutlineInPlace && zctasInCounty ? (
          <g className="zip-outline-overlay" pointerEvents="none">
            {zctasInCounty.map((f) => {
              const z = String(f.id ?? '')
              const d = projectedPath(f as never) ?? ''
              if (!d) return null
              return (
                <path
                  key={`zip-outline-${z}`}
                  d={d}
                  style={{
                    fill: 'none',
                    stroke: '#475569',
                    strokeWidth: 0.6,
                    strokeDasharray: '2 2',
                    strokeLinejoin: 'round',
                    vectorEffect: 'non-scaling-stroke',
                  }}
                />
              )
            })}
          </g>
        ) : null}
        {view === 'place' && showZipOutlineInPlace && zctasInCounty ? (
          <g className="zip-outline-labels" pointerEvents="none">
            {zctasInCounty.map((f) => {
              const z = String(f.id ?? '')
              if (!z) return null
              const c = projectedPath.centroid(f as never)
              if (!c || !Number.isFinite(c[0]) || !Number.isFinite(c[1])) return null
              const fontSize = 9 / zoomK
              return (
                <text
                  key={`zip-lbl-${z}`}
                  x={c[0]}
                  y={c[1]}
                  textAnchor="middle"
                  dominantBaseline="central"
                  style={{
                    fontSize,
                    fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                    fontWeight: 600,
                    fill: '#475569',
                    stroke: '#ffffff',
                    strokeWidth: fontSize * 0.5,
                    strokeLinejoin: 'round',
                    paintOrder: 'stroke',
                  }}
                >
                  {z}
                </text>
              )
            })}
          </g>
        ) : null}

        {/* always-on place labels — short name (drops the ", State" suffix and
            the trailing "city/town/CDP" classifier) centered at the centroid. */}
        {view === 'place' && placesInCounty ? (
          <g className="place-labels" pointerEvents="none">
            {placesInCounty.map((f) => {
              const gid = String(f.id ?? (f.properties as { GEOID?: string })?.GEOID ?? '').padStart(7, '0')
              if (!gid || gid === '0000000') return null
              const rawName = (f.properties as { NAME?: string })?.NAME ?? ''
              // "Wetumpka city, Alabama" → "Wetumpka"; "Alexander City city, Alabama" → "Alexander City"
              const short = rawName
                .split(',')[0]
                .replace(/\s+(city|town|village|borough|CDP)$/i, '')
                .trim()
              if (!short) return null
              const c = projectedPath.centroid(f as never)
              if (!c || !Number.isFinite(c[0]) || !Number.isFinite(c[1])) return null
              const fontSize = 12 / zoomK
              return (
                <text
                  key={`lbl-${gid}`}
                  x={c[0]}
                  y={c[1]}
                  textAnchor="middle"
                  dominantBaseline="central"
                  style={{
                    fontSize,
                    fontFamily: 'inherit',
                    fontWeight: 600,
                    fill: '#0f172a',
                    stroke: '#ffffff',
                    strokeWidth: fontSize * 0.32,
                    strokeLinejoin: 'round',
                    paintOrder: 'stroke',
                  }}
                >
                  {short}
                </text>
              )
            })}
          </g>
        ) : null}

        {/* county outline (opt-in) — draw the drilled-from county's boundary
            over the ZCTAs so the user can see which ZIPs fall in/near it.
            County geometry is pre-projected → plain `path`. */}
        {view === 'zip' && showCountyOutline && selectedCountyFeature ? (
          <path
            d={path(selectedCountyFeature as never) ?? ''}
            pointerEvents="none"
            style={{
              fill: 'none',
              stroke: '#b45309',
              strokeWidth: 1.6,
              strokeLinejoin: 'round',
              strokeDasharray: '4 3',
              vectorEffect: 'non-scaling-stroke',
            }}
          />
        ) : null}

        {/* always-on ZIP code labels — one per ZCTA, centered. Inside the zoomed
            <g>, so font + halo are counter-scaled by 1/k to read at a constant
            on-screen size. White halo (paint-order stroke) keeps them legible
            over any choropleth fill. */}
        {view === 'zip' && zctasInCounty ? (
          <g className="zcta-labels" pointerEvents="none">
            {zctasInCounty.map((f) => {
              const zid = String(f.id ?? (f.properties as { GEOID20?: string })?.GEOID20 ?? '')
              if (!zid) return null
              const c = projectedPath.centroid(f as never)
              if (!c || !Number.isFinite(c[0]) || !Number.isFinite(c[1])) return null
              // Counter-scale to a constant ~14px on-screen size (10px read too
              // small per user feedback). Stays readable at any zoom level.
              const fontSize = 14 / zoomK
              return (
                <text
                  key={`lbl-${zid}`}
                  x={c[0]}
                  y={c[1]}
                  textAnchor="middle"
                  dominantBaseline="central"
                  style={{
                    fontSize,
                    fontFamily: 'inherit',
                    fontWeight: 600,
                    fill: '#0f172a',
                    stroke: '#ffffff',
                    strokeWidth: fontSize * 0.32,
                    strokeLinejoin: 'round',
                    paintOrder: 'stroke',
                  }}
                >
                  {zid}
                </text>
              )
            })}
          </g>
        ) : null}

        {/* hover overlay — re-render the cursor's polygon as a top stroke so
            neighbor polygons can't paint over its shared edges. Fill stays
            transparent (the base layer already has the choropleth color). */}
        {hoveredId
          ? (() => {
              const isZip = view === 'zip' && !!zctasInCounty
              const isPlace = view === 'place' && !!placesInCounty
              const target = isZip
                ? zctasInCounty!.find((f) => String(f.id) === hoveredId)
                : isPlace
                  ? placesInCounty!.find(
                      (f) => String(f.id ?? '').padStart(7, '0') === hoveredId,
                    )
                  : (view === 'state' || view === 'county') && countiesInState
                    ? countiesInState.find((f) => geoid5(f.id as string | number) === hoveredId)
                    : states?.find((f) => fips2(f.id as string | number) === hoveredId)
              if (!target) return null
              // ZCTA + place geometries are raw lng/lat; everything else is pre-projected.
              const d = (isZip || isPlace ? projectedPath : path)(target as never) ?? ''
              return (
                <path
                  d={d}
                  pointerEvents="none"
                  style={{
                    fill: 'none',
                    stroke: '#0f172a',
                    strokeWidth: hoveredId.length === 5 ? 1.8 : 2.2,
                    vectorEffect: 'non-scaling-stroke',
                  }}
                />
              )
            })()
          : null}

        {/* bubbles overlay — lives inside the zoomed <g>, so radii are
            counter-scaled by 1/zoomK to keep a constant on-screen footprint
            (same trick as the ZIP labels and pinned marker). Without this the
            county-tier bubbles balloon to many times the polygon they sit on.
            ZIP-tier ZCTAs are raw lng/lat (projectedPath) while state/county
            tiles are pre-projected (path) — pick the right path per tier. */}
        {viz === 'bubble' && states ? (
          <g className="bubbles-layer" pointerEvents="none">
            {view === 'place' && placesInCounty
              ? placesInCounty.map((f) => {
                  const gid = String(f.id ?? (f.properties as { GEOID?: string })?.GEOID ?? '').padStart(7, '0')
                  if (!gid || gid === '0000000') return null
                  const v = placeDisplayByGeoid[gid]
                  if (v == null) return null
                  const c = projectedPath.centroid(f as never)
                  if (!c || !Number.isFinite(c[0])) return null
                  const r = bubbleRadiusPx(v, placeBubbleExtent.min, placeBubbleExtent.max, scale, 2, 12) / zoomK
                  const t =
                    metricToDisplayT(v, placeBubbleExtent.min, placeBubbleExtent.max, scale) ?? 0
                  return (
                    <circle
                      key={`bp-${gid}`}
                      cx={c[0]}
                      cy={c[1]}
                      r={r}
                      fill={bubbleFillFromT(t, 0.86)}
                      stroke="#fff"
                      strokeWidth={0.5 / zoomK}
                    />
                  )
                })
              : view === 'zip' && zctasInCounty
              ? zctasInCounty.map((f) => {
                  const zid = String(f.id ?? (f.properties as { GEOID20?: string; ZCTA5CE20?: string })?.GEOID20 ?? '')
                  if (!zid) return null
                  const v = zctaDisplayByZcta[zid]
                  if (v == null) return null
                  const c = projectedPath.centroid(f as never)
                  if (!c || !Number.isFinite(c[0])) return null
                  const r = bubbleRadiusPx(v, zctaBubbleExtent.min, zctaBubbleExtent.max, scale, 2, 12) / zoomK
                  const t =
                    metricToDisplayT(v, zctaBubbleExtent.min, zctaBubbleExtent.max, scale) ?? 0
                  return (
                    <circle
                      key={`bz-${zid}`}
                      cx={c[0]}
                      cy={c[1]}
                      r={r}
                      fill={bubbleFillFromT(t, 0.86)}
                      stroke="#fff"
                      strokeWidth={0.5 / zoomK}
                    />
                  )
                })
              : (view === 'state' || view === 'county') && countiesInState
              ? countiesInState.map((f) => {
                  const gid = geoid5(f.id as string | number)
                  const v = countyDisplayByGeoid[gid]
                  if (v == null) return null
                  const c = path.centroid(f as never)
                  if (!c || !Number.isFinite(c[0])) return null
                  const r = bubbleRadiusPx(v, countyBubbleExtent.min, countyBubbleExtent.max, scale, 2, 14) / zoomK
                  const t =
                    metricToDisplayT(v, countyBubbleExtent.min, countyBubbleExtent.max, scale) ?? 0
                  return (
                    <circle
                      key={`bc-${gid}`}
                      cx={c[0]}
                      cy={c[1]}
                      r={r}
                      fill={bubbleFillFromT(t, 0.86)}
                      stroke="#fff"
                      strokeWidth={0.5 / zoomK}
                    />
                  )
                })
              : states.map((f) => {
                  const sid = fips2(f.id as string | number)
                  const v = stateDisplayById[sid]
                  if (v == null) return null
                  const c = path.centroid(f as never)
                  if (!c || !Number.isFinite(c[0])) return null
                  const r = bubbleRadiusPx(v, stateBubbleExtent.min, stateBubbleExtent.max, scale, 4, 20) / zoomK
                  const t = metricToDisplayT(v, stateBubbleExtent.min, stateBubbleExtent.max, scale) ?? 0
                  return (
                    <circle
                      key={`bs-${sid}`}
                      cx={c[0]}
                      cy={c[1]}
                      r={r}
                      fill={bubbleFillFromT(t, 0.86)}
                      stroke="#fff"
                      strokeWidth={0.6 / zoomK}
                    />
                  )
                })}
          </g>
        ) : null}

        {/* pinned address marker — projected through Albers. Lives inside the
            zoomed <g>, so counter-scale by 1/k (same trick as the ZIP labels)
            to keep a constant on-screen size; without this it balloons at the
            high zoom levels the ZIP tier reaches. */}
        {pinnedLngLat
          ? (() => {
              const xy = ALBERS([pinnedLngLat.lng, pinnedLngLat.lat])
              if (!xy || !Number.isFinite(xy[0])) return null
              const s = 1 / zoomK
              return (
                <g transform={`translate(${xy[0]},${xy[1]}) scale(${s})`} pointerEvents="none">
                  <circle r={11} fill="rgba(244, 63, 94, 0.18)" />
                  <circle r={6.5} fill="#f43f5e" stroke="#ffffff" strokeWidth={2} />
                  <circle r={2.2} fill="#ffffff" />
                </g>
              )
            })()
          : null}
      </g>
    </svg>
    </div>
  )
}

