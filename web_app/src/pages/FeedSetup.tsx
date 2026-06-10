import { Fragment, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Dialog, Transition } from '@headlessui/react'
import { MapPinIcon, CheckCircleIcon, ExclamationCircleIcon, XMarkIcon } from '@heroicons/react/24/outline'
import api from '../lib/api'
import { useAuth } from '../contexts/AuthContext'
import { toLensSlug, fromLensSlug, toSignalSlug, fromSignalSlug } from '../lib/feedSlugs'

/**
 * FeedSetup — the /feed-setup wizard that captures a personalized "Close to
 * Home" profile: where you live, the value-frames you care about, and the
 * signals to surface. Doubles as an editor (pre-fills from GET /api/feed/config).
 *
 * Presented as a centered modal popup over a dimmed backdrop (not an inline
 * page in the content column). Dismissing it — close button, Esc, or backdrop
 * click — returns to '/'. Saving PUTs the full config (which marks
 * profile_completed=true server-side), then returns to '/' where Close-to-Home
 * is now unlocked.
 *
 * No fabricated data: location suggestions come ONLY from the real geocoder
 * (GET /api/feed/places); an empty/short query shows nothing.
 */

const FONT = { fontFamily: "'DM Sans', sans-serif" } as const

// Value-frames — mirrors StoryLenses VALUE_FRAMES (id/name/emoji) so the wizard
// reads the same as the homepage strip. Saved as backend lens slugs.
const VALUE_FRAMES: { id: string; name: string; em: string }[] = [
  { id: 'family', name: 'Family First', em: '\u{1F46A}' },
  { id: 'faith', name: 'Faith & Community', em: '⛪' },
  { id: 'charitable', name: 'Charitable Impact', em: '\u{1F91D}' },
  { id: 'neighborhood', name: 'Neighborhood Life', em: '\u{1F3D8}\u{FE0F}' },
  { id: 'education', name: 'Education', em: '\u{1F393}' },
  { id: 'economy', name: 'Local Economy', em: '\u{1F4BC}' },
]

// Signals — mirrors StoryLenses LENSES (id/label/emoji). Saved as signal slugs.
const SIGNALS: { id: string; label: string; em: string }[] = [
  { id: 'contested', em: '\u{1F525}', label: 'Contested' },
  { id: 'money', em: '\u{1F4B2}', label: 'Money Moves' },
  { id: 'flags', em: '\u{1F928}', label: 'Raised Eyebrows' },
  { id: 'soon', em: '⚡', label: 'Moving Fast' },
  { id: 'next', em: '\u{1F4C5}', label: 'Watch Next' },
]

// ---- API shapes (mirrors api/routes/feed) ----
type SharedLevel = 'street' | 'district' | 'city' | 'county' | 'state'

interface PlaceHit {
  name: string
  city?: string
  county?: string
  state?: string
  state_code?: string
  latitude: number
  longitude: number
}

interface LocationChip {
  name: string
  shared_level: SharedLevel
  is_primary: boolean
  state_code?: string
  state?: string
  county?: string
  place_fips?: string
  county_fips?: string
  latitude?: number
  longitude?: number
  jurisdiction_id?: string
}

interface FeedConfigOut {
  locations: LocationChip[]
  lenses: string[]
  signals: string[]
  profile_completed: boolean
}

function placeHitToChip(hit: PlaceHit, isPrimary: boolean): LocationChip {
  const display = hit.name || [hit.city, hit.state_code].filter(Boolean).join(', ')
  return {
    name: display,
    shared_level: 'city',
    is_primary: isPrimary,
    state_code: hit.state_code,
    state: hit.state,
    county: hit.county,
    latitude: hit.latitude,
    longitude: hit.longitude,
  }
}

function SignInPanel({ login }: { login: (provider: string) => void }) {
  return (
    <div className="max-w-md mx-auto px-4 py-16 text-center" style={FONT}>
      <div
        className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl text-[32px]"
        style={{ background: 'rgba(26,107,107,0.10)' }}
        aria-hidden
      >
        🏠
      </div>
      <h1 className="mb-2 text-2xl font-bold" style={{ color: '#354F52' }}>
        Sign in to personalize your feed
      </h1>
      <p className="mb-8 text-gray-600">
        Tell us a little about your area and the issues you care about to unlock Close to Home.
      </p>
      <div className="flex flex-col gap-3">
        <button
          type="button"
          onClick={() => login('google')}
          className="w-full rounded-xl border border-gray-300 bg-white px-4 py-3 text-[15px] font-semibold text-gray-700 transition-colors hover:bg-gray-50"
        >
          Continue with Google
        </button>
        <button
          type="button"
          onClick={() => login('facebook')}
          className="w-full rounded-xl border border-gray-300 bg-white px-4 py-3 text-[15px] font-semibold text-gray-700 transition-colors hover:bg-gray-50"
        >
          Continue with Facebook
        </button>
        <button
          type="button"
          onClick={() => login('github')}
          className="w-full rounded-xl border border-gray-300 bg-white px-4 py-3 text-[15px] font-semibold text-gray-700 transition-colors hover:bg-gray-50"
        >
          Continue with GitHub
        </button>
      </div>
    </div>
  )
}

export default function FeedSetup() {
  const navigate = useNavigate()
  const { isAuthenticated, isLoading: authLoading, login, refreshUser } = useAuth()

  const [locations, setLocations] = useState<LocationChip[]>([])
  const [frames, setFrames] = useState<Set<string>>(() => new Set())
  const [signals, setSignals] = useState<Set<string>>(() => new Set())

  // Typeahead state
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<PlaceHit[]>([])
  const [searching, setSearching] = useState(false)

  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)
  const prefilledRef = useRef(false)

  // Pre-fill from saved config once, so the wizard doubles as an editor.
  useEffect(() => {
    if (prefilledRef.current) return
    if (authLoading || !isAuthenticated) return
    prefilledRef.current = true
    let cancelled = false
    api
      .get('/feed/config')
      .then((r) => {
        if (cancelled) return
        const cfg = r.data as FeedConfigOut
        if (Array.isArray(cfg.locations) && cfg.locations.length > 0) {
          setLocations(
            cfg.locations.map((l) => ({
              ...l,
              shared_level: (l.shared_level as SharedLevel) || 'city',
            })),
          )
        }
        const frameIds = (cfg.lenses ?? []).map(fromLensSlug).filter((id): id is string => !!id)
        if (frameIds.length) setFrames(new Set(frameIds))
        const signalIds = (cfg.signals ?? []).map(fromSignalSlug).filter((id): id is string => !!id)
        if (signalIds.length) setSignals(new Set(signalIds))
      })
      .catch(() => {
        // First-time setup or fetch failure — start from an empty form, never
        // fabricate selections.
      })
    return () => {
      cancelled = true
    }
  }, [authLoading, isAuthenticated])

  // Debounced geocoder typeahead (min 3 chars, real hits only).
  useEffect(() => {
    const q = query.trim()
    if (q.length < 3) {
      setResults([])
      setSearching(false)
      return
    }
    setSearching(true)
    const handle = window.setTimeout(() => {
      let cancelled = false
      api
        .get('/feed/places', { params: { q } })
        .then((r) => {
          if (cancelled) return
          setResults(((r.data as { results?: PlaceHit[] })?.results ?? []) as PlaceHit[])
        })
        .catch(() => {
          if (!cancelled) setResults([])
        })
        .finally(() => {
          if (!cancelled) setSearching(false)
        })
      return () => {
        cancelled = true
      }
    }, 300)
    return () => window.clearTimeout(handle)
  }, [query])

  const addLocation = (hit: PlaceHit) => {
    setLocations((prev) => {
      const isPrimary = prev.length === 0
      const chip = placeHitToChip(hit, isPrimary)
      // De-dupe by display name.
      if (prev.some((l) => l.name === chip.name)) return prev
      return [...prev, chip]
    })
    setQuery('')
    setResults([])
  }

  const removeLocation = (name: string) => {
    setLocations((prev) => {
      const next = prev.filter((l) => l.name !== name)
      // Re-anchor primary onto the first remaining chip.
      if (next.length > 0 && !next.some((l) => l.is_primary)) {
        next[0] = { ...next[0], is_primary: true }
      }
      return next
    })
  }

  const toggle = (set: Set<string>, setter: (s: Set<string>) => void, id: string) => {
    const next = new Set(set)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    setter(next)
  }

  const canSave = locations.length > 0 && !saving

  const handleSave = async () => {
    if (!canSave) return
    setSaving(true)
    setSaveError(null)
    const body = {
      locations: locations.map((l) => ({
        name: l.name,
        shared_level: l.shared_level || 'city',
        is_primary: l.is_primary,
        state_code: l.state_code,
        state: l.state,
        county: l.county,
        place_fips: l.place_fips,
        county_fips: l.county_fips,
        latitude: l.latitude,
        longitude: l.longitude,
        jurisdiction_id: l.jurisdiction_id,
      })),
      lenses: Array.from(frames).map(toLensSlug).filter((s): s is string => !!s),
      signals: Array.from(signals).map(toSignalSlug).filter((s): s is string => !!s),
    }
    try {
      await api.put('/feed/config', body)
      // Refresh auth (profile_completed + synced city/state) so Close-to-Home
      // unlocks immediately, then land them back on the homepage.
      await refreshUser()
      navigate('/')
    } catch {
      setSaveError('Could not save your feed. Please try again.')
      setSaving(false)
    }
  }

  // Dismiss the modal (close button, Esc, backdrop) — never trap the user on a
  // bare route; send them back to the homepage. Ignored mid-save.
  const close = () => {
    if (saving) return
    navigate('/')
  }

  return (
    <Transition appear show as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={close} style={FONT}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black/40" />
        </Transition.Child>

        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-start justify-center p-4 sm:items-center">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <Dialog.Panel className="relative flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl bg-white text-left shadow-xl transition-all">
                <button
                  type="button"
                  onClick={close}
                  aria-label="Close"
                  className="absolute right-4 top-4 z-10 text-gray-400 transition-colors hover:text-gray-600"
                >
                  <XMarkIcon className="h-6 w-6" />
                </button>

                <div className="overflow-y-auto px-6 py-8 sm:px-8">
                  {authLoading ? (
                    <div className="px-4 py-16 text-center text-gray-500">Loading…</div>
                  ) : !isAuthenticated ? (
                    <SignInPanel login={login} />
                  ) : (
                    <>
                      <div className="mb-8 pr-8">
                        <Dialog.Title
                          as="h1"
                          className="text-3xl font-bold"
                          style={{ color: '#354F52' }}
                        >
                          Personalize your feed
                        </Dialog.Title>
                        <p className="mt-1 text-gray-600">
                          Set up Close to Home — civic activity near you, on the issues you care about.
                        </p>
                      </div>

                      {/* 1) Where do you live? */}
      <section className="bg-white rounded-lg shadow mb-6">
        <div className="border-b border-gray-200 px-6 py-4">
          <div className="flex items-center gap-2">
            <MapPinIcon className="h-6 w-6 text-gray-600" />
            <h2 className="text-xl font-semibold text-gray-900">Where do you live?</h2>
          </div>
          <p className="text-sm text-gray-500 mt-1">
            Search for your city or town. The first place you add is your primary location.
          </p>
        </div>
        <div className="px-6 py-4">
          {locations.length > 0 && (
            <div className="mb-4 flex flex-wrap gap-2">
              {locations.map((l) => (
                <span
                  key={l.name}
                  className="inline-flex items-center gap-2 rounded-full border border-[#cfe0db] bg-[#eef5f3] px-3 py-1.5 text-sm font-medium text-[#0f2b2b]"
                >
                  <MapPinIcon className="h-4 w-4 text-[#1a6b6b]" aria-hidden />
                  {l.name}
                  {l.is_primary && (
                    <span className="rounded-full bg-[#1a6b6b] px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white">
                      primary
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={() => removeLocation(l.name)}
                    aria-label={`Remove ${l.name}`}
                    className="text-[#56635e] hover:text-[#0f2b2b]"
                  >
                    <XMarkIcon className="h-4 w-4" aria-hidden />
                  </button>
                </span>
              ))}
            </div>
          )}

          <div className="relative">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g., Tuscaloosa, AL"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#1a6b6b]/40"
            />
            {query.trim().length >= 3 && (
              <div className="absolute z-10 mt-1 w-full overflow-hidden rounded-lg border border-gray-200 bg-white shadow-lg">
                {searching ? (
                  <div className="px-4 py-3 text-sm text-gray-400">Searching…</div>
                ) : results.length === 0 ? (
                  <div className="px-4 py-3 text-sm text-gray-400">No matching places.</div>
                ) : (
                  results.map((hit, i) => {
                    const sub = [hit.county, hit.state || hit.state_code].filter(Boolean).join(', ')
                    return (
                      <button
                        key={`${hit.name}-${hit.latitude}-${hit.longitude}-${i}`}
                        type="button"
                        onClick={() => addLocation(hit)}
                        className="flex w-full items-start gap-2 px-4 py-2.5 text-left hover:bg-gray-50"
                      >
                        <MapPinIcon className="mt-0.5 h-4 w-4 shrink-0 text-[#1a6b6b]" aria-hidden />
                        <span>
                          <span className="block text-sm font-medium text-gray-900">{hit.name}</span>
                          {sub && <span className="block text-xs text-gray-500">{sub}</span>}
                        </span>
                      </button>
                    )
                  })
                )}
              </div>
            )}
          </div>
        </div>
      </section>

      {/* 2) What do you care about? (value-frames) */}
      <section className="bg-white rounded-lg shadow mb-6">
        <div className="border-b border-gray-200 px-6 py-4">
          <h2 className="text-xl font-semibold text-gray-900">What do you care about?</h2>
          <p className="text-sm text-gray-500 mt-1">Pick the value-frames that matter to you.</p>
        </div>
        <div className="px-6 py-4 flex flex-wrap gap-2">
          {VALUE_FRAMES.map((f) => {
            const on = frames.has(f.id)
            return (
              <button
                key={f.id}
                type="button"
                onClick={() => toggle(frames, setFrames, f.id)}
                aria-pressed={on}
                className={`inline-flex items-center gap-1.5 rounded-full border px-3.5 py-2 text-sm font-semibold transition-colors ${
                  on
                    ? 'border-[#1a6b6b] bg-[#1a6b6b] text-white'
                    : 'border-gray-300 bg-white text-gray-700 hover:border-[#1a6b6b]'
                }`}
              >
                <span aria-hidden>{f.em}</span>
                {f.name}
              </button>
            )
          })}
        </div>
      </section>

      {/* 3) Signals to surface */}
      <section className="bg-white rounded-lg shadow mb-6">
        <div className="border-b border-gray-200 px-6 py-4">
          <h2 className="text-xl font-semibold text-gray-900">Signals to surface</h2>
          <p className="text-sm text-gray-500 mt-1">
            Which editorial angles should lead your feed?
          </p>
        </div>
        <div className="px-6 py-4 flex flex-wrap gap-2">
          {SIGNALS.map((s) => {
            const on = signals.has(s.id)
            return (
              <button
                key={s.id}
                type="button"
                onClick={() => toggle(signals, setSignals, s.id)}
                aria-pressed={on}
                className={`inline-flex items-center gap-1.5 rounded-full border px-3.5 py-2 text-sm font-semibold transition-colors ${
                  on
                    ? 'border-[#1a6b6b] bg-[#1a6b6b] text-white'
                    : 'border-gray-300 bg-white text-gray-700 hover:border-[#1a6b6b]'
                }`}
              >
                <span aria-hidden>{s.em}</span>
                {s.label}
              </button>
            )
          })}
        </div>
      </section>

      {saveError && (
        <div className="mb-4 flex items-center gap-2 rounded-lg bg-red-50 p-4 text-red-800">
          <ExclamationCircleIcon className="h-5 w-5" />
          <span>{saveError}</span>
        </div>
      )}

      <div className="flex items-center gap-4">
        <button
          type="button"
          onClick={handleSave}
          disabled={!canSave}
          className="inline-flex items-center gap-2 rounded-lg px-6 py-2.5 text-[15px] font-semibold text-white transition-colors disabled:cursor-not-allowed disabled:opacity-50"
          style={{ backgroundColor: '#1a6b6b' }}
        >
          {saving ? (
            'Saving…'
          ) : (
            <>
              <CheckCircleIcon className="h-5 w-5" />
              Save & view my feed
            </>
          )}
        </button>
        {locations.length === 0 && (
          <span className="text-sm text-gray-500">Add at least one location to save.</span>
        )}
      </div>
                    </>
                  )}
                </div>
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>
    </Transition>
  )
}
