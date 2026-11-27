import { useState, type FormEvent } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useLocation as useLocationContext, type LocationData } from '../contexts/LocationContext'
import { PLACE_PICK_STATE, usePlacePick } from '../hooks/usePlacePick'
import { phonePlaceState, searchForScope, type PhonePlaceState } from '../utils/headerPlace'
import { resolveZipToChoices } from '../utils/resolvePlace'

export interface HeaderPlacePhoneViewProps {
  state: PhonePlaceState
  /** The ZIP field shows (no town yet, or the reader tapped the active town to change it). */
  editing: boolean
  zip: string
  busy: boolean
  error: string | null
  /** A ZIP that spans places: its real choices (from the geocoder), to pick one. */
  choices: { label: string; loc: LocationData }[] | null
  onZip: (zip: string) => void
  onSubmit: () => void
  onCancel: () => void
  onPickChoice: (loc: LocationData) => void
  onToggle: (target: 'place' | 'national') => void
  onEdit: () => void
}

/**
 * The phone header's location selector (#1301), as markup only: the pin + ZIP field, or the town / National toggle. The
 * owner asked for it in the header on every page, in the simple pin + ZIP form, with one tap to National and back.
 */
export function HeaderPlacePhoneView(p: HeaderPlacePhoneViewProps) {
  const zipForm = p.state.mode === 'zip' || p.editing
  return (
    <div className="sh-pphone" data-testid="header-place-phone">
      {zipForm ? (
        <form
          className="sh-pzip"
          role="search"
          aria-label="Your ZIP code"
          onSubmit={(e: FormEvent) => {
            e.preventDefault()
            p.onSubmit()
          }}
        >
          <span aria-hidden="true">📍</span>
          <input
            className="sh-pzip-input"
            type="text"
            inputMode="numeric"
            autoComplete="postal-code"
            pattern="[0-9]{5}"
            maxLength={5}
            placeholder="ZIP"
            aria-label="ZIP code"
            value={p.zip}
            disabled={p.busy}
            onChange={(e) => p.onZip(e.target.value.replace(/\D/g, '').slice(0, 5))}
          />
          <button type="submit" className="sh-pzip-go" disabled={p.busy || p.zip.length !== 5} aria-label="Go to this ZIP">
            {p.busy ? '…' : 'Go'}
          </button>
          {p.state.mode === 'toggle' && (
            <button type="button" className="sh-pzip-cancel" aria-label="Keep the current place" onClick={p.onCancel}>
              ✕
            </button>
          )}
        </form>
      ) : p.state.mode === 'toggle' ? (
        <div className="sh-ptoggle" role="group" aria-label="Place for this page">
          <button
            type="button"
            className="sh-ptoggle-btn"
            data-side="place"
            aria-pressed={p.state.active === 'place'}
            title={p.state.active === 'place' ? 'Change your ZIP' : `Show ${p.state.place}`}
            onClick={() => (p.state.mode === 'toggle' && p.state.active === 'place' ? p.onEdit() : p.onToggle('place'))}
          >
            <span aria-hidden="true">📍</span>
            <span className="sh-ptoggle-text">{p.state.place}</span>
          </button>
          {p.state.canToggle && (
            <button
              type="button"
              className="sh-ptoggle-btn"
              data-side="national"
              aria-pressed={p.state.active === 'national'}
              title="Show national data"
              onClick={() => p.state.mode === 'toggle' && p.state.active !== 'national' && p.onToggle('national')}
            >
              National
            </button>
          )}
        </div>
      ) : null}
      {(p.error || (p.choices && p.choices.length > 1)) && (
        <div className="sh-pzip-pop" role="status">
          {p.error && <p className="sh-pzip-error">{p.error}</p>}
          {p.choices && p.choices.length > 1 && (
            <>
              <p className="sh-pzip-note">{p.zip} crosses places. Which is home?</p>
              {p.choices.map((c, i) => (
                <button key={c.label + i} type="button" className="sh-pzip-choice" onClick={() => p.onPickChoice(c.loc)}>
                  {c.label}
                </button>
              ))}
            </>
          )}
        </div>
      )}
    </div>
  )
}

/** The selector wired to the router and the saved location. Shown in the header below the menu breakpoint. */
export default function HeaderPlacePhone() {
  const routerLocation = useLocation()
  const navigate = useNavigate()
  const { location: saved } = useLocationContext()
  const pickPlace = usePlacePick()
  const [editing, setEditing] = useState(false)
  const [zip, setZip] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [choices, setChoices] = useState<{ label: string; loc: LocationData }[] | null>(null)
  const search = new URLSearchParams(routerLocation.search)
  const state = phonePlaceState(routerLocation.pathname, search, saved)

  const reset = () => {
    setEditing(false)
    setZip('')
    setError(null)
    setChoices(null)
  }
  const commit = (loc: LocationData) => {
    reset()
    pickPlace(loc)
  }
  const submit = async () => {
    if (!/^\d{5}$/.test(zip)) {
      setError('Enter a 5-digit ZIP code.')
      return
    }
    setBusy(true)
    setError(null)
    setChoices(null)
    try {
      const opts = await resolveZipToChoices(zip)
      if (opts.length === 0) setError("We couldn't find that ZIP.")
      else if (opts.length === 1) commit(opts[0]!.loc)
      else setChoices(opts)
    } catch {
      setError("We couldn't look up that ZIP right now. Try again.")
    } finally {
      setBusy(false)
    }
  }
  const toggle = (target: 'place' | 'national') => {
    const next = searchForScope(routerLocation.pathname, search, target, saved)
    if (next.toString() === search.toString()) return
    const qs = next.toString()
    // The same pick marker as a town pick: Layout remounts the page once this URL commits, so label and data move together.
    navigate(`${routerLocation.pathname}${qs ? `?${qs}` : ''}${routerLocation.hash}`, {
      replace: routerLocation.pathname === '/',
      state: { [PLACE_PICK_STATE]: Date.now() },
    })
  }

  return (
    <HeaderPlacePhoneView
      state={state}
      editing={editing}
      zip={zip}
      busy={busy}
      error={error}
      choices={choices}
      onZip={(z) => {
        setZip(z)
        setError(null)
        setChoices(null)
      }}
      onSubmit={() => void submit()}
      onCancel={reset}
      onPickChoice={commit}
      onToggle={toggle}
      onEdit={() => setEditing(true)}
    />
  )
}
