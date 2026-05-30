import { useEffect, useRef, useState } from 'react'
import { MagnifyingGlassIcon, XMarkIcon } from '@heroicons/react/24/outline'
import { nominatimUsStateCode } from '../utils/stateMapping'

/** Smallest geographic unit the search result actually identifies. */
export type MapAddressGranularity = 'state' | 'county' | 'place' | 'address'

export interface MapAddressResult {
  displayName: string
  shortLabel: string
  lat: number
  lon: number
  stateCode: string | null
  county: string
  city: string
  /** Classifies the Nominatim hit so callers can route to the right map tier. */
  granularity: MapAddressGranularity
}

interface MapAddressSearchProps {
  onPick: (result: MapAddressResult) => void
  onClear?: () => void
  initialValue?: string
  className?: string
  placeholder?: string
}

interface NominatimSuggestion {
  osm_id: number
  osm_type: string
  lat: string
  lon: string
  display_name: string
  address?: Record<string, unknown>
  /** Nominatim's coarse classification ("state", "county", "city", "house"…). */
  addresstype?: string
  /** Coarse OSM class ("boundary", "place", "building"…). */
  class?: string
  /** Finer-grained OSM type within the class ("administrative", "city"…). */
  type?: string
}

/**
 * Classify a Nominatim hit into the smallest tier our map can route to.
 *
 * - `state`   when the result IS a state (e.g. "Georgia")
 * - `county`  when the result IS a county (e.g. "Tuscaloosa County")
 * - `place`   when the result is a city/town/village/CDP (e.g. "Tuscaloosa")
 * - `address` when there's a house number, road, or anything finer-grained
 *
 * Nominatim's `addresstype` is the primary signal; we fall back to inspecting
 * the parsed `address` object for ambiguous cases (e.g. a hit on a city named
 * the same as its county).
 */
function classifyGranularity(s: NominatimSuggestion): MapAddressGranularity {
  const at = (s.addresstype ?? '').toLowerCase()
  const cls = (s.class ?? '').toLowerCase()
  const typ = (s.type ?? '').toLowerCase()
  if (at === 'state') return 'state'
  if (at === 'county') return 'county'
  if (at === 'city' || at === 'town' || at === 'village' || at === 'hamlet' || at === 'municipality') {
    return 'place'
  }
  // Boundary-class results without an addresstype: lean on type for state/county.
  if (cls === 'boundary' && typ === 'administrative') {
    const addr = s.address ?? {}
    if ((addr as Record<string, unknown>).state && !(addr as Record<string, unknown>).county) return 'state'
    if ((addr as Record<string, unknown>).county) return 'county'
  }
  // Anything with a house number or road is definitely an address.
  const a = (s.address ?? {}) as Record<string, unknown>
  if (a.house_number || a.road || a.building || a.amenity) return 'address'
  // Place-class hits (neighborhood, suburb…) collapse to the parent place.
  if (cls === 'place') return 'place'
  return 'address'
}

function shortLabelFromAddress(addr: Record<string, unknown> | undefined, fallback: string): string {
  if (!addr) return fallback
  const road = (addr.road as string) || ''
  const houseNumber = (addr.house_number as string) || ''
  const city =
    (addr.city as string) ||
    (addr.town as string) ||
    (addr.village as string) ||
    (addr.hamlet as string) ||
    (addr.municipality as string) ||
    ''
  const state = (addr.state as string) || ''
  const street = [houseNumber, road].filter(Boolean).join(' ').trim()
  const parts = [street, city, state].filter(Boolean)
  return parts.length ? parts.join(', ') : fallback
}

export default function MapAddressSearch({
  onPick,
  onClear,
  initialValue = '',
  className = '',
  placeholder = 'Search address, city, or place',
}: MapAddressSearchProps) {
  const [value, setValue] = useState(initialValue)
  const [suggestions, setSuggestions] = useState<NominatimSuggestion[]>([])
  const [open, setOpen] = useState(false)
  const [activeIdx, setActiveIdx] = useState(-1)
  const [loading, setLoading] = useState(false)
  const debounceRef = useRef<number | null>(null)
  const rootRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current) return
      if (!rootRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  const fetchSuggestions = async (query: string) => {
    if (query.trim().length < 3) {
      setSuggestions([])
      setOpen(false)
      return
    }
    setLoading(true)
    try {
      // Same-origin proxy (api/routes/geocode.py) — avoids Nominatim CORS and
      // honors its 1 req/s policy via server-side throttle + cache.
      const r = await fetch(
        `/api/geocode/search?q=${encodeURIComponent(query)}&limit=6`,
      )
      if (!r.ok) return
      const raw: NominatimSuggestion[] = await r.json()
      const seen = new Set<string>()
      const deduped = raw.filter((s) => {
        const k = `${s.osm_type}_${s.osm_id}`
        if (seen.has(k)) return false
        seen.add(k)
        return true
      })
      setSuggestions(deduped)
      setOpen(deduped.length > 0)
      setActiveIdx(-1)
    } catch {
      // ignore network blips — user can retype
    } finally {
      setLoading(false)
    }
  }

  const handleChange = (v: string) => {
    setValue(v)
    if (debounceRef.current) window.clearTimeout(debounceRef.current)
    debounceRef.current = window.setTimeout(() => fetchSuggestions(v), 280)
  }

  const choose = (s: NominatimSuggestion) => {
    const lat = Number(s.lat)
    const lon = Number(s.lon)
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) return
    const stateCode = nominatimUsStateCode(s.address ?? {}) || null
    const county = ((s.address?.county as string) || '').trim()
    const city =
      ((s.address?.city as string) ||
        (s.address?.town as string) ||
        (s.address?.village as string) ||
        (s.address?.hamlet as string) ||
        (s.address?.municipality as string) ||
        '').trim()
    const shortLabel = shortLabelFromAddress(s.address, s.display_name)
    const granularity = classifyGranularity(s)
    setValue(shortLabel)
    setOpen(false)
    setSuggestions([])
    onPick({
      displayName: s.display_name,
      shortLabel,
      lat,
      lon,
      stateCode,
      county,
      city,
      granularity,
    })
  }

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') {
      setOpen(false)
      return
    }
    if (!open || !suggestions.length) {
      if (e.key === 'Enter') {
        e.preventDefault()
        fetchSuggestions(value)
      }
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActiveIdx((i) => Math.min(suggestions.length - 1, i + 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIdx((i) => Math.max(0, i - 1))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      const pick = activeIdx >= 0 ? suggestions[activeIdx] : suggestions[0]
      if (pick) choose(pick)
    }
  }

  const clear = () => {
    setValue('')
    setSuggestions([])
    setOpen(false)
    setActiveIdx(-1)
    onClear?.()
  }

  return (
    <div ref={rootRef} className={`relative ${className}`}>
      <div className="flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1.5 shadow-md focus-within:border-[#354F52] focus-within:ring-2 focus-within:ring-[#354F52]/30">
        <MagnifyingGlassIcon className="h-4 w-4 shrink-0 text-slate-500" aria-hidden />
        <input
          type="text"
          aria-label="Search address"
          value={value}
          placeholder={placeholder}
          className="min-w-0 flex-1 bg-transparent text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none"
          onChange={(e) => handleChange(e.target.value)}
          onFocus={() => {
            if (suggestions.length) setOpen(true)
          }}
          onKeyDown={onKeyDown}
        />
        {value ? (
          <button
            type="button"
            onClick={clear}
            className="rounded-full p-0.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            aria-label="Clear search"
          >
            <XMarkIcon className="h-4 w-4" />
          </button>
        ) : null}
      </div>
      {open && suggestions.length > 0 ? (
        <ul
          role="listbox"
          className="absolute left-0 right-0 top-[110%] z-40 max-h-72 overflow-auto rounded-xl border border-slate-200 bg-white py-1 shadow-xl"
        >
          {suggestions.map((s, i) => {
            const short = shortLabelFromAddress(s.address, s.display_name)
            const active = i === activeIdx
            return (
              <li key={`${s.osm_type}_${s.osm_id}`}>
                <button
                  type="button"
                  role="option"
                  aria-selected={active}
                  onMouseEnter={() => setActiveIdx(i)}
                  onClick={() => choose(s)}
                  className={`block w-full px-3 py-2 text-left text-sm leading-snug ${
                    active ? 'bg-slate-100 text-slate-900' : 'text-slate-700 hover:bg-slate-50'
                  }`}
                >
                  <div className="font-medium">{short}</div>
                  <div className="mt-0.5 truncate text-xs text-slate-500">{s.display_name}</div>
                </button>
              </li>
            )
          })}
        </ul>
      ) : null}
      {loading ? (
        <div className="pointer-events-none absolute right-10 top-1/2 -translate-y-1/2 text-[10px] text-slate-400">
          …
        </div>
      ) : null}
    </div>
  )
}
