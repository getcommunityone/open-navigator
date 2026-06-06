import { useMemo, useState } from 'react'
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet'
import { useQuery } from '@tanstack/react-query'
import api from '../lib/api'
import { withSpan } from '../instrumentation'
import { STATE_CODES } from '../lib/usStates'
import 'leaflet/dist/leaflet.css'

/**
 * A single geocoded civic-decision pin from `GET /decisions/map`.
 *
 * NOTE: this maps the `event_decision` mart, NOT `event_policy_decision`. The
 * `/decisions/{id}` detail route resolves against a *different* mart, so the
 * popup here is intentionally display-only — do not deep-link `event_decision_id`
 * to that page (it will 404).
 */
interface DecisionPin {
  event_decision_id: number | string
  decision_id: number | string | null
  place_id: number | string | null
  latitude: number
  longitude: number
  headline: string | null
  primary_theme: string | null
  outcome: string | null
  vote_tally: string | null
  jurisdiction_name: string | null
  state_code: string | null
  /** Wire calendar values can arrive as ISO date strings; treat as display text. */
  event_date: string | null
  normalized_address: string | null
  is_primary: boolean | null
}

/**
 * Controlled-vocabulary `primary_theme` → color. Labels mirror the canonical
 * theme strings used elsewhere in the app (see Home.tsx cause icon map). Any
 * theme not listed (or null) falls back to a neutral slate.
 */
const THEME_COLORS: Record<string, string> = {
  'Fiscal and Budget Management': '#16a34a',
  'Zoning and Land Use': '#9333ea',
  'Infrastructure and Capital Projects': '#ea580c',
  'Economic Development and Business': '#0d9488',
  'Social Protection': '#db2777',
  'Recreation, Culture, and Religion': '#d97706',
  Recreation: '#d97706',
  'General Public Services': '#2563eb',
  'Governance and Administrative Policy': '#2563eb',
  'Public Engagement and Communications': '#0891b2',
  Defense: '#64748b',
  Transportation: '#dc2626',
}
const FALLBACK_COLOR = '#475569'

function themeColor(theme: string | null): string {
  if (!theme) return FALLBACK_COLOR
  return THEME_COLORS[theme] ?? FALLBACK_COLOR
}

/** Center of the contiguous US, matching the Heatmap reference. */
const US_CENTER: [number, number] = [39.8283, -98.5795]

export default function DecisionsMapPage() {
  const [selectedState, setSelectedState] = useState<string>('')
  const [selectedTheme, setSelectedTheme] = useState<string>('')

  const {
    data: pins,
    isLoading,
    isError,
  } = useQuery<DecisionPin[]>({
    queryKey: ['decisions-map', selectedState, selectedTheme],
    queryFn: async () => {
      const params: Record<string, string> = { limit: '1000' }
      if (selectedState) params.state = selectedState
      if (selectedTheme) params.theme = selectedTheme
      // Trace the data load with low-cardinality attributes only.
      return withSpan(
        'decisions_map.fetch',
        async () => {
          const response = await api.get('/decisions/map', { params })
          // Tolerate both a bare array and an envelope ({ decisions: [...] }).
          const data = response.data
          if (Array.isArray(data)) return data as DecisionPin[]
          if (Array.isArray(data?.decisions)) return data.decisions as DecisionPin[]
          if (Array.isArray(data?.pins)) return data.pins as DecisionPin[]
          return [] as DecisionPin[]
        },
        {
          'decisions_map.has_state': !!selectedState,
          'decisions_map.has_theme': !!selectedTheme,
        },
      )
    },
  })

  // Only pins with finite coordinates are renderable — the backend returns a
  // handful of geocoded rows today, the rest get filtered out here defensively.
  const geocoded = useMemo(
    () =>
      (pins ?? []).filter(
        (p) =>
          typeof p.latitude === 'number' &&
          typeof p.longitude === 'number' &&
          Number.isFinite(p.latitude) &&
          Number.isFinite(p.longitude),
      ),
    [pins],
  )

  // Theme legend: the canonical themes that actually appear in the data, so the
  // legend stays relevant as the geocode backfill grows.
  const presentThemes = useMemo(() => {
    const set = new Set<string>()
    for (const p of geocoded) if (p.primary_theme) set.add(p.primary_theme)
    return Array.from(set).sort()
  }, [geocoded])

  const onStateChange = (v: string) =>
    withSpan('decisions_map.filter_state', () => setSelectedState(v), {
      'decisions_map.has_state': !!v,
    })
  const onThemeChange = (v: string) =>
    withSpan('decisions_map.filter_theme', () => setSelectedTheme(v), {
      'decisions_map.has_theme': !!v,
    })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Civic Decisions Map</h1>
        <p className="mt-1 text-sm text-gray-600">
          Geocoded local-government decisions nationwide, colored by policy theme.
          Coverage grows as the address geocode backfill runs.
        </p>
      </div>

      {/* Filters */}
      <div className="card flex flex-col gap-4 sm:flex-row">
        <div className="flex-1">
          <label className="mb-2 block text-sm font-medium text-gray-700">
            Filter by State
          </label>
          <select
            className="block w-full rounded-md border-gray-300 text-gray-900 shadow-sm focus:border-primary-500 focus:ring-primary-500"
            value={selectedState}
            onChange={(e) => onStateChange(e.target.value)}
          >
            <option value="">All States</option>
            {STATE_CODES.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </select>
        </div>

        <div className="flex-1">
          <label className="mb-2 block text-sm font-medium text-gray-700">
            Filter by Theme
          </label>
          <select
            className="block w-full rounded-md border-gray-300 text-gray-900 shadow-sm focus:border-primary-500 focus:ring-primary-500"
            value={selectedTheme}
            onChange={(e) => onThemeChange(e.target.value)}
          >
            <option value="">All Themes</option>
            {Object.keys(THEME_COLORS).map((theme) => (
              <option key={theme} value={theme}>
                {theme}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Legend — only themes present in the current view */}
      {presentThemes.length > 0 && (
        <div className="card">
          <h3 className="mb-3 text-sm font-medium text-gray-700">Policy Theme</h3>
          <div className="flex flex-wrap gap-x-6 gap-y-2">
            {presentThemes.map((theme) => (
              <div key={theme} className="flex items-center gap-2">
                <span
                  className="inline-block h-4 w-4 rounded-full"
                  style={{ backgroundColor: themeColor(theme) }}
                />
                <span className="text-sm text-gray-700">{theme}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Map */}
      <div className="card relative h-[600px]">
        <MapContainer
          center={US_CENTER}
          zoom={4}
          scrollWheelZoom={false}
          style={{ height: '100%', width: '100%' }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {geocoded.map((p) => (
            <CircleMarker
              key={String(p.event_decision_id)}
              center={[p.latitude, p.longitude]}
              radius={p.is_primary ? 9 : 7}
              pathOptions={{
                fillColor: themeColor(p.primary_theme),
                fillOpacity: 0.75,
                color: themeColor(p.primary_theme),
                weight: 2,
              }}
            >
              <Popup>
                <div className="min-w-[260px] p-1">
                  <h4 className="font-bold text-gray-900">
                    {p.headline || 'Untitled decision'}
                  </h4>
                  {p.primary_theme && (
                    <p className="mt-2 text-sm text-gray-700">
                      <strong>Theme:</strong> {p.primary_theme}
                    </p>
                  )}
                  {p.outcome && (
                    <p className="text-sm text-gray-700">
                      <strong>Outcome:</strong> {p.outcome}
                    </p>
                  )}
                  {p.vote_tally && (
                    <p className="text-sm text-gray-700">
                      <strong>Vote:</strong> {p.vote_tally}
                    </p>
                  )}
                  {p.jurisdiction_name && (
                    <p className="text-sm text-gray-700">
                      <strong>Jurisdiction:</strong> {p.jurisdiction_name}
                      {p.state_code ? `, ${p.state_code}` : ''}
                    </p>
                  )}
                  {p.event_date && (
                    <p className="text-sm text-gray-700">
                      <strong>Date:</strong> {p.event_date}
                    </p>
                  )}
                  {p.normalized_address && (
                    <p className="mt-1 text-xs text-gray-500">{p.normalized_address}</p>
                  )}
                </div>
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>

        {/* Overlay states — non-blocking, sit above the map chrome */}
        {isLoading && (
          <div className="pointer-events-none absolute inset-0 z-[1000] flex items-center justify-center bg-white/60">
            <span className="text-sm font-medium text-gray-700">Loading decisions…</span>
          </div>
        )}
        {!isLoading && isError && (
          <div className="pointer-events-none absolute inset-x-0 top-2 z-[1000] mx-auto w-fit rounded-md bg-red-50 px-3 py-1.5 text-sm text-red-700 shadow">
            Couldn’t load decisions. Try again.
          </div>
        )}
        {!isLoading && !isError && geocoded.length === 0 && (
          <div className="pointer-events-none absolute inset-x-0 top-2 z-[1000] mx-auto w-fit rounded-md bg-amber-50 px-3 py-1.5 text-sm text-amber-800 shadow">
            No geocoded decisions in view
            {selectedState ? ` for ${selectedState}` : ''}
            {selectedTheme ? ` · ${selectedTheme}` : ''}.
          </div>
        )}
      </div>

      {/* Summary */}
      <div className="card">
        <h3 className="mb-2 text-lg font-semibold">Summary</h3>
        <p className="text-gray-600">
          Showing <strong>{geocoded.length}</strong> geocoded decision
          {geocoded.length === 1 ? '' : 's'}
          {selectedState && ` in ${selectedState}`}
          {selectedTheme && ` · ${selectedTheme}`}.
        </p>
      </div>
    </div>
  )
}
