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

export type DrilldownView = 'nation' | 'state' | 'county'

interface Topo {
  type: 'Topology'
  objects: Record<string, unknown>
}

interface StageProps {
  view: DrilldownView
  statesTopo: Topo | null
  countiesTopo: Topo | null
  selectedStateFips: string | null
  selectedCountyGeoid: string | null
  /** Display value (raw / yoy / vs_natl) keyed by 2-digit state FIPS. */
  stateDisplayById: Record<string, number | null>
  /** Display value keyed by 5-digit county GEOID. */
  countyDisplayByGeoid: Record<string, number | null>
  /** Extents for the choropleth ramp (already percentile-clipped). */
  stateChoroExtent: { min: number; max: number }
  countyChoroExtent: { min: number; max: number }
  /** Extents for the bubble size scale. */
  stateBubbleExtent: { min: number; max: number }
  countyBubbleExtent: { min: number; max: number }
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
  /** Click on empty SVG background — reset to nation. */
  onResetToNation: () => void
  /** Optional pinned address (lng/lat). Renders an SVG circle. */
  pinnedLngLat?: { lng: number; lat: number } | null
  /** Highlight the pinned county polygon (when the click-locked card is open). */
  pinnedCountyGeoid?: string | null
  /** Optional state rank by FIPS — passed through to onHoverInfo for the aside card. */
  stateRankById?: Record<string, { rank: number; total: number } | null>
  /** Optional county rank by GEOID — passed through to onHoverInfo for the aside card. */
  countyRankByGeoid?: Record<string, { rank: number; total: number } | null>
  /** Called when the cursor enters/leaves a polygon. The parent renders the
   * hover readout in its own panel (no floating tooltip — keeps the map clean). */
  onHoverInfo?: (
    info: {
      kind: 'state' | 'county'
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

export default function CensusDrilldownStage({
  view,
  statesTopo,
  countiesTopo,
  selectedStateFips,
  selectedCountyGeoid,
  stateDisplayById,
  countyDisplayByGeoid,
  stateChoroExtent,
  countyChoroExtent,
  stateBubbleExtent,
  countyBubbleExtent,
  scale,
  viz,
  onPickState,
  onPickCounty,
  onResetToNation,
  pinnedLngLat = null,
  pinnedCountyGeoid = null,
  stateRankById,
  countyRankByGeoid,
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
    if (view === 'state' && selectedStateFips && states) {
      targetFeature = states.find((f) => fips2(f.id as string | number) === selectedStateFips) ?? null
    } else if (view === 'county' && selectedCountyGeoid && countiesInState) {
      targetFeature =
        countiesInState.find((f) => geoid5(f.id as string | number) === selectedCountyGeoid) ?? null
    }
    if (!targetFeature) {
      // Nation reset.
      select(svgEl).transition().duration(750).call(z.transform as never, zoomIdentity)
      return
    }
    const [[x0, y0], [x1, y1]] = path.bounds(targetFeature as never) as [[number, number], [number, number]]
    const k = Math.min(150, 0.9 / Math.max((x1 - x0) / W, (y1 - y0) / H))
    const tx = W / 2 - k * ((x0 + x1) / 2)
    const ty = H / 2 - k * ((y0 + y1) / 2)
    const next = zoomIdentity.translate(tx, ty).scale(k) as ZoomTransform
    select(svgEl).transition().duration(900).call(z.transform as never, next)
  }, [view, selectedStateFips, selectedCountyGeoid, states, countiesInState])

  // --- fill / bubble helpers (depend on viz + scale + extents) ---
  const stateFill = (sid: string): string => {
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

        {/* hover overlay — re-render the cursor's polygon as a top stroke so
            neighbor polygons can't paint over its shared edges. Fill stays
            transparent (the base layer already has the choropleth color). */}
        {hoveredId
          ? (() => {
              const target =
                (view === 'state' || view === 'county') && countiesInState
                  ? countiesInState.find((f) => geoid5(f.id as string | number) === hoveredId)
                  : states?.find((f) => fips2(f.id as string | number) === hoveredId)
              if (!target) return null
              const d = path(target as never) ?? ''
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

        {/* bubbles overlay */}
        {viz === 'bubble' && states ? (
          <g className="bubbles-layer" pointerEvents="none">
            {(view === 'state' || view === 'county') && countiesInState
              ? countiesInState.map((f) => {
                  const gid = geoid5(f.id as string | number)
                  const v = countyDisplayByGeoid[gid]
                  if (v == null) return null
                  const c = path.centroid(f as never)
                  if (!c || !Number.isFinite(c[0])) return null
                  const r = bubbleRadiusPx(v, countyBubbleExtent.min, countyBubbleExtent.max, scale, 2, 14)
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
                      strokeWidth={0.5}
                    />
                  )
                })
              : states.map((f) => {
                  const sid = fips2(f.id as string | number)
                  const v = stateDisplayById[sid]
                  if (v == null) return null
                  const c = path.centroid(f as never)
                  if (!c || !Number.isFinite(c[0])) return null
                  const r = bubbleRadiusPx(v, stateBubbleExtent.min, stateBubbleExtent.max, scale, 4, 20)
                  const t = metricToDisplayT(v, stateBubbleExtent.min, stateBubbleExtent.max, scale) ?? 0
                  return (
                    <circle
                      key={`bs-${sid}`}
                      cx={c[0]}
                      cy={c[1]}
                      r={r}
                      fill={bubbleFillFromT(t, 0.86)}
                      stroke="#fff"
                      strokeWidth={0.6}
                    />
                  )
                })}
          </g>
        ) : null}

        {/* pinned address marker — projected through Albers */}
        {pinnedLngLat
          ? (() => {
              const xy = ALBERS([pinnedLngLat.lng, pinnedLngLat.lat])
              if (!xy || !Number.isFinite(xy[0])) return null
              return (
                <g transform={`translate(${xy[0]},${xy[1]})`} pointerEvents="none">
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

