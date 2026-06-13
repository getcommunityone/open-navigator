import { useEffect, useMemo, useRef, useState } from 'react'
import { MapContainer, TileLayer, useMap } from 'react-leaflet'
import { useQuery } from '@tanstack/react-query'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import 'leaflet.markercluster'
import 'leaflet.markercluster/dist/MarkerCluster.css'
import api from '../lib/api'

/**
 * Clustered map of every place we index, served by `GET /api/browse/place-map`.
 *
 * Pins are grouped into independently-toggleable levels (state / county / city /
 * school_district), each its own marker-cluster group so clusters never mix
 * levels. Every pin sits on a real census centroid and represents a place with
 * at least one transcript — no fabricated points.
 */

interface PlaceMapPin {
  geoid: string
  name: string
  state_code: string | null
  latitude: number
  longitude: number
  place_count: number
  transcript_count: number
}

interface PlaceMapLevel {
  level: string
  label: string
  count: number
  pins: PlaceMapPin[]
}

interface PlaceMapResponse {
  levels: PlaceMapLevel[]
}

/** Per-level pin / cluster color (distinct, accessible hues). */
const LEVEL_COLORS: Record<string, string> = {
  state: '#7c3aed',          // violet
  county: '#0d9488',         // teal
  city: '#2563eb',           // blue
  school_district: '#d97706', // amber
}
const FALLBACK_COLOR = '#475569'

function levelColor(level: string): string {
  return LEVEL_COLORS[level] ?? FALLBACK_COLOR
}

/** A small colored dot marker for an individual place. */
function pinIcon(color: string): L.DivIcon {
  return L.divIcon({
    className: 'place-cluster-pin',
    html: `<span style="display:block;width:14px;height:14px;border-radius:9999px;background:${color};border:2px solid #fff;box-shadow:0 0 0 1px rgba(0,0,0,0.25)"></span>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
    popupAnchor: [0, -8],
  })
}

/** A colored cluster bubble whose size scales with the child count. */
function clusterIcon(count: number, color: string): L.DivIcon {
  const size = count < 10 ? 34 : count < 100 ? 42 : 50
  return L.divIcon({
    className: 'place-cluster-bubble',
    html:
      `<div style="display:flex;align-items:center;justify-content:center;` +
      `width:${size}px;height:${size}px;border-radius:9999px;color:#fff;` +
      `font-size:13px;font-weight:700;background:${color};` +
      `border:3px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,0.35)">${count}</div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  })
}

/** Popup HTML. State pins deep-link to the filtered places list; individual
 *  places link to their place home. Counts are real (from the warehouse). */
function popupHtml(pin: PlaceMapPin, level: string): string {
  const href =
    level === 'state'
      ? `/jurisdictions?state=${encodeURIComponent(pin.state_code ?? '')}`
      : `/jurisdiction/${encodeURIComponent(pin.geoid)}/meetings`
  const transcripts = `${pin.transcript_count.toLocaleString()} transcript${pin.transcript_count === 1 ? '' : 's'}`
  const places =
    level === 'state'
      ? `<div style="color:#6b7280;font-size:12px;margin-top:2px">${pin.place_count.toLocaleString()} indexed place${pin.place_count === 1 ? '' : 's'}</div>`
      : ''
  return (
    `<div style="min-width:160px">` +
    `<div style="font-weight:700;color:#111827;font-size:14px">${pin.name}</div>` +
    `<div style="color:#6b7280;font-size:12px;margin-top:2px">${transcripts}</div>` +
    places +
    `<a href="${href}" style="display:inline-block;margin-top:8px;color:#0d9488;font-weight:600;font-size:13px;text-decoration:none">View →</a>` +
    `</div>`
  )
}

/** Builds one marker-cluster group per level and toggles each on/off the map. */
function ClusterLayers({
  levels,
  enabled,
}: {
  levels: PlaceMapLevel[]
  enabled: Set<string>
}) {
  const map = useMap()
  const groupsRef = useRef<Record<string, L.MarkerClusterGroup>>({})

  // Rebuild the cluster groups whenever the underlying data changes.
  useEffect(() => {
    // Tear down any previous groups first.
    for (const g of Object.values(groupsRef.current)) {
      if (map.hasLayer(g)) map.removeLayer(g)
      g.clearLayers()
    }
    groupsRef.current = {}

    for (const lvl of levels) {
      const color = levelColor(lvl.level)
      const group = L.markerClusterGroup({
        chunkedLoading: true,
        showCoverageOnHover: false,
        maxClusterRadius: 55,
        iconCreateFunction: (cluster) =>
          clusterIcon(cluster.getChildCount(), color),
      })
      const markers = lvl.pins.map((p) => {
        const m = L.marker([p.latitude, p.longitude], { icon: pinIcon(color) })
        m.bindPopup(popupHtml(p, lvl.level))
        return m
      })
      group.addLayers(markers)
      groupsRef.current[lvl.level] = group
    }

    return () => {
      for (const g of Object.values(groupsRef.current)) {
        if (map.hasLayer(g)) map.removeLayer(g)
      }
    }
  }, [map, levels])

  // Add/remove groups as the enabled set changes.
  useEffect(() => {
    for (const [lvl, g] of Object.entries(groupsRef.current)) {
      if (enabled.has(lvl)) {
        if (!map.hasLayer(g)) map.addLayer(g)
      } else if (map.hasLayer(g)) {
        map.removeLayer(g)
      }
    }
  }, [map, enabled, levels])

  return null
}

/** Keeps the Leaflet canvas correctly sized when its container resizes — e.g.
 *  when the filters panel docks open and the page content reflows narrower. */
function InvalidateOnResize() {
  const map = useMap()
  useEffect(() => {
    const el = map.getContainer()
    const ro = new ResizeObserver(() => map.invalidateSize())
    ro.observe(el)
    return () => ro.disconnect()
  }, [map])
  return null
}

/** Fits the viewport to the pins of the currently-selected levels, so the map
 *  zooms into the selection. Re-fires whenever the selected levels (`enabledKey`)
 *  or the page's state focus (`focusKey`) change — including the initial seed —
 *  but never on plain pan/zoom, so a user's manual navigation between selection
 *  changes is preserved. */
function FitToSelection({
  levels,
  enabled,
  enabledKey,
  focusKey,
}: {
  levels: PlaceMapLevel[]
  enabled: Set<string>
  enabledKey: string
  focusKey: string
}) {
  const map = useMap()
  useEffect(() => {
    const pts: [number, number][] = []
    for (const lvl of levels) {
      if (!enabled.has(lvl.level)) continue
      for (const p of lvl.pins) pts.push([p.latitude, p.longitude])
    }
    if (pts.length) {
      map.fitBounds(L.latLngBounds(pts), { padding: [40, 40], maxZoom: 9 })
    }
    // enabledKey / focusKey drive the re-fit; levels/enabled are read fresh.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, enabledKey, focusKey])
  return null
}

/** Maps a page-level filter id (which includes town / special_district / village)
 *  onto the four map levels. Unmapped ids (special_district, village) have no map
 *  layer and are simply dropped. */
const PAGE_TO_MAP_LEVEL: Record<string, string> = {
  city: 'city',
  town: 'city',
  county: 'county',
  state: 'state',
  school_district: 'school_district',
}

interface PlaceClusterMapProps {
  /** 2-letter state code — restrict pins to this state and zoom to it. */
  filterState?: string
  /** City/locality name — focus the map on this single place and zoom to it. */
  filterCity?: string
  /** Page-level jurisdiction filter ids — restrict the visible map layers. */
  filterLevels?: string[]
}

export default function PlaceClusterMap({
  filterState,
  filterCity,
  filterLevels,
}: PlaceClusterMapProps = {}) {
  const { data, isLoading, error } = useQuery<PlaceMapResponse>({
    queryKey: ['browse-place-map'],
    queryFn: async () => {
      const res = await api.get('/browse/place-map')
      return res.data
    },
    staleTime: 1000 * 60 * 30, // slow-moving index
  })

  const allLevels = useMemo(() => data?.levels ?? [], [data])

  // Restrict pins to the active page filters (when they carry one). The map data
  // is fetched once with every place, so this is an instant client-side narrowing
  // — no refetch — and counts/labels reflect the filtered set.
  const stateCode = (filterState ?? '').trim().toUpperCase()
  const cityName = (filterCity ?? '').trim().toUpperCase()
  const levels = useMemo(() => {
    if (!stateCode && !cityName) return allLevels

    // 1) State narrowing (when a state is selected).
    const stateScoped = allLevels.map((l) => {
      const pins = stateCode
        ? l.pins.filter((p) => (p.state_code ?? '').toUpperCase() === stateCode)
        : l.pins
      return { ...l, pins, count: pins.length }
    })
    if (!cityName) return stateScoped

    // 2) City focus: a selected city should show *that* locality, not every
    //    place in the state. Match pins by name (counties/states have no pin
    //    named for a city, so those layers naturally empty out). If the city
    //    isn't an indexed place, fall back to the state view so the map is
    //    never left blank.
    const cityScoped = stateScoped.map((l) => {
      const pins = l.pins.filter(
        (p) => (p.name ?? '').trim().toUpperCase() === cityName,
      )
      return { ...l, pins, count: pins.length }
    })
    const cityTotal = cityScoped.reduce((sum, l) => sum + l.count, 0)
    return cityTotal > 0 ? cityScoped : stateScoped
  }, [allLevels, stateCode, cityName])

  // Page-level filter ids mapped onto map levels (empty = no level filter).
  const filterKey = (filterLevels ?? []).join(',')
  const mappedLevels = useMemo(() => {
    const ids = (filterLevels ?? [])
      .map((id) => PAGE_TO_MAP_LEVEL[id])
      .filter(Boolean) as string[]
    return new Set(ids)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filterKey])

  // Visible layers: chip-toggleable, but seeded/overridden by the page's level
  // filter so picking levels in the flyout updates the map immediately.
  const [enabled, setEnabled] = useState<Set<string>>(new Set())
  useEffect(() => {
    if (mappedLevels.size > 0) {
      setEnabled(new Set(mappedLevels))
    } else if (allLevels.length) {
      setEnabled(new Set(allLevels.map((l) => l.level)))
    }
  }, [mappedLevels, allLevels])

  const toggle = (level: string) => {
    setEnabled((prev) => {
      const next = new Set(prev)
      if (next.has(level)) next.delete(level)
      else next.add(level)
      return next
    })
  }

  // Stable key for the selected level set — drives the map's zoom-to-selection.
  const enabledKey = useMemo(() => [...enabled].sort().join(','), [enabled])

  const totalPins = useMemo(
    () => levels.reduce((sum, l) => sum + l.count, 0),
    [levels],
  )

  return (
    <div className="bg-white rounded-lg shadow-sm p-5 mb-6">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div>
          <h2 className="text-lg font-bold text-gray-900">Explore the places we index</h2>
          <p className="text-sm text-gray-500">
            {isLoading
              ? 'Loading map…'
              : `${totalPins.toLocaleString()} indexed places — pan, zoom, and click a pin to open it.`}
          </p>
        </div>

        {/* Level filter chips */}
        <div className="flex flex-wrap items-center gap-2">
          {levels.map((lvl) => {
            const on = enabled.has(lvl.level)
            const color = levelColor(lvl.level)
            return (
              <button
                key={lvl.level}
                onClick={() => toggle(lvl.level)}
                className={`flex items-center gap-2 px-3 py-1.5 rounded-full border-2 text-sm font-medium transition-colors ${
                  on
                    ? 'bg-white text-gray-800 shadow-sm'
                    : 'bg-gray-50 text-gray-400 border-gray-200'
                }`}
                style={on ? { borderColor: color } : undefined}
                aria-pressed={on}
              >
                <span
                  className="inline-block w-3 h-3 rounded-full"
                  style={{ backgroundColor: on ? color : '#cbd5e1' }}
                />
                {lvl.label}
                <span className="text-xs text-gray-400">{lvl.count.toLocaleString()}</span>
              </button>
            )
          })}
        </div>
      </div>

      {error ? (
        <div className="h-[440px] flex items-center justify-center rounded-lg bg-gray-50 text-gray-500">
          Map unavailable right now.
        </div>
      ) : (
        <div className="relative z-0 isolate h-[440px] rounded-lg overflow-hidden border border-gray-200">
          <MapContainer
            center={[39.5, -98.35]}
            zoom={4}
            scrollWheelZoom
            style={{ height: '100%', width: '100%' }}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <ClusterLayers levels={levels} enabled={enabled} />
            <InvalidateOnResize />
            <FitToSelection
              levels={levels}
              enabled={enabled}
              enabledKey={enabledKey}
              focusKey={`${stateCode}|${cityName}`}
            />
          </MapContainer>
        </div>
      )}
    </div>
  )
}
