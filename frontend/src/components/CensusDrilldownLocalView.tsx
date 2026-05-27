import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

type Basemap = 'streets' | 'satellite'

interface LocalViewProps {
  center: { lat: number; lng: number }
  zoom?: number
  /** Label shown in a tooltip on the marker. */
  label?: string
  /** "Back to county" or similar button slot — rendered top-left. */
  topLeftSlot?: React.ReactNode
  /** Basemap to show first. Defaults to 'satellite'. */
  initialBasemap?: Basemap
  /** Fires when the user clicks the dropped pin — page handles details lookup. */
  onMarkerClick?: () => void
}

/**
 * Tile providers picked for universal accessibility (no API key, no signed
 * referrer, no rate-limit auth):
 * - OSM for streets: the most widely-cached tile server on the public web.
 * - Esri World Imagery for satellite: hosted on the ArcGIS Online CDN, broad
 *   coverage, attribution-only license. The previous USGS endpoints sometimes
 *   get blocked by network policies or browser extensions, leaving the map
 *   gray with no error.
 */
const STREETS_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png'
const SATELLITE_URL =
  'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'

export default function CensusDrilldownLocalView({
  center,
  zoom = 17,
  label,
  topLeftSlot,
  initialBasemap = 'satellite',
  onMarkerClick,
}: LocalViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<L.Map | null>(null)
  const markerRef = useRef<L.CircleMarker | null>(null)
  const layersRef = useRef<{ streets?: L.TileLayer; satellite?: L.TileLayer; active?: L.TileLayer }>({})
  const [basemap, setBasemap] = useState<Basemap>(initialBasemap)
  const [tileStatus, setTileStatus] = useState<'loading' | 'ok' | 'partial' | 'failed'>('loading')
  const tileErrCountRef = useRef(0)
  const tileLoadCountRef = useRef(0)

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return
    const map = L.map(containerRef.current, {
      center: [center.lat, center.lng],
      zoom,
      zoomControl: true,
      attributionControl: true,
      zoomSnap: 0.5,
    })
    mapRef.current = map

    const wireDiagnostics = (layer: L.TileLayer, name: string) => {
      layer.on('tileerror', (e: any) => {
        tileErrCountRef.current += 1
        const url = e?.tile?.src ?? '(no URL)'
        if (tileErrCountRef.current <= 3) {
          console.warn(`[Local map] tile error on "${name}":`, url)
        }
        if (tileErrCountRef.current > 6 && tileLoadCountRef.current === 0) {
          setTileStatus('failed')
        } else if (tileErrCountRef.current > 3) {
          setTileStatus('partial')
        }
      })
      layer.on('tileload', () => {
        tileLoadCountRef.current += 1
        if (tileStatus !== 'ok' && tileLoadCountRef.current >= 1) {
          setTileStatus(tileErrCountRef.current > 3 ? 'partial' : 'ok')
        }
      })
    }

    const streets = L.tileLayer(STREETS_URL, {
      maxZoom: 19,
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    })
    const satellite = L.tileLayer(SATELLITE_URL, {
      maxZoom: 22,
      maxNativeZoom: 19,
      attribution: 'Imagery © <a href="https://www.esri.com/">Esri</a>, Maxar, Earthstar Geographics',
    })
    wireDiagnostics(streets, 'streets')
    wireDiagnostics(satellite, 'satellite')

    layersRef.current.streets = streets
    layersRef.current.satellite = satellite
    const initial = initialBasemap === 'streets' ? streets : satellite
    initial.addTo(map)
    layersRef.current.active = initial

    // Leaflet needs the container measured to start fetching tiles. The
    // post-mount layout race used to leave the map blank — these calls poke
    // it after the parent's height transitions in.
    map.invalidateSize()
    const t1 = window.setTimeout(() => map.invalidateSize(), 120)
    const t2 = window.setTimeout(() => map.invalidateSize(), 500)
    return () => {
      window.clearTimeout(t1)
      window.clearTimeout(t2)
      map.remove()
      mapRef.current = null
      markerRef.current = null
      layersRef.current = {}
    }
  }, [])

  // Reset diagnostics + switch active layer when basemap toggles.
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    const next = basemap === 'streets' ? layersRef.current.streets : layersRef.current.satellite
    const active = layersRef.current.active
    if (next && next !== active) {
      if (active) map.removeLayer(active)
      next.addTo(map)
      layersRef.current.active = next
      tileErrCountRef.current = 0
      tileLoadCountRef.current = 0
      setTileStatus('loading')
    }
  }, [basemap])

  // Fly to new center / zoom when props change after mount.
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    map.flyTo([center.lat, center.lng], zoom, { duration: 0.9 })
  }, [center.lat, center.lng, zoom])

  // Update marker + label.
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    if (markerRef.current) {
      markerRef.current.setLatLng([center.lat, center.lng])
    } else {
      markerRef.current = L.circleMarker([center.lat, center.lng], {
        // Small enough to not dominate a house-scale aerial, big enough for
        // the click target (Leaflet's hit detection has a few px slop too).
        radius: 4,
        color: '#ffffff',
        weight: 1,
        fillColor: '#b8442c',
        fillOpacity: 0.95,
        className: 'cursor-pointer',
      }).addTo(map)
    }
    if (label) {
      markerRef.current.bindTooltip(label, { direction: 'top', offset: [0, -8] })
    } else {
      markerRef.current.unbindTooltip()
    }
    // Rebind click on every update so the latest onMarkerClick closure is used.
    markerRef.current.off('click')
    if (onMarkerClick) {
      markerRef.current.on('click', () => onMarkerClick())
    }
  }, [center.lat, center.lng, label, onMarkerClick])

  return (
    <div className="relative h-full w-full overflow-hidden rounded-lg border border-slate-200 bg-slate-200 shadow-sm">
      <div ref={containerRef} className="absolute inset-0" />
      {topLeftSlot ? <div className="absolute left-3 top-3 z-[400]">{topLeftSlot}</div> : null}
      <div className="absolute right-3 top-3 z-[400] flex overflow-hidden rounded-md border border-slate-300 bg-white shadow-md">
        <button
          type="button"
          onClick={() => setBasemap('streets')}
          className={`px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide ${
            basemap === 'streets' ? 'bg-slate-900 text-white' : 'text-slate-700 hover:bg-slate-50'
          }`}
        >
          Streets
        </button>
        <button
          type="button"
          onClick={() => setBasemap('satellite')}
          className={`border-l border-slate-200 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide ${
            basemap === 'satellite' ? 'bg-slate-900 text-white' : 'text-slate-700 hover:bg-slate-50'
          }`}
        >
          Satellite
        </button>
      </div>
      {tileStatus === 'failed' ? (
        <div className="pointer-events-auto absolute bottom-6 left-1/2 z-[400] -translate-x-1/2 rounded-md border border-rose-200 bg-white px-3 py-2 text-[12px] text-slate-800 shadow-lg">
          <div className="font-semibold text-rose-700">Tiles failed to load</div>
          <div className="mt-1 leading-snug text-slate-600">
            Your browser couldn't reach the {basemap === 'satellite' ? 'Esri World Imagery' : 'OpenStreetMap'} tile
            server. Likely causes: an ad-blocker / privacy extension blocking <code>arcgisonline.com</code> or{' '}
            <code>openstreetmap.org</code>, a corporate proxy, or no internet.
          </div>
          <div className="mt-1.5 text-[11px] text-slate-500">Check DevTools → Network for the actual error.</div>
        </div>
      ) : null}
      {tileStatus === 'loading' ? (
        <div className="pointer-events-none absolute bottom-3 left-3 z-[400] rounded bg-white/85 px-2 py-1 text-[10px] font-medium uppercase tracking-wide text-slate-600 shadow">
          Loading tiles…
        </div>
      ) : null}
    </div>
  )
}
